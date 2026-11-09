"""소유자 조건을 포함한 프로젝트 SQL. 데모 JSON만 저장하며 업로드는 처리하지 않는다."""
import hashlib
import json
from pathlib import Path

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from backend import auth
from backend.projects.models import Project, ProjectSummary

ROOT = Path(__file__).resolve().parents[2]
DEMOS = {
    "breadboard_supply": "SparkFun Breadboard Power Supply 5V/3.3V",
    "mosfet_driver": "Adafruit MOSFET Driver STEMMA",
    "attiny85_dev": "ATtiny85 dev board",
    "pro_micro": "SparkFun Pro Micro v13",
    "franzininho_diy": "Franzininho DIY",
}
FIELDS = "id, name, source_kind, demo_id, created_at, updated_at"


class ProjectNotFound(Exception):
    """없는 프로젝트와 다른 사용자의 프로젝트는 구별하지 않는다."""


class InvalidProject(ValueError):
    """알 수 없는 데모 또는 잘못된 프로젝트 이름."""


def project_name(name: str) -> str:
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 200:
        raise InvalidProject("프로젝트 이름은 1~200자여야 합니다.")
    return name.strip()


class ProjectRepository:
    def create_demo(self, user_id: int, demo_id: str, name: str) -> Project:
        name = project_name(name)
        if demo_id not in DEMOS:
            raise InvalidProject("등록된 데모 회로를 선택해 주세요.")
        # 사용자 입력을 경로로 사용하지 않고 허용된 카탈로그에서만 고른다.
        base = ROOT / "data/circuits/collected"
        path = (base / "received-20261030/c09/connections.json" if demo_id == "franzininho_diy"
                else base / "samples" / demo_id / "converted/connections.json")
        source = path.read_bytes()
        connections = json.loads(source)
        with auth.connection() as conn:
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
            cur.execute(f"SELECT {FIELDS} FROM projects WHERE user_id=%s ORDER BY updated_at DESC, id DESC", (user_id,))
            return [ProjectSummary(**row) for row in cur.fetchall()]

    def get_owned(self, user_id: int, project_id: int) -> Project:
        with auth.connection() as conn:
            return self._get_owned(conn, user_id, project_id)

    def _get_owned(self, conn, user_id: int, project_id: int) -> Project:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT p.id, p.name, p.source_kind, p.demo_id, p.created_at, p.updated_at, c.connections "
                "FROM projects p JOIN circuits c ON c.project_id=p.id WHERE p.user_id=%s AND p.id=%s",
                (user_id, project_id),
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
