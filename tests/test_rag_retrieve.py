"""검색 규칙(docs/specs/rag-pipeline.md AC-05~09)을 DB와 API 없이 지킨다."""
from backend.rag.retrieve import allowed_chunks, part_index, rrf, tokens
from evals.run_retrieval import gold_locations


def test_rrf_puts_cards_in_both_lists_first():
    assert rrf([1, 2, 3], [3, 4])[0][0] == 3


def test_tokens_drop_korean_particle():
    assert tokens('TSC 1N5819는') == ['tsc', '1n5819']


def test_gold_locations_skip_netlist():
    gold = ['1N5817 SERIES_H2104.pdf, 2쪽, ELECTRICAL SPECIFICATIONS, VF 행',
            'data/circuits/collected/samples/pro_micro/converted/circuit.net, D2 핀 A']
    assert gold_locations(gold) == [('1N5817 SERIES_H2104.pdf', 2)]


# (카드 id, 문서 id, 본문): 문서 1은 SS34, 문서 2는 SS34L만 표지에 적혀 있다
ROWS = [(1, 1, '[SS32 SERIES_Q2412.pdf] 이 데이터시트의 품번: SS310, SS32, SS34'), (2, 1, '[SS32 SERIES_Q2412.pdf · 2쪽 · RATINGS] VRRM: 40'),
        (3, 2, '[SS34L SERIES_A1.pdf] 이 데이터시트의 품번: SS34L'), (4, 2, '[SS34L SERIES_A1.pdf · 1쪽 · RATINGS] SS34 VRRM: 40')]


def test_part_index_reads_cover_cards():
    part_docs, doc_chunks = part_index(ROWS)
    assert part_docs == {'ss310': {1}, 'ss32': {1}, 'ss34': {1}, 'ss34l': {2}}
    assert doc_chunks == {1: [1, 2], 2: [3, 4]}


def test_parts_filter_matches_whole_part_only():
    assert allowed_chunks(part_index(ROWS), ['ss34']) == {1, 2}


def test_unknown_part_allows_nothing():
    assert allowed_chunks(part_index(ROWS), ['NOPE123']) == set()
