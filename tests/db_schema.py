"""서비스 표 SQL을 올바른 순서로 적용하는 시험 헬퍼. SQL 파일 이름을 부르는 곳은 이 파일 하나다(새 SQL이 생기면 SERVICE_SQL만 고친다).

사용:
    apply_service_schema(conn)              # 격리 스키마(search_path)에 public 쪽 서비스 표 전부: 인증 · 구글 · 프로젝트 · 대화 · 승인 · 견적
    apply_service_schema(conn, agent=True)  # + sojafit_agent(분석 서비스) 표 · 함수. 격리가 안 되는 진짜 스키마라 일회용 DB의 public에만 쓴다

- [왜] 시험마다 003 · 005 · 018 같은 파일 이름을 하드코딩했더니 SQL이 바뀔 때마다 시험 7개를 고쳤다. 순서는 compose initdb(db/*.sql 이름순)와 같다.
- [주의] 한 DB(스키마)에 한 번만 적용한다. 다시 적용하면 027의 ADD COLUMN에서 실패한다. 파일은 표 이름에 스키마를 붙이지 않아 격리 스키마에 들어간다
  (sojafit_agent 파일은 진짜 sojafit_agent 스키마와 public을 이름으로 부르므로 agent=True는 격리 스키마에서 쓰지 않는다).
- 뺀 것: 007(데모 시드, psql 전용), 026(공개 역할 권한 · RLS, test_public_grants가 따로 시험), 코퍼스 002 · 008 · 009 · 012(RAG 시험이 따로 적용).
"""
from pathlib import Path

DB_DIR = Path(__file__).resolve().parents[1] / 'db'

# (파일, 분석 서비스 파일인가). 순서 = db/ 번호순
SERVICE_SQL = (
    ('003_auth.sql', False), ('005_auth_attempt_window.sql', False), ('006_user_roles.sql', False), ('010_google_auth.sql', False),
    ('013_agent_memory.sql', True), ('014_thread_inputs.sql', True), ('015_analysis_limits.sql', True), ('016_memory_controls.sql', True),
    ('017_analysis_events.sql', True),
    ('018_projects.sql', False), ('019_conversations.sql', False), ('020_approvals_quotes.sql', False), ('021_auth_ip_limits.sql', False),
    ('022_token_limits.sql', True), ('023_retention.sql', True),
    ('024_projects_demo_c01.sql', False), ('025_runs_safe_result_preferred_mount.sql', False),
    ('027_service_redesign_p1.sql', False), ('028_service_redesign_agent.sql', True), ('029_drop_google_pending.sql', False),
)


def service_sql_names(agent=False):
    return [name for name, is_agent in SERVICE_SQL if agent or not is_agent]


def apply_service_schema(conn, agent=False):
    """conn(psycopg 연결)에 서비스 표를 만든다. 트랜잭션은 호출한 쪽이 정한다."""
    for name in service_sql_names(agent):
        conn.execute((DB_DIR / name).read_text(encoding='utf-8-sig'))
