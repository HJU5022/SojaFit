"""그래프 상태의 칸이 덮어쓰기와 쌓기로 나뉘어 합쳐지는지 확인한다(SPEC 2절, 강의 2주 04강)."""
from langgraph.graph import END, START, StateGraph

from backend.graph.state import AgentState


def test_tries_and_path_accumulate_while_docs_overwrite():
    # 검색을 두 번 하는 작은 그래프: 노드가 돌려준 칸만 메모장에 합쳐진다
    def first_search(state):
        return {"docs": [{"id": "a"}], "tries": 1, "path": ["검색"]}

    def second_search(state):
        return {"docs": [{"id": "b"}], "tries": 1, "path": ["검색"]}

    graph = StateGraph(AgentState)
    graph.add_node("first", first_search)
    graph.add_node("second", second_search)
    graph.add_edge(START, "first")
    graph.add_edge("first", "second")
    graph.add_edge("second", END)

    result = graph.compile().invoke({"input": "질문", "tries": 0, "path": []})

    assert result["tries"] == 2                   # 쌓기: 1 + 1
    assert result["path"] == ["검색", "검색"]       # 쌓기: 이어 붙인다
    assert result["docs"] == [{"id": "b"}]        # 덮어쓰기: 마지막 검색 결과만 남는다
    assert result["input"] == "질문"               # 아무 노드도 안 건드린 칸은 그대로다
