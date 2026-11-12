"""Supervisor(계획, LLM 1번) · 배분(Send)과 답 모으기(코드) · 종합(할 일 2개 이상일 때만 LLM 1번), 그리고 마무리 답 검사(코드).

- 역할:
  - 계획 `plan_node`: 질문 · 대상 회로 · 확인된 사실을 글로 만들어 LLM에 주고 계획서(`Plan`: 범위 판정 · 질문 종류 · 할 일 최대 3개와
    할 일마다 지시서)를 받는다. 형식이 틀리면 `llm.chat`이 다시 부르고, 끝내 틀리면 거절한다. `after_plan`이 할 일을 서브에이전트에 Send로 동시에 보낸다.
  - 답 모으기 `collect_node`: 돌아온 보고의 상태 · 사유만 보고 상한을 검사해 다음 길(답 정리 · 종합 · 거절 · 재계획)을 정한다.
    재계획(설계 v2, 11-07): 이번 회차에 다시 해 볼 만한 실패(사유가 no_result · all_rejected · partial이거나 없음)가 있거나
    계획이 '앞 결과가 필요하다(replan)'고 표시했으면, 아직 재계획 전일 때만 Supervisor(계획)로 되돌린다. 무엇을 할지는 계획(LLM)이 정한다.
    `single_node`는 할 일 1개의 답을 그대로 쓰고(판정은 코드 답 틀), `synth_node`는 할 일 2개 이상일 때만 부분 답을 한 답으로 합친다.
    판정(kind=judge)이 끝난 답은 둘 다 코드 판정 답 틀만 쓴다(출력 경계 `_judgement_reply`, 문서 · 종합 자유 글을 붙이지 않음).
  - 마무리 `check_node`: 인용 번호가 받은 근거 안인지, 종합 글의 숫자가 부분 답 · 판정 결과에 있는 숫자인지 코드로 본다.
- 하지 않는 일: 검색 · 판정 자체(서브에이전트), 숫자 비교(`backend/judge/`), LLM 직접 호출(`chat` 함수를 받아 쓴다. 실제 연결은 `llm.node_chat`),
  질문 종류 · 거절 · 할 일 나누기 판단(LLM이 계획으로 정한다). 코드가 바꾸는 것은 상한 초과 · 판정 꺼짐 · 형식 실패와
  찾기 질문인데 판정 찾기 할 일이 없을 때 그 할 일로 맞추는 것뿐이다(사전 등록 #47, ADR 0017).
- 출처: backend/multi_agent/MULTI_AGENT.md "구조 결정"(11-06 재설계, 11-07 실패 고리), ADR 0017, backend/prompts/supervisor.md · synth.md
"""
import os
import re
from pathlib import Path

from langgraph.types import Send
from pydantic import BaseModel, Field
from backend.graph.memory import memory_context, memory_sources
from backend.judge.pdf_claims import bind_run_citations, check_pdf_lines

from backend.multi_agent.contracts import MAX_AGENT_RUNS, MAX_REPLANS, MAX_SEARCHES, MAX_SUPERVISOR_CALLS, RETRY_REASONS, Plan, Reason, Task, TaskReport
from backend.multi_agent.messages import refusal_for, render_judgement

PROMPTS = Path(__file__).resolve().parents[1] / 'prompts'
PROMPT = (PROMPTS / 'supervisor.md').read_text(encoding='utf-8')
SYNTH_PROMPT = (PROMPTS / 'synth.md').read_text(encoding='utf-8')
NUMBER = re.compile(r'\d+(?:\.\d+)?')
# [왜] 그래프 노드 이름은 강의처럼 한국어다(build.py가 이 이름으로 노드를 단다). 갈림 함수는 다음 노드 이름을 그대로 돌려줘
#      draw_mermaid 그림에 영어 라벨이 붙지 않는다. 계획서 · 모으기의 값(docs · finish · single 등)은 그대로 두고 여기서만 옮긴다
NODE = {'docs': 'RAG 에이전트', 'judge': 'Spec 에이전트', 'finish': '끝내기', 'price': '가격 안내', 'refuse': '거절',
        'collect': '답 모으기', 'single': '답 정리', 'synth': '종합'}
