"""Langfuse 적용 계약. 네트워크와 실제 LLM 없이 컴파일·버전·전달 경계를 확인한다."""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from backend.services import langfuse_prompts as managed
from backend.services import llm


class Prompt:
    name = "sojafit/generate"
    version = 7
    config = {"model": "anthropic/claude-haiku-5.5", "temperature": 0, "max_tokens": 4096}

    def compile(self, **values):
        return [{"role": "system", "content": "base" + values["domain_skill"]},
                {"role": "user", "content": values["input"]}]


class Client:
    def __init__(self):
        self.spans = []

    @contextmanager
    def start_as_current_observation(self, **values):
        self.spans.append(values)
        yield SimpleNamespace(update=lambda **kwargs: None)


def test_managed_generation_links_prompt_and_skill_without_changing_user(monkeypatch):
    client = Client()
    seen = []
    skill = SimpleNamespace(name="sojafit/skills/diode-evidence", version=3, prompt="skill")
    monkeypatch.setattr(managed, "callback", lambda: "callback")

    def chat(system, user, schema):
        seen.append((system, user, managed.invocation_config()))
        return SimpleNamespace(model_dump=lambda: {"answer": "ok"})

    monkeypatch.setattr(llm, "chat", chat)
    with managed.session(client, {"generate": Prompt()}, skill):
        llm.node_chat("generate", "base\n\n<domain_skill>\nskill\n</domain_skill>", "question", object,
                      skill_text="skill")
    assert seen[0][0] == "base\n\n<domain_skill>\nskill\n</domain_skill>"
    assert seen[0][1] == "question"
    assert seen[0][2]["metadata"]["langfuse_prompt"].version == 7
    assert client.spans[0]["metadata"]["skill_version"] == 3
    assert managed.invocation_config() is None


def test_remote_local_mismatch_stops_before_chat(monkeypatch):
    monkeypatch.setattr(llm, "chat", lambda *args: pytest.fail("불일치한 프롬프트로 호출하면 안 된다"))
    with managed.session(Client(), {"generate": Prompt()}, None):
        with pytest.raises(ValueError):
            llm.node_chat("generate", "different", "question", object)


def test_untraced_node_uses_existing_chat_without_sdk(monkeypatch):
    monkeypatch.setattr(llm, "chat", lambda system, user, schema: (system, user))
    assert llm.node_chat("route", "system", "question", object) == ("system", "question")


def test_budget_preserves_langfuse_invocation_config(monkeypatch):
    sentinel = {"callbacks": ["callback"], "metadata": {"prompt_version": 7}}
    seen = {}

    def invoke(messages, **options):
        seen.update(options)
        return "answer"

    monkeypatch.setattr(managed, "invocation_config", lambda: sentinel)
    monkeypatch.setattr(managed, "bind_prompt", lambda runnable, options: SimpleNamespace(
        invoke=lambda messages, **kwargs: runnable.invoke(messages, **options, **kwargs)))
    monkeypatch.setattr(llm, "_chat_model", lambda: SimpleNamespace(
        with_structured_output=lambda schema: SimpleNamespace(invoke=invoke)))
    from pydantic import BaseModel

    class Schema(BaseModel):
        answer: str

    with llm.evaluation_limits(llm.EvaluationBudget(1, 1, 60, 0.000001, 0.000001)):
        llm._openrouter_call("system", "user", Schema)
    assert seen["config"] is sentinel
    assert seen["max_tokens"] == 1024 and seen["timeout"] <= 45


@pytest.mark.parametrize("broken", ["generation_missing", "wrong_version", "parent_missing"])
def test_timeline_rejects_incomplete_generation_binding(broken):
    from scripts.langfuse_skill_check import validate_timeline
    rows = [
        {"id": "root", "type": "SPAN", "name": "root", "start_time": "0", "end_time": "2"},
        {"id": "node", "type": "SPAN", "name": "generate", "parent_observation_id": "root", "start_time": "0", "end_time": "2"},
        {"id": "gen", "type": "GENERATION", "parent_observation_id": "node", "start_time": "1", "end_time": "2",
         "model": managed.CONFIG["model"], "prompt_name": Prompt.name, "prompt_version": 7},
    ]
    validate_timeline(rows, {"generate": Prompt()}, 1)
    if broken == "generation_missing":
        rows.pop()
    elif broken == "wrong_version":
        rows[-1]["prompt_version"] = 6
    else:
        rows[-1]["parent_observation_id"] = "absent"
    with pytest.raises(ValueError):
        validate_timeline(rows, {"generate": Prompt()}, 1)


