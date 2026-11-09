"""세션 사용자별 업로드·분석 thread·승인 사례. 공유 DB setup은 명시적 CLI만 수행한다."""
import argparse
import os
from contextlib import ExitStack, contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
from fastapi import HTTPException
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from langgraph.types import Command
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from backend.graph.memory import namespace
from backend.graph.netlist import parse_netlist


def initialize(dsn):
    """인증 DB에 전용 스키마를 준비한다. 기존 코퍼스·인증 행은 변경하지 않는다."""
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row, connect_timeout=5) as conn:
        conn.execute((Path(__file__).parents[1] / 'db/013_agent_memory.sql').read_text(encoding='utf-8'))
        conn.execute('SET search_path TO sojafit_agent')
        PostgresSaver(conn).setup()
        PostgresStore(conn).setup()


class Conversations:
    def __init__(self, dsn, factory=None):
        self.dsn = make_conninfo(dsn, options='-c search_path=sojafit_agent')
        self.stack = ExitStack()
        try:
            with self.connection() as conn:
                if not all(conn.execute("SELECT to_regclass(%s) AS name", (name,)).fetchone()['name']
                           for name in ('threads', 'approvals', 'checkpoints', 'store')):
                    raise RuntimeError('분석 DB 준비 명령을 먼저 실행하세요.')
            self.pool = self.stack.enter_context(ConnectionPool(self.dsn, min_size=1, max_size=4, timeout=5,
                kwargs={'autocommit': True, 'row_factory': dict_row, 'prepare_threshold': 0}))
            self.saver, self.store = PostgresSaver(self.pool), PostgresStore(self.pool)
            self.graph = factory(self.saver, self.store) if factory else self._graph()
        except Exception:
            self.stack.close()
            raise

    def connection(self):
        return psycopg.connect(self.dsn, autocommit=True, row_factory=dict_row, connect_timeout=5)

    def close(self):
        self.stack.close()

    def _graph(self):
        from backend.graph.mcp_retriever import StdioMcpRetriever
        from backend.multi_agent.build import build_graph
        from backend.multi_agent.facts import make_lookup
        from backend.rag.retrieve import retrieve
        from backend.services import llm
        mcp = self.stack.enter_context(StdioMcpRetriever())
        return build_graph(chat=llm.node_chat, retriever=retrieve, judge_enabled=True,
            lookup=make_lookup(mcp.check), specs=mcp.part_specs, find=mcp.find_parts,
            checkpointer=self.saver, store=self.store)

    @staticmethod
    def config(thread):
        return {'configurable': {'thread_id': str(thread)}, 'recursion_limit': 50}

    @staticmethod
    def _owned(conn, user, thread):
        row = conn.execute('SELECT t.*,c.filename,c.connections FROM threads t JOIN circuits c ON c.id=t.circuit_id '
                           'WHERE t.id=%s AND t.user_id=%s AND c.user_id=%s', (thread, user, user)).fetchone()
        if not row:
            raise HTTPException(404, '분석을 찾을 수 없습니다.')
        return row

    @contextmanager
    def locked(self, user, thread):
        with self.connection() as conn:
            row = self._owned(conn, user, thread)
            if not conn.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS ok', (str(thread),)).fetchone()['ok']:
                raise HTTPException(409, '분석을 처리 중입니다. 잠시 후 다시 시도하세요.')
            try:
                yield conn, self._owned(conn, user, thread)
            finally:
                conn.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))', (str(thread),))

    def upload(self, user, filename, netlist):
        if not filename or '/' in filename or '\\' in filename or len(filename) > 200 or not filename.lower().endswith('.net'):
            raise HTTPException(422, 'KiCad .net 파일을 선택하세요.')
        try:
            connections = parse_netlist(netlist)
        except ValueError:
            raise HTTPException(422, '넷리스트 형식·크기·부품 참조를 확인하세요.') from None
        with self.connection() as conn:
            if conn.execute('SELECT count(*) AS n FROM circuits WHERE user_id=%s', (user,)).fetchone()['n'] >= 100:
                raise HTTPException(409, '회로 저장 한도(100건)에 도달했습니다.')
            circuit = str(uuid4())
            conn.execute('INSERT INTO circuits(id,user_id,filename,netlist,connections) VALUES (%s,%s,%s,%s,%s)',
                         (circuit, user, filename, netlist, Jsonb(connections)))
        return {'id': circuit, 'filename': filename, 'components': connections['components']}

    def circuits(self, user):
        with self.connection() as conn:
            rows = conn.execute('SELECT id,filename,connections FROM circuits WHERE user_id=%s ORDER BY created_at DESC LIMIT 100', (user,)).fetchall()
        return [{'id': str(r['id']), 'filename': r['filename'], 'components': r['connections']['components']} for r in rows]

    def create(self, user, circuit, target):
        with self.connection() as conn:
            row = conn.execute('SELECT connections FROM circuits WHERE id=%s AND user_id=%s', (circuit, user)).fetchone()
            if not row:
                raise HTTPException(404, '회로를 찾을 수 없습니다.')
            if target not in {p['ref'] for p in row['connections']['components']}:
                raise HTTPException(422, '회로에 없는 대상 부품입니다.')
            thread = str(uuid4())
            conn.execute('INSERT INTO threads(id,user_id,circuit_id,target) VALUES (%s,%s,%s,%s)', (thread, user, circuit, target))
        return {'id': thread}

    def threads(self, user):
        with self.connection() as conn:
            rows = conn.execute('SELECT t.id,t.target,t.status,t.version,c.filename FROM threads t JOIN circuits c ON c.id=t.circuit_id '
                                'WHERE t.user_id=%s ORDER BY t.created_at DESC LIMIT 100', (user,)).fetchall()
        return [{**r, 'id': str(r['id'])} for r in rows]

    def detail(self, user, thread):
        with self.connection() as conn:
            row = self._owned(conn, user, thread)
            # 실행 중인 연결이 잠금을 가진 동안에는 중간 체크포인트를 완료로 바꾸지 않는다.
            if conn.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS ok', (str(thread),)).fetchone()['ok']:
                try:
                    self._reconcile(conn, row)
                    row = self._owned(conn, user, thread)
                finally:
                    conn.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))', (str(thread),))
            messages = conn.execute('SELECT role,content FROM messages WHERE thread_id=%s ORDER BY id LIMIT 200', (thread,)).fetchall()
        snapshot = self.graph.get_state(self.config(thread))
        state = snapshot.values or {}
        pending = [i.value for task in snapshot.tasks for i in task.interrupts]
        judgement = state.get('judgement') or {}
        can_approve = (row['status'] == 'DONE' and state.get('run_version') == row['version'] and not snapshot.next
                       and not state.get('refusal') and bool(judgement.get('shown') or judgement.get('results')))
        related = self.memories(user, roles=judgement.get('roles'), part=(state.get('target_part') or {}).get('value')) if judgement else []
        return {'id': str(row['id']), 'filename': row['filename'], 'target': row['target'], 'version': row['version'],
                'status': row['status'], 'messages': messages, 'answer': '' if pending else state.get('answer', ''),
                'interrupt': pending[0] if pending else None, 'can_approve': bool(can_approve),
                'can_retry': bool(snapshot.next and not pending and row['retries'] < 2 and state.get('run_version') == row['version']),
                'related_memories': related[:5]}

    def message(self, user, thread, text, conditions=''):
        with self.locked(user, thread) as (conn, row):
            self._reconcile(conn, row)
            if self.graph.get_state(self.config(thread)).next:
                raise HTTPException(409, '먼저 요청한 조건에 답해주세요.')
            history = conn.execute("SELECT content FROM messages WHERE thread_id=%s AND role='user' ORDER BY id", (thread,)).fetchall()
            if len(history) >= 50:
                raise HTTPException(409, '분석당 질문 한도(50건)에 도달했습니다.')
            version = row['version'] + 1
            content = (f'사용 조건: {conditions}\n' if conditions else '') + text
            part = next((p.get('value', '') for p in row['connections']['components'] if p['ref'] == row['target']), '')
            memories = self.memories(user, part=part)[:5] if part else []
            with conn.transaction():
                conn.execute("UPDATE threads SET version=%s,status='RUNNING',retries=0 WHERE id=%s", (version, thread))
                conn.execute("INSERT INTO messages(thread_id,role,content) VALUES (%s,'user',%s)", (thread, content))
            # 이전 사용자 입력만 조건 문맥으로 쓴다. 모델 답변을 측정값의 근거로 되먹이지 않는다.
            context = '\n'.join(r['content'] for r in history[-12:])[-20000:]
            inputs = {'input': f'이전 사용자 입력:\n{context}\n현재 질문:\n{content}' if context else content,
                      'connections': row['connections'], 'circuit': row['filename'], 'target': row['target'],
                      'conditions': conditions, 'user_id': str(user), 'run_version': version,
                      'approved_memories': memories}
            self._invoke(conn, thread, inputs)
        return self.detail(user, thread)

    def resume(self, user, thread, answers, role, version):
        with self.locked(user, thread) as (conn, row):
            if version != row['version']:
                raise HTTPException(409, '새 결과의 조건 질문을 다시 확인하세요.')
            snapshot = self.graph.get_state(self.config(thread))
            if not snapshot.next:
                raise HTTPException(409, '재개할 조건 질문이 없습니다.')
            pending = [i.value for task in snapshot.tasks for i in task.interrupts]
            if not pending or set(answers) - set(pending[0].get('missing') or []):
                raise HTTPException(422, '요청한 조건의 답만 입력하세요.')
            if role and role not in (pending[0].get('role_choices') or []):
                raise HTTPException(422, '제시된 역할을 선택하세요.')
            content = '조건 답변:\n' + ('\n'.join(f'{key}: {value}' for key, value in answers.items()) or '모름')
            if role:
                content += f'\n선택한 역할: {role}'
            conn.execute("INSERT INTO messages(thread_id,role,content) VALUES (%s,'user',%s)", (thread, content))
            self._invoke(conn, thread, Command(resume={'answers': answers, 'role': role}))
        return self.detail(user, thread)

    def _invoke(self, conn, thread, inputs):
        try:
            self.graph.invoke(inputs, self.config(thread))
            self._finish(conn, thread, self.graph.get_state(self.config(thread)))
        except Exception:
            conn.execute("UPDATE threads SET status='FAILED' WHERE id=%s", (thread,))
            raise HTTPException(503, '분석을 완료하지 못했습니다. 잠시 후 상태를 확인하세요.') from None

    def _finish(self, conn, thread, snapshot):
        pending = [i.value for task in snapshot.tasks for i in task.interrupts]
        answer = str(pending[0].get('question', '조건을 입력하세요.')) if pending else snapshot.values.get('answer', '')
        checkpoint = snapshot.config['configurable']['checkpoint_id']
        with conn.transaction():
            conn.execute('UPDATE threads SET status=%s WHERE id=%s', ('WAITING' if pending else 'DONE', thread))
            conn.execute("INSERT INTO messages(thread_id,role,content,checkpoint_id) VALUES (%s,'assistant',%s,%s) ON CONFLICT DO NOTHING",
                         (thread, answer, checkpoint))

    def _reconcile(self, conn, row):
        snapshot = self.graph.get_state(self.config(row['id']))
        pending = [i for task in snapshot.tasks for i in task.interrupts]
        if (snapshot.values or {}).get('run_version') == row['version'] and (not snapshot.next or pending):
            self._finish(conn, row['id'], snapshot)

    def retry(self, user, thread, version):
        with self.locked(user, thread) as (conn, row):
            snapshot = self.graph.get_state(self.config(thread))
            pending = [i for task in snapshot.tasks for i in task.interrupts]
            if (version != row['version'] or row['retries'] >= 2 or not snapshot.next or pending
                    or (snapshot.values or {}).get('run_version') != version):
                raise HTTPException(409, '현재 실패한 실행만 최대 두 번 재시도할 수 있습니다.')
            conn.execute("UPDATE threads SET retries=retries+1,status='RUNNING' WHERE id=%s", (thread,))
            self._invoke(conn, thread, None)
        return self.detail(user, thread)

    def approve(self, user, thread, version):
        with self.locked(user, thread) as (conn, row):
            approved = conn.execute('SELECT snapshot,approved_at FROM approvals WHERE thread_id=%s AND version=%s', (thread, version)).fetchone()
            # 기존 승인은 현재 그래프 상태와 무관하게 불변 원본으로 Store만 복구한다.
            if not approved:
                self._reconcile(conn, row)
                detail = self.detail(user, thread)
                if version != row['version'] or not detail['can_approve']:
                    raise HTTPException(409, '현재 완료된 판정 결과만 승인할 수 있습니다.')
                state = self.graph.get_state(self.config(thread)).values
                conn.execute('INSERT INTO approvals(thread_id,version,snapshot) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',
                             (thread, version, Jsonb({'answer': detail['answer'], 'judgement': state['judgement'],
                                                      'part': (state.get('target_part') or {}).get('value', ''),
                                                      'context': {'question': state.get('question', ''),
                                                                  'conditions': state.get('conditions', ''),
                                                                  'target_part': state.get('target_part') or {},
                                                                  'judge_read': state.get('judge_read') or {}}})))
                approved = conn.execute('SELECT snapshot,approved_at FROM approvals WHERE thread_id=%s AND version=%s', (thread, version)).fetchone()
            judgement = approved['snapshot']['judgement']
            # 이전 스냅샷에는 part가 없다. 변경 불가인 업로드 회로의 고정 대상에서 읽는다.
            part = approved['snapshot'].get('part')
            if part is None:
                part = next((p.get('value', '') for p in row['connections']['components'] if p['ref'] == row['target']), '')
            value = {'thread_id': str(thread), 'version': version, 'approved_at': approved['approved_at'].isoformat(),
                     'roles': judgement.get('roles') or [], 'part': part,
                     'summary': approved['snapshot']['answer'][:2000]}
            try:
                self.store.put(namespace(str(user)), f'{thread}:{version}', value)
            except Exception:
                raise HTTPException(503, '승인 원본은 보관했습니다. 기억 저장을 위해 같은 결과를 다시 승인하세요.') from None
        return {'ok': True, 'version': version}

    def memories(self, user, roles=None, part=None):
        items = self.store.search(namespace(str(user)), filter={'part': part} if part and not roles else None, limit=100)
        matches = [i.value for i in items if (not roles and not part) or
                   set(roles or []) & set(i.value.get('roles') or []) or
                   (part and part.casefold() == i.value.get('part', '').casefold())]
        results = []
        with self.connection() as conn:
            for value in matches:
                row = conn.execute('SELECT a.snapshot,a.approved_at,c.connections,t.target FROM approvals a JOIN threads t ON t.id=a.thread_id '
                                   'JOIN circuits c ON c.id=t.circuit_id '
                                   'WHERE t.user_id=%s AND a.thread_id=%s AND a.version=%s',
                                   (user, value['thread_id'], value['version'])).fetchone()
                if row:
                    snapshot = row['snapshot']
                    original_part = snapshot.get('part')
                    if original_part is None:
                        original_part = next((p.get('value', '') for p in row['connections']['components'] if p['ref'] == row['target']), '')
                    original_roles = snapshot['judgement'].get('roles') or []
                    if (roles or part) and not (set(roles or []) & set(original_roles) or
                                               (part and part.casefold() == original_part.casefold())):
                        continue
                    results.append({'thread_id': value['thread_id'], 'version': value['version'],
                                    'approved_at': row['approved_at'].isoformat(), 'part': original_part,
                                    'roles': original_roles, 'summary': snapshot['answer'][:2000],
                                    'context': snapshot.get('context'), 'judgement': snapshot['judgement']})
        return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='사용자 분석 저장소 준비(대상 DB를 먼저 확인하세요)')
    parser.add_argument('--setup', action='store_true', required=True)
    parser.parse_args()
    initialize(os.environ['DATABASE_URL'])
    print('분석 저장소 준비 완료')
