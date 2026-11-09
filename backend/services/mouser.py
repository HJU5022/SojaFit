"""Mouser Search API 가격·재고 조회 클라이언트. 응답은 저장하지 않는다(ADR 0009).

- 역할: 품번 1~10개를 Mouser Search API 품번 검색(`POST /api/v1/search/partnumber`)에 한 번 보내고, 화면에 필요한 칸
  (품번 · 제조사 · 수량별 가격과 통화 · 재고 표시 · 상품 주소)과 조회 시각만 골라 돌려준다. 프로세스당 호출 횟수에 상한을 둔다.
  호출자: backend/main.py `GET /api/prices`(요청 때마다), tests/services/test_mouser.py · tests/api/test_prices.py(가짜 transport).
- 하지 않는 일: 응답 저장 · 캐시 · 로그(DB · 파일 · 로그 · 그래프 상태 어디에도 남기지 않는다), 재시도, 그래프 안에서 부르기(그래프는 품번만 정한다),
  데모 모드 판단(`/api/prices`가 한다), 제조사 거르기 · 가격 비교.
- 출처: SPEC 4절(가격·재고 계약) · 6절(Mouser), ADR 0009, Mouser Search API v1 문서(https://api.mouser.com/api/docs/V1, 11-06 확인:
  키는 `apiKey` 쿼리, 품번은 `|`로 이어 10개까지, 품번마다 3~40자, 응답 `Errors` · `SearchResults.Parts[]`).
- 읽는 환경변수: MOUSER_API_KEY(비면 `no_key` 오류).

[주의] 문서가 키를 요청 주소(쿼리)에 넣게 한다. 그래서 요청 주소와 httpx 예외(요청 주소를 담는다)를 로그 · 오류 문구에 넣지 않는다.
httpx가 INFO로 남기는 "HTTP Request: POST <주소>" 줄은 아래 `_HideMouserRequest` 필터가 막는다.
"""
import logging
import os
import re
import threading
from datetime import datetime, timezone

import httpx

URL = "https://api.mouser.com/api/v1/search/partnumber"
SOURCE = "Mouser Electronics"  # 화면에 붙이는 출처 표기(약관 5절, ADR 0009)
MAX_PARTS = 10  # [왜] Mouser 품번 검색이 한 번에 받는 품번 수 상한(문서)
PART = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .\-/+#]{2,39}")  # 품번 하나: 3~40자(문서). `|`는 품번 구분자라 받지 않는다
TIMEOUT = httpx.Timeout(10.0, connect=5.0)  # [왜] 화면이 기다릴 수 있는 시간. 넘으면 다시 부르지 않고 실패로 끝낸다
# shortcut: 프로세스가 살아 있는 동안의 누적 상한이라 날이 바뀌어도 줄지 않고 Cloud Run 인스턴스마다 따로 센다. Mouser 한도를 확인하면 일 단위로 바꾼다
MAX_CALLS = 300  # [왜] AGENTS 6번(루프 · 호출 상한). 화면이 고장 나 계속 불러도 키 한도를 다 쓰지 않게 한다(값은 추정)
_calls = 0       # 이 프로세스에서 Mouser에 보낸 요청 수
_lock = threading.Lock()  # [왜] FastAPI는 동기 엔드포인트를 스레드 여러 개에서 돌린다. 세기와 비교 사이에 다른 요청이 끼지 않게 한다


class MouserError(RuntimeError):
    """조회 실패. 종류(kind)와 HTTP 상태만 담고 요청 주소 · 키 · 응답 원문은 담지 않는다."""

    def __init__(self, kind: str, status: int | None = None):
        super().__init__(kind if status is None else f"{kind} (HTTP {status})")
        self.kind, self.status = kind, status


