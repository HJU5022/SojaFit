"""판정 에이전트: 역할 · 회로 값을 읽고(LLM 1번), 빠진 값을 묻고(인터럽트), 사양 표 값으로 판정한다(코드).

- 역할: `judge_read_agent`(읽기 노드)와 `judge_agent`(판정 노드). 읽기를 따로 두는 이유는 인터럽트에서 재개하면
  노드가 처음부터 다시 돌기 때문이다(읽기 결과를 먼저 상태에 남겨 LLM을 다시 부르지 않는다).
- 하지 않는 일: 숫자 비교(backend/judge/verdict.py), 답 문구(backend/multi_agent/messages.py), LLM 직접 호출(chat을 받아 쓴다).
- 출처: docs/specs/judge-agent.md What · How
"""
import re
from pathlib import Path
from typing import Literal

from langgraph.types import interrupt
from pydantic import BaseModel, Field

from backend.graph.mcp_retriever import RetrievalUnavailableError
from backend.judge import conditions as C
from backend.judge import sheet_conditions as S
from backend.judge import verdict as V
from backend.multi_agent.contracts import AgentReport, Reason
from backend.rag.spec_lookup import CODES as SPEC_CODES
from backend.rag.units import to_si

PROMPT = (Path(__file__).resolve().parents[2] / 'prompts' / 'judge_read.md').read_text(encoding='utf-8')


class Value(BaseModel):
    """질문에서 읽은 회로 값 하나. quote는 질문 글에서 그대로 옮긴 부분이다(숫자 확인에 쓴다)."""
    name: str = Field(max_length=40)
    number: float | None = None
    unit: str = Field(default='', max_length=10)
    flag: bool | None = None
    condition: str = Field(default='', max_length=120)
    quote: str = Field(max_length=200)


class RequiredSpec(BaseModel):
    """사용자가 꼭 요구한 부품 성질 하나: 사용자 말 그대로와, 그 성질을 재는 사양 표 항목(없으면 none)."""
    words: str = Field(max_length=80)
    code: Literal[SPEC_CODES + ('none',)]  # [왜] 목록 밖 글자는 형식 검사에서 걸린다. none이면 판정 노드가 거절한다(SPEC 8.3)


class JudgeRead(BaseModel):
    """읽기 노드의 구조화 출력."""
    role: str = Field(pattern='^(R0[1-9]|R1[0-9]|R2[0-3]|other)$')
    role_alt: str | None = Field(default=None, pattern='^(R0[1-9]|R1[0-9]|R2[0-3])$')
    role_evidence: list[str] = Field(default_factory=list, max_length=6)
    values: list[Value] = Field(default_factory=list, max_length=20)
    original_part: str = Field(default='', max_length=100)
    candidates: list[str] = Field(default_factory=list, max_length=5)
    package_wanted: str = Field(default='', max_length=30)
    category_wanted: str = Field(default='', max_length=100)
    # 사용자가 꼭 요구했지만 코퍼스 밖일 수 있는 것(코퍼스 밖 요구 거절, SPEC 8.3)
    required_specs: list[RequiredSpec] = Field(default_factory=list, max_length=6)
    maker_wanted: str = Field(default='', max_length=60)     # 요구한 제조사(영어, Taiwan Semiconductor는 TSC)
    revision_wanted: str = Field(default='', max_length=40)  # 요구한 개정 코드 · 판(쓴 그대로)


def render_read(state: dict, rules: dict) -> str:
    """읽기 LLM에 줄 user 글: 역할 목록(이름 · 알아보는 법 · 그 역할이 받는 값 이름과 종류), 대상 주변 회로, 사용 조건, 질문."""
    part = state.get('target_part') or {}
    # [왜] 값 이름을 역할마다 roles.yaml에서 만든다. 모든 역할의 이름을 한 줄로 주면 다른 역할의 이름(i_out · v_bus)으로 읽어
    #      to_inputs가 버리고 기준값이 비었다(11-06 동결 평가 4회 실측, 인용 없는 답 40건 중 20건)
    lines = ['Roles (each lists the value names it accepts):']
    lines += [f'- {rid}: {r["name"]} — {r["recognize"]} | inputs: ' + ', '.join(f'{n} ({k})' for n, k in C.inputs(r).items())
              for rid, r in rules.items()]
    lines += [f'Question type: {state.get("question_type", "")}',
              f'Target: {part.get("ref", state.get("target", ""))} value={part.get("value", "")} footprint={part.get("footprint", "")}',
              'Nets around the target:']
    lines += [f'- {n["name"]}: ' + ', '.join(n['nodes']) + (f' (+{n["more"]} more)' if n.get('more') else '') for n in part.get('nets', [])]
    lines += [f'Conditions: {state.get("conditions", "")}', f'Question: {state.get("question", "")}']
    return '\n'.join(lines)


