"""세션 사용자별 업로드·분석 thread·승인 기록·사용자 사실 기억(profile). 공유 DB setup은 명시적 CLI만 수행한다.

React 작업대의 run·재개도 `ensure_thread`로 같은 UUID의 thread를 만든 뒤 이 서비스를 거친다(backend/api/conversations.py).
장기 기억은 사용자 사실 3칸(`profile.py`, SPEC 8.5)이다. 질문을 분석할 때 그 질문으로 사실을 찾아 결과의 `profile_hints`로만 돌려주고,
모델 프롬프트 · 판정 입력에는 넣지 않는다(`backend/multi_agent/` 병합 뒤). 승인한 판정 사례는 기억이 아니라 승인 기록이다:
새 분석에 넘기지 않고(`approved_memories`는 빈 목록) Store에도 쓰지 않는다.
분석 예산: 호출마다 USD 예약과 같은 위쪽 경계 토큰을 사용자 · 서비스 전체의 UTC 하루 상한(200,000 · 2,000,000, SPEC 8.6)에서
DB로 원자적으로 차감한다(`_budget`, db/022). 공급자가 청구한 토큰이 아니라 예약이다.
삭제(SPEC 8.5): 프로젝트 삭제는 같은 UUID의 분석 thread · checkpoint를 같은 트랜잭션에서 지우고(`delete_analysis_threads`),
탈퇴는 계정 단위 잠금을 잡고 분석 기록 → Store namespace 순서로 지운다(`account_deletion`, 계정은 호출자가 마지막에 지움).
분석 · 기록을 만드는 쓰기는 같은 잠금을 공유로 잡아(`_hold_account`) 탈퇴 중이면 409, 쓰는 중이면 탈퇴가 409다.
보관 기간: 새 분석(질문)을 시작할 때 프로젝트 60일 · 기록 30일 청소 함수(db/023)를 작은 묶음으로 부른다(`_purge_expired`, 스케줄러 없음).
"""
import argparse
import os
import math
import time
import logging
import json
from decimal import Decimal
from contextlib import ExitStack, contextmanager
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

import psycopg
from fastapi import HTTPException
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.base import PutOp
from langgraph.store.postgres import PostgresStore
from langgraph.types import Command
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row, tuple_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool

from backend.conversations import profile
from backend.graph.memory import namespace, memory_policy
from backend.graph.netlist import parse_netlist

LOGGER = logging.getLogger('backend.conversations')
RETENTION_LOGGER = logging.getLogger('backend.conversations.retention')

# 하루 LLM 토큰 상한(11-09 결정, UTC 날짜). 공급자 청구 토큰이 아니라 호출 전에 잡는 예약 토큰의 합이다
USER_DAILY_TOKENS = 200_000
SERVICE_DAILY_TOKENS = 2_000_000
TOKEN_MARGIN = 8192  # [주의] llm.EvaluationBudget._reserve가 입력 바이트에 더하는 여유와 같아야 한다(시험이 USD 예약과 맞춰 본다)
USER_TOKENS_FULL = '오늘 쓸 수 있는 분석 사용량(하루 200,000 토큰)을 다 썼습니다. 한국 시각 오전 9시(UTC 0시) 뒤에 다시 시도하세요.'
SERVICE_TOKENS_FULL = '오늘 서비스 전체 분석 사용량(하루 2,000,000 토큰)이 다 찼습니다. 한국 시각 오전 9시(UTC 0시) 뒤에 다시 시도하세요.'


@lru_cache(maxsize=1)
def _token_budget_class():
    """EvaluationBudget을 이어받아 호출마다 예약 토큰 수를 `reserving_tokens`에 두는 클래스."""
    # [왜] llm은 import 때 .env를 읽는다. 준비 CLI가 .env의 원격 DB를 집지 않게 처음 예산을 만들 때 import한다
    from backend.services.llm import EvaluationBudget

    class TokenBudget(EvaluationBudget):
        def _reserve(self, text, *, output_tokens, embedding=False):
            # [왜] reserve()가 잠금을 잡은 채 부르므로 이 값은 같은 호출의 on_reserve(DB 차감)만 읽는다
            self.reserving_tokens = len(text.encode('utf-8')) + TOKEN_MARGIN + output_tokens
            return super()._reserve(text, output_tokens=output_tokens, embedding=embedding)

    return TokenBudget


