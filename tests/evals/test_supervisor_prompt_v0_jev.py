"""Jev Decisions Supervisor Prompt V0 실행 경로를 API 없이 검증한다."""

import json

import pytest

from backend.graph.supervisor import build_jev_question_contract
from evals.runners import run_supervisor_prompt_v0_jev as jev


def jev_response(**choices):
    return {
        "answers": {
            key: {
                "type": "choice",
                "choice": value,
                "confidence": 1.0,
                "probabilities": {value: 1.0},
            }
            for key, value in choices.items()
        }
    }


def item_with_only_circuit():
    return {
        "id": "sv0-09",
        "user_request": "D1 대신 SS14를 쓸 수 있나?",
        "current_state": {"available_evidence": ["circuit"]},
        "external_material": [{"source": "circuit", "ref": "fixture-circuit"}],
        "gold": {
            "question_type": "candidate_judge",
            "required_evidence": ["circuit", "datasheet"],
            "next_action": "search_agent",
            "reason_code": "CANDIDATE_JUDGE",
        },
    }


def test_jev_uses_canonical_v0_contract():
    assert jev.QUESTION_CONTRACT == build_jev_question_contract()


def test_jev_request_uses_same_input_envelope_without_gold():
    item = {
        "id": "sv0-01",
        "user_request": "MOSFET 추천해 줘",
        "current_state": {},
        "external_material": [],
        "gold": {"question_type": "out_of_scope"},
    }

    request = jev.build_request_from_item(item)

    assert request["model"] == "typesafe/jev-1.14"
    assert set(request["state"]) == {"user_request", "current_state", "external_material"}
    assert "gold" not in str(request)
    assert "sv0-01" not in str(request)


def test_jev_row_records_semantic_errors_separately():
    payload = jev_response(
        question_type="candidate_judge",
        needs_circuit="yes",
        needs_datasheet="yes",
        needs_approved_case="no",
        next_action="judge_answer_agent",
    )

    row = jev.parse_item_response(item_with_only_circuit(), payload)

    assert row["decision"]["required_evidence"] == ["circuit", "datasheet"]
    assert row["semantic_errors"] == ["next_action"]


def test_jev_rejects_invalid_probability_contract():
    payload = jev_response(
        question_type="candidate_judge",
        needs_circuit="yes",
        needs_datasheet="yes",
        needs_approved_case="no",
        next_action="search_agent",
    )
    payload["answers"]["next_action"]["probabilities"] = {"search_agent": 1.2}

    with pytest.raises(jev.JevFormatError):
        jev.parse_item_response(item_with_only_circuit(), payload)


def test_jev_plan_is_network_free(tmp_path, monkeypatch):
    monkeypatch.setattr(
        jev.llm,
        "evaluation_decision",
        lambda request: pytest.fail("plan must not call Decisions API"),
    )
    output = tmp_path / "jev-v0"

    assert jev.main(["plan", str(output)]) == 0

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["jobs"]) == 13
    assert manifest["model"] == "typesafe/jev-1.14"
    assert len(manifest["question_contract_sha256"]) == 64
    assert len(manifest["common_module_sha256"]) == 64
    assert len(manifest["contract_sha256"]) == 64


def test_jev_live_requires_confirmation_and_positive_caps(tmp_path):
    with pytest.raises(SystemExit):
        jev.main([
            "run", str(tmp_path), "--max-calls", "13", "--max-seconds", "60",
            "--max-usd", "1",
        ])


def test_jev_run_requires_matching_smoke(tmp_path, monkeypatch):
    run_dir = tmp_path / "jev-v0"
    assert jev.main(["plan", str(run_dir)]) == 0

    with pytest.raises(ValueError, match="smoke"):
        jev.execute(run_dir, max_calls=13, max_seconds=60, approved_max_usd=1)

    smoke = {
        "status": "complete",
        "model_id": jev.MODEL_ID,
        "provider": "TypeSafe",
        "actual_model": jev.MODEL_ID,
        "dataset_sha256": jev._sha256(jev.DATASET),
        "contract_sha256": jev._sha256(jev.CONTRACT_PATH),
    }
    (run_dir / "smoke_typesafe__jev-1.14.json").write_text(
        json.dumps(smoke), encoding="utf-8"
    )
    policies = []

    def fake_decision(request, **kwargs):
        policies.append(request["provider"])
        return {
            **jev_response(
                question_type="out_of_scope",
                needs_circuit="no",
                needs_datasheet="no",
                needs_approved_case="no",
                next_action="refuse",
            ),
            "model": jev.MODEL_ID,
            "provider": "TypeSafe",
            "usage": {},
        }

    monkeypatch.setattr(jev.llm, "evaluation_decision", fake_decision)
    result = jev.execute(run_dir, max_calls=13, max_seconds=60, approved_max_usd=1)

    assert result["status"] == "complete"
    assert len(policies) == 13
    assert all(policy["only"] == ["TypeSafe"] for policy in policies)
    with pytest.raises(SystemExit):
        jev.main([
            "run", str(tmp_path), "--max-calls", "0", "--max-seconds", "60",
            "--max-usd", "1", "--confirm-live",
        ])
