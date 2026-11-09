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
# [왜] 제너 VZ 행은 청크를 나눌 때 표 제목의 "(TA = 25°C unless otherwise noted)"가 떨어졌다(제목 'ELECTRICAL PART NUMBER' 등,
#      VZ 3,683행 중 3,668행이 제목에 조건 없음). 온도를 적은 VZ 행 78개는 모두 TA = 25°C다(11-06 실측).
#      그래서 제목이 조건을 적지 않은 VZ 행만 TA = 25°C로 본다. 다른 코드는 그대로 "적혀 있지 않음"(넓히면 다른 역할 판정이 바뀐다)
UNSTATED = {'VZ': {'TA': 25.0}}


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
    package_citation: dict | None = None                 # 기판 수정이 필요할 때 후보 패키지 행의 근거(답에 인용한다)


def _room(temp: dict) -> bool:
    """사용 온도 조건이 주변 온도 25°C(TJ도 적었으면 그것도 25°C)뿐인가.

    [주의] TJ만 25°C면 상온이 아니다: 표 정격은 TA = 25°C라 접합 온도만으로는 같은 조건이 아니다(판정 dev n01 해석).
    """
    return abs(temp.get('TA', -1.0) - 25.0) < 0.5 and abs(temp.get('TJ', 25.0) - 25.0) < 0.5 and set(temp) <= {'TA', 'TJ'}


def _value(r: dict, slot: str) -> float | None:
    """행의 비교 값. 정격 · 최대 칸이 비면 대표 · 최소로 물러난다. CJ는 대표값이 먼저다(spec_lookup.DEFAULT_SLOT과 같음)."""
    order = {'max': ('max', 'typ', 'min'), 'typ': ('typ', 'max', 'min'), 'min': ('min',)}[slot]
    return next((r[k] for k in order if r.get(k) is not None), None)


def _table(r: dict) -> dict:
    """행의 표 제목 기본 조건. 제목이 조건을 적지 않았으면 그 코드의 관례 조건(UNSTATED, 없으면 빈 조건)."""
    return S.parse((r.get('citation') or {}).get('table')) or dict(UNSTATED.get(r['code'], {}))


def _pick(rows: list[dict], codes: list[str], required: dict) -> tuple[str, list[dict], str]:
    """codes 순서대로 그 코드의 행 중 시험 조건이 required와 같은 행을 고른다 → (쓴 코드, 고른 행, 못 고른 이유)."""
    why = '사양 표에 값 없음'
    for code in codes:
        found = [r for r in rows if r['code'] == code]
        same = [r for r in found if S.compare(required, S.parse(r.get('test_condition')), _table(r)) == 'same']
        if same:
            return code, same, ''
        if found:
            why = '시험 조건이 다르거나 적혀 있지 않음'
    return codes[0], [], why


def _rated_voltage(rows: list[dict] | None) -> float | None:
    """그 품번의 정격 역전압(VRRM, 없으면 VR). '@ rated VR' 시험 조건의 실제 전압이다."""
    return next((r.get('max') for code in ('VRRM', 'VR') for r in rows or [] if r['code'] == code and r.get('max') is not None), None)


def _same_condition(a: dict, b: dict, a_rows: list[dict] | None = None, b_rows: list[dict] | None = None) -> bool:
    """두 사양 표 행의 시험 조건(표 제목 기본 조건 포함)이 같은지. 한쪽에만 적힌 항목이 있으면 같지 않다.

    [왜] '@ rated VR'은 품번마다 실제 전압이 다르다(SS34 40 V · SS36 60 V). 품번 행을 주면 정격 역전압으로 바꿔 비교한다(판정 dev 02 해석:
         시험 전압이 다르면 비교할 수 없다). 주지 않으면 예전처럼 'rated'끼리 같다고 본다
    """
    x, y = (S.fill(S.parse(r.get('test_condition')), _table(r)) for r in (a, b))
    for cond, rows in ((x, a_rows), (y, b_rows)):
        if cond.get('VR') == 'rated' and (v := _rated_voltage(rows)) is not None:
            cond['VR'] = v
    return S.compare(x, y) == 'same' and S.compare(y, x) == 'same'


