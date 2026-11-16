"""LLM 호출 입구(backend.services.llm): 형식 검증, 재시도 상한, 임베딩 반환 계약을 가짜 모델로 확인한다.

- 역할: chat()의 형식 검증·재시도 상한(호출 3번)·구독 CLI 명령, 임베딩 반환 계약을 확인한다.
- 하지 않는 일: API를 부르지 않는다. 모델 응답의 품질은 보지 않는다.
- 출처: AGENTS.md 지킬 것 2·6, ADR 0010
"""
import json
import io
from types import SimpleNamespace

import pytest


def test_budget_reservations_are_thread_safe_and_callback_precedes_accounting():
    from concurrent.futures import ThreadPoolExecutor
    from backend.services.llm import EvaluationBudget, EvaluationLimitError
    charges = []
    budget = EvaluationBudget(max_calls=1, max_usd=1, max_seconds=30,
                              prompt_rate=0.000001, completion_rate=0.000001, on_reserve=charges.append)
    def reserve(_):
        try:
            budget.reserve('x', output_tokens=0)
            return True
        except EvaluationLimitError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, range(2))) == [False, True]
    assert len(charges) == 1 and budget.calls == 1
    assert budget.remaining() <= 30


def test_exhausted_runtime_budget_does_not_invoke_provider(monkeypatch):
    from backend.services import llm
    class Model:
        def with_structured_output(self, schema):
            return self
        def invoke(self, *args, **kwargs):
            raise AssertionError('external provider must not run')
    monkeypatch.setattr(llm, '_chat_model', lambda *args: Model())
    budget = llm.EvaluationBudget(max_calls=1, max_usd=1, max_seconds=30,
                                 prompt_rate=0.000001, completion_rate=0.000001, on_reserve=lambda cost: None)
    budget.reserve('first', output_tokens=0)
    from backend.graph.nodes import Answer
    with llm.evaluation_limits(budget), pytest.raises(llm.EvaluationLimitError):
        llm._openrouter_call('system', 'user', Answer)
from pydantic import BaseModel

from backend.services import llm


def test_evaluation_decisions_catalog_uses_decisions_and_zdr_filters():
    urls = []

    def opener(url, timeout):
        urls.append((url, timeout))
        return io.BytesIO(b'{"data": [{"id": "typesafe/jev-1.14"}]}')

    assert llm.evaluation_decisions_catalog(zdr=False, opener=opener)[0]["id"] == "typesafe/jev-1.14"
    assert llm.evaluation_decisions_catalog(zdr=True, opener=opener)[0]["id"] == "typesafe/jev-1.14"
    assert urls == [
        ("https://openrouter.ai/api/v1/models?output_modalities=decisions", 30),
        ("https://openrouter.ai/api/v1/models?output_modalities=decisions&zdr=true", 30),
    ]


