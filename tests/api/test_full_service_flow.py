"""격리 PostgreSQL에서 업로드→run 재개→승인→가격 없는 견적→소유권→cascade를 잇는다."""
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from backend import auth
from tests.db_schema import apply_service_schema


@pytest.fixture
def full_storage(monkeypatch):
    url = os.getenv('TEST_AUTH_DATABASE_URL')
    if not url:
        pytest.skip('requires isolated PostgreSQL')
    schema = 'full_service_' + uuid4().hex
    with psycopg.connect(url, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        connect = lambda: psycopg.connect(url, options=f'-csearch_path={schema}')
        monkeypatch.setattr(auth, 'connection', connect)
        try:
            with connect() as conn:
                apply_service_schema(conn)
                users = [row[0] for row in conn.execute("INSERT INTO users(login_id,password_hash,role) VALUES ('flow-owner@test','fake','user'),('flow-other@test','fake','user') RETURNING id")]
            yield users, connect
        finally:
            admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_full_owned_flow_and_price_free_cascade(full_storage):
    from backend.conversations.repository import ConversationNotFound, ConversationRepository
    from backend.projects.netlist import PARSER_VERSION, normalize_netlist
    from backend.projects.repository import ProjectRepository
    from backend.services.quote import InvalidApproval, QuoteNotFound, QuoteService
    owner, other = full_storage[0]
    connect = full_storage[1]
    projects, conversations, quotes = ProjectRepository(), ConversationRepository(), QuoteService()

    normalized = normalize_netlist(Path('tests/fixtures/netlists/minimal.net').read_bytes())
    project = projects.create_upload(owner, '전체 흐름', connections=normalized.connections,
                                     source_sha256=normalized.source_sha256, parser_version=PARSER_VERSION)
    target = normalized.parts[0]
    thread = conversations.create_thread(owner, project.id)
    run, _ = conversations.start(owner, thread, {'question': f'{target} 대체?', 'target_ref': target})
    conversations.finish(owner, thread, run, 'requires_input', {'answer': '', 'interrupt': {'missing': ['v_in'], 'question': 'value?'}})
    conversations.resume(owner, thread, run)
    conversations.finish(owner, thread, run, 'completed', {
        'answer': 'SS34는 역할상 충분합니다.', 'question_type': 'candidate_judge',
        'evidence': [{'document': 'SS34.pdf', 'page': 2, 'table': 'RATINGS', 'row': 'VRRM', 'citation_number': '7'}],
        'judgement': {'kind': 'judge', 'roles': ['R01'], 'results': [{'part': 'SS34', 'verdict': 'ROLE_SUFFICIENT'}, {'part': 'SS33', 'verdict': 'ROLE_SUFFICIENT'}]},
    })
    saved = conversations.get_run(owner, run)
    assert quotes.list_approvals(owner, saved['message_id']) == []
    with connect() as conn:
        user_message = conn.execute("SELECT id FROM messages WHERE run_id=%s AND role='user'", (run,)).fetchone()[0]
    for user, message in ((other, saved['message_id']), (owner, saved['message_id'] + 100000), (owner, user_message)):
        with pytest.raises(QuoteNotFound): quotes.list_approvals(user, message)
    approval = quotes.approve(owner, saved['message_id'], 'SS34', 'ROLE_SUFFICIENT')
    assert quotes.list_approvals(owner, saved['message_id']) == [{**approval, 'quotes': []}]
    assert set(quotes.list_approvals(owner, saved['message_id'])[0]) == {'id', 'message_id', 'candidate_part', 'part_number', 'verdict', 'case_id', 'created_at', 'quotes'}
    # [왜] 활성 사례가 남은 같은 메시지를 다시 승인하면 거절한다(API는 409 ALREADY_APPROVED, #139)
    with pytest.raises(InvalidApproval): quotes.approve(owner, saved['message_id'], 'SS34', 'ROLE_SUFFICIENT')
    assert len(quotes.list_cases(owner)) == 1
    quote = quotes.create_quote(owner, approval['id'], 25)
    assert quote['part_number'] == 'SS34' and quote['quantity'] == 25
    assert quotes.list_quotes(owner, project.id)[0]['id'] == quote['id']
    assert quotes.list_cases(owner)[0]['candidate_part'] == 'SS34'

    with pytest.raises(ConversationNotFound): conversations.get_run(other, run)
    with pytest.raises(QuoteNotFound): quotes.approve(other, saved['message_id'], 'SS34', 'ROLE_SUFFICIENT')
    with pytest.raises(QuoteNotFound): quotes.list_quotes(other, project.id)
    with pytest.raises(psycopg.errors.CheckViolation), connect() as conn:
        conn.execute("UPDATE approvals SET snapshot=snapshot || %s WHERE id=%s", (Jsonb({'product_url': 'https://forbidden.test'}), approval['id']))
    with connect() as conn:
        stored = ''.join(row[0] for row in conn.execute('SELECT snapshot::text FROM approvals'))
        # [왜] 스냅샷은 approvals 한 곳뿐이다: 견적 · 승인 사례에는 snapshot 칸이 없고, 승인 칸 3개가 스냅샷과 같은 값을 가진다
        assert conn.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema=current_schema() AND column_name='snapshot' "
                            "AND table_name IN ('quotes','approved_cases')").fetchone()[0] == 0
        assert conn.execute('SELECT candidate_part,verdict,part_number FROM approvals WHERE id=%s', (approval['id'],)).fetchone() == ('SS34', 'ROLE_SUFFICIENT', 'SS34')
    assert not any(key in stored for key in ('price', 'stock', 'availability', 'product_url', 'fetched_at'))
    # [주의] 승인당 견적은 DB가 하나로 막지 않는다(quotes에 approval_id UNIQUE 없음): 같은 승인으로 두 번째 견적도 저장된다
    assert quotes.create_quote(owner, approval['id'], 1)['id'] != quote['id']
    assert len(quotes.list_quotes(owner, project.id)) == 2

    quotes.delete_case(owner, approval['case_id'])
    assert quotes.list_cases(owner) == []
    assert quotes.list_approvals(owner, saved['message_id']) == []
    with pytest.raises(QuoteNotFound): quotes.create_quote(owner, approval['id'], 1)
    assert len(quotes.list_quotes(owner, project.id)) == 2
    replacement = quotes.approve(owner, saved['message_id'], 'SS33', 'ROLE_SUFFICIENT')
    assert replacement['id'] != approval['id']
    assert quotes.list_approvals(owner, saved['message_id']) == [{**replacement, 'quotes': []}]  # 지운 승인의 견적은 새 승인에 붙지 않는다
    assert quotes.create_quote(owner, replacement['id'], 3)['part_number'] == 'SS33'
    with connect() as conn:
        assert conn.execute('SELECT candidate_part,snapshot FROM approvals WHERE id=%s', (approval['id'],)).fetchone()[0] == 'SS34'
    quotes.delete_case(owner, replacement['case_id'])
    from concurrent.futures import ThreadPoolExecutor
    def try_approve(part):
        try:
            return quotes.approve(owner, saved['message_id'], part, 'ROLE_SUFFICIENT')
        except InvalidApproval:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        competing = list(pool.map(try_approve, ['SS33', 'SS34']))
    assert sum(item is not None for item in competing) == 1
    active = quotes.list_approvals(owner, saved['message_id'])
    assert len(active) == 1
    quotes.delete_case(owner, active[0]['case_id'])
    assert quotes.approve(owner, saved['message_id'], active[0]['candidate_part'], 'ROLE_SUFFICIENT')['id'] != active[0]['id']
    projects.delete_owned(owner, project.id)
    with connect() as conn:
        counts = {name: conn.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(name))).fetchone()[0]
                  for name in ('projects', 'circuits', 'threads', 'runs', 'messages', 'approvals', 'quotes', 'approved_cases')}
    assert not any(counts.values())


