"""그래프 평가 실행: 최종 메모장에서 Langfuse에 붙일 실행 점수를 바르게 뽑는지 확인한다.

- 역할: evals/runners/run_graph.py의 run_scores가 경로·검색 횟수·청크 수·인용 검사 점수를 뽑고, 거절로 끝나면 인용 검사 점수를 빼는지 확인한다.
- 하지 않는 일: Langfuse·LLM 없이 돈다. 답이 맞았는지는 보지 않는다.
- 출처: SPEC 7절(그래프 평가 실행), docs/GATES.md G6
"""
from evals.runners import run_graph as R
from evals.runners.run_graph import run_scores


def test_answer_path_scores_include_citation_check():
    state = {"path": ["입력 읽기", "라우팅", "검색", "채점", "생성"], "question_type": "rating", "tries": 1,
             "docs": [{"chunk_id": 7}, {"chunk_id": 8}], "passed": [7], "answer": "VRRM은 20 V다 [7]. 근거 없는 문장.",
             "check": {"fake_citations": ["999"], "uncited_sentences": 1, "used": ["7"]}}
    scores = run_scores(state, 2.34, ["Route", "Grade", "Answer"])
    assert scores["path"][:2] == ("입력 읽기>라우팅>검색>채점>생성", "CATEGORICAL")
    assert scores["not_found"][0] == 0.0 and scores["tries"][0] == 1.0 and scores["llm_calls"][0] == 3.0
    assert scores["docs_found"][0] == 2.0 and scores["passed_cards"][0] == 1.0 and scores["latency_s"][0] == 2.3
    assert scores["fake_citations"][0] == 1.0 and scores["uncited_sentences"][0] == 1.0


def test_refuse_path_has_no_citation_scores():
    state = {"path": ["입력 읽기", "라우팅", "검색", "채점", "거절"], "question_type": "rating", "tries": 1, "docs": [],
             "passed": [], "answer": "문서로 확인 안 됨: 1N4001 데이터시트를 찾지 못했습니다.", "check": {}}
    scores = run_scores(state, 0.8, ["Route"])
    assert scores["not_found"][0] == 1.0
    assert "fake_citations" not in scores and "uncited_sentences" not in scores


def _scores(metric, qtype="rating", latency=1.0, calls=3):
    """run_scores가 돌려주는 모양의 점수 묶음(시험용)."""
    return {"path": ("입력 읽기>라우팅>재작성>검색>채점>생성", "CATEGORICAL", None), "question_type": (qtype, "CATEGORICAL", None),
            "not_found": (0.0, "BOOLEAN", None), "tries": (1.0, "NUMERIC", None), "llm_calls": (float(calls), "NUMERIC", None),
            "docs_found": (5.0, "NUMERIC", None), "passed_cards": (1.0, "NUMERIC", None), "latency_s": (latency, "NUMERIC", None),
            "answer_metric": (metric, "CATEGORICAL", None)}


def test_result_row_keeps_ids_and_metrics_but_no_answer_text():
    from evals.runners.run_graph import result_row
    item = {"id": "draft30-e03", "kind": "relevant", "question_type": "rating", "expected": "정답 문장"}
    state = {"passed": [7], "answer": "VRRM은 20 V다 [7].", "docs": [{"chunk_id": 7, "content": "청크 원문"}]}
    row = result_row(item, state, _scores("cited_gold"), "https://trace/1")
    assert row["gold_type"] == "rating" and row["routed_type"] == "rating" and row["answer_metric"] == "cited_gold"
    assert row["passed"] == [7] and row["trace_url"] == "https://trace/1"
    # [왜] 답변 문장과 청크 원문은 저장소에 두지 않는다(SPEC 6절)
    assert "answer" not in row and "docs" not in row and "청크 원문" not in str(row) and "VRRM" not in str(row)