def test_evaluation_decision_posts_policy_once_without_network(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    calls = []

    def opener(request, timeout):
        calls.append((request, timeout))
        return io.BytesIO(b'{"id": "decision-1", "answers": {}}')

    body = {
        "model": "typesafe/jev-1.14",
        "state": {"user_input": "질문"},
        "questions": {"question_type": {"type": "choice"}},
        "provider": {"zdr": True, "data_collection": "deny", "allow_fallbacks": False},
    }
    assert llm.evaluation_decision(body, timeout=12, opener=opener)["id"] == "decision-1"
    assert len(calls) == 1
    request, timeout = calls[0]
    assert request.get_method() == "POST"
    assert request.full_url == "https://openrouter.ai/api/alpha/decisions"
    assert json.loads(request.data)["provider"] == body["provider"]
    assert timeout == 12


def test_evaluation_decision_rejects_unsafe_policy_before_network(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    with pytest.raises(ValueError, match="provider policy"):
        llm.evaluation_decision(
            {"model": "typesafe/jev-1.14", "provider": {"zdr": False}},
            opener=lambda *_args, **_kwargs: pytest.fail("network called"),
        )


class Route(BaseModel):
    kind: str


def _fake_calls(monkeypatch, answers):
    """LangChain 채팅 모델을 가짜로 바꾼다. 정해 둔 답 글자를 schema로 검증해 돌려주고 호출 횟수를 센다."""
    calls = []

    def invoke(messages, schema):
        calls.append(messages)
        # 진짜 with_structured_output처럼 형식이 틀리면 ValidationError를 낸다
        return schema.model_validate_json(answers[len(calls) - 1])

    fake_model = SimpleNamespace(
        with_structured_output=lambda schema: SimpleNamespace(invoke=lambda messages: invoke(messages, schema)))
    monkeypatch.setattr(llm, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm, "_chat_model", lambda *_: fake_model)
    return calls


def test_chat_returns_validated_model(monkeypatch):
    calls = _fake_calls(monkeypatch, ['{"kind": "role"}', '{"kind": "role"}'])
    assert llm.chat("sys", "q", Route) == Route(kind="role")
    assert len(calls) == 1
    # [왜] OpenRouter의 Claude 모델은 고정 지시문(system)에만 캐시 표시를 붙인다(11-09 프롬프트 캐싱). 질문(user)은 그대로
    assert calls[0] == [{"role": "system", "content": [{"type": "text", "text": "sys", "cache_control": {"type": "ephemeral"}}]},
                        {"role": "user", "content": "q"}]
    monkeypatch.setattr(llm, "LLM_MODEL", LUNA)  # Claude가 아닌 모델에는 붙이지 않는다
    llm.chat("sys", "q", Route)
    assert calls[1] == [{"role": "system", "content": "sys"}, {"role": "user", "content": "q"}]


def test_chat_retries_bad_format_then_succeeds(monkeypatch):
    calls = _fake_calls(monkeypatch, ["not json", '{"wrong": 1}', '{"kind": "out_of_scope"}'])
    assert llm.chat("sys", "q", Route).kind == "out_of_scope"
    assert len(calls) == 3


def test_chat_stops_after_retry_limit(monkeypatch):
    # [왜] 상수끼리 비교하면 상한을 바꿔도 통과하므로 호출 수를 리터럴 3(첫 호출 + 재시도 2)과 비교한다
    calls = _fake_calls(monkeypatch, ["bad"] * 10)
    with pytest.raises(ValueError):
        llm.chat("sys", "q", Route)
    assert len(calls) == 3


def test_chat_retries_connection_error_within_the_same_limit(monkeypatch):
    """연결 오류는 같은 상한(첫 호출 + 재시도 2) 안에서 다시 부르고, 끝내 안 되면 연결 오류 그대로 올린다."""
    import httpx
    from openai import APIConnectionError
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)
    calls = []

    def fake_call(system, user, schema):
        calls.append(1)
        if len(calls) < 3:
            raise APIConnectionError(request=httpx.Request("POST", "https://example.test"))
        return Route(kind="role")
    monkeypatch.setattr(llm, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm, "_openrouter_call", fake_call)
    assert llm.chat("sys", "q", Route) == Route(kind="role") and len(calls) == 3
    calls.clear()
    monkeypatch.setattr(llm, "_openrouter_call", lambda *a: calls.append(1) or (_ for _ in ()).throw(
        APIConnectionError(request=httpx.Request("POST", "https://example.test"))))
    with pytest.raises(APIConnectionError):
        llm.chat("sys", "q", Route)
    assert len(calls) == 3


def test_node_chat_retries_model_timeout_within_the_same_limit(monkeypatch):
    """그래프의 실제 node_chat 입구도 SDK 시간 초과를 3회 상한으로 재시도한다."""
    import httpx
    from openai import APITimeoutError

    monkeypatch.setattr(llm, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)
    calls = []

    def timeout(*_args):
        calls.append(1)
        raise APITimeoutError(request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat"))

    monkeypatch.setattr(llm, "_openrouter_call", timeout)
    with pytest.raises(APITimeoutError):
        llm.node_chat("route", "system", "user", Route)
    assert len(calls) == 3


def _status_error(cls, status):
    import httpx
    return cls(message=f"synthetic {status}", response=httpx.Response(status, request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat")),
               body={"error": {"code": status}})


def test_node_chat_retries_model_rate_limit_within_the_same_limit(monkeypatch):
    """공급자 429는 형식 · 연결 오류와 같은 상한(첫 호출 + 재시도 2)과 1 · 2초 쉼으로 다시 부르고, 끝내 안 되면 그 오류를 올린다(점검 C #2)."""
    from openai import RateLimitError

    monkeypatch.setattr(llm, "LLM_PROVIDER", "openrouter")
    sleeps = []
    monkeypatch.setattr(llm.time, "sleep", sleeps.append)
    calls = []

    def rate_limited(*_args):
        calls.append(1)
        raise _status_error(RateLimitError, 429)

    monkeypatch.setattr(llm, "_openrouter_call", rate_limited)
    with pytest.raises(RateLimitError):
        llm.node_chat("route", "system", "user", Route)
    assert len(calls) == 3 and sleeps == [1, 2]


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_chat_recovers_after_transient_provider_status(monkeypatch, status):
    from openai import InternalServerError, RateLimitError

    monkeypatch.setattr(llm, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm.time, "sleep", lambda *_: None)
    calls = []

    def flaky(*_args):
        calls.append(1)
        if len(calls) < 3:
            raise _status_error(RateLimitError if status == 429 else InternalServerError, status)
        return Route(kind="role")

    monkeypatch.setattr(llm, "_openrouter_call", flaky)
    assert llm.chat("sys", "q", Route) == Route(kind="role") and len(calls) == 3


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404])
def test_chat_does_not_retry_permanent_provider_status(monkeypatch, status):
    """키 · 크레딧 · 요청 오류는 다시 불러도 같고 호출 수(키 한도)만 늘어난다."""
    from openai import APIStatusError

    monkeypatch.setattr(llm, "LLM_PROVIDER", "openrouter")
    monkeypatch.setattr(llm.time, "sleep", lambda *_: pytest.fail("permanent errors must not wait"))
    calls = []

    def refused(*_args):
        calls.append(1)
        raise _status_error(APIStatusError, status)

    monkeypatch.setattr(llm, "_openrouter_call", refused)
    with pytest.raises(APIStatusError):
        llm.chat("sys", "q", Route)
    assert len(calls) == 1


def test_provider_and_format_failures_are_llm_failures_but_limits_are_not():
    from openai import RateLimitError
    assert llm.is_llm_failure(llm.LLMFormatError("x")) and llm.is_llm_failure(_status_error(RateLimitError, 429))
    assert issubclass(llm.LLMFormatError, ValueError)  # ValueError로 잡던 곳(plan_node)은 그대로 동작한다
    assert not llm.is_llm_failure(llm.EvaluationLimitError("한도")) and not llm.is_llm_failure(RuntimeError("x"))


def test_cli_call_disables_tools_and_puts_schema_in_system_prompt(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"], seen["cwd"] = cmd, kwargs["cwd"]
        return SimpleNamespace(stdout=json.dumps({"result": '{"kind": "role"}'}))

    monkeypatch.setattr(llm, "LLM_PROVIDER", "claude_cli")
    monkeypatch.setattr(llm.subprocess, "run", fake_run)
    assert llm.chat("규칙", "질문", Route).kind == "role"
    cmd = seen["cmd"]
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--model") + 1] == llm.LLM_CLI_MODEL
    assert '"kind"' in cmd[cmd.index("--system-prompt") + 1]
    assert cmd[-1] == "질문"


def test_cli_call_reads_json_inside_code_fence(monkeypatch):
    fenced = '```json\n{"kind": "rating"}\n```'
    monkeypatch.setattr(llm, "LLM_PROVIDER", "claude_cli")
    monkeypatch.setattr(llm.subprocess, "run", lambda cmd, **kw: SimpleNamespace(stdout=json.dumps({"result": fenced})))
    assert llm.chat("규칙", "질문", Route).kind == "rating"


def test_embed_texts_returns_vectors_usage_and_provider_metadata(monkeypatch):
    response = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1, 0.2])],
        usage=SimpleNamespace(total_tokens=7),
    )
    embeddings = SimpleNamespace(create=lambda **_: response)
    client = SimpleNamespace(embeddings=embeddings)
    monkeypatch.setattr(
        llm,
        "_embedding_client",
        lambda: (client, "test-provider", "test-model"),
        raising=False,
    )

    assert llm.embed_texts(["query"]) == (
        [[0.1, 0.2]],
        7,
        "test-provider",
        "test-model",
    )


