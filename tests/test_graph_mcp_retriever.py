"""LangGraph용 MCP 검색 어댑터의 응답 검증과 세션 수명을 확인한다."""
import json
from types import SimpleNamespace

import pytest

from backend.graph.mcp_retriever import RetrievalUnavailableError, decode_search_result


CARD = {"chunk_id": 7, "file": "1N5817 SERIES_H2104.pdf", "page": 1,
        "content": "VRRM 20 V", "table": None, "doc_parts": ["1n5817"]}


def result(value, *, is_error=False):
    return SimpleNamespace(isError=is_error,
                           content=[SimpleNamespace(text=json.dumps(value))])


@pytest.mark.parametrize("value", [[CARD], []])
def test_decode_search_result_accepts_card_lists(value):
    assert decode_search_result(result(value)) == value


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
