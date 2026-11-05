"""역할 규칙(rules/roles.yaml)을 읽고, 규칙의 기준식으로 대체 조건의 기준값을 낸다.

- 역할: 규칙 파일 모양 검사, 기준식 계산(정해진 문법만), 그 역할에 아직 없는 회로 값 목록(인터럽트로 물을 것).
- 하지 않는 일: 사양 값과의 비교 · 판정(verdict.py), LLM · DB 호출.
- 출처: docs/specs/judge-agent.md How "규칙 파일 형식", SPEC 5절
"""
import ast
import operator
from functools import lru_cache
from pathlib import Path

import yaml

RULES_FILE = Path(__file__).with_name('rules') / 'roles.yaml'
MARGINS = {'kV': 1.25, 'kI': 1 / 0.7}  # [왜] 전압은 정격의 80%, 전류는 70% 안에서 쓴다(정답 판정 기준표 3절, 정운 10-30)
ROLES = tuple(f'R{n:02d}' for n in range(1, 24))
CODES = ('VRRM', 'IF_AV', 'IFSM', 'VF', 'IR', 'TRR', 'VZ', 'PD', 'CJ', 'TJ_MAX', 'VR', 'VRWM', 'VBR', 'VC', 'IPP', 'PPPM', 'VESD')
KINDS = ('number', 'flag', 'condition')
TIERS = ('required', 'conditional')
OPS = ('>=', '<=', 'within')
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
        codes = cond['code'] if isinstance(cond['code'], list) else [cond['code']]
        if cond.get('tier') not in TIERS or cond.get('op') not in OPS or any(c not in CODES for c in codes):
            raise ValueError(f'{rid}: 조건 {cond} 의 tier · op · code가 정해진 값 밖')
        if (cond['op'] == 'within') != (isinstance(cond['basis'], list) and len(cond['basis']) == 2):
            raise ValueError(f'{rid}: within은 [하한식, 상한식] 두 개를 쓴다')
        for basis in _bases(cond) + ([cond['default']] if cond.get('default') else []):
            unknown = names(basis) - set(known)
            if unknown:
                raise ValueError(f'{rid}: 기준식 {basis!r} 의 {sorted(unknown)} 가 inputs에 없음')
        for key in ('when', 'unless', 'at'):
            if cond.get(key) and cond[key] not in known:
                raise ValueError(f'{rid}: {key}={cond[key]} 가 inputs에 없음')
    for code, way in (rule.get('major') or {}).items():
        if code not in CODES or way not in ('higher', 'lower'):
            raise ValueError(f'{rid}: major {code}={way} 가 정해진 값 밖')


def needed(rule: dict, present: set[str]) -> list[str]:
    """아직 없는 회로 값: 필수 조건의 기준식 · 시험 조건 값, 조건부의 발동 여부(when). 기본값(default)이 있으면 묻지 않는다."""
    want = []
    for cond in rule['conditions']:
        if cond['tier'] == 'conditional':
            if cond.get('when') and cond['when'] not in present:
                want.append(cond['when'])
            continue
        if not cond.get('default'):
            want += [n for b in _bases(cond) for n in sorted(names(b)) if n not in present]
        if cond.get('at') and cond['at'] not in present:
            want.append(cond['at'])
    return list(dict.fromkeys(want))


@lru_cache(maxsize=4)
def load(path: str | None = None) -> dict[str, dict]:
    """roles.yaml을 읽고 모든 규칙을 검사해 {역할 번호: 규칙}으로 돌려준다(한 번 읽으면 캐시)."""
    data = yaml.safe_load(Path(path or RULES_FILE).read_text(encoding='utf-8'))
    for rid, rule in data.items():
        check_rule(rid, rule)
    return data
