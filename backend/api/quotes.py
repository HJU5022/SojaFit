"""사람 승인 뒤의 견적·승인 사례 API. 가격·재고는 받지 않는다."""
from datetime import datetime
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend import auth
from backend.errors import ApiError
from backend.services.quote import InvalidApproval, QuoteNotFound, QuoteService

router = APIRouter(prefix='/api', tags=['quotes'])


Approvable = Literal['IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT']  # 사람이 승인할 수 있는 판정 3종


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra='forbid', json_schema_extra={'examples': [{'candidate_part': '1N5819', 'verdict': 'SPEC_EQUIVALENT'}]})
    candidate_part: str = Field(min_length=1, max_length=100)
    verdict: Approvable

    @field_validator('candidate_part')
    @classmethod
    def valid_part(cls, value):
        # [왜] 후보 이름은 판정 결과가 보여 준 그대로('TSC 1N4007G')라 공백이 들어온다. 이 값은 저장된 판정 결과의 후보와 정확히 같아야만
        #      쓰이고(approval_snapshot), 견적용 식별 품번은 서버가 따로 만든다(quote.part_number). 여기서는 제어 문자와 빈 값만 거른다
        if not value.strip() or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            raise ValueError('invalid part')
        return value


class QuoteBody(BaseModel):
    model_config = ConfigDict(extra='forbid', json_schema_extra={'examples': [{'quantity': 100}]})
    quantity: int = Field(ge=1, le=100000)


# 응답 본문. 칸은 backend/services/quote.py가 만드는 dict와 frontend/src/api.ts의 타입과 같다. 가격 · 재고 칸은 없다
class Approval(BaseModel):
    id: int
    message_id: int
    candidate_part: str
    part_number: str
    verdict: Approvable
    case_id: int  # 함께 만든 승인 사례 id
    created_at: datetime


class Quote(BaseModel):
    id: int
    approval_id: int
    part_number: str
    quantity: int
    created_at: datetime


class SavedApproval(Approval):
    case_id: int | None  # 응답 형식은 유지하며 조회에는 활성 사례가 있는 승인만 반환한다(사례를 지우면 승인 기록은 남아도 목록에서 빠져 다시 승인할 수 있다).
    quotes: list[Quote]  # [왜] 새로고침 뒤 화면이 이 승인의 마지막 견적을 다시 보여 준다(가격 칸 없음, ADR 0009)


class QuoteListItem(Quote):
    thread_id: str  # 견적이 나온 검토(대화). 화면이 그 검토로 돌아가는 링크에 쓴다


class ApprovedCase(BaseModel):
    id: int
    approval_id: int
    candidate_part: str
    verdict: Approvable
    created_at: datetime


def service():
    try:
        yield QuoteService()
    except QuoteNotFound:
        raise HTTPException(404, '승인 자료를 찾을 수 없습니다.') from None
    except (InvalidApproval, psycopg.errors.UniqueViolation):
        # [왜] 화면은 이 코드면 승인을 다시 보내지 않는다(ADR 0019). 완료 판정이 아닌 경우와 같은 메시지 승인 두 번을 한 코드로 둔다
        raise ApiError(409, '승인할 수 없는 판정이거나 이미 승인되었습니다.', code='ALREADY_APPROVED') from None
    except (psycopg.Error, KeyError, TypeError):
        raise HTTPException(503, '승인·견적 서비스를 사용할 수 없습니다.') from None


@router.post('/messages/{message_id}/approvals', status_code=201, response_model=Approval, dependencies=[Depends(auth.check_origin)])
def approve(message_id: int, body: ApproveBody, user_id: int = Depends(auth.current_user_id), quotes=Depends(service)):
    return quotes.approve(user_id, message_id, body.candidate_part, body.verdict)


@router.get('/messages/{message_id}/approvals', response_model=list[SavedApproval])
def list_approvals(message_id: int, response: Response, user_id: int = Depends(auth.current_user_id), quotes=Depends(service)):
    response.headers['Cache-Control'] = 'no-store'
    return quotes.list_approvals(user_id, message_id)


@router.post('/approvals/{approval_id}/quotes', status_code=201, response_model=Quote, dependencies=[Depends(auth.check_origin)])
def create_quote(approval_id: int, body: QuoteBody, user_id: int = Depends(auth.current_user_id), quotes=Depends(service)):
    return quotes.create_quote(user_id, approval_id, body.quantity)


@router.get('/projects/{project_id}/quotes', response_model=list[QuoteListItem])
def list_quotes(project_id: int, user_id: int = Depends(auth.current_user_id), quotes=Depends(service)):
    return quotes.list_quotes(user_id, project_id)


@router.get('/approved-cases', response_model=list[ApprovedCase])
def list_cases(user_id: int = Depends(auth.current_user_id), quotes=Depends(service)):
    return quotes.list_cases(user_id)


@router.delete('/approved-cases/{case_id}', status_code=204, dependencies=[Depends(auth.check_origin)])
def delete_case(case_id: int, user_id: int = Depends(auth.current_user_id), quotes=Depends(service)):
    quotes.delete_case(user_id, case_id)
    return Response(status_code=204)
