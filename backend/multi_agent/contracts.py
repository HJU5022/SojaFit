"""멀티 에이전트가 서로 주고받는 약속: 결정서 · 보고서 · 이유 코드 · 한도.

- 역할: Supervisor가 내리는 결정서(`Decision`)와 서브에이전트가 올리는 보고서(`AgentReport`)의 모양, 이유 코드(`Reason`),
  루프 한도와 한도 검사(`check_limit`)를 한 곳에 둔다. 모든 에이전트가 같은 규격을 쓰게 하려는 것이다.
- 하지 않는 일: LLM · 검색 · DB 호출, 사용자에게 보일 문구 만들기(내부 코드와 사용자 문구는 따로 둔다), 상태 저장.
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05 설계 대화), AGENTS.md 규칙 6(재시도와 루프에는 상한)
"""
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# [왜] Supervisor는 서브에이전트가 끝날 때마다 판단하므로 총 판단 횟수에 상한이 없으면 서로 되돌려 보내며 끝없이 돈다(AGENTS 6)
MAX_HOPS = 8        # Supervisor 판단 횟수: 정상 경로가 4번 안팎이라 두 배로 둔 여유값(측정해 보고 조정)
MAX_SEARCHES = 2    # 검색: 처음 1번 + 실패 사유를 붙여 다르게 다시 1번 (D4 MAX_TRIES와 같음)
MAX_WRITES = 2      # 작성: 처음 1번 + 검증에 걸린 뒤 다시 쓰기 1번
MAX_SUMMARY = 200   # 보고서 요약 글자 수 상한. Supervisor는 원문이 아니라 짧은 요약만 읽는다(컨텍스트 분리)

# 'web'은 나중 조각(평가 모드에서는 끔). 'price'는 가격 안내로 끝내는 길(Mouser는 부르지 않는다, ADR 0009)
NextNode = Literal['search', 'judge', 'writer', 'verifier', 'web', 'finish', 'refuse', 'price']
AgentName = Literal['search', 'judge', 'writer', 'verifier']
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
    LIMIT_REACHED = 'limit_reached'          # 판단 횟수 한도
    VERIFY_FAILED = 'verify_failed'          # 검증에 두 번 걸림
    SEARCH_ERROR = 'search_error'            # 검색 장애(오류이며 정상 거절이 아니다)
    # 재시도 사유: 다음 시도에서 무엇을 바꿀지 알려 주는 용도
    NO_RESULT = 'no_result'                  # 검색 0건: 필터를 풀어 본다
    ALL_REJECTED = 'all_rejected'            # 결과는 있으나 채점에서 전부 탈락: 검색어를 바꿔 본다
    PARTIAL = 'partial'                      # 일부 근거만 있음: 부족한 값을 겨냥해 본다


REFUSAL_REASONS = frozenset({Reason.OUT_OF_SCOPE, Reason.PART_MISSING, Reason.REVISION_MISSING, Reason.NOT_FOUND,
                             Reason.LIMIT_REACHED, Reason.VERIFY_FAILED, Reason.SEARCH_ERROR})
RETRY_REASONS = frozenset({Reason.NO_RESULT, Reason.ALL_REJECTED, Reason.PARTIAL})


class Decision(BaseModel):
    """Supervisor의 결정서: 다음에 누구에게 맡길지(또는 끝낼지)."""
    next: NextNode  # [왜] Literal이라 LLM이 목록 밖 이름을 내면 pydantic 검사에서 걸러진다
    question_type: QuestionType | None = None  # 처음 판단에서 정한 질문 종류. 판정 에이전트가 필요한지가 이걸로 갈린다
    reason: Reason | None = None  # 거절이면 필수. 재시도면 지난 실패 사유를 담아 다음 시도가 다르게 하게 한다
    # [왜] 800자: Sonnet Supervisor가 300자를 넘는 지시를 써서 #38에서 3문항이 형식 검사로 실패했다(11-05 정운 결정). 사용자에게 보이지 않고 서브에이전트만 읽는다
    brief: str = Field(default='', max_length=800, description='다음 에이전트에게 줄 짧은 지시')
    reply: str = Field(default='', max_length=300, description='일상 대화(chat)로 끝낼 때 사용자에게 보여 줄 한국어 답')

    @model_validator(mode='after')
    def refuse_needs_refusal_reason(self):
        if self.next == 'refuse' and self.reason not in REFUSAL_REASONS:
            raise ValueError('거절에는 거절 사유(REFUSAL_REASONS)가 필요하다')
        if self.next == 'finish' and self.question_type == 'chat' and not self.reply.strip():
            raise ValueError('일상 대화로 끝내려면 reply가 필요하다')  # [왜] 이 길은 작성 에이전트를 거치지 않아 Supervisor의 reply가 곧 답이다
        return self


class AgentReport(BaseModel):
    """서브에이전트의 보고서: Supervisor가 읽는 요약. 청크 원문은 담지 않는다."""
    agent: AgentName
    status: Literal['ok', 'partial', 'fail']  # 검색: 충분 · 부분 · 부족 / 검증: 통과 · 실패 처럼 에이전트마다 같은 세 칸으로 쓴다
    summary: str = Field(max_length=MAX_SUMMARY)
    evidence_ids: list[str] = Field(default_factory=list)  # 근거 청크 번호(원문은 상태에 두고 번호만 올린다)
    missing: list[str] = Field(default_factory=list)       # 부족한 값 이름(예: VRRM)
    reason: Reason | None = None                            # 실패면 사유


class Counters(BaseModel):
    """지금까지 센 것. Supervisor가 한도를 넘기지 않았는지 보는 데 쓴다."""
    hops: int = 0      # Supervisor 판단 횟수
    searches: int = 0  # 검색 횟수
    writes: int = 0    # 작성 횟수
    recent: list[Reason] = Field(default_factory=list)  # 최근 검색 실패 사유(같은 사유가 반복됐는지 본다)


def check_limit(c: Counters, next_node: str) -> Reason | None:
    """다음 노드로 가면 한도를 넘는지 본다. 넘으면 그 대신 거절할 이유를, 아니면 None을 돌려준다."""
    if next_node in ('finish', 'refuse'):
        return None  # [왜] 끝내는 길까지 막으면 한도에 닿은 뒤 정상 종료도 못 한다
    if c.hops >= MAX_HOPS:
        return Reason.LIMIT_REACHED
    if next_node == 'search' and c.searches >= MAX_SEARCHES:
        # 같은 사유로 두 번 실패했으면 코퍼스에 없다고 추정하고(NOT_FOUND), 사유가 섞였으면 한도 도달로 본다
        last_two = c.recent[-2:]
        same = len(last_two) == 2 and last_two[0] == last_two[1] and last_two[0] in RETRY_REASONS
        return Reason.NOT_FOUND if same else Reason.LIMIT_REACHED
    if next_node == 'writer' and c.writes >= MAX_WRITES:
        return Reason.VERIFY_FAILED
    return None
