"""카드 찾기(`backend.rag.card_find`): 검색 문장, 문서 고르기(분류 · 개수), 카드 거르기, find_candidates와 같은 거르기 · 순서.

- 역할: 검색 · 카드 적재 · 카드 읽기 · 문서 분류를 가짜로 넘겨 DB · LLM 없이 make_find의 find를 본다.
  같은 사양 행에서 이상 · 이하 · 자리(slot) 결과가 spec_lookup.find_candidates(가짜 연결)와 같은지도 본다.
- 하지 않는 일: 실제 검색 · DB 적재 SQL(load_cards · doc_meta)과 카드 읽기 LLM. 그것은 실제 실행에서 본다.
- 출처: spec_lookup.find_candidates 계약(SPEC.md 8.7, ADR 0013)
"""
import pytest

from backend.rag import card_find, spec_lookup


def row(part, code, slot, value, category=None, unit='V'):
    """card_read가 돌려주는 사양 한 줄(spec_lookup._row 모양)."""
    r = {'part': part, 'category': category, 'code': code, 'min': None, 'typ': None, 'max': None, 'text': None, 'unit': unit,
         'source_value_text': f'{value} {unit}', 'test_condition': None,
         'citation': {'document': 'x.pdf', 'page': 2, 'table': 'T', 'row': part, 'chunk_index': None}}
    r[slot] = value
    return r


def card(chunk_id, file, text):
    return {'chunk_id': chunk_id, 'document': file, 'page': 2, 'table': 'ELECTRICAL', 'row': 'r', 'content': f'[{file} · 2쪽 · ELECTRICAL] {text}'}


VRRM_CARD = 'PARAMETER: Repetitive peak reverse voltage | SYMBOL: VRRM | VALUE: 40 | UNIT: V'


def doc(key, parts, texts=(), cards=None):
    """가짜 문서 하나. 카드가 없으면 VRRM 행 카드 하나를 둔다(카드 거르기를 지나 read가 불리게)."""
    file = f'{key}.pdf'
    return {'file': file, 'parts': list(parts), 'texts': list(texts),
            'cards': cards if cards is not None else [card(ord(key[0]), file, VRRM_CARD)]}


class World:
    """검색 · 적재 · 읽기 · 분류 가짜. 부른 인자를 calls에 남긴다. read는 카드와 상관없이 정해진 행을 돌려준다."""

    def __init__(self, docs, rows=(), meta=None, hits=None):
        self.docs, self.rows, self.meta = docs, list(rows), meta or {}
        self.hits = hits if hits is not None else [{'document_key': k} for k in docs]
        self.calls = {'retrieve': [], 'load': [], 'read': []}

    def retrieve(self, sentence, k):
        self.calls['retrieve'].append((sentence, k))
        return self.hits

    def load_cards(self, keys):
        self.calls['load'].append(list(keys))
        return {k: self.docs[k] for k in keys if k in self.docs}

    def read(self, cards, codes, doc_parts, *, chat):
        self.calls['read'].append((cards, codes, doc_parts, chat))
        return self.rows, []

    def doc_meta(self, keys):
        return {k: v for k, v in self.meta.items() if k in keys}

    def find(self, n_docs=8):
        return card_find.make_find(retrieve=self.retrieve, load_cards=self.load_cards, read=self.read, chat='CHAT',
                                   doc_meta=self.doc_meta, n_docs=n_docs)


