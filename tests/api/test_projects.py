"""프로젝트 HTTP 계약: 세션·Origin·공통 오류·실제 DB 소유권."""
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from backend import auth
from backend.main import app
from tests.db_schema import apply_service_schema


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("AUTH_ORIGIN", "http://testserver")
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("method,path,body", [
    ("GET", "/api/projects", None), ("POST", "/api/projects", {"demo_id": "breadboard_supply", "name": "회로"}),
    ("GET", "/api/projects/1", None), ("PATCH", "/api/projects/1", {"name": "수정"}),
    ("DELETE", "/api/projects/1", None), ("GET", "/api/demo-circuits", None),
    ("POST", "/api/projects/1/netlist", None),
])
def test_projects_require_session(client, method, path, body):
    response = client.request(method, path, json=body, headers={"origin": "http://testserver"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize("origin", [None, "https://evil.example"])
@pytest.mark.parametrize("method,path,body", [
    ("POST", "/api/projects", {"demo_id": "breadboard_supply", "name": "회로"}),
    ("PATCH", "/api/projects/1", {"name": "수정"}), ("DELETE", "/api/projects/1", None),
    ("POST", "/api/projects/1/netlist", None),
])
def test_project_mutations_check_origin(client, origin, method, path, body):
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    response = client.request(method, path, json=body, headers={"origin": origin} if origin else {})
    assert response.status_code == 403
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


def test_demo_catalog_and_invalid_creation(client):
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    response = client.get("/api/demo-circuits")
    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {
        "breadboard_supply", "mosfet_driver", "attiny85_dev", "pro_micro", "franzininho_diy", "attiny85_time_switch",
        "fc_rom_vomitter", "attiny2313a_thermostat", "tiny85_fan_control", "ug56_pwm_controller",
        "car_radio_acc_delay", "overengineered_psu", "tinydimmer", "hrem", "zr7_taillight",
    }
    for body in ({"demo_id": "../../secret", "name": "회로"}, {"demo_id": "breadboard_supply", "name": " "},
                 {"demo_id": "breadboard_supply", "name": "x" * 201},
                 {"demo_id": "breadboard_supply", "name": "회로", "user_id": 2}):
        result = client.post("/api/projects", json=body, headers={"origin": "http://testserver"})
        assert result.status_code == 422
        assert result.json()["error"]["code"] == "VALIDATION_ERROR"


def test_demo_project_create_is_404_outside_demo_mode(client, monkeypatch):
    """실서비스(DEMO_MODE=0)에서는 데모 회로로 프로젝트 만들기가 없다(업로드만)."""
    monkeypatch.setenv("DEMO_MODE", "0")
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    response = client.post(
        "/api/projects",
        json={"demo_id": "breadboard_supply", "name": "전원 회로"},
        headers={"origin": "http://testserver"},
    )
    assert response.status_code == 404


def test_empty_creation_works_outside_demo_mode(client, monkeypatch):
    from backend.api.projects import repository
    monkeypatch.setenv("DEMO_MODE", "0")
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    class EmptyRepository:
        def create_empty(self, user_id, name):
            return {"id": 1, "name": name, "source_kind": "upload", "demo_id": None,
                    "created_at": "2026-11-13T00:00:00Z", "updated_at": "2026-11-13T00:00:00Z",
                    "circuit_version": 0, "connections": {"parts": [], "nets": []}}
    app.dependency_overrides[repository] = lambda: EmptyRepository()
    response = client.post("/api/projects", json={"name": "빈 프로젝트"}, headers={"origin": "http://testserver"})
    assert response.status_code == 201, response.text
    assert response.json()["circuit_version"] == 0 and response.json()["connections"]["parts"] == []


@pytest.mark.parametrize("filename,raw,status", [
    ("test.net", None, 201), ("test.txt", None, 201), ("test.pdf", None, 400),
    ("test.net", b"", 400), ("test.net", b"\xff", 400), ("test.net", b"x" * (5 * 1024 * 1024 + 1), 413),
])
def test_chat_netlist_uses_bounded_parser_and_creates_new_thread(upload_boundary, filename, raw, status):
    from backend.api.projects import repository
    client, payloads, uploads, _ = upload_boundary
    base = app.dependency_overrides[repository]()
    class ImportRepository:
        def import_netlist(self, user_id, project_id, **payload):
            assert project_id == 5
            return base.create_upload(user_id, "회로", **payload), str(uuid4())
    app.dependency_overrides[repository] = lambda: ImportRepository()
    response = client.post("/api/projects/5/netlist", files={"file": (filename, raw if raw is not None else Path("tests/fixtures/netlists/minimal.net").read_bytes())},
                           headers={"origin": "http://testserver"})
    assert response.status_code == status, response.text
    if status == 201:
        assert set(response.json()) == {"project", "thread_id"}
        assert len(payloads) == 1
    else:
        assert payloads == []
    assert uploads and all(upload.file.closed for upload in uploads)


@pytest.mark.parametrize("path,data,expected", [
    ("/api/projects/upload", b"\xff", "UTF-8로 다시 저장하거나 KiCad에서 넷리스트(.net)로 다시 내보내 주세요."),
    ("/api/projects/upload", b"(not-export)", "KiCad 넷리스트(.net)로 다시 내보내 주세요. PDF·이미지·회로도 파일은 사용할 수 없습니다."),
    ("/api/projects/5/netlist", b"(not-export)", "KiCad 넷리스트(.net)로 다시 내보내 주세요. PDF·이미지·회로도 파일은 사용할 수 없습니다."),
])
def test_netlist_failure_messages_distinguish_encoding_and_syntax(upload_boundary, path, data, expected):
    client, payloads, uploads, _ = upload_boundary
    files = {"file": ("test.net", data)}
    if path.endswith("/upload"):
        response = client.post(path, data={"name": "회로"}, files=files, headers={"origin": "http://testserver"})
    else:
        response = client.post(path, files=files, headers={"origin": "http://testserver"})
    assert response.status_code == 400
    assert response.json()["error"] == {"code": "VALIDATION_ERROR", "message": expected, "request_id": response.headers["X-Request-ID"]}
    assert payloads == []
    assert uploads and all(upload.file.closed for upload in uploads)


def test_netlist_multipart_failure_has_attachment_retry_message(upload_boundary):
    client, payloads, uploads, _ = upload_boundary
    content = b"--boundary\r\nContent-Disposition: form-data; name=\"file\"; filename=\"test.net\"\r\n\r\n"
    response = client.post("/api/projects/upload", content=content,
                           headers={"origin": "http://testserver", "content-type": "multipart/form-data; boundary=boundary"})
    assert response.status_code == 400
    assert response.json()["error"]["message"] == "파일을 다시 첨부해 주세요. 업로드 형식이 올바르지 않습니다."
    assert payloads == []
    assert uploads and all(upload.file.closed for upload in uploads)


def test_chat_netlist_accepts_more_than_json_limit(upload_boundary):
    from backend.api.projects import repository
    client, _, _, _ = upload_boundary
    base = app.dependency_overrides[repository]()
    class ImportRepository:
        def import_netlist(self, user_id, project_id, **payload):
            return base.create_upload(user_id, "회로", **payload), str(uuid4())
    app.dependency_overrides[repository] = lambda: ImportRepository()
    raw = Path("tests/fixtures/netlists/minimal.net").read_bytes() + b" " * (1024 * 1024)
    response = client.post("/api/projects/5/netlist", files={"file": ("circuit.net", raw)}, headers={"origin": "http://testserver"})
    assert response.status_code == 201, response.text


def test_demo_catalog_follows_demo_mode(client, monkeypatch):
    """데모 회로 목록도 데모 모드에서만 있다(생성과 같은 규칙). 로그인은 모드와 무관하게 먼저 확인한다."""
    monkeypatch.setenv("DEMO_MODE", "0")
    assert client.get("/api/demo-circuits").status_code == 401
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    assert client.get("/api/demo-circuits").status_code == 404
    monkeypatch.setenv("DEMO_MODE", "1")
    assert len(client.get("/api/demo-circuits").json()) == 15


def test_demo_catalog_exposes_only_verified_public_schematic_metadata(client):
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    response = client.get("/api/demo-circuits")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 15
    for item in body:
        assert set(item) == {"id", "name", "schematic"}
        schematic = item["schematic"]
        assert set(schematic) == {
            "image_url", "original_url", "source_repo", "source_commit", "license", "license_evidence_url", "attribution",
        }
        assert schematic["image_url"] == f"/circuit-schematics/{item['id']}.png"
        for field in ("original_url", "source_repo", "license_evidence_url"):
            assert schematic[field].startswith("https://")
    for private in ("sha256", "local_path", "checkout_path", "C:\\", "file://"):
        assert private not in response.text


def test_demo_catalog_requires_session(client):
    assert client.get("/api/demo-circuits").status_code == 401


def test_demo_catalog_filters_pages_and_sets_cache_header(client):
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    response = client.get("/api/demo-circuits", params={"q": "attiny", "offset": 2, "limit": 1})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == ["attiny2313a_thermostat"]
    assert response.headers["Cache-Control"] == "private, max-age=300"  # 로그인 경로라 공유 캐시에 두지 않는다


@pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"limit": 101}, {"q": ""}])
def test_demo_catalog_rejects_invalid_page_parameters(client, params):
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    assert client.get("/api/demo-circuits", params=params).status_code == 422


