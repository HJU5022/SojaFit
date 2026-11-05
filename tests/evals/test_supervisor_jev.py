"""Jev 수퍼바이저 평가기의 계약과 오프라인 실행 경계를 검사한다."""

import json
from copy import deepcopy
from pathlib import Path

import pytest

from evals.runners import run_supervisor_jev as jev


ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evals/dataset_v2.jsonl"
FROZEN = ROOT / "evals/FROZEN.json"


def response_payload(**choices):
    return {
        "id": "decision-1",
        "model": "typesafe/jev-1.14",
        "provider": "Typesafe",
        "answers": {
            key: {
                "type": "choice",
                "choice": value,
                "confidence": 0.9,
                "probabilities": {value: 0.9},
            }
            for key, value in choices.items()
        },
        "usage": {"input_tokens": 120, "output_tokens": 0, "cost": 0.00000504},
    }


def valid_response_payload():
    return response_payload(
        question_type="candidate_judge",
        needs_circuit="yes",
        needs_datasheet="yes",
        needs_approved_case="no",
        next_action="search_agent",
    )


def test_manifest_has_one_pinned_jev_job_per_frozen_case():
    manifest = jev.create_manifest(DATASET, FROZEN)

    assert manifest["model"] == "typesafe/jev-1.14"
    assert manifest["dataset_count"] == 70
    assert len(manifest["jobs"]) == 70
    assert {job["run_index"] for job in manifest["jobs"]} == {1}
    assert len({job["case_id"] for job in manifest["jobs"]}) == 70


def test_stage2_manifest_and_summary_use_only_run_index_two():
    manifest = jev.create_manifest(DATASET, FROZEN, run_index=2)
    assert manifest["run_index"] == 2
    assert {job["run_index"] for job in manifest["jobs"]} == {2}
    assert len(manifest["jobs"]) == 70

    items = {"q1": {"question_type": "candidate_judge"}}
    rows = [
        {"case_id": "q1", "run_index": 1, "status": "complete", "decision": {"question_type": "rating"}, "reported_cost_sum": 0.99},
        {"case_id": "q1", "run_index": 2, "status": "error", "error_type": "RuntimeError", "retry_count": 0, "budget_accounted_cost": 0.001},
        {"case_id": "q1", "run_index": 2, "status": "complete", "decision": {"question_type": "candidate_judge"}, "reported_cost_sum": 0.002, "budget_accounted_cost": 0.002},
    ]
    summary = jev.summarize(rows, items, run_index=2)
    assert summary["Question Type Accuracy"] == {
        "numerator": 1, "denominator": 1, "value": 1.0, "scored_unique_cases": 1,
    }
    assert summary["Completion Rate"]["numerator"] == 1
    assert summary["Reported Cost Sum"] == pytest.approx(0.002)
    assert summary["Budget-Accounted Cost"] == pytest.approx(0.003)
    assert summary["Raw Calls"] == 2


def test_stage2_plan_creates_only_second_run_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(jev, "live_preflight", lambda: pytest.fail("network called"))
    output = tmp_path / "jev-stage2"
    assert jev.main(["plan", str(output), "--run-index", "2"]) == 0
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert {job["run_index"] for job in manifest["jobs"]} == {2}
    assert not (output / "smoke.json").exists()
    assert not (output / "rows.json").exists()


def test_stage2_run_all_uses_service_and_writes_second_run_only(tmp_path, monkeypatch):
    output = tmp_path / "jev-stage2"
    assert jev.main(["plan", str(output), "--run-index", "2"]) == 0
    (output / "smoke.json").write_text(json.dumps({
        "status": "complete", "actual_model": jev.MODEL_ID, "provider": "TypeSafe",
    }), encoding="utf-8")
    calls = []

    def fake_service(body, *, timeout):
        calls.append((body, timeout))
        payload = valid_response_payload()
        payload["provider"] = "TypeSafe"
        return payload

    monkeypatch.setattr(jev.llm, "evaluation_decision", fake_service)
    result = jev.run_all(output, max_usd=0.01, input_price_per_token=0.0, timeout=45)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert result["status"] == "complete"
    assert len(result["rows"]) == len(calls) == 70
    assert {row["run_index"] for row in result["rows"]} == {2}
    assert all(body["provider"]["only"] == ["TypeSafe"] for body, _ in calls)
    assert summary["Completion Rate"]["numerator"] == 70
    assert summary["Question Type Accuracy"]["denominator"] == 35


