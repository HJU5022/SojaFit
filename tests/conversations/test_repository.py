import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from backend import auth


@pytest.fixture
def storage(monkeypatch):
    url = os.getenv('TEST_AUTH_DATABASE_URL')
    if not url:
        pytest.skip('requires isolated PostgreSQL')
    schema = 'conv_' + uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        connect = lambda: psycopg.connect(url, options=f'-csearch_path={schema}')
        monkeypatch.setattr(auth, 'connection', connect)
        try:
            with connect() as conn:
                for name in ('003_auth.sql', '005_auth_attempt_window.sql', '006_user_roles.sql', '013_projects.sql', '014_conversations.sql'):
                    conn.execute(Path('db', name).read_text(encoding='utf-8-sig'))
                users = [r[0] for r in conn.execute("INSERT INTO users(login_id,password_hash,role) VALUES ('owner@test','fake','user'),('other@test','fake','user') RETURNING id")]
                project = conn.execute("INSERT INTO projects(user_id,name,source_kind) VALUES (%s,'test','upload') RETURNING id", (users[0],)).fetchone()[0]
                conn.execute("INSERT INTO circuits(project_id,connections,source_sha256,parser_version) VALUES (%s,'{}',%s,'test')", (project,'a'*64))
            from backend.conversations.repository import ConversationRepository
            yield ConversationRepository(), users, project, connect
        finally:
            admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_ownership_and_atomic_active_run(storage):
    from backend.conversations.repository import ConversationNotFound
    repo, (owner, other), project, connect = storage
    thread = repo.create_thread(owner, project)
    with pytest.raises(ConversationNotFound):
        repo.get_thread(other, thread)
    run, circuit = repo.start(owner, thread, {'question': 'test', 'target': 'D1', 'conditions': ''})
    with pytest.raises(psycopg.errors.UniqueViolation):
        repo.start(owner, thread, {'question': 'again', 'target': 'D1', 'conditions': ''})
    with connect() as conn:
        assert conn.execute('SELECT count(*) FROM messages').fetchone()[0] == 1
        assert conn.execute('SELECT count(*) FROM runs').fetchone()[0] == 1
    repo.finish(owner, thread, run, 'completed', {'answer': 'ok'})
    with connect() as conn:
        conn.execute('DELETE FROM projects WHERE id=%s', (project,))
        assert conn.execute('SELECT count(*) FROM threads').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM runs').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM messages').fetchone()[0] == 0


