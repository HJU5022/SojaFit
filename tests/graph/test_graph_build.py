"""그래프 조립: 질문 종류와 채점 결과에 따라 노드가 SPEC 2절 순서로 이어지는지 확인한다.

- 역할: 가짜 LLM·가짜 검색기로 정격 검색 고리(재작성 뒤 첫 검색 통과, 다시 재작성 뒤 통과, 두 번 다 통과 없음, 검색 0장, 검색 장애)와
  첫 단 거절(범위 밖 · 다른 부품 · 없는 품번 · 없는 개정판, 검색 0번), 짧은 답, 역할, 판정 · 찾기의 경로를 확인한다.
- 하지 않는 일: 실제 LLM·검색 품질, 답의 정확도는 보지 않는다.
- 출처: SPEC 2절(그래프)·"근거가 없을 때", ADR 0006
"""
import pytest

from backend.graph import nodes
from backend.graph.build import build_graph
from backend.graph.mcp_retriever import RetrievalUnavailableError

QUESTION = "TSC 1N5817은 역전압을 몇 V까지 견뎌?"
# 평가셋 v1과 같은 입력 형식(회로·넷리스트·대상·질문). 넷리스트는 저장소의 샘플 회로다
INPUT = ("회로: SparkFun Breadboard Supply\n"
         "넷리스트: data/circuits/collected/samples/breadboard_supply/converted/circuit.net\n"
         f"대상: D1\n질문: {QUESTION}")
CARD = {"chunk_id": 7, "file": "1N5817 SERIES_H2104.pdf", "page": 1, "table": None, "doc_parts": ["1n5817"],
        "content": "Repetitive peak reverse voltage VRRM 20 V"}
REWRITTEN = "1N5817 repetitive peak reverse voltage VRRM"


def run(monkeypatch, question_type, grades, docs, *, lookup=None, **route):
    """가짜 LLM과 가짜 검색기를 꽂고 그래프를 끝까지 돌린다. grades는 채점 LLM이 호출 순서대로 낼 통과 청크 목록이다.

    route는 라우팅 답안지에 더할 칸(reason · reply), lookup은 사실 확인 함수다.
    """
    grades = iter(grades)  # [주의] 정해 둔 것보다 채점을 더 부르면 StopIteration으로 시험이 깨진다

    def fake_chat(system, user, schema):
        if schema is nodes.Route:
            return schema(question_type=question_type, **route)
        if schema is nodes.Grade:
            return schema(passed_ids=next(grades))
        if schema is nodes.Rewrite:
            return schema(query=REWRITTEN)
        return schema(answer="1N5817의 반복 피크 역전압은 20 V다 [7].")

    calls = []  # 검색기가 받은 (검색어, 품번) 기록. 검색 횟수를 센다

    def fake_retriever(question, *, parts=None):
        calls.append((question, parts))
        return docs

    monkeypatch.setattr(nodes.llm, "chat", fake_chat)
    return build_graph(retriever=fake_retriever, lookup=lookup).invoke({"input": INPUT}), calls


def test_passed_card_answers_after_one_search(monkeypatch):
    out, calls = run(monkeypatch, "rating", [[7]], [CARD])
    assert out["path"] == ["입력 읽기", "사실 확인", "라우팅", "재작성", "검색", "채점", "생성"]  # 첫 검색도 재작성한 검색어로 한다
    # [왜] 재작성 입력은 입력 전체가 아니라 질문 줄만이다. 회로 이름·D1까지 넣으면 BM25가 품번보다 그 낱말에 끌린다(11-02 격자 실측)
    assert calls == [(REWRITTEN, ["1N5817"])]
    assert out["tries"] == 1 and "[7]" in out["answer"]


def test_search_route_goes_through_rewrite(monkeypatch):
    out, _ = run(monkeypatch, "rating", [[7]], [CARD])
    assert out["path"].index("재작성") < out["path"].index("검색")  # 첫 검색 전에 재작성한다


def test_no_pass_rewrites_then_searches_again(monkeypatch):
    out, calls = run(monkeypatch, "rating", [[], [7]], [CARD])
    assert out["path"] == ["입력 읽기", "사실 확인", "라우팅", "재작성", "검색", "채점", "재작성", "검색", "채점", "생성"]
    assert calls == [(REWRITTEN, ["1N5817"])] * 2  # 품번 필터는 원래 질문에서 뽑는다
    assert out["tries"] == 2


def test_still_no_pass_refuses_after_two_searches(monkeypatch):
    out, calls = run(monkeypatch, "rating", [[], []], [CARD])
    # 상수 MAX_TRIES가 아니라 리터럴 2와 비교한다. 상수끼리 비교하면 상한을 바꿔도 통과한다(build.py 안내)
    assert len(calls) == 2
    assert out["path"][-1] == "거절" and "검색 2번" in out["answer"]


