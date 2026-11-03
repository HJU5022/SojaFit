"""LangGraph 검색 경계에서 사용하는 MCP 검색 오류 타입."""
from typing import Literal


RetrievalErrorKind = Literal["mcp_unavailable", "timeout", "tool_error", "invalid_response"]


class RetrievalUnavailableError(RuntimeError):
    """정상 빈 검색 결과와 구분해야 하는 MCP 검색 장애."""

    def __init__(self, kind: RetrievalErrorKind):
        self.kind = kind
        super().__init__(kind)