def test_evaluation_chat_enforces_privacy_and_returns_usage(monkeypatch):
    """평가 전용 호출이 full model ID·ZDR 정책·schema를 보내고 usage만 구조화해 돌려줘야 한다."""
    seen = {}

    class Usage:
        def model_dump(self):
            return {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15, "cost": 0.00001}

    response = SimpleNamespace(
        id="gen-1",
        model="openai/gpt-6-luna",
        provider="test-provider",
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"kind":"role"}'), finish_reason="stop")],
        usage=Usage(),
    )

    class Completions:
        def create(self, **kwargs):
            seen.update(kwargs)
            return response

    client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    monkeypatch.setattr(llm, "_evaluation_client", lambda timeout: client)
    policy = {"zdr": True, "data_collection": "deny", "allow_fallbacks": False, "require_parameters": True}

    parsed, metadata = llm.evaluation_chat(
        "openai/gpt-6-luna", "system", "question", Route, provider_policy=policy, max_tokens=256, timeout=12,
    )

    assert parsed == Route(kind="role")
    assert seen["model"] == "openai/gpt-6-luna"
    assert seen["max_completion_tokens"] == 256
    assert "temperature" not in seen and "max_tokens" not in seen
    assert seen["extra_body"] == {"provider": policy, "usage": {"include": True}}
    assert seen["response_format"]["type"] == "json_schema"
    assert metadata == {
        "response_id": "gen-1",
        "actual_model": "openai/gpt-6-luna",
        "provider": "test-provider",
        "finish_reason": "stop",
        "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15, "cost": 0.00001},
    }