def test_zero_cards_refuses_without_rewrite(monkeypatch):
    out, calls = run(monkeypatch, "rating", [], [])  # 채점 LLM을 부르면 StopIteration으로 깨진다
    assert len(calls) == 1
    assert out["path"] == ["입력 읽기", "사실 확인", "라우팅", "재작성", "검색", "채점", "거절"]


def test_retrieval_failure_is_not_reported_as_empty_corpus(monkeypatch):
    def fake_chat(system, user, schema):
        if schema is nodes.Route:
            return schema(question_type="rating")
        if schema is nodes.Rewrite:  # [왜] 첫 검색 전에 재작성한다(사전 등록 #25). 장애는 그 뒤 검색에서 난다
            return schema(query=REWRITTEN)
        raise AssertionError(f"장애 뒤 LLM을 호출하면 안 됨: {schema.__name__}")

    calls = []

    def unavailable(question, *, parts=None):
        calls.append((question, parts))
        raise RetrievalUnavailableError("timeout")

    monkeypatch.setattr(nodes.llm, "chat", fake_chat)
    out = build_graph(retriever=unavailable).invoke({"input": INPUT})
    assert calls == [(REWRITTEN, ["1N5817"])]
    assert out["retrieval_error"] == {"kind": "timeout"}
    assert out["path"] == ["입력 읽기", "사실 확인", "라우팅", "재작성", "검색", "거절"]
    assert "검색 도구" in out["answer"]
    assert "데이터시트를 찾지 못" not in out["answer"]


def test_role_skips_search(monkeypatch):
    out, calls = run(monkeypatch, "role", [], [CARD])
    assert calls == []
    assert out["path"] == ["입력 읽기", "사실 확인", "라우팅", "생성"]


@pytest.mark.parametrize("question_type, route, facts, code", [
    ("out_of_scope", {}, {}, "out_of_scope"),
    ("other_part", {}, {}, "not_found"),
    ("rating", {"reason": "part_missing"}, {"parts": {"1N4001": False}}, "part_missing"),
    ("candidate_judge", {"reason": "part_missing"}, {"parts": {"BAT85": False}}, "part_missing"),
    ("rating", {"reason": "revision_missing"}, {"parts": {"1N5817": True}, "revisions": {"K9999": False}}, "revision_missing"),
])
def test_scope_is_refused_at_the_first_stage_without_searching(monkeypatch, question_type, route, facts, code):
    """범위 밖 · 다른 부품 · 코퍼스에 없는 품번 · 개정판은 라우팅 바로 뒤에서 거절한다. 검색기는 한 번도 부르지 않는다."""
    from backend.multi_agent.supervisor import Facts
    out, calls = run(monkeypatch, question_type, [], [CARD], lookup=lambda state: Facts(**facts), **route)
    assert len(calls) == 0
    assert out["path"] == ["입력 읽기", "사실 확인", "라우팅", "거절"]
    assert out["refusal"]["code"] == code and out["answer"] == out["refusal"]["message"]


def test_chat_is_answered_with_the_router_reply_without_searching(monkeypatch):
    out, calls = run(monkeypatch, "chat", [], [CARD], reply="안녕하세요! 회로 속 다이오드의 역할과 대체 후보를 도와 드려요.")
    assert calls == [] and out["path"] == ["입력 읽기", "사실 확인", "라우팅", "짧은 답"]
    assert out["answer"].startswith("안녕하세요") and out["check"] == {}


@pytest.mark.parametrize("question, parts", [("1N5817 지금 가격이랑 재고 알려 줘", ["1N5817"]), ("D1 가격 얼마야?", ["1N4001"])])
def test_price_question_ends_with_the_notice_and_no_mouser_call(monkeypatch, question, parts):
    """가격 질문은 가격 안내로 끝난다: 검색 · HTTP(Mouser) 호출 없이 물은 품번만 남고, 상태와 답에 가격 · 재고 값이 없다(ADR 0009).

    질문에 품번이 없으면 대상(D1) 값의 품번을 쓴다(검색 노드와 같은 규칙).
    """
    import httpx
    from backend.multi_agent.messages import price_message

    def no_http(*args, **kwargs):
        raise AssertionError("그래프가 HTTP를 부르면 안 된다(Mouser는 그래프 밖 /api/prices만)")
    monkeypatch.setattr(httpx.Client, "send", no_http)
    monkeypatch.setattr(nodes.llm, "chat", lambda system, user, schema: schema(question_type="price"))
    calls = []
    out = build_graph(retriever=lambda q, *, parts=None: calls.append(q) or []).invoke({"input": INPUT.replace(QUESTION, question)})
    assert calls == [] and out["path"] == ["입력 읽기", "사실 확인", "라우팅", "가격 안내"]
    assert out["price_parts"] == parts and out["answer"] == price_message(parts)  # 정해진 안내뿐이라 값이 끼어들 자리가 없다
    assert {k for k in out if "price" in k or "stock" in k} == {"price_parts"} and out["check"] == {}