def test_search_sentence_uses_words_symbols_and_natural_units():
    """0.001 A는 1 mA, 3e-8 s는 30 ns처럼 데이터시트 말투로 쓰고, 같은 코드 조건 둘은 낱말을 한 번만 쓴다."""
    conds = [{'code': 'VRRM', 'gte': 40}, {'code': 'IF_AV', 'gte': 0.001}, {'code': 'TRR', 'lte': 3e-8},
             {'code': 'CJ', 'lte': 1.5e-11}, {'code': 'IR', 'lte': 0.0002}, {'code': 'TJ_MAX', 'gte': 150}]
    assert card_find.search_sentence(conds, 'schottky-rectifier', 'SOD-123F') == (
        'repetitive peak reverse voltage VRRM 40 V, average forward current IF(AV) 1 mA, reverse recovery time trr 30 ns, '
        'junction capacitance CJ 15 pF, reverse leakage current IR 200 µA, operating junction temperature TJ 150 °C, '
        'schottky rectifier, SOD-123F')
    zener = [{'code': 'VZ', 'slot': 'min', 'gte': 3.42}, {'code': 'VZ', 'slot': 'max', 'lte': 3.78}]
    assert card_find.search_sentence(zener) == 'zener voltage VZ 3.42 V 3.78 V'
    w = World({'a': doc('a', ['SS14'])})
    w.find()(zener, 'zener-diode')
    assert w.calls['retrieve'] == [('zener voltage VZ 3.42 V 3.78 V, zener diode', 40)]


def test_category_filters_only_documents_with_known_category():
    """분류를 주면 분류가 다른 문서를 빼고, 분류가 비었거나 모르는 문서(열이 아직 없음)는 남긴다. 분류를 안 주면 거르지 않는다."""
    docs = {k: doc(k, [k.upper()]) for k in 'abcd'}
    meta = {'a': {'category': 'zener-diode'}, 'b': {'category': 'schottky-rectifier'}, 'c': {'category': None}}
    w = World(docs, meta=meta)
    w.find()([{'code': 'VRRM', 'gte': 1}], 'zener-diode')
    w.find()([{'code': 'VRRM', 'gte': 1}])
    assert w.calls['load'] == [['a', 'c', 'd'], ['a', 'b', 'c', 'd']]
    w = World(docs)  # doc_meta가 빈 dict(category 열 없음)
    w.find()([{'code': 'VRRM', 'gte': 1}], 'zener-diode')
    assert w.calls['load'] == [['a', 'b', 'c', 'd']]


def test_takes_first_n_docs_in_first_appearance_order():
    hits = [{'document_key': k} for k in ['a', 'b', 'a', 'c', 'd', 'b', 'e']]
    w = World({k: doc(k, [k.upper()]) for k in 'abcde'}, hits=hits)
    w.find(n_docs=3)([{'code': 'VRRM', 'gte': 1}])
    assert w.calls['load'] == [['a', 'b', 'c']]


def test_part_meeting_every_condition_is_returned_with_matches():
    """SS14는 두 조건을 다 채워 나온다. SS12는 VRRM이 모자라고, SS16은 IF_AV 행이 없어 빠진다."""
    rows = [row('SS14', 'VRRM', 'max', 40.0), row('SS14', 'IF_AV', 'max', 1.0, unit='A'),
            row('SS12', 'VRRM', 'max', 20.0), row('SS12', 'IF_AV', 'max', 1.0, unit='A'),
            row('SS16', 'VRRM', 'max', 60.0)]
    w = World({'a': doc('a', ['SS12', 'SS14', 'SS16'], texts=['[a.pdf · 1쪽] Case: SMA (DO-214AC)'])}, rows,
              meta={'a': {'category': 'schottky-rectifier'}})
    found = w.find()([{'code': 'VRRM', 'gte': 40}, {'code': 'IF_AV', 'gte': 1}])
    assert found == [{'part': 'SS14', 'category': 'schottky-rectifier', 'packages': ['SMA', 'DO-214AC'], 'matches': rows[:2]}]


ZENER = [row('BZT52C3V6', 'VZ', 'min', 3.42, 'zener-diode'), row('BZT52C3V6', 'VZ', 'max', 3.78, 'zener-diode'),
         row('BZT52C3V9', 'VZ', 'min', 3.7, 'zener-diode'), row('BZT52C3V9', 'VZ', 'max', 4.1, 'zener-diode'),
         row('BZT52C3V3', 'VZ', 'min', 3.1, 'zener-diode'), row('BZT52C3V3', 'VZ', 'max', 3.5, 'zener-diode'),
         row('BZT52C3V6X', 'VZ', 'min', 3.5, 'zener-diode'),  # 최대 행이 없다
         row('D1', 'CJ', 'typ', 1.5e-11, 'zener-diode', 'F'), row('D2', 'CJ', 'max', 1e-11, 'zener-diode', 'F'),
         row('D3', 'CJ', 'typ', 3e-11, 'zener-diode', 'F'), row('D4', 'VZ', 'max', 3.42, 'zener-diode')]


