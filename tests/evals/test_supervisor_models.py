"""수퍼바이저 후보 비교 실행기의 계획·안전 조건·부분 저장을 API 없이 검사한다."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.runners import run_supervisor_models as supervisor


def test_build_plan_contains_all_1050_unique_jobs():
    """후보·문항·반복 중 하나를 빠뜨리거나 중복하면 1,050개 고유 job 계약이 깨진다."""
    items = [{"id": f"q{i:02d}"} for i in range(70)]

    jobs = supervisor.build_plan(items)

    assert len(jobs) == 1050
    assert len({(job["model_id"], job["case_id"], job["run_index"]) for job in jobs}) == 1050
    assert {job["model_id"] for job in jobs} == {
        "anthropic/claude-haiku-5.5",
        "openai/gpt-6-luna",
        "deepseek/deepseek-v4.1-flash",
        "meta/muse-glimmer-30b",
        "cohere/command-a-plus",
    }
    assert {job["run_index"] for job in jobs} == {1, 2, 3}


def test_load_dataset_rejects_changed_frozen_file(tmp_path):
    """동결 파일 내용이나 건수가 바뀌면 유료 실행 계획을 만들기 전에 중단해야 한다."""
    dataset = tmp_path / "dataset_v2.jsonl"
    dataset.write_text('{"id":"q1"}\n', encoding="utf-8")
    frozen = tmp_path / "FROZEN.json"
    frozen.write_text(json.dumps({"dataset_v2.jsonl": {"sha256": "0" * 64, "count": 70}}), encoding="utf-8")

    with pytest.raises(ValueError, match="동결 평가셋 해시 불일치"):
        supervisor.load_frozen_dataset(dataset, frozen)


def test_provider_policy_fails_closed_without_fallback():
    """평가 요청이 ZDR·data collection deny·fallback 금지를 빠뜨리면 개인정보 계약이 깨진다."""
    assert supervisor.PROVIDER_POLICY == {
        "zdr": True,
        "data_collection": "deny",
        "allow_fallbacks": False,
        "require_parameters": True,
    }


def test_pending_jobs_skips_terminal_output_errors_but_retries_budget_stop():
    """schema 실패는 확정하고, 예산 차단·rate limit처럼 재개 가능한 job은 남겨야 한다."""
    plan = [
        {"model_id": "m", "case_id": "q1", "run_index": 1},
        {"model_id": "m", "case_id": "q1", "run_index": 2},
        {"model_id": "m", "case_id": "q1", "run_index": 3},
        {"model_id": "m", "case_id": "q2", "run_index": 1},
    ]
    rows = [
        {**plan[0], "status": "complete"},
        {**plan[1], "status": "error", "error_type": "ValidationError"},
        {**plan[2], "status": "error", "error_type": "EvaluationLimitError"},
        {**plan[3], "status": "error", "error_type": "RateLimitError"},
    ]

    assert supervisor.pending_jobs(plan, rows) == [plan[2], plan[3]]


def test_run_job_retries_format_and_never_sends_gold():
    """schema 오류만 두 번 재시도하고 gold·expected는 모델 입력에 보내지 않아야 한다."""
    calls = []

    def fake_call(model, system, user, schema, **kwargs):
        calls.append((model, system, user, kwargs))
        assert "SECRET_GOLD" not in user
        if len(calls) < 3:
            schema.model_validate({})
        return schema(
            question_type="rating",
            required_evidence=["datasheet"],
            next_action="search_agent",
            reason_code="RATING",
        ), {"response_id": "r3", "finish_reason": "stop", "usage": {"total_tokens": 20}}

    item = {"id": "q1", "input": "질문: 1N5817 정격은?", "expected": "SECRET_GOLD", "gold_chunks": ["SECRET_GOLD"]}
    job = {"model_id": "openai/gpt-6-luna", "case_id": "q1", "run_index": 1}

    row = supervisor.run_job(job, item, call=fake_call, clock=lambda: 10.0)

    assert row["status"] == "complete" and row["retry_count"] == 2
    assert row["decision"] == {
        "question_type": "rating",
        "required_evidence": ["datasheet"],
        "next_action": "search_agent",
        "reason_code": "RATING",
    }
    assert row["usage"] == {"total_tokens": 20}
    assert all(call[2] == item["input"] for call in calls)


def test_run_job_sanitizes_external_error():
    """provider 오류 원문에 키나 입력이 있어도 결과에는 예외 종류만 남겨야 한다."""
    def fail(*args, **kwargs):
        raise RuntimeError("sk-secret question text")

    job = {"model_id": "openai/gpt-6-luna", "case_id": "q1", "run_index": 1}
    row = supervisor.run_job(job, {"id": "q1", "input": "private"}, call=fail, clock=lambda: 1.0)

    assert row["status"] == "error" and row["error_type"] == "RuntimeError"
    assert "sk-secret" not in json.dumps(row) and "private" not in json.dumps(row)


def test_create_manifest_uses_frozen_v2_without_gold_content():
    """manifest는 동결 v2의 hash·70건·1,050 job만 담고 정답 본문을 복제하지 않아야 한다."""
    root = Path(__file__).resolve().parents[2]

    manifest = supervisor.create_manifest(root / "evals/dataset_v2.jsonl", root / "evals/FROZEN.json")

    assert manifest["dataset_count"] == 70 and len(manifest["jobs"]) == 1050
    assert manifest["dataset_sha256"] == "81582c59ef47fdfa7b3b9dc4af7e882c0b140a450fa6bc060a14ed8146bb09a9"
    assert set(manifest["code_sha256"]) == {
        "backend/services/llm.py", "evals/runners/run_supervisor_models.py",
    }
    assert all(len(value) == 64 for value in manifest["code_sha256"].values())
    encoded = json.dumps(manifest, ensure_ascii=False)
    assert '"expected"' not in encoded and '"gold_chunks"' not in encoded


def test_execute_jobs_saves_partial_rows_and_stops_on_budget(tmp_path):
    """각 job 뒤 결과를 저장하고 예산 상한이면 다음 job을 호출하지 않아야 한다."""
    jobs = [
        {"model_id": "openai/gpt-6-luna", "case_id": f"q{i}", "run_index": 1}
        for i in range(3)
    ]
    items = {f"q{i}": {"id": f"q{i}", "input": f"question {i}"} for i in range(3)}
    calls = []

    def fake_call(model, system, user, schema, **kwargs):
        calls.append(user)
        if len(calls) == 2:
            from backend.services.llm import EvaluationLimitError
            raise EvaluationLimitError("private budget detail")
        return schema(question_type="rating", required_evidence=["datasheet"],
                      next_action="search_agent", reason_code="RATING"), {"usage": None}

    output = tmp_path / "rows.json"
    result = supervisor.execute_jobs(jobs, items, output, call=fake_call)

    assert result["status"] == "budget_stopped" and len(result["rows"]) == 2
    assert len(calls) == 2
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved == result and "private budget detail" not in output.read_text(encoding="utf-8")


def test_execute_jobs_keeps_schema_error_terminal_on_resume(tmp_path):
    """이미 세 번 schema 실패한 key를 재개 때 다시 호출하지 않고 실패 측정값으로 남겨야 한다."""
    job = {"model_id": "openai/gpt-6-luna", "case_id": "q1", "run_index": 1}
    output = tmp_path / "rows.json"
    output.write_text(json.dumps({"status": "incomplete", "rows": [{**job, "status": "error", "error_type": "ValidationError"}]}),
                      encoding="utf-8")

    def must_not_call(*args, **kwargs):
        pytest.fail("terminal schema error must not be retried")

    result = supervisor.execute_jobs([job], {"q1": {"id": "q1", "input": "q"}}, output, call=must_not_call)

    assert result["status"] == "complete_with_errors"
    assert [row["status"] for row in result["rows"]] == ["error"]


def test_plan_command_writes_new_manifest_and_refuses_overwrite(tmp_path):
    """plan 명령은 API 없이 새 폴더에 manifest를 만들고 기존 실행 폴더를 덮어쓰지 않아야 한다."""
    output = tmp_path / "supervisor-run"

    assert supervisor.main(["plan", str(output)]) == 0
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["dataset_count"] == 70 and len(manifest["jobs"]) == 1050
    with pytest.raises(FileExistsError):
        supervisor.main(["plan", str(output)])


def test_run_model_executes_only_selected_jobs_under_budget(monkeypatch, tmp_path):
    """worker는 고른 full model ID의 job만 실행하고 raw call 수와 예약 비용을 남겨야 한다."""
    root = Path(__file__).resolve().parents[2]
    manifest = supervisor.create_manifest(root / "evals/dataset_v2.jsonl", root / "evals/FROZEN.json")
    model = "openai/gpt-6-luna"
    manifest["jobs"] = [job for job in manifest["jobs"] if job["model_id"] == model][:2]
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    calls = []

    class Usage:
        def model_dump(self):
            return {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "cost": 0.000002}

    def create(**kwargs):
        calls.append(kwargs)
        content = json.dumps({
            "question_type": "rating", "required_evidence": ["datasheet"],
            "next_action": "search_agent", "reason_code": "RATING",
        })
        return SimpleNamespace(id=f"r{len(calls)}", usage=Usage(), choices=[
            SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop"),
        ])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(supervisor.llm, "_evaluation_client", lambda timeout: client)

    result = supervisor.run_model(run_dir, model, max_usd=1.0, prompt_rate=0.0000001,
                                  completion_rate=0.0000005, max_seconds=60)

    assert result["status"] == "complete" and len(result["rows"]) == 2
    assert len(calls) == 2 and {row["model_id"] for row in result["rows"]} == {model}
    assert calls[0]["extra_body"]["provider"]["max_price"] == {"prompt": 0.1, "completion": 0.5}
    assert result["budget"]["cumulative_raw_calls"] == 2
    assert result["budget"]["cumulative_reserved_usd"] > 0
    assert result["summary"]["Question Type Accuracy"]["scored_unique_cases"] == 35


def test_run_model_can_limit_execution_to_first_run_index(monkeypatch, tmp_path):
    """1차 선별 실행이 run 2·3 job을 호출하면 단계별 비용 절감 계약이 깨진다."""
    root = Path(__file__).resolve().parents[2]
    model = "openai/gpt-6-luna"
    manifest = supervisor.create_manifest(root / "evals/dataset_v2.jsonl", root / "evals/FROZEN.json")
    manifest["jobs"] = [job for job in manifest["jobs"] if job["model_id"] == model][:2]
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    calls = []

    class Usage:
        def model_dump(self):
            return {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "cost": 0.000002}

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            id="r1", model=model, provider="Azure", usage=Usage(),
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
                "question_type": "rating", "required_evidence": ["datasheet"],
                "next_action": "search_agent", "reason_code": "RATING",
            })), finish_reason="stop")],
        )

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(supervisor.llm, "_evaluation_client", lambda timeout: client)

    result = supervisor.run_model(
        run_dir, model, max_usd=1.0, prompt_rate=0.0000001,
        completion_rate=0.0000005, max_seconds=60, run_indices=(1,),
    )

    assert len(calls) == 1
    assert [(row["case_id"], row["run_index"]) for row in result["rows"]] == [("draft30-e01", 1)]


def test_build_pairwise_and_robustness_plans_are_complete_and_deterministic():
    """추가 비교 계획은 API 없이 1,400 pairwise 판정과 70개 의미 보존 변형을 고정해야 한다."""
    items = [{"id": f"q{i:02d}", "input": f" part: 1N5817  voltage: {i}V "} for i in range(70)]

    pairwise = supervisor.build_pairwise_plan(items)
    robustness = supervisor.build_robustness_plan(items)

    assert len(pairwise) == 1400
    assert len({(row["case_id"], row["model_a"], row["model_b"], row["position"]) for row in pairwise}) == 1400
    assert {row["position"] for row in pairwise} == {"AB", "BA"}
    assert len(robustness) == 70 and {row["case_id"] for row in robustness} == {item["id"] for item in items}
    assert all("1N5817" in row["perturbed_input"] for row in robustness)
    assert all(row["perturbed_input"].strip() == item["input"].strip()
               for row, item in zip(robustness, items, strict=True))


def test_execute_jobs_stops_after_three_consecutive_provider_errors(tmp_path):
    """같은 provider 장애가 연속되면 나머지 70문항을 소모하지 않고 세 번째에서 멈춰야 한다."""
    jobs = [{"model_id": "openai/gpt-6-luna", "case_id": f"q{i}", "run_index": 1} for i in range(5)]
    items = {f"q{i}": {"id": f"q{i}", "input": "q"} for i in range(5)}
    calls = []

    class NotFoundError(RuntimeError):
        pass

    def fail(*args, **kwargs):
        calls.append(1)
        raise NotFoundError("do not persist")

    result = supervisor.execute_jobs(jobs, items, tmp_path / "rows.json", call=fail)

    assert result["status"] == "provider_stopped"
    assert result["stop_reason"] == {"error_type": "NotFoundError", "consecutive": 3}
    assert len(calls) == 3


def test_run_command_requires_explicit_live_confirmation(monkeypatch, tmp_path):
    """키가 있어도 명시적인 live 확인 없이는 catalog 조회나 유료 호출을 시작하지 않아야 한다."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    monkeypatch.setattr(supervisor, "_catalog_model", lambda *a, **k: pytest.fail("must stop before network"))

    with pytest.raises(SystemExit):
        supervisor.main(["run", str(tmp_path), "--model", "openai/gpt-6-luna", "--max-usd", "1"])


