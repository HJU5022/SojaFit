"""Langfuse 프롬프트·Skill 등록 후 합성 요청을 한 건씩 실행하고 원격 타임라인을 확인한다.

uv run python -m scripts.langfuse_skill_check <새 결과 JSON>
전체 평가셋을 사용하지 않으며 서비스 그래프 조립/MCP 검증을 대신하지 않는다.
"""
import argparse
from collections import Counter
import math
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.request import urlopen

from backend.graph import nodes
from backend.services import langfuse_prompts as managed
from backend.services import llm


def cases():
    part = {"ref": "D_TEST", "value": "DIODE_TEST", "footprint": "TEST_ONLY", "nets": [
        {"name": "VIN", "nodes": ["J_TEST.1(INPUT)", "D_TEST.A(DIODE_TEST)"], "more": 0},
        {"name": "VOUT", "nodes": ["D_TEST.K(DIODE_TEST)", "J_OUT.1(OUTPUT)"], "more": 0}]}
    return [
        ("rating", "합성 표본의 순방향 전압 전형값과 시험 조건은?", [
            {"chunk_id": 1, "file": "synthetic_test.pdf", "page": 1, "content":
             "합성 개발 표본. 실제 제품 아님. Forward voltage | TYP 0.7 V | IF=10 mA | TA=25 C. MAX 값 없음."}]),
        ("unsupported_guarantee", "합성 표본의 순방향 전압 보장 최댓값은?", [
            {"chunk_id": 1, "file": "synthetic_test.pdf", "page": 1, "content":
             "합성 개발 표본. 실제 제품 아님. Forward voltage | TYP 0.7 V | IF=10 mA | TA=25 C. MAX 값 없음."}]),
        ("role", "D_TEST의 두 핀이 어떤 연결에 있는지 설명해 줘.", part),
        ("out_of_scope", "MCU 펌웨어 코드를 작성해 줘.", []),
    ]


def execute_case(kind, question, evidence):
    with managed.step("read_input"):
        state = nodes.read_input({"input": question})
        if kind == "role":
            state["target_part"] = evidence
    state.update(nodes.route(state))
    if kind == "out_of_scope":
        if state["question_type"] != "out_of_scope":
            raise ValueError("범위 밖 요청 라우팅 불일치")
        with managed.step("refuse"):
            return nodes.refuse(state)
    if kind == "role":
        if state["question_type"] != "role":
            raise ValueError("역할 요청 라우팅 불일치")
    else:
        if state["question_type"] != "rating":
            raise ValueError("정격 요청 라우팅 불일치")
        # 합성 자료를 검색 결과로 주입한다. 실제 코퍼스 검색 품질을 측정하지 않는다.
        with managed.step("search", metadata={"source": "synthetic_fixture", "retrieval_test": False}):
            state.update({"docs": evidence, "parts": [], "tries": 1})
        state.update(nodes.grade(state))
        if not state["passed"]:
            state.update(nodes.rewrite(state))
            with managed.step("search", metadata={"source": "synthetic_fixture", "attempt": 2}):
                state["tries"] = 2
            state.update(nodes.grade(state))
            if not state["passed"]:
                with managed.step("refuse"):
                    return nodes.refuse(state)
    return nodes.generate(state, use_skill=True)


def validate_timeline(observations, prompts, expected_calls, *, case_kind=None):
    by_id = {o["id"]: o for o in observations}
    if not observations or any(not o.get("start_time") or not o.get("end_time") for o in observations):
        raise ValueError("타임라인 수집 미완료")
    if len(by_id) != len(observations) or any(str(o.get("level", "")).upper() == "ERROR" for o in observations):
        raise ValueError("타임라인 중복 또는 오류 observation")
    if case_kind is not None:
        validate_case_spans(observations, case_kind)
    generations = [o for o in observations if o.get("type", "").upper() == "GENERATION"]
    if len(generations) != expected_calls or not generations:
        raise ValueError("실제 요청과 generation 건수 불일치")
    coverage = Counter()
    for generation in generations:
        if generation.get("model") != managed.CONFIG["model"] or generation.get("level") == "ERROR":
            raise ValueError("generation 모델/오류 불일치")
        parent = generation.get("parent_observation_id")
        visited = set()
        node = None
        node_span = None
        while parent:
            if parent not in by_id or parent in visited:
                raise ValueError("타임라인 부모 연결 누락/순환")
            visited.add(parent)
            ancestor = by_id[parent]
            if node is None and ancestor.get("name") in prompts and ancestor.get("type") == "SPAN":
                node = ancestor["name"]
                node_span = ancestor
            parent = ancestor.get("parent_observation_id")
        if node is None:
            raise ValueError("generation의 노드 부모 누락")
        if generation.get("prompt_name") != prompts[node].name or generation.get("prompt_version") != prompts[node].version:
            raise ValueError("generation 프롬프트 버전 연결 불일치")
        if generation["start_time"] > generation["end_time"]:
            raise ValueError("타임라인 시간 순서 불일치")
        coverage[node_span["id"]] += 1
        if case_kind is not None:
            start = datetime.fromisoformat(generation["start_time"].replace("Z", "+00:00")).timestamp()
            end = datetime.fromisoformat(generation["end_time"].replace("Z", "+00:00")).timestamp()
            for ancestor_id in visited:
                ancestor = by_id[ancestor_id]
                lower = datetime.fromisoformat(ancestor["start_time"].replace("Z", "+00:00")).timestamp()
                upper = datetime.fromisoformat(ancestor["end_time"].replace("Z", "+00:00")).timestamp()
                if start < lower - 0.001 or end > upper + 0.001:
                    raise ValueError("generation이 부모 실행 시각을 벗어남")
    if case_kind is not None and any(o.get("type") == "SPAN" and o.get("name") in prompts and not coverage[o["id"]] for o in observations):
        raise ValueError("LLM 노드의 generation 누락")


