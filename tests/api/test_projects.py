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
    ("POST", "/api/projects/1/netlist", None), ("GET", "/api/projects/1/parts?circuit_version=1", None),
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
    assert response.json()["has_circuit"] is False


@pytest.mark.parametrize('kind', ['empty', 'demo', 'upload'])
def test_duplicate_warning_uses_safe_common_error_and_explicit_override(client, monkeypatch, kind):
    from backend.api.projects import repository
    from backend.projects.repository import DuplicateProject
    monkeypatch.setenv('DEMO_MODE', '1')
    app.dependency_overrides[auth.current_user_id] = lambda: 1
    calls = []
    class DuplicateRepository:
        def create(self, user_id, *args, **payload):
            calls.append((user_id, payload.get('allow_duplicate', False)))
            if not payload.get('allow_duplicate'):
                raise DuplicateProject([{'id': 5, 'name': '기존 프로젝트', 'matches': ['name', 'netlist']}])
            return {'id': 6, 'name': '새 프로젝트', 'source_kind': 'upload', 'demo_id': None,
                    'created_at': '2026-11-14T00:00:00Z', 'updated_at': '2026-11-14T00:00:00Z', 'connections': {}}
        create_empty = create_demo = create_upload = create
    app.dependency_overrides[repository] = lambda: DuplicateRepository()
    path = '/api/projects/upload' if kind == 'upload' else '/api/projects'
    def send(suffix=''):
        payload = {'name': '새 프로젝트'}
        if kind == 'upload':
            return client.post(path + suffix, data=payload, files={'file': ('different-name.net', Path('tests/fixtures/netlists/minimal.net').read_bytes())}, headers={'origin': 'http://testserver'})
        if kind == 'demo': payload['demo_id'] = 'breadboard_supply'
        return client.post(path + suffix, json=payload, headers={'origin': 'http://testserver'})
    response = send()
    assert response.status_code == 409
    assert response.json()['error']['code'] == 'CONFLICT'
    assert response.json()['error']['request_id'] == response.headers['X-Request-ID']
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert response.json()['details'] == {'duplicates': [{'id': 5, 'name': '기존 프로젝트', 'matches': ['name', 'netlist']}]}
    assert send('?allow_duplicate=invalid').status_code == 422
    assert send('?allow_duplicate=true').status_code == 201
    assert calls == [(1, False), (1, True)]


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
    ("/api/projects/upload", b"(not-export)", "KiCad 넷리스트(.net)로 다시 내보내 주세요. PDF·이미지 파일은 사용할 수 없습니다."),
    ("/api/projects/5/netlist", b"(not-export)", "KiCad 넷리스트(.net)로 다시 내보내 주세요. PDF·이미지 파일은 사용할 수 없습니다."),
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
    assert response.json() == {"error": {"code": "VALIDATION_ERROR", "message": ".net 넷리스트나 .kicad_sch 회로도 파일이 필요합니다.",
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
            duplicate = client.post('/api/projects/upload', data={'name': '다른 파일명'}, files={'file': ('renamed.net', raw)}, headers={'origin': 'http://testserver'})
            assert duplicate.status_code == 409
            assert duplicate.json()['details']['duplicates'] == [{'id': uploaded_id, 'name': '업로드', 'matches': ['netlist']}]
            copied = client.post('/api/projects/upload?allow_duplicate=true', data={'name': '복사본'}, files={'file': ('renamed.net', raw)}, headers={'origin': 'http://testserver'})
            assert copied.status_code == 201 and copied.json()['id'] != uploaded_id
            assert client.get(f'/api/projects/{uploaded_id}').json() == uploaded.json()
            assert client.delete(f"/api/projects/{copied.json()['id']}", headers={'origin': 'http://testserver'}).status_code == 204
            imported = client.post(f"/api/projects/{project_id}/netlist", files={"file": ("circuit.txt", raw)}, headers={"origin": "http://testserver"})
            assert imported.status_code == 201, imported.text
            thread_id = imported.json()["thread_id"]
            assert imported.json()["project"]["id"] == project_id and imported.json()["project"]["circuit_version"] == 2
            assert client.get(f"/api/projects/{project_id}?thread_id={thread_id}").json() == imported.json()["project"]
            assert client.get(f"/api/projects/{uploaded_id}?thread_id={thread_id}").status_code == 404
            assert client.get(f"/api/projects/{project_id}?thread_id=invalid").status_code == 422
            client.cookies.set(auth.COOKIE, "admin-token")
            assert client.get("/api/projects").json() == []
            own_upload = client.post('/api/projects/upload', data={'name': '업로드'}, files={'file': ('renamed.net', raw)}, headers={'origin': 'http://testserver'})
            assert own_upload.status_code == 201 and 'details' not in own_upload.json()
            assert client.delete(f"/api/projects/{own_upload.json()['id']}", headers={'origin': 'http://testserver'}).status_code == 204
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


SCHEMATIC = Path("tests/fixtures/netlists/minimal.kicad_sch").read_bytes()
HIERARCHICAL = SCHEMATIC.replace(b"(sheet_instances", b'(sheet (property "Sheetfile" "child.kicad_sch")) (sheet_instances', 1)


def png():
    import io
    from PIL import Image
    stream = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture
def fake_renderer(monkeypatch):
    """KiCad 렌더러 자리의 가짜 HTTP 서버(#52). mode: ok · invalid(422) · down(503) · offline(연결 실패) · garbage(넷리스트 아님)."""
    import base64
    import functools
    import json
    import httpx
    from backend.projects import external_schematic, schematic
    state = {"mode": "ok", "bodies": []}

    def respond(request):
        state["bodies"].append(json.loads(request.content))
        if state["mode"] == "offline":
            raise httpx.ConnectError("renderer offline")
        if state["mode"] in ("invalid", "down"):
            return httpx.Response(422 if state["mode"] == "invalid" else 503, json={"detail": "x"})
        netlist = "(not-export)" if state["mode"] == "garbage" else Path("tests/fixtures/netlists/minimal.net").read_text()
        return httpx.Response(200, json={"sheets": [base64.b64encode(png()).decode()], "netlist": netlist})
    monkeypatch.setenv("KICAD_RENDERER_URL", "http://renderer.test")
    monkeypatch.delenv("K_SERVICE", raising=False)
    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(schematic, "export_uploaded_kicad", functools.partial(schematic.export_uploaded_kicad, client=client))
    # [주의] 그림 캐시는 프로세스 전체가 같이 쓴다. 시험마다 업로드 그림을 비운다
    external_schematic._SERVICE.images.delete_matching(lambda key: isinstance(key, tuple) and key[:1] == ("upload",))
    yield state
    client.close()


def test_schematic_upload_takes_the_netlist_path_with_the_schematic_hash(upload_boundary, fake_renderer):
    import hashlib
    client, payloads, uploads, reads = upload_boundary
    response = client.post("/api/projects/upload", data={"name": "보드"}, files={"file": ("../dir/board.kicad_sch", SCHEMATIC)},
                           headers={"origin": "http://testserver"})
    assert response.status_code == 201, response.text
    (user_id, name, payload), = payloads
    assert (user_id, name) == (7, "보드")
    assert set(payload) == {"connections", "source_sha256", "parser_version", "schematic"}
    assert [part["ref"] for part in payload["connections"]["parts"]] == ["D1", "R1"]  # 렌더러가 내보낸 넷리스트를 .net과 같이 정규화
    # [왜] 내보낸 넷리스트에는 임시 경로 · 시각이 들어가 해시가 매번 다르다. 409 중복은 회로도 파일 해시로 본다
    assert payload["source_sha256"] == hashlib.sha256(SCHEMATIC).hexdigest()
    assert payload["schematic"] == ("board.kicad_sch", SCHEMATIC.decode())
    assert fake_renderer["bodies"] == [{"schematic": SCHEMATIC.decode()}]  # 사용자 경로 · 이름은 렌더러에 가지 않는다
    assert reads == [5 * 1024 * 1024 + 1] and all(upload.file.closed for upload in uploads)


@pytest.mark.parametrize("raw,mode,status,message,calls", [
    (HIERARCHICAL, "ok", 422, "하위 시트가 있는 회로도는 아직 지원하지 않아요. 넷리스트(.net)를 함께 올려 주세요.", 0),
    (b"(export (components))", "ok", 422, "회로도를 읽지 못했어요. KiCad 6 이상에서 저장한 .kicad_sch인지 확인해 주세요.", 0),
    (b"\xff", "ok", 422, "회로도를 읽지 못했어요. KiCad 6 이상에서 저장한 .kicad_sch인지 확인해 주세요.", 0),
    (SCHEMATIC, "invalid", 422, "회로도를 읽지 못했어요. KiCad 6 이상에서 저장한 .kicad_sch인지 확인해 주세요.", 1),
    (SCHEMATIC, "garbage", 422, "회로도를 읽지 못했어요. KiCad 6 이상에서 저장한 .kicad_sch인지 확인해 주세요.", 1),
    (SCHEMATIC, "down", 503, "회로도 그림 서버에 연결하지 못했어요. 넷리스트(.net)로 올려 주세요.", 1),
    (SCHEMATIC, "offline", 503, "회로도 그림 서버에 연결하지 못했어요. 넷리스트(.net)로 올려 주세요.", 1),
    (SCHEMATIC, "unset", 503, "회로도 그림 서버에 연결하지 못했어요. 넷리스트(.net)로 올려 주세요.", 0),
])
@pytest.mark.parametrize("path", ["/api/projects/upload", "/api/projects/5/netlist"])
def test_schematic_upload_errors_never_reach_storage(upload_boundary, fake_renderer, monkeypatch, path, raw, mode, status, message, calls):
    client, payloads, uploads, _ = upload_boundary
    fake_renderer["mode"] = mode
    if mode == "unset":
        monkeypatch.delenv("KICAD_RENDERER_URL")
    response = client.post(path, data={"name": "보드"} if path.endswith("/upload") else None,
                           files={"file": ("board.kicad_sch", raw)}, headers={"origin": "http://testserver"})
    assert response.status_code == status, response.text
    assert response.json()["error"]["message"] == message
    assert len(fake_renderer["bodies"]) == calls
    assert payloads == [] and all(upload.file.closed for upload in uploads)


def test_uploaded_schematic_is_owner_scoped_versioned_and_rendered_on_demand(client, fake_renderer, monkeypatch):
    from backend.projects import external_schematic
    url = os.getenv("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    schema = "projects_schematic_" + uuid4().hex
    origin = {"origin": "http://testserver"}
    clear = lambda: external_schematic._SERVICE.images.delete_matching(lambda key: isinstance(key, tuple) and key[:1] == ("upload",))
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(sql.Identifier(schema)))
        connect = lambda: psycopg.connect(url, options=f"-csearch_path={schema}")
        monkeypatch.setattr(auth, "connection", connect)
        try:
            with connect() as conn:
                apply_service_schema(conn)
                users = [row[0] for row in conn.execute("INSERT INTO users (login_id,password_hash,role) VALUES ('a@example.test','fake','user'),('b@example.test','fake','user') RETURNING id").fetchall()]
                for token, user_id in zip(("owner-token", "other-token"), users):
                    conn.execute("INSERT INTO auth_sessions (token_hash,user_id,expires_at) VALUES (%s,%s,CURRENT_TIMESTAMP + INTERVAL '1 hour')", (auth.session_token_hash(token), user_id))
            client.cookies.set(auth.COOKIE, "owner-token")
            created = client.post("/api/projects/upload", data={"name": "보드"}, files={"file": ("board.kicad_sch", SCHEMATIC)}, headers=origin)
            assert created.status_code == 201, created.text
            project = created.json()
            pid = project["id"]
            assert (project["circuit_version"], project["schematic_file"]) == (1, "board.kicad_sch")
            assert client.get(f"/api/projects/{pid}").json()["schematic_file"] == "board.kicad_sch"
            # 같은 회로도는 .net과 같은 409 규칙(같은 파일 내용 = netlist)
            duplicate = client.post("/api/projects/upload", data={"name": "다른 이름"}, files={"file": ("copy.kicad_sch", SCHEMATIC)}, headers=origin)
            assert duplicate.status_code == 409
            assert duplicate.json()["details"]["duplicates"] == [{"id": pid, "name": "보드", "matches": ["netlist"]}]
            # 업로드 때 받은 그림을 캐시에서 쓰고, 캐시가 비면 저장한 원문으로 다시 그린다
            calls = len(fake_renderer["bodies"])
            image = client.get(f"/api/projects/{pid}/schematic?circuit_version=1")
            assert image.status_code == 200 and image.content == png() and image.headers["content-type"] == "image/png"
            assert image.headers["cache-control"] == "private, no-store" and len(fake_renderer["bodies"]) == calls
            clear()
            assert client.get(f"/api/projects/{pid}/schematic?circuit_version=1").content == png()
            assert fake_renderer["bodies"][-1] == {"schematic": SCHEMATIC.decode()} and len(fake_renderer["bodies"]) == calls + 1
            clear()
            fake_renderer["mode"] = "down"
            assert client.get(f"/api/projects/{pid}/schematic?circuit_version=1").status_code == 503
            fake_renderer["mode"] = "ok"
            assert client.get(f"/api/projects/{pid}/schematic").status_code == 422  # 회로 버전은 꼭 준다
            # 넷리스트로 바꾼 버전에는 회로도가 없고, 회로도로 바꾼 버전에는 있다. 이전 버전 그림은 그대로
            net = client.post(f"/api/projects/{pid}/netlist", files={"file": ("c.net", Path("tests/fixtures/netlists/minimal.net").read_bytes())}, headers=origin)
            assert net.status_code == 201 and (net.json()["project"]["circuit_version"], net.json()["project"]["schematic_file"]) == (2, None)
            assert client.get(f"/api/projects/{pid}/schematic?circuit_version=2").status_code == 404
            sch = client.post(f"/api/projects/{pid}/netlist", files={"file": ("v3.kicad_sch", SCHEMATIC)}, headers=origin)
            assert sch.status_code == 201 and (sch.json()["project"]["circuit_version"], sch.json()["project"]["schematic_file"]) == (3, "v3.kicad_sch")
            thread = net.json()["thread_id"]
            assert client.get(f"/api/projects/{pid}?thread_id={thread}").json()["schematic_file"] is None  # 대화가 고정한 버전 기준
            assert client.get(f"/api/projects/{pid}/schematic?circuit_version=3").status_code == 200
            assert client.get(f"/api/projects/{pid}/schematic?circuit_version=1").status_code == 200
            # 다른 사용자는 프로젝트도 그림도 404
            client.cookies.set(auth.COOKIE, "other-token")
            for version in (1, 3):
                denied = client.get(f"/api/projects/{pid}/schematic?circuit_version={version}")
                assert denied.status_code == 404 and denied.json()["error"]["code"] == "NOT_FOUND"
            assert client.get(f"/api/projects/{pid}").status_code == 404
            # 프로젝트를 지우면 원문도 함께 지워진다(FK CASCADE)
            client.cookies.set(auth.COOKIE, "owner-token")
            assert client.delete(f"/api/projects/{pid}", headers=origin).status_code == 204
            with connect() as conn:
                assert conn.execute("SELECT count(*) FROM circuit_schematics").fetchone()[0] == 0
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


# 부품 점검표(#68) 시험 회로: 다이오드 둘(D1 · D10) · LED(D2) · 저항 둘 · IC. 순서를 섞어 자연 정렬도 본다
PARTS_CIRCUIT = {"parts": [
    {"ref": "U1", "value": "ATtiny85-20SU", "footprint": "Package_SO:SOIC-8", "symbol": "MCU_Microchip_ATtiny:ATtiny85-20SU"},
    {"ref": "D10", "value": "BAT54", "footprint": "Package_TO_SOT_SMD:SOT-23", "symbol": "Device:D_Schottky"},
    {"ref": "R2", "value": "1k", "footprint": "Resistor_SMD:R_0603", "symbol": "Device:R"},
    {"ref": "D2", "value": "LED", "footprint": "LED_SMD:LED_0805", "symbol": "Device:LED"},
    {"ref": "D1", "value": "1N4148", "footprint": "Diode_SMD:D_SOD-123", "symbol": "Device:D"},
    {"ref": "R1", "value": "10k", "footprint": "Resistor_SMD:R_0603", "symbol": "Device:R"},
], "nets": []}


def test_parts_check_reuses_kind_support_and_corpus_rules_owner_only(client, monkeypatch):
    """종류 · 개수는 part_kind, 판정 지원은 _require_supported_target, 데이터시트는 corpus_known 대조와 같다. 남의 프로젝트 · 없는 버전은 404."""
    from fastapi import HTTPException
    from backend.conversations.memory_service import _require_supported_target
    from backend.projects.repository import ProjectRepository
    from backend.rag import retrieve
    url = os.getenv("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    looked = []
    def corpus_known():  # [왜] 진짜는 검색 색인(DB 전체 청크)을 만든다. 사실 확인 도구(check_corpus)가 쓰는 소문자 품번 집합만 흉내 낸다
        looked.append(1)
        return {"1n4148"}, {"K2301"}
    monkeypatch.setattr(retrieve, "corpus_known", corpus_known)
    schema = "projects_parts_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(sql.Identifier(schema)))
        connect = lambda: psycopg.connect(url, options=f"-csearch_path={schema}")
        monkeypatch.setattr(auth, "connection", connect)
        try:
            with connect() as conn:
                apply_service_schema(conn)
                users = [row[0] for row in conn.execute("INSERT INTO users (login_id,password_hash,role) VALUES ('a@example.test','fake','user'),('b@example.test','fake','user') RETURNING id").fetchall()]
                for token, user_id in zip(("owner-token", "other-token"), users):
                    conn.execute("INSERT INTO auth_sessions (token_hash,user_id,expires_at) VALUES (%s,%s,CURRENT_TIMESTAMP + INTERVAL '1 hour')", (auth.session_token_hash(token), user_id))
            repo = ProjectRepository()
            pid = repo.create_upload(users[0], "부품 회로", connections=PARTS_CIRCUIT, source_sha256="a" * 64, parser_version="test").id
            empty = repo.create_empty(users[0], "빈 프로젝트").id
            client.cookies.set(auth.COOKIE, "owner-token")
            response = client.get(f"/api/projects/{pid}/parts?circuit_version=1")
            assert response.status_code == 200, response.text
            body = response.json()
            rows = {row["ref"]: row for row in body["parts"]}
            assert [row["ref"] for row in body["parts"]] == ["D1", "D2", "D10", "R1", "R2", "U1"]
            assert {ref: (row["kind"], row["kind_name"]) for ref, row in rows.items()} == {
                "D1": ("diode", "다이오드"), "D2": ("led", "LED"), "D10": ("diode", "다이오드"),
                "R1": ("resistor", "저항"), "R2": ("resistor", "저항"), "U1": ("ic", "IC")}
            assert body["counts"] == [{"kind": "diode", "name": "다이오드", "count": 2}, {"kind": "resistor", "name": "저항", "count": 2},
                                      {"kind": "led", "name": "LED", "count": 1}, {"kind": "ic", "name": "IC", "count": 1}]
            # 판정 지원은 판정이 대상을 받는지와 같다(서버 422를 그대로 따른다)
            for ref, row in rows.items():
                try:
                    _require_supported_target(PARTS_CIRCUIT, ref)
                    supported = True
                except HTTPException:
                    supported = False
                assert row["judge_supported"] is supported, ref
            assert {ref: row["judge_reason"] for ref, row in rows.items()} == {
                "D1": None, "D10": None, "D2": "LED라서", "R1": "다이오드가 아니라서", "R2": "다이오드가 아니라서", "U1": "다이오드가 아니라서"}
            assert {ref: row["datasheet"] for ref, row in rows.items()} == {
                "D1": "1N4148", "D2": None, "D10": None, "R1": None, "R2": None, "U1": None}
            assert rows["U1"] == {"ref": "U1", "value": "ATtiny85-20SU", "footprint": "Package_SO:SOIC-8", "symbol": "MCU_Microchip_ATtiny:ATtiny85-20SU",
                            "kind": "ic", "kind_name": "IC", "judge_supported": False, "judge_reason": "다이오드가 아니라서", "datasheet": None}
            # 회로 없는 v0은 빈 표이고 코퍼스를 읽지 않는다
            calls = len(looked)
            assert client.get(f"/api/projects/{empty}/parts?circuit_version=0").json() == {"circuit_version": 0, "parts": [], "counts": []}
            assert len(looked) == calls
            assert client.get(f"/api/projects/{pid}/parts?circuit_version=2").status_code == 404  # 없는 버전
            assert client.get(f"/api/projects/{pid}/parts").status_code == 422  # 회로 버전은 꼭 준다
            client.cookies.set(auth.COOKIE, "other-token")
            denied = client.get(f"/api/projects/{pid}/parts?circuit_version=1")
            assert denied.status_code == 404 and denied.json()["error"]["code"] == "NOT_FOUND"
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
