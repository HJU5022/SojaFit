"""평가셋 문항을 줄기 그래프로 끝까지 돌려, 문항마다 Langfuse 트레이스와 실행 점수를 남긴다.

- 하는 일: 문항마다 build_graph()를 invoke하고 Langfuse CallbackHandler로 단계별 입력·출력과 LLM 호출의 토큰·비용을 남긴다.
  실행 조건(공급자·모델·검색 방식·git 커밋·프롬프트 해시)은 메타데이터로, 실행 점수(경로·질문 종류·검색 횟수·LLM 호출 수·
  카드 수·인용 검사·걸린 시간)는 트레이스 점수로 붙인다. 한 번 실행한 문항들은 Langfuse session 하나로 묶는다.
- 하지 않는 일: 답이 맞았는지 채점(답 채점기는 따로 만든다, evals/README.md). 문항별 결과 파일 저장(카드 내용이 들어가
  저장소에 두지 않는다, SPEC 6절). 문항별 기록은 Langfuse에서 본다.
- 출처: SPEC 2절(그래프)·7절(Langfuse), ADR 0010(결정에 쓰는 측정은 OpenRouter로), docs/GATES.md G6
- 필요한 것: DATABASE_URL, OPENROUTER_API_KEY(LLM_PROVIDER=openrouter), LANGFUSE_PUBLIC_KEY·SECRET_KEY·BASE_URL.
  DEMO_MODE=1이면 검색은 임베딩 없이 BM25만 쓴다(backend/rag/retrieve.py).

실행(저장소 루트에서): uv run python -m evals.run_graph <평가셋 jsonl> [문항 id ...]
  예) LLM_PROVIDER=openrouter DEMO_MODE=1 uv run python -m evals.run_graph evals/dataset_v1.jsonl draft30-e01 draft30-e03
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def run_scores(state: dict, seconds: float, llm_calls: list[str]) -> dict:
    """그래프 최종 메모장에서 실행 점수를 뽑는다. 값은 (값, Langfuse data_type, 설명)."""
    from backend.graph.nodes import NOT_FOUND
    check = state.get("check") or {}
    scores = {
        # [왜] 경로를 범주 점수로 두면 Langfuse에서 경로별 문항 수를 세어 어느 노드에서 갈렸는지 본다(ADR 0010)
        "path": (">".join(state.get("path", [])), "CATEGORICAL", None),
        "question_type": (state.get("question_type") or "", "CATEGORICAL", None),
        "not_found": (float((state.get("answer") or "").startswith(NOT_FOUND)), "BOOLEAN", "답이 '문서로 확인 안 됨'으로 시작"),
        "tries": (float(state.get("tries", 0)), "NUMERIC", "검색 횟수"),
        "llm_calls": (float(len(llm_calls)), "NUMERIC", ", ".join(llm_calls)),
        "docs_found": (float(len(state.get("docs") or [])), "NUMERIC", "마지막 검색 카드 수"),
        "passed_cards": (float(len(state.get("passed") or [])), "NUMERIC", "채점 통과 카드 수"),
        "latency_s": (round(seconds, 1), "NUMERIC", None),
    }
    if "fake_citations" in check:  # 생성 노드를 지난 문항만 인용 검사 결과가 있다
        scores["fake_citations"] = (float(len(check["fake_citations"])), "NUMERIC", "넘긴 적 없는 근거 번호 수")
        scores["uncited_sentences"] = (float(check["uncited_sentences"]), "NUMERIC", "근거 번호가 없는 문장 수")
    return scores


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def main(dataset_path, ids=()):
    # [왜] 다른 코드의 트레이스와 나눠 보려고 환경 이름을 둔다. Langfuse 클라이언트가 만들어지기 전에 정해야 한다
    os.environ.setdefault("LANGFUSE_TRACING_ENVIRONMENT", "eval")
    from langfuse import get_client
    from langfuse.langchain import CallbackHandler

    from backend.graph import nodes
    from backend.graph.build import build_graph
    from backend.services import llm  # load_dotenv와 LANGFUSE_HOST → LANGFUSE_BASE_URL 맞추기가 여기서 일어난다

    if os.environ.get("LANGFUSE_BASE_URL", "").endswith("/"):
        # [주의] 끝에 /가 있으면 전송 주소가 //api/public/otel/...이 되어 308을 받고 트레이스가 소리 없이 버려진다(11-03 실측)
        raise SystemExit("LANGFUSE_BASE_URL 끝의 /를 지우세요(예: https://cloud.langfuse.com)")
    items = [json.loads(line) for line in open(dataset_path, encoding="utf-8") if line.strip()]
    if ids:
        items = [it for it in items if it["id"] in set(ids)]
    if not items:
        raise SystemExit(f"돌릴 문항이 없습니다: {dataset_path} {' '.join(ids)}")

    client = get_client()
    session = f"graph-{Path(dataset_path).stem}-{time.strftime('%m%d-%H%M')}-{llm.LLM_PROVIDER}"  # 이번 실행 문항들을 한 묶음으로
    common = {"provider": llm.LLM_PROVIDER,
              "model": llm.LLM_MODEL if llm.LLM_PROVIDER == "openrouter" else f"claude-cli:{llm.LLM_CLI_MODEL}",
              "demo_mode": llm.DEMO_MODE,
              "retrieval": "bm25" if llm.DEMO_MODE else "hybrid",  # DEMO_MODE=1이면 retrieve가 임베딩 없이 BM25만 쓴다
              "dataset": dataset_path,
              "git": _git("rev-parse", "--short", "HEAD") + ("+dirty" if _git("status", "--porcelain") else ""),
              # 프롬프트 파일 내용의 해시. 프롬프트를 고치면 바뀌어 실행끼리 비교할 때 구분된다
              "prompts": {p.stem: hashlib.sha1(p.read_bytes()).hexdigest()[:8]
                          for p in sorted(nodes.PROMPTS.glob("*.md")) if p.stem != "README"}}

    calls = []  # 이번 문항의 LLM 호출(답안지 이름). 노드는 llm.chat을 모듈에서 찾으므로 감싼 함수가 모든 호출을 본다
    chat = llm.chat
    llm.chat = lambda system, user, schema: calls.append(schema.__name__) or chat(system, user, schema)

    app = build_graph()
    failed = 0
    for it in items:
        calls.clear()
        # [왜] 트레이스 id를 직접 정해 넘긴다. 핸들러의 last_trace_id는 실제로 보낸 트레이스 id와 달랐다(11-03 실측)
        trace_id = client.create_trace_id()
        meta = {**common, "question_id": it["id"], "kind": it["kind"], "corpus_version": it.get("corpus_version"),
                "langfuse_session_id": session, "langfuse_tags": ["graph-eval", it["id"], llm.LLM_PROVIDER, it["kind"]]}
        if it.get("irrelevant_type"):
            meta["irrelevant_type"] = it["irrelevant_type"]
        config = {"callbacks": [CallbackHandler(trace_context={"trace_id": trace_id})], "run_name": f"graph {it['id']}",
                  "metadata": meta}
        start = time.perf_counter()
        try:
            state = app.invoke({"input": it["input"]}, config)
        except Exception as error:  # [왜] 한 문항이 죽어도 나머지는 잰다. 실패는 끝에 센다
            failed += 1
            print(f"{it['id']}\t실패\t{type(error).__name__}: {error}", flush=True)
            continue
        seconds = time.perf_counter() - start
        for name, (value, kind, comment) in run_scores(state, seconds, list(calls)).items():
            client.create_score(trace_id=trace_id, name=name, value=value, data_type=kind, comment=comment)
        print(f"{it['id']}\t{'>'.join(state['path'])}\t검색 {state.get('tries', 0)}번\t{seconds:.1f}초\t"
              f"{client.get_trace_url(trace_id=trace_id)}", flush=True)
    client.flush()  # [주의] 보내기는 백그라운드라 끝나기 전에 비워야 트레이스와 점수가 다 올라간다
    print(f"session {session}\t문항 {len(items)}건\t실패 {failed}건", flush=True)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("사용법: python -m evals.run_graph <평가셋 jsonl> [문항 id ...]")
    main(sys.argv[1], sys.argv[2:])