def judge_read_agent(state: dict, *, chat) -> dict:
    """그래프 노드: 읽기 LLM을 한 번 불러 결과를 상태에 남긴다."""
    read = chat('judge_read', PROMPT, render_read(state, C.load()), JudgeRead)
    return {'judge_read': read.model_dump(mode='json'), 'path': ['판정 읽기']}


NUM = re.compile(r'\d+(?:\.\d+)?')
REPLY = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*([a-zA-Zµμ°%]*)\s*$')
YES, NO = {'예', '네', '응', 'yes', 'true', 'y'}, {'아니오', '아니', 'no', 'false', 'n'}


def _norm(s: str) -> str:
    return ' '.join(s.split())


def grounded(text: str, v: Value) -> bool:
    """값의 quote가 질문 · 회로 글에 그대로 있고, number와 condition의 숫자가 모두 그 quote에 있는지(AC-02)."""
    quote = _norm(v.quote)
    if not quote or quote not in _norm(text):
        return False
    have = {float(n) for n in NUM.findall(quote)}
    want = ([v.number] if v.number is not None else []) + [float(n) for n in NUM.findall(v.condition)]
    return all(n in have for n in want)


def _si(number: float, unit: str) -> float:
    """읽은 숫자 · 단위 → SI 값. %는 100으로 나누고, 단위가 없거나 모르면 숫자 그대로(권선비 등)."""
    if unit == '%':
        return number / 100
    found = to_si(number, unit) if unit else None
    return found[0] if found else number


def to_inputs(read: JudgeRead, text: str, kinds: dict) -> tuple[dict, dict, list[str]]:
    """읽기 결과 → (숫자 · 예/아니오 값, 시험 조건 값, 버린 이름). 규칙에 없는 이름과 근거 없는 값은 버린다."""
    values, conds, dropped = {}, {}, []
    for v in read.values:
        kind = kinds.get(v.name)
        if kind is None or not grounded(text, v):
            dropped.append(v.name)
        elif kind == 'flag' and v.flag is not None:
            values[v.name] = v.flag
        elif kind == 'number' and v.number is not None:
            values[v.name] = _si(v.number, v.unit)
        elif kind == 'condition' and v.condition:
            conds[v.name] = S.parse(v.condition)
        else:
            dropped.append(v.name)
    return values, conds, dropped


def merge_reply(answers: dict, values: dict, conds: dict, kinds: dict) -> tuple[dict, dict]:
    """인터럽트 답({이름: "150mA" | "예" | "TJ=25°C"})을 회로 값에 더한다. 못 읽는 답은 버린다(= 모름)."""
    values, conds = dict(values), dict(conds)
    for name, raw in (answers or {}).items():
        kind, text = kinds.get(name), str(raw).strip()
        if kind == 'flag' and text.lower() in YES | NO:
            values[name] = text.lower() in YES
        elif kind == 'number' and (m := REPLY.match(text)):
            values[name] = _si(float(m.group(1)), m.group(2))
        elif kind == 'condition' and (parsed := S.parse(text)):
            conds[name] = parsed
    return values, conds


def _ask_text(missing: list[str], roles: list[str], rules: dict) -> str:
    """사용자에게 보일 한국어 질문 하나(빠진 값 이름을 그대로 보여 준다)."""
    head = '판정에 필요한 값이 빠져 있어요. 아는 만큼 알려 주세요(모르면 비워 두면 돼요): '
    return head + ', '.join(missing) + (f" / 역할이 {' 또는 '.join(rules[r]['name'] for r in roles)} 중 어느 쪽인지도 알려 주세요." if len(roles) > 1 else '')


# [왜] 읽기가 품번을 'TSC 1N5817'처럼 제조사 이름과 함께 낸다. 사양 표 품번에는 제조사 이름이 없어 0행이 된다(11-06 평가 7건)
MAKER = re.compile(r'^\s*(?:TSC|Taiwan\s+Semiconductor)\s+', re.I)


def _part(name: str) -> str:
    """품번 앞의 제조사 이름(TSC · Taiwan Semiconductor)을 뗀다."""
    return MAKER.sub('', name or '').strip()