@pytest.mark.parametrize("question_type", ["candidate_judge", "candidate_find"])
def test_candidate_questions_use_the_search_loop_when_no_judge_is_wired(monkeypatch, question_type):
    """사양 표 도구(specs · find)를 넘기지 않으면 판정 · 찾기 질문은 예전처럼 검색 고리로 간다(기존 호출을 깨지 않는다)."""
    out, calls = run(monkeypatch, question_type, [[7]], [CARD])
    assert out["path"] == ["입력 읽기", "사실 확인", "라우팅", "재작성", "검색", "채점", "생성"] and len(calls) == 1


def test_facts_are_checked_before_routing_and_shown_to_the_router(monkeypatch):
    """사실 확인 노드가 라우팅 앞에서 품번을 코퍼스 목록과 대조하고, 그 결과가 라우팅 LLM 입력에 멀티 Supervisor와 같은 글로 들어간다."""
    from backend.multi_agent.supervisor import Facts
    seen = []
    monkeypatch.setattr(nodes.llm, "chat", lambda system, user, schema: seen.append(user) or (
        schema(question_type="role") if schema is nodes.Route else schema(answer="D1은 역전압 보호 다이오드다 [넷리스트].")))
    out = build_graph(retriever=lambda q, *, parts=None: [], lookup=lambda state: Facts(parts={"1N5817": True})).invoke({"input": INPUT})
    assert out["path"][:3] == ["입력 읽기", "사실 확인", "라우팅"]
    assert out["facts"] == {"parts": {"1N5817": True}, "revisions": {}}
    assert "Verified facts:\n- part 1N5817: in corpus" in seen[0]


def test_no_lookup_leaves_facts_empty(monkeypatch):
    out, _ = run(monkeypatch, "role", [], [CARD])
    assert out["facts"] == {"parts": {}, "revisions": {}}


