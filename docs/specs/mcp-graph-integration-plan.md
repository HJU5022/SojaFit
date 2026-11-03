# MCP `search_corpus` LangGraph Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 동기 LangGraph 검색 주입 계약에 FastMCP stdio `search_corpus`를 연결하고 정상 빈 결과와 MCP 장애를 구분한다.

**Architecture:** `StdioMcpRetriever`가 그래프가 기대하는 동기 callable을 제공하고 내부 전용 asyncio 루프에서 stdio 서버와 `ClientSession`을 한 번 열어 재사용한다. 기존 그래프는 직접 retriever 기본값을 유지하며, MCP 어댑터가 낸 제한된 오류만 State에 기록해 빈 결과와 다른 거절 경로로 보낸다.

**Tech Stack:** Python 3.12, LangGraph 1.x, MCP Python SDK 1.x, pytest, PostgreSQL 16 + pgvector, uv.

## Global Constraints

- B는 `backend/graph/`와 그래프 통합 테스트만 구현하며 `backend/mcp_skill/mcp_server/server.py`와 A의 MCP 계약 테스트를 수정하지 않는다.
- MCP 호출은 `search_corpus(query, k=5, parts=<품번 목록 또는 null>)` 하나만 연결한다. 나머지 도구 4개 연결은 이번 계획의 범위 밖이다.
- 기존 `build_graph()`의 직접 RAG 기본 경로와 검색 최대 2회(첫 검색 + 재작성 뒤 1회)를 유지한다.
- 정상 `[]`와 MCP 장애를 구분하고, 오류 원문·키·DB URL·환경변수는 State·응답·로그에 저장하지 않는다.
- 실제 stdio 검증은 `DEMO_MODE=1`로 외부 임베딩·웹 호출을 막고, `TEST_DATABASE_URL`의 격리 DB만 사용한다.
- 운영·공유 DB와 기존 Docker 볼륨을 초기화·삭제하지 않는다.
- 패키지는 uv로만 관리한다. 현재 `mcp>=1.28,<2`가 있으므로 새 의존성을 추가하지 않는다.
- 동결 평가셋과 `evals/FROZEN.json`은 수정하지 않는다.
- 원격 push·PR 생성은 이 계획에 포함하지 않는다. 로컬 커밋은 SSH 서명 설정을 바꾸지 않고 `--no-gpg-sign`을 사용한다.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `backend/graph/mcp_retriever.py` | MCP 응답 검증, 제한된 오류, stdio 세션의 시작·재사용·종료, 동기 retriever 인터페이스 |
| `backend/graph/state.py` | `retrieval_error` 상태 타입 |
| `backend/graph/nodes.py` | MCP 전용 오류를 State로 변환하고 장애 응답을 생성 |
| `backend/graph/build.py` | 검색 직후 성공/장애 분기 |
| `tests/test_graph_mcp_retriever.py` | 응답 검증, 도구 인자, timeout, 세션 수명 단위 테스트 |
| `tests/test_graph_build.py` | 빈 결과와 장애의 그래프 경로, 재검색 상한 회귀 테스트 |
| `tests/test_graph_mcp_stdio.py` | 실제 stdio 서버와 격리 DB를 경유하는 조건부 통합 테스트 |
| `backend/graph/README.md` | MCP 검색기 주입법과 장애 의미 |
| `SPEC.md` | 그래프의 검색 장애 분기와 MCP 통합 경계 |
| `tests/README.md` | 신규 테스트 파일 설명과 조건부 DB 검사 명령 |
| `docs/GATES.md` | 세 가지 변이 확인 결과 |
| `docs/worklog/STH.md` | 변경 파일, 실행 명령, 실제 결과, 미검증 범위 |

---

### Task 1: 그래프에서 검색 장애와 빈 결과 구분

**Files:**
- Modify: `backend/graph/state.py`
- Modify: `backend/graph/nodes.py`
- Modify: `backend/graph/build.py`
- Modify: `tests/test_graph_build.py`

**Interfaces:**
- Consumes: 기존 `retriever(query: str, *, parts: list[str] | None = None) -> list[dict]`.
- Produces: `RetrievalUnavailableError.kind`, `AgentState.retrieval_error`, `after_search(state) -> "채점" | "거절"`.