def test_schema_restrictions_and_indexes(storage):
    _, _, _, connect = storage
    with connect() as conn:
        rows = conn.execute("SELECT relname,relrowsecurity, EXISTS (SELECT 1 FROM aclexplode(coalesce(relacl,acldefault('r',relowner))) a WHERE a.grantee=0) FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relname IN ('threads','messages','runs')").fetchall()
        assert len(rows) == 3 and all(rls and not public for _, rls, public in rows)
        for role in ('anon', 'authenticated'):
            if conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,)).fetchone():
                for table in ('threads', 'messages', 'runs'):
                    assert conn.execute("SELECT has_table_privilege(%s,%s,'SELECT,INSERT,UPDATE,DELETE')", (role, table)).fetchone() == (False,)
        cols = [r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name IN ('threads','messages','runs')")]
        assert not set(cols) & {'price', 'stock', 'product_url', 'fetched_at'}
        indexes = [r[0] for r in conn.execute("SELECT indexdef FROM pg_indexes WHERE schemaname=current_schema()")]
        assert any('UNIQUE INDEX' in i and 'requires_input' in i for i in indexes)


def test_library_postgres_checkpoint_setup(storage):
    from langgraph.checkpoint.postgres import PostgresSaver
    _, _, _, connect = storage
    with connect() as conn:
        conn.autocommit = True
        saver = PostgresSaver(conn)
        saver.setup()
        assert conn.execute("SELECT to_regclass('checkpoints')").fetchone()[0] is not None


def test_safe_result_rejects_extra_fields_and_cross_owner_operations(storage):
    from pydantic import ValidationError
    from backend.conversations.repository import ConversationNotFound
    repo, (owner, other), project, connect = storage
    thread = repo.create_thread(owner, project)
    with pytest.raises(ConversationNotFound):
        repo.create_thread(other, project)
    with pytest.raises(ConversationNotFound):
        repo.start(other, thread, {'question': 'bad'})
    run, _ = repo.start(owner, thread, {'question': 'hello'})
    with pytest.raises(ConversationNotFound):
        repo.finish(other, thread, run, 'completed', {'answer': 'bad'})
    with pytest.raises(ValidationError):
        repo.finish(owner, thread, run, 'completed', {'answer': 'ok', 'product_url': 'x'})
    with connect() as conn:
        assert conn.execute('SELECT status,safe_result FROM runs WHERE id=%s', (run,)).fetchone() == ('running', None)


def test_message_run_thread_integrity(storage):
    repo, (owner, _), project, connect = storage
    one, two = repo.create_thread(owner, project), repo.create_thread(owner, project)
    run, _ = repo.start(owner, one, {'question': 'hello'})
    with pytest.raises(psycopg.errors.ForeignKeyViolation), connect() as conn:
        conn.execute("INSERT INTO messages(thread_id,run_id,role,content) VALUES (%s,%s,'user','x')", (two,run))


def test_checkpoint_setup_and_d5_execution_on_isolated_postgres(storage):
    import asyncio
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from backend.multi_agent.contracts import Plan
    from backend.multi_agent.supervisor import Facts
    from backend.services.d5 import D5Service, RunInput, setup_checkpoints
    _, _, _, connect = storage
    with connect() as conn:
        from psycopg.conninfo import make_conninfo
        dsn = make_conninfo(os.environ['TEST_AUTH_DATABASE_URL'], options=conn.info.options)
    async def run():
        await setup_checkpoints(dsn)
        async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
            service = D5Service(chat=lambda *a: Plan(question_type='chat', next='finish', reply='안녕하세요'),
                                retriever=lambda *a, **k: [], lookup=lambda _: Facts(),
                                specs=lambda *a, **k: [], find=lambda *a, **k: [], checkpointer=saver)
            data = RunInput(question='안녕', target_ref='', connections={'parts': [], 'nets': []})
            events = [e async for e in service.start('stable-postgres-thread', data)]
            assert events[-1].type == 'completed' and events[-1].state['answer'] == '안녕하세요'
        with connect() as conn:
            assert conn.execute('SELECT count(*) FROM checkpoints').fetchone()[0] > 0
            names = ('checkpoints', 'checkpoint_blobs', 'checkpoint_writes', 'checkpoint_migrations')
            for name in names:
                assert conn.execute("SELECT relrowsecurity FROM pg_class WHERE oid=%s::regclass", (name,)).fetchone() == (True,)
                assert not conn.execute("SELECT EXISTS (SELECT 1 FROM pg_class c, LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) a WHERE c.oid=%s::regclass AND a.grantee=0)", (name,)).fetchone()[0]
    import sys
    if sys.platform == 'win32':
        asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    else:
        asyncio.run(run())



def test_resume_is_owner_scoped_and_single_claim(storage):
    from backend.conversations.repository import ConversationNotFound, InvalidRunState
    repo, (owner, other), project, _ = storage
    thread = repo.create_thread(owner, project)
    run, _ = repo.start(owner, thread, {'question': 'hello'})
    repo.finish(owner, thread, run, 'requires_input')
    with pytest.raises(ConversationNotFound):
        repo.resume(other, thread, run)
    repo.resume(owner, thread, run)
    with pytest.raises(InvalidRunState):
        repo.resume(owner, thread, run)


def test_database_rejects_unsafe_result_shape(storage):
    from psycopg.types.json import Jsonb
    repo, (owner, _), project, connect = storage
    thread = repo.create_thread(owner, project)
    run, _ = repo.start(owner, thread, {'question': 'hello'})
    for result in ({}, {'answer': 3}, {'answer': 'ok', 'product_url': 'x'}):
        with pytest.raises(psycopg.errors.CheckViolation), connect() as conn:
            conn.execute('UPDATE runs SET safe_result=%s WHERE id=%s', (Jsonb(result), run))


def test_terminal_run_cannot_be_finished_twice(storage):
    from backend.conversations.repository import InvalidRunState
    repo, (owner, _), project, connect = storage
    thread = repo.create_thread(owner, project)
    run, _ = repo.start(owner, thread, {'question': 'hello'})
    repo.finish(owner, thread, run, 'completed', {'answer': 'ok'})
    with pytest.raises(InvalidRunState):
        repo.finish(owner, thread, run, 'completed', {'answer': 'duplicate'})
    with connect() as conn:
        assert conn.execute('SELECT count(*) FROM messages').fetchone()[0] == 2


def test_service_deletes_checkpoint_data(storage):
    import asyncio
    import sys
    from psycopg.conninfo import make_conninfo
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from backend.multi_agent.contracts import Plan
    from backend.multi_agent.supervisor import Facts
    from backend.services.d5 import D5Service, RunInput, setup_checkpoints
    repo, (owner, _), project, connect = storage
    thread = repo.create_thread(owner, project)
    with connect() as conn:
        dsn = make_conninfo(os.environ['TEST_AUTH_DATABASE_URL'], options=conn.info.options)
    async def run():
        await setup_checkpoints(dsn)
        async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
            service = D5Service(chat=lambda *a: Plan(question_type='chat', next='finish', reply='hi'), retriever=lambda *a, **k: [], lookup=lambda _: Facts(), specs=lambda *a, **k: [], find=lambda *a, **k: [], checkpointer=saver)
            data = RunInput(question='hi', target_ref='', connections={'parts': [], 'nets': []})
            assert [e async for e in service.start(thread, data)][-1].type == 'completed'
            with connect() as conn:
                assert conn.execute('SELECT count(*) FROM checkpoints WHERE thread_id=%s', (thread,)).fetchone()[0] > 0
            await service.delete_thread(thread)
        with connect() as conn:
            for table in ('checkpoints', 'checkpoint_blobs', 'checkpoint_writes'):
                assert conn.execute(sql.SQL('SELECT count(*) FROM {} WHERE thread_id=%s').format(sql.Identifier(table)), (thread,)).fetchone()[0] == 0
    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop) if sys.platform == 'win32' else asyncio.run(run())


