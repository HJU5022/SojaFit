"""판정 값을 카드(청크)에서 읽기(3단계): 사양 표(part_specifications) 없이 `spec_lookup.part_specs`와 같은 모양의 행을 돌려준다.

- 역할: `make_specs(...)`가 돌려주는 specs(part, codes=None)는 품번이 적힌 문서의 카드를 읽고(card_read.read_values: 코드가 먼저,
  코드가 못 읽은 카드만 LLM), 확인을 거친 숫자 행에 패키지(PACKAGE) · AEC-Q101(AEC_Q101) 행과 분류를 붙여 돌려준다.
  `specs.prefetch(parts, codes)`는 후보 여러 개를 문서별로 묶어 동시에 읽어 둔다(판정이 후보마다 한 번씩 부르기 전에).
  `specs.doc_rows(part)`는 LLM 없이 그 품번 문서의 PACKAGE 행만 준다(사실 확인 노드가 문서 · 개정만 볼 때).
- 하지 않는 일: 판정 · 비교(`backend/judge/`), 카드 값 대조(`card_read.py`), 찾기(`card_find.py`), LLM 직접 호출(chat을 받아 넘긴다).
- 출처: lab v3 결정 21의 3단계(표 없이 판정 값), 행 모양은 `spec_lookup._row`, 패키지 규칙은 `pipeline/specs.py`(packages_of), AEC 규칙은 11-09에 지운 사양 표 변환의 aec_of와 같음
"""
import contextvars
import os
import re
from concurrent.futures import ThreadPoolExecutor

from backend.rag.card_find import MAX_CARDS, bi_copies, doc_packages, h_copies, mentions
from backend.rag.card_read import SI, _names
from backend.rag.pipeline.specs import AEC_ALL

NUMERIC = tuple(SI)  # 카드에서 읽는 숫자 코드(코드가 먼저, 못 읽은 카드만 LLM). PACKAGE · AEC_Q101은 코드가 글에서 정한다


def _bases(part: str) -> set[str]:
    """품번이 값을 물려받을 수 있는 이름들: 자기, H를 뗀 이름, 양방향 C를 뗀 이름(h_copies · bi_copies가 쓰는 기본 품번)."""
    p = part.upper()
    out = {p}
    if p.endswith('H'):
        out.add(p[:-1])
    for q in list(out):
        out.add(re.sub(r'C(A?H?)$', r'\1', q))
    return out


def _text_row(part, code, text, doc, category, chunk=None):
    """글로 정하는 행(PACKAGE · AEC_Q101) 하나. 숫자 칸은 비고, 인용은 그 글이 나온 카드(없으면 문서만)."""
    return {'part': part, 'category': category, 'code': code, 'min': None, 'typ': None, 'max': None, 'text': text, 'unit': None,
            'source_value_text': text, 'test_condition': None,
            'citation': {'document': doc['file'], 'page': chunk and chunk.get('page'), 'table': chunk and chunk.get('table'),
                         'row': chunk and chunk.get('row'), 'chunk_index': None, 'chunk_id': chunk and chunk.get('chunk_id')}}


def _where(doc, word):
    """그 낱말이 처음 나온 카드(표 행 · 글). 패키지 · AEC 행의 인용 쪽을 정한다."""
    for c in doc['cards'] + doc.get('text_cards', []):
        if word.upper() in c['content'].upper():
            return c
    return None


def text_rows(part, doc, category):
    """PACKAGE 행(문서의 패키지 이름마다)과 AEC_Q101 행(문서가 밝혔을 때만, 11-09에 지운 사양 표 변환의 aec_of와 같은 규칙)."""
    rows = [_text_row(part, 'PACKAGE', name, doc, category, _where(doc, name)) for name in doc_packages(doc)]
    if doc.get('aec_h'):
        if part.upper().endswith('H'):
            rows.append(_text_row(part, 'AEC_Q101', 'AEC-Q101 qualified ("H")', doc, category, _where(doc, 'AEC')))
    else:
        feat = next((c for c in doc.get('text_cards', []) if '· FEATURES]' in c['content'] and AEC_ALL.search(c['content'])), None)
        if feat is not None:
            rows.append(_text_row(part, 'AEC_Q101', 'AEC-Q101 qualified', doc, category, feat))
    return rows