def test_jev_decision_call_uses_service_and_rejects_provider_change(monkeypatch):
    seen = []

    def fake_service(body, *, timeout):
        seen.append((body, timeout))
        payload = valid_response_payload()
        payload["provider"] = "OtherProvider"
        return payload

    monkeypatch.setattr(jev.llm, "evaluation_decision", fake_service)
    with pytest.raises(jev.JevProviderMismatch):
        jev._decision_call("TypeSafe", 45)("질문")
    assert seen[0][0]["provider"]["only"] == ["TypeSafe"]
    assert seen[0][1] == 45


def test_manifest_provider_policy_change_fails_before_live_call(tmp_path):
    manifest = jev.create_manifest(DATASET, FROZEN, run_index=2)
    manifest["provider_policy"]["zdr"] = False
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="provider_policy"):
        jev._load_live_context(tmp_path)


def test_request_contains_only_user_input_and_fixed_contract():
    item = json.loads(DATASET.read_text(encoding="utf-8").splitlines()[0])

    request = jev.build_request(item["input"])

    encoded = json.dumps(request, ensure_ascii=False)
    assert request["state"] == {"user_input": item["input"]}
    assert item["expected"] not in encoded
    assert item["why"] not in encoded
    assert "gold_chunks" not in encoded
    assert set(request["questions"]) == {
        "question_type",
        "needs_circuit",
        "needs_datasheet",
        "needs_approved_case",
        "next_action",
    }
    assert request["provider"] == {
        "zdr": True,
        "data_collection": "deny",
        "allow_fallbacks": False,
    }


def test_parse_maps_five_answers_to_existing_supervisor_shape():
    decision, evidence = jev.parse_decision_response(valid_response_payload())

    assert decision == {
        "question_type": "candidate_judge",
        "required_evidence": ["circuit", "datasheet"],
        "next_action": "search_agent",
        "reason_code": "CANDIDATE_JUDGE",
    }
    assert evidence["question_type"]["confidence"] == 0.9


@pytest.mark.parametrize(
    ("mutation", "key", "value"),
    [
        ("missing_answer", "needs_datasheet", None),
        ("bad_question_type", "question_type", "unknown"),
        ("bad_yes_no", "needs_circuit", "maybe"),
        ("bad_action", "next_action", "unknown_agent"),
        ("missing_confidence", "question_type", None),
    ],
)
def test_parse_rejects_incomplete_or_unknown_typed_answers(mutation, key, value):
    payload = deepcopy(valid_response_payload())
    if mutation == "missing_answer":
        del payload["answers"][key]
    elif mutation == "missing_confidence":
        del payload["answers"][key]["confidence"]
    else:
        payload["answers"][key]["choice"] = value

    with pytest.raises(jev.JevFormatError):
        jev.parse_decision_response(payload)


def test_run_job_retries_only_format_failures_three_times():
    calls = 0

    def invalid(_user_input):
        nonlocal calls
        calls += 1
        raise jev.JevFormatError("invalid")

    job = {"model_id": jev.MODEL_ID, "case_id": "q1", "run_index": 1}
    item = {"id": "q1", "input": "질문"}

    row = jev.run_job(job, item, call=invalid, clock=lambda: 1.0)

    assert calls == 3
    assert row["error_type"] == "ValidationError"
    assert row["retry_count"] == 2