- [ ] **Step 1: MCP 검색 장애가 문서 없음과 다른 경로를 타는 실패 테스트 작성**

`tests/test_graph_build.py`에 아래 테스트를 추가한다. Task 2에서 만들 예외를 먼저 import하므로 현재는 import 실패가 예상된다.

```python
from backend.graph.mcp_retriever import RetrievalUnavailableError


def test_retrieval_failure_is_not_reported_as_empty_corpus(monkeypatch):
    def fake_chat(system, user, schema):
        if schema is nodes.Route:
            return schema(question_type="rating")
        raise AssertionError(f"장애 뒤 LLM을 호출하면 안 됨: {schema.__name__}")

    calls = []

    def unavailable(question, *, parts=None):
        calls.append((question, parts))
        raise RetrievalUnavailableError("timeout")

    monkeypatch.setattr(nodes.llm, "chat", fake_chat)
    out = build_graph(retriever=unavailable).invoke({"input": INPUT})
    assert calls == [(QUESTION, ["1N5817"])]
    assert out["retrieval_error"] == {"kind": "timeout"}
    assert out["path"] == ["입력 읽기", "라우팅", "검색", "거절"]
    assert "검색 도구" in out["answer"]
    assert "데이터시트를 찾지 못" not in out["answer"]
```

- [ ] **Step 2: 실패 테스트 실행**

Run: `uv run --no-sync pytest -q tests/test_graph_build.py::test_retrieval_failure_is_not_reported_as_empty_corpus`

Expected: FAIL during collection because `backend.graph.mcp_retriever` does not exist.

- [ ] **Step 3: 제한된 오류와 State 필드의 최소 구현 추가**

`backend/graph/mcp_retriever.py`를 만들고 우선 예외만 정의한다.

```python
from typing import Literal

RetrievalErrorKind = Literal["mcp_unavailable", "timeout", "tool_error", "invalid_response"]


class RetrievalUnavailableError(RuntimeError):
    def __init__(self, kind: RetrievalErrorKind):
        self.kind = kind
        super().__init__(kind)
```

`backend/graph/state.py`의 `AgentState` 검색 상태에 다음 필드를 추가한다.

```python
retrieval_error: dict[str, str] | None
```

`backend/graph/nodes.py`에서 예외를 import하고 `search()`의 retriever 호출만 감싼다.

```python
from backend.graph.mcp_retriever import RetrievalUnavailableError

try:
    docs = retriever(query, parts=parts)
except RetrievalUnavailableError as error:
    return {"query": query, "parts": parts, "docs": [],
            "retrieval_error": {"kind": error.kind}, "tries": 1, "path": ["검색"]}
return {"query": query, "parts": parts, "docs": docs,
        "retrieval_error": None, "tries": 1, "path": ["검색"]}
```

`refuse()`의 범위 밖 처리 다음, 문서 없음 처리 전에 장애 응답을 추가한다.

```python
if state.get("retrieval_error"):
    return {"answer": "검색 도구를 사용할 수 없어 문서 근거를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.",
            "check": {}, "skill": skill_info, "path": ["거절"]}
```

`backend/graph/build.py`에 분기 함수를 추가하고 기존 `검색 → 채점` 단일 edge를 조건부 edge로 바꾼다.

```python
def after_search(state: AgentState) -> str:
    return "거절" if state.get("retrieval_error") else "채점"

b.add_conditional_edges("검색", after_search, {"채점": "채점", "거절": "거절"})
```

- [ ] **Step 4: 장애 테스트와 기존 그래프 테스트 실행**

Run: `uv run --no-sync pytest -q tests/test_graph_build.py tests/test_graph_search.py tests/test_graph_refuse.py`

Expected: PASS. 기존 빈 목록 테스트의 path는 `입력 읽기→라우팅→검색→채점→거절`, 장애 테스트는 `입력 읽기→라우팅→검색→거절`이어야 한다.

- [ ] **Step 5: Task 1 로컬 커밋**

```powershell
git add backend/graph/mcp_retriever.py backend/graph/state.py backend/graph/nodes.py backend/graph/build.py tests/test_graph_build.py
git commit --no-gpg-sign -m "feat(graph): 검색 장애를 빈 결과와 구분한다"
```

---