def test_second_message_in_same_thread_starts_fresh(monkeypatch):
    """체크포인터로 같은 thread에 두 번째 질문이 오면 앞 턴의 query·tries가 남아 재작성 없이 거절되거나 낡은 검색어로 찾으면 안 된다."""
    from langgraph.checkpoint.memory import MemorySaver
    grades = iter([[], [], [7]])  # 1턴: 통과 없음 2번(거절), 2턴: 첫 채점에서 통과
    monkeypatch.setattr(nodes.llm, "chat", lambda system, user, schema: (
        schema(question_type="rating") if schema is nodes.Route else
        schema(passed_ids=next(grades)) if schema is nodes.Grade else
        schema(query=REWRITTEN) if schema is nodes.Rewrite else schema(answer="20 V다 [7].")))
    calls = []
    app = build_graph(retriever=lambda q, *, parts=None: calls.append(q) or [CARD], checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t"}}
    app.invoke({"input": INPUT}, cfg)
    out = app.invoke({"input": INPUT}, cfg)
    assert calls[-1] == REWRITTEN and len(calls) == 3  # 2턴도 첫 검색부터 재작성한 검색어로 찾고, 1턴의 tries가 남지 않는다
    assert out["tries"] == 1 and out["path"][-1] == "생성"


# ── 판정 길: 판정 읽기 → 판정(빠진 값 인터럽트 1번) → 답 틀. 멀티의 Spec 에이전트 코드를 그대로 쓴다 ──
JUDGE_INPUT = ("회로: SparkFun Breadboard Supply\n"
               "넷리스트: data/circuits/collected/samples/breadboard_supply/converted/circuit.net\n"
               "대상: D1\n사용 조건: 입력 전압의 최댓값은 20V\n질문: D1을 TSC 1N5817로 바꿔도 돼?")
SPEC_ROWS = [{"part": "1N5817", "code": "VRRM", "min": None, "typ": None, "max": 20.0, "text": None, "unit": "V",
              "source_value_text": "20", "test_condition": None,
              "citation": {"document": "a.pdf", "page": 1, "table": "ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)",
                           "row": "VRRM", "chunk_index": 1}}]


def judge_app(monkeypatch, specs, calls, read=None, revisions=None):
    """판정 길을 이은 앱. 라우팅은 nodes.llm 가짜로, 판정 읽기는 chat 인자로 정해 둔 읽기 결과를 낸다."""
    from langgraph.checkpoint.memory import InMemorySaver
    from backend.multi_agent.agents import judge as J
    from backend.multi_agent.supervisor import Facts
    monkeypatch.setattr(nodes.llm, "chat", lambda system, user, schema: schema(question_type="candidate_judge"))
    read = read or J.JudgeRead(role="R01", candidates=["1N5817"],
                               values=[J.Value(name="v_in_max", number=20, unit="V", quote="입력 전압의 최댓값은 20V")])
    facts = Facts(parts={"1N5817": True}, revisions=revisions or {})
    return build_graph(retriever=lambda q, *, parts=None: calls.append(q) or [], lookup=lambda state: facts,
                       specs=specs, find=lambda *a: [], chat=lambda node, system, user, schema: read, checkpointer=InMemorySaver())


def test_judge_path_asks_once_then_answers_with_the_code_template(monkeypatch):
    from langgraph.types import Command
    calls = []
    app = judge_app(monkeypatch, lambda part, codes=None: SPEC_ROWS, calls)
    config = {"configurable": {"thread_id": "j1"}}
    state = app.invoke({"input": JUDGE_INPUT}, config)
    assert "__interrupt__" in state  # 빠진 회로 값을 한 번 묻는다
    state = app.invoke(Command(resume={"answers": {}}), config)  # 평가 실행기처럼 빈 답(= 모름)으로 재개
    assert state["path"] == ["입력 읽기", "사실 확인", "라우팅", "판정 읽기", "판정", "답 틀"]  # 재개해도 읽기는 다시 돌지 않는다
    assert calls == []  # 판정 길은 검색 고리를 거치지 않는다
    assert "불충족" in state["answer"] and "a.pdf" in state["answer"] and "같은 동작은 보장하지 않" in state["answer"]
    assert "reports" not in state and state["check"] == {"used": [], "judgement": True}


def test_spec_table_failure_ends_as_a_search_error_refusal(monkeypatch):
    from langgraph.types import Command

    def broken(part, codes=None):
        raise RetrievalUnavailableError("timeout")
    app = judge_app(monkeypatch, broken, [])
    config = {"configurable": {"thread_id": "j2"}}
    app.invoke({"input": JUDGE_INPUT}, config)
    state = app.invoke(Command(resume={"answers": {}}), config)
    assert state["path"][-2:] == ["판정", "거절"] and state["refusal"]["code"] == "search_error"


@pytest.mark.parametrize("extra, revisions, code", [
    ({"required_specs": [{"words": "1kHz 순방향 전류 잡음 밀도", "code": "none"}]}, {}, "not_found"),
    ({"maker_wanted": "Toshiba"}, {}, "part_missing"),
    ({"revision_wanted": "2027년판"}, {}, "revision_missing"),
    ({"revision_wanted": "G2710"}, {"G2710": False}, "revision_missing"),  # 라우팅이 사실을 놓쳐 판정 길로 와도 거절
])
def test_requirement_outside_the_corpus_ends_as_a_refusal_without_asking(monkeypatch, extra, revisions, code):
    """코퍼스 밖 요구(SPEC 8.3)는 인터럽트 · 사양 표 조회 없이 판정 → 거절로 끝나고, 멀티와 같은 문구 · 사유 코드를 남긴다."""
    from backend.multi_agent.agents import judge as J
    from backend.multi_agent.contracts import Reason
    from backend.multi_agent.messages import refusal_for
    app = judge_app(monkeypatch, lambda part, codes=None: pytest.fail("사양 표를 읽었다"), [],
                    read=J.JudgeRead(role="R01", candidates=["1N5817"], **extra), revisions=revisions)
    asked = JUDGE_INPUT + " " + extra.get("revision_wanted", "")  # 판 요구는 사용자 글에 있어야 한다(지어낸 판으로 거절하지 않게, 11-06 h3-15)
    state = app.invoke({"input": asked}, {"configurable": {"thread_id": f"gate-{code}-{extra}"}})
    assert "__interrupt__" not in state
    assert state["path"][-3:] == ["판정 읽기", "판정", "거절"] and state["refusal"]["code"] == code
    assert state["answer"] == refusal_for(Reason(code), state["facts"]) and "1N5817" not in state["answer"]  # 있는 품번은 없다고 하지 않는다


@pytest.mark.parametrize("kw", ["both_without_checkpointer", "specs_only", "find_only"])
def test_judge_path_needs_both_spec_tools_and_a_checkpointer(kw):
    """[왜] 판정은 인터럽트로 멈췄다 같은 thread에서 재개하므로 체크포인터가 있어야 한다. 도구 하나만 주면 켜진 척하지 않고 멈춘다."""
    from langgraph.checkpoint.memory import InMemorySaver
    specs, find = (lambda part, codes=None: []), (lambda *a: [])
    args = {"both_without_checkpointer": {"specs": specs, "find": find}, "specs_only": {"specs": specs, "checkpointer": InMemorySaver()},
            "find_only": {"find": find, "checkpointer": InMemorySaver()}}[kw]
    with pytest.raises(ValueError):
        build_graph(retriever=lambda q, *, parts=None: [], **args)
