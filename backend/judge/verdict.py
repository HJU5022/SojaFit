"""후보 부품 하나의 조건별 비교와 판정 5종, 찾기 검색 조건, 후보 정렬.

- 역할: 역할 규칙 · 회로 값 · 사양 표 행으로 조건마다 통과 · 실패 · 확인 안 됨을 정하고 SPEC 3절 순서로 판정한다.
  숫자 비교는 이 파일에서만 한다(AGENTS 7번).
- 하지 않는 일: LLM · DB · MCP 호출(행과 값은 인자로 받는다), 답 문구 만들기(backend/multi_agent/messages.py).
- 출처: SPEC 3절, docs/specs/judge-agent.md What · EC · AC
"""
import re
from typing import Literal

from pydantic import BaseModel, Field

from backend.judge import conditions as C
from backend.judge import sheet_conditions as S

Verdict = Literal['IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT', 'NOT_VERIFIED', 'NOT_SUFFICIENT']
ORDER = ('IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT', 'NOT_VERIFIED', 'NOT_SUFFICIENT')  # 좋은 것부터


class Check(BaseModel):
    """조건 하나의 비교 결과(답의 조건 표 한 줄)."""
    code: str
    tier: str
    op: str
    basis: str
    threshold: float | list[float] | None = None
    value: float | list[float] | None = None
    unit: str | None = None
    condition: str | None = None
    citation: dict | None = None
    result: Literal['pass', 'fail', 'unverified']
    why: str = ''


class Judgement(BaseModel):
    """후보 하나의 판정."""
    part: str
    role: str
    verdict: Verdict
    checks: list[Check] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)    # 빠진 회로 값(알려 주면 판정할 수 있다)
    uncertain: list[str] = Field(default_factory=list)  # 발동 여부 · 온도를 몰라 빼고 판정한 조건, 기본값을 쓴 조건
    cautions: list[str] = Field(default_factory=list)   # 사람이 확인할 것(규칙의 cautions)
    board_change: bool | None = None                     # 패키지가 달라 기판 수정 필요(모르면 None)


def _value(r: dict, slot: str) -> float | None:
    """행의 비교 값. 정격 · 최대 칸이 비면 대표 · 최소로 물러난다. CJ는 대표값이 먼저다(spec_lookup.DEFAULT_SLOT과 같음)."""
    order = {'max': ('max', 'typ', 'min'), 'typ': ('typ', 'max', 'min'), 'min': ('min',)}[slot]
    return next((r[k] for k in order if r.get(k) is not None), None)


def _pick(rows: list[dict], codes: list[str], required: dict) -> tuple[str, list[dict], str]:
    """codes 순서대로 그 코드의 행 중 시험 조건이 required와 같은 행을 고른다 → (쓴 코드, 고른 행, 못 고른 이유)."""
    why = '사양 표에 값 없음'
    for code in codes:
        found = [r for r in rows if r['code'] == code]
        same = [r for r in found
                if S.compare(required, S.parse(r.get('test_condition')), S.parse((r.get('citation') or {}).get('table'))) == 'same']
        if same:
            return code, same, ''
        if found:
            why = '시험 조건이 다르거나 적혀 있지 않음'
    return codes[0], [], why


