"""수퍼바이저 후보 5종을 동결 v2 70문항에서 3회 비교하는 평가 실행기."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import math
import time
from itertools import combinations
from typing import Literal
from urllib.request import urlopen

from pydantic import BaseModel, ConfigDict, ValidationError

from backend.services import llm

ROOT = Path(__file__).resolve().parents[2]

CANDIDATE_MODELS = (
    "anthropic/claude-haiku-5.5",
    "openai/gpt-6-luna",
    "deepseek/deepseek-v4.1-flash",
    "meta/muse-glimmer-30b",
    "cohere/command-a-plus",
)

PROVIDER_POLICY = {
    "zdr": True,
    "data_collection": "deny",
    "allow_fallbacks": False,
    "require_parameters": True,
}

SYSTEM_PROMPT = """너는 SojaFit의 수퍼바이저다. 사용자 입력을 읽고 답을 생성하지 말고 다음 실행 경로만 정한다.

question_type:
- out_of_scope: 다이오드 외 부품 선택, 가격·재고·주문, 펌웨어 수정 등 서비스 범위 밖
- role: 회로 안 대상 다이오드의 역할·연결·전류 경로 질문
- candidate_find: 대체 다이오드 후보를 찾아 달라는 질문이며 후보 품번이 없음
- candidate_judge: 특정 후보 품번을 그 자리에 쓸 수 있는지 묻는 질문
- rating: 특정 다이오드 품번의 정격·특성·시험 조건·패키지·개정판 질문
- insufficient_information: 필요한 대상이나 조건이 없어 위 분류와 안전한 다음 작업을 정할 수 없음

