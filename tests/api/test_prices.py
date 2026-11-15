"""가격·재고 API(`GET /api/prices`, backend/api/prices.py) 시험: 가짜 transport로 Mouser 없이 확인한다.

- 역할: 로그인 필요(401), `Cache-Control: no-store`, 데모 모드 · 키 없음 · 상한 · Mouser 실패의 "값 없음" 모양, 품번 개수 · 형식(422),
  응답이 화면 칸과 조회 시각만 담는지, 로그에 키 · 요청 주소 · Mouser 값이 남지 않는지 본다.
- 하지 않는 일: 실제 Mouser 호출, DB 세션(로그인은 의존성 바꾸기로 대신한다. 401만 실제 의존성으로 본다).
  가짜 응답은 손으로 쓴 값이고 실제 응답에서 옮긴 것이 아니다(ADR 0009).
- 출처: SPEC 4절(가격·재고 계약) · 7절(데모 모드) · 8.4 수용 기준, ADR 0009
"""
import logging
from functools import partial
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import auth
from backend.main import app
from backend.services import mouser

FAKE_KEY = "fake-mouser-key-for-api-tests"
FAKE = {"Errors": [], "SearchResults": {"NumberOfResult": 1, "Parts": [{
    "ManufacturerPartNumber": "FAKE-SS34", "Manufacturer": "Example Maker", "Description": "dropped",
    "PriceBreaks": [{"Quantity": 1, "Price": "7.77", "Currency": "XXX"}],
    "Availability": "fake availability", "ProductDetailUrl": "https://example.test/p/2"}]}}


@pytest.fixture
def mouser_calls(monkeypatch):
    """로그인한 사용자 · 가짜 키 · 실제 모드로 두고, Mouser 요청을 가짜 transport가 받아 requests에 적는다(status로 응답 코드를 바꾼다)."""
    seen = SimpleNamespace(requests=[], status=200)

    def handler(request):
        seen.requests.append(request)
        return httpx.Response(seen.status, json=FAKE)
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("MOUSER_API_KEY", FAKE_KEY)
    monkeypatch.setattr(mouser, "_calls", 0)
    monkeypatch.setattr(mouser, "search_parts", partial(mouser.search_parts, transport=httpx.MockTransport(handler)))
    app.dependency_overrides[auth.current_user_id] = lambda: 7
    yield seen
    app.dependency_overrides.clear()


def get(parts: str):
    return TestClient(app).get("/api/prices", params={"parts": parts})


def test_login_is_required_and_mouser_is_not_called(monkeypatch):
    monkeypatch.setattr(mouser, "search_parts", lambda *a, **k: pytest.fail("로그인 전에 Mouser를 부르면 안 된다"))
    assert get("1N4148").status_code == 401


def test_live_lookup_returns_only_screen_fields_with_no_store_and_logs_nothing(mouser_calls, caplog):
    caplog.set_level(logging.DEBUG)
    response = get("SS34, 1N4148,SS34")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {"available", "source", "fetched_at", "parts"} and body["available"] is True
    assert body["source"] == "Mouser Electronics" and body["fetched_at"]
    assert body["parts"] == [{"part_number": "FAKE-SS34", "manufacturer": "Example Maker",
                              "price_breaks": [{"quantity": 1, "price": "7.77", "currency": "XXX"}],
                              "availability": "fake availability", "product_url": "https://example.test/p/2"}]
    (request,) = mouser_calls.requests
    assert request.url.params["apiKey"] == FAKE_KEY
    assert b'"SS34|1N4148"' in request.content  # 공백을 떼고 같은 품번은 한 번만 보낸다
    for secret in (FAKE_KEY, "api.mouser.com", "7.77", "fake availability"):
        assert secret not in caplog.text, secret  # 키 · 요청 주소 · Mouser 값이 로그에 없다


@pytest.mark.parametrize("env, kind", [({"DEMO_MODE": "1"}, "demo_mode"), ({"MOUSER_API_KEY": ""}, "no_key")])
def test_demo_mode_and_missing_key_return_the_empty_shape_without_calling_mouser(mouser_calls, monkeypatch, env, kind):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    response = get("1N4148")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert response.json() == {"available": False, "source": "Mouser Electronics", "reason": kind,
                               "message": response.json()["message"], "parts": []}
    assert mouser_calls.requests == []


@pytest.mark.parametrize("parts", [",".join(f"PART{i:02d}" for i in range(11)), "1N4148|SS34", "AB", " , "])
def test_bad_or_too_many_parts_are_422_without_calling_mouser(mouser_calls, parts):
    response = get(parts)
    assert response.status_code == 422 and response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": response.json()["error"]["message"],
            "request_id": response.headers["X-Request-ID"],
        }
    }
    assert mouser_calls.requests == []


def test_call_cap_and_mouser_failure_return_the_empty_shape(mouser_calls, monkeypatch):
    monkeypatch.setattr(mouser, "_calls", 300)
    assert get("1N4148").json()["reason"] == "limit" and mouser_calls.requests == []
    monkeypatch.setattr(mouser, "_calls", 0)
    mouser_calls.status = 503
    body = get("1N4148").json()
    assert body["available"] is False and body["reason"] == "http" and body["parts"] == [] and len(mouser_calls.requests) == 1


def test_quantity_estimate_is_transient_exact_and_owned_by_requested_part(mouser_calls, caplog):
    caplog.set_level(logging.DEBUG)
    web = TestClient(app)
    response = web.get('/api/prices', params={'parts': 'FAKE-SS34', 'quantity': 25})
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    assert response.json()['parts'][0]['estimate'] == {
        'quantity': 25, 'break_quantity': 1, 'unit_price': '7.77', 'total': '194.25', 'currency': 'XXX'}
    mismatch = web.get('/api/prices', params={'parts': 'SS34', 'quantity': 25})
    assert mismatch.json()['parts'][0]['estimate'] is None
    assert '194.25' not in caplog.text and '7.77' not in caplog.text
    count = len(mouser_calls.requests)
    for quantity in ['0', '100001', '1.5']:
        assert web.get('/api/prices', params={'parts': 'SS34', 'quantity': quantity}).status_code == 422
    assert len(mouser_calls.requests) == count
