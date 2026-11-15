"""LangGraph 검색 경계의 MCP 검색기: stdio MCP 세션 재사용(`StdioMcpRetriever`), 응답 검증, 빈 결과와 장애를 구분하는 `RetrievalUnavailableError`."""
import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import asynccontextmanager
import json
import os
import sys
import threading
from typing import Literal

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


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
    """MCP 구조화 응답을 그래프 검색 청크 목록으로 검증해 변환한다."""
    if getattr(result, "isError", False) is True:
        raise RetrievalUnavailableError("tool_error")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict) and "result" in structured:
        payload = structured["result"]
    else:
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


def decode_check_result(result) -> dict:
    """`check_corpus` 응답을 {"parts": {이름: bool}, "revisions": {이름: bool}}로 검증해 변환한다."""
    if getattr(result, "isError", False) is True:
        raise RetrievalUnavailableError("tool_error")
    payload = getattr(result, "structuredContent", None)
    if not isinstance(payload, dict) or "parts" not in payload:
        content = getattr(result, "content", None)
        if (not isinstance(content, list) or len(content) != 1
                or not isinstance(getattr(content[0], "text", None), str)):
            raise RetrievalUnavailableError("invalid_response")
        try:
            payload = json.loads(content[0].text)
        except (json.JSONDecodeError, TypeError):
            raise RetrievalUnavailableError("invalid_response") from None
    if not (isinstance(payload, dict) and all(
            isinstance(payload.get(key), dict) and all(isinstance(v, bool) for v in payload[key].values())
            for key in ("parts", "revisions"))):
        raise RetrievalUnavailableError("invalid_response")
    return {"parts": payload["parts"], "revisions": payload["revisions"]}


@asynccontextmanager
async def open_stdio_session(params):
    """stdio 서버를 시작하고 초기화된 MCP 세션 하나를 제공한다."""
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            yield session


class StdioMcpRetriever:
    """동기 LangGraph에서 재사용할 수 있는 stdio MCP 검색기."""

    def __init__(self, command: str = sys.executable,
                 args: list[str] | None = None,
                 env: dict[str, str] | None = None,
                 timeout_seconds: float = 30.0,
                 session_context_factory=open_stdio_session):
        self.timeout_seconds = timeout_seconds
        self._session_context_factory = session_context_factory
        self._params = StdioServerParameters(
            command=command,
            args=args or ["-m", "backend.mcp_skill.mcp_server.server"],
            env={**os.environ, **(env or {})},
        )
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._session = None
        self._startup_error: BaseException | None = None

    def __enter__(self):
        if self._thread is not None:
            raise RuntimeError("MCP retriever context는 한 번만 열 수 있습니다")
        self._thread = threading.Thread(
            target=self._thread_main, name="sojafit-mcp", daemon=True)
        self._thread.start()
        if not self._ready.wait(self.timeout_seconds):
            raise RetrievalUnavailableError("timeout")
        if self._startup_error is not None or self._session is None:
            raise RetrievalUnavailableError("mcp_unavailable")
        return self

    def __call__(self, query: str, *, parts: list[str] | None = None) -> list[dict]:
        return self._run(self._call(query, parts))

    def _run(self, coroutine):
        """세션 스레드의 이벤트 루프에서 코루틴을 돌리고, 장애는 `RetrievalUnavailableError`로 바꿔 던진다."""
        if (self._thread is None or not self._thread.is_alive()
                or self._loop is None or self._session is None):
            coroutine.close()  # [왜] 돌리지 못한 코루틴은 닫아야 "never awaited" 경고가 안 난다
            raise RetrievalUnavailableError("mcp_unavailable")
        from backend.services import llm
        budget = llm._evaluation_budget.get()
        timeout = self.timeout_seconds
        if budget is not None and budget.on_reserve is not None:
            try:
                timeout = min(timeout, budget.remaining())
            except Exception:
                coroutine.close()
                raise
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout)
        except FutureTimeoutError:
            future.cancel()
            raise RetrievalUnavailableError("timeout") from None
        except RetrievalUnavailableError:
            raise
        except BaseException:
            raise RetrievalUnavailableError("mcp_unavailable") from None

    def check(self, parts: list[str], revisions: list[str]) -> dict:
        """코퍼스에 품번 · 개정 코드가 있는지 `check_corpus` 도구로 묻는다(같은 세션을 쓴다)."""
        return self._run(self._check(parts, revisions))

    def __exit__(self, exc_type, exc, traceback):
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
        if self._thread is not None:
            self._thread.join(max(self.timeout_seconds, 1.0))
        if self._thread is not None and self._thread.is_alive() and exc_type is None:
            raise RetrievalUnavailableError("mcp_unavailable")
        return False

    def _thread_main(self) -> None:
        try:
            asyncio.run(self._serve())
        except BaseException as error:
            self._startup_error = error
            self._ready.set()

    async def _serve(self) -> None:
        try:
            async with self._session_context_factory(self._params) as session:
                self._loop = asyncio.get_running_loop()
                self._session = session
                self._stop = asyncio.Event()
                self._ready.set()
                await self._stop.wait()
        except BaseException as error:
            self._startup_error = error
            self._ready.set()

    async def _check(self, parts: list[str], revisions: list[str]) -> dict:
        result = await self._session.call_tool("check_corpus", {"parts": parts, "revisions": revisions})
        return decode_check_result(result)

    async def _call(self, query: str, parts: list[str] | None) -> list[dict]:
        result = await self._session.call_tool(
            "search_corpus", {"query": query, "k": 5, "parts": parts})
        return decode_search_result(result)
