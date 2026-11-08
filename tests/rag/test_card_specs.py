"""카드에서 판정 값 읽기(`backend.rag.card_specs`)의 묶어 읽기 · 다시 읽지 않기를 가짜 의존으로 확인한다(실제 LLM · DB 없음)."""
from backend.rag.card_specs import make_specs


def test_prefetched_part_is_not_read_again_and_text_rows_are_added():
    calls = []
    doc = {'file': 'd.pdf', 'parts': ['P1', 'P2'], 'aec_h': False, 'both': False, 'texts': ['Case: SMA'], 'text_cards': [],
           'cards': [{'chunk_id': 1, 'document': 'd.pdf', 'page': 1, 'table': 't', 'row': 'r', 'content': '[d.pdf · 1쪽 · t] Part number: P1 | VRRM (V): 40'}]}

    def read(cards, codes, doc_parts, *, chat):
        calls.append(tuple(codes))
        return [{'part': 'P1', 'category': None, 'code': 'VRRM', 'min': None, 'typ': None, 'max': 40.0}], []
    specs = make_specs(load_cards=lambda keys: {'k': doc}, read=read, chat=None, doc_meta=lambda keys: {'k': {'category': 'schottky-rectifier'}},
                       part_docs=lambda p: ['k'])
    specs.prefetch(['P1', 'P2'], ['VRRM'])
    rows = specs('P1')  # codes 없이 다시 불러도 다시 읽지 않는다
    assert len(calls) == 1 and {r['code'] for r in rows} == {'VRRM', 'PACKAGE'}
    assert all(r['category'] == 'schottky-rectifier' for r in rows)


def test_rows_already_read_by_find_are_reused_and_missing_parts_are_read():
    """찾기가 판정 코드까지 읽어 둔 문서(shared)는 다시 읽지 않고, 원하는 품번 행이 없을 때만 새로 읽는다(11-09)."""
    calls = []
    doc = {'file': 'd.pdf', 'parts': ['P1', 'P2'], 'aec_h': False, 'both': False, 'texts': [], 'text_cards': [],
           'cards': [{'chunk_id': 1, 'document': 'd.pdf', 'page': 1, 'table': 't', 'row': 'r',
                      'content': '[d.pdf · 1쪽 · t] Part number: P1 P2 | VRRM (V): 40 | IFSM (A): 30'}]}
    row = lambda p, code, v: {'part': p, 'category': None, 'code': code, 'min': None, 'typ': None, 'max': v}  # noqa: E731
    shared = {'k': {'codes': {'VRRM', 'IFSM', 'IF_AV'}, 'rows': [row('P1', 'VRRM', 40.0), row('P1', 'IFSM', 30.0)]}}

    def read(cards, codes, doc_parts, *, chat):
        calls.append(tuple(codes))
        return [row('P2', c, 1.0) for c in codes], []
    specs = make_specs(load_cards=lambda keys: {'k': doc}, read=read, chat=None, doc_meta=lambda keys: {'k': {'category': None}},
                       part_docs=lambda p: ['k'], shared=shared)
    specs.prefetch(['P1'], ['VRRM', 'IFSM'])
    assert calls == [] and {r['code'] for r in specs('P1')} == {'VRRM', 'IFSM'}
    specs.prefetch(['P2'], ['VRRM'])  # shared에 P2 행이 없으면 새로 읽는다
    assert calls == [('VRRM',)]
