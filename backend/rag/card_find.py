"""카드(표 행 청크)를 읽어 숫자 조건에 맞는 부품 찾기(서비스 · 평가 실행기 기본, ADR 0016). 찾기 계약은 SPEC.md 8.7.

- 역할: `make_find(...)`가 돌려주는 find(conditions, category, package, limit, original_packages, original_category)는
  읽을 문서를 고르고(분류가 있으면 그 분류 문서의 개요 줄을 코드가 먼저 보고(`code_pick`), 근거가 없을 때만 LLM `pick_docs`,
  분류가 없으면 조건으로 만든 검색 문장 하나로 retrieve 1번), 앞 문서 n_docs개의 표 행 카드를 읽어(card_read.read_values: 코드가 먼저, 못 읽은 카드만 LLM)
  사양 행을 얻은 뒤 거르고(모든 조건을 행 하나 이상이 채움) 줄 세운다
  (원래 부품의 패키지 → 원래 부품의 분류 → 기준에 가까운 순 → 품번 순). 반환 모양도 같다: [{'part', 'category', 'packages', 'matches'}].
  `default_find()`는 실제 검색 · DB(DATABASE_URL) · 카드 읽기 · node_chat을 묶는다. 테스트는 make_find에 가짜를 넘긴다.
- 하지 않는 일: 판정 · 대체 가능 여부(`backend/judge/`, AGENTS 지킬 것 7), 카드 값 읽기와 원문 대조(`card_read.py`),
  단위 환산(조건 · 행 값은 이미 SI), LLM 직접 호출(chat을 받아 넘긴다). 비교는 행을 거르는 >= · <=와 순서 비율뿐이다(spec_lookup과 같음).
- 출처: 지운 사양 표 찾기(ADR 0013 → 0016)와 같은 규칙(SPEC.md 8.7), lab v3 사양 표 제거(part_specifications가 빈 sojafit_v4),
  문서 고르기 코드 먼저(사전 등록 #44)

[주의] 검색에 걸린 앞 문서 n_docs개만 본다. 여기서 빠진 품번은 "조건 불충족"이 아니라 "못 찾음"이다(spec_lookup과 같은 뜻).
"""
import contextvars
import json
import os
import re
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urlparse

from pydantic import BaseModel, Field

from backend.rag.pipeline.specs import AEC_H, BOTH_DIRECTIONS, KEYWORDS, PKG, SI, SYMS, packages_of
from backend.rag.retrieve import COVER
from backend.rag.spec_lookup import DEFAULT_SLOT, THT_PACKAGES, _norm_package, _ratio

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
    """카드 글이 codes 중 하나의 기호나 설명 낱말을 담는지(읽을 카드를 줄이는 거친 거르기, 값은 보지 않는다)."""
    # [주의] 시험 조건의 기호(VF 행의 'IF = 1A')도 걸린다. 넘치게 넘기는 쪽이라 괜찮다(빠뜨리면 못 찾는다)
    symbols = re.findall(r'[A-Z][A-Z0-9()]*', text.upper())
    return any(SYMS.get(s) in codes for s in symbols) or any(code in codes and p.search(text) for p, code in KEYWORDS)


def doc_packages(doc):
    """문서 하나의 패키지 이름(표 행의 PACKAGE 열 · 본문 'Case:' 글, `pipeline/specs.py`의 packages_of 규칙, 문서 단위)."""
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
N_PICK = 20  # 구매 규격 전체 후보를 위해 읽을 문서 수 상한. 검색 자체의 후보 상한(50)은 별도다.
CODE_PICK_DEFAULT = 10  # 직접 호출하는 문서 선택기의 보수적 기본값(서비스는 n_docs를 명시한다)


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