def validate_case_spans(observations, kind):
    roots = [o for o in observations if o.get("name") == f"sojafit-skill-{kind}" and o.get("type") == "SPAN"
             and not o.get("parent_observation_id")]
    if len(roots) != 1:
        raise ValueError("대표 요청의 root span 불일치")
    root = roots[0]
    names = {"read_input", "route", "search", "grade", "rewrite", "generate", "refuse"}
    spans = [o for o in observations if o.get("type") == "SPAN" and o.get("name") in names]
    by_name = {name: sorted([o for o in spans if o["name"] == name], key=lambda o: o["start_time"]) for name in names}
    if kind == "rating":
        expected = ["read_input", "route", "search", "grade", "generate"]
    elif kind == "role":
        expected = ["read_input", "route", "generate"]
    elif kind == "out_of_scope":
        expected = ["read_input", "route", "refuse"]
    elif kind == "unsupported_guarantee":
        attempts = len(by_name["search"])
        if attempts not in (1, 2) or bool(by_name["generate"]) == bool(by_name["refuse"]):
            raise ValueError("근거 부재 요청의 분기 불일치")
        expected = ["read_input", "route", "search", "grade"]
        if attempts == 2:
            expected += ["rewrite", "search", "grade"]
        expected += ["generate" if by_name["generate"] else "refuse"]
    else:
        raise ValueError("알 수 없는 대표 요청")
    if Counter(o["name"] for o in spans) != Counter(expected):
        raise ValueError("대표 요청의 필수 노드 누락 또는 추가")
    if any(o.get("parent_observation_id") != root["id"] for o in spans):
        raise ValueError("노드 span의 root 연결 불일치")
    def stamp(value):
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    lower, upper = stamp(root["start_time"]), stamp(root["end_time"])
    previous_end = lower
    used = Counter()
    for name in expected:
        span = by_name[name][used[name]]
        used[name] += 1
        start, end = stamp(span["start_time"]), stamp(span["end_time"])
        # API의 밀리초 정밀도에서 같은 시각으로 보이는 경계는 허용한다.
        if start < lower - 0.001 or end > upper + 0.001 or end < start or start < previous_end - 0.001:
            raise ValueError("대표 요청의 노드 시각/순서 불일치")
        previous_end = end


def export_metadata(value):
    """SDK 응답을 바꾸지 않고 저장용 메타데이터에서 자격증명 필드를 뺀다."""
    if isinstance(value, dict):
        credentials = {"public_key", "secret_key", "api_key", "access_token", "authorization"}
        return {key: export_metadata(item) for key, item in value.items()
                if key.lower().replace("-", "_").split(".")[-1] not in credentials}
    if isinstance(value, list):
        return [export_metadata(item) for item in value]
    return value