### Task 2: MCP `search_corpus` 응답 검증

**Files:**
- Modify: `backend/graph/mcp_retriever.py`
- Create: `tests/test_graph_mcp_retriever.py`

**Interfaces:**
- Consumes: MCP `CallToolResult`의 `isError`와 `content`.
- Produces: `decode_search_result(result) -> list[dict]`; 실패 시 `RetrievalUnavailableError("tool_error" | "invalid_response")`.

- [ ] **Step 1: 정상·빈 목록·오류·형식 위반 테스트 작성**

`tests/test_graph_mcp_retriever.py`를 만들고 아래 fixture와 테스트를 작성한다.

```python
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


@pytest.mark.parametrize("bad", ["not-json", {}, [dict(CARD, chunk_id=True)],
                                   [dict(CARD, doc_parts="1n5817")]])
def test_decode_search_result_rejects_invalid_payload(bad):
    payload = bad if bad == "not-json" else json.dumps(bad)
    raw = SimpleNamespace(isError=False, content=[SimpleNamespace(text=payload)])
    with pytest.raises(RetrievalUnavailableError) as error:
        decode_search_result(raw)
    assert error.value.kind == "invalid_response"
```

- [ ] **Step 2: 응답 검증 테스트 실패 확인**

Run: `uv run --no-sync pytest -q tests/test_graph_mcp_retriever.py`

Expected: FAIL because `decode_search_result` is not defined.

- [ ] **Step 3: 엄격한 decoder 구현**

`backend/graph/mcp_retriever.py`에 다음 함수를 추가한다.

```python
import json

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
```

- [ ] **Step 4: decoder와 MCP 서버 계약 테스트 실행**

Run: `uv run --no-sync pytest -q tests/test_graph_mcp_retriever.py tests/test_mcp_search.py tests/test_mcp_manifest.py`

Expected: PASS. A 소유 테스트 파일은 수정하지 않는다.

- [ ] **Step 5: Task 2 로컬 커밋**

```powershell
git add backend/graph/mcp_retriever.py tests/test_graph_mcp_retriever.py
git commit --no-gpg-sign -m "feat(graph): MCP 검색 응답을 검증한다"
```

---

### Task 3: 지속 stdio 세션을 쓰는 동기 retriever 구현

**Files:**
- Modify: `backend/graph/mcp_retriever.py`
- Modify: `tests/test_graph_mcp_retriever.py`

**Interfaces:**
- Consumes: `session_context_factory(StdioServerParameters) -> AsyncContextManager[ClientSession]`.
- Produces: `StdioMcpRetriever(command, args, env, timeout_seconds, session_context_factory)`, `__enter__`, `__call__(query, *, parts=None)`, `__exit__`.

- [ ] **Step 1: 도구 인자·세션 재사용·종료·timeout 테스트 작성**

테스트용 async context와 세션을 추가한다.

```python
from contextlib import asynccontextmanager
import asyncio

from backend.graph.mcp_retriever import StdioMcpRetriever


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
```

- [ ] **Step 2: 수명 테스트 실패 확인**

Run: `uv run --no-sync pytest -q tests/test_graph_mcp_retriever.py -k 'stdio_retriever'`

Expected: FAIL because `StdioMcpRetriever` is not defined.

- [ ] **Step 3: async session context와 전용 실행 루프 구현**

`backend/graph/mcp_retriever.py`에 기본 stdio context를 추가한다.

```python
from contextlib import asynccontextmanager
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@asynccontextmanager
async def open_stdio_session(params):
    async with stdio_client(params) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            yield session
```

`StdioMcpRetriever`는 아래 코드대로 구현한다.

```python
import asyncio
from concurrent.futures import TimeoutError as FutureTimeoutError
import os
import sys
import threading


class StdioMcpRetriever:
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
        if (self._thread is None or not self._thread.is_alive()
                or self._loop is None or self._session is None):
            raise RetrievalUnavailableError("mcp_unavailable")
        future = asyncio.run_coroutine_threadsafe(self._call(query, parts), self._loop)
        try:
            return future.result(self.timeout_seconds)
        except FutureTimeoutError:
            future.cancel()
            raise RetrievalUnavailableError("timeout") from None
        except RetrievalUnavailableError:
            raise
        except BaseException:
            raise RetrievalUnavailableError("mcp_unavailable") from None

    def __exit__(self, exc_type, exc, traceback):
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
        if self._thread is not None:
            self._thread.join(self.timeout_seconds)
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

    async def _call(self, query: str, parts: list[str] | None) -> list[dict]:
        result = await self._session.call_tool(
            "search_corpus", {"query": query, "k": 5, "parts": parts})
        return decode_search_result(result)
```