def test_delete_rejects_active_then_removes_owned_checkpoints(storage):
    from contextlib import asynccontextmanager
    from backend.api.projects import delete_owned_with_checkpoints
    from backend.conversations.repository import InvalidRunState
    repo, (owner, other), project, connect = storage
    thread = repo.create_thread(owner, project)
    run, _ = repo.start(owner, thread, {'question': 'hi'})
    deleted = []
    @asynccontextmanager
    async def service():
        class Fake:
            async def delete_thread(self, thread_id): deleted.append(thread_id)
        yield Fake()
    with pytest.raises(InvalidRunState):
        delete_owned_with_checkpoints(owner, project, service)
    assert deleted == []
    repo.finish(owner, thread, run, 'requires_input', {'answer': '', 'interrupt': {'missing': ['voltage']}})
    with pytest.raises(InvalidRunState):
        delete_owned_with_checkpoints(owner, project, service)
    repo.resume(owner, thread, run)
    repo.finish(owner, thread, run, 'completed', {'answer': 'ok'})
    delete_owned_with_checkpoints(owner, project, service)
    assert deleted == [thread]
    with connect() as conn:
        assert conn.execute('SELECT count(*) FROM projects WHERE id=%s', (project,)).fetchone()[0] == 0


def test_resume_result_survives_repository_reconstruction(storage):
    repo, (owner, _), project, _ = storage
    thread = repo.create_thread(owner, project)
    run, _ = repo.start(owner, thread, {'question': 'hi'})
    repo.finish(owner, thread, run, 'requires_input', {'answer': '', 'interrupt': {'missing': ['voltage'], 'question': 'value?'}})
    from backend.conversations.repository import ConversationRepository
    saved = ConversationRepository().get_run(owner, run)
    assert saved['status'] == 'requires_input'
    assert saved['safe_result']['interrupt']['missing'] == ['voltage']


