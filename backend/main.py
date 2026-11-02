"""FastAPI entry point."""
import os
from pathlib import Path

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, StrictBool

from backend import auth

app = FastAPI(title="SojaFit API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def login_page():
    return (Path(__file__).parent / "web" / "login.html").read_text(encoding="utf-8")


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=1, max_length=1024)


@app.post("/api/auth/login")
def login(body: Login, request: Request, response: Response):
    auth.check_origin(request)
    try:
        result = auth.authenticate(body.email, body.password)
    except (psycopg.Error, KeyError):
        raise HTTPException(status_code=503, detail="로그인 서비스를 사용할 수 없습니다.") from None
    if result is None:
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호를 확인해 주세요.")
    token, user_id = result
    secure = os.environ.get("AUTH_ORIGIN", "http://localhost:8000").startswith("https://")
    response.set_cookie(auth.COOKIE, token, httponly=True, secure=secure, samesite="lax", max_age=8 * 3600, path="/")
    return {"user_id": user_id}


@app.get("/api/auth/me")
def me(user_id: int = Depends(auth.current_user_id)):
    return {"user_id": user_id}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    auth.check_origin(request)
    auth.logout(request)
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


class AccountState(BaseModel):
    is_active: StrictBool


@app.get("/api/admin/users")
def admin_users(user_id: int = Depends(auth.current_user_id)):
    return {"users": auth.admin_users(user_id)}


@app.patch("/api/admin/users/{target_id}")
def admin_set_active(target_id: int, body: AccountState, request: Request, user_id: int = Depends(auth.current_user_id)):
    auth.check_origin(request)
    auth.admin_set_active(user_id, target_id, body.is_active)
    return {"ok": True}
