"""/health 응답과 미구현 루트 화면의 404를 확인한다.

- 역할: 서버가 뜨는지 알리는 /health 응답 형식과, 아직 없는 루트 경로가 404인지 확인한다.
- 하지 않는 일: 화면·인증·DB는 보지 않는다.
- 출처: docs/GATES.md G1·G2(배포 상태 확인, 아래 테스트 주석)
"""
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