@pytest.mark.parametrize(
    ("model", "expected", "absent"),
    [
        ("anthropic/claude-haiku-5.5", {"max_tokens": 256}, {"temperature", "max_completion_tokens"}),
        ("deepseek/deepseek-v4.1-flash", {"temperature": 0, "max_tokens": 256}, {"max_completion_tokens"}),
    ],
)
def test_evaluation_chat_uses_model_supported_generation_parameters(monkeypatch, model, expected, absent):
    """ZDR endpoint가 지원하지 않는 parameter를 보내 require_parameters routing을 막아서는 안 된다."""
    seen = {}
    response = SimpleNamespace(
        id="gen-parameters", model=model, provider="test-provider",
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"kind":"role"}'), finish_reason="stop")],
        usage=None,
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: seen.update(kwargs) or response,
    )))
    monkeypatch.setattr(llm, "_evaluation_client", lambda timeout: client)

    llm.evaluation_chat(model, "sys", "q", Route, provider_policy={"zdr": True, "require_parameters": True},
                        max_tokens=256, timeout=30)

    assert all(seen[key] == value for key, value in expected.items())
    assert absent.isdisjoint(seen)


def test_evaluation_chat_reserves_budget_before_sdk_call(monkeypatch):
    """평가 호출은 SDK 전송 전에 호출 수·예약 비용을 차감하고 상한 뒤 요청은 보내지 않아야 한다."""
    calls = []
    response = SimpleNamespace(
        id="gen-1",
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"kind":"role"}'), finish_reason="stop")],
        usage=None,
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kwargs: calls.append(kwargs) or response,
    )))
    monkeypatch.setattr(llm, "_evaluation_client", lambda timeout: client)
    budget = llm.EvaluationBudget(1, 1, 60, 0.000001, 0.000001, max_tokens=256)

    with llm.evaluation_limits(budget):
        llm.evaluation_chat("openai/gpt-6-luna", "sys", "q", Route,
                            provider_policy={"zdr": True}, max_tokens=256, timeout=30)
        with pytest.raises(llm.EvaluationLimitError):
            llm.evaluation_chat("openai/gpt-6-luna", "sys", "q", Route,
                                provider_policy={"zdr": True}, max_tokens=256, timeout=30)

    assert len(calls) == 1 and budget.calls == 1


