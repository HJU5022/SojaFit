"""실제 격리 PostgreSQL에서 프로젝트 소유권·원자성·제약을 검증한다."""
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from backend import auth
from tests.db_schema import apply_service_schema


@pytest.fixture
def storage(monkeypatch):
    url = os.getenv("TEST_AUTH_DATABASE_URL")
    if not url:
        pytest.skip("requires an isolated authentication test database")
    schema = "projects_test_" + uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION CURRENT_USER").format(sql.Identifier(schema)))
        connect = lambda: psycopg.connect(url, options=f"-csearch_path={schema}")
        monkeypatch.setattr(auth, "connection", connect)
        try:
            with connect() as conn:
                apply_service_schema(conn)
                users = [row[0] for row in conn.execute(
                    "INSERT INTO users (login_id, password_hash, role) VALUES "
                    "('owner@example.test', 'fake', 'user'), ('other@example.test', 'fake', 'admin') RETURNING id"
                ).fetchall()]
            from backend.projects.repository import ProjectRepository
            yield ProjectRepository(), users, connect
        finally:
            admin.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_invalid_demo_never_opens_database(monkeypatch):
    from backend.projects.repository import InvalidProject, ProjectRepository
    def unexpected_connection():
        pytest.fail("invalid input must be rejected before connecting")
    monkeypatch.setattr(auth, "connection", unexpected_connection)
    for demo_id, name in (("../secrets", "회로"), ("breadboard_supply", "   "), ("breadboard_supply", "x" * 201)):
        with pytest.raises(InvalidProject):
            ProjectRepository().create_demo(1, demo_id, name)


def test_schematic_comparison_reads_owned_thread_circuit_version(storage):
    import json
    from fastapi import HTTPException
    from backend.api.external_circuits import _project_circuit
    from backend.projects.netlist import normalize_netlist, circuit_fingerprint
    repo,(owner,other),_=storage
    normalized=normalize_netlist(Path('tests/fixtures/netlists/minimal.net').read_bytes())
    project=repo.create_upload(owner,'회로도 대조',connections=normalized.connections,source_sha256=normalized.source_sha256,parser_version='test')
    first,thread=repo.import_netlist(owner,project.id,connections=normalized.connections,source_sha256=normalized.source_sha256,parser_version='test')
    changed=json.loads(json.dumps(normalized.connections,default=dict));changed['nets'][0]['nodes'][0]['pin']='99'
    latest,_=repo.import_netlist(owner,project.id,connections=changed,source_sha256='f'*64,parser_version='test')
    assert circuit_fingerprint(_project_circuit(owner,project.id,first.circuit_version,thread).connections)==circuit_fingerprint(normalized.connections)
    assert circuit_fingerprint(_project_circuit(owner,project.id,latest.circuit_version,None).connections)!=circuit_fingerprint(normalized.connections)
    with pytest.raises(HTTPException) as denied:_project_circuit(other,project.id,first.circuit_version,thread)
    assert denied.value.status_code==404


def test_received_demo_circuit_is_read_from_its_own_folder(monkeypatch):
    """[왜] c01(키 없는 데모 v3-01의 회로)은 samples/가 아니라 received-20261030/c01에 있다. DB 없이 넣는 값만 본다."""
    import hashlib
    import json
    from backend.projects.repository import ProjectRepository, demo_path
    sent = []

    class Conn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, query, params): sent.append(params); return self
        def fetchone(self): return (5,)
    monkeypatch.setattr(auth, "connection", Conn)
    monkeypatch.setattr(ProjectRepository, "_get_owned", lambda self, conn, user_id, project_id: project_id)
    monkeypatch.setattr(ProjectRepository, "_check_duplicates", lambda *args, **kwargs: None)
    assert ProjectRepository().create_demo(1, "attiny85_time_switch", "타임 스위치") == 5
    source = demo_path("attiny85_time_switch").read_bytes()
    assert demo_path("attiny85_time_switch").as_posix().endswith("received-20261030/c01/connections.json")
    assert sent[0] == (1, "타임 스위치", "attiny85_time_switch")
    assert sent[1][1].obj == json.loads(source) and sent[1][2] == hashlib.sha256(source).hexdigest()