def test_sdk_generation_keeps_prompt_version_with_budget(monkeypatch):
    import httpx
    from langchain_openai import ChatOpenAI
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler
    from langfuse.model import ChatPromptClient
    from langfuse.api.prompts.types.prompt import Prompt_Chat
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    from backend.graph.nodes import Answer
    import json

    exported = InMemorySpanExporter()
    key = "pk-lf-local-test"
    client = Langfuse(public_key=key, secret_key="sk-lf-local-test", base_url="https://example.invalid",
                      span_exporter=exported)
    prompt = ChatPromptClient(Prompt_Chat(type="chat", name="sojafit/generate", version=7,
        config=managed.CONFIG, labels=["development"], tags=[], prompt=[
            {"type": "chatmessage", "role": "system", "content": "base{{domain_skill}}"},
            {"type": "chatmessage", "role": "user", "content": "{{input}}"}]))

    def transport(request):
        body = json.loads(request.content)
        assert body.get("max_completion_tokens", body.get("max_tokens")) == 4096
        message = {"role": "assistant", "content": '{"answer":"ok"}'}
        if body.get("tools"):
            message["tool_calls"] = [{"id": "test", "type": "function", "function": {
                "name": "Answer", "arguments": '{"answer":"ok"}'}}]
        return httpx.Response(200, json={"id": "test", "object": "chat.completion", "model": managed.CONFIG["model"],
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}]})

    monkeypatch.setattr(managed, "callback", lambda: CallbackHandler(public_key=key))
    with httpx.Client(transport=httpx.MockTransport(transport)) as http:
        model = ChatOpenAI(model=managed.CONFIG["model"], api_key="test", base_url="https://example.invalid",
                           http_client=http, max_retries=0)
        monkeypatch.setattr(llm, "_chat_model", lambda: model)
        budget = llm.EvaluationBudget(1, 1, 60, 0.000001, 0.000001, max_tokens=4096)
        with managed.session(client, {"generate": prompt}, None), llm.evaluation_limits(budget):
            assert llm.node_chat("generate", "base", "question", Answer).answer == "ok"
    client.flush()
    generations = [s for s in exported.get_finished_spans() if s.attributes.get("langfuse.observation.type") == "generation"]
    assert len(generations) == 1
    assert generations[0].attributes["langfuse.observation.prompt.name"] == "sojafit/generate"
    assert generations[0].attributes["langfuse.observation.prompt.version"] == 7
    client.shutdown()


def test_publish_reuses_sdk_message_representation(monkeypatch):
    existing = SimpleNamespace(prompt=[{"type": "message", "role": "system", "content": "base"}], config=managed.CONFIG)
    client = SimpleNamespace(api=SimpleNamespace(prompts=SimpleNamespace(list=lambda **kwargs: SimpleNamespace(
        data=[SimpleNamespace(name="sojafit/route", labels=["development"])]))),
        get_prompt=lambda *args, **kwargs: existing,
        create_prompt=lambda **kwargs: pytest.fail("본문이 같으면 새 버전을 만들지 않는다"))
    assert managed.publish(client, "sojafit/route", [{"role": "system", "content": "base"}],
                           kind="chat", config=managed.CONFIG) is existing


def test_timeline_reads_public_observation_fields():
    from scripts.langfuse_skill_check import inspect_timeline
    rows = [SimpleNamespace(id="root", name="generate", type="SPAN", start_time="0", end_time="2"),
            SimpleNamespace(id="gen", name="model", type="GENERATION", parent_observation_id="root",
                            start_time="1", end_time="2", model=managed.CONFIG["model"],
                            prompt_name=Prompt.name, prompt_version=7)]
    client = SimpleNamespace(api=SimpleNamespace(observations=SimpleNamespace(
        get_many=lambda **kwargs: SimpleNamespace(data=rows))))
    timeline = inspect_timeline(client, "trace", {"generate": Prompt()}, 1)
    assert timeline[1]["parent_observation_id"] == "root"
    assert timeline[1]["prompt_version"] == 7