REPLAN = '다시 해 볼 실패 · 다시 계획(최대 1번)'  # 답 모으기 → Supervisor 되돌림만 노드 이름이 아닌 키라 그림에 이 라벨이 붙는다


class Facts(BaseModel):
    """코드가 목록에서 확인한 사실. LLM이 짐작하지 않고 이 값을 믿는다."""
    parts: dict[str, bool] = Field(default_factory=dict)      # 질문에 나온 품번 → 코퍼스 목록에 있나
    revisions: dict[str, bool] = Field(default_factory=dict)  # 요청한 개정 코드 → 코퍼스에 있나


def render_facts(facts: Facts) -> list[str]:
    """확인된 사실을 LLM 입력 줄로 쓴다. [왜] D4 v2 단일 그래프의 라우팅도 이 글을 받아, 같은 사실로 거절을 정하게 한다(D4 · D5 공정 비교)."""
    lines = ['Verified facts:']
    for name, ok in facts.parts.items():
        lines.append(f'- part {name}: {"in corpus" if ok else "NOT in corpus"}')
    for name, ok in facts.revisions.items():
        lines.append(f'- revision {name}: {"in corpus" if ok else "NOT in corpus"}')
    if not facts.parts and not facts.revisions:
        lines.append('- (no part number or revision to verify in the question)')
    return lines


def render_plan(state: dict, judge_enabled: bool, web_enabled: bool = False) -> str:
    """계획 LLM에 줄 user 글(영어 라벨). 청크 원문은 없다: 질문 · 대상 · 사용 조건 · 확인된 사실 · 쓸 수 있는 에이전트."""
    part = state.get('target_part') or {}
    # Footprint annotations are untrusted metadata, not planning or role instructions.
    target = f"{part.get('ref', state.get('target', ''))} {part.get('value', '')}".strip() or state.get('target', '')
    agents = ['docs'] + (['judge'] if judge_enabled else [])
    lines = [f"Question: {state['question']}", f'Target part: {target or "(none)"}', f"Conditions: {state.get('conditions', '')}",
             *render_facts(Facts(**(state.get('facts') or {}))), 'Agents you may use: ' + ', '.join(agents),
             f'External web fallback: {"enabled" if web_enabled else "disabled"}']
    if state.get('reports'):
        # [왜] 재계획: 앞 회차의 지시서와 보고 요약만 준다(청크 원문 · 판정 표는 주지 않는다, 컨텍스트 분리)
        tasks = {t['id']: t for t in (state.get('plan') or {}).get('tasks', [])}
        lines += ['', 'REPLAN. Earlier round tasks and their reports:']
        for r in (TaskReport.model_validate(x) for x in state['reports']):
            t = tasks.get(r.task, {})
            lines.append(f"- task {r.task} [{r.agent} · {t.get('kind', '')}] goal: {t.get('goal', '')} → {r.status}"
                         + (f" (reason {r.reason.value})" if r.reason else '') + f': {r.summary}'
                         + (f"; missing: {', '.join(r.missing)}" if r.missing else ''))
    return '\n'.join(lines) + memory_context(state.get('approved_memories') or [])


