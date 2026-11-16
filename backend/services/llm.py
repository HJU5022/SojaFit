"""LLM·임베딩 호출의 유일한 입구.

역할: 채팅 호출(`chat`·`node_chat`, Pydantic 출력 검증, 형식 재시도 상한), 임베딩(`embed_texts`), 평가 전용 호출 예산(`evaluation_limits`), Decisions API 평가 호출(`evaluation_decision`)을 맡는다.
호출자: backend/graph 노드(`node_chat`), backend/rag(`embed_texts`), evals/*(`evaluation_limits`·Decisions 평가), tests/services/test_llm.py.
입력: 시스템·사용자 프롬프트와 Pydantic schema. 출력: 검증된 schema 객체(임베딩은 벡터 목록).
Voyage(검색): `voyage_embed`(질문 임베딩 voyage-4-large 1024차원), `voyage_rerank`(rerank-3). 사전 등록 #25의 측정 설정이다(ADR 0004 갱신 2026-11-03).
하지 않는 일: 데모 모드 응답 기록 · 재생(backend/services/demo.py의 recorder · replayer. 서비스는 DEMO_REPLAY=1에서 이 파일 대신 재생 chat을 쓴다. DEMO_MODE는 검색의 임베딩 호출만 끈다, backend/rag/retrieve.py),
프롬프트 원문(backend/prompts/), 프롬프트 등록·고정 버전 검증(langfuse_prompts.py), 수치 비교(backend/judge/).
출처: SPEC.md 2절(모델·공급자)·5절(Langfuse 프롬프트와 실행 추적, 평가 예산)·7절(데모 모드), ADR 0010, backend/services/SERVICES.md.
[왜] 호출을 한 곳에 모아야 그래프 노드가 openai를 직접 import하지 않고, 재시도 상한과 키 한도(조당 30달러)를 한 곳에서 지킨다.
Langfuse: 명시적인 프롬프트 세션에서는 고정 버전 검증과 노드 추적을 켠다. 그래프 평가 실행(`evals/runners/run_graph.py`)은 별도 CallbackHandler를 쓴다.
모델: 노드마다 `langfuse_prompts.NODE_MODELS` 표의 모델을 쓴다(시작값, 최종 아님). 환경변수 LLM_MODEL을 정하면 모든 노드가 그 모델 하나를 쓴다(예: 11-04 기준선 재현).
읽는 환경변수: DEMO_MODE, LLM_PROVIDER(openrouter | claude_cli), LLM_MODEL, LLM_CLI_MODEL,
OPENROUTER_API_KEY, OPENAI_API_KEY(임베딩), VOYAGE_API_KEY(검색 임베딩·리랭크), LANGFUSE_BASE_URL(없으면 LANGFUSE_HOST를 옮겨 씀). .env는 load_dotenv로 읽는다.
"""
import json
import base64
import math
import os
import re
import subprocess
import tempfile
import time
import threading
from typing import Callable
from urllib.request import Request, urlopen
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()
if not os.getenv("LANGFUSE_BASE_URL") and os.getenv("LANGFUSE_HOST"):
    os.environ["LANGFUSE_BASE_URL"] = os.environ["LANGFUSE_HOST"]
if os.getenv("LANGFUSE_BASE_URL"):
    os.environ["LANGFUSE_BASE_URL"] = os.environ["LANGFUSE_BASE_URL"].rstrip("/")

DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1"

# 그래프 LLM(ADR 0010). openrouter는 기록용 측정과 서비스, claude_cli는 개발 중 반복 테스트(같은 모델을 구독으로)
LLM_PROVIDER = os.getenv("LLM_PROVIDER") or "openrouter"
LLM_MODEL_OVERRIDE = os.getenv("LLM_MODEL") or None  # [왜] 설정하면 모든 노드가 이 모델 하나를 쓴다(노드별 표보다 우선)
LLM_MODEL = LLM_MODEL_OVERRIDE or "anthropic/claude-haiku-5.5"  # 노드 밖 호출과 기록용 기본 모델
LLM_CLI_MODEL = os.getenv("LLM_CLI_MODEL") or "haiku"
MAX_FORMAT_RETRIES = 2  # [왜] 형식이 틀린 답을 다시 부르는 횟수의 상한(SPEC 2절). 무한 재시도로 키 한도를 쓰지 않게 한다