def test_evaluation_chat_reconciles_reservation_to_reported_cost(monkeypatch):
    """provider cost가 있으면 보수적 예약액 대신 실제 비용만 다음 호출 예산에서 차감해야 한다."""
    class Usage:
        def model_dump(self):
            return {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3, "cost": 0.00001}

    response = SimpleNamespace(
        id="gen-cost", model="openai/gpt-6-luna", provider="test-provider",
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"kind":"role"}'), finish_reason="stop")],
        usage=Usage(),
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: response)))
    monkeypatch.setattr(llm, "_evaluation_client", lambda timeout: client)
    budget = llm.EvaluationBudget(2, 1, 60, 0.000001, 0.000001, max_tokens=256)

    with llm.evaluation_limits(budget):
        llm.evaluation_chat("openai/gpt-6-luna", "sys", "q", Route,
                            provider_policy={"zdr": True}, max_tokens=256, timeout=30)

    assert budget.reserved_usd == pytest.approx(0.00001)


def test_evaluation_chat_keeps_provider_metadata_when_schema_is_invalid(monkeypatch):
    """응답 schema가 틀려도 호출 성공 여부와 provider를 잃으면 endpoint 실패로 오판한다."""
    response = SimpleNamespace(
        id="gen-invalid", model="meta/muse-glimmer-30b", provider="TestProvider",
        choices=[SimpleNamespace(message=SimpleNamespace(content='{}'), finish_reason="stop")],
        usage=None,
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: response)))
    monkeypatch.setattr(llm, "_evaluation_client", lambda timeout: client)

    with pytest.raises(llm.EvaluationFormatError) as caught:
        llm.evaluation_chat("meta/muse-glimmer-30b", "sys", "q", Route,
                            provider_policy={"zdr": True}, max_tokens=256, timeout=30)

    assert caught.value.metadata["provider"] == "TestProvider"
    assert caught.value.metadata["actual_model"] == "meta/muse-glimmer-30b"


def _voyage_http(monkeypatch, *replies):
    """httpx.post를 가짜로 바꿔 (주소, 요청 본문)을 기록하고 replies를 차례로 돌려준다. 네트워크는 쓰지 않는다."""
    import httpx
    sent, replies = [], list(replies)
    monkeypatch.setenv("VOYAGE_API_KEY", "fake-key")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    monkeypatch.setattr(httpx, "post", lambda url, **kw: sent.append((url, kw["json"])) or replies.pop(0))
    return sent


def _reply(status, body=None, text=""):
    return SimpleNamespace(status_code=status, json=lambda: body, text=text)


def test_voyage_embed_builds_query_payload_and_orders_by_index(monkeypatch):
    sent = _voyage_http(monkeypatch, _reply(200, {"data": [{"index": 1, "embedding": [2.0]}, {"index": 0, "embedding": [1.0]}]}))
    assert llm.voyage_embed(["a", "b"], "query") == [[1.0], [2.0]]
    assert sent == [("https://api.voyageai.com/v1/embeddings", {"input": ["a", "b"], "model": "voyage-4-large", "input_type": "query",
                                                                  "truncation": True, "output_dimension": 1024})]