def test_summarize_counts_metrics_by_kind_type_and_routing():
    from evals.runners.run_graph import result_row, summarize
    rel = {"id": "a", "kind": "relevant", "question_type": "rating"}
    rel2 = {"id": "b", "kind": "relevant", "question_type": "role"}
    irr = {"id": "c", "kind": "irrelevant", "irrelevant_type": "unknown_entity"}
    rows = [result_row(rel, {}, _scores("cited_gold", latency=2.0), ""),
            result_row(rel2, {}, _scores("over_refusal", qtype="rating", latency=4.0), ""),  # 역할을 정격으로 잘못 보냄
            result_row(irr, {}, _scores("correct_refusal", latency=1.0, calls=1), "")]
    s = summarize(rows, [{"id": "d", "error": "TimeoutError"}])
    assert s["items"] == 4 and s["finished"] == 3 and s["failed"] == 1
    assert s["metrics"] == {"cited_gold": 1, "correct_refusal": 1, "over_refusal": 1}
    assert s["by_kind"]["relevant"] == {"cited_gold": 1, "over_refusal": 1}
    assert s["by_type"]["irrelevant/unknown_entity"] == {"correct_refusal": 1}
    assert s["routing_match_relevant"] == 1 and s["relevant"] == 2
    assert s["latency_p50_s"] == 2.0 and s["llm_calls_total"] == 7


def test_default_out_does_not_overwrite_same_day_file(tmp_path, monkeypatch):
    from evals.runners.run_graph import default_out
    monkeypatch.chdir(tmp_path)
    first = default_out("evals/dataset_v2.jsonl", "2026-11-04")
    assert first.as_posix() == "evals/results/graph/graph_dataset_v2_2026-11-04.json"
    first.parent.mkdir(parents=True)
    first.write_text("{}")
    second = default_out("evals/dataset_v2.jsonl", "2026-11-04")
    assert second != first and second.name.startswith("graph_dataset_v2_2026-11-04-")


def test_main_writes_metrics_only_result_file(tmp_path, monkeypatch):
    """main을 Langfuse·LLM·DB 없이 가짜로 돌려 결과 파일 모양과 실패 문항 기록을 확인한다."""
    import json
    import langfuse
    import langfuse.langchain
    from evals.runners import run_graph

    class FakeClient:
        def create_trace_id(self): return "t1"
        def create_score(self, **kw): pass
        def get_trace_url(self, trace_id): return f"https://lf/{trace_id}"
        def flush(self): pass

    class FakeApp:
        def invoke(self, inp, config):
            if "boom" in inp["input"]:
                raise TimeoutError("느림")
            return {"path": ["입력 읽기", "라우팅", "거절"], "question_type": "out_of_scope", "tries": 0, "docs": [],
                    "passed": [], "answer": "이 질문은 SojaFit 범위 밖입니다.", "check": {}}

    monkeypatch.setattr(langfuse, "get_client", lambda: FakeClient())
    monkeypatch.setattr(langfuse.langchain, "CallbackHandler", lambda **kw: None)
    monkeypatch.setattr(run_graph, "make_app", lambda multi, stack: FakeApp())
    data = tmp_path / "set.jsonl"
    data.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in [
        {"id": "i1", "kind": "irrelevant", "irrelevant_type": "out_of_domain", "input": "질문: 주식 추천", "expected": "", "gold_chunks": []},
        {"id": "i2", "kind": "irrelevant", "irrelevant_type": "out_of_domain", "input": "질문: boom", "expected": "", "gold_chunks": []}]), encoding="utf-8")
    out = tmp_path / "out.json"
    run_graph.main(str(data), (), str(out))
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["summary"]["finished"] == 1 and result["summary"]["failed"] == 1
    assert result["failed"] == [{"id": "i2", "error": "TimeoutError: 느림"}]
    assert result["rows"][0]["id"] == "i1" and result["rows"][0]["trace_url"] == "https://lf/t1"
    assert len(result["meta"]["dataset_sha256"]) == 64 and result["meta"]["ids"] == "all"
    assert "범위 밖입니다" not in out.read_text(encoding="utf-8")  # 답변 문장은 파일에 넣지 않는다


def test_multi_state_adds_hops_refusal_code_and_tries_from_counters():
    state = {"path": ["입력 읽기", "사실 확인", "거절"], "answer": "문서에 없는 부품입니다.", "check": {},
             "refusal": {"code": "part_missing", "message": "x"}, "counters": {"hops": 1, "searches": 0, "writes": 0}}
    scores = run_scores(state, 1.0, ["Decision"])
    assert scores["tries"][0] == 0.0 and scores["hops"][0] == 1.0 and scores["refusal_code"][0] == "part_missing"
    done = run_scores({"path": ["끝"], "answer": "ok [1].", "counters": {"hops": 4, "searches": 2, "writes": 1}}, 1.0, [])
    assert done["tries"][0] == 2.0 and done["refusal_code"][0] == ""


