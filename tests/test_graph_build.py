"""그래프 조립: 질문 종류와 채점 결과에 따라 노드가 SPEC 2절 순서로 이어지는지 확인한다. LLM과 검색기는 가짜로 바꾼다."""
import pytest

from backend.graph import nodes
from backend.graph.build import build_graph

QUESTION = "TSC 1N5817은 역전압을 몇 V까지 견뎌?"
# 평가셋 v1과 같은 입력 형식(회로·넷리스트·대상·질문). 넷리스트는 저장소의 샘플 회로다
INPUT = ("회로: SparkFun Breadboard Supply\n"
         "넷리스트: data/circuits/collected/samples/breadboard_supply/converted/circuit.net\n"
         f"대상: D1\n질문: {QUESTION}")
CARD = {"chunk_id": 7, "file": "1N5817 SERIES_H2104.pdf", "page": 1, "table": None, "doc_parts": ["1n5817"],
        "content": "Repetitive peak reverse voltage VRRM 20 V"}
REWRITTEN = "1N5817 repetitive peak reverse voltage VRRM"


def run(monkeypatch, question_type, grades, docs):
    """가짜 LLM과 가짜 검색기를 꽂고 그래프를 끝까지 돌린다. grades는 채점 LLM이 호출 순서대로 낼 통과 카드 목록이다."""
    grades = iter(grades)  # [주의] 정해 둔 것보다 채점을 더 부르면 StopIteration으로 시험이 깨진다

    def fake_chat(system, user, schema):
        if schema is nodes.Route:
            return schema(question_type=question_type)
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
    return build_graph(retriever=fake_retriever).invoke({"input": INPUT}), calls


def test_passed_card_answers_after_one_search(monkeypatch):
    out, calls = run(monkeypatch, "rating", [[7]], [CARD])
    assert out["path"] == ["입력 읽기", "라우팅", "검색", "채점", "생성"]
    # [왜] 검색어는 입력 전체가 아니라 질문 줄만이다. 회로 이름·D1까지 넣으면 BM25가 품번보다 그 낱말에 끌린다(11-02 격자 실측)
    assert calls == [(QUESTION, ["1N5817"])]
    assert out["tries"] == 1 and "[7]" in out["answer"]


def test_no_pass_rewrites_then_searches_again(monkeypatch):
    out, calls = run(monkeypatch, "rating", [[], [7]], [CARD])
    assert out["path"] == ["입력 읽기", "라우팅", "검색", "채점", "재작성", "검색", "채점", "생성"]
    assert calls == [(QUESTION, ["1N5817"]), (REWRITTEN, ["1N5817"])]  # 품번 필터는 그대로, 검색어만 바뀐다
    assert out["tries"] == 2


def test_still_no_pass_refuses_after_two_searches(monkeypatch):
    out, calls = run(monkeypatch, "rating", [[], []], [CARD])
    # 상수 MAX_TRIES가 아니라 리터럴 2와 비교한다. 상수끼리 비교하면 상한을 바꿔도 통과한다(build.py 안내)
    assert len(calls) == 2
    assert out["path"][-1] == "거절" and "검색 2번" in out["answer"]


def test_zero_cards_refuses_without_rewrite(monkeypatch):
    out, calls = run(monkeypatch, "rating", [], [])  # 채점 LLM을 부르면 StopIteration으로 깨진다
    assert len(calls) == 1
    assert out["path"] == ["입력 읽기", "라우팅", "검색", "채점", "거절"]


@pytest.mark.parametrize("question_type, last", [("out_of_scope", "거절"), ("role", "생성")])
def test_out_of_scope_and_role_skip_search(monkeypatch, question_type, last):
    out, calls = run(monkeypatch, question_type, [], [CARD])
    assert calls == []
    assert out["path"] == ["입력 읽기", "라우팅", last]