class EvaluationLimitError(RuntimeError):
    """평가 호출 수·시간·예약 비용 상한을 넘겼을 때 내는 오류."""


class UpstreamError(RuntimeError):
    """바깥 공급자(Voyage)가 오류 상태로 답했을 때 내는 오류. 키 없음처럼 우리 설정 문제는 RuntimeError 그대로다."""


def is_upstream_error(error: BaseException) -> bool:
    """LLM · 임베딩 공급자(OpenRouter · OpenAI · Voyage)가 실패했거나 연결이 끊겼으면 True(분석 실패 502 · 503 가르기, ADR 0019)."""
    # [왜] openai SDK 예외는 이 모듈만 import한다(AGENTS.md 지킬 것 2). LangChain ChatOpenAI는 openai 예외를 감싸지 않고 올린다
    import httpx
    from openai import APIError  # 연결 끊김 · 시간 초과(APIConnectionError)와 공급자 오류 상태(APIStatusError)의 공통 부모

    return isinstance(error, (UpstreamError, APIError, httpx.HTTPError))  # httpx: Voyage 호출의 연결 · 시간 초과


class LLMFormatError(ValueError):
    """`chat()`이 형식 재시도를 다 쓰고도 schema를 못 맞췄을 때. ValueError 그대로 잡던 곳은 그대로 동작한다."""


def is_llm_failure(error: BaseException) -> bool:
    """LLM · 임베딩 호출이 형식 오류나 공급자 오류로 끝났나(에이전트가 실패 보고로 바꿔 받아도 되는 오류).

    [주의] 한도 초과(EvaluationLimitError) · 그래프 인터럽트 · 코드 오류는 아니다. 이들은 그대로 올라가야 한다.
    """
    return isinstance(error, LLMFormatError) or is_upstream_error(error)


class EvaluationFormatError(RuntimeError):
    """provider 응답은 받았지만 평가 schema 검증에 실패했을 때 metadata를 보존하는 오류."""

    def __init__(self, metadata: dict):
        super().__init__("평가 응답 schema 불일치")
        self.metadata = metadata


# 서비스 예약에 쓰는 모델별 OpenRouter 단가(토큰당 USD): (입력, 출력, 가격 구간). 출처는 11-10 실행 전 확인한 OpenRouter 가격
# (evals/results/threads/claim_consistency_live_2026-11-10.json의 preflight.pricing). 키는 langfuse_prompts.HAIKU · SONNET과 같다.
# shortcut: 단가를 코드에 고정했다. OpenRouter 가격이 오르면 예약이 실제보다 적어질 수 있으니 모델이나 가격이 바뀌면 이 표를 같이 고친다
MODEL_RATES = {
    "anthropic/claude-haiku-5.5": (0.0000001, 0.0000005, ({"min_prompt_tokens": 100000, "prompt": "0.0000005", "completion": "0.0000025"},)),
    "anthropic/claude-sonnet-5.5": (0.000002, 0.00001, ()),
}