구현 규칙은 다음과 같이 고정한다.

- 기본 args는 `['-m', 'backend.mcp_skill.mcp_server.server']`.
- `StdioServerParameters.env`는 `{**os.environ, **env}`로 구성하되 로그에 출력하지 않는다.
- `__enter__`는 30초 안에 ready가 오지 않거나 session 초기화 예외가 있으면 `mcp_unavailable`을 발생시킨다.
- `__call__`은 `asyncio.run_coroutine_threadsafe()`로 `_call`을 제출하고 `future.result(timeout_seconds)`로 기다린다.
- `concurrent.futures.TimeoutError`이면 future를 cancel하고 `timeout`을 발생시킨다.
- `_call`에서 발생한 `RetrievalUnavailableError`는 kind를 유지한다. 그 밖의 예외는 원문 없이 `mcp_unavailable`로 바꾼다.
- `__exit__`는 기존 예외가 있을 때 종료 오류로 덮어쓰지 않는다. 기존 예외가 없는데 thread가 제한 시간 뒤에도 살아 있으면 `mcp_unavailable`을 발생시킨다.

- [ ] **Step 4: retriever 단위 테스트와 누수 확인 실행**

Run: `uv run --no-sync pytest -q tests/test_graph_mcp_retriever.py`

Expected: PASS, 테스트 종료 뒤 `mcp-server` thread가 남지 않는다.

- [ ] **Step 5: Task 3 로컬 커밋**

```powershell
git add backend/graph/mcp_retriever.py tests/test_graph_mcp_retriever.py
git commit --no-gpg-sign -m "feat(graph): stdio MCP 검색 세션을 연결한다"
```

---

### Task 4: MCP retriever를 통한 그래프 정상·재검색 경로 검증

**Files:**
- Modify: `tests/test_graph_build.py`
- Modify: `tests/test_graph_mcp_retriever.py`

**Interfaces:**
- Consumes: Task 3의 `StdioMcpRetriever` callable.
- Produces: 기존 graph path에서 동일 세션의 1회·2회 MCP 검색 증거.

- [ ] **Step 1: retriever와 그래프를 함께 실행하는 테스트 작성**

`tests/test_graph_mcp_retriever.py`에 graph imports와 고정 입력을 추가하고, 같은 파일의 `FakeSession`·`fake_context`를 사용해 다음 실행 가능한 helper와 테스트를 추가한다.

```python
from backend.graph import nodes
from backend.graph.build import build_graph

QUESTION = "TSC 1N5817은 역전압을 몇 V까지 견뎌?"
INPUT = f"질문: {QUESTION}"
REWRITTEN = "1N5817 repetitive peak reverse voltage VRRM"


def graph_chat(grades):
    grades = iter(grades)

    def fake(system, user, schema):
        if schema is nodes.Route:
            return schema(question_type="rating")
        if schema is nodes.Grade:
            return schema(passed_ids=next(grades))
        if schema is nodes.Rewrite:
            return schema(query=REWRITTEN)
        if schema is nodes.Answer:
            return schema(answer="1N5817의 반복 피크 역전압은 20 V다 [7].")
        raise AssertionError(schema)
    return fake


def test_graph_uses_mcp_retriever_for_one_search(monkeypatch):
    events = []
    session = FakeSession([[CARD]])
    monkeypatch.setattr(nodes.llm, "chat", graph_chat([[7]]))
    with StdioMcpRetriever(session_context_factory=fake_context(session, events)) as retriever:
        out = build_graph(retriever=retriever).invoke({"input": INPUT})
    assert out["path"] == ["입력 읽기", "라우팅", "검색", "채점", "생성"]
    assert session.calls == [
        ("search_corpus", {"query": QUESTION, "k": 5, "parts": ["1N5817"]})]
    assert events == ["open", "close"]


def test_graph_reuses_mcp_session_for_rewritten_search(monkeypatch):
    events = []
    session = FakeSession([[CARD], [CARD]])
    monkeypatch.setattr(nodes.llm, "chat", graph_chat([[], [7]]))
    with StdioMcpRetriever(session_context_factory=fake_context(session, events)) as retriever:
        out = build_graph(retriever=retriever).invoke({"input": INPUT})
    assert out["path"] == ["입력 읽기", "라우팅", "검색", "채점",
                           "재작성", "검색", "채점", "생성"]
    assert session.calls == [
        ("search_corpus", {"query": QUESTION, "k": 5, "parts": ["1N5817"]}),
        ("search_corpus", {"query": REWRITTEN, "k": 5, "parts": ["1N5817"]}),
    ]
    assert events == ["open", "close"]
    assert out["tries"] == 2
```

