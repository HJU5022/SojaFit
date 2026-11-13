"""내 설정(사용자 사실 기억) HTTP 경계: `GET · PATCH · DELETE /api/me/memory`와 탈퇴 `DELETE /api/me`.

- 로그인 사용자만 쓴다. 사용자 id는 세션에서만 오고, 본문의 사용자 id · 모르는 칸은 공통 422다.
- 바꾸는 요청(PATCH · DELETE)은 다른 상태 변경 경로처럼 Origin을 확인한다(다르면 403). PATCH는 탈퇴가 진행 중이면 409다.
- 기억은 분석 저장소(`THREADS_ENABLED=1`의 `app.state.conversations.profile`)에 있다. 없으면 공통 503.
- 탈퇴는 분석 기록 → Store → 계정 순서로 지우고 지운 건수를 돌려준다. 관리자는 409.
- 화면 쪽 짝: `frontend/src/api/profile.ts`(탈퇴 `deleteAccount`만 `frontend/src/api/auth.ts`에 있다).
하지 않는 일: 칸 검사 · 문장 만들기 · Store 쓰기 · 의미 검색(`backend/conversations/profile.py`), 대화에서 사실 뽑기,
  분석 기록 지우기(`Conversations.account_deletion`) · 계정 행 지우기(`backend/auth.py`의 `delete_account`).
출처: SPEC.md 8.5절, docs/specs/user-thread-memory.md "사용자 사실 기억"(탈퇴 `DELETE /api/me` 줄 포함).
"""
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from backend import auth

router = APIRouter(prefix='/api/me', tags=['profile'])


def _profile_module():
    """기억 기능을 실제로 사용할 때만 LangGraph 기반 모듈을 불러온다."""
    from backend.conversations import profile
    return profile


class ProfileUpdate(BaseModel):
    """바꿀 칸만 보낸다. 세 칸 밖의 이름(사용자 id 포함)은 422다."""
    model_config = ConfigDict(extra='forbid', strict=True,
                              json_schema_extra={'examples': [{'affiliation': '예시전자 회로설계팀', 'job_role': 'design', 'mounting_preference': 'smd'}]})
    affiliation: str | None = None
    job_role: str | None = None
    mounting_preference: str | None = None

    @field_validator('affiliation', 'job_role', 'mounting_preference')
    @classmethod
    def allowed(cls, value, info: ValidationInfo):
        return value if value is None else _profile_module().clean(info.field_name, value)


Kind = Literal['affiliation', 'job_role', 'mounting_preference']


class ProfileFact(BaseModel):
    """사실 한 칸(`backend/conversations/profile.py`의 update가 Store에 쓰는 값 그대로)."""
    kind: Kind
    value: str
    text: str  # 코드가 정한 틀로 만든 한국어 문장
    version: int
    updated_at: str  # [왜] Store에 ISO 문자열로 저장한다. datetime으로 두면 다시 써서 모양이 바뀐다
    source: str


class Deleted(BaseModel):
    """탈퇴로 지운 건수. 키: analysis_threads · analysis_circuits · checkpoints · memory_items · projects · quotes · account."""

    deleted: dict[str, int]


def conversation_service(request: Request):
    service = getattr(request.app.state, 'conversations', None)
    if service is None:
        raise HTTPException(503, '분석 저장소가 준비되지 않았습니다.')
    return service


def profile_memory(request: Request):
    """분석 저장소의 사용자 사실 기억. 서비스가 없으면 공통 503."""
    service = getattr(request.app.state, 'conversations', None)
    if service is None:
        raise HTTPException(503, '분석 저장소가 준비되지 않았습니다.')
    return service.profile


@router.get('/memory', response_model=list[ProfileFact])
def read_memory(q: str | None = Query(default=None, min_length=1, max_length=500),
                user_id: int = Depends(auth.current_user_id), memory=Depends(profile_memory)):
    """내 사실(최대 3개). q를 주면 의미가 가까운 순(색인이 꺼져 있으면 순위 없이)."""
    # shortcut: q 검색마다 Voyage 임베딩을 한 번 부르고 사용자별 호출 한도는 없다. 남용이 보이면 분석 입장 간격 한도를 같이 건다
    return memory.facts(user_id, q)


@router.patch('/memory', response_model=list[ProfileFact], dependencies=[Depends(auth.check_origin)])
def update_memory(body: ProfileUpdate, request: Request, user_id: int = Depends(auth.current_user_id), memory=Depends(profile_memory)):
    """보낸 칸만 덮어쓰고(version 올림) 바뀐 뒤 내 사실 목록을 돌려준다. 탈퇴 중이면 409."""
    # [왜] 탈퇴가 Store를 지운 뒤 이 쓰기가 끼어들면 지운 계정의 사실이 남는다. 계정 공유 잠금 안에서 쓴다
    with request.app.state.conversations.account_writer(user_id):
        return memory.update(user_id, body.model_dump(exclude_none=True))


@router.delete('/memory', status_code=204, dependencies=[Depends(auth.check_origin)])
def delete_memory(kind: Kind | None = None,
                  user_id: int = Depends(auth.current_user_id), memory=Depends(profile_memory)):
    """kind 한 칸 또는(없으면) 내 사실 전부를 지운다."""
    memory.delete(user_id, kind)


@router.delete('', response_model=Deleted)
def delete_me(request: Request, response: Response, user: tuple[int, str] = Depends(auth.current_user)):
    """탈퇴: 로그인 사용자의 기록을 먼저, 계정을 마지막에 지우고 지운 건수를 돌려준다(SPEC 8.5, 개인정보 보호법 37조 동의 철회)."""
    # [주의] 403 Origin 불일치, 409 관리자 · 진행 중 분석, 503 분석 저장소 없음 · 일부만 지움(다시 요청하면 남은 것부터 이어서 지움)
    auth.check_origin(request)
    if user[1] != "user":
        raise HTTPException(status_code=409, detail="관리자 계정은 이 기능으로 삭제할 수 없습니다.")
    try:
        with conversation_service(request).account_deletion(user[0]) as deleted:
            deleted.update(auth.delete_account(user[0]))  # 계정은 마지막: 앞에서 실패하면 계정이 남아 다시 요청할 수 있다
    except (psycopg.Error, PoolTimeout, OSError):
        raise HTTPException(status_code=503, detail="계정 삭제를 끝내지 못했습니다. 다시 요청하면 남은 기록부터 이어서 지웁니다.") from None
    response.delete_cookie(auth.COOKIE, path="/")
    return {"deleted": deleted}
