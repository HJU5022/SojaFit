"""그래프 조립 (G4).

필수:
  - Supervisor와 서브에이전트 2개 이상 (역할과 컨텍스트를 나눈다)
  - 체크포인트 (재개 가능, DB에 저장)
  - 사람 승인(interrupt) 지점 1곳 이상
권장 순서:
  - D4(11/5) 단일 에이전트 그래프로 기준 점수를 잰다 (역할 파악, 대체 조건 도출, 후보 검색, 판정, 재검색)
  - D5(11/6) Supervisor와 서브에이전트로 나누고 같은 평가셋(v2)으로 다시 잰다
시험하기 쉽게 만드는 법:
  - 검색기와 체크포인터를 인자로 받는다: build_graph(retriever=None, checkpointer=None).
    그래야 가짜 검색기와 메모리 체크포인터로 키 없이 시험하고, 요청 수를 셀 수 있다.
  - 재작성 횟수 상한은 상수 하나로 둔다. 시험에서는 상수 대신 리터럴(예: 2)과 비교하고 retrieve 호출 횟수를 센다
    (상수끼리 비교하면 상한을 바꿔도 통과한다. docs/GATES.md 변이 확인).
  - 근거 충분 여부를 어휘 겹침 같은 점수 하나로만 정하지 말고, 품번·제조사·개정판·시험 조건(온도·전류)이 질문과 맞는지 같은 결정적 검사를 따로 둔다
    (예: 1N4148을 물었는데 1N4148W 카드를 인용하거나, TJ = 25°C 값을 물었는데 100°C 값을 인용하는 실패를 막는다).
  - 품번 목록, 낱말 가중치 같은 코퍼스 의존 값을 코드에 고정하지 않는다. 코퍼스가 커지면 새 대상을 전부 거절하게 된다.
"""
from backend.graph.state import AgentState

MAX_TRIES = 2  # 검색 상한: 첫 검색 + 재작성 뒤 1번(SPEC 2절)


def after_grade(state: AgentState) -> str:
    """채점 뒤 갈림길: 통과 카드가 있으면 생성, 다시 찾아도 소용없거나 상한에 닿았으면 거절, 아니면 재작성(강의 2주 20강 채점후)."""
    if state.get("passed"):
        return "생성"  # 통과 카드가 하나라도 있으면 답한다
    if not state.get("docs"):
        # [왜] 재작성은 품번 필터를 바꾸지 않는다. 코퍼스에 없는 품번(1N4001)이라 0장이면 다시 찾아도 0장이고 LLM 호출만 버린다(11-02 조장 결정)
        return "거절"
    if state.get("tries", 0) >= MAX_TRIES:
        return "거절"
    return "재작성"


def build_graph(retriever=None, checkpointer=None):
    raise NotImplementedError("TODO: StateGraph를 조립하세요")