# 개요 줄(제목)에서 값 읽기. [주의] 품번 · 패키지 이름 안의 숫자('SMA6J10A' · 'SOD-123W' · 'BZT52B2V4')는 값이 아니라 앞이 글자 · 점 · 하이픈이면 건너뛴다
_EDGE, _NUM = r'(?<![\w.\-])', r'(\d+(?:\.\d+)?)'
TITLE_V_RANGE = re.compile(_EDGE + _NUM + r'\s*V?\s*-\s*' + _NUM + r'\s*V\b')  # '50V - 1000V' · '50 - 1000 V' · '100-250V'
TITLE_V = re.compile(_EDGE + r'(?:VWM\s*=\s*)?' + _NUM + r'\s*V\b')  # '600V' · ESD 'VWM=5V'
TITLE_A = re.compile(_EDGE + _NUM + r'\s*(m?)A\b')
TITLE_W = re.compile(_EDGE + _NUM + r'\s*([km]?)W\b')
PART_RANGE = re.compile(r'^\s*\S+\s+-\s+\S+\s*$', re.M)  # 품번 범위뿐인 줄('SMAJ5.0(A)H - SMAJ188(A)H'). 패키지 이름(SMAJ5)처럼 읽혀 뺀다
SURFACE = re.compile(r'surface[- ]?mount|(?-i:\bSMD\b)', re.I)
TITLE_V_CODE = {'zener-diode': 'VZ', 'tvs': 'VRWM', 'esd-protection': 'VRWM'}  # 제목 전압이 뜻하는 코드(그 밖 분류는 VRRM)
TITLE_W_CODE = {'zener-diode': 'PD', 'tvs': 'PPPM'}
# [왜] 제목 값은 대표 값이다(제너 VZ는 공칭이라 최소 · 최대 칸과 다르고, TVS 제목 전압은 VBR일 때가 있다). 10% 넘게 어긋날 때만 버린다
SLACK = 1.1
_SCALE = {'': 1, 'm': 1e-3, 'k': 1e3}


def title_values(text, category):
    """개요 줄 → {코드: (낮은 값, 높은 값)}(SI). 전압은 분류의 대표 코드, 전류는 IF_AV, 전력은 제너 PD · TVS PPPM. 못 읽은 코드는 없다."""
    t = ' '.join(text.split('] ', 1)[-1].split())
    out = {}
    if m := TITLE_V_RANGE.search(t) or TITLE_V.search(t):
        out[TITLE_V_CODE.get(category, 'VRRM')] = (float(m.group(1)), float(m.groups()[-1]))  # 범위면 (낮은, 높은), 값 하나면 (값, 값)
    if amps := [float(n) * _SCALE[p] for n, p in TITLE_A.findall(t)]:
        out['IF_AV'] = (min(amps), max(amps))
    if (watts := [float(n) * _SCALE[p] for n, p in TITLE_W.findall(t)]) and category in TITLE_W_CODE:
        out[TITLE_W_CODE[category]] = (min(watts), max(watts))
    return out


def _title_fit(conditions, values):
    """제목 값과 조건: 어긋나면 None, 아니면 (제목으로 확인한 조건 수, 제목 범위가 조건 안에 다 드는가, 기준에서 먼 비율)."""
    known, inside, ratio = 0, True, 1.0
    for code in dict.fromkeys(c['code'] for c in conditions):
        if code not in values:
            continue  # 제목에 없는 값(trr · VC 등)은 확인 못 할 뿐 어긋남이 아니다
        lo, hi = values[code]
        cs = [c for c in conditions if c['code'] == code]
        if any('gte' in c and hi * SLACK < c['gte'] or 'lte' in c and lo > c['lte'] * SLACK for c in cs):
            return None
        low = max((c['gte'] for c in cs if 'gte' in c), default=None)
        high = min((c['lte'] for c in cs if 'lte' in c), default=None)
        known += len(cs)
        inside = inside and (low is None or lo * SLACK >= low) and (high is None or hi <= high * SLACK)
        # find의 _ratio와 같은 뜻: 범위 안에서 기준에 가장 가까운 값이 기준에서 얼마나 먼가(1이면 범위가 기준을 품음)
        if low is not None and low > 0:
            ratio = max(ratio, min(max(low, lo), hi) / low)
        elif high is not None and high > 0 and (near := min(max(high, lo), hi)) > 0:
            ratio = max(ratio, high / near)
    return known, inside, ratio


