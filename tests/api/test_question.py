"""로그인 후 질문 API와 화면의 인증·저장 경계를 확인한다."""
from fastapi.testclient import TestClient

from backend import auth
from backend.main import app


def test_question_requires_session_before_building_or_invoking_graph(monkeypatch):
    def unexpected_graph():
        raise AssertionError("unauthenticated requests must not build the graph")

    monkeypatch.setattr("backend.main.get_question_graph", unexpected_graph, raising=False)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    response = TestClient(app).post(
        "/api/ask", json={"question": "What is SS34?"}, headers={"Origin": "http://testserver"}
    )
    assert response.status_code == 401


def test_question_uses_session_user_id_and_returns_only_answer(monkeypatch):
    calls = []

    class Graph:
        def invoke(self, state):
            calls.append(state)
            return {"answer": "SS34 is a Schottky diode."}

    monkeypatch.setattr("backend.main.get_question_graph", lambda: Graph(), raising=False)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    app.dependency_overrides[auth.current_user] = lambda: (17, "user")
    try:
        response = TestClient(app).post("/api/ask", json={"question": "What is SS34?"}, headers={"Origin": "http://testserver"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"answer": "SS34 is a Schottky diode."}
    assert calls == [{"input": "What is SS34?", "user_id": "17"}]


def test_question_rejects_client_selected_identity(monkeypatch):
    calls = []
    monkeypatch.setattr("backend.main.get_question_graph", lambda: calls.append(True), raising=False)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    app.dependency_overrides[auth.current_user] = lambda: (17, "user")
    try:
        response = TestClient(app).post("/api/ask", json={"question": "What is SS34?", "user_id": 18, "thread_id": "other"}, headers={"Origin": "http://testserver"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert calls == []


def test_question_rejects_blank_input_without_echoing(monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    app.dependency_overrides[auth.current_user] = lambda: (17, "user")
    try:
        response = TestClient(app).post("/api/ask", json={"question": "  "}, headers={"Origin": "http://testserver"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert "  " not in response.text


def test_question_rejects_oversized_input(monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    app.dependency_overrides[auth.current_user] = lambda: (17, "user")
    try:
        response = TestClient(app).post("/api/ask", json={"question": "x" * 2001}, headers={"Origin": "http://testserver"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_question_rejects_foreign_origin_before_session_or_graph(monkeypatch):
    calls = []
    monkeypatch.setattr("backend.main.get_question_graph", lambda: calls.append(True), raising=False)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    app.dependency_overrides[auth.current_user] = lambda: calls.append("session") or (17, "user")
    try:
        response = TestClient(app).post(
            "/api/ask", json={"question": "What is SS34?"}, headers={"Origin": "https://attacker.example"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert calls == []


def test_login_page_is_served_from_same_origin():
    response = TestClient(app).get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'id="login-form"' in response.text
    assert 'id="question-form"' in response.text
