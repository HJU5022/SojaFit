"""단계별 시간 기록기(evals/runners/stage_timing.py)와 집계(scripts/eval/stage_report.py)가 값을 바르게 모으는지 확인한다.

- 역할: 단계·비용 기록과 p50 · p95 정의를 확인하고, run_gate가 문항 trace별로 점수·실제 호출 수·실행 조건을 연결하며 전송 장애에도 원래 결과를 보존하는지 본다.
- 하지 않는 일: 모델 · Voyage · DB 호출(가짜 모델과 가짜 함수만 쓴다).
"""
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from langgraph.graph import END, START, StateGraph

from evals.runners import stage_timing
from scripts.eval import stage_report


def test_gate_attaches_scores_to_each_trace_and_counts_recorded_calls(tmp_path, monkeypatch):
    """점수 전송 누락·호출 수 0·오류를 성공으로 채점하는 회귀를 실제 main 경로에서 잡는다."""
    import json
    import langfuse
    from evals.runners import run_gate

    class Client:
        def __init__(self): self.scores, self.flushed, self.count = [], False, 0
        def create_trace_id(self):
            self.count += 1
            return str(self.count) * 32
        def create_score(self, **score): self.scores.append(score)
        def get_trace_url(self, trace_id): return f'https://example.invalid/{trace_id}'
        def flush(self): self.flushed = True

    client, configs = Client(), []
    monkeypatch.setattr(langfuse, 'get_client', lambda: client)
    monkeypatch.setattr(run_gate, 'callback', lambda **kw: None)
    monkeypatch.setattr(run_gate, 'make_app', lambda *args: (object(), lambda: None))

    def invoke(app, inputs, config):
        configs.append(config)
        rec = config['callbacks'][-1]
        rec.llm_calls.append({'node': 'Supervisor', 'cost_usd': 0.002, 'ok': True})
        if inputs['input'] == '합성 오류':
            raise TimeoutError('합성 오류')
        return {'path': ['Supervisor', '거절'], 'question_type': 'out_of_scope', 'answer': 'SojaFit 범위 밖입니다.'}

    monkeypatch.setattr(run_gate, 'invoke_with_resume', invoke)
    data = tmp_path / 'synthetic.jsonl'
    data.write_text('\n'.join(json.dumps({'id': f'i{i}', 'kind': 'irrelevant', 'irrelevant_type': 'out_of_domain',
        'input': text, 'expected': '', 'gold_chunks': []}) for i, text in enumerate(['합성 질문', '합성 오류'], 1)))
    out = tmp_path / 'out'
    assert run_gate.main(str(data), str(out), sets=1, keep_going=True) == 0
    rows = json.loads((out / 'set1.json').read_text())['rows']
    scores = {(s['trace_id'], s['name']): s for s in client.scores}
    assert scores[('1' * 32, 'answer_metric')]['value'] == 'correct_refusal'
    assert scores[('1' * 32, 'llm_calls')]['value'] == 1.0
    assert scores[('1' * 32, 'cost_usd')]['value'] == 0.002
    assert scores[('1' * 32, 'pass')]['value'] == 1.0
    assert scores[('1' * 32, 'pass')]['data_type'] == 'BOOLEAN'
    assert scores[('2' * 32, 'pass')]['value'] == 0.0
    assert ('2' * 32, 'answer_metric') not in scores
    assert rows[1]['trace_url'].endswith('2' * 32)
    assert rows[0]['score_delivery'] == 'queued' and rows[1]['score_delivery'] == 'queued'
    assert client.flushed
    assert {'provider', 'node_models', 'dataset', 'git', 'prompts'} <= configs[0]['metadata'].keys()


def test_gate_score_failure_does_not_erase_result_or_invent_missing_cost(tmp_path, monkeypatch):
    """추적 장애가 평가 실패로 바뀌지 않고, 미보고 비용을 0으로 만들지 않는다."""
    import json
    import langfuse
    from evals.runners import run_gate

    class Client:
        def create_trace_id(self): return 'a' * 32
        def create_score(self, **score): raise RuntimeError('PRIVATE_ERROR')
        def get_trace_url(self, trace_id): return f'https://example.invalid/{trace_id}'
        def flush(self): pass

    monkeypatch.setattr(langfuse, 'get_client', lambda: Client())
    monkeypatch.setattr(run_gate, 'callback', lambda **kw: None)
    monkeypatch.setattr(run_gate, 'make_app', lambda *args: (object(), lambda: None))
    monkeypatch.setattr(run_gate, 'invoke_with_resume', lambda *args: {'path': ['거절'], 'question_type': 'out_of_scope', 'answer': 'SojaFit 범위 밖입니다.'})
    data = tmp_path / 'synthetic.jsonl'
    data.write_text(json.dumps({'id': 'i1', 'kind': 'irrelevant', 'irrelevant_type': 'out_of_domain', 'input': '합성 질문', 'expected': '', 'gold_chunks': []}))
    out = tmp_path / 'out'
    assert run_gate.main(str(data), str(out), sets=1, keep_going=True) == 0
    row = json.loads((out / 'set1.json').read_text())['rows'][0]
    assert row['pass'] is True and 'error' not in row
    assert row['score_delivery'] == 'failed' and row['cost_usd'] is None
    assert 'PRIVATE_ERROR' not in (out / 'set1.json').read_text()


