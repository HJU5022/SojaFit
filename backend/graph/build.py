"""그래프 조립 (G4).

필수:
  - Supervisor와 서브에이전트 2개 이상 (역할과 컨텍스트를 나눈다)
  - 체크포인트 (재개 가능, DB에 저장)
  - 사람 승인(interrupt) 지점 1곳 이상
권장 순서:
  - D4(11/5) 단일 에이전트 그래프로 기준 점수를 잰다 (질의 라우팅, 문서 채점, 질의 재작성, 재검색)
  - D5(11/6) Supervisor와 서브에이전트로 나누고 같은 평가셋(v2)으로 다시 잰다
"""


def build_graph():
    raise NotImplementedError("TODO: StateGraph를 조립하세요")
