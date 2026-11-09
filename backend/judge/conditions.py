"""역할 규칙(rules/roles.yaml)을 읽고, 규칙의 기준식으로 대체 조건의 기준값을 낸다.

- 역할: 규칙 파일 모양 검사, 기준식 계산(정해진 문법만), 그 역할에 아직 없는 회로 값 목록(인터럽트로 물을 것).
- 하지 않는 일: 사양 값과의 비교 · 판정(verdict.py), LLM · DB 호출.
- 출처: docs/specs/judge-agent.md How "규칙 파일 형식", SPEC 5절
"""
import ast
import operator
import re
from functools import lru_cache
from pathlib import Path

import yaml

RULES_FILE = Path(__file__).with_name('rules') / 'roles.yaml'
MARGINS = {'kV': 1.25, 'kI': 1 / 0.7}  # [왜] 전압은 정격의 80%, 전류는 70% 안에서 쓴다(정답 판정 기준표 3절)
ROLES = tuple(f'R{n:02d}' for n in range(1, 24))
CODES = ('VRRM', 'IF_AV', 'IFSM', 'VF', 'IR', 'TRR', 'VZ', 'PD', 'CJ', 'TJ_MAX', 'VR', 'VRWM', 'VBR', 'VC', 'IPP', 'PPPM', 'VESD')
KINDS = ('number', 'flag', 'condition')
TIERS = ('required', 'conditional')
OPS = ('>=', '<=', 'within')
EXEMPTS = ('schottky', 'sic', 'none')  # TRR 면제 범위: 쇼트키 계열 모두(기본) · SiC 쇼트키만 · 면제 없음
SLOTS = ('min', 'typ', 'max')  # 조건의 slot: 후보 행에서 그 칸 값만 본다(spec_lookup.SLOTS와 같은 이름)
COMMON_INPUTS = {'temp': 'condition'}  # [왜] 사용 온도(TA 또는 TJ)는 모든 역할의 정격 비교에 걸린다
_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def _walk(node, values: dict, original: dict, used: set):
    """기준식 AST를 계산한다. 허용하지 않는 글이면 ValueError, 쓰는 값이 없으면 None."""
    if isinstance(node, ast.Expression):
        return _walk(node.body, values, original, used)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        a, b = _walk(node.left, values, original, used), _walk(node.right, values, original, used)
        if a is None or b is None or (isinstance(node.op, ast.Div) and b == 0):
            return None
        return _BIN[type(node.op)](a, b)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        v = _walk(node.operand, values, original, used)
        return None if v is None else -v
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id in MARGINS:
            return MARGINS[node.id]
        used.add(node.id)
        v = values.get(node.id)
        return None if v is None or isinstance(v, bool) else float(v)
    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'orig'
            and node.attr in CODES):
        v = (original or {}).get(node.attr)
        return None if v is None else float(v)
    raise ValueError(f'기준식에 쓸 수 없는 글: {ast.dump(node)}')


def evaluate(basis: str, values: dict, original: dict | None = None) -> float | None:
    """기준식 → 기준값. 쓰는 값이 하나라도 없으면 None. 사칙 연산 · 숫자 · 회로 값 이름 · kV · kI · orig.<코드>만 허용(임의 코드 실행 없음)."""
    return _walk(ast.parse(basis, mode='eval'), values, original or {}, set())


def names(basis: str) -> set[str]:
    """기준식이 쓰는 회로 값 이름(kV · kI · orig.* 제외)."""
    used = set()
    _walk(ast.parse(basis, mode='eval'), {}, {}, used)
    return used


def orig_codes(basis: str) -> set[str]:
    """기준식이 쓰는 원래 부품 코드(orig.<코드>의 코드)."""
    return {n.attr for n in ast.walk(ast.parse(basis, mode='eval'))
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == 'orig'}


def inputs(rule: dict) -> dict[str, str]:
    """규칙의 회로 값 이름 → 종류(number · flag · condition). 공통 값(temp)을 더한다."""
    return {**COMMON_INPUTS, **rule.get('inputs', {})}


def _bases(cond: dict) -> list[str]:
    return cond['basis'] if isinstance(cond['basis'], list) else [cond['basis']]


