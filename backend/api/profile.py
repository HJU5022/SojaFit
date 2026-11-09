"""내 설정(사용자 사실 기억) HTTP 경계: `GET · PATCH · DELETE /api/me/memory`.

- 로그인 사용자만 쓴다. 사용자 id는 세션에서만 오고, 본문의 사용자 id · 모르는 칸은 공통 422다.
- 바꾸는 요청(PATCH · DELETE)은 다른 상태 변경 경로처럼 Origin을 확인한다(다르면 403).
- 기억은 분석 저장소(`THREADS_ENABLED=1`의 `app.state.conversations.profile`)에 있다. 없으면 공통 503.
하지 않는 일: 칸 검사 · 문장 만들기 · Store 쓰기 · 의미 검색(`backend/conversations/profile.py`), 대화에서 사실 뽑기.
출처: SPEC.md 8.5절, docs/specs/user-thread-memory.md "사용자 사실 기억".
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from backend import auth
from backend.conversations import profile

router = APIRouter(prefix='/api/me', tags=['profile'])


class ProfileUpdate(BaseModel):
    """바꿀 칸만 보낸다. 세 칸 밖의 이름(사용자 id 포함)은 422다."""
    model_config = ConfigDict(extra='forbid', strict=True)
    affiliation: str | None = None
    job_role: str | None = None
    mounting_preference: str | None = None

    @field_validator('affiliation', 'job_role', 'mounting_preference')
    @classmethod
    def allowed(cls, value, info: ValidationInfo):
        return value if value is None else profile.clean(info.field_name, value)


def profile_memory(request: Request):
    """분석 저장소의 사용자 사실 기억. 서비스가 없으면 공통 503."""
    service = getattr(request.app.state, 'conversations', None)
    if service is None:
        raise HTTPException(503, '분석 저장소가 준비되지 않았습니다.')
    return service.profile


@router.get('/memory')
def read_memory(q: str | None = Query(default=None, min_length=1, max_length=500),
                user_id: int = Depends(auth.current_user_id), memory=Depends(profile_memory)):
    """내 사실(최대 3개). q를 주면 의미가 가까운 순(색인이 꺼져 있으면 순위 없이)."""
    # shortcut: q 검색마다 Voyage 임베딩을 한 번 부르고 사용자별 호출 한도는 없다. 남용이 보이면 분석 입장 간격 한도를 같이 건다
    return memory.facts(user_id, q)


@router.patch('/memory', dependencies=[Depends(auth.check_origin)])
def update_memory(body: ProfileUpdate, user_id: int = Depends(auth.current_user_id), memory=Depends(profile_memory)):
    """보낸 칸만 덮어쓰고(version 올림) 바뀐 뒤 내 사실 목록을 돌려준다."""
    return memory.update(user_id, body.model_dump(exclude_none=True))


@router.delete('/memory', status_code=204, dependencies=[Depends(auth.check_origin)])
def delete_memory(kind: Literal['affiliation', 'job_role', 'mounting_preference'] | None = None,
                  user_id: int = Depends(auth.current_user_id), memory=Depends(profile_memory)):
    """kind 한 칸 또는(없으면) 내 사실 전부를 지운다."""
    memory.delete(user_id, kind)
