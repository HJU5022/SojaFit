"""데이터시트 카드(청크)에서 사양 값을 읽는다: 코드가 먼저 읽고, 코드가 못 읽은 카드만 LLM이 읽는다. 읽은 값마다 카드 글과 대조해 받거나 버린다.

- 역할: `read_values`가 카드마다 `pipeline/specs.py` 규칙(`read_card`, 카드 한 장)으로 먼저 읽고, 원하는 코드의 값을 하나도 받지
  못했거나 검토 표시가 난 카드만 `llm_read`로 넘긴다(한 프롬프트에 4장씩, LLM 노드 `card_read`). 코드 읽기와 LLM 읽기 모두 값마다
  카드 번호 · 인용 · 숫자 · 단위 차원 · 품번을 같은 규칙(`_check`)으로 확인하고, 받은 값은 `spec_lookup._row`와 같은 모양(SI 값)으로 돌려줘
  판정 코드가 사양 표 행처럼 쓴다. 틀린 값은 고치지 않고 사유와 함께 버린다.
- 하지 않는 일: 조건과 값 비교 · 판정(`backend/judge/`, AGENTS 지킬 것 7), 카드 찾기(부르는 쪽), LLM 직접 호출(chat을 받아 쓴다),
  사양 표 만들기 · 저장(팀 결정: 질문 때 카드를 읽는다). 여기서 숫자를 보는 일은 "읽은 숫자가 인용 글에 있는가"뿐이다.
- 출처: 사양 표 제거 뒤 카드 읽기(lab v3 b-redesign), 코드 먼저 읽기(사전 등록 #43, 11-09 조사), 행 모양은 `spec_lookup._row`,
  단위 환산은 `units.to_si`(SPEC 3절)
"""
import contextvars
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.rag.pipeline.specs import EXCLUDE, SI, SKIP_SYMS, code_of, fields, parse_cell, read_card
from backend.rag.pipeline.specs import NUM as CELL_NUM
from backend.rag.units import to_si

PROMPT = (Path(__file__).resolve().parents[1] / 'prompts' / 'card_read.md').read_text(encoding='utf-8')
NUM = re.compile(r'\d+(?:\.\d+)?')
# 한 번에 읽힐 카드 수. [왜] 시리즈 표 한 행은 품번 7개 안팎의 값을 담아 카드 4장이면 읽기 약 30개(출력 약 2천 토큰)로 상한 4096 안에 든다
BATCH = 4
# 프로세스 전체에서 동시에 떠 있는 카드 읽기 LLM 호출 수의 상한
# [왜] 문서 10개 × 문서마다 묶음 여러 개로 곱해져 94개가 동시에 떴고 31개가 연결 오류로 끊겨 문항이 실패했다(v3-15, 11-09 OpenRouter 실측)
MAX_PARALLEL = 24
_SLOTS = threading.BoundedSemaphore(MAX_PARALLEL)


def RANGE_AROUND(value: str) -> re.Pattern:  # noqa: N802
    """읽은 숫자가 '5.5 - 171' · '50V ~ 1000V' · '6.8 to 440'처럼 범위의 한쪽 끝인지 찾는 정규식."""
    v = re.escape(value.replace(',', ''))
    sep = r'\s*[A-Za-zµ]{0,2}\s*(?:-|–|~|to)\s*'
    return re.compile(rf'(?<![\d.]){v}{sep}\d|\d{sep}{v}(?![\d.])')


class Reading(BaseModel):
    """카드에서 읽은 값 하나. value · unit · quote는 카드에 적힌 그대로다(숫자 확인에 쓴다).

    part는 품번 하나, 묶음 칸이면 ', '로 이은 품번들, 품번 없는 문서 전체 정격 행이면 '*'(그 문서 품번 전부)다.
    """
    # [왜] 묶음 칸 · 문서 전체 정격을 품번마다 한 줄씩 쓰게 하면 계열 문서(품번 30여 개)에서 출력 상한(4096)에 잘린다. 코드가 펼친다
    # [왜] 제너 묶음 칸은 품번 수십 개를 ', '로 이어 400자를 넘었고, 형식 오류로 문항이 실패했다(v3-13, 생각 끔, 11-09). 펼친 품번은 코드가 문서 표지 품번과 대조한다
    part: str = Field(max_length=2000)
    code: Literal[tuple(SI)]  # [왜] 목록 밖 코드는 형식 검사에서 걸린다
    slot: Literal['min', 'typ', 'max']
    value: str = Field(max_length=20)
    unit: str = Field(max_length=10)
    condition: str = Field(default='', max_length=120)
    quote: str = Field(max_length=300)
    chunk_id: int