@dataclass
class EvaluationBudget:
    """평가 전용 호출 예산(호출 수·시간·예약 비용·출력 토큰 상한)."""
    # [주의] 예약 비용은 실제 사용량·청구액이 아니며 실패 요청도 돌려주지 않는다
    max_calls: int
    max_usd: float
    max_seconds: float
    prompt_rate: float
    completion_rate: float
    embedding_rate: float = 0.000001
    max_tokens: int = 1024
    pricing_tiers: tuple = ()
    # [왜] True면 OpenRouter 호출의 예약을 그 호출이 실제로 쓰는 모델 단가(MODEL_RATES)로 잡는다. 서비스 분석만 켠다.
    #      평가 실행기는 원시 결과의 예약액이 이전 실행과 같은 기준이어야 해서 꺼 둔 채(prompt_rate · completion_rate 하나)로 둔다
    per_model_rates: bool = False
    calls: int = 0
    reserved_usd: float = 0.0
    started: float = field(default_factory=time.monotonic)
    _pending_reservations: list[float] = field(default_factory=list, repr=False)
    on_reserve: Callable[[float], None] | None = field(default=None, repr=False)
    _lock: object = field(default_factory=threading.Lock, repr=False)

    def __post_init__(self):
        """만들 때 상한·단가를 검증한다."""
        self.validate()

    def validate(self):
        """상한·단가가 유한한 양수(호출 수·토큰은 양의 정수)이고 가격 구간이 올바른지 확인한다(아니면 ValueError)."""
        # [왜] NaN·무한대·0이 상한 비교를 무력화하지 않게 값을 먼저 걸러낸다
        values = (self.max_usd, self.max_seconds, self.prompt_rate, self.completion_rate, self.embedding_rate)
        if any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 for value in values):
            raise ValueError("평가 상한과 단가는 유한한 양수여야 합니다")
        if any(type(value) is not int or value <= 0 for value in (self.max_calls, self.max_tokens)):
            raise ValueError("호출 수와 토큰 상한은 양의 정수여야 합니다")
        for tier in self.pricing_tiers:
            threshold = tier.get("min_prompt_tokens", 0)
            if type(threshold) is not int or threshold < 0:
                raise ValueError("가격 구간의 시작 토큰 수가 잘못되었습니다")
            for key in ("prompt", "completion"):
                rate = float(tier.get(key, 0))
                if not math.isfinite(rate) or rate < 0:
                    raise ValueError("가격 구간의 단가가 잘못되었습니다")

    def reserve(self, text: str, *, output_tokens: int, embedding: bool = False, model: str | None = None) -> float:
        # LangGraph/판정 읽기가 병렬로 호출해도 같은 요청의 한도를 공유한다.
        with self._lock:
            return self._reserve(text, output_tokens=output_tokens, embedding=embedding, model=model)

    def remaining(self) -> float:
        remaining = self.max_seconds - (time.monotonic() - self.started)
        if remaining <= 0:
            raise EvaluationLimitError('분석 시간 상한')
        return min(45.0, remaining)

    def _reserve(self, text: str, *, output_tokens: int, embedding: bool = False, model: str | None = None) -> float:
        """호출 한 번의 최대 비용을 호출 전에 예약하고, 이 호출에 줄 제한 시간(초, 최대 45 또는 남은 시간)을 돌려준다.

        text의 바이트 수에 여유 8192를 더해 입력 토큰 상한으로 본다. embedding=True면 임베딩 단가를 쓴다.
        per_model_rates가 켜져 있고 model이 MODEL_RATES에 있으면 그 모델의 단가 · 가격 구간을 쓰고, 없으면 예산의 단가를 쓴다.
        Raises:
            EvaluationLimitError: 호출 수·시간·예약 비용 상한을 넘길 때(다음 호출 전에 중단).
            ValueError: output_tokens가 0 이상 max_tokens 이하가 아닐 때.
        """
        self.validate()
        if type(output_tokens) is not int or not 0 <= output_tokens <= self.max_tokens:
            raise ValueError("예약 출력 토큰 수가 잘못되었습니다")
        remaining = self.max_seconds - (time.monotonic() - self.started)
        # [왜] 토큰 수를 정확히 세지 않고 바이트 수+여유로 입력 토큰의 위쪽 경계를 잡아 비용을 보수적으로 예약한다
        upper = len(text.encode("utf-8")) + 8192
        # [왜] 서비스는 노드마다 모델이 다르다(대부분 Haiku, 종합만 Sonnet). 모든 호출을 한 단가(Sonnet 이상)로 잡으면 판정 읽기 여러 번과
        #      Supervisor만으로 분석 한 번의 예약 상한($0.50)을 넘어 판정 질문이 멈췄다(11-10 데모 기록 실측). 실제 모델 단가로 잡는다
        prompt_rate, completion_rate, price_tiers = (MODEL_RATES[model] if self.per_model_rates and model in MODEL_RATES
                                                      else (self.prompt_rate, self.completion_rate, self.pricing_tiers))
        tiers = [p for p in price_tiers if p.get("min_prompt_tokens", 0) <= upper] if not embedding else []
        # [왜] 가격 구간이 여럿이면 가장 비싼 단가로 예약해 실제보다 적게 잡는 일을 막는다
        rate = self.embedding_rate if embedding else max([prompt_rate, *[float(p.get("prompt", 0)) for p in tiers]])
        output_rate = max([completion_rate, *[float(p.get("completion", 0)) for p in tiers]])
        cost = upper * rate + output_tokens * output_rate
        if remaining <= 0 or self.calls >= self.max_calls or self.reserved_usd + cost > self.max_usd:
            raise EvaluationLimitError("평가 호출/시간/예약비용 상한")
        if self.on_reserve:
            self.on_reserve(cost)  # DB 사용자 예산도 통과한 뒤에만 외부 호출을 허용한다.
        self.calls += 1
        self.reserved_usd += cost
        self._pending_reservations.append(cost)
        return self.remaining()

    def reconcile(self, reported_cost: float | None) -> None:
        """가장 최근 호출 예약액을 provider가 보고한 실제 비용으로 정산한다.

        비용이 없으면 보수적 예약액을 유지한다. 호출 오류로 응답이 없었던 예약은 정산하지 않는다.
        """
        if not self._pending_reservations:
            raise RuntimeError("정산할 평가 호출 예약이 없습니다")
        reserved = self._pending_reservations.pop()
        if reported_cost is None:
            return
        if not isinstance(reported_cost, (int, float)) or not math.isfinite(reported_cost) or reported_cost < 0:
            raise ValueError("provider 비용은 유한한 0 이상의 수여야 합니다")
        self.reserved_usd += float(reported_cost) - reserved


