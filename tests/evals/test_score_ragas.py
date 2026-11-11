"""RAGAS Score 추출: 근거 모으기·질문 줄 고르기·비활성/재료 부족 시 빈 결과(API·DB 없이)."""
import pandas as pd

from evals.runners import score_ragas as S


def test_contexts_from_docs_and_judgement_citations():
    state = {
        'docs': [{'content': 'chunk A VRRM 1000V'}],
        'reports': [{
            'docs': [{'content': 'chunk B IF 1A'}],
            'judgement': {
                'role_evidence': ['D1 cathode toward load'],
                'results': [{'conditions': [{'citation': '1N4001G SERIES p1 VRRM 1000V'}]}],
            },
        }],
    }
    ctx = S.contexts_from_state(state)
    assert ctx[0] == 'chunk A VRRM 1000V'
    assert 'chunk B IF 1A' in ctx
    assert 'D1 cathode toward load' in ctx
    assert '1N4001G SERIES p1 VRRM 1000V' in ctx


def test_question_text_prefers_질문_line():
    item = {'input': '회로: x\n질문: 바꿔도 될까?\n'}
    assert S.question_text(item, {}) == '바꿔도 될까?'


def test_score_ragas_disabled(monkeypatch):
    monkeypatch.setenv('RAGAS_ENABLED', '0')
    assert S.score_ragas({'input': '질문: a'}, {'answer': 'b', 'docs': [{'content': 'c'}]}) == {}


def test_score_ragas_skips_without_contexts(monkeypatch):
    monkeypatch.setenv('RAGAS_ENABLED', '1')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'sk-test')
    assert S.score_ragas({'input': '질문: a'}, {'answer': 'b', 'docs': []}) == {}


def test_score_ragas_returns_langfuse_tuples(monkeypatch):
    monkeypatch.setenv('RAGAS_ENABLED', '1')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'sk-test')

    class FakeResult:
        def to_pandas(self):
            return pd.DataFrame([{
                'faithfulness': 0.8,
                'llm_context_precision_without_reference': 0.5,
            }])

    monkeypatch.setattr(S, '_patch_vertexai_stub', lambda: None)

    import sys
    import types

    fake_ragas = types.ModuleType('ragas')
    fake_ragas.EvaluationDataset = types.SimpleNamespace(from_list=lambda rows: rows)
    fake_ragas.evaluate = lambda **kwargs: FakeResult()
    fake_metrics = types.ModuleType('ragas.metrics')
    fake_metrics.Faithfulness = lambda: object()
    fake_metrics.LLMContextPrecisionWithoutReference = lambda: object()
    fake_llms = types.ModuleType('ragas.llms')
    fake_llms.llm_factory = lambda *a, **k: object()
    monkeypatch.setitem(sys.modules, 'ragas', fake_ragas)
    monkeypatch.setitem(sys.modules, 'ragas.metrics', fake_metrics)
    monkeypatch.setitem(sys.modules, 'ragas.llms', fake_llms)

    scores = S.score_ragas(
        {'input': '질문: 바꿔도 될까?'},
        {'answer': '역할상 충분', 'docs': [{'content': 'VRRM 1000V'}]},
    )
    assert scores['ragas_faithfulness'][0] == 0.8
    assert scores['ragas_faithfulness'][1] == 'NUMERIC'
    assert scores['ragas_context_precision'][0] == 0.5