def test_run_model_resume_uses_cumulative_budget(monkeypatch, tmp_path):
    """재개 실행은 앞선 예약 비용과 raw call을 잊지 않고 전체 cap에서 차감해야 한다."""
    root = Path(__file__).resolve().parents[2]
    model = "openai/gpt-6-luna"
    manifest = supervisor.create_manifest(root / "evals/dataset_v2.jsonl", root / "evals/FROZEN.json")
    manifest["jobs"] = [job for job in manifest["jobs"] if job["model_id"] == model][:2]
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    output = run_dir / "rows_openai__gpt-6-luna.json"
    output.write_text(json.dumps({"status": "incomplete", "rows": [], "budget_progress": {
        "cumulative_raw_calls": 2, "cumulative_reserved_usd": 0.2,
    }}), encoding="utf-8")
    monkeypatch.setattr(supervisor.llm, "_evaluation_client",
                        lambda timeout: pytest.fail("budget must stop before client creation"))

    with pytest.raises(supervisor.llm.EvaluationLimitError):
        supervisor.run_model(run_dir, model, max_usd=0.2, prompt_rate=0.0000001,
                             completion_rate=0.0000005, max_seconds=60)


def test_full_run_requires_matching_successful_smoke_before_api(monkeypatch, tmp_path):
    """CLI full run 경로는 같은 manifest의 provider 기록 smoke 없이는 API client를 만들지 않아야 한다."""
    root = Path(__file__).resolve().parents[2]
    manifest = supervisor.create_manifest(root / "evals/dataset_v2.jsonl", root / "evals/FROZEN.json")
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(supervisor.llm, "_evaluation_client",
                        lambda timeout: pytest.fail("smoke gate must stop before API client creation"))

    with pytest.raises(ValueError, match="smoke"):
        supervisor.run_model(run_dir, "openai/gpt-6-luna", max_usd=1,
                             prompt_rate=0.0000001, completion_rate=0.0000005,
                             max_seconds=60, require_smoke=True)