def test_voyage_rerank_returns_ranked_indices(monkeypatch):
    sent = _voyage_http(monkeypatch, _reply(200, {"data": [{"index": 2}, {"index": 0}, {"index": 1}]}))
    assert llm.voyage_rerank("q", ["a", "b", "c"]) == [2, 0, 1]
    assert sent[0] == ("https://api.voyageai.com/v1/rerank", {"query": "q", "documents": ["a", "b", "c"], "model": "rerank-3", "truncation": True})


def test_voyage_retries_429_but_stops_on_payment_signal(monkeypatch):
    sent = _voyage_http(monkeypatch, _reply(429), _reply(200, {"data": [{"index": 0}]}))
    assert llm.voyage_rerank("q", ["a"]) == [0] and len(sent) == 2
    sent = _voyage_http(monkeypatch, _reply(402, text="payment required"))
    with pytest.raises(llm.UpstreamError, match="payment") as error:  # [왜] 바깥 공급자 장애라 분석 실패는 502(ADR 0019)
        llm.voyage_rerank("q", ["a"])
    assert len(sent) == 1 and llm.is_upstream_error(error.value)  # 결제 신호는 다시 부르지 않는다


def test_voyage_runtime_retry_reserves_before_each_external_call(monkeypatch):
    sent = _voyage_http(monkeypatch, _reply(429))
    charges = []
    budget = llm.EvaluationBudget(1, 1, 30, 0.000001, 0.000001, on_reserve=charges.append)
    with llm.evaluation_limits(budget), pytest.raises(llm.EvaluationLimitError):
        llm.voyage_rerank('q', ['a'])
    assert len(sent) == len(charges) == budget.calls == 1


HAIKU, LUNA, SONNET = "anthropic/claude-haiku-5.5", "openai/gpt-6-luna", "anthropic/claude-sonnet-5.5"


