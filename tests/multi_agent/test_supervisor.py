"""Supervisor(backend/multi_agent/supervisor.py) 시험: 지시서 받기 · 갈림길 · 답 검사.

- 역할: Supervisor LLM에 주는 글(질문 · 대상 · 사실 · 고를 수 있는 에이전트), 형식이 끝내 틀리면 거절, 대체 부품 에이전트가 꺼지면 RAG로,
  갈림길이 지시서의 다음 길 이름을 그대로 돌려주는지, 답 검사가 없는 근거 인용 · 인용 없는 답을 막는지, 프롬프트가 에이전트 하나를 고르게 쓰였는지 본다.
  가짜 LLM을 쓰므로 API를 부르지 않는다.
- 하지 않는 일: LLM이 실제로 좋은 길을 고르는지는 보지 않는다(그건 실제 평가셋으로 잰다).
- 출처: backend/multi_agent/supervisor.py, backend/prompts/supervisor.md, 강의 IV-3 15강
"""
from backend.multi_agent import supervisor as S
from backend.multi_agent.contracts import Plan, Reason, Task

STATE = {'question': 'D1을 1N5817로 바꿔도 돼?', 'target': 'D1', 'conditions': '입력 최대 20V',
         'target_part': {'ref': 'D1', 'value': '1N4148', 'footprint': 'DO-35', 'nets': []},
         'facts': {'parts': {'1N5817': True, 'BAT85': False}, 'revisions': {}}}


def test_supervisor_input_has_question_target_facts_and_agents():
    text = S.render_plan(STATE, judge_enabled=True)
    for want in ('D1을 1N5817로', 'D1 1N4148 DO-35', '입력 최대 20V', 'part 1N5817: in corpus', 'part BAT85: NOT in corpus', 'docs, judge'):
        assert want in text, want
    assert 'judge' not in S.render_plan(STATE, judge_enabled=False).split('Agents you may use:')[1]


def test_format_failure_ends_as_refusal_without_agents():
    def chat(node, system, user, schema):
        raise ValueError('형식을 3번 모두 어겼다')  # llm.chat이 다시 불러도 틀렸을 때 내는 오류
    out = S.plan_node(STATE, chat=chat, judge_enabled=True)
    assert out['refusal_reason'] == Reason.LIMIT_REACHED.value and out['plan'] == {} and out['counters']['hops'] == 1
    assert S.after_plan({**STATE, **out}) == 'refuse'


def test_supervisor_writes_the_brief_for_the_chosen_agent_and_counts_one_call():
    p = Plan(question_type='candidate_judge', next='judge', task=Task(goal='judge 1N5817'))
    out = S.plan_node(STATE, chat=lambda *a: p, judge_enabled=True)
    assert out['task']['goal'] == 'judge 1N5817' and out['question_type'] == 'candidate_judge'
    assert out['counters'] == {'hops': 1, 'searches': 0} and out['path'] == ['Supervisor'] and 'refusal_reason' not in out


def test_judge_goes_to_the_rag_agent_when_judge_is_off():
    p = Plan(question_type='candidate_judge', next='judge', task=Task(goal='goal 1'))
    out = S.plan_node(STATE, chat=lambda *a: p, judge_enabled=False)
    assert out['plan']['next'] == 'docs' and out['task']['query'] == 'goal 1'  # 검색어가 없으면 목표로 찾는다


def test_after_plan_returns_the_next_step_name_for_the_edge_table():
    """[왜] 어느 노드로 갈지는 build.py 간선 표가 정한다(강의 03강). 갈림길 함수는 지시서의 이름만 돌려준다."""
    for nxt in ('docs', 'judge', 'finish', 'price', 'refuse'):
        assert S.after_plan({'plan': {'next': nxt}, 'refusal_reason': ''}) == nxt
    assert S.after_plan({'plan': {'next': 'refuse'}, 'refusal_reason': 'out_of_scope'}) == 'refuse'


def test_check_blocks_fake_citations_and_uncited_answers():
    docs = [{'chunk_id': 7, 'file': 'a.pdf', 'page': 1, 'content': 'x'}]
    one = {**STATE, 'docs': docs, 'passed': [7]}
    assert 'refusal_reason' not in S.check_node({**one, 'answer': 'VRRM은 40 V이다 [7].'})
    assert S.check_node({**one, 'answer': 'VRRM은 40 V이다 [8].'})['refusal_reason'] == 'verify_failed'  # 받은 적 없는 근거
    assert S.check_node({**one, 'answer': 'VRRM은 40 V이다.'})['refusal_reason'] == 'verify_failed'      # 인용이 하나도 없음
    # 판정 답 틀은 번호 인용 없이 표로 근거를 단다
    assert 'refusal_reason' not in S.check_node({**STATE, 'answer': '1N5817: 불충족', 'judgement': {'kind': 'judge'}})
    # 에이전트가 이미 거절 사유를 냈으면 검사하지 않고 거절로 보낸다
    out = S.check_node({**one, 'answer': '', 'refusal_reason': 'not_found'})
    assert out == {'path': ['답 검사']} and S.after_check({'refusal_reason': 'not_found'}) == 'refuse'
    assert S.after_check({'refusal_reason': ''}) == 'finish'


def test_prompt_picks_one_agent_and_keeps_constraints():
    for reason in ('out_of_scope', 'part_missing', 'revision_missing', 'not_found'):
        assert reason in S.PROMPT, reason
    assert 'never compare numbers' in S.PROMPT and 'exactly one of' in S.PROMPT
    # [왜] 할 일 목록 · 재계획은 11-09에 뺐다. 프롬프트에 남으면 모델이 없는 칸을 쓴다
    for gone in ('REPLAN', 'replan', 'keep_earlier', '1 to 3 tasks', 'Tasks run at the same time'):
        assert gone not in S.PROMPT, gone
