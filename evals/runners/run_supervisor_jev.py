"""Jev 수퍼바이저를 동결 v2 70문항에서 평가하기 위한 전용 실행기."""

import argparse
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path

from backend.services import llm
from evals.runners.run_supervisor_models import load_frozen_dataset


MODEL_ID = "typesafe/jev-1.14"
ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "evals/dataset_v2.jsonl"
FROZEN = ROOT / "evals/FROZEN.json"

PROVIDER_POLICY = {
    "zdr": True,
    "data_collection": "deny",
    "allow_fallbacks": False,
}

QUESTION_TYPES = (
    "out_of_scope",
    "role",
    "candidate_find",
    "candidate_judge",
    "rating",
    "insufficient_information",
)
ACTIONS = ("circuit_agent", "search_agent", "judge_answer_agent", "refuse")
EVIDENCE_ANSWERS = (
    ("needs_circuit", "circuit"),
    ("needs_datasheet", "datasheet"),
    ("needs_approved_case", "approved_case"),
)

QUESTION_CONTRACT = {
    "question_type": {
        "type": "choice",
        "instructions": "사용자 질문의 종류를 하나 고르세요.",
        "criteria": {
            "out_of_scope": "다이오드 대체 서비스 범위 밖 질문",
            "role": "회로 안 대상 다이오드의 역할이나 연결 질문",
            "candidate_find": "후보 품번 없이 대체품을 찾아 달라는 질문",
            "candidate_judge": "특정 후보 품번의 대체 가능성을 묻는 질문",
            "rating": "특정 다이오드의 정격이나 특성을 묻는 질문",
            "insufficient_information": "안전한 분류에 필요한 대상이나 조건이 없음",
        },
    },
    "needs_circuit": {
        "type": "choice",
        "instructions": "회로 연결 근거가 필요합니까?",
        "criteria": {"yes": "필요함", "no": "필요하지 않음"},
    },
    "needs_datasheet": {
        "type": "choice",
        "instructions": "데이터시트 근거가 필요합니까?",
        "criteria": {"yes": "필요함", "no": "필요하지 않음"},
    },
    "needs_approved_case": {
        "type": "choice",
        "instructions": "사용자가 승인한 과거 사례가 필요합니까?",
        "criteria": {"yes": "필요함", "no": "필요하지 않음"},
    },
    "next_action": {
        "type": "choice",
        "instructions": "다음 실행 노드를 하나 고르세요.",
        "criteria": {
            "circuit_agent": "회로 역할과 연결을 확인",
            "search_agent": "데이터시트나 대체 후보를 검색",
            "judge_answer_agent": "준비된 근거로 판정하고 답을 작성",
            "refuse": "범위 밖이거나 정보 부족으로 단서 요청 또는 거절",
        },
    },
}


class JevFormatError(ValueError):
    """Decisions 응답이 고정 typed-answer 계약을 따르지 않을 때 발생한다."""


class JevProviderMismatch(ValueError):
    """요청한 모델 또는 smoke로 고정한 provider와 다른 응답."""

    def __init__(self, payload: dict):
        super().__init__("Jev model/provider mismatch")
        self.actual_model = payload.get("model")
        self.provider = payload.get("provider")
        self.usage = payload.get("usage")


def _choice(answers: dict, key: str) -> str:
    answer = answers.get(key)
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        raise JevFormatError(key)
    choice = answer.get("choice")
    if not isinstance(choice, str):
        raise JevFormatError(key)
    confidence = answer.get("confidence")
    probabilities = answer.get("probabilities")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        raise JevFormatError(key)
    if not isinstance(probabilities, dict) or choice not in probabilities:
        raise JevFormatError(key)
    return choice


def _safe_answer(answer: dict) -> dict:
    """원문 없이 비교에 필요한 typed-answer 측정값만 남긴다."""
    return {
        key: answer[key]
        for key in ("type", "choice", "confidence", "probabilities")
        if key in answer
    }


def parse_decision_response(payload: dict) -> tuple[dict, dict]:
    """Jev의 5개 typed answer를 기존 수퍼바이저 결정 구조로 변환한다."""
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise JevFormatError("answers")
    choices = {key: _choice(answers, key) for key in QUESTION_CONTRACT}
    if choices["question_type"] not in QUESTION_TYPES:
        raise JevFormatError("question_type")
    if choices["next_action"] not in ACTIONS:
        raise JevFormatError("next_action")
    if any(choices[key] not in {"yes", "no"} for key, _ in EVIDENCE_ANSWERS):
        raise JevFormatError("required_evidence")

    required_evidence = [
        evidence
        for key, evidence in EVIDENCE_ANSWERS
        if choices[key] == "yes"
    ]
    decision = {
        "question_type": choices["question_type"],
        "required_evidence": required_evidence,
        "next_action": choices["next_action"],
        "reason_code": choices["question_type"].upper(),
    }
    evidence = {key: _safe_answer(answers[key]) for key in QUESTION_CONTRACT}
    return decision, evidence


