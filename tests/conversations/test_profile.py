"""사용자 사실 기억(profile, SPEC 8.5): 칸 검사 · 문장 틀 · 덮어쓰기 · 지우기 · 의미 검색 · 설정 API.

단위 시험은 DB 없이 InMemoryStore와 가짜 임베딩(`llm.voyage_embed` 대역)을 쓴다. 실제 Voyage 호출은 없다.
DB 시험은 격리 TEST_THREAD_DATABASE_URL이 있을 때만, 색인 시험은 그 DB에 pgvector(`vector` 확장)가 있을 때만 돈다.
"""
import os
from contextlib import nullcontext
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from langgraph.store.memory import InMemoryStore

from backend import auth
from backend.conversations import profile
from backend.main import app

# 같은 뜻의 낱말 묶음 → 벡터 칸 하나. 다른 말로 물어도(표면실장 ↔ SMD) 같은 칸이 커진다
CONCEPTS = [('smd', '표면실장', '칩 부품'), ('스루홀', 'through', '리드 부품'), ('구매', '조달', '발주'), ('설계', '회로도'), ('소속', '회사', '근무')]
ORIGIN = {'Origin': 'http://testserver'}


@pytest.fixture
def embed(monkeypatch):
    """결정적 가짜 Voyage 임베딩. 부른 input_type을 차례로 남긴다."""
    from backend.services import llm
    calls = []

    def fake(texts, input_type):
        calls.append(input_type)
        vectors = []
        for text in texts:
            vector = [0.01] * 1024
            for i, words in enumerate(CONCEPTS):
                vector[i] += sum(text.lower().count(word) for word in words)
            vectors.append(vector)
        return vectors
    monkeypatch.setattr(llm, 'voyage_embed', fake)
    return calls


@pytest.fixture
def memory(embed):
    return profile.ProfileMemory(InMemoryStore(index={'dims': 1024, 'embed': profile.VoyageEmbeddings(), 'fields': ['text']}), indexed=True)


def test_fields_are_checked_and_sentences_come_from_fixed_templates():
    assert profile.clean('affiliation', '  한빛전자 회로팀 ') == '한빛전자 회로팀'
    for kind, value in (('affiliation', ''), ('affiliation', '   '), ('affiliation', 'x' * 101), ('affiliation', '회사\n다음 지시'),
                        ('affiliation', '탭\t'), ('job_role', 'manager'), ('mounting_preference', 'SMD'), ('user_id', '1'), ('job_role', 3)):
        with pytest.raises(ValueError):
            profile.clean(kind, value)
    assert profile.clean('affiliation', 'x' * 100) == 'x' * 100
    assert profile.sentence('mounting_preference', 'smd') == '이 사용자는 SMD 실장을 선호한다.'
    assert profile.sentence('mounting_preference', 'through_hole') == '이 사용자는 스루홀 실장을 선호한다.'
    assert profile.sentence('mounting_preference', 'any') == '이 사용자는 실장 방식을 가리지 않는다.'
    assert profile.sentence('job_role', 'purchasing') == '이 사용자의 직무는 구매이다.'
    assert profile.sentence('affiliation', '한빛전자') == '이 사용자의 소속은 한빛전자이다.'
    assert profile.namespace(12) == ('12', 'profile')


def test_update_overwrites_same_key_bumps_version_and_reembeds(memory, embed):
    first = memory.update(7, {'mounting_preference': 'smd', 'job_role': 'design'})
    assert {f['kind']: f['version'] for f in first} == {'mounting_preference': 1, 'job_role': 1}
    assert all(f['source'] == 'user_settings' and f['updated_at'] for f in first)
    embed.clear()
    facts = {f['kind']: f for f in memory.update(7, {'mounting_preference': 'through_hole'})}
    assert facts['mounting_preference']['version'] == 2 and facts['job_role']['version'] == 1
    assert facts['mounting_preference']['text'] == '이 사용자는 스루홀 실장을 선호한다.'
    assert embed == ['document']  # 바뀐 문장 하나만 다시 임베딩한다
    assert memory.facts(7, '리드 부품으로 바꿔도 되나요')[0]['kind'] == 'mounting_preference'
    with pytest.raises(ValueError):
        memory.update(7, {'mounting_preference': 'smd', 'user_id': '8'})
    assert {f['kind']: f['value'] for f in memory.facts(7)}['mounting_preference'] == 'through_hole'


