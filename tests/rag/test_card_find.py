"""카드 찾기(`backend.rag.card_find`): 검색 문장, 문서 고르기(분류 · 개수 · 개요 줄로 코드가 먼저), 카드 거르기, 거르기 · 순서.

- 역할: 검색 · 카드 적재 · 카드 읽기 · 문서 분류를 가짜로 넘겨 DB · LLM 없이 make_find의 find를 본다.
  같은 사양 행에서 이상 · 이하 · 자리(slot) 거르기와 찾기 순위(패키지 → 분류 → 기준에 가까운 순, 가장 먼 조건의 비율)를 정한 값으로 본다.
- 하지 않는 일: 실제 검색 · DB 적재 SQL(load_cards · doc_meta)과 카드 읽기 LLM. 그것은 실제 실행에서 본다.
- 출처: 찾기 계약(SPEC.md 8.7, ADR 0013 → 0016)
"""
import pytest

from backend.rag import card_find


def row(part, code, slot, value, category=None, unit='V'):
    """card_read가 돌려주는 사양 한 줄(분류 · 코드 · 최소/대표/최대 · 단위 · 원문 · 시험 조건 · 인용)."""
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


@pytest.mark.parametrize('conds, expected, matches', [
    # 제너 VZ 창: 최소 ≥ 3.42 그리고 최대 ≤ 3.8(경계 포함). 최대 행이 없는 C3V6X는 빠진다. 조건마다 다른 행(최소 행 · 최대 행)이 채운다
    ([{'code': 'VZ', 'slot': 'min', 'gte': 3.42}, {'code': 'VZ', 'slot': 'max', 'lte': 3.8}], ['BZT52C3V6'],
     [[('VZ', 3.42, None, None), ('VZ', None, None, 3.78)]]),
    # slot을 안 주면 최대 칸(D4 3.42 경계 포함, 최소 칸만 있는 C3V6X는 안 봄), 기준에 가까운 순
    ([{'code': 'VZ', 'gte': 3.42}], ['D4', 'BZT52C3V3', 'BZT52C3V6', 'BZT52C3V9'],
     [[('VZ', None, None, 3.42)], [('VZ', None, None, 3.5)], [('VZ', None, None, 3.78)], [('VZ', None, None, 4.1)]]),
    # CJ의 기본 칸은 대표. 최대 칸만 있는 D2는 빠진다
    ([{'code': 'CJ', 'lte': 2e-11}], ['D1'], [[('CJ', None, 1.5e-11, None)]]),
    ([{'code': 'CJ', 'slot': 'max', 'lte': 2e-11}], ['D2'], [[('CJ', None, None, 1e-11)]]),
    # 이상 · 이하를 둘 다 주면 둘 다 채워야 하고, 순서는 둘 중 먼 비율(3.6/3.42 > 3.6/3.5)
    ([{'code': 'VZ', 'slot': 'min', 'gte': 3.4, 'lte': 3.6}], ['BZT52C3V6X', 'BZT52C3V6'],
     [[('VZ', 3.5, None, None)], [('VZ', 3.42, None, None)]]),
])
def test_filter_and_order_by_slot_and_bounds(conds, expected, matches):
    """이상 · 이하 · 자리(slot)로 행을 거르고(그 칸이 비면 거짓, 경계 포함), 채운 행과 분류를 붙여 기준에 가까운 순으로 낸다."""
    parts = sorted({r['part'] for r in ZENER})
    cards = [card(1, 'z.pdf', 'PARAMETER: Zener voltage | SYMBOL: VZ'), card(2, 'z.pdf', 'PARAMETER: Junction capacitance | SYMBOL: CJ')]
    w = World({'z': doc('z', parts, cards=cards)}, ZENER, meta={'z': {'category': 'zener-diode'}})
    found = w.find()(conds)
    assert [p['part'] for p in found] == expected
    assert [[(m['code'], m['min'], m['typ'], m['max']) for m in p['matches']] for p in found] == matches
    assert {p['category'] for p in found} == {'zener-diode'}


