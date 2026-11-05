"""Langfuse 프롬프트 등록·고정 버전 검증·선택적 노드 추적.

역할: 로컬 소스(backend/prompts/*.md, backend/mcp_skill/skills/SKILL.md)를 `development` 라벨로 등록하고, 로컬과 원격이
한 글자라도 다르면 LLM 호출 전에 ValueError로 멈춘다. `session()`을 명시적으로 켠 구간에서만 추적하고, 꺼져 있으면 no-op이거나 빈 값이다.
호출자: backend/services/llm.py(`node_chat`·`_openrouter_call`), scripts/langfuse/langfuse_skill_check.py(등록·검증), evals/*, tests/services/test_langfuse_prompts.py.
입력: Langfuse client(langfuse.get_client()). 읽는 환경변수는 없다(키는 langfuse SDK가 LANGFUSE_* 에서 읽는다).
하지 않는 일: LLM 호출 자체(llm.py), production 라벨 변경, 프롬프트 원문 관리(backend/prompts/).
출처: SPEC.md 5절 "Langfuse 프롬프트와 실행 추적"·"도메인 Skill 적용", backend/services/SERVICES.md.
"""
from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# [왜] 등록한 프롬프트의 config와 실제 호출 설정이 어긋나면 안 되므로 모델·temperature·출력 상한을 여기 한 곳에 고정한다(SPEC 5절)
HAIKU, LUNA, SONNET = "anthropic/claude-haiku-5.5", "openai/gpt-6-luna", "anthropic/claude-sonnet-5.5"
CONFIG = {"model": HAIKU, "temperature": 0, "max_tokens": 4096}
NODES = ("route", "grade", "rewrite", "generate", "supervisor")  # [왜] supervisor는 멀티 에이전트(D5)의 판단 노드, 영어 프롬프트(11-05)
# [왜] 노드마다 쓸 모델을 한 표에 둔다. 같은 모델을 적으면 같고 다른 모델을 적으면 다르다. 아래는 시작값이며 최종 결정이 아니다(11-05, 측정 뒤 ADR로 정한다)
# [왜] Supervisor는 Sonnet, 그 아래 서브에이전트가 쓰는 노드는 Haiku, 채점은 Luna(11-05 정운 결정)
NODE_MODELS = {"route": HAIKU, "grade": LUNA, "rewrite": HAIKU, "generate": HAIKU, "supervisor": SONNET}
SKILL_NAME = "skill-diode-evidence"  # [왜] 폴더(슬래시) 없이 이름 한 줄로 둔다. 프로젝트가 SojaFit 하나라 접두사가 필요 없다(11-05)
# [왜] contextvar라 세션·노드 호출 상태가 동시 실행(스레드·async) 사이에 섞이지 않는다
_session = ContextVar("langfuse_prompt_session", default=None)
_invocation = ContextVar("langfuse_invocation", default=None)


def callback():
    """노드 호출 하나를 추적하는 Langfuse LangChain CallbackHandler를 새로 만든다."""
    from langfuse.langchain import CallbackHandler
    return CallbackHandler()


def node_config(node):
    """노드가 쓰는 모델의 등록 설정. Luna에만 temperature를 보내지 않고(3차 실측 계약), 나머지는 CONFIG에 모델만 바꾼다."""
    model = NODE_MODELS[node]
    return {"model": model, "max_tokens": CONFIG["max_tokens"]} if model == LUNA else {**CONFIG, "model": model}


def publish(client, name, body, *, kind, config):
    """프롬프트를 `development` 라벨로 등록한다(본문·설정이 같으면 새 버전을 만들지 않고 기존 객체를 돌려준다)."""
    # body는 chat이면 메시지 목록, text이면 문자열이고 kind는 "chat" | "text"다
    matches = [p for p in client.api.prompts.list(name=name, limit=100).data if p.name == name]
    if matches and "development" in matches[0].labels:
        existing = client.get_prompt(name, label="development", type=kind, cache_ttl_seconds=0)
        # [왜] 서버가 메시지에 붙이는 type="message"만 빼고 비교해 내용이 같은데 새 버전이 쌓이는 일을 막는다
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
    """노드(NODES)를 backend/prompts/<node>.md에서 읽어 등록하고 {노드: 프롬프트}를 돌려준다."""
    prompts = {}
    for node in NODES:
        system = (ROOT / "backend/prompts" / f"{node}.md").read_text(encoding="utf-8")
        if node == "generate":
            # [왜] generate만 선택 Skill이 붙을 자리({{domain_skill}})를 시스템 프롬프트 끝에 둔다
            system += "{{domain_skill}}"
        body = [{"role": "system", "content": system}, {"role": "user", "content": "{{input}}"}]
        prompts[node] = publish(client, node, body, kind="chat", config=node_config(node))
    return prompts


def publish_skill(client):
    """Skill 본문(SKILL.md)을 sha256과 함께 text 프롬프트로 등록한다."""
    raw = (ROOT / "backend/mcp_skill/skills/SKILL.md").read_bytes()
    return publish(client, SKILL_NAME, raw.decode("utf-8"), kind="text",
                   config={"scope": ["S1", "S2"], "sha256": hashlib.sha256(raw).hexdigest()})