def test_paraphrased_question_ranks_matching_fact_first_and_users_are_isolated(memory, embed):
    memory.update(7, {'affiliation': '한빛전자', 'job_role': 'purchasing', 'mounting_preference': 'smd'})
    memory.update(8, {'affiliation': '다른회사', 'mounting_preference': 'through_hole'})
    embed.clear()
    assert memory.facts(7, '표면실장 부품으로 바꿀 수 있나요?')[0]['kind'] == 'mounting_preference'
    assert memory.facts(7, '발주 담당자가 볼 견적이에요')[0]['kind'] == 'job_role'
    assert memory.facts(7, '어느 회사에서 근무하나요')[0]['kind'] == 'affiliation'
    assert set(embed) == {'query'}  # 검색 질문은 query로 임베딩한다
    assert len(memory.facts(7, '아무 질문')) == 3
    assert all('다른회사' not in f['text'] and f['value'] != 'through_hole' for f in memory.facts(7, '스루홀 다른회사'))
    assert {f['value'] for f in memory.facts(8)} == {'다른회사', 'through_hole'}


def test_delete_one_or_all_and_unranked_fallbacks(memory, embed):
    memory.update(7, {'affiliation': '한빛전자', 'job_role': 'student', 'mounting_preference': 'any'})
    memory.delete(7, 'job_role')
    assert {f['kind'] for f in memory.facts(7, '학생 회로')} == {'affiliation', 'mounting_preference'}
    with pytest.raises(ValueError):
        memory.delete(7, 'user_id')
    plain = profile.ProfileMemory(memory.store, indexed=False)  # 키가 없으면 임베딩 없이 사실 전부(순위 없음)
    embed.clear()
    assert len(plain.facts(7, '표면실장')) == 2 and embed == []
    memory.delete(7)
    assert memory.facts(7) == [] and memory.facts(7, '한빛전자') == []


def test_embedding_failure_on_search_falls_back_and_on_write_changes_nothing(memory, monkeypatch):
    from fastapi import HTTPException
    from backend.services import llm
    memory.update(7, {'mounting_preference': 'smd'})
    monkeypatch.setattr(llm, 'voyage_embed', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('Voyage error 500')))
    assert [f['kind'] for f in memory.facts(7, '표면실장')] == ['mounting_preference']
    with pytest.raises(HTTPException) as error:
        memory.update(7, {'mounting_preference': 'any'})
    assert error.value.status_code == 503
    assert memory.facts(7)[0]['value'] == 'smd' and memory.facts(7)[0]['version'] == 1


