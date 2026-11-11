import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.runners import import_supervisor_prompt_v0_langfuse as subject


def test_build_plan_has_fixed_scope_and_no_gold_in_input():
    plan = subject.build_import_plan()

    assert plan["dataset_name"] == "sojafit-supervisor-v0"
    assert plan["dataset_item_count"] == 13
    assert plan["experiment_count"] == 3
    assert plan["score_count"] == 13 * 3 * 7
    assert set(plan["score_names"]) == set(subject.SCORE_NAMES)
    for item in plan["dataset_items"]:
        assert set(item["input"]) == {
            "user_request",
            "current_state",
            "external_material",
        }
        assert "gold" not in item["input"]


def test_dataset_item_ids_are_stable_and_unique():
    first = subject.build_import_plan()["dataset_items"]
    second = subject.build_import_plan()["dataset_items"]

    assert [item["id"] for item in first] == [item["id"] for item in second]
    assert len({item["id"] for item in first}) == 13


def test_evaluate_result_returns_seven_deterministic_scores():
    expected = {
        "question_type": "candidate_search",
        "required_evidence": ["circuit_context"],
        "next_action": "retrieve_candidates",
        "reason_code": "READY_FOR_CANDIDATE_SEARCH",
    }
    output = {
        "status": "complete",
        "decision": dict(expected),
        "semantic_errors": [],
    }

    scores = subject.evaluate_result(output=output, expected_output=expected)

    assert [score["name"] for score in scores] == list(subject.SCORE_NAMES)
    assert all(score["value"] == 1 for score in scores)

    output["decision"]["next_action"] = "refuse"
    output["semantic_errors"] = ["invalid transition"]
    scores = {score["name"]: score["value"] for score in subject.evaluate_result(
        output=output, expected_output=expected
    )}
    assert scores["schema_valid"] == 1
    assert scores["next_action_correct"] == 0
    assert scores["semantic_valid"] == 0
    assert scores["exact_decision_match"] == 0


def test_hash_mismatch_stops_before_any_client_write(tmp_path: Path):
    source = subject.RESULT_ROOT / "chat" / "rows_openai__gpt-6-luna.json"
    changed = json.loads(source.read_text(encoding="utf-8"))
    changed["dataset_sha256"] = "wrong"
    bad = tmp_path / "rows.json"
    bad.write_text(json.dumps(changed), encoding="utf-8")

    runs = list(subject.MODEL_RUNS)
    runs[0] = {**runs[0], "path": bad}
    with pytest.raises(ValueError, match="dataset hash mismatch"):
        subject.build_import_plan(model_runs=tuple(runs))


def test_existing_receipt_blocks_external_write(tmp_path: Path):
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError, match="receipt already exists"):
        subject.ensure_import_not_already_recorded(receipt)


def test_langfuse_base_url_is_normalized_for_otel(monkeypatch):
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com/")

    subject.normalize_langfuse_base_url()

    assert subject.os.environ["LANGFUSE_BASE_URL"] == "https://cloud.langfuse.com"


def test_import_uses_saved_rows_and_creates_three_experiments():
    plan = subject.build_import_plan()
    items = [
        SimpleNamespace(metadata=payload["metadata"])
        for payload in plan["dataset_items"]
    ]
    dataset = SimpleNamespace(
        id="dataset-id",
        metadata={"dataset_sha256": plan["dataset_sha256"]},
        items=items,
    )

    class FakeClient:
        def __init__(self):
            self.item_writes = []
            self.experiment_writes = []

        def get_dataset(self, _name):
            return dataset

        def create_dataset_item(self, **kwargs):
            self.item_writes.append(kwargs)

        def create_trace_id(self, *, seed):
            return f"trace:{seed}"

        def run_experiment(self, **kwargs):
            self.experiment_writes.append(kwargs)
            outputs = [kwargs["task"](item=item) for item in kwargs["data"]]
            assert all("response_id" not in output for output in outputs)
            return SimpleNamespace(
                run_name=kwargs["run_name"],
                experiment_id=kwargs["experiment_id"],
                experiment_url=f"https://example.test/{kwargs['run_name']}",
                item_results=[
                    SimpleNamespace(evaluations=[None] * len(subject.SCORE_NAMES))
                    for _output in outputs
                ],
            )

        def flush(self):
            return None

    client = FakeClient()
    receipt = subject.import_results(plan, client=client)

    assert len(client.item_writes) == 13
    assert len(client.experiment_writes) == 3
    assert all(call["max_concurrency"] == 1 for call in client.experiment_writes)
    assert all(call["metadata"]["imported_existing_result"] == "true" for call in client.experiment_writes)
    assert receipt["model_calls_performed"] == 0
    assert receipt["score_count"] == 273
