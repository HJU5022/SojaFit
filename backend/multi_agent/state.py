"""멀티 에이전트의 공용 메모장(MultiState)과, 판정 에이전트 하위 그래프의 메모장(JudgeState).

- 역할: 질문 하나가 Supervisor ① 계획 → 서브에이전트(동시 실행) → Supervisor ② 종합 → 답 검사를 지나는 동안 쓰는 칸과 그 타입을 정한다.
  단일 그래프 `AgentState`와 칸이 달라서(계획서, 보고서 목록, 횟수, 사실, 거절 기록) 따로 둔다.
- 하지 않는 일: 노드 동작, 노드 연결(`build.py`), 사용자별 장기 기억.
- 출처: backend/multi_agent/MULTI_AGENT.md "구조 결정"(11-06 재설계), backend/graph/state.py(칸 이름을 맞춘 부분)

[왜] 계획서 · 보고서 · 횟수는 pydantic 객체가 아니라 dict로 저장한다. 체크포인터가 저장하고 Langfuse 트레이스에 그대로 보여야 해서다.
"""
import operator
from typing import Annotated, TypedDict


def add_or_reset(old: list | None, new: list | None) -> list:
    """보고서 칸의 합치기 규칙: 서브에이전트가 동시에 올린 보고를 이어 붙이고, None이 오면 비운다(새 질문 시작)."""
    # [왜] 서브에이전트는 Send로 동시에 돌아 한 단계에서 같은 칸에 여러 번 쓴다. 덮어쓰기 칸이면 LangGraph가 InvalidUpdateError를 낸다
    return [] if new is None else (old or []) + new


class MultiState(TypedDict, total=False):
    # ── 입력 읽기 노드가 채운다 (단일 그래프와 같은 칸) ──
    input: str
    approved_memories: list[dict]  # 새 질문마다 서버가 갱신, 현재 조건·사양 근거와 분리
    memory_refs: list[str]  # 모델이 선택하고 현재 요청의 제공 사례와 대조한 ID
    user_id: str
    connections: dict
    run_version: int
    circuit: str
    netlist_path: str
    target: str
    conditions: str
    question: str
    target_part: dict

    # ── 사실 · Supervisor ① 계획 ──
    facts: dict          # 코드가 목록에서 확인한 사실(품번 · 개정판이 코퍼스에 있나). `supervisor.Facts`
    plan: dict           # 계획서 `contracts.Plan`(할 일마다 지시서)
    question_type: str   # 계획이 정한 질문 종류
    counters: dict       # {'hops': Supervisor LLM 호출, 'agents': 서브에이전트 실행, 'searches': 검색, 'replans': 재계획} — 평가 실행기가 읽는다
    round: int           # 지금 계획 회차(첫 계획 1, 재계획 뒤 2). 보고서의 round와 맞춰 이번 회차 보고를 가린다
    reports: Annotated[list, add_or_reset]  # 서브에이전트 보고서 `contracts.TaskReport` 목록

    # ── Supervisor ② 모으기 · 마무리 ──
    outcome: str         # 모으기가 정한 다음 길: single · synth · refuse · replan
    final_reports: list  # 답에 쓰는 보고(재계획 뒤에는 이번 회차 + 계획이 남기라 한 앞 회차 보고). 비면 reports 전체
    synth_text: str      # 종합 LLM이 쓴 글(판정 답 틀을 붙이기 전). 답 검사가 이 글의 숫자만 본다
    refusal_reason: str  # 거절로 끝낼 때의 이유 코드(계획 · 모으기 · 답 검사가 정한다)
    docs: list[dict]     # 문서 할 일들이 보여 준 청크(채점기가 인용 위치를 읽는다)
    passed: list         # 그 청크 id(채점기 칸 이름을 단일 그래프와 맞춘다)
    judgement: dict      # 판정 할 일의 판정 · 찾기 결과(답 틀의 입력)
    price_parts: list[str]  # 가격 · 재고를 물은 품번. 값은 넣지 않는다(ADR 0009, 화면이 /api/prices로 조회)
    answer: str
    check: dict          # 답 검사 결과 {used, fake_citations, uncited_sentences, judgement}
    refusal: dict        # 거절하면 {code, message}. 이유 코드는 Langfuse에 남긴다

    # ── 지나간 노드 (쌓는 칸) ──
    # [왜] 이름은 단일 그래프와 같은 말(거절 등)을 써서 평가 채점기(score_answer)가 끝이 '거절'인지 볼 수 있게 한다
    path: Annotated[list[str], operator.add]


class JudgeState(TypedDict, total=False):
    """판정 에이전트 하위 그래프의 메모장. Send 꾸러미(지시서 + 필요한 입력)만 받는다."""
    task: dict
    approved_memories: list[dict]  # 부모가 소유권을 확인한 사례만 Send로 전달한다
    question: str
    conditions: str
    target: str
    target_part: dict
    facts: dict
    question_type: str   # 할 일의 종류(candidate_judge · candidate_find). 판정 코드가 찾기인지 이걸로 가른다
    round: int           # 이 할 일의 계획 회차(보고서에 그대로 적는다)
    judge_read: dict     # 읽기 노드 결과(인터럽트 재개 때 LLM을 다시 부르지 않게 남긴다)
    reports: Annotated[list, add_or_reset]
    path: Annotated[list[str], operator.add]


class JudgeOut(TypedDict, total=False):
    """하위 그래프가 바깥 메모장에 돌려주는 칸(보고와 지나간 노드만)."""
    reports: Annotated[list, add_or_reset]
    path: Annotated[list[str], operator.add]