def load_development(client):
    """등록된 development 버전을 읽어 (프롬프트 딕셔너리, Skill)을 돌려준다(로컬과 다르면 ValueError)."""
    # [주의] cache_ttl_seconds=0으로 캐시 없이 원격의 현재 버전을 읽는다. 다르면 LLM·trace 생성 전에 중단한다
    prompts = {node: client.get_prompt(node, label="development", type="chat", cache_ttl_seconds=0)
               for node in NODES}
    for node, prompt in prompts.items():
        system = (ROOT / "backend/prompts" / f"{node}.md").read_text(encoding="utf-8")
        expected = [{"role": "system", "content": system}, {"role": "user", "content": "preflight"}]
        if prompt.config != node_config(node) or prompt.compile(input="preflight", domain_skill="") != expected:
            raise ValueError("로컬/원격 프롬프트 불일치")
    skill = client.get_prompt(SKILL_NAME, label="development", type="text", cache_ttl_seconds=0)
    raw = (ROOT / "backend/mcp_skill/skills/SKILL.md").read_bytes()
    if skill.prompt != raw.decode("utf-8") or skill.config.get("sha256") != hashlib.sha256(raw).hexdigest():
        raise ValueError("로컬/원격 Skill 불일치: 검토된 본문을 명시적으로 등록해야 합니다")
    return prompts, skill


@contextmanager
def session(client, prompts, skill):
    """이 구간에서만 Langfuse 추적을 켠다(prompts·skill은 load_development의 반환값)."""
    token = _session.set((client, prompts, skill))
    try:
        yield
    finally:
        _session.reset(token)


def invocation_config():
    """진행 중인 노드 호출의 LangChain config를 돌려준다(호출 중이 아니면 None)."""
    active = _invocation.get()
    return active[0] if active else None


def is_active():
    """`session()` 안이면 True."""
    return _session.get() is not None


def model_options():
    """노드 호출 중이면 등록된 max_tokens와 45초 timeout을 담은 dict, 아니면 빈 dict를 돌려준다."""
    # [왜] 호출마다 새 dict를 만들어, 호출하는 쪽이 값을 덮어써도 다음 호출에 영향이 없다
    active = _invocation.get()
    return {"max_tokens": active[1]["max_tokens"], "timeout": 45} if active else {}


def bind_prompt(runnable, options):
    """`managed_prompt` 단계를 LLM 앞에 붙여 프롬프트 버전을 generation에 연결한다(노드 호출 중이 아니면 runnable 그대로)."""
    config = invocation_config()
    if config is None:
        return runnable
    # [왜] 메시지는 그대로 통과시키고 metadata의 langfuse_prompt만 LLM보다 먼저 callback에 등록해, generation이 프롬프트 버전과 이어지게 한다
    from langchain_core.runnables import RunnableLambda
    render = RunnableLambda(lambda messages: messages).with_config(
        run_name="managed_prompt", metadata={"langfuse_prompt": config["metadata"]["langfuse_prompt"]})
    return render | runnable.bind(**options)


def step(name, *, metadata=None):
    """세션 안이면 이름 붙은 span 컨텍스트를, 아니면 빈 컨텍스트(nullcontext)를 돌려준다."""
    active = _session.get()
    return active[0].start_as_current_observation(name=name, as_type="span", metadata=metadata) if active else nullcontext()


@contextmanager
def prompt_scope(node, system, user, *, skill_text=""):
    """노드 호출 하나를 검증하고 추적 범위를 열어 Langfuse span(세션이 없으면 None)을 내놓는다.

    Langfuse에서 컴파일한 메시지가 로컬 system·user와 다르거나 Skill 본문·모델 설정이 다르면 ValueError.
    """
    active = _session.get()
    if active is None:
        yield None
        return
    client, prompts, skill = active
    prompt = prompts[node]
    if prompt.config != node_config(node):
        raise ValueError("Langfuse 모델 설정 불일치")
    if skill_text and (skill is None or skill.prompt != skill_text):
        raise ValueError("Langfuse Skill 본문 불일치")
    suffix = f"\n\n<domain_skill>\n{skill_text}\n</domain_skill>" if skill_text else ""
    # [주의] 원격 템플릿을 컴파일한 결과가 실제로 보낼 로컬 메시지와 한 글자라도 다르면 추적이 거짓이 되므로 멈춘다
    compiled = prompt.compile(input=user, domain_skill=suffix)
    if compiled != [{"role": "system", "content": system}, {"role": "user", "content": user}]:
        raise ValueError("Langfuse와 로컬 프롬프트 불일치")
    metadata = {"prompt_name": prompt.name, "prompt_version": prompt.version,
                "skill_applied": bool(skill_text),
                "skill_version": skill.version if skill_text else None,
                "skill_sha256": hashlib.sha256(skill_text.encode()).hexdigest() if skill_text else None}
    # None 값(Skill 미적용 시 버전·해시)은 메타데이터에서 뺀다
    metadata = {key: value for key, value in metadata.items() if value is not None}
    config = {"callbacks": [callback()], "metadata": {"langfuse_prompt": prompt, **metadata}}
    token = _invocation.set((config, prompt.config))
    try:
        with client.start_as_current_observation(name=node, as_type="span", metadata=metadata) as span:
            yield span
    finally:
        _invocation.reset(token)
