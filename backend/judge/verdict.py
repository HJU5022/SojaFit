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
# [왜] 역전압 정격은 온도로 줄지 않아 사용 온도(temp)를 맞추지 않는다. 전류 · 전력 정격과 특성 값(VF · IR · VBR · VC 등)은 온도를 맞춘다
VOLTAGE_RATINGS = ('VRRM', 'VR', 'VRWM')


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
    exempt: Literal['schottky', 'sic', 'none'] = 'schottky'  # TRR 면제 범위(규칙의 exempt, 면제는 판정 노드가 한다)


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


def _same_condition(a: dict, b: dict) -> bool:
    """두 사양 표 행의 시험 조건(표 제목 기본 조건 포함)이 같은지. 한쪽에만 적힌 항목이 있으면 같지 않다."""
    x, y = (S.fill(S.parse(r.get('test_condition')), S.parse((r.get('citation') or {}).get('table'))) for r in (a, b))
    return S.compare(x, y) == 'same' and S.compare(y, x) == 'same'


def _original(original_rows: list[dict], code: str, row: dict | None) -> dict[str, float]:
    """기준식의 orig.<코드> 값. 비교하는 코드(code)는 후보 행(row)과 시험 조건이 같은 원래 행의 값만 쓴다."""
    # [주의] 다른 코드(R04 · R18 PD 기준식의 orig.VZ)는 후보 행과 시험 조건을 맞출 수 없어 원래 부품의 첫 행 값을 쓴다
    other = first_values([o for o in original_rows if o['code'] != code])
    same = first_values([o for o in original_rows if o['code'] == code and row is not None and _same_condition(o, row)])
    return {**other, **same}


def _margin(op: str, value, t: list[float]) -> float:
    """기준까지 남은 여유. 0 이상이면 통과."""
    if op == 'within':
        return min(value[0] - t[0], t[1] - value[1])
    return value - t[0] if op == '>=' else t[0] - value


def _check(cond: dict, values: dict, conds: dict, rows: list[dict], original_rows: list[dict]) -> tuple[Check, list[str], str]:
    """조건 하나 → (결과, 빠진 회로 값, 불확실 메모)."""
    codes = cond['code'] if isinstance(cond['code'], list) else [cond['code']]
    bases = C._bases(cond)
    label = ' ~ '.join(bases)
    base = dict(code=codes[0], tier=cond['tier'], op=cond['op'], basis=label, exempt=cond.get('exempt', 'schottky'))
    lack = sorted({n for b in bases for n in C.names(b) if values.get(n) is None})
    note = ''
    if lack and cond.get('default'):
        bases, note = [cond['default']], f"{codes[0]}: {label}에 쓸 값이 없어 기본값({cond['default']})으로 판정"
        # [왜] 기본값 식도 회로 값을 쓸 수 있다(R17 처짐 기본값의 v_peak · c_hold). 그 값이 없으면 빠진 값으로 알린다
        lack = sorted(n for n in C.names(cond['default']) if values.get(n) is None)
    if cond.get('at') and cond['at'] not in conds:
        lack.append(cond['at'])
    if lack:
        return Check(**base, result='unverified', why='빠진 값: ' + ', '.join(lack)), lack, note
    if {c for b in bases for c in C.orig_codes(b)} - {o['code'] for o in original_rows}:
        return Check(**base, result='unverified', why='원래 부품 값 없음'), [], note
    temp = {} if set(codes) <= set(VOLTAGE_RATINGS) else conds.get('temp', {})
    required = {**temp, **(conds.get(cond['at'], {}) if cond.get('at') else {})}
    code, picked, why = _pick(rows, codes, required)

    def limits(r: dict | None) -> list[float] | None:
        t = [C.evaluate(b, values, _original(original_rows, code, r)) for b in bases]
        return None if None in t else t

    def shown(t):
        return t if t is None or len(t) > 1 else t[0]
    if not picked:
        return Check(**{**base, 'code': code}, threshold=shown(limits(None)), result='unverified', why=why), [], note
    pairs = [(r, t) for r in picked if (t := limits(r))]
    if not pairs:
        return Check(**{**base, 'code': code}, result='unverified', why='원래 부품의 같은 시험 조건 값 없음'), [], note
    found = []
    for r, t in pairs:
        value = [_value(r, 'min'), _value(r, 'max')] if cond['op'] == 'within' else _value(r, 'typ' if code == 'CJ' else 'max')
        if cond['op'] == 'within' and None in value:
            return Check(**{**base, 'code': code}, threshold=shown(t), result='unverified', why='최소 · 최대 값 없음'), [], note
        if value is not None:
            found.append((r, t, value))
    if not found:
        return Check(**{**base, 'code': code}, threshold=shown(pairs[0][1]), result='unverified', why='값 없음'), [], note
    r, t, value = min(found, key=lambda x: _margin(cond['op'], x[2], x[1]))  # [왜] 같은 조건 행이 여럿이면 불리한 쪽으로 본다
    return Check(**{**base, 'code': code}, threshold=shown(t), value=value, unit=r.get('unit'), condition=r.get('test_condition'),
                 citation=r.get('citation'), result='pass' if _margin(cond['op'], value, t) >= 0 else 'fail'), [], note


