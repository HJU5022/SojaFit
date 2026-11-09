"""멀티 에이전트의 공용 메모장(MultiState)과, 두 에이전트 하위 그래프의 메모장(RAG · 대체 부품).

- 역할: 질문 하나가 입력 읽기 → 품번·판 확인 → Supervisor → 에이전트 하나 → 답 검사를 지나는 동안 쓰는 칸과 그 타입을 정한다.
  단일 그래프 `AgentState`와 칸이 달라서(지시서, 횟수, 사실, 거절 기록) 따로 둔다.
  하위 그래프마다 받는 칸(`…In`) · 안에서 쓰는 칸 · 돌려주는 칸(`…Out`)을 나눈다.
- 하지 않는 일: 노드 동작, 노드 연결(`build.py`), 사용자별 장기 기억.
- 출처: 강의 IV-2 14강(서브그래프: 그래프를 노드로), backend/graph/state.py(칸 이름을 맞춘 부분)

[왜] 지시서 · 횟수는 pydantic 객체가 아니라 dict로 저장한다. 체크포인터가 저장하고 Langfuse 트레이스에 그대로 보여야 해서다.
[왜] 하위 그래프의 받는 칸에는 `path`를 넣지 않는다. 넣으면 하위 그래프가 바깥 경로 전체를 받아 끝에 다시 돌려주어 경로가 두 번 쌓인다.
"""
import operator
from typing import Annotated, TypedDict


class MultiState(TypedDict, total=False):
    # ── 입력 읽기 노드가 채운다 (단일 그래프와 같은 칸) ──
    input: str
    user_id: str
    circuit: str
    netlist_path: str
    target: str
    conditions: str
    question: str
    target_part: dict

    # ── 품번·판 확인 · Supervisor ──
    facts: dict          # 코드가 목록에서 확인한 사실(품번 · 개정판이 코퍼스에 있나). `supervisor.Facts`
    plan: dict           # Supervisor 지시서 `contracts.Plan`(다음 길 하나 · 거절한 부분)
    task: dict           # 고른 에이전트의 지시 `contracts.Task`(두 하위 그래프가 이 칸으로 받는다)
    question_type: str   # Supervisor가 정한 질문 종류
    counters: dict       # {'hops': Supervisor LLM 호출, 'searches': RAG 검색} — 평가 실행기가 읽는다

    # ── 에이전트가 낸 답 · 답 검사 ──
    searches: list       # RAG 검색마다 {query, parts, top: [[파일, 쪽], ...]}(감시 실행기의 검색 지표용)
    refusal_reason: str  # 거절로 끝낼 때의 이유 코드(Supervisor · 에이전트 · 답 검사가 정한다)
    docs: list[dict]     # RAG 에이전트가 답에 쓴 청크(채점기가 인용 위치를 읽는다)
    passed: list         # 그 청크 id(채점기 칸 이름을 단일 그래프와 맞춘다)
    judgement: dict      # 대체 부품 에이전트의 판정 · 찾기 결과(답 틀의 입력)
    price_parts: list[str]  # 가격 · 재고를 물은 품번. 값은 넣지 않는다(ADR 0009, 화면이 /api/prices로 조회)
    answer: str
    check: dict          # 답 검사 결과 {used, fake_citations, uncited_sentences, judgement}
    refusal: dict        # 거절하면 {code, message}. 이유 코드는 Langfuse에 남긴다

    # ── 지나간 노드 (쌓는 칸) ──
    # [왜] 이름은 단일 그래프와 같은 말(거절 등)을 써서 평가 채점기(score_answer)가 끝이 '거절'인지 볼 수 있게 한다
    path: Annotated[list[str], operator.add]


class AgentOut(TypedDict, total=False):
    """두 에이전트 하위 그래프가 바깥 메모장에 돌려주는 칸: 답(또는 거절 사유)과 지나간 노드."""
    answer: str
    refusal_reason: str
    path: Annotated[list[str], operator.add]


class RagIn(TypedDict, total=False):
    """RAG 에이전트가 바깥 메모장에서 받는 칸."""
    task: dict
    question: str
    target_part: dict
    plan: dict           # 거절한 부분(declined)을 답 끝에 붙이려고 받는다
    facts: dict
    counters: dict


class RagOut(AgentOut, total=False):
    docs: list[dict]
    passed: list
    searches: list
    counters: dict


class RagState(RagIn, RagOut, total=False):
    """RAG 에이전트 하위 그래프의 메모장: 받는 칸 + 돌려주는 칸 + 검색 → 근거 채점 고리가 쓰는 칸."""
    tries: int           # 검색 → 근거 채점을 몇 바퀴 돌았나(MAX_SEARCHES까지)
    query: str           # 이번 바퀴의 검색어(첫 바퀴는 지시서 검색어, 다음 바퀴는 근거 채점이 준 다른 검색어)
    next_query: str      # 근거 채점이 다시 찾으라고 준 검색어. 비면 고리를 나간다
    relax: bool          # 품번 필터 안에서 0건이라 필터를 풀고 다시 찾는 중
    filter_parts: list   # 묘사한 정격으로 사양 표에서 찾은 품번(그 문서 안에서만 찾는다)
    found: list[dict]    # 이번 바퀴에 LLM에 보여 줄 청크
    error: str           # 검색 · 사양 표 도구 장애나 정격에 맞는 품번 없음(이유 코드). 있으면 LLM을 부르지 않는다


class JudgeIn(TypedDict, total=False):
    """대체 부품 에이전트가 바깥 메모장에서 받는 칸."""
    task: dict
    question: str
    conditions: str
    target: str
    target_part: dict
    facts: dict
    question_type: str   # candidate_judge · candidate_find. 판정 코드가 찾기인지 이걸로 가른다
    plan: dict


class JudgeOut(AgentOut, total=False):
    judgement: dict


class JudgeState(JudgeIn, JudgeOut, total=False):
    """대체 부품 에이전트 하위 그래프의 메모장."""
    judge_read: dict     # 회로 역할 읽기 결과(인터럽트 재개 때 LLM을 다시 부르지 않게 남긴다)
