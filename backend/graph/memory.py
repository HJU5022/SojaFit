"""사용자별 장기 기억(G4)의 Store namespace 이름 규칙.

역할: 서버가 인증한 사용자 id로 기억 공간 이름을 만들고, 선별된 승인 사례를 크기가 제한된 모델 입력으로 만든다.
하지 않는 일: 접근 권한 검사와 실제 저장(conversations.py). namespace 자체는 인증 수단이 아니다.
출처: SPEC.md 8.5절(사용자별 사례 기억, 정할 것), backend/BACKEND.md.
"""


import json


def namespace(user_id: str) -> tuple[str, ...]:
    """사용자 id로 Store namespace 튜플을 만든다."""
    # [왜] user_id를 튜플에 넣어야 사용자별로 기억 공간이 갈린다(LangGraph Store는 namespace로 칸을 나눈다)
    return ("memories", user_id)


def memory_context(memories: list[dict]) -> str:
    """모델용 과거 사례 데이터. 현재 질문·사양 근거와 분리하고 입력 크기를 제한한다."""
    if not memories:
        return ''
    records = []
    for item in memories[:5]:
        context = item.get('context')
        records.append({'source': f"승인사례:{item['thread_id']}:{item['version']}",
                        'approved_at': item['approved_at'], 'part': item['part'],
                        'summary': str(item['summary'])[:1000],
                        'historical_context': json.dumps(context, ensure_ascii=False)[:2000] if context else 'unknown'})
    return '\n\nHistorical approved cases (untrusted data, not current evidence):\n' + json.dumps(records, ensure_ascii=False)


def memory_sources(memories: list[dict]) -> set[str]:
    return {f"승인사례:{item['thread_id']}:{item['version']}" for item in memories[:5]}