def test_imported_provider_evidence_reuses_verified_call_without_calling_it_smoke(tmp_path):
    """과거 호출 결과는 원본 hash를 검증한 evidence로만 재사용하고 현재 smoke로 위장하지 않아야 한다."""
    root = Path(__file__).resolve().parents[2]
    model = "deepseek/deepseek-v4.1-flash"
    target = tmp_path / "target"
    source = tmp_path / "source"
    target.mkdir()
    source.mkdir()
    target_manifest = supervisor.create_manifest(root / "evals/dataset_v2.jsonl", root / "evals/FROZEN.json")
    source_manifest = {**target_manifest, "code_sha256": {"legacy": "1" * 64}}
    (target / "manifest.json").write_text(json.dumps(target_manifest), encoding="utf-8")
    (source / "manifest.json").write_text(json.dumps(source_manifest), encoding="utf-8")
    source_smoke = source / "smoke_deepseek__deepseek-v4.1-flash.json"
    source_smoke.write_text(json.dumps({
        "status": "complete", "model_id": model, "provider": "Morph", "actual_model": model,
        "manifest_prompt_sha256": source_manifest["prompt_sha256"],
        "manifest_code_sha256": source_manifest["code_sha256"],
    }), encoding="utf-8")

    imported = supervisor.import_provider_evidence(target, source)

    assert imported["models"][model]["provider"] == "Morph"
    assert not (target / "smoke_deepseek__deepseek-v4.1-flash.json").exists()
    assert supervisor.verified_provider(target, model, target_manifest) == "Morph"
    source_smoke.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="evidence 원본 hash 불일치"):
        supervisor.verified_provider(target, model, target_manifest)