def check_rule(rid: str, rule: dict) -> None:
    """규칙 하나의 모양을 검사한다. 틀리면 무엇이 틀렸는지 ValueError로 알린다."""
    known = inputs(rule)
    if rid not in ROLES:
        raise ValueError(f'{rid}: 역할 번호가 R01~R23 밖')
    for key in ('name', 'recognize', 'conditions', 'source'):
        if key not in rule:
            raise ValueError(f'{rid}: {key} 칸이 없음')
    if any(kind not in KINDS for kind in known.values()):
        raise ValueError(f'{rid}: inputs 종류는 {KINDS} 중 하나')
    for cond in rule['conditions']:
        if 'any' in cond:
            # [왜] "A 또는 B" 묶음: 멤버마다 보통 조건처럼 검사한다. 층 · 발동 조건(tier · when · unless)은 묶음에만 쓴다
            members = cond['any'] if isinstance(cond['any'], list) else []
            if len(members) < 2 or any(k in m for m in members for k in ('tier', 'when', 'unless', 'any')):
                raise ValueError(f'{rid}: any는 멤버 둘 이상이고, tier · when · unless는 묶음에만 쓴다')
            for key in ('when', 'unless'):
                if cond.get(key) and cond[key] not in known:
                    raise ValueError(f'{rid}: {key}={cond[key]} 가 inputs에 없음')
            for m in members:
                _check_cond(rid, {**m, 'tier': cond.get('tier')}, known)
        else:
            _check_cond(rid, cond, known)
    for code, way in (rule.get('major') or {}).items():
        if code not in CODES or way not in ('higher', 'lower'):
            raise ValueError(f'{rid}: major {code}={way} 가 정해진 값 밖')


def _check_cond(rid: str, cond: dict, known: dict) -> None:
    """조건 하나(또는 any 묶음의 멤버 하나)의 모양을 검사한다."""
    codes = cond['code'] if isinstance(cond.get('code'), list) else [cond.get('code')]
    if cond.get('tier') not in TIERS or cond.get('op') not in OPS or any(c not in CODES for c in codes):
        raise ValueError(f'{rid}: 조건 {cond} 의 tier · op · code가 정해진 값 밖')
    if (cond['op'] == 'within') != (isinstance(cond['basis'], list) and len(cond['basis']) == 2):
        raise ValueError(f'{rid}: within은 [하한식, 상한식] 두 개를 쓴다')
    if cond.get('exempt', 'schottky') not in EXEMPTS:
        raise ValueError(f'{rid}: exempt={cond["exempt"]} 는 {EXEMPTS} 중 하나')
    if cond.get('slot', 'max') not in SLOTS or ('slot' in cond and cond['op'] == 'within'):
        raise ValueError(f'{rid}: slot={cond.get("slot")} 는 {SLOTS} 중 하나이고 within에는 쓰지 않는다')
    for basis in _bases(cond) + ([cond['default']] if cond.get('default') else []):
        unknown = names(basis) - set(known)
        if unknown:
            raise ValueError(f'{rid}: 기준식 {basis!r} 의 {sorted(unknown)} 가 inputs에 없음')
    for key in ('when', 'unless', 'at'):
        if cond.get(key) and cond[key] not in known:
            raise ValueError(f'{rid}: {key}={cond[key]} 가 inputs에 없음')
    if cond.get('at_default') not in (None, 'rated') or (cond.get('at_default') and not cond.get('at')):
        raise ValueError(f'{rid}: at_default는 at과 함께 rated만 쓴다')


def _asks(cond: dict, present: set[str]) -> list[str]:
    """조건 하나를 계산하는 데 아직 없는 회로 값(기준식 · 시험 조건). 기본값이 있으면 기준식 값 대신 기본값 식의 값을 묻는다."""
    want = [n for b in _bases(cond) for n in sorted(names(b)) if n not in present]
    if want and cond.get('default'):
        # [왜] 기준식 값을 모르면 기본값으로 판정한다. 기본값 식도 회로 값을 쓰면(R14 v_dss · R15 v_bus) 그 값은 있어야 판정된다
        want = [n for n in sorted(names(cond['default'])) if n not in present]
    if cond.get('at') and cond['at'] not in present:
        want.append(cond['at'])
    return want


def needed(rule: dict, present: set[str]) -> list[str]:
    """아직 없는 회로 값: 필수 조건의 기준식 · 시험 조건 값, 조건부의 발동 여부(when).

    기본값(default)이 있는 조건은 기준식 값이 없을 때 기본값 식의 값만 묻는다. "A 또는 B" 묶음(any)은 지금 값으로
    계산할 수 있는 멤버가 없을 때만 첫 멤버의 값을 묻는다(질문을 짧게).
    """
    want = []
    for cond in rule['conditions']:
        if cond['tier'] == 'conditional':
            if cond.get('when') and cond['when'] not in present:
                want.append(cond['when'])
            continue
        if 'any' in cond:
            asks = [_asks(m, present) for m in cond['any']]
            want += asks[0] if all(asks) else []
        else:
            want += _asks(cond, present)
    return list(dict.fromkeys(want))


