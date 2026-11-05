"""Luna·Haiku에 Supervisor Prompt V0를 같은 입력으로 평가하는 실행기."""

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

from pydantic import ValidationError

from backend.graph.supervisor import SupervisorDecision, render_chat_input, semantic_errors
from backend.services import llm
from evals.runners.supervisor_prompt_v0_common import (
    DATASET,
    FROZEN,
    load_v0_dataset,
    model_input,
    score_decisions,
)


ROOT = Path(__file__).resolve().parents[2]
PROMPT_PATH = ROOT / "backend" / "prompts" / "supervisor_v0.md"
COMMON_PATH = ROOT / "evals" / "runners" / "supervisor_prompt_v0_common.py"
PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

MODELS = ("openai/gpt-6-luna", "anthropic/claude-haiku-5.5")
PROVIDER_POLICY = {
    "zdr": True,
    "data_collection": "deny",
    "allow_fallbacks": False,
    "require_parameters": True,
}
MAX_TOKENS = 256
MAX_RAW_ATTEMPTS = 3


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json_atomic(path: Path, value: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def build_plan(items: list[dict]) -> list[dict]:
    """두 Chat 모델에 같은 13건을 한 번씩 주는 26-job 계획을 만든다."""

    return [
        {"model_id": model, "case_id": item["id"], "run_index": 1}
        for model in MODELS
        for item in items
    ]


def create_manifest(dataset=DATASET, frozen=FROZEN) -> dict:
    """API 호출 없이 입력·프롬프트·공통 계약 hash를 고정한다."""

    dataset = Path(dataset)
    frozen = Path(frozen)
    items = load_v0_dataset(dataset, frozen)
    return {
        "dataset": str(dataset.relative_to(ROOT)),
        "dataset_sha256": _sha256(dataset),
        "dataset_count": len(items),
        "models": list(MODELS),
        "runs_per_case": 1,
        "provider_policy": PROVIDER_POLICY,
        "prompt_sha256": _sha256(PROMPT_PATH),
        "common_module_sha256": _sha256(COMMON_PATH),
        "jobs": build_plan(items),
    }


def run_one(
    model: str,
    item: dict,
    *,
    call=llm.evaluation_chat,
    clock=time.perf_counter,
) -> dict:
    """한 문항을 형식 오류에만 최대 세 번 시도하고 저장 가능한 행으로 만든다."""

    if model not in MODELS:
        raise ValueError("등록되지 않은 Supervisor Prompt V0 Chat 모델")

    started = clock()
    user = render_chat_input(model_input(item))
    attempt_usages = []
    for attempt in range(1, MAX_RAW_ATTEMPTS + 1):
        try:
            decision, metadata = call(
                model,
                PROMPT,
                user,
                SupervisorDecision,
                provider_policy=PROVIDER_POLICY,
                max_tokens=MAX_TOKENS,
                timeout=45.0,
            )
            return {
                "model_id": model,
                "case_id": item["id"],
                "status": "complete",
                "decision": decision.model_dump(),
                "semantic_errors": semantic_errors(decision, item.get("current_state", {})),
                "first_pass_valid": attempt == 1,
                "raw_attempts": attempt,
                "latency_seconds": clock() - started,
                "response_id": metadata.get("response_id"),
                "actual_model": metadata.get("actual_model"),
                "provider": metadata.get("provider"),
                "finish_reason": metadata.get("finish_reason"),
                "usage": metadata.get("usage"),
            }
        except (llm.EvaluationFormatError, ValidationError) as error:
            metadata = getattr(error, "metadata", {})
            attempt_usages.append(metadata.get("usage"))
            if attempt < MAX_RAW_ATTEMPTS:
                continue
            return {
                "model_id": model,
                "case_id": item["id"],
                "status": "error",
                "error_type": "ValidationError",
                "first_pass_valid": False,
                "raw_attempts": attempt,
                "latency_seconds": clock() - started,
                "attempt_usages": attempt_usages,
                "actual_model": metadata.get("actual_model"),
                "provider": metadata.get("provider"),
            }
        except Exception as error:
            return {
                "model_id": model,
                "case_id": item["id"],
                "status": "error",
                "error_type": type(error).__name__,
                "first_pass_valid": False,
                "raw_attempts": attempt,
                "latency_seconds": clock() - started,
            }
    raise AssertionError("unreachable")


def _validate_manifest(run_dir: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    items = load_v0_dataset(DATASET, FROZEN)
    expected = create_manifest()
    for key in (
        "dataset_sha256",
        "dataset_count",
        "models",
        "provider_policy",
        "prompt_sha256",
        "common_module_sha256",
        "jobs",
    ):
        if manifest.get(key) != expected[key]:
            raise ValueError(f"manifest {key} mismatch")
    return manifest, items


def execute_model(
    run_dir: Path,
    model: str,
    *,
    max_usd: float,
    max_seconds: float,
    prompt_rate: float,
    completion_rate: float,
    call=llm.evaluation_chat,
) -> dict:
    """한 모델의 13건을 예산 안에서 실행하며 매 문항 뒤 원자적으로 저장한다."""

    if model not in MODELS:
        raise ValueError("등록되지 않은 Supervisor Prompt V0 Chat 모델")
    run_dir = Path(run_dir)
    _, items = _validate_manifest(run_dir)
    output = run_dir / f"rows_{model.replace('/', '__')}.json"
    result = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {
        "status": "incomplete",
        "model_id": model,
        "rows": [],
    }
    completed_ids = {row["case_id"] for row in result["rows"]}
    budget = llm.EvaluationBudget(
        max_calls=len(items) * MAX_RAW_ATTEMPTS,
        max_usd=max_usd,
        max_seconds=max_seconds,
        prompt_rate=prompt_rate,
        completion_rate=completion_rate,
        max_tokens=MAX_TOKENS,
    )
    consecutive_provider_errors = 0
    locked_provider = next(
        (row.get("provider") for row in result["rows"] if row.get("provider")),
        None,
    )

    with llm.evaluation_limits(budget):
        for item in items:
            if item["id"] in completed_ids:
                continue
            row = run_one(model, item, call=call)
            result["rows"].append(row)

            if row.get("status") == "complete":
                provider = row.get("provider")
                if locked_provider and provider and provider != locked_provider:
                    result["status"] = "provider_stopped"
                    result["stop_reason"] = {"error_type": "ProviderChanged"}
                    _write_json_atomic(output, result)
                    break
                locked_provider = locked_provider or provider
                consecutive_provider_errors = 0
            elif row.get("error_type") == "EvaluationLimitError":
                result["status"] = "budget_stopped"
                _write_json_atomic(output, result)
                break
            elif row.get("error_type") != "ValidationError":
                consecutive_provider_errors += 1
                if consecutive_provider_errors >= 3:
                    result["status"] = "provider_stopped"
                    result["stop_reason"] = {
                        "error_type": row["error_type"],
                        "consecutive": consecutive_provider_errors,
                    }
                    _write_json_atomic(output, result)
                    break
            _write_json_atomic(output, result)
        else:
            result["status"] = (
                "complete_with_errors"
                if any(row.get("status") == "error" for row in result["rows"])
                else "complete"
            )

    result["budget"] = {
        "max_calls": budget.max_calls,
        "max_usd": budget.max_usd,
        "max_seconds": budget.max_seconds,
        "raw_calls": budget.calls,
        "reserved_usd": budget.reserved_usd,
    }
    result["summary"] = score_decisions(result["rows"], items)
    _write_json_atomic(output, result)
    return result


def _positive(parser: argparse.ArgumentParser, args) -> None:
    values = (
        args.max_usd,
        args.max_seconds,
        args.prompt_rate,
        args.completion_rate,
    )
    if any(value <= 0 for value in values):
        parser.error("live 상한과 단가는 모두 양수여야 합니다")
    if not args.confirm_live:
        parser.error("live API 호출에는 --confirm-live가 필요합니다")
    if not os.getenv("OPENROUTER_API_KEY"):
        parser.error("OPENROUTER_API_KEY가 필요합니다")


def main(argv=None) -> int:
    """오프라인 plan 또는 명시적으로 승인된 smoke/run 명령을 처리한다."""

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("output", type=Path)
    for name in ("smoke", "run"):
        live = commands.add_parser(name)
        live.add_argument("output", type=Path)
        live.add_argument("--model", choices=MODELS, required=True)
        live.add_argument("--max-usd", type=float, required=True)
        live.add_argument("--max-seconds", type=float, required=True)
        live.add_argument("--prompt-rate", type=float, required=True)
        live.add_argument("--completion-rate", type=float, required=True)
        live.add_argument("--confirm-live", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "plan":
        args.output.mkdir(parents=True, exist_ok=False)
        manifest = create_manifest()
        _write_json_atomic(args.output / "manifest.json", manifest)
        print(json.dumps({"status": "prepared", "jobs": len(manifest["jobs"])}, ensure_ascii=False))
        return 0

    _positive(parser, args)
    if args.command == "smoke":
        _validate_manifest(args.output)
        item = load_v0_dataset(DATASET, FROZEN)[0]
        budget = llm.EvaluationBudget(
            MAX_RAW_ATTEMPTS,
            args.max_usd,
            args.max_seconds,
            args.prompt_rate,
            args.completion_rate,
            max_tokens=MAX_TOKENS,
        )
        with llm.evaluation_limits(budget):
            row = run_one(args.model, item)
        result = {"status": row["status"], "model_id": args.model, "row": row}
        _write_json_atomic(args.output / f"smoke_{args.model.replace('/', '__')}.json", result)
    else:
        result = execute_model(
            args.output,
            args.model,
            max_usd=args.max_usd,
            max_seconds=args.max_seconds,
            prompt_rate=args.prompt_rate,
            completion_rate=args.completion_rate,
        )
    print(json.dumps({"status": result["status"], "model": args.model}, ensure_ascii=False))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
