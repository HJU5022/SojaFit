"""완료된 Supervisor Prompt V0 결과를 모델 재호출 없이 Langfuse로 가져온다."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path
from typing import Any, Iterable

from evals.runners.supervisor_prompt_v0_common import (
    DECISION_FIELDS,
    FROZEN,
    load_v0_dataset,
    model_input,
)


ROOT = Path(__file__).resolve().parents[2]
RESULT_ROOT = ROOT / "evals" / "results" / "supervisor" / "2026-11-06-prompt-v0-v1"
RECEIPT = RESULT_ROOT / "langfuse_import.json"
DATASET_NAME = "sojafit-supervisor-v0"
SOURCE_COMMIT = "68367c5"
SCORE_NAMES = (
    "schema_valid",
    "question_type_correct",
    "required_evidence_exact",
    "next_action_correct",
    "reason_code_correct",
    "semantic_valid",
    "exact_decision_match",
)
MODEL_RUNS = (
    {
        "model_id": "openai/gpt-6-luna",
        "provider": "Azure",
        "api_mode": "chat_completions",
        "slug": "luna-azure",
        "path": RESULT_ROOT / "chat" / "rows_openai__gpt-6-luna.json",
    },
    {
        "model_id": "anthropic/claude-haiku-5.5",
        "provider": "Google",
        "api_mode": "chat_completions",
        "slug": "haiku-google",
        "path": RESULT_ROOT / "chat" / "rows_anthropic__claude-haiku-5.5.json",
    },
    {
        "model_id": "typesafe/jev-1.14",
        "provider": "TypeSafe",
        "api_mode": "decisions",
        "slug": "jev-typesafe",
        "path": RESULT_ROOT / "jev" / "rows_typesafe__jev-1.14.json",
    },
)


def _dataset_item_id(case_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"sojafit/{DATASET_NAME}/{case_id}"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_result(run: dict[str, Any], *, dataset_hash: str, case_ids: set[str]) -> dict[str, Any]:
    payload = _load_json(Path(run["path"]))
    if payload.get("dataset_sha256") != dataset_hash:
        raise ValueError(f"dataset hash mismatch: {run['model_id']}")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"rows missing: {run['model_id']}")
    row_ids = [row.get("case_id") for row in rows]
    if len(row_ids) != len(set(row_ids)) or set(row_ids) != case_ids:
        raise ValueError(f"case set mismatch: {run['model_id']}")
    if any(row.get("status") != "complete" for row in rows):
        raise ValueError(f"incomplete result row: {run['model_id']}")
    return payload


def build_import_plan(*, model_runs: Iterable[dict[str, Any]] = MODEL_RUNS) -> dict[str, Any]:
    items = load_v0_dataset()
    frozen = _load_json(FROZEN)
    dataset_hash = frozen["sha256"]
    case_ids = {item["id"] for item in items}
    loaded_runs = []
    contract_hash = None
    for run in model_runs:
        payload = _load_result(run, dataset_hash=dataset_hash, case_ids=case_ids)
        if contract_hash is None:
            contract_hash = payload.get("contract_sha256")
        if not contract_hash or payload.get("contract_sha256") != contract_hash:
            raise ValueError(f"contract hash mismatch: {run['model_id']}")
        loaded_runs.append({**run, "rows": payload["rows"]})

    dataset_items = [
        {
            "id": _dataset_item_id(item["id"]),
            "input": model_input(item),
            "expected_output": item["gold"],
            "metadata": {
                "case_id": item["id"],
                "dataset_sha256": dataset_hash,
                "contract_sha256": contract_hash,
                "imported_existing_result": True,
            },
        }
        for item in items
    ]
    return {
        "dataset_name": DATASET_NAME,
        "dataset_sha256": dataset_hash,
        "contract_sha256": contract_hash,
        "dataset_item_count": len(dataset_items),
        "experiment_count": len(loaded_runs),
        "score_names": list(SCORE_NAMES),
        "score_count": len(dataset_items) * len(loaded_runs) * len(SCORE_NAMES),
        "dataset_items": dataset_items,
        "model_runs": loaded_runs,
    }


def evaluate_result(*, output: dict[str, Any], expected_output: dict[str, Any], **_: Any) -> list[dict[str, Any]]:
    decision = output.get("decision")
    schema_valid = (
        output.get("status") == "complete"
        and isinstance(decision, dict)
        and all(field in decision for field in DECISION_FIELDS)
    )
    field_scores = {
        "question_type_correct": schema_valid and decision["question_type"] == expected_output["question_type"],
        "required_evidence_exact": schema_valid and decision["required_evidence"] == expected_output["required_evidence"],
        "next_action_correct": schema_valid and decision["next_action"] == expected_output["next_action"],
        "reason_code_correct": schema_valid and decision["reason_code"] == expected_output["reason_code"],
    }
    values = {
        "schema_valid": schema_valid,
        **field_scores,
        "semantic_valid": schema_valid and not output.get("semantic_errors", []),
        "exact_decision_match": schema_valid and all(field_scores.values()),
    }
    return [{"name": name, "value": int(values[name])} for name in SCORE_NAMES]


def ensure_import_not_already_recorded(receipt: Path = RECEIPT) -> None:
    if receipt.exists():
        raise FileExistsError(f"Langfuse import receipt already exists: {receipt}")


def normalize_langfuse_base_url() -> None:
    """Langfuse 5.0.4의 OTEL endpoint 이중 슬래시를 막는다."""

    base_url = os.environ.get("LANGFUSE_BASE_URL")
    if base_url:
        os.environ["LANGFUSE_BASE_URL"] = base_url.rstrip("/")


def _safe_output(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: row.get(key)
        for key in (
            "status",
            "decision",
            "semantic_errors",
            "first_pass_valid",
            "latency_seconds",
            "usage",
        )
        if key in row
    }


def import_results(plan: dict[str, Any], *, client: Any) -> dict[str, Any]:
    """Langfuse 쓰기. 호출 전 plan 전체가 검증되어 있어야 한다."""

    from langfuse.api.commons.errors.not_found_error import NotFoundError

    try:
        dataset = client.get_dataset(DATASET_NAME)
        metadata = dataset.metadata or {}
        if metadata.get("dataset_sha256") != plan["dataset_sha256"]:
            raise ValueError("existing Langfuse dataset hash mismatch")
    except NotFoundError:
        client.create_dataset(
            name=DATASET_NAME,
            description="SojaFit Supervisor Prompt V0 13-case comparison (imported existing results)",
            metadata={
                "dataset_sha256": plan["dataset_sha256"],
                "contract_sha256": plan["contract_sha256"],
                "source_commit": SOURCE_COMMIT,
                "imported_existing_result": True,
            },
        )

    for item in plan["dataset_items"]:
        client.create_dataset_item(dataset_name=DATASET_NAME, **item)

    dataset = client.get_dataset(DATASET_NAME)
    if len(dataset.items) != plan["dataset_item_count"]:
        raise ValueError("Langfuse dataset item count mismatch after upload")

    experiments = []
    for run in plan["model_runs"]:
        rows_by_case = {row["case_id"]: row for row in run["rows"]}

        def stored_result(*, item: Any, _rows: dict[str, dict[str, Any]] = rows_by_case, **_: Any) -> dict[str, Any]:
            return _safe_output(_rows[item.metadata["case_id"]])

        run_name = f"supervisor-v0-{run['slug']}-2026-11-06"
        result = client.run_experiment(
            name=run_name,
            run_name=run_name,
            experiment_id=client.create_trace_id(seed=f"{DATASET_NAME}/{run_name}"),
            description="Imported existing 2026-11-06 Supervisor V0 result; no model call performed.",
            data=dataset.items,
            task=stored_result,
            evaluators=[evaluate_result],
            max_concurrency=1,
            metadata={
                "model": run["model_id"],
                "provider": run["provider"],
                "api_mode": run["api_mode"],
                "source_commit": SOURCE_COMMIT,
                "dataset_sha256": plan["dataset_sha256"],
                "contract_sha256": plan["contract_sha256"],
                "imported_existing_result": "true",
            },
        )
        if len(result.item_results) != plan["dataset_item_count"]:
            raise RuntimeError(
                f"Langfuse experiment item count mismatch: {run_name} "
                f"({len(result.item_results)}/{plan['dataset_item_count']})"
            )
        if any(len(item.evaluations) != len(SCORE_NAMES) for item in result.item_results):
            raise RuntimeError(f"Langfuse experiment score count mismatch: {run_name}")
        experiments.append(
            {
                "model_id": run["model_id"],
                "run_name": result.run_name,
                "experiment_id": result.experiment_id,
                "experiment_url": result.experiment_url,
                "item_count": len(result.item_results),
            }
        )

    client.flush()
    return {
        "dataset_name": DATASET_NAME,
        "dataset_id": dataset.id,
        "dataset_item_count": len(dataset.items),
        "dataset_sha256": plan["dataset_sha256"],
        "contract_sha256": plan["contract_sha256"],
        "source_commit": SOURCE_COMMIT,
        "imported_existing_result": True,
        "model_calls_performed": 0,
        "score_names": list(SCORE_NAMES),
        "score_count": plan["score_count"],
        "experiments": experiments,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "import"))
    parser.add_argument("--confirm-langfuse-write", action="store_true")
    args = parser.parse_args()

    plan = build_import_plan()
    if args.command == "plan":
        printable = {key: value for key, value in plan.items() if key not in {"dataset_items", "model_runs"}}
        print(json.dumps(printable, ensure_ascii=False, indent=2))
        return 0
    if not args.confirm_langfuse_write:
        parser.error("import requires --confirm-langfuse-write")
    ensure_import_not_already_recorded()

    from langfuse import get_client

    normalize_langfuse_base_url()
    client = get_client()
    if not client.auth_check():
        raise RuntimeError("Langfuse authentication failed")
    receipt = import_results(plan, client=client)
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
