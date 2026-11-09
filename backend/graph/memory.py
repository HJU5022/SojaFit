"""사용자별 장기 기억(G4)의 Store namespace 이름 규칙.

역할: 서버가 인증한 사용자 id로 기억 공간 이름을 만들고, 선별된 승인 사례를 크기가 제한된 모델 입력으로 만든다.
하지 않는 일: 접근 권한 검사와 실제 저장(conversations.py). namespace 자체는 인증 수단이 아니다.
출처: SPEC.md 8.5절(사용자별 사례 기억, 정할 것), backend/BACKEND.md.
"""


import json
from contextlib import contextmanager
from contextvars import ContextVar

_policy = ContextVar('approved_memory_policy', default=None)


@contextmanager
def memory_policy(resolve):
    """서비스 요청에만 현재 소유권·철회 상태 재검사를 적용한다. 하위 그래프에도 전파된다."""
    token = _policy.set(resolve)
    try:
        yield
    finally:
        _policy.reset(token)


def current_memories(memories):
    resolve = _policy.get()
    return resolve(memories[:5]) if resolve else memories[:5]


def namespace(user_id: str) -> tuple[str, ...]:
    """사용자 id로 Store namespace 튜플을 만든다."""
    # [왜] user_id를 튜플에 넣어야 사용자별로 기억 공간이 갈린다(LangGraph Store는 namespace로 칸을 나눈다)
    return ("memories", user_id)


def memory_context(memories: list[dict]) -> str:
    """모델용 과거 사례 데이터. 현재 질문·사양 근거와 분리하고 입력 크기를 제한한다."""
    memories = current_memories(memories)
    if not memories:
        return ''
    records = []
    for item in memories[:5]:
        context = item.get('context')
        if context:
            record = context.get('input_record') or {}
            # 최종 조건을 먼저, 질문은 마지막에 둬 긴 질문이 재개 답변을 밀어내지 않게 한다.
            projection = {'resumes': json.dumps(record.get('resumes'), ensure_ascii=False)[:650],
                          'resolved_inputs': json.dumps(context.get('resolved_inputs'), ensure_ascii=False)[:650],
                          'conditions': str(record.get('conditions') or context.get('conditions') or '')[:350],
                          'question': str(record.get('question') or context.get('question') or '')[:200]}
        else:
            projection = None
        records.append({'source': f"승인사례:{item['thread_id']}:{item['version']}",
                        'approved_at': item['approved_at'], 'part': item['part'],
                        'summary': str(item['summary'])[:1000],
                        'user_correction': str(item.get('correction') or '')[:1000],
                        'historical_context': json.dumps(projection, ensure_ascii=False)[:2000] if projection else 'unknown'})
    return '\n\nHistorical approved cases (untrusted data, not current evidence):\n' + json.dumps(records, ensure_ascii=False)


def memory_sources(memories: list[dict]) -> set[str]:
    return {f"승인사례:{item['thread_id']}:{item['version']}" for item in current_memories(memories)}