def _check(cond: dict, values: dict, conds: dict, rows: list[dict], original: dict | None) -> tuple[Check, list[str], str]:
    """조건 하나 → (결과, 빠진 회로 값, 불확실 메모)."""
    codes = cond['code'] if isinstance(cond['code'], list) else [cond['code']]
    bases = C._bases(cond)
    label = ' ~ '.join(bases)
    base = dict(code=codes[0], tier=cond['tier'], op=cond['op'], basis=label)
    lack = sorted({n for b in bases for n in C.names(b) if values.get(n) is None})
    note = ''
    if lack and cond.get('default'):
        bases, lack, note = [cond['default']], [], f"{codes[0]}: {label}에 쓸 값이 없어 기본값({cond['default']})으로 판정"
    if cond.get('at') and cond['at'] not in conds:
        lack.append(cond['at'])
    if lack:
        return Check(**base, result='unverified', why='빠진 값: ' + ', '.join(lack)), lack, note
    threshold = [C.evaluate(b, values, original) for b in bases]
    if any(t is None for t in threshold):
        return Check(**base, result='unverified', why='원래 부품 값 없음'), [], note
    required = {**conds.get('temp', {}), **(conds.get(cond['at'], {}) if cond.get('at') else {})}
    code, picked, why = _pick(rows, codes, required)
    shown = threshold[0] if len(threshold) == 1 else threshold
    if not picked:
        return Check(**{**base, 'code': code}, threshold=shown, result='unverified', why=why), [], note
    if cond['op'] == 'within':
        lows, highs = [_value(r, 'min') for r in picked], [_value(r, 'max') for r in picked]
        if None in lows or None in highs:
            return Check(**{**base, 'code': code}, threshold=shown, result='unverified', why='최소 · 최대 값 없음'), [], note
        value = [min(lows), max(highs)]
        ok = value[0] >= threshold[0] and value[1] <= threshold[1]
    else:
        found = [v for v in (_value(r, 'typ' if code == 'CJ' else 'max') for r in picked) if v is not None]
        if not found:
            return Check(**{**base, 'code': code}, threshold=shown, result='unverified', why='값 없음'), [], note
        value = min(found) if cond['op'] == '>=' else max(found)  # [왜] 같은 조건 행이 여럿이면 불리한 쪽으로 본다
        ok = value >= threshold[0] if cond['op'] == '>=' else value <= threshold[0]
    r = picked[0]
    return Check(**{**base, 'code': code}, threshold=shown, value=value, unit=r.get('unit'), condition=r.get('test_condition'),
                 citation=r.get('citation'), result='pass' if ok else 'fail'), [], note


def first_values(rows: list[dict]) -> dict[str, float]:
    """원래 부품의 코드별 첫 값(기준식의 orig.<코드>). 같은 코드가 여럿이면 표의 첫 행이다."""
    out = {}
    for r in rows:
        v = _value(r, 'typ' if r['code'] == 'CJ' else 'max')
        if v is not None:
            out.setdefault(r['code'], v)
    return out


def _not_worse(major: dict, rows: list[dict], original_rows: list[dict]) -> bool:
    """주요 정격(major)마다 같은 시험 조건의 원래 값과 비교해 하나도 나쁘지 않으면 True. 비교할 짝이 없으면 False."""
    if not major:
        return False
    for code, way in major.items():
        pairs = [(c, o) for o in original_rows if o['code'] == code for c in rows if c['code'] == code
                 and S.compare(S.parse(o.get('test_condition')), S.parse(c.get('test_condition')),
                               S.parse((c.get('citation') or {}).get('table'))) == 'same']
        if not pairs:
            return False
        for c, o in pairs:
            a, b = _value(c, 'max'), _value(o, 'max')
            if a is None or b is None or (a < b if way == 'higher' else a > b):
                return False
    return True


def board_change(footprint: str | None, packages: list[str] | None) -> bool | None:
    """원래 풋프린트 이름에 후보 패키지 이름이 하나도 없으면 True(기판 수정 필요). 둘 중 하나라도 모르면 None."""
    # shortcut: 이름 글자 포함으로만 본다(DO-214AC = SMA 같은 별명은 모른다), 별명 때문에 틀리는 사례가 나오면 별명 표를 둔다
    if not footprint or not packages:
        return None
    fp = re.sub(r'[^A-Z0-9]', '', footprint.upper())
    return not any(re.sub(r'[^A-Z0-9]', '', p.upper()) in fp for p in packages if p)