def code_pick(conditions, package, overviews, category, max_docs=CODE_PICK_DEFAULT):
    """개요 줄의 범위 · 단위 · 패키지로 문서를 고른다(LLM 없음). → 문서 키 N_PICK개까지, 코드가 고를 근거가 없으면 None(LLM이 고른다).

    - 버림: 제목 값이 조건과 10% 넘게 어긋남, 제목이 원하는 패키지 말고 다른 패키지만 적음, 삽입형을 원하는데 제목이 표면실장.
    - 순서: 제목의 패키지(원하는 것 → 없음 → 원하는 이름이 다른 이름에 붙음) → 제목으로 확인한 조건 수 → 제목 범위가 조건 안에 다 듦
      → 기준에 가까운 순 → 파일 이름.
    - None: 어느 제목에서도 조건 코드 값을 못 읽었거나, 10번째 문서도 제목으로 확인한 조건이 없을 때(줄 세울 근거가 없다).
    """
    want = _norm_package(package) if package else ''
    codes = {c['code'] for c in conditions}
    ranked, checked = [], False
    for o in overviews:
        title = o['text'].split('] ', 1)[-1]
        values = title_values(o['text'], category)
        checked = checked or bool(codes & set(values))
        fit = _title_fit(conditions, values)
        if fit is None:
            continue
        pkgs = {_norm_package(x) for x in PKG.findall(PART_RANGE.sub('', title))}
        tier = 1  # 0 제목이 원하는 패키지를 적음, 1 제목에 패키지 없음(모름), 2 다른 패키지를 적었지만 원하는 이름이 글에 붙어 있음
        if want and want in pkgs:
            tier = 0
        elif want:
            if want in THT_PACKAGES and SURFACE.search(title):
                continue  # [왜] DO-41을 원하는데 표면실장 문서가 자리를 차지해 정답 문서(UF1A)가 10개 밖으로 밀렸다(11-09 v3-12 시제품)
            if pkgs:
                # [주의] 'TO-263AB (D 2 PAK)'(D2PAK) · 'Micro SMA'(SMA)처럼 원하는 이름이 글에 붙어 있으면 버리지 않고 맨 뒤에 둔다
                if want not in re.sub(r'[^A-Z0-9]', '', title.upper()):
                    continue
                tier = 2
        known, inside, ratio = fit
        ranked.append(((tier, -known, not inside, ratio, o['file']), o['key']))
    if not checked:
        return None
    ranked.sort()
    max_docs = max(1, min(int(max_docs), N_PICK))
    if len(ranked) > max_docs and ranked[max_docs - 1][0][1] == 0:
        return None
    return [k for _, k in ranked[:max_docs]]


def _meets(cond, row):
    """행 하나가 조건 하나를 채우는지(그 칸이 비면 거짓, 경계 포함)."""
    v = row.get(cond.get('slot') or DEFAULT_SLOT.get(cond['code'], 'max'))
    return row['code'] == cond['code'] and v is not None and v >= cond.get('gte', v) and v <= cond.get('lte', v)


# 찾기가 조건 코드 말고 더 읽어 둘 숫자 코드(판정이 쓸 코드). find.also_read(codes)로 정한다. 요청마다 문맥(contextvars)에 둬 동시 요청이 섞이지 않는다
EXTRA_CODES = contextvars.ContextVar('card_find_extra_codes', default=())
# 문서 키 → {'codes': 읽은 코드, 'rows': 행}. default_find와 default_specs가 같은 것을 써, 판정 값 읽기가 찾기에서 이미 읽은 문서를 다시 읽지 않는다
SHARED_READS = {}