def test_approval_reselection_migration_is_idempotent_and_keeps_rows(full_storage):
    with full_storage[1]() as conn:
        conn.execute('DROP INDEX ix_approvals_message')
        conn.execute('ALTER TABLE approvals ADD CONSTRAINT approvals_message_id_key UNIQUE(message_id)')
        migration = Path('db/032_approval_reselection.sql').read_text(encoding='utf-8')
        conn.execute(migration)
        conn.execute(migration)
        assert conn.execute("SELECT count(*) FROM pg_constraint WHERE conrelid='approvals'::regclass AND conname='approvals_message_id_key'").fetchone()[0] == 0
        assert conn.execute("SELECT to_regclass(current_schema() || '.ix_approvals_message')").fetchone()[0]


def test_http_case_deletion_unlocks_new_candidate_and_preserves_quote_history(full_storage):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.projects.repository import ProjectRepository
    from backend.conversations.repository import ConversationRepository
    owner, other = full_storage[0]
    project = ProjectRepository().create_demo(owner, 'breadboard_supply', '승인 재선택')
    repository = ConversationRepository()
    thread = repository.create_thread(owner, project.id)
    run, _ = repository.start(owner, thread, {'question': '후보 승인'})
    repository.finish(owner, thread, run, 'completed', {'answer': '검토 결과', 'judgement': {'kind': 'judge', 'results': [
        {'part': 'SS34', 'verdict': 'ROLE_SUFFICIENT'}, {'part': 'SS33', 'verdict': 'ROLE_SUFFICIENT'}]}})
    message = repository.get_run(owner, run)['message_id']
    app.dependency_overrides[auth.current_user_id] = lambda: owner
    app.dependency_overrides[auth.check_origin] = lambda: None
    try:
        web = TestClient(app, raise_server_exceptions=False)
        first = web.post(f'/api/messages/{message}/approvals', json={'candidate_part': 'SS34', 'verdict': 'ROLE_SUFFICIENT'})
        assert first.status_code == 201
        approval = first.json()
        quote = web.post(f"/api/approvals/{approval['id']}/quotes", json={'quantity': 2})
        assert quote.status_code == 201
        app.dependency_overrides[auth.current_user_id] = lambda: other
        assert web.delete(f"/api/approved-cases/{approval['case_id']}").status_code == 404
        app.dependency_overrides[auth.current_user_id] = lambda: owner
        assert web.delete(f"/api/approved-cases/{approval['case_id']}").status_code == 204
        assert web.get(f'/api/messages/{message}/approvals').json() == []
        assert web.post(f"/api/approvals/{approval['id']}/quotes", json={'quantity': 1}).status_code == 404
        second = web.post(f'/api/messages/{message}/approvals', json={'candidate_part': 'SS33', 'verdict': 'ROLE_SUFFICIENT'})
        assert second.status_code == 201 and second.json()['id'] != approval['id']
        assert web.post(f'/api/messages/{message}/approvals', json={'candidate_part': 'SS34', 'verdict': 'ROLE_SUFFICIENT'}).status_code == 409
        assert web.get(f'/api/projects/{project.id}/quotes').json() == [quote.json()]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize('shown, number', [('TSC 1N4007G', '1N4007G'), ('1N4148 A0G', '1N4148-A0G'), ('SS34', 'SS34')])
