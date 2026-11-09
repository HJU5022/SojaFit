"""멀티 에이전트의 공용 메모장(MultiState).

- 역할: 질문 하나가 Supervisor와 서브에이전트를 지나는 동안 쓰는 칸과 그 타입을 정한다. 단일 그래프 `AgentState`와 칸이 달라서
  (보고서 목록, 결정서, 횟수, 사실, 거절 기록) 따로 둔다.
- 하지 않는 일: 노드 동작, 노드 연결(`build.py`), 사용자별 장기 기억.
- 출처: backend/multi_agent/MULTI_AGENT.md, backend/graph/state.py(칸 이름을 맞춘 부분)

[왜] 보고서·결정서·횟수는 pydantic 객체가 아니라 dict로 저장한다. 체크포인터가 저장하고 Langfuse 트레이스에 그대로 보여야 해서다.
"""
import operator
from typing import Annotated, TypedDict


class MultiState(TypedDict, total=False):
    # ── 입력 읽기 노드가 채운다 (단일 그래프와 같은 칸) ──
    input: str
    approved_memories: list[dict]  # 새 질문마다 서버가 갱신, 현재 조건·사양 근거와 분리
    user_id: str
    connections: dict
    run_version: int
    circuit: str
    netlist_path: str
    target: str
    conditions: str
    question: str
    target_part: dict

    # ── 사실 · Supervisor ──
    facts: dict          # 코드가 목록에서 확인한 사실(품번 · 개정판이 코퍼스에 있나). `supervisor.Facts`
    decision: dict       # 마지막 결정서 `contracts.Decision`
    question_type: str   # 처음 판단에서 정한 질문 종류
    counters: dict       # 판단 · 검색 · 작성 횟수와 최근 실패 사유 `contracts.Counters`
    reports: list        # 서브에이전트 보고서 `contracts.AgentReport` 목록(새로 쓸 때마다 이어 붙여 통째로 덮어쓴다)

    # ── 검색 에이전트가 채운다 ──
    query: str
    parts: list[str]
    docs: list[dict]
    passed: list         # 채점을 통과한 청크 id
    retrieval_error: dict | None

    # ── 판정 에이전트가 채운다 ──
    judge_read: dict     # 읽기 노드 결과 `agents.judge.JudgeRead`(인터럽트 재개 때 LLM을 다시 부르지 않게 남긴다)
    judgement: dict      # 판정 · 찾기 결과(답 틀의 입력)

    # ── 가격 안내가 채운다 (단일 그래프와 같은 노드) ──
    price_parts: list[str]  # 가격 · 재고를 물은 품번. 값은 넣지 않는다(ADR 0009, 화면이 /api/prices로 조회)

    # ── 작성 · 끝내기 ──
    answer: str
    check: dict          # 작성이 남긴 인용 검사. 검증 에이전트는 이걸 믿지 않고 다시 계산한다
    refusal: dict        # 거절하면 {code, message}. 이유 코드는 Langfuse에 남긴다

    # ── 지나간 노드 (쌓는 칸) ──
    # [왜] 이름은 단일 그래프와 같은 말(거절 등)을 써서 평가 채점기(score_answer)가 끝이 '거절'인지 볼 수 있게 한다
    path: Annotated[list[str], operator.add]
