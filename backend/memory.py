"""사용자별 장기 기억(G4)의 Store namespace 이름 규칙.

역할: namespace에 사용자 id를 넣어 사용자 사이에 기억이 섞이지 않게 한다. 호출자는 아직 없다(D6에서 그래프에 Store를 붙일 때 쓴다).
하지 않는 일: 승인 사례 저장, 틀린 기억 정정, DB 기반 Store, 무엇을 기억할지의 기준(모두 아직 정하지 않음).
출처: SPEC.md 8.5절(사용자별 사례 기억, 정할 것), backend/BACKEND.md.
"""


def namespace(user_id: str) -> tuple[str, ...]:
    """사용자 id로 Store namespace 튜플을 만든다."""
    # [왜] user_id를 튜플에 넣어야 사용자별로 기억 공간이 갈린다(LangGraph Store는 namespace로 칸을 나눈다)
    return ("memories", user_id)
