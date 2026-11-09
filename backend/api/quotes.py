"""사람 승인 뒤의 견적·승인 사례 API. 가격·재고는 받지 않는다."""
import re
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend import auth
from backend.errors import ApiError
from backend.services.quote import InvalidApproval, QuoteNotFound, QuoteService

router = APIRouter(prefix='/api', tags=['quotes'])


class ApproveBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    candidate_part: str = Field(min_length=1, max_length=100)
    verdict: Literal['IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT']

    @field_validator('candidate_part')
    @classmethod
    def valid_part(cls, value):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}', value):
            raise ValueError('invalid part')
        return value


class QuoteBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    quantity: int = Field(ge=1, le=100000)


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


@router.post('/messages/{message_id}/approvals', status_code=201, dependencies=[Depends(auth.check_origin)])
def approve(message_id: int, body: ApproveBody, user_id: int = Depends(auth.current_user_id), quotes=Depends(service)):
    return quotes.approve(user_id, message_id, body.candidate_part, body.verdict)


@router.post('/approvals/{approval_id}/quotes', status_code=201, dependencies=[Depends(auth.check_origin)])
def create_quote(approval_id: int, body: QuoteBody, user_id: int = Depends(auth.current_user_id), quotes=Depends(service)):
    return quotes.create_quote(user_id, approval_id, body.quantity)


@router.get('/projects/{project_id}/quotes')
def list_quotes(project_id: int, user_id: int = Depends(auth.current_user_id), quotes=Depends(service)):
    return quotes.list_quotes(user_id, project_id)


@router.get('/approved-cases')
def list_cases(user_id: int = Depends(auth.current_user_id), quotes=Depends(service)):
    return quotes.list_cases(user_id)


@router.delete('/approved-cases/{case_id}', status_code=204, dependencies=[Depends(auth.check_origin)])
def delete_case(case_id: int, user_id: int = Depends(auth.current_user_id), quotes=Depends(service)):
    quotes.delete_case(user_id, case_id)
    return Response(status_code=204)
