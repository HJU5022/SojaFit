"""프로젝트 소유권을 매 쿼리에서 확인하는 대화 저장소."""
import os
from uuid import uuid4
from psycopg.types.json import Jsonb
from backend import auth
from backend.conversations.models import SafeResult


def thread_title(content):
    text = ' '.join((content or '').split())
    return text[:60] + ('…' if len(text) > 60 else '') if text else '새 대화'


class ConversationNotFound(Exception):
    """없는 대화와 다른 사용자의 대화를 구분하지 않는다."""


class InvalidRunState(Exception):
    """실행 상태가 요청한 전이에 맞지 않는다."""


class ConversationRepository:
    def recover_stale_run(self, user_id, run_id):
        """멈춘 소유 실행만 정리한다. 분석 잠금이 있으면 시각과 관계없이 그대로 둔다."""
        stale_seconds = max(300, float(os.getenv('ANALYSIS_MAX_SECONDS', '90')) + 60)
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
        if checkpoint_delete is None:
            from backend.conversations.memory_service import delete_analysis_threads
            checkpoint_delete = lambda conn, ids: delete_analysis_threads(conn, user_id, ids)
        with auth.connection() as conn:
            project = conn.execute('SELECT p.id FROM projects p JOIN threads t ON t.project_id=p.id WHERE t.id=%s AND p.user_id=%s FOR UPDATE OF p', (thread_id, user_id)).fetchone()
            if project is None:
                raise ConversationNotFound
            # Run/resume also lock the project; the advisory lock protects checkpoint writers.
            if conn.execute("SELECT 1 FROM runs WHERE thread_id=%s AND status='running' LIMIT 1", (thread_id,)).fetchone():
                raise InvalidRunState
            if not conn.execute('SELECT pg_try_advisory_xact_lock(hashtextextended(%s,0))', (thread_id,)).fetchone()[0]:
                raise InvalidRunState
            checkpoint_delete(conn, [thread_id])
            conn.execute('DELETE FROM threads WHERE id=%s AND project_id=%s', (thread_id, project[0]))

    def create_thread(self, user_id, project_id):
        thread_id = uuid4()
        with auth.connection() as conn:
            if conn.execute('SELECT id FROM projects WHERE id=%s AND user_id=%s FOR UPDATE', (project_id, user_id)).fetchone() is None:
                raise ConversationNotFound
            row = conn.execute('INSERT INTO threads(id,project_id) SELECT %s,id FROM projects WHERE id=%s AND user_id=%s RETURNING id',
                               (thread_id, project_id, user_id)).fetchone()
            if row is None:
                raise ConversationNotFound
        return str(thread_id)

    def get_thread(self, user_id, thread_id):
        with auth.connection() as conn:
            row = conn.execute('SELECT t.id, t.project_id, c.connections, p.name FROM threads t JOIN projects p ON p.id=t.project_id JOIN circuits c ON c.project_id=p.id WHERE t.id=%s AND p.user_id=%s',
                               (thread_id, user_id)).fetchone()
            if row is None:
                raise ConversationNotFound
            return row

    def start(self, user_id, thread_id, data):
        run_id = uuid4()
        with auth.connection() as conn:
            if conn.execute('SELECT p.id FROM projects p JOIN threads t ON t.project_id=p.id WHERE t.id=%s AND p.user_id=%s FOR UPDATE OF p', (thread_id, user_id)).fetchone() is None:
                raise ConversationNotFound
            row = conn.execute("INSERT INTO runs(id,thread_id,status) SELECT %s,t.id,'running' FROM threads t JOIN projects p ON p.id=t.project_id WHERE t.id=%s AND p.user_id=%s RETURNING id", (run_id, thread_id, user_id)).fetchone()
            if row is None:
                raise ConversationNotFound
            conn.execute("INSERT INTO messages(thread_id,run_id,role,content) VALUES (%s,%s,'user',%s)", (thread_id, run_id, data['question']))
            circuit = conn.execute('SELECT c.connections FROM circuits c JOIN threads t ON t.project_id=c.project_id WHERE t.id=%s', (thread_id,)).fetchone()[0]
        return str(run_id), circuit

    def finish(self, user_id, thread_id, run_id, status, result=None):
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

    def resume(self, user_id, thread_id, run_id):
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
        with auth.connection() as conn:
            if conn.execute('SELECT id FROM projects WHERE id=%s AND user_id=%s', (project_id, user_id)).fetchone() is None:
                raise ConversationNotFound
            rows = conn.execute("""SELECT t.id,t.created_at,q.content,r.id,r.status,
                greatest(t.created_at,m.last_at,r.last_at) AS activity
                FROM threads t JOIN projects p ON p.id=t.project_id
                LEFT JOIN LATERAL (SELECT content FROM messages WHERE thread_id=t.id AND role='user' ORDER BY id LIMIT 1) q ON true
                LEFT JOIN LATERAL (SELECT max(created_at) AS last_at FROM messages WHERE thread_id=t.id) m ON true
                LEFT JOIN LATERAL (SELECT id,status,max(updated_at) OVER () AS last_at FROM runs WHERE thread_id=t.id ORDER BY created_at DESC,id DESC LIMIT 1) r ON true
                WHERE t.project_id=%s AND p.user_id=%s ORDER BY activity DESC,t.id DESC""", (project_id, user_id))
            return [{'id': str(row[0]), 'project_id': project_id, 'created_at': row[1], 'title': thread_title(row[2]),
                     'latest_run_id': str(row[3]) if row[3] else None, 'status': row[4], 'last_activity_at': row[5]} for row in rows]

    def thread_detail(self, user_id, thread_id, limit=50, before_message_id=None):
        with auth.connection() as conn:
            row = conn.execute('SELECT t.id,t.project_id FROM threads t JOIN projects p ON p.id=t.project_id WHERE t.id=%s AND p.user_id=%s', (thread_id, user_id)).fetchone()
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
        return {'id': str(row[0]), 'project_id': row[1], 'title': thread_title(title[0] if title else ''),
                'target_ref': target[0] if target else None, 'target_locked': latest is not None,
                'latest_run': {'id': str(latest[0]), 'status': latest[1], 'message_id': latest[2]} if latest else None,
                'messages': [{'id': r[0], 'run_id': str(r[1]), 'role': r[2], 'content': r[3], 'created_at': r[4]} for r in reversed(page)],
                'next_before_message_id': page[-1][0] if len(rows) > limit else None}

    def get_run(self, user_id, run_id):
        with auth.connection() as conn:
            row = conn.execute("""SELECT r.id,r.thread_id,r.status,r.safe_result,
                (SELECT m.id FROM messages m WHERE m.run_id=r.id AND m.role='assistant' ORDER BY m.id DESC LIMIT 1)
                FROM runs r JOIN threads t ON t.id=r.thread_id JOIN projects p ON p.id=t.project_id
                WHERE r.id=%s AND p.user_id=%s""", (run_id,user_id)).fetchone()
            if row is None:
                raise ConversationNotFound
            return {'id': str(row[0]), 'thread_id': str(row[1]), 'status': row[2], 'safe_result': row[3] or {}, 'message_id': row[4]}