def _original(original_rows: list[dict], code: str, row: dict | None, rows: list[dict] | None = None) -> dict[str, float]:
    """기준식의 orig.<코드> 값. 비교하는 코드(code)는 후보 행(row)과 시험 조건이 같은 원래 행의 값만 쓴다."""
    # [주의] 다른 코드(R04 · R18 PD 기준식의 orig.VZ)는 후보 행과 시험 조건을 맞출 수 없어 원래 부품의 첫 행 값을 쓴다
    other = first_values([o for o in original_rows if o['code'] != code])
    same = first_values([o for o in original_rows if o['code'] == code and row is not None and _same_condition(o, row, original_rows, rows)])
    return {**other, **same}


def _margin(op: str, value, t: list[float]) -> float:
    """기준까지 남은 여유. 0 이상이면 통과."""
    if op == 'within':
        return min(value[0] - t[0], t[1] - value[1])
    return value - t[0] if op == '>=' else t[0] - value


CURRENTS = ('i_max', 'i_out', 'i_coil', 'i_d', 'i_limit', 'i_z')  # 다이오드에 흐르는 동작 전류(평균 · 정상) 값 이름, 앞에서부터 쓴다
WAVE_10_1000 = re.compile(r'10\s*/\s*1000|\btp\s*=\s*1\s*ms\b', re.I)  # TSC TVS 문서의 정격 서지 파형 표기('10/1000µs waveform', 'tp = 1ms')
WAVE_8_20 = re.compile(r'\b8\s*/\s*20\b')


def _within_rating(user: dict, wave: str, rows: list[dict]) -> bool:
    """사용자 서지 조건이 정격과 같은 파형이고, 서지 전류를 적었다면 그 전류가 후보의 정격 IPP 이하인가."""
    if user.get('wave') and user['wave'] != wave.removesuffix('us'):
        return False  # 다른 파형(8/20 대 10/1000)은 정격 값으로 바꿔 볼 수 없다
    ipp = next((r.get('max') for r in rows if r['code'] == 'IPP' and r.get('max') is not None), None)
    return user.get('IPP') is None or (ipp is not None and user['IPP'] <= ipp)


def _waveform(rows: list[dict]) -> str | None:
    """TVS 부품 행들의 정격 서지 파형. PPPM · IPP · VC 행 조건(표 제목 포함)에서 읽고, 모르면 None."""
    # [왜] SMAJ · SMCJ의 'tp = 1ms'와 SMBJ의 '10/1000µs'는 주석 · 그림이 가리키는 같은 10/1000 µs 파형이다(판정 dev 해석 8, 판정 기준표 R06)
    for r in rows:
        if r['code'] in ('PPPM', 'IPP', 'VC'):
            text = f"{r.get('test_condition') or ''} {(r.get('citation') or {}).get('table') or ''}"
            if WAVE_10_1000.search(text):
                return '10/1000us'
            if WAVE_8_20.search(text):
                return '8/20us'
    return None


