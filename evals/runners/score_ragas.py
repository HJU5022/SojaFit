"""그래프 최종 상태의 질문·근거·답으로 RAGAS Faithfulness·Context Precision을 재 Langfuse Score 칸에 붙일 값을 만든다.

- 역할: 강의 03강과 같이 reference 없이 되는 두 지표만 잰다. 결과는 `run_gate`가 같은 trace에 `create_score`로 올린다(G6).
- 하지 않는 일: 평가셋 고치기, reference가 필요한 Context Recall, 회귀 게이트 합격선 판정.
- 출처: 강의 `03강_RAGAS_실제로_실행하기`, docs/GATES.md G6, evals/runners/run_gate.py
"""
from __future__ import annotations

import os
import sys
import types
import warnings
from typing import Any


def _patch_vertexai_stub() -> None:
    """ragas 0.4.3이 없는 langchain_community.chat_models.vertexai를 import할 때 쓰일 더미를 먼저 넣는다(강의 03강)."""
    name = 'langchain_community.chat_models.vertexai'
    if name in sys.modules:
        return
    stub = types.ModuleType(name)
    stub.ChatVertexAI = type('ChatVertexAI', (), {})  # type: ignore[attr-defined]
    sys.modules[name] = stub


def contexts_from_state(state: dict) -> list[str]:
    """검색 청크·판정 근거의 글만 모아 RAGAS retrieved_contexts로 쓴다(원문 PDF 전체를 다시 받지 않음)."""
    out: list[str] = []

    def add(text: Any) -> None:
        s = str(text or '').strip()
        if s and s not in out:
            out.append(s[:2000])  # [왜] judge 입력 폭주·비용 폭주를 막는다

    for doc in state.get('docs') or []:
        if isinstance(doc, dict):
            add(doc.get('content'))
    for report in state.get('final_reports') or state.get('reports') or []:
        if not isinstance(report, dict):
            continue
        for doc in report.get('docs') or []:
            if isinstance(doc, dict):
                add(doc.get('content'))
        _add_judgement_contexts(report.get('judgement') or {}, add)
    _add_judgement_contexts(state.get('judgement') or {}, add)
    return out[:15]


def _add_judgement_contexts(judgement: dict, add) -> None:
    """판정 결과의 역할 근거·조건 인용 글을 근거 목록에 넣는다(판정 길은 docs 칸이 비는 경우가 많다)."""
    for ev in judgement.get('role_evidence') or []:
        add(ev)
    for result in judgement.get('results') or []:
        if not isinstance(result, dict):
            continue
        for cond in result.get('conditions') or []:
            if isinstance(cond, dict):
                add(cond.get('citation'))
        add(result.get('summary'))


def question_text(item: dict, state: dict) -> str:
    """평가셋 입력에서 질문 줄만 고르고, 없으면 그래프가 읽은 question 칸을 쓴다."""
    raw = item.get('input') or ''
    for line in str(raw).splitlines():
        if line.startswith('질문:'):
            return line[len('질문:'):].strip() or raw
    return (state.get('question') or raw or '').strip()


def score_ragas(item: dict, state: dict) -> dict[str, tuple]:
    """RAGAS 두 지표를 (값, Langfuse data_type, 설명)으로 돌려준다. 끄거나 재료가 없으면 빈 dict.

    환경변수 `RAGAS_ENABLED=0`이면 완전히 건너뛴다. 모델은 `RAGAS_MODEL`(기본 openai/gpt-4o-mini).
    """
    if os.getenv('RAGAS_ENABLED', '1') == '0':
        return {}
    answer = (state.get('answer') or '').strip()
    contexts = contexts_from_state(state)
    question = question_text(item, state)
    if not answer or not question:
        return {}
    if not contexts:
        # [왜] 근거 없이 Faithfulness를 돌리면 거절·판정 답을 0점으로 벌주는 함정만 남긴다(강의 03강)
        return {}
    if not os.getenv('OPENROUTER_API_KEY'):
        return {}

    _patch_vertexai_stub()
    warnings.filterwarnings('ignore', message='.*ragas.metrics.*deprecated.*', category=DeprecationWarning)
    from openai import OpenAI
    from ragas import EvaluationDataset, evaluate
    from ragas.llms import llm_factory
    from ragas.metrics import Faithfulness, LLMContextPrecisionWithoutReference

    model = os.getenv('RAGAS_MODEL') or 'openai/gpt-4o-mini'
    max_tokens = int(os.getenv('RAGAS_MAX_TOKENS') or '4096')  # [왜] Faithfulness가 긴 판정 답을 자르면 IncompleteOutputException으로 NaN만 남는다(Marvia ragas_score도 4096)
    client = OpenAI(api_key=os.environ['OPENROUTER_API_KEY'], base_url='https://openrouter.ai/api/v1')
    judge = llm_factory(model, client=client, max_tokens=max_tokens)
    ds = EvaluationDataset.from_list([{
        'user_input': question,
        'retrieved_contexts': contexts,
        'response': answer,
    }])
    result = evaluate(
        dataset=ds,
        metrics=[Faithfulness(), LLMContextPrecisionWithoutReference()],
        llm=judge,
        show_progress=False,
        raise_exceptions=False,
    )
    row = result.to_pandas().iloc[0]
    scores: dict[str, tuple] = {}
    faith = row.get('faithfulness')
    prec = row.get('llm_context_precision_without_reference')
    if faith == faith:  # NaN 제외
        scores['ragas_faithfulness'] = (float(faith), 'NUMERIC', 'RAGAS Faithfulness(강의 03강, reference 없음)')
    if prec == prec:
        scores['ragas_context_precision'] = (
            float(prec), 'NUMERIC', 'RAGAS LLMContextPrecisionWithoutReference(강의 03강)')
    return scores