def test_multi_not_found_matches_single_meaning():
    """멀티 거절 문구는 일상어라 '문서로 확인 안 됨'으로 시작하지 않는다. 범위 밖이 아닌 거절은 단일처럼 not_found로 센다."""
    def nf(code, answer="문서에서 찾지 못했어요."):
        state = {"path": ["거절"], "answer": answer, "refusal": {"code": code} if code else {}, "counters": {"hops": 1, "searches": 0, "writes": 0}}
        return run_scores(state, 1.0, [])["not_found"][0]
    assert nf("revision_missing") == 1.0 and nf("part_missing") == 1.0 and nf("not_found") == 1.0
    assert nf("out_of_scope") == 0.0  # 단일도 범위 밖 거절은 not_found가 아니다
    assert nf("", "안녕하세요!") == 0.0  # 일상 대화 답
    assert nf("", "문서로 확인 안 됨") == 1.0  # 작성 에이전트가 낸 '문서로 확인 안 됨' 답


def test_single_state_has_no_multi_scores():
    scores = run_scores({"path": ["생성"], "tries": 1, "answer": "x"}, 1.0, [])
    assert "hops" not in scores and "refusal_code" not in scores


def test_single_refusal_code_is_scored_like_multi():
    """D4 v2 단일 그래프도 거절 사유 코드를 `refusal`에 남긴다. 멀티와 같은 이름으로 세고, 범위 밖이 아닌 거절은 not_found로 맞춘다."""
    state = {"path": ["입력 읽기", "사실 확인", "라우팅", "거절"], "tries": 0, "answer": "1N4001의 데이터시트를 찾을 수 없어요.",
             "refusal": {"code": "part_missing", "message": "x"}}
    scores = run_scores(state, 1.0, ["Route"])
    assert scores["refusal_code"][0] == "part_missing" and scores["not_found"][0] == 1.0
    assert scores["tries"][0] == 0.0 and "hops" not in scores  # 검색 횟수는 단일의 tries 그대로, 판단 횟수는 멀티만
    chat = run_scores({"path": ["짧은 답"], "tries": 0, "answer": "안녕하세요!", "refusal": {}}, 1.0, ["Route"])
    assert chat["refusal_code"][0] == "" and chat["not_found"][0] == 0.0


def test_default_out_names_multi_runs_separately(tmp_path, monkeypatch):
    from evals.runners.run_graph import default_out
    monkeypatch.chdir(tmp_path)
    assert default_out("evals/dataset_v2.jsonl", "2026-11-05").name == "graph_dataset_v2_2026-11-05.json"
    assert default_out("evals/dataset_v2.jsonl", "2026-11-05", "multi").name == "multi_dataset_v2_2026-11-05.json"


def test_node_models_records_model_of_every_node(monkeypatch):
    from backend.services import langfuse_prompts, llm
    from evals.runners.run_graph import node_models
    monkeypatch.setattr(llm, "LLM_MODEL_OVERRIDE", None)
    models = node_models()
    assert set(models) == set(langfuse_prompts.NODES)
    assert models["supervisor"] == langfuse_prompts.HAIKU and models["synth"] == langfuse_prompts.SONNET and models["grade"] == langfuse_prompts.LUNA and models["generate"] == langfuse_prompts.HAIKU
    monkeypatch.setattr(llm, "LLM_MODEL_OVERRIDE", "x/y")
    assert set(node_models().values()) == {"x/y"}


class FakeMcp:
    """MCP 서버 가짜: 열고 닫힌 때와 사실 확인 호출을 기록한다."""
    events, checked = [], []

    def __enter__(self):
        self.events.append("open")
        return self

    def __exit__(self, *exc):
        self.events.append("close")

    def check(self, parts, revisions):
        self.checked.append((parts, revisions))
        return {"parts": {p: False for p in parts}, "revisions": {r: False for r in revisions}}

    def part_specs(self, part, codes=None):
        return []

    def find_parts(self, conditions, category=None, package=None, limit=50):
        return []