def test_observation_export_excludes_credentials_and_keeps_evidence():
    from scripts.langfuse_skill_check import inspect_timeline
    metadata = {"scope.attributes.public_key": "test-public-identifier",
                "nested": [{"secret_key": "test-secret", "skill_version": 1}],
                "skill_sha256": "test-hash", "prompt_tokens": 12}
    rows = [SimpleNamespace(id="node", name="generate", type="SPAN", start_time="0", end_time="2",
                            metadata=metadata),
            SimpleNamespace(id="gen", type="GENERATION", parent_observation_id="node",
                            start_time="1", end_time="2", model=managed.CONFIG["model"],
                            prompt_name=Prompt.name, prompt_version=7)]
    client = SimpleNamespace(api=SimpleNamespace(observations=SimpleNamespace(
        get_many=lambda **kwargs: SimpleNamespace(data=rows))))
    timeline = inspect_timeline(client, "trace", {"generate": Prompt()}, 1)
    assert timeline[0]["metadata"] == {"nested": [{"skill_version": 1}],
                                       "skill_sha256": "test-hash", "prompt_tokens": 12}
    assert metadata["scope.attributes.public_key"] == "test-public-identifier"


def test_timeline_rejects_error_in_parent_span():
    from scripts.langfuse_skill_check import validate_timeline
    rows = [{"id": "root", "name": "generate", "type": "SPAN", "start_time": "0", "end_time": "2", "level": "ERROR"},
            {"id": "gen", "type": "GENERATION", "parent_observation_id": "root", "start_time": "1", "end_time": "2",
             "model": managed.CONFIG["model"], "prompt_name": Prompt.name, "prompt_version": 7}]
    with pytest.raises(ValueError):
        validate_timeline(rows, {"generate": Prompt()}, 1)


def test_check_default_does_not_publish_draft(monkeypatch, tmp_path):
    from scripts import langfuse_skill_check as check
    import langfuse
    import sys
    import io, json
    monkeypatch.setattr(sys, "argv", ["check", str(tmp_path / "result.json")])
    monkeypatch.setattr(llm, "DEMO_MODE", False)
    monkeypatch.setattr(check, "urlopen", lambda *args, **kwargs: io.StringIO(json.dumps({"data": [
        {"id": managed.CONFIG["model"], "pricing": {"prompt": "0.0000001", "completion": "0.0000005"}}]})))
    monkeypatch.setattr(langfuse, "get_client", lambda: SimpleNamespace(auth_check=lambda: True))
    monkeypatch.setattr(managed, "publish_nodes", lambda client: pytest.fail("기본 확인은 원격에 쓰면 안 된다"))
    def mismatch(client):
        raise ValueError("로컬/원격 본문 불일치")
    monkeypatch.setattr(managed, "load_development", mismatch, raising=False)
    with pytest.raises(ValueError, match="불일치"):
        check.main()
    assert not (tmp_path / "result.json").exists()


def test_telemetry_failure_keeps_completed_case_and_budget(monkeypatch, tmp_path):
    from scripts import langfuse_skill_check as check
    import json
    client = Client()
    @contextmanager
    def root(**kwargs):
        yield SimpleNamespace(trace_id="trace", update=lambda **kwargs: None)
    client.start_as_current_observation = root
    def fail():
        raise RuntimeError("private-error-text")
    client.flush = fail
    def execute(*args):
        llm._evaluation_budget.get().reserve("question", output_tokens=1)
        return {"answer": "completed"}
    monkeypatch.setattr(check, "execute_case", execute)
    output = tmp_path / "result.json"
    result = {"cases": []}
    code = check.run_checks(client, {}, SimpleNamespace(version=1), output,
        llm.EvaluationBudget(10, 1, 60, 0.000001, 0.000001), result)
    saved = json.loads(output.read_text())
    assert code == 1 and saved["budget"]["raw_calls"] == 1
    assert saved["cases"][0]["result"]["answer"] == "completed"
    assert saved["cases"][0]["timeline_error_type"] == "RuntimeError"
    assert "private-error-text" not in output.read_text()


@pytest.mark.parametrize("bad", ["nan", "inf", "0", "-1"])
def test_invalid_cli_budget_stops_before_external_access(monkeypatch, tmp_path, bad):
    from scripts import langfuse_skill_check as check
    import sys
    monkeypatch.setattr(sys, "argv", ["check", str(tmp_path / "result.json"), "--max-usd", bad])
    monkeypatch.setattr(check, "urlopen", lambda *args, **kwargs: pytest.fail("유효하지 않은 예산으로 외부 접근하면 안 된다"))
    with pytest.raises(SystemExit) as error:
        check.main()
    assert error.value.code == 2