def test_received_demo_circuit_is_stored_and_owned(storage):
    repo, (owner, other), _ = storage
    project = repo.create_demo(owner, "attiny85_time_switch", "타임 스위치")
    assert project.demo_id == "attiny85_time_switch" and "D1" in {p["ref"] for p in project.connections["components"]}
    assert repo.list_owned(other) == []


def test_upload_stores_only_normalized_data_and_remains_owned(storage):
    import hashlib
    from backend.projects.netlist import normalize_netlist
    from backend.projects.repository import ProjectNotFound
    repo, (owner, other), connect = storage
    raw = Path("tests/fixtures/netlists/minimal.net").read_bytes()
    normalized = normalize_netlist(raw)
    project = repo.create_upload(owner, "업로드", connections=normalized.connections,
                                 source_sha256=normalized.source_sha256, parser_version="kicad-export-v1")
    assert project.source_kind == "upload" and project.demo_id is None
    assert set(project.connections) == {"parts", "nets"}
    with connect() as conn:
        row = conn.execute("SELECT row_to_json(circuits) FROM circuits WHERE project_id=%s", (project.id,)).fetchone()[0]
    assert set(row) == {"project_id", "connections", "source_sha256", "parser_version", "created_at", "version"}
    assert row["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert row["parser_version"] == "kicad-export-v1"
    assert "RAW_UPLOAD_MARKER" not in str(row)
    assert repo.list_owned(other) == []
    with pytest.raises(ProjectNotFound):
        repo.get_owned(other, project.id)
    with connect() as conn:
        conn.execute("ALTER TABLE circuits ADD CONSTRAINT reject_upload CHECK (false) NOT VALID")
    with pytest.raises(psycopg.errors.CheckViolation):
        repo.create_upload(owner, "rollback", connections=normalized.connections,
                           source_sha256=normalized.source_sha256, parser_version="kicad-export-v1", allow_duplicate=True)
    assert [item.id for item in repo.list_owned(owner)] == [project.id]


def test_every_repository_boundary_is_owner_scoped(storage):
    from backend.projects.repository import ProjectNotFound
    repo, (owner, other), _ = storage
    project = repo.create_demo(owner, "breadboard_supply", "전원 회로")
    assert repo.get_owned(owner, project.id).connections["components"][3]["ref"] == "D1"
    assert [p.id for p in repo.list_owned(owner)] == [project.id]
    assert repo.list_owned(other) == []
    for target in (project.id, project.id + 100000):
        for operation in (repo.get_owned, repo.delete_owned):
            with pytest.raises(ProjectNotFound):
                operation(other, target)
        with pytest.raises(ProjectNotFound):
            repo.rename_owned(other, target, "stolen")
    renamed = repo.rename_owned(owner, project.id, " 새 이름 ")
    assert renamed.name == "새 이름"
    assert renamed.updated_at >= project.updated_at
    assert renamed.connections == project.connections


def test_project_and_user_delete_cascade_circuits(storage):
    repo, (owner, _), connect = storage
    first = repo.create_demo(owner, "breadboard_supply", "첫 회로")
    second = repo.create_demo(owner, "attiny85_dev", "다음 회로")
    repo.delete_owned(owner, first.id)
    with connect() as conn:
        assert conn.execute("SELECT 1 FROM circuits WHERE project_id=%s", (first.id,)).fetchone() is None
        conn.execute("DELETE FROM users WHERE id=%s", (owner,))
    assert repo.list_owned(owner) == []
    with connect() as conn:
        assert conn.execute("SELECT 1 FROM circuits WHERE project_id=%s", (second.id,)).fetchone() is None


def test_circuit_insert_failure_rolls_back_project(storage):
    repo, (owner, _), connect = storage
    with connect() as conn:
        conn.execute("ALTER TABLE circuits ADD CONSTRAINT reject_test_insert CHECK (false)")
    with pytest.raises(psycopg.errors.CheckViolation):
        repo.create_demo(owner, "breadboard_supply", "실패 회로")
    assert repo.list_owned(owner) == []


def test_empty_project_imports_versions_and_preserves_old_threads(storage):
    from backend.conversations.repository import ConversationRepository
    from backend.projects.netlist import normalize_netlist, PARSER_VERSION
    from backend.projects.repository import ProjectNotFound
    repo, (owner, other), connect = storage
    conversations = ConversationRepository()
    empty = repo.create_empty(owner, "빈 회로")
    assert empty.circuit_version == 0 and empty.connections == {"parts": [], "nets": []}
    empty_thread = conversations.create_thread(owner, empty.id)
    raw = Path("tests/fixtures/netlists/minimal.net").read_bytes()
    first = normalize_netlist(raw)
    def import_file(normalized):
        return repo.import_netlist(owner, empty.id, connections=normalized.connections,
                                   source_sha256=normalized.source_sha256, parser_version=PARSER_VERSION)
    project, thread1 = import_file(first)
    assert project.id == empty.id and project.circuit_version == 1
    run, circuit = conversations.start(owner, thread1, {"question": "D1 질문"})
    conversations.finish(owner, thread1, run, "requires_input")
    second = normalize_netlist(raw.replace(b"D1", b"D9"))
    project2, thread2 = import_file(second)
    assert project2.id == empty.id and project2.circuit_version == 2 and thread1 != thread2
    assert repo.get_owned(owner, empty.id, thread1).connections == project.connections
    assert repo.get_owned(owner, empty.id, empty_thread).circuit_version == 0
    assert conversations.get_thread(owner, thread1)[2] == circuit
    assert conversations.get_thread(owner, thread2)[2] == project2.connections
    conversations.resume(owner, thread1, run)
    assert conversations.get_thread(owner, thread1)[2] == circuit
    latest_thread = conversations.create_thread(owner, empty.id)
    assert repo.get_owned(owner, empty.id, latest_thread).circuit_version == 2
    foreign = repo.create_empty(owner, "다른 프로젝트")
    for user, project_id in ((other, empty.id), (owner, foreign.id)):
        with pytest.raises(ProjectNotFound):
            repo.get_owned(user, project_id, thread1)
    with connect() as conn:
        conn.execute("ALTER TABLE threads ADD CONSTRAINT reject_new_thread CHECK (false) NOT VALID")
    with pytest.raises(psycopg.errors.CheckViolation):
        import_file(first)
    assert repo.get_owned(owner, empty.id).circuit_version == 2
    with connect() as conn:
        assert conn.execute("SELECT max(version) FROM project_circuit_versions WHERE project_id=%s", (empty.id,)).fetchone()[0] == 2
    repo.delete_owned(owner, empty.id)
    with connect() as conn:
        assert conn.execute("SELECT count(*) FROM project_circuit_versions WHERE project_id=%s", (empty.id,)).fetchone()[0] == 0


def test_schema_restricts_public_access_and_indexes_foreign_keys(storage):
    _, (owner, _), connect = storage
    with connect() as conn:
        rows = conn.execute(
            "SELECT relname, relrowsecurity, EXISTS (SELECT 1 FROM aclexplode(coalesce(relacl, acldefault('r', relowner))) a WHERE a.grantee=0) "
            "FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relname IN ('projects', 'circuits')"
        ).fetchall()
        assert len(rows) == 2
        assert all(rls and not public_access for _, rls, public_access in rows)
        for role in ("anon", "authenticated"):
            if conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                for table in ("projects", "circuits"):
                    assert conn.execute("SELECT has_table_privilege(%s, %s, 'SELECT,INSERT,UPDATE,DELETE')", (role, table)).fetchone() == (False,)
                assert conn.execute("SELECT has_sequence_privilege(%s, 'projects_id_seq', 'USAGE,SELECT,UPDATE')", (role,)).fetchone() == (False,)
        assert conn.execute(
            "SELECT count(*) FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=i.indkey[0] "
            "WHERE i.indrelid='projects'::regclass AND a.attname='user_id' AND i.indisvalid"
        ).fetchone()[0] >= 1
        assert conn.execute("SELECT data_type FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='circuits' AND column_name='project_id'").fetchone() == ("bigint",)
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("INSERT INTO projects (user_id,name,source_kind) VALUES (%s,'invalid','unknown')", (owner,))
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("INSERT INTO projects (user_id,name,source_kind) VALUES (%s,'   ','upload')", (owner,))


def test_demo_check_requires_demo_id_only_for_demo_projects(storage):
    # [왜] 11-10 DEMOS에 c01을 더하고 DB 허용 목록을 빠뜨려 데모 생성이 503이 됐다. 새 CHECK(ck_projects_demo)는 목록 없이 "데모일 때만 demo_id"만 보므로
    #      목록 대조 시험 대신 (1) 카탈로그의 모든 데모가 실제로 저장되고 (2) 규칙 위반을 DB가 거부하는지 본다
    from backend.projects.repository import DEMOS
    repo, (owner, _), connect = storage
    for demo_id in DEMOS:
        assert repo.create_demo(owner, demo_id, f"데모 {demo_id}").demo_id == demo_id
    with connect() as conn:
        assert conn.execute("INSERT INTO projects (user_id,name,source_kind) VALUES (%s,'업로드','upload') RETURNING demo_id", (owner,)).fetchone() == (None,)
        for kind, demo_id in (("demo", None), ("upload", "breadboard_supply")):
            with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
                conn.execute("INSERT INTO projects (user_id,name,source_kind,demo_id) VALUES (%s,'위반',%s,%s)", (owner, kind, demo_id))
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("INSERT INTO projects (user_id,name,source_kind) VALUES (%s,'demo without id','demo')", (owner,))
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("INSERT INTO projects (user_id,name,source_kind,demo_id) VALUES (%s,'upload with id','upload','breadboard_supply')", (owner,))


def test_duplicate_name_is_owned_and_requires_explicit_confirmation(storage):
    from backend.projects.repository import DuplicateProject
    repo, (owner, other), _ = storage
    original = repo.create_empty(owner, ' Board ')
    with pytest.raises(DuplicateProject) as raised:
        repo.create_empty(owner, ' board ')
    assert raised.value.projects == [{'id': original.id, 'name': 'Board', 'matches': ['name']}]
    assert [p.id for p in repo.list_owned(owner)] == [original.id]
    assert repo.create_empty(other, 'board').id != original.id
    copy = repo.create_empty(owner, 'board', allow_duplicate=True)
    assert copy.id != original.id and repo.get_owned(owner, original.id).name == 'Board'


def test_duplicate_upload_and_demo_content_are_checked_before_inserting(storage):
    from backend.projects.netlist import normalize_netlist, PARSER_VERSION
    from backend.projects.repository import DuplicateProject
    repo, (owner, other), _ = storage
    circuit = normalize_netlist(Path('tests/fixtures/netlists/minimal.net').read_bytes())
    payload = dict(connections=circuit.connections, source_sha256=circuit.source_sha256, parser_version=PARSER_VERSION)
    original = repo.create_upload(owner, '원본', **payload)
    with pytest.raises(DuplicateProject) as raised:
        repo.create_upload(owner, '다른 파일명', **payload)
    assert raised.value.projects == [{'id': original.id, 'name': '원본', 'matches': ['netlist']}]
    assert repo.create_upload(other, '원본', **payload).id != original.id
    copy = repo.create_upload(owner, '복사', allow_duplicate=True, **payload)
    assert copy.id != original.id and len(repo.list_owned(owner)) == 2
    demo = repo.create_demo(owner, 'breadboard_supply', '데모')
    with pytest.raises(DuplicateProject):
        repo.create_demo(owner, 'breadboard_supply', '다른 데모 이름')
    assert repo.create_demo(owner, 'breadboard_supply', '명시적 복사', allow_duplicate=True).id != demo.id


def test_concurrent_creations_cannot_silently_skip_duplicate_warning(storage):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from backend.projects.repository import DuplicateProject
    repo, (owner, _), _ = storage
    ready = Barrier(2)
    def create():
        ready.wait(timeout=5)
        try:
            return repo.create_empty(owner, '동시 생성').id
        except DuplicateProject:
            return 'duplicate'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: create(), range(2)))
    assert results.count('duplicate') == 1 and len(repo.list_owned(owner)) == 1
