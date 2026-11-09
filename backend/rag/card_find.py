"""카드(표 행 청크)를 읽어 숫자 조건에 맞는 부품 찾기: 사양 표(part_specifications) 없이 `spec_lookup.find_candidates`와 같은 계약.

- 역할: `make_find(...)`가 돌려주는 find(conditions, category, package, limit, original_packages, original_category)는
  조건으로 검색 문장 하나를 만들어 검색하고(retrieve 1번), 앞 문서 n_docs개의 표 행 카드를 읽어(card_read.read_values, LLM 1번)
  사양 행을 얻은 뒤 find_candidates와 같은 규칙으로 거르고(모든 조건을 행 하나 이상이 채움) 줄 세운다
  (원래 부품의 패키지 → 원래 부품의 분류 → 기준에 가까운 순 → 품번 순). 반환 모양도 같다: [{'part', 'category', 'packages', 'matches'}].
  `default_find()`는 실제 검색 · DB(DATABASE_URL) · 카드 읽기 · node_chat을 묶는다. 테스트는 make_find에 가짜를 넘긴다.
- 하지 않는 일: 판정 · 대체 가능 여부(`backend/judge/`, AGENTS 지킬 것 7), 카드 값 읽기와 원문 대조(`card_read.py`),
  단위 환산(조건 · 행 값은 이미 SI), LLM 직접 호출(chat을 받아 넘긴다). 비교는 행을 거르는 >= · <=와 순서 비율뿐이다(spec_lookup과 같음).
- 출처: `spec_lookup.find_candidates`(ADR 0013, SPEC.md 8.7), lab v3 사양 표 제거(part_specifications가 빈 sojafit_v4)

[주의] 검색에 걸린 앞 문서 n_docs개만 본다. 여기서 빠진 품번은 "조건 불충족"이 아니라 "못 찾음"이다(spec_lookup과 같은 뜻).
"""
import contextvars
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlparse

from pydantic import BaseModel, Field

from backend.rag.pipeline.specs import AEC_H, BOTH_DIRECTIONS, KEYWORDS, SI, SYMS, packages_of
from backend.rag.retrieve import COVER
from backend.rag.spec_lookup import DEFAULT_SLOT, _norm_package, _ratio

# 코드 → 검색 문장에 넣을 설명 낱말 + 기호(데이터시트 표의 PARAMETER · SYMBOL 칸 말투)
WORDS = {'VRRM': 'repetitive peak reverse voltage VRRM', 'VR': 'DC reverse voltage VR', 'VRWM': 'reverse stand-off voltage VRWM',
         'VBR': 'breakdown voltage VBR', 'VC': 'clamping voltage VC', 'VZ': 'zener voltage VZ', 'VF': 'forward voltage VF',
         'VESD': 'ESD voltage VESD', 'IF_AV': 'average forward current IF(AV)', 'IFSM': 'peak forward surge current IFSM',
         'IR': 'reverse leakage current IR', 'IPP': 'peak pulse current IPP', 'PD': 'power dissipation PD',
         'PPPM': 'peak pulse power PPPM', 'TRR': 'reverse recovery time trr', 'CJ': 'junction capacitance CJ',
         'TJ_MAX': 'operating junction temperature TJ'}
# [왜] 데이터시트는 0.001 A를 1 mA로 적는다. 1 이상은 기본 단위 그대로 둔다(정류 다이오드 표는 1 kV가 아니라 1000 V로 적는다)
PREFIX = ((1, ''), (1e-3, 'm'), (1e-6, 'µ'), (1e-9, 'n'), (1e-12, 'p'))
K_SEARCH = 40  # 검색해서 볼 청크 수. 문서 n_docs개를 고르는 재료다
# shortcut: 문서 하나에서 카드는 60장까지만 읽힌다(제너 표처럼 품번이 수십 개면 뒤 행이 잘릴 수 있다). 잘려서 못 찾는 문항이 나오면 문서 안에서 다시 나눈다
MAX_CARDS = 60


