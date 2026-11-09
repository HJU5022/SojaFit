"""세션 사용자별 업로드·분석 thread·승인 사례. 공유 DB setup은 명시적 CLI만 수행한다."""
import argparse
import os
import math
import time
import logging
import json
from decimal import Decimal
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

from backend.graph.memory import namespace, memory_policy
from backend.graph.netlist import parse_netlist


def initialize(dsn):
    """인증 DB에 전용 스키마를 준비한다. 기존 코퍼스·인증 행은 변경하지 않는다."""
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row, connect_timeout=5) as conn:
        for script in ('013_agent_memory.sql', '014_thread_inputs.sql', '015_analysis_limits.sql', '016_memory_controls.sql', '017_analysis_events.sql'):
            conn.execute((Path(__file__).parents[1] / 'db' / script).read_text(encoding='utf-8'))
        conn.execute('SET search_path TO sojafit_agent')
        PostgresSaver(conn).setup()
        PostgresStore(conn).setup()


class Conversations:
    def __init__(self, dsn, factory=None):
        from backend.services import demo
        self.mode = 'demo' if demo.enabled() else 'live'
        self.dsn = make_conninfo(dsn, options='-c search_path=sojafit_agent')
        self.stack = ExitStack()
        try:
            with self.connection() as conn:
                if not all(conn.execute("SELECT to_regclass(%s) AS name", (name,)).fetchone()['name']
                           for name in ('threads', 'approvals', 'checkpoints', 'store', 'analysis_usage')):
                    raise RuntimeError('분석 DB 준비 명령을 먼저 실행하세요.')
                if not conn.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='sojafit_agent' AND table_name='threads' AND column_name='input_record'").fetchone():
                    raise RuntimeError('분석 DB 준비 명령으로 입력 기록 마이그레이션을 적용하세요.')
            self._budget_settings()
            self.readiness()
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

    def readiness(self):
        """모델 호출·사용자 행 읽기 없이 현재 분석 저장소의 연결과 스키마를 확인한다."""
        with self.connection() as conn:
            conn.execute('SELECT t.input_record,a.memory_status,a.correction FROM threads t, circuits c, messages m, approvals a, analysis_usage u, analysis_events e LIMIT 0')
            conn.execute('SELECT 1 FROM checkpoints, checkpoint_blobs, checkpoint_writes, store LIMIT 0')

    @staticmethod
    def _budget_settings():
        from backend.services.llm import EvaluationBudget
        budget = EvaluationBudget(max_calls=int(os.getenv('ANALYSIS_MAX_CALLS', '16')),
            max_usd=float(os.getenv('ANALYSIS_MAX_USD', '0.50')), max_seconds=float(os.getenv('ANALYSIS_MAX_SECONDS', '90')),
            max_tokens=int(os.getenv('ANALYSIS_MAX_TOKENS', '4096')),
            prompt_rate=float(os.getenv('ANALYSIS_PROMPT_RATE', '0.000003')),
            completion_rate=float(os.getenv('ANALYSIS_COMPLETION_RATE', '0.000015')))
        daily = float(os.getenv('ANALYSIS_DAILY_USD', '3'))
        interval = float(os.getenv('ANALYSIS_MIN_INTERVAL_SECONDS', '2'))
        if not math.isfinite(daily) or daily <= 0 or not math.isfinite(interval) or interval < 0:
            raise ValueError('분석 일일 예산/빈도 설정을 확인하세요.')
        return budget, daily, interval

    def _budget(self, user):
        budget, daily, interval = self._budget_settings()
        with self.connection() as conn:
            row = conn.execute("INSERT INTO analysis_usage(user_id,day,next_allowed) VALUES (%s,(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date,CURRENT_TIMESTAMP + %s * INTERVAL '1 second') "
                "ON CONFLICT(user_id,day) DO UPDATE SET attempts=analysis_usage.attempts+1,next_allowed=EXCLUDED.next_allowed "
                "WHERE analysis_usage.next_allowed<=CURRENT_TIMESTAMP AND analysis_usage.reserved_usd<%s RETURNING day",
                (user, interval, Decimal(str(daily)))).fetchone()
        if not row:
            raise HTTPException(429, '호출 간격 또는 하루 분석 예약 예산을 확인하세요.', headers={'Retry-After': str(max(1, math.ceil(interval)))})
        def charge(cost):
            with self.connection() as conn:
                charged = conn.execute('UPDATE analysis_usage SET reserved_usd=reserved_usd+%s WHERE user_id=%s AND day=%s AND reserved_usd+%s<=%s RETURNING user_id',
                    (Decimal(str(cost)), user, row['day'], Decimal(str(cost)), Decimal(str(daily)))).fetchone()
            if not charged:
                raise HTTPException(429, '하루 분석 예약 예산에 도달했습니다.')
        budget.on_reserve = charge
        return budget

    def _graph(self):
        from backend.graph.mcp_retriever import StdioMcpRetriever
        from backend.multi_agent.build import build_graph
        from backend.services import demo
        from backend.services.langfuse_prompts import timed_tool
        if demo.enabled():
            self.mode = 'demo'
            return build_graph(chat=demo.chat, retriever=lambda *a, **k: [], judge_enabled=True,
                lookup=demo.lookup, specs=timed_tool('specs',demo.specs), find=lambda *a, **k: [], checkpointer=self.saver, store=self.store)
        from backend.multi_agent.facts import make_lookup
        from backend.rag.retrieve import retrieve
        from backend.services import llm
        mcp = self.stack.enter_context(StdioMcpRetriever())
        return build_graph(chat=llm.node_chat, retriever=timed_tool('search',retrieve), judge_enabled=True,
            lookup=make_lookup(mcp.check), specs=timed_tool('specs',mcp.part_specs), find=timed_tool('find',mcp.find_parts),
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
        if self.mode == 'demo':
            from backend.services.demo import configuration
            if connections != parse_netlist(configuration()['netlist']):
                raise HTTPException(422, '합성 데모 회로만 업로드할 수 있습니다.')
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
            approvals = conn.execute('SELECT version,snapshot,approved_at,memory_status,correction FROM approvals WHERE thread_id=%s ORDER BY version DESC LIMIT 50', (thread,)).fetchall()
            events = conn.execute('SELECT version,request_id,mode,status,elapsed_ms,stages,trace_id,trace_delivery FROM analysis_events WHERE thread_id=%s ORDER BY created_at DESC LIMIT 20', (thread,)).fetchall()
        approval_rows = []
        for approval in approvals:
            memory_state = approval['memory_status']
            if memory_state == 'active':
                try:
                    memory_state = 'stored' if self.store.get(namespace(str(user)), f"{thread}:{approval['version']}") else 'pending'
                except Exception:
                    memory_state = 'unknown'
            approval_rows.append({'version': approval['version'], 'approved_at': approval['approved_at'].isoformat(),
                                  'memory_state': memory_state, 'summary': approval['snapshot']['answer'][:2000],
                                  'correction': approval['correction'],
                                  'input_record': (approval['snapshot'].get('context') or {}).get('input_record')})
        snapshot = self.graph.get_state(self.config(thread))
        state = snapshot.values or {}
        pending = [i.value for task in snapshot.tasks for i in task.interrupts]
        judgement = state.get('judgement') or {}
        visible_memories = self._current_memories(user, state.get('approved_memories') or [])
        can_approve = (row['status'] == 'DONE' and state.get('run_version') == row['version'] and not snapshot.next
                       and not state.get('refusal') and bool(judgement.get('shown') or judgement.get('results')))
        related = self.memories(user, roles=judgement.get('roles'), part=(state.get('target_part') or {}).get('value')) if judgement else []
        return {'id': str(row['id']), 'mode': self.mode, 'filename': row['filename'], 'target': row['target'], 'version': row['version'],
                'status': row['status'], 'messages': messages, 'answer': '' if pending or (row.get('input_record') or {}).get('execution_limit_reached') else state.get('answer', ''),
                'interrupt': pending[0] if pending else None, 'can_approve': bool(can_approve),
                'can_retry': bool(snapshot.next and not pending and row['retries'] < 2 and state.get('run_version') == row['version']),
                'related_memories': related[:5], 'approvals': approval_rows, 'events': events,
                'consulted_memories': visible_memories,
                'referenced_memories': [m for m in visible_memories
                                        if f"승인사례:{m['thread_id']}:{m['version']}" in (state.get('memory_refs') or [])
                                        and not pending and not state.get('refusal')]}

    def message(self, user, thread, text, conditions='', request_id=''):
        with self.locked(user, thread) as (conn, row):
            if self.mode == 'demo':
                from backend.services.demo import validate_question
                validate_question(text, conditions)
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
            budget = self._budget(user)
            with conn.transaction():
                conn.execute("UPDATE threads SET version=%s,status='RUNNING',retries=0,input_record=%s WHERE id=%s",
                             (version, Jsonb({'version': version, 'question': text, 'conditions': conditions, 'resumes': []}), thread))
                conn.execute("INSERT INTO messages(thread_id,role,content) VALUES (%s,'user',%s)", (thread, content))
            # 이전 사용자 입력만 조건 문맥으로 쓴다. 모델 답변을 측정값의 근거로 되먹이지 않는다.
            context = '\n'.join(r['content'] for r in history[-12:])[-20000:]
            inputs = {'input': f'이전 사용자 입력:\n{context}\n현재 질문:\n{content}' if context else content,
                      'connections': row['connections'], 'circuit': row['filename'], 'target': row['target'],
                      'conditions': conditions, 'user_id': str(user), 'run_version': version,
                      'approved_memories': memories}
            self._invoke(conn, thread, inputs, budget, request_id)
        return self.detail(user, thread)

    def resume(self, user, thread, answers, role, version, request_id=''):
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
            budget = self._budget(user)
            content = '조건 답변:\n' + ('\n'.join(f'{key}: {value}' for key, value in answers.items()) or '모름')
            if role:
                content += f'\n선택한 역할: {role}'
            record = row.get('input_record') or {'version': version, 'question': None, 'conditions': None, 'resumes': []}
            record.pop('execution_limit_reached',None)
            record['resumes'].append({'answers': answers, 'role': role})
            with conn.transaction():
                conn.execute('UPDATE threads SET input_record=%s WHERE id=%s', (Jsonb(record), thread))
                conn.execute("INSERT INTO messages(thread_id,role,content) VALUES (%s,'user',%s)", (thread, content))
            self._invoke(conn, thread, Command(resume={'answers': answers, 'role': role}), budget, request_id)
        return self.detail(user, thread)

    def _invoke(self, conn, thread, inputs, budget, request_id=''):
        from backend.services.llm import evaluation_limits, EvaluationLimitError
        from backend.services import langfuse_prompts
        timings = langfuse_prompts.AnalysisTimings()
        started = time.monotonic()
        try:
            user = conn.execute('SELECT user_id FROM threads WHERE id=%s', (thread,)).fetchone()['user_id']
            with evaluation_limits(budget), memory_policy(lambda items: self._current_memories(user, items)), langfuse_prompts.analysis_timings(timings):
                budget.remaining()
                self.graph.invoke(inputs, {**self.config(thread), 'callbacks': [timings]})
                budget.remaining()
            saved = time.monotonic()
            self._finish(conn, thread, self.graph.get_state(self.config(thread)))
            timings.stages.append({'stage':'save_result','status':'ok','elapsed_ms':int((time.monotonic()-saved)*1000)})
        except Exception as error:
            conn.execute("UPDATE threads SET status='FAILED' WHERE id=%s", (thread,))
            if isinstance(error, EvaluationLimitError) or (isinstance(error,HTTPException) and error.status_code==429):
                conn.execute("UPDATE threads SET input_record=jsonb_set(COALESCE(input_record,'{}'::jsonb),'{execution_limit_reached}','true') WHERE id=%s", (thread,))
            logging.getLogger(__name__).warning(json.dumps({'event': 'analysis_failed', 'request_id': request_id,
                'thread_id': str(thread), 'error_type': type(error).__name__,
                'elapsed_ms': int((time.monotonic()-budget.started)*1000)}))
            if isinstance(error, HTTPException):
                raise
            if isinstance(error, EvaluationLimitError):
                status = 504 if time.monotonic()-budget.started >= budget.max_seconds else 429
                raise HTTPException(status, '분석 실행의 시간·호출·예약 예산 상한에 도달했습니다.') from None
            raise HTTPException(503, '분석을 완료하지 못했습니다. 잠시 후 상태를 확인하세요.') from None
        finally:
            self._record_event(conn,thread,started,timings.report(),request_id)

    def _record_event(self, conn, thread, started, stages, request_id, status=None, version=None):
        from backend.services import langfuse_prompts
        # 관측 장애가 이미 저장한 checkpoint/답변/승인의 성공 여부를 바꾸지 않는다.
        try:
            row = conn.execute('SELECT user_id,version,status FROM threads WHERE id=%s', (thread,)).fetchone()
            event = {'version': version if version is not None else row['version'], 'request_id': request_id,
                     'mode': self.mode, 'status': status or row['status'], 'elapsed_ms': int((time.monotonic()-started)*1000),
                     'stages': stages, 'trace_id': uuid4().hex}
            try:
                delivery = langfuse_prompts.publish_analysis_trace(row['user_id'], thread, event)
            except Exception:
                delivery = 'failed'
            conn.execute('INSERT INTO analysis_events(id,thread_id,version,request_id,mode,status,elapsed_ms,stages,trace_id,trace_delivery) '
                         'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                         (uuid4(),thread,event['version'],request_id,self.mode,event['status'],event['elapsed_ms'],Jsonb(stages),event['trace_id'],delivery))
            logging.getLogger(__name__).info(json.dumps({'event':'analysis_finished','user_id':row['user_id'],
                'thread_id':str(thread),**event,'trace_delivery':delivery}))
        except Exception:
            logging.getLogger(__name__).warning('analysis_metadata_unavailable')

    def _finish(self, conn, thread, snapshot):
        pending = [i.value for task in snapshot.tasks for i in task.interrupts]
        answer = str(pending[0].get('question', '조건을 입력하세요.')) if pending else snapshot.values.get('answer', '')
        checkpoint = snapshot.config['configurable']['checkpoint_id']
        with conn.transaction():
            conn.execute('UPDATE threads SET status=%s WHERE id=%s', ('WAITING' if pending else 'DONE', thread))
            conn.execute("INSERT INTO messages(thread_id,role,content,checkpoint_id) VALUES (%s,'assistant',%s,%s) ON CONFLICT DO NOTHING",
                         (thread, answer, checkpoint))

    def _reconcile(self, conn, row):
        if (row.get('input_record') or {}).get('execution_limit_reached'):
            return
        snapshot = self.graph.get_state(self.config(row['id']))
        pending = [i for task in snapshot.tasks for i in task.interrupts]
        if (snapshot.values or {}).get('run_version') == row['version'] and (not snapshot.next or pending):
            self._finish(conn, row['id'], snapshot)

    def retry(self, user, thread, version, request_id=''):
        with self.locked(user, thread) as (conn, row):
            snapshot = self.graph.get_state(self.config(thread))
            pending = [i for task in snapshot.tasks for i in task.interrupts]
            if (version != row['version'] or row['retries'] >= 2 or not snapshot.next or pending
                    or (snapshot.values or {}).get('run_version') != version):
                raise HTTPException(409, '현재 실패한 실행만 최대 두 번 재시도할 수 있습니다.')
            budget = self._budget(user)
            conn.execute("UPDATE threads SET retries=retries+1,status='RUNNING',input_record=input_record-'execution_limit_reached' WHERE id=%s", (thread,))
            self._invoke(conn, thread, None, budget, request_id)
        return self.detail(user, thread)

    def approve(self, user, thread, version, request_id=''):
        with self.connection() as conn:
            self._owned(conn,user,thread)
            started, status = time.monotonic(), 'failed'
            try:
                result = self._approve(user,thread,version); status = 'ok'; return result
            finally:
                stages = [{'stage':'approval_and_store','status':status,'elapsed_ms':int((time.monotonic()-started)*1000)}]
                self._record_event(conn,thread,started,stages,request_id,'APPROVED' if status=='ok' else 'APPROVAL_FAILED',version)

    def _approve(self, user, thread, version):
        with self.locked(user, thread) as (conn, row):
            approved = conn.execute('SELECT snapshot,approved_at,memory_status FROM approvals WHERE thread_id=%s AND version=%s', (thread, version)).fetchone()
            if approved and approved['memory_status'] != 'active':
                raise HTTPException(409, '철회·삭제한 기억은 재승인으로 복구할 수 없습니다. 철회 복구 기능을 사용하세요.')
            # 기존 승인은 현재 그래프 상태와 무관하게 불변 원본으로 Store만 복구한다.
            if not approved:
                self._reconcile(conn, row)
                detail = self.detail(user, thread)
                if version != row['version'] or not detail['can_approve']:
                    raise HTTPException(409, '현재 완료된 판정 결과만 승인할 수 있습니다.')
                state = self.graph.get_state(self.config(thread)).values
                resolved = [{'task': r.get('task'), 'inputs': r['judgement']['analysis_inputs']}
                            for r in state.get('final_reports') or state.get('reports') or []
                            if (r.get('judgement') or {}).get('analysis_inputs')]
                if not resolved and state['judgement'].get('analysis_inputs'):
                    resolved = [{'task': None, 'inputs': state['judgement']['analysis_inputs']}]
                conn.execute('INSERT INTO approvals(thread_id,version,snapshot) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',
                             (thread, version, Jsonb({'answer': detail['answer'], 'judgement': state['judgement'],
                                                      'part': (state.get('target_part') or {}).get('value', ''),
                                                      'context': {'question': state.get('question', ''),
                                                                  'input_record': row.get('input_record'),
                                                                  'resolved_inputs': resolved,
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
                row = conn.execute('SELECT a.snapshot,a.approved_at,a.correction,c.connections,t.target FROM approvals a JOIN threads t ON t.id=a.thread_id '
                                   'JOIN circuits c ON c.id=t.circuit_id '
                                   "WHERE t.user_id=%s AND a.thread_id=%s AND a.version=%s AND a.memory_status='active'",
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
                                    'correction': row['correction'],
                                    'context': snapshot.get('context'), 'judgement': snapshot['judgement']})
        return results

    def _current_memories(self, user, items):
        if not items:
            return []
        # checkpoint의 과거 사본 대신 현재 승인 원본/상태/정정 메모를 다시 읽는다.
        active = {(m['thread_id'],m['version']):m for m in self.memories(user)}
        return [active[(m['thread_id'],m['version'])] for m in items
                if (m['thread_id'],m['version']) in active]

    def control_memory(self, user, thread, version, action, correction):
        if action not in ('correct','revoke','restore','delete') or len(correction) > 1000:
            raise HTTPException(422, '기억 관리 요청을 확인하세요.')
        with self.locked(user, thread) as (conn, _):
            row = conn.execute('SELECT memory_status FROM approvals WHERE thread_id=%s AND version=%s', (thread,version)).fetchone()
            if not row:
                raise HTTPException(404, '승인 사례를 찾을 수 없습니다.')
            if row['memory_status'] == 'deleted' and action != 'delete':
                raise HTTPException(409, '기억에서 삭제한 사례는 복구할 수 없습니다. 대화·승인 원본은 유지됩니다.')
            if action == 'correct':
                conn.execute('UPDATE approvals SET correction=%s,memory_updated_at=CURRENT_TIMESTAMP WHERE thread_id=%s AND version=%s', (correction,thread,version))
            else:
                status = {'revoke':'revoked','restore':'active','delete':'deleted'}[action]
                conn.execute('UPDATE approvals SET memory_status=%s,memory_updated_at=CURRENT_TIMESTAMP WHERE thread_id=%s AND version=%s', (status,thread,version))
                if action == 'delete':
                    # 먼저 삭제 표식을 확정한다. Store 장애가 있어도 이후 모델 입력은 차단된다.
                    try:
                        self.store.delete(namespace(str(user)), f'{thread}:{version}')
                    except Exception:
                        raise HTTPException(503, '기억 참조는 차단했습니다. Store 사본 제거를 위해 기억 삭제를 다시 요청하세요.') from None
        return {'ok':True, 'version':version}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='사용자 분석 저장소 준비(대상 DB를 먼저 확인하세요)')
    parser.add_argument('--setup', action='store_true', required=True)
    parser.parse_args()
    initialize(os.environ['DATABASE_URL'])
    print('분석 저장소 준비 완료')
