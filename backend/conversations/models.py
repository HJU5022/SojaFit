"""대화 식별자와 안전한 실행 결과의 내부 형식."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class SafeModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SafeCitation(SafeModel):
    document: str = ''
    page: int | str | None = None
    table: str = ''
    row: str = ''
    chunk_index: int | None = None
    chunk_id: str | int | None = None


class SafeEvidence(SafeModel):
    document: str = ''
    page: int | str | None = None
    table: str = ''
    row: str = ''
    section: str = ''
    citation_number: str = ''


class SafeCheck(SafeModel):
    code: str
    tier: str = ''
    op: str = ''
    basis: str = ''
    threshold: float | list[float] | None = None
    value: float | list[float] | None = None
    unit: str | None = None
    condition: str | None = None
    result: str = ''
    why: str = ''
    citation: SafeCitation | None = None


class SafeCandidate(SafeModel):
    part: str
    role: str = ''
    verdict: Literal['IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT', 'NOT_VERIFIED', 'NOT_SUFFICIENT']
    checks: list[SafeCheck] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    uncertain: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    board_change: bool | None = None
    package_citation: SafeCitation | None = None


class SafeTerm(SafeModel):
    code: str
    gte: float | None = None
    lte: float | None = None


class SafeInputCondition(SafeModel):
    code: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=200)

    @field_validator('code')
    @classmethod
    def known_input(cls, value):
        from backend.judge import conditions
        known = {name for rule in conditions.load().values() for name in conditions.inputs(rule)} | {'VF', 'IR'}
        if value not in known:
            raise ValueError('unknown input condition')
        return value


class SafeJudgement(SafeModel):
    kind: Literal['judge', 'find', 'no_rule']
    roles: list[str] = Field(default_factory=list)
    role_evidence: list[str] = Field(default_factory=list)
    results: list[SafeCandidate] = Field(default_factory=list)
    shown: list[SafeCandidate] = Field(default_factory=list)
    unverified: list[SafeCandidate] = Field(default_factory=list)
    terms: list[SafeTerm] = Field(default_factory=list)
    capped: bool = False
    preferred_mount: Literal['', 'smd', 'tht'] = ''  # 찾기 순서에 쓴 내 설정의 선호 실장 방식(SPEC 8.5). 없으면 ''


class SafeTargetChoice(SafeModel):
    """대상 부품 후보 하나(넷리스트의 지원 다이오드). 고르는 것은 사용자다(SPEC 8.8)."""
    ref: str = Field(pattern=r'^[Dd][0-9][A-Za-z0-9_.+-]{0,98}$')
    value: str = Field(default='', max_length=100)


class SafeInterrupt(SafeModel):
    missing: list[str] = Field(default_factory=list)
    role_choices: list[str] = Field(default_factory=list)
    question: str = ''
    target_choices: list[SafeTargetChoice] = Field(default_factory=list)  # 대상 부품을 물을 때만. 그때 missing · role_choices는 비었다


class SafePendingStart(SafeModel):
    """대상 부품을 물은 run의 첫 질문 · 사용 조건. 고른 부품으로 재개할 때 그대로 다시 보낸다(브라우저 결과에는 넣지 않는다)."""
    question: str = Field(max_length=4000)
    conditions: str = Field(default='', max_length=2000)


class SafeRunError(SafeModel):
    code: str
    message: str = Field(min_length=1, max_length=500)

    @field_validator('code')
    @classmethod
    def known_code(cls, value):
        from backend.errors import DEFAULT_CODES, SPECIAL_CODES
        if value not in set(DEFAULT_CODES.values()) | set(SPECIAL_CODES):
            raise ValueError('unknown public error code')
        return value


class SafeResult(SafeModel):
    answer: str = ''
    evidence: list[SafeEvidence] = Field(default_factory=list)
    question_type: str = ''
    price_parts: list[Annotated[str, Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}$')]] = Field(default_factory=list)
    interrupt: SafeInterrupt = Field(default_factory=SafeInterrupt)
    judgement: SafeJudgement | None = None
    error: SafeRunError | None = None
    # [왜] 대상을 고르기 전에는 분석 thread가 없어 사용 조건을 둘 곳이 이 run 기록뿐이다. result_dto는 이 칸을 고르지 않는다
    pending_start: SafePendingStart | None = None


RunStatus = Literal['running', 'requires_input', 'completed', 'refused', 'failed']
