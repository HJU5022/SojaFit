"""추가 API 호출 없이 수퍼바이저 1~3차 원시 행을 대조하고 3차 집계를 만든다."""

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODELS = (
    "anthropic/claude-haiku-5.5", "openai/gpt-6-luna",
    "deepseek/deepseek-v4.1-flash", "meta/muse-glimmer-30b",
    "cohere/command-a-plus", "typesafe/jev-1.14",
)
FIVE_DIRS = ("2026-11-04-stage1-v1", "2026-11-05-stage2-five-v1", "2026-11-05-stage3-five-v1")
JEV_DIRS = ("2026-11-04-jev-stage1-ready-v1", "2026-11-05-jev-stage2-v1", "2026-11-05-jev-stage3-v1")


def rate(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def percentile(values, fraction):
    values = sorted(values)
    return values[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def source_digest(path):
    """기존 회차는 LF 정규화, 바이트 보존한 3차 파일은 원시 hash로 식별한다."""
    path = Path(path)
    data = path.read_bytes()
    if path.parent.name in (*FIVE_DIRS[:2], *JEV_DIRS[:2]):
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def latest_rows(result, items, model, run_index):
    latest = {}
    for row in result["rows"]:
        if row["case_id"] not in items or row["model_id"] != model or row["run_index"] != run_index:
            raise ValueError("원시 행의 model/case/run_index 불일치")
        latest[row["case_id"]] = row
    return latest


def summarize_run(result, items, model, run_index):
    latest = latest_rows(result, items, model, run_index)
    valid = {key: row for key, row in latest.items()
             if row.get("status") == "complete" and isinstance(row.get("decision"), dict)}
    labeled = {key: item for key, item in items.items() if item.get("question_type")}
    predictions = {key: row["decision"]["question_type"] for key, row in valid.items()}
    correct = sum(predictions.get(key) == item["question_type"] for key, item in labeled.items())
    per_class = {}
    for label in sorted({item["question_type"] for item in labeled.values()}):
        tp = sum(predictions.get(key) == label and item["question_type"] == label for key, item in labeled.items())
        fp = sum(predictions.get(key) == label and item["question_type"] != label for key, item in labeled.items())
        fn = sum(predictions.get(key) != label and item["question_type"] == label for key, item in labeled.items())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        per_class[label] = {"tp": tp, "fp": fp, "fn": fn,
                            "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0}
    usages = [usage or {} for row in result["rows"]
              for usage in (row["attempt_usages"] if "attempt_usages" in row else [row.get("usage")])]
    reported = sum(row["reported_cost_sum"] for row in result["rows"] if row.get("reported_cost_sum") is not None)
    if not any("reported_cost_sum" in row for row in result["rows"]):
        reported = sum(usage.get("cost") or 0.0 for usage in usages)
    progress = result.get("budget_progress", {})
    calls = progress.get("cumulative_raw_calls", sum(row.get("retry_count", 0) + 1 for row in result["rows"]))
    accounted = progress.get("cumulative_reserved_usd", result.get("budget_accounted_cost"))
    out_of_scope = {key: row for key, row in valid.items() if row["decision"]["question_type"] == "out_of_scope"}
    inconsistent = {key: row["decision"]["next_action"] for key, row in out_of_scope.items()
                    if row["decision"]["next_action"] != "refuse"}
    latencies = [row["latency_seconds"] for row in latest.values() if row.get("latency_seconds") is not None]
    terminal = [row for row in latest.values() if row.get("error_type") != "EvaluationLimitError"]
    attempted = [row for row in latest.values()
                 if row.get("error_type") != "EvaluationLimitError" or row.get("retry_count", 0) > 0]
    format_failures = [row for row in latest.values() if row.get("error_type") == "ValidationError"]
    failure_usages = [usage for row in format_failures for usage in row.get("attempt_usages", []) if usage]
    return {
        "status": result.get("status"),
        "score_status": "complete" if len(terminal) == len(items) else "partial_not_comparable",
        "Attempted Outputs": rate(len(attempted), len(items)),
        "Completion Rate": rate(len(terminal), len(items)),
        "Schema Valid Rate": rate(len(valid), len(items)),
        "First-Pass Schema Success Rate": rate(sum(row.get("retry_count", 0) == 0 for row in valid.values()), len(items)),
        "Retry Rate": rate(sum(row.get("retry_count", 0) > 0 for row in latest.values()), len(items)),
        "API Error Rate": rate(sum(row.get("status") == "error" and row.get("error_type") not in
                                    {"ValidationError", "EvaluationLimitError"} for row in latest.values()), len(items)),
        "Question Type Accuracy": rate(correct, len(labeled)),
        "Question Type Macro-F1": sum(value["f1"] for value in per_class.values()) / len(per_class),
        "Question Type Per-Class": per_class,
        "Routing Consistency": {"Predicted out_of_scope": len(out_of_scope),
                                "Inconsistent Action": rate(len(inconsistent), len(out_of_scope)),
                                "inconsistent_case_actions": inconsistent},
        "Raw Calls": calls,
        "Errors": dict(Counter(row["error_type"] for row in result["rows"] if row.get("error_type"))),
        "Reported Cost Sum": reported,
        "Budget-Accounted Cost": accounted,
        "Input Tokens (recorded)": sum(usage.get("prompt_tokens", usage.get("input_tokens", 0)) for usage in usages),
        "Output Tokens (recorded)": sum(usage.get("completion_tokens", usage.get("output_tokens", 0)) for usage in usages),
        "Reported Cost Calls": sum(usage.get("cost") is not None for usage in usages),
        "p50 Latency": percentile(latencies, .5),
        "p95 Latency": percentile(latencies, .95),
        "Providers": sorted({row["provider"] for row in result["rows"] if row.get("provider")}),
        "Actual Models": sorted({row["actual_model"] for row in result["rows"] if row.get("actual_model")}),
        "Output Limit Diagnostics": {
            "Length-Limited Validation Failures": rate(sum(row.get("finish_reason") == "length" for row in format_failures), len(format_failures)),
            "labeled_validation_failure_count": sum(key in labeled and row.get("error_type") == "ValidationError" for key, row in latest.items()),
            "validation_attempt_usage_records": len(failure_usages),
            "validation_attempts_at_256_tokens": sum(usage.get("completion_tokens", usage.get("output_tokens")) == 256 for usage in failure_usages),
        },
    }


def compare_runs(results, items, model):
    runs = [latest_rows(result, items, model, index) for index, result in enumerate(results, 1)]
    comparable, exact, type_flips, action_flips, incomplete = [], [], [], [], []
    changes = []
    for key, item in items.items():
        rows = [run.get(key) for run in runs]
        valid = [row is not None and row.get("status") == "complete" and isinstance(row.get("decision"), dict) for row in rows]
        if all(valid):
            comparable.append(key)
            decisions = [row["decision"] for row in rows]
            if len({json.dumps(decision, sort_keys=True, ensure_ascii=False) for decision in decisions}) == 1:
                exact.append(key)
            if len({decision["question_type"] for decision in decisions}) > 1:
                type_flips.append(key)
            if len({decision["next_action"] for decision in decisions}) > 1:
                action_flips.append(key)
        else:
            incomplete.append(key)
        if item.get("question_type"):
            observations = [{"status": row.get("status") if row else "missing",
                             "question_type": row.get("decision", {}).get("question_type") if row else None}
                            for row in rows]
            if observations[1] != observations[2]:
                changes.append({"case_id": key, "gold": item["question_type"], "runs": observations})
    return {
        "Comparable Three-Run Cases": rate(len(comparable), len(items)),
        "Three-Run Exact Agreement": rate(len(exact), len(comparable)),
        "Question Type Flip Rate": rate(len(type_flips), len(comparable)),
        "Next Action Flip Rate": rate(len(action_flips), len(comparable)),
        "incomplete_case_ids": incomplete,
        "question_type_flip_case_ids": type_flips,
        "next_action_flip_case_ids": action_flips,
        "stage2_to_stage3_labeled_changes": changes,
    }


def build_summary(root=ROOT):
    root = Path(root)
    dataset = root / "evals/dataset_v2.jsonl"
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    frozen = json.loads((root / "evals/FROZEN.json").read_text(encoding="utf-8"))[dataset.name]
    if digest != frozen["sha256"]:
        raise ValueError("동결 평가셋 hash 불일치")
    items = {item["id"]: item for item in (json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line)}
    if len(items) != frozen["count"]:
        raise ValueError("동결 평가셋 건수 불일치")
    summary = {"dataset_sha256": digest, "run_index": 3, "sources": {}, "models": {},
               "source_hash_policy": {"stage1_stage2": "SHA-256 after CRLF-to-LF normalization", "stage3": "SHA-256 of original bytes, preserved by .gitattributes -text"},
               "analysis_code_sha256_lf": hashlib.sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest(),
               "execution_code_sha256_lf": {
                   name: hashlib.sha256((root / name).read_bytes().replace(b"\r\n", b"\n")).hexdigest()
                   for name in ("backend/services/llm.py", "evals/runners/run_supervisor_models.py", "evals/runners/run_supervisor_jev.py")
               },
               "metric_notes": {
                   "gold": "Accuracy/Macro-F1 use 35 labeled cases; 35 unlabeled cases are not correctness-scored",
                   "routing": "Inconsistent Action is non-refuse among predicted out_of_scope valid rows",
                   "agreement": "Agreement/flip denominator includes only cases with 3 valid decisions; coverage is separate",
                   "cost": "Recorded usage and budget-accounted values are not independently verified invoices",
                   "scope": "Third measurement of the same frozen 70 cases, not an independent evaluation set",
               },
               "unscored_case_ids": [key for key, item in items.items() if not item.get("question_type")]}
    for model in MODELS:
        directories = JEV_DIRS if model == "typesafe/jev-1.14" else FIVE_DIRS
        name = "rows.json" if model == "typesafe/jev-1.14" else f"rows_{model.replace('/', '__')}.json"
        results = []
        contracts = set()
        for index, directory in enumerate(directories, 1):
            path = root / "evals/results/supervisor" / directory / name
            manifest_path = path.parent / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("dataset_sha256") != digest:
                raise ValueError("회차별 manifest dataset hash 불일치")
            contracts.add(manifest.get("prompt_sha256", manifest.get("question_contract_sha256")))
            summary["sources"][manifest_path.relative_to(root).as_posix()] = source_digest(manifest_path)
            relative = path.relative_to(root).as_posix()
            summary["sources"][relative] = source_digest(path)
            results.append(json.loads(path.read_text(encoding="utf-8")))
        if len(contracts) != 1 or None in contracts:
            raise ValueError("회차별 prompt/typed question 계약 불일치")
        summary["models"][model] = {
            "contract_sha256": next(iter(contracts)),
            "runs": {str(index): summarize_run(result, items, model, index) for index, result in enumerate(results, 1)},
            "three_run_comparison": compare_runs(results, items, model),
        }
    execution = root / "evals/results/supervisor/2026-11-05-stage3-five-v1/execution.json"
    if execution.exists():
        summary["execution"] = json.loads(execution.read_text(encoding="utf-8"))
        summary["sources"][execution.relative_to(root).as_posix()] = source_digest(execution)
    for directory in (FIVE_DIRS[2], JEV_DIRS[2]):
        for path in sorted((root / "evals/results/supervisor" / directory).glob("*.json")):
            summary["sources"][path.relative_to(root).as_posix()] = source_digest(path)
    return summary


def render_reports(summary, output, root=ROOT):
    """집계 JSON에서 상세 표와 간단 보고서를 함께 생성한다."""
    root = Path(root)
    models = summary["models"]
    metrics = {model: value["runs"]["3"] for model, value in models.items()}

    def ratio(value):
        return f'{value["numerator"]}/{value["denominator"]}' if value["denominator"] else "Not Applicable (0/0)"

    def number(value, digits=3):
        return f"{value:.{digits}f}" if value is not None else "Not Recorded"

    def table(headers, rows, meaning):
        return "\n".join(["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers),
                          *["| " + " | ".join(map(str, row)) + " |" for row in rows], "", "표 읽는 법: " + meaning, ""])

    def accuracy(value):
        return ratio(value["Question Type Accuracy"]) if value["score_status"] == "complete" else "Not Comparable (partial run)"

    total = sum(value["Budget-Accounted Cost"] or 0 for value in metrics.values())
    raw_calls = sum(value["Raw Calls"] for value in metrics.values())
    summary_hash = hashlib.sha256(Path(output).read_bytes()).hexdigest()
    summary_link = "../../" + Path(output).resolve().relative_to(root.resolve()).as_posix()
    elapsed = {event["model_id"]: event["elapsed_seconds"]
               for event in summary.get("execution", {}).get("events", []) if event["phase"] == "run"}
    heading = ["# 수퍼바이저 6종 3차 공동 평가 결과", "", "측정일: 2026-11-05 · 상태: 3차 실행 종료", "",
               "## 범위와 재계산 근거", "",
               "- 동결 v2 70문항, SHA-256 `" + summary["dataset_sha256"] + "`. 모델별 `run_index=3` 한 번만 실행했다. 유형 gold 35문항만 Accuracy·Macro-F1로 채점한다.",
               "- 사전 등록 #33: [3차 계약](../experiments/supervisor-stage3-six-models.md), 유료 호출 전 로컬 커밋 `d10a30b`. 원격 공개 시점으로 실행 전 등록을 독립 증명했다고 주장하지 않는다.",
               "- [3차 집계 JSON](" + summary_link + ") SHA-256 `" + summary_hash + "`. 1~3차 원시 파일과 3차 metadata의 hash, 모델별 수치·문항 ID를 담는다.",
               "- 출처 hash 정책: 기존 1·2차 파일은 Git checkout의 줄바꿈 차이를 제외한 LF 정규화 SHA-256을 사용한다. 3차 JSON은 .gitattributes의 -text로 원시 바이트를 보존하고 그 SHA-256을 기록한다. 기존 회차 원시 파일과 3차 호출 결과의 내용은 수정하지 않았다.",
               "- `execution.json`에 모델별 명령 인자·시작/종료 시각·process 경과 시간·종료 코드·원시 파일 hash를 보존했다. `preflight.json`에는 공개 catalog 가격·ZDR 노출·첫 문항 예약액을 기록했다.",
               "- 재계산: `uv run --no-sync python -m evals.runners.report_supervisor_stage3 evals/results/supervisor/2026-11-05-stage3-comparison-v1/stage3_summary.json`. 집계기는 API를 호출하지 않으며 두 보고서도 같은 JSON에서 생성한다.", "",
               "## PR 검토용 근거 구성", "",
               "3차 사전 등록·두 manifest·공개 catalog preflight·6종 smoke·문항별 원시 행·실행 metadata·정정 집계 JSON·이 보고서와 간단 보고서를 보존한다. 기존 모델 호출 실행기는 저장소의 `run_supervisor_models.py`·`run_supervisor_jev.py`·`backend/services/llm.py`이며 source hash는 집계 JSON에 있다. 새 `report_supervisor_stage3.py`와 `tests/evals/test_supervisor_stage3_report.py`는 분모·라우팅 오류·3회 coverage 및 2차 정정 수치의 재계산을 검증한다.", "",
               "## 3차 실측표", ""]
    main_rows = []
    for model, value in metrics.items():
        errors = ", ".join(f"{key} {count}" for key, count in value["Errors"].items()) or "없음"
        main_rows.append([f"`{model}`", ratio(value["Attempted Outputs"]), ratio(value["Completion Rate"]),
                          ratio(value["Schema Valid Rate"]), accuracy(value), number(value["Question Type Macro-F1"]),
                          value["Raw Calls"], errors, number(value["Reported Cost Sum"], 9),
                          number(value["Budget-Accounted Cost"], 9), number(value["p50 Latency"]), number(value["p95 Latency"])])
    main_table = table(["Model ID", "Attempted Outputs", "Completion Rate", "Schema Valid Rate", "Question Type Accuracy",
                        "Question Type Macro-F1", "Raw Calls", "Errors", "Reported Cost Sum (USD)", "Budget-Accounted Cost (USD)",
                        "p50 Latency (s)", "p95 Latency (s)"], main_rows,
                       "Attempted Outputs는 호출을 시도한 고유 문항 수 / 70, Completion Rate는 성공·확정 실패 행 수 / 70이다. Schema Valid Rate는 형식상 유효한 결정 수 / 70이며 라우팅 정답을 보장하지 않는다. Question Type Accuracy는 gold 35문항의 정답 수 / 35, Macro-F1은 네 gold 유형 F1의 동일 가중 평균이다. Raw Calls는 재시도 포함 호출 수, Errors는 최종 오류 종류·수다. Reported Cost Sum은 저장된 usage 비용 합계, Budget-Accounted Cost는 보고 비용과 미보고 호출 예약액의 관리값이다. p50·p95 Latency는 nearest-rank 방식의 50·95백분위수이며 단위는 초다. 미완료 모델의 전체 정확도는 Not Comparable로 표시한다.")
    heading += [main_table, f"본 실행의 Raw Calls 합계는 {raw_calls}회, Budget-Accounted Cost 합계는 US${total:.12f}다. smoke는 포함하지 않는다. 기록 비용은 실제 전체 청구액의 독립 증명이 아니다.", "", "## 호출·형식·시간 상세", ""]
    heading.append(table(["Model ID", "Provider", "Actual Model", "Main Test Status", "First-Pass Schema Success Rate", "Retry Rate", "API Error Rate", "Elapsed Time (s)"],
                         [[f"`{model}`", ", ".join(value["Providers"]), ", ".join(value["Actual Models"]), value["status"],
                           ratio(value["First-Pass Schema Success Rate"]), ratio(value["Retry Rate"]), ratio(value["API Error Rate"]),
                           number(elapsed.get(model))] for model, value in metrics.items()],
                         "Provider·Actual Model은 응답에 기록된 공급자·모델 ID다. Main Test Status는 실행기 종료 상태이며 complete_with_errors는 일부 최종 형식 오류가 남아도 모든 job을 처리했다는 뜻이다. First-Pass Schema Success Rate는 첫 시도에 형식을 통과한 수 / 70, Retry Rate는 재시도한 문항 수 / 70, API Error Rate는 형식·예산 차단 외 호출 오류 문항 수 / 70이다. Elapsed Time은 catalog 확인을 포함한 본 실행 process의 경과 시간이다."))
    heading.append(table(["Model ID", "Input Tokens (recorded)", "Output Tokens (recorded)", "Reported Cost Calls"],
                         [[f"`{model}`", value["Input Tokens (recorded)"], value["Output Tokens (recorded)"], value["Reported Cost Calls"]]
                          for model, value in metrics.items()],
                         "Input/Output Tokens (recorded)는 저장된 usage의 입력·출력 토큰 합계다. Reported Cost Calls는 비용 필드가 남은 usage record 수다. 생성형 5종은 재시도 뒤 성공한 문항의 앞선 실패 usage를 모두 보존하지 않으므로 전체 Raw Calls·실제 전체 청구액과 같지 않을 수 있다."))
    heading += ["## Routing Consistency", "", table(["Model ID", "Predicted out_of_scope", "Inconsistent Action", "Case IDs and Actions"],
                 [[f"`{model}`", value["Routing Consistency"]["Predicted out_of_scope"], ratio(value["Routing Consistency"]["Inconsistent Action"]),
                   "; ".join(f"{key}: {action}" for key, action in value["Routing Consistency"]["inconsistent_case_actions"].items()) or "없음"]
                  for model, value in metrics.items()],
                 "Predicted out_of_scope는 모델이 스스로 범위 밖이라고 분류한 유효 행 수다. Inconsistent Action은 그중 refuse 외 동작을 고른 수 / 범위 밖 예측 수이며, 분모 0은 Not Applicable이다. 이 지표는 내부 출력의 일관성으로, gold와 대조한 범위 밖 탐지·거절 정확도가 아니다. Case IDs and Actions는 해당 문항 ID와 선택 동작이다.")]
    heading += ["## 1~3차 안정성", "", table(["Model ID", "Comparable Three-Run Cases", "Three-Run Exact Agreement", "Question Type Flip Rate", "Next Action Flip Rate"],
                 [[f"`{model}`", *[ratio(value["three_run_comparison"][key]) for key in
                   ("Comparable Three-Run Cases", "Three-Run Exact Agreement", "Question Type Flip Rate", "Next Action Flip Rate")]]
                  for model, value in models.items()],
                 "Comparable Three-Run Cases는 세 회차 모두 형식상 유효한 문항 수 / 70이다. 나머지 세 지표의 분모는 그 비교 가능한 문항 수다. Exact Agreement는 decision 전체가 같은 문항 비율, 두 Flip Rate는 질문 유형·다음 동작이 한 번이라도 달라진 비율이다. 같은 오류를 반복해도 일치율이 높을 수 있다. 비교 가능한 문항이 적을 때 높은 일치율을 전체 성능으로 해석하지 않는다. 객체 키 순서만 정규화하고 required_evidence 배열의 순서는 보존한다.")]
    heading += ["## 1·2·3차 점수 대조", "", table(["Model ID", "Stage 1 Accuracy", "Stage 2 Accuracy", "Stage 3 Accuracy", "Stage 1 Schema Valid Rate", "Stage 2 Schema Valid Rate", "Stage 3 Schema Valid Rate"],
                 [[f"`{model}`", *[accuracy(value["runs"][str(index)]) for index in (1, 2, 3)],
                   *[ratio(value["runs"][str(index)]["Schema Valid Rate"]) for index in (1, 2, 3)]] for model, value in models.items()],
                 "각 Stage의 Accuracy는 같은 gold 35문항에서 유형을 맞힌 수, Schema Valid Rate는 전체 70문항의 형식 통과 수다. Stage 1의 일부 provider 중단 모델은 완료된 전체 실험과 직접 비교할 수 없어 Not Comparable로 표시한다.")]
    heading.append(table(["Model ID", "Stage 1 Provider", "Stage 2 Provider", "Stage 3 Provider"],
                         [[f"`{model}`", *[", ".join(value["runs"][str(index)]["Providers"]) or "Not Recorded" for index in (1, 2, 3)]]
                          for model, value in models.items()],
                         "Provider는 각 회차 응답에 기록된 실제 공급자다. 같은 Model ID에서도 공급자가 바뀌면 형식 지원·지연·모델 제공 조건이 달라질 수 있으므로 점수 차이를 모델 자체 변화로만 해석하지 않는다. Not Recorded는 공급자 정보가 남지 않았다는 뜻이다."))
    deepseek = models["deepseek/deepseek-v4.1-flash"]["runs"]
    heading += ["### DeepSeek 출력 길이 진단", "", table(
        ["Run", "Provider", "Schema Valid Rate", "Length-Limited Validation Failures", "Validation Attempts at 256 Tokens"],
        [[index, ", ".join(deepseek[index]["Providers"]), ratio(deepseek[index]["Schema Valid Rate"]),
          ratio(deepseek[index]["Output Limit Diagnostics"]["Length-Limited Validation Failures"]),
          str(deepseek[index]["Output Limit Diagnostics"]["validation_attempts_at_256_tokens"]) + "/" +
          str(deepseek[index]["Output Limit Diagnostics"]["validation_attempt_usage_records"])] for index in ("2", "3")],
        "Run은 회차, Provider는 실제 공급자, Schema Valid Rate는 형식 통과 / 70이다. Length-Limited Validation Failures는 마지막 종료 사유가 length인 형식 실패 수 / 전체 형식 실패 수다. Validation Attempts at 256 Tokens는 형식 실패 문항의 저장된 시도 usage 중 출력 토큰 256개인 수 / 해당 usage record 수다."),
        "3차 gold 35문항 중 33문항은 형식 실패했고 유효한 두 문항은 모두 유형 정답이었다. 프롬프트·출력 상한 256·실행 로직은 유지됐으며, 두 manifest의 실행기 hash 차이는 LF/CRLF 줄바꿈 차이로 확인했다. 공급자 변경과 출력 제한 도달이 함께 관찰됐지만, 내부 추론 설정이나 JSON 처리 차이의 인과관계는 이 자료로 확정하지 않는다.", ""]
    heading += ["### 2차에서 3차로 달라진 labeled 문항", ""]
    changed = []
    for model, value in models.items():
        for case in value["three_run_comparison"]["stage2_to_stage3_labeled_changes"]:
            observations = [entry["question_type"] if entry["status"] == "complete" else entry["status"] for entry in case["runs"]]
            changed.append([f"`{model}`", case["case_id"], case["gold"], observations[1], observations[2]])
    heading.append(table(["Model ID", "Case ID", "Gold", "Stage 2", "Stage 3"], changed,
                         "Gold는 동결된 질문 유형, Stage 2·3은 저장된 질문 유형 또는 실패 상태다. 같은 정오라도 예측 유형이 달라지면 포함하며, next_action만 달라진 문항은 집계 JSON의 flip 목록에서 확인한다."))
    heading += ["## 3차 유형별 F1", "", table(["Model ID", "candidate_find", "candidate_judge", "rating", "role"],
                 [[f"`{model}`", *[number(value["Question Type Per-Class"][label]["f1"]) for label in
                   ("candidate_find", "candidate_judge", "rating", "role")]] for model, value in metrics.items()],
                 "candidate_find는 후보 찾기, candidate_judge는 특정 후보 판단, rating은 정격·특성, role은 회로 역할 질문이다. 각 값은 해당 유형의 정밀도와 재현율을 함께 반영한 F1이며 1에 가까울수록 높다.")]
    heading += ["## 원시 결과 무결성", "", table(["Raw Result File", "SHA-256"],
                 [[path, digest] for path, digest in summary["sources"].items() if "stage3" in path and Path(path).name.startswith("rows")],
                 "Raw Result File은 3차 문항별 원시 파일 경로, SHA-256은 그 파일 바이트의 식별값이다. 해시 자체가 API 호출·정답·실제 청구를 독립 증명하지는 않는다. 나머지 metadata와 1·2차 원본의 hash는 집계 JSON에 있다.")]
    heading += ["## 최종 후보 모델", "",
                "3차 결과 확인 후 사용자 결정으로 최종 후보를 `openai/gpt-6-luna`, `typesafe/jev-1.14`, `anthropic/claude-haiku-5.5`의 3종으로 확정했다. 아래 표는 후보 유지·탈락 상태를 기록하며 순위를 부여하지 않는다. 이 결정은 사전 등록의 선정 규칙으로 소급하지 않으며 서비스 채택 모델 확정과 구별한다. 기존 여섯 모델의 코드·실측·원시 근거는 보존한다.", "",
                table(["Model ID", "Final Candidate Status", "Basis"], [
                    ["`openai/gpt-6-luna`", "Final Candidate", "1~3차 유형 정답 35·34·33/35, 형식 통과 66·65·65/70. 최종 후보로 유지."],
                    ["`typesafe/jev-1.14`", "Final Candidate", "세 회차 유형 정답 33/35·형식 통과 70/70. 최종 후보로 유지하며 3차 동작 불일치 4/6도 후속 검증 항목으로 보존."],
                    ["`anthropic/claude-haiku-5.5`", "Final Candidate", "사용자 결정으로 최종 후보에 유지. 세 회차 유형 정답 22·21·23/35, 형식 통과 48·46·50/70의 실측과 한계도 함께 보존."],
                    ["`deepseek/deepseek-v4.1-flash`", "Excluded", "사용자는 세 회차 실행의 안정성이 부족하다고 판단해 탈락 결정. 1차 provider 중단, 2·3차 공급자 변경과 3차 출력 제한 실패를 기록하며 모델 자체의 보편적 성능 저하로 단정하지 않음."],
                    ["`cohere/command-a-plus`", "Excluded", "세 회차 유형 정답 8·9·8/35, 형식 통과 20·21·21/70. 현재 계약의 실패가 반복돼 최종 후보에서 제외."],
                    ["`meta/muse-glimmer-30b`", "Excluded", "세 회차 모두 유형 정답 1/35·형식 통과 1/70으로 최종 후보에서 제외."],
                ], "Final Candidate Status의 Final Candidate는 후속 비교를 위한 최종 후보, Excluded는 최종 후보에서 탈락했다는 뜻이다. Basis는 관찰한 실측과 사용자 결정의 근거이며 순위나 서비스 채택 완료를 뜻하지 않는다."),
                "최종 후보의 프롬프트·동작 제약·출력 상한을 바꿔 실행한다면 별도 조건 변경 실험으로 등록한다. 기존 호출 실행기의 후보 목록은 과거 결과 재현을 위해 유지한다.", ""]
    heading += ["## 해석 제한", "",
                "- 같은 동결 70문항을 반복했다. 35개 비관련 문항의 올바른 거절 여부와 독립 평가셋·실서비스 그래프 성능은 이번 측정으로 입증하지 않는다.",
                "- 유형 gold는 35문항이어서 한 문항이 약 2.86%p다. 1~2문항 차이는 달라진 문항을 확인하는 근거이며 일반적인 모델 우열의 확정 근거로 삼지 않는다.",
                "- Jev의 typed answer와 결정적 출력 변환은 다른 5종의 JSON 생성과 다르다. 형식 성공과 전체 decision 일치율을 동일한 생성 능력으로 해석하지 않는다.",
                "- 모델별 provider가 회차마다 달라질 수 있다. 특히 실행 metadata의 공급자 차이가 있으면 모델 자체 변화와 분리해 해석해야 한다.",
                "- Jev 실행기는 2차 뒤 비용 초과 중단·비유한 인자 차단이 추가됐다. 프롬프트·변환 계약은 유지했다. --max-usd는 입력 비용 추정에 의한 다음 job 차단값이며 마지막 job의 실제 비용이 계획값을 넘을 수 있다.",
                "- 생성형 5종 raw summary는 세 회차 전체 계획의 210건 분모를 사용하므로 이 보고서는 원시 run_index=3 행만 재계산했다. configured_max_calls=630은 전체 1~3차 계획의 값이고, 이번 selected_run_indices=[3]의 job 70건은 각 최대 3회로 실제 210호출 이하다.",
                "- 5종 smoke 파일은 usage 비용을 보존하지 않아 실제 smoke 총 비용을 확정할 수 없다. Jev smoke의 보고 비용은 해당 smoke.json에서 확인한다.",
                "- 5종 manifest의 code_sha256은 실행 전 파일 원시 바이트 hash다. 집계 JSON의 execution_code_sha256_lf·analysis_code_sha256_lf는 줄바꿈을 LF로 정규화한 hash이므로 CRLF checkout의 원시 hash와 직접 비교하지 않는다.",
                "- 사전 등록의 ‘2차와 크게 다르지 않다’에 수치 허용 범위가 없으므로 가설 통과 여부나 운영 모델 변경을 자동 판정하지 않는다. 실측 차이와 실패 문항을 그대로 기록한다.", ""]
    (root / "docs/research/supervisor-stage3-results.md").write_text("\n".join(heading), encoding="utf-8", newline="\n")
    brief = ["# 수퍼바이저 6종 3차 평가 간단 보고서", "", "측정일: 2026-11-05 · 상태: 3차 실행 종료", "",
             "동결 v2 70문항을 여섯 모델에서 run_index=3으로 한 번씩 실행했다. 유형 정답률은 관련 gold 35문항만 채점한다. 같은 문항의 반복이므로 독립 평가셋 성능으로 해석하지 않는다.", "",
             table(["Model ID", "Schema Valid Rate", "Question Type Accuracy", "Question Type Macro-F1", "Inconsistent Action", "Raw Calls", "Budget-Accounted Cost (USD)", "p95 Latency (s)"],
                   [[f"`{model}`", ratio(value["Schema Valid Rate"]), accuracy(value), number(value["Question Type Macro-F1"]),
                     ratio(value["Routing Consistency"]["Inconsistent Action"]), value["Raw Calls"], number(value["Budget-Accounted Cost"], 9), number(value["p95 Latency"])]
                    for model, value in metrics.items()],
                   "Schema Valid Rate는 형식 통과 / 70, Question Type Accuracy는 유형 정답 / 35, Macro-F1은 네 유형 F1 평균이다. Inconsistent Action은 자체 범위 밖 예측 중 거절하지 않은 비율이며 올바른 거절 정답률이 아니다. Raw Calls는 재시도 포함 호출 수, Budget-Accounted Cost는 기록 비용·예약액의 관리값, p95 Latency는 문항별 처리 시간 95백분위수(초)다."),
             f"본 실행 비용 관리값 합계는 US${total:.12f}, Raw Calls는 {raw_calls}회다. 실제 청구액과 smoke 비용 전체는 확인하지 않았다.", "", "## 2차 대비 유형 정답 변화", ""]
    for model, value in models.items():
        brief.append(f'- `{model}`: {accuracy(value["runs"]["2"])} → {accuracy(value["runs"]["3"])}; 형식 통과 {ratio(value["runs"]["2"]["Schema Valid Rate"])} → {ratio(value["runs"]["3"]["Schema Valid Rate"])}.')
        if value["runs"]["2"]["Providers"] != value["runs"]["3"]["Providers"]:
            brief.append(f'  Provider도 {", ".join(value["runs"]["2"]["Providers"])} → {", ".join(value["runs"]["3"]["Providers"])}로 달라져 점수 변화를 모델 자체에만 귀속할 수 없다.')
    brief += ["", "## 해석", "", "3회 일치율은 세 회차가 모두 유효한 문항만 비교하며 비교 가능한 문항 수를 함께 보고한다. 형식 성공·유형 정답·라우팅 모순·provider 변화·비용·지연을 함께 확인해야 한다. 이번 결과로 기존 운영 모델 결정을 자동 변경하지 않는다.", "",
              "사용자 결정에 따른 최종 후보는 `openai/gpt-6-luna`, `typesafe/jev-1.14`, `anthropic/claude-haiku-5.5`의 3종이다. `deepseek/deepseek-v4.1-flash`는 실행 안정성 부족으로 탈락했고, `cohere/command-a-plus`와 `meta/muse-glimmer-30b`도 최종 후보에서 제외했다. 후보의 순위는 제시하지 않는다. Jev의 동작 불일치 4/6과 Haiku의 형식 실패를 포함한 기존 실측 근거는 전부 보존한다.", "",
              "[상세 결과·문항 변화·원시 파일 hash](supervisor-stage3-results.md), [3차 사전 등록](../experiments/supervisor-stage3-six-models.md)", ""]
    (root / "docs/research/supervisor-stage3-brief-report.md").write_text("\n".join(brief), encoding="utf-8", newline="\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    summary = build_summary()
    if summary.get("execution", {}).get("status") != "finished":
        raise ValueError("3차 순차 실행이 종료된 뒤 집계해야 합니다")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    render_reports(summary, args.output)
    print(json.dumps({model: value["runs"]["3"]["Question Type Accuracy"] for model, value in summary["models"].items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