def test_run_job_counts_cost_of_all_schema_attempts():
    calls = 0

    def answer(_user_input):
        nonlocal calls
        calls += 1
        payload = valid_response_payload()
        payload["usage"]["cost"] = 0.001
        if calls == 1:
            payload["answers"].pop("question_type")
        return payload

    row = jev.run_job(
        {"model_id": jev.MODEL_ID, "case_id": "q1", "run_index": 2},
        {"id": "q1", "input": "질문"}, call=answer, clock=lambda: 1.0,
    )
    assert row["status"] == "complete"
    assert row["retry_count"] == 1
    assert row["reported_cost_sum"] == pytest.approx(0.002)


def test_run_job_sanitizes_external_error_text():
    def fail(_user_input):
        raise RuntimeError("sk-secret private question")

    job = {"model_id": jev.MODEL_ID, "case_id": "q1", "run_index": 1}
    row = jev.run_job(job, {"id": "q1", "input": "private"}, call=fail, clock=lambda: 1.0)

    encoded = json.dumps(row)
    assert row["error_type"] == "RuntimeError"
    assert "sk-secret" not in encoded and "private" not in encoded


def test_summary_uses_35_gold_cases_and_70_completion_cases():
    items = jev.load_frozen_dataset(DATASET, FROZEN)
    rows = []
    for item in items:
        question_type = item.get("question_type") or "out_of_scope"
        rows.append({
            "model_id": jev.MODEL_ID,
            "case_id": item["id"],
            "run_index": 1,
            "status": "complete",
            "decision": {
                "question_type": question_type,
                "required_evidence": [],
                "next_action": "refuse",
                "reason_code": question_type.upper(),
            },
            "usage": {"input_tokens": 1, "output_tokens": 0, "cost": 0.0},
            "latency_seconds": 0.1,
        })

    summary = jev.summarize(rows, {item["id"]: item for item in items})

    assert summary["Question Type Accuracy"]["denominator"] == 35
    assert summary["Completion Rate"]["denominator"] == 70
    assert summary["Schema Valid Rate"]["denominator"] == 70


