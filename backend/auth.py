"""로그인과 사용자 식별 (G4).

평가자는 조가 비공개로 제출한 평가용 계정 2개로 로그인해, 두 사용자의 대화(thread)와
장기 기억(Store namespace)이 섞이지 않는지 봅니다. 계정 정보를 저장소에 적지 않습니다.
"""


def current_user_id() -> str:
    raise NotImplementedError("TODO: 요청에서 로그인한 사용자 id를 꺼냅니다")
