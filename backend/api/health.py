"""서비스 생존 확인 `GET /health`.

호출자: 배포 환경(Cloud Run)과 평가자, `scripts/smoke/http_smoke.py` 1단계.
하지 않는 일: DB · 분석 서비스 상태 확인(늘 {"status": "ok"}), 로그인 확인.
출처: SPEC.md 4절, docs/GATES.md G1·G2.
"""
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=['health'])


class Health(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=Health)
def health():
    """서비스 생존 확인용. 배포 환경과 평가자가 부르며 항상 {"status": "ok"}를 돌려준다."""
    return {"status": "ok"}
