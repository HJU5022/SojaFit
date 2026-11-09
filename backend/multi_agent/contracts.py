"""멀티 에이전트가 서로 주고받는 약속: 계획서 · 할 일 · 보고서 · 이유 코드 · 상한.

- 역할: Supervisor(계획)가 내는 계획서(`Plan`, 할 일 `Task` 최대 3개)와 서브에이전트가 올리는 보고서(`TaskReport`),
  이유 코드(`Reason`), 질문당 상한을 한 곳에 둔다. 모든 에이전트가 같은 규격을 쓰게 하려는 것이다.
  대체 부품 에이전트 코드가 쓰는 짧은 보고(`AgentReport`)는 단일 그래프(D4 v2)도 같이 쓰므로 그대로 둔다.
- 하지 않는 일: LLM · 검색 · DB 호출, 사용자에게 보일 문구 만들기(내부 코드와 사용자 문구는 따로 둔다), 상태 저장.
- 출처: backend/multi_agent/MULTI_AGENT.md "구조 결정"(11-06 재설계: Supervisor 계획 1번 + RAG 에이전트 · 대체 부품 에이전트, 각자 LLM 1번, 계획 형식 검사 · 상한),
  AGENTS.md 규칙 6(재시도와 루프에는 상한)
"""
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# [왜] 질문 하나가 쓰는 LLM · 도구 호출에 상한을 둔다(AGENTS 6). 넘으면 거절한다(MULTI_AGENT.md "구조 결정"의 상한)
MAX_TASKS = 3             # 계획의 할 일 수(설계 그림 "할 일 목록(최대 3)")
MAX_SUPERVISOR_CALLS = 4  # Supervisor LLM 호출: 계획 1 + 재계획 ≤1(MAX_REPLANS) + 종합 ≤1 = 3에 1을 더 둔 상한. 형식 재시도는 llm.chat 안에서 따로 센다
MAX_AGENT_RUNS = 6        # 서브에이전트 실행 수(할 일 3개 × 2의 여유)
MAX_SEARCHES = 2          # 문서 할 일 하나의 검색: 첫 검색어 1번 + 근거가 모자라면 다른 검색어 1번
MAX_SUMMARY = 200         # 보고 요약 글자 수 상한. Supervisor는 원문이 아니라 짧은 요약만 읽는다(컨텍스트 분리)
# [왜] 실패 · 부족 보고나 '앞 결과가 필요한 일' 뒤에 Supervisor(계획)가 다시 계획하는 횟수(설계 v2, 11-07: 실패하면 계획으로 되돌아가 다시 한다).
#      1번이면 에이전트 실행 6 = 할 일 3개 × 2회차, Supervisor 호출 4 ≥ 계획 1 + 재계획 1 + 종합 1과 맞는다
MAX_REPLANS = 1

AgentName = Literal['docs', 'judge']
# 단일 그래프 Route의 다섯 가지에 일상 대화(chat)와 다이오드가 아닌 전자 부품(other_part)을 더했다(11-05 결정). out_of_scope는 서비스와 전혀 무관한 질문만 뜻한다
# price: 다이오드 품번의 가격 · 재고 질문(11-06 결정, SPEC 1절). 그래프는 품번만 정하고 값은 화면이 그래프 밖에서 조회한다
QuestionType = Literal['out_of_scope', 'chat', 'other_part', 'price', 'role', 'candidate_find', 'candidate_judge', 'rating']
TaskKind = Literal['role', 'rating', 'candidate_judge', 'candidate_find']  # 할 일 하나가 답하는 부분의 종류


class Reason(str, Enum):
    """실패 · 거절 이유. 내부 코드이며 Langfuse에 남긴다(사용자 문구는 따로)."""
    # 거절 사유: 이 이유로 끝낼 수 있다
    OUT_OF_SCOPE = 'out_of_scope'            # 서비스 대상이 아님(전자부품이 아님 등)
    PART_MISSING = 'part_missing'            # 품번이 코퍼스 목록에 없음(확정: 목록 대조)
    REVISION_MISSING = 'revision_missing'    # 요청한 개정판이 없음(확정: 목록 대조)
    NOT_FOUND = 'not_found'                  # 두 번 찾았는데 못 찾음(추정: 정말 없다고 단정하지 않는다)
    LIMIT_REACHED = 'limit_reached'          # 질문당 상한 초과 · 계획 형식 실패
    VERIFY_FAILED = 'verify_failed'          # 답 검사(인용 · 숫자)에 걸림
    SEARCH_ERROR = 'search_error'            # 검색 장애(오류이며 정상 거절이 아니다)
    # 재시도 사유: 다음 시도에서 무엇을 바꿀지 알려 주는 용도(단일 그래프 · 기록용)
    NO_RESULT = 'no_result'                  # 검색 0건: 필터를 풀어 본다
    ALL_REJECTED = 'all_rejected'            # 결과는 있으나 근거가 아님: 검색어를 바꿔 본다
    PARTIAL = 'partial'                      # 일부 근거만 있음: 부족한 값을 겨냥해 본다


