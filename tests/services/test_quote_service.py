import pytest

from backend.services.quote import InvalidApproval, approval_snapshot, assert_no_price_data, part_number


def result(verdict='ROLE_SUFFICIENT'):
    return {'answer': 'ok', 'question_type': 'candidate_judge', 'evidence': [{'document': 'a.pdf'}],
            'judgement': {'kind': 'judge', 'results': [{'part': 'SS34', 'verdict': verdict, 'checks': []}], 'shown': []}}


@pytest.mark.parametrize('verdict', ['NOT_SUFFICIENT', 'NOT_VERIFIED'])
def test_rejects_unapprovable_verdicts(verdict):
    with pytest.raises(InvalidApproval): approval_snapshot(result(verdict), 'SS34', verdict)


def test_rejects_missing_judgement_and_unknown_candidate():
    with pytest.raises(InvalidApproval): approval_snapshot({'answer': 'no judgement'}, 'SS34', 'ROLE_SUFFICIENT')
    with pytest.raises(InvalidApproval): approval_snapshot(result(), 'OTHER', 'ROLE_SUFFICIENT')


@pytest.mark.parametrize('key', ['price', 'price_breaks', 'stock', 'availability', 'product_url', 'fetched_at'])
def test_forbidden_price_keys_are_rejected_at_any_depth(key):
    with pytest.raises(InvalidApproval): assert_no_price_data({'candidate': {'checks': [{key: 'private'}]}})


def test_snapshot_is_immutable_copy_without_price_data():
    source = result()
    snapshot = approval_snapshot(source, 'SS34', 'ROLE_SUFFICIENT')
    source['judgement']['results'][0]['part'] = 'changed'
    assert snapshot['candidate']['part'] == 'SS34'
    assert_no_price_data(snapshot)


def test_snapshot_uses_the_explicitly_confirmed_verdict_for_duplicate_part_numbers():
    source = result('IDENTICAL')
    source['judgement']['shown'] = [{'part': 'SS34', 'verdict': 'ROLE_SUFFICIENT', 'checks': []}]
    snapshot = approval_snapshot(source, 'SS34', 'ROLE_SUFFICIENT')
    assert snapshot['candidate']['verdict'] == 'ROLE_SUFFICIENT'


def test_forbidden_keys_match_the_sql_check():
    # [왜] 승인 snapshot(approvals)의 DB 검사(db/020)와 코드의 금지 키가 어긋나면 저장이 거부되거나 가격이 저장된다
    import re
    from pathlib import Path
    from backend.services.quote import FORBIDDEN
    sql = (Path(__file__).resolve().parents[2] / 'db' / '020_approvals_quotes.sql').read_text(encoding='utf-8')
    listed = re.search(r"ANY \(ARRAY\[(.*?)\]\)", sql).group(1)
    assert set(re.findall(r"'([^']+)'", listed)) == FORBIDDEN


@pytest.mark.parametrize('shown, number', [
    ('1N4007G', '1N4007G'), ('TSC 1N4007G', '1N4007G'), ('tsc 1N4007G', '1N4007G'), ('Taiwan Semiconductor 1N4007G', '1N4007G'),
    ('1N4148 A0G', '1N4148-A0G'), ('TSC 1N4148 A0G', '1N4148-A0G'), ('  SS34  ', 'SS34'), ('SMAJ5.0A/TR', 'SMAJ5.0A/TR'),
])
def test_part_number_drops_maker_name_and_joins_order_code(shown, number):
    """판정 결과의 표시 이름('TSC 1N4007G')에서 DB 품번 규칙에 맞는 식별 품번을 만든다(11-10 배포 점검의 422)."""
    assert part_number(shown) == number


@pytest.mark.parametrize('shown', ['', '   ', 'TSC ', '한글품번', '1N4007G;DROP', "1N4007G'", '-1N4007G', 'x' * 101])
def test_part_number_rejects_names_the_quote_table_cannot_hold(shown):
    with pytest.raises(InvalidApproval): part_number(shown)


def test_approval_with_maker_name_keeps_display_name_and_stores_identifier():
    """모델이 'TSC 1N4007G'로 읽은 후보도 승인되고, 표시 이름은 그대로 · 견적용 품번은 따로 저장한다."""
    source = result()
    source['judgement']['results'][0]['part'] = 'TSC 1N4007G'
    snapshot = approval_snapshot(source, 'TSC 1N4007G', 'ROLE_SUFFICIENT')
    assert snapshot['candidate']['part'] == 'TSC 1N4007G' and snapshot['candidate']['part_number'] == '1N4007G'
    assert_no_price_data(snapshot)
    with pytest.raises(InvalidApproval): approval_snapshot(source, '1N4007G', 'ROLE_SUFFICIENT')  # 저장된 판정 결과의 후보와 달라서 거절


def test_approval_is_refused_when_no_identifier_can_be_made():
    """견적으로 이어질 수 없는 이름은 승인 단계에서 막는다(승인만 되고 견적에서 깨지지 않게)."""
    source = result()
    source['judgement']['results'][0]['part'] = '한글 후보'
    with pytest.raises(InvalidApproval): approval_snapshot(source, '한글 후보', 'ROLE_SUFFICIENT')

