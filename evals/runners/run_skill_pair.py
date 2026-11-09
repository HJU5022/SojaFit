"""그림의 노드를 순차 호출하는 평가용 실행기. 서비스 StateGraph가 아니다. 평가 담당이 손으로 돌린다.

- 역할: 같은 검색 상태에서 생성 노드에 도메인 Skill을 켰을 때(with)와 껐을 때(without) 답이 어떻게 다른지 본다.
  문항 순서마다 with/without 호출 순서를 번갈아 순서 효과를 줄인다.
- 하지 않는 일: 서비스 그래프·체크포인트·승인·MCP 통합 검증, 정답 채점(expected 충족률은 검토 전 null),
  동결 평가셋 수정. DB는 읽기 전용으로만 쓴다.
- 출처: SPEC 5절 "Skill 비교용 순차 실행기"·"도메인 Skill 적용", evals/guides/preregister.md #17(비교)·#18(출력 상한 변경), ADR 0010
- 입력: 동결 평가셋 evals/dataset_v1.jsonl(해시·건수가 evals/FROZEN.json과 다르면 중단).
- 원시 결과: <새 결과 폴더>/result.json(이미 있는 폴더면 실패). 문항마다 검색 상태·상태 해시·두 답·걸린 시간을 쓰고,
  실행 파일 해시·모델·호출 상한·예약 비용도 적는다. 예외 원문은 저장하지 않고 예외 이름만 남긴다.
- 호출 상한: llm.EvaluationBudget(호출 600건, --max-usd, 900초, --max-tokens)이 모든 원시 호출을 막는다.
- 필요한 것: DEMO_MODE=0, LLM_PROVIDER=openrouter, LLM_MODEL=anthropic/claude-haiku-5.5, OPENROUTER_API_KEY(OPENAI_API_KEY는 없어야 함),
  DATABASE_URL(적재한 코퍼스), 단가 조회용 네트워크(openrouter.ai).

실행(저장소 루트에서): DEMO_MODE=0 uv run python -m evals.runners.run_skill_pair <새 결과 폴더>
"""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

