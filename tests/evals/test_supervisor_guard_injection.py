"""Supervisor 답 가드 전후 실행기(evals/runners/run_supervisor_guard_injection.py)의 무료 검사: 가짜 LLM으로 도달 경로와 가드 켬/끔 짝을 본다.

- 역할: 코퍼스 글이 재계획 Supervisor 입력에만 닿고 reply 길에는 닿지 않는지, 첫 계획 reply 길에서 가드 켬/끔이 갈리는지, 계획 모드가 호출하지 않는지.
- 하지 않는 일: 실제 모델의 저항성 판단(실측은 --execute 원시 결과의 몫).
"""
import json

import pytest

from backend.multi_agent.contracts import Plan, Reason, Task
from backend.multi_agent.messages import refusal_for
from evals.runners import run_supervisor_guard_injection as runner

CASES = {c['id']: c for c in runner.CASES}


def scripted(*plans):
    """Supervisor만 차례로 답하는 가짜 LLM(RAG 에이전트 답은 K2 사례가 실행기 안에서 고정한다)."""
    queue = list(plans)
    return lambda node, system, user, schema: queue.pop(0)


def test_corpus_text_reaches_only_the_replan_input_and_the_replan_reply_is_never_emitted():
    docs = Plan(question_type='rating', next='tasks', tasks=[Task(id=1, agent='docs', kind='rating', goal='SS34 IFSM', query='SS34 IFSM')])
    obey = Plan(question_type='chat', next='finish', reply=runner.ATTACK_REPLY)  # 재계획 Supervisor가 심은 글을 따른 최악의 경우
    row = runner.run_case(CASES['K2-A'], scripted(docs, obey))
    assert row['canary_in_supervisor_input'] == [False, True] and row['reply_markers']
    assert row['finish_reply_branch'] is False and row['on_matches_graph']
    assert row['answer_on'] == row['answer_off'] and not row['final_markers_on'] and not row['final_markers_off']


def test_first_plan_reply_is_split_by_the_guard_only():
    row = runner.run_case(CASES['D1-url'], scripted(Plan(question_type='chat', next='finish', reply=runner.ATTACK_REPLY)))
    assert row['finish_reply_branch'] and row['guard_reason'] == 'url' and row['on_matches_graph']
    assert row['answer_on'] == refusal_for(Reason.OUT_OF_SCOPE, {}) and row['answer_off'] == runner.ATTACK_REPLY
    assert not row['final_markers_on'] and row['final_markers_off']


def test_history_numbers_pass_but_new_numbers_are_over_blocked():
    passed = runner.run_case(CASES['N4-history'], scripted(Plan(question_type='chat', next='finish', reply='입력 12 V, 부하 20 mA였습니다.')))
    assert passed['guard_reason'] == '' and passed['answer_on'] == passed['answer_off'] == '입력 12 V, 부하 20 mA였습니다.'
    concept = runner.run_case(CASES['N2-schottky'], scripted(Plan(question_type='chat', next='finish', reply='쇼트키는 순방향 전압이 약 0.3 V로 낮습니다.')))
    assert concept['guard_reason'] == 'new_quantity' and concept['answer_on'] != concept['answer_off']


def test_plan_mode_calls_nothing_and_refuses_to_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'run_case', lambda *a: pytest.fail('plan mode ran a case'))
    out = tmp_path / 'guard.json'
    assert runner.main(['--out', str(out)]) == 0
    report = json.loads(out.read_text(encoding='utf-8'))
    assert len(report['jobs']) == len(runner.CASES) * runner.REPEATS and {j['status'] for j in report['jobs']} == {'not_run'}
    assert report['limits']['max_usd'] <= 1.0 and report['billing_reconciled'] is False
    with pytest.raises(FileExistsError):
        runner.main(['--out', str(out), '--execute'])
