"""Mouser 가격·재고 클라이언트(backend/services/mouser.py) 시험: 가짜 transport로 네트워크 없이 확인한다.

- 역할: 요청 모양(POST, `apiKey` 쿼리, `|`로 이은 품번), 화면에 필요한 칸만 고르기, 한 번만 보내기(재시도 없음),
  품번 조건 · 키 없음 · 호출 상한에서 Mouser를 부르지 않기, 로그 · 오류 문구에 키와 요청 주소가 없는지 본다.
- 하지 않는 일: 실제 Mouser 호출. 가짜 응답은 손으로 쓴 값이고(통화 XXX, example.test 주소) 실제 응답에서 옮긴 것이 아니다(ADR 0009).
- 출처: SPEC 4절(가격·재고 계약) · 6절 · 8.4 수용 기준, ADR 0009
"""
import json
import logging

import httpx
import pytest

from backend.services import mouser

FAKE_KEY = "fake-mouser-key-for-tests-only"
FAKE = {"Errors": [], "SearchResults": {"NumberOfResult": 1, "Parts": [{
    "ManufacturerPartNumber": "FAKE-1N4148", "Manufacturer": "Example Maker", "MouserPartNumber": "000-FAKE",
    "PriceBreaks": [{"Quantity": 1, "Price": "9.99", "Currency": "XXX"}, {"Quantity": 100, "Price": "1.11", "Currency": "XXX"}],
    "Availability": "fake availability", "ProductDetailUrl": "https://example.test/p/1",
    "Description": "dropped", "LifecycleStatus": "dropped"}]}}


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    """시험마다 가짜 키와 빈 호출 횟수로 시작한다. [왜] 다른 모듈의 load_dotenv가 진짜 키를 환경에 올려도 가짜 키로 덮는다."""
    monkeypatch.setenv("MOUSER_API_KEY", FAKE_KEY)
    monkeypatch.setattr(mouser, "_calls", 0)


def fake(status=200, payload=FAKE, seen=None):
    """요청을 seen에 적고 정해 둔 응답을 돌려주는 가짜 transport."""
    def handler(request):
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=payload)
    return httpx.MockTransport(handler)


def test_request_shape_and_only_screen_fields_are_returned():
    seen = []
    out = mouser.search_parts(["1N4148", "SS34"], transport=fake(seen=seen))
    (request,) = seen  # 한 번만 보낸다
    assert request.method == "POST" and request.url.path == "/api/v1/search/partnumber" and request.url.host == "api.mouser.com"
    assert request.url.params["apiKey"] == FAKE_KEY  # 문서: 키는 apiKey 쿼리
    assert json.loads(request.content) == {"SearchByPartRequest": {"mouserPartNumber": "1N4148|SS34", "partSearchOptions": "None"}}
    assert out["source"] == "Mouser Electronics" and out["fetched_at"].endswith("+00:00")
    assert out["parts"] == [{"part_number": "FAKE-1N4148", "manufacturer": "Example Maker",
                             "price_breaks": [{"quantity": 1, "price": "9.99", "currency": "XXX"}, {"quantity": 100, "price": "1.11", "currency": "XXX"}],
                             "availability": "fake availability", "product_url": "https://example.test/p/1"}]  # 설명 · 단종 여부는 버린다


def test_no_log_line_contains_the_key_or_the_request_url(caplog):
    caplog.set_level(logging.DEBUG)  # [왜] 모든 로거의 DEBUG까지 모은다. httpx는 INFO로 요청 주소를 남긴다
    mouser.search_parts(["1N4148"], transport=fake())
    with pytest.raises(mouser.MouserError):
        mouser.search_parts(["1N4148"], transport=fake(status=500))
    assert FAKE_KEY not in caplog.text and "apiKey" not in caplog.text and "api.mouser.com" not in caplog.text


@pytest.mark.parametrize("error", [httpx.ConnectTimeout, httpx.ConnectError])
def test_transport_failure_is_one_attempt_and_the_error_hides_the_url(error):
    calls = []

    def broken(request):
        calls.append(request)
        raise error(f"failed {request.url}", request=request)  # [주의] httpx 예외 문구에는 요청 주소(키 포함)가 들어간다
    with pytest.raises(mouser.MouserError) as caught:
        mouser.search_parts(["1N4148"], transport=httpx.MockTransport(broken))
    assert len(calls) == 1  # 다시 부르지 않는다
    assert caught.value.kind in ("timeout", "network") and FAKE_KEY not in str(caught.value) and FAKE_KEY not in repr(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__  # traceback에 httpx 예외(주소)가 따라 나오지 않는다


@pytest.mark.parametrize("status, payload, kind", [
    (401, {}, "bad_key"),
    (503, {}, "http"),
    (200, {"Errors": [{"Code": "Invalid", "Message": "fake", "PropertyName": "API Key"}], "SearchResults": None}, "bad_key"),
    (200, {"Errors": [{"Code": "Other", "Message": "fake", "PropertyName": "mouserPartNumber"}]}, "api_error"),
    (200, ["not", "an", "object"], "bad_response"),
])
def test_failures_become_a_kind_without_mouser_text(status, payload, kind):
    with pytest.raises(mouser.MouserError) as caught:
        mouser.search_parts(["1N4148"], transport=fake(status=status, payload=payload))
    assert caught.value.kind == kind and "fake" not in str(caught.value)  # Mouser 오류 문구는 넘기지 않는다


@pytest.mark.parametrize("parts", [[], [f"PART{i:02d}" for i in range(11)], ["1N4148|SS34"], ["AB"], ["x" * 41]])
def test_bad_parts_are_rejected_before_calling_mouser(parts):
    seen = []
    with pytest.raises(ValueError):
        mouser.search_parts(parts, transport=fake(seen=seen))
    assert seen == []


def test_no_key_and_call_cap_do_not_call_mouser(monkeypatch):
    seen = []
    monkeypatch.setenv("MOUSER_API_KEY", "")
    with pytest.raises(mouser.MouserError, match="no_key"):
        mouser.search_parts(["1N4148"], transport=fake(seen=seen))
    monkeypatch.setenv("MOUSER_API_KEY", FAKE_KEY)
    monkeypatch.setattr(mouser, "_calls", 300)  # 리터럴 300: 상수끼리 비교하면 상한을 바꿔도 통과한다
    with pytest.raises(mouser.MouserError, match="limit"):
        mouser.search_parts(["1N4148"], transport=fake(seen=seen))
    assert seen == []
    monkeypatch.setattr(mouser, "_calls", 299)
    mouser.search_parts(["1N4148"], transport=fake(seen=seen))
    assert len(seen) == 1 and mouser._calls == 300  # 상한 바로 아래는 한 번 보내고 센다
