"""읽기 뒤 품번 바로잡기: 읽기 LLM이 적은 원래 부품 · 후보 품번을 사용자 글에 있는 품번으로 맞춘다(LLM 호출 없음).

- 역할: `ground_part_names`가 (1) 원래 부품이 지금 달려 있는 부품으로 글에 적혀 있으면 그것으로 바꾸고,
  (2) 읽기의 품번이 글의 품번과 같지 않으면(끝 글자 'B'가 빠짐, 제조사 이름이 붙음) 글에서 유일하게 이어지는 품번으로 바꾼다.
- 하지 않는 일: 품번을 지어내기(맞는 글 품번이 없거나 둘 이상이면 읽은 그대로 둔다), 숫자 비교, LLM 호출.
- 출처: SPEC 8.3 "읽기 뒤 품번 바로잡기", 11-10 읽기 6회 반복(h4-02 · judgedev-16 품번 흔들림)
"""
import re

from backend.graph.nodes import QUANTITY, REVISION, STANDARD, WORD
from backend.multi_agent.facts import ORDER_CODE, refs_of

# [왜] 읽기가 품번을 'TSC 1N5817'처럼 제조사 이름과 함께 낸다. 사양 표 품번에는 제조사 이름이 없다(judge.py `_part`가 이 규칙으로 뗀다)
MAKER = re.compile(r'^\s*(?:TSC|Taiwan\s+Semiconductor)\s+', re.I)

# [왜] 품번 모양은 find_parts와 같다(영문 + 숫자 낱말). 주문 코드(R0G · L0G)가 띄어 붙은 'LL4448 L0G'는 하나로도 본다
_PART = r'(?:(?:TSC|Taiwan\s+Semiconductor)\s+)?([A-Za-z0-9][A-Za-z0-9.\-]*[A-Za-z0-9](?:[ ][RALM][A-Z0-9]G?(?![A-Za-z0-9]))?)'
# [왜] 지금 달린 부품을 말하는 표현만 작게 둔다. 후보는 '대신 X' · 'X로 바꿔도' · 'X를 쓰면'로 나와 아래 어느 모양에도 닿지 않는다
_PAST = r'(?:교체|변경)\s*(?:했(?!다면)|한\s*상태)|바꿔\s*달았|바꿔\s*끼웠'
_CURRENT = [
    r'(?:지금|현재)\s*(?:대상\s*)?[A-Z]{1,3}\d{1,3}\s*(?:은|는)\s*' + _PART + r'\s*(?:이다|이고|이며|입니다)',  # 지금 D5는 TSC 1N5231B이다
    r'(?:지금|현재)\s*' + _PART + r'\s*(?:을|를|이|가)?\s*(?:대신|쓰고\s*있|달아|달려)',                 # 지금 SS26 대신 … · 현재 TSC SS14가 달려 있다
    _PART + r'\s*(?:으로|로)\s*(?:' + _PAST + ')',                                                   # TSC SS26으로 교체했고
    _PART + r'\s*(?:을|를)\s*(?:달아\s*쓰고|쓰고\s*있|사용\s*중)',                                       # SS26을 달아 쓰고 있다
]


def _strip(name: str) -> str:
    return MAKER.sub('', name or '').strip()


def _key(name: str) -> str:
    """비교 열쇠: 제조사 이름 · 공백을 떼고 대문자로."""
    return re.sub(r'\s+', '', _strip(name)).upper()


def _is_part(word: str, refs: set[str]) -> bool:
    return (bool(re.search(r'[A-Za-z]', word) and re.search(r'\d', word))
            and not (word in refs or QUANTITY.fullmatch(word) or REVISION.fullmatch(word) or STANDARD.fullmatch(word)))


def part_tokens(text: str, refs: set[str]) -> list[str]:
    """글에서 품번으로 보이는 낱말을 순서대로. 주문 코드가 띄어 붙으면 기본 품번과 '기본 품번 주문코드' 둘 다 낸다."""
    words = list(WORD.finditer(text))
    out, order_codes = [], set()
    for i, m in enumerate(words):
        if i in order_codes or not _is_part(m.group(), refs):
            continue  # [왜] 앞 품번에 붙은 주문 코드(L0G)는 따로 품번이 아니다
        out.append(m.group())
        nxt = words[i + 1] if i + 1 < len(words) else None
        if nxt and re.fullmatch(r' +', text[m.end():nxt.start()]) and ORDER_CODE.fullmatch(nxt.group()):
            out.append(f'{m.group()} {nxt.group()}')
            order_codes.add(i + 1)
    return list(dict.fromkeys(out))


def _ground(name: str, tokens: list[str], skip: set[str]) -> str:
    """글의 품번과 같으면 글의 모양으로, 글 품번 하나가 읽은 값으로 시작하면 그것으로. 아니면 그대로."""
    k = _key(name)
    if not k:
        return name
    if hit := next((t for t in tokens if _key(t) == k), None):
        return hit
    # [주의] 앞부분 일치만 본다(1N5231 → 1N5231B). 3자 미만, 둘 이상, 다른 쪽 품번(skip)이면 건드리지 않는다
    longer = {_key(t): t for t in tokens if len(k) >= 3 and _key(t).startswith(k) and _key(t) not in skip}
    return next(iter(longer.values())) if len(longer) == 1 else name


def current_part(conditions: str, question: str, target: str, refs: set[str]) -> str | None:
    """사용자 글이 대상에 지금 달려 있다고 밝힌 품번 하나. 없거나 둘 이상이면 None.

    [주의] 대상 회로 기호(D2)가 나온 문장만 본다. 다른 부품(D3)의 교체 이야기를 대상의 것으로 읽지 않는다.
    """
    found = []
    for sentence in re.split(r'(?<=[.!?。])\s+|\n', f'{conditions}\n{question}'):
        if target and not re.search(rf'(?<![A-Za-z0-9]){re.escape(target)}(?![A-Za-z0-9])', sentence):
            continue
        for pattern in _CURRENT:
            for m in re.finditer(pattern, sentence):
                name = _strip(m.group(1))
                if _is_part(name.split()[0], refs):
                    found.append(name)
    keys = {_key(f): f for f in found}
    return next(iter(keys.values())) if len(keys) == 1 else None


def ground_part_names(original: str, candidates: list[str], state: dict) -> tuple[str, list[str]]:
    """읽은 원래 부품 · 후보 품번을 사용자 글(사용 조건 · 질문 · 넷리스트 값)의 품번으로 맞춘다. 출력은 제조사 이름 없이 글에 쓴 모양."""
    part = state.get('target_part') or {}
    conditions, question = state.get('conditions', ''), state.get('question', '')
    refs = refs_of(part)
    tokens = part_tokens(f'{conditions}\n{question}\n{part.get("value", "")}', refs)
    cands = [_ground(c, tokens, {_key(original)}) for c in candidates]
    new = _ground(original, tokens, {_key(c) for c in candidates})
    # 글이 밝힌 현재 부품이 있으면 넷리스트 값보다 앞선다. 후보와 같은 품번이면 후보를 원래로 읽은 것이므로 따르지 않는다
    if (now := current_part(conditions, question, part.get('ref') or state.get('target', ''), refs)) and _key(now) not in {_key(c) for c in cands}:
        new = _ground(now, tokens, set())
    return new, list(dict.fromkeys(cands))