def delete_analysis_threads(conn, user, ids=None):
    """사용자의 분석 thread(ids가 없으면 전부)와 딸린 checkpoint · 메시지 · 승인 기록 · 분석 사건 · 회로를 conn의 트랜잭션에서 지운다.

    프로젝트 삭제(ids = 그 프로젝트의 React 대화 UUID)와 탈퇴(ids 없음)가 쓴다. 지운 건수를 돌려주고, 분석 서비스 표가 없는 DB면 모두 0이다.
    [주의] 사용자 조건(user_id)으로 고른 thread만 지운다. 호출자가 ids의 소유권을 따로 확인했어도 다른 사용자 행은 건드리지 않는다.
    """
    counts = {'analysis_threads': 0, 'analysis_circuits': 0, 'checkpoints': 0}
    cur = conn.cursor(row_factory=tuple_row)  # [왜] 프로젝트 API 연결(튜플 행)과 이 서비스 연결(dict 행) 둘 다에서 같은 모양으로 읽는다
    has_threads, has_checkpoints = cur.execute("SELECT to_regclass('sojafit_agent.threads') IS NOT NULL, "
                                               "to_regclass('sojafit_agent.checkpoints') IS NOT NULL").fetchone()
    if not has_threads:
        return counts
    owned, params = 'SELECT id FROM sojafit_agent.threads WHERE user_id=%s', (user,)
    if ids is not None:
        owned, params = owned + ' AND id = ANY(%s::uuid[])', (user, list(ids))
    if has_checkpoints:
        # [왜] LangGraph checkpoint 표 3개는 thread_id(글자)로만 묶이고 FK가 없어 thread보다 먼저 직접 지운다
        for table in ('checkpoint_writes', 'checkpoint_blobs', 'checkpoints'):
            deleted = cur.execute(sql.SQL('DELETE FROM sojafit_agent.{} WHERE thread_id IN (SELECT id::text FROM ({}) o)').format(
                sql.Identifier(table), sql.SQL(owned)), params).rowcount
        counts['checkpoints'] = deleted
    # 메시지 · 승인 기록 · 분석 사건은 thread FK cascade로 함께 지워진다
    counts['analysis_threads'] = cur.execute(sql.SQL('DELETE FROM sojafit_agent.threads WHERE id IN ({})').format(sql.SQL(owned)), params).rowcount
    # 회로: 탈퇴면 사용자 회로 전부, 프로젝트 삭제면 같은 UUID 회로 중 남은 thread가 없는 것(React 대화 하나 = 회로 하나)
    circuits = 'DELETE FROM sojafit_agent.circuits c WHERE c.user_id=%s'
    if ids is not None:
        circuits += ' AND c.id = ANY(%s::uuid[]) AND NOT EXISTS (SELECT 1 FROM sojafit_agent.threads t WHERE t.circuit_id=c.id)'
    counts['analysis_circuits'] = cur.execute(circuits, params).rowcount
    return counts


def _vector_schema(conn):
    """설치된 pgvector 확장의 스키마 이름(로컬 Compose는 public, Supabase는 extensions). 없으면 None."""
    row = conn.execute("SELECT n.nspname AS name FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector'").fetchone()
    return row['name'] if row else None


def initialize(dsn):
    """인증 DB에 전용 스키마를 준비한다. 기존 코퍼스·인증 행은 변경하지 않는다."""
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row, connect_timeout=5) as conn:
        for script in ('013_agent_memory.sql', '014_thread_inputs.sql', '015_analysis_limits.sql', '016_memory_controls.sql', '017_analysis_events.sql',
                       '022_token_limits.sql', '023_retention.sql'):
            conn.execute((Path(__file__).parents[2] / 'db' / script).read_text(encoding='utf-8'))
        vector = _vector_schema(conn)
        # [왜] 의미 색인 표(store_vectors)의 vector 형은 확장이 설치된 스키마에 있다. sojafit_agent만 보면 형을 못 찾는다.
        #      표는 search_path 첫 스키마(sojafit_agent)에 만들어진다
        conn.execute(sql.SQL('SET search_path TO sojafit_agent{}').format(sql.SQL(', {}').format(sql.Identifier(vector)) if vector else sql.SQL('')))
        PostgresSaver(conn).setup()
        # [주의] vector 확장이 없으면(CI의 postgres:16) 색인 표 없이 준비한다. 확장 설치는 여기서 하지 않는다(db/000_init.sql · Supabase 몫)
        PostgresStore(conn, index=profile.INDEX if vector else None).setup()