def natural(value, unit):
    """SI 값 → 데이터시트 말투('0.001', 'A' → '1 mA', 3e-08 s → '30 ns'). 온도는 °C."""
    if unit == 'degC':
        return f'{value:g} °C'
    scale, prefix = next(((s, p) for s, p in PREFIX if abs(value) >= s), PREFIX[-1])
    return f'{value / scale:g} {prefix}{unit}'


def search_sentence(conditions, category=None, package=None):
    """조건 → 검색 문장 하나(코드마다 낱말 + 기호 + 경계 값, 그 뒤에 분류 낱말 · 패키지 이름)."""
    by_code = {}  # 코드 → 경계 값 글들. [왜] 제너 VZ 최소 · 최대처럼 같은 코드 조건이 둘이면 낱말은 한 번만 쓴다
    for c in conditions:
        unit = SI.get(c['code'])
        by_code.setdefault(c['code'], []).extend(natural(c[k], unit) for k in ('gte', 'lte') if k in c and unit)
    pieces = [' '.join([WORDS.get(code, code), *values]) for code, values in by_code.items()]
    if category:
        pieces.append(category.replace('-', ' '))  # 'zener-diode' → 'zener diode'
    if package:
        pieces.append(package)
    return ', '.join(pieces)


def mentions(text, codes):
    """카드 글이 codes 중 하나의 기호나 설명 낱말을 담는지(LLM에 넘길 카드를 줄이는 거친 거르기, 값은 보지 않는다)."""
    # [주의] 시험 조건의 기호(VF 행의 'IF = 1A')도 걸린다. 넘치게 넘기는 쪽이라 괜찮다(빠뜨리면 못 찾는다)
    symbols = re.findall(r'[A-Z][A-Z0-9()]*', text.upper())
    return any(SYMS.get(s) in codes for s in symbols) or any(code in codes and p.search(text) for p, code in KEYWORDS)


def doc_packages(doc):
    """문서 하나의 패키지 이름(표 행의 PACKAGE 열 · 본문 'Case:' 글, specs.build와 같은 규칙, 문서 단위)."""
    names = [x for c in doc['cards'] for x in packages_of({'kind': 'table_row', 'text': c['content']})]
    names += [x for t in doc['texts'] for x in packages_of({'kind': 'text', 'text': t})]
    return list(dict.fromkeys(names))


class Pick(BaseModel):
    """LLM이 고른 문서 하나. quote는 그 문서 개요 줄에서 그대로 옮긴, 조건에 맞을 근거(범위 · 패키지)다."""
    document: str = Field(max_length=120)
    quote: str = Field(max_length=200)


class Picks(BaseModel):
    """LLM 출력: 조건을 채우는 품번이 있을 만한 문서들(많아야 N_PICK개, 없으면 빈 목록)."""
    picks: list[Pick] = Field(default_factory=list, max_length=20)


PICK_PROMPT = (Path(__file__).resolve().parents[1] / 'prompts' / 'card_pick.md').read_text(encoding='utf-8')
N_PICK = 10  # 카드를 읽힐 문서 수 상한. [왜] 8개일 때 회차에 따라 정답 문서(SSB2H100H)가 빠졌다(h4-14, 11-08)


def pick_docs(conditions, package, overviews, *, chat):
    """같은 분류 문서들의 개요 줄(PDF 1쪽 제목 글 그대로)을 LLM에 보여 조건에 맞을 문서를 고르게 하고, 코드가 확인한 문서 키만 돌려준다.

    - overviews: [{'key', 'file', 'text'}]. 고른 문서는 목록에 있어야 하고 quote가 그 개요 줄에 그대로 있어야 받는다(지어낸 문서를 막는다).
    """
    if not overviews:
        return []
    want = '; '.join(search_sentence(conditions, None, package).split(', '))
    user = '\n'.join([f'Conditions: {want}', f'Package wanted: {package or "any"}', f'Pick at most {N_PICK} documents.', 'Documents:',
                      *(f"- {o['file']}: {' '.join(o['text'].split('] ', 1)[-1].split())}" for o in overviews)])
    by_file = {o['file']: o for o in overviews}
    keys = []
    for p in chat('card_pick', PICK_PROMPT, user, Picks).picks:
        o = by_file.get(p.document)
        if o and ' '.join(p.quote.split()) in ' '.join(o['text'].split()) and o['key'] not in keys:
            keys.append(o['key'])
    return keys[:N_PICK]


