"""검색 규칙(docs/specs/rag-pipeline.md AC-05·06·07)을 DB와 API 없이 지킨다."""
from backend.rag.retrieve import rrf, tokens
from evals.run_retrieval import gold_locations


def test_rrf_puts_cards_in_both_lists_first():
    assert rrf([1, 2, 3], [3, 4])[0][0] == 3


def test_tokens_drop_korean_particle():
    assert tokens('TSC 1N5819는') == ['tsc', '1n5819']


def test_gold_locations_skip_netlist():
    gold = ['1N5817 SERIES_H2104.pdf, 2쪽, ELECTRICAL SPECIFICATIONS, VF 행',
            'data/circuits/collected/samples/pro_micro/converted/circuit.net, D2 핀 A']
    assert gold_locations(gold) == [('1N5817 SERIES_H2104.pdf', 2)]