def inspect_timeline(client, trace_id, prompts, expected_calls, *, case_kind=None):
    observations = []
    for attempt in range(8):
        response = client.api.observations.get_many(trace_id=trace_id, limit=100,
            fields="basic,usage,model,prompt,metadata")
        keys = ("id", "name", "type", "parent_observation_id", "start_time", "end_time", "level", "model",
                "prompt_name", "prompt_version", "usage_details", "cost_details", "metadata")
        observations = []
        for observation in response.data:
            row = {key: getattr(observation, key, None) for key in keys}
            row["metadata"] = export_metadata(row["metadata"])
            for key in ("start_time", "end_time"):
                if hasattr(row[key], "isoformat"):
                    row[key] = row[key].isoformat()
            observations.append(row)
        try:
            validate_timeline(observations, prompts, expected_calls, case_kind=case_kind)
            return sorted(observations, key=lambda o: o.get("start_time", ""))
        except ValueError:
            if attempt == 7:
                raise
        time.sleep(5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-usd", type=float, default=0.20)
    parser.add_argument("--max-calls", type=int, default=40)
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--publish", action="store_true", help="로컬 프롬프트와 Skill을 development에 등록")
    args = parser.parse_args()
    if not math.isfinite(args.max_usd) or args.max_usd <= 0 or args.max_calls <= 0:
        parser.error("예산은 유한한 양수, 호출 상한은 양의 정수여야 합니다")
    if args.publish and args.resume_from:
        parser.error("재개 시에는 새 프롬프트를 등록하지 않습니다")
    if llm.DEMO_MODE or llm.LLM_PROVIDER != "openrouter" or llm.LLM_MODEL != managed.CONFIG["model"]:
        parser.error("DEMO_MODE=0과 지정 OpenRouter 모델이 필요합니다")
    if args.output.exists():
        parser.error("결과를 덮어쓰지 않습니다")
    if args.resume_from:
        previous = json.loads(args.resume_from.read_text(encoding="utf-8"))
        if len(previous.get("cases", [])) != 1 or previous["cases"][0].get("case") != "rating" or previous["cases"][0].get("status") != "executed":
            parser.error("재개는 실행된 첫 정격 요청 한 건만 지원합니다")
    # 단가 조회는 읽기 전용이며 등록/모델 호출 전에 예산 전체를 검증한다.
    with urlopen("https://openrouter.ai/api/v1/models", timeout=15) as response:
        models = json.load(response)["data"]
    price = next(m["pricing"] for m in models if m["id"] == managed.CONFIG["model"])
    budget = llm.EvaluationBudget(args.max_calls, args.max_usd, 300, float(price["prompt"]), float(price["completion"]),
        max_tokens=4096, pricing_tiers=tuple(price.get("overrides", [])))
    from langfuse import get_client
    client = get_client()
    if not client.auth_check():
        raise RuntimeError("Langfuse 인증 실패")
    if args.publish:
        managed.publish_nodes(client)
        managed.publish_skill(client)
    prompts, skill = managed.load_development(client)
    result = {"kind": "synthetic_development_check", "time": datetime.now(timezone.utc).isoformat(),
              "ui_checked": False, "prompts": {key: {"name": p.name, "version": p.version} for key, p in prompts.items()},
              "skill": {"name": skill.name, "version": skill.version, "sha256": skill.config["sha256"]}, "cases": []}
    resumed = None
    if args.resume_from:
        previous = json.loads(args.resume_from.read_text(encoding="utf-8"))
        if previous["prompts"] != result["prompts"] or previous["skill"] != result["skill"]:
            raise ValueError("재개할 프롬프트/Skill 버전 불일치")
        if len(previous["cases"]) != 1 or previous["cases"][0]["case"] != "rating" or previous["cases"][0]["status"] != "executed":
            raise ValueError("재개는 실행된 첫 정격 요청 한 건만 지원합니다")
        resumed = previous["cases"][0]
        result["resumed_raw_calls"] = previous["budget"]["raw_calls"]
        result["source_result"] = str(args.resume_from)
    return run_checks(client, prompts, skill, args.output, budget, result, resumed=resumed)


def run_checks(client, prompts, skill, output, budget, result, *, resumed=None):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8"):
        pass
    def save():
        temporary = output.with_name(output.name + ".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(output)
    save()
    try:
        with llm.evaluation_limits(budget), managed.session(client, prompts, skill):
            for kind, question, evidence in cases():
                calls_before = budget.calls
                if kind == "rating" and resumed:
                    row = dict(resumed)
                    row.pop("timeline_error_type", None)
                    result["cases"].append(row)
                    expected_calls = result["resumed_raw_calls"]
                else:
                    with client.start_as_current_observation(name=f"sojafit-skill-{kind}", as_type="span",
                            metadata={"dataset": "synthetic-development", "skill_version": skill.version}) as root:
                        row = {"case": kind, "trace_id": root.trace_id, "status": "incomplete"}
                        result["cases"].append(row)
                        save()
                        try:
                            row["result"] = execute_case(kind, question, evidence)
                            row["status"] = "executed"
                        except Exception as error:
                            row["error_type"] = type(error).__name__
                            root.update(level="ERROR", status_message=type(error).__name__)
                    expected_calls = budget.calls - calls_before
                row["raw_calls"] = expected_calls
                save()
                try:
                    client.flush()
                    row["trace_url"] = client.get_trace_url(trace_id=row["trace_id"])
                    timeline = inspect_timeline(client, row["trace_id"], prompts, expected_calls, case_kind=kind)
                    row["timeline"] = timeline
                    row["generations"] = sum(o.get("type", "").upper() == "GENERATION" for o in timeline)
                    row["timeline_verified"] = True
                except Exception as error:
                    row["timeline_error_type"] = type(error).__name__
                    row["timeline_verified"] = False
                save()
                print(json.dumps({k: row.get(k) for k in ("case", "status", "generations", "error_type", "timeline_error_type", "trace_url")}), flush=True)
                if row["status"] != "executed" or not row.get("timeline_verified"):
                    break
    except Exception as error:
        result["error_type"] = type(error).__name__
    finally:
        result["budget"] = {"raw_calls": budget.calls, "reserved_usd": budget.reserved_usd,
                            "seconds": time.monotonic() - budget.started}
        save()
    return 0 if len(result["cases"]) == 4 and all(c.get("timeline_verified") and c["status"] == "executed" for c in result["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