_evaluation_budget = ContextVar("evaluation_budget", default=None)


@contextmanager
def evaluation_limits(budget: EvaluationBudget):
    """평가 실행 동안만 원시 호출을 제한하고 종료 시 원래 설정으로 복원한다."""
    budget.validate()
    token = _evaluation_budget.set(budget)
    try:
        yield budget
    finally:
        _evaluation_budget.reset(token)


@lru_cache(maxsize=1)
def _embedding_client():
    """임베딩 클라이언트와 (공급자, 모델)을 돌려준다(키가 모두 없으면 RuntimeError)."""
    from openai import OpenAI

    openai_key = os.getenv("OPENAI_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    # [왜] OPENAI_API_KEY가 있으면 직접 호출을 우선하고, 없으면 OpenRouter를 거친다. 재시도는 호출하는 쪽이 상한을 센다(max_retries=0)
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
    """글 목록을 임베딩해 (벡터 목록, 사용 토큰 수, 공급자, 모델)을 돌려준다."""
    client, provider, model = _embedding_client()
    budget = _evaluation_budget.get()
    # [주의] 평가 상한(`evaluation_limits`) 안이면 호출 전에 예산을 예약한다(초과 시 EvaluationLimitError). 키가 없으면 RuntimeError
    if budget:
        timeout = budget.reserve("\n".join(texts), output_tokens=0, embedding=True)
        client = client.with_options(timeout=timeout)
    response = client.embeddings.create(model=model, input=texts)
    vectors = [row.embedding for row in response.data]
    return vectors, response.usage.total_tokens, provider, model


_voyage_client = None
_voyage_client_lock = threading.Lock()


def _voyage_http():
    """Voyage용 POST 함수. 프로세스 공용 httpx.Client 하나(연결·TLS 재사용, 스레드 안전)의 post를 돌려준다. 요청마다 timeout을 따로 준다."""
    global _voyage_client
    import httpx
    # [왜] 평가 러너(run_injection_preflight·injection_baseline_runtime)와 시험이 httpx.post를 바꿔 Voyage 호출을 세거나 막는다. 바뀌었으면 그 함수를 그대로 쓴다
    if httpx.post.__module__ != "httpx":
        return httpx.post
    with _voyage_client_lock:
        if _voyage_client is None:
            _voyage_client = httpx.Client()
        return _voyage_client.post


def _voyage_post(path: str, payload: dict) -> dict:
    """Voyage REST에 POST해 JSON 본문을 돌려준다. 429·5xx는 5번까지 늘려 가며 다시 부르고, 결제 신호(402)는 바로 멈춘다."""
    key = os.getenv("VOYAGE_API_KEY")
    if not key:
        raise RuntimeError("VOYAGE_API_KEY is required")
    for attempt in range(5):  # [왜] 재시도 상한. 키 한도(조당 30달러)를 무한 루프가 쓰지 않게 한다
        budget = _evaluation_budget.get()
        runtime = budget is not None and budget.on_reserve is not None
        timeout = budget.reserve(json.dumps(payload), output_tokens=0, embedding=True) if runtime else 180
        r = _voyage_http()(f"https://api.voyageai.com/v1/{path}", timeout=timeout, headers={"Authorization": f"Bearer {key}"}, json=payload)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 402 or re.search("payment|billing", r.text, re.I):
            raise UpstreamError(f"Voyage payment signal {r.status_code}")
        if r.status_code in (429, 500, 502, 503, 504) and attempt < 4:
            delay = 5 * 2**attempt
            time.sleep(min(delay, budget.remaining()) if runtime else delay)
            continue
        raise UpstreamError(f"Voyage error {r.status_code}")  # [주의] 응답 본문과 키는 메시지에 넣지 않는다


def voyage_embed(texts: list[str], input_type: str) -> list[list[float]]:
    """글 목록을 voyage-4-large(1024차원)로 임베딩해 벡터 목록을 입력 순서대로 돌려준다. input_type은 'query' 또는 'document'."""
    d = _voyage_post("embeddings", {"input": texts, "model": "voyage-4-large", "input_type": input_type,
                                    "truncation": True, "output_dimension": 1024})
    return [x["embedding"] for x in sorted(d["data"], key=lambda x: x["index"])]


def voyage_rerank(query: str, docs: list[str], model: str = "rerank-3") -> list[int]:
    """docs를 query와 가까운 순으로 다시 세워 docs의 위치 번호 목록을 돌려준다."""
    d = _voyage_post("rerank", {"query": query, "documents": docs, "model": model, "truncation": True})
    return [x["index"] for x in d["data"]]


_node_model = ContextVar("llm_node_model", default=None)  # node_chat이 부르는 동안 그 노드의 모델


def node_model(node: str) -> str:
    """노드가 쓸 모델. LLM_MODEL을 환경변수로 정했으면 그 모델, 아니면 노드별 표(`langfuse_prompts.NODE_MODELS`)."""
    from backend.services import langfuse_prompts
    return LLM_MODEL_OVERRIDE or langfuse_prompts.node_config(node)["model"]


@lru_cache(maxsize=8)
def _chat_model(model: str):
    """모델마다 OpenRouter용 LangChain 채팅 모델을 한 번씩 만든다(강의 2주 20강과 같은 방식)."""
    from langchain_openai import ChatOpenAI
    from backend.services import langfuse_prompts

    # [왜] OpenRouter는 OpenAI와 같은 API 모양이라 base_url만 바꾸면 ChatOpenAI로 여러 회사 모델을 부를 수 있다
    # [왜] 라이브러리 자체 재시도는 끄고(max_retries=0) 재시도 상한은 chat()의 MAX_FORMAT_RETRIES 하나로만 센다
    # [왜] Luna에는 temperature를 보내지 않는다(3차 실측 계약). Haiku·Sonnet은 0. 출력 상한은 LangChain이 max_completion_tokens로 바꿔 보낸다
    temperature = None if model == langfuse_prompts.LUNA else 0
    # [왜] 생각(추론)은 기본으로 끈다(SPEC 2절 "생각(추론)"). OpenRouter · Supabase · Langfuse로 v3 50문항을 재니 정확도는 그대로이고
    #      응답 시간 p50 8.8 → 5.9초, p95 45.1 → 33.9초, 판정 질문 25 → 13초로 줄었다
    # [주의] Sonnet 5.5는 생각을 끄면 OpenRouter가 400("Reasoning is mandatory")을 내서 끄지 않고 짧게(effort low) 한다. Luna 등 다른 모델에는 보내지 않는다
    reasoning = {langfuse_prompts.HAIKU: {"enabled": False}, langfuse_prompts.SONNET: {"effort": "low"}}.get(model)
    return ChatOpenAI(model=model, base_url="https://openrouter.ai/api/v1",
                      api_key=os.environ["OPENROUTER_API_KEY"], temperature=temperature, max_retries=0,
                      extra_body={"reasoning": reasoning} if reasoning else None)


def _evaluation_client(timeout: float):
    """평가 전용 OpenRouter client를 재시도 없이 만든다."""
    from openai import OpenAI

    return OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1",
                  max_retries=0, timeout=timeout)