def _rows(specs, name: str) -> list[dict]:
    """품번의 사양 표 행. 제조사 이름을 떼고 찾고, 없으면 첫 낱말(주문 코드를 뗀 기본 품번, 1N4148 R0G → 1N4148)로 다시 찾는다."""
    name = _part(name)
    return (specs(name) or specs(name.split()[0])) if name else []


def _identical(retriever, original: str, candidate: str) -> bool:
    """같은 기본 품번의 주문 코드만 다를 때, 제조사가 같은 제품이라고 밝힌 청크가 있는지(EC-10)."""
    base_o, base_c = original.split()[0].upper() if original else '', candidate.split()[0].upper()
    if not base_o or base_o != base_c:
        return False
    if original.upper() == candidate.upper():
        return True
    if retriever is None:
        return False
    docs = retriever(f'{base_c} ordering information physically identical', parts=[base_c])
    return any('identical' in d.get('content', '').lower() for d in docs)


def _schottky_exempt(j: V.Judgement, category: str) -> V.Judgement:
    """쇼트키 계열 후보의 TRR 조건은 면제(정답 판정 기준표 3.5). 면제한 뒤 판정을 다시 정한다.

    조건의 exempt가 면제 범위다: schottky(쇼트키 계열 모두, 기본) · sic(SiC 쇼트키만, R14 100 kHz 초과) · none(면제 없음).
    """
    sic = category.startswith('sic-schottky')
    if not sic and not category.startswith('schottky'):
        return j
    free = ('schottky', 'sic') if sic else ('schottky',)
    checks = [c.model_copy(update={'result': 'pass', 'why': '쇼트키 면제'}) if c.code == 'TRR' and c.exempt in free else c
              for c in j.checks]
    if any(c.result == 'fail' for c in checks):
        verdict = 'NOT_SUFFICIENT'
    elif any(c.result == 'unverified' for c in checks):
        verdict = 'NOT_VERIFIED'
    else:
        verdict = j.verdict if j.verdict in ('IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT') else 'ROLE_SUFFICIENT'
    return j.model_copy(update={'checks': checks, 'verdict': verdict})


def outside_corpus(read: JudgeRead, facts: dict) -> tuple[Reason, str] | None:
    """사용자가 꼭 요구한 것이 코퍼스 밖이면 (거절 사유, 요약). 이름 · 항목만 대조한다(숫자 판단 없음, SPEC 8.3)."""
    maker = re.sub(r'[^A-Z]', '', read.maker_wanted.upper())  # 'Taiwan Semiconductor Co.' → 'TAIWANSEMICONDUCTORCO'
    if maker and maker != 'TSC' and not maker.startswith('TAIWANSEMI'):
        return Reason.PART_MISSING, f'required maker {read.maker_wanted} is not TSC'
    wanted = read.revision_wanted.strip().upper()
    # [왜] 판정 길에는 코퍼스 개정판 전체 목록이 없다. 사실 확인이 코퍼스에 있다고 확인한 개정 코드(K2611)를 담을 때만 통과한다
    if wanted and not any(ok and code in wanted for code, ok in (facts.get('revisions') or {}).items()):
        return Reason.REVISION_MISSING, f'required revision {read.revision_wanted} is not confirmed in the corpus'
    unheld = [r.words for r in read.required_specs if r.code == 'none']
    if unheld:
        return Reason.NOT_FOUND, 'required property not in the spec table: ' + ', '.join(unheld)
    return None


def _report(status: str, summary: str, missing=(), reason=None) -> dict:
    return AgentReport(agent='judge', status=status, summary=summary[:200], missing=list(missing), reason=reason).model_dump(mode='json')