def _meets(cond, row):
    """행 하나가 조건 하나를 채우는지. find_candidates의 SQL과 같은 뜻(그 칸이 비면 거짓, 경계 포함)."""
    v = row.get(cond.get('slot') or DEFAULT_SLOT.get(cond['code'], 'max'))
    return row['code'] == cond['code'] and v is not None and v >= cond.get('gte', v) and v <= cond.get('lte', v)


# 찾기가 조건 코드 말고 더 읽어 둘 숫자 코드(판정이 쓸 코드). find.also_read(codes)로 정한다. 요청마다 문맥(contextvars)에 둬 동시 요청이 섞이지 않는다
EXTRA_CODES = contextvars.ContextVar('card_find_extra_codes', default=())
# 문서 키 → {'codes': 읽은 코드, 'rows': 행}. default_find와 default_specs가 같은 것을 써, 판정 값 읽기가 찾기에서 이미 읽은 문서를 다시 읽지 않는다
SHARED_READS = {}


def make_find(*, retrieve, load_cards, read, chat, doc_meta, n_docs=10, overviews=None, shared=None):
    """의존(검색 · 카드 적재 · 카드 읽기 · LLM · 문서 분류)을 받아 find를 만든다.

    - overviews(category) → 그 분류 문서들의 개요 줄 [{'key', 'file', 'text'}]. 주면 분류가 있는 찾기는 검색 대신
      LLM이 개요 줄을 보고 문서를 고른다(`pick_docs`, LLM 1번 더). 분류가 없으면 검색으로 고른다.
    - retrieve(sentence, k=40) → 청크 목록(`document_key` 필요, retrieve.retrieve와 같은 모양).
    - doc_meta(document_keys) → {document_key: {'category': 분류 이름 또는 None}}. 모르는 문서 · 빈 분류는 분류로 거르지 않는다.
    - load_cards(document_keys) → {document_key: {'file', 'parts'(표지 품번), 'cards'(표 행 카드), 'texts'(표 밖 글 본문)}}.
    - read(cards, codes, doc_parts, chat=chat) → (사양 행 목록(spec_lookup._row 모양), 버린 읽기). card_read.read_values와 같은 모양.
    - shared: 주면 문서마다 읽은 행을 담아 둔다(card_specs가 같은 dict를 받아 다시 읽지 않는다).
    """
    memo = {}  # (조건, 분류, 패키지) → (rows, keys, docs, meta)

    def gather(conditions, category, package):
        """검색 → 문서 고르기 → 카드 적재 → 카드 읽기(LLM 1번). 같은 (조건, 분류, 패키지)는 한 번만 읽는다."""
        # [왜] judge.py는 순서용 인자(original_*)만 바꿔 같은 조건으로 find를 두 번 부른다. 순서는 아래에서 다시 매기므로 읽기를 다시 쓴다
        memo_key = json.dumps([conditions, category, package], sort_keys=True, default=str)
        if memo_key in memo:
            return memo[memo_key]
        if category is not None and overviews is not None:
            # [왜] 검색은 '600 V'처럼 숫자로 문서를 잘 못 고른다(h4-11 정답 문서가 검색 59등 · h4-13은 17등, 11-08 실측).
            #      문서마다 PDF 1쪽 제목 줄('1N4001G - 1N4007G 1A, 50V - 1000V Standard Rectifier')을 LLM이 보고 고르게 한다
            keys = pick_docs(conditions, package, overviews(category), chat=chat)
        else:
            hits = retrieve(search_sentence(conditions, category, package), k=K_SEARCH)
            keys = list(dict.fromkeys(h['document_key'] for h in hits))  # 처음 나온 순서(검색 순위)
        meta = doc_meta(keys) if keys else {}
        if category is not None:
            # [왜] 분류를 아는 문서만 거른다. category 열(db/012)이 없거나 비면 거르지 않는다(빈 결과보다 판정이 보는 편이 낫다)
            keys = [k for k in keys if (meta.get(k) or {}).get('category') in (None, category)]
        keys = keys[:n_docs]
        docs = load_cards(keys) if keys else {}
        # [왜] 판정은 같은 문서를 판정 규칙 코드로 또 읽었다(찾기 질문에서 카드 읽기가 차례로 두 번, 11-09 Langfuse).
        #      판정이 쓸 코드(EXTRA_CODES)까지 한 번에 읽어 shared에 두면 판정 값 읽기가 그 행을 쓴다. 거르기는 조건 코드로만 한다
        codes = list(dict.fromkeys([c['code'] for c in conditions] + [c for c in EXTRA_CODES.get() if c in SI]))

        def read_doc(k):
            """문서 하나의 카드를 읽는다(LLM 1번). 읽을 카드가 없으면 부르지 않는다."""
            doc = docs[k]
            cards = [c for c in doc['cards'] if mentions(c['content'], codes)][:MAX_CARDS]
            if not cards:
                return []
            got, _ = read(cards, codes, {doc['file']: doc['parts']}, chat=chat)
            got += h_copies(got, doc)
            got += bi_copies(got, doc)  # [주의] H 다음에 양방향: CAH는 AH(H로 붙인 단방향) 값을 받는다
            if shared is not None and not set(codes) < (shared.get(k) or {}).get('codes', set()):
                shared[k] = {'codes': set(codes), 'rows': got}  # 더 많은 코드로 읽은 것은 덮지 않는다
            return got
        # [왜] 문서를 한 번에 읽히면 읽기가 150개를 넘어 느리고 출력 상한(4096)에 잘린다(h4-11 148개, 11-08). 문서마다 나눠 동시에 부른다
        with ThreadPoolExecutor(max_workers=max(1, len(keys))) as pool:
            # [주의] 스레드마다 문맥(contextvars)을 복사해 넘긴다(judge.py 읽기와 같은 방법). 안 넘기면 Langfuse 추적에서 카드 읽기가 빠졌다(11-09 실측)
            futures = [pool.submit(contextvars.copy_context().run, read_doc, k) for k in keys if k in docs]
            rows = [r for f in futures for r in f.result()]
        memo[memo_key] = (rows, keys, docs, meta)
        return memo[memo_key]

    def find(conditions, category=None, package=None, limit=50, original_packages=None, original_category=None):
        """모든 조건을 채운 품번 목록. 인자 · 반환 · 순서는 spec_lookup.find_candidates와 같다(카드를 읽어 행을 만든다는 것만 다름)."""
        rows, keys, docs, meta = gather(conditions, category, package)
        if not rows:
            return []

        cat_of, pkgs_of = {}, {}  # 품번 대문자 → 분류(처음 나온 문서), 패키지(그 품번이 표지에 적힌 문서들의 합)
        for k in keys:
            if k not in docs:
                continue
            pkgs = doc_packages(docs[k])
            for p in docs[k]['parts']:
                cat_of.setdefault(p.upper(), (meta.get(k) or {}).get('category'))
                pkgs_of[p.upper()] = list(dict.fromkeys(pkgs_of.get(p.upper(), []) + pkgs))
        parts, met = {}, {}  # find_candidates와 같은 두 표: 품번 → 결과 한 개, 품번 → {채운 조건 번호: 가장 가까운 비율}
        for row in rows:
            ok = [i for i, c in enumerate(conditions) if _meets(c, row)]
            if not ok:
                continue
            key = row['part'].upper()
            parts.setdefault(key, {'part': row['part'], 'category': cat_of.get(key), 'packages': pkgs_of.get(key, []),
                                   'matches': []})['matches'].append(row)
            near = met.setdefault(key, {})
            for i in ok:
                near[i] = min(near.get(i, float('inf')), _ratio(conditions[i], row))
        found = {k: p for k, p in parts.items() if len(met[k]) == len(conditions)}
        if package is not None:
            # [왜] find_candidates와 같이 이름이 같을 때만 같은 패키지다(SMA는 SMAF에 걸리지 않음)
            found = {k: p for k, p in found.items() if _norm_package(package) in {_norm_package(x) for x in p['packages']}}
        want = {_norm_package(p) for p in original_packages or []} - {''}

        def order(key):
            p = found[key]
            return (bool(want) and not want & {_norm_package(x) for x in p['packages']},
                    original_category is not None and p['category'] != original_category, max(met[key].values()), key)
        return [found[k] for k in sorted(found, key=order)][:limit]
    find.also_read = lambda codes: EXTRA_CODES.set(tuple(codes))  # 판정 에이전트가 찾기 전에 부른다(사양 표 find에는 없음)
    return find


