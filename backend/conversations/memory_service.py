"""세션 사용자별 분석 thread·사용자 사실 기억(profile). 공유 DB setup은 명시적 CLI만 수행한다.

React 작업대의 run·재개는 `ensure_thread`로 같은 UUID의 thread를 만든 뒤 이 서비스를 거친다(backend/api/conversations.py).
HTTP 입구는 그 run·재개(`admission` · `ensure_thread` · `message` · `resume` · `detail`)와 내 설정 · 탈퇴, 그리고 회로도 후보 대화의 예산(`schematic_dialogue_budget`, api/external_circuits.py),
프로젝트 삭제의 분석 기록 삭제(`delete_analysis_threads`) · 부품 점검표의 판정 지원 검사(`_require_supported_target`, api/projects.py), 다른 대상 안내(`other_targets_note`, api/conversations.py)다.
`message` · `resume`의 `progress`는 그래프 노드가 시작할 때마다 노드 이름으로 불린다(SSE `status` 진행 단계, SPEC 4절).
분석 thread는 화면용 `public.threads`와 같은 UUID이고(FK, 화면 대화를 지우면 DB가 같이 지움),
회로 이름 · 연결 정보는 `public.threads → project_circuit_versions`의 고정 버전에서 읽는다(`_owned`).
장기 기억은 사용자 사실 3칸(`profile.py`, SPEC 8.5)이다. 질문을 분석할 때 그 질문으로 사실을 찾아 결과의 `profile_hints`로 돌려준다.
그래프에는 `user_id`와 Store만 넘기고, 선호 실장 방식은 그래프의 기억 읽기 노드가 직접 읽어 찾기 후보 순서에만 쓴다(`backend/graph/memory.py`).
사실을 모델 프롬프트에는 넣지 않는다. 승인한 판정 사례는 기억이 아니라 승인 기록이다:
새 분석에 넘기지 않고(`approved_memories`는 빈 목록) Store에도 쓰지 않는다. 승인 기록은 `public.approvals`(견적 승인, 이 서비스 밖)뿐이다.
분석 예산: 호출마다 USD 예약과 같은 위쪽 경계 토큰을 사용자 · 서비스 전체의 UTC 하루 상한(5,000,000 · 10,000,000, SPEC 8.6)에서
DB로 원자적으로 차감한다(`_budget`, db/020_service_baseline.sql). 공급자가 청구한 토큰이 아니라 예약이다.
삭제(SPEC 8.5): 프로젝트 삭제는 같은 UUID의 분석 thread · checkpoint를 같은 트랜잭션에서 지우고(`delete_analysis_threads`),
탈퇴는 계정 단위 잠금을 잡고 분석 기록 → Store namespace 순서로 지운다(`account_deletion`, 계정은 호출자가 마지막에 지움).
분석 · 기록을 만드는 쓰기는 같은 잠금을 공유로 잡아(`_hold_account`) 탈퇴 중이면 409, 쓰는 중이면 탈퇴가 409다.
보관 기간: 새 분석(질문)을 시작할 때 프로젝트 60일 · 기록 30일 청소 함수(db/020_service_baseline.sql)와 관리자 처리 이력(admin_audit) 1년 삭제를 작은 묶음으로 부른다(`_purge_expired`, 스케줄러 없음).
오류 코드(ADR 0019, backend/errors.py): 하루 토큰 · USD 상한과 실행 한 번의 호출 · 예약 상한은 429 `LIMIT_EXCEEDED`, 호출 간격은 429 `RATE_LIMITED`,
조건 질문 대기는 409 `CONDITION_PENDING`, 분석 실패는 LLM · 임베딩 공급자 장애면 502 `UPSTREAM_ERROR`, 시간 예산 초과는 504, 그 밖은 503이다.
키 없는 데모(`DEMO_REPLAY=1` · `DEMO_MODE=1`, SPEC 7절): 같은 그래프를 돌리고 LLM 응답만 기록에서 꺼낸다(`backend/services/demo.py`).
기록한 회로 · 대상 · 질문 · 사용 조건을 새 대화의 첫 질문으로만 받고(아니면 422), 재개는 기록한 답 · 역할만 받는다(아니면 422).
기록 파일이 없으면 503, 확인을 통과했는데 기록에 없는 호출(ReplayMiss)도 503으로 이유를 보인다.
"""
import argparse
import re
import os
import math
import time
import logging
from decimal import Decimal
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from functools import lru_cache
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
from psycopg_pool import ConnectionPool, PoolTimeout

from backend.conversations import profile
from backend.conversations.repository import pinned_version
from backend.errors import ApiError
from backend.graph.memory import namespace, memory_policy

LOGGER = logging.getLogger('backend.conversations')
RETENTION_LOGGER = logging.getLogger('backend.conversations.retention')

# 하루 LLM 토큰 상한(11-09 결정, UTC 날짜). 공급자 청구 토큰이 아니라 호출 전에 잡는 예약 토큰의 합이다
# [왜] 11-12: 사용자별 5M이 실사용 한도. 서비스 10M은 다계정 합산 안전선(이전 1M/2M은 스모크·점검에 서비스 전체부터 먼저 찼다)
# [왜] 11-17: 운영에서 팀 점검 · 시연 준비만으로 서비스 10M이 16시에 다 차 분석이 모두 429가 됐다. 값은 코드가 아니라 환경변수로 올릴 수 있게 한다
#      (없으면 전과 같은 5M · 10M). 사용자별 하루 USD 상한(ANALYSIS_DAILY_USD)과 공급자 키 한도는 그대로 남는다
USER_DAILY_TOKENS = int(os.getenv('ANALYSIS_USER_DAILY_TOKENS') or 5_000_000)
SERVICE_DAILY_TOKENS = int(os.getenv('ANALYSIS_SERVICE_DAILY_TOKENS') or 10_000_000)
TOKEN_MARGIN = 8192  # [주의] llm.EvaluationBudget._reserve가 입력 바이트에 더하는 여유와 같아야 한다(시험이 USD 예약과 맞춰 본다)
USER_TOKENS_FULL = f'오늘 쓸 수 있는 분석 사용량(하루 {USER_DAILY_TOKENS:,} 토큰)을 다 썼습니다. 한국 시각 오전 9시(UTC 0시) 뒤에 다시 시도하세요.'
SERVICE_TOKENS_FULL = f'오늘 서비스 전체 분석 사용량(하루 {SERVICE_DAILY_TOKENS:,} 토큰)이 다 찼습니다. 한국 시각 오전 9시(UTC 0시) 뒤에 다시 시도하세요.'
TOO_LONG = '답변 시간이 너무 길어져 멈췄어요. 질문을 나눠 다시 시도해 주세요.'  # 분석 한 번의 시간 · 호출 · 예약 상한(504 · 429, #29 문구 11-16)

