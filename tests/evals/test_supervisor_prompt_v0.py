"""Luna·Haiku Supervisor Prompt V0 실행 경로를 네트워크 없이 검증한다."""

import json

import pytest

from backend.services import llm
from evals.runners import run_supervisor_prompt_v0 as runner


def test_v0_chat_models_are_exactly_luna_and_haiku():
    assert runner.MODELS == ("openai/gpt-6-luna", "anthropic/claude-haiku-5.5")


def test_v0_job_sends_envelope_without_gold():
    calls = []
    item = {
        "id": "sv0-01",
        "user_request": "MOSFET 추천해 줘",
        "current_state": {},
        "external_material": [],
        "gold": {"question_type": "out_of_scope"},
    }

    def fake_call(model, system, user, schema, **kwargs):
        calls.append((model, system, user, schema, kwargs))
        assert "gold" not in user
        assert "sv0-01" not in user
        return schema(
            question_type="out_of_scope",
            required_evidence=[],
            next_action="refuse",
            reason_code="OUT_OF_SCOPE",
        ), {"usage": {"total_tokens": 1}}

    row = runner.run_one("openai/gpt-6-luna", item, call=fake_call)

    assert len(calls) == 1
    assert row["status"] == "complete"
    assert row["first_pass_valid"] is True
    assert row["semantic_errors"] == []


def test_v0_job_retries_only_format_errors_three_raw_attempts():
    calls = 0
    item = {
        "id": "sv0-01",
        "user_request": "MOSFET 추천해 줘",
        "current_state": {},
        "external_material": [],
    }

    def invalid_call(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise llm.EvaluationFormatError({"usage": {"total_tokens": 1}})

    row = runner.run_one("openai/gpt-6-luna", item, call=invalid_call)

    assert calls == 3
    assert row["status"] == "error"
    assert row["error_type"] == "ValidationError"
    assert row["first_pass_valid"] is False
    assert row["raw_attempts"] == 3


def test_plan_is_network_free_and_contains_26_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runner.llm,
        "_evaluation_client",
        lambda timeout: pytest.fail("plan must not create client"),
    )
    output = tmp_path / "chat-v0"

    assert runner.main(["plan", str(output)]) == 0

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["jobs"]) == 26
    assert manifest["models"] == list(runner.MODELS)
    assert manifest["provider_policy"] == runner.PROVIDER_POLICY
    assert len(manifest["dataset_sha256"]) == 64
    assert len(manifest["prompt_sha256"]) == 64
    assert len(manifest["common_module_sha256"]) == 64
    assert len(manifest["contract_sha256"]) == 64


def test_live_commands_require_confirmation_and_positive_limits(tmp_path):
    with pytest.raises(SystemExit):
        runner.main([
            "run", str(tmp_path), "--model", "openai/gpt-6-luna",
            "--max-usd", "1", "--max-seconds", "10",
            "--prompt-rate", "0.000001", "--completion-rate", "0.000001",
        ])
    with pytest.raises(SystemExit):
        runner.main([
            "run", str(tmp_path), "--model", "openai/gpt-6-luna",
            "--max-usd", "0", "--max-seconds", "10",
            "--prompt-rate", "0.000001", "--completion-rate", "0.000001",
            "--confirm-live",
        ])