def _known(cond: dict, rows: list[dict], codes: list[str]) -> dict:
    """비교할 기준을 못 만들 때도 답에 보일 후보 값과 근거: 그 코드의 표 기본 조건 행(없으면 첫 행)."""
    # [왜] 회로 값이 빠져 기준을 못 세우면 조건 줄에 값 · 근거가 없어 답 전체에 인용이 사라졌다. 판정은 그대로 '확인 안 됨'이고
    #      후보 정격과 그 쪽만 보여 준다(값 비교 없음, 11-07 v2 draft30-m04 · h04 · h05)
    code, picked, _ = _pick(rows, codes, {})
    r = picked[0] if picked else next((x for x in rows if x['code'] in codes), None)
    if not r:
        return {}
    value = r.get(cond['slot']) if cond.get('slot') else _value(r, 'typ' if r['code'] == 'CJ' else 'max')
    return {'code': r['code'], 'value': value, 'unit': r.get('unit'), 'condition': r.get('test_condition'), 'citation': r.get('citation')}


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
    rated = False  # 두 문서의 같은 정격 파형 값끼리 비교하는가(사용자 시험 조건의 행 대신)
    wave = _waveform(rows) if cond.get('at') and cond.get('at_default') == 'rated' else None
    same_wave = bool(wave) and wave == _waveform(original_rows)
    if cond.get('at') and cond['at'] not in conds:
        # [왜] at_default: rated면, 사용자가 파형을 말하지 않아도 두 데이터시트가 같은 정격 파형이면 정격 값끼리 비교한다(판정 기준표 R06)
        if same_wave:
            rated = True
        else:
            lack.append(cond['at'])
    elif same_wave and _within_rating(conds[cond['at']], wave, rows):
        # [왜] 사용자가 정격과 같은 파형의 서지('피크 10A의 단발 10/1000µs')를 말해도 데이터시트에는 정격 IPP(27A) 행만 있다.
        #      서지 전류가 후보의 정격 IPP 이하이면 같은 파형의 정격 값끼리 비교한다(판정 기준표 R06, v3-09 SMBJ14AH)
        rated = True
    if lack:
        return Check(**{**base, **_known(cond, rows, codes)}, result='unverified', why='빠진 값: ' + ', '.join(lack)), lack, note
    if {c for b in bases for c in C.orig_codes(b)} - {o['code'] for o in original_rows}:
        return Check(**{**base, **_known(cond, rows, codes)}, result='unverified', why='원래 부품 값 없음'), [], note
    temp = {} if set(codes) <= set(VOLTAGE_RATINGS) else conds.get('temp', {})
    required = {**temp, **(conds.get(cond['at'], {}) if cond.get('at') and not rated else {})}
    if cond.get('at_current'):
        # 사용자 VF 한계는 회로 전류에서 본다(conditions.user_conditions). 전류를 모르면 비교할 행을 고를 수 없다
        current = next((values[n] for n in CURRENTS if values.get(n) is not None), None)
        if current is None:
            return Check(**{**base, **_known(cond, rows, codes)}, result='unverified', why='회로 전류를 몰라 그 전류의 VF를 볼 수 없음'), [], note
        required = {**required, 'IF': current}
    code, picked, why = _pick(rows, codes, required)
    if picked and 'temp' not in conds and code not in VOLTAGE_RATINGS:
        # [왜] 사용 온도를 모르면 메모('표의 기본 온도(대부분 25°C) 값으로 판정')대로 25°C(또는 온도를 안 적은) 행을 쓴다.
        #      모든 온도 행에서 가장 불리한 행을 고르면 TJ = 100°C 누설전류로 불충족을 냈다(11-06 v3-07 SS16)
        def temp_of(r):
            c = S.fill(S.parse(r.get('test_condition')), _table(r))
            return c.get('TJ', c.get('TA'))
        room = [r for r in picked if temp_of(r) in (None, 25.0)]
        picked = room or picked

    def limits(r: dict | None) -> list[float] | None:
        # [주의] 정격 비교면 원래 부품 값도 그 부품의 정격 행(첫 행)에서 쓴다. 정격 IPP가 품번마다 달라 시험 조건을 맞추면 원래 값이 없어진다
        orig = first_values(original_rows) if rated else _original(original_rows, code, r, rows)
        t = [C.evaluate(b, values, orig) for b in bases]
        return None if None in t else t

    def shown(t):
        return t if t is None or len(t) > 1 else t[0]
    if not picked:
        return Check(**{**base, 'code': code}, threshold=shown(limits(None)), result='unverified', why=why), [], note
    pairs = [(r, t) for r in picked if (t := limits(r))]
    if not pairs:
        return Check(**{**base, 'code': code}, result='unverified', why='원래 부품의 같은 시험 조건 값 없음'), [], note
    slot = cond.get('slot')
    have = [o for o in original_rows if o['code'] in codes]
    if slot and set(codes) & {c for b in bases for c in C.orig_codes(b)} and have and not any(o.get(slot) is not None for o in have):
        # [왜] 원래 부품 문서가 공칭값만 적으면(1N5231B VZ 5.1 V) orig.VZ는 공칭값이다. 후보 최대값(MMSZ5231B 5.36 V)과 비교하면
        #      칸이 달라 같은 5.1 V 제너가 불충족이 났다(판정 dev 16, 11-09). 원래 값이 있는 칸으로 후보도 맞춘다(공칭끼리)
        slot = next((s for s in ('typ', 'max', 'min') if any(o.get(s) is not None for o in have)), slot)
    found = []
    for r, t in pairs:
        if cond['op'] == 'within':
            value = [_value(r, 'min'), _value(r, 'max')]
        elif slot:
            # [왜] slot을 적은 조건은 그 칸 값만 본다. 제너 VZ는 최소 · 대표 · 최대가 한 행씩이라, 물러나면 최소 행이 최대로 읽힌다
            value = r.get(slot)
        else:
            value = _value(r, 'typ' if code == 'CJ' else 'max')
        if cond['op'] == 'within' and None in value:
            return Check(**{**base, 'code': code}, threshold=shown(t), result='unverified', why='최소 · 최대 값 없음'), [], note
        if value is not None:
            found.append((r, t, value))
    if not found:
        return Check(**{**base, 'code': code}, threshold=shown(pairs[0][1]), result='unverified', why='값 없음'), [], note
    r, t, value = min(found, key=lambda x: _margin(cond['op'], x[2], x[1]))  # [왜] 같은 조건 행이 여럿이면 불리한 쪽으로 본다
    result, why = ('pass', '') if _margin(cond['op'], value, t) >= 0 else ('fail', '')
    if result == 'fail' and code == 'IR' and cond['op'] == '<=' and not _ir_fail_holds(r, rows, values):
        # [왜] 누설전류는 역전압이 낮을수록 작다. 실제 역전압보다 높은 시험 전압(정격 VR)에서 한계를 넘었다고 실제로 넘는다고 단정할 수 없다(v3-07, 판정 dev 해석 1)
        result, why = 'unverified', '시험 역전압이 실제 역전압보다 높아(또는 실제 역전압을 몰라) 불충족을 단정할 수 없음'
    return Check(**{**base, 'code': code}, threshold=shown(t), value=value, unit=r.get('unit'), condition=r.get('test_condition'),
                 citation=r.get('citation'), result=result, why=why), [], note