def _connect():
    import psycopg
    return psycopg.connect(os.environ['DATABASE_URL'])


def load_cards(keys):
    """문서 키 → {'file', 'parts', 'cards', 'texts', 'aec_h', 'both'}. 표 행(row_label 있음)은 cards, 표 밖 글 · 개요는 texts.
    aec_h는 문서 어딘가(표 주석 포함)에 '"H" means AEC-Q101 qualified'가 있는지(H 품번에 기본 품번 값을 붙이는 근거),
    both는 '… characteristics apply in both directions'가 있는지다(양방향 품번에 단방향 품번 값을 붙이는 근거)."""
    out = {}
    with _connect() as conn:
        rows = conn.execute('SELECT d.document_key, d.source_url, c.id, c.chunk_index, c.page_number, c.table_name, c.row_label, c.content'
                            ' FROM document_chunks c JOIN source_documents d ON d.id = c.document_id'
                            ' WHERE d.document_key = ANY(%s) ORDER BY c.document_id, c.chunk_index', (list(keys),)).fetchall()
    for key, url, chunk_id, index, page, table, row, content in rows:
        # 문서 파일 이름은 출처 URL 끝(spec_lookup 인용 · retrieve의 file과 같은 방식)
        doc = out.setdefault(key, {'file': unquote(os.path.basename(urlparse(url).path)), 'parts': [], 'cards': [], 'texts': [],
                                   'text_cards': [], 'aec_h': False, 'both': False})
        doc['aec_h'] = doc['aec_h'] or bool(AEC_H.search(content))
        doc['both'] = doc['both'] or bool(BOTH_DIRECTIONS.search(content))
        cover = COVER.match(content) if index == 0 else None
        if cover:  # 표지(chunk_index 0)는 품번 목록뿐이다
            doc['parts'] = [p.strip() for p in cover.group(1).split(', ') if p.strip()]
        elif row is not None:
            doc['cards'].append({'chunk_id': chunk_id, 'document': doc['file'], 'page': page, 'table': table, 'row': row,
                                 'content': content})
        elif table is None:
            doc['texts'].append(content)  # 패키지 이름('Case: SOD-123F')을 읽을 글. 표 주석은 aec_h만 본다
            # card_specs가 패키지 · AEC 행의 인용 쪽을 정할 때 쓴다
            doc['text_cards'].append({'chunk_id': chunk_id, 'page': page, 'table': table, 'row': row, 'content': content})
    return out