def judge_agent(state: dict, *, specs, find, retriever) -> dict:
    """그래프 노드: 코퍼스 밖 요구면 거절 사유로 보고하고, 아니면 빠진 값을 한 번 묻고 사양 표 값으로 후보를 판정한다(찾기면 거르고 판정하고 줄 세운다)."""
    rules = C.load()
    read = JudgeRead.model_validate(state['judge_read'])
    # [왜] 코퍼스 밖 요구(사양 표에 없는 성질 · TSC 아닌 제조사 · 확인 안 된 개정판)는 규칙 · 조건을 만들기 전에 거절한다.
    #      묻거나 판정하면 그 요구와 상관없는 판정 답이 나간다(11-06 동결 평가: 비관련 35건 중 8~10건)
    if refused := outside_corpus(read, state.get('facts') or {}):
        reason, why = refused
        return {'path': ['판정'], 'reports': (state.get('reports') or []) + [_report('fail', f'cannot judge from the corpus: {why}', reason=reason)]}
    part = state.get('target_part') or {}
    # [왜] 숫자 확인은 질문 · 사용 조건 · 대상 주변 회로 글로만 한다. 역할 목록(rules)의 알아보는 법 글에 있는 숫자는 사용자가 준 값이 아니다(AC-02)
    text = '\n'.join([state.get('conditions', ''), state.get('question', ''), render_read(state, {})])
    roles = [r for r in (read.role, read.role_alt) if r and r != 'other']
    base = {'roles': roles, 'role_evidence': read.role_evidence, 'results': [], 'shown': [], 'unverified': [], 'terms': [],
            'capped': False, 'dropped': [], 'asked': []}
    if not roles:
        return {'judgement': {**base, 'kind': 'no_rule'}, 'path': ['판정'],
                'reports': (state.get('reports') or []) + [_report('partial', 'role outside the 23 roles: no judging rule')]}
    kinds = {k: v for r in roles for k, v in C.inputs(rules[r]).items()}
    values, conds, dropped = to_inputs(read, text, kinds)
    asked = list(dict.fromkeys(n for r in roles for n in C.needed(rules[r], set(values) | set(conds))))
    if asked or len(roles) > 1:
        # [주의] 인터럽트는 문항당 한 번이다(AC-08). 재개하면 이 노드가 처음부터 다시 돌지만, 읽기는 앞 노드에 남아 있어 LLM을 다시 부르지 않는다
        # [주의] 재개 값은 {'answers': {...}, 'role': ...} 모양이다. 빈 dict({})로 재개하면 LangGraph가 재개로 보지 않고 다시 멈춘다(11-06 실측)
        reply = interrupt({'missing': asked, 'role_choices': roles if len(roles) > 1 else [], 'question': _ask_text(asked, roles, rules)}) or {}
        values, conds = merge_reply(reply.get('answers') or {}, values, conds, kinds)
        if reply.get('role') in roles:
            roles = [reply['role']]
    try:
        original_rows = _rows(specs, read.original_part)  # 후보 조회와 같은 규칙(제조사 이름 · 주문 코드)
        footprint = part.get('footprint')
        if state.get('question_type') == 'candidate_find':
            terms = V.search_conditions(rules[roles[0]], values)
            found = find(terms, read.category_wanted or None, read.package_wanted or None, 50) if terms else []
            candidates = [(f['part'], f.get('category', ''), f.get('packages', [])) for f in found]
        else:
            terms, found = [], []
            candidates = [(p, '', None) for p in read.candidates]
        results = []
        for name, category, packages in candidates:
            rows = _rows(specs, name)
            packages = packages if packages is not None else [x['text'] for x in rows if x['code'] == 'PACKAGE' and x.get('text')]
            category = category or next((x['category'] for x in rows if x.get('category')), '')  # 판정 질문은 행의 분류로
            same = _identical(retriever, read.original_part, name)
            judged = [_schottky_exempt(V.judge_part(rules[r], r, name, values, conds, rows,
                                                    original_rows=original_rows or None, identical=same,
                                                    footprint=footprint, packages=packages), category) for r in roles]
            results.append(max(judged, key=lambda j: V.ORDER.index(j.verdict)))  # 역할이 둘이면 더 나쁜 판정(EC-02)
    except RetrievalUnavailableError as error:
        return {'judgement': {**base, 'kind': 'judge'}, 'path': ['판정'],
                'reports': (state.get('reports') or []) + [_report('fail', f'spec table tool failed: {error.kind}', reason=Reason.SEARCH_ERROR)]}
    shown, unverified = V.rank(results) if state.get('question_type') == 'candidate_find' else (results, [])
    judgement = {**base, 'kind': 'find' if state.get('question_type') == 'candidate_find' else 'judge', 'roles': roles,
                 'results': [j.model_dump(mode='json') for j in results], 'shown': [j.model_dump(mode='json') for j in shown],
                 'unverified': [j.model_dump(mode='json') for j in unverified], 'terms': terms, 'capped': len(found) >= 50,
                 'dropped': dropped, 'asked': asked}
    missing = sorted({m for j in results for m in j.missing})
    status = 'ok' if results else 'partial'
    summary = f'{len(results)} candidates judged' + (f', {len(shown)} shown' if judgement['kind'] == 'find' else '')
    return {'judgement': judgement, 'path': ['판정'], 'reports': (state.get('reports') or []) + [_report(status, summary, missing)]}
