"""evals/runners/run_skill_pair.py의 순차 실행 경로·생성 입력 격리·부분 결과 저장과 llm.EvaluationBudget 호출 상한을 검사한다.

- 역할: 순차 실행의 여섯 경로·검색 상한, 같은 생성 상태의 사본 격리와 실행 순서 교차, 예외 시 부분 결과·오류 원문 제외·덮어쓰기 금지, 평가 호출·예약비용 상한을 확인한다.
- 하지 않는 일: 외부 API는 호출하지 않는다. 답의 품질 비교는 하지 않는다.
- 출처: SPEC 5절 "Skill 비교용 순차 실행기", evals/guides/preregister.md #17·#18
"""
import json

import pytest

from backend.graph import nodes
from backend.services import llm
from evals.runners import run_skill_pair as pair


@pytest.mark.parametrize("kind,passes,empty,want", [
    ("role", [], False, ["입력 읽기", "라우팅"]),
    ("out_of_scope", [], False, ["입력 읽기", "라우팅", "거절"]),
    ("rating", [True], False, ["입력 읽기", "라우팅", "검색", "채점"]),
    ("candidate_judge", [False, True], False, ["입력 읽기", "라우팅", "검색", "채점", "재작성", "검색", "채점"]),
    ("candidate_find", [False, False], False, ["입력 읽기", "라우팅", "검색", "채점", "재작성", "검색", "채점", "거절"]),
    ("rating", [], True, ["입력 읽기", "라우팅", "검색", "채점", "거절"]),
])
def test_prepare_follows_diagram(monkeypatch, kind, passes, empty, want):
    """질문 종류·채점 결과별로 prepare가 그림의 노드 순서를 따르고, 검색은 2번을 넘지 않으며, 정답이 LLM 입력에 새지 않는지 확인한다."""
    grades = iter(passes)
    queries = []

    def chat(system, user, schema):
        """라우팅·채점·재작성 호출을 흉내 낸다. 입력에 정답이 있으면 실패한다."""
        assert "SECRET_ANSWER" not in user
        if schema is nodes.Route:
            return schema(question_type=kind)
        if schema is nodes.Grade:
            return schema(passed_ids=[1] if next(grades) else [])
        assert schema is nodes.Rewrite
        return schema(query="1N5819 Forward voltage")

    def retrieve(question, *, parts):
        """검색을 흉내 내고 호출 인자를 기록한다."""
        queries.append((question, parts))
        return [] if empty else [{"chunk_id": 1, "file": "diode.pdf", "page": 1, "content": "VF", "table": ""}]

    monkeypatch.setattr(nodes.llm, "chat", chat)
    state = pair.prepare({"id": "x", "input": "1N5819 VF?", "expected": "SECRET_ANSWER"}, retrieve)
    assert state["path"] == want
    assert len(queries) == want.count("검색") <= 2
    assert "expected" not in state
    if len(queries) == 2:
        assert queries[0][1] == queries[1][1] == ["1N5819"]


def test_pair_uses_isolated_equal_states_and_alternates_order(monkeypatch):
    """with/without 생성이 같은 입력의 따로 복사한 상태를 받고, reverse면 순서가 뒤집히는지 확인한다."""
    seen = []

    def generate(state, *, use_skill=False):
        """받은 상태를 기록하고 일부러 상태를 망가뜨려 복사본 격리를 시험한다."""
        seen.append((use_skill, json.dumps(state, sort_keys=True)))
        state["docs"].clear()
        return {"answer": "answer", "skill": {"applied": use_skill}}

    monkeypatch.setattr(nodes, "generate", generate)
    state = {"question_type": "rating", "docs": [{"chunk_id": 1}], "passed": [1], "path": ["채점"]}
    pair.compare(state, reverse=True)
    assert [x[0] for x in seen] == [True, False]
    assert seen[0][1] == seen[1][1]
    assert state["docs"] == [{"chunk_id": 1}]


def test_error_keeps_previous_rows_and_sanitizes_error(monkeypatch, tmp_path):
    """둘째 문항에서 예외가 나도 첫 문항 결과가 남고, 예외 원문(비밀 후보)은 파일에 저장되지 않으며, 결과 폴더를 덮어쓰지 않는지 확인한다."""
    def prepare(item, retriever):
        """문항 b에서만 비밀이 든 예외를 낸다."""
        if item["id"] == "b":
            raise RuntimeError("secret-password")
        return {"question_type": "out_of_scope", "answer": "범위 밖", "path": ["거절"]}

    monkeypatch.setattr(pair, "prepare", prepare)
    result = pair.run([{"id": "a", "input": "A"}, {"id": "b", "input": "B"}], None, tmp_path / "new", {})
    assert result["status"] == "incomplete"
    assert result["error_type"] == "RuntimeError"
    raw = (tmp_path / "new" / "result.json").read_text()
    assert "secret-password" not in raw
    assert len(json.loads(raw)["rows"]) == 1
    with pytest.raises(FileExistsError):
        pair.run([], None, tmp_path / "new", {})