def test_approval_and_quote_with_maker_name_or_order_code_in_real_postgres(full_storage, shown, number):
    """판정 결과의 표시 이름에 제조사 이름 · 주문 코드 공백이 있어도 승인 → 견적이 DB 품번 규칙(CHECK)을 통과한다(11-10 배포 점검의 422)."""
    from backend.conversations.repository import ConversationRepository
    from backend.projects.netlist import PARSER_VERSION, normalize_netlist
    from backend.projects.repository import ProjectRepository
    from backend.services.quote import QuoteService
    owner = full_storage[0][0]
    projects, conversations, quotes = ProjectRepository(), ConversationRepository(), QuoteService()
    normalized = normalize_netlist(Path('tests/fixtures/netlists/minimal.net').read_bytes())
    project = projects.create_upload(owner, '표시 이름 흐름', connections=normalized.connections,
                                     source_sha256=normalized.source_sha256, parser_version=PARSER_VERSION)
    thread = conversations.create_thread(owner, project.id)
    run, _ = conversations.start(owner, thread, {'question': f'{normalized.parts[0]} 대체?', 'target_ref': normalized.parts[0]})
    conversations.finish(owner, thread, run, 'completed', {
        'answer': '역할상 충분합니다.', 'question_type': 'candidate_judge', 'evidence': [],
        'judgement': {'kind': 'judge', 'roles': ['R01'], 'results': [{'part': shown, 'verdict': 'ROLE_SUFFICIENT'}]},
    })
    message_id = conversations.get_run(owner, run)['message_id']
    approval = quotes.approve(owner, message_id, shown, 'ROLE_SUFFICIENT')
    assert approval['candidate_part'] == shown  # 화면에는 보인 이름 그대로
    quote = quotes.create_quote(owner, approval['id'], 5)
    assert quote['part_number'] == number
    assert quotes.list_quotes(owner, project.id)[0]['part_number'] == number
    assert quotes.list_cases(owner)[0]['candidate_part'] == shown