required_evidence에는 필요한 근거만 circuit, datasheet, approved_case 중에서 고른다.
next_action은 circuit_agent, search_agent, judge_answer_agent, refuse 중 하나다.
범위 밖이면 refuse, 역할이면 circuit_agent, 검색 근거가 필요하면 search_agent를 고른다.
judge_answer_agent는 검색 근거가 준비된 뒤 대체 가능 판정·인용 답을 만드는 단계가 필요할 때만 고른다.
reason_code는 question_type과 대응하는 OUT_OF_SCOPE, ROLE, CANDIDATE_FIND, CANDIDATE_JUDGE, RATING,
INSUFFICIENT_INFORMATION 중 하나만 쓴다. 입력의 품번·수치·극성·조건을 바꾸거나 추측하지 않는다.
"""


class SupervisorDecision(BaseModel):
    """후보 모델 모두가 따라야 하는 수퍼바이저 평가 출력 계약."""
    model_config = ConfigDict(extra="forbid")

    question_type: Literal[
        "out_of_scope", "role", "candidate_find", "candidate_judge", "rating", "insufficient_information",
    ]
    required_evidence: list[Literal["circuit", "datasheet", "approved_case"]]
    next_action: Literal["circuit_agent", "search_agent", "judge_answer_agent", "refuse"]
    reason_code: Literal[
        "OUT_OF_SCOPE", "ROLE", "CANDIDATE_FIND", "CANDIDATE_JUDGE", "RATING",
        "INSUFFICIENT_INFORMATION",
    ]


def build_plan(items: list[dict], runs: int = 3) -> list[dict]:
    """모든 model·case·run 조합의 고유 실행 계획을 만든다."""
    return [
        {"model_id": model_id, "case_id": item["id"], "run_index": run_index}
        for model_id in CANDIDATE_MODELS
        for item in items
        for run_index in range(1, runs + 1)
    ]


def build_pairwise_plan(items: list[dict]) -> list[dict]:
    """5개 후보의 모든 쌍·70문항·A/B 위치 교환 계획 1,400개를 만든다."""
    return [
        {"case_id": item["id"], "model_a": left, "model_b": right, "position": position}
        for left, right in combinations(CANDIDATE_MODELS, 2)
        for item in items
        for position in ("AB", "BA")
    ]


def build_robustness_plan(items: list[dict]) -> list[dict]:
    """입력 내부를 바꾸지 않고 앞뒤 빈 줄만 더한 결정적 robustness 계획을 만든다."""
    return [
        {"case_id": item["id"], "perturbation": "surrounding_blank_lines",
         "perturbed_input": f"\n\n{item['input']}\n\n"}
        for item in items
    ]


def load_frozen_dataset(dataset: Path, frozen_path: Path) -> list[dict]:
    """동결 기록과 hash·건수가 같은 JSONL 평가셋만 읽는다."""
    dataset = Path(dataset)
    frozen = json.loads(Path(frozen_path).read_text(encoding="utf-8"))[dataset.name]
    if hashlib.sha256(dataset.read_bytes()).hexdigest() != frozen["sha256"]:
        raise ValueError("동결 평가셋 해시 불일치")
    items = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(items) != frozen["count"]:
        raise ValueError("동결 평가셋 건수 불일치")
    return items


def create_manifest(dataset: Path, frozen_path: Path) -> dict:
    """동결 v2에서 정답 본문 없이 재현 가능한 1,050-job manifest를 만든다."""
    dataset = Path(dataset)
    items = load_frozen_dataset(dataset, frozen_path)
    code_files = ("backend/services/llm.py", "evals/runners/run_supervisor_models.py")
    return {
        "dataset": dataset.name,
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "dataset_count": len(items),
        "models": list(CANDIDATE_MODELS),
        "runs_per_case": 3,
        "provider_policy": PROVIDER_POLICY,
        "prompt_sha256": hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest(),
        "code_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in code_files},
        "jobs": build_plan(items),
    }


def pending_jobs(plan: list[dict], rows: list[dict]) -> list[dict]:
    """완료·schema 실패 job은 확정하고 호출 전에 예산으로 막힌 job만 재개한다."""
    terminal = {
        (row["model_id"], row["case_id"], row["run_index"])
        for row in rows
        if row.get("status") == "complete" or row.get("error_type") == "ValidationError"
    }
    return [
        job for job in plan
        if (job["model_id"], job["case_id"], job["run_index"]) not in terminal
    ]


def run_job(job: dict, item: dict, *, call=llm.evaluation_chat, clock=time.monotonic,
            max_tokens: int = 256, timeout: float = 45.0, provider_policy: dict | None = None) -> dict:
    """한 job을 실행하고 gold나 예외 원문 없이 저장 가능한 row를 만든다."""
    started = clock()
    base = {key: job[key] for key in ("model_id", "case_id", "run_index")}
    format_attempts = []
    for attempt in range(3):
        try:
            decision, metadata = call(
                job["model_id"], SYSTEM_PROMPT, item["input"], SupervisorDecision,
                provider_policy=provider_policy or PROVIDER_POLICY, max_tokens=max_tokens, timeout=timeout,
            )
            return {
                **base,
                "status": "complete",
                "decision": decision.model_dump(),
                "retry_count": attempt,
                "latency_seconds": clock() - started,
                "response_id": metadata.get("response_id"),
                "actual_model": metadata.get("actual_model"),
                "provider": metadata.get("provider"),
                "finish_reason": metadata.get("finish_reason"),
                "usage": metadata.get("usage"),
            }
        except (ValidationError, llm.EvaluationFormatError) as error:
            metadata = getattr(error, "metadata", {})
            format_attempts.append(metadata)
            if attempt < 2:
                continue
            return {**base, "status": "error", "error_type": "ValidationError",
                    "retry_count": attempt, "latency_seconds": clock() - started,
                    "provider": metadata.get("provider"), "actual_model": metadata.get("actual_model"),
                    "finish_reason": metadata.get("finish_reason"),
                    "attempt_usages": [row.get("usage") for row in format_attempts]}
        except Exception as error:
            return {**base, "status": "error", "error_type": type(error).__name__,
                    "retry_count": attempt, "latency_seconds": clock() - started}
    raise AssertionError("unreachable")


def _write_json_atomic(path: Path, value: dict) -> None:
    """중단돼도 기존 JSON이 깨지지 않게 임시 파일을 바꿔치기한다."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def execute_jobs(jobs: list[dict], items_by_id: dict[str, dict], output: Path, *,
                 call=llm.evaluation_chat, provider_policy: dict | None = None,
                 budget: llm.EvaluationBudget | None = None, prior_raw_calls: int = 0,
                 prior_reserved_usd: float = 0.0, expected_provider: str | None = None,
                 provider_error_limit: int = 3) -> dict:
    """미완료 job을 순차 실행하고 매 job 뒤 결과를 원자적으로 저장한다."""
    output = Path(output)
    result = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {
        "status": "incomplete", "rows": [],
    }
    consecutive_provider_errors = 0
    for job in pending_jobs(jobs, result["rows"]):
        row = run_job(job, items_by_id[job["case_id"]], call=call, provider_policy=provider_policy)
        result["rows"].append(row)
        if budget is not None:
            result["budget_progress"] = {
                "cumulative_raw_calls": prior_raw_calls + budget.calls,
                "cumulative_reserved_usd": prior_reserved_usd + budget.reserved_usd,
            }
        if row.get("error_type") == "EvaluationLimitError":
            result["status"] = "budget_stopped"
            _write_json_atomic(output, result)
            return result
        if row.get("status") == "complete":
            consecutive_provider_errors = 0
            if expected_provider and row.get("provider") != expected_provider:
                result["status"] = "provider_stopped"
                result["stop_reason"] = {"error_type": "ProviderChanged", "consecutive": 1}
                _write_json_atomic(output, result)
                return result
        elif row.get("error_type") != "ValidationError":
            consecutive_provider_errors += 1
            if consecutive_provider_errors >= provider_error_limit:
                result["status"] = "provider_stopped"
                result["stop_reason"] = {
                    "error_type": row.get("error_type"), "consecutive": consecutive_provider_errors,
                }
                _write_json_atomic(output, result)
                return result
        _write_json_atomic(output, result)
    has_errors = any(row.get("status") == "error" and row.get("error_type") != "EvaluationLimitError"
                     for row in result["rows"])
    result["status"] = "complete_with_errors" if has_errors else "complete"
    _write_json_atomic(output, result)
    return result


