"""/health 응답과 공통 오류·요청 ID 계약을 확인한다.

- 역할: /health 성공 응답, 서버 생성 요청 ID, HTTP·검증·내부 오류의 안전한 공통 형식을 확인한다.
- 하지 않는 일: 실제 화면·DB·외부 서비스는 보지 않는다.
- 출처: docs/GATES.md G1·G2, docs/specs/api-error-contract.md
"""
from uuid import UUID

from fastapi.testclient import TestClient

from backend.main import app


def test_health():
    # 배포 환경과 평가자가 서비스 상태를 확인하는 엔드포인트. 이게 깨지면 G1, G2가 모두 위험하다.
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_has_server_generated_request_id():
    response = TestClient(app).get("/health", headers={"X-Request-ID": "client-value"})
    request_id = response.headers["X-Request-ID"]
    assert UUID(request_id).version == 4
    assert request_id != "client-value"
    assert response.json() == {"status": "ok"}


def test_not_found_uses_error_contract():
    response = TestClient(app).get("/api/not-a-route")
    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Not Found",
            "request_id": response.headers["X-Request-ID"],
        }
    }


def test_auth_required_uses_error_contract():
    response = TestClient(app).get("/api/auth/me")
    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "UNAUTHORIZED",
            "message": "로그인이 필요합니다.",
            "request_id": response.headers["X-Request-ID"],
        }
    }


def test_forbidden_uses_error_contract():
    response = TestClient(app).post(
        "/api/auth/logout",
        headers={"origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.json() == {
        "error": {
            "code": "ORIGIN_MISMATCH",
            "message": "요청 출처를 확인할 수 없습니다.",
            "request_id": response.headers["X-Request-ID"],
        }
    }


def test_validation_error_uses_safe_error_contract():
    email = "not-an-email"
    password = "private-test-password"
    response = TestClient(app).post(
        "/api/auth/login",
        headers={"origin": "http://testserver"},
        json={"email": email, "password": password},
    )
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "요청 형식이 올바르지 않습니다.",
            "request_id": response.headers["X-Request-ID"],
        }
    }
    assert email not in response.text
    assert password not in response.text
    assert "detail" not in response.json()


def test_unhandled_error_does_not_expose_internal_message(monkeypatch):
    monkeypatch.setenv('AUTH_ORIGIN', 'http://localhost:8000')
    def fail_authentication(email, password, ip):
        raise RuntimeError("private traceback detail")

    monkeypatch.setattr("backend.main.auth.authenticate", fail_authentication)
    response = TestClient(app, raise_server_exceptions=False).post(
        "/api/auth/login",
        headers={"origin": "http://localhost:8000"},
        json={"email": "user@example.test", "password": "valid-length-password"},
    )
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "요청을 처리하지 못했습니다.",
            "request_id": response.headers["X-Request-ID"],
        }
    }
    assert "private traceback detail" not in response.text


def test_openapi_documents_common_validation_error_contract():
    schema = TestClient(app).get("/openapi.json").json()
    validation_response = schema["paths"]["/api/auth/login"]["post"]["responses"]["422"]
    assert validation_response["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorEnvelope"
    }
    error_schema = schema["components"]["schemas"]["ErrorEnvelope"]
    assert "detail" not in error_schema.get("properties", {})
