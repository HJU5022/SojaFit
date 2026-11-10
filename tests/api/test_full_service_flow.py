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
    projects.delete_owned(owner, project.id)
    with connect() as conn:
        counts = {name: conn.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(name))).fetchone()[0]
                  for name in ('projects', 'circuits', 'threads', 'runs', 'messages', 'approvals', 'quotes', 'approved_cases')}
    assert not any(counts.values())


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
    """식별 품번 칸(approvals.part_number)이 NULL인 옛 승인(expand 뒤 contract 전)도 같은 규칙으로 계산해 견적을 저장한다."""
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
    with connect() as conn:  # 옛 승인: contract(NOT NULL) 전의 expand 상태를 흉내 낸다. 칸 part_number가 NULL이고 스냅샷에도 식별 품번이 없다
        conn.execute('ALTER TABLE approvals ALTER COLUMN part_number DROP NOT NULL')
        conn.execute("UPDATE approvals SET part_number=NULL, snapshot = snapshot #- '{candidate,part_number}' WHERE id=%s", (approval['id'],))
    assert quotes.create_quote(owner, approval['id'], 3)['part_number'] == 'SS34'