@lru_cache(maxsize=4)
def load(path: str | None = None) -> dict[str, dict]:
    """roles.yaml을 읽고 모든 규칙을 검사해 {역할 번호: 규칙}으로 돌려준다(한 번 읽으면 캐시)."""
    data = yaml.safe_load(Path(path or RULES_FILE).read_text(encoding='utf-8'))
    for rid, rule in data.items():
        check_rule(rid, rule)
    return data


# 사용자가 적은 수치 규격(판정 읽기의 required_specs) → 규칙과 같은 모양의 조건. 숫자 해석은 판정 코드에서만 한다(AGENTS 7)
_NUM_UNIT = re.compile(r'([-+]?\d+(?:\.\d+)?)\s*([a-zA-Zµμ°%Ω]+)?')
_RANGE = re.compile(r'([-+]?\d+(?:\.\d+)?)\s*([a-zA-Zµμ]*)\s*(?:~|–|-|to|에서)\s*([-+]?\d+(?:\.\d+)?)\s*([a-zA-Zµμ]+)')
_LE, _LT = re.compile(r'이하|까지|최대|\bmax(?:imum)?\b|≤|<=|or less|at most|up to|no more than|넘지', re.I), re.compile(r'미만|under|below|less than|<(?!=)', re.I)
# [주의] min · max는 낱말 경계로만 본다. 'nominal'의 min을 '이상'으로 읽었다(v3-13)
_GE, _GT = re.compile(r'이상|최소|\bmin(?:imum)?\b|≥|>=|or more|at least', re.I), re.compile(r'초과|over|above|more than|>(?!=)', re.I)
HIGHER_BETTER = {'VRRM', 'VR', 'VRWM', 'VBR', 'IF_AV', 'IFSM', 'IPP', 'PD', 'PPPM', 'TJ_MAX', 'VESD'}  # 연산 말 없는 숫자는 '이상'
LOWER_BETTER = {'VC', 'VF', 'IR', 'TRR', 'CJ'}  # 연산 말 없는 숫자는 '이하'(VZ는 같음)
RATED = re.compile(r'정격|rating|rated', re.I)  # '정격 1A'처럼 정격 값을 말하면 같음
_TOL = re.compile(r'±\s*(\d+(?:\.\d+)?)\s*%')  # 제너 공차 '±2%'
# [왜] 표는 VZ 최소 · 최대를 반올림해 적는다: B 등급(±2%)은 소수 둘째 자리(3.23), C 등급(±5%)은 첫째 자리(4.8), 높은 전압은 정수(31).
#      여유는 0.05 V와 공칭의 1.5% 중 큰 값이다. 등급 사이 간격(2% · 5%)이 3% 이상이라 여유로 등급이 섞이지 않는다(11-06 h3-13 BZV55C5V1)
VZ_ROUND, VZ_ROUND_REL = 0.05, 0.015
USER_CODES = ('VRRM', 'VR', 'VRWM', 'VBR', 'VC', 'VZ', 'VF', 'VESD', 'IF_AV', 'IFSM', 'IR', 'IPP', 'PD', 'PPPM', 'TRR', 'CJ', 'TJ_MAX')


CODE_UNIT = {'VRRM': 'V', 'VR': 'V', 'VRWM': 'V', 'VBR': 'V', 'VC': 'V', 'VZ': 'V', 'VF': 'V', 'VESD': 'V', 'IF_AV': 'A', 'IFSM': 'A',
             'IR': 'A', 'IPP': 'A', 'PD': 'W', 'PPPM': 'W', 'TRR': 's', 'CJ': 'F', 'TJ_MAX': 'degC'}


def _si(number: str, unit: str, code: str) -> float | None:
    """숫자 글 · 단위 → 그 코드 단위(V · A · W · s · F · °C)의 SI 값. 단위가 그 코드와 다르면(PPPM의 '1000µs') None."""
    from backend.rag.units import to_si
    found = to_si(float(number), unit)
    return found[0] if found and found[1] == CODE_UNIT[code] else None


_OPS = ((_LT, ('<=', 1 - 1e-9)), (_LE, ('<=', 1.0)), (_GT, ('>=', 1 + 1e-9)), (_GE, ('>=', 1.0)))