class SqlConn:
    """find_candidates의 조건 질의를 SQL 뜻으로 흉내 낸다: 조건마다 (코드 같음 AND 그 칸 >= gte AND 그 칸 <= lte), NULL 비교는 거짓."""

    def __init__(self, rows, conditions):
        self.rows, self.conditions = rows, conditions

    def execute(self, sql, params):
        if sql.lstrip().startswith('SELECT part_number'):  # 패키지 질의: 이 시험은 패키지 없음
            return []
        out = []
        for r in self.rows:
            hits = []
            for c in self.conditions:
                v = r[c.get('slot') or spec_lookup.DEFAULT_SLOT.get(c['code'], 'max')]
                hits.append(r['code'] == c['code'] and v is not None and ('gte' not in c or v >= c['gte']) and ('lte' not in c or v <= c['lte']))
            out.append((r['part'], r['category'], r['code'], r['min'], r['typ'], r['max'], None, r['unit'], r['source_value_text'],
                        None, 'https://x.test/a.pdf', 2, 'T', r['part'], 1, *hits))
        return out


@pytest.mark.parametrize('conds, expected', [
    # 제너 VZ 창: 최소 ≥ 3.42 그리고 최대 ≤ 3.8(경계 포함). 최대 행이 없는 C3V6X는 빠진다
    ([{'code': 'VZ', 'slot': 'min', 'gte': 3.42}, {'code': 'VZ', 'slot': 'max', 'lte': 3.8}], ['BZT52C3V6']),
    # slot을 안 주면 최대 칸(D4 3.42 경계 포함, 최소 칸만 있는 C3V6X는 안 봄), 기준에 가까운 순
    ([{'code': 'VZ', 'gte': 3.42}], ['D4', 'BZT52C3V3', 'BZT52C3V6', 'BZT52C3V9']),
    # CJ의 기본 칸은 대표. 최대 칸만 있는 D2는 빠진다
    ([{'code': 'CJ', 'lte': 2e-11}], ['D1']),
    ([{'code': 'CJ', 'slot': 'max', 'lte': 2e-11}], ['D2']),
    # 이상 · 이하를 둘 다 주면 둘 다 채워야 하고, 순서는 둘 중 먼 비율(3.6/3.42 > 3.6/3.5)
    ([{'code': 'VZ', 'slot': 'min', 'gte': 3.4, 'lte': 3.6}], ['BZT52C3V6X', 'BZT52C3V6']),
])
def test_filter_and_order_same_as_find_candidates(conds, expected):
    """같은 사양 행이면 카드 찾기와 find_candidates가 같은 품번 · 같은 순서 · 같은 채운 행을 낸다."""
    parts = sorted({r['part'] for r in ZENER})
    cards = [card(1, 'z.pdf', 'PARAMETER: Zener voltage | SYMBOL: VZ'), card(2, 'z.pdf', 'PARAMETER: Junction capacitance | SYMBOL: CJ')]
    w = World({'z': doc('z', parts, cards=cards)}, ZENER, meta={'z': {'category': 'zener-diode'}})
    mine = w.find()(conds)
    theirs = spec_lookup.find_candidates(SqlConn(ZENER, conds), conds)
    assert [p['part'] for p in mine] == [p['part'] for p in theirs] == expected
    values = lambda found: [[(m['code'], m['min'], m['typ'], m['max']) for m in p['matches']] for p in found]  # noqa: E731
    assert values(mine) == values(theirs)
    assert [p['category'] for p in mine] == [p['category'] for p in theirs]