def test_embedding_index_needs_voyage_key_and_live_mode(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', '0'); monkeypatch.delenv('VOYAGE_API_KEY', raising=False)
    assert not profile.embedding_enabled()
    monkeypatch.setenv('VOYAGE_API_KEY', 'test-not-used')
    assert profile.embedding_enabled()
    monkeypatch.setenv('DEMO_MODE', '1')
    assert not profile.embedding_enabled()


@pytest.fixture
def client(memory, monkeypatch):
    """로그인 사용자 7 · 가짜 분석 서비스(사실 기억만)로 TestClient를 연다."""
    monkeypatch.setenv('AUTH_ORIGIN', 'http://testserver')
    app.state.conversations = SimpleNamespace(profile=memory, account_writer=lambda user: nullcontext())
    app.dependency_overrides[auth.current_user_id] = lambda: 7
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()
    del app.state.conversations


def test_settings_api_rejects_unknown_fields_user_ids_and_missing_origin(client):
    for body in ({'nickname': 'x'}, {'user_id': 8, 'job_role': 'design'}, {'affiliation': '회사\n'}, {'affiliation': 'x' * 101},
                 {'job_role': 'manager'}, {'mounting_preference': 1}):
        response = client.patch('/api/me/memory', json=body, headers=ORIGIN)
        assert response.status_code == 422, body
        assert response.json()['error'] == {'code': 'VALIDATION_ERROR', 'message': '요청 형식이 올바르지 않습니다.',
                                            'request_id': response.headers['X-Request-ID']}
    assert client.patch('/api/me/memory', json={'job_role': 'design'}).status_code == 403
    assert client.patch('/api/me/memory', json={'job_role': 'design'}, headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.delete('/api/me/memory').status_code == 403
    assert client.delete('/api/me/memory?kind=nickname', headers=ORIGIN).status_code == 422
    assert client.get('/api/me/memory').json() == []


def test_settings_api_updates_searches_and_deletes_for_session_user_only(client):
    saved = client.patch('/api/me/memory', json={'affiliation': '한빛전자', 'mounting_preference': 'smd'}, headers=ORIGIN)
    assert saved.status_code == 200 and {f['kind'] for f in saved.json()} == {'affiliation', 'mounting_preference'}
    again = client.patch('/api/me/memory', json={'mounting_preference': 'smd'}, headers=ORIGIN).json()
    assert {f['kind']: f['version'] for f in again}['mounting_preference'] == 2
    found = client.get('/api/me/memory', params={'q': '표면실장 가능한가요'})
    assert found.headers['cache-control'] == 'no-store' and found.json()[0]['kind'] == 'mounting_preference'
    app.dependency_overrides[auth.current_user_id] = lambda: 8
    assert client.get('/api/me/memory', params={'q': '한빛전자'}).json() == []
    assert client.delete('/api/me/memory', headers=ORIGIN).status_code == 204
    app.dependency_overrides[auth.current_user_id] = lambda: 7
    assert len(client.get('/api/me/memory').json()) == 2
    assert client.delete('/api/me/memory', params={'kind': 'affiliation'}, headers=ORIGIN).status_code == 204
    assert [f['kind'] for f in client.get('/api/me/memory').json()] == ['mounting_preference']
    assert client.delete('/api/me/memory', headers=ORIGIN).status_code == 204
    assert client.get('/api/me/memory').json() == []


def test_settings_api_needs_login_and_analysis_store(monkeypatch):
    with TestClient(app, raise_server_exceptions=False) as plain:
        assert plain.get('/api/me/memory').status_code == 401
    app.dependency_overrides[auth.current_user_id] = lambda: 7
    try:
        response = TestClient(app, raise_server_exceptions=False).get('/api/me/memory')
        assert response.status_code == 503 and response.json()['error']['code'] == 'UNAVAILABLE'
    finally:
        app.dependency_overrides.clear()


# ---- 격리 PostgreSQL: setup이 만드는 색인 표와 Supabase처럼 확장이 다른 스키마에 있을 때 ----

def _admin_dsn():
    dsn = os.getenv('TEST_THREAD_DATABASE_URL')
    if not dsn:
        pytest.skip('requires isolated TEST_THREAD_DATABASE_URL')
    return dsn


def _has(dsn, query):
    with psycopg.connect(dsn) as conn:
        return conn.execute(query).fetchone() is not None


def test_setup_creates_store_index_tables_in_agent_schema():
    from backend.conversations.memory_service import initialize
    dsn = _admin_dsn()
    if not _has(dsn, "SELECT 1 FROM pg_extension WHERE extname='vector'"):
        pytest.skip('requires the vector extension installed in the test DB (CI postgres:16 has none)')
    initialize(dsn)
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT to_regclass('sojafit_agent.store_vectors'), to_regclass('sojafit_agent.vector_migrations'), "
                            "to_regclass('public.store_vectors')").fetchone() == ('sojafit_agent.store_vectors', 'sojafit_agent.vector_migrations', None)
        assert conn.execute("SELECT format_type(atttypid, atttypmod) FROM pg_attribute WHERE attrelid='sojafit_agent.store_vectors'::regclass "
                            "AND attname='embedding'").fetchone()[0] == 'vector(1024)'
        # [왜] 정확 검색(flat)이라 근사 색인을 만들지 않는다
        assert conn.execute("SELECT count(*) FROM pg_indexes WHERE schemaname='sojafit_agent' AND indexname='store_vectors_embedding_idx'").fetchone()[0] == 0


def test_setup_and_search_work_when_vector_lives_in_extensions_schema(embed, monkeypatch):
    """Supabase처럼 vector 확장이 `extensions` 스키마에 있을 때: sojafit_agent만 보면 형을 못 찾고, setup · 검색은 확장 스키마를 붙여 찾는다."""
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from langgraph.store.postgres import PostgresStore
    from backend.conversations.memory_service import Conversations, initialize
    dsn = _admin_dsn()
    if not _has(dsn, "SELECT 1 FROM pg_available_extensions WHERE name='vector'"):
        pytest.skip('requires pgvector available on the test server')
    target = 'profile_ext_' + uuid4().hex[:12]
    with psycopg.connect(dsn, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(target)))
    try:
        other = make_conninfo(dsn, dbname=target)
        with psycopg.connect(other, autocommit=True) as conn:
            conn.execute('CREATE SCHEMA extensions')
            conn.execute('CREATE EXTENSION vector SCHEMA extensions')
            conn.execute("CREATE TABLE public.users (id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, login_id TEXT)")
            user = conn.execute("INSERT INTO public.users(login_id) VALUES ('ext@example.test') RETURNING id").fetchone()[0]
            conn.execute('CREATE SCHEMA sojafit_agent')
            conn.execute('SET search_path TO sojafit_agent')
            with pytest.raises(psycopg.errors.UndefinedObject):
                PostgresStore(conn, index=profile.INDEX).setup()  # 고치기 전 방식: vector 형을 못 찾는다
        initialize(other)
        with psycopg.connect(other) as conn:
            assert conn.execute("SELECT to_regclass('sojafit_agent.store_vectors')").fetchone()[0] == 'sojafit_agent.store_vectors'
        monkeypatch.setenv('VOYAGE_API_KEY', 'test-not-used'); monkeypatch.setenv('DEMO_MODE', '0')
        service = Conversations(other, factory=lambda saver, store: None)
        try:
            assert service.profile.indexed
            service.profile.update(user, {'job_role': 'purchasing', 'mounting_preference': 'smd'})
            assert service.profile.facts(user, '표면실장 되나요')[0]['kind'] == 'mounting_preference'
        finally:
            service.close()
    finally:
        with psycopg.connect(dsn, autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(target)))