def plan_node(state: dict, *, chat, judge_enabled: bool = False, web_enabled: bool = False) -> dict:
    """그래프 노드 `Supervisor`(계획): 계획서를 받는다(재계획이면 앞 회차 보고도 읽는다). 형식이 끝내 틀리면 거절로 끝낸다."""
    replan = bool(state.get('reports'))
    old = state.get('counters') or {}
    c = {'hops': old.get('hops', 0) + 1, 'agents': old.get('agents', 0), 'searches': old.get('searches', 0),
         'replans': old.get('replans', 0) + (1 if replan else 0)}
    try:
        plan = chat('supervisor', PROMPT, render_plan(state, judge_enabled, web_enabled), Plan)
    except ValueError:
        # [왜] llm.chat이 형식을 다시 맞춰 보고도(MAX_FORMAT_RETRIES) 틀리면 ValueError를 낸다. 틀린 계획으로 서브에이전트를 부르지 않는다(MULTI_AGENT.md "구조 결정")
        if replan:  # 재계획만 틀렸으면 이미 받은 보고로 답한다
            return {'plan': {**(state.get('plan') or {}), 'next': 'answer'}, 'counters': c, 'path': ['계획']}
        return {'plan': {}, 'question_type': '', 'refusal_reason': Reason.LIMIT_REACHED.value, 'counters': c, 'path': ['계획']}
    if plan.next == 'answer' and not replan:
        plan = plan.model_copy(update={'next': 'refuse', 'reason': Reason.LIMIT_REACHED})  # 받은 보고가 없는데 '있는 답으로'는 형식 오류다
    if (not replan and judge_enabled and plan.next == 'tasks' and plan.question_type == 'candidate_find'
            and not any(t.agent == 'judge' and t.kind == 'candidate_find' for t in plan.tasks)):
        # [주의] 코드 라우팅(11-10 조장 결정, ADR 0017): 계획 스스로 찾기 질문이라 해 놓고 판정 찾기 할 일을 내지 않으면 코드가 그 할 일로 바꾼다.
        #      Haiku Supervisor가 찾기를 문서 할 일(rating · candidate_find)이나 문서 + 이름 없는 판정으로 나눠 후보를 못 냈다
        #      (#46 v3-12 · 14 · 15, h4-12 찾기 질문: 문제를 적어 다시 물어도 같은 계획). 역할 할 일만 남긴다(다른 물음)
        roles = [t for t in plan.tasks if t.kind == 'role']
        find = Task(id=1, agent='judge', kind='candidate_find', goal='Find candidates that meet the conditions in the question.')
        plan = plan.model_copy(update={'tasks': [find, *(t.model_copy(update={'id': i}) for i, t in enumerate(roles, 2))], 'replan': False})
    if not judge_enabled:
        # [왜] Spec 에이전트가 없으면 판정 할 일은 문서 할 일로 돌린다(거절이 아니라 근거로 답하는 길, 예전 Supervisor와 같음)
        plan.tasks = [t.model_copy(update={'agent': 'docs', 'query': t.query or t.goal}) if t.agent == 'judge' else t for t in plan.tasks]
    out = {'plan': plan.model_dump(mode='json'), 'counters': c, 'path': ['계획'],
           'round': (state.get('round') or 0) + (1 if plan.next == 'tasks' else 0)}
    if not replan:
        out['question_type'] = plan.question_type  # [왜] 질문 종류는 첫 계획이 정한다(채점기가 읽는다)
    if plan.next == 'refuse':
        out['refusal_reason'] = plan.reason.value
    return out


def payload(state: dict, task: dict) -> dict:
    """Send 꾸러미: 서브에이전트는 메모장 전체가 아니라 지시서와 필요한 입력만 받는다(컨텍스트 분리)."""
    base = {'task': task, 'question': state['question'], 'target_part': state.get('target_part') or {}, 'round': state.get('round') or 1}
    if state.get('approved_memories'):
        base['approved_memories'] = state['approved_memories']
    if task['agent'] == 'judge':
        base.update(conditions=state.get('conditions', ''), target=state.get('target', ''), facts=state.get('facts') or {},
                    question_type=task['kind'],  # [왜] 판정 코드는 question_type으로 판정 · 찾기를 가른다. 할 일 종류가 그 값이다
                    mount_preference=state.get('mount_preference') or '')  # [왜] 기억 읽기가 읽은 선호 실장 방식. Spec 에이전트만 쓴다(찾기 순서)
    return base