def bi_copies(rows, doc):
    """양방향 품번(…C · …CA · …CH · …CAH)에 단방향 품번(C를 뺀 이름) 행을 붙인다. 문서가 '특성은 양방향 모두 적용'이라고 밝혔을 때만.

    [왜] TVS 값 표는 단방향 품번으로만 적어, 양방향 TVS 찾기에서 정답 5개를 모두 놓쳤다(h4-15, 11-09 claude -p 실측).
         11-09에 지운 사양 표 변환(pipeline/specs.py)의 양방향 규칙과 같다. 이미 그 코드 값이 있는 양방향 품번은 건드리지 않는다
    """
    if not doc.get('both'):
        return []
    mine = {}
    for r in rows:
        mine.setdefault(r['part'].upper(), []).append(r)
    names = {p.upper() for p in doc['parts']}
    out = []
    for p in doc['parts']:
        u = re.sub(r'C(A?H?)$', r'\1', p.upper())
        if u != p.upper() and u in names and u in mine:
            have = {r['code'] for r in mine.get(p.upper(), [])}
            out += [{**r, 'part': p} for r in mine[u] if r['code'] not in have]
    return out


def h_copies(rows, doc):
    """H 품번(표지에는 'XH', 값 표에는 X만)에 기본 품번 X의 행을 붙인다. 문서가 '"H" means AEC-Q101 qualified'라고 밝혔을 때만.

    [왜] 값 표는 기본 품번으로만 적어, 카드 읽기가 1N4005GH의 VRRM을 못 읽었다(h4-11 GH 3개, 11-08 claude -p 실측).
         11-09에 지운 사양 표 변환(pipeline/specs.py)의 h_copies와 같은 규칙이다. 이미 그 코드 값이 있는 H 품번은 건드리지 않는다
    """
    if not doc.get('aec_h'):
        return []
    mine = {}
    for r in rows:
        mine.setdefault(r['part'].upper(), []).append(r)
    out = []
    for p in doc['parts']:
        P = p.upper()
        if P.endswith('H') and P[:-1] in mine:
            have = {r['code'] for r in mine.get(P, [])}
            out += [{**r, 'part': p} for r in mine[P[:-1]] if r['code'] not in have]
    return out


