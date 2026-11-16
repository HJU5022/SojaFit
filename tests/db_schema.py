"""서비스 표 기준선(db/020_service_baseline.sql)을 시험 DB에 적용하는 헬퍼. 기준선 파일 이름을 부르는 곳은 이 파일 하나다.

사용:
    apply_service_schema(conn)              # 격리 스키마(search_path)에 public 쪽 서비스 표 전부: 인증 · 구글 · 프로젝트 · 대화 · 승인 · 견적
    apply_service_schema(conn, agent=True)  # + sojafit_agent(분석 서비스) 표 · 함수. 격리가 안 되는 진짜 스키마라 일회용 DB의 public에만 쓴다

- [왜] 시험마다 003 · 005 · 018 같은 파일 이름을 하드코딩했더니 SQL이 바뀔 때마다 시험 7개를 고쳤다. 지금은 기준선 한 파일이고 compose initdb와 CI도 같은 파일을 쓴다.
- [주의] 한 DB(스키마)에 한 번만 적용한다(CREATE TABLE이 다시 실행되면 실패). 기준선은 `-- @@AGENT@@` 줄을 경계로 앞은 public 표(스키마 이름 없음, 격리 스키마에 들어감),
  뒤는 sojafit_agent와 `public.`을 이름으로 부르는 부분이다. 그래서 agent=True는 격리 스키마에서 쓰지 않는다.
- 뺀 것: 026(공개 역할 권한 · RLS, test_public_grants가 따로 시험), 코퍼스 000 · 002 · 008 · 009 · 012(RAG 시험이 따로 적용), 옛 증분 파일(db/legacy/, 이력용).
"""
import re
from pathlib import Path

DB_DIR = Path(__file__).resolve().parents[1] / 'db'
BASELINE = DB_DIR / '020_service_baseline.sql'
AGENT_MARK = '-- @@AGENT@@'


def baseline_sql(agent=False):
    text = BASELINE.read_text(encoding='utf-8-sig')
    # [주의] 머리 주석도 경계 표시를 글로 언급하므로 줄 맨 앞에서 시작하는 경계 줄만 찾는다
    mark = re.search('^' + re.escape(AGENT_MARK), text, re.M)
    assert mark, f'{BASELINE.name}에 {AGENT_MARK} 경계 줄이 없다'
    return text if agent else text[:mark.start()]


def apply_service_schema(conn, agent=False):
    """conn(psycopg 연결)에 서비스 표를 만든다. 트랜잭션은 호출한 쪽이 정한다."""
    conn.execute(baseline_sql(agent))
    for name in ("027_google_user_login.sql", "029_email_account_security.sql", "030_google_onboarding.sql", "031_circuit_versions.sql", "032_approval_reselection.sql",
                 "033_thread_titles.sql", "034_admin_audit.sql"):
        conn.execute((DB_DIR / name).read_text(encoding="utf-8").replace("public.", ""))
