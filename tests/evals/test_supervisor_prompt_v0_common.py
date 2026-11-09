"""Supervisor V0 상태 평가셋의 동결·입력 격리·채점을 API 없이 검사한다."""

import hashlib
import json

import pytest

from evals.runners.supervisor_prompt_v0_common import (
    DATASET,
    FROZEN,
    load_v0_dataset,
    model_input,
    score_decisions,
)


def test_loader_rejects_changed_dataset_hash(tmp_path):
    """평가 행을 바꾼 뒤 hash를 갱신하지 않으면 모델 비교 입력이 조용히 달라진다."""
    dataset = tmp_path / "v0.jsonl"
    dataset.write_text('{"id":"x"}\n', encoding="utf-8")
    frozen = tmp_path / "frozen.json"
    frozen.write_text(json.dumps({"sha256": "0" * 64, "count": 1}), encoding="utf-8")

    with pytest.raises(ValueError, match="hash"):
        load_v0_dataset(dataset, frozen)


def test_model_input_excludes_id_and_gold():
    """정답과 case id가 모델 입력에 들어가면 평가 정확도가 누출로 부풀려진다."""
    item = {
        "id": "sv0-03",
        "user_request": "D1 역할은?",
        "current_state": {},
        "external_material": [],
        "gold": {
            "question_type": "role",
            "required_evidence": ["circuit"],
            "next_action": "circuit_agent",
            "reason_code": "ROLE",
        },
    }

    assert model_input(item) == {
        "user_request": "D1 역할은?",
        "current_state": {},
        "external_material": [],
    }
    assert "gold" not in json.dumps(model_input(item), ensure_ascii=False)
    assert "sv0-03" not in json.dumps(model_input(item), ensure_ascii=False)


def test_score_keeps_failed_rows_in_every_denominator():
    """실패한 문항을 분모에서 빼면 불완전한 모델의 정확도가 높아진다."""
    items = [
        {"id": "a", "gold": {
            "question_type": "rating",
            "required_evidence": ["datasheet"],
            "next_action": "search_agent",
            "reason_code": "RATING",
        }},
        {"id": "b", "gold": {
            "question_type": "role",
            "required_evidence": ["circuit"],
            "next_action": "circuit_agent",
            "reason_code": "ROLE",
        }},
    ]
    rows = [
        {"case_id": "a", "status": "complete", "semantic_errors": [],
         "decision": items[0]["gold"]},
        {"case_id": "b", "status": "error", "error_type": "TimeoutError"},
    ]

    assert score_decisions(rows, items) == {
        "case_count": 2,
        "completion_rate": 0.5,
        "question_type_accuracy": 0.5,
        "required_evidence_exact_match": 0.5,
        "next_action_accuracy": 0.5,
        "reason_code_accuracy": 0.5,
        "semantic_valid_rate": 0.5,
        "exact_decision_match": 0.5,
    }


def test_repository_dataset_has_thirteen_frozen_state_cases():
    """V0 비교셋은 같은 요청의 상태 전이를 포함한 사전 합의 13건이어야 한다."""
    items = load_v0_dataset(DATASET, FROZEN)
    metadata = json.loads(FROZEN.read_text(encoding="utf-8"))

    assert len(items) == 13
    assert metadata == {
        "sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        "count": 13,
    }
    by_id = {item["id"]: item for item in items}
    assert by_id["sv0-08"]["user_request"] == by_id["sv0-09"]["user_request"] == by_id["sv0-10"]["user_request"]
    assert by_id["sv0-08"]["gold"]["next_action"] == "circuit_agent"
    assert by_id["sv0-09"]["gold"]["next_action"] == "search_agent"
    assert by_id["sv0-10"]["gold"]["next_action"] == "judge_answer_agent"
    assert by_id["sv0-13"]["current_state"]["retry_exhausted"] is True
    assert by_id["sv0-13"]["gold"]["next_action"] == "refuse"