- [ ] **Step 2: 새 그래프 통합 테스트 실행**

Run: `uv run --no-sync pytest -q tests/test_graph_build.py -k 'mcp_retriever'`

Expected: PASS. 실패하면 Task 3의 callable 계약 또는 graph error branch만 수정하고 MCP 서버 코드는 수정하지 않는다.

- [ ] **Step 3: 검색 관련 전체 회귀 테스트 실행**

Run: `uv run --no-sync pytest -q tests/test_graph_build.py tests/test_graph_search.py tests/test_graph_mcp_retriever.py tests/test_mcp_search.py tests/test_rag_retrieve.py`

Expected: PASS with only the existing `TEST_DATABASE_URL` skip allowed.

- [ ] **Step 4: Task 4 로컬 커밋**

```powershell
git add tests/test_graph_build.py tests/test_graph_mcp_retriever.py
git commit --no-gpg-sign -m "test(graph): MCP 검색과 재검색 경로를 검증한다"
```

---

### Task 5: 실제 stdio 서버와 격리 DB 통합 검사

**Files:**
- Create: `tests/test_graph_mcp_stdio.py`
- Modify: `tests/README.md`

**Interfaces:**
- Consumes: `TEST_DATABASE_URL`, 실제 `backend.mcp_skill.mcp_server.server`, `StdioMcpRetriever`.
- Produces: 그래프→stdio MCP→실제 BM25 카드와 출처 필드 경로의 조건부 테스트.

- [ ] **Step 1: 격리 DB 준비 여부 검사와 조건부 테스트 작성**

`tests/test_rag_retrieve.py`의 `_has_corpus()`와 같은 읽기 전용 조건을 새 파일 안에 독립적으로 정의한다. `DATABASE_URL`은 직접 읽지 않고 반드시 `TEST_DATABASE_URL`을 stdio 자식 환경의 `DATABASE_URL`로 매핑한다. 파일 전체를 다음 코드로 시작한다.

```python
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
```

이 테스트는 실제 LLM·임베딩·웹 API를 호출하지 않는다.

- [ ] **Step 2: DB 없는 기본 환경에서 skip 확인**

Run: `uv run --no-sync pytest -q -rs tests/test_graph_mcp_stdio.py`

Expected: `TEST_DATABASE_URL`이 없으면 1 skipped와 위 reason. 다른 오류로 skip하면 안 된다.

- [ ] **Step 3: 격리 DB가 준비된 환경에서 실제 stdio 테스트 실행**

Run: `uv run --no-sync pytest -q -rs tests/test_graph_mcp_stdio.py`

Precondition: `TEST_DATABASE_URL`은 명령 기록에 값을 남기지 않는 보안 방식으로 현재 PowerShell 환경에 미리 설정한다.

Expected: PASS. URL 값은 작업 기록·채팅·테스트 출력에 복사하지 않는다. 일반 진입점 첫 검색이 timeout이면 제품 수정으로 숨기지 말고 실패 유형과 단발 경과 시간만 작업 기록에 남긴다.

- [ ] **Step 4: 테스트 README 갱신**

`tests/README.md` 파일 표에 두 항목을 추가한다.

```markdown
- `test_graph_mcp_retriever.py` — MCP 검색 응답·stdio 세션 수명과 안전한 오류 경계
- `test_graph_mcp_stdio.py` — `TEST_DATABASE_URL`의 격리 코퍼스로 그래프→stdio MCP 검색을 확인하는 조건부 검사
```