def test_database_errors_use_safe_common_response(client, monkeypatch):
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    def unavailable():
        raise psycopg.OperationalError("private database connection detail")
    monkeypatch.setattr(auth, "connection", unavailable)
    response = client.get("/api/projects")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "UNAVAILABLE"
    assert "private" not in response.text
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]


@pytest.fixture
def upload_boundary(client, monkeypatch):
    from backend.api.projects import repository
    from starlette.datastructures import UploadFile
    import tempfile
    payloads, uploads, reads = [], [], []
    class RecordingRepository:
        def create_upload(self, user_id, name, **payload):
            import json
            assert uploads and all(upload.file.closed for upload in uploads), "original must be closed before persistence"
            payloads.append((user_id, name, payload))
            return {"id": 101, "name": name, "source_kind": "upload", "demo_id": None,
                    "created_at": "2026-11-09T00:00:00Z", "updated_at": "2026-11-09T00:00:00Z",
                    "connections": json.loads(json.dumps(payload["connections"], default=dict))}
    async def close(upload):
        uploads.append(upload)
        await original_close(upload)
    async def read(upload, size=-1):
        reads.append(size)
        return await original_read(upload, size)
    def no_disk(*args, **kwargs):
        pytest.fail("uploaded originals must never roll over to a disk temporary file")
    original_close, original_read = UploadFile.close, UploadFile.read
    monkeypatch.setattr(UploadFile, "close", close)
    monkeypatch.setattr(UploadFile, "read", read)
    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", no_disk)
    app.dependency_overrides[auth.current_user_id] = lambda: 7
    app.dependency_overrides[repository] = lambda: RecordingRepository()
    return client, payloads, uploads, reads


