"""서비스 분석 추적(service_trace): 모델 호출 메타는 나가고 질문·답·검색 값·내 설정 본문은 어떤 칸에도 남지 않는다."""
from types import MappingProxyType
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from backend.services import service_trace as trace

SECRETS = ('PRIVATE_QUESTION_D1', 'PRIVATE_ANSWER_TEXT', 'NETLIST_R1_4k7', 'MY_SETTING_PROFILE')


def leaks(spans):
    """내보낸 모든 span의 이름·속성·상태 설명·이벤트에서 비밀 문자열이 보이는 칸."""
    found = []
    for span in spans:
        values = {'name': span.name, 'status': span.status.description, **dict(span.attributes)}
        values.update({f'event:{e.name}': str(dict(e.attributes)) for e in span.events})
        found += [key for key, value in values.items() if any(secret in str(value) for secret in SECRETS)]
    return found


class State(TypedDict, total=False):
    question: str
    answer: str


class Chat(FakeListChatModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        result = super()._generate(messages, stop, run_manager, **kwargs)
        message = result.generations[0].message
        result.generations[0].message = AIMessage(content=message.content, usage_metadata={'input_tokens': 11, 'output_tokens': 7, 'total_tokens': 18},
                                                  response_metadata={'model_name': 'anthropic/claude-haiku-5.5'})
        return result


def build_graph(fail=False):
    model = Chat(responses=['PRIVATE_ANSWER_TEXT for NETLIST_R1_4k7'], metadata={'ls_model_name': 'anthropic/claude-haiku-5.5'})

    def generate(state):
        if fail:
            raise ValueError('bad output: PRIVATE_ANSWER_TEXT')
        return {'answer': model.invoke(f"{state['question']} MY_SETTING_PROFILE").content}

    graph = StateGraph(State)
    graph.add_node('generate', generate)
    graph.add_edge(START, 'generate')
    graph.add_edge('generate', END)
    return graph.compile()


@pytest.fixture
def exported(monkeypatch):
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    exporter = InMemorySpanExporter()
    key = f'pk-lf-service-trace-{uuid4().hex}'  # [주의] 같은 키는 이전 client(이전 내보내기 객체)를 재사용하므로 시험마다 새 키
    monkeypatch.setenv('LANGFUSE_PUBLIC_KEY', key)
    monkeypatch.setenv('LANGFUSE_SECRET_KEY', 'sk-lf-service-trace-test')
    monkeypatch.setattr(trace, '_ready', False)
    assert trace.ensure_client(base_url='https://example.invalid', span_exporter=exporter)
    from langfuse import get_client
    client = get_client(public_key=key)
    yield exporter, client
    client.shutdown()


def run(exporter, client, fail=False):
    handlers, metadata = trace.callbacks('a' * 32, 'thread-uuid-1', 'service')
    try:
        build_graph(fail).invoke({'question': 'PRIVATE_QUESTION_D1'}, {'callbacks': handlers, 'metadata': metadata})
    except ValueError:
        pass
    client.flush()
    return exporter.get_finished_spans()


def test_model_call_meta_goes_out_and_bodies_do_not(exported):
    spans = run(*exported)
    assert spans and leaks(spans) == []
    attributes = [dict(s.attributes) for s in spans]
    generation = [a for a in attributes if a.get('langfuse.observation.type') == 'generation']
    assert len(generation) == 1 and generation[0]['langfuse.observation.model.name'] == 'anthropic/claude-haiku-5.5'
    assert '"input": 11' in generation[0]['langfuse.observation.usage_details']
    assert generation[0]['langfuse.observation.input'] == trace.PLACEHOLDER and generation[0]['langfuse.observation.output'] == trace.PLACEHOLDER
    assert {s.name for s in spans} >= {'generate'}  # 노드 이름은 남는다


def test_all_model_call_spans_share_the_given_trace_and_session(exported):
    spans = run(*exported)
    assert {format(s.context.trace_id, '032x') for s in spans} == {'a' * 32}
    assert {dict(s.attributes).get('session.id') for s in spans} >= {'thread-uuid-1'}


def test_error_text_is_not_exported_but_error_level_is(exported):
    spans = run(*exported, fail=True)
    assert leaks(spans) == []
    assert any(dict(s.attributes).get('langfuse.observation.level') == 'ERROR' for s in spans)


def test_hook_removes_unknown_and_body_attributes_and_keeps_meta():
    from langfuse.types import MaskOtelSpansParams, OtelSpanData, OtelSpanIdentifier
    attributes = {'langfuse.observation.input': 'PRIVATE_QUESTION_D1', 'langfuse.observation.output': 'PRIVATE_ANSWER_TEXT',
                  'langfuse.observation.metadata.q': 'NETLIST_R1_4k7', 'langfuse.observation.status_message': 'MY_SETTING_PROFILE',
                  'langfuse.observation.model.parameters': 'MY_SETTING_PROFILE', 'gen_ai.prompt.0.content': 'PRIVATE_QUESTION_D1',
                  'langfuse.observation.model.name': 'm', 'langfuse.observation.usage_details': '{"input": 1}',
                  'langfuse.observation.cost_details': '{"total": 0.1}', 'langfuse.observation.level': 'ERROR'}
    ident = OtelSpanIdentifier(trace_id='a' * 32, span_id='b' * 16)
    span = OtelSpanData(trace_id='a' * 32, span_id='b' * 16, parent_span_id=None, name='x', instrumentation_scope_name='langfuse',
                        instrumentation_scope_version=None, attributes=MappingProxyType(attributes), resource_attributes=MappingProxyType({}))
    patch = trace.mask_otel_spans(params=MaskOtelSpansParams(spans={ident: span})).span_patches[ident]
    result = {k: v for k, v in attributes.items() if k not in patch.delete_attributes} | dict(patch.set_attributes)
    assert not any(secret in str(v) for v in result.values() for secret in SECRETS)
    assert result['langfuse.observation.input'] == trace.PLACEHOLDER
    assert {'langfuse.observation.model.name', 'langfuse.observation.usage_details', 'langfuse.observation.cost_details',
            'langfuse.observation.level'} <= set(result)


def test_no_keys_means_no_handler(monkeypatch):
    monkeypatch.delenv('LANGFUSE_PUBLIC_KEY', raising=False)
    assert trace.callbacks('a' * 32, 't', 'service') == ([], {})


def test_handler_failure_is_swallowed(monkeypatch):
    monkeypatch.setenv('LANGFUSE_PUBLIC_KEY', 'pk')
    monkeypatch.setenv('LANGFUSE_SECRET_KEY', 'sk')
    monkeypatch.setattr(trace, 'ensure_client', lambda: (_ for _ in ()).throw(RuntimeError('sk-secret')))
    assert trace.callbacks('a' * 32, 't', 'service') == ([], {})