def test_package_filter_needs_the_same_package_name():
    """패키지는 문서의 'Case:' 글과 PACKAGE 열에서 읽는다. 이름이 같아야 하고(SOD-123은 SOD-123F에 걸리지 않음) 하이픈 · 대소문자는 무시한다."""
    order_card = card(9, 'b.pdf', 'PART NO.: B1 | PACKAGE: SOD-123 | PACKING: 3K / 7" REEL')
    docs = {'a': doc('a', ['A1'], texts=['[a.pdf · 1쪽] Case: SOD-123F molded plastic']),
            'b': doc('b', ['B1'], cards=[card(8, 'b.pdf', VRRM_CARD), order_card])}
    w = World(docs, [row('A1', 'VRRM', 'max', 40.0), row('B1', 'VRRM', 'max', 40.0)])
    find, cond = w.find(), [{'code': 'VRRM', 'gte': 40}]
    assert [p['part'] for p in find(cond, package='SOD-123')] == ['B1']
    assert [p['part'] for p in find(cond, package='sod123f')] == ['A1']
    assert [(p['part'], p['packages']) for p in find(cond)] == [('A1', ['SOD-123F']), ('B1', ['SOD-123'])]
    assert all(c['chunk_id'] != 9 for c in w.calls['read'][0][0])  # 주문표 카드는 패키지만 주고 LLM에는 안 넘긴다


def test_orders_by_original_package_then_category_then_ratio():
    """find_candidates 순위 시험(test_find_ranks_all_matches_before_the_limit)과 같은 부품 · 같은 순서."""
    docs = {'a': doc('a', ['SS14'], texts=['Case: SMA']), 'b': doc('b', ['AAA1'], texts=['Case: SMA']),
            'c': doc('c', ['1N5817', '1N5819'], texts=['Case: DO-41']), 'd': doc('d', ['1N4001'], texts=['Case: DO-41']),
            'e': doc('e', ['ZZ1'], texts=['Case: SMA'])}
    meta = {k: {'category': 'schottky-rectifier'} for k in 'ace'} | {k: {'category': 'standard-rectifier'} for k in 'bd'}
    rows = [row('SS14', 'VRRM', 'max', 40.0), row('AAA1', 'VRRM', 'max', 1000.0), row('1N5817', 'VRRM', 'max', 20.0),
            row('1N5819', 'VRRM', 'max', 40.0), row('1N4001', 'VRRM', 'max', 50.0), row('ZZ1', 'VRRM', 'max', 10.0)]
    find, cond = World(docs, rows, meta).find(), [{'code': 'VRRM', 'gte': 15}]
    assert [p['part'] for p in find(cond, original_packages=['sma'], original_category='schottky-rectifier')] == [
        'SS14', 'AAA1', '1N5817', '1N5819', '1N4001']
    assert [p['part'] for p in find(cond)] == ['1N5817', '1N5819', 'SS14', '1N4001', 'AAA1']
    assert [p['part'] for p in find(cond, limit=1, original_packages=['SMA'], original_category='schottky-rectifier')] == ['SS14']


def test_read_is_called_once_with_cards_that_mention_the_codes(monkeypatch):
    """조건 코드의 기호나 낱말이 있는 카드만, 문서 순서대로, MAX_CARDS장까지 넘긴다. doc_parts는 넘긴 카드의 문서만."""
    a = [card(1, 'a.pdf', VRRM_CARD), card(2, 'a.pdf', 'PARAMETER: Marking code | VALUE: S4'),
         card(3, 'a.pdf', 'PARAMETER: Maximum average forward rectified current | VALUE: 1 | UNIT: A')]
    docs = {'a': doc('a', ['SS14'], cards=a), 'b': doc('b', ['X1'], cards=[card(4, 'b.pdf', 'PARAMETER: Weight | VALUE: 0.1 g')])}
    w = World(docs)
    assert w.find()([{'code': 'VRRM', 'gte': 40}, {'code': 'IF_AV', 'gte': 1}]) == []
    assert w.calls['read'] == [([a[0], a[2]], ['VRRM', 'IF_AV'], {'a.pdf': ['SS14']}, 'CHAT')]
    monkeypatch.setattr(card_find, 'MAX_CARDS', 1)
    w.find()([{'code': 'VRRM', 'gte': 40}, {'code': 'IF_AV', 'gte': 1}])
    assert w.calls['read'][1][0] == [a[0]]


