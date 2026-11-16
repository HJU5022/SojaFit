"""관리자 계정 관리 HTTP 경계: 계정 목록 · 활성 상태 변경 · 이메일 가림 해제 · 탈퇴 처리 · 작업 이력(`/api/admin/*`).

- 관리자인지 · 대상이 일반 계정인지는 `backend/auth.py`(`admin_users` · `admin_set_active` · `admin_unmask` · `admin_check_deletable` · `admin_audit_log`)가 확인한다(아니면 403, 대상 없음 404).
- 바꾸는 요청과 가림 해제(POST)는 Origin을 확인한다. 가림 해제 · 정지 · 재활성화 · 탈퇴 처리는 `admin_audit`(db/034)에 한 줄씩 남는다.
- 탈퇴 처리는 본인 탈퇴(`backend/api/profile.py`의 `erase_account`)와 같은 순서로 지운다. 관리자 계정 · 자기 자신은 지우지 않는다.
- 화면 쪽 짝: `frontend/src/api.ts`, 화면 `frontend/src/Admin.tsx`.
하지 않는 일: 관리자 계정 만들기 · 비활성화(운영자 CLI `python -m backend.auth`), Google 관리자 로그인(`backend/api/auth.py`), 이메일 원문 로그.
출처: SPEC.md 4절 · 8.6절, docs/specs/login-auth.md.
"""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, StrictBool, field_validator

from backend import auth
from backend.api.auth import Ok
from backend.api.profile import Deleted, erase_account

router = APIRouter(prefix='/api/admin', tags=['admin'])


class Account(BaseModel):
    id: int
    email: str  # 사용자명을 가린 이메일(auth.mask_email)
    role: Literal["admin", "user"]
    is_active: bool


class Accounts(BaseModel):
    users: list[Account]


class AccountState(BaseModel):
    """계정 활성 상태 변경 요청 본문. 모르는 칸은 공통 422다."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"is_active": False}]})
    # [왜] StrictBool이라 "false" 같은 문자열이 True로 해석되는 일을 막는다
    is_active: StrictBool


class Unmask(BaseModel):
    """가림 해제 사유. 겹친 공백을 한 칸으로 줄이고 앞뒤를 뗀 뒤 5~500자가 아니면 공통 422(이력도 남지 않는다)."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"reason": "사용자 문의 응대를 위해 가입 이메일 확인"}]})
    reason: str

    @field_validator("reason")
    @classmethod
    def five_to_500(cls, value):
        value = " ".join(value.split())  # [왜] 공백만 적은 사유가 길이 검사를 지나가지 않게 먼저 줄인다
        if not 5 <= len(value) <= 500:
            raise ValueError("reason must be 5-500 characters")
        return value


class Unmasked(BaseModel):
    email: str  # 원문. 화면만 잠깐 보이고 저장 · 로그하지 않는다


class AuditEntry(BaseModel):
    id: int
    actor_id: int
    actor_email: str  # 처리한 관리자(가림)
    target_id: int
    target_email: str  # 대상(가림). 탈퇴 처리로 계정이 지워져도 남는다
    action: Literal["unmask", "deactivate", "activate", "delete"]
    fields: list[str]  # 가림 해제로 연 칸(지금은 email뿐)
    reason: str | None
    created_at: datetime


@router.get("/users", response_model=Accounts)
def admin_users(user_id: int = Depends(auth.current_user_id)):
    """관리자 전용 계정 목록을 반환하고 이메일 사용자명을 마스킹한다."""
    users = auth.admin_users(user_id)
    return {"users": [{**user, "email": auth.mask_email(user["email"])} for user in users]}

@router.patch("/users/{target_id}", response_model=Ok)
def admin_set_active(target_id: int, body: AccountState, request: Request, user_id: int = Depends(auth.current_user_id)):
    """일반 계정(user)을 활성화·비활성화한다(관리자 전용)."""
    # [주의] 403 Origin 불일치·관리자 아님·대상이 관리자, 404 대상 없음. 비활성화하면 auth가 그 계정의 세션도 지운다
    auth.check_origin(request)
    auth.admin_set_active(user_id, target_id, body.is_active)
    return {"ok": True}


@router.post("/users/{target_id}/unmask", response_model=Unmasked)
def admin_unmask(target_id: int, body: Unmask, request: Request, response: Response, user_id: int = Depends(auth.current_user_id)):
    """사유를 이력에 남기고 계정 한 명의 이메일 원문을 돌려준다(관리자 전용). 이력을 못 쓰면 원문도 주지 않는다."""
    auth.check_origin(request)
    email = auth.admin_unmask(user_id, target_id, body.reason)
    response.headers["Cache-Control"] = "no-store"
    return {"email": email}


@router.delete("/users/{target_id}", response_model=Deleted)
def admin_delete_user(target_id: int, request: Request, user_id: int = Depends(auth.current_user_id)):
    """일반 계정을 탈퇴 처리한다(관리자 전용). 분석 기록 → Store → 계정 순서로 지우고 지운 건수를 돌려준다."""
    # [주의] 403 Origin · 관리자 아님 · 대상이 관리자 · 자기 자신, 404 대상 없음은 기록을 하나도 지우기 전에 낸다. 409 대상의 분석이 도는 중, 503 일부만 지움
    auth.check_origin(request)
    auth.admin_check_deletable(user_id, target_id)
    return {"deleted": erase_account(request, target_id, user_id)}


@router.get("/audit", response_model=list[AuditEntry])
def admin_audit(response: Response, user_id: int = Depends(auth.current_user_id)):
    """관리자 작업 이력(가림 해제 · 정지 · 재활성화 · 탈퇴 처리)을 최근 100건까지 최근 순으로."""
    response.headers["Cache-Control"] = "no-store"
    return auth.admin_audit_log(user_id)