def test_chat_model_is_cached_per_model_and_luna_gets_no_temperature(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    llm._chat_model.cache_clear()
    haiku, luna = llm._chat_model(HAIKU), llm._chat_model(LUNA)
    assert haiku.model_name == HAIKU and haiku.temperature == 0
    assert luna.model_name == LUNA and luna.temperature is None  # [왜] Luna에는 temperature를 보내지 않는다(3차 실측 계약)
    assert llm._chat_model(LUNA) is luna
    assert llm._chat_model(SONNET).temperature == 0  # Luna가 아닌 모델은 temperature 0


def test_openrouter_thinking_off_disables_haiku_and_shortens_sonnet(monkeypatch):
    """생각은 기본으로 끈다: Haiku는 reasoning 끔, Sonnet은 끌 수 없어(400) effort low, Luna에는 보내지 않는다."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    llm._chat_model.cache_clear()
    assert llm._chat_model(HAIKU).extra_body == {"reasoning": {"enabled": False}}
    assert llm._chat_model(SONNET).extra_body == {"reasoning": {"effort": "low"}}
    assert llm._chat_model(LUNA).extra_body is None


def test_node_model_follows_table_and_env_override_wins(monkeypatch):
    monkeypatch.setattr(llm, "LLM_MODEL_OVERRIDE", None)
    assert llm.node_model("supervisor") == HAIKU and llm.node_model("synth") == SONNET and llm.node_model("grade") == LUNA
    assert [llm.node_model(n) for n in ("route", "rewrite", "generate")] == [HAIKU] * 3
    monkeypatch.setattr(llm, "LLM_MODEL_OVERRIDE", "x/y")
    assert {llm.node_model(n) for n in ("route", "grade", "generate", "supervisor")} == {"x/y"}


def test_node_chat_calls_the_model_of_that_node(monkeypatch):
    monkeypatch.setattr(llm, "LLM_MODEL_OVERRIDE", None)
    monkeypatch.setattr(llm, "LLM_PROVIDER", "openrouter")
    used = []

    def chat_model(model):
        used.append(model)
        return SimpleNamespace(with_structured_output=lambda schema: SimpleNamespace(
            invoke=lambda messages: schema.model_validate_json('{"kind": "role"}')))

    monkeypatch.setattr(llm, "_chat_model", chat_model)
    llm.node_chat("synth", "sys", "q", Route)
    llm.node_chat("route", "sys", "q", Route)
    assert used == [SONNET, HAIKU]
    llm.chat("sys", "q", Route)  # node_chat 밖의 호출은 기본 모델
    assert used[-1] == llm.LLM_MODEL


def test_node_image_is_bounded_scoped_and_sent_only_to_provider(monkeypatch):
    monkeypatch.setattr(llm, 'LLM_PROVIDER', 'openrouter')
    messages = []
    monkeypatch.setattr(llm, '_chat_model', lambda model: SimpleNamespace(
        with_structured_output=lambda schema: SimpleNamespace(
            invoke=lambda body, **options: messages.append(body) or schema(kind='role'))))
    image = b'\x89PNG\r\n\x1a\nexample-image'
    llm.node_chat('docs_answer', 'sys', 'source caption', Route, image=image)
    assert messages[0][1]['content'][0] == {'type':'text', 'text':'source caption'}
    assert messages[0][1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
    assert llm._figure_image.get() is None
    llm.node_chat('docs_answer', 'sys', 'text only', Route)
    assert messages[1][1]['content'] == 'text only'
    for bad in (b'not-png', image * 30000):
        with pytest.raises(ValueError, match='bounded PNG'):
            llm.node_chat('docs_answer', 'sys', 'source caption', Route, image=bad)
    assert len(messages) == 2


def test_node_image_resets_after_provider_failure(monkeypatch):
    monkeypatch.setattr(llm, 'LLM_PROVIDER', 'openrouter')
    def fail(*args):
        assert llm._figure_image.get() is not None
        raise RuntimeError('provider failed')
    monkeypatch.setattr(llm, 'chat', fail)
    with pytest.raises(RuntimeError, match='provider failed'):
        llm.node_chat('docs_answer', 'sys', 'caption', Route, image=b'\x89PNG\r\n\x1a\nexample')
    assert llm._figure_image.get() is None


def test_model_rates_keys_match_node_models():
    from backend.services import langfuse_prompts, llm
    # [왜] 서비스 노드 모델(Haiku · Sonnet)이 단가표에 없으면 예약이 Sonnet 이상 기본 단가로 돌아가 판정 질문이 상한에 걸린다
    assert set(llm.MODEL_RATES) == {langfuse_prompts.HAIKU, langfuse_prompts.SONNET}
    assert {m for n, m in langfuse_prompts.NODE_MODELS.items() if n in ('supervisor', 'judge_read', 'docs_answer', 'card_read', 'card_pick', 'synth')} <= set(llm.MODEL_RATES)


def test_service_budget_fits_supervisor_and_three_judge_reads():
    # 11-10 데모 기록이 판정 읽기 두 번째 예약에서 멈춘 일을 재현한다: Supervisor 1번 + 판정 읽기 등 큰 호출 3번(예전 다수결 때 재현), 지시문 약 15KB씩
    from backend.conversations.memory_service import Conversations
    from backend.services import langfuse_prompts, llm
    prompt = 'x' * 15000
    budget, _, _ = Conversations._budget_settings()
    assert budget.per_model_rates
    for _ in range(4):
        budget.reserve(prompt, output_tokens=budget.max_tokens, model=langfuse_prompts.HAIKU)
    assert budget.reserved_usd < 0.05  # 실제 Haiku 단가라 넉넉하다
    old = llm.EvaluationBudget(max_calls=16, max_usd=0.50, max_seconds=90, prompt_rate=0.000003,
                               completion_rate=0.000015, max_tokens=4096)  # 예전 서비스 예약(모든 호출 같은 단가)
    with pytest.raises(llm.EvaluationLimitError):
        for _ in range(4):
            old.reserve(prompt, output_tokens=4096, model=langfuse_prompts.HAIKU)  # 네 번째 예약에서 $0.50을 넘는다


def test_unknown_model_falls_back_to_budget_rates():
    from backend.services import llm
    budget = llm.EvaluationBudget(max_calls=2, max_usd=1, max_seconds=30, prompt_rate=0.000003,
                                  completion_rate=0.000015, max_tokens=100, per_model_rates=True)
    budget.reserve('a' * 1000, output_tokens=100, model='openai/gpt-6-luna')
    assert budget.reserved_usd == pytest.approx((1000 + 8192) * 0.000003 + 100 * 0.000015)


def test_schematic_dialogue_uses_haiku_and_restores_model_context(monkeypatch):
    class Description(BaseModel):
        message: str
    models = []
    class Model:
        def with_structured_output(self, schema):
            return self
        def invoke(self, messages, **options):
            assert options['max_tokens'] == 128
            return Description(message='제조사가 다른 두 회로도입니다.')
    monkeypatch.setattr(llm, 'LLM_PROVIDER', 'openrouter')
    monkeypatch.setattr(llm, '_chat_model', lambda name: models.append(name) or Model())
    outer = llm._node_model.set('test/other-model')
    budget = llm.EvaluationBudget(max_calls=1, max_usd=.1, max_seconds=30,
        max_tokens=128, prompt_rate=1e-7, completion_rate=5e-7)
    try:
        with llm.evaluation_limits(budget):
            answer = llm.schematic_dialogue_chat('system', 'candidates', Description)
        assert answer.message == '제조사가 다른 두 회로도입니다.'
        assert models == ['anthropic/claude-haiku-5.5']
        assert budget.calls == 1
        assert llm._node_model.get() == 'test/other-model'
    finally:
        llm._node_model.reset(outer)


def test_schematic_dialogue_cannot_call_provider_without_a_budget(monkeypatch):
    monkeypatch.setattr(llm, '_chat_model', lambda *args: pytest.fail('unbudgeted provider call'))
    with pytest.raises(RuntimeError, match='budget'):
        llm.schematic_dialogue_chat('system', 'candidates', BaseModel)


def test_schematic_dialogue_keeps_daily_reservation_and_stops_after_three_calls(monkeypatch):
    from backend.conversations.memory_service import Conversations
    charges = []
    service = Conversations.__new__(Conversations)
    budget = llm.EvaluationBudget(max_calls=16, max_usd=.5, max_seconds=90,
        max_tokens=4096, prompt_rate=1e-7, completion_rate=5e-7,
        on_reserve=lambda cost: charges.append(cost))
    users = []
    monkeypatch.setattr(service, '_budget', lambda user: users.append(user) or budget)
    limited = service.schematic_dialogue_budget(7)
    assert users == [7]
    assert limited.remaining() <= 45
    assert limited.max_tokens <= 2048
    for _ in range(3):
        limited.reserve('candidate facts', output_tokens=10)
    with pytest.raises(llm.EvaluationLimitError):
        limited.reserve('fourth', output_tokens=10)
    assert len(charges) == 3


def test_voyage_reuses_one_client_with_per_request_timeout_and_headers(monkeypatch):
    import httpx
    made, seen = [], []

    class Client:
        def __init__(self):
            made.append(self)

        def post(self, url, **kw):
            seen.append(kw)
            return _reply(200, {"data": [{"index": 0, "embedding": [1.0]}]})

    monkeypatch.setattr(httpx, "Client", Client)
    monkeypatch.setattr(llm, "_voyage_client", None)
    monkeypatch.setenv("VOYAGE_API_KEY", "fake-key")
    llm.voyage_embed(["a"], "query")
    llm.voyage_embed(["b"], "query")
    assert len(made) == 1 and [k["timeout"] for k in seen] == [180, 180]  # client 하나를 재사용하고 요청마다 timeout을 준다
    assert seen[0]["headers"] == {"Authorization": "Bearer fake-key"}