class CardRead(BaseModel):
    """LLM 출력. 카드에 없는 값은 읽지 않는다(빈 목록도 된다)."""
    # [주의] 출력 상한(CONFIG max_tokens 4096)이라 실제로는 50개 안팎에서 잘린다. 카드 · 품번을 많이 넘기지 않는다
    readings: list[Reading] = Field(default_factory=list, max_length=100)


def _norm(s: str) -> str:
    # [왜] 줄바꿈 · 겹친 공백과 μ(그리스 문자) · µ(마이크로 기호)를 맞춰 인용 대조가 표기 차이로 떨어지지 않게 한다(parse.py와 같은 규칙)
    return ' '.join(s.replace('μ', 'µ').split())


def _names(part: str, text: str) -> bool:
    """카드 글에 품번이 있는지(대소문자 · 공백 무시). 앞뒤가 영문 · 숫자면 다른 품번이다(SS14는 SS14ALH에 걸리지 않음)."""
    chars = [re.escape(c) for c in part if not c.isspace()]
    return bool(chars) and re.search(r'(?<![A-Z0-9])' + r'\s*'.join(chars) + r'(?![A-Z0-9])', text, re.I) is not None


def _check(r: Reading, card: dict | None, codes: list[str], doc_parts: dict) -> str | None:
    """읽은 값 하나를 카드와 대조해 버릴 사유를 돌려준다(받으면 None)."""
    if r.code not in codes:
        return 'code_not_asked'
    if card is None:
        return 'chunk_not_given'
    text, quote = _norm(card['content']), _norm(r.quote)
    if not quote or quote not in text:
        return 'quote_not_in_card'
    try:
        number = float(r.value.replace(',', ''))
    except ValueError:
        return 'value_not_number'
    # [왜] '1,000'의 쉼표를 지우고 숫자를 뽑는다. 부호는 보지 않는다('-55 to +150'의 -55도 55로 찾는다)
    if abs(number) not in {float(n) for n in NUM.findall(re.sub(r'(?<=\d),(?=\d{3})', '', quote))}:
        return 'value_not_in_quote'
    si = to_si(number, r.unit)
    if si is None:
        return 'unit_unknown'
    if si[1] != SI[r.code]:
        return 'unit_dimension'
    # [왜] 차원만 보면 µA를 mA로 잘못 적어도(같은 전류) 1000배 틀린 값이 통과한다. 적은 단위 글자가 그 카드에 있어야 한다
    if _norm(r.unit) not in text:
        return 'unit_not_in_card'
    parts = doc_parts.get(card['document'], [])
    # [주의] 카드 첫 칸의 파일 이름('1N4148W SERIES_C1901.pdf')에 대표 품번이 들어 있다. 품번 대조에서는 빼야 정격 행을 알아본다
    text = text.replace(_norm(card['document']), '')
    if _names(r.part, text):
        return None
    # [왜] 정격 표는 품번 없이 문서 전체 값 하나만 적는다. 그 문서 품번을 하나도 적지 않은 카드일 때만 그 문서 품번에 붙인다
    if any(_names(p, text) for p in parts):
        return 'part_not_in_card'
    # [왜] 품번 없는 요약 줄의 범위('VRWM | VALUE: 5.5 - 171')는 계열 전체 범위라 어느 품번의 값도 아니다. 모든 품번에 붙였더니
    #      양방향 품번이 VRWM 최대 171 V를 받아 조건(6.5 V 이하)에서 떨어졌다(h4-15, 11-09). 온도 범위(-55 to +150)는 그 품번의 값이다
    if r.code != 'TJ_MAX' and RANGE_AROUND(r.value).search(quote):
        return 'series_range'
    key = r.part.replace(' ', '').upper()
    return None if key in {p.replace(' ', '').upper() for p in parts} else 'part_not_in_document'