@pytest.mark.parametrize("broken", ["missing_input", "wrong_order"])
def test_case_timeline_requires_expected_nodes_and_order(broken):
    from scripts.langfuse_skill_check import validate_timeline
    stamp = lambda seconds: f"2026-11-03T00:00:0{seconds}+00:00"
    rows = [{"id": "root", "type": "SPAN", "name": "sojafit-skill-role", "start_time": stamp(0), "end_time": stamp(9)}]
    for index, name in enumerate(["read_input", "route", "generate"]):
        rows.append({"id": name, "type": "SPAN", "name": name, "parent_observation_id": "root",
                     "start_time": stamp(index * 2), "end_time": stamp(index * 2 + 1)})
    rows.append({"id": "gen", "type": "GENERATION", "parent_observation_id": "generate",
        "start_time": stamp(4), "end_time": stamp(5), "model": managed.CONFIG["model"],
        "prompt_name": Prompt.name, "prompt_version": 7})
    validate_timeline(rows, {"generate": Prompt()}, 1, case_kind="role")
    if broken == "missing_input":
        rows = [o for o in rows if o["id"] != "read_input"]
    else:
        rows[1]["start_time"], rows[1]["end_time"] = stamp(6), stamp(7)
    with pytest.raises(ValueError):
        validate_timeline(rows, {"generate": Prompt()}, 1, case_kind="role")


@pytest.mark.parametrize("broken", ["outside_parent", "uncovered_node"])
def test_timeline_rejects_generation_time_or_node_coverage(broken):
    from scripts.langfuse_skill_check import validate_timeline
    from copy import deepcopy
    def stamp(second):
        return f"2026-01-01T00:00:{second:02d}+00:00"
    def span(id, name, start, end, parent="root"):
        return {"id": id, "type": "SPAN", "name": name, "parent_observation_id": parent,
                "start_time": stamp(start), "end_time": stamp(end)}
    def generation(id, parent, node, start, end):
        return {"id": id, "type": "GENERATION", "parent_observation_id": parent,
                "start_time": stamp(start), "end_time": stamp(end), "model": managed.CONFIG["model"],
                "prompt_name": f"sojafit/{node}", "prompt_version": 4}
    observations = [span("root", "sojafit-skill-rating", 0, 12, None),
                    span("read", "read_input", 0, 1), span("route", "route", 1, 3),
                    span("search", "search", 3, 4), span("grade", "grade", 4, 6),
                    span("generate", "generate", 6, 8),
                    generation("r", "route", "route", 1, 2),
                    generation("g", "grade", "grade", 4, 5),
                    generation("a", "generate", "generate", 6, 7)]
    prompts = {name: SimpleNamespace(name=f"sojafit/{name}", version=4)
               for name in ("route", "grade", "generate")}
    validate_timeline(observations, prompts, 3, case_kind="rating")
    observations = deepcopy(observations)
    generation = next(o for o in observations if o.get("prompt_name") == "sojafit/generate")
    if broken == "outside_parent":
        generation["start_time"] = "2099-01-01T00:00:00+00:00"
        generation["end_time"] = "2099-01-01T00:00:01+00:00"
    else:
        route = next(o for o in observations if o["name"] == "route" and o["type"] == "SPAN")
        generation.update(parent_observation_id=route["id"], prompt_name="sojafit/route",
                          start_time=route["start_time"], end_time=route["end_time"])
    with pytest.raises(ValueError):
        validate_timeline(observations, prompts, 3, case_kind="rating")


def test_load_existing_versions_rejects_unpublished_local_skill(monkeypatch, tmp_path):
    import hashlib
    for node in managed.NODES:
        folder = tmp_path / "backend/prompts"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{node}.md").write_text("base")
    folder = tmp_path / "backend/mcp_skill/skills"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("local draft")
    monkeypatch.setattr(managed, "ROOT", tmp_path)
    class ExistingPrompt:
        config = managed.CONFIG
        def compile(self, **values):
            return [{"role": "system", "content": "base"}, {"role": "user", "content": values["input"]}]
    old_skill = SimpleNamespace(prompt="published version", config={"sha256": hashlib.sha256(b"published version").hexdigest()})
    client = SimpleNamespace(get_prompt=lambda name, **kwargs: old_skill if name == managed.SKILL_NAME else ExistingPrompt())
    with pytest.raises(ValueError, match="Skill 불일치"):
        managed.load_development(client)