class _HideMouserRequest(logging.Filter):
    """httpx 요청 로그 중 Mouser 주소가 든 줄을 버린다(주소에 키가 있다)."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "api.mouser.com" not in record.getMessage()


logging.getLogger("httpx").addFilter(_HideMouserRequest())  # [주의] 필터는 그 이름의 로거에 직접 남긴 줄에만 걸린다. httpx는 "httpx" 로거 하나에 남긴다


def check_parts(parts: list[str]) -> list[str]:
    """품번 목록이 Mouser 문서의 조건(1~10개, 3~40자, `|` 없음)에 맞는지 본다. 틀리면 ValueError(Mouser를 부르기 전에 막는다)."""
    if not 1 <= len(parts) <= MAX_PARTS or not all(PART.fullmatch(p) for p in parts):
        raise ValueError(f"품번은 1~{MAX_PARTS}개, 품번마다 3~40자(영문 · 숫자 · 공백 . - / + #)여야 합니다")
    return parts


def _pick(part: dict) -> dict:
    """Mouser 부품 하나에서 화면에 필요한 칸만 고른다. [왜] 나머지(설명 · 단종 여부 · 사진 등)는 쓰지 않으니 넘기지도 않는다."""
    return {"part_number": part.get("ManufacturerPartNumber"), "manufacturer": part.get("Manufacturer"),
            "price_breaks": [{"quantity": b.get("Quantity"), "price": b.get("Price"), "currency": b.get("Currency")}
                             for b in part.get("PriceBreaks") or []],
            "availability": part.get("Availability"), "product_url": part.get("ProductDetailUrl")}


def search_parts(parts: list[str], *, transport: httpx.BaseTransport | None = None) -> dict:
    """품번들을 Mouser에서 한 번 찾아 `{source, fetched_at, parts: [{part_number, manufacturer, price_breaks, availability, product_url}]}`를 돌려준다.

    transport는 시험이 가짜 응답을 넣는 자리다(None이면 실제 네트워크). 결과는 부른 쪽이 화면에 보여 주고 버린다(SPEC 4절).
    Raises:
        ValueError: 품번이 조건에 맞지 않을 때(`check_parts`). Mouser를 부르지 않는다.
        MouserError: kind가 no_key(키 없음) · limit(프로세스 상한) · timeout · network · bad_key(키 거부) · http(200이 아님) ·
            api_error(응답 Errors) · bad_response(형식이 다름). 어느 경우에도 다시 부르지 않는다.
    """
    global _calls
    check_parts(parts)
    key = os.getenv("MOUSER_API_KEY", "")
    if not key:
        raise MouserError("no_key")
    with _lock:
        if _calls >= MAX_CALLS:
            raise MouserError("limit")
        _calls += 1  # [왜] 응답을 받기 전에 센다. 실패한 요청도 Mouser 한도를 쓴다
    body = {"SearchByPartRequest": {"mouserPartNumber": "|".join(parts), "partSearchOptions": "None"}}
    try:
        # [왜] httpx.Client 기본 transport는 재시도하지 않는다(retries=0). 한 요청에 한 번만 보낸다
        with httpx.Client(timeout=TIMEOUT, transport=transport) as client:
            response = client.post(URL, params={"apiKey": key}, json=body)
    except httpx.TimeoutException:
        raise MouserError("timeout") from None  # [주의] from None: httpx 예외는 요청 주소(키 포함)를 담아 뒤따르는 traceback에 보인다
    except httpx.HTTPError:
        raise MouserError("network") from None
    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")  # 조회 시각. 화면이 출처 옆에 붙인다
    if response.status_code in (401, 403):
        raise MouserError("bad_key", response.status_code)
    if response.status_code != 200:
        raise MouserError("http", response.status_code)
    try:
        data = response.json()
        errors = data.get("Errors") or []
        if errors:
            # [왜] 키가 틀려도 200에 Errors로 올 수 있다. 오류 칸 이름(PropertyName)에 key가 있으면 키 거부로 본다(문구는 넘기지 않는다)
            raise MouserError("bad_key" if any("key" in str(e.get("PropertyName") or "").lower() for e in errors) else "api_error", 200)
        found = [_pick(p) for p in (data.get("SearchResults") or {}).get("Parts") or []]
    except (ValueError, AttributeError, TypeError):
        raise MouserError("bad_response", 200) from None  # JSON이 아니거나 칸 모양이 문서와 다름
    return {"source": SOURCE, "fetched_at": fetched_at, "parts": found}