def _op(after: str, before: str) -> tuple[str, float] | None:
    """숫자에 가장 가까운 연산 말로 (연산, 경계 비율)을 정한다. 뒤 말(한국어 '이상 · 미만', 영어 'or more')과 앞 말(영어 'at least · under')
    중 숫자에서 가까운 쪽, 같으면 뒤 말이다.

    [왜] '400W or more and less than 600W'의 400 뒤 글에는 600의 'less than'도, 'at least 1A and under 2A'의 1A 뒤 글에는 2A의 'under'도
         들어 있다. 미만을 먼저 찾으면 400W · 1A가 미만으로 읽혔다(11-06 v3-15, 생각을 끈 읽기가 사용자 말을 영어로 옮김)
    """
    # [주의] 뒤 말 중 바로 다음에 숫자가 오는 연산 말('… 23.2V under 10A surge'의 under)은 다음 숫자의 것이다(영어는 연산 말이 숫자 앞에 온다).
    #        23.2V가 미만으로 읽혀 23.2 V 후보가 떨어졌다(11-06 v3-09 안정성 측정)
    near_after = min(((m.start(), val) for pat, val in _OPS for m in pat.finditer(after) if not re.match(r'\s*(?:(?:a|an|the)\s+)?[-+]?\d', after[m.end():], re.I)),
                     default=None)
    near_before = min(((len(before) - m.end(), val) for pat, val in _OPS for m in pat.finditer(before)), default=None)
    if near_after and (not near_before or near_after[0] <= near_before[0]):
        return near_after[1]
    return near_before[1] if near_before else None