def test_live_commands_fail_before_network_without_confirmation(monkeypatch, tmp_path):
    called = False

    def unexpected_preflight(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(jev, "live_preflight", unexpected_preflight)

    with pytest.raises(SystemExit):
        jev.main(["smoke", str(tmp_path), "--max-usd", "0.01"])

    assert called is False


def test_execute_jobs_saves_each_result_and_stops_before_budget(tmp_path):
    jobs = [
        {"model_id": jev.MODEL_ID, "case_id": f"q{i}", "run_index": 1}
        for i in range(3)
    ]
    items = {f"q{i}": {"id": f"q{i}", "input": "short"} for i in range(3)}
    calls = 0

    def call(_user_input):
        nonlocal calls
        calls += 1
        payload = valid_response_payload()
        payload["usage"]["cost"] = 0.006
        return payload

    output = tmp_path / "rows.json"
    result = jev.execute_jobs(
        jobs,
        items,
        output,
        call=call,
        max_usd=0.01,
        input_price_per_token=0.0,
    )

    assert result["status"] == "budget_stopped"
    assert calls == 2
    assert json.loads(output.read_text(encoding="utf-8")) == result


def test_execute_jobs_reserves_three_format_attempts_before_call(tmp_path):
    job = {"model_id": jev.MODEL_ID, "case_id": "q1", "run_index": 1}

    def must_not_call(_user_input):
        pytest.fail("budget reservation must stop before network")

    result = jev.execute_jobs(
        [job],
        {"q1": {"id": "q1", "input": "1234567890"}},
        tmp_path / "rows.json",
        call=must_not_call,
        max_usd=0.01,
        input_price_per_token=0.001,
    )

    assert result["status"] == "budget_stopped"
    assert result["rows"] == []


def test_execute_jobs_accounts_for_failed_call_without_reported_cost(tmp_path):
    jobs = [{"model_id": jev.MODEL_ID, "case_id": f"q{i}", "run_index": 2} for i in range(2)]
    items = {f"q{i}": {"id": f"q{i}", "input": "short"} for i in range(2)}
    calls = 0

    def fail(_user_input):
        nonlocal calls
        calls += 1
        raise RuntimeError("provider unavailable")

    request_bytes = json.dumps(jev.build_request("short"), ensure_ascii=False).encode("utf-8")
    reservation = max(1, len(request_bytes) // 2) * 0.000001 * 3
    result = jev.execute_jobs(
        jobs, items, tmp_path / "rows.json", call=fail,
        max_usd=reservation * 1.5, input_price_per_token=0.000001,
    )
    assert result["status"] == "budget_stopped"
    assert calls == 1
    assert result["rows"][0]["budget_accounted_cost"] > 0


def test_execute_jobs_stops_when_process_time_limit_is_reached(tmp_path):
    jobs = [{"model_id": jev.MODEL_ID, "case_id": "q1", "run_index": 2}]
    result = jev.execute_jobs(
        jobs, {"q1": {"id": "q1", "input": "short"}}, tmp_path / "rows.json",
        call=lambda _: pytest.fail("time limit must stop before network"),
        max_usd=0.01, input_price_per_token=0.0, max_seconds=1.0,
        clock=iter((0.0, 1.0)).__next__,
    )
    assert result["status"] == "time_stopped"
    assert result["rows"] == []


def test_execute_jobs_stops_only_after_three_provider_failures(tmp_path):
    jobs = [{"model_id": jev.MODEL_ID, "case_id": f"q{i}", "run_index": 2} for i in range(4)]
    items = {f"q{i}": {"id": f"q{i}", "input": "short"} for i in range(4)}
    calls = 0

    def fail(_user_input):
        nonlocal calls
        calls += 1
        raise RuntimeError("provider unavailable")

    result = jev.execute_jobs(
        jobs, items, tmp_path / "rows.json", call=fail,
        max_usd=1.0, input_price_per_token=0.0,
    )
    assert result["status"] == "provider_stopped"
    assert calls == 3
    assert len(result["rows"]) == 3


def test_execute_jobs_stops_immediately_on_model_provider_mismatch(tmp_path):
    jobs = [{"model_id": jev.MODEL_ID, "case_id": f"q{i}", "run_index": 2} for i in range(2)]
    items = {f"q{i}": {"id": f"q{i}", "input": "short"} for i in range(2)}
    calls = 0

    def changed(_user_input):
        nonlocal calls
        calls += 1
        raise jev.JevProviderMismatch({"model": "another-model", "provider": "Other", "usage": {"cost": 0.001}})

    result = jev.execute_jobs(
        jobs, items, tmp_path / "rows.json", call=changed,
        max_usd=1.0, input_price_per_token=0.0,
    )
    assert result["status"] == "provider_stopped"
    assert calls == 1
    assert result["rows"][0]["error_type"] == "JevProviderMismatch"


def test_plan_creates_manifest_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(jev, "live_preflight", lambda: pytest.fail("network called"))
    output = tmp_path / "jev-plan"

    assert jev.main(["plan", str(output)]) == 0

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["model"] == "typesafe/jev-1.14"
    assert len(manifest["jobs"]) == 70
    assert list(output.iterdir()) == [output / "manifest.json"]


def test_live_preflight_queries_decisions_catalog_and_zdr_filter():
    filters = []

    def catalog_get(*, zdr):
        filters.append(zdr)
        return [{"id": jev.MODEL_ID, "pricing": {"prompt": "0.000000042"}}]

    result = jev.live_preflight(catalog_get=catalog_get)

    assert result["catalog"]["id"] == jev.MODEL_ID
    assert filters == [False, True]


@pytest.mark.parametrize(
    ("actual_model", "matches"),
    [
        ("typesafe/jev-1.14", True),
        ("typesafe/jev-1.14-20261014", True),
        ("typesafe/jev-1.13-20260917", False),
        ("typesafe/jev-1.140-20261014", False),
    ],
)
def test_pinned_model_accepts_only_jev_1_14_canonical_snapshot(actual_model, matches):
    assert jev.matches_requested_model(actual_model) is matches