def make_specs(*, load_cards, read, chat, doc_meta, part_docs, shared=None):
    """의존을 받아 specs를 만든다. part_docs(part) → 그 품번이 표지에 적힌 문서 키 목록.

    shared: card_find와 같은 dict(문서 키 → {'codes', 'rows'}). 찾기가 그 문서를 이 코드까지 이미 읽었으면 다시 읽지 않는다.
    """
    cache = {}  # 품번 대문자 → {'codes': 읽은 숫자 코드, 'rows': 행}
    docs, meta = {}, {}

    def _load(keys):
        new = [k for k in keys if k not in docs]
        if new:
            docs.update(load_cards(new))
            meta.update(doc_meta(new))

    def _read_doc(key, wanted, codes):
        """문서 하나에서 wanted 품번들의 codes를 읽는다(코드가 먼저, 못 읽은 카드만 LLM). 품번이 적힌 카드와 품번 없는 문서 전체 카드만 넘긴다."""
        doc = docs[key]
        want = {p.upper() for p in wanted}
        hit = (shared or {}).get(key)
        if hit and set(codes) <= hit['codes']:
            # [왜] 찾기가 판정 코드까지 읽어 둔 문서는 다시 읽지 않는다(찾기 질문의 두 번째 읽기 차례를 없앤다, 11-09).
            #      [주의] 찾기 쪽은 카드 60장에서 자를 수 있어, 원하는 품번 행이 하나라도 없으면 아래에서 새로 읽는다
            rows = [r for r in hit['rows'] if r['part'].upper() in want and r['code'] in codes]
            if {r['part'].upper() for r in rows} >= want:
                return rows
        names = {b for p in wanted for b in _bases(p)}
        text_of = lambda c: c['content'].replace(doc['file'], '')  # noqa: E731  [왜] 파일 이름의 대표 품번은 품번 대조에서 뺀다
        cards = [c for c in doc['cards'] if mentions(c['content'], codes)
                 and (any(_names(n, text_of(c)) for n in names) or not any(_names(p, text_of(c)) for p in doc['parts']))][:MAX_CARDS]
        if not cards:
            return []
        got, _ = read(cards, codes, {doc['file']: doc['parts']}, chat=chat)
        got += h_copies(got, doc)
        got += bi_copies(got, doc)
        return [r for r in got if r['part'].upper() in want]

    def prefetch(parts, codes=None):
        """품번들의 codes(기본: 숫자 코드 전부)를 문서별로 묶어 동시에 읽어 둔다. 이미 읽은 코드는 다시 읽지 않는다."""
        codes = [c for c in (codes or NUMERIC) if c in SI]
        todo = {}  # 문서 키 → {품번: 더 읽을 코드}
        for p in dict.fromkeys(x for x in parts if x):
            entry = cache.setdefault(p.upper(), {'codes': set(), 'rows': None})
            missing = [c for c in codes if c not in entry['codes']]
            keys = part_docs(p)
            _load(keys)
            if entry['rows'] is None:  # 처음 보는 품번: 글로 정하는 행(PACKAGE · AEC)을 먼저 붙인다(LLM 없음)
                entry['rows'] = [r for k in keys if k in docs for r in text_rows(p, docs[k], (meta.get(k) or {}).get('category'))]
            for k in keys:
                if missing and k in docs:
                    todo.setdefault(k, {})[p] = missing
        jobs = [(k, list(w), sorted({c for cs in w.values() for c in cs})) for k, w in todo.items()]
        if jobs:
            # [왜] 판정은 후보마다 차례로 부른다. 문서별로 묶어 동시에 읽어 두면 LLM 호출 수와 기다림이 준다
            with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
                # [주의] 스레드마다 문맥(contextvars)을 복사해 넘긴다(judge.py 읽기와 같은 방법). 안 넘기면 Langfuse 추적에서 카드 읽기가 빠졌다(11-09 실측)
                futures = [pool.submit(contextvars.copy_context().run, _read_doc, *j) for j in jobs]
                for (k, wanted, cs), got in zip(jobs, (f.result() for f in futures)):
                    cat = (meta.get(k) or {}).get('category')
                    for p in wanted:
                        entry = cache[p.upper()]
                        entry['rows'] += [{**r, 'category': cat} for r in got if r['part'].upper() == p.upper()]
                        entry['codes'] |= set(cs)

    def specs(part, codes=None):
        """품번 하나의 행(spec_lookup.part_specs와 같은 모양). codes를 주면 그 코드만(숫자 코드는 필요하면 그때 읽는다)."""
        if not part:
            return []
        entry = cache.get(part.upper())
        # [왜] 판정은 미리 읽어 둔(prefetch) 품번을 codes 없이 다시 부른다. 그때 나머지 코드를 품번마다 또 읽으면 LLM 호출이 후보 수만큼 늘어난다
        if codes is not None or entry is None or not entry['codes']:
            prefetch([part], [c for c in (codes or NUMERIC) if c in SI])
        rows = cache.get(part.upper(), {}).get('rows') or []
        return [r for r in rows if codes is None or r['code'] in codes]

    def doc_rows(part, codes=None):
        """LLM 없이 그 품번 문서의 PACKAGE 행만(문서 · 개정 확인용). 패키지 이름을 못 읽은 문서도 문서 인용 한 줄은 준다."""
        keys = part_docs(part)
        _load(keys)
        out = []
        for k in keys:
            if k in docs:
                rows = [r for r in text_rows(part, docs[k], (meta.get(k) or {}).get('category')) if r['code'] == 'PACKAGE']
                out += rows or [_text_row(part, 'PACKAGE', None, docs[k], (meta.get(k) or {}).get('category'))]
        return out

    specs.prefetch, specs.doc_rows = prefetch, doc_rows
    return specs


