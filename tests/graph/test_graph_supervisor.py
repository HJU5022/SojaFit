"""Supervisor V0의 공통 출력·입력·의미 계약을 API 없이 검사한다."""

import json

import pytest
from pydantic import ValidationError

from backend.graph.supervisor import (
    SupervisorDecision,
    build_input_envelope,
    build_jev_question_contract,
    render_chat_input,
    semantic_errors,
)


def test_decision_rejects_fields_outside_the_four_field_contract():
    """Supervisor가 사용자 답변 같은 추가 필드를 내면 다음 노드가 계약 밖 값을 받는다."""
    with pytest.raises(ValidationError):
        SupervisorDecision.model_validate({
            "question_type": "candidate_judge",
            "required_evidence": ["circuit", "datasheet"],
            "next_action": "search_agent",
            "reason_code": "CANDIDATE_JUDGE",
            "answer": "수퍼바이저가 직접 만든 답",
        })


def test_input_envelope_keeps_user_state_and_external_material_separate():
    """상태나 외부 자료가 사용자 원문에 합쳐지면 반복 호출의 근거 경계를 잃는다."""
    envelope = build_input_envelope(
        "D3 대신 1N60P를 쓸 수 있나?",
        current_state={"available_evidence": ["circuit"]},
        external_material=[{"source": "datasheet", "text": "VF table"}],
    )

    assert envelope == {
        "user_request": "D3 대신 1N60P를 쓸 수 있나?",
        "current_state": {"available_evidence": ["circuit"]},
        "external_material": [{"source": "datasheet", "text": "VF table"}],
    }
    assert "gold" not in json.dumps(envelope, ensure_ascii=False)
    assert json.loads(render_chat_input(envelope)) == envelope


def test_input_envelope_supplies_empty_first_call_state():
    """최초 호출의 빈 상태가 호출자마다 다른 모양이면 모델 비교 입력이 달라진다."""
    assert build_input_envelope("D1 역할은?") == {
        "user_request": "D1 역할은?",
        "current_state": {
            "completed_actions": [],
            "available_evidence": [],
            "last_result": None,
            "failures": [],
            "retry_exhausted": False,
        },
        "external_material": [],
    }


def test_semantic_validation_reports_order_reason_and_action_conflicts():
    """스키마가 맞아도 근거 순서·사유·상태 라우팅이 모순이면 유효 결정이 아니다."""
    decision = SupervisorDecision(
        question_type="candidate_judge",
        required_evidence=["datasheet", "circuit"],
        next_action="judge_answer_agent",
        reason_code="RATING",
    )

    assert semantic_errors(decision, {"available_evidence": ["circuit"]}) == [
        "evidence_order",
        "reason_code",
        "next_action",
    ]


def test_jev_contract_exposes_the_same_types_evidence_and_actions():
    """Jev typed questions가 Chat 계약과 달라지면 세 모델을 같은 의미로 비교할 수 없다."""
    contract = build_jev_question_contract()

    assert set(contract) == {
        "question_type",
        "needs_circuit",
        "needs_datasheet",
        "needs_approved_case",
        "next_action",
    }
    assert set(contract["question_type"]["criteria"]) == {
        "out_of_scope",
        "insufficient_information",
        "candidate_judge",
        "candidate_find",
        "role",
        "rating",
    }
    assert set(contract["next_action"]["criteria"]) == {
        "circuit_agent",
        "search_agent",
        "judge_answer_agent",
        "refuse",
    }
