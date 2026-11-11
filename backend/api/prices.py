"""가격 · 재고 HTTP 경계: `GET /api/prices`(로그인 필요, 요청 때 Mouser를 한 번 조회).

- 화면 쪽 짝: `frontend/src/api/prices.ts`.
하지 않는 일: Mouser 호출 · 응답 거르기 · 호출 상한(`backend/services/mouser.py`), 결과 저장 · 캐시 · 로그(ADR 0009, 하지 않는다).
출처: SPEC.md 4절 · 6절 · 7절 · 8.4절, ADR 0009.
읽는 환경변수: DEMO_MODE(기본 1, 1이면 Mouser를 부르지 않음).
"""
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from backend import auth
from backend.services import mouser

router = APIRouter(prefix='/api', tags=['prices'])


# [왜] 가격 칸은 Mouser 응답에서 그대로 옮긴 값이라 모두 null을 허용한다(형식이 다르면 mouser.py가 bad_response로 거른다)
class PriceBreak(BaseModel):
    quantity: int | None
    price: str | None
    currency: str | None


class PricePart(BaseModel):
    part_number: str | None
    manufacturer: str | None
    price_breaks: list[PriceBreak]
    availability: str | None
    product_url: str | None


class PricesAvailable(BaseModel):
    available: Literal[True]
    source: str
    fetched_at: str  # 조회 시각(UTC ISO 8601)
    parts: list[PricePart]


class PricesUnavailable(BaseModel):
    """키 없음 · 데모 모드 · 호출 상한 · Mouser 실패. parts는 늘 빈 목록이다."""

    available: Literal[False]
    source: str
    reason: str
    message: str
    parts: list[PricePart]


def price_unavailable(reason: str) -> dict:
    """Mouser 값 없이 돌려주는 모양(SPEC 4절). reason: demo_mode 또는 `mouser.MouserError.kind`."""
    message = "데모 모드라 Mouser 가격·재고를 조회하지 않아요." if reason == "demo_mode" else "지금은 Mouser 가격·재고를 불러올 수 없어요."
    return {"available": False, "source": mouser.SOURCE, "reason": reason, "message": message, "parts": []}


@router.get("/prices", dependencies=[Depends(auth.current_user_id)], response_model=PricesAvailable | PricesUnavailable)
def prices(response: Response, parts: str = Query(min_length=1, max_length=450, description="쉼표로 나눈 품번 1~10개")):
    """로그인한 사용자에게 후보 품번의 Mouser 가격·재고를 요청 때 한 번 조회해 돌려준다(SPEC 4절).

    [주의] ADR 0009: 결과는 이 응답으로만 내보내고 저장 · 캐시 · 로그하지 않는다. 그래서 이 함수는 아무것도 로그에 쓰지 않고,
    브라우저 · 중간 캐시도 남기지 않게 `Cache-Control: no-store`를 붙인다. 그래프는 이 API를 부르지 않는다.
    """
    response.headers["Cache-Control"] = "no-store"
    names = list(dict.fromkeys(p.strip() for p in parts.split(",") if p.strip()))  # 같은 품번은 한 번만
    try:
        mouser.check_parts(names)  # [왜] 데모 모드에서도 같은 입력 규칙(422)을 쓴다. Mouser를 부르기 전에 거른다
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error), headers={"Cache-Control": "no-store"}) from None
    if os.getenv("DEMO_MODE", "1") == "1":
        return price_unavailable("demo_mode")  # SPEC 7절: 데모 모드는 Mouser 칸을 비운다
    try:
        return {"available": True, **mouser.search_parts(names)}
    except mouser.MouserError as error:
        return price_unavailable(error.kind)  # [주의] 오류를 로그에 쓰지 않는다. 종류만 화면에 알린다