MAX_CONVERSATION_HISTORY_CHARS = 20_000
# 이번 run의 노드 진행 알림(message · resume의 progress). `_invoke`가 읽어 노드 시간 callback에 붙인다.
# [왜] `_invoke` 인자로 넘기지 않는다. 시험 · 평가 실행기(evals/runners/run_injection_baseline.py)가 `_invoke`를 지금 인자 그대로 바꿔 끼운다
_progress = ContextVar('analysis_progress', default=None)


@contextmanager
def _reporting(progress):
    """with 안에서 부르는 `_invoke`가 노드가 시작할 때마다 progress(노드 이름)를 부르게 한다."""
    token = _progress.set(progress)
    try:
        yield
    finally:
        _progress.reset(token)


def _conversation_history(contents, *, max_chars=MAX_CONVERSATION_HISTORY_CHARS):
    """이전 사용자 입력을 질문과 분리해, 온전한 항목 단위로 최근 문맥만 만든다.

    질문 개수로 자르지 않고 문자 상한만 적용한다. 답변·승인 기록은 호출자가
    넘기지 않으므로 이 함수의 입력은 messages의 user content만 허용한다.
    """
    selected = []
    size = 0
    for content in reversed(contents):
        content = str(content)
        extra = len(content) + (1 if selected else 0)
        if selected and size + extra > max_chars:
            break
        if not selected and len(content) > max_chars:
            selected.append(content[-max_chars:])
            break
        selected.append(content)
        size += extra
    return list(reversed(selected))


def _topic(ref):
    """ref에 은/는을 붙인다. 끝 글자를 한국어로 읽은 받침으로 고른다(숫자는 영·일·이·삼…, 영문은 엘·엠·엔·알만 받침). frontend/src/circuit.ts와 같은 규칙."""
    last = ref[-1:].upper()
    final = (ord(last) - 0xAC00) % 28 > 0 if '가' <= last <= '힣' else last in '013678LMNR'
    return ref + ('은' if final else '는')


def _require_supported_target(connections, target):
    part = next((p for p in connections.get('components', connections.get('parts', [])) if p['ref'] == target), None)
    if part is None:
        raise HTTPException(422, '회로에 없는 대상 부품입니다.')
    identifiers = ' '.join(part.get(key) or '' for key in ('value', 'footprint'))
    description = (part.get('description') or '').strip()
    led_description = re.search(r'light[\s-]*emitting[\s-]*diode|발광\s*다이오드|^(?:(?:red|green|blue|white|yellow|amber|orange|rgb)\s+)?leds?$', description, re.I)
    if re.search(r'(^|[^a-z0-9])leds?(?=$|[^a-z])', identifiers, re.I) or led_description or re.match(r'LED\d', target, re.I):
        raise HTTPException(422, f'{_topic(target)} LED라서 아직 교체 검토를 지원하지 않아요. 다이오드를 골라 주세요.')
    if re.search(r'(^|[^a-z0-9])(?:7|seven)[\s_-]*seg(?:ment)?', identifiers, re.I):
        raise HTTPException(422, f'{_topic(target)} 표시기라서 아직 교체 검토를 지원하지 않아요. 다이오드를 골라 주세요.')
    if not re.match(r'D\d', target, re.I):
        raise HTTPException(422, f'{_topic(target)} 다이오드가 아니라서 아직 교체 검토를 지원하지 않아요. 다이오드를 골라 주세요.')


def _named(text, ref):
    """글에 회로 기호 ref가 따로 적힌 자리(없으면 None).
    [주의] \\b는 한글도 글자로 봐 'D1을'에서 D1을 못 찾는다. 앞뒤가 영문 · 숫자가 아닐 때만 그 부품으로 본다(D10 · D1N4148 안의 D1은 아님)"""
    return re.search(rf'(?<![A-Za-z0-9]){re.escape(ref)}(?![A-Za-z0-9])', text or '', re.I)


def target_choices(connections, question=''):
    """대상 부품 후보 [{ref, value}]: 질문에 적힌 지원 다이오드가 있으면 앞에 적힌 하나, 없으면 회로의 지원 다이오드 전부(SPEC 8.9).

    지원 여부는 `_require_supported_target`와 같은 규칙이다. 하나면 그 부품으로 진행하고, 둘 이상이면 그래프가 계획을 본 뒤 필요할 때만 묻는다. LLM은 고르지 않는다.
    질문에 회로의 부품 ref가 있는데 모두 지원 대상이 아니면 그 부품의 422를 낸다. 회로 전체로 넘어가는 것은 질문에 회로 ref가 없을 때뿐이다.
    """
    parts = connections.get('components', connections.get('parts', []))
    diodes = []
    for part in parts:
        try:
            _require_supported_target(connections, part['ref'])
        except HTTPException:
            continue
        diodes.append({'ref': part['ref'], 'value': part.get('value') or ''})
    named = [p['ref'] for p in parts if _named(question, p['ref'])]
    chosen = [d for d in diodes if d['ref'] in named]
    if named and not chosen:
        # [왜] 질문이 회로의 다른 부품(LED · 표시기 · 다이오드 아님)을 가리키면 유일한 다이오드로 몰래 바꾸지 않는다.
        #      그 부품을 target_ref로 보낸 것과 같은 422 · 같은 문구로 막는다(SPEC 8.9)
        _require_supported_target(connections, named[0])
    # [왜] 대상은 대화마다 하나다. 둘 이상 적었으면('D1 D2 둘 다') 앞에 적힌 것을 보고, 나머지는 답 끝에 새 대화에서 물어 달라고 적는다(other_targets_note, #62)
    return sorted(chosen, key=lambda d: _named(question, d['ref']).start())[:1] or diodes


DIODE_REF = re.compile(r'(?<![A-Za-z0-9])D\d+(?![A-Za-z0-9])', re.I)  # 다이오드 기호 모양(D9). D1N4148 · SS34 안은 아님


def absent_diode_reply(connections, question):
    """질문이 회로에 없는 다이오드 기호(D9)만 적었으면 그 사실과 회로의 지원 다이오드를 알리는 답(코드 글, #62). 아니면 빈 글자."""
    parts = connections.get('components', connections.get('parts', []))
    asked = DIODE_REF.findall(question or '')
    if not asked or any(_named(question, p['ref']) for p in parts):
        return ''
    found = ', '.join(d['ref'] + (f"({d['value']})" if d['value'] else '') for d in target_choices(connections))
    return f'이 회로에 {_topic(asked[0].upper())} 없어요. 넷리스트에서 다이오드 {found}를 찾았어요.'