def _percentile(values: list[float], fraction: float) -> float | None:
    """nearest-rank 방식의 백분위수를 돌려준다."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def summarize(rows: list[dict], items_by_id: dict[str, dict]) -> dict:
    """객관 label이 있는 출력만 accuracy로, 모든 완결 3회 묶음은 stability로 집계한다."""
    latest = {}
    for row in rows:
        latest[(row["case_id"], row["run_index"])] = row
    complete = [row for row in latest.values() if row.get("status") == "complete"]
    labeled_items = {case_id: item for case_id, item in items_by_id.items() if item.get("question_type")}
    unscored_ids = sorted(case_id for case_id, item in items_by_id.items() if not item.get("question_type"))

    def rate(numerator, denominator):
        return {"numerator": numerator, "denominator": denominator,
                "value": numerator / denominator if denominator else None}

    accuracy_runs, macro_runs, per_class_runs = {}, {}, {}
    classes = sorted({item["question_type"] for item in labeled_items.values()})
    for run_index in (1, 2, 3):
        predictions = {
            case_id: latest[(case_id, run_index)]["decision"]["question_type"]
            for case_id in labeled_items
            if latest.get((case_id, run_index), {}).get("status") == "complete"
        }
        correct = sum(predictions.get(case_id) == item["question_type"] for case_id, item in labeled_items.items())
        accuracy_runs[str(run_index)] = rate(correct, len(labeled_items))
        class_scores = {}
        for label in classes:
            tp = sum(predictions.get(case_id) == label and item["question_type"] == label
                     for case_id, item in labeled_items.items())
            fp = sum(predictions.get(case_id) == label and item["question_type"] != label
                     for case_id, item in labeled_items.items())
            fn = sum(predictions.get(case_id) != label and item["question_type"] == label
                     for case_id, item in labeled_items.items())
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / (tp + fn) if tp + fn else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            class_scores[label] = {"precision": precision, "recall": recall, "f1": f1,
                                   "tp": tp, "fp": fp, "fn": fn}
        per_class_runs[str(run_index)] = class_scores
        macro_runs[str(run_index)] = sum(score["f1"] for score in class_scores.values()) / len(classes) if classes else None

    grouped = {case_id: [latest.get((case_id, run_index)) for run_index in (1, 2, 3)] for case_id in items_by_id}
    complete_groups = {case_id: group for case_id, group in grouped.items()
                       if all(row and row.get("status") == "complete" for row in group)}
    stable = sum(len({json.dumps(row["decision"], sort_keys=True) for row in group}) == 1
                 for group in complete_groups.values())
    type_flips = sum(len({row["decision"]["question_type"] for row in group}) > 1
                     for group in complete_groups.values())
    action_flips = sum(len({row["decision"]["next_action"] for row in group}) > 1
                       for group in complete_groups.values())
    expected_outputs = len(items_by_id) * 3
    usages = [usage or {} for row in rows for usage in ([row.get("usage")] if "attempt_usages" not in row
              else row.get("attempt_usages", []))]
    costs = [usage.get("cost") for usage in usages]
    latencies = [float(row["latency_seconds"]) for row in rows if row.get("latency_seconds") is not None]
    accuracy_values = [entry["value"] for entry in accuracy_runs.values() if entry["value"] is not None]
    macro_values = [value for value in macro_runs.values() if value is not None]

    return {
        "Question Type Accuracy": {"per_run": accuracy_runs,
                                   "mean": sum(accuracy_values) / len(accuracy_values) if accuracy_values else None,
                                   "min": min(accuracy_values) if accuracy_values else None,
                                   "max": max(accuracy_values) if accuracy_values else None,
                                   "scored_unique_cases": len(labeled_items)},
        "Question Type Macro-F1": {"per_run": macro_runs,
                                   "mean": sum(macro_values) / len(macro_values) if macro_values else None,
                                   "min": min(macro_values) if macro_values else None,
                                   "max": max(macro_values) if macro_values else None},
        "Question Type Per-Class": {"per_run": per_class_runs},
        "Known Limitation": {"unscored_case_count": len(unscored_ids), "unscored_case_ids": unscored_ids,
                             "reason": "question_type gold 없음; 70문항 실행은 유지하되 objective score에서 제외"},
        "Completion Rate": rate(len(complete), expected_outputs),
        "Three-Run Exact Agreement": rate(stable, len(items_by_id)),
        "Incomplete Three-Run Case Count": len(items_by_id) - len(complete_groups),
        "Question Type Flip Rate": rate(type_flips, len(items_by_id)),
        "Next Action Flip Rate": rate(action_flips, len(items_by_id)),
        "Input Tokens": sum(usage.get("prompt_tokens", usage.get("input_tokens", 0)) for usage in usages),
        "Output Tokens": sum(usage.get("completion_tokens", usage.get("output_tokens", 0)) for usage in usages),
        "Actual Total Cost": sum(costs) if costs and all(cost is not None for cost in costs) else None,
        "p50 Latency": _percentile(latencies, 0.50),
        "p95 Latency": _percentile(latencies, 0.95),
    }


def _smoke_path(run_dir: Path, model_id: str) -> Path:
    return Path(run_dir) / f"smoke_{model_id.replace('/', '__')}.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_call_evidence(source_dir: Path, model_id: str, source_manifest: dict) -> tuple[Path, dict] | None:
    """과거 smoke 또는 본 실행 row에서 exact model·provider 호출 증거 한 건을 찾는다."""
    smoke_path = _smoke_path(source_dir, model_id)
    if smoke_path.exists():
        smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
        if (smoke.get("status") in {"complete", "schema_error"}
                and smoke.get("model_id") == model_id and smoke.get("actual_model") == model_id
                and smoke.get("provider")
                and smoke.get("manifest_prompt_sha256") == source_manifest.get("prompt_sha256")
                and smoke.get("manifest_code_sha256") == source_manifest.get("code_sha256")):
            return smoke_path, {"provider": smoke["provider"], "actual_model": model_id, "source_kind": "smoke"}
    rows_path = Path(source_dir) / f"rows_{model_id.replace('/', '__')}.json"
    if not rows_path.exists():
        return None
    result = json.loads(rows_path.read_text(encoding="utf-8"))
    for row in result.get("rows", []):
        if (row.get("model_id") == model_id and row.get("actual_model") == model_id and row.get("provider")
                and (row.get("status") == "complete" or row.get("error_type") == "ValidationError")):
            return rows_path, {"provider": row["provider"], "actual_model": model_id, "source_kind": "main_test_row"}
    return None


def import_provider_evidence(run_dir: Path, source_dir: Path) -> dict:
    """API 없이 과거 exact-model 호출 증거를 hash 고정된 provider evidence로 가져온다."""
    run_dir, source_dir = Path(run_dir).resolve(), Path(source_dir).resolve()
    target_manifest_path, source_manifest_path = run_dir / "manifest.json", source_dir / "manifest.json"
    target_manifest = json.loads(target_manifest_path.read_text(encoding="utf-8"))
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    for key in ("dataset_sha256", "prompt_sha256", "provider_policy"):
        if source_manifest.get(key) != target_manifest.get(key):
            raise ValueError(f"provider evidence {key} 불일치")
    evidence_path = run_dir / "provider_evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8")) if evidence_path.exists() else {
        "target_dataset_sha256": target_manifest["dataset_sha256"],
        "target_prompt_sha256": target_manifest["prompt_sha256"],
        "target_code_sha256": target_manifest["code_sha256"],
        "models": {},
    }
    if (evidence.get("target_dataset_sha256") != target_manifest["dataset_sha256"]
            or evidence.get("target_prompt_sha256") != target_manifest["prompt_sha256"]
            or evidence.get("target_code_sha256") != target_manifest["code_sha256"]):
        raise ValueError("provider evidence 대상 manifest 불일치")
    for model_id in CANDIDATE_MODELS:
        found = _source_call_evidence(source_dir, model_id, source_manifest)
        if not found:
            continue
        artifact_path, details = found
        evidence["models"][model_id] = {
            **details,
            "source_manifest": str(source_manifest_path),
            "source_manifest_sha256": _sha256(source_manifest_path),
            "source_artifact": str(artifact_path),
            "source_artifact_sha256": _sha256(artifact_path),
        }
    _write_json_atomic(evidence_path, evidence)
    return evidence


def verified_provider(run_dir: Path, model_id: str, manifest: dict) -> str:
    """현재 smoke 또는 원본 hash가 유지된 과거 호출 evidence에서 고정 provider를 확인한다."""
    smoke_path = _smoke_path(run_dir, model_id)
    if smoke_path.exists():
        smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
        if (smoke.get("status") in {"complete", "schema_error"} and smoke.get("provider")
                and smoke.get("actual_model") == model_id
                and smoke.get("manifest_prompt_sha256") == manifest["prompt_sha256"]
                and smoke.get("manifest_code_sha256") == manifest["code_sha256"]):
            return smoke["provider"]
    evidence_path = Path(run_dir) / "provider_evidence.json"
    if not evidence_path.exists():
        raise ValueError("성공한 smoke 또는 검증된 provider evidence가 필요합니다")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if (evidence.get("target_dataset_sha256") != manifest["dataset_sha256"]
            or evidence.get("target_prompt_sha256") != manifest["prompt_sha256"]
            or evidence.get("target_code_sha256") != manifest["code_sha256"]):
        raise ValueError("provider evidence 대상 manifest 불일치")
    entry = evidence.get("models", {}).get(model_id)
    if not entry:
        raise ValueError("성공한 smoke 또는 검증된 provider evidence가 필요합니다")
    source_manifest_path = Path(entry["source_manifest"])
    source_artifact_path = Path(entry["source_artifact"])
    if (_sha256(source_manifest_path) != entry["source_manifest_sha256"]
            or _sha256(source_artifact_path) != entry["source_artifact_sha256"]):
        raise ValueError("provider evidence 원본 hash 불일치")
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    found = _source_call_evidence(source_artifact_path.parent, model_id, source_manifest)
    if not found or found[0].resolve() != source_artifact_path.resolve() or found[1]["provider"] != entry["provider"]:
        raise ValueError("provider evidence 원본 내용 불일치")
    return entry["provider"]


def run_model(run_dir: Path, model_id: str, *, max_usd: float, prompt_rate: float,
              completion_rate: float, max_seconds: float, max_tokens: int = 256,
              require_smoke: bool = False, run_indices: tuple[int, ...] | None = None) -> dict:
    """manifest에서 model 하나의 job만 골라 평가 예산 안에서 실행·재개한다."""
    if model_id not in CANDIDATE_MODELS:
        raise ValueError("등록되지 않은 수퍼바이저 후보")
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("provider_policy") != PROVIDER_POLICY:
        raise ValueError("provider policy 불일치")
    if manifest.get("prompt_sha256") != hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest():
        raise ValueError("수퍼바이저 prompt hash 불일치")
    current_code = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("backend/services/llm.py", "evals/runners/run_supervisor_models.py")
    }
    if manifest.get("code_sha256") != current_code:
        raise ValueError("실행 code hash 불일치")
    dataset = ROOT / "evals" / manifest["dataset"]
    items = load_frozen_dataset(dataset, ROOT / "evals/FROZEN.json")
    if hashlib.sha256(dataset.read_bytes()).hexdigest() != manifest["dataset_sha256"]:
        raise ValueError("manifest 평가셋 hash 불일치")
    all_model_jobs = [job for job in manifest["jobs"] if job["model_id"] == model_id]
    jobs = all_model_jobs
    if run_indices is not None:
        selected = set(run_indices)
        if not selected or not selected <= {1, 2, 3}:
            raise ValueError("run index는 1, 2, 3 중 하나 이상이어야 합니다")
        jobs = [job for job in jobs if job["run_index"] in selected]
    output = run_dir / f"rows_{model_id.replace('/', '__')}.json"
    existing = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    progress = existing.get("budget_progress", {})
    prior_calls = int(progress.get("cumulative_raw_calls", 0))
    prior_reserved = float(progress.get("cumulative_reserved_usd", 0.0))
    remaining_usd = max_usd - prior_reserved
    remaining_calls = len(all_model_jobs) * 3 - prior_calls
    if remaining_usd <= 0 or remaining_calls <= 0:
        raise llm.EvaluationLimitError("누적 평가 예산 상한")
    expected_provider = None
    if require_smoke:
        expected_provider = verified_provider(run_dir, model_id, manifest)
    budget = llm.EvaluationBudget(
        max_calls=remaining_calls, max_usd=remaining_usd, max_seconds=max_seconds,
        prompt_rate=prompt_rate, completion_rate=completion_rate, max_tokens=max_tokens,
    )
    policy = {**PROVIDER_POLICY, "sort": "price", "max_price": {
        "prompt": round(prompt_rate * 1_000_000, 6),
        "completion": round(completion_rate * 1_000_000, 6),
    }}
    if expected_provider:
        policy["only"] = [expected_provider]
    with llm.evaluation_limits(budget):
        result = execute_jobs(
            jobs, {item["id"]: item for item in items}, output, provider_policy=policy,
            budget=budget, prior_raw_calls=prior_calls, prior_reserved_usd=prior_reserved,
            expected_provider=expected_provider,
        )
    result["budget"] = {
        "configured_max_calls": len(all_model_jobs) * 3,
        "selected_run_indices": sorted(set(job["run_index"] for job in jobs)),
        "configured_max_usd": max_usd,
        "remaining_max_calls_at_start": budget.max_calls,
        "remaining_max_usd_at_start": budget.max_usd,
        "max_seconds": budget.max_seconds,
        "max_tokens": budget.max_tokens,
        "raw_calls_this_process": budget.calls,
        "reserved_usd_this_process": budget.reserved_usd,
        "cumulative_raw_calls": prior_calls + budget.calls,
        "cumulative_reserved_usd": prior_reserved + budget.reserved_usd,
        "elapsed_seconds": time.monotonic() - budget.started,
    }
    result["summary"] = summarize(result["rows"], {item["id"]: item for item in items})
    _write_json_atomic(output, result)
    return result


def smoke_model(run_dir: Path, model_id: str, *, max_usd: float, prompt_rate: float,
                completion_rate: float, max_seconds: float, max_tokens: int = 256) -> dict:
    """full run 전에 한 건만 호출해 endpoint·schema·provider metadata를 확인한다."""
    run_dir = Path(run_dir)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    current_prompt = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()
    current_code = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in ("backend/services/llm.py", "evals/runners/run_supervisor_models.py")
    }
    if manifest.get("prompt_sha256") != current_prompt or manifest.get("code_sha256") != current_code:
        raise ValueError("smoke 실행 전 manifest hash 불일치")
    dataset = ROOT / "evals" / manifest["dataset"]
    items = load_frozen_dataset(dataset, ROOT / "evals/FROZEN.json")
    job = next(job for job in manifest["jobs"] if job["model_id"] == model_id)
    budget = llm.EvaluationBudget(3, max_usd, max_seconds, prompt_rate, completion_rate, max_tokens=max_tokens)
    policy = {**PROVIDER_POLICY, "sort": "price", "max_price": {
        "prompt": round(prompt_rate * 1_000_000, 6), "completion": round(completion_rate * 1_000_000, 6),
    }}
    with llm.evaluation_limits(budget):
        row = run_job(job, {item["id"]: item for item in items}[job["case_id"]], provider_policy=policy,
                      max_tokens=max_tokens)
    smoke_status = "complete" if row["status"] == "complete" else (
        "schema_error" if row.get("error_type") == "ValidationError" and row.get("provider") else "error"
    )
    result = {
        "status": smoke_status,
        "model_id": model_id, "provider": row.get("provider"), "actual_model": row.get("actual_model"),
        "error_type": row.get("error_type") or (None if row.get("provider") else "ProviderMetadataMissing"),
        "manifest_prompt_sha256": manifest["prompt_sha256"],
        "manifest_code_sha256": manifest["code_sha256"],
    }
    _write_json_atomic(_smoke_path(run_dir, model_id), result)
    return result


def _catalog_model(model_id: str, *, zdr: bool) -> dict | None:
    """OpenRouter 공개 catalog에서 model 한 건을 찾는다(평가 입력·키를 보내지 않는다)."""
    suffix = "?zdr=true" if zdr else ""
    with urlopen(f"https://openrouter.ai/api/v1/models{suffix}", timeout=30) as response:
        return next((row for row in json.load(response)["data"] if row["id"] == model_id), None)


def main(argv=None) -> int:
    """API 없는 plan 명령 또는 model 하나의 유료 run 명령을 처리한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("output", type=Path)
    evidence_parser = commands.add_parser("import-evidence")
    evidence_parser.add_argument("output", type=Path)
    evidence_parser.add_argument("--source", type=Path, required=True)
    for name in ("smoke", "run"):
        live_parser = commands.add_parser(name)
        live_parser.add_argument("output", type=Path)
        live_parser.add_argument("--model", required=True, choices=CANDIDATE_MODELS)
        live_parser.add_argument("--max-usd", type=float, required=True)
        live_parser.add_argument("--max-seconds", type=float, default=7200)
        live_parser.add_argument("--max-tokens", type=int, default=256)
        live_parser.add_argument("--run-index", type=int, action="append", choices=(1, 2, 3))
        live_parser.add_argument("--confirm-live", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "plan":
        args.output.mkdir(parents=True, exist_ok=False)
        manifest = create_manifest(ROOT / "evals/dataset_v2.jsonl", ROOT / "evals/FROZEN.json")
        _write_json_atomic(args.output / "manifest.json", manifest)
        items = load_frozen_dataset(ROOT / "evals/dataset_v2.jsonl", ROOT / "evals/FROZEN.json")
        _write_json_atomic(args.output / "comparison_plans.json", {
            "pairwise": build_pairwise_plan(items),
            "robustness": build_robustness_plan(items),
            "pairwise_status": "planned_only_judge_model_and_budget_not_approved",
            "robustness_status": "planned_only_budget_not_approved",
        })
        print(json.dumps({"status": "prepared", "jobs": len(manifest["jobs"]), "output": str(args.output)}, ensure_ascii=False))
        return 0
    if args.command == "import-evidence":
        evidence = import_provider_evidence(args.output, args.source)
        print(json.dumps({"status": "imported", "models": sorted(evidence["models"])}, ensure_ascii=False))
        return 0
    if args.command in {"smoke", "run"}:
        if args.max_usd <= 0 or args.max_seconds <= 0 or args.max_tokens <= 0:
            parser.error("--max-usd, --max-seconds, --max-tokens는 양수여야 합니다")
        if not args.confirm_live:
            parser.error("live API 호출에는 --confirm-live가 필요합니다")
        if not os.getenv("OPENROUTER_API_KEY"):
            parser.error("OPENROUTER_API_KEY가 필요합니다")
        model = _catalog_model(args.model, zdr=False)
        if model is None:
            parser.error("OpenRouter 공개 catalog에 model이 없습니다")
        if _catalog_model(args.model, zdr=True) is None:
            parser.error("현재 ZDR endpoint가 없어 실행하지 않습니다")
        price = model["pricing"]
        run = smoke_model if args.command == "smoke" else run_model
        kwargs = {"max_usd": args.max_usd, "prompt_rate": float(price["prompt"]),
                  "completion_rate": float(price["completion"]), "max_seconds": args.max_seconds,
                  "max_tokens": args.max_tokens}
        if args.command == "run":
            kwargs["require_smoke"] = True
            kwargs["run_indices"] = tuple(args.run_index) if args.run_index else None
        result = run(args.output, args.model, **kwargs)
        print(json.dumps({"status": result["status"], "model": args.model,
                          "rows": len(result.get("rows", [])), "budget": result.get("budget")}, ensure_ascii=False))
        return 0 if result["status"] == "complete" else 1
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(main())
