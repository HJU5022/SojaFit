"""프로젝트 소유권을 매 쿼리에서 확인하는 대화 저장소."""
import os
from uuid import uuid4
from psycopg.types.json import Jsonb
from backend import auth
from backend.conversations.models import SafeResult, SafeRunError


def thread_title(content):
    """이름을 고치지 않은 대화의 표시 이름: 첫 질문의 공백을 줄여 60자까지(넘으면 …), 비었으면 '새 대화'."""
    text = ' '.join((content or '').split())
    return text[:60] + ('…' if len(text) > 60 else '') if text else '새 대화'


def pinned_version(t, versions='project_circuit_versions'):
    """대화(별칭 t의 threads 행)가 읽는 회로 버전 SQL 식. 회로 없이 시작한 대화(0)는 그 뒤 프로젝트에 처음 올린 회로(1 이상 중 가장 작은 버전)를 읽는다.

    versions: 회로 버전 표 이름. search_path가 public이 아닌 연결(분석 서비스)은 `public.`을 붙여 넘긴다.

    [왜] 고정 버전 칸은 트리거(db/031)가 바꾸지 못하게 막는다. 대화 안에서 넷리스트를 붙이면(SPEC 4절 netlist의 thread_id) 같은 대화가 그 회로를 이어 읽게 읽을 때 정한다.
         가장 작은 버전이라 그 뒤 업로드가 이 대화를 다시 바꾸지 않는다. 회로가 아직 없으면 0(빈 회로)이다.
    """
    return (f'CASE WHEN {t}.circuit_version=0 THEN COALESCE((SELECT min(v0.version) FROM {versions} v0 '
            f'WHERE v0.project_id={t}.project_id AND v0.version>0),0) ELSE {t}.circuit_version END')


class ConversationNotFound(Exception):
    """없는 대화와 다른 사용자의 대화를 구분하지 않는다."""


class InvalidRunState(Exception):
    """실행 상태가 요청한 전이에 맞지 않는다."""


def stale_run_seconds():
    """마지막 갱신 뒤 이 시간이 지난 running run은 멈춘 것으로 본다(분석 한 번의 최대 시간 + 60초, 최소 300초)."""
    return max(300, float(os.getenv('ANALYSIS_MAX_SECONDS', '90')) + 60)


# [왜] 삭제를 막아야 하는 running run = 최근에 갱신됐거나, 갱신이 오래됐어도 그 thread의 분석 잠금을 누가 쥔 run. 인스턴스가 내려가 멈춘 run은 막지 않는다(점검 B #3)
# [주의] 매개변수 하나(stale_run_seconds())가 필요하다. 호출한 쪽 트랜잭션이 끝날 때까지 멈춘 run의 thread 잠금을 쥔다(삭제와 새 실행이 서로 기다리게 하려는 것)
LIVE_RUN = ("r.status='running' AND (r.updated_at >= CURRENT_TIMESTAMP-(%s * interval '1 second') "
            "OR NOT pg_try_advisory_xact_lock(hashtextextended(r.thread_id::text,0)))")


def _summaries(conn, user_id, thread_id=None):
    """대화 요약 {id, project_id, project_name, title, created_at, last_activity_at}. thread_id를 주면 그 대화 하나만."""
    # [왜] 마지막 활동 = 만든 시각 · 마지막 메시지 · 마지막 run 갱신 중 가장 늦은 것(프로젝트별 목록 list_threads와 같은 기준)
    rows = conn.execute("""SELECT t.id,t.project_id,p.name,t.title,q.content,t.created_at,greatest(t.created_at,m.last_at,r.last_at) AS activity
        FROM threads t JOIN projects p ON p.id=t.project_id
        LEFT JOIN LATERAL (SELECT content FROM messages WHERE thread_id=t.id AND role='user' ORDER BY id LIMIT 1) q ON true
        LEFT JOIN LATERAL (SELECT max(created_at) AS last_at FROM messages WHERE thread_id=t.id) m ON true
        LEFT JOIN LATERAL (SELECT max(updated_at) AS last_at FROM runs WHERE thread_id=t.id) r ON true
        WHERE p.user_id=%s AND (%s::uuid IS NULL OR t.id=%s::uuid) ORDER BY activity DESC,t.id DESC""", (user_id, thread_id, thread_id))
    return [{'id': str(row[0]), 'project_id': row[1], 'project_name': row[2], 'title': row[3] or thread_title(row[4]),
             'created_at': row[5], 'last_activity_at': row[6]} for row in rows]


