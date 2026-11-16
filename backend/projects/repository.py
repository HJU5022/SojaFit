"""소유자 조건을 포함한 프로젝트 SQL. 데모 또는 정규화 연결 JSON을 저장하고, 넷리스트 원문은 저장하지 않는다. 올린 회로도(.kicad_sch)만 원문을 그 회로 버전에 둔다(#52)."""
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend import auth
from backend.conversations.repository import pinned_version
from backend.projects.catalog import catalog_by_id, load_catalog
from backend.projects.models import Project, ProjectSummary

DEMOS = {item.id: item.name for item in load_catalog()}
FIELDS = "id, name, source_kind, demo_id, created_at, updated_at"


class ProjectNotFound(Exception):
    """없는 프로젝트와 다른 사용자의 프로젝트는 구별하지 않는다."""


class InvalidProject(ValueError):
    """알 수 없는 데모 또는 잘못된 프로젝트 이름."""


class DuplicateProject(Exception):
    """소유자에게만 공개할 중복 후보. 원본과 해시는 포함하지 않는다."""
    def __init__(self, projects: list[dict]):
        self.projects = projects


def demo_path(demo_id: str) -> Path:
    """카탈로그(DEMOS)에 있는 데모 회로의 연결 정보 파일. 키 없는 데모 재생도 이 경로로 기록 질문의 회로를 잇는다."""
    item = catalog_by_id().get(demo_id)
    if item is None:
        raise InvalidProject("등록된 데모 회로를 선택해 주세요.")
    return item.connections_path


def project_name(name: str) -> str:
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
        raise InvalidProject("프로젝트 이름은 1~200자여야 합니다.")
    return name.strip()


