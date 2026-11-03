"""격리 DB가 있을 때만 실제 stdio MCP를 거쳐 LangGraph 검색을 확인한다."""
import os
import re

import pytest

from backend.graph import nodes
from backend.graph.build import build_graph
from backend.graph.mcp_retriever import StdioMcpRetriever


def _has_corpus():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        return False
    import psycopg
    with psycopg.connect(url) as conn:
        return (conn.execute("SELECT to_regclass('document_chunks') IS NOT NULL").fetchone()[0]
                and conn.execute("SELECT EXISTS (SELECT 1 FROM document_chunks)").fetchone()[0])


@pytest.mark.skipif(not _has_corpus(), reason="TEST_DATABASE_URL에 격리 코퍼스가 있을 때만 돈다")
def test_graph_reaches_real_search_through_stdio_mcp(monkeypatch):
    env = {"DATABASE_URL": os.environ["TEST_DATABASE_URL"],
           "DEMO_MODE": "1", "EXA_WEB_SEARCH_ENABLED": "0"}
    chosen = []

    def fake_chat(system, user, schema):
        if schema is nodes.Route:
            return schema(question_type="rating")
        if schema is nodes.Grade:
            ids = [int(value) for value in re.findall(r"\[(\d+)\]", user)]
            chosen[:] = ids[:1]
            return schema(passed_ids=chosen)
        if schema is nodes.Answer:
            return schema(answer=f"격리 DB MCP 검색 근거 [{chosen[0]}].")
        raise AssertionError(f"예상하지 않은 LLM 호출: {schema.__name__}")

    monkeypatch.setattr(nodes.llm, "chat", fake_chat)
    with StdioMcpRetriever(env=env, timeout_seconds=30.0) as retriever:
        app = build_graph(retriever=retriever)
        state = app.invoke({"input": "질문: SS34 정격이 어떻게 돼?"})
    assert state["path"] == ["입력 읽기", "라우팅", "검색", "채점", "생성"]
    assert state["docs"]
    assert all(card["file"] == "SS32 SERIES_Q2412.pdf" for card in state["docs"])
    assert all(card["document_key"] and card["page"] for card in state["docs"])
    assert state["retrieval_error"] is None
