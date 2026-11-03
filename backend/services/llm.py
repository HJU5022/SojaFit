"""LLM 호출은 이 파일 하나로 모읍니다.

그래프 노드나 라우터가 openai를 직접 import하지 않게 하세요.
여기서 책임지는 것:
  - 데모 모드: DEMO_MODE=1이면 키 없이 기록해 둔 응답을 재생합니다 (G2). 재생 코드는 아직 없습니다.
    평가자에게는 API 키가 없습니다. 같은 입력에 같은 응답이 나오도록 입력 해시를 키로 기록하세요.
    기록에 없는 질문이 와도 키 없이 죽지 않게 2단으로 만드세요: 1) 입력 해시 재생, 2) 기록이 없으면 검색된 근거 문장을 그대로 인용하는 추출형 답변.
    작은 로컬 모델(1.5B~3B급)은 "[청크 id]" 같은 인용 형식을 지키지 못하므로 데모 모드의 주력으로 권하지 않습니다.
  - Langfuse 연결: Cloud 자격증명을 확인합니다. 그래프 트레이스는 실행하는 쪽(`evals/run_graph.py`)이 CallbackHandler로 남깁니다(SPEC 7절).
  - 출력 계약 검증(Pydantic), 실패 시 재시도와 폴백. 재시도에는 반드시 상한을 둡니다.
    키는 조당 하나이고 한도가 있습니다(조당 30달러).
  - 채팅 호출 `chat()`: 그래프 노드가 쓰는 유일한 LLM 입구입니다. 모델과 공급자는 SPEC 2절·ADR 0010을 따릅니다.
"""
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()
if not os.getenv("LANGFUSE_BASE_URL") and os.getenv("LANGFUSE_HOST"):
    os.environ["LANGFUSE_BASE_URL"] = os.environ["LANGFUSE_HOST"]

DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1"

# 그래프 LLM(ADR 0010). openrouter는 기록용 측정과 서비스, claude_cli는 개발 중 반복 테스트(같은 모델을 구독으로)
LLM_PROVIDER = os.getenv("LLM_PROVIDER") or "openrouter"
LLM_MODEL = os.getenv("LLM_MODEL") or "anthropic/claude-haiku-5.5"
LLM_CLI_MODEL = os.getenv("LLM_CLI_MODEL") or "haiku"
MAX_FORMAT_RETRIES = 2  # [왜] 형식이 틀린 답을 다시 부르는 횟수의 상한(SPEC 2절). 무한 재시도로 키 한도를 쓰지 않게 한다
API_EMBEDDING_MODELS = {
    "openai/text-embedding-3-small",
    "baai/bge-m3",
    "voyageai/voyage-4-lite",
    "voyageai/voyage-4",
    "voyageai/voyage-4-large",
}