def fake_mcp(monkeypatch):
    from backend.graph import mcp_retriever
    monkeypatch.setattr(FakeMcp, "events", [])
    monkeypatch.setattr(FakeMcp, "checked", [])
    monkeypatch.setattr(mcp_retriever, "StdioMcpRetriever", FakeMcp)
    return FakeMcp


def test_make_app_multi_opens_mcp_for_whole_run_and_builds_multi_graph(monkeypatch):
    from contextlib import ExitStack
    from evals.runners.run_graph import make_app
    mcp = fake_mcp(monkeypatch)
    with ExitStack() as stack:
        app = make_app(True, stack)
        assert mcp.events == ["open"] and "Supervisor" in app.get_graph().nodes and "대체 부품 에이전트" in app.get_graph().nodes
    assert mcp.events == ["open", "close"]


def test_make_app_single_is_d4_v2_with_facts_and_judge_from_mcp(monkeypatch):
    """단일도 멀티처럼 MCP 서버를 열어 사실 확인(check_corpus) · 사양 표 도구로 쓰고 판정 길을 잇는다(D4 v2, 11-06)."""
    from contextlib import ExitStack
    from backend.graph import nodes
    from evals.runners.run_graph import make_app
    mcp = fake_mcp(monkeypatch)
    monkeypatch.setattr(nodes.llm, "chat", lambda system, user, schema: schema(question_type="rating", reason="part_missing"))
    with ExitStack() as stack:
        app = make_app(False, stack)
        assert {"사실 확인", "라우팅", "판정 읽기", "판정", "답 틀"} <= set(app.get_graph().nodes)
        state = app.invoke({"input": "질문: 1N4001 정격이 뭐야?"}, {"configurable": {"thread_id": "s1"}})  # 체크포인터가 있어 thread가 필요하다
        assert mcp.events == ["open"]
    assert mcp.checked == [(["1N4001"], [])]  # 사실 확인이 MCP check_corpus로 간다
    assert state["path"][-1] == "거절" and state["refusal"]["code"] == "part_missing"
    assert mcp.events == ["open", "close"]



class FakeApp:
    def __init__(self):
        self.calls = []

    def invoke(self, value, config):
        self.calls.append(value)
        return {'__interrupt__': ['ask']} if len(self.calls) == 1 else {'answer': 'done'}


def test_interrupt_is_resumed_once_with_empty_reply():
    """평가 문항에는 사람이 답할 수 없어 인터럽트에 빈 답({'answers': {}}, = 모름)으로 한 번만 재개한다(작업서 How "인터럽트")."""
    app = FakeApp()
    state = R.invoke_with_resume(app, {'input': 'q'}, {'configurable': {'thread_id': 'x'}})
    assert state == {'answer': 'done'} and len(app.calls) == 2
    assert getattr(app.calls[1], 'resume', None) == {'answers': {}}


def test_second_interrupt_is_not_resumed_again():
    class Always(FakeApp):
        def invoke(self, value, config):
            self.calls.append(value)
            return {'__interrupt__': ['ask']}
    app = Always()
    state = R.invoke_with_resume(app, {'input': 'q'}, {'configurable': {'thread_id': 'x'}})
    assert '__interrupt__' in state and len(app.calls) == 2  # 상한 1번(AGENTS 6번)


def test_resume_answers_every_pending_interrupt_by_id():
    from types import SimpleNamespace
    from evals.runners.run_graph import invoke_with_resume
    seen = []

    class App:
        def invoke(self, arg, config):
            if not seen:
                seen.append('first')
                return {'__interrupt__': [SimpleNamespace(id='a'), SimpleNamespace(id='b')]}
            seen.append(arg.resume)
            return {'answer': 'ok'}
    assert invoke_with_resume(App(), {'input': 'q'}, {})['answer'] == 'ok'
    # [왜] 판정 할 일 둘이 동시에 물으면 id 없이 재개할 수 없다(11-07 c20-11 RuntimeError)
    assert seen[1] == {'a': {'answers': {}}, 'b': {'answers': {}}}