def make_find(*, retrieve, load_cards, read, chat, doc_meta, n_docs=10, overviews=None, shared=None):
    """의존(검색 · 카드 적재 · 카드 읽기 · LLM · 문서 분류)을 받아 find를 만든다.

    - overviews(category) → 그 분류 문서들의 개요 줄 [{'key', 'file', 'text'}]. 주면 분류가 있는 찾기는 검색 대신
      코드가 개요 줄의 범위 · 패키지로 문서를 고르고(`code_pick`), 줄 세울 근거가 없을 때만 LLM이 고른다(`pick_docs`). 분류가 없으면 검색으로 고른다.
    - retrieve(sentence, k=40) → 청크 목록(`document_key` 필요, retrieve.retrieve와 같은 모양).
    - doc_meta(document_keys) → {document_key: {'category': 분류 이름 또는 None}}. 모르는 문서 · 빈 분류는 분류로 거르지 않는다.
    - load_cards(document_keys) → {document_key: {'file', 'parts'(표지 품번), 'cards'(표 행 카드), 'texts'(표 밖 글 본문)}}.
    - read(cards, codes, doc_parts, chat=chat) → (사양 행 목록(card_read._row 모양), 버린 읽기). card_read.read_values와 같은 모양.
    - shared: 주면 문서마다 읽은 행을 담아 둔다(card_specs가 같은 dict를 받아 다시 읽지 않는다).
    """
    memo = {}  # (조건, 분류, 패키지) → (rows, keys, docs, meta)
    reads, reads_lock = {}, threading.Lock()  # (문서 키, 읽은 코드) → Future(행). 같은 문서 · 같은 코드의 카드 읽기를 한 번만 한다

    def gather(conditions, category, package):
        """검색 → 문서 고르기 → 카드 적재 → 카드 읽기(코드가 먼저, 못 읽은 카드만 LLM). 같은 (조건, 분류, 패키지)는 한 번만 읽는다."""
        # [왜] judge.py는 순서용 인자(original_*)만 바꿔 같은 조건으로 find를 두 번 부른다. 순서는 아래에서 다시 매기므로 읽기를 다시 쓴다
        memo_key = json.dumps([conditions, category, package], sort_keys=True, default=str)
        if memo_key in memo:
            return memo[memo_key]
        if category is not None and overviews is not None:
            # [왜] 검색은 '600 V'처럼 숫자로 문서를 잘 못 고른다(h4-11 정답 문서가 검색 59등 · h4-13은 17등, 11-08 실측).
            #      문서마다 PDF 1쪽 제목 줄('1N4001G - 1N4007G 1A, 50V - 1000V Standard Rectifier')을 보고 고른다
            # [왜] 코드가 제목의 범위 · 패키지로 먼저 고른다. LLM 고르기가 찾기 문항 시간의 약 3초였고, 기록된 18번 모두 코드가 정답 문서를
            #      LLM만큼 이상 골랐다(사전 등록 #44). 제목으로 줄 세울 근거가 없을 때만 LLM이 고른다
            lines = overviews(category)
            keys = code_pick(conditions, package, lines, category, max_docs=n_docs)
            if keys is None:
                keys = pick_docs(conditions, package, lines, chat=chat)
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
            # [왜] 'SMA(DO-214AC)'처럼 패키지가 둘로 갈리면 패키지마다 gather가 같은 문서의 카드를 LLM으로 또 읽었다(v3-15 찾기 5.6초 → 10.4초).
            #      같은 문서 · 같은 코드 목록이면 카드 목록(mentions 거르기 · MAX_CARDS 자르기)도 같아 행이 같다. 먼저 온 쪽이 읽고 나머지는 같은 결과를 기다린다
            # [주의] 코드가 더 많거나 적은 읽기는 재사용하지 않는다(행이 달라진다). 데모가 shared를 비우면 그 문서의 재사용도 끊는다(기록과 같은 호출을 내려고)
            rk = (k, tuple(codes))
            with reads_lock:
                fut = reads.get(rk)
                if fut is not None and fut.done() and shared is not None and k not in shared:
                    fut = None
                mine = fut is None
                if mine:
                    fut = reads[rk] = Future()
            if not mine:
                return list(fut.result())
            try:
                got, _ = read(cards, codes, {doc['file']: doc['parts']}, chat=chat)
                got += h_copies(got, doc)
                got += bi_copies(got, doc)  # [주의] H 다음에 양방향: CAH는 AH(H로 붙인 단방향) 값을 받는다
                if shared is not None and not set(codes) < (shared.get(k) or {}).get('codes', set()):
                    shared[k] = {'codes': set(codes), 'rows': got}  # 더 많은 코드로 읽은 것은 덮지 않는다
            except BaseException as e:
                with reads_lock:
                    reads.pop(rk, None)  # 실패는 남기지 않는다(다음 찾기가 다시 읽는다)
                fut.set_exception(e)
                raise
            fut.set_result(got)
            return list(got)
        # [왜] 문서를 한 번에 읽히면 읽기가 150개를 넘어 느리고 출력 상한(4096)에 잘린다(h4-11 148개, 11-08). 문서마다 나눠 동시에 부른다
        with ThreadPoolExecutor(max_workers=max(1, len(keys))) as pool:
            # [주의] 스레드마다 문맥(contextvars)을 복사해 넘긴다(judge.py 읽기와 같은 방법). 안 넘기면 Langfuse 추적에서 카드 읽기가 빠졌다(11-09 실측)
            futures = [pool.submit(contextvars.copy_context().run, read_doc, k) for k in keys if k in docs]
            rows = [r for f in futures for r in f.result()]
        memo[memo_key] = (rows, keys, docs, meta)
        return memo[memo_key]

    def find(conditions, category=None, package=None, limit=50, original_packages=None, original_category=None):
        """모든 조건을 채운 품번 목록. 인자 · 반환 · 순서는 SPEC.md 8.7(지운 사양 표 찾기와 같고, 카드를 읽어 행을 만든다는 것만 다름)."""
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
        parts, met = {}, {}  # 두 표: 품번 → 결과 한 개, 품번 → {채운 조건 번호: 가장 가까운 비율}
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
            # [왜] 이름이 같을 때만 같은 패키지다. 부분 일치면 SMA가 다른 패키지 SMAF까지 잡는다(11-05, 564개 중 36개)
            found = {k: p for k, p in found.items() if _norm_package(package) in {_norm_package(x) for x in p['packages']}}
        want = {_norm_package(p) for p in original_packages or []} - {''}

        def order(key):
            p = found[key]
            return (bool(want) and not want & {_norm_package(x) for x in p['packages']},
                    original_category is not None and p['category'] != original_category, max(met[key].values()), key)
        return [found[k] for k in sorted(found, key=order)][:limit]
    find.also_read = lambda codes: EXTRA_CODES.set(tuple(codes))  # Spec 에이전트가 찾기 전에 부른다(사양 표 find에는 없음)
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
    for doc in out.values():
        doc['parts'] = sorted(documented_parts(doc))
    return out