- [ ] **Step 5: Task 5 로컬 커밋**

```powershell
git add tests/test_graph_mcp_stdio.py tests/README.md
git commit --no-gpg-sign -m "test(graph): 실제 stdio MCP 검색 경로를 확인한다"
```

---

### Task 6: 문서·변이 확인·전체 검증

**Files:**
- Modify: `SPEC.md`
- Modify: `backend/graph/README.md`
- Modify: `docs/GATES.md`
- Modify: `docs/worklog/STH.md`

**Interfaces:**
- Consumes: Task 1~5의 확정된 코드·테스트·실제 결과.
- Produces: 프로젝트 정본과 재현 가능한 완료 증거.

- [ ] **Step 1: SPEC와 그래프 README 갱신**

`SPEC.md` 2절 검색 노드에 다음 의미를 추가한다.

```markdown
MCP 검색기를 주입한 경우 정상 빈 목록은 문서 없음으로 처리하고, 세션·도구·응답 형식 장애는 별도 상태로 기록해 재검색이나 채점 없이 안전한 장애 응답으로 끝낸다. MCP를 주입하지 않은 기본 그래프는 기존 직접 검색을 유지한다.
```

`backend/graph/README.md`의 파일 표와 흐름 설명에 `mcp_retriever.py`, context manager 사용법, 직접 검색 기본값, 장애와 빈 결과의 차이를 기록한다. MCP 서버 구현 완료나 G4 완료라고 쓰지 않는다.

- [ ] **Step 2: 세 가지 변이 확인**

각 변이는 깨끗한 작업 트리에서 한 번에 하나만 적용하고 지정 테스트가 실패하는지 확인한 뒤 즉시 역패치를 적용한다.

1. `build.py`의 검색 상한 비교를 리터럴 3이 통과하도록 임시 변경 → `test_still_no_pass_refuses_after_two_searches` 실패.
2. `nodes.search()`가 `RetrievalUnavailableError`에서 `retrieval_error=None`을 반환하도록 임시 변경 → `test_retrieval_failure_is_not_reported_as_empty_corpus` 실패.
3. 장애 분기에서 거절 대신 채점을 반환하도록 임시 변경 → 같은 장애 테스트 또는 LLM 미호출 assertion 실패.

각 실행은 `git diff`로 대상 한 줄만 바뀐 것을 확인하고, 역패치 뒤 `git diff --check`와 관련 테스트 통과를 확인한다. `git checkout --`, `git reset --hard`는 사용하지 않는다.

- [ ] **Step 3: GATES와 worklog에 실제 결과 기록**

`docs/GATES.md` 변이 표에 파일·깨뜨린 한 줄·실패한 테스트·날짜 `2026-11-03`을 세 행 기록한다. `docs/worklog/STH.md`에는 다음을 실제 출력과 일치하게 기록한다.

- 변경 파일과 커밋.
- 실행한 테스트 명령과 passed/skipped/failed 수.
- 실제 stdio·격리 DB 실행 여부와 단발 경과 시간.
- `TEST_DATABASE_URL` 부재, 일반 진입점 timeout 등 확인하지 못한 항목.
- 외부 API·운영 DB·나머지 도구 4개를 사용하지 않았음.

- [ ] **Step 4: 전체 검증 실행**

Run:

```powershell
uv lock --check
uv run --no-sync pytest -q -rs
git diff --check
git status --short --branch
```

Expected: lock check exit 0, 테스트 실패 0, 알려진 조건부 검사만 skip, diff check 출력 없음. 작업 트리에는 Task 6 문서 변경만 남아야 한다.

- [ ] **Step 5: Task 6 로컬 커밋**

```powershell
git add SPEC.md backend/graph/README.md docs/GATES.md docs/worklog/STH.md
git commit --no-gpg-sign -m "docs: MCP 그래프 통합 검증을 기록한다"
```

- [ ] **Step 6: 커밋 후 최종 상태 확인**

Run:

```powershell
git status --short --branch
git log -7 --oneline --decorate
git rev-list --left-right --count origin/STH...HEAD
```

Expected: 작업 트리 clean, 로컬 `STH`만 구현 커밋만큼 ahead, 원격 push 없음.
