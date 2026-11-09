"""실제 격리 PostgreSQL에서 프로젝트 소유권·원자성·제약을 검증한다."""
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from backend import auth


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
                for name in ("003_auth.sql", "005_auth_attempt_window.sql", "006_user_roles.sql", "018_projects.sql"):
                    conn.execute(Path("db", name).read_text(encoding="utf-8-sig"))
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
    assert set(row) == {"project_id", "connections", "source_sha256", "parser_version", "created_at"}
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
                           source_sha256=normalized.source_sha256, parser_version="kicad-export-v1")
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
