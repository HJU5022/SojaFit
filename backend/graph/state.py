"""그래프 상태 정의 (G4). 질문 하나가 노드들을 지나가는 동안 같이 쓰는 공용 메모장이다.

- 역할: 칸 이름과 타입, 칸마다 값이 바뀌는 방식(덮어쓰기 / 쌓기)을 정한다. `nodes.py`·`build.py`가 import한다.
- 하지 않는 일: 노드 동작(`nodes.py`), 노드 연결(`build.py`), 사용자별 장기 기억(Store, `backend/graph/memory.py`).
- 출처: SPEC.md 2절 "그래프"의 노드 표, backend/graph/GRAPH.md, 강의 2주 04강(State 리듀서)·20강(`QAState`).

State와 Store는 다르다.
  - State: 이번 대화(thread) 안에서만 쓰는 것 (질문, 검색 결과, 중간 판단). 체크포인터가 저장한다.
  - Store: 대화를 넘어 사용자별로 남기는 것 (승인된 판정 사례). D6에서 붙인다.

노드는 메모장 전체를 다시 쓰지 않고 자기가 바꾼 칸만 dict로 돌려준다. LangGraph가 그 dict를 메모장에 합친다.
"""
import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict, total=False):  # total=False: 처음에는 비어 있는 칸이 있어도 된다
    """줄기 그래프의 공용 메모장. 칸 묶음별 주석이 어느 노드가 채우는지 알려 준다."""
    # ── 입력 (사용자가 넣는 것) ──
    input: str      # 사용자 원문: 회로·넷리스트 경로·대상·사용 조건·질문. 끝까지 바뀌지 않는다
    user_id: str    # 로그인한 사용자 id. D6에서 thread와 Store namespace를 여기서 가른다

    # ── 입력 읽기 노드가 채운다 (LLM 없이 글자를 나누고 넷리스트를 읽는다) ──
    circuit: str        # 회로 이름 (예: SparkFun Breadboard Supply)
    netlist_path: str   # 넷리스트 파일 경로
    target: str         # 바꿀 부품 기호 (예: D1)
    conditions: str     # 사용 조건 (예: 전원은 J1 잭으로만 공급한다)
    question: str       # 질문 문장만
    target_part: dict   # 대상 부품의 값·풋프린트와 전원 경로 (예: J1 → S1 → D1 → F1)

    # ── 라우팅 노드가 채운다 ──
    # [왜] 평가셋의 kind(관련/비관련)와 헷갈리지 않게 question_type이라 부른다
    question_type: str  # role | rating | candidate_judge | candidate_find | out_of_scope

    # ── 검색·재작성 노드가 채운다 (다시 검색하면 덮어쓴다. 새 메시지가 오면 입력 읽기 노드가 비운다) ──
    query: str          # 이번 검색어
    parts: list[str]    # 품번 필터. retrieve(..., parts=...)에 그대로 넘긴다
    docs: list[dict]    # 검색해 온 카드

    # ── 채점 노드가 채운다 ──
    passed: list[int]   # 채점을 통과한 카드 id(chunk_id). 비어 있으면 재작성이나 거절로 간다

    # ── 생성·거절 노드가 채운다 ──
    answer: str         # 사용자에게 보여 줄 답
    check: dict         # 인용 검사 결과 (없는 근거 인용, 인용 없는 문장 수)
    skill: dict         # 생성 노드의 Skill 적용 여부(enabled/applied)와 사용 파일 sha256

    # ── 쌓이는 칸 (Annotated[타입, operator.add]) ──
    # 리듀서(reducer): 노드가 칸 값을 돌려줄 때 LangGraph가 옛 값과 새 값을 합치는 규칙이다.
    # 칸에 리듀서가 없으면 새 값이 옛 값을 덮어쓰고, operator.add면 옛 값에 새 값을 더한다(숫자는 덧셈, 리스트는 이어 붙이기).
    # [왜] 덮어쓰지 않고 더하거나 이어 붙여야 검색 횟수와 지나간 길이 남는다(강의 2주 04강)
    tries: Annotated[int, operator.add]        # 검색 횟수. 검색 노드가 1을 돌려주면 1씩 늘어난다. 상한 판단에 쓴다
    # [주의] 더하기 칸은 덮어쓸 수 없어서, 새 메시지에서는 입력 읽기 노드가 지금 값의 음수를 돌려 0으로 되돌린다
    path: Annotated[list[str], operator.add]   # 지나간 노드 이름. 문항별로 어느 노드에서 틀렸는지 셀 때 쓴다
