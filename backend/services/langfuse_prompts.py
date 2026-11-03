"""Langfuse 프롬프트 등록·고정 버전 컴파일·선택적 노드 추적. LLM 호출은 llm.py에 둔다."""
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = {"model": "anthropic/claude-haiku-5.5", "temperature": 0, "max_tokens": 4096}
NODES = ("route", "grade", "rewrite", "generate")
SKILL_NAME = "sojafit/skills/diode-evidence"
_session = ContextVar("langfuse_prompt_session", default=None)
_invocation = ContextVar("langfuse_invocation", default=None)


def callback():
    from langfuse.langchain import CallbackHandler
    return CallbackHandler()


def publish(client, name, body, *, kind, config):
    matches = [p for p in client.api.prompts.list(name=name, limit=100).data if p.name == name]
    if matches and "development" in matches[0].labels:
        existing = client.get_prompt(name, label="development", type=kind, cache_ttl_seconds=0)
        def comparable(value):
            if kind != "chat":
                return value
            return [{key: val for key, val in message.items() if key != "type" or val != "message"} for message in value]

        if comparable(existing.prompt) == comparable(body) and existing.config == config:
            return existing
    return client.create_prompt(name=name, prompt=body, type=kind, config=config,
                                labels=["development"], tags=["sojafit"],
                                commit_message="도메인 근거 해석 입력 계약")


def publish_nodes(client):
    prompts = {}
    for node in NODES:
        system = (ROOT / "backend/prompts" / f"{node}.md").read_text(encoding="utf-8")
        if node == "generate":
            system += "{{domain_skill}}"
        body = [{"role": "system", "content": system}, {"role": "user", "content": "{{input}}"}]
        prompts[node] = publish(client, f"sojafit/{node}", body, kind="chat", config=CONFIG)
    return prompts


def publish_skill(client):
    raw = (ROOT / "backend/mcp_skill/skills/SKILL.md").read_bytes()
    return publish(client, SKILL_NAME, raw.decode("utf-8"), kind="text",
                   config={"scope": ["S1", "S2"], "sha256": hashlib.sha256(raw).hexdigest()})


def load_development(client):
    """등록된 버전만 읽고 로컬 소스와 다르면 LLM/trace 생성 전에 중단한다."""
    prompts = {node: client.get_prompt(f"sojafit/{node}", label="development", type="chat", cache_ttl_seconds=0)
               for node in NODES}
    for node, prompt in prompts.items():
        system = (ROOT / "backend/prompts" / f"{node}.md").read_text(encoding="utf-8")
        expected = [{"role": "system", "content": system}, {"role": "user", "content": "preflight"}]
        if prompt.config != CONFIG or prompt.compile(input="preflight", domain_skill="") != expected:
            raise ValueError("로컬/원격 프롬프트 불일치")
    skill = client.get_prompt(SKILL_NAME, label="development", type="text", cache_ttl_seconds=0)
    raw = (ROOT / "backend/mcp_skill/skills/SKILL.md").read_bytes()
    if skill.prompt != raw.decode("utf-8") or skill.config.get("sha256") != hashlib.sha256(raw).hexdigest():
        raise ValueError("로컬/원격 Skill 불일치: 검토된 본문을 명시적으로 등록해야 합니다")
    return prompts, skill


@contextmanager
def session(client, prompts, skill):
    token = _session.set((client, prompts, skill))
    try:
        yield
    finally:
        _session.reset(token)


def invocation_config():
    active = _invocation.get()
    return active[0] if active else None


def is_active():
    return _session.get() is not None


def model_options():
    active = _invocation.get()
    return {"max_tokens": active[1]["max_tokens"], "timeout": 45} if active else {}


def bind_prompt(runnable, options):
    config = invocation_config()
    if config is None:
        return runnable
    # 컴파일된 메시지를 그대로 넘기되 LLM보다 먼저 프롬프트 버전을 callback에 등록한다.
    from langchain_core.runnables import RunnableLambda
    render = RunnableLambda(lambda messages: messages).with_config(
        run_name="managed_prompt", metadata={"langfuse_prompt": config["metadata"]["langfuse_prompt"]})
    return render | runnable.bind(**options)


def step(name, *, metadata=None):
    active = _session.get()
    return active[0].start_as_current_observation(name=name, as_type="span", metadata=metadata) if active else nullcontext()


@contextmanager
def prompt_scope(node, system, user, *, skill_text=""):
    active = _session.get()
    if active is None:
        yield None
        return
    client, prompts, skill = active
    prompt = prompts[node]
    if prompt.config != CONFIG:
        raise ValueError("Langfuse 모델 설정 불일치")
    if skill_text and (skill is None or skill.prompt != skill_text):
        raise ValueError("Langfuse Skill 본문 불일치")
    suffix = f"\n\n<domain_skill>\n{skill_text}\n</domain_skill>" if skill_text else ""
    compiled = prompt.compile(input=user, domain_skill=suffix)
    if compiled != [{"role": "system", "content": system}, {"role": "user", "content": user}]:
        raise ValueError("Langfuse와 로컬 프롬프트 불일치")
    metadata = {"prompt_name": prompt.name, "prompt_version": prompt.version,
                "skill_applied": bool(skill_text),
                "skill_version": skill.version if skill_text else None,
                "skill_sha256": hashlib.sha256(skill_text.encode()).hexdigest() if skill_text else None}
    metadata = {key: value for key, value in metadata.items() if value is not None}
    config = {"callbacks": [callback()], "metadata": {"langfuse_prompt": prompt, **metadata}}
    token = _invocation.set((config, prompt.config))
    try:
        with client.start_as_current_observation(name=node, as_type="span", metadata=metadata) as span:
            yield span
    finally:
        _invocation.reset(token)