def test_budget_stops_before_call_and_keeps_reservation():
    """호출 수·예약 비용 상한을 넘기 전에 EvaluationLimitError가 나고, 거절된 예약은 기록되지 않는지 확인한다."""
    budget = llm.EvaluationBudget(max_calls=1, max_usd=1, max_seconds=60, prompt_rate=0.000001, completion_rate=0.000001)
    assert 0 < budget.reserve("abc", output_tokens=10) <= 45
    with pytest.raises(llm.EvaluationLimitError):
        budget.reserve("abc", output_tokens=10)
    assert budget.calls == 1 and budget.reserved_usd > 0
    tiny = llm.EvaluationBudget(max_calls=5, max_usd=0.000001, max_seconds=60, prompt_rate=1, completion_rate=1)
    with pytest.raises(llm.EvaluationLimitError):
        tiny.reserve("abc", output_tokens=10)
    assert tiny.calls == 0


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, 0.0])
def test_budget_rejects_invalid_limits_before_reserving(bad):
    """NaN·무한대·0·음수 예산은 예약 전에 ValueError로 거부되는지 확인한다."""
    with pytest.raises(ValueError):
        budget = llm.EvaluationBudget(1, bad, 60, 0.000001, 0.000001)
        budget.reserve("question", output_tokens=1)


def test_reservation_uses_all_reachable_price_tiers():
    """프롬프트 길이로 닿을 수 있는 가장 비싼 가격 구간으로 예약하는지 확인한다."""
    budget = llm.EvaluationBudget(5, 1, 60, 0.0000001, 0.0000005,
        pricing_tiers=({"min_prompt_tokens": 10000, "prompt": "0.0000005", "completion": "0.0000025"},))
    budget.reserve("a", output_tokens=10)
    first = budget.reserved_usd
    assert first == pytest.approx(8193 * 0.0000001 + 10 * 0.0000005)
    budget.reserve("a" * 2000, output_tokens=10)
    assert budget.reserved_usd - first == pytest.approx(10192 * 0.0000005 + 10 * 0.0000025)


def test_raw_chat_and_embedding_share_budget_and_restore_defaults(monkeypatch):
    """채팅과 임베딩 호출이 한 예산을 나눠 쓰고, 상한을 넘으면 막히며, 끝나면 예산 설정이 복원되는지 확인한다."""
    calls = []

    class Model:
        def with_structured_output(self, schema):
            return self

        def invoke(self, messages, **options):
            assert options["max_tokens"] == 1024
            assert 0 < options["timeout"] <= 45
            calls.append("chat")
            return nodes.Answer(answer="확인")

    class Embedding:
        def with_options(self, *, timeout):
            assert 0 < timeout <= 45
            return self

        @property
        def embeddings(self):
            return self

        def create(self, **kwargs):
            from types import SimpleNamespace
            calls.append("embed")
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1])], usage=SimpleNamespace(total_tokens=1))

    monkeypatch.setattr(llm, "_chat_model", Model)
    monkeypatch.setattr(llm, "_embedding_client", lambda: (Embedding(), "openrouter", "small"))
    budget = llm.EvaluationBudget(2, 1, 60, 0.000001, 0.000001)
    with llm.evaluation_limits(budget):
        llm._openrouter_call("system", "user", nodes.Answer)
        llm.embed_texts(["question"])
        with pytest.raises(llm.EvaluationLimitError):
            llm._openrouter_call("system", "user", nodes.Answer)
    assert calls == ["chat", "embed"]
    assert llm._evaluation_budget.get() is None
    budget.started -= 61
    with pytest.raises(llm.EvaluationLimitError):
        budget.reserve("abc", output_tokens=1)


def test_second_generation_failure_keeps_first_answer(monkeypatch, tmp_path):
    """두 번째 생성이 실패해도 첫 번째 답은 result.json에 남는지 확인한다."""
    monkeypatch.setattr(pair, "prepare", lambda item, retriever: {"question_type": "role", "path": ["라우팅"]})

    def generate(state, *, use_skill=False):
        """Skill 있는 쪽만 실패하고 없는 쪽은 첫 답을 돌려준다."""
        if use_skill:
            raise TimeoutError("private")
        return {"answer": "first"}

    monkeypatch.setattr(nodes, "generate", generate)
    out = pair.run([{"id": "a", "input": "A"}], None, tmp_path / "new", {})
    assert out["status"] == "incomplete"
    assert list(out["rows"][0]["answers"]) == ["without"]
    assert out["rows"][0]["answers"]["without"]["answer"] == "first"


def test_actual_sdk_request_receives_evaluation_timeout(monkeypatch):
    """실제 SDK 요청에 평가용 타임아웃(45초 이하)과 출력 토큰 상한(1024)이 실리는지 가짜 전송으로 확인한다."""
    import httpx
    from langchain_openai import ChatOpenAI
    seen = []

    def transport(request):
        """요청의 타임아웃과 본문을 기록하고 고정 응답을 돌려준다."""
        body = json.loads(request.content)
        seen.append((request.extensions["timeout"], body))
        message = {"role": "assistant", "content": '{"answer":"ok"}'}
        if body.get("tools"):
            message["tool_calls"] = [{"id": "test", "type": "function", "function": {
                "name": "Answer", "arguments": '{"answer":"ok"}'}}]
        return httpx.Response(200, json={"id": "test", "object": "chat.completion", "model": "gpt-4o",
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}]})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = ChatOpenAI(model="gpt-4o", api_key="test-key", base_url="https://example.invalid/v1",
                           http_client=client, max_retries=0)
        monkeypatch.setattr(llm, "_chat_model", lambda: model)
        with llm.evaluation_limits(llm.EvaluationBudget(1, 1, 60, 0.000001, 0.000001)):
            assert llm._openrouter_call("sys", "q", nodes.Answer).answer == "ok"
    timeout, body = seen[0]
    assert all(value is not None and 0 < value <= 45 for value in timeout.values())
    assert body.get("max_completion_tokens", body.get("max_tokens")) == 1024