def other_targets_note(connections, question, target):
    """질문에 적었지만 이 대화의 대상이 아닌 지원 다이오드를 알리는 답 끝 한 줄(#62). 없으면 빈 글자.
    [왜] 대상은 대화마다 고정이라(target_locked) 같은 대화에서 다시 물어도 그 부품을 보지 않는다. 새 대화로 안내한다"""
    others = [d['ref'] for d in target_choices(connections) if d['ref'] != target and _named(question, d['ref'])]
    return f"\n\n이 대화는 {target}만 검토해요. {_topic(', '.join(others))} 새 대화에서 따로 물어봐 주세요." if target and others else ''


@lru_cache(maxsize=1)
def _token_budget_class():
    """EvaluationBudget을 이어받아 호출마다 예약 토큰 수를 `reserving_tokens`에 두는 클래스."""
    # [왜] llm은 import 때 .env를 읽는다. 준비 CLI가 .env의 원격 DB를 집지 않게 처음 예산을 만들 때 import한다
    from backend.services.llm import EvaluationBudget

    class TokenBudget(EvaluationBudget):
        def _reserve(self, text, *, output_tokens, embedding=False, model=None):
            # [왜] reserve()가 잠금을 잡은 채 부르므로 이 값은 같은 호출의 on_reserve(DB 차감)만 읽는다
            self.reserving_tokens = len(text.encode('utf-8')) + TOKEN_MARGIN + output_tokens
            return super()._reserve(text, output_tokens=output_tokens, embedding=embedding, model=model)

    return TokenBudget