def _contract_hash() -> str:
    encoded = json.dumps(QUESTION_CONTRACT, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_request(user_input: str, provider: str | None = None) -> dict:
    """gold 없이 사용자 입력과 고정 질문 계약만 Decisions 요청으로 만든다."""
    policy = dict(PROVIDER_POLICY)
    if provider:
        policy["only"] = [provider]
    return {
        "model": MODEL_ID,
        "state": {"user_input": user_input},
        "questions": QUESTION_CONTRACT,
        "provider": policy,
    }


def create_manifest(dataset: Path = DATASET, frozen_path: Path = FROZEN, *, run_index: int = 1) -> dict:
    """동결 v2에서 정답 본문 없이 Jev 70-job manifest를 만든다."""
    if run_index not in (1, 2, 3):
        raise ValueError("run_index는 1, 2, 3 중 하나여야 합니다")
    dataset = Path(dataset)
    items = load_frozen_dataset(dataset, frozen_path)
    return {
        "model": MODEL_ID,
        "dataset": dataset.name,
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "dataset_count": len(items),
        "runs_per_case": 1,
        "run_index": run_index,
        "provider_policy": dict(PROVIDER_POLICY),
        "question_contract_sha256": _contract_hash(),
        "jobs": [
            {"model_id": MODEL_ID, "case_id": item["id"], "run_index": run_index}
            for item in items
        ],
    }


def _base_row(job: dict, elapsed: float) -> dict:
    return {
        "model_id": job["model_id"],
        "case_id": job["case_id"],
        "run_index": job["run_index"],
        "latency_seconds": elapsed,
    }


def run_job(job: dict, item: dict, *, call, clock=time.monotonic) -> dict:
    """한 job을 실행하고 schema 오류만 총 3회 시도한다."""
    started = clock()
    last_payload = {}
    attempt_costs = []
    for attempt in range(3):
        try:
            payload = call(item["input"])
            last_payload = payload
            attempt_costs.append((payload.get("usage") or {}).get("cost"))
            decision, evidence = parse_decision_response(payload)
            return {
                **_base_row(job, clock() - started),
                "status": "complete",
                "retry_count": attempt,
                "decision": decision,
                "typed_answers": evidence,
                "response_id": payload.get("id"),
                "actual_model": payload.get("model"),
                "provider": payload.get("provider"),
                "usage": payload.get("usage"),
                "reported_cost_sum": sum(attempt_costs) if all(cost is not None for cost in attempt_costs) else None,
            }
        except JevFormatError:
            if attempt == 2:
                return {
                    **_base_row(job, clock() - started),
                    "status": "error",
                    "error_type": "ValidationError",
                    "retry_count": attempt,
                    "actual_model": last_payload.get("model"),
                    "provider": last_payload.get("provider"),
                    "usage": last_payload.get("usage"),
                    "reported_cost_sum": sum(attempt_costs) if all(cost is not None for cost in attempt_costs) else None,
                }
        except JevProviderMismatch as error:
            attempt_costs.append((error.usage or {}).get("cost"))
            return {
                **_base_row(job, clock() - started),
                "status": "error",
                "error_type": "JevProviderMismatch",
                "retry_count": attempt,
                "actual_model": error.actual_model,
                "provider": error.provider,
                "usage": error.usage,
                "reported_cost_sum": sum(attempt_costs) if all(cost is not None for cost in attempt_costs) else None,
            }
        except Exception as error:
            if len(attempt_costs) <= attempt:
                attempt_costs.append(None)
            return {
                **_base_row(job, clock() - started),
                "status": "error",
                "error_type": type(error).__name__,
                "retry_count": attempt,
                "reported_cost_sum": None,
            }
    raise AssertionError("unreachable")


def _rate(numerator: int, denominator: int) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator if denominator else None,
    }


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def summarize(rows: list[dict], items_by_id: dict[str, dict], *, run_index: int = 1) -> dict:
    """70개 전체 운영 지표와 gold가 있는 35개의 분류 지표를 분리한다."""
    latest = {(row["case_id"], row["run_index"]): row for row in rows}
    run_rows = [row for row in rows if row.get("run_index") == run_index]
    considered = [latest.get((case_id, run_index)) for case_id in items_by_id]
    complete = [row for row in considered if row and row.get("status") == "complete"]
    schema_valid = [row for row in complete if isinstance(row.get("decision"), dict)]
    labeled = {case_id: item for case_id, item in items_by_id.items() if item.get("question_type")}
    predictions = {
        case_id: latest[(case_id, run_index)]["decision"]["question_type"]
        for case_id in labeled
        if latest.get((case_id, run_index), {}).get("status") == "complete"
    }
    correct = sum(predictions.get(case_id) == item["question_type"] for case_id, item in labeled.items())
    classes = sorted({item["question_type"] for item in labeled.values()})
    per_class = {}
    for label in classes:
        tp = sum(predictions.get(case_id) == label and item["question_type"] == label
                 for case_id, item in labeled.items())
        fp = sum(predictions.get(case_id) == label and item["question_type"] != label
                 for case_id, item in labeled.items())
        fn = sum(predictions.get(case_id) != label and item["question_type"] == label
                 for case_id, item in labeled.items())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
    usages = [row.get("usage") or {} for row in complete]
    costs = [usage.get("cost") for usage in usages]
    latencies = [float(row["latency_seconds"]) for row in considered if row and row.get("latency_seconds") is not None]
    confidences = [
        float(answer["confidence"])
        for row in complete
        for answer in row.get("typed_answers", {}).values()
        if answer.get("confidence") is not None
    ]
    expected = len(items_by_id)
    return {
        "Question Type Accuracy": {**_rate(correct, len(labeled)), "scored_unique_cases": len(labeled)},
        "Question Type Macro-F1": (
            sum(score["f1"] for score in per_class.values()) / len(per_class) if per_class else None
        ),
        "Question Type Per-Class": per_class,
        "Known Limitation": {
            "unscored_case_count": expected - len(labeled),
            "reason": "question_type gold 없음; 70문항 실행은 유지하되 objective score에서 제외",
        },
        "Completion Rate": _rate(len(complete), expected),
        "Schema Valid Rate": _rate(len(schema_valid), expected),
        "Input Tokens": sum(usage.get("input_tokens", usage.get("prompt_tokens", 0)) for usage in usages),
        "Output Tokens": sum(usage.get("output_tokens", usage.get("completion_tokens", 0)) for usage in usages),
        "Actual Total Cost": sum(costs) if costs and all(cost is not None for cost in costs) else None,
        "Reported Cost Sum": sum(row["reported_cost_sum"] for row in run_rows if row.get("reported_cost_sum") is not None),
        "Budget-Accounted Cost": sum(row.get("budget_accounted_cost", 0.0) for row in run_rows),
        "Raw Calls": sum(row.get("retry_count", 0) + 1 for row in run_rows),
        "Errors": {
            error_type: sum(row.get("error_type") == error_type for row in run_rows)
            for error_type in sorted({row["error_type"] for row in run_rows if row.get("error_type")})
        },
        "p50 Latency": _percentile(latencies, 0.50),
        "p95 Latency": _percentile(latencies, 0.95),
        "Confidence": {
            "count": len(confidences),
            "mean": sum(confidences) / len(confidences) if confidences else None,
            "min": min(confidences) if confidences else None,
            "max": max(confidences) if confidences else None,
        },
    }