def test_project_deletion_serializes_new_run(storage):
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from contextlib import asynccontextmanager
    from backend.api.projects import delete_owned_with_checkpoints
    from backend.conversations.repository import ConversationNotFound
    repo, (owner, _), project, _ = storage
    thread = repo.create_thread(owner, project)
    entered, release = threading.Event(), threading.Event()
    @asynccontextmanager
    async def service():
        class Fake:
            async def delete_thread(self, thread_id):
                entered.set()
                assert release.wait(5)
        yield Fake()
    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion = pool.submit(delete_owned_with_checkpoints, owner, project, service)
        try:
            assert entered.wait(5)
            start = pool.submit(repo.start, owner, thread, {'question': 'hi'})
            assert not start.done()
        finally:
            release.set()
        deletion.result(timeout=5)
        with pytest.raises(ConversationNotFound):
            start.result(timeout=5)


def test_database_rejects_nested_private_fields_and_bad_types(storage):
    from psycopg.types.json import Jsonb
    from backend.conversations.models import SafeResult
    repo, (owner, _), project, connect = storage
    thread = repo.create_thread(owner, project)
    run, _ = repo.start(owner, thread, {'question': 'hi'})
    safe = SafeResult.model_validate({'answer': 'ok', 'judgement': {'kind': 'judge', 'results': [{'part': '1N5817', 'verdict': 'NOT_VERIFIED', 'checks': [{'code': 'VRRM', 'citation': {'document': 'a.pdf'}}]}]}}).model_dump(mode='json')
    import copy
    bad = copy.deepcopy(safe)
    bad['judgement']['results'][0]['checks'][0]['citation']['text'] = 'secret'
    bad2 = copy.deepcopy(safe)
    bad2['judgement']['results'][0]['checks'][0]['citation']['page'] = {'path': '/private'}
    bad3 = copy.deepcopy(safe)
    bad3['price_parts'] = ['https://example.test/secret']
    for value in (bad, bad2, bad3):
        with pytest.raises(psycopg.errors.CheckViolation), connect() as conn:
            conn.execute('UPDATE runs SET safe_result=%s WHERE id=%s', (Jsonb(value), run))


def test_docs_evidence_is_persisted_without_raw_chunk(storage):
    from backend.services.d5 import public_state
    from backend.conversations.dto import result_dto
    repo, (owner, _), project, _ = storage
    thread = repo.create_thread(owner, project)
    run, _ = repo.start(owner, thread, {'question': 'hi'})
    state = public_state({'answer': 'ok [3]', 'final_reports': [{'evidence_ids': ['3']}], 'docs': [{'chunk_id': 3, 'file': 'a.pdf', 'page': 2, 'table': None, 'content': 'RAW_CHUNK_MARKER', 'doc_parts': ['RAW_CHUNK_MARKER']}]})
    repo.finish(owner, thread, run, 'completed', state)
    saved = repo.get_run(owner, run)['safe_result']
    assert saved['evidence'][0]['document'] == 'a.pdf'
    assert result_dto(saved, status='completed', request_id='r').evidence[0]['citation_number'] == '3'
    assert 'RAW_CHUNK_MARKER' not in str(saved)