def after_plan(state: dict):
    """계획 뒤 갈림길: 일상 대화 → 끝내기, 가격 → 가격 안내, 거절 → 거절, 할 일 → 서브에이전트에 동시에 Send. 노드 이름을 돌려준다."""
    plan = state.get('plan') or {}
    if state.get('refusal_reason') or not plan:
        return NODE['refuse']
    if plan['next'] == 'answer':
        return NODE['collect']  # 재계획이 더 할 일 없이 받은 보고로 답하라고 했다
    if plan['next'] != 'tasks':
        return NODE[plan['next']]
    # [왜] 할 일끼리 서로 기다릴 필요가 없어 한 번에 보낸다. LangGraph가 같은 단계에서 동시에 돌리고, 보고는 add_or_reset이 이어 붙인다
    return [Send(NODE[t['agent']], payload(state, t)) for t in plan['tasks']]


def final_reports(state: dict) -> list[TaskReport]:
    """답에 쓸 보고: 모으기가 고른 것(재계획 뒤 이번 회차 + 남기라 한 앞 회차), 없으면 전체."""
    return [TaskReport.model_validate(r) for r in (state.get('final_reports') or state.get('reports') or [])]


def collect_node(state: dict) -> dict:
    """그래프 노드 `답 모으기`(코드): 상한을 보고, 보고 상태 · 사유로 재계획 · 답 정리 · 종합 · 거절을 정한다."""
    reports = [TaskReport.model_validate(r) for r in state.get('reports') or []]
    plan, rnd = state.get('plan') or {}, state.get('round') or 1
    c = {**(state.get('counters') or {}), 'agents': len(reports), 'searches': sum(len(r.searches) for r in reports)}
    out = {'counters': c, 'path': ['모으기']}
    if len(reports) > MAX_AGENT_RUNS:
        return {**out, 'outcome': 'refuse', 'refusal_reason': Reason.LIMIT_REACHED.value}
    if not bind_run_citations(reports):
        return {**out, 'outcome': 'refuse', 'refusal_reason': Reason.VERIFY_FAILED.value}
    current = [r for r in reports if r.round == rnd]
    if plan.get('next') == 'answer':
        final = [r for r in current if r.status != 'fail'] or current  # 재계획이 '있는 답으로'라 했다: 이번 회차의 쓸 만한 보고
    elif rnd > 1:
        final = [r for r in reports if r.round < rnd and r.status == 'ok' and plan.get('keep_earlier')] + current
    else:
        final = reports
    # [왜] 설계 v2(11-07, MULTI_AGENT.md 실패 고리): 다시 해 볼 만한 실패 · 앞 결과가 필요한 계획이면 Supervisor(계획)로 한 번 되돌린다.
    #      확정 거절 사유(코퍼스 밖 · 목록 대조 · 도구 장애 · 상한)는 다시 해도 같아 되돌리지 않는다. 무엇을 할지는 계획(LLM)이 정한다
    # [주의] RAG 에이전트의 '일부만 답함'(partial, 사유 없음)은 되돌리지 않는다. 답은 있고, 매번 Supervisor를 한 번 더 부르면 시간이 는다
    # [주의] RAG 에이전트가 검색어를 바꿔 두 번 찾고도 근거가 아니라고 본 것(all_rejected)은 되돌리지 않는다. 그 데이터시트에 없는 성질을
    #      다시 찾느라 Supervisor · 문서를 한 번 더 불러 13초가 걸렸다(11-07 판정 dev irr-11 장기 안정성)
    tried = lambda r: r.reason == Reason.ALL_REJECTED and len(r.searches) >= MAX_SEARCHES
    retry = [r for r in current if not tried(r) and ((r.status == 'fail' and (r.reason is None or r.reason in RETRY_REASONS))
                                                     or (r.status == 'partial' and r.reason in RETRY_REASONS))]
    if plan.get('next') != 'answer' and c.get('replans', 0) < MAX_REPLANS and (retry or plan.get('replan')):
        if os.getenv('SUPERVISOR_REPLAN', '1') == '0':
            pass  # [왜] 속도·정확도 A/B용. 기본(1)은 재계획 유지. 0이면 no_result 등에서도 docs 재시도 없이 아래 거절·답으로 간다
        else:
            return {**out, 'outcome': 'replan'}
    final_dump = {'final_reports': [r.model_dump(mode='json') for r in final]}
    good = [r for r in final if r.status != 'fail']
    if not good:
        # [왜] 모든 할 일이 실패했으면 첫 실패의 사유로 거절한다. 다시 찾을 사유(no_result 등)로 끝났으면 '못 찾음'이다
        first = next((r.reason for r in final if r.reason), Reason.NOT_FOUND)
        return {**out, **final_dump, 'outcome': 'refuse',
                'refusal_reason': (Reason.NOT_FOUND if first in RETRY_REASONS else first).value}
    # 문서 답은 일부 실패해도 검증된 다른 보고를 그대로 보존한다. 종합이 이미 찾은 정격을 누락했던 T1 재발을 막는다.
    # [왜] 판정 할 일도 답이 코드 답 틀이라 모두 ok면 종합 LLM 없이 코드로 잇는다(복합 질문 p95 18초, 11-07 c20).
    #      판정(kind=judge)이 끝난 답은 답 정리 · 종합 모두 판정 답 틀만 쓰고 문서 답은 붙이지 않는다(`_judgement_reply`)
    uses_pdf = any(cid.startswith('W') for r in good for cid in r.evidence_ids)
    joinable = uses_pdf or len(final) == 1 or all(r.status == 'ok' for r in final) or all(r.agent == 'docs' for r in final)
    return {**out, **final_dump, 'outcome': 'single' if joinable else 'synth'}


