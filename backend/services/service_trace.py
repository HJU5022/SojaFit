"""서비스 분석 경로의 모델 호출별 Langfuse 추적: 메타(이름·모델·토큰·비용·시간·오류 여부)만 보내고 본문은 보내지 않는다.

역할: 분석 요청 한 번의 LangGraph 실행에 Langfuse CallbackHandler를 붙이되, 내보내기 직전에 모든 관측에서 질문·답·검색 값·내 설정 같은 본문을 지운다.
호출자: backend/conversations/memory_service.py(`_invoke`의 callbacks, `_record_event`), langfuse_prompts.publish_analysis_trace(`ensure_client`).
입력: LANGFUSE_PUBLIC_KEY·LANGFUSE_SECRET_KEY(둘 중 하나라도 없으면 완전히 꺼진다). 출력: callbacks()의 (handler 목록, config metadata)(꺼졌거나 실패하면 빈 값).
하지 않는 일: 평가 추적(evals/runners/run_graph.py는 입력·출력을 남기는 별도 프로세스이며 이 모듈을 부르지 않는다), 프롬프트 등록(langfuse_prompts).
출처: SPEC.md 5절 "Langfuse 프롬프트와 실행 추적", 로그인 화면의 개인정보 처리 안내("질문 · 답변 글을 넣지 않습니다").
"""
import functools
import logging
import os
import threading

LOGGER = logging.getLogger(__name__)
PLACEHOLDER = '[redacted]'
_OBS = 'langfuse.observation.'
# [왜] 지우는 방식이 아니라 남기는 목록(allowlist)이다. SDK가 새 본문 칸을 추가해도 기본은 지워진다
_KEEP = frozenset({
    _OBS + 'type', _OBS + 'level', _OBS + 'model.name', _OBS + 'usage_details', _OBS + 'cost_details',
    _OBS + 'completion_start_time', _OBS + 'prompt.name', _OBS + 'prompt.version',
    'langfuse.version', 'langfuse.environment', 'langfuse.release', 'langfuse.trace.name', 'langfuse.trace.tags',
    'langfuse.trace.public', 'langfuse.internal.as_root', 'langfuse.internal.is_app_root', 'user.id', 'session.id'})
_BODY = (_OBS + 'input', _OBS + 'output')
# [왜] analysis-metadata는 서버가 만든 상태·단계별 시간뿐이라(질문·답 없음) 기존 그대로 metadata를 남긴다
_METADATA_SPAN = 'analysis-metadata'
_lock, _ready = threading.Lock(), False


def mask_otel_spans(*, params):
    """내보내기 직전 훅: 남기는 목록 밖의 칸을 지우고 입력·출력은 고정 자리표시자로 바꾼다."""
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch
    patches = {}
    for identifier, span in params.spans.items():
        keep_metadata = span.name == _METADATA_SPAN
        drop = [key for key in span.attributes
                if key not in _KEEP and not (keep_metadata and key.startswith(_OBS + 'metadata'))]
        patches[identifier] = OtelSpanPatch(delete_attributes=drop,
                                            set_attributes={key: PLACEHOLDER for key in _BODY if key in span.attributes})
    return MaskOtelSpansResult(span_patches=patches)


def enabled():
    return bool(os.getenv('LANGFUSE_PUBLIC_KEY') and os.getenv('LANGFUSE_SECRET_KEY'))


def ensure_client(**options):
    """마스킹 훅을 건 Langfuse client를 프로세스에서 한 번 만든다. 훅이 걸리지 않았으면 False(추적하지 않는다)."""
    global _ready
    from langfuse import Langfuse
    with _lock:
        if not _ready:
            client = Langfuse(mask_otel_spans=mask_otel_spans, **options)
            # [주의] 같은 키의 client가 이미 훅 없이 만들어졌다면 Langfuse가 그것을 재사용한다. 그러면 본문이 나가므로 쓰지 않는다
            _ready = client._resources is not None and client._resources.mask_otel_spans is mask_otel_spans
        return _ready


@functools.cache
def _handler_class():
    from backend.services.langfuse_prompts import CostCallbackHandler

    class ServiceHandler(CostCallbackHandler):
        def _get_error_level_and_status_message(self, error):
            # [왜] 오류 문구(pydantic 검증 오류 등)에 모델 출력 글이 들어갈 수 있다. OTel 상태 설명은 위 훅이 못 고치므로 종류 이름만 남긴다
            level, _ = super()._get_error_level_and_status_message(error)
            return level, type(error).__name__

        def on_tool_end(self, output, **kwargs):
            if getattr(output, 'status', None) == 'error':  # 도구 오류 본문도 상태 문구로 간다
                output = output.model_copy(update={'content': 'error'})
            return super().on_tool_end(output, **kwargs)

    return ServiceHandler


def callbacks(trace_id, thread, mode):
    """분석 실행 하나의 (handler 목록, LangChain config metadata). 꺼졌거나 만들지 못하면 ([], {})이고 분석에는 영향이 없다."""
    if not enabled():
        return [], {}
    try:
        if not ensure_client():
            LOGGER.warning('langfuse_service_trace_unmasked')
            return [], {}
        # [왜] analysis-metadata와 같은 trace_id(analysis_events.trace_id)로 묶는다. session_id는 thread, 사용자 값은 보내지 않는다
        handler = _handler_class()(public_key=os.environ['LANGFUSE_PUBLIC_KEY'], trace_context={'trace_id': trace_id})
        return [handler], {'langfuse_session_id': str(thread), 'langfuse_tags': ['analysis', mode]}
    except Exception:
        LOGGER.warning('langfuse_service_trace_unavailable')  # 예외 문구에 키·값이 있을 수 있어 문구는 적지 않는다
        return [], {}
