"""관리자 계정 관리 API(#23) DB 시험: 이메일 가림 해제와 사유 · 작업 이력, 정지 · 재활성화, 탈퇴 처리.

- 역할: 관리자 아님 401 · 403, 사유 없음 · 짧음 · 공백뿐 · 501자 422(이력 없음), 다른 출처 403, 가림 해제가 이력을 먼저 쓰고 원문을 돌려주며
  로그에 원문이 없음, 이력 목록, 정지가 세션을 지움, 탈퇴 처리가 관리자 · 자기 자신을 기록을 지우기 전에 거절함을 확인한다.
- 하지 않는 일: 분석 기록 · Store 삭제 자체(`test_deletion.py`가 진짜 분석 서비스로 확인한다. 여기서는 account_deletion을 가짜로 둔다).
  DB 시험은 TEST_AUTH_DATABASE_URL(tests/db_schema.py를 적용한 격리 DB)이 있을 때만 돈다.
- 출처: SPEC.md 4절 · 8.6절, db/034_admin_audit.sql.
"""
import logging
import os
import secrets
from contextlib import contextmanager
from types import SimpleNamespace

import psycopg
import pytest
from fastapi.testclient import TestClient

from backend import auth
from backend.main import app

ORIGIN = {"origin": "http://testserver"}
PASSWORD = "test-only-password-123"


