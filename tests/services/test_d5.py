import asyncio
from langgraph.checkpoint.memory import InMemorySaver
from backend.multi_agent.agents.judge import JudgeRead
from backend.multi_agent.contracts import Plan, Task
from backend.multi_agent.supervisor import Facts


def test_d5_interrupt_resume_preserves_checkpoint_and_read_once():
    from backend.services.d5 import D5Service, RunInput
    calls = []
    plan = Plan(question_type='candidate_judge', next='tasks', tasks=[Task(id=1, agent='judge', kind='candidate_judge', goal='judge')])
    def chat(node, system, user, schema):
        calls.append(node)
        return plan if node == 'supervisor' else JudgeRead(role='R02', candidates=['1N5819'])
    service = D5Service(chat=chat, retriever=lambda *a, **k: [], lookup=lambda _: Facts(),
                        specs=lambda *a, **k: [], find=lambda *a, **k: [], checkpointer=InMemorySaver())
    async def run():
        data = RunInput(question='D1을 바꿔도 돼?', target_ref='D1',
                        connections={'parts': [{'ref':'D1', 'value':'1N5819', 'footprint':'SOD-123'}], 'nets': []})
        start = [e async for e in service.start('thread-1', data)]
        assert start[0].type == 'status' and start[-1].type == 'requires_input'
        resume = [e async for e in service.resume('thread-1', {})]
        assert resume[0].type == 'status' and resume[-1].type in ('completed', 'refused')
    asyncio.run(run())
    assert calls.count('judge_read') == 1


def test_run_input_rejects_unrelated_fields():
    import pytest
    from pydantic import ValidationError
    from backend.services.d5 import RunInput
    with pytest.raises(ValidationError):
        RunInput(question='hi', target_ref='D1', connections={}, product_url='x')


def test_resume_uses_command_and_same_graph_thread():
    from langgraph.types import Command
    from backend.services.d5 import D5Service, RunInput
    class Graph:
        calls = []
        async def astream(self, value, config, stream_mode):
            self.calls.append((value, config))
            if False:
                yield None
        async def aget_state(self, config):
            from types import SimpleNamespace
            return SimpleNamespace(values={'answer': 'ok'})
    service = D5Service(chat=None, retriever=None, lookup=None, specs=lambda: None, find=lambda: None, checkpointer=InMemorySaver())
    service.graph = Graph()
    async def run():
        data = RunInput(question='hello', target_ref='D1', connections={'components': [{'ref': 'D1'}], 'nets': []})
        await collect(service.start('stable', data))
        await collect(service.resume('stable', {'voltage': '5 V'}, role='R02'))
    async def collect(items): return [x async for x in items]
    asyncio.run(run())
    first, second = service.graph.calls
    assert first[1]['configurable']['thread_id'] == second[1]['configurable']['thread_id'] == 'stable'
    assert isinstance(second[0], Command) and second[0].resume == {'answers': {'voltage': '5 V'}, 'role': 'R02'}
    assert first[0]['target_part']['ref'] == 'D1'
    assert 'connections' not in first[0]


def test_failure_event_never_exposes_exception_text():
    from backend.services.d5 import D5Service, RunInput
    class Graph:
        async def astream(self, *args, **kwargs):
            raise RuntimeError('private exception marker')
            yield
    service = D5Service(chat=None, retriever=None, lookup=None, specs=lambda: None, find=lambda: None, checkpointer=InMemorySaver())
    service.graph = Graph()
    async def run():
        data = RunInput(question='hello', target_ref='', connections={'parts': [], 'nets': []})
        return [e async for e in service.start('t', data)]
    events = asyncio.run(run())
    assert events[-1].type == 'failed'
    assert 'private exception marker' not in str(events)


def test_terminal_public_result_preserves_safe_graph_fields_only():
    from backend.services.d5 import public_state
    result = public_state({'answer': 'ok', 'question_type': 'candidate_judge', 'price_parts': ['1N5819', 'https://private'], 'facts': {'x': 'secret'}, 'reports': [{'secret': 1}]})
    assert result == {'answer': 'ok', 'question_type': 'candidate_judge', 'price_parts': ['1N5819']}


def test_docs_evidence_selects_only_cited_metadata():
    from backend.services.d5 import public_state
    result = public_state({'answer': 'ok [3]', 'final_reports': [{'evidence_ids': ['3'], 'summary': 'secret summary'}],
                           'docs': [{'chunk_id': 3, 'file': '/private/sheet.pdf', 'page': 2, 'table': 'T', 'content': 'private chunk', 'doc_parts': ['private']},
                                    {'chunk_id': 4, 'file': 'unused.pdf', 'page': 3, 'content': 'other private'}]})
    assert result['evidence'] == [{'document': 'sheet.pdf', 'page': 2, 'table': 'T', 'row': '', 'section': '', 'citation_number': '3'}]
    assert 'private' not in str(result) and 'unused' not in str(result)