def test_rank_uses_the_farthest_condition():
    """조건이 여럿이면 조건마다 '값/기준'(이하면 '기준/값') 중 가장 큰 비율로 줄 세운다. 한 값만 크게 넘는 부품이 뒤로 간다."""
    rows = [row('A1', 'VRRM', 'max', 21.0), row('A1', 'IF_AV', 'max', 0.1, unit='A'),   # 최대 비율 2/0.1 = 20
            row('B1', 'VRRM', 'max', 60.0), row('B1', 'IF_AV', 'max', 1.0, unit='A')]   # 최대 비율 60/20 = 3
    found = World({'a': doc('a', ['A1', 'B1'])}, rows).find()([{'code': 'VRRM', 'gte': 20}, {'code': 'IF_AV', 'lte': 2.0}])
    assert [p['part'] for p in found] == ['B1', 'A1']


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
    """조건을 채운 품번 전부를 원래 부품과 같은 패키지 → 같은 분류 → 기준에 가까운 순 → 품번 순으로 줄 세운 뒤 limit에서 자른다(SPEC 8.3 찾기 순위)."""
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


def ov(key, title):
    """개요 줄 하나(overview_lines 모양). 글 앞머리는 청킹이 붙이는 '[파일 · 1쪽 · 제품 개요] '다."""
    return {'key': key, 'file': f'{key}.pdf', 'text': f'[{key}.pdf · 1쪽 · 제품 개요] {title}'}


def test_title_values_read_ranges_but_not_numbers_inside_part_or_package_names():
    tv = card_find.title_values
    assert tv(ov('a', '1N4001G - 1N4007G\n1A, 50V - 1000V Standard Rectifier')['text'], 'standard-rectifier') == {
        'VRRM': (50.0, 1000.0), 'IF_AV': (1.0, 1.0)}
    assert tv(ov('b', 'SMAJ5.0(A)H - SMAJ188(A)H\n400W, 5V - 188V Surface Mount TVS')['text'], 'tvs') == {
        'VRWM': (5.0, 188.0), 'PPPM': (400.0, 400.0)}
    assert tv(ov('c', '500mW, 2.4V - 75V Surface Mount Zener Diode\nMMELF')['text'], 'zener-diode') == {
        'VZ': (2.4, 75.0), 'PD': (0.5, 0.5)}
    # SOD-123W의 W · BZT52B2V4의 2V4는 값이 아니다. 값 없는 제목은 빈 dict
    assert tv(ov('d', 'BZT52B2V4 - BZT52B75\nSOD-123W\n2% Tolerance SMD Zener Diode')['text'], 'zener-diode') == {}


def test_code_pick_drops_contradicting_titles_and_orders_wanted_package_first():
    cond = [{'code': 'VRRM', 'gte': 400}, {'code': 'VRRM', 'lte': 600}, {'code': 'IF_AV', 'gte': 1}, {'code': 'IF_AV', 'lte': 2}]
    lines = [ov('high', 'DO-214AC (SMA)\n1A, 1600V Surface Mount Rectifier'),         # VRRM이 600 V를 넘는다
             ov('amps', 'DO-214AC (SMA)\n3A, 50V - 1000V Surface Mount Rectifier'),  # 전류가 2 A를 넘는다
             ov('smb', 'DO-214AA (SMB)\n1A, 50V - 1000V Surface Mount Rectifier'),   # 다른 패키지만 적음
             ov('nopkg', '1A, 400V ESD Capability Rectifier'),                        # 패키지 모름: 뒤로
             ov('sub', 'Sub SMA\n1A, 50V - 1000V Surface Mount Rectifier'),          # 'SMA'가 붙은 다른 이름: 맨 뒤
             ov('sma', 'S1A - S1M\n1A, 50V - 1000V Surface Mount Rectifier\nDO-214AC (SMA)')]
    assert card_find.code_pick(cond, 'SMA', lines, 'standard-rectifier') == ['sma', 'nopkg', 'sub']
    # 삽입형(DO-41)을 원하면 표면실장 제목은 버린다(패키지 · 실장 방식을 모르는 제목만 남음)
    assert card_find.code_pick(cond, 'DO-41', lines, 'standard-rectifier') == ['nopkg']