class ProjectRepository:
    def _check_duplicates(self, conn, user_id, name, source_sha256=None, *, allow_duplicate=False):
        # 같은 계정의 동시 생성도 검사와 INSERT 사이에 끼어들지 못하게 한다.
        conn.execute('SELECT id FROM users WHERE id=%s FOR UPDATE', (user_id,))
        if allow_duplicate:
            return
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute('SELECT p.id,p.name,lower(btrim(p.name))=lower(%s) AS same_name,'
                        'c.source_sha256=%s AS same_netlist FROM projects p LEFT JOIN circuits c ON c.project_id=p.id '
                        'WHERE p.user_id=%s AND (lower(btrim(p.name))=lower(%s) OR c.source_sha256=%s) '
                        'ORDER BY p.updated_at DESC,p.id DESC LIMIT 5', (name, source_sha256, user_id, name, source_sha256))
            matches = [{'id': row['id'], 'name': row['name'],
                        'matches': [key for key, same in (('name', row['same_name']), ('netlist', row['same_netlist'])) if same]}
                       for row in cur.fetchall()]
        if matches:
            raise DuplicateProject(matches)

    def create_empty(self, user_id: int, name: str, *, allow_duplicate=False) -> Project:
        name = project_name(name)
        with auth.connection() as conn:
            self._check_duplicates(conn, user_id, name, allow_duplicate=allow_duplicate)
            project_id = conn.execute("INSERT INTO projects(user_id,name,source_kind) VALUES (%s,%s,'upload') RETURNING id",
                                      (user_id, name)).fetchone()[0]
            return self._get_owned(conn, user_id, project_id)

    def import_netlist(self, user_id: int, project_id: int, *, connections, source_sha256: str, parser_version: str, thread_id=None, schematic=None):
        """회로를 올리고 (프로젝트, 대화 id)를 돌려준다. 대화는 새로 만든다.

        회로가 없던 프로젝트에 그 프로젝트의 회로 없는 대화(버전 0) thread_id를 주면 새 대화를 만들지 않고 그 대화를 돌려준다.
        그 대화는 이 회로를 읽는다(`pinned_version`). 조건이 맞지 않는 thread_id는 무시하고 지금처럼 새 대화를 만든다.
        """
        with auth.connection() as conn:
            if conn.execute('SELECT id FROM projects WHERE id=%s AND user_id=%s FOR UPDATE', (project_id, user_id)).fetchone() is None:
                raise ProjectNotFound
            # [주의] 회로를 올리기 전에 본다. 프로젝트 행을 잠가 같은 프로젝트의 동시 첨부와 겹치지 않는다
            same = thread_id is not None and conn.execute(
                'SELECT 1 FROM threads t WHERE t.id=%s AND t.project_id=%s AND t.circuit_version=0 '
                'AND NOT EXISTS (SELECT 1 FROM circuits c WHERE c.project_id=t.project_id)', (thread_id, project_id)).fetchone() is not None
            conn.execute("UPDATE projects SET source_kind='upload',demo_id=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=%s AND user_id=%s", (project_id, user_id))
            version = conn.execute('INSERT INTO circuits(project_id,connections,source_sha256,parser_version) VALUES (%s,%s,%s,%s) '
                         'ON CONFLICT (project_id) DO UPDATE SET connections=EXCLUDED.connections,source_sha256=EXCLUDED.source_sha256,'
                         'parser_version=EXCLUDED.parser_version,version=circuits.version+1,created_at=CURRENT_TIMESTAMP RETURNING version',
                         (project_id, Jsonb(connections, dumps=lambda value: json.dumps(value, default=dict)), source_sha256, parser_version)).fetchone()[0]
            self._save_schematic(conn, project_id, version, schematic)
            if not same:
                thread_id = uuid4()
                conn.execute('INSERT INTO threads(id,project_id) VALUES (%s,%s)', (thread_id, project_id))
            return self._get_owned(conn, user_id, project_id), str(thread_id)

    def create_upload(self, user_id: int, name: str, *, connections, source_sha256: str, parser_version: str, allow_duplicate=False, schematic=None) -> Project:
        name = project_name(name)
        with auth.connection() as conn:
            self._check_duplicates(conn, user_id, name, source_sha256, allow_duplicate=allow_duplicate)
            project_id = conn.execute(
                "INSERT INTO projects (user_id, name, source_kind) VALUES (%s, %s, 'upload') RETURNING id",
                (user_id, name),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO circuits (project_id, connections, source_sha256, parser_version) VALUES (%s, %s, %s, %s)",
                (project_id, Jsonb(connections, dumps=lambda value: json.dumps(value, default=dict)), source_sha256, parser_version),
            )
            self._save_schematic(conn, project_id, 1, schematic)
            return self._get_owned(conn, user_id, project_id)

    @staticmethod
    def _save_schematic(conn, project_id, version, schematic):
        """올린 회로도 원문을 방금 만든 회로 버전에 붙인다(#52). schematic은 None이거나 (파일 이름, 원문)."""
        if schematic is not None:
            conn.execute('INSERT INTO circuit_schematics(project_id,circuit_version,file_name,source) VALUES (%s,%s,%s,%s)',
                         (project_id, version, *schematic))

    def uploaded_schematic(self, user_id: int, project_id: int, circuit_version: int) -> str:
        """그 사용자 프로젝트의 그 회로 버전에 올린 회로도 원문. 없거나 남의 것이면 ProjectNotFound."""
        with auth.connection() as conn:
            row = conn.execute('SELECT s.source FROM circuit_schematics s JOIN projects p ON p.id=s.project_id '
                               'WHERE p.user_id=%s AND s.project_id=%s AND s.circuit_version=%s',
                               (user_id, project_id, circuit_version)).fetchone()
        if row is None:
            raise ProjectNotFound
        return row[0]

    def create_demo(self, user_id: int, demo_id: str, name: str, *, allow_duplicate=False) -> Project:
        name = project_name(name)
        if demo_id not in DEMOS:
            raise InvalidProject("등록된 데모 회로를 선택해 주세요.")
        # 사용자 입력을 경로로 사용하지 않고 허용된 카탈로그에서만 고른다.
        source = demo_path(demo_id).read_bytes()
        connections = json.loads(source)
        with auth.connection() as conn:
            self._check_duplicates(conn, user_id, name, hashlib.sha256(source).hexdigest(), allow_duplicate=allow_duplicate)
            project_id = conn.execute(
                "INSERT INTO projects (user_id, name, source_kind, demo_id) VALUES (%s, %s, 'demo', %s) RETURNING id",
                (user_id, name, demo_id),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO circuits (project_id, connections, source_sha256, parser_version) VALUES (%s, %s, %s, %s)",
                (project_id, Jsonb(connections), hashlib.sha256(source).hexdigest(), "demo-connections-v1"),
            )
            return self._get_owned(conn, user_id, project_id)

    def list_owned(self, user_id: int) -> list[ProjectSummary]:
        with auth.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"SELECT {FIELDS}, COALESCE((SELECT version FROM circuits WHERE project_id=projects.id),0) AS circuit_version FROM projects WHERE user_id=%s ORDER BY updated_at DESC, id DESC", (user_id,))
            return [ProjectSummary(**row) for row in cur.fetchall()]

    def get_owned(self, user_id: int, project_id: int, thread_id=None) -> Project:
        with auth.connection() as conn:
            return self._get_owned(conn, user_id, project_id, thread_id)

    def _get_owned(self, conn, user_id: int, project_id: int, thread_id=None) -> Project:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT p.id, p.name, v.source_kind, v.demo_id, p.created_at, p.updated_at, v.connections,v.version AS circuit_version,"
                "(SELECT s.file_name FROM circuit_schematics s WHERE s.project_id=v.project_id AND s.circuit_version=v.version) AS schematic_file "
                "FROM projects p LEFT JOIN circuits c ON c.project_id=p.id "
                "LEFT JOIN threads t ON t.project_id=p.id AND t.id=%s::uuid "
                f"JOIN project_circuit_versions v ON v.project_id=p.id AND v.version=CASE WHEN %s::uuid IS NULL THEN COALESCE(c.version,0) ELSE {pinned_version('t')} END "
                "WHERE p.user_id=%s AND p.id=%s",
                (thread_id, thread_id, user_id, project_id),
            )
            row = cur.fetchone()
        if row is None:
            raise ProjectNotFound
        return Project(**row)

    def rename_owned(self, user_id: int, project_id: int, name: str) -> Project:
        name = project_name(name)
        with auth.connection() as conn:
            row = conn.execute(
                "UPDATE projects SET name=%s, updated_at=CURRENT_TIMESTAMP WHERE user_id=%s AND id=%s RETURNING id",
                (name, user_id, project_id),
            ).fetchone()
            if row is None:
                raise ProjectNotFound
            return self._get_owned(conn, user_id, project_id)

    def delete_owned(self, user_id: int, project_id: int) -> None:
        with auth.connection() as conn:
            if conn.execute("DELETE FROM projects WHERE user_id=%s AND id=%s RETURNING id", (user_id, project_id)).fetchone() is None:
                raise ProjectNotFound