@lru_cache(maxsize=8)
def _embedding_client(model_id: str | None = None):
    """Return the configured live embedding client and provider metadata."""
    from openai import OpenAI

    openai_key = os.getenv("OPENAI_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    selected = model_id or "openai/text-embedding-3-small"
    if selected not in API_EMBEDDING_MODELS:
        raise ValueError(f"unsupported embedding model: {selected}")
    if openrouter_key:
        return (
            OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1", max_retries=0),
            "openrouter",
            selected,
        )
    if openai_key and selected == "openai/text-embedding-3-small":
        return OpenAI(api_key=openai_key, max_retries=0), "openai", "text-embedding-3-small"
    raise RuntimeError("OPENAI_API_KEY or OPENROUTER_API_KEY is required")


def embed_texts(
    texts: list[str],
    *,
    model_id: str | None = None,
    input_type: str | None = None,
    dimensions: int | None = None,
) -> tuple[list[list[float]], int, str, str]:
    """Embed texts through the single service boundary used by runtime and evaluations."""
    client, provider, default_model = (
        _embedding_client(model_id) if model_id is not None else _embedding_client()
    )
    model = model_id or default_model
    request = {"model": model, "input": texts}
    if input_type is not None:
        # OpenAI SDK의 정식 인자에는 없지만 OpenRouter 임베딩 API가 받는 확장 필드다.
        request["extra_body"] = {"input_type": input_type}
    if dimensions is not None:
        request["dimensions"] = dimensions
    response = client.embeddings.create(**request)
    vectors = [row.embedding for row in response.data]
    usage = getattr(response, "usage", None)
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
    return vectors, total_tokens, provider, model


def _openrouter_rerank_request(payload: dict, timeout: float) -> dict:
    """Send one rerank request without retries or secret-bearing logs."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required")
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/rerank",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"OpenRouter rerank returned HTTP {error.code}") from error


def rerank_texts(
    query: str,
    documents: list[str],
    *,
    model_id: str,
    top_n: int | None = None,
    timeout: float = 120,
) -> tuple[list[dict], int, str, str]:
    """Rerank documents through OpenRouter and normalize result metadata."""
    if not documents:
        raise ValueError("documents must not be empty")
    limit = len(documents) if top_n is None else top_n
    if limit < 1 or limit > len(documents):
        raise ValueError("top_n must be between 1 and the document count")
    payload = {
        "model": model_id,
        "query": query,
        "documents": documents,
        "top_n": limit,
    }
    response = _openrouter_rerank_request(payload, timeout)
    raw_rows = response.get("results")
    if not isinstance(raw_rows, list):
        raise ValueError("OpenRouter rerank response has no results list")
    rows = [
        {
            "index": int(row["index"]),
            "relevance_score": float(row["relevance_score"]),
        }
        for row in raw_rows
    ]
    indices = [row["index"] for row in rows]
    if len(indices) != len(set(indices)) or any(index < 0 or index >= len(documents) for index in indices):
        raise ValueError("OpenRouter rerank response contains an invalid index")
    rows.sort(key=lambda row: row["relevance_score"], reverse=True)
    usage = response.get("usage") or {}
    total_tokens = int(usage.get("total_tokens") or usage.get("prompt_tokens") or 0)
    provider = str(response.get("provider") or "openrouter")
    actual_model = str(response.get("model") or model_id)
    return rows, total_tokens, provider, actual_model


def _cohere_request(payload: dict, timeout: float) -> dict:
    """Send one direct Cohere request without retries or secret-bearing logs."""
    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is required")
    request = urllib.request.Request(
        "https://api.cohere.com/v2/rerank",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Cohere API returned HTTP {error.code}") from error


def cohere_rerank_texts(
    query: str,
    documents: list[str],
    *,
    model_id: str = "rerank-v4.0-pro",
    top_n: int | None = None,
    timeout: float = 120,
) -> tuple[list[dict], int, str, str]:
    """Rerank documents through Cohere's direct API using COHERE_API_KEY."""
    if not documents:
        raise ValueError("documents must not be empty")
    limit = len(documents) if top_n is None else top_n
    if limit < 1 or limit > len(documents):
        raise ValueError("top_n must be between 1 and the document count")
    response = _cohere_request(
        {
            "model": model_id,
            "query": query,
            "documents": documents,
            "top_n": limit,
        },
        timeout,
    )
    raw_rows = response.get("results")
    if not isinstance(raw_rows, list):
        raise ValueError("Cohere rerank response has no results list")
    rows = [
        {
            "index": int(row["index"]),
            "relevance_score": float(row["relevance_score"]),
        }
        for row in raw_rows
    ]
    indices = [row["index"] for row in rows]
    if len(indices) != len(set(indices)) or any(index < 0 or index >= len(documents) for index in indices):
        raise ValueError("Cohere rerank response contains an invalid index")
    rows.sort(key=lambda row: row["relevance_score"], reverse=True)
    meta = response.get("meta") or {}
    tokens = meta.get("tokens") or {}
    total_tokens = int(tokens.get("input_tokens") or 0)
    return rows, total_tokens, "cohere", model_id


def _voyage_request(path: str, payload: dict, timeout: float) -> dict:
    """Send one direct Voyage request without retries or secret-bearing logs."""
    api_key = os.getenv("VOYAGE_API_KEY")
    if not api_key:
        raise RuntimeError("VOYAGE_API_KEY is required")
    request = urllib.request.Request(
        f"https://api.voyageai.com{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Voyage API returned HTTP {error.code}") from error


def voyage_embed_texts(
    texts: list[str],
    *,
    model_id: str,
    input_type: str | None = None,
    dimensions: int | None = None,
    timeout: float = 120,
) -> tuple[list[list[float]], int, str, str]:
    """Embed texts through Voyage's direct API using VOYAGE_API_KEY."""
    if not texts:
        raise ValueError("texts must not be empty")
    if input_type not in {None, "query", "document"}:
        raise ValueError("input_type must be query, document, or None")
    payload = {"input": texts, "model": model_id}
    if input_type is not None:
        payload["input_type"] = input_type
    if dimensions is not None:
        payload["output_dimension"] = dimensions
    response = _voyage_request("/v1/embeddings", payload, timeout)
    data = response.get("data")
    if not isinstance(data, list) or len(data) != len(texts):
        raise ValueError("Voyage embedding response count mismatch")
    ordered = sorted(data, key=lambda row: int(row["index"]))
    indices = [int(row["index"]) for row in ordered]
    if indices != list(range(len(texts))):
        raise ValueError("Voyage embedding response contains an invalid index")
    vectors = [row["embedding"] for row in ordered]
    usage = response.get("usage") or {}
    total_tokens = int(usage.get("total_tokens") or response.get("total_tokens") or 0)
    actual_model = str(response.get("model") or model_id)
    return vectors, total_tokens, "voyage", actual_model


def voyage_rerank_texts(
    query: str,
    documents: list[str],
    *,
    model_id: str = "rerank-3",
    top_n: int | None = None,
    timeout: float = 120,
) -> tuple[list[dict], int, str, str]:
    """Rerank documents through Voyage's direct API using VOYAGE_API_KEY."""
    if not documents:
        raise ValueError("documents must not be empty")
    limit = len(documents) if top_n is None else top_n
    if limit < 1 or limit > len(documents):
        raise ValueError("top_n must be between 1 and the document count")
    payload = {
        "query": query,
        "documents": documents,
        "model": model_id,
        "top_k": limit,
        "return_documents": False,
    }
    response = _voyage_request("/v1/rerank", payload, timeout)
    raw_rows = response.get("data") or response.get("results")
    if not isinstance(raw_rows, list):
        raise ValueError("Voyage rerank response has no results list")
    rows = [
        {
            "index": int(row["index"]),
            "relevance_score": float(row["relevance_score"]),
        }
        for row in raw_rows
    ]
    indices = [row["index"] for row in rows]
    if len(indices) != len(set(indices)) or any(index < 0 or index >= len(documents) for index in indices):
        raise ValueError("Voyage rerank response contains an invalid index")
    rows.sort(key=lambda row: row["relevance_score"], reverse=True)
    usage = response.get("usage") or {}
    total_tokens = int(usage.get("total_tokens") or response.get("total_tokens") or 0)
    actual_model = str(response.get("model") or model_id)
    return rows, total_tokens, "voyage", actual_model


@lru_cache(maxsize=1)
def _chat_model():
    """OpenRouter에 붙는 LangChain 채팅 모델을 한 번만 만든다(강의 2주 20강과 같은 방식)."""
    from langchain_openai import ChatOpenAI

    # [왜] OpenRouter는 OpenAI와 같은 API 모양이라 base_url만 바꾸면 ChatOpenAI로 여러 회사 모델을 부를 수 있다
    # [왜] 라이브러리 자체 재시도는 끄고(max_retries=0) 재시도 상한은 chat()의 MAX_FORMAT_RETRIES 하나로만 센다
    return ChatOpenAI(model=LLM_MODEL, base_url="https://openrouter.ai/api/v1",
                      api_key=os.environ["OPENROUTER_API_KEY"], temperature=0, max_retries=0)


def _openrouter_call(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    """OpenRouter에 구조화 출력을 요청하고 schema 객체로 돌려준다."""
    # with_structured_output(schema)는 Pydantic 모델을 JSON Schema로 바꿔 response_format(json_schema)으로 보내고,
    # 받은 JSON을 그 모델로 검증해 객체로 돌려준다. 형식이 틀리면 ValidationError나 OutputParserException을 낸다.
    structured = _chat_model().with_structured_output(schema)
    return structured.invoke([{"role": "system", "content": system}, {"role": "user", "content": user}])


def _cli_call(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    """구독 `claude -p`로 같은 모델을 부르고 schema 객체로 돌려준다(개발 중 반복 테스트용, 최종 정리 때 지운다)."""
    # [왜] CLI에는 response_format이 없어 JSON Schema를 시스템 프롬프트 끝에 붙여 형식을 요구한다
    schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    system_full = f"{system}\n\n출력은 아래 JSON Schema를 따르는 JSON 하나만 낸다. 다른 글은 쓰지 않는다.\n{schema_text}"
    # [주의] --tools ""로 도구를 끄고, 임시 폴더에서 실행해 저장소의 CLAUDE.md가 읽히지 않게 한다
    done = subprocess.run(
        ["claude", "-p", "--model", LLM_CLI_MODEL, "--tools", "", "--system-prompt", system_full,
         "--output-format", "json", user],
        cwd=tempfile.gettempdir(), capture_output=True, text=True, timeout=300, check=True,
    )
    return schema.model_validate_json(_json_part(json.loads(done.stdout).get("result", "")))


def _json_part(raw: str) -> str:
    """답 글자에서 첫 { 부터 마지막 } 까지를 꺼낸다(코드 블록으로 감싼 답 대비)."""
    found = re.search(r"\{.*\}", raw, re.S)
    return found.group(0) if found else raw


def chat(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    """시스템·사용자 메시지를 보내고 schema 형식으로 검증한 답을 돌려준다.

    형식이 틀리면 MAX_FORMAT_RETRIES번까지 다시 부르고, 그래도 틀리면 마지막 검증 오류를 담아 ValueError를 낸다.
    공급자는 LLM_PROVIDER(openrouter | claude_cli), 모델은 LLM_MODEL / LLM_CLI_MODEL이다(ADR 0010).
    """
    from langchain_core.exceptions import OutputParserException

    call = _cli_call if LLM_PROVIDER == "claude_cli" else _openrouter_call
    last_error = None
    for _ in range(1 + MAX_FORMAT_RETRIES):
        try:
            return call(system, user, schema)
        except (ValidationError, OutputParserException) as error:
            last_error = error
    raise ValueError(f"LLM 출력이 {schema.__name__} 형식을 {1 + MAX_FORMAT_RETRIES}번 모두 어겼다") from last_error


def check_langfuse_connection() -> bool:
    """Check configured Langfuse credentials without creating a trace."""
    from langfuse import get_client

    return get_client().auth_check()
