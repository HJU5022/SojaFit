"""멀티 에이전트가 서로 주고받는 약속: Supervisor 지시서 · 이유 코드 · 상한.

- 역할: Supervisor가 내는 지시서(`Plan`: 고른 에이전트 하나와 그 에이전트의 지시 `Task`), 이유 코드(`Reason`), 질문당 상한을
  한 곳에 둔다. 판정 에이전트 코드가 쓰는 짧은 보고(`AgentReport`)는 단일 그래프(D4 v2)도 같이 쓰므로 그대로 둔다.
- 하지 않는 일: LLM · 검색 · DB 호출, 사용자에게 보일 문구 만들기(내부 코드와 사용자 문구는 따로 둔다), 상태 저장.
- 출처: 강의 IV-3 15강 cell 14(Supervisor가 에이전트 하나를 고르고 그 에이전트가 답한 뒤 끝), 11-09 강사 피드백(Supervisor가 앞뒤에 있어 헷갈리고 LLM 단계가 많다),
  회의록 D4-D5 B-지시서 4-4(형식 검사 · 상한), AGENTS.md 규칙 6(재시도와 루프에는 상한)
"""
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# [왜] 질문 하나가 쓰는 검색에 상한을 둔다(AGENTS 6). RAG 에이전트의 검색 → 근거 채점 고리가 이 횟수까지만 돈다
MAX_SEARCHES = 2          # 첫 검색어 1번 + 근거가 모자라면 다른 검색어(또는 품번 필터를 푼 검색) 1번
MAX_SUMMARY = 200         # 판정 코드 보고 요약 글자 수 상한

# 단일 그래프 Route의 다섯 가지에 일상 대화(chat)와 다이오드가 아닌 전자 부품(other_part)을 더했다(11-05 결정). out_of_scope는 서비스와 전혀 무관한 질문만 뜻한다
# price: 다이오드 품번의 가격 · 재고 질문(11-06 결정, SPEC 1절). 그래프는 품번만 정하고 값은 화면이 그래프 밖에서 조회한다
QuestionType = Literal['out_of_scope', 'chat', 'other_part', 'price', 'role', 'candidate_find', 'candidate_judge', 'rating']


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
                   'esd-protection', 'bridge']  # 사양 표의 분류 이름(backend/mcp_skill find_parts_by_specs와 같음)


class Spec(BaseModel):
    """질문이 품번 없이 부품을 묘사한 정격 하나(사용자 글의 숫자 그대로). 코드가 SI로 바꿔 사양 표에서 같은 값의 품번을 찾는다."""
    code: SpecCode
    value: float
    unit: str = Field(default='', max_length=6, description='unit as the user wrote it: V, mV, A, mA, W, mW, ns, pF or °C')


class Task(BaseModel):
    """고른 에이전트 하나에 주는 지시서: 목표 · 출력 · 경계, 문서 검색이면 첫 검색어와 묘사한 정격."""
    # [왜] 600자: Sonnet이 사용 조건을 목표에 옮겨 적어 300자를 넘겨 형식 검사에 세 번 걸렸다(11-06 v3-01 · 11 시험). 짧게 쓰라는 말은 프롬프트에 둔다
    goal: str = Field(max_length=600, description='What the agent must answer, in English, in one or two short sentences')
    output: str = Field(default='', max_length=300, description='What the agent should return')
    boundary: str = Field(default='', max_length=300, description='What the agent must not do or answer')
    query: str = Field(default='', max_length=200,
                       description='docs only: first English search query with datasheet terms; empty when the netlist alone answers (role)')
    # [왜] 품번 없이 정격으로 묘사한 부품("1000 V, 40 A 브리지 정류기의 TJ"): 판정 찾기는 회로 교체용이라 사용자 값에 감쇄율을 걸고 회로 역할을 요구한다.
    #      그래서 지시서가 묘사한 정격을 그대로 옮기고, RAG 에이전트가 사양 표 도구로 같은 값의 품번을 찾아 그 문서 안에서 검색한다(11-07 R1 dev G4)
    specs: list[Spec] = Field(default_factory=list, max_length=4,
                              description='docs only: when the question names no part number but describes the part by printed ratings, those ratings exactly as written (no derating)')
    category: Category = Field(default='', description='docs only, with specs: the part category the question names')
    package: str = Field(default='', max_length=30, description='docs only, with specs: the package name the question names, e.g. DO-201AD; empty otherwise')


class Declined(BaseModel):
    """여러 개를 묻는 질문에서 Supervisor가 거절하는 부분 하나와 그 이유(나머지 부분은 고른 에이전트가 답한다)."""
    ask: str = Field(max_length=160, description="the sub-question you refuse, in the user's words (Korean)")
    reason: Reason


class Plan(BaseModel):
    """Supervisor 지시서: 범위 판정 · 질문 종류와 다음 길 하나(RAG 에이전트 · 대체 부품 에이전트 · 끝내기 · 가격 안내 · 거절)."""
    question_type: QuestionType
    # [왜] 강의 15강처럼 에이전트를 하나만 고른다. 할 일 목록 · 동시 실행 · 재계획은 11-09에 뺐다(Sonnet 단계가 앞뒤로 늘어 p95 19초)
    next: Literal['docs', 'judge', 'finish', 'price', 'refuse']
    reason: Reason | None = None  # 거절이면 필수
    reply: str = Field(default='', max_length=300, description='Korean reply when finishing a chat question')
    task: Task | None = Field(default=None, description='next=docs or judge: the brief for that agent')
    # [왜] 여러 개를 묻는 질문의 일부가 코퍼스 밖이면 그 부분을 말없이 빼지 않고 거절 이유와 함께 답에 남긴다(B-지시서 4-5.3 '답하면 안 되는 것', 11-07 c20-15 · 18 · 19)
    declined: list[Declined] = Field(default_factory=list, max_length=3,
                                     description='next=docs or judge only: parts of a multi-part question you refuse, each with its refusal reason')

    @model_validator(mode='after')
    def consistent(self):
        # [왜] 형식이 틀린 지시서는 llm.chat이 다시 부르게 ValidationError로 낸다(B-지시서 4-4 "형식이 틀리면 다시")
        if self.next == 'refuse' and self.reason not in REFUSAL_REASONS:
            raise ValueError('refuse needs a refusal reason')
        if any(d.reason not in REFUSAL_REASONS for d in self.declined):
            raise ValueError('a declined part needs a refusal reason')
        if self.next == 'finish' and not self.reply.strip():
            raise ValueError('finish needs a reply')  # [왜] 이 길은 에이전트를 거치지 않아 Supervisor의 reply가 곧 답이다
        if self.next in ('docs', 'judge'):
            if self.task is None:
                raise ValueError(f'{self.next} needs a task brief')
            if self.next == 'judge' and self.question_type not in ('candidate_judge', 'candidate_find'):
                raise ValueError('the judge agent only takes candidate_judge or candidate_find questions')
            if self.next == 'docs' and self.question_type != 'role' and not self.task.query.strip():
                raise ValueError('the docs agent needs a search query unless the question is a role question')
        return self


class AgentReport(BaseModel):
    """판정 에이전트 코드(`agents/judge.py`)의 짧은 보고. 단일 그래프도 같은 함수를 써서 남겨 둔다."""
    agent: Literal['search', 'judge', 'writer', 'verifier']
    status: Literal['ok', 'partial', 'fail']
    summary: str = Field(max_length=MAX_SUMMARY)
    evidence_ids: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    reason: Reason | None = None