def delete_analysis_threads(conn, user, ids=None):
    """사용자의 분석 thread(ids가 없으면 전부)와 딸린 checkpoint · 메시지 · 분석 사건을 conn의 트랜잭션에서 지운다.

    프로젝트 삭제(ids = 그 프로젝트의 React 대화 UUID)와 탈퇴(ids 없음)가 쓴다. 지운 건수를 돌려주고, 분석 서비스 표가 없는 DB면 모두 0이다. `analysis_circuits`는 응답 모양을 지키려는 상수 0이다(회로 사본 표가 없다, P2).
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
    # 메시지 · 분석 사건은 thread FK cascade로 함께 지워진다. 화면 대화(public.threads)를 지우면 DB가 분석 thread와 checkpoint도 지우므로(db/020_service_baseline.sql) 이 호출은 건수를 세고 먼저 지우는 용도다
    counts['analysis_threads'] = cur.execute(sql.SQL('DELETE FROM sojafit_agent.threads WHERE id IN ({})').format(sql.SQL(owned)), params).rowcount
    return counts


def _vector_schema(conn):
    """설치된 pgvector 확장의 스키마 이름(로컬 Compose는 public, Supabase는 extensions). 없으면 None."""
    row = conn.execute("SELECT n.nspname AS name FROM pg_extension e JOIN pg_namespace n ON n.oid=e.extnamespace WHERE e.extname='vector'").fetchone()
    return row['name'] if row else None


def initialize(dsn):
    """분석 DB의 LangGraph 표(Checkpointer · Store)를 만든다. sojafit_agent 서비스 표는 이미 있어야 한다. 기존 코퍼스·인증 행은 변경하지 않는다."""
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row, connect_timeout=5) as conn:
        # [주의] SQL 파일(013~017 · 022 · 023 · 028)은 적용하지 않는다. 다시 적용하면 028이 지운 회로 사본 · 승인 표가 되살아난다. 표는 initdb(db/*.sql) 몫이고 여기서는 LangGraph 표만 만든다
        vector = _vector_schema(conn)
        # [왜] 의미 색인 표(store_vectors)의 vector 형은 확장이 설치된 스키마에 있다. sojafit_agent만 보면 형을 못 찾는다.
        #      표는 search_path 첫 스키마(sojafit_agent)에 만들어진다
        conn.execute(sql.SQL('SET search_path TO sojafit_agent{}').format(sql.SQL(', {}').format(sql.Identifier(vector)) if vector else sql.SQL('')))
        PostgresSaver(conn).setup()
        # [주의] vector 확장이 없으면(CI의 postgres:16) 색인 표 없이 준비한다. 확장 설치는 여기서 하지 않는다(db/000_init.sql · Supabase 몫)
        PostgresStore(conn, index=profile.INDEX if vector else None).setup()


def has_pending_question(snapshot) -> bool:
    """사용자의 조건 답을 기다리는 인터럽트가 실제로 남았는가.

    [왜] 예외(502 · 503 · 504)로 멈춘 실행의 체크포인트에는 실패한 노드가 next로 남는다. next만 보면 그 대화가 영원히 조건 대기(409)로 막혔다.
         같은 대화에 새 질문을 넣으면 남은 노드는 다시 돌지 않고 새 입력이 이어받는다(점검 B #2, InMemorySaver 실측).
    """
    return bool(snapshot.next and any(task.interrupts for task in getattr(snapshot, 'tasks', ())))


class Conversations:
    def __init__(self, dsn, factory=None):
        from backend.services import demo
        self.mode = 'demo' if demo.enabled() else 'live'
        self.dsn = make_conninfo(dsn, options='-c search_path=sojafit_agent')
        self.stack = ExitStack()
        try:
            with self.connection() as conn:
                if not all(conn.execute("SELECT to_regclass(%s) AS name", (name,)).fetchone()['name']
                           for name in ('threads', 'checkpoints', 'store', 'analysis_usage', 'analysis_service_usage')):
                    raise RuntimeError('분석 DB 준비 명령을 먼저 실행하세요.')
                # [왜] 청소 함수가 없으면 보관 기간 규칙이 조용히 꺼진다. 표와 같이 시작 때 확인한다(db/020_service_baseline.sql)
                if not all(conn.execute('SELECT to_regprocedure(%s) AS name', (name,)).fetchone()['name']
                           for name in ('purge_inactive_projects(integer,integer)', 'purge_log_records(integer,integer)')):
                    raise RuntimeError('보관 기간 청소 함수가 없습니다. 서비스 표 기준선(db/020_service_baseline.sql)을 먼저 적용하세요.')
                if not conn.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='sojafit_agent' AND table_name='threads' AND column_name='input_record'").fetchone():
                    raise RuntimeError('thread 입력 기록 칸이 없습니다. 서비스 표 기준선(db/020_service_baseline.sql)을 먼저 적용하세요.')
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
            self.mcp = None  # [왜] 그래프를 만들 때 _graph가 채운다. warm()이 이 검색기로 품번 색인도 미리 만든다(factory로 만든 시험 그래프는 없음)
            self.graph = factory(self.saver, self.store) if factory else self._graph()
        except Exception:
            self.stack.close()
            raise

    def connection(self):
        return psycopg.connect(self.dsn, autocommit=True, row_factory=dict_row, connect_timeout=5)

    def close(self):
        self.stack.close()

    def warm(self):
        """서버 시작 뒤 데몬 스레드에서 부른다: 검색 BM25 색인과 MCP 하위 프로세스의 품번 색인을 미리 만들어 첫 질문의 콜드 스타트(7~23초)를 없앤다(점검 C #1).

        [주의] 실패해도 서버는 그대로 뜬다. 오류는 종류만 로그에 남기고(질의 · 접속 정보 제외) 첫 질문이 원래대로 색인을 만든다.
        """
        try:
            from backend.rag.retrieve import warmup
            warmup()
            if self.mcp is not None:
                self.mcp.check([], [])
        except Exception as error:
            LOGGER.warning('warmup_failed error=%s', type(error).__name__)

    def readiness(self):
        """모델 호출·사용자 행 읽기 없이 현재 분석 저장소의 연결과 스키마를 확인한다."""
        with self.connection() as conn:
            conn.execute('SELECT t.input_record,u.reserved_tokens,s.reserved_tokens FROM threads t, messages m, '
                         'analysis_usage u, analysis_events e, analysis_service_usage s LIMIT 0')
            conn.execute('SELECT 1 FROM checkpoints, checkpoint_blobs, checkpoint_writes, store LIMIT 0')

    @staticmethod
    def _budget_settings():
        budget = _token_budget_class()(max_calls=int(os.getenv('ANALYSIS_MAX_CALLS', '16')),
            max_usd=float(os.getenv('ANALYSIS_MAX_USD', '0.50')), max_seconds=float(os.getenv('ANALYSIS_MAX_SECONDS', '90')),
            max_tokens=int(os.getenv('ANALYSIS_MAX_TOKENS', '4096')),
            prompt_rate=float(os.getenv('ANALYSIS_PROMPT_RATE', '0.000003')),
            completion_rate=float(os.getenv('ANALYSIS_COMPLETION_RATE', '0.000015')),
            # [왜] 판정 읽기 여러 번이 Sonnet 이상 단가로 예약돼 분석 한 번의 상한을 넘었다(11-10). 호출 모델 단가로 예약하고, 표에 없는 모델만 위 단가를 쓴다
            per_model_rates=True)
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
        # [왜] 하루 상한은 잠시 뒤 다시 보내도 다시 걸린다. 화면이 다음 날까지 기다리게 RATE_LIMITED와 코드를 나눈다(ADR 0019)
        if (used['mine'] or 0) + TOKEN_MARGIN > USER_DAILY_TOKENS:
            raise ApiError(429, USER_TOKENS_FULL, code='LIMIT_EXCEEDED')
        if (used['service'] or 0) + TOKEN_MARGIN > SERVICE_DAILY_TOKENS:
            raise ApiError(429, SERVICE_TOKENS_FULL, code='LIMIT_EXCEEDED')

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
            # [왜] 위 문장은 호출 간격 · 하루 USD 중 무엇에 걸렸는지 돌려주지 않는다. 걸렸을 때만 USD를 한 번 더 읽어 코드를 가른다(ADR 0019)
            if not row and conn.execute("SELECT reserved_usd >= %s AS spent FROM analysis_usage WHERE user_id=%s AND day=(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')::date",
                                        (Decimal(str(daily)), user)).fetchone()['spent']:
                raise ApiError(429, '하루 분석 예약 예산에 도달했습니다.', code='LIMIT_EXCEEDED')
        if not row:
            raise HTTPException(429, '분석 호출 간격이 너무 짧습니다. 잠시 후 다시 시도하세요.', headers={'Retry-After': str(max(1, math.ceil(interval)))})
        def charge(cost):
            """호출 한 번의 예약 USD · 토큰을 사용자 행과 서비스 행에 한 트랜잭션으로 더한다. 하나라도 넘으면 모두 되돌리고 429."""
            tokens, cost = budget.reserving_tokens, Decimal(str(cost))
            def apply(conn):
                # [왜] 사용자 행 → 서비스 행 순서로만 잠가 동시 호출끼리 교착하지 않는다. 예외가 나면 트랜잭션이 둘 다 되돌린다
                usage = conn.execute('SELECT reserved_usd,reserved_tokens FROM analysis_usage WHERE user_id=%s AND day=%s FOR UPDATE',
                                     (user, row['day'])).fetchone()
                if usage['reserved_tokens'] + tokens > USER_DAILY_TOKENS:
                    raise ApiError(429, USER_TOKENS_FULL, code='LIMIT_EXCEEDED')
                if usage['reserved_usd'] + cost > Decimal(str(daily)):
                    raise ApiError(429, '하루 분석 예약 예산에 도달했습니다.', code='LIMIT_EXCEEDED')
                conn.execute('INSERT INTO analysis_service_usage(day) VALUES (%s) ON CONFLICT DO NOTHING', (row['day'],))
                if not conn.execute('UPDATE analysis_service_usage SET reserved_tokens=reserved_tokens+%s WHERE day=%s AND reserved_tokens+%s<=%s RETURNING day',
                                    (tokens, row['day'], tokens, SERVICE_DAILY_TOKENS)).fetchone():
                    raise ApiError(429, SERVICE_TOKENS_FULL, code='LIMIT_EXCEEDED')
                conn.execute('UPDATE analysis_usage SET reserved_usd=reserved_usd+%s,reserved_tokens=reserved_tokens+%s WHERE user_id=%s AND day=%s',
                             (cost, tokens, user, row['day']))
            # [왜] 호출마다 새 접속(TLS+인증)을 열면 예약 잠금 안에서 동시 호출이 줄을 섰다. 풀 연결을 빌린다(풀도 autocommit · dict_row · prepare_threshold=0이라 같은 의미)
            # [주의] 풀이 짧은 시간 안에 연결을 못 주면 예전처럼 새 접속으로 한다. 풀 때문에 예전에 되던 예약이 실패하면 안 된다
            try:
                with self.pool.connection(timeout=0.5) as conn, conn.transaction():
                    apply(conn)
            except PoolTimeout:
                with self.connection() as conn, conn.transaction():
                    apply(conn)
        budget.on_reserve = charge
        return budget

    def schematic_dialogue_budget(self, user):
        """회로도 소개도 기존 사용자·서비스 일일 예약을 공유한다."""
        budget = self._budget(user)
        budget.max_calls = min(budget.max_calls, 3)
        budget.max_usd = min(budget.max_usd, .10)
        budget.max_seconds = min(budget.max_seconds, 45)
        budget.max_tokens = min(budget.max_tokens, 2048)
        budget.validate()
        return budget

    def _graph(self):
        from functools import update_wrapper
        from backend.graph.mcp_retriever import StdioMcpRetriever
        from backend.multi_agent.build import build_graph
        from backend.multi_agent.facts import make_lookup, with_prefetch
        from backend.rag.card_find import default_find
        from backend.rag.card_specs import default_specs
        from backend.rag.retrieve import retrieve
        from backend.services import demo, exa, llm
        from backend.services.langfuse_prompts import timed_tool
        # [왜] 키 없는 데모는 실제 그래프를 그대로 돌리고 LLM 응답만 기록에서 꺼낸다(조장 결정 11-10). 카드 도구의 카드 읽기 LLM도
        #      같은 chat을 받아야 프롬프트가 기록(scripts/demo/record_demo.py의 build_app)과 같아진다
        chat = demo.service_chat() if self.mode == 'demo' else llm.node_chat
        mcp = self.mcp = self.stack.enter_context(StdioMcpRetriever())  # 사실 확인(check_corpus)만 MCP로 부른다
        # [왜] 사양 표(part_specifications)를 11-09에 버리고 후보 찾기 · 판정 값은 카드 읽기가 기본이다(ADR 0016, 평가 실행기 run_graph.py와 같은 조립)
        # [주의] 카드 도구는 MCP를 거치지 않고 DATABASE_URL로 DB를 직접 읽는다. 표지 품번 색인은 조립 때가 아니라 첫 판정 때 한 번 읽는다
        specs, find = default_specs(chat=chat), default_find(chat=chat)
        # [주의] timed_tool은 함수만 감싸 prefetch · doc_rows · also_read 속성을 잃는다. Spec 에이전트가 getattr로 찾으므로 update_wrapper로 옮긴다
        # [왜] 데모는 Store를 넘기지 않는다. 기록은 Store 없이 돌았고, 사용자가 저장한 선호 실장 방식이 찾기 후보 순서를 바꾸면 기록과 다른 답이 된다
        web_enabled = self.mode != 'demo' and exa.enabled()
        return build_graph(chat=chat, retriever=timed_tool('search',retrieve), web_enabled=web_enabled,
            web_search=timed_tool('grade2_datasheet', exa.search_grade2_evidence) if web_enabled else None,
            web_search_fallback=timed_tool('grade3_reference', exa.search_grade3_reference) if web_enabled else None,
            judge_web_search_fallback=timed_tool('grade3_reference_judge', exa.search_grade3_reference) if web_enabled else None,
            judge_enabled=True,
            lookup=with_prefetch(make_lookup(mcp.check, specs.doc_rows), exa.prefetch) if web_enabled else make_lookup(mcp.check, specs.doc_rows),
            specs=update_wrapper(timed_tool('specs',specs), specs),
            find=update_wrapper(timed_tool('find',find), find), checkpointer=self.saver, store=None if self.mode == 'demo' else self.store)

    @staticmethod
    def config(thread):
        return {'configurable': {'thread_id': str(thread)}, 'recursion_limit': 50}

    @staticmethod
    def _owned(conn, user, thread):
        # [왜] 회로 이름 · 연결 정보는 화면 쪽 정본(public)에서 읽는다. 이 연결의 search_path는 sojafit_agent뿐이라 public을 이름으로 부른다
        row = conn.execute('SELECT t.*,p.name AS filename,c.connections FROM threads t JOIN public.threads pt ON pt.id=t.id '
                           f"JOIN public.projects p ON p.id=pt.project_id JOIN public.project_circuit_versions c ON c.project_id=p.id AND c.version={pinned_version('pt', 'public.project_circuit_versions')} "
                           'WHERE t.id=%s AND t.user_id=%s AND p.user_id=%s', (thread, user, user)).fetchone()
        if not row:
            raise HTTPException(404, '분석을 찾을 수 없습니다.')
        # [왜] 저장된 업로드는 {parts, nets}, 그래프 · 데모 확인은 {components, nets}를 읽는다.
        c = row['connections']
        row['connections'] = {'components': c.get('components', c.get('parts', [])), 'nets': c.get('nets', [])}
        return row

    @contextmanager
    def locked(self, user, thread):
        with self.connection() as conn:
            self._owned(conn, user, thread)  # 소유자가 아니면 404
            self._hold_account(conn, user)  # [왜] 실행이 끝날 때까지 탈퇴가 끼어들어 지운 기록을 다시 만들지 않게 한다
            if not conn.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS ok', (str(thread),)).fetchone()['ok']:
                raise HTTPException(409, '분석을 처리 중입니다. 잠시 후 다시 시도하세요.')
            try:
                yield conn, self._owned(conn, user, thread)
            finally:
                conn.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))', (str(thread),))

    def ensure_thread(self, user, thread, filename, connections, target, question=None, conditions=''):
        """React 대화(public.threads) 하나를 같은 UUID의 분석 thread로 처음 한 번 만든다. 대상 부품이 바뀌면 409.

        [주의] 입력 회로 대신 소유 대화의 고정 버전을 읽는다. filename · connections 인자는 기존 호출 호환용이다.
        target이 None이면 이미 만든 분석 thread의 대상을 쓰고, 없으면 `target_choices`로 정한다(SPEC 8.9).
        후보가 둘 이상이면 대상 없이(빈 글자) 만든다. 고를 부품은 그래프의 '대상 확인'이 계획을 본 뒤 필요할 때만 묻는다(#62).
        질문이 회로에 없는 다이오드 기호(D9)만 적었으면 분석 thread를 만들지 않고 그 사실을 알리는 답 글을 돌려준다(호출자가 그대로 답한다). 그 밖에는 None.

        키 없는 데모면 기록한 회로 · 대상(question을 주면 질문 · 사용 조건까지)인지 먼저 본다(아니면 422, 기록이 없으면 503)."""
        with self.connection() as conn:
            self._hold_account(conn, user)
            pinned = conn.execute('SELECT c.connections FROM public.threads pt JOIN public.projects p ON p.id=pt.project_id '
                                  f"JOIN public.project_circuit_versions c ON c.project_id=p.id AND c.version={pinned_version('pt', 'public.project_circuit_versions')} "
                                  'WHERE pt.id=%s AND p.user_id=%s', (thread, user)).fetchone()
            # [왜] 대상은 첫 run에 고정된다(target_locked). 이후 질문에 부품을 적지 않아도 다시 묻지 않는다
            locked = conn.execute('SELECT target FROM threads WHERE id=%s AND user_id=%s', (thread, user)).fetchone() if target is None else None
        if pinned is None:
            raise HTTPException(404, '분석을 찾을 수 없습니다.')
        connections = pinned['connections']
        # React 정규화 회로는 parts, 데모 회로는 components다.
        connections = {'components': connections.get('components', connections.get('parts', [])), 'nets': connections.get('nets', [])}
        empty = unresolved = not connections['components']
        if target is None:
            if locked and locked['target']:
                choices = [{'ref': locked['target'], 'value': ''}]
            elif empty:
                # [왜] 회로 없이 시작한 대화는 대상 없이(빈 글자) 분석한다. 회로가 필요한 질문은 그래프 계획 뒤 넷리스트를 달라고 끝난다(SPEC 8.9).
                #      빈 대상은 회로를 붙인 뒤 처음 정한 부품으로 바뀐다(아래 UPDATE)
                choices = [{'ref': '', 'value': ''}]
            else:
                choices = target_choices(connections, question)
            if not choices:
                raise HTTPException(422, '회로에 판정할 수 있는 다이오드가 없습니다. 다이오드가 있는 넷리스트를 첨부해 주세요.')
            if not empty and (reply := absent_diode_reply(connections, question)):
                return reply
            # [왜] 지원 다이오드가 여럿이면 묻지 않고 대상 없이(빈 글자) 분석한다. 일상 대화 · 부품 목록 · 품번 정격은 대상이 필요 없다(#62)
            unresolved = empty or len(choices) > 1
            target = '' if unresolved else choices[0]['ref']
        if target or not unresolved:
            _require_supported_target(connections, target)
        if self.mode == 'demo':
            from backend.services import demo
            # [왜] run 스트림을 열기 전에 거른다(공통 오류 JSON). 기록이 없으면 503, 기록한 회로 · 대상 · 질문이 아니면 422
            if not demo.match(connections, target):
                raise demo.refusal('이 회로 · 대상 부품에는 기록한 데모 질문이 없습니다.')
            if question is not None and not demo.match(connections, target, question, conditions):
                raise demo.refusal('기록한 데모 질문과 질문 · 사용 조건이 다릅니다.')
        with self.connection() as conn:
            self._hold_account(conn, user)  # 탈퇴 중이면 409(지운 분석 기록을 다시 만들지 않게)
            # [왜] 같은 UUID의 대화는 생성 당시의 project_circuit_versions를 계속 읽는다.
            # [주의] 화면 대화가 없거나 남의 것이면 _owned가 404다(INSERT ... SELECT가 0행). FK 위반으로 500이 되지 않는다
            conn.execute('INSERT INTO threads(id,user_id,target) SELECT pt.id,p.user_id,%s FROM public.threads pt JOIN public.projects p ON p.id=pt.project_id '
                         'WHERE pt.id=%s AND p.user_id=%s ON CONFLICT (id) DO NOTHING', (target, thread, user))
            if target:
                conn.execute("UPDATE threads SET target=%s WHERE id=%s AND user_id=%s AND target=''", (target, thread, user))
            row = self._owned(conn, user, thread)
        if row['target'] != target:
            raise HTTPException(409, '대상 부품을 바꾸려면 새 대화를 시작하세요.')

    def threads(self, user):
        with self.connection() as conn:
            rows = conn.execute('SELECT t.id,t.target,t.status,t.version,p.name AS filename FROM threads t JOIN public.threads pt ON pt.id=t.id '
                                'JOIN public.projects p ON p.id=pt.project_id WHERE t.user_id=%s AND p.user_id=%s ORDER BY t.created_at DESC LIMIT 100', (user, user)).fetchall()
        return [{**r, 'id': str(r['id'])} for r in rows]

    def detail(self, user, thread, hints=()):
        """thread 상태 · 결과. 승인 · 기억 칸은 응답 모양을 지키려 빈 값으로 둔다(P2). hints는 이번 질문으로 찾은 사용자 사실(message · resume만 넘기고 GET은 빈 목록)."""
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
            events = conn.execute('SELECT version,request_id,mode,status,elapsed_ms,stages,trace_id,trace_delivery FROM analysis_events WHERE thread_id=%s ORDER BY created_at DESC LIMIT 20', (thread,)).fetchall()
        snapshot = self.graph.get_state(self.config(thread))
        state = snapshot.values or {}
        pending = [i.value for task in snapshot.tasks for i in task.interrupts]
        return {'id': str(row['id']), 'mode': self.mode, 'filename': row['filename'], 'target': row['target'], 'version': row['version'],
                'status': row['status'], 'messages': messages, 'answer': '' if pending or (row.get('input_record') or {}).get('execution_limit_reached') else state.get('answer', ''),
                'interrupt': pending[0] if pending else None, 'can_approve': False,
                'can_retry': bool(snapshot.next and not pending and row['retries'] < 2 and state.get('run_version') == row['version']),
                'related_memories': [], 'approvals': [], 'events': events,
                'profile_hints': list(hints), 'consulted_memories': [], 'referenced_memories': []}

    def _purge_expired(self):
        """보관 기간이 지난 프로젝트(60일) · 기록(30일) · 관리자 처리 이력(1년)을 작은 묶음으로 지운다(db/020_service_baseline.sql). 실패해도 분석은 계속한다."""
        try:
            with self.connection() as conn:
                conn.execute('SELECT purge_inactive_projects(), purge_log_records()')
                # 관리자 처리 이력(admin_audit, db/034)은 1년(처리방침 2절, 11-16 결정). [왜] 청소 함수를 고치면 배포 때 운영 DB 이전이 필요해 앱 SQL 한 줄로 둔다
                conn.execute("DELETE FROM public.admin_audit WHERE id = ANY(ARRAY(SELECT id FROM public.admin_audit "
                             "WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '1 year' LIMIT 200))")
        except psycopg.Error:
            RETENTION_LOGGER.warning('retention_purge_failed')

    def message(self, user, thread, text, conditions='', request_id='', progress=None):
        # [왜] 새 분석이 시작될 때 청소한다(스케줄러 없음). 이 thread를 잠그기 전에 해서, 60일 지난 thread면 반쯤 쓴 상태 없이 404로 끝난다
        self._purge_expired()
        with self.locked(user, thread) as (conn, row):
            if row['target']:  # 회로 없는 대화 · 지원 다이오드가 여럿인 대화는 대상 없이(빈 글자) 돈다(ensure_thread)
                _require_supported_target(row['connections'], row['target'])
            self._reconcile(conn, row)
            if has_pending_question(self.graph.get_state(self.config(thread))):
                # [왜] 화면은 이 코드면 조건 입력 폼을 다시 보여 준다(ADR 0019). 다른 409는 문구만 보여 준다
                raise ApiError(409, '먼저 요청한 조건에 답해주세요.', code='CONDITION_PENDING')
            history = conn.execute("SELECT content FROM messages WHERE thread_id=%s AND role='user' ORDER BY id", (thread,)).fetchall()
            if len(history) >= 50:
                raise HTTPException(409, '분석당 질문 한도(50건)에 도달했습니다.')
            if self.mode == 'demo':
                from backend.rag.card_find import SHARED_READS
                from backend.services import demo
                # [왜] 같은 대화의 두 번째 질문부터는 '이전 사용자 입력'이 프롬프트에 붙어 기록과 달라진다(재생이 멈춤). 첫 질문만 받는다
                if history:
                    raise demo.refusal('데모 질문은 새 대화의 첫 질문으로만 재생합니다. 새 대화에서 보내세요.')
                if not demo.match(row['connections'], row['target'], text, conditions):
                    raise demo.refusal('기록한 데모 질문과 질문 · 사용 조건이 다릅니다.')
                # [왜] 기록은 질문마다 카드 읽기 공유 칸을 비우고 돌았다(record_demo.run_question). 앞 질문이 읽어 둔 카드가 남으면 호출 · 답이 달라진다
                # shortcut: 데모 사용자 둘이 동시에 돌리면 한쪽이 다른 쪽의 공유 칸을 비워 재생이 멈출 수 있다(503). 동시 시연이 필요하면 실행별 칸으로 바꾼다
                SHARED_READS.clear()
            version = row['version'] + 1
            content = (f'사용 조건: {conditions}\n' if conditions else '') + text
            budget = self._budget(user)
            hints = self._profile_hints(user, text)
            with conn.transaction():
                conn.execute("UPDATE threads SET version=%s,status='RUNNING',retries=0,input_record=%s WHERE id=%s",
                             (version, Jsonb({'version': version, 'question': text, 'conditions': conditions, 'resumes': []}), thread))
                conn.execute("INSERT INTO messages(thread_id,role,content) VALUES (%s,'user',%s)", (thread, content))
            # 현재 질문과 이전 사용자 입력을 별도 칸으로 보낸다. 이전 질문을
            # 현재 질문 문자열에 붙이면 회로 역할·조건이 섞이므로, 모델의 현재
            # 입력은 항상 이번 요청만 보게 한다.
            conversation_history = _conversation_history([r['content'] for r in history])
            # [왜] 그래프는 턴마다 판정 칸을 비운다. 직전 판정의 요약만 따로 실어 "그래서 뭐 써?" · "조건이 뭐야?"에 코드가 답하게 한다(11-17).
            #      판정 없는 턴(견적 안내 · 일상 대화)을 지나도 남도록 앞 요약을 이어 쓴다
            from backend.multi_agent.messages import judgement_summary
            before = getattr(self.graph.get_state(self.config(thread)), 'values', None) or {}  # 새 대화는 앞 상태가 없다
            last_judgement = judgement_summary(before.get('judgement') or {}, before.get('target') or '') or before.get('last_judgement') or {}
            inputs = {'input': content, 'conversation_history': conversation_history, 'last_judgement': last_judgement,
                      'connections': row['connections'], 'circuit': row['filename'], 'target': row['target'],
                      'conditions': conditions, 'user_id': str(user), 'run_version': version,
                      # [왜] 대상이 없으면 그래프의 '대상 확인'이 계획을 본 뒤 이 후보에서 묻는다(#62). 매 질문 덮어써 앞 질문의 후보가 남지 않게 한다
                      'target_choices': [] if row['target'] else target_choices(row['connections']),
                      # [왜] 승인 사례는 더 이상 새 분석에 넘기지 않는다. 빈 목록을 넣어 checkpoint에 남은 이전 목록도 지운다
                      'approved_memories': []}
            with _reporting(progress):
                web_unavailable = self._invoke(conn, thread, inputs, budget, request_id)
        return {**self.detail(user, thread, hints), 'web_search_unavailable': web_unavailable}

    def _profile_hints(self, user, question):
        """질문 글로 사용자 사실을 찾아 화면 참고용 칸(kind · value · text)만 돌려준다. 실패해도 분석은 계속한다."""
        try:
            return [{key: fact[key] for key in ('kind', 'value', 'text')} for fact in self.profile.facts(user, question)] if question else []
        except Exception:
            LOGGER.warning('profile_hints_unavailable')
            return []

    def resume(self, user, thread, answers, role, version, request_id='', progress=None, text=''):
        with self.locked(user, thread) as (conn, row):
            if version != row['version']:
                raise HTTPException(409, '새 결과의 조건 질문을 다시 확인하세요.')
            _require_supported_target(row['connections'], row['target'])
            snapshot = self.graph.get_state(self.config(thread))
            if not snapshot.next:
                raise HTTPException(409, '재개할 조건 질문이 없습니다.')
            pending = [i.value for task in snapshot.tasks for i in task.interrupts]
            if not pending or set(answers) - set(pending[0].get('missing') or []):
                raise HTTPException(422, '요청한 조건의 답만 입력하세요.')
            if role and role not in (pending[0].get('role_choices') or []):
                raise HTTPException(422, '제시된 역할을 선택하세요.')
            if self.mode == 'demo':
                from backend.services import demo
                record = row.get('input_record') or {}
                recorded = demo.match(row['connections'], row['target'], record.get('question'), record.get('conditions'))
                want = (recorded[0].get('resume') if recorded else None) or {}
                # [왜] 재개 답도 프롬프트에 들어간다. 기록 때 보낸 답 · 역할과 같아야 재생된다
                if not want or text or (answers, role) != (want['answers'], want['role']):  # 글 답은 기록에 없어 재생하지 못한다
                    shown = ', '.join(f'{k}={v}' for k, v in (want.get('answers') or {}).items()) or '모름'
                    raise HTTPException(422, f"키 없는 데모는 기록한 답(답: {shown}, 역할: {want.get('role') or '없음'})으로만 재개합니다. "
                                             "화면의 '기록한 답으로 계속하기'를 누르세요.")
            budget = self._budget(user)
            content = '조건 답변:\n' + ('\n'.join([*(f'{key}: {value}' for key, value in answers.items()), *([text] if text else [])]) or '모름')
            if role:
                content += f'\n선택한 역할: {role}'
            if 'target_choices' in pending[0]:  # 대상 부품을 물었다(호출자가 고른 부품을 분석 thread에 먼저 고정한다)
                content = f"선택한 부품: {row['target']}"
            record = row.get('input_record') or {'version': version, 'question': None, 'conditions': None, 'resumes': []}
            record.pop('execution_limit_reached',None)
            record['resumes'].append({'answers': answers, 'role': role, **({'text': text} if text else {})})
            with conn.transaction():
                conn.execute('UPDATE threads SET input_record=%s WHERE id=%s', (Jsonb(record), thread))
                conn.execute("INSERT INTO messages(thread_id,role,content) VALUES (%s,'user',%s)", (thread, content))
            hints = self._profile_hints(user, record.get('question'))
            with _reporting(progress):
                web_unavailable = self._invoke(conn, thread, Command(resume={'answers': answers, 'role': role, 'target': row['target'], **({'text': text} if text else {})}), budget, request_id)
        return {**self.detail(user, thread, hints), 'web_search_unavailable': web_unavailable}

    def _invoke(self, conn, thread, inputs, budget, request_id=''):
        """그래프를 한 번 돌리고 결과를 저장한다. 돌려주는 값: 이 실행에서 Exa 웹 검색 호출이 실패했는지(#28, 화면 안내 한 줄)."""
        from backend.services.llm import evaluation_limits, EvaluationLimitError, is_upstream_error
        from backend.services import langfuse_prompts, service_trace
        from backend.services.demo import ReplayMiss
        timings = langfuse_prompts.AnalysisTimings(on_node=_progress.get())  # 노드 시작 알림은 message · resume이 progress를 줬을 때만
        started = time.monotonic()
        # [왜] 모델 호출별 추적을 analysis-metadata와 같은 trace_id로 묶으려고 실행 시작에 trace_id를 정한다(키가 없으면 빈 값)
        trace_id = uuid4().hex
        traces, trace_metadata = service_trace.callbacks(trace_id, thread, self.mode)
        try:
            user = conn.execute('SELECT user_id FROM threads WHERE id=%s', (thread,)).fetchone()['user_id']
            from backend.services.exa import request_scope
            with request_scope() as web, evaluation_limits(budget), memory_policy(lambda items: self._current_memories(user, items)), langfuse_prompts.analysis_timings(timings):
                budget.remaining()
                self.graph.invoke(inputs, {**self.config(thread), 'callbacks': [timings, *traces], 'metadata': trace_metadata})
                budget.remaining()
            saved = time.monotonic()
            self._finish(conn, thread, self.graph.get_state(self.config(thread)))
            timings.stages.append({'stage':'save_result','status':'ok','elapsed_ms':int((time.monotonic()-saved)*1000)})
            return web['web_search_unavailable']
        except Exception as error:
            conn.execute("UPDATE threads SET status='FAILED' WHERE id=%s", (thread,))
            if isinstance(error, EvaluationLimitError) or (isinstance(error,HTTPException) and error.status_code==429):
                conn.execute("UPDATE threads SET input_record=jsonb_set(COALESCE(input_record,'{}'::jsonb),'{execution_limit_reached}','true') WHERE id=%s", (thread,))
            LOGGER.warning('analysis_failed', extra={'request_id': request_id, 'thread_id': str(thread), 'error_type': type(error).__name__,
                                                     'elapsed_ms': int((time.monotonic()-budget.started)*1000)})
            if isinstance(error, HTTPException):
                raise
            if isinstance(error, ReplayMiss):
                # [왜] 확인을 통과한 데모 질문인데 기록에 없는 호출이면 DB · 코드 · 설정이 기록 때와 다르다. 실제 LLM으로 넘기지 않고 이유를 보인다
                raise HTTPException(503, f'데모 기록을 재생하지 못했습니다. {error} 기록 때와 DB · 코드가 다를 수 있습니다'
                                         '(scripts/demo/DEMO.md의 재생 확인).') from error
            late = time.monotonic()-budget.started >= budget.max_seconds
            # [왜] 바깥 호출에는 남은 시간만큼만 제한 시간을 준다(llm.EvaluationBudget). 시간 예산을 다 써 끊긴 바깥 호출도 504다
            if isinstance(error, EvaluationLimitError) or (late and is_upstream_error(error)):
                if late:
                    raise HTTPException(504, TOO_LONG) from None
                # [왜] 실행 한 번의 호출 수 · 예약 USD 상한이다. 같은 요청을 곧바로 되풀이해도 다시 걸려 LIMIT_EXCEEDED로 둔다(ADR 0019 결과)
                raise ApiError(429, TOO_LONG, code='LIMIT_EXCEEDED') from None
            # [왜] LLM · 임베딩 공급자 장애(502)와 우리 DB · 설정 문제(503)를 코드로 가른다(ADR 0019). from error는 로그 traceback에 원인 프레임을 남긴다
            if is_upstream_error(error):
                raise HTTPException(502, '답변을 만들지 못했어요. 잠시 후 다시 시도해 주세요.') from error
            raise HTTPException(503, '분석을 완료하지 못했습니다. 잠시 후 상태를 확인하세요.') from error
        finally:
            self._record_event(conn,thread,started,timings.report(),request_id,trace_id=trace_id)

    def _record_event(self, conn, thread, started, stages, request_id, status=None, version=None, trace_id=None):
        from backend.services import langfuse_prompts
        # 관측 장애가 이미 저장한 checkpoint/답변/승인의 성공 여부를 바꾸지 않는다.
        try:
            row = conn.execute('SELECT user_id,version,status FROM threads WHERE id=%s', (thread,)).fetchone()
            event = {'version': version if version is not None else row['version'], 'request_id': request_id,
                     'mode': self.mode, 'status': status or row['status'], 'elapsed_ms': int((time.monotonic()-started)*1000),
                     'stages': stages, 'trace_id': trace_id or uuid4().hex}
            try:
                delivery = langfuse_prompts.publish_analysis_trace(row['user_id'], thread, event)
            except Exception:
                delivery = 'failed'
            conn.execute('INSERT INTO analysis_events(id,thread_id,version,request_id,mode,status,elapsed_ms,stages,trace_id,trace_delivery) '
                         'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                         (uuid4(),thread,event['version'],request_id,self.mode,event['status'],event['elapsed_ms'],Jsonb(stages),event['trace_id'],delivery))
            LOGGER.info('analysis_finished', extra={'user_id': row['user_id'], 'thread_id': str(thread), **event, 'trace_delivery': delivery})
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



    def _current_memories(self, user, items):
        if not items:
            return []
        # [주의] `self.memories`는 없다. 승인 사례가 비활성이라 items는 늘 비어 위에서 끝난다. 비어 있지 않으면 AttributeError다
        active = {(m['thread_id'],m['version']):m for m in self.memories(user)}
        return [active[(m['thread_id'],m['version'])] for m in items
                if (m['thread_id'],m['version']) in active]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='사용자 분석 저장소 준비(대상 DB를 먼저 확인하세요)')
    parser.add_argument('--setup', action='store_true', required=True)
    parser.parse_args()
    initialize(os.environ['DATABASE_URL'])
    print('분석 저장소 준비 완료')