def _ir_fail_holds(row: dict, rows: list[dict], values: dict) -> bool:
    """IR이 한계를 넘은 행의 시험 역전압이 실제 회로의 역전압 이하인가(그래야 불충족이 확실하다). 둘 중 하나라도 모르면 False."""
    actual = next((values[n] for n in ('v_reverse_max', 'v_in_max', 'v_line_max', 'v_cc') if values.get(n) is not None), None)
    vr = S.parse(row.get('test_condition')).get('VR')
    if vr is None and re.search(r'\brated\b', row.get('test_condition') or '', re.I):
        vr = 'rated'  # 사양 표가 '@ rated; TJ = 25°C'처럼 VR 글자를 뗀 경우
    if vr == 'rated':  # '@ rated VR'은 그 품번의 정격 역전압(VRRM, 없으면 VR)이다
        vr = next((x.get('max') for x in rows if x['code'] in ('VRRM', 'VR') and x.get('max') is not None), None)
    return actual is not None and isinstance(vr, (int, float)) and vr <= actual


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
    """행들의 코드별 첫 값. 같은 코드가 여럿이면 표의 첫 행이다. VZ만 최대 VZ(최대 칸 값 중 가장 큰 것)다."""
    out = {}
    for r in rows:
        v = _value(r, 'typ' if r['code'] == 'CJ' else 'max')
        if v is not None:
            out.setdefault(r['code'], v)
    # [왜] 제너 VZ는 최소 · 대표 · 최대가 한 행씩이고 첫 행이 최소다(VZ 품번 1,322개 중 1,202개, 11-06 실측). orig.VZ는 최대 VZ다(R04 규칙)
    if vz := [r['max'] for r in rows if r['code'] == 'VZ' and r.get('max') is not None]:
        out['VZ'] = max(vz)
    return out


# [왜] 사람 판정(judge_dev README 해석 6)의 주요 정격은 역할 규칙의 major에 더해, 두 문서가 같은 시험 조건으로 적은 정격 · 특성
#      (PD · IFSM · IR · TJ 최대, VF, TVS의 VRWM · VBR 등)이다. 판정 dev 20(SMBJ14A → SMBJ13A, VWM · VBR이 낮아 역할상 충분)을 코드가 사양 동등으로 냈다.
#      역할 major는 짝이 없으면 사양 동등이 아니고, 이 추가 항목은 두 문서가 같은 조건으로 적었을 때만 본다
EXTRA_MAJOR = {'VRRM': 'higher', 'IF_AV': 'higher', 'IFSM': 'higher', 'VF': 'lower', 'IR': 'lower', 'PD': 'higher', 'TJ_MAX': 'higher',
               'VRWM': 'higher', 'VBR': 'higher', 'IPP': 'higher', 'VC': 'lower', 'PPPM': 'higher'}


def _not_worse(major: dict, rows: list[dict], original_rows: list[dict]) -> bool:
    """주요 정격(major)마다 같은 시험 조건의 원래 값과 비교해 하나도 나쁘지 않고, 추가 항목(EXTRA_MAJOR)도 같은 조건 짝이 있으면 나쁘지 않을 때 True."""
    if not major:
        return False
    extra = {k: v for k, v in EXTRA_MAJOR.items() if k not in major}
    return _compare_major(major, rows, original_rows, required=True) and _compare_major(extra, rows, original_rows, required=False)


