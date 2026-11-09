"""Supervisor Prompt V0 세 모델 통합 집계를 API 없이 검증한다."""

import hashlib
import json

import pytest

from evals.runners.compare_supervisor_prompt_v0 import CONTRACT_PATH, compare
from evals.runners.supervisor_prompt_v0_common import DATASET, FROZEN, load_v0_dataset


@pytest.fixture
def complete_result_files(tmp_path):
    paths = []
    modes = {
        "openai/gpt-6-luna": "chat_completions",
        "anthropic/claude-haiku-5.5": "chat_completions",
        "typesafe/jev-1.14": "decisions",
    }
    items = load_v0_dataset(DATASET, FROZEN)
    for index, (model, mode) in enumerate(modes.items()):
        path = tmp_path / f"result-{index}.json"
        rows = []
        for item in items:
            row = {
                "case_id": item["id"],
                "status": "complete",
                "decision": item["gold"],
                "semantic_errors": [],
                "latency_seconds": index + 1,
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "cost": 0.01},
            }
            if mode == "chat_completions":
                row["first_pass_valid"] = True
            else:
                row["typed_answers"] = {
                    "question_type": {
                        "confidence": 0.9,
                        "probabilities": {item["gold"]["question_type"]: 1.0},
                    }
                }
            rows.append(row)
        path.write_text(
            json.dumps({
                "model_id": model,
                "api_mode": mode,
                "dataset_sha256": hashlib.sha256(DATASET.read_bytes()).hexdigest(),
                "contract_sha256": hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest(),
                "rows": rows,
            }),
            encoding="utf-8",
        )
        paths.append(path)
    return paths


def test_compare_requires_exact_three_models(tmp_path):
    with pytest.raises(ValueError, match="three models"):
        compare([], tmp_path / "summary.json")


def test_compare_keeps_api_modes_separate(tmp_path, complete_result_files):
    output = tmp_path / "summary.json"

    summary = compare(complete_result_files, output)

    assert set(summary["models"]) == {
        "openai/gpt-6-luna",
        "anthropic/claude-haiku-5.5",
        "typesafe/jev-1.14",
    }
    assert summary["models"]["typesafe/jev-1.14"]["api_mode"] == "decisions"
    assert summary["models"]["typesafe/jev-1.14"]["first_pass_schema_valid_rate"] is None
    assert summary["models"]["openai/gpt-6-luna"]["api_mode"] == "chat_completions"
    assert summary["models"]["openai/gpt-6-luna"]["first_pass_schema_valid_rate"] == 1.0
    assert "typesafe/jev-1.14" in summary["decisions_metadata"]
    assert json.loads(output.read_text(encoding="utf-8")) == summary


def test_compare_rejects_duplicate_model_and_hash_mismatch(tmp_path, complete_result_files):
    with pytest.raises(ValueError, match="duplicate"):
        compare([complete_result_files[0]] * 3, tmp_path / "duplicate.json")

    changed = json.loads(complete_result_files[2].read_text(encoding="utf-8"))
    changed["contract_sha256"] = "c" * 64
    complete_result_files[2].write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="contract hash"):
        compare(complete_result_files, tmp_path / "mismatch.json")


def test_compare_rejects_mixed_run_counts(tmp_path, complete_result_files):
    changed = json.loads(complete_result_files[0].read_text(encoding="utf-8"))
    changed["rows"].append({**changed["rows"][0], "case_id": "sv0-02"})
    complete_result_files[0].write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(ValueError, match="run counts"):
        compare(complete_result_files, tmp_path / "mixed.json")