def bi_copies(rows, doc):
    """양방향 품번(…C · …CA · …CH · …CAH)에 단방향 품번(C를 뺀 이름) 행을 붙인다. 문서가 '특성은 양방향 모두 적용'이라고 밝혔을 때만.

    [왜] TVS 값 표는 단방향 품번으로만 적어, 양방향 TVS 찾기에서 정답 5개를 모두 놓쳤다(h4-15, 11-09 claude -p 실측).
         이미 그 코드 값이 있는 양방향 품번은 건드리지 않는다
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


def documented_parts(doc):
    """Include exact ordering H names only when their base belongs to this document."""
    names = {p.upper() for p in doc['parts']}
    if not doc.get('aec_h'):
        return names
    body = ' '.join(doc.get('texts', [])) + ' ' + ' '.join(c.get('content', '') for c in doc.get('cards', []))
    mentioned = set(re.findall(r'(?<![A-Z0-9])[A-Z0-9][A-Z0-9-]{2,}H(?![A-Z0-9])', body.upper()))
    return names | {p for p in mentioned if p[:-1] in names}


def h_copies(rows, doc):
    """H 품번(표지에는 'XH', 값 표에는 X만)에 기본 품번 X의 행을 붙인다. 문서가 '"H" means AEC-Q101 qualified'라고 밝혔을 때만.

    [왜] 값 표는 기본 품번으로만 적어, 카드 읽기가 1N4005GH의 VRRM을 못 읽었다(h4-11 GH 3개, 11-08 claude -p 실측).
         11-10에 지운 사양 표 변환(pipeline/specs.py h_copies)과 같은 규칙이다. 이미 그 코드 값이 있는 H 품번은 건드리지 않는다
    """
    if not doc.get('aec_h'):
        return []
    mine = {}
    for r in rows:
        mine.setdefault(r['part'].upper(), []).append(r)
    out = []
    names = documented_parts(doc)
    for P in names:
        if P.endswith('H') and P[:-1] in mine:
            have = {r['code'] for r in mine.get(P, [])}
            out += [{**r, 'part': P} for r in mine[P[:-1]] if r['code'] not in have]
    return out


# [왜] 코퍼스는 프로세스가 도는 동안 바뀌지 않는다. 찾기와 판정 값 읽기가 같은 문서를 DB에서 다시 읽지 않게 프로세스 하나가 문서 키별로 들고 있는다
# [주의] 1 GiB Cloud Run이라 문서 수를 MAX_CACHED_DOCS로 막는다(넘으면 오래된 것부터 버린다). 문서 dict는 읽기만 하고 고치지 않는다
MAX_CACHED_DOCS = 64
_DOCS, _META = {}, {}


def cached_load_cards(keys):
    """load_cards와 같은 결과(문서 키 → 문서). 이미 읽은 문서는 DB를 안 부르고, 나머지는 한 번에 적재한다."""
    keys = list(dict.fromkeys(keys))
    new = [k for k in keys if k not in _DOCS]
    if new:
        for k, d in load_cards(new).items():
            while len(_DOCS) >= MAX_CACHED_DOCS:
                _DOCS.pop(next(iter(_DOCS)), None)
            _DOCS[k] = d
    return {k: _DOCS[k] for k in keys if k in _DOCS}


def cached_doc_meta(keys):
    """doc_meta와 같은 결과. 이미 알아낸 문서는 DB를 안 부른다(열이 없어 빈 dict였던 결과는 남기지 않는다)."""
    keys = list(dict.fromkeys(keys))
    new = [k for k in keys if k not in _META]
    if new:
        _META.update(doc_meta(new))
    return {k: _META[k] for k in keys if k in _META}


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


_OVERVIEWS = {}


def overview_lines(category):
    """분류 하나의 문서마다 개요 카드(PDF 1쪽 제목 줄, 청킹이 만든 '제품 개요' 카드) [{'key', 'file', 'text'}]. 분류마다 한 번만 읽는다."""
    # [왜] 찾기마다 모든 청크를 LIKE로 훑었다. 코퍼스는 프로세스 동안 그대로라 분류별로 한 번이면 된다. 읽는 쪽은 줄을 고치지 않는다
    if category not in _OVERVIEWS:
        _OVERVIEWS[category] = _query_overviews(category)
    return list(_OVERVIEWS[category])


def _query_overviews(category):
    with _connect() as conn:
        rows = conn.execute("SELECT d.document_key, d.source_url, dc.content FROM document_chunks dc"
                            " JOIN source_documents d ON d.id = dc.document_id"
                            " WHERE d.category = %s AND dc.content LIKE %s ORDER BY d.document_key",
                            (category, '%· 제품 개요]%')).fetchall()
    return [{'key': k, 'file': unquote(os.path.basename(urlparse(u).path)), 'text': t} for k, u, t in rows]


def default_find(n_docs=None, chat=None):
    """실제 검색 · DB · 카드 읽기 · node_chat을 묶은 find. 분류가 있으면 개요 줄로 문서 고르기(코드가 못 고를 때만 LLM 1번), 없으면 검색 1번.
    카드 읽기 LLM은 코드가 못 읽은 카드가 있을 때만. chat을 주면 node_chat 대신 쓴다(데모 응답 기록 · 재생, `backend/services/demo.py`).

    n_docs 기본 5. FIND_N_DOCS로 덮어쓴다(속도·정확도 A/B용).
    """
    if n_docs is None:
        n_docs = int(os.getenv('FIND_N_DOCS', '5') or '5')  # [왜] Spec 7문항 A/B(11-11): n10·n5 모두 7/7 cited_gold, n5가 p95 10.4→9.9 · 평균 7.5→7.0
    from backend.rag.card_read import read_values
    from backend.rag.retrieve import retrieve
    from backend.services.llm import node_chat
    return make_find(retrieve=retrieve, load_cards=cached_load_cards, read=read_values, chat=chat or node_chat, doc_meta=cached_doc_meta, n_docs=n_docs,
                     overviews=overview_lines, shared=SHARED_READS)
