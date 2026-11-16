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


def test_part_docs_index_reads_corpus_on_first_lookup_only(monkeypatch):
    """[왜] 서버 시작 때 코퍼스 표를 읽으면 코퍼스 없는 DB(CI)에서 앱이 뜨지 않는다. 색인은 첫 찾기 때 한 번만 읽는다."""
    from backend.rag import card_specs, db_pool
    connects = []

    class Conn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, sql): return [('doc-1', '[ss34.pdf] 이 데이터시트의 품번: SS34, SS36')]
    monkeypatch.setenv('DATABASE_URL', 'postgresql://unused')
    monkeypatch.setattr(db_pool, 'connection', lambda: connects.append('pool') or Conn())
    lookup = card_specs.part_docs_index()
    assert connects == []
    assert lookup('ss34') == lookup('SS34 ') == ['doc-1'] and connects == ['pool']
    assert lookup('SS99') == [] and len(connects) == 1


def test_prefetch_loads_all_parts_documents_in_one_call():
    """품번마다 따로 적재하지 않고 필요한 문서를 한 번에 적재한다(같은 문서는 한 번만)."""
    loads, metas = [], []
    docs = {k: {'file': f'{k}.pdf', 'parts': [k.upper()], 'aec_h': False, 'both': False, 'texts': [], 'text_cards': [], 'cards': []}
            for k in ('a', 'b')}
    specs = make_specs(load_cards=lambda keys: loads.append(list(keys)) or {k: docs[k] for k in keys},
                       read=lambda *a, **k: ([], []), chat=None,
                       doc_meta=lambda keys: metas.append(list(keys)) or {}, part_docs=lambda p: ['a', 'b'] if p == 'P1' else ['b'])
    specs.prefetch(['P1', 'P2'], ['VRRM'])
    assert loads == [['a', 'b']] and metas == [['a', 'b']]
