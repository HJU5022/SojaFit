from fastapi.testclient import TestClient

from backend.main import app


def test_health():
    # 배포 환경과 평가자가 서비스 상태를 확인하는 엔드포인트. 이게 깨지면 G1, G2가 모두 위험하다.
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_root_has_no_login_screen():
    response = TestClient(app).get("/")
    assert response.status_code == 404