def _slots(r: dict) -> frozenset:
    return frozenset(k for k in ('min', 'typ', 'max') if r.get(k) is not None)


def _compare_major(major: dict, rows: list[dict], original_rows: list[dict], required: bool) -> bool:
    """major 항목마다 비교한다. required면 짝이 없을 때 False, 아니면 짝이 없는 항목은 건너뛴다."""
    # [왜] TVS의 PPPM · IPP · VC는 두 문서가 같은 정격 파형이면 각 품번의 정격 값끼리 비교한다(판정 조건과 같은 규칙, 판정 기준표 R06).
    #      시험 조건 글('10/1000µs waveform' 대 'tp = 1ms')만 맞추면 짝이 없어 사양 동등을 못 냈다(판정 dev 19 · 22)
    wave = _waveform(rows)
    rated = bool(wave) and wave == _waveform(original_rows)
    for code, way in major.items():
        if rated and code in ('PPPM', 'IPP', 'VC'):
            first = [next((r for r in group if r['code'] == code), None) for group in (rows, original_rows)]
            pairs = [tuple(first)] if None not in first else []
        elif required:
            pairs = [(c, o) for o in original_rows if o['code'] == code for c in rows if c['code'] == code
                     and S.compare(S.parse(o.get('test_condition')), S.parse(c.get('test_condition')), _table(c)) == 'same']
        else:
            # [주의] 추가 항목은 두 행의 시험 조건이 서로 같을 때만 짝짓는다(한쪽 조건이 비어 다른 온도 행과 짝지어지지 않게)
            pairs = [(c, o) for o in original_rows if o['code'] == code for c in rows if c['code'] == code and _same_condition(o, c, original_rows, rows)]
        # [주의] 최소 · 대표 · 최대가 행마다 따로인 항목(VBR · VZ)은 같은 칸끼리만 짝짓는다. 후보 최소 행(15.6)을 원래 최대 행(17.2)과 비교해
        #        '낮다'로 봤다(11-06 판정 dev 19 · 22 · 24)
        pairs = [(c, o) for c, o in pairs if _slots(c) == _slots(o)]
        if not pairs:
            if required:
                return False
            continue
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


def _off(cond: dict, values: dict) -> bool:
    """unless 값이 있고 거짓이 아니면 그 조건은 꺼진다(when의 반대). 플래그는 참일 때, 숫자(R04 vz_min)는 주어졌을 때다."""
    v = values.get(cond['unless']) if cond.get('unless') else None
    return v is not None and v is not False