def test_code_pick_returns_none_when_titles_cannot_rank_documents():
    """제목에서 조건 코드 값을 하나도 못 읽거나, 10번째 문서도 확인한 조건이 없으면 None(LLM이 고른다)."""
    esd = [ov(f'e{i}', 'PACKAGE: DFN1006-2L\nUni-directional ESD Protection Diode') for i in range(12)]
    assert card_find.code_pick([{'code': 'VRWM', 'gte': 5}], None, esd, 'esd-protection') is None
    one = [ov('v', 'VWM=5V, 0.6pF ESD Protection Array')] + esd
    assert card_find.code_pick([{'code': 'VRWM', 'gte': 5}], None, one, 'esd-protection') is None
    assert card_find.code_pick([{'code': 'VRWM', 'gte': 5}], None, one[:5], 'esd-protection')[0] == 'v'
    assert card_find.code_pick([{'code': 'TRR', 'lte': 5e-8}], None, [ov('a', '1A, 50V - 1000V Rectifier')], 'x') is None


def test_category_find_picks_by_code_and_calls_llm_only_when_code_cannot():
    calls = []

    def chat(node, system, user, schema):
        calls.append(node)
        return schema(picks=[{'document': 'b.pdf', 'quote': 'ESD'}])
    docs = {'a': doc('a', ['SS14']), 'b': doc('b', ['X1'])}
    w = World(docs, [row('SS14', 'VRRM', 'max', 40.0)])

    def make(lines):
        return card_find.make_find(retrieve=w.retrieve, load_cards=w.load_cards, read=w.read, chat=chat, doc_meta=w.doc_meta,
                                   overviews=lambda category: lines)
    make([ov('a', '1A, 20V - 100V Schottky Rectifier'), ov('b', '1A, 10V Schottky Rectifier')])([{'code': 'VRRM', 'gte': 40}], 'schottky')
    assert calls == [] and w.calls['load'][-1] == ['a'] and w.calls['retrieve'] == []
    make([ov('a', 'Schottky Rectifier'), ov('b', 'ESD Rectifier')])([{'code': 'VRRM', 'gte': 40}], 'schottky')
    assert calls == ['card_pick'] and w.calls['load'][-1] == ['b']


def test_concurrent_gathers_for_two_packages_read_each_document_once():
    """패키지만 다른 찾기 둘이 동시에 같은 문서를 읽으려 하면 문서마다 읽기는 한 번이고, 둘 다 같은 행을 받는다(in-flight 공유)."""
    import threading
    docs = {k: doc(k, [k.upper()]) for k in 'ab'}
    w = World(docs, rows=[row('A', 'VRRM', 'max', 40.0)])
    start, release, n = threading.Barrier(2), threading.Event(), []
    plain_read = w.read

    def slow_read(cards, codes, doc_parts, *, chat):
        n.append(1)
        release.wait(2)  # 다른 gather가 같은 문서에 도착할 시간을 준다
        return plain_read(cards, codes, doc_parts, chat=chat)
    w.read = slow_read
    find = w.find()
    out = {}

    def run(pkg):
        start.wait()
        out[pkg] = find([{'code': 'VRRM', 'gte': 1}], None, pkg)
    ts = [threading.Thread(target=run, args=(p,)) for p in ('SMA', 'DO-214AC')]
    [t.start() for t in ts]
    threading.Timer(0.3, release.set).start()
    [t.join() for t in ts]
    assert len(n) == 2  # 문서 a · b 한 번씩(패키지마다 읽었다면 4)
    # 조건이 다르면(코드 목록이 다르면) 재사용하지 않는다
    find([{'code': 'VRRM', 'gte': 1}, {'code': 'IR', 'lte': 1}], None, None)
    assert len(n) == 4


