"""평가셋 문항을 줄기 그래프로 끝까지 돌려, 문항마다 Langfuse 트레이스와 실행 점수를 남긴다. 평가 담당이 손으로 돌린다.

- 역할: 문항마다 build_graph()를 invoke하고 Langfuse CallbackHandler로 단계별 입력·출력과 LLM 호출의 토큰·비용을 남긴다.
  실행 조건(공급자·모델·검색 방식·git 커밋·프롬프트 해시)은 메타데이터로, 실행 점수(경로·질문 종류·검색 횟수·LLM 호출 수·
  청크 수·인용 검사·걸린 시간)는 트레이스 점수로 붙인다. 한 번 실행한 문항들은 Langfuse session 하나로 묶는다.
- 하지 않는 일: 답변 문장·청크 원문을 결과 파일에 넣기(SPEC 6절: 청크 내용은 저장소에 두지 않는다). 그것은 Langfuse 트레이스에서 본다.
- 출처: SPEC 2절(그래프)·7절(그래프 평가 실행의 Langfuse 추적), ADR 0010(결정에 쓰는 측정은 OpenRouter로), docs/GATES.md G6, docs/experiments/answer-refusal-scorer.md
- 원시 결과: 문항별 지표(경로·검색 횟수·LLM 호출·통과 청크 id·인용 검사·5지표·시간·트레이스 주소)와 실행 조건, 5지표 요약을
  `evals/results/graph/graph_<평가셋>_<YYYY-MM-DD>.json`에 남긴다(가이드 v5 "평가셋과 원시 결과, 재현 명령은 레포 내").
  문항별 트레이스·점수는 Langfuse(환경 이름 eval, session graph-<평가셋>-<월일-시분>-<공급자>)에, 문항별 한 줄은 표준출력에 찍는다.
- 필요한 것: DATABASE_URL, OPENROUTER_API_KEY(LLM_PROVIDER=openrouter), LANGFUSE_PUBLIC_KEY·SECRET_KEY·BASE_URL.
  DEMO_MODE=1이면 검색은 임베딩 없이 BM25만 쓴다(backend/rag/retrieve.py).
  찾기 · 판정 값은 서비스와 같은 카드 도구(backend/rag/card_find.py · card_specs.py, ADR 0016)이고, MCP 서버는 사실 확인(check_corpus)에만 쓴다.
  카드 도구는 DATABASE_URL로 DB를 직접 읽고, 코드가 못 읽은 카드가 있으면 카드 읽기 LLM을 부른다(비용).
실행(저장소 루트에서): uv run python -m evals.runners.run_graph <평가셋 jsonl> [문항 id ...] [--out <결과 json>] [--multi]
  기본은 D4 v2 단일 그래프다(사실 확인 · 판정 길을 켜려고 MCP 서버를 연다). 판정 인터럽트는 빈 답(= 모름)으로 한 번 재개한다(사람이 답할 수 없어서).
  --multi: 단일 그래프 대신 멀티 에이전트(Supervisor + 서브에이전트, backend/multi_agent)를 같은 평가셋 · 같은 채점 · 같은 MCP 도구로 잰다.
           결과는 multi_<평가셋>_<날짜>.json
  예) LLM_PROVIDER=openrouter DEMO_MODE=1 uv run python -m evals.runners.run_graph evals/dataset_v1.jsonl draft30-e01 draft30-e03
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from contextlib import ExitStack
from pathlib import Path


def run_scores(state: dict, seconds: float, llm_calls: list[str], item: dict | None = None) -> dict:
    """그래프 최종 메모장(state)에서 실행 점수를 뽑는다. 각 값은 (값, Langfuse data_type, 설명) 튜플이다."""
    from backend.graph.nodes import NOT_FOUND
    check = state.get("check") or {}  # 생성 노드가 남긴 인용 검사 결과(생성을 안 거치면 없음)
    scores = {
        # [왜] 경로를 범주 점수로 두면 Langfuse에서 경로별 문항 수를 세어 어느 노드에서 갈렸는지 본다(ADR 0010)
        "path": (">".join(state.get("path", [])), "CATEGORICAL", None),
        "question_type": (state.get("question_type") or "", "CATEGORICAL", None),
        # BOOLEAN은 Langfuse가 0/1 숫자로 받는다
        "not_found": (float((state.get("answer") or "").startswith(NOT_FOUND)), "BOOLEAN", "답이 '문서로 확인 안 됨'으로 시작"),
        "tries": (float(state.get("tries", 0)), "NUMERIC", "검색 횟수"),
        "llm_calls": (float(len(llm_calls)), "NUMERIC", ", ".join(llm_calls)),
        "docs_found": (float(len(state.get("docs") or [])), "NUMERIC", "마지막 검색 청크 수"),
        "passed_cards": (float(len(state.get("passed") or [])), "NUMERIC", "채점 통과 청크 수"),
        "latency_s": (round(seconds, 1), "NUMERIC", None),
    }
    if "fake_citations" in check:  # 생성 노드를 지난 문항만 인용 검사 결과가 있다
        scores["fake_citations"] = (float(len(check["fake_citations"])), "NUMERIC", "넘긴 적 없는 근거 번호 수")
        scores["uncited_sentences"] = (float(check["uncited_sentences"]), "NUMERIC", "근거 번호가 없는 문장 수")
    counters = state.get("counters")
    if counters:  # 멀티 에이전트만: 검색 횟수는 단일 그래프의 tries와 같은 뜻으로 맞추고, Supervisor 판단 횟수를 더한다
        scores["tries"] = (float(counters["searches"]), "NUMERIC", "검색 횟수")
        scores["hops"] = (float(counters["hops"]), "NUMERIC", "Supervisor 판단 횟수")
    if counters or "refusal" in state:  # 멀티와 D4 v2 단일 그래프는 거절 사유 코드를 refusal 칸에 남긴다
        scores["refusal_code"] = ((state.get("refusal") or {}).get("code", ""), "CATEGORICAL", None)
        # [왜] 첫 단 거절은 사용자용 일상어 문구라 NOT_FOUND로 시작하지 않는다. 예전 단일과 같은 뜻(범위 밖이 아닌 '못 찾음')으로 맞춰 나란히 비교한다
        code = scores["refusal_code"][0]
        if code and code != "out_of_scope":
            scores["not_found"] = (1.0, "BOOLEAN", scores["not_found"][2])
    if item is not None:
        from evals.runners.score_answer import score_item
        scored = score_item(item, state)
        scores["answer_metric"] = (scored["metric"], "CATEGORICAL",
                                   "5지표(cited_gold/wrong_citation/over_refusal/correct_refusal/hallucination_risk)")
    return scores


def result_row(item: dict, state: dict, scores: dict, trace_url: str) -> dict:
    """결과 파일에 남길 문항 한 줄. 답변 문장·청크 원문은 넣지 않고 지표와 id만 남긴다(SPEC 6절)."""
    row = {"id": item["id"], "kind": item["kind"],
           # [왜] 정답 쪽 질문 종류(평가셋)와 라우팅이 고른 종류를 나란히 둬야 라우팅이 틀린 문항을 바로 센다
           "gold_type": item.get("question_type") or item.get("irrelevant_type"),
           "routed_type": scores["question_type"][0]}
    row.update({name: value for name, (value, _, _) in scores.items() if name != "question_type"})
    row["passed"] = list(state.get("passed") or [])  # 채점을 통과한 청크 id. 원문은 DB에서 id로 다시 볼 수 있다
    if state.get("judgement"):
        from evals.runners.score_answer import judgement_parts
        # [왜] 판정이 정답 판정과 맞는지 실행 뒤에 세려면 후보별 판정 코드가 남아야 한다(답 글은 남기지 않는다)
        row["verdicts"] = [[p.get("part"), p.get("verdict")] for p in judgement_parts(state["judgement"])]
    row["trace_url"] = trace_url
    return row


def summarize(rows: list[dict], failed: list[dict]) -> dict:
    """문항별 결과에서 5지표 건수를 전체·관련/비관련·정답 질문 종류별로 세고, 라우팅이 맞은 관련 문항 수를 센다."""
    def count(group):
        out = {}
        for r in group:
            key = r.get("answer_metric") or "unscored"
            out[key] = out.get(key, 0) + 1
        return dict(sorted(out.items()))

    by_type = {}
    for r in rows:
        by_type.setdefault(f"{r['kind']}/{r['gold_type']}", []).append(r)
    relevant = [r for r in rows if r["kind"] == "relevant"]
    latencies = sorted(r["latency_s"] for r in rows)
    return {
        "items": len(rows) + len(failed), "finished": len(rows), "failed": len(failed),
        "metrics": count(rows),
        "by_kind": {k: count([r for r in rows if r["kind"] == k]) for k in ("relevant", "irrelevant")},
        "by_type": {k: count(v) for k, v in sorted(by_type.items())},
        # [왜] 관련 문항만 평가셋에 질문 종류가 있다. 비관련 문항은 범위 밖으로 가야 하는지 문항마다 달라 여기서 세지 않는다
        "routing_match_relevant": sum(r["routed_type"] == r["gold_type"] for r in relevant),
        "relevant": len(relevant),
        "latency_p50_s": latencies[len(latencies) // 2] if latencies else None,
        "llm_calls_total": sum(r["llm_calls"] for r in rows),
    }


def default_out(dataset_path: str, today: str, name: str = "graph") -> Path:
    """결과 파일 기본 경로. 같은 날 같은 평가셋을 또 돌리면 시각을 붙여 덮어쓰지 않는다."""
    out = Path("evals/results/graph") / f"{name}_{Path(dataset_path).stem}_{today}.json"
    return out.with_name(f"{out.stem}-{time.strftime('%H%M')}.json") if out.exists() else out


def node_models() -> dict:
    """노드마다 실제로 쓸 모델(결과 파일과 Langfuse 메타데이터에 남겨, 어느 모델 조합으로 쟀는지 구분한다)."""
    from backend.services import langfuse_prompts, llm
    return {node: llm.node_model(node) for node in langfuse_prompts.NODES}


def evaluation_metadata(dataset_path: str) -> dict:
    """그래프·반복 평가가 같은 실행 조건을 Langfuse에 기록한다(본문·비밀값 제외)."""
    from backend.graph import nodes
    from backend.services import llm
    return {"provider": llm.LLM_PROVIDER,
            "model": llm.LLM_MODEL if llm.LLM_PROVIDER == "openrouter" else f"claude-cli:{llm.LLM_CLI_MODEL}",
            "demo_mode": llm.DEMO_MODE, "node_models": node_models(),
            "retrieval": "bm25" if llm.DEMO_MODE else "hybrid", "dataset": dataset_path,
            "git": _git("rev-parse", "--short", "HEAD") + ("+dirty" if _git("status", "--porcelain", "--untracked-files=no") else ""),
            "prompts": {p.stem: hashlib.sha1(p.read_bytes()).hexdigest()[:8]
                        for p in sorted(nodes.PROMPTS.glob("*.md")) if p.stem != "PROMPTS"}}


def invoke_with_resume(app, inputs: dict, config: dict, max_resumes: int = 1) -> dict:
    """그래프를 돌리고, 인터럽트로 멈추면 빈 답(= 모름)으로 최대 max_resumes번 재개한다."""
    from langgraph.types import Command
    state = app.invoke(inputs, config)
    for _ in range(max_resumes):
        if '__interrupt__' not in state:
            break
        # [주의] 빈 dict({})로 재개하면 LangGraph가 재개로 보지 않고 다시 멈춘다. 답 없음은 {'answers': {}}로 보낸다(11-06 실측)
        # [주의] 판정 할 일이 둘(판정 + 찾기)이면 인터럽트도 둘이다. id 없이 재개하면 RuntimeError라 인터럽트마다 답을 준다(11-07 c20-11)
        pending = state['__interrupt__']
        resume = {i.id: {'answers': {}} for i in pending} if len(pending) > 1 else {'answers': {}}
        state = app.invoke(Command(resume=resume), config)
    return state


def make_app(multi: bool, stack: ExitStack):
    """평가할 그래프를 조립한다. 단일 · 멀티 모두 MCP 서버를 stack에 열어(실행이 끝날 때 닫힘) 사실 확인에 쓰고, 찾기 · 판정 값은 카드 도구로 판정 길을 켠다.

    반환: (app, warm_eval). warm_eval()은 BM25·첫 검색·MCP 품번확인을 한 번 데운다(GATE_WARMUP용, 안 불러도 됨).
    """
    from backend.graph import mcp_retriever
    from backend.multi_agent.facts import make_lookup
    from backend.rag import card_find, card_specs
    from langgraph.checkpoint.memory import InMemorySaver
    mcp = stack.enter_context(mcp_retriever.StdioMcpRetriever())
    # [왜] 사양 표는 11-09에 버렸다(ADR 0016). 서비스(memory_service.py)와 같은 조립: 찾기 · 판정 값은 카드 읽기, 사실 확인의 문서 행은 LLM 없는 doc_rows
    specs = card_specs.default_specs()
    from functools import update_wrapper
    from backend.services.langfuse_prompts import timed_tool  # [왜] 서비스와 같은 칸 이름(search · specs · find)으로 단계 시간을 남긴다. 기록기가 없으면 그대로 통과한다
    raw_specs, raw_find = specs, card_find.default_find()
    # [왜] 판정 노드는 인터럽트로 멈췄다 같은 thread에서 재개하므로 체크포인터가 필요하다(메모리 안, 실행이 끝나면 사라짐)
    # [왜] 단일(D4 v2)과 멀티(D5)가 같은 사실 확인 · 같은 판정 도구를 써야 같은 평가셋 점수를 나란히 비교할 수 있다
    lookup = make_lookup(mcp.check, specs.doc_rows)
    tools = {"lookup": lookup, "specs": update_wrapper(timed_tool("specs", raw_specs), raw_specs),
             "find": update_wrapper(timed_tool("find", raw_find), raw_find), "checkpointer": InMemorySaver()}

    def warm_eval():
        """BM25 색인 · Voyage 첫 검색 · MCP check_corpus를 프로세스 앞에서 한 번 불러 첫 문항 콜드를 줄인다."""
        from backend.rag.retrieve import retrieve, warmup
        warmup()
        retrieve('1N4007G VRRM', k=5, parts=['1N4007G'])
        lookup({'question': '1N4007G VRRM', 'target_part': {}})

    if not multi:
        from backend.graph.build import build_graph
        return build_graph(**tools), warm_eval  # 서비스와 같은 D4 v2 단일 그래프(SPEC 2절). 검색기는 기본값 retrieve
    from backend.multi_agent.build import build_graph as build_multi
    from backend.rag.retrieve import retrieve
    from backend.services import llm
    return build_multi(chat=llm.node_chat, retriever=timed_tool("search", retrieve), judge_enabled=True, **tools), warm_eval


def _git(*args):
    """git 명령을 실행해 앞뒤 공백을 뗀 표준출력을 돌려준다(실패하면 빈 글자, 커밋 해시·변경 여부 기록용)."""
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def select_items(items, ids):
    """평가셋 문항 중 고른 id만 남긴다(ids가 비면 전부)."""
    if not ids:
        return items
    missing = sorted(set(ids) - {it["id"] for it in items})
    if missing:
        # [왜] 없는 id를 조용히 빼면 유료 실행이 일부 문항만 돌고도 정상으로 보이므로 오타로 보고 멈춘다
        raise SystemExit(f"평가셋에 없는 문항 id: {' '.join(missing)}")
    return [it for it in items if it["id"] in set(ids)]


def main(dataset_path, ids=(), out=None, multi=False):
    """문항을 하나씩 그래프로 돌리고 Langfuse에 트레이스·실행 점수를, 결과 파일에 문항별 지표를 남긴다(ids가 비면 전부)."""
    # [주의] 문항마다 LLM을 부르는 유료 실행이다. 전체(50건)를 돌리기 전에 문항 id 한두 개로 먼저 확인한다
    # [왜] 다른 코드의 트레이스와 나눠 보려고 환경 이름을 둔다. Langfuse 클라이언트가 만들어지기 전에 정해야 한다
    os.environ.setdefault("LANGFUSE_TRACING_ENVIRONMENT", "eval")
    from langfuse import get_client
    from backend.services.langfuse_prompts import callback

    from backend.services import llm  # load_dotenv와 LANGFUSE_HOST → LANGFUSE_BASE_URL 맞추기가 여기서 일어난다

    if os.environ.get("LANGFUSE_BASE_URL", "").endswith("/"):
        # [주의] 끝에 /가 있으면 전송 주소가 //api/public/otel/...이 되어 308을 받고 트레이스가 소리 없이 버려진다(11-03 실측)
        raise SystemExit("LANGFUSE_BASE_URL 끝의 /를 지우세요(예: https://cloud.langfuse.com)")
    # 평가셋은 한 줄에 문항 하나인 jsonl이다
    items = select_items([json.loads(line) for line in open(dataset_path, encoding="utf-8") if line.strip()], ids)
    if not items:
        raise SystemExit(f"돌릴 문항이 없습니다: {dataset_path} {' '.join(ids)}")

    client = get_client()
    family = "multi" if multi else "graph"  # [왜] 같은 평가셋 · 같은 채점으로 멀티 에이전트도 재서 결과 모양을 같게 둔다
    session = f"{family}-{Path(dataset_path).stem}-{time.strftime('%m%d-%H%M')}-{llm.LLM_PROVIDER}"  # 이번 실행 문항들을 한 묶음으로
    common = evaluation_metadata(dataset_path)

    calls = []  # 이번 문항의 LLM 호출(답안지 이름). 노드는 llm.chat을 모듈에서 찾으므로 감싼 함수가 모든 호출을 본다
    chat = llm.chat
    # [주의] llm.chat을 이 프로세스 안에서 바꿔 끼운다(호출 이름만 기록하고 그대로 넘긴다). 서비스 코드는 건드리지 않는다
    llm.chat = lambda system, user, schema: calls.append(schema.__name__) or chat(system, user, schema)

    with ExitStack() as stack:  # [왜] 멀티는 MCP 서버를 전 문항 동안 한 번만 열어 두고 끝나면 닫는다
        app, _warm_eval = make_app(multi, stack)  # 그래프를 한 번 조립해 문항마다 재사용한다
        rows, failed = [], []  # 결과 파일에 남길 문항별 지표, 오류로 멈춘 문항
        for it in items:
            calls.clear()  # 이전 문항의 호출 기록을 비운다
            # [왜] 트레이스 id를 직접 정해 넘긴다. 핸들러의 last_trace_id는 실제로 보낸 트레이스 id와 달랐다(11-03 실측)
            trace_id = client.create_trace_id()
            meta = {**common, "question_id": it["id"], "kind": it["kind"], "corpus_version": it.get("corpus_version"),
                    "langfuse_session_id": session, "langfuse_tags": [f"{family}-eval", it["id"], llm.LLM_PROVIDER, it["kind"]]}
            if it.get("irrelevant_type"):
                meta["irrelevant_type"] = it["irrelevant_type"]
            # 입력은 평가셋의 input 하나뿐이다. expected(정답)는 그래프에 넘기지 않는다
            # [왜] thread_id: 판정 인터럽트를 같은 문항의 thread에서 재개한다(단일 · 멀티 모두 메모리 체크포인터를 쓴다)
            config = {"callbacks": [callback(trace_context={"trace_id": trace_id})], "run_name": f"{family} {it['id']}",
                      "metadata": meta, "configurable": {"thread_id": it["id"]}}
            start = time.perf_counter()
            try:
                state = invoke_with_resume(app, {"input": it["input"]}, config)
            except Exception as error:  # [왜] 한 문항이 죽어도 나머지는 잰다. 실패는 끝에 세고 결과 파일에도 남긴다
                failed.append({"id": it["id"], "error": f"{type(error).__name__}: {str(error)[:200]}"})
                print(f"{it['id']}\t실패\t{type(error).__name__}: {error}", flush=True)
                continue
            seconds = time.perf_counter() - start
            scores = run_scores(state, seconds, list(calls), item=it)
            # 점수 하나하나를 이 문항의 트레이스에 붙인다
            for name, (value, kind, comment) in scores.items():
                client.create_score(trace_id=trace_id, name=name, value=value, data_type=kind, comment=comment)
            url = client.get_trace_url(trace_id=trace_id)
            rows.append(result_row(it, state, scores, url))
            print(f"{it['id']}\t{'>'.join(state['path'])}\t{scores['answer_metric'][0]}\t검색 {scores['tries'][0]:.0f}번\t"
                  f"{seconds:.1f}초\t{url}", flush=True)
    client.flush()  # [주의] 보내기는 백그라운드라 끝나기 전에 비워야 트레이스와 점수가 다 올라간다

    # [왜] 평가자는 Langfuse에 들어올 수 없으니, 같은 지표를 레포에 남겨 숫자를 맞춰 볼 수 있게 한다(가이드 v5 제출물)
    out_path = Path(out) if out else default_out(dataset_path, time.strftime("%Y-%m-%d"), family)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    meta = {**common, "session": session, "ran_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "dataset_sha256": hashlib.sha256(Path(dataset_path).read_bytes()).hexdigest(), "ids": list(ids) or "all"}
    result = {"meta": meta, "summary": summarize(rows, failed), "rows": rows, "failed": failed}
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"session {session}\t문항 {len(items)}건\t실패 {len(failed)}건\t결과 {out_path}", flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    out = None
    if "--out" in args:  # [왜] 시험 실행(10문항)과 본 실행을 같은 날 따로 남기려고 결과 파일 이름을 고를 수 있게 한다
        i = args.index("--out")
        out, args = args[i + 1], args[:i] + args[i + 2:]
    multi = "--multi" in args
    args = [a for a in args if a != "--multi"]
    if not args:
        raise SystemExit("사용법: python -m evals.runners.run_graph <평가셋 jsonl> [문항 id ...] [--out <결과 json>] [--multi]")
    main(args[0], args[1:], out, multi)