def judge_part(rule: dict, role: str, part: str, values: dict, conds: dict, rows: list[dict], *,
               original: dict | None = None, original_rows: list[dict] | None = None, identical: bool = False,
               footprint: str | None = None, packages: list[str] | None = None) -> Judgement:
    """후보 하나를 판정한다. values는 숫자 · 예/아니오, conds는 시험 조건(dict), rows는 후보의 사양 표 행."""
    checks, missing, uncertain = [], [], []
    for cond in rule['conditions']:
        if cond.get('unless') and values.get(cond['unless']) is True:
            continue
        if cond['tier'] == 'conditional' and cond.get('when'):
            trigger = values.get(cond['when'], conds.get(cond['when']))
            if trigger is None:
                uncertain.append(f"{cond['code'] if isinstance(cond['code'], str) else cond['code'][0]}: {cond['when']} 정보가 없어 이 조건을 빼고 판정")
                continue
            if trigger is False:
                continue
        check, lack, note = _check(cond, values, conds, rows, original)
        checks.append(check)
        missing += lack
        if note:
            uncertain.append(note)
    if 'temp' not in conds:
        uncertain.append('사용 온도를 몰라 표의 기본 온도(대부분 25°C) 값으로 판정')
    if identical:
        verdict = 'IDENTICAL'
    elif any(c.result == 'fail' for c in checks):
        verdict = 'NOT_SUFFICIENT'
    elif any(c.result == 'unverified' for c in checks):
        verdict = 'NOT_VERIFIED'
    elif original_rows and _not_worse(rule.get('major') or {}, rows, original_rows):
        verdict = 'SPEC_EQUIVALENT'
    else:
        verdict = 'ROLE_SUFFICIENT'
    return Judgement(part=part, role=role, verdict=verdict, checks=checks, missing=list(dict.fromkeys(missing)),
                     uncertain=uncertain, cautions=list(rule.get('cautions') or []), board_change=board_change(footprint, packages))


def search_conditions(rule: dict, values: dict, original: dict | None = None) -> list[dict]:
    """찾기용 사양 표 검색 조건(find_parts_by_specs). 시험 조건이 없는 필수 조건의 하한 · 상한만 쓰고 최대 10개(MCP 한도)."""
    out = []
    for cond in rule['conditions']:
        if cond['tier'] != 'required' or cond.get('at') or (cond.get('unless') and values.get(cond['unless']) is True):
            continue
        # shortcut: 대체 코드 중 첫 코드(VRRM)로만 거른다. VR만 적은 소신호 부품이 빠지는 사례가 보이면 코드마다 따로 찾아 합친다
        code = cond['code'][0] if isinstance(cond['code'], list) else cond['code']
        t = [C.evaluate(b, values, original) for b in C._bases(cond)]
        if None in t:
            continue
        if cond['op'] == '>=':
            out.append({'code': code, 'gte': t[0]})
        elif cond['op'] == '<=':
            out.append({'code': code, 'lte': t[0]})
        else:
            out += [{'code': code, 'slot': 'min', 'gte': t[0]}, {'code': code, 'slot': 'max', 'lte': t[1]}]
    return out[:10]


def rank(judgements: list[Judgement], per_verdict: int = 3, total: int = 5) -> tuple[list[Judgement], list[Judgement]]:
    """찾기 결과 → (보여 줄 후보, 확인 안 됨 후보). 불충족은 뺀다. 판정 순서 → 기판 수정 불필요 먼저 → 품번 순."""
    good = sorted((j for j in judgements if j.verdict in ORDER[:3]),
                  key=lambda j: (ORDER.index(j.verdict), j.board_change is True, j.part))
    shown, count = [], {}
    for j in good:
        if count.get(j.verdict, 0) < per_verdict and len(shown) < total:
            shown.append(j)
            count[j.verdict] = count.get(j.verdict, 0) + 1
    unverified = sorted((j for j in judgements if j.verdict == 'NOT_VERIFIED'), key=lambda j: j.part)[:total]
    return shown, unverified


def worse(a: str, b: str) -> str:
    """두 판정 중 나쁜 쪽(역할이 둘로 갈릴 때, EC-02)."""
    return a if ORDER.index(a) >= ORDER.index(b) else b