@pytest.fixture
def world(monkeypatch):
    """관리자 둘 · 일반 사용자 둘을 만들고 로그인한 클라이언트를 준다. 끝나면 이력 · 계정을 지운다(시험 정리만 DELETE한다)."""
    url = os.environ.get("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    suffix, password_hash = secrets.token_hex(6), auth.hash_password(PASSWORD)
    emails = {name: f"{name}-{suffix}@example.test" for name in ("admin", "admin2", "user", "user2")}
    with psycopg.connect(url) as conn:
        conn.execute("DELETE FROM auth_login_ip_attempts")
        ids = {name: conn.execute("INSERT INTO users(login_id,password_hash,role) VALUES (%s,%s,%s) RETURNING id",
                                  (email, password_hash, "admin" if name.startswith("admin") else "user")).fetchone()[0]
               for name, email in emails.items()}
    clients = {}
    for name in ("admin", "user"):
        clients[name] = TestClient(app)
        assert clients[name].post("/api/auth/login", headers=ORIGIN, json={"email": emails[name], "password": PASSWORD}).status_code == 200
    calls = []

    @contextmanager
    def account_deletion(user):  # 가짜 분석 기록 삭제: 불렸는지만 남긴다
        calls.append(user)
        yield {"analysis_threads": 0, "analysis_circuits": 0, "checkpoints": 0, "memory_items": 0}
    app.state.conversations = SimpleNamespace(account_deletion=account_deletion)
    yield SimpleNamespace(url=url, ids=ids, emails=emails, admin=clients["admin"], user=clients["user"], anonymous=TestClient(app), calls=calls)
    del app.state.conversations
    with psycopg.connect(url) as conn:
        conn.execute("DELETE FROM admin_audit WHERE actor_id = ANY(%s)", (list(ids.values()),))
        conn.execute("DELETE FROM users WHERE id = ANY(%s)", (list(ids.values()),))


def audit_rows(w):
    with psycopg.connect(w.url) as conn:
        return conn.execute("SELECT actor_id,target_id,target_email_masked,action,fields,reason FROM admin_audit "
                            "WHERE actor_id = ANY(%s) ORDER BY id", (list(w.ids.values()),)).fetchall()


def test_admin_endpoints_reject_anonymous_and_regular_users(world):
    target = world.ids["user2"]
    for client, status in ((world.anonymous, 401), (world.user, 403)):
        assert client.get("/api/admin/audit").status_code == status
        assert client.post(f"/api/admin/users/{target}/unmask", headers=ORIGIN, json={"reason": "문의 응대 확인"}).status_code == status
        assert client.delete(f"/api/admin/users/{target}", headers=ORIGIN).status_code == status
    assert world.calls == [] and audit_rows(world) == []


def test_unmask_needs_a_reason_and_records_it_before_showing_the_email(world, caplog):
    target, admin = world.ids["user2"], world.admin
    for body in ({}, {"reason": ""}, {"reason": "     "}, {"reason": "abcd"}, {"reason": "가" * 501}, {"reason": "문의 응대 확인", "extra": 1}):
        assert admin.post(f"/api/admin/users/{target}/unmask", headers=ORIGIN, json=body).status_code == 422, body
    assert admin.post(f"/api/admin/users/{target}/unmask", headers={"origin": "https://evil.example"}, json={"reason": "문의 응대 확인"}).status_code == 403
    assert admin.post("/api/admin/users/999999999/unmask", headers=ORIGIN, json={"reason": "문의 응대 확인"}).status_code == 404
    assert audit_rows(world) == []  # 거절된 요청은 이력도 남기지 않는다

    caplog.set_level(logging.DEBUG)
    shown = admin.post(f"/api/admin/users/{target}/unmask", headers=ORIGIN, json={"reason": "  사용자  문의 응대를 위해 확인  "})
    assert shown.status_code == 200 and shown.json() == {"email": world.emails["user2"]}
    assert shown.headers["cache-control"] == "no-store"
    assert world.emails["user2"] not in caplog.text  # 원문은 로그에 남지 않는다
    masked = auth.mask_email(world.emails["user2"])
    assert audit_rows(world) == [(world.ids["admin"], target, masked, "unmask", ["email"], "사용자 문의 응대를 위해 확인")]

    entries = admin.get("/api/admin/audit")
    assert entries.status_code == 200 and entries.headers["cache-control"] == "no-store"
    entry = next(e for e in entries.json() if e["target_id"] == target)
    assert (entry["action"], entry["fields"], entry["reason"], entry["target_email"]) == ("unmask", ["email"], "사용자 문의 응대를 위해 확인", masked)
    assert entry["actor_id"] == world.ids["admin"] and entry["actor_email"] == auth.mask_email(world.emails["admin"])
    assert world.emails["user2"] not in entries.text and world.emails["admin"] not in entries.text


def test_suspend_revokes_sessions_and_both_changes_are_recorded(world):
    target = world.ids["user"]
    assert world.admin.patch(f"/api/admin/users/{target}", headers=ORIGIN, json={"is_active": False}).status_code == 200
    assert world.user.get("/api/auth/me").status_code == 401  # 정지하면 기존 세션이 끝난다
    assert world.admin.patch(f"/api/admin/users/{target}", headers=ORIGIN, json={"is_active": True}).status_code == 200
    assert world.user.get("/api/auth/me").status_code == 401  # 재활성화해도 예전 세션은 돌아오지 않는다
    assert [row[3] for row in audit_rows(world)] == ["deactivate", "activate"]


def test_delete_refuses_admins_self_and_missing_before_touching_records(world):
    admin = world.admin
    assert admin.delete(f"/api/admin/users/{world.ids['admin2']}", headers=ORIGIN).status_code == 403
    assert admin.delete(f"/api/admin/users/{world.ids['admin']}", headers=ORIGIN).status_code == 403
    assert admin.delete("/api/admin/users/999999999", headers=ORIGIN).status_code == 404
    assert admin.delete(f"/api/admin/users/{world.ids['user']}", headers={"origin": "https://evil.example"}).status_code == 403
    assert world.calls == [] and audit_rows(world) == []  # 분석 기록을 지우기 전에 거절했다

    deleted = admin.delete(f"/api/admin/users/{world.ids['user']}", headers=ORIGIN)
    assert deleted.status_code == 200 and deleted.json()["deleted"]["account"] == 1
    assert world.calls == [world.ids["user"]] and world.user.get("/api/auth/me").status_code == 401
    assert "set-cookie" not in deleted.headers  # 관리자 자신의 세션 쿠키는 그대로다
    assert admin.get("/api/auth/me").status_code == 200
    with psycopg.connect(world.url) as conn:
        assert conn.execute("SELECT count(*) FROM users WHERE id=%s", (world.ids["user"],)).fetchone()[0] == 0
    assert audit_rows(world) == [(world.ids["admin"], world.ids["user"], auth.mask_email(world.emails["user"]), "delete", [], None)]