REFUSAL_REASONS = frozenset({Reason.OUT_OF_SCOPE, Reason.PART_MISSING, Reason.REVISION_MISSING, Reason.NOT_FOUND,
                             Reason.LIMIT_REACHED, Reason.VERIFY_FAILED, Reason.SEARCH_ERROR})
RETRY_REASONS = frozenset({Reason.NO_RESULT, Reason.ALL_REJECTED, Reason.PARTIAL})


SpecCode = Literal['VRRM', 'IF_AV', 'IFSM', 'VF', 'IR', 'TRR', 'VZ', 'PD', 'CJ', 'TJ_MAX', 'VRWM', 'VBR', 'VC', 'IPP', 'PPPM', 'VESD']
Category = Literal['', 'standard-rectifier', 'schottky-rectifier', 'schottky-diode', 'sic-schottky-diode', 'fast-recovery-trr-100-500ns',
                   'high-efficiency-trr-50-99ns', 'super-fast-recovery', 'ultra-fast-recovery', 'switching-diode', 'zener-diode', 'tvs',
                   'esd-protection', 'bridge']  # 문서 분류 이름(source_documents.category, pipeline/specs.py family)


class Spec(BaseModel):
    """질문이 품번 없이 부품을 묘사한 정격 하나(사용자 글의 숫자 그대로). 코드가 SI로 바꿔 사양 표에서 같은 값의 품번을 찾는다."""
    code: SpecCode
    value: float
    unit: str = Field(default='', max_length=6, description='unit as the user wrote it: V, mV, A, mA, W, mW, ns, pF or °C')


class Task(BaseModel):
    """할 일 하나의 지시서: 맡을 에이전트 · 목표 · 출력 형식 · 경계 · 첫 검색어."""
    id: int = Field(description='1, 2, 3 in order')
    agent: AgentName
    kind: TaskKind
    # [왜] 600자: Sonnet이 사용 조건을 목표에 옮겨 적어 300자를 넘겨 형식 검사에 세 번 걸렸다(11-06 v3-01 · 11 시험). 짧게 쓰라는 말은 프롬프트에 둔다
    goal: str = Field(max_length=600, description='What this part of the question needs, in English, in one or two short sentences')
    output: str = Field(default='', max_length=300, description='What the agent should return')
    boundary: str = Field(default='', max_length=300, description='What the agent must not do or answer')
    query: str = Field(default='', max_length=200,
                       description='docs only: first English search query with datasheet terms; empty for a role task answered from the netlist')
    # [왜] 재계획에서 앞 회차 찾기가 낸 품번으로 문서 검색을 거르려고 둔다(품번 없이 사양만 준 질문, 설계 v2)
    # [왜] 품번 없이 정격으로 묘사한 부품("1000 V, 40 A 브리지 정류기의 TJ"): 판정 찾기는 회로 교체용이라 사용자 값에 감쇄율을 걸고 회로 역할을 요구한다.
    #      그래서 계획이 묘사한 정격을 그대로 옮기고, RAG 에이전트가 사양 표 도구로 같은 값의 품번을 찾아 그 문서 안에서 검색한다(11-07 R1 dev G4)
    specs: list[Spec] = Field(default_factory=list, max_length=4,
                              description='docs only: when the question names no part number but describes the part by printed ratings, those ratings exactly as written (no derating)')
    category: Category = Field(default='', description='docs only, with specs: the part category the question names')
    package: str = Field(default='', max_length=30, description='docs only, with specs: the package name the question names, e.g. DO-201AD; empty otherwise')
    parts: list[str] = Field(default_factory=list, max_length=8,
                             description='docs only: part numbers to restrict the search to, e.g. parts an earlier find task reported; empty = parts named in the question')


class Declined(BaseModel):
    """여러 개를 묻는 질문에서 Supervisor가 거절하는 부분 하나와 그 이유(나머지 부분은 할 일로 답한다)."""
    ask: str = Field(max_length=160, description="the sub-question you refuse, in the user's words (Korean)")
    reason: Reason