def test_no_hits_or_no_cards_means_no_llm_call():
    w = World({'b': doc('b', ['X1'], cards=[card(4, 'b.pdf', 'PARAMETER: Weight | VALUE: 0.1 g')])})
    assert w.find()([{'code': 'VRRM', 'gte': 40}]) == []
    w.hits = []
    assert w.find()([{'code': 'VRRM', 'gte': 40}]) == []
    assert w.calls['read'] == [] and w.calls['load'] == [['b']]


def test_same_conditions_read_once_even_with_different_order_args():
    # [왜] judge.py는 순서용 인자만 바꿔 같은 조건으로 두 번 부른다. 카드 읽기(LLM)는 한 번이어야 한다
    import backend.rag.card_find as F
    calls = []

    def read(cards, codes, doc_parts, *, chat):
        calls.append(1)
        return [{'part': 'P1', 'code': 'VRRM', 'min': None, 'typ': None, 'max': 60.0, 'unit': 'V'}], []
    find = F.make_find(retrieve=lambda s, k: [{'document_key': 'd1'}], doc_meta=lambda keys: {},
                       load_cards=lambda keys: {'d1': {'file': 'd1.pdf', 'parts': ['P1'],
                                                       'cards': [{'chunk_id': 1, 'document': 'd1.pdf', 'content': 'SYMBOL: VRRM | VALUE: 60'}],
                                                       'texts': []}},
                       read=read, chat=None)
    a = find([{'code': 'VRRM', 'gte': 40}], None, None, 50, original_packages=['SMA'])
    b = find([{'code': 'VRRM', 'gte': 40}], None, None, 50)
    assert [p['part'] for p in a] == [p['part'] for p in b] == ['P1'] and len(calls) == 1


def test_bidirectional_parts_take_unidirectional_values_when_document_says_so():
    # [왜] TVS 값 표는 단방향 품번만 적는다. '특성은 양방향 모두 적용' 문서만 C · CA · CAH 품번에 단방향 값을 붙인다(h4-15, 11-09)
    from backend.rag.card_find import bi_copies, h_copies
    doc = {'parts': ['SMAJ6.0A', 'SMAJ6.0AH', 'SMAJ6.0CA', 'SMAJ6.0CAH'], 'aec_h': True, 'both': True}
    rows = [{'part': 'SMAJ6.0A', 'code': 'VRWM', 'max': 6.0}]
    rows += h_copies(rows, doc)
    got = sorted(r['part'] for r in rows + bi_copies(rows, doc))
    assert got == ['SMAJ6.0A', 'SMAJ6.0AH', 'SMAJ6.0CA', 'SMAJ6.0CAH']
    assert bi_copies(rows, {**doc, 'both': False}) == []


def test_also_read_codes_are_read_once_and_shared_with_judge_specs():
    """판정이 쓸 코드(also_read)까지 한 번에 읽고, 문서마다 읽은 행을 shared에 둔다. 거르기는 조건 코드로만 한다(11-09)."""
    import contextvars
    rows = [row('SS14', 'VRRM', 'max', 40.0), row('SS14', 'IFSM', 'max', 30.0, unit='A')]
    w = World({'a': doc('a', ['SS14'], cards=[card(1, 'a.pdf', VRRM_CARD + ' | IFSM (A): 30')])}, rows)
    shared = {}
    find = card_find.make_find(retrieve=w.retrieve, load_cards=w.load_cards, read=w.read, chat='CHAT', doc_meta=w.doc_meta, shared=shared)

    def run():
        find.also_read(['IFSM', 'PACKAGE'])  # PACKAGE는 숫자 코드가 아니라 읽지 않는다
        return find([{'code': 'VRRM', 'gte': 40}])
    found = contextvars.copy_context().run(run)
    assert [f['part'] for f in found] == ['SS14'] and w.calls['read'][0][1] == ['VRRM', 'IFSM']
    assert shared['a']['codes'] == {'VRRM', 'IFSM'} and shared['a']['rows'] == rows
    assert card_find.EXTRA_CODES.get() == ()  # 다른 문맥(다른 요청)에는 새지 않는다