def test_recorder_names_node_and_keeps_reported_cost_and_report_has_no_stale_rows():
    rec = stage_timing.StageRecorder()
    model = FakeListChatModel(responses=['ok'])
    graph = StateGraph(dict)
    graph.add_node('답 쓰기', lambda state: {'out': model.invoke('질문').content})
    graph.add_edge(START, '답 쓰기')
    graph.add_edge('답 쓰기', END)
    assert graph.compile().invoke({}, {'callbacks': [rec]})['out'] == 'ok'
    assert [c['node'] for c in rec.llm_calls] == ['답 쓰기']
    assert [s['stage'] for s in rec.report()] == ['답 쓰기']  # 예전 report()는 plan · judge_read 같은 0ms 건너뜀 행을 붙였다


def test_on_llm_end_reads_tokens_cost_and_cached_tokens():
    rec = stage_timing.StageRecorder()
    rec.on_chat_model_start({}, [[]], run_id='r', metadata={'langgraph_node': 'Supervisor', 'ls_model_name': 'm'})
    message = AIMessage(content='x', usage_metadata={'input_tokens': 100, 'output_tokens': 7, 'total_tokens': 107})
    usage = {'cost': 0.001, 'prompt_tokens_details': {'cached_tokens': 60}}
    rec.on_llm_end(LLMResult(generations=[[ChatGeneration(message=message)]], llm_output={'token_usage': usage, 'model_name': 'anthropic/x'}), run_id='r')
    (call,) = rec.llm_calls
    assert (call['node'], call['model'], call['input_tokens'], call['output_tokens'], call['cached_tokens'], call['cost_usd']) == \
        ('Supervisor', 'anthropic/x', 100, 7, 60, 0.001)
    rec.on_chat_model_start({}, [[]], run_id='e', metadata={'langgraph_node': '회로 읽기'})
    rec.on_llm_error(RuntimeError('x'), run_id='e')
    assert rec.llm_calls[1]['ok'] is False and rec.llm_calls[1]['cost_usd'] is None


def test_voyage_timing_collects_kind_seconds_tokens_and_restores(monkeypatch):
    from backend.services import llm
    monkeypatch.setattr(llm, '_voyage_post', lambda path, payload: {'usage': {'total_tokens': 9}, 'data': []})
    original = llm._voyage_post
    stage_timing.drain_voyage()
    with stage_timing.voyage_timing():
        llm._voyage_post('embeddings', {})
        llm._voyage_post('rerank', {})
    assert llm._voyage_post is original
    kinds = [(v['kind'], v['tokens']) for v in stage_timing.drain_voyage()]
    assert kinds == [('embed', 9), ('rerank', 9)] and stage_timing.drain_voyage() == []


def test_stage_report_definitions_and_cost():
    assert stage_report.median([1, 2, 3, 4]) == 2.5 and stage_report.p95(list(range(1, 51))) == 48  # 실행기 p50은 sorted[n//2] = 3
    row = lambda i, cost: {'id': i, 'latency_s': float(i), 'pass': True, 'stages': [{'stage': 'search', 'status': 'ok', 'elapsed_ms': 1000}],  # noqa: E731
                           'llm_call_log': [{'node': 'Supervisor', 'model': 'm', 'seconds': 1.0, 'input_tokens': 10, 'output_tokens': 1, 'cached_tokens': 0, 'cost_usd': cost}],
                           'voyage': [{'kind': 'embed', 'seconds': 0.25, 'tokens': 5}, {'kind': 'rerank', 'seconds': 0.5, 'tokens': 1_000_000}]}
    s = stage_report.summarize([row(1, 0.001), row(2, 0.003), row(3, None), row(4, 0.002)])
    assert s['latency_s']['p50'] == 2.5 and s['latency_s']['runner_p50_s'] == 3.0
    assert s['search_s']['db_bm25_rrf'] == {'n': 4, 'p50': 0.25, 'p95': 0.25}
    assert s['cost_usd']['llm_total'] == 0.006 and s['cost_usd']['llm_calls_without_reported_cost'] == 1
    assert s['cost_usd']['rerank_total'] == 0.2 and s['llm_by_node']['Supervisor']['calls'] == 4
    assert 'Supervisor' in stage_report.markdown(s)


def test_merge_rows_lets_a_later_file_replace_failed_rows():
    first = [{'id': 'a', 'error': 'x'}, {'id': 'b'}]
    rows, replaced = stage_report.merge_rows([first, [{'id': 'a', 'latency_s': 1.0}]])
    assert rows == [{'id': 'a', 'latency_s': 1.0}, {'id': 'b'}] and replaced == ['a']
