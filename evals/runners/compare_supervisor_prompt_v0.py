"""Supervisor Prompt V0의 Chat 2종과 Decisions 1종 결과를 결정적으로 비교한다."""

import argparse
import hashlib
import json
import math
from pathlib import Path

from evals.runners.supervisor_prompt_v0_common import (
    DATASET,
    FROZEN,
    load_v0_dataset,
    score_decisions,
)


EXPECTED_MODES = {
    "openai/gpt-6-luna": "chat_completions",
    "anthropic/claude-haiku-5.5": "chat_completions",
    "typesafe/jev-1.14": "decisions",
}
ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "backend" / "graph" / "supervisor.py"


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def _usage(rows: list[dict]) -> dict:
    usages = [row.get("usage") for row in rows if isinstance(row.get("usage"), dict)]
    return {
        "input_tokens": sum(value.get("prompt_tokens", value.get("input_tokens", 0)) for value in usages),
        "output_tokens": sum(value.get("completion_tokens", value.get("output_tokens", 0)) for value in usages),
        "reported_rows": len(usages),
    }


def _cost(rows: list[dict]) -> dict:
    costs = [row.get("usage", {}).get("cost") for row in rows if isinstance(row.get("usage"), dict)]
    if costs and all(isinstance(cost, (int, float)) for cost in costs):
        return {"status": "reported", "reported_total_usd": sum(costs)}
    return {"status": "Not Reported", "reported_total_usd": None}


def _decisions_metadata(rows: list[dict]) -> dict:
    confidences = []
    probability_answers = 0
    for row in rows:
        typed = row.get("typed_answers")
        if not isinstance(typed, dict):
            continue
        for answer in typed.values():
            if not isinstance(answer, dict):
                continue
            confidence = answer.get("confidence")
            if isinstance(confidence, (int, float)) and not isinstance(confidence, bool):
                confidences.append(float(confidence))
            if isinstance(answer.get("probabilities"), dict):
                probability_answers += 1
    return {
        "typed_answer_count": len(confidences),
        "mean_confidence": sum(confidences) / len(confidences) if confidences else None,
        "probability_answer_count": probability_answers,
    }


def compare(result_paths: list[Path], output: Path) -> dict:
    """정확히 세 모델의 같은 실행 집합만 공통 지표로 집계해 JSON으로 쓴다."""

    if len(result_paths) != 3:
        raise ValueError("three models are required")
    payloads = [json.loads(Path(path).read_text(encoding="utf-8")) for path in result_paths]
    model_ids = [payload.get("model_id") for payload in payloads]
    if len(set(model_ids)) != len(model_ids):
        raise ValueError("duplicate model result")
    if set(model_ids) != set(EXPECTED_MODES):
        raise ValueError("three models must be the exact V0 candidates")

    dataset_hashes = {payload.get("dataset_sha256") for payload in payloads}
    current_dataset_hash = hashlib.sha256(DATASET.read_bytes()).hexdigest()
    if dataset_hashes != {current_dataset_hash}:
        raise ValueError("dataset hash mismatch")
    contract_hashes = {payload.get("contract_sha256") for payload in payloads}
    current_contract_hash = hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest()
    if contract_hashes != {current_contract_hash}:
        raise ValueError("contract hash mismatch")

    row_counts = {len(payload.get("rows", [])) for payload in payloads}
    case_sets = [{row.get("case_id") for row in payload.get("rows", [])} for payload in payloads]
    if len(row_counts) != 1 or any(cases != case_sets[0] for cases in case_sets[1:]):
        raise ValueError("mixed run counts or case sets")
    if any(len(cases) != len(payload.get("rows", [])) for cases, payload in zip(case_sets, payloads)):
        raise ValueError("duplicate case rows")

    all_items = {item["id"]: item for item in load_v0_dataset(DATASET, FROZEN)}
    if case_sets[0] != set(all_items):
        raise ValueError("incomplete or unknown case set")
    items = [all_items[case_id] for case_id in sorted(case_sets[0])]

    models = {}
    decisions_metadata = {}
    for payload in payloads:
        model_id = payload["model_id"]
        mode = payload.get("api_mode")
        if mode != EXPECTED_MODES[model_id]:
            raise ValueError("api mode mismatch")
        rows = payload["rows"]
        scores = score_decisions(rows, items)
        latencies = [
            float(row["latency_seconds"])
            for row in rows
            if isinstance(row.get("latency_seconds"), (int, float))
        ]
        if mode == "chat_completions":
            first_pass = sum(
                row.get("status") == "complete" and row.get("first_pass_valid") is True
                for row in rows
            ) / len(items)
        else:
            first_pass = None
            decisions_metadata[model_id] = _decisions_metadata(rows)
        models[model_id] = {
            "api_mode": mode,
            "question_type_accuracy": scores["question_type_accuracy"],
            "required_evidence_exact_match": scores["required_evidence_exact_match"],
            "next_action_accuracy": scores["next_action_accuracy"],
            "reason_code_accuracy": scores["reason_code_accuracy"],
            "first_pass_schema_valid_rate": first_pass,
            "final_schema_valid_rate": scores["completion_rate"],
            "semantic_valid_rate": scores["semantic_valid_rate"],
            "exact_decision_match": scores["exact_decision_match"],
            "latency_p50_seconds": _percentile(latencies, 0.50),
            "latency_p95_seconds": _percentile(latencies, 0.95),
            "usage": _usage(rows),
            "cost": _cost(rows),
        }

    summary = {
        "dataset_sha256": next(iter(dataset_hashes)),
        "contract_sha256": next(iter(contract_hashes)),
        "case_count": next(iter(row_counts)),
        "models": models,
        "decisions_metadata": decisions_metadata,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("results", nargs=3, type=Path)
    args = parser.parse_args(argv)
    summary = compare(args.results, args.output)
    print(json.dumps({"status": "complete", "case_count": summary["case_count"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