def evaluation_chat(model: str, system: str, user: str, schema: type[BaseModel], *,
                    provider_policy: dict, max_tokens: int, timeout: float) -> tuple[BaseModel, dict]:
    """평가 후보 한 건을 명시한 model·provider policy로 호출하고 검증된 출력과 usage metadata를 돌려준다."""
    budget = _evaluation_budget.get()
    if budget:
        schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        timeout = min(timeout, budget.reserve(system + user + schema_text, output_tokens=max_tokens))
    client = _evaluation_client(timeout)
    generation_parameters = {"max_tokens": max_tokens, "temperature": 0}
    if model == "anthropic/claude-haiku-5.5":
        generation_parameters.pop("temperature")
    elif model == "openai/gpt-6-luna":
        generation_parameters = {"max_completion_tokens": max_tokens}
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        **generation_parameters,
        response_format={"type": "json_schema", "json_schema": {
            "name": schema.__name__, "schema": schema.model_json_schema(), "strict": True,
        }},
        extra_body={"provider": provider_policy, "usage": {"include": True}},
    )
    choice = response.choices[0]
    usage = response.usage.model_dump() if response.usage is not None else None
    if budget:
        budget.reconcile(usage.get("cost") if usage else None)
    extra = getattr(response, "model_extra", None) or {}
    metadata = {
        "response_id": response.id,
        "actual_model": getattr(response, "model", None) or extra.get("model"),
        "provider": getattr(response, "provider", None) or extra.get("provider"),
        "finish_reason": choice.finish_reason,
        "usage": usage,
    }
    try:
        parsed = schema.model_validate_json(choice.message.content)
    except ValidationError as error:
        raise EvaluationFormatError(metadata) from error
    return parsed, metadata