class ConversationRepository:
    """대화 · run · 메시지 저장소. 모든 쿼리가 프로젝트 소유자(user_id)를 함께 확인한다."""
    def recover_stale_run(self, user_id, run_id):
        """멈춘 소유 실행만 정리한다. 분석 잠금이 있으면 시각과 관계없이 그대로 둔다."""
        stale_seconds = stale_run_seconds()
        with auth.connection() as conn:
            row = conn.execute('SELECT r.thread_id FROM runs r JOIN threads t ON t.id=r.thread_id '
                               'JOIN projects p ON p.id=t.project_id WHERE r.id=%s AND p.user_id=%s FOR UPDATE OF p,r',
                               (run_id, user_id)).fetchone()
            if row is None:
                raise ConversationNotFound
            if not conn.execute('SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0))', (str(row[0]),)).fetchone()[0]:
                return
            conn.execute("UPDATE runs SET status='failed',safe_result=NULL,updated_at=CURRENT_TIMESTAMP "
                         "WHERE id=%s AND status='running' AND updated_at<CURRENT_TIMESTAMP-(%s * interval '1 second')",
                         (run_id, stale_seconds))

    def delete_thread(self, user_id, thread_id, checkpoint_delete=None):
        """소유한 대화와 그 분석 기록을 한 트랜잭션에서 지운다. 살아 있는 run이나 분석 잠금이 있으면 InvalidRunState."""
        if checkpoint_delete is None:
            from backend.conversations.memory_service import delete_analysis_threads
            checkpoint_delete = lambda conn, ids: delete_analysis_threads(conn, user_id, ids)
        with auth.connection() as conn:
            project = conn.execute('SELECT p.id FROM projects p JOIN threads t ON t.project_id=p.id WHERE t.id=%s AND p.user_id=%s FOR UPDATE OF p', (thread_id, user_id)).fetchone()
            if project is None:
                raise ConversationNotFound
            # Run/resume also lock the project; the advisory lock protects checkpoint writers.
            if conn.execute(f"SELECT 1 FROM runs r WHERE r.thread_id=%s AND {LIVE_RUN} LIMIT 1", (thread_id, stale_run_seconds())).fetchone():
                raise InvalidRunState
            if not conn.execute('SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0))', (thread_id,)).fetchone()[0]:
                raise InvalidRunState
            checkpoint_delete(conn, [thread_id])
            conn.execute('DELETE FROM threads WHERE id=%s AND project_id=%s', (thread_id, project[0]))

    def create_thread(self, user_id, project_id, circuit_version=None):
        """소유 프로젝트에 새 대화를 만들고 id를 돌려준다. circuit_version을 주면 그 버전이 있어야 한다."""
        thread_id = uuid4()
        with auth.connection() as conn:
            if conn.execute('SELECT id FROM projects WHERE id=%s AND user_id=%s FOR UPDATE', (project_id, user_id)).fetchone() is None:
                raise ConversationNotFound
            if circuit_version is not None and conn.execute(
                    'SELECT 1 FROM project_circuit_versions WHERE project_id=%s AND version=%s',
                    (project_id, circuit_version)).fetchone() is None:
                raise ConversationNotFound
            if circuit_version is None:
                row = conn.execute('INSERT INTO threads(id,project_id) SELECT %s,id FROM projects WHERE id=%s AND user_id=%s RETURNING id',
                                   (thread_id, project_id, user_id)).fetchone()
            else:
                row = conn.execute('INSERT INTO threads(id,project_id,circuit_version) VALUES (%s,%s,%s) RETURNING id',
                                   (thread_id, project_id, circuit_version)).fetchone()
            if row is None:
                raise ConversationNotFound
        return str(thread_id)

    def get_thread(self, user_id, thread_id):
        """소유한 대화의 (id, project_id, 읽는 회로 버전의 연결, 프로젝트 이름)."""
        with auth.connection() as conn:
            row = conn.execute(f"SELECT t.id, t.project_id, c.connections, p.name FROM threads t JOIN projects p ON p.id=t.project_id JOIN project_circuit_versions c ON c.project_id=p.id AND c.version={pinned_version('t')} WHERE t.id=%s AND p.user_id=%s",
                               (thread_id, user_id)).fetchone()
            if row is None:
                raise ConversationNotFound
            return row

    def start(self, user_id, thread_id, data):
        """running run과 사용자 질문 메시지를 만들고 (run id, 대화가 읽는 회로 연결)을 돌려준다."""
        run_id = uuid4()
        with auth.connection() as conn:
            if conn.execute('SELECT p.id FROM projects p JOIN threads t ON t.project_id=p.id WHERE t.id=%s AND p.user_id=%s FOR UPDATE OF p', (thread_id, user_id)).fetchone() is None:
                raise ConversationNotFound
            row = conn.execute("INSERT INTO runs(id,thread_id,status) SELECT %s,t.id,'running' FROM threads t JOIN projects p ON p.id=t.project_id WHERE t.id=%s AND p.user_id=%s RETURNING id", (run_id, thread_id, user_id)).fetchone()
            if row is None:
                raise ConversationNotFound
            conn.execute("INSERT INTO messages(thread_id,run_id,role,content) VALUES (%s,%s,'user',%s)", (thread_id, run_id, data['question']))
            circuit = conn.execute(f"SELECT c.connections FROM project_circuit_versions c JOIN threads t ON t.project_id=c.project_id AND c.version={pinned_version('t')} WHERE t.id=%s", (thread_id,)).fetchone()[0]
        return str(run_id), circuit

    def finish(self, user_id, thread_id, run_id, status, result=None):
        """running run을 status로 끝내고 공개 결과를 저장한다. 완료 · 거절이면 답을 assistant 메시지로 남긴다."""
        safe = SafeResult.model_validate(result).model_dump() if result is not None else None
        with auth.connection() as conn:
            row = conn.execute("UPDATE runs r SET status=%s,safe_result=%s,updated_at=CURRENT_TIMESTAMP FROM threads t JOIN projects p ON p.id=t.project_id WHERE r.id=%s AND r.thread_id=t.id AND t.id=%s AND p.user_id=%s AND r.status='running' RETURNING r.id",
                               (status, Jsonb(safe) if safe is not None else None, run_id, thread_id, user_id)).fetchone()
            if row is None:
                owned = conn.execute('SELECT r.id FROM runs r JOIN threads t ON t.id=r.thread_id JOIN projects p ON p.id=t.project_id WHERE r.id=%s AND t.id=%s AND p.user_id=%s', (run_id, thread_id, user_id)).fetchone()
                if owned is None:
                    raise ConversationNotFound
                raise InvalidRunState
            if safe is not None and status in ('completed', 'refused'):
                conn.execute("INSERT INTO messages(thread_id,run_id,role,content) VALUES (%s,%s,'assistant',%s)", (thread_id, run_id, safe['answer']))

    def record_resume_error(self, user_id, run_id, error):
        """재개 입구에서 거절된 오류(예: 하루 한도 429)를 아직 입력 대기인 run의 결과에 덧붙인다."""
        safe = SafeRunError.model_validate(error).model_dump()
        with auth.connection() as conn:
            # 다른 요청이 이미 재개/완료한 실행에는 뒤늦은 입구 오류를 덮어쓰지 않는다.
            row = conn.execute("UPDATE runs r SET safe_result=COALESCE(r.safe_result,%s)||%s,updated_at=CURRENT_TIMESTAMP "
                               "FROM threads t JOIN projects p ON p.id=t.project_id "
                               "WHERE r.id=%s AND r.thread_id=t.id AND p.user_id=%s AND r.status='requires_input' RETURNING r.id",
                               (Jsonb(SafeResult().model_dump()), Jsonb({'error': safe}), run_id, user_id)).fetchone()
            if row is None and conn.execute('SELECT r.id FROM runs r JOIN threads t ON t.id=r.thread_id '
                                            'JOIN projects p ON p.id=t.project_id WHERE r.id=%s AND p.user_id=%s',
                                            (run_id, user_id)).fetchone() is None:
                raise ConversationNotFound

    def resume(self, user_id, thread_id, run_id):
        """입력 대기(requires_input) run을 다시 running으로 바꾼다. 다른 상태면 InvalidRunState."""
        with auth.connection() as conn:
            if conn.execute('SELECT p.id FROM projects p JOIN threads t ON t.project_id=p.id WHERE t.id=%s AND p.user_id=%s FOR UPDATE OF p', (thread_id, user_id)).fetchone() is None:
                raise ConversationNotFound
            row = conn.execute("UPDATE runs r SET status='running',updated_at=CURRENT_TIMESTAMP FROM threads t JOIN projects p ON p.id=t.project_id WHERE r.id=%s AND r.thread_id=t.id AND t.id=%s AND p.user_id=%s AND r.status='requires_input' RETURNING r.id", (run_id, thread_id, user_id)).fetchone()
            if row is None:
                owned = conn.execute('SELECT r.id FROM runs r JOIN threads t ON t.id=r.thread_id JOIN projects p ON p.id=t.project_id WHERE r.id=%s AND t.id=%s AND p.user_id=%s', (run_id, thread_id, user_id)).fetchone()
                if owned is None:
                    raise ConversationNotFound
                raise InvalidRunState

    def list_threads(self, user_id, project_id):
        """소유 프로젝트 하나의 대화 목록(마지막 run 상태 · 읽는 회로 버전 포함), 마지막 활동이 최근인 순."""
        with auth.connection() as conn:
            if conn.execute('SELECT id FROM projects WHERE id=%s AND user_id=%s', (project_id, user_id)).fetchone() is None:
                raise ConversationNotFound
            rows = conn.execute(f"""SELECT t.id,t.created_at,q.content,r.id,r.status,
                greatest(t.created_at,m.last_at,r.last_at) AS activity,{pinned_version('t')},t.title
                FROM threads t JOIN projects p ON p.id=t.project_id
                LEFT JOIN LATERAL (SELECT content FROM messages WHERE thread_id=t.id AND role='user' ORDER BY id LIMIT 1) q ON true
                LEFT JOIN LATERAL (SELECT max(created_at) AS last_at FROM messages WHERE thread_id=t.id) m ON true
                LEFT JOIN LATERAL (SELECT id,status,max(updated_at) OVER () AS last_at FROM runs WHERE thread_id=t.id ORDER BY created_at DESC,id DESC LIMIT 1) r ON true
                WHERE t.project_id=%s AND p.user_id=%s ORDER BY activity DESC,t.id DESC""", (project_id, user_id))
            return [{'id': str(row[0]), 'project_id': project_id, 'created_at': row[1], 'title': row[7] or thread_title(row[2]),
                     'latest_run_id': str(row[3]) if row[3] else None, 'status': row[4], 'last_activity_at': row[5], 'circuit_version': row[6]} for row in rows]

    def list_all_threads(self, user_id):
        """사용자의 모든 프로젝트 대화를 마지막 활동이 최근인 순으로(사이드바 "대화" 목록). 읽기만 한다."""
        with auth.connection() as conn:
            return _summaries(conn, user_id)

    def rename_thread(self, user_id, thread_id, title):
        """소유한 대화의 이름만 바꾼다. 다른 사용자의 대화는 없는 대화와 같게 404."""
        with auth.connection() as conn:
            # [왜] 회로 버전 고정 트리거(db/031)는 project_id · circuit_version 변경만 막으므로 이름 변경은 지나간다
            if conn.execute('UPDATE threads t SET title=%s FROM projects p WHERE p.id=t.project_id AND t.id=%s AND p.user_id=%s RETURNING t.id',
                            (title, thread_id, user_id)).fetchone() is None:
                raise ConversationNotFound
            return _summaries(conn, user_id, thread_id)[0]

    def thread_detail(self, user_id, thread_id, limit=50, before_message_id=None):
        """소유한 대화의 상세(이어 온 대화 · 분석 대상 · 마지막 run)와 메시지 한 쪽(limit개, 오래된 것부터)."""
        with auth.connection() as conn:
            row = conn.execute(f"SELECT t.id,t.project_id,{pinned_version('t')},t.title,"
                               "CASE WHEN pp.id IS NULL THEN NULL ELSE tc.previous_thread_id END "
                               "FROM threads t JOIN projects p ON p.id=t.project_id "
                               "LEFT JOIN thread_continuations tc ON tc.thread_id=t.id "
                               "LEFT JOIN threads pt ON pt.id=tc.previous_thread_id AND pt.project_id=t.project_id "
                               "LEFT JOIN projects pp ON pp.id=pt.project_id AND pp.user_id=p.user_id "
                               "WHERE t.id=%s AND p.user_id=%s", (thread_id, user_id)).fetchone()
            if row is None:
                raise ConversationNotFound
            title = conn.execute("SELECT m.content FROM messages m JOIN threads t ON t.id=m.thread_id JOIN projects p ON p.id=t.project_id WHERE t.id=%s AND p.user_id=%s AND m.role='user' ORDER BY m.id LIMIT 1", (thread_id, user_id)).fetchone()
            rows = conn.execute('''SELECT m.id,m.run_id,m.role,m.content,m.created_at FROM messages m
                JOIN threads t ON t.id=m.thread_id JOIN projects p ON p.id=t.project_id
                WHERE t.id=%s AND p.user_id=%s AND (%s::bigint IS NULL OR m.id<%s)
                ORDER BY m.id DESC LIMIT %s''', (thread_id, user_id, before_message_id, before_message_id, limit + 1)).fetchall()
            latest = conn.execute('''SELECT r.id,r.status,(SELECT m.id FROM messages m WHERE m.run_id=r.id AND m.role='assistant' ORDER BY m.id DESC LIMIT 1)
                FROM runs r JOIN threads t ON t.id=r.thread_id JOIN projects p ON p.id=t.project_id
                WHERE t.id=%s AND p.user_id=%s ORDER BY r.created_at DESC,r.id DESC LIMIT 1''', (thread_id, user_id)).fetchone()
            target = None
            if conn.execute("SELECT to_regclass('sojafit_agent.threads')").fetchone()[0] is not None:
                target = conn.execute('SELECT a.target FROM sojafit_agent.threads a JOIN threads t ON t.id=a.id JOIN projects p ON p.id=t.project_id WHERE t.id=%s AND p.user_id=%s AND a.user_id=%s', (thread_id, user_id, user_id)).fetchone()
        page = rows[:limit]
        # [왜] 회로 없이 시작한 대화의 분석 대상은 빈 글자다(memory_service.ensure_thread). 아직 정하지 않은 대상으로 보이고 고정되지 않는다
        ref = target[0] if target else None
        return {'id': str(row[0]), 'project_id': row[1], 'circuit_version': row[2], 'previous_thread_id': str(row[4]) if row[4] else None,
                'title': row[3] or thread_title(title[0] if title else ''),
                'target_ref': ref or None, 'target_locked': latest is not None and ref != '',
                'latest_run': {'id': str(latest[0]), 'status': latest[1], 'message_id': latest[2]} if latest else None,
                'messages': [{'id': r[0], 'run_id': str(r[1]), 'role': r[2], 'content': r[3], 'created_at': r[4]} for r in reversed(page)],
                'next_before_message_id': page[-1][0] if len(rows) > limit else None}

    def get_run(self, user_id, run_id):
        """소유한 run의 상태 · 저장된 공개 결과 · 답 메시지 id."""
        with auth.connection() as conn:
            row = conn.execute("""SELECT r.id,r.thread_id,r.status,r.safe_result,
                (SELECT m.id FROM messages m WHERE m.run_id=r.id AND m.role='assistant' ORDER BY m.id DESC LIMIT 1)
                FROM runs r JOIN threads t ON t.id=r.thread_id JOIN projects p ON p.id=t.project_id
                WHERE r.id=%s AND p.user_id=%s""", (run_id,user_id)).fetchone()
            if row is None:
                raise ConversationNotFound
            return {'id': str(row[0]), 'thread_id': str(row[1]), 'status': row[2], 'safe_result': row[3] or {}, 'message_id': row[4]}