def test_failed_read_is_not_cached():
    """읽기가 실패하면 결과를 남기지 않아 다음 찾기가 다시 읽는다."""
    w = World({'a': doc('a', ['A'])}, rows=[row('A', 'VRRM', 'max', 40.0)])
    ok, fail = w.read, [True]

    def flaky(cards, codes, doc_parts, *, chat):
        if fail.pop() if fail else False:
            raise RuntimeError('LLM down')
        return ok(cards, codes, doc_parts, chat=chat)
    w.read = flaky
    find = w.find()
    with pytest.raises(RuntimeError):
        find([{'code': 'VRRM', 'gte': 1}], None, None)
    assert [r['part'] for r in find([{'code': 'VRRM', 'gte': 1}], None, 'DO-214AC')] == []
    assert [r['part'] for r in find([{'code': 'VRRM', 'gte': 1}], None, None)] == ['A']

def test_shared_clear_forces_a_new_read():
    """shared를 비우면(데모 질문 사이) 읽기 재사용이 끊겨 기록과 같은 호출이 나간다."""
    docs = {'a': doc('a', ['A'])}
    w = World(docs, rows=[row('A', 'VRRM', 'max', 40.0)])
    shared = {}
    find = card_find.make_find(retrieve=w.retrieve, load_cards=w.load_cards, read=w.read, chat='C', doc_meta=w.doc_meta, shared=shared)
    find([{'code': 'VRRM', 'gte': 1}], None, None)
    find([{'code': 'VRRM', 'gte': 1}], None, 'DO-214AC')
    assert len(w.calls['read']) == 1
    shared.clear()
    find([{'code': 'VRRM', 'gte': 1}], None, 'SOD-123')
    assert len(w.calls['read']) == 2


def test_overview_lines_and_doc_caches_hit_the_db_once(monkeypatch):
    """분류별 개요 줄 · 문서 · 문서 분류는 프로세스에서 한 번만 DB로 읽는다."""
    monkeypatch.setattr(card_find, '_OVERVIEWS', {})
    monkeypatch.setattr(card_find, '_DOCS', {})
    monkeypatch.setattr(card_find, '_META', {})
    n = {'ov': 0, 'load': [], 'meta': []}
    monkeypatch.setattr(card_find, '_query_overviews', lambda c: n.__setitem__('ov', n['ov'] + 1) or [{'key': 'a', 'file': 'a.pdf', 'text': 't'}])
    monkeypatch.setattr(card_find, 'load_cards', lambda ks: n['load'].append(list(ks)) or {k: {'file': k} for k in ks})
    monkeypatch.setattr(card_find, 'doc_meta', lambda ks: n['meta'].append(list(ks)) or {k: {'category': 'c'} for k in ks})
    assert card_find.overview_lines('c') == card_find.overview_lines('c') and n['ov'] == 1
    assert card_find.cached_load_cards(['a', 'b']) == {'a': {'file': 'a'}, 'b': {'file': 'b'}}
    assert card_find.cached_load_cards(['b', 'c', 'a']) == {'b': {'file': 'b'}, 'c': {'file': 'c'}, 'a': {'file': 'a'}}
    assert n['load'] == [['a', 'b'], ['c']]
    card_find.cached_doc_meta(['a']); card_find.cached_doc_meta(['a', 'b'])
    assert n['meta'] == [['a'], ['b']]
    monkeypatch.setattr(card_find, 'MAX_CACHED_DOCS', 2)
    card_find.cached_load_cards(['x', 'y', 'z'])
    assert len(card_find._DOCS) <= 3 and 'z' in card_find._DOCS  # 상한을 넘기면 오래된 것부터 버린다
