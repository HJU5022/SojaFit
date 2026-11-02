"""LLM 호출은 이 파일 하나로 모읍니다.

그래프 노드나 라우터가 openai를 직접 import하지 않게 하세요.
여기서 책임지는 것:
  - 데모 모드: DEMO_MODE=1이면 키 없이 기록해 둔 응답을 재생합니다 (G2). 재생 코드는 아직 없습니다.
    평가자에게는 API 키가 없습니다. 같은 입력에 같은 응답이 나오도록 입력 해시를 키로 기록하세요.
    기록에 없는 질문이 와도 키 없이 죽지 않게 2단으로 만드세요: 1) 입력 해시 재생, 2) 기록이 없으면 검색된 근거 문장을 그대로 인용하는 추출형 답변.
    작은 로컬 모델(1.5B~3B급)은 "[청크 id]" 같은 인용 형식을 지키지 못하므로 데모 모드의 주력으로 권하지 않습니다.
  - Langfuse 연결: Cloud 자격증명을 확인합니다. 트레이스 데이터 수집은 별도 결정 전까지 하지 않습니다.
  - 출력 계약 검증(Pydantic), 실패 시 재시도와 폴백. 재시도에는 반드시 상한을 둡니다.
    키는 조당 하나이고 한도가 있습니다(조당 30달러).
  - 채팅 호출 `chat()`: 그래프 노드가 쓰는 유일한 LLM 입구입니다. 모델과 공급자는 SPEC 2절·ADR 0010을 따릅니다.
"""
import json
import os
import re
import subprocess
import tempfile
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


@lru_cache(maxsize=1)
def _embedding_client():
    """Return the configured live embedding client and provider metadata."""
    from openai import OpenAI

    openai_key = os.getenv("OPENAI_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openai_key:
        return OpenAI(api_key=openai_key, max_retries=0), "openai", "text-embedding-3-small"
    if openrouter_key:
        return (
            OpenAI(api_key=openrouter_key, base_url="https://openrouter.ai/api/v1", max_retries=0),
            "openrouter",
            "openai/text-embedding-3-small",
        )
    raise RuntimeError("OPENAI_API_KEY or OPENROUTER_API_KEY is required")


def embed_texts(texts: list[str]) -> tuple[list[list[float]], int, str, str]:
    """Embed texts through the single service boundary used by runtime and evaluations."""
    client, provider, model = _embedding_client()
    response = client.embeddings.create(model=model, input=texts)
    vectors = [row.embedding for row in response.data]
    return vectors, response.usage.total_tokens, provider, model


@lru_cache(maxsize=1)
def _chat_client():
    """OpenRouter 채팅 클라이언트를 한 번만 만든다."""
    from openai import OpenAI

    # [왜] SDK 자체 재시도는 끄고(max_retries=0) 재시도 상한은 chat()의 MAX_FORMAT_RETRIES 하나로만 센다
    return OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1", max_retries=0)


def _openrouter_call(system: str, user: str, schema: type[BaseModel]) -> str:
    """OpenRouter에 구조화 출력을 요청하고 답의 JSON 글자를 돌려준다."""
    # parse()는 Pydantic 모델을 strict JSON Schema로 바꿔 response_format으로 보내고,
    # 받은 글자를 그 모델로 검증한다. 검증이 실패하면 pydantic ValidationError를 낸다.
    completion = _chat_client().chat.completions.parse(
        model=LLM_MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format=schema,
        temperature=0,
    )
    return completion.choices[0].message.content or ""


def _cli_call(system: str, user: str, schema: type[BaseModel]) -> str:
    """구독 `claude -p`로 같은 모델을 부르고 답 글자를 돌려준다(개발 중 반복 테스트용)."""
    # [왜] CLI에는 response_format이 없어 JSON Schema를 시스템 프롬프트 끝에 붙여 형식을 요구한다
    schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    system_full = f"{system}\n\n출력은 아래 JSON Schema를 따르는 JSON 하나만 낸다. 다른 글은 쓰지 않는다.\n{schema_text}"
    # [주의] --tools ""로 도구를 끄고, 임시 폴더에서 실행해 저장소의 CLAUDE.md가 읽히지 않게 한다
    done = subprocess.run(
        ["claude", "-p", "--model", LLM_CLI_MODEL, "--tools", "", "--system-prompt", system_full,
         "--output-format", "json", user],
        cwd=tempfile.gettempdir(), capture_output=True, text=True, timeout=300, check=True,
    )
    return json.loads(done.stdout).get("result", "")


def _json_part(raw: str) -> str:
    """답 글자에서 첫 { 부터 마지막 } 까지를 꺼낸다(코드 블록으로 감싼 답 대비)."""
    found = re.search(r"\{.*\}", raw, re.S)
    return found.group(0) if found else raw


def chat(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    """시스템·사용자 메시지를 보내고 schema 형식으로 검증한 답을 돌려준다.

    형식이 틀리면 MAX_FORMAT_RETRIES번까지 다시 부르고, 그래도 틀리면 마지막 검증 오류를 담아 ValueError를 낸다.
    공급자는 LLM_PROVIDER(openrouter | claude_cli), 모델은 LLM_MODEL / LLM_CLI_MODEL이다(ADR 0010).
    """
    call = _cli_call if LLM_PROVIDER == "claude_cli" else _openrouter_call
    last_error = None
    for _ in range(1 + MAX_FORMAT_RETRIES):
        try:
            return schema.model_validate_json(_json_part(call(system, user, schema)))
        except ValidationError as error:
            last_error = error
    raise ValueError(f"LLM 출력이 {schema.__name__} 형식을 {1 + MAX_FORMAT_RETRIES}번 모두 어겼다") from last_error


def check_langfuse_connection() -> bool:
    """Check configured Langfuse credentials without creating a trace."""
    from langfuse import get_client

    return get_client().auth_check()