def after_collect(state: dict) -> str:
    """모으기 뒤 갈림길: 모으기가 정한 길(outcome)을 노드 이름으로, 재계획은 간선 라벨 키(REPLAN)로 돌려준다."""
    return REPLAN if state['outcome'] == 'replan' else NODE[state['outcome']]


def _merged(reports: list[TaskReport]) -> dict:
    """채점기 · 답 검사가 읽는 칸: 문서 할 일이 보여 준 청크와 그 id, 첫 판정 결과."""
    docs = list({d['chunk_id']: d for r in reports for d in r.docs}.values())
    judgement = next((r.judgement for r in reports if r.agent == 'judge' and r.status != 'fail' and r.judgement), {})
    return {'docs': docs, 'passed': [d['chunk_id'] for d in docs], 'judgement': judgement,
            'memory_refs': sorted({ref for r in reports if r.status != 'fail' for ref in r.memory_refs})}


def part_text(r: TaskReport) -> str:
    """보고 하나의 부분 답 글. 판정은 코드 답 틀(숫자 · 인용은 판정 결과 그대로)."""
    return render_judgement(r.judgement) if r.agent == 'judge' and r.judgement else r.answer


def declined_text(state: dict) -> str:
    """계획이 거절한 부분마다 한 줄: 물은 말 + 거절 문구(사용자 문구는 거절 노드와 같은 refusal_for)."""
    lines = [f"- 답하지 않은 부분 '{d['ask']}': {refusal_for(Reason(d['reason']), state.get('facts') or {})}"
             for d in (state.get('plan') or {}).get('declined') or []]
    return '\n'.join(lines)


def _with_declined(state: dict, answer: str) -> str:
    extra = declined_text(state)
    return f'{answer}\n\n{extra}' if extra else answer


