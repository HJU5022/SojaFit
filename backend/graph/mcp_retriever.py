"""LangGraph 검색 경계에서 사용하는 MCP 검색 오류 타입."""
import json
from typing import Literal


RetrievalErrorKind = Literal["mcp_unavailable", "timeout", "tool_error", "invalid_response"]


class RetrievalUnavailableError(RuntimeError):
    """정상 빈 검색 결과와 구분해야 하는 MCP 검색 장애."""

    def __init__(self, kind: RetrievalErrorKind):
        self.kind = kind
        super().__init__(kind)


REQUIRED_CARD_FIELDS = {"chunk_id", "file", "page", "content", "table", "doc_parts"}


def _valid_card(card: object) -> bool:
    return (isinstance(card, dict) and REQUIRED_CARD_FIELDS <= card.keys()
            and isinstance(card["chunk_id"], int) and not isinstance(card["chunk_id"], bool)
            and isinstance(card["file"], str)
            and isinstance(card["page"], int) and not isinstance(card["page"], bool)
            and isinstance(card["content"], str)
            and (card["table"] is None or isinstance(card["table"], str))
            and isinstance(card["doc_parts"], list)
            and all(isinstance(part, str) for part in card["doc_parts"]))


def decode_search_result(result) -> list[dict]:
    """MCP 텍스트 응답을 그래프 검색 카드 목록으로 검증해 변환한다."""
    if getattr(result, "isError", False) is True:
        raise RetrievalUnavailableError("tool_error")
    content = getattr(result, "content", None)
    if (not isinstance(content, list) or len(content) != 1
            or not isinstance(getattr(content[0], "text", None), str)):
        raise RetrievalUnavailableError("invalid_response")
    try:
        payload = json.loads(content[0].text)
    except (json.JSONDecodeError, TypeError):
        raise RetrievalUnavailableError("invalid_response") from None
    if not isinstance(payload, list) or not all(_valid_card(card) for card in payload):
        raise RetrievalUnavailableError("invalid_response")
    return payload