def test_quote_for_an_old_approval_without_identifier_uses_the_same_rule(full_storage):
    """승인 칸 3개가 모두 NULL인 옛 승인(expand 뒤 contract 전)도 같은 규칙으로 계산해 견적을 저장한다."""
    from backend.conversations.repository import ConversationRepository
    from backend.projects.netlist import PARSER_VERSION, normalize_netlist
    from backend.projects.repository import ProjectRepository
    from backend.services.quote import QuoteService
    owner, _ = full_storage[0]
    connect = full_storage[1]
    projects, conversations, quotes = ProjectRepository(), ConversationRepository(), QuoteService()
    normalized = normalize_netlist(Path('tests/fixtures/netlists/minimal.net').read_bytes())
    project = projects.create_upload(owner, '옛 승인', connections=normalized.connections,
                                     source_sha256=normalized.source_sha256, parser_version=PARSER_VERSION)
    thread = conversations.create_thread(owner, project.id)
    run, _ = conversations.start(owner, thread, {'question': f'{normalized.parts[0]} 대체?', 'target_ref': normalized.parts[0]})
    conversations.finish(owner, thread, run, 'completed', {
        'answer': '역할상 충분합니다.', 'question_type': 'candidate_judge', 'evidence': [],
        'judgement': {'kind': 'judge', 'roles': ['R01'], 'results': [{'part': 'SS34', 'verdict': 'ROLE_SUFFICIENT'}]},
    })
    approval = quotes.approve(owner, conversations.get_run(owner, run)['message_id'], 'SS34', 'ROLE_SUFFICIENT')
    with connect() as conn:  # 옛 승인: contract(NOT NULL) 전의 expand 상태를 흉내 낸다. 옛 코드는 칸 3개를 모르고 넣어 모두 NULL이고 스냅샷에도 식별 품번이 없다
        conn.execute('ALTER TABLE approvals ALTER COLUMN candidate_part DROP NOT NULL, ALTER COLUMN verdict DROP NOT NULL, ALTER COLUMN part_number DROP NOT NULL')
        conn.execute("UPDATE approvals SET candidate_part=NULL, verdict=NULL, part_number=NULL, snapshot = snapshot #- '{candidate,part_number}' WHERE id=%s", (approval['id'],))
    assert quotes.create_quote(owner, approval['id'], 3)['part_number'] == 'SS34'
    # 목록도 칸이 NULL인 옛 승인에서 스냅샷 값으로 읽는다
    assert [(c['candidate_part'], c['verdict']) for c in quotes.list_cases(owner)] == [('SS34', 'ROLE_SUFFICIENT')]

def test_saved_history_http_reads_real_storage_and_preserves_owner_boundary(full_storage):
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.conversations.repository import ConversationRepository
    from backend.projects.repository import ProjectRepository
    owner, other = full_storage[0]
    project = ProjectRepository().create_demo(owner, 'breadboard_supply', '저장 기록 시험')
    repo = ConversationRepository()
    thread = repo.create_thread(owner, project.id)
    run, _ = repo.start(owner, thread, {'question': 'D1 저장 질문'})
    repo.finish(owner, thread, run, 'completed', {'answer': '저장 답변', 'judgement': {'kind': 'judge', 'results': [{'part': 'SS34', 'verdict': 'ROLE_SUFFICIENT'}]}})
    app.dependency_overrides[auth.current_user_id] = lambda: owner
    try:
        client = TestClient(app, raise_server_exceptions=False)
        listing = client.get(f'/api/projects/{project.id}/threads')
        detail = client.get(f'/api/threads/{thread}')
        result = client.get(f'/api/runs/{run}')
        assert listing.status_code == detail.status_code == result.status_code == 200
        assert listing.json()[0]['title'] == 'D1 저장 질문'
        assert [m['content'] for m in detail.json()['messages']] == ['D1 저장 질문', '저장 답변']
        assert result.json()['thread_id'] == thread
        assert result.json()['message_id'] == detail.json()['latest_run']['message_id']
        assert result.json()['result']['judgement']['results'][0]['part'] == 'SS34'
        assert result.json()['result']['profile_hints'] == []
        for response in (listing, detail, result): assert response.headers['cache-control'] == 'no-store'
        app.dependency_overrides[auth.current_user_id] = lambda: other
        for path in (f'/api/projects/{project.id}/threads', f'/api/threads/{thread}', f'/api/runs/{run}'):
            response = client.get(path)
            assert response.status_code == 404 and '저장 답변' not in response.text
    finally:
        app.dependency_overrides.clear()
