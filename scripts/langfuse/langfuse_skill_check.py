"""Langfuse 프롬프트·Skill 등록 후 합성 요청 4건(정격·근거 부재·역할·범위 밖)을 한 건씩 실행하고 원격 타임라인을 확인하는 개발 점검. 프롬프트 담당이 손으로 돌린다.

- 역할: Langfuse에 등록한 노드 프롬프트·Skill 버전이 실제 generation에 연결되는가, 노드 span 순서·부모·시각이
  기대한 경로와 같은가를 본다. 답의 정확도 평가가 아니라 개발 환경 점검이다.
- 하지 않는 일: 전체 평가셋 실행, 실제 코퍼스 검색 품질 측정, 서비스 그래프 조립/MCP 검증 대체.
- 출처: SPEC 5절 "Langfuse 프롬프트와 실행 추적", evals/guides/preregister.md #19(이 점검)·#20(Skill 본문 재검증), scripts/SCRIPTS.md
- 원시 결과: 인자로 준 <새 결과 JSON> 경로(이미 있으면 실패, 덮어쓰지 않는다). 요청별 트레이스 id·타임라인·호출 수·예산을 쓴다.
  SCRIPTS.md 관례의 scripts/results/<주제>/ 날짜 파일이 아니라 사용자가 정한 경로에 쓰므로 저장소에 둘 때는 scripts/results/의 맞는 주제 폴더로 옮긴다.
- 호출 상한: llm.EvaluationBudget(--max-calls 기본 40, --max-usd 기본 0.20, 300초, 출력 4096토큰). 타임라인 조회는 요청당 최대 8회(5초 간격).
- 필요한 것: DEMO_MODE=0, LLM_PROVIDER=openrouter, LLM_MODEL=등록 모델, OPENROUTER_API_KEY, Langfuse 키(LANGFUSE_PUBLIC_KEY·SECRET_KEY·BASE_URL),
  단가 조회용 네트워크. --publish는 로컬 프롬프트·Skill을 Langfuse development에 등록한다.

실행(저장소 루트에서): DEMO_MODE=0 uv run python -m scripts.langfuse.langfuse_skill_check <새 결과 JSON>
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
    """합성 대표 요청 4건을 (종류, 질문, 근거 또는 부품 정보) 목록으로 돌려준다. 종류는 rating·unsupported_guarantee·role·out_of_scope."""
    # [주의] 실제 데이터시트가 아닌 가짜 근거만 쓴다(합성 개발 표본). 실제 코퍼스 품질은 이 점검이 말해 주지 않는다
    part = {"ref": "D_TEST", "value": "DIODE_TEST", "footprint": "TEST_ONLY", "nets": [
        {"name": "VIN", "nodes": ["J_TEST.1(INPUT)", "D_TEST.A(DIODE_TEST)"], "more": 0},
        {"name": "VOUT", "nodes": ["D_TEST.K(DIODE_TEST)", "J_OUT.1(OUTPUT)"], "more": 0}]}
    return [
        ("rating", "합성 표본의 순방향 전압 전형값과 시험 조건은?", [
            {"chunk_id": 1, "file": "synthetic_test.pdf", "page": 1, "content":
             "합성 개발 표본. 실제 제품 아님. Forward voltage | TYP 0.7 V | IF=10 mA | TA=25 C. MAX 값 없음."}]),
        # 근거에 TYP만 있고 MAX가 없는데 "보장 최댓값"을 묻는다: 없는 값을 지어내지 않고 근거 부재로 가는지 본다
        ("unsupported_guarantee", "합성 표본의 순방향 전압 보장 최댓값은?", [
            {"chunk_id": 1, "file": "synthetic_test.pdf", "page": 1, "content":
             "합성 개발 표본. 실제 제품 아님. Forward voltage | TYP 0.7 V | IF=10 mA | TA=25 C. MAX 값 없음."}]),
        ("role", "D_TEST의 두 핀이 어떤 연결에 있는지 설명해 줘.", part),
        ("out_of_scope", "MCU 펌웨어 코드를 작성해 줘.", []),
    ]


def execute_case(kind, question, evidence):
    """대표 요청 한 건(kind, question, evidence는 cases()의 값)을 노드 순서대로 실행해 마지막 노드(generate 또는 refuse)의 출력 dict를 돌려준다."""
    # [주의] 노드마다 LLM을 부르는 유료 호출이다. 라우팅이 기대 종류와 다르면 ValueError로 멈춘다
    with managed.step("read_input"):
        state = nodes.read_input({"input": question})
        if kind == "role":
            state["target_part"] = evidence
    state.update(nodes.route(state))  # 노드는 바뀐 칸만 돌려주므로 update로 상태에 합친다
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
        # [주의] 합성 자료를 검색 결과로 주입한다. 실제 코퍼스 검색 품질을 측정하지 않는다
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
    """Langfuse에서 받은 observation 목록이 기대와 맞는지 검사하고, 하나라도 다르면 ValueError를 낸다.

    확인: 시각 누락·중복·오류 없음, generation 수가 실제 호출 수(expected_calls)와 같음, 모델·프롬프트 버전 연결,
    generation의 노드 부모 연결, case_kind가 있으면 노드 span 순서와 generation 시각 포함 관계.
    prompts는 노드 이름 -> 등록한 프롬프트 객체다.
    """
    by_id = {o["id"]: o for o in observations}
    # [왜] 원격 반영이 덜 끝나면 시각이 비어 있을 수 있어, 이 경우를 "수집 미완료"로 알려 재시도(inspect_timeline)하게 한다
    if not observations or any(not o.get("start_time") or not o.get("end_time") for o in observations):
        raise ValueError("타임라인 수집 미완료")
    if len(by_id) != len(observations) or any(str(o.get("level", "")).upper() == "ERROR" for o in observations):
        raise ValueError("타임라인 중복 또는 오류 observation")
    if case_kind is not None:
        validate_case_spans(observations, case_kind)
    generations = [o for o in observations if o.get("type", "").upper() == "GENERATION"]
    if len(generations) != expected_calls or not generations:
        raise ValueError("실제 요청과 generation 건수 불일치")
    coverage = Counter()  # 노드 span마다 연결된 generation 수(LLM 노드에 generation이 빠졌는지 확인용)
    for generation in generations:
        if generation.get("model") != managed.CONFIG["model"] or generation.get("level") == "ERROR":
            raise ValueError("generation 모델/오류 불일치")
        # generation에서 부모를 따라 올라가며 가장 가까운 "프롬프트 이름과 같은 SPAN"(= 노드)을 찾는다. visited로 순환을 막는다
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
            # 시각은 "Z"를 +00:00으로 바꿔 읽는다(fromisoformat이 Z를 못 읽는 파이썬 버전 대비). generation은 모든 조상 span의 시각 안에 있어야 한다
            start = datetime.fromisoformat(generation["start_time"].replace("Z", "+00:00")).timestamp()
            end = datetime.fromisoformat(generation["end_time"].replace("Z", "+00:00")).timestamp()
            for ancestor_id in visited:
                ancestor = by_id[ancestor_id]
                lower = datetime.fromisoformat(ancestor["start_time"].replace("Z", "+00:00")).timestamp()
                upper = datetime.fromisoformat(ancestor["end_time"].replace("Z", "+00:00")).timestamp()
                # 0.001초 여유: API가 밀리초까지만 줘서 같은 시각이 어긋나 보일 수 있다
                if start < lower - 0.001 or end > upper + 0.001:
                    raise ValueError("generation이 부모 실행 시각을 벗어남")
    if case_kind is not None and any(o.get("type") == "SPAN" and o.get("name") in prompts and not coverage[o["id"]] for o in observations):
        raise ValueError("LLM 노드의 generation 누락")


def validate_case_spans(observations, kind):
    """대표 요청(kind)의 root span 아래 노드 span이 종류별 기대 순서·시각 안에 있는지 검사하고, 어긋나면 ValueError를 낸다."""
    roots = [o for o in observations if o.get("name") == f"sojafit-skill-{kind}" and o.get("type") == "SPAN"
             and not o.get("parent_observation_id")]
    if len(roots) != 1:
        raise ValueError("대표 요청의 root span 불일치")
    root = roots[0]
    names = {"read_input", "route", "search", "grade", "rewrite", "generate", "refuse"}
    spans = [o for o in observations if o.get("type") == "SPAN" and o.get("name") in names]
    by_name = {name: sorted([o for o in spans if o["name"] == name], key=lambda o: o["start_time"]) for name in names}
    # 종류별 기대 노드 순서. unsupported_guarantee는 통과/재작성 여부에 따라 길이 두 가지(검색 1번 또는 2번)가 모두 정상이다
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
    # 노드 이름별 개수가 기대와 같아야 한다(빠지거나 더해진 노드 탐지)
    if Counter(o["name"] for o in spans) != Counter(expected):
        raise ValueError("대표 요청의 필수 노드 누락 또는 추가")
    if any(o.get("parent_observation_id") != root["id"] for o in spans):
        raise ValueError("노드 span의 root 연결 불일치")
    def stamp(value):
        """ISO 시각 글자를 epoch 초로 바꾼다."""
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    # 같은 이름 노드는 시작순으로 쓰고, 각 노드는 root 안에 있으며 앞 노드가 끝난 뒤에 시작해야 한다
    lower, upper = stamp(root["start_time"]), stamp(root["end_time"])
    previous_end = lower
    used = Counter()
    for name in expected:
        span = by_name[name][used[name]]
        used[name] += 1
        start, end = stamp(span["start_time"]), stamp(span["end_time"])
        # [왜] API가 밀리초까지만 줘서 같은 시각으로 보이는 경계가 어긋나 보일 수 있어 0.001초는 허용한다
        if start < lower - 0.001 or end > upper + 0.001 or end < start or start < previous_end - 0.001:
            raise ValueError("대표 요청의 노드 시각/순서 불일치")
        previous_end = end


def export_metadata(value):
    """SDK 응답을 바꾸지 않고 저장용 메타데이터에서 자격증명 필드를 뺀다."""
    # [주의] 결과 json은 저장소에 옮겨질 수 있으므로 키·토큰 필드를 중첩 구조 끝까지 지운다
    if isinstance(value, dict):
        credentials = {"public_key", "secret_key", "api_key", "access_token", "authorization"}
        return {key: export_metadata(item) for key, item in value.items()
                if key.lower().replace("-", "_").split(".")[-1] not in credentials}
    if isinstance(value, list):
        return [export_metadata(item) for item in value]
    return value


def inspect_timeline(client, trace_id, prompts, expected_calls, *, case_kind=None):
    """트레이스의 observation을 받아 validate_timeline으로 검사하고 시작 시각순 목록(자격증명 제거)을 돌려준다.

    원격 반영이 늦을 수 있어 최대 8번(5초 간격, 최대 약 35초) 다시 시도하고, 8번째에도 실패하면 ValueError를 그대로 낸다.
    """
    observations = []
    for attempt in range(8):
        # [주의] 요청마다 최대 8번 읽기 호출이 나간다(Langfuse API 조회라 LLM 비용은 아님)
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
            if attempt == 7:  # 마지막 시도면 더 기다리지 않고 실패를 알린다
                raise
        time.sleep(5)  # [왜] 방금 보낸 트레이스가 Langfuse에서 조회 가능해질 때까지 기다린다


def main():
    """예산·조건을 검사하고 대표 요청 4건을 실행한 뒤 결과를 output에 쓴다(4건 모두 통과하면 종료 코드 0, 아니면 1)."""
    # [주의] 유료 실행이다. --max-calls(기본 40)·--max-usd(기본 0.20)를 넘으면 llm.EvaluationBudget이 막는다
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-usd", type=float, default=0.20)
    parser.add_argument("--max-calls", type=int, default=40)
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--publish", action="store_true", help="로컬 프롬프트와 Skill을 development에 등록")
    args = parser.parse_args()
    if not math.isfinite(args.max_usd) or args.max_usd <= 0 or args.max_calls <= 0:
        parser.error("예산은 유한한 양수, 호출 상한은 양의 정수여야 합니다")
    # [왜] 재개는 "같은 버전으로 이어서"가 전제라서, 재개 중에 새 프롬프트를 등록해 버전을 바꾸는 조합을 막는다
    if args.publish and args.resume_from:
        parser.error("재개 시에는 새 프롬프트를 등록하지 않습니다")
    if llm.DEMO_MODE or llm.LLM_PROVIDER != "openrouter" or llm.LLM_MODEL != managed.CONFIG["model"]:
        parser.error("DEMO_MODE=0과 지정 OpenRouter 모델이 필요합니다")
    # [주의] 이전 유료 실행 결과를 지키려고 이미 있는 output은 거부한다
    if args.output.exists():
        parser.error("결과를 덮어쓰지 않습니다")
    if args.resume_from:
        previous = json.loads(args.resume_from.read_text(encoding="utf-8"))
        # 재개는 첫 정격 요청만 실행된 결과에서만 이어 간다(나머지 3건을 새로 돌린다)
        if len(previous.get("cases", [])) != 1 or previous["cases"][0].get("case") != "rating" or previous["cases"][0].get("status") != "executed":
            parser.error("재개는 실행된 첫 정격 요청 한 건만 지원합니다")
    # 단가 조회는 읽기 전용이며 등록/모델 호출 전에 예산 전체를 검증한다(예약 비용 계산에 모델 단가가 필요하다)
    with urlopen("https://openrouter.ai/api/v1/models", timeout=15) as response:
        models = json.load(response)["data"]
    price = next(m["pricing"] for m in models if m["id"] == managed.CONFIG["model"])
    budget = llm.EvaluationBudget(args.max_calls, args.max_usd, 300, float(price["prompt"]), float(price["completion"]),
        max_tokens=4096, pricing_tiers=tuple(price.get("overrides", [])))
    from langfuse import get_client
    client = get_client()
    if not client.auth_check():  # 키가 틀렸으면 유료 호출 전에 멈춘다
        raise RuntimeError("Langfuse 인증 실패")
    if args.publish:  # [주의] 원격 Langfuse development에 프롬프트·Skill을 등록(쓰기)한다. 명시했을 때만
        managed.publish_nodes(client)
        managed.publish_skill(client)
    prompts, skill = managed.load_development(client)  # 등록된 development 버전을 조회해 로컬 소스와 대조한다
    result = {"kind": "synthetic_development_check", "time": datetime.now(timezone.utc).isoformat(),
              "ui_checked": False, "prompts": {key: {"name": p.name, "version": p.version} for key, p in prompts.items()},
              "skill": {"name": skill.name, "version": skill.version, "sha256": skill.config["sha256"]}, "cases": []}
    resumed = None
    if args.resume_from:
        previous = json.loads(args.resume_from.read_text(encoding="utf-8"))
        # [왜] 등록본이 이전 실행 때와 다르면 이어 붙인 결과가 서로 다른 버전의 것이 되므로 중단한다
        if previous["prompts"] != result["prompts"] or previous["skill"] != result["skill"]:
            raise ValueError("재개할 프롬프트/Skill 버전 불일치")
        if len(previous["cases"]) != 1 or previous["cases"][0]["case"] != "rating" or previous["cases"][0]["status"] != "executed":
            raise ValueError("재개는 실행된 첫 정격 요청 한 건만 지원합니다")
        resumed = previous["cases"][0]
        result["resumed_raw_calls"] = previous["budget"]["raw_calls"]
        result["source_result"] = str(args.resume_from)
    return run_checks(client, prompts, skill, args.output, budget, result, resumed=resumed)


def run_checks(client, prompts, skill, output, budget, result, *, resumed=None):
    """요청 4건을 차례로 실행하고 요청마다 타임라인을 검증하며 결과 JSON을 그때그때 저장한다(종료 코드 0 전부 통과, 1 실패).

    한 건이라도 실행 또는 검증에 실패하면 거기서 멈춘다. result에 cases를 쌓고, resumed는 이전 실행에서 가져올 첫 정격 요청 결과다.
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # [주의] "x" 모드: output이 이미 있으면 FileExistsError로 멈춘다(덮어쓰기 금지). 빈 파일을 먼저 만들어 자리를 잡는다
    with output.open("x", encoding="utf-8"):
        pass
    def save():
        """결과를 임시 파일에 쓴 뒤 바꿔치기해 중간에 죽어도 깨진 JSON이 남지 않게 한다."""
        temporary = output.with_name(output.name + ".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(output)
    save()
    try:
        with llm.evaluation_limits(budget), managed.session(client, prompts, skill):
            for kind, question, evidence in cases():
                calls_before = budget.calls  # 이 요청이 쓴 호출 수 = 끝난 뒤 budget.calls - 이 값. generation 수와 대조한다
                if kind == "rating" and resumed:
                    row = dict(resumed)
                    row.pop("timeline_error_type", None)  # 이전 실행의 타임라인 오류 기록은 이번에 다시 검증하므로 지운다
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
                    client.flush()  # [주의] 보내기는 백그라운드라 조회 전에 비워야 방금 트레이스가 올라간다
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
                    break  # 실패하면 남은 요청을 돌려 비용을 더 쓰지 않는다
    except Exception as error:
        result["error_type"] = type(error).__name__  # [주의] 키·주소가 섞일 수 있는 예외 원문은 저장하지 않는다
    finally:
        result["budget"] = {"raw_calls": budget.calls, "reserved_usd": budget.reserved_usd,
                            "seconds": time.monotonic() - budget.started}
        save()
    return 0 if len(result["cases"]) == 4 and all(c.get("timeline_verified") and c["status"] == "executed" for c in result["cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
