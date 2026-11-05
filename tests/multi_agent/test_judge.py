"""판정 에이전트(backend/multi_agent/agents/judge.py) 시험: 가짜 LLM · 가짜 사양 표로 읽기 · 숫자 확인 · 인터럽트 · 판정을 본다.

- 역할: AC-02(질문에 없는 숫자는 버림) · AC-07(other) · AC-08(인터럽트 1번) · AC-09(비교는 verdict에서만), 찾기 흐름.
- 하지 않는 일: 실제 LLM · MCP · DB 호출.
- 출처: docs/specs/judge-agent.md What · How · AC
"""
from backend.multi_agent.agents import judge as J

STATE = {'question': 'D1을 TSC 1N5817로 바꿔도 역극성 보호용으로 쓸 수 있어?',
         'conditions': '입력 전압의 최댓값은 20V, D1의 최대 순방향 전류는 150mA이다. 주변 온도는 25°C이다.',
         'target': 'D1', 'target_part': {'ref': 'D1', 'value': '1N4001', 'footprint': 'Diode_THT:D_DO-41_SOD81_P10.16mm',
                                         'nets': [{'name': 'RAW', 'nodes': ['D1.K(1N4001)', 'F1.1(500mA)'], 'more': 0}]},
         'question_type': 'candidate_judge'}


def test_judge_read_calls_llm_once_with_roles_and_circuit():
    seen = []

    def chat(node, system, user, schema):
        seen.append((node, user))
        return J.JudgeRead(role='R01', role_evidence=['D1.K → RAW'])
    out = J.judge_read_agent(STATE, chat=chat)
    assert len(seen) == 1 and seen[0][0] == 'judge_read'
    assert 'R01' in seen[0][1] and 'D1.K(1N4001)' in seen[0][1] and '150mA' in seen[0][1]
    assert out['judge_read']['role'] == 'R01' and out['path'] == ['판정 읽기']
