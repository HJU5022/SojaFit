import os
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from backend import auth
from tests.db_schema import apply_service_schema


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
                apply_service_schema(conn)  # [왜] SQL 파일 이름은 tests/db_schema.py 한 곳에만 둔다
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


def test_project_delete_needs_no_public_checkpoint_tables(storage):
    from backend.api.projects import delete_owned_with_checkpoints
    repo, (owner, _), project, connect = storage
    thread = repo.create_thread(owner, project)
    run, _ = repo.start(owner, thread, {'question': 'hi'})
    repo.finish(owner, thread, run, 'completed', {'answer': 'ok'})
    with connect() as conn:
        assert conn.execute("SELECT to_regclass('checkpoints')").fetchone()[0] is None
    delete_owned_with_checkpoints(owner, project)
    with connect() as conn:
        for table in ('projects', 'threads', 'runs', 'messages'):
            assert conn.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0] == 0


def test_delete_rejects_active_then_removes_owned_checkpoints(storage):
    from backend.api.projects import delete_owned_with_checkpoints
    from backend.conversations.repository import InvalidRunState
    repo, (owner, other), project, connect = storage
    thread = repo.create_thread(owner, project)
    run, _ = repo.start(owner, thread, {'question': 'hi'})
    deleted = []
    def delete_checkpoints(_conn, thread_ids): deleted.extend(thread_ids)
    with pytest.raises(InvalidRunState):
        delete_owned_with_checkpoints(owner, project, delete_checkpoints)
    assert deleted == []
    repo.finish(owner, thread, run, 'requires_input', {'answer': '', 'interrupt': {'missing': ['voltage']}})
    with pytest.raises(InvalidRunState):
        delete_owned_with_checkpoints(owner, project, delete_checkpoints)
    repo.resume(owner, thread, run)
    repo.finish(owner, thread, run, 'completed', {'answer': 'ok'})
    delete_owned_with_checkpoints(owner, project, delete_checkpoints)
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
    from backend.api.projects import delete_owned_with_checkpoints
    from backend.conversations.repository import ConversationNotFound
    repo, (owner, _), project, _ = storage
    thread = repo.create_thread(owner, project)
    entered, release = threading.Event(), threading.Event()
    def delete_checkpoints(_conn, _thread_ids):
        entered.set()
        assert release.wait(5)
    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion = pool.submit(delete_owned_with_checkpoints, owner, project, delete_checkpoints)
        try:
            assert entered.wait(5)
            start = pool.submit(repo.start, owner, thread, {'question': 'hi'})
            assert not start.done()
        finally:
            release.set()
        deletion.result(timeout=5)
        with pytest.raises(ConversationNotFound):
            start.result(timeout=5)


def test_project_and_checkpoint_cleanup_share_one_rollback(storage):
    from backend.api.projects import delete_owned_with_checkpoints
    repo, (owner, _), project, connect = storage
    repo.create_thread(owner, project)

    def partial_then_fail(conn, _thread_ids):
        conn.execute("UPDATE projects SET name='partial' WHERE id=%s", (project,))
        raise RuntimeError('checkpoint cleanup failed')

    with pytest.raises(RuntimeError):
        delete_owned_with_checkpoints(owner, project, partial_then_fail)
    with connect() as conn:
        assert conn.execute('SELECT name FROM projects WHERE id=%s', (project,)).fetchone() == ('test',)


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
    from backend.conversations.dto import public_state
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
