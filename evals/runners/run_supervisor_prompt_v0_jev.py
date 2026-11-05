"""Jev Decisions API로 Supervisor Prompt V0 의미 계약을 평가하는 실행기."""

import argparse
import hashlib
import json
import math
import os
import time
from pathlib import Path

from backend.graph.supervisor import (
    REASON_BY_TYPE,
    SupervisorDecision,
    build_jev_question_contract,
    semantic_errors,
)
from backend.services import llm
from evals.runners.supervisor_prompt_v0_common import (
    DATASET,
    FROZEN,
    load_v0_dataset,
    model_input,
    score_decisions,
)


ROOT = Path(__file__).resolve().parents[2]
COMMON_PATH = ROOT / "evals" / "runners" / "supervisor_prompt_v0_common.py"
MODEL_ID = "typesafe/jev-1.14"
PROVIDER_POLICY = {
    "zdr": True,
    "data_collection": "deny",
    "allow_fallbacks": False,
}
QUESTION_CONTRACT = build_jev_question_contract()
EVIDENCE_QUESTIONS = (
    ("needs_circuit", "circuit"),
    ("needs_datasheet", "datasheet"),
    ("needs_approved_case", "approved_case"),
)


class JevFormatError(ValueError):
    """Decisions 응답이 V0 typed-answer 계약과 다를 때 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _contract_hash() -> str:
    encoded = json.dumps(QUESTION_CONTRACT, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_json_atomic(path: Path, value: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _choice(answers: dict, key: str) -> str:
    answer = answers.get(key)
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        raise JevFormatError(key)
    choice = answer.get("choice")
    allowed = set(QUESTION_CONTRACT[key]["criteria"])
    if choice not in allowed:
        raise JevFormatError(key)

    confidence = answer.get("confidence")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(confidence)
        or not 0 <= confidence <= 1
    ):
        raise JevFormatError(key)
    probabilities = answer.get("probabilities")
    if not isinstance(probabilities, dict) or choice not in probabilities:
        raise JevFormatError(key)
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
        for value in probabilities.values()
    ):
        raise JevFormatError(key)
    if not math.isclose(sum(probabilities.values()), 1.0, abs_tol=1e-6):
        raise JevFormatError(key)
    return choice


def build_request_from_item(item: dict, provider: str | None = None) -> dict:
    """정답·case id를 제외한 공통 envelope를 Decisions state에 넣는다."""

    policy = dict(PROVIDER_POLICY)
    if provider:
        policy["only"] = [provider]
    return {
        "model": MODEL_ID,
        "state": model_input(item),
        "questions": QUESTION_CONTRACT,
        "provider": policy,
    }


def parse_item_response(item: dict, payload: dict) -> dict:
    """다섯 typed answer를 공통 네 필드로 정규화하고 의미 오류를 따로 남긴다."""

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise JevFormatError("answers")
    choices = {key: _choice(answers, key) for key in QUESTION_CONTRACT}
    required_evidence = [
        evidence
        for question, evidence in EVIDENCE_QUESTIONS
        if choices[question] == "yes"
    ]
    decision = SupervisorDecision(
        question_type=choices["question_type"],
        required_evidence=required_evidence,
        next_action=choices["next_action"],
        reason_code=REASON_BY_TYPE[choices["question_type"]],
    )
    return {
        "model_id": MODEL_ID,
        "case_id": item["id"],
        "status": "complete",
        "decision": decision.model_dump(),
        "semantic_errors": semantic_errors(decision, item.get("current_state", {})),
        "typed_answers": {
            key: {
                field: answers[key][field]
                for field in ("type", "choice", "confidence", "probabilities")
            }
            for key in QUESTION_CONTRACT
        },
    }


def create_manifest(dataset=DATASET, frozen=FROZEN) -> dict:
    """API 호출 없이 Jev 13-job 입력과 두 의미 계약 hash를 고정한다."""

    dataset = Path(dataset)
    frozen = Path(frozen)
    items = load_v0_dataset(dataset, frozen)
    return {
        "model": MODEL_ID,
        "dataset": str(dataset.relative_to(ROOT)),
        "dataset_sha256": _sha256(dataset),
        "dataset_count": len(items),
        "provider_policy": PROVIDER_POLICY,
        "question_contract_sha256": _contract_hash(),
        "common_module_sha256": _sha256(COMMON_PATH),
        "jobs": [
            {"model_id": MODEL_ID, "case_id": item["id"], "run_index": 1}
            for item in items
        ],
    }


def _validate_manifest(run_dir: Path) -> tuple[dict, list[dict]]:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    expected = create_manifest()
    for key in (
        "model",
        "dataset_sha256",
        "dataset_count",
        "provider_policy",
        "question_contract_sha256",
        "common_module_sha256",
        "jobs",
    ):
        if manifest.get(key) != expected[key]:
            raise ValueError(f"manifest {key} mismatch")
    return manifest, load_v0_dataset(DATASET, FROZEN)


def execute(
    run_dir: Path,
    *,
    max_calls: int,
    max_seconds: float,
    approved_max_usd: float,
) -> dict:
    """호출·시간 상한을 집행하고 승인 USD는 비용 미보고 상태로만 기록한다."""

    run_dir = Path(run_dir)
    _, items = _validate_manifest(run_dir)
    output = run_dir / "rows_typesafe__jev-1.14.json"
    result = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {
        "status": "incomplete",
        "model_id": MODEL_ID,
        "rows": [],
    }
    completed_ids = {row["case_id"] for row in result["rows"]}
    started = time.monotonic()
    calls = 0

    for item in items:
        if item["id"] in completed_ids:
            continue
        if calls >= max_calls:
            result["status"] = "call_limit_stopped"
            break
        if time.monotonic() - started >= max_seconds:
            result["status"] = "time_limit_stopped"
            break
        calls += 1
        request = build_request_from_item(item)
        before = time.monotonic()
        try:
            payload = llm.evaluation_decision(
                request,
                timeout=max(0.001, min(45.0, max_seconds - (time.monotonic() - started))),
            )
            row = parse_item_response(item, payload)
            row.update({
                "latency_seconds": time.monotonic() - before,
                "response_id": payload.get("id"),
                "actual_model": payload.get("model"),
                "provider": payload.get("provider"),
                "usage": payload.get("usage"),
            })
        except JevFormatError:
            row = {
                "model_id": MODEL_ID,
                "case_id": item["id"],
                "status": "error",
                "error_type": "ValidationError",
                "latency_seconds": time.monotonic() - before,
            }
        except Exception as error:
            row = {
                "model_id": MODEL_ID,
                "case_id": item["id"],
                "status": "error",
                "error_type": type(error).__name__,
                "latency_seconds": time.monotonic() - before,
            }
        result["rows"].append(row)
        _write_json_atomic(output, result)
    else:
        result["status"] = (
            "complete_with_errors"
            if any(row.get("status") == "error" for row in result["rows"])
            else "complete"
        )

    result["limits"] = {
        "max_calls": max_calls,
        "calls_this_process": calls,
        "max_seconds": max_seconds,
        "approved_max_usd": approved_max_usd,
        "reported_cost": "Not Reported",
        "usd_cap_technically_enforced": False,
    }
    result["summary"] = score_decisions(result["rows"], items)
    _write_json_atomic(output, result)
    return result


def _validate_live(parser: argparse.ArgumentParser, args) -> None:
    if args.max_calls <= 0 or args.max_seconds <= 0 or args.max_usd <= 0:
        parser.error("--max-calls, --max-seconds, --max-usd는 양수여야 합니다")
    if not args.confirm_live:
        parser.error("live API 호출에는 --confirm-live가 필요합니다")
    if not os.getenv("OPENROUTER_API_KEY"):
        parser.error("OPENROUTER_API_KEY가 필요합니다")


def main(argv=None) -> int:
    """오프라인 plan 또는 명시적으로 승인된 smoke/run 명령을 처리한다."""

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("output", type=Path)
    for name in ("smoke", "run"):
        live = commands.add_parser(name)
        live.add_argument("output", type=Path)
        live.add_argument("--max-calls", type=int, required=True)
        live.add_argument("--max-seconds", type=float, required=True)
        live.add_argument("--max-usd", type=float, required=True)
        live.add_argument("--confirm-live", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "plan":
        args.output.mkdir(parents=True, exist_ok=False)
        manifest = create_manifest()
        _write_json_atomic(args.output / "manifest.json", manifest)
        print(json.dumps({"status": "prepared", "jobs": len(manifest["jobs"])}, ensure_ascii=False))
        return 0

    _validate_live(parser, args)
    max_calls = 1 if args.command == "smoke" else args.max_calls
    result = execute(
        args.output,
        max_calls=max_calls,
        max_seconds=args.max_seconds,
        approved_max_usd=args.max_usd,
    )
    print(json.dumps({"status": result["status"], "model": MODEL_ID}, ensure_ascii=False))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