def test_run_model_rejects_stale_code_manifest(monkeypatch, tmp_path):
    """plan 뒤 실행기나 LLM 경계가 바뀌면 이전 manifest로 유료 호출을 시작하지 않아야 한다."""
    root = Path(__file__).resolve().parents[2]
    manifest = supervisor.create_manifest(root / "evals/dataset_v2.jsonl", root / "evals/FROZEN.json")
    manifest["code_sha256"]["backend/services/llm.py"] = "0" * 64
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(supervisor.llm, "_evaluation_client",
                        lambda timeout: pytest.fail("stale manifest must fail before API client creation"))

    with pytest.raises(ValueError, match="code hash 불일치"):
        supervisor.run_model(run_dir, "openai/gpt-6-luna", max_usd=1.0,
                             prompt_rate=0.0000001, completion_rate=0.0000005, max_seconds=60)


def test_summarize_separates_labeled_accuracy_stability_and_usage():
    """gold 없는 문항을 accuracy 분모에 넣지 않고 3회 안정성·usage를 별도로 계산해야 한다."""
    items = {
        "labeled": {"id": "labeled", "question_type": "rating"},
        "unlabeled": {"id": "unlabeled", "question_type": ""},
    }
    rows = []
    for run_index in (1, 2, 3):
        rows.append({
            "model_id": "m", "case_id": "labeled", "run_index": run_index, "status": "complete",
            "decision": {"question_type": "rating", "required_evidence": ["datasheet"],
                         "next_action": "search_agent", "reason_code": "RATING"},
            "latency_seconds": float(run_index),
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "cost": 0.001},
        })
        rows.append({
            "model_id": "m", "case_id": "unlabeled", "run_index": run_index, "status": "complete",
            "decision": {"question_type": "out_of_scope", "required_evidence": [],
                         "next_action": "refuse", "reason_code": "OUT"},
            "latency_seconds": float(run_index + 3),
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "cost": 0.001},
        })

    summary = supervisor.summarize(rows, items)

    assert summary["Question Type Accuracy"] == {
        "per_run": {
            "1": {"numerator": 1, "denominator": 1, "value": 1.0},
            "2": {"numerator": 1, "denominator": 1, "value": 1.0},
            "3": {"numerator": 1, "denominator": 1, "value": 1.0},
        },
        "mean": 1.0, "min": 1.0, "max": 1.0, "scored_unique_cases": 1,
    }
    assert summary["Question Type Macro-F1"]["mean"] == 1.0
    assert summary["Known Limitation"] == {
        "unscored_case_count": 1,
        "unscored_case_ids": ["unlabeled"],
        "reason": "question_type gold 없음; 70문항 실행은 유지하되 objective score에서 제외",
    }
    assert summary["Completion Rate"] == {"numerator": 6, "denominator": 6, "value": 1.0}
    assert summary["Three-Run Exact Agreement"] == {"numerator": 2, "denominator": 2, "value": 1.0}
    assert summary["Question Type Flip Rate"] == {"numerator": 0, "denominator": 2, "value": 0.0}
    assert summary["Next Action Flip Rate"] == {"numerator": 0, "denominator": 2, "value": 0.0}
    assert summary["Input Tokens"] == 60 and summary["Output Tokens"] == 12
    assert summary["Actual Total Cost"] == pytest.approx(0.006)
    assert summary["p50 Latency"] == 3.0 and summary["p95 Latency"] == 6.0


def test_summarize_keeps_all_70_style_cases_in_stability_denominator_when_run_missing():
    """한 run이 실패해도 stability 분모에서 문항을 빼 정확도가 부풀어서는 안 된다."""
    items = {"q1": {"id": "q1", "question_type": "rating"}, "q2": {"id": "q2", "question_type": "role"}}
    decision = {"question_type": "rating", "required_evidence": ["datasheet"],
                "next_action": "search_agent", "reason_code": "RATING"}
    rows = [{"model_id": "m", "case_id": "q1", "run_index": run, "status": "complete",
             "decision": decision, "latency_seconds": 1.0, "usage": {}} for run in (1, 2, 3)]
    rows += [{"model_id": "m", "case_id": "q2", "run_index": run, "status": "complete",
              "decision": {**decision, "question_type": "role"}, "latency_seconds": 1.0, "usage": {}}
             for run in (1, 2)]

    summary = supervisor.summarize(rows, items)

    assert summary["Three-Run Exact Agreement"] == {"numerator": 1, "denominator": 2, "value": 0.5}
    assert summary["Incomplete Three-Run Case Count"] == 1
    assert summary["Completion Rate"] == {"numerator": 5, "denominator": 6, "value": 5 / 6}