class Conversations:
    def __init__(self, dsn, factory=None):
        from backend.services import demo
        self.mode = 'demo' if demo.enabled() else 'live'
        self.dsn = make_conninfo(dsn, options='-c search_path=sojafit_agent')
        self.stack = ExitStack()
        try:
            with self.connection() as conn:
                if not all(conn.execute("SELECT to_regclass(%s) AS name", (name,)).fetchone()['name']
                           for name in ('threads', 'approvals', 'checkpoints', 'store', 'analysis_usage', 'analysis_service_usage')):
                    raise RuntimeError('분석 DB 준비 명령을 먼저 실행하세요.')
                # [왜] 청소 함수가 없으면 보관 기간 규칙이 조용히 꺼진다. 표와 같이 시작 때 확인한다(db/023)
                if not all(conn.execute('SELECT to_regprocedure(%s) AS name', (name,)).fetchone()['name']
                           for name in ('purge_inactive_projects(integer,integer)', 'purge_log_records(integer,integer)')):
                    raise RuntimeError('분석 DB 준비 명령으로 보관 기간 청소 함수(db/023)를 만드세요.')
                if not conn.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='sojafit_agent' AND table_name='threads' AND column_name='input_record'").fetchone():
                    raise RuntimeError('분석 DB 준비 명령으로 입력 기록 마이그레이션을 적용하세요.')
                vector = _vector_schema(conn) if conn.execute("SELECT to_regclass('store_vectors') AS name").fetchone()['name'] else None
            indexed = bool(vector) and profile.embedding_enabled()
            if indexed:
                # [왜] 의미 검색 SQL이 vector 형 · 거리 연산자를 이름만으로 찾는다. 확장 스키마를 뒤에 붙인다(같은 이름 표는 sojafit_agent가 먼저)
                self.dsn = make_conninfo(dsn, options=f'-c search_path=sojafit_agent,"{vector}"')
            elif profile.embedding_enabled():
                LOGGER.warning('profile_index_unavailable: 분석 DB 준비 명령으로 의미 색인 표를 만드세요. 지금은 순위 없이 사실을 돌려줍니다.')
            self._budget_settings()
            self.readiness()
            self.pool = self.stack.enter_context(ConnectionPool(self.dsn, min_size=1, max_size=4, timeout=5,
                kwargs={'autocommit': True, 'row_factory': dict_row, 'prepare_threshold': 0}))
            self.saver, self.store = PostgresSaver(self.pool), PostgresStore(self.pool)
            # [왜] 그래프에 넘기는 Store에는 색인을 켜지 않는다(다른 put이 임베딩 호출을 부르지 않게). 사실 기억만 색인 Store를 쓴다
            self.profile = profile.ProfileMemory(PostgresStore(self.pool, index=profile.INDEX) if indexed else self.store, indexed)
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
            conn.execute('SELECT t.input_record,a.memory_status,a.correction,u.reserved_tokens,s.reserved_tokens FROM threads t, circuits c, messages m, approvals a, '
                         'analysis_usage u, analysis_events e, analysis_service_usage s LIMIT 0')
            conn.execute('SELECT 1 FROM checkpoints, checkpoint_blobs, checkpoint_writes, store LIMIT 0')

    @staticmethod
    def _budget_settings():
        budget = _token_budget_class()(max_calls=int(os.getenv('ANALYSIS_MAX_CALLS', '16')),
            max_usd=float(os.getenv('ANALYSIS_MAX_USD', '0.50')), max_seconds=float(os.getenv('ANALYSIS_MAX_SECONDS', '90')),
            max_tokens=int(os.getenv('ANALYSIS_MAX_TOKENS', '4096')),
            prompt_rate=float(os.getenv('ANALYSIS_PROMPT_RATE', '0.000003')),
            completion_rate=float(os.getenv('ANALYSIS_COMPLETION_RATE', '0.000015')))
        daily = float(os.getenv('ANALYSIS_DAILY_USD', '3'))
        interval = float(os.getenv('ANALYSIS_MIN_INTERVAL_SECONDS', '2'))
        if not math.isfinite(daily) or daily <= 0 or not math.isfinite(interval) or interval < 0:
            raise ValueError('분석 일일 예산/빈도 설정을 확인하세요.')
        return budget, daily, interval

    @staticmethod
    def _token_room(conn, user):
        """오늘(UTC) 사용자 · 서비스 전체 예약 토큰에 호출 한 번(여유 TOKEN_MARGIN) 자리가 없으면 429. 외부 호출 전에 거른다."""
        used = conn.execute("SELECT (SELECT reserved_tokens FROM analysis_usage WHERE user_id=%s AND day=(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date) AS mine, "
                            "(SELECT reserved_tokens FROM analysis_service_usage WHERE day=(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date) AS service",
                            (user,)).fetchone()
        if (used['mine'] or 0) + TOKEN_MARGIN > USER_DAILY_TOKENS:
            raise HTTPException(429, USER_TOKENS_FULL)
        if (used['service'] or 0) + TOKEN_MARGIN > SERVICE_DAILY_TOKENS:
            raise HTTPException(429, SERVICE_TOKENS_FULL)

    def admission(self, user):
        """React run · 재개가 스트림을 열기 전에 부른다. 탈퇴 중이면 409, 하루 토큰 상한이 찼으면 429(공통 오류)로 거절한다."""
        with self.connection() as conn:
            self._hold_account(conn, user)  # 확인만 한다. 연결을 닫으면 풀리고, 실행은 locked()가 다시 잡는다
            self._token_room(conn, user)

    @staticmethod
    def _hold_account(conn, user):
        """이 연결이 닫힐 때까지 계정 공유 잠금을 잡는다. 탈퇴(같은 키의 배타 잠금)가 진행 중이면 409."""
        # [왜] 분석 · 기록 쓰기끼리는 서로 막지 않고(공유), 탈퇴와만 서로 막는다(배타). DB 세션 잠금이라 프로세스가 죽어도 연결과 함께 풀린다
        if not conn.execute('SELECT pg_try_advisory_lock_shared(hashtextextended(%s,0)) AS ok', (f'account:{user}',)).fetchone()['ok']:
            raise HTTPException(409, '계정 삭제를 처리하는 중입니다.')

    @contextmanager
    def account_writer(self, user):
        """분석 밖의 기록 쓰기(내 설정 Store)를 계정 공유 잠금 안에서 한다. 탈퇴 중이면 409."""
        with self.connection() as conn:
            self._hold_account(conn, user)
            yield

    @contextmanager
    def account_deletion(self, user):
        """탈퇴: 계정 배타 잠금을 잡고 분석 기록 → Store namespace 순서로 지운 건수를 넘긴다. 호출자는 with 안에서 계정을 마지막에 지운다.

        진행 중인 분석 · 기록 쓰기(공유 잠금)가 있으면 409. 잠금은 with가 끝나 연결을 닫을 때 풀린다.
        [주의] 계정을 먼저 지우면 기록 삭제가 실패했을 때 다시 요청할 방법이 없다. 중간에 실패해도 계정이 남아 있어
        다시 요청하면 남은 것부터 이어서 지운다(이미 지운 것은 0건으로 센다).
        """
        with self.connection() as conn:
            if not conn.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS ok', (f'account:{user}',)).fetchone()['ok']:
                raise HTTPException(409, '진행 중인 분석이나 저장이 끝난 뒤 다시 시도하세요.')
            with conn.transaction():
                counts = delete_analysis_threads(conn, user)
            counts['memory_items'] = self._delete_store(user)
            yield counts

    def _delete_store(self, user):
        """사용자의 Store 항목을 namespace 접두사로 찾아 모두 지우고 지운 수를 돌려준다."""
        # [왜] 아는 key만 지우면 나중에 생길 namespace가 남는다. 첫 칸이 사용자인 `(user, ...)` 전부와 옛 승인 사본 `("memories", user)`를 지운다
        # [주의] 접두사 검색은 칸 단위다(`("1",)`은 `("10", ...)`과 맞지 않음, 시험이 확인). 색인 벡터 행은 Store 표 FK cascade로 함께 지워진다
        deleted = 0
        for prefix in ((str(user),), namespace(str(user))):
            for _ in range(100):  # [왜] 반복 상한(한 번에 100개, 1만 개). 넘으면 503이고 다시 요청하면 이어서 지운다
                items = self.store.search(prefix, limit=100)
                if not items:
                    break
                self.store.batch([PutOp(item.namespace, item.key, None) for item in items])
                deleted += len(items)
            else:
                raise HTTPException(503, '계정 삭제를 끝내지 못했습니다. 다시 요청하면 남은 기록부터 이어서 지웁니다.')
        return deleted

    def _budget(self, user):
        budget, daily, interval = self._budget_settings()
        with self.connection() as conn:
            self._token_room(conn, user)
            row = conn.execute("INSERT INTO analysis_usage(user_id,day,next_allowed) VALUES (%s,(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date,CURRENT_TIMESTAMP + %s * INTERVAL '1 second') "
                "ON CONFLICT(user_id,day) DO UPDATE SET attempts=analysis_usage.attempts+1,next_allowed=EXCLUDED.next_allowed "
                "WHERE analysis_usage.next_allowed<=CURRENT_TIMESTAMP AND analysis_usage.reserved_usd<%s RETURNING day",
                (user, interval, Decimal(str(daily)))).fetchone()
        if not row:
            raise HTTPException(429, '호출 간격 또는 하루 분석 예약 예산을 확인하세요.', headers={'Retry-After': str(max(1, math.ceil(interval)))})
        def charge(cost):
            """호출 한 번의 예약 USD · 토큰을 사용자 행과 서비스 행에 한 트랜잭션으로 더한다. 하나라도 넘으면 모두 되돌리고 429."""
            tokens, cost = budget.reserving_tokens, Decimal(str(cost))
            with self.connection() as conn, conn.transaction():
                # [왜] 사용자 행 → 서비스 행 순서로만 잠가 동시 호출끼리 교착하지 않는다. 예외가 나면 트랜잭션이 둘 다 되돌린다
                usage = conn.execute('SELECT reserved_usd,reserved_tokens FROM analysis_usage WHERE user_id=%s AND day=%s FOR UPDATE',
                                     (user, row['day'])).fetchone()
                if usage['reserved_tokens'] + tokens > USER_DAILY_TOKENS:
                    raise HTTPException(429, USER_TOKENS_FULL)
                if usage['reserved_usd'] + cost > Decimal(str(daily)):
                    raise HTTPException(429, '하루 분석 예약 예산에 도달했습니다.')
                conn.execute('INSERT INTO analysis_service_usage(day) VALUES (%s) ON CONFLICT DO NOTHING', (row['day'],))
                if not conn.execute('UPDATE analysis_service_usage SET reserved_tokens=reserved_tokens+%s WHERE day=%s AND reserved_tokens+%s<=%s RETURNING day',
                                    (tokens, row['day'], tokens, SERVICE_DAILY_TOKENS)).fetchone():
                    raise HTTPException(429, SERVICE_TOKENS_FULL)
                conn.execute('UPDATE analysis_usage SET reserved_usd=reserved_usd+%s,reserved_tokens=reserved_tokens+%s WHERE user_id=%s AND day=%s',
                             (cost, tokens, user, row['day']))
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
        from functools import update_wrapper
        from backend.multi_agent.facts import make_lookup
        from backend.rag.card_find import default_find
        from backend.rag.card_specs import default_specs
        from backend.rag.retrieve import retrieve
        from backend.services import llm
        mcp = self.stack.enter_context(StdioMcpRetriever())  # 사실 확인(check_corpus)만 MCP로 부른다
        # [왜] 사양 표(part_specifications)를 11-09에 버리고 후보 찾기 · 판정 값은 카드 읽기가 기본이다(ADR 0016, 평가 실행기 run_graph.py와 같은 조립)
        # [주의] 카드 도구는 MCP를 거치지 않고 DATABASE_URL로 DB를 직접 읽는다. 표지 품번 색인은 조립 때가 아니라 첫 판정 때 한 번 읽는다
        specs, find = default_specs(), default_find()
        # [주의] timed_tool은 함수만 감싸 prefetch · doc_rows · also_read 속성을 잃는다. 대체 부품 에이전트가 getattr로 찾으므로 update_wrapper로 옮긴다
        return build_graph(chat=llm.node_chat, retriever=timed_tool('search',retrieve), judge_enabled=True,
            lookup=make_lookup(mcp.check, specs.doc_rows), specs=update_wrapper(timed_tool('specs',specs), specs),
            find=update_wrapper(timed_tool('find',find), find), checkpointer=self.saver, store=self.store)

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
            self._hold_account(conn, user)  # [왜] 실행이 끝날 때까지 탈퇴가 끼어들어 지운 기록을 다시 만들지 않게 한다
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
            self._hold_account(conn, user)
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
            self._hold_account(conn, user)
            row = conn.execute('SELECT connections FROM circuits WHERE id=%s AND user_id=%s', (circuit, user)).fetchone()
            if not row:
                raise HTTPException(404, '회로를 찾을 수 없습니다.')
            if target not in {p['ref'] for p in row['connections']['components']}:
                raise HTTPException(422, '회로에 없는 대상 부품입니다.')
            thread = str(uuid4())
            conn.execute('INSERT INTO threads(id,user_id,circuit_id,target) VALUES (%s,%s,%s,%s)', (thread, user, circuit, target))
        return {'id': thread}

    def ensure_thread(self, user, thread, filename, connections, target):
        """React 대화 하나를 같은 UUID의 분석 회로·thread로 처음 한 번 만든다. 대상 부품이 바뀌면 409."""
        # React 정규화 회로는 부품 목록이 parts, 데모 회로는 components다. 넷리스트 원문은 다시 읽지 않는다
        connections = {'components': connections.get('components', connections.get('parts', [])), 'nets': connections.get('nets', [])}
        if target not in {p['ref'] for p in connections['components']}:
            raise HTTPException(422, '회로에 없는 대상 부품입니다.')
        if self.mode == 'demo':
            from backend.services.demo import configuration
            if connections != parse_netlist(configuration()['netlist']):
                raise HTTPException(422, '합성 데모 회로만 분석할 수 있습니다.')
        with self.connection() as conn:
            self._hold_account(conn, user)  # 탈퇴 중이면 409(지운 분석 기록을 다시 만들지 않게)
            # [왜] React 대화 하나 = 분석 회로 하나 + thread 하나라 회로 id도 thread UUID를 쓴다. 동시 첫 실행에도 행이 하나만 생긴다
            # [주의] React 업로드는 원본을 저장하지 않으므로 netlist 칸은 빈 글자로 둔다
            with conn.transaction():
                conn.execute('INSERT INTO circuits(id,user_id,filename,netlist,connections) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING',
                             (thread, user, filename, '', Jsonb(connections)))
                conn.execute('INSERT INTO threads(id,user_id,circuit_id,target) VALUES (%s,%s,%s,%s) ON CONFLICT (id) DO NOTHING',
                             (thread, user, thread, target))
            row = self._owned(conn, user, thread)
        if row['target'] != target:
            raise HTTPException(409, '대상 부품을 바꾸려면 새 대화를 시작하세요.')

    def threads(self, user):
        with self.connection() as conn:
            rows = conn.execute('SELECT t.id,t.target,t.status,t.version,c.filename FROM threads t JOIN circuits c ON c.id=t.circuit_id '
                                'WHERE t.user_id=%s ORDER BY t.created_at DESC LIMIT 100', (user,)).fetchall()
        return [{**r, 'id': str(r['id'])} for r in rows]

    def detail(self, user, thread, hints=()):
        """thread 상태 · 결과 · 승인 기록. hints는 이번 질문으로 찾은 사용자 사실(message · resume만 넘기고 GET은 빈 목록)."""
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
            # [왜] 승인 사례는 이제 Store 기억이 아니라 승인 기록이다. 상태는 승인 원본 옆 표식(active · revoked · deleted) 그대로다
            approval_rows.append({'version': approval['version'], 'approved_at': approval['approved_at'].isoformat(),
                                  'memory_state': approval['memory_status'], 'summary': approval['snapshot']['answer'][:2000],
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
                'profile_hints': list(hints), 'consulted_memories': visible_memories,
                'referenced_memories': [m for m in visible_memories
                                        if f"승인사례:{m['thread_id']}:{m['version']}" in (state.get('memory_refs') or [])
                                        and not pending and not state.get('refusal')]}

    def _purge_expired(self):
        """보관 기간이 지난 프로젝트(60일) · 기록(30일)을 작은 묶음으로 지운다(db/023). 실패해도 분석은 계속한다."""
        try:
            with self.connection() as conn:
                conn.execute('SELECT purge_inactive_projects(), purge_log_records()')
        except psycopg.Error:
            RETENTION_LOGGER.warning('retention_purge_failed')

    def message(self, user, thread, text, conditions='', request_id=''):
        # [왜] 새 분석이 시작될 때 청소한다(스케줄러 없음). 이 thread를 잠그기 전에 해서, 60일 지난 thread면 반쯤 쓴 상태 없이 404로 끝난다
        self._purge_expired()
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
            budget = self._budget(user)
            hints = self._profile_hints(user, text)
            with conn.transaction():
                conn.execute("UPDATE threads SET version=%s,status='RUNNING',retries=0,input_record=%s WHERE id=%s",
                             (version, Jsonb({'version': version, 'question': text, 'conditions': conditions, 'resumes': []}), thread))
                conn.execute("INSERT INTO messages(thread_id,role,content) VALUES (%s,'user',%s)", (thread, content))
            # 이전 사용자 입력만 조건 문맥으로 쓴다. 모델 답변을 측정값의 근거로 되먹이지 않는다.
            context = '\n'.join(r['content'] for r in history[-12:])[-20000:]
            inputs = {'input': f'이전 사용자 입력:\n{context}\n현재 질문:\n{content}' if context else content,
                      'connections': row['connections'], 'circuit': row['filename'], 'target': row['target'],
                      'conditions': conditions, 'user_id': str(user), 'run_version': version,
                      # [왜] 승인 사례는 더 이상 새 분석에 넘기지 않는다. 빈 목록을 넣어 checkpoint에 남은 이전 목록도 지운다
                      'approved_memories': []}
            self._invoke(conn, thread, inputs, budget, request_id)
        return self.detail(user, thread, hints)

    def _profile_hints(self, user, question):
        """질문 글로 사용자 사실을 찾아 화면 참고용 칸(kind · value · text)만 돌려준다. 실패해도 분석은 계속한다."""
        try:
            return [{key: fact[key] for key in ('kind', 'value', 'text')} for fact in self.profile.facts(user, question)] if question else []
        except Exception:
            LOGGER.warning('profile_hints_unavailable')
            return []

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
            hints = self._profile_hints(user, record.get('question'))
            self._invoke(conn, thread, Command(resume={'answers': answers, 'role': role}), budget, request_id)
        return self.detail(user, thread, hints)

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
            LOGGER.warning(json.dumps({'event': 'analysis_failed', 'request_id': request_id,
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
            LOGGER.info(json.dumps({'event':'analysis_finished','user_id':row['user_id'],
                'thread_id':str(thread),**event,'trace_delivery':delivery}))
        except Exception:
            LOGGER.warning('analysis_metadata_unavailable')

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
            # 이미 승인한 버전은 현재 그래프 상태와 무관하게 원본을 그대로 두고 성공으로 답한다(멱등).
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
            # [왜] 승인 사례는 장기 기억이 아니라 승인 기록이다(11-09 결정). Store에 쓰지 않는다
        return {'ok': True, 'version': version}

    def memories(self, user, roles=None, part=None):
        """자기 승인 기록(철회 · 삭제 안 한 것, 최근 승인 순 최대 100건). roles · part를 주면 역할이나 품번이 같은 것만."""
        with self.connection() as conn:
            rows = conn.execute('SELECT a.thread_id,a.version,a.snapshot,a.approved_at,a.correction,c.connections,t.target FROM approvals a '
                                'JOIN threads t ON t.id=a.thread_id JOIN circuits c ON c.id=t.circuit_id '
                                "WHERE t.user_id=%s AND c.user_id=%s AND a.memory_status='active' ORDER BY a.approved_at DESC LIMIT 100",
                                (user, user)).fetchall()
        results = []
        for row in rows:
            snapshot = row['snapshot']
            # 이전 스냅샷에는 part가 없다. 변경 불가인 업로드 회로의 고정 대상에서 읽는다.
            original_part = snapshot.get('part')
            if original_part is None:
                original_part = next((p.get('value', '') for p in row['connections']['components'] if p['ref'] == row['target']), '')
            original_roles = snapshot['judgement'].get('roles') or []
            if (roles or part) and not (set(roles or []) & set(original_roles) or
                                       (part and part.casefold() == original_part.casefold())):
                continue
            results.append({'thread_id': str(row['thread_id']), 'version': row['version'],
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
                    # 먼저 삭제 표식을 확정한다. 이전 코드가 Store에 써 둔 사본이 있으면 지운다(새 승인은 Store에 쓰지 않음).
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