def _judgement_reply(state: dict, reports: list[TaskReport]) -> dict | None:
    """판정(kind=judge)이 끝난 답의 출력 경계: 코드 판정 답 틀만 쓰고 문서 · 종합의 자유 글은 붙이지 않는다. 판정이 없으면 None."""
    # [왜] 판정표가 '불충족'인데 문서 에이전트 글이 옆에 사용 권고(C2 공격)나 '부하 0.1 A 미제공' 같은 오서술(P4 정상군)을 붙여
    #      최종 답까지 나갔다(docs/research/thread-memory-work-summary.md). 문서 글을 검증할 계약이 없어 판정 답에는 넣지 않는다
    # [왜] 판정한 후보가 없으면 판정 보고는 fail이 된다(judge_task_node). 성공한 판정만 보면 '실패한 판정 + 문서 답'에서
    #      문서 글("사용해도 됩니다")이 그대로 나가므로, 판정(kind=judge) 보고가 하나라도 있으면 성공 · 실패와 관계없이 이 경계를 쓴다(11-10 조장 결정)
    asked = [r for r in reports if r.agent == 'judge' and r.judgement.get('kind') == 'judge']
    if not asked:
        return None
    judged = [r for r in reports if r.agent == 'judge' and r.status != 'fail' and r.judgement]
    parts = [render_judgement(r.judgement) for r in judged] or ['판정을 완료하지 못했습니다.']
    if any(r.agent == 'docs' for r in reports):
        # [주의] 기능 절충: 판정과 함께 물은 별도 문서 설명은 답하지 않고 그렇다고 알린다. 문서만 묻는 질문 · 찾기(find) · no_rule 길은 그대로다
        parts.append('별도로 요청한 문서 설명은 이 답변에 포함하지 않았습니다.')
    if judged and any(r.agent == 'judge' and (r.status != 'ok' or not r.judgement.get('results')) for r in reports):
        parts.append('일부 부품의 판정은 완료하지 못했습니다.')  # 실패 · 미완료 판정에서 예전 자유 글로 돌아가지 않는다
    # [왜] 원래 보고(state['reports'])는 그대로 두고, 답 검사(check_node)에는 실제로 답에 쓴 판정 보고만 넘긴다(final_reports는 덮어쓰는 칸).
    #      모두 실패면 그 판정 보고를 넘긴다. 비우면 final_reports()가 문서 보고까지 되살려 답 검사가 인용 없음으로 거절한다
    return {**_merged(judged), 'final_reports': [r.model_dump(mode='json') for r in (judged or asked)],
            'answer': _with_declined(state, '\n\n'.join(parts)), 'synth_text': '', 'path': ['답 정리']}


def single_node(state: dict) -> dict:
    """검증된 문서 답은 LLM 없이 보존하고, 판정이 끝났으면 판정 답 틀만 쓴다."""
    reports = sorted(final_reports(state), key=lambda r: (r.round, r.task))
    judged = _judgement_reply(state, reports)
    if judged is not None:
        return judged
    docs_only = all(r.agent == 'docs' for r in reports)
    kept = [r for r in reports if r.status != 'fail'] if docs_only else reports
    answer = '\n\n'.join(part_text(r) for r in kept)
    if docs_only and any(r.status != 'ok' for r in reports) and (len(reports) > 1 or any(r.missing for r in kept)):
        answer += '\n\n일부 문서 작업은 완료되지 않았습니다. 위 내용은 확인된 답변만 포함합니다.'
    return {**_merged(kept), 'answer': _with_declined(state, answer), 'synth_text': '', 'path': ['답 정리']}


class Synth(BaseModel):
    """종합 LLM의 답안지."""
    answer: str = Field(description='Korean answer that joins the parts; keeps every [n] citation; judge verdict tables are added by code after it')
    memory_refs: list[str] = Field(default_factory=list, max_length=5, description='Historical source IDs consulted; not answer evidence')


def render_synth(state: dict, reports: list[TaskReport]) -> str:
    plan_tasks = {t['id']: t for t in (state.get('plan') or {}).get('tasks', [])}
    lines = [f"Question: {state['question']}", 'Parts:']
    for r in sorted(reports, key=lambda r: r.task):
        t = plan_tasks.get(r.task, {})
        lines.append(f"{r.task}. [{r.agent} · {t.get('kind', '')}] goal: {t.get('goal', '')} → {r.status}"
                     + (f" (reason {r.reason.value})" if r.reason else ''))
        if r.status != 'fail':
            lines.append('answer:\n' + part_text(r))
    return '\n'.join(lines) + memory_context(state.get('approved_memories') or [])


