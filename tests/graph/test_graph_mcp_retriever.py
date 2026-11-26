"""LangGraph용 MCP 검색 어댑터의 응답 검증과 세션 수명을 확인한다."""
import asyncio
from contextlib import asynccontextmanager
import json
from types import SimpleNamespace

import pytest

from backend.graph.mcp_retriever import (
    RetrievalUnavailableError,
    StdioMcpRetriever,
    decode_search_result,
)


CARD = {"chunk_id": 7, "file": "1N5817 SERIES_H2104.pdf", "page": 1,
        "content": "VRRM 20 V", "table": None, "doc_parts": ["1n5817"]}


def result(value, *, is_error=False):
    return SimpleNamespace(isError=is_error,
                           content=[SimpleNamespace(text=json.dumps(value))])


def structured_result(value):
    content = [SimpleNamespace(text=json.dumps(card)) for card in value]
    return SimpleNamespace(isError=False, structuredContent={"result": value}, content=content)


@pytest.mark.parametrize("value", [[CARD], []])
def test_decode_search_result_accepts_card_lists(value):
    assert decode_search_result(result(value)) == value


@pytest.mark.parametrize("value", [[CARD], []])
def test_decode_search_result_accepts_pr44_structured_result(value):
    """PR #44의 실제 FastMCP 계약인 structuredContent.result를 청크 목록으로 읽는다."""
    assert decode_search_result(structured_result(value)) == value


def test_decode_search_result_rejects_tool_error():
    with pytest.raises(RetrievalUnavailableError) as error:
        decode_search_result(result({"message": "private"}, is_error=True))
    assert error.value.kind == "tool_error"


@pytest.mark.parametrize("bad", [
    "not-json",
    {},
    [dict(CARD, chunk_id=True)],
    [dict(CARD, doc_parts="1n5817")],
])
def test_decode_search_result_rejects_invalid_payload(bad):
    payload = bad if bad == "not-json" else json.dumps(bad)
    raw = SimpleNamespace(isError=False, content=[SimpleNamespace(text=payload)])
    with pytest.raises(RetrievalUnavailableError) as error:
        decode_search_result(raw)
    assert error.value.kind == "invalid_response"


class FakeSession:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        value = next(self.outputs)
        if value == "hang":
            await asyncio.sleep(60)
        return result(value)


def fake_context(session, events):
    @asynccontextmanager
    async def open_session(params):
        events.append("open")
        try:
            yield session
        finally:
            events.append("close")
    return open_session


def test_stdio_retriever_reuses_one_session_and_sends_contract():
    events = []
    session = FakeSession([[CARD], []])
    with StdioMcpRetriever(session_context_factory=fake_context(session, events)) as retriever:
        assert retriever("1N5817 VRRM", parts=["1N5817"]) == [CARD]
        assert retriever("rewritten", parts=["1N5817"]) == []
    assert events == ["open", "close"]
    assert session.calls == [
        ("search_corpus", {"query": "1N5817 VRRM", "k": 5, "parts": ["1N5817"]}),
        ("search_corpus", {"query": "rewritten", "k": 5, "parts": ["1N5817"]}),
    ]


def test_stdio_retriever_turns_timeout_into_safe_kind():
    session = FakeSession(["hang"])
    with StdioMcpRetriever(timeout_seconds=0.01,
                           session_context_factory=fake_context(session, [])) as retriever:
        with pytest.raises(RetrievalUnavailableError) as error:
            retriever("q", parts=None)
    assert error.value.kind == "timeout"



def test_stdio_retriever_check_sends_contract_on_same_session():
    answer = {"parts": {"1N5819": True}, "revisions": {}}
    session = FakeSession([answer])
    with StdioMcpRetriever(session_context_factory=fake_context(session, [])) as retriever:
        assert retriever.check(["1N5819"], []) == answer
    assert session.calls == [("check_corpus", {"parts": ["1N5819"], "revisions": []})]


@pytest.mark.parametrize("bad", [[], {"parts": {"A": "yes"}, "revisions": {}}, {"parts": {}}, {"parts": [], "revisions": {}}])
def test_stdio_retriever_check_rejects_invalid_payload(bad):
    session = FakeSession([bad])
    with StdioMcpRetriever(session_context_factory=fake_context(session, [])) as retriever:
        with pytest.raises(RetrievalUnavailableError) as info:
            retriever.check(["A"], [])
    assert info.value.kind == "invalid_response"