def evaluation_decisions_catalog(*, zdr: bool, opener=None) -> list[dict]:
    """OpenRouter Decisions 출력 모델 목록을 조회한다. 평가 실행기에는 네트워크 호출을 두지 않는다."""
    url = "https://openrouter.ai/api/v1/models?output_modalities=decisions"
    if zdr:
        url += "&zdr=true"
    with (opener or urlopen)(url, timeout=30) as response:
        payload = json.load(response)
    models = payload.get("data")
    if not isinstance(models, list):
        raise ValueError("Decisions catalog 형식이 잘못되었습니다")
    return models


def evaluation_decision(request_body: dict, *, timeout: float = 45.0, opener=None) -> dict:
    """ZDR·fallback 금지 계약의 Decisions 요청을 재시도 없이 한 번 보낸다."""
    policy = request_body.get("provider") if isinstance(request_body, dict) else None
    if not isinstance(policy, dict) or policy.get("zdr") is not True or policy.get("data_collection") != "deny" or policy.get("allow_fallbacks") is not False:
        raise ValueError("Decisions 평가의 provider policy가 잘못되었습니다")
    if not isinstance(request_body.get("model"), str) or not request_body["model"]:
        raise ValueError("Decisions 평가 model ID가 없습니다")
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Decisions 평가 timeout은 양수여야 합니다")
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY가 필요합니다")
    request = Request(
        "https://openrouter.ai/api/alpha/decisions",
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with (opener or urlopen)(request, timeout=timeout) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError("Decisions 응답 형식이 잘못되었습니다")
    return payload


_figure_image = ContextVar('figure_image', default=None)


def _openrouter_call(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    """OpenRouter에 구조화 출력을 요청하고 schema 객체로 돌려준다."""
    # [왜] with_structured_output(schema)는 Pydantic 모델을 JSON Schema로 바꿔 response_format(json_schema)으로 보내고,
    # 받은 JSON을 그 모델로 검증해 객체로 돌려준다. 형식이 틀리면 ValidationError나 OutputParserException을 낸다(chat()이 잡는다).
    name = _node_model.get() or LLM_MODEL
    model = _chat_model(name)
    budget = _evaluation_budget.get()
    from backend.services import langfuse_prompts
    options = langfuse_prompts.model_options()
    config = langfuse_prompts.invocation_config()
    if budget:
        # [주의] 평가 중이면 출력 토큰·시간 상한을 예산에서 받아 덮어쓴다
        image_reservation = ' ' * 24576 if _figure_image.get() else ''
        timeout = budget.reserve(system + user + json.dumps(schema.model_json_schema()) + image_reservation,
                                 output_tokens=budget.max_tokens, model=name)
        options.update(max_tokens=budget.max_tokens, timeout=timeout)
    structured = model.with_structured_output(schema)
    system_content = system
    if name in (langfuse_prompts.HAIKU, langfuse_prompts.SONNET):
        # [왜] 노드마다 고정 지시문(system)이 길어 매번 새로 읽히면 입력 비용이 든다. OpenRouter의 Anthropic 프롬프트 캐싱(cache_control)으로
        #      고정 지시문만 캐시에 둔다. 두 번째 호출부터 지시문 입력 비용이 약 1/10(계획 Sonnet 0.0086 → 0.0006달러), 시간은 그대로(11-09 실측 · 조장 결정)
        # [주의] 질문 · 카드가 든 user는 매번 달라 걸지 않는다. 지시문 글자는 그대로라 Langfuse 프롬프트 대조(prompt_scope)와 무관하다. Luna 등 다른 모델은 그대로
        system_content = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    user_content = user
    if image := _figure_image.get():
        user_content = [{'type':'text', 'text':user},
                        {'type':'image_url', 'image_url':{'url':'data:image/png;base64,' + base64.b64encode(image).decode('ascii')}}]
    messages = [{"role": "system", "content": system_content}, {"role": "user", "content": user_content}]
    if config and _figure_image.get() is None:
        # Langfuse 노드 추적 중: callback 설정을 넘기고 프롬프트 버전을 generation에 연결한다
        structured = langfuse_prompts.bind_prompt(structured, options)
        return structured.invoke(messages, config=config)
    return structured.invoke(messages, **options)


def node_chat(node: str, system: str, user: str, schema: type[BaseModel], *, skill_text: str = "", image: bytes | None = None):
    """그래프 노드용 LLM 호출. Langfuse 세션이 켜져 있을 때만 고정 버전 검증·노드 span·generation callback을 쓴다.

    node는 route | grade | rewrite | generate | supervisor | judge_read, skill_text는 generate에 붙일 Skill 본문이다. 검증된 schema 객체를 돌려준다.
    Raises:
        ValueError: Langfuse 설정·프롬프트와 실제 공급자·모델·출력 상한이 다를 때, 또는 `chat()`이 형식을 못 맞출 때.
        RuntimeError: 노드 호출이 중첩될 때.
    """
    from backend.services import langfuse_prompts
    if image is not None and (LLM_PROVIDER != 'openrouter' or not isinstance(image, bytes)
                              or not image.startswith(b'\x89PNG\r\n\x1a\n') or len(image) > 512 * 1024):
        raise ValueError('Figure input must be a bounded PNG on the OpenRouter path')
    if langfuse_prompts.is_active():
        # [주의] 추적 중에 실제 호출 설정이 등록된 프롬프트 설정과 다르면 기록이 거짓이 되므로 호출 전에 멈춘다
        if LLM_PROVIDER != "openrouter" or node_model(node) != langfuse_prompts.node_config(node)["model"]:
            raise ValueError("Langfuse 설정과 실제 공급자/모델 불일치")
        budget = _evaluation_budget.get()
        if budget and budget.max_tokens != langfuse_prompts.CONFIG["max_tokens"]:
            raise ValueError("Langfuse 설정과 출력 토큰 상한 불일치")
    if langfuse_prompts.invocation_config() is not None:
        # [왜] 노드 호출이 겹치면 추적 범위(contextvar)가 섞이므로 중첩을 막는다
        raise RuntimeError("LLM 노드 호출은 중첩하지 않습니다")
    token = _node_model.set(node_model(node))
    image_token = _figure_image.set(image)
    try:
        with langfuse_prompts.prompt_scope(node, system, user, skill_text=skill_text) as span:
            answer = chat(system, user, schema)
            if span is not None:
                span.update(output=answer.model_dump())
            return answer
    finally:
        _figure_image.reset(image_token)
        _node_model.reset(token)


def _cli_call(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    """구독 `claude -p`로 같은 모델을 불러 schema 객체로 돌려준다(개발 중 반복 테스트용, 최종 정리 때 지운다)."""
    # [왜] CLI에는 response_format이 없어 JSON Schema를 시스템 프롬프트 끝에 붙여 형식을 요구한다
    # 시스템 프롬프트에 JSON Schema를 붙이고, 답에서 JSON만 꺼내 schema로 검증한다
    budget = _evaluation_budget.get()
    if budget is not None and budget.on_reserve is not None:
        raise EvaluationLimitError('운영 예산은 OpenRouter 경로에서만 지원합니다.')
    schema_text = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    system_full = f"{system}\n\n출력은 아래 JSON Schema를 따르는 JSON 하나만 낸다. 다른 글은 쓰지 않는다.\n{schema_text}"
    # [주의] --tools ""로 도구를 끄고, 임시 폴더에서 실행해 저장소의 CLAUDE.md가 읽히지 않게 한다
    done = subprocess.run(
        ["claude", "-p", "--model", LLM_CLI_MODEL, "--tools", "", "--system-prompt", system_full,
         "--output-format", "json", user],
        cwd=tempfile.gettempdir(), capture_output=True, text=True, timeout=300, check=True,  # [주의] 300초 제한, 실패하면 CalledProcessError
    )
    return schema.model_validate_json(_json_part(json.loads(done.stdout).get("result", "")))


def _json_part(raw: str) -> str:
    """답 글자에서 첫 { 부터 마지막 } 까지를 꺼낸다."""
    # [왜] 모델이 JSON을 ``` 코드 블록으로 감싸 답하는 경우에 대비한다
    found = re.search(r"\{.*\}", raw, re.S)
    return found.group(0) if found else raw


def chat(system: str, user: str, schema: type[BaseModel]) -> BaseModel:
    """시스템·사용자 메시지를 보내고 schema 형식으로 검증한 답을 돌려준다(그래프 노드가 쓰는 유일한 LLM 입구).

    형식이 틀리면 MAX_FORMAT_RETRIES번까지 다시 부르고, 그래도 틀리면 마지막 검증 오류를 담아 ValueError를 낸다.
    연결 오류(시간 초과 포함)와 429 · 5xx도 같은 상한 안에서 잠깐 쉬고 다시 부르고, 끝내 안 되면 그 오류를 그대로 낸다.
    공급자는 LLM_PROVIDER(openrouter | claude_cli), 모델은 LLM_MODEL / LLM_CLI_MODEL이다(ADR 0010).
    """
    from langchain_core.exceptions import OutputParserException
    from openai import APIConnectionError, APIStatusError

    call = _cli_call if LLM_PROVIDER == "claude_cli" else _openrouter_call
    last_error = None
    # [주의] 최초 1번 + 재시도 MAX_FORMAT_RETRIES번이 호출 횟수의 절대 상한이다(키 한도 보호). 형식 오류 · 연결 오류 · 429/5xx가 같은 상한을 나눠 쓴다
    for attempt in range(1 + MAX_FORMAT_RETRIES):
        try:
            return call(system, user, schema)
        except (ValidationError, OutputParserException) as error:
            last_error = error
        except (APIConnectionError, APIStatusError) as error:
            # [왜] 연결이 끊기거나 시간이 넘으면(APITimeoutError 포함) 한 번에 문항 전체가 실패했다(v3-15, 11-09 OpenRouter). 잠깐 쉬고 다시 부른다
            #      429(한도) · 5xx(공급자 오류)도 일시적이라 같은 상한 안에서 1 · 2초 쉬고 다시 부른다(점검 C #2). 그 밖의 4xx(키 · 크레딧 · 요청 오류)는 다시 불러도 같다
            if isinstance(error, APIStatusError) and error.status_code != 429 and error.status_code < 500:
                raise
            last_error = error
            if attempt < MAX_FORMAT_RETRIES:
                budget = _evaluation_budget.get()
                delay = (1 if isinstance(error, APIStatusError) else 2) * (attempt + 1)
                time.sleep(min(delay, budget.remaining()) if budget else delay)
    if isinstance(last_error, (APIConnectionError, APIStatusError)):
        raise last_error  # 연결 · 공급자 오류는 형식 오류로 바꾸지 않고 그대로 올린다
    raise LLMFormatError(f"LLM 출력이 {schema.__name__} 형식을 {1 + MAX_FORMAT_RETRIES}번 모두 어겼다") from last_error