def user_conditions(specs: list[tuple[str, str]]) -> list[dict]:
    """(사용자 말, 사양 표 코드) 목록 → 필수 조건 목록. 숫자가 없거나 코드가 사양 표 숫자 항목이 아니면 만들지 않는다.

    '400~600V' → ≥ 400 · ≤ 600, '1A 이상 2A 미만' → ≥ 1 · < 2, '100ns 이하' → ≤ 1e-07, '1.8V까지' → ≤ 1.8,
    연산 말 없음: 정격 · VZ면 같음, 아니면 좋은 방향('10A 서지' → IPP ≥ 10, 'VF 1.1V' → ≤ 1.1).
    [주의] 미만 · 초과는 경계를 아주 조금(1e-9 비율) 안쪽으로 둬 같은 값을 통과시키지 않는다. 단위가 그 코드와 다른 숫자는 버린다.
    """
    out = []
    for words, code in specs:
        if code not in USER_CODES:
            continue
        cond = {'tier': 'required', 'code': code, 'source': 'user', 'words': words}
        m = _RANGE.search(words)
        if m and (lo := _si(m.group(1), m.group(2) or m.group(4), code)) is not None and (hi := _si(m.group(3), m.group(4), code)) is not None:
            upper = hi * (1 - 1e-9) if _LT.search(words[m.end():]) else hi
            low_slot, high_slot = {}, {}
            if code == 'VZ':
                # [왜] 제너 표는 최소 · 대표 · 최대가 한 행씩이라 칸을 정하지 않으면 최소 행(3.42)과 '≥ 3.6'을 비교해 떨어뜨렸다(11-07 h4-13).
                #      '공칭 3.6~3.9V'는 대표 칸이 그 범위 안, 그냥 '3.42~3.78V 범위'는 최소 칸 ≥ 하한 · 최대 칸 ≤ 상한(퍼짐이 범위 안)이다
                nominal = re.search(r'공칭|nominal|\bnom\b', words, re.I)
                low_slot, high_slot = ({'slot': 'typ'}, {'slot': 'typ'}) if nominal else ({'slot': 'min'}, {'slot': 'max'})
            out += [{**cond, 'op': '>=', 'basis': repr(lo), **low_slot}, {**cond, 'op': '<=', 'basis': repr(upper), **high_slot}]
            continue
        tol = _TOL.search(words) if code == 'VZ' else None
        hits = [x for x in _NUM_UNIT.finditer(words) if x.group(2) and _si(x.group(1), x.group(2), code) is not None]
        if tol and len(hits) == 1:
            # [왜] '공칭 3.3V, 공차 ±2%(B 등급)'는 공칭(대표 칸) = 3.3, 최소 칸 ≥ 3.3 × 0.98, 최대 칸 ≤ 3.3 × 1.02다. 표는 반올림해 적어
            #      (BZT52B3V3 3.23 / 3.37, BZV55C5V1 4.8 / 5.4) 경계에 반올림 여유(VZ_ROUND)를 둔다(11-06 v3-13, 열린 항목 'VZ 공차 등급')
            v, t = _si(hits[0].group(1), hits[0].group(2), code), float(tol.group(1)) / 100
            slack = max(VZ_ROUND, VZ_ROUND_REL * v)
            lo, hi = v * (1 - t), v * (1 + t)
            # [왜] 공차는 등급이다(B 등급 ±2%, C 등급 ±5%). 최소 · 최대 칸이 그 등급의 경계 근처(반올림 여유 안)여야 같은 등급이다.
            #      더 좁은 등급도 범위 안이라 통과시켰더니 '공차가 다른 부품은 섞지 말라'는 ±5% 찾기에 ±2% 부품이 나왔다(11-06 h3-13)
            out += [{**cond, 'op': '>=', 'basis': repr(v), 'slot': 'typ'}, {**cond, 'op': '<=', 'basis': repr(v), 'slot': 'typ'},
                    {**cond, 'op': '>=', 'basis': repr(round(lo - slack, 6)), 'slot': 'min'},
                    {**cond, 'op': '<=', 'basis': repr(round(lo + slack, 6)), 'slot': 'min'},
                    {**cond, 'op': '>=', 'basis': repr(round(hi - slack, 6)), 'slot': 'max'},
                    {**cond, 'op': '<=', 'basis': repr(round(hi + slack, 6)), 'slot': 'max'}]
            continue
        made = []
        for i, x in enumerate(hits):
            after = words[x.end():hits[i + 1].start() if i + 1 < len(hits) else len(words)]
            before = words[hits[i - 1].end() if i else 0:x.start()]
            found = _op(after, before)
            if found:
                op, k = found
                made.append({**cond, 'op': op, 'basis': repr(_si(x.group(1), x.group(2), code) * k)})
        if not made and len(hits) == 1:
            v = _si(hits[0].group(1), hits[0].group(2), code)
            # [왜] 연산 말이 없으면 그 항목의 좋은 방향이다('10A 서지 보호 유지' → IPP ≥ 10, v3-09). '정격 1A'처럼 정격을 말하거나 VZ면 같음.
            #      같음은 ≥ v · ≤ v 두 조건이다(within은 최소 · 최대 칸이 둘 다 있어야 해 정격값 하나를 못 본다)
            if RATED.search(words) or code not in HIGHER_BETTER | LOWER_BETTER:
                # [왜] VZ 하나만 말하면 공칭(대표 칸)과 같아야 한다. 기본 칸(최대)으로 보면 '3.3V'가 최대 3.37인 3.3V 제너를 떨어뜨렸다(v3-13)
                slot = {'slot': 'typ'} if code == 'VZ' else {}
                made = [{**cond, 'op': '>=', 'basis': repr(v), **slot}, {**cond, 'op': '<=', 'basis': repr(v), **slot}]
            else:
                made = [{**cond, 'op': '>=' if code in HIGHER_BETTER else '<=', 'basis': repr(v)}]
        if code == 'VF':
            # [왜] 사용자의 전압강하 한계('1.8V까지 허용')는 회로 동작 전류에서의 한계다. 사람 판정은 그 전류의 VF MAX가 표에 없으면 확인 안 됨으로 본다
            #      (v3-02 · 04 · 07). 표의 시험 전류 값과 비교하면 사용 온도를 읽었는지에 따라 통과 · 확인 안 됨이 오갔다(11-06 개발용 3 · 4회차)
            made = [{**c, 'at_current': True} for c in made]
        if len(hits) == 1 and made and {c['op'] for c in made} == {'<='} and code in HIGHER_BETTER - {'VRWM'} and not RATED.search(words):
            # [왜] 좋은 방향이 큰 항목(IFSM · IF_AV · IPP · PPPM …)에 상한 하나만 있으면 회로가 거는 부하('투입 피크 최대 2A')를 적은 것이다.
            #      부품은 그 이상을 버텨야 한다. '2A 이하'로 읽어 IFSM 30A 후보가 불충족이 됐다(11-06 v3-01). 범위('1A 이상 2A 미만')는 그대로 둔다
            made = [{**c, 'op': '>=', 'basis': repr(_si(hits[0].group(1), hits[0].group(2), code))} for c in made]
        elif len(hits) == 1 and made and {c['op'] for c in made} == {'>='} and code in LOWER_BETTER:
            # [왜] 좋은 방향이 작은 항목(VC · VF · IR · TRR · CJ)에 하한 하나만 있으면 한계를 거꾸로 읽은 것이다('최대 9.2V'를 'not above'로 옮긴 뒤
            #      VC ≥ 9.2가 됨, 11-06 공식 6회차 v3-10). 상한으로 본다
            made = [{**c, 'op': '<=', 'basis': repr(_si(hits[0].group(1), hits[0].group(2), code))} for c in made]
        out += made
    return out
