"""프로젝트 소유권을 매 쿼리에서 확인하는 대화 저장소."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from backend import auth
from backend.conversations.models import SafeResult


class ConversationNotFound(Exception):
    """없는 대화와 다른 사용자의 대화를 구분하지 않는다."""


class InvalidRunState(Exception):
    """실행 상태가 요청한 전이에 맞지 않는다."""


class ConversationRepository:
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
            return [{'id': str(row[0]), 'project_id': project_id} for row in conn.execute('SELECT id FROM threads WHERE project_id=%s ORDER BY created_at,id', (project_id,))]

    def thread_detail(self, user_id, thread_id):
        row = self.get_thread(user_id, thread_id)
        with auth.connection() as conn:
            rows = conn.execute('SELECT m.role,m.content FROM messages m JOIN threads t ON t.id=m.thread_id JOIN projects p ON p.id=t.project_id WHERE t.id=%s AND p.user_id=%s ORDER BY m.id', (thread_id, user_id)).fetchall()
        return {'id': str(row[0]), 'project_id': row[1], 'messages': [{'role': r[0], 'content': r[1]} for r in rows]}

    def get_run(self, user_id, run_id):
        with auth.connection() as conn:
            row = conn.execute("""SELECT r.id,r.thread_id,r.status,r.safe_result,
                (SELECT m.id FROM messages m WHERE m.run_id=r.id AND m.role='assistant' ORDER BY m.id DESC LIMIT 1)
                FROM runs r JOIN threads t ON t.id=r.thread_id JOIN projects p ON p.id=t.project_id
                WHERE r.id=%s AND p.user_id=%s""", (run_id,user_id)).fetchone()
            if row is None:
                raise ConversationNotFound
            return {'id': str(row[0]), 'thread_id': str(row[1]), 'status': row[2], 'safe_result': row[3] or {}, 'message_id': row[4]}