def synth_node(state: dict, *, chat) -> dict:
    """그래프 노드 `종합`(LLM 1번): 할 일 2개 이상의 부분 답을 한 답으로 합친다. 판정 답 틀은 코드가 뒤에 그대로 붙인다.
    판정(kind=judge)이 끝났으면 LLM을 부르지 않고 판정 답 틀만 쓴다(`_judgement_reply`)."""
    reports = final_reports(state)
    judged = _judgement_reply(state, sorted(reports, key=lambda r: (r.round, r.task)))
    if judged is not None:
        return judged
    c = {**state['counters'], 'hops': state['counters']['hops'] + 1}
    if c['hops'] > MAX_SUPERVISOR_CALLS:
        return {'counters': c, 'refusal_reason': Reason.LIMIT_REACHED.value, 'answer': '', 'path': ['종합']}
    response = chat('synth', SYNTH_PROMPT, render_synth(state, reports), Synth)
    text = response.answer.strip()
    # [왜] 판정 숫자는 LLM이 다시 쓰지 않는다(AGENTS 7). 종합 글 뒤에 코드 답 틀을 그대로 붙인다
    tables = [render_judgement(r.judgement) for r in sorted(reports, key=lambda r: r.task) if r.agent == 'judge' and r.status != 'fail' and r.judgement]
    merged = _merged(reports)
    return {**merged, 'memory_refs': sorted(set(merged['memory_refs']) | set(response.memory_refs)),
            'counters': c, 'answer': _with_declined(state, '\n\n'.join([text, *tables])), 'synth_text': text, 'path': ['종합']}


def check_node(state: dict) -> dict:
    """그래프 노드 마무리 답 검사(코드): 인용 번호가 받은 근거 안인지, 종합 글이 부분 답에 없는 숫자를 지어내지 않았는지 본다."""
    from backend.graph.nodes import citations  # [왜] 여기서 불러온다. graph.nodes가 이 모듈의 Facts를 불러 맨 위에서 부르면 순환 import다
    if state.get('refusal_reason'):
        return {'path': ['답 검사']}  # 종합이 상한으로 멈췄다
    answer = state.get('answer') or ''
    reports = final_reports(state)
    valid = {str(i) for i in state.get('passed') or []}
    if state.get('target_part') and any(r.agent == 'docs' and r.status != 'fail' and '넷리스트' in r.evidence_ids for r in reports):
        valid.add('넷리스트')  # 재계획에서 버린 보고나 실패한 역할 작업은 최종 답에 근거 권한을 주지 않는다.
    invalid_memories = set(state.get('memory_refs') or []) - memory_sources(state.get('approved_memories') or [])
    judge_only = all(r.agent == 'judge' for r in reports if r.status != 'fail')
    cited = citations(answer)
    sentences = [s for s in re.split(r'(?<=[.。])\s+', answer) if s.strip()]
    check = {'used': sorted(cited & valid), 'fake_citations': sorted(cited - valid),
             'uncited_sentences': sum(1 for s in sentences if not citations(s)), 'judgement': bool(state.get('judgement'))}
    problem = bool(check['fake_citations'] or invalid_memories) or (not judge_only and not check['used'])
    expected_pdf = {cid for r in reports if r.status != 'fail' for cid in r.evidence_ids if cid.startswith('W')}
    if expected_pdf or any(cid.startswith('W') for cid in cited):
        if expected_pdf != {cid for cid in cited if cid.startswith('W')} or check_pdf_lines(answer, state.get('docs') or []) is None:
            problem = True
    if len(reports) > 1 and not problem:
        # [왜] 종합 글의 숫자는 부분 답 · 판정 결과 · 질문에 있던 숫자여야 한다(설계 그림 "판정 숫자가 코드 결과와 같음")
        part = state.get('target_part') or {}
        given = ' '.join([state['question'], state.get('conditions', ''), part.get('ref', ''), part.get('value', '')])  # 사용자가 준 글과 대상 부품
        known = set(NUMBER.findall(given + ' ' + ' '.join(part_text(r) for r in reports)))
        problem = bool(set(NUMBER.findall(state.get('synth_text', ''))) - known)
    out = {'check': check, 'path': ['답 검사']}
    return {**out, 'refusal_reason': Reason.VERIFY_FAILED.value} if problem else out


def after_check(state: dict) -> str:
    return NODE['refuse'] if state.get('refusal_reason') else NODE['finish']
