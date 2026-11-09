"""데이터시트 카드(청크)를 LLM이 읽어 사양 값을 내고, 코드가 읽은 값마다 카드 글과 대조해 받거나 버린다.

- 역할: `read_values` 하나. 후보 부품의 카드를 한 프롬프트에 넣어 LLM(노드 `card_read`)을 한 번 부르고, 읽은 값마다
  카드 번호 · 인용 · 숫자 · 단위 차원 · 품번을 확인한다. 받은 값은 `spec_lookup._row`와 같은 모양(SI 값)으로 돌려줘
  판정 코드가 사양 표 행처럼 쓴다. 틀린 값은 고치지 않고 사유와 함께 버린다.
- 하지 않는 일: 조건과 값 비교 · 판정(`backend/judge/`, AGENTS 지킬 것 7), 카드 찾기(부르는 쪽), LLM 직접 호출(chat을 받아 쓴다).
  여기서 숫자를 보는 일은 "읽은 숫자가 인용 글에 있는가"뿐이다.
- 출처: 사양 표 제거 뒤 카드 읽기(lab v3 b-redesign), 행 모양은 `spec_lookup._row`, 단위 환산은 `units.to_si`(SPEC 3절)
"""
import contextvars
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.rag.units import to_si

PROMPT = (Path(__file__).resolve().parents[1] / 'prompts' / 'card_read.md').read_text(encoding='utf-8')
# 코드마다 SI 단위. pipeline/specs.py의 SI와 같은 표다
SI = {'VRRM': 'V', 'VR': 'V', 'VRWM': 'V', 'VBR': 'V', 'VC': 'V', 'VZ': 'V', 'VF': 'V', 'VESD': 'V',
      'IF_AV': 'A', 'IFSM': 'A', 'IR': 'A', 'IPP': 'A', 'PD': 'W', 'PPPM': 'W', 'TRR': 's', 'CJ': 'F', 'TJ_MAX': 'degC'}
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


def read_values(cards: list[dict], codes: list[str], doc_parts: dict[str, list[str]], *, chat) -> tuple[list[dict], list[dict]]:
    """카드를 LLM에 한 번 읽혀 (받은 사양 행, 버린 읽기)를 돌려준다.

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
            futures = [pool.submit(contextvars.copy_context().run, read_values, b, codes, doc_parts, chat=chat) for b in batches]
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
