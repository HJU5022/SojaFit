"""그림의 노드를 순차 호출하는 평가용 실행기. 서비스 StateGraph가 아니다.

uv run python -m evals.run_skill_pair <새 결과 폴더>
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

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(item, retriever):
    state = {"input": item["input"], "tries": 0, "path": []}

    def step(fn, *args):
        update = fn(deepcopy(state), *args)
        for key, value in update.items():
            state[key] = state.get(key, [] if key == "path" else 0) + value if key in ("tries", "path") else value

    step(nodes.read_input)
    step(nodes.route)
    if state["question_type"] == "role":
        return state
    if state["question_type"] != "out_of_scope":
        while True:
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
    if state["path"][-1] == "거절":
        return {mode: {"answer": state["answer"], "check": state.get("check", {}),
                       "skill": {"enabled": False, "applied": False, "sha256": None}, "seconds": 0}
                for mode in ("without", "with")}
    result = {}
    for enabled in ((True, False) if reverse else (False, True)):
        started = time.monotonic()
        out = nodes.generate(deepcopy(state), use_skill=enabled)
        result["with" if enabled else "without"] = {**out, "seconds": time.monotonic() - started}
        if on_answer:
            on_answer(deepcopy(result))
    return result


def run(items, retriever, output, metadata):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    result = {"metadata": metadata, "status": "incomplete", "rows": [], "expected_match_rate": None}

    def save():
        temp = output / "result.tmp"
        temp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(output / "result.json")

    save()
    try:
        for index, item in enumerate(items):
            state = prepare(item, retriever)
            # 생성 전에 저장해 두 번째 생성 실패 시에도 입력 상태를 보존한다.
            row = {"id": item["id"], "state": state, "state_sha256": hashlib.sha256(
                json.dumps(state, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
            result["rows"].append(row)
            save()
            def record(answers):
                row["answers"] = answers
                save()

            row["answers"] = compare(state, reverse=bool(index % 2), on_answer=record)
            save()
            print(json.dumps({"id": item["id"], "path": state["path"], "paired": True}, ensure_ascii=False), flush=True)
        result["status"] = "complete"
    except Exception as error:
        result["error_type"] = type(error).__name__  # 접속 문자열·키가 포함될 수 있는 예외 원문은 저장하지 않는다
    finally:
        budget = llm._evaluation_budget.get()
        if budget:
            result["budget"] = {"raw_calls": budget.calls, "reserved_usd": budget.reserved_usd,
                                "seconds": time.monotonic() - budget.started}
        save()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-usd", type=float, default=1.0)
    parser.add_argument("--max-tokens", type=int, default=1024)
    args = parser.parse_args()
    if llm.DEMO_MODE or llm.LLM_PROVIDER != "openrouter" or llm.LLM_MODEL != "anthropic/claude-haiku-5.5":
        parser.error("DEMO_MODE=0, OpenRouter와 규정 모델이 필요합니다")
    if os.getenv("OPENAI_API_KEY") or not os.getenv("OPENROUTER_API_KEY"):
        parser.error("OpenRouter 키만 사용해야 합니다")
    dataset = ROOT / "evals/dataset_v1.jsonl"
    frozen = json.loads((ROOT / "evals/FROZEN.json").read_text())[dataset.name]
    if digest(dataset) != frozen["sha256"]:
        raise ValueError("동결 평가셋 해시 불일치")
    items = [json.loads(x) for x in dataset.read_text().splitlines() if x.strip()]
    if len(items) != frozen["count"]:
        raise ValueError("동결 평가셋 건수 불일치")
    catalog = []
    for endpoint in ("models", "embeddings/models"):
        with urlopen(f"https://openrouter.ai/api/v1/{endpoint}", timeout=15) as response:
            catalog.extend(json.load(response)["data"])

    def pricing(model_id):
        return next(m["pricing"] for m in catalog if m["id"] == model_id)

    price = pricing(llm.LLM_MODEL)
    budget = llm.EvaluationBudget(600, args.max_usd, 900, float(price["prompt"]), float(price["completion"]),
                                float(pricing("openai/text-embedding-3-small")["prompt"]),
                                max_tokens=args.max_tokens, pricing_tiers=tuple(price.get("overrides", [])))
    files = ["evals/dataset_v1.jsonl", "data/manifest.jsonl", "backend/mcp_skill/skills/SKILL.md",
             "backend/graph/nodes.py", "backend/graph/build.py", "backend/graph/state.py",
             "backend/services/llm.py", "backend/rag/retrieve.py", "evals/run_skill_pair.py"]
    files += [str(p.relative_to(ROOT)) for p in (ROOT / "backend/prompts").glob("*.md")]
    # 회로 입력은 실제 read_input이 찾는 connections.json도 함께 고정한다.
    for item in items:
        fields = nodes.parse_input(item["input"])
        if fields.get("netlist_path"):
            net = ROOT / fields["netlist_path"]
            files.append(str(net.relative_to(ROOT)))
            connection = nodes._connections_file(fields["netlist_path"])
            if connection:
                files.append(str(connection.relative_to(ROOT)))
    metadata = {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "files": {f: digest(ROOT / f) for f in sorted(set(files))},
                "provider": llm.LLM_PROVIDER, "model": llm.LLM_MODEL, "retrieval": "hybrid", "k": 5,
                "vector_type": os.getenv("RAG_VECTOR_TYPE", "vector"), "temperature": 0,
                "format_retries": llm.MAX_FORMAT_RETRIES,
                "limits": {k: getattr(budget, k) for k in ("max_calls", "max_usd", "max_seconds", "max_tokens",
                                                           "prompt_rate", "completion_rate", "embedding_rate", "pricing_tiers")}}
    # DB는 읽기 전용으로 연결하고 긴 쿼리에는 상한을 둔다.
    os.environ["PGOPTIONS"] = "-c default_transaction_read_only=on -c statement_timeout=30000"
    os.environ["PGCONNECT_TIMEOUT"] = "10"
    from backend.rag.retrieve import retrieve
    with llm.evaluation_limits(budget):
        result = run(items, retrieve, args.output, metadata)
    print(json.dumps({"status": result["status"], "rows": len(result["rows"]),
                      "error_type": result.get("error_type"), "budget": result.get("budget")}, ensure_ascii=False))
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