def doc_meta(keys):
    """문서 키 → {'category'}. category 열(db/012)이 아직 없으면 빈 dict다(분류로 거르지 않음)."""
    import psycopg
    try:
        with _connect() as conn:
            rows = conn.execute('SELECT document_key, category FROM source_documents WHERE document_key = ANY(%s)',
                                (list(keys),)).fetchall()
    except psycopg.errors.UndefinedColumn:
        return {}
    return {k: {'category': c} for k, c in rows}


def overview_lines(category):
    """분류 하나의 문서마다 개요 카드(PDF 1쪽 제목 줄, 청킹이 만든 '제품 개요' 카드) [{'key', 'file', 'text'}]."""
    with _connect() as conn:
        rows = conn.execute("SELECT d.document_key, d.source_url, dc.content FROM document_chunks dc"
                            " JOIN source_documents d ON d.id = dc.document_id"
                            " WHERE d.category = %s AND dc.content LIKE %s ORDER BY d.document_key",
                            (category, '%· 제품 개요]%')).fetchall()
    return [{'key': k, 'file': unquote(os.path.basename(urlparse(u).path)), 'text': t} for k, u, t in rows]


def default_find(n_docs=10):
    """실제 검색 · DB · 카드 읽기 · node_chat을 묶은 find. 분류가 있으면 LLM 2번(문서 고르기 + 카드 읽기), 없으면 검색 1번 + LLM 1번."""
    from backend.rag.card_read import read_values
    from backend.rag.retrieve import retrieve
    from backend.services.llm import node_chat
    return make_find(retrieve=retrieve, load_cards=load_cards, read=read_values, chat=node_chat, doc_meta=doc_meta, n_docs=n_docs,
                     overviews=overview_lines, shared=SHARED_READS)
