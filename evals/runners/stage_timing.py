"""평가 실행기가 문항 행에 단계별 시간과 모델 호출별 시간 · 토큰 · 비용을 남기게 하는 기록기(D8 재측정).

- 역할: `AnalysisTimings`(서비스가 analysis_events.stages에 쓰는 것과 같은 노드 단위 시간)를 이어받아 LLM 호출 하나마다
  {노드, 모델, 초, 입력 · 출력 토큰, 공급자 보고 비용}을 모아 행의 `llm_call_log`에 두고, Voyage 임베딩 · 리랭크 호출의 시간 · 토큰을 모은다.
- 하지 않는 일: 질문 · 답 · 프롬프트 본문 저장(길이와 숫자만 둔다), 서비스 코드 변경, 예산 집행.
- 출처: docs/experiments/d8-stage-remeasure-plan.md 6절 1 · 2번, backend/services/langfuse_prompts.py `AnalysisTimings`
- 주의: 노드 단위 시간은 부모 노드가 자식 노드를 품으면 겹쳐 센다(단계 이름별로 따로 읽는다). 비용은 공급자가 응답에 실은 `cost`이고 없으면 None이다(실제 청구액과 대조하지 않음).
"""
import threading
import time
from contextlib import contextmanager

from backend.services.langfuse_prompts import AnalysisTimings


class StageRecorder(AnalysisTimings):
    """노드 단위 시간(부모 클래스) + LLM 호출 단위 기록."""

    def __init__(self):
        super().__init__()
        self.llm_calls, self._open = [], {}

    def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kwargs):
        meta = metadata or {}
        with self.lock:
            self._open[run_id] = (meta.get('langgraph_node'), meta.get('ls_model_name'), time.monotonic())

    def on_llm_end(self, response, *, run_id, **kwargs):
        with self.lock:
            node, model, started = self._open.pop(run_id, (None, None, time.monotonic()))
        output = response.llm_output or {}
        usage = output.get('token_usage') or {}
        message = getattr(response.generations[0][0], 'message', None) if response.generations and response.generations[0] else None
        meta = getattr(message, 'usage_metadata', None) or {}
        cost = usage.get('cost')
        cached = (usage.get('prompt_tokens_details') or {}).get('cached_tokens')  # [왜] 지시문 캐시(cache_control) 읽기 토큰. 같은 노드도 캐시 적중에 따라 비용이 달라진다
        with self.lock:
            self.llm_calls.append({
                'node': node, 'model': output.get('model_name') or model, 'seconds': round(time.monotonic() - started, 3),
                'input_tokens': meta.get('input_tokens', usage.get('prompt_tokens')),
                'output_tokens': meta.get('output_tokens', usage.get('completion_tokens')),
                'cached_tokens': cached, 'cost_usd': float(cost) if isinstance(cost, (int, float)) else None, 'ok': True})

    def on_llm_error(self, error, *, run_id, **kwargs):
        with self.lock:
            node, model, started = self._open.pop(run_id, (None, None, time.monotonic()))
            self.llm_calls.append({'node': node, 'model': model, 'seconds': round(time.monotonic() - started, 3),
                                   'input_tokens': None, 'output_tokens': None, 'cached_tokens': None, 'cost_usd': None, 'ok': False})

    def report(self):
        # [왜] 부모의 report()는 옛 영어 노드 이름으로 0ms '건너뜀' 행을 덧붙인다. 평가 집계에는 실제로 돈 칸만 쓴다
        return list(self.stages)


_voyage, _voyage_lock = [], threading.Lock()


def drain_voyage() -> list[dict]:
    """지금까지 모은 Voyage 호출 기록을 비우며 돌려준다(문항 하나가 끝날 때마다 부른다)."""
    with _voyage_lock:
        out, _voyage[:] = list(_voyage), []
    return out


@contextmanager
def voyage_timing():
    """`llm._voyage_post`를 감싸 임베딩 · 리랭크 호출의 {종류, 초, 토큰}을 모은다(임베딩과 리랭크가 모두 이 함수를 지난다)."""
    from backend.services import llm
    post = llm._voyage_post

    def timed(path, payload):
        started = time.perf_counter()
        data = post(path, payload)
        with _voyage_lock:
            _voyage.append({'kind': 'embed' if path == 'embeddings' else path, 'seconds': round(time.perf_counter() - started, 3),
                            'tokens': (data.get('usage') or {}).get('total_tokens')})
        return data
    llm._voyage_post = timed
    try:
        yield
    finally:
        llm._voyage_post = post
