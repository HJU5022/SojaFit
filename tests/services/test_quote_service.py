import pytest

from backend.services.quote import InvalidApproval, approval_snapshot, assert_no_price_data


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