def _row(r: Reading, card: dict) -> dict:
    """받은 값 → `spec_lookup._row`와 같은 모양의 사양 한 줄(+ 인용 글)."""
    value, unit = to_si(float(r.value.replace(',', '')), r.unit)
    # [왜] 100 µA를 SI로 바꾸면 9.999999999999999e-05가 된다. 유효숫자 12자리로 맞춰 판정의 경계 비교가 어긋나지 않게 한다
    slots = {s: float(f'{value:.12g}') if s == r.slot else None for s in ('min', 'typ', 'max')}
    return {'part': r.part, 'category': None, 'code': r.code, **slots, 'text': None, 'unit': unit,
            'source_value_text': f'{r.value} {r.unit}', 'test_condition': r.condition or None,
            'citation': {'document': card['document'], 'page': card['page'], 'table': card['table'], 'row': card['row'],
                         'chunk_index': None, 'chunk_id': card['chunk_id']},
            'quote': r.quote}


def _excluded(card: dict) -> bool:
    """행 이름 · SYMBOL 칸이 프롬프트가 읽지 말라는 파라미터인가(RMS · IFRM · TSTG · 시험 전류 등, specs.code_of와 같은 규칙)."""
    syms = [v for _, col, v in fields(card['content']) if col.upper().startswith('SYMBOL')]
    name = f"{card['row'] or ''} {' '.join(syms)}"
    return bool(EXCLUDE.search(name) or any(s.strip().upper() in SKIP_SYMS for s in syms)
                or (re.search(r'storage', name, re.I) and not re.search(r'junction', name, re.I)))


def _quote(card: dict, part: str, number: str, code: str, unit: str, slot: str) -> str | None:
    """값 숫자가 든 칸 하나('MAX: 100', 'VBR at IT(1) / Min / V: 86.7')를 인용으로 고른다. 숫자가 든 칸이 없으면 None."""
    segs = [_norm(s) for s in card['content'].split('] ', 1)[-1].split('\n주: ', 1)[0].split(' | ')]
    words = {'min': ('MIN',), 'typ': ('TYP', 'NOM'), 'max': ('MAX',)}[slot]

    def rank(s):
        head, _, v = s.rpartition(': ')
        last = head.split(' / ')[-1].upper()
        # [왜] 같은 숫자가 여러 칸에 있다(SMBJ14A의 IR 1 µA와 'Test current IT (mA): 1', MBR1045CT 열과 MBR 1035 CT 열의 10). 앞 칸부터
        #      고르면 다른 칸을 인용했다(11-09). 값 칸으로 읽히는 칸(parse_cell) > 머리가 그 품번 > 머리가 그 코드(specs.code_of)
        #      > 머리에 그 단위 > 머리 끝이 그 칸(MIN · TYP · MAX) 순으로 고른다
        return (number in [n.replace(' ', '') for n in parse_cell(v)[1]], _names(part, head), code_of(head)[0] == code,
                f'({unit})' in head or f'/ {unit}' in head, any(last.startswith(w) for w in words))
    # [주의] 글자로 숫자가 없어도 칸 값으로 읽히면 후보다('–55 to +150'의 –55는 parse_cell이 -55로 읽는다)
    hits = [(r, -i, s) for i, s in enumerate(segs) if (r := rank(s))[0] or number in s.rpartition(': ')[2]]
    return max(hits)[2] if hits else None