def _check_any(cond: dict, values: dict, conds: dict, rows: list[dict], original_rows: list[dict]) -> tuple[Check, list[str], str]:
    """"A 또는 B" 묶음(any) → (결과, 빠진 회로 값, 불확실 메모). 멤버 하나라도 통과하면 통과, 모두 계산돼 실패하면 실패, 그 밖은 확인 안 됨."""
    done = [_check({**m, 'tier': cond['tier']}, values, conds, rows, original_rows) for m in cond['any']]
    checks = [c for c, _, _ in done]
    if any(c.result == 'pass' for c in checks):
        result = 'pass'
        i = next(k for k, c in enumerate(checks) if c.result == 'pass')
    else:
        result = 'fail' if all(c.result == 'fail' for c in checks) else 'unverified'
        # [왜] 통과가 아니면 TRR 멤버로 알린다. 판정 노드의 쇼트키 면제가 TRR 결과만 보고 묶음을 통과로 바꾸기 때문이다
        i = next((k for k, c in enumerate(checks) if c.code == 'TRR'), next(k for k, c in enumerate(checks) if c.result == result))
    why = checks[i].why if result != 'unverified' else ' / '.join(f'{c.code}: {c.why}' for c in checks if c.result == 'unverified')
    # [왜] 빠진 회로 값은 어느 멤버도 계산할 수 없을 때만 알린다(멤버 하나를 지금 값으로 계산할 수 있으면 묻지 않는 needed와 같음)
    lacks = [lack for _, lack, _ in done]
    missing = list(dict.fromkeys(n for lack in lacks for n in lack)) if all(lacks) else []
    label = ' 또는 '.join(f'{c.code} {c.op} {c.basis}' for c in checks)
    return checks[i].model_copy(update={'basis': label, 'result': result, 'why': why}), missing, done[i][2]


def _name(cond: dict) -> str:
    """조건 이름(메모용): 첫 코드. "A 또는 B" 묶음이면 멤버 이름을 ' 또는 '로 잇는다."""
    if 'any' in cond:
        return ' 또는 '.join(_name(m) for m in cond['any'])
    return cond['code'] if isinstance(cond['code'], str) else cond['code'][0]


def first_values(rows: list[dict]) -> dict[str, float]:
    """행들의 코드별 첫 값. 같은 코드가 여럿이면 표의 첫 행이다."""
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
               original_rows: list[dict] | None = None, identical: bool = False,
               footprint: str | None = None, packages: list[str] | None = None) -> Judgement:
    """후보 하나를 판정한다. values는 숫자 · 예/아니오, conds는 시험 조건(dict), rows는 후보의 사양 표 행, original_rows는 원래 부품의 행."""
    checks, missing, uncertain = [], [], []
    for cond in rule['conditions']:
        if cond.get('unless') and values.get(cond['unless']) is True:
            continue
        if cond['tier'] == 'conditional' and cond.get('when'):
            trigger = values.get(cond['when'], conds.get(cond['when']))
            if trigger is None:
                uncertain.append(f"{_name(cond)}: {cond['when']} 정보가 없어 이 조건을 빼고 판정")
                continue
            if trigger is False:
                continue
        check, lack, note = (_check_any if 'any' in cond else _check)(cond, values, conds, rows, original_rows or [])
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


def search_conditions(rule: dict, values: dict) -> list[dict]:
    """찾기용 사양 표 검색 조건(find_parts_by_specs). 시험 조건이 없는 필수 조건의 하한 · 상한만 쓰고 최대 10개(MCP 한도)."""
    out = []
    for cond in rule['conditions']:
        if cond['tier'] != 'required' or cond.get('at') or (cond.get('unless') and values.get(cond['unless']) is True):
            continue
        if 'any' in cond or any(C.orig_codes(b) for b in C._bases(cond)):
            # [왜] "A 또는 B"는 한 코드로 거를 수 없고, 원래 부품 값(orig.*)은 시험 조건이 같은 행끼리 판정에서 본다
            continue
        # shortcut: 대체 코드 중 첫 코드(VRRM)로만 거른다. VR만 적은 소신호 부품이 빠지는 사례가 보이면 코드마다 따로 찾아 합친다
        code = cond['code'][0] if isinstance(cond['code'], list) else cond['code']
        t = [C.evaluate(b, values) for b in C._bases(cond)]
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