def judge_part(rule: dict, role: str, part: str, values: dict, conds: dict, rows: list[dict], *,
               original_rows: list[dict] | None = None, identical: bool = False, identical_citation: dict | None = None,
               footprint: str | None = None, packages: list[str] | None = None) -> Judgement:
    """후보 하나를 판정한다. values는 숫자 · 예/아니오, conds는 시험 조건(dict), rows는 후보의 사양 표 행, original_rows는 원래 부품의 행.

    identical_citation: 주문 코드만 달라 동일품일 때의 근거(주문 정보 표 행). 주면 조건 표 맨 앞에 그 근거 줄을 넣는다.
    """
    checks, missing, uncertain = [], [], []
    temp_known = 'temp' in conds
    if temp_known and _room(conds['temp']):
        # [왜] 사용 온도 25°C는 '모름'과 같이 25°C(또는 온도를 안 적은) 행을 쓴다. 읽기가 'TA=25°C'를 적은 회차만 온도를 안 적은 행이
        #      '확인 안 됨'이 되어, 같은 질문의 판정이 회차마다 바뀌었다(11-06 판정 dev 05 · 12, v3-08 일관성 측정)
        conds = {k: v for k, v in conds.items() if k != 'temp'}
    for cond in rule['conditions']:
        if _off(cond, values):
            continue
        if cond['tier'] == 'conditional' and cond.get('when'):
            trigger = values.get(cond['when'], conds.get(cond['when']))
            if trigger is None:
                uncertain.append(f"{_name(cond)}: {cond['when']} 정보가 없어 이 조건을 빼고 판정")
                continue
            if trigger is False:
                continue
        check, lack, note = (_check_any if 'any' in cond else _check)(cond, values, conds, rows, original_rows or [])
        defaulted = bool(note) and '기본값' in note
        if (cond['tier'] == 'conditional' or defaulted) and check.result == 'unverified' and check.why == '원래 부품 값 없음':
            # [왜] 회로 값이 없어 원래 부품 값으로 대신한(기본값) 조건도, 원래 부품 문서가 없으면 비교할 기준이 없다. 대신할 값이 없는 것이지
            #      후보가 나쁘다는 근거가 아니라 조건부와 같이 빼고 남긴다(11-07 c20-01 R07 IFSM 기본값 orig.IFSM, 원래 D_Schottky 품번 모름)
            # [왜] 조건부 항목(외부 단자의 VESD 등)을 원래 부품 문서가 적지 않았으면 비교할 기준이 없다. 후보가 원래보다 나쁘다고 볼 근거가 아니라
            #      이 조건을 빼고 사람이 확인할 것으로 남긴다. SMBJ14A → SMBJ14AH가 VESD 때문에 확인 안 됨이 됐다(11-06 v3-09)
            uncertain.append(f"{check.code}: 원래 부품 문서에 값이 없어 이 조건을 빼고 판정")
            continue
        checks.append(check)
        missing += lack
        if note:
            uncertain.append(note)
    if not temp_known:
        uncertain.append('사용 온도를 몰라 표의 기본 온도(대부분 25°C) 값으로 판정')
    if identical_citation:
        checks.insert(0, Check(code='ORDER_CODE', tier='required', op='=', basis='같은 기본 품번, 주문 코드만 다름', condition='—',
                               citation=identical_citation, result='pass', why='동일품'))
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
    change = board_change(footprint, packages)
    # [왜] 기판 수정이 필요하다는 줄도 근거(후보 패키지 행)를 단다. v2 draft30-m04 · h04는 정답이 이 패키지 쪽이었다
    package_cite = next((r.get('citation') for r in rows if r['code'] == 'PACKAGE' and r.get('citation')), None) if change else None
    return Judgement(part=part, role=role, verdict=verdict, checks=checks, missing=list(dict.fromkeys(missing)),
                     uncertain=uncertain, cautions=list(rule.get('cautions') or []), board_change=change, package_citation=package_cite)


def search_conditions(rule: dict, values: dict) -> list[dict]:
    """찾기용 사양 표 검색 조건(find_parts_by_specs). 시험 조건이 없는 필수 조건의 하한 · 상한만 쓰고 최대 10개(MCP 한도)."""
    out = []
    for cond in rule['conditions']:
        if cond['tier'] != 'required' or cond.get('at') or _off(cond, values):
            continue
        if 'any' in cond or any(C.orig_codes(b) for b in C._bases(cond)):
            # [왜] "A 또는 B"는 한 코드로 거를 수 없고, 원래 부품 값(orig.*)은 시험 조건이 같은 행끼리 판정에서 본다
            continue
        # shortcut: 대체 코드 중 첫 코드(VRRM)로만 거른다. VR만 적은 소신호 부품이 빠지는 사례가 보이면 코드마다 따로 찾아 합친다
        code = cond['code'][0] if isinstance(cond['code'], list) else cond['code']
        t = [C.evaluate(b, values) for b in C._bases(cond)]
        if None in t:
            continue
        slot = {'slot': cond['slot']} if cond.get('slot') else {}  # [왜] 칸을 정한 조건(VZ 공칭 = 대표 칸)은 찾기에서도 그 칸으로 거른다(v3-13)
        if cond['op'] == '>=':
            out.append({'code': code, 'gte': t[0], **slot})
        elif cond['op'] == '<=':
            out.append({'code': code, 'lte': t[0], **slot})
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
    # [왜] 확인 안 됨 후보는 확인 안 된 조건이 적은 것부터, 같으면 찾은 순서(원래 부품의 패키지 · 분류 → 기준에 가까운 순)로 둔다.
    #      품번 이름순이면 회로 값이 빠졌을 때 엉뚱한 계열(1N4001G)이 앞에 왔다(11-07 v2 찾기)
    order = {id(j): i for i, j in enumerate(judgements)}
    unverified = sorted((j for j in judgements if j.verdict == 'NOT_VERIFIED'),
                        key=lambda j: (sum(c.result == 'unverified' for c in j.checks), order[id(j)]))[:total]
    return shown, unverified


def worse(a: str, b: str) -> str:
    """두 판정 중 나쁜 쪽(역할이 둘로 갈릴 때, EC-02)."""
    return a if ORDER.index(a) >= ORDER.index(b) else b