def _by_code(card: dict, codes: list[str], doc_parts: dict) -> tuple[list[dict], list[dict]] | None:
    """카드 한 장을 코드로 읽는다 → (받은 행, 버린 읽기). LLM에 넘길 카드면 None, 읽을 값이 없는 카드면 ([], [])."""
    cands, flags, row_code = read_card(card['document'], doc_parts.get(card['document'], []), card)
    wanted = [r for r in cands if r['parameter_code'] in codes]
    flagged = [f for f in flags if f['parameter_code'] in codes]
    # 품번 없는 계열 범위('VRWM | VALUE: 5.5 - 171')는 프롬프트도 읽지 말라는 값이다. 그 표시뿐이면 검토가 아니라 읽을 값이 없는 것이다
    series = bool(flagged) and all(f['reason'] == 'range_unsplittable' and '문서 전체' in f['detail'] for f in flagged)
    if flagged and not series:
        return None  # [왜] 여러 값 칸 · 자리 표시 없음 · 대상 불명 등은 코드가 짐작하지 않는다. 카드 전체를 LLM이 읽는다
    if not wanted:
        body = card['content'].split('] ', 1)[-1].split('\n주: ', 1)[0]
        skip = (series or (row_code is None and _excluded(card)) or row_code not in (None, 'per_part', *codes)
                or not re.search(r':\s*[-+]?\d', body))  # 계열 범위 · 읽지 말 행 · 다른 코드 행 · 숫자 칸 없는 행
        return ([], []) if skip else None
    rows, rejected = [], []
    for cand in wanted:
        code = cand['parameter_code']
        unit = cand['source_unit'] or {'V': 'V', 'degC': '°C'}[SI[code]]  # [왜] 단위 없는 전압 칸은 V, 온도 칸은 °C로 읽었다(specs.emit)
        # 원문 글 '86.7 V'는 숫자 하나 · 칸 하나, 온도 범위 '-55 to +150 °C'는 숫자 둘 · 최소와 최대다(specs.emit이 쓴 순서)
        nums = [n.replace(' ', '') for n in re.findall(CELL_NUM, cand['source_value_text'])]
        slots = [s for s, k in (('min', 'minimum_value'), ('typ', 'typical_value'), ('max', 'maximum_value')) if cand[k] is not None]
        if len(nums) != len(slots):
            continue  # [주의] 숫자와 칸을 짝지을 수 없으면 짐작하지 않는다(다른 값이 모두 버려지면 그 카드는 LLM이 읽는다)
        for slot, number in zip(slots, nums):
            quote = _quote(card, cand['part'], number, code, _norm(unit), slot)
            if quote is None:
                continue
            # [왜] model_construct: 길이 상한(조건 120자 등)은 LLM 출력의 형식 검사다. 코드가 원문에서 옮긴 조건을 잘라 뜻을 바꾸지 않는다
            r = Reading.model_construct(part=cand['part'], code=code, slot=slot, value=number, unit=unit,
                                        condition=cand['test_condition'] or '', quote=quote[-300:], chunk_id=card['chunk_id'])
            if reason := _check(r, card, codes, doc_parts):
                rejected.append({**r.model_dump(), 'reason': reason})
            else:
                rows.append(_row(r, card))
    # [왜] 코드 읽기가 확인에서 모두 버려졌으면 쓸 값이 없다. 그 카드는 LLM이 읽는다
    return (rows, rejected) if rows else None


def read_values(cards: list[dict], codes: list[str], doc_parts: dict[str, list[str]], *, chat) -> tuple[list[dict], list[dict]]:
    """카드마다 코드가 먼저 읽고, 코드가 못 읽은 카드만 LLM에 읽혀(`llm_read`) (받은 사양 행, 버린 읽기)를 돌려준다.

    - 인자 · 반환은 `llm_read`와 같다. 코드가 다 읽으면 chat을 부르지 않는다.
    - 프롬프트가 읽지 말라는 행(RMS · TSTG · IFRM 등), 숫자 칸이 없는 행, 원하지 않는 코드의 행, 품번 없는 계열 범위뿐인 행은 LLM에도 보내지 않는다.
    """
    if not cards or not codes:
        return [], []
    rows, rejected, left = [], [], []
    for card in cards:
        got = _by_code(card, codes, doc_parts)
        if got is None:
            left.append(card)
        else:
            rows += got[0]
            rejected += got[1]
    more, more_rejected = llm_read(left, codes, doc_parts, chat=chat)
    order = {c['chunk_id']: i for i, c in enumerate(cards)}
    # [왜] 판정은 같은 코드의 첫 행을 '표의 첫 행'으로 쓴다(verdict.first_values). LLM이 읽은 카드 행도 카드 순서 자리에 둔다
    return sorted(rows + more, key=lambda r: order[r['citation']['chunk_id']]), rejected + more_rejected


