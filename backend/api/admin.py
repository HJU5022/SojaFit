"""관리자 계정 관리 HTTP 경계: `GET /api/admin/users`, `PATCH /api/admin/users/{target_id}`.

- 관리자인지 · 대상이 일반 계정인지는 `backend/auth.py`(`admin_users` · `admin_set_active`)가 확인한다(아니면 403, 대상 없음 404).
- 화면 쪽 짝: `frontend/src/api/admin.ts`.
하지 않는 일: 관리자 계정 만들기 · 지우기(운영자 CLI `python -m backend.auth`), Google 관리자 로그인(`backend/api/auth.py`).
출처: SPEC.md 4절 · 8.6절, docs/specs/login-auth.md.
"""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, StrictBool

from backend import auth
from backend.api.auth import Ok

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