def part_docs_index():
    """품번 대문자 → 문서 키 목록을 찾는 함수를 돌려준다. 색인(표지 chunk_index 0의 품번 목록)은 처음 찾을 때 한 번 만든다(DATABASE_URL 필요)."""
    index = None

    def load():
        import psycopg
        from backend.rag.retrieve import COVER
        built = {}
        with psycopg.connect(os.environ['DATABASE_URL']) as conn:
            for key, content in conn.execute('SELECT d.document_key, c.content FROM document_chunks c JOIN source_documents d'
                                             ' ON d.id = c.document_id WHERE c.chunk_index = 0'):
                m = COVER.match(content)
                for p in (m.group(1).split(', ') if m else []):
                    built.setdefault(p.strip().upper(), []).append(key)
        return built

    def lookup(part):
        nonlocal index
        # [왜] 서버 시작(default_specs 조립) 때 코퍼스 표를 읽으면 코퍼스 없는 DB(CI)에서 앱이 뜨지 않는다. 첫 판정 때 읽는다
        # [주의] 읽기가 실패하면 index는 None으로 남아 다음 호출이 다시 읽는다. 동시에 처음 부르면 두 번 읽을 수 있으나 결과는 같다
        if index is None:
            index = load()
        return index.get((part or '').strip().upper(), [])
    return lookup


def default_specs():
    """실제 DB · 카드 읽기 · node_chat을 묶은 specs. 카드 읽기 LLM은 코드가 못 읽은 카드가 있을 때만 부른다."""
    from backend.rag.card_find import SHARED_READS, doc_meta, load_cards
    from backend.rag.card_read import read_values
    from backend.services.llm import node_chat
    return make_specs(load_cards=load_cards, read=read_values, chat=node_chat, doc_meta=doc_meta, part_docs=part_docs_index(),
                      shared=SHARED_READS)