def llm_read(cards: list[dict], codes: list[str], doc_parts: dict[str, list[str]], *, chat) -> tuple[list[dict], list[dict]]:
    """카드를 LLM에 읽혀 (받은 사양 행, 버린 읽기)를 돌려준다.

    - cards: [{'chunk_id', 'document'(PDF 파일 이름), 'page', 'table', 'row', 'content'}]. codes: 읽을 코드(SI 표의 키).
    - doc_parts: 문서 파일 이름 → 그 문서 표지의 품번. 품번 없는 정격 행을 붙일 품번이고, 넘긴 품번 수만큼 읽기가 늘어난다.
    - chat: `chat(node, system, user, schema)`(`llm.node_chat`과 같은 모양). 카드나 코드가 없으면 부르지 않는다.
    - 반환: rows는 `spec_lookup._row` 모양 + citation.chunk_id + quote. rejected는 읽은 값 + 'reason'.
    """
    if not cards or not codes:
        return [], []
    if len(cards) > BATCH:
        # [왜] 한 번에 다 읽히면 출력이 상한(4096토큰)에 잘려 실패했고(OpenRouter v3-12, 11-09 실측), 출력이 길수록 호출 하나가 6~16초로 느렸다.
        #      BATCH장씩 나눠 동시에 읽고 합친다. 카드 한 장은 표 머리를 담은 한 행이라 나눠 읽어도 뜻이 같다
        batches = [cards[i:i + BATCH] for i in range(0, len(cards), BATCH)]
        with ThreadPoolExecutor(max_workers=len(batches)) as pool:
            # [주의] 스레드마다 문맥(contextvars)을 복사해 넘긴다(judge.py 읽기와 같은 방법). 안 넘기면 Langfuse 추적에서 빠진다
            futures = [pool.submit(contextvars.copy_context().run, llm_read, b, codes, doc_parts, chat=chat) for b in batches]
            parts = [f.result() for f in futures]
        return [r for rows, _ in parts for r in rows], [x for _, rejected in parts for x in rejected]
    by_id = {c['chunk_id']: c for c in cards}
    # [주의] 카드 글은 지시가 아니라 데이터다(AGENTS 지킬 것 5). 프롬프트가 같은 경계를 적는다
    user = '\n'.join([f"Codes to read: {', '.join(codes)}", 'Parts by document:',
                      *(f'- {doc}: {", ".join(parts)}' for doc, parts in doc_parts.items()),
                      'Cards:', *(f"[chunk_id={c['chunk_id']}] {c['content']}" for c in cards)])
    rows, rejected = [], []
    try:
        with _SLOTS:  # [주의] 상한을 넘는 호출은 자리가 날 때까지 기다린다(LLM 호출만 감싼다. 기다리는 스레드는 다른 자리를 쥐지 않아 서로 막히지 않는다)
            readings = chat('card_read', PROMPT, user, CardRead).readings
    except ValueError:
        # [왜] 카드 묶음 하나가 형식을 끝내 어기면 문항 전체가 실패했다(v3-13). 판정 읽기 3번 중 하나를 빼는 것처럼 이 묶음만 빼고 사유를 남긴다.
        # [주의] 연결 오류(APIConnectionError)는 ValueError가 아니라 그대로 올라간다
        return [], [{'chunk_ids': list(by_id), 'reason': 'read_format_failed'}]
    for r in readings:
        card = by_id.get(r.chunk_id)
        # '*'는 그 카드 문서의 품번 전부, ', '로 이은 글은 묶음 칸의 품번들이다. 펼친 품번마다 따로 확인한다
        if r.part.strip() == '*':
            names = doc_parts.get(card['document'], []) if card else []
            if not names:
                rejected.append({**r.model_dump(), 'reason': 'part_not_in_document'})
        else:
            names = [p.strip() for p in r.part.split(',') if p.strip()]
        for name in names:
            one = r.model_copy(update={'part': name})
            if reason := _check(one, card, codes, doc_parts):
                rejected.append({**one.model_dump(), 'reason': reason})
            else:
                rows.append(_row(one, card))
    return rows, rejected