from backend.graph import nodes
from backend.graph.build import after_grade
from backend.services import llm

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    """파일 내용의 sha256 16진수 글자를 돌려준다(실행 파일·입력이 바뀌었는지 비교하는 지문)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_frozen_items(dataset, frozen_path):
    """UTF-8 동결 평가셋을 읽고 기록된 해시·건수와 일치하는 문항 목록을 돌려준다."""
    dataset, frozen_path = Path(dataset), Path(frozen_path)
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))[dataset.name]
    if digest(dataset) != frozen["sha256"]:
        raise ValueError("동결 평가셋 해시 불일치")
    items = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(items) != frozen["count"]:
        raise ValueError("동결 평가셋 건수 불일치")
    return items


def prepare(item, retriever):
    """한 문항을 그림의 노드 순서(입력 읽기, 라우팅, 검색, 채점, 재작성, 거절)대로 생성 직전까지 진행해 상태 dict를 돌려준다.

    path의 마지막이 "거절"이면 생성 없이 끝난 문항이다.
    """
    # [주의] 정답(expected)은 상태에 넣지 않는다. 검색은 최대 2번이며 채점 통과면 멈추고 끝내 실패하면 거절로 간다
    state = {"input": item["input"], "tries": 0, "path": []}

    def step(fn, *args):
        # 노드는 상태의 사본을 받아 바뀐 칸만 돌려준다. tries·path는 쌓고(+) 나머지는 덮어쓴다(state.py와 같은 규칙)
        update = fn(deepcopy(state), *args)
        for key, value in update.items():
            state[key] = state.get(key, [] if key == "path" else 0) + value if key in ("tries", "path") else value

    step(nodes.read_input)
    step(nodes.route)
    if state["question_type"] == "role":  # 회로 역할 질문은 검색 없이 바로 생성으로 간다
        return state
    if state["question_type"] != "out_of_scope":
        while True:  # 갈림길(after_grade)이 생성/거절로 끝낼 때까지 도는데, 서비스 규칙상 검색은 2번을 넘지 않는다
            step(nodes.search, retriever)
            step(nodes.grade)
            branch = after_grade(state)
            if branch == "생성":
                return state
            if branch == "거절":
                break
            step(nodes.rewrite)
    step(nodes.refuse)
    return state


def compare(state, *, reverse=False, on_answer=None):
    """같은 상태의 깊은 복사본으로 Skill 없이/있이 생성을 한 번씩 불러 {"without": 답, "with": 답}을 돌려준다.

    reverse=True면 Skill 있는 쪽을 먼저 부르고(순서 효과 상쇄), on_answer는 답 하나가 끝날 때마다 지금까지의 결과를 받는다(부분 저장용).
    """
    # 거절 경로는 생성을 부르지 않으므로 같은 거절 답을 양쪽에 넣는다(Skill 적용 정보는 꺼짐으로 둔다)
    if state["path"][-1] == "거절":
        return {mode: {"answer": state["answer"], "check": state.get("check", {}),
                       "skill": {"enabled": False, "applied": False, "sha256": None}, "seconds": 0}
                for mode in ("without", "with")}
    result = {}
    # [왜] 홀수 문항은 Skill 있는 쪽을 먼저 불러, 먼저/나중 호출 차이가 한쪽에만 쏠리지 않게 한다
    for enabled in ((True, False) if reverse else (False, True)):
        started = time.monotonic()
        out = nodes.generate(deepcopy(state), use_skill=enabled)  # [주의] 문항당 최대 2번의 유료 LLM 호출
        result["with" if enabled else "without"] = {**out, "seconds": time.monotonic() - started}
        if on_answer:
            on_answer(deepcopy(result))
    return result


def run(items, retriever, output, metadata):
    """문항을 차례로 돌려 result.json에 문항마다 저장하고 결과 dict(status·rows·budget)를 돌려준다. 중간에 죽어도 앞 문항 결과는 남는다."""
    output = Path(output)
    # [주의] exist_ok=False: 결과 폴더가 이미 있으면 FileExistsError로 멈춘다(이전 유료 실행 결과를 덮어쓰지 않으려고)
    output.mkdir(parents=True, exist_ok=False)
    result = {"metadata": metadata, "status": "incomplete", "rows": [], "expected_match_rate": None}

    def save():
        # [왜] 임시 파일에 쓴 뒤 바꿔치기해, 쓰는 도중 죽어도 깨진 json이 남지 않게 한다
        temp = output / "result.tmp"
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(output / "result.json")

    save()
    try:
        for index, item in enumerate(items):
            state = prepare(item, retriever)
            # [왜] 생성 전에 저장해 두면 생성이 실패해도 입력 상태(검색 결과)는 남는다. 해시는 같은 상태로 두 호출을 했는지 증명한다
            row = {"id": item["id"], "state": state, "state_sha256": hashlib.sha256(
                json.dumps(state, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
            result["rows"].append(row)
            save()
            def record(answers):  # 답 하나가 끝날 때마다 호출돼 부분 결과를 저장한다
                row["answers"] = answers
                save()

            row["answers"] = compare(state, reverse=bool(index % 2), on_answer=record)
            save()
            print(json.dumps({"id": item["id"], "path": state["path"], "paired": True}, ensure_ascii=False), flush=True)
        result["status"] = "complete"
    except Exception as error:
        result["error_type"] = type(error).__name__  # [주의] 접속 문자열·키가 포함될 수 있어 예외 원문은 저장하지 않고 이름만 남긴다
    finally:  # 성공이든 실패든 사용한 호출 수·예약 비용·시간을 남긴다
        budget = llm._evaluation_budget.get()
        if budget:
            result["budget"] = {"raw_calls": budget.calls, "reserved_usd": budget.reserved_usd,
                                "seconds": time.monotonic() - budget.started}
        save()
    return result


def main():
    """평가 조건을 검사하고 예산을 세운 뒤 동결 평가셋 전체를 돌린다(종료 코드 0 전 문항 완료, 1 중간 멈춤)."""
    # [주의] 유료 실행이다. 호출 상한(600건)·--max-usd(기본 1.0)·900초·--max-tokens(기본 1024)를 넘으면 llm.EvaluationBudget이 막는다
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-usd", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=1024)
    args = parser.parse_args()
    # [왜] 사전 등록 #17의 조건(실제 호출, OpenRouter, 규정 모델)과 다른 설정으로 돌면 비교가 무효가 되므로 시작 전에 막는다
    if llm.DEMO_MODE or llm.LLM_PROVIDER != "openrouter" or llm.LLM_MODEL != "anthropic/claude-haiku-5.5":
        parser.error("DEMO_MODE=0, OpenRouter와 규정 모델이 필요합니다")
    # [왜] 비용이 OpenRouter 한 곳으로만 잡히도록 OPENAI 키가 있으면 막는다
    if os.getenv("OPENAI_API_KEY") or not os.getenv("OPENROUTER_API_KEY"):
        parser.error("OpenRouter 키만 사용해야 합니다")
    dataset = ROOT / "evals/dataset_v1.jsonl"
    # [주의] 동결 평가셋의 해시·건수가 FROZEN.json과 다르면 정답이 바뀐 것이므로 ValueError로 중단한다
    items = load_frozen_items(dataset, ROOT / "evals/FROZEN.json")
    catalog = []  # OpenRouter 모델 목록(단가 포함). 예약 비용을 계산하려고 실행 전에 한 번 받는다
    for endpoint in ("models", "embeddings/models"):
        with urlopen(f"https://openrouter.ai/api/v1/{endpoint}", timeout=15) as response:
            catalog.extend(json.load(response)["data"])

    def pricing(model_id):
        return next(m["pricing"] for m in catalog if m["id"] == model_id)

    price = pricing(llm.LLM_MODEL)
    # 인자: 호출 600건, 최대 달러, 900초, 모델 단가(프롬프트·출력·임베딩 토큰당). 단가 구간(overrides)이 있으면 같이 넘긴다
    budget = llm.EvaluationBudget(600, args.max_usd, 900, float(price["prompt"]), float(price["completion"]),
                                float(pricing("openai/text-embedding-3-small")["prompt"]),
                                max_tokens=args.max_tokens, pricing_tiers=tuple(price.get("overrides", [])))
    # 이 실행의 입력·코드 지문 목록. 나중에 결과가 어느 코드·프롬프트로 나온 것인지 해시로 대조한다
    files = ["evals/dataset_v1.jsonl", "data/manifest.jsonl", "backend/mcp_skill/skills/SKILL.md",
             "backend/graph/nodes.py", "backend/graph/build.py", "backend/graph/state.py",
             "backend/services/llm.py", "backend/rag/retrieve.py", "evals/runners/run_skill_pair.py"]
    files += [str(p.relative_to(ROOT)) for p in (ROOT / "backend/prompts").glob("*.md")
              if p.name != "PROMPTS.md"]  # 폴더 설명 파일은 프롬프트가 아니라 해시에서 뺀다
    # 회로 입력은 실제 read_input이 찾는 connections.json도 함께 고정한다.
    for item in items:
        fields = nodes.parse_input(item["input"])
        if fields.get("netlist_path"):
            net = ROOT / fields["netlist_path"]
            files.append(str(net.relative_to(ROOT)))
            connection = nodes._connections_file(fields["netlist_path"])
            if connection:
                files.append(str(connection.relative_to(ROOT)))
    # k=5, hybrid, temperature 0은 코드가 고정한 값이라 여기서 기록만 한다(바꾸려면 사전 등록 #17부터)
    metadata = {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "files": {f: digest(ROOT / f) for f in sorted(set(files))},
                "provider": llm.LLM_PROVIDER, "model": llm.LLM_MODEL, "retrieval": "hybrid", "k": 5,
                "vector_type": os.getenv("RAG_VECTOR_TYPE", "vector"), "temperature": 0,
                "format_retries": llm.MAX_FORMAT_RETRIES,
                "limits": {k: getattr(budget, k) for k in ("max_calls", "max_usd", "max_seconds", "max_tokens",
                                                           "prompt_rate", "completion_rate", "embedding_rate", "pricing_tiers")}}
    # [주의] DB 안전장치: 읽기 전용 트랜잭션 + 쿼리 30초 상한. 이 실행기가 코퍼스를 바꾸지 못하게 한다
    os.environ["PGOPTIONS"] = "-c default_transaction_read_only=on -c statement_timeout=30000"
    os.environ["PGCONNECT_TIMEOUT"] = "10"
    # [왜] 환경변수를 정한 뒤에 import해야 위 DB 옵션이 연결에 적용된다
    from backend.rag.retrieve import retrieve
    with llm.evaluation_limits(budget):  # 이 블록 안의 모든 원시 호출이 예산에 잡힌다
        result = run(items, retrieve, args.output, metadata)
    print(json.dumps({"status": result["status"], "rows": len(result["rows"]),
                      "error_type": result.get("error_type"), "budget": result.get("budget")}, ensure_ascii=False))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