def test_upload_persists_only_normalized_payload_and_closes(upload_boundary):
    import hashlib
    client, payloads, uploads, reads = upload_boundary
    raw = Path("tests/fixtures/netlists/minimal.net").read_bytes()
    # Cross the framework's default 1 MiB spool threshold without creating a temporary file.
    raw += b" " * (1024 * 1024)
    response = client.post("/api/projects/upload", data={"name": " 업로드 "},
                           files={"file": ("../../RAW_UPLOAD_MARKER.net", raw)}, headers={"origin": "http://testserver"})
    assert response.status_code == 201, response.text
    user_id, name, payload = payloads[0]
    assert (user_id, name) == (7, "업로드")
    assert set(payload) == {"connections", "source_sha256", "parser_version"}
    assert set(payload["connections"]) == {"parts", "nets"}
    assert payload["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert payload["parser_version"] == "kicad-export-v2"
    assert "RAW_UPLOAD_MARKER" not in repr(payload) + response.text
    assert all(not isinstance(value, (bytes, Path)) and not hasattr(value, "read") for value in payload.values())
    assert reads == [5 * 1024 * 1024 + 1]
    assert uploads and all(upload.file.closed for upload in uploads)


@pytest.mark.parametrize("raw,status", [(b"\xff", 400), (b"(not-export)", 400), (b"x" * (5 * 1024 * 1024 + 1), 413)])
def test_invalid_upload_uses_safe_common_errors_and_closes(upload_boundary, raw, status):
    client, payloads, uploads, reads = upload_boundary
    response = client.post("/api/projects/upload", data={"name": "회로"}, files={"file": ("RAW_UPLOAD_MARKER.net", raw)},
                           headers={"origin": "http://testserver"})
    assert response.status_code == status
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert "RAW_UPLOAD_MARKER" not in response.text
    assert payloads == []
    assert uploads and all(upload.file.closed for upload in uploads)
    assert all(size == 5 * 1024 * 1024 + 1 for size in reads)


@pytest.mark.parametrize('filename',['synthetic.png','synthetic.net'])
def test_injection_preparation_rejects_images_including_renamed_net(upload_boundary,filename):
    client,payloads,_,_=upload_boundary
    response=client.post('/api/projects/upload',data={'name':'회로'},
                         files={'file':(filename,b'\x89PNG\r\n\x1a\nsynthetic-image')},
                         headers={'origin':'http://testserver'})
    assert response.status_code==400
    assert payloads==[]


def test_upload_closes_on_repository_failure(upload_boundary, monkeypatch):
    from backend.api.projects import repository
    client, _, uploads, _ = upload_boundary
    class Unavailable:
        def create_upload(self, *args, **kwargs):
            raise psycopg.OperationalError("RAW_UPLOAD_MARKER database detail")
    # Keep the real dependency's common DB error translation.
    app.dependency_overrides.pop(repository)
    monkeypatch.setattr("backend.api.projects.ProjectRepository", Unavailable)
    response = client.post("/api/projects/upload", data={"name": "회로"},
                           files={"file": ("synthetic.net", Path("tests/fixtures/netlists/minimal.net").read_bytes())},
                           headers={"origin": "http://testserver"})
    assert response.status_code == 503
    assert "RAW_UPLOAD_MARKER" not in response.text
    assert uploads and all(upload.file.closed for upload in uploads)


@pytest.mark.parametrize("authenticated,origin,status", [(False, "http://testserver", 401), (True, None, 403), (True, "https://evil.example", 403)])
def test_upload_requires_session_and_origin(client, authenticated, origin, status):
    if authenticated:
        app.dependency_overrides[auth.current_user_id] = lambda: 1
    response = client.post("/api/projects/upload", data={"name": "회로"}, files={"file": ("test.net", b"private")},
                           headers={"origin": origin} if origin else {})
    assert response.status_code == status


@pytest.mark.parametrize("data,files", [({"name": " "}, {"file": ("test.net", b"private")}),
    ({"name": "회로"}, {}), ({"name": "회로", "source": "private"}, {"file": ("test.net", b"private")})])
def test_invalid_upload_fields_never_reach_repository(upload_boundary, data, files):
    client, payloads, uploads, _ = upload_boundary
    response = client.post("/api/projects/upload", data=data, files=files, headers={"origin": "http://testserver"})
    assert response.status_code in (400, 422)
    assert payloads == []
    assert all(upload.file.closed for upload in uploads)


@pytest.mark.parametrize("extra,truncate,status", [(1, False, 413), (0, True, 400)])
def test_upload_closes_on_partial_multipart_failure(upload_boundary, extra, truncate, status):
    client, payloads, uploads, _ = upload_boundary
    content = (b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="synthetic.net"\r\n\r\n'
               + b"x" * (5 * 1024 * 1024 + 1 + extra) + (b"" if truncate else b"\r\n--boundary--\r\n"))
    response = client.post("/api/projects/upload", content=content,
                           headers={"origin": "http://testserver", "content-type": "multipart/form-data; boundary=boundary"})
    assert response.status_code == status
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert payloads == []
    assert uploads and all(upload.file.closed for upload in uploads)


@pytest.mark.parametrize("filename", ["circuit.txt", "", "   ", "circuit.net.txt"])
def test_upload_requires_nonempty_net_filename_and_closes(upload_boundary, filename):
    client, payloads, uploads, reads = upload_boundary
    raw = Path("tests/fixtures/netlists/minimal.net").read_bytes()
    content = (b'--boundary\r\nContent-Disposition: form-data; name="name"\r\n\r\ncircuit\r\n'
               + f'--boundary\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n\r\n'.encode()
               + raw + b'\r\n--boundary--\r\n')
    response = client.post("/api/projects/upload", content=content,
                           headers={"origin": "http://testserver", "content-type": "multipart/form-data; boundary=boundary"})
    assert response.status_code == 400
    assert response.headers["X-Request-ID"]
    assert response.json() == {"error": {"code": "VALIDATION_ERROR", "message": ".net 확장자의 KiCad 넷리스트 파일이 필요합니다.",
                                          "request_id": response.headers["X-Request-ID"]}}
    assert payloads == [] and reads == []
    assert uploads and all(upload.file.closed for upload in uploads)


def test_upload_rejects_missing_filename_before_reading_or_persisting(upload_boundary):
    client, payloads, uploads, reads = upload_boundary
    response = client.post("/api/projects/upload", data={"name": "회로"},
                           files={"file": (None, Path("tests/fixtures/netlists/minimal.net").read_bytes())},
                           headers={"origin": "http://testserver"})
    assert response.status_code == 400
    # filename이 없는 file은 두 번째 text field다. max_fields=1에서 거절되어 route의 422 검사까지 가지 않는다.
    assert response.headers["X-Request-ID"]
    assert response.json() == {"error": {"code": "VALIDATION_ERROR", "message": "파일을 다시 첨부해 주세요. 업로드 형식이 올바르지 않습니다.",
                                          "request_id": response.headers["X-Request-ID"]}}
    assert payloads == [] and uploads == [] and reads == []


@pytest.mark.parametrize("raw", [
    b'(export(components(comp(ref D1)(value "\x00")))(nets(net(code 1)(name GND)(node(ref D1)(pin 1)))))',
    b'(export(components(comp(ref D1)))(nets(net(code 1)(name GND)(node(ref D1)(pin 1)))(net(code 1)(name VCC)(node(ref D1)(pin 2)))))',
    b'(export(components(comp(ref D1)))(nets(net(code 0)(name GND)(node(ref D1)(pin 1)))))',
    b'(export(components(comp(ref D1)))(nets(net(code -1)(name GND)(node(ref D1)(pin 1)))))',
    b'(export(components(comp(ref D1)))(nets(net(code "not-an-integer")(name GND)(node(ref D1)(pin 1)))))',
])
def test_invalid_net_identity_and_nul_never_reach_storage(upload_boundary, raw):
    client, payloads, uploads, _ = upload_boundary
    response = client.post("/api/projects/upload", data={"name": "회로"}, files={"file": ("synthetic.net", raw)},
                           headers={"origin": "http://testserver"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert response.json()["error"]["request_id"] == response.headers["X-Request-ID"]
    assert payloads == []
    assert uploads and all(upload.file.closed for upload in uploads)


def test_owned_crud_and_foreign_admin_404_use_real_database(client, monkeypatch):
    url = os.getenv("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    schema = "projects_api_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(sql.Identifier(schema)))
        connect = lambda: psycopg.connect(url, options=f"-csearch_path={schema}")
        monkeypatch.setattr(auth, "connection", connect)
        try:
            with connect() as conn:
                apply_service_schema(conn)
                users = [row[0] for row in conn.execute("INSERT INTO users (login_id,password_hash,role) VALUES ('a@example.test','fake','user'),('b@example.test','fake','admin') RETURNING id").fetchall()]
                for token, user_id in zip(("owner-token", "admin-token"), users):
                    conn.execute("INSERT INTO auth_sessions (token_hash,user_id,expires_at) VALUES (%s,%s,CURRENT_TIMESTAMP + INTERVAL '1 hour')", (auth.session_token_hash(token), user_id))
            client.cookies.set(auth.COOKIE, "owner-token")
            response = client.post("/api/projects", json={"demo_id": "breadboard_supply", "name": "전원 회로"}, headers={"origin": "http://testserver"})
            assert response.status_code == 201
            project = response.json()
            project_id = project["id"]
            assert project["source_kind"] == "demo"
            assert project["connections"]["components"][3]["ref"] == "D1"
            assert "user_id" not in project and "netlist_content" not in project
            assert [p["id"] for p in client.get("/api/projects").json()] == [project_id]
            assert client.get(f"/api/projects/{project_id}").json() == project
            renamed = client.patch(f"/api/projects/{project_id}", json={"name": "名前変更"}, headers={"origin": "http://testserver"})
            assert renamed.status_code == 200 and renamed.json()["name"] == "名前変更"
            uploaded = client.post("/api/projects/upload", data={"name": "업로드"},
                                   files={"file": ("synthetic.net", Path("tests/fixtures/netlists/minimal.net").read_bytes())},
                                   headers={"origin": "http://testserver"})
            assert uploaded.status_code == 201
            uploaded_id = uploaded.json()["id"]
            assert "RAW_UPLOAD_MARKER" not in uploaded.text
            raw = Path("tests/fixtures/netlists/minimal.net").read_bytes()
            imported = client.post(f"/api/projects/{project_id}/netlist", files={"file": ("circuit.txt", raw)}, headers={"origin": "http://testserver"})
            assert imported.status_code == 201, imported.text
            thread_id = imported.json()["thread_id"]
            assert imported.json()["project"]["id"] == project_id and imported.json()["project"]["circuit_version"] == 2
            assert client.get(f"/api/projects/{project_id}?thread_id={thread_id}").json() == imported.json()["project"]
            assert client.get(f"/api/projects/{uploaded_id}?thread_id={thread_id}").status_code == 404
            assert client.get(f"/api/projects/{project_id}?thread_id=invalid").status_code == 422
            client.cookies.set(auth.COOKIE, "admin-token")
            assert client.get("/api/projects").json() == []
            assert client.post(f"/api/projects/{project_id}/netlist", files={"file": ("circuit.net", raw)}, headers={"origin": "http://testserver"}).status_code == 404
            assert client.get(f"/api/projects/{project_id}?thread_id={thread_id}").status_code == 404
            for method, body in (("GET", None), ("PATCH", {"name": "stolen"}), ("DELETE", None)):
                errors = []
                for target in (project_id, uploaded_id, project_id + 10000):
                    result = client.request(method, f"/api/projects/{target}", json=body, headers={"origin": "http://testserver"})
                    assert result.status_code == 404
                    error = result.json()["error"]
                    assert error.pop("request_id") == result.headers["X-Request-ID"]
                    errors.append(error)
                assert all(error == {"code": "NOT_FOUND", "message": "프로젝트를 찾을 수 없습니다."} for error in errors)
            client.cookies.set(auth.COOKIE, "owner-token")
            assert client.delete(f"/api/projects/{project_id}", headers={"origin": "http://testserver"}).status_code == 204
            assert client.get(f"/api/projects/{project_id}").status_code == 404
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