class Plan(BaseModel):
    """Supervisor ①의 계획서: 범위 판정 · 질문 종류 · 할 일 목록, 또는 바로 끝내는 길(일상 대화 · 가격 안내 · 거절)."""
    question_type: QuestionType
    next: Literal['tasks', 'finish', 'price', 'refuse', 'answer']  # answer: 재계획에서 더 할 일 없이 받은 보고로 답한다
    reason: Reason | None = None  # 거절이면 필수
    reply: str = Field(default='', max_length=300, description='Korean reply when finishing a chat question')
    tasks: list[Task] = Field(default_factory=list)
    # [왜] 여러 개를 묻는 질문의 일부가 코퍼스 밖이면 그 부분을 말없이 빼지 않고 거절 이유와 함께 답에 남긴다(11-07 c20-15 · 18 · 19)
    declined: list[Declined] = Field(default_factory=list, max_length=3,
                                     description='next=tasks only: parts of a multi-part question you refuse, each with its refusal reason')
    replan: bool = Field(default=False, description="true when the next step can only be planned after seeing these tasks' reports; the first-step tasks still go in tasks")
    # [왜] 처음엔 앞 회차 할 일 번호 목록(list[int])이었는데, 직통 구조화 출력에서 모델이 그 칸에 1만 자리 숫자를 써 계획이 깨졌다(11-07 G4 시험).
    #      참 · 거짓 하나로 줄인다: 참이면 앞 회차의 ok 보고를 답에 남긴다
    keep_earlier: bool = Field(default=False, description='replan only: true to keep the earlier ok answers in the final answer (e.g. the found candidates when the user asked for them)')

    @model_validator(mode='after')
    def consistent(self):
        # [왜] 형식이 틀린 계획은 llm.chat이 다시 부르게 ValidationError로 낸다(MULTI_AGENT.md "구조 결정": 형식이 틀리면 다시 부름)
        if self.next == 'refuse' and self.reason not in REFUSAL_REASONS:
            raise ValueError('refuse needs a refusal reason')
        if any(d.reason not in REFUSAL_REASONS for d in self.declined):
            raise ValueError('a declined part needs a refusal reason')
        if self.next == 'finish' and not self.reply.strip():
            raise ValueError('finish needs a reply')  # [왜] 이 길은 서브에이전트를 거치지 않아 Supervisor의 reply가 곧 답이다
        if self.next == 'tasks':
            if not 1 <= len(self.tasks) <= MAX_TASKS:
                raise ValueError(f'tasks needs 1 to {MAX_TASKS} tasks')
            if [t.id for t in self.tasks] != list(range(1, len(self.tasks) + 1)):
                raise ValueError('task ids must be 1, 2, 3 in order')
            for t in self.tasks:
                if t.agent == 'judge' and t.kind not in ('candidate_judge', 'candidate_find'):
                    raise ValueError('the judge agent only takes candidate_judge or candidate_find tasks')
                if t.agent == 'docs' and t.kind != 'role' and not t.query.strip():
                    raise ValueError('a docs task other than role needs a search query')
        return self


class TaskReport(BaseModel):
    """서브에이전트가 할 일 하나를 마치고 올리는 보고서. 답 모으기 · 재계획은 요약 · 상태만 읽고, 마무리 코드가 부분 답 · 근거를 쓴다."""
    task: int
    agent: AgentName
    status: Literal['ok', 'partial', 'fail']
    summary: str = Field(max_length=MAX_SUMMARY)
    reason: Reason | None = None                            # 실패면 사유
    missing: list[str] = Field(default_factory=list)        # 부족한 값 이름(예: VRRM)
    answer: str = ''                                        # 문서 할 일의 부분 답(문장마다 [번호] 인용, 한국어)
    memory_refs: list[str] = Field(default_factory=list, max_length=5)  # 본문 근거와 분리한 과거 사례 ID
    evidence_ids: list[str] = Field(default_factory=list)   # 인용한 근거 번호
    docs: list[dict] = Field(default_factory=list)          # 문서 할 일이 LLM에 보여 준 청크(인용 검사 · 채점이 쓴다)
    judgement: dict = Field(default_factory=dict)           # 판정 할 일의 판정 · 찾기 결과(답 틀의 입력)
    searches: list[dict] = Field(default_factory=list)      # 검색마다 {query, parts, top: [[파일, 쪽], ...]}(검색 지표 계산용)
    llm_calls: int = 0
    round: int = 1                                          # 몇 번째 계획의 할 일인가(재계획 뒤 2)


class AgentReport(BaseModel):
    """대체 부품 에이전트 코드(`agents/judge.py`)의 짧은 보고. 단일 그래프도 같은 함수를 써서 남겨 둔다."""
    agent: Literal['search', 'judge', 'writer', 'verifier']
    status: Literal['ok', 'partial', 'fail']
    summary: str = Field(max_length=MAX_SUMMARY)
    evidence_ids: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    reason: Reason | None = None
