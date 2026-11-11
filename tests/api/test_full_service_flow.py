"""격리 PostgreSQL에서 업로드→run 재개→승인→가격 없는 견적→소유권→cascade를 잇는다."""
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from backend import auth


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
                for name in ('003_auth.sql', '005_auth_attempt_window.sql', '006_user_roles.sql', '018_projects.sql', '019_conversations.sql', '020_approvals_quotes.sql'):
                    conn.execute(Path('db', name).read_text(encoding='utf-8-sig'))
                users = [row[0] for row in conn.execute("INSERT INTO users(login_id,password_hash,role) VALUES ('flow-owner@test','fake','user'),('flow-other@test','fake','user') RETURNING id")]
            yield users, connect
        finally:
            admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


def test_full_owned_flow_and_price_free_cascade(full_storage):
    from backend.conversations.repository import ConversationNotFound, ConversationRepository
    from backend.projects.netlist import PARSER_VERSION, normalize_netlist
    from backend.projects.repository import ProjectRepository
    from backend.services.quote import QuoteNotFound, QuoteService
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
        'judgement': {'kind': 'judge', 'roles': ['R01'], 'results': [{'part': 'SS34', 'verdict': 'ROLE_SUFFICIENT'}]},
    })
    saved = conversations.get_run(owner, run)
    approval = quotes.approve(owner, saved['message_id'], 'SS34', 'ROLE_SUFFICIENT')
    # [왜] 같은 메시지를 다시 승인하면 UNIQUE(message_id)가 막아 승인 · 사례가 한 건으로 남는다(API는 409, db/020)
    with pytest.raises(psycopg.errors.UniqueViolation): quotes.approve(owner, saved['message_id'], 'SS34', 'ROLE_SUFFICIENT')
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
        stored = ''.join(row[0] for row in conn.execute('SELECT snapshot::text FROM approvals UNION ALL SELECT snapshot::text FROM quotes UNION ALL SELECT snapshot::text FROM approved_cases'))
    assert not any(key in stored for key in ('price', 'stock', 'availability', 'product_url', 'fetched_at'))

    quotes.delete_case(owner, approval['case_id'])
    assert quotes.list_cases(owner) == []
    projects.delete_owned(owner, project.id)
    with connect() as conn:
        counts = {name: conn.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(name))).fetchone()[0]
                  for name in ('projects', 'circuits', 'threads', 'runs', 'messages', 'approvals', 'quotes', 'approved_cases')}
    assert not any(counts.values())