def _write_json_atomic(path: Path, value: dict) -> None:
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _pending_jobs(jobs: list[dict], rows: list[dict]) -> list[dict]:
    terminal = {
        (row["model_id"], row["case_id"], row["run_index"])
        for row in rows
        if row.get("status") == "complete" or row.get("error_type") == "ValidationError"
    }
    return [
        job for job in jobs
        if (job["model_id"], job["case_id"], job["run_index"]) not in terminal
    ]


def execute_jobs(
    jobs: list[dict],
    items_by_id: dict[str, dict],
    output: Path,
    *,
    call,
    max_usd: float,
    input_price_per_token: float,
    max_seconds: float = 7200.0,
    clock=time.monotonic,
) -> dict:
    """추정 비용으로 다음 job을 차단하고 보고 비용이 초과하면 즉시 멈춘다."""
    if not math.isfinite(max_usd) or max_usd <= 0:
        raise ValueError("max_usd는 유한한 양수여야 합니다")
    if not math.isfinite(input_price_per_token) or input_price_per_token < 0:
        raise ValueError("input_price_per_token은 유한한 0 이상의 수여야 합니다")
    if not math.isfinite(max_seconds) or max_seconds <= 0:
        raise ValueError("max_seconds는 유한한 양수여야 합니다")
    output = Path(output)
    existing = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {"rows": []}
    rows = list(existing.get("rows", []))
    spent = sum(
        row.get("budget_accounted_cost", (row.get("usage") or {}).get("cost") or 0.0)
        for row in rows
    )
    if not math.isfinite(spent) or spent < 0:
        raise ValueError("기존 비용 기록이 유효하지 않습니다")
    provider_failures = 0
    for previous in reversed(rows):
        if previous.get("status") != "error" or previous.get("error_type") == "ValidationError":
            break
        provider_failures += 1
    started = clock()
    status = "complete"
    for job in _pending_jobs(jobs, rows):
        if provider_failures >= 3:
            status = "provider_stopped"
            break
        if clock() - started >= max_seconds:
            status = "time_stopped"
            break
        item = items_by_id[job["case_id"]]
        request_bytes = json.dumps(build_request(item["input"]), ensure_ascii=False).encode("utf-8")
        estimated_tokens = max(1, len(request_bytes) // 2)
        reservation = estimated_tokens * input_price_per_token * 3
        if spent >= max_usd or spent + reservation > max_usd:
            status = "budget_stopped"
            break
        row = run_job(job, item, call=call)
        reported_cost = row.get("reported_cost_sum")
        row["budget_accounted_cost"] = reported_cost if reported_cost is not None else reservation
        rows.append(row)
        spent += row["budget_accounted_cost"]
        result = {"status": "incomplete", "budget_accounted_cost": spent, "rows": rows}
        _write_json_atomic(output, result)
        if spent > max_usd:
            status = "budget_exceeded"
            break
        if row.get("error_type") == "JevProviderMismatch":
            status = "provider_stopped"
            break
        provider_failures = provider_failures + 1 if row.get("status") == "error" and row.get("error_type") != "ValidationError" else 0
        if provider_failures >= 3:
            status = "provider_stopped"
            break
    else:
        status = "complete" if all(row.get("status") == "complete" for row in rows) else "complete_with_errors"
    result = {"status": status, "budget_accounted_cost": spent, "rows": rows}
    _write_json_atomic(output, result)
    return result


def live_preflight(catalog_get=None) -> dict:
    """현재 model catalog에서 pinned Jev의 일반·ZDR 노출을 확인한다."""
    found = {}
    catalog_get = catalog_get or llm.evaluation_decisions_catalog
    for label, zdr in (("catalog", False), ("zdr", True)):
        models = catalog_get(zdr=zdr)
        found[label] = next((model for model in models if model.get("id") == MODEL_ID), None)
        if found[label] is None:
            raise ValueError(f"{label}에서 {MODEL_ID}를 찾지 못했습니다")
    return found


def _load_live_context(output: Path) -> tuple[dict, list[dict], dict[str, dict]]:
    manifest_path = Path(output) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    current = create_manifest(run_index=manifest.get("run_index", 1))
    for key in ("model", "dataset_sha256", "dataset_count", "runs_per_case", "provider_policy", "question_contract_sha256", "jobs"):
        if manifest.get(key) != current.get(key):
            raise ValueError(f"live 실행 전 manifest {key} 불일치")
    if manifest.get("run_index", 1) != current["run_index"]:
        raise ValueError("live 실행 전 manifest run_index 불일치")
    items = load_frozen_dataset(DATASET, FROZEN)
    return manifest, items, {item["id"]: item for item in items}


def _decision_call(provider: str | None, timeout: float):
    def call(user_input: str) -> dict:
        payload = llm.evaluation_decision(build_request(user_input, provider), timeout=timeout)
        if not matches_requested_model(payload.get("model")) or not payload.get("provider") or (provider and payload["provider"] != provider):
            raise JevProviderMismatch(payload)
        return payload
    return call


def matches_requested_model(actual_model: object) -> bool:
    """요청한 1.14 ID 또는 OpenRouter가 돌려주는 날짜 고정 snapshot만 허용한다."""
    return isinstance(actual_model, str) and bool(
        re.fullmatch(rf"{re.escape(MODEL_ID)}(?:-\d{{8}})?", actual_model)
    )


def smoke(
    output: Path,
    *,
    max_usd: float,
    input_price_per_token: float,
    timeout: float,
) -> dict:
    """첫 문항으로 endpoint·model·provider·typed-answer 계약을 확인한다."""
    if not math.isfinite(max_usd) or max_usd <= 0:
        raise ValueError("max_usd는 유한한 양수여야 합니다")
    if not math.isfinite(input_price_per_token) or input_price_per_token < 0:
        raise ValueError("input_price_per_token은 유한한 0 이상의 수여야 합니다")
    manifest, _, items_by_id = _load_live_context(output)
    job = manifest["jobs"][0]
    request_bytes = json.dumps(
        build_request(items_by_id[job["case_id"]]["input"]),
        ensure_ascii=False,
    ).encode("utf-8")
    estimated_tokens = max(1, len(request_bytes) // 2)
    if estimated_tokens * input_price_per_token * 3 > max_usd:
        raise ValueError("smoke 3회 시도 예약 비용이 --max-usd를 초과합니다")
    row = run_job(job, items_by_id[job["case_id"]], call=_decision_call(None, timeout))
    called = matches_requested_model(row.get("actual_model")) and bool(row.get("provider"))
    status = "complete" if row.get("status") == "complete" and called else (
        "schema_error" if row.get("error_type") == "ValidationError" and called else "error"
    )
    reported_cost = row.get("reported_cost_sum")
    if reported_cost is not None and reported_cost > max_usd:
        status = "budget_exceeded"
    result = {
        "status": status,
        "model_id": MODEL_ID,
        "actual_model": row.get("actual_model"),
        "provider": row.get("provider"),
        "error_type": row.get("error_type"),
        "usage": row.get("usage"),
        "reported_cost_sum": reported_cost,
    }
    _write_json_atomic(Path(output) / "smoke.json", result)
    return result


def run_all(
    output: Path,
    *,
    max_usd: float,
    input_price_per_token: float,
    timeout: float,
    max_seconds: float = 7200.0,
) -> dict:
    """smoke가 확인한 provider에 고정해 70개 job을 실행한다."""
    manifest, _, items_by_id = _load_live_context(output)
    smoke_path = Path(output) / "smoke.json"
    smoke_result = json.loads(smoke_path.read_text(encoding="utf-8"))
    if smoke_result.get("status") not in {"complete", "schema_error"}:
        raise ValueError("호출이 확인된 smoke가 필요합니다")
    if not matches_requested_model(smoke_result.get("actual_model")) or not smoke_result.get("provider"):
        raise ValueError("smoke의 exact model·provider evidence가 부족합니다")
    result = execute_jobs(
        manifest["jobs"],
        items_by_id,
        Path(output) / "rows.json",
        call=_decision_call(smoke_result["provider"], timeout),
        max_usd=max_usd,
        input_price_per_token=input_price_per_token,
        max_seconds=max_seconds,
    )
    summary = summarize(result["rows"], items_by_id, run_index=manifest.get("run_index", 1))
    _write_json_atomic(Path(output) / "summary.json", summary)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("output", type=Path)
    plan.add_argument("--run-index", type=int, choices=(1, 2, 3), default=1)
    for name in ("smoke", "run"):
        live = commands.add_parser(name)
        live.add_argument("output", type=Path)
        live.add_argument("--max-usd", type=float, required=True)
        live.add_argument("--timeout", type=float, default=45.0)
        live.add_argument("--max-seconds", type=float, default=7200.0)
        live.add_argument("--confirm-live", action="store_true")
    return parser


def main(argv=None) -> int:
    """오프라인 plan과 명시적으로 승인된 향후 live 명령을 구분한다."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command == "plan":
        args.output.mkdir(parents=True, exist_ok=False)
        manifest = create_manifest(run_index=args.run_index)
        _write_json_atomic(args.output / "manifest.json", manifest)
        print(json.dumps({"status": "prepared", "model": MODEL_ID, "jobs": len(manifest["jobs"])}, ensure_ascii=False))
        return 0
    if not args.confirm_live:
        parser.error("live API 호출에는 --confirm-live가 필요합니다")
    if not os.getenv("OPENROUTER_API_KEY"):
        parser.error("OPENROUTER_API_KEY가 필요합니다")
    if any(not math.isfinite(value) or value <= 0 for value in (args.max_usd, args.timeout, args.max_seconds)):
        parser.error("--max-usd, --timeout, --max-seconds는 유한한 양수여야 합니다")
    catalog = live_preflight()
    prompt_price = float(catalog["catalog"].get("pricing", {}).get("prompt", 0.0))
    if not math.isfinite(prompt_price) or prompt_price <= 0:
        parser.error("현재 input token 가격을 확인할 수 없습니다")
    if args.command == "smoke":
        result = smoke(
            args.output,
            max_usd=args.max_usd,
            input_price_per_token=prompt_price,
            timeout=args.timeout,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] in {"complete", "schema_error"} else 1
    result = run_all(
        args.output,
        max_usd=args.max_usd,
        input_price_per_token=prompt_price,
        timeout=args.timeout,
        max_seconds=args.max_seconds,
    )
    print(json.dumps({"status": result["status"], "rows": len(result["rows"])}, ensure_ascii=False))
    return 0 if result["status"] in {"complete", "complete_with_errors"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
