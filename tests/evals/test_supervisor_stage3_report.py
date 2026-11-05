"""3차 재집계의 gold 분모·라우팅 오류·3회 비교 범위를 검증한다."""

import json
from pathlib import Path

import pytest

from evals.runners import report_supervisor_stage3 as report


def row(case, run=3, kind="rating", action="search_agent", status="complete"):
    return {"model_id": "test/model", "case_id": case, "run_index": run,
            "status": status, "decision": {"question_type": kind, "next_action": action,
                                           "required_evidence": [], "reason_code": kind.upper()},
            "latency_seconds": 1, "retry_count": 0, "usage": {"cost": .001}}


def test_run_metrics_keep_gold_format_and_routing_denominators_separate():
    items = {"q1": {"question_type": "rating"}, "q2": {"question_type": "role"}, "q3": {"question_type": None}}
    failed = row("q2", status="error")
    failed["error_type"] = "ValidationError"
    result = {"status": "complete_with_errors", "rows": [row("q1"), failed, row("q3", kind="out_of_scope")],
              "budget_progress": {"cumulative_raw_calls": 5, "cumulative_reserved_usd": .006}}
    metrics = report.summarize_run(result, items, "test/model", 3)
    assert metrics["Completion Rate"] == report.rate(3, 3)
    assert metrics["Schema Valid Rate"] == report.rate(2, 3)
    assert metrics["Question Type Accuracy"] == report.rate(1, 2)
    assert metrics["Routing Consistency"]["Inconsistent Action"] == report.rate(1, 1)
    assert metrics["Routing Consistency"]["inconsistent_case_actions"] == {"q3": "search_agent"}
    assert metrics["Raw Calls"] == 5
    assert metrics["Budget-Accounted Cost"] == .006


def test_agreement_and_flips_exclude_incomplete_cases_and_show_coverage():
    items = {"q1": {"question_type": "rating"}, "q2": {"question_type": "rating"}}
    results = [{"rows": [row("q1", run=run, action="search_agent" if run < 3 else "refuse"),
                         row("q2", run=run, status="error" if run == 1 else "complete")]}
               for run in (1, 2, 3)]
    comparison = report.compare_runs(results, items, "test/model")
    assert comparison["Comparable Three-Run Cases"] == report.rate(1, 2)
    assert comparison["Three-Run Exact Agreement"] == report.rate(0, 1)
    assert comparison["Question Type Flip Rate"] == report.rate(0, 1)
    assert comparison["Next Action Flip Rate"] == report.rate(1, 1)
    assert comparison["incomplete_case_ids"] == ["q2"]


@pytest.mark.parametrize("field,value", [("model_id", "other/model"), ("case_id", "unknown"), ("run_index", 2)])
def test_mixed_source_rows_are_rejected(field, value):
    entry = row("q1")
    entry[field] = value
    with pytest.raises(ValueError, match="불일치"):
        report.summarize_run({"rows": [entry]}, {"q1": {"question_type": "rating"}}, "test/model", 3)


def test_stage2_jev_recalculation_matches_recorded_findings():
    root = Path(__file__).resolve().parents[2]
    items = {item["id"]: item for item in (json.loads(line) for line in
             (root / "evals/dataset_v2.jsonl").read_text(encoding="utf-8").splitlines())}
    result = json.loads((root / "evals/results/supervisor/2026-11-05-jev-stage2-v1/rows.json").read_text(encoding="utf-8"))
    metrics = report.summarize_run(result, items, "typesafe/jev-1.14", 2)
    assert metrics["Schema Valid Rate"] == report.rate(70, 70)
    assert metrics["Question Type Accuracy"] == report.rate(33, 35)
    assert metrics["Routing Consistency"]["Inconsistent Action"] == report.rate(4, 6)
    assert metrics["Reported Cost Sum"] == pytest.approx(.002689092)


def test_all_stage2_metrics_match_previous_corrected_summary():
    root = Path(__file__).resolve().parents[2]
    items = {item["id"]: item for item in (json.loads(line) for line in
             (root / "evals/dataset_v2.jsonl").read_text(encoding="utf-8").splitlines())}
    reference = json.loads((root / "evals/results/supervisor/2026-11-05-stage2-comparison-v1/stage2_summary_v2.json").read_text(encoding="utf-8"))
    for expected in reference["models"]:
        model = expected["model_id"]
        directory = report.JEV_DIRS[1] if model == report.MODELS[-1] else report.FIVE_DIRS[1]
        name = "rows.json" if model == report.MODELS[-1] else f"rows_{model.replace('/', '__')}.json"
        raw = json.loads((root / "evals/results/supervisor" / directory / name).read_text(encoding="utf-8"))
        metrics = report.summarize_run(raw, items, model, 2)
        for measured, previous in (
            ("Question Type Macro-F1", "question_type_macro_f1"), ("Raw Calls", "raw_calls"),
            ("Reported Cost Sum", "reported_cost_sum_from_saved_rows"),
            ("Budget-Accounted Cost", "budget_accounted_cost"), ("p95 Latency", "p95_latency_seconds"),
        ):
            assert metrics[measured] == pytest.approx(expected[previous])


def test_stage3_deepseek_diagnostic_matches_length_limited_failures():
    root = Path(__file__).resolve().parents[2]
    items = {item["id"]: item for item in (json.loads(line) for line in
             (root / "evals/dataset_v2.jsonl").read_text(encoding="utf-8").splitlines())}
    raw = json.loads((root / "evals/results/supervisor/2026-11-05-stage3-five-v1/rows_deepseek__deepseek-v4.1-flash.json").read_text(encoding="utf-8"))
    metrics = report.summarize_run(raw, items, "deepseek/deepseek-v4.1-flash", 3)
    diagnosis = metrics["Output Limit Diagnostics"]
    assert diagnosis["Length-Limited Validation Failures"] == report.rate(63, 63)
    assert diagnosis["labeled_validation_failure_count"] == 33
    assert diagnosis["validation_attempt_usage_records"] == 189
    assert diagnosis["validation_attempts_at_256_tokens"] == 189


def test_source_hash_policy_handles_checkout_line_endings(tmp_path):
    old = tmp_path / report.FIVE_DIRS[1] / "rows.json"
    new = tmp_path / report.FIVE_DIRS[2] / "rows.json"
    for path in (old, new):
        path.parent.mkdir(parents=True)
        path.write_bytes(b"{}\r\n")
    old_digest = report.source_digest(old)
    new_digest = report.source_digest(new)
    old.write_bytes(b"{}\n")
    new.write_bytes(b"{}\n")
    assert report.source_digest(old) == old_digest
    assert report.source_digest(new) != new_digest


def test_report_marks_partial_run_accuracy_and_schema_as_not_comparable(tmp_path):
    root = Path(__file__).resolve().parents[2]
    source = root / "evals/results/supervisor/2026-11-05-stage3-comparison-v1/stage3_summary.json"
    summary = json.loads(source.read_text(encoding="utf-8"))
    output = tmp_path / "summary.json"
    output.write_bytes(source.read_bytes())
    (tmp_path / "docs/research").mkdir(parents=True)

    report.render_reports(summary, output, tmp_path)

    text = (tmp_path / "docs/research/supervisor-stage3-results.md").read_text(encoding="utf-8")
    section = text.split("## 1·2·3차 점수 대조")[1]
    line = next(line for line in section.splitlines() if line.startswith("| `deepseek/deepseek-v4.1-flash`"))
    assert line.count("Not Comparable (3/70 attempted, 0 valid)") == 2
    assert "| 0/70 |" not in line
    assert "| 62/70 | 7/70 |" in line
