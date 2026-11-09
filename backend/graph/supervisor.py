"""Supervisor V0가 공유하는 입력·출력·라우팅 의미 계약."""

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict


QuestionType = Literal[
    "out_of_scope",
    "insufficient_information",
    "candidate_judge",
    "candidate_find",
    "role",
    "rating",
]
EvidenceType = Literal["circuit", "datasheet", "approved_case"]
NextAction = Literal["circuit_agent", "search_agent", "judge_answer_agent", "refuse"]
ReasonCode = Literal[
    "OUT_OF_SCOPE",
    "INSUFFICIENT_INFORMATION",
    "CANDIDATE_JUDGE",
    "CANDIDATE_FIND",
    "ROLE",
    "RATING",
]

EVIDENCE_ORDER = ("circuit", "datasheet", "approved_case")
REASON_BY_TYPE = {
    "out_of_scope": "OUT_OF_SCOPE",
    "insufficient_information": "INSUFFICIENT_INFORMATION",
    "candidate_judge": "CANDIDATE_JUDGE",
    "candidate_find": "CANDIDATE_FIND",
    "role": "ROLE",
    "rating": "RATING",
}


class SupervisorDecision(BaseModel):
    """후보 모델 세 종이 반환하는 공통 네 필드."""

    model_config = ConfigDict(extra="forbid")

    question_type: QuestionType
    required_evidence: list[EvidenceType]
    next_action: NextAction
    reason_code: ReasonCode


def build_input_envelope(
    user_request: str,
    *,
    current_state: dict | None = None,
    external_material: list | None = None,
) -> dict:
    """사용자 요청, 실행 상태, 외부 자료를 섞지 않은 모델 입력을 만든다."""

    return {
        "user_request": user_request,
        "current_state": current_state if current_state is not None else {
            "completed_actions": [],
            "available_evidence": [],
            "last_result": None,
            "failures": [],
            "retry_exhausted": False,
        },
        "external_material": external_material if external_material is not None else [],
    }


def render_chat_input(envelope: dict) -> str:
    """Chat Completions에 보낼 envelope를 안정적인 JSON 문자열로 만든다."""

    return json.dumps(envelope, ensure_ascii=False, sort_keys=True)


def _expected_action(decision: SupervisorDecision, state: dict) -> str:
    if decision.question_type in {"out_of_scope", "insufficient_information"}:
        return "refuse"
    if state.get("retry_exhausted") is True:
        return "refuse"
    if decision.question_type == "role":
        return "circuit_agent"

    available = set(state.get("available_evidence", []))
    missing = [item for item in decision.required_evidence if item not in available]
    if "circuit" in missing:
        return "circuit_agent"
    if missing:
        return "search_agent"
    return "judge_answer_agent"


def semantic_errors(decision: SupervisorDecision, state: dict) -> list[str]:
    """스키마로 잡을 수 없는 근거 순서·사유·상태 라우팅 모순을 찾는다."""

    errors = []
    ordered = [item for item in EVIDENCE_ORDER if item in decision.required_evidence]
    if decision.required_evidence != ordered:
        errors.append("evidence_order")
    if decision.reason_code != REASON_BY_TYPE[decision.question_type]:
        errors.append("reason_code")
    if decision.next_action != _expected_action(decision, state):
        errors.append("next_action")
    return errors


def build_jev_question_contract() -> dict:
    """Jev Decisions API가 공통 의미 계약을 선택형 질문으로 받게 한다."""

    return {
        "question_type": {
            "type": "choice",
            "instructions": "사용자 요청의 주된 질문 유형을 우선순위에 따라 하나 고르세요.",
            "criteria": {
                "out_of_scope": "요청 전체가 다이오드 교체·회로 역할·정격 확인 범위 밖",
                "insufficient_information": "범위 안이지만 대상 또는 질문 목적이 부족함",
                "candidate_judge": "특정 후보 품번의 대체 가능성을 물음",
                "candidate_find": "후보 품번 없이 대체 후보를 요청함",
                "role": "대상 다이오드의 회로 역할·연결·전류 경로를 물음",
                "rating": "특정 다이오드의 정격·특성·시험 조건·패키지·개정판을 물음",
            },
        },
        "needs_circuit": {
            "type": "choice",
            "instructions": "답변에 회로 근거가 필요합니까?",
            "criteria": {"yes": "필요함", "no": "필요하지 않음"},
        },
        "needs_datasheet": {
            "type": "choice",
            "instructions": "답변에 데이터시트 근거가 필요합니까?",
            "criteria": {"yes": "필요함", "no": "필요하지 않음"},
        },
        "needs_approved_case": {
            "type": "choice",
            "instructions": "사용자가 승인한 과거 사례가 필요합니까?",
            "criteria": {"yes": "필요함", "no": "필요하지 않음"},
        },
        "next_action": {
            "type": "choice",
            "instructions": "현재 상태에서 다음 실행 경로를 하나 고르세요.",
            "criteria": {
                "circuit_agent": "회로 역할과 연결 근거를 확인",
                "search_agent": "데이터시트 또는 승인 사례 근거를 검색",
                "judge_answer_agent": "준비된 근거로 판정하고 사용자 답변을 작성",
                "refuse": "범위 밖·정보 부족·재시도 소진으로 단서 요청 또는 거절",
            },
        },
    }
