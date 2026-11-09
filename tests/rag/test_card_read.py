"""카드 읽기(`backend.rag.card_read.read_values`)를 가짜 chat으로 확인한다.

- 역할: LLM이 낸 읽기를 코드가 카드 글과 대조해 받거나(사양 행 모양 · SI 값) 사유와 함께 버리는지 본다.
  인용이 카드에 없음, 숫자가 인용에 없음, 단위 차원이 다름, 품번 없는 정격 행, 다른 문서 품번, mA → A, chat 한 번 호출.
- 하지 않는 일: 실제 LLM 호출(가짜 chat만 쓴다), 카드 찾기, 판정.
- 출처: backend/rag/card_read.py, backend/rag/spec_lookup.py `_row`
"""
import pytest

from backend.rag.card_read import CardRead, Reading, read_values
from backend.services.llm import node_model

SS14, SMC, RATING = 'SS14ALH SERIES_B2103.pdf', '5KSMC SERIES_A2201.pdf', '1N4148W SERIES_C1901.pdf'
CARDS = [
    {'chunk_id': 11, 'document': SS14, 'page': 2, 'table': 'ELECTRICAL SPECIFICATIONS', 'row': 'Reverse current',
     'content': f'[{SS14} · 2쪽 · ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)] PARAMETER: Reverse current @ rated VR(2)'
                ' | PARAMETER: SS14ALH SS16ALH | CONDITIONS: TJ = 25°C | SYMBOL: IR | TYP: - | MAX: 100 | UNIT: µA'},
    {'chunk_id': 12, 'document': SMC, 'page': 3, 'table': 'ELECTRICAL CHARACTERISTICS', 'row': '5KSMC78CAH',
     'content': f'[{SMC} · 3쪽 · ELECTRICAL CHARACTERISTICS] Part number: 5KSMC78CAH | Marking code: 5K78A'
                ' | IR max at VWM / µA: 1 | IR max at VWM / V: 78 | VBR at IT(1) / Min / V: 86.7'},
    {'chunk_id': 13, 'document': RATING, 'page': 1, 'table': 'MAXIMUM RATINGS', 'row': 'Repetitive peak reverse voltage',
     'content': f'[{RATING} · 1쪽 · MAXIMUM RATINGS] PARAMETER: Repetitive peak reverse voltage | SYMBOL: VRRM | VALUE: 75 | UNIT: V'},
    {'chunk_id': 14, 'document': RATING, 'page': 1, 'table': 'MAXIMUM RATINGS', 'row': 'Forward current',
     'content': f'[{RATING} · 1쪽 · MAXIMUM RATINGS] PARAMETER: Forward continuous current | SYMBOL: IF | VALUE: 150 | UNIT: mA'},
]
DOC_PARTS = {SS14: ['SS14ALH', 'SS16ALH'], SMC: ['5KSMC78CAH'], RATING: ['1N4148W', '1N4148WS']}
CODES = ['VRRM', 'VBR', 'IR', 'IF_AV']


def reading(**kw):
    base = {'part': '5KSMC78CAH', 'code': 'VBR', 'slot': 'min', 'value': '86.7', 'unit': 'V', 'condition': '',
            'quote': 'VBR at IT(1) / Min / V: 86.7', 'chunk_id': 12}
    return Reading(**{**base, **kw})


def run(*readings):
    """가짜 chat이 주어진 읽기를 돌려주고, 부른 인자를 기록한다."""
    calls = []

    def chat(node, system, user, schema):
        calls.append((node, system, user, schema))
        return CardRead(readings=list(readings))
    rows, rejected = read_values(CARDS, CODES, DOC_PARTS, chat=chat)
    return rows, rejected, calls


def test_accepted_reading_gives_spec_row_shape():
    rows, rejected, _ = run(reading())
    assert rejected == []
    assert rows == [{'part': '5KSMC78CAH', 'category': None, 'code': 'VBR', 'min': 86.7, 'typ': None, 'max': None,
                     'text': None, 'unit': 'V', 'source_value_text': '86.7 V', 'test_condition': None,
                     'citation': {'document': SMC, 'page': 3, 'table': 'ELECTRICAL CHARACTERISTICS', 'row': '5KSMC78CAH',
                                  'chunk_index': None, 'chunk_id': 12},
                     'quote': 'VBR at IT(1) / Min / V: 86.7'}]


def test_merged_group_cell_and_micro_to_si():
    """'SS14ALH SS16ALH' 머리 칸은 두 품번 모두에 붙고, µA는 A로(유효숫자 12자리라 1e-4 그대로)."""
    quote = 'SYMBOL: IR | TYP: - | MAX: 100 | UNIT: µA'
    rows, rejected, _ = run(*(reading(part=p, code='IR', slot='max', value='100', unit='µA', condition='TJ = 25°C',
                                      quote=quote, chunk_id=11) for p in ('SS14ALH', 'SS16ALH')))
    assert rejected == [] and [r['part'] for r in rows] == ['SS14ALH', 'SS16ALH']
    assert rows[0]['max'] == 0.0001 and rows[0]['unit'] == 'A' and rows[0]['test_condition'] == 'TJ = 25°C'


def test_quote_not_in_card_is_rejected():
    _, rejected, _ = run(reading(quote='VBR min 86.7 V'))
    assert [r['reason'] for r in rejected] == ['quote_not_in_card']
    assert rejected[0]['part'] == '5KSMC78CAH' and rejected[0]['value'] == '86.7'  # 읽은 값을 그대로 남긴다


def test_quote_whitespace_and_micro_sign_are_normalized():
    rows, rejected, _ = run(reading(code='IR', slot='max', value='1', unit='µA', quote='IR max  at\nVWM / μA: 1'))
    assert rejected == [] and rows[0]['max'] == 1e-6


def test_number_not_in_quote_is_rejected():
    _, rejected, _ = run(reading(value='87.6'))
    assert [r['reason'] for r in rejected] == ['value_not_in_quote']


def test_footnote_digit_is_not_the_value():
    """'IT(1)'의 1만 있는 인용으로 값 1을 받지 않도록, 숫자는 인용 안의 숫자 토큰과 같아야 한다(86.7의 일부 '8'도 안 됨)."""
    _, rejected, _ = run(reading(value='8'))
    assert [r['reason'] for r in rejected] == ['value_not_in_quote']


def test_wrong_unit_dimension_is_rejected():
    _, rejected, _ = run(reading(part='1N4148W', code='VRRM', slot='max', value='75', unit='mA', quote='VALUE: 75', chunk_id=13))
    assert [r['reason'] for r in rejected] == ['unit_dimension']


def test_document_wide_rating_row_applies_to_document_parts():
    rows, rejected, _ = run(reading(part='1N4148WS', code='VRRM', slot='max', value='75', unit='V', quote='VALUE: 75 | UNIT: V', chunk_id=13))
    assert rejected == [] and rows[0]['part'] == '1N4148WS' and rows[0]['max'] == 75.0


def test_part_of_another_document_is_rejected():
    _, rejected, _ = run(reading(part='SS14ALH', code='VRRM', slot='max', value='75', unit='V', quote='VALUE: 75', chunk_id=13))
    assert [r['reason'] for r in rejected] == ['part_not_in_document']


def test_part_not_named_in_card_that_names_other_parts_is_rejected():
    """카드가 그 문서 품번(5KSMC78CAH)을 적었으면 다른 품번에 붙이지 않는다. SS14는 SS14ALH에 걸리지 않는다."""
    _, rejected, _ = run(reading(part='5KSMC78CA'), reading(part='SS14', code='IR', slot='max', value='100', unit='µA',
                                                            quote='MAX: 100', chunk_id=11))
    assert [r['reason'] for r in rejected] == ['part_not_in_card', 'part_not_in_card']


def test_milliamp_converts_to_amp():
    rows, rejected, _ = run(reading(part='1N4148W', code='IF_AV', slot='max', value='150', unit='mA',
                                    quote='VALUE: 150 | UNIT: mA', chunk_id=14))
    assert rejected == [] and rows[0]['max'] == 0.15 and rows[0]['unit'] == 'A'
    assert rows[0]['source_value_text'] == '150 mA'


@pytest.mark.parametrize('kw, reason', [({'chunk_id': 99}, 'chunk_not_given'), ({'code': 'VZ'}, 'code_not_asked'),
                                        ({'unit': 'Vx'}, 'unit_unknown')])
def test_other_rejections(kw, reason):
    _, rejected, _ = run(reading(**kw))
    assert [r['reason'] for r in rejected] == [reason]


def test_chat_called_once_with_card_read_node():
    _, _, calls = run(reading(), reading(code='IR', slot='max', value='1', unit='µA', quote='IR max at VWM / µA: 1'))
    assert len(calls) == 1
    node, system, user, schema = calls[0]
    assert node == 'card_read' and schema is CardRead and 'TSTG' in system
    assert all(f"[chunk_id={c['chunk_id']}]" in user for c in CARDS) and SMC in user
    assert node_model('card_read')  # 노드별 모델 표에 등록되어 있다


def test_no_cards_means_no_call():
    calls = []
    assert read_values([], CODES, DOC_PARTS, chat=lambda *a: calls.append(a)) == ([], [])
    assert calls == []


def test_group_cell_and_document_wide_row_are_written_once_and_expanded():
    # [왜] 묶음 칸 · 문서 전체 정격을 품번마다 한 줄씩 쓰면 계열 문서에서 출력 상한에 잘린다. LLM은 한 줄로 쓰고 코드가 펼친다
    rows, rejected, _ = run(reading(part='SS14ALH, SS16ALH', code='IR', slot='max', value='100', unit='µA', condition='TJ = 25°C',
                                    quote='CONDITIONS: TJ = 25°C | SYMBOL: IR | TYP: - | MAX: 100', chunk_id=11),
                            reading(part='*', code='VRRM', slot='max', value='75', unit='V', quote='VALUE: 75 | UNIT: V', chunk_id=13))
    assert rejected == [] and sorted(r['part'] for r in rows) == ['1N4148W', '1N4148WS', 'SS14ALH', 'SS16ALH']


def test_star_on_card_that_names_parts_keeps_only_named_parts():
    # '*'를 품번을 적은 카드에 쓰면, 문서 품번 중 그 카드에 없는 품번(SS110ALH)은 버리고 적힌 품번만 받는다
    def chat(node, system, user, schema):
        return CardRead(readings=[reading(part='*', code='IR', slot='max', value='100', unit='µA', quote='MAX: 100 | UNIT: µA', chunk_id=11)])
    rows, rejected = read_values(CARDS, CODES, {**DOC_PARTS, SS14: ['SS14ALH', 'SS16ALH', 'SS110ALH']}, chat=chat)
    assert [r['part'] for r in rows] == ['SS14ALH', 'SS16ALH']
    assert [(r['part'], r['reason']) for r in rejected] == [('SS110ALH', 'part_not_in_card')]


def test_unit_not_printed_in_card_is_rejected():
    # [왜] 차원만 보면 µA를 mA로 잘못 적어도 통과해 1000배 틀린 값이 된다. 적은 단위 글자가 카드에 있어야 한다
    _, rejected, _ = run(reading(part='SS14ALH', code='IR', slot='max', value='100', unit='mA', quote='MAX: 100', chunk_id=11))
    assert rejected[0]['reason'] == 'unit_not_in_card'


def test_series_range_in_document_wide_row_is_rejected():
    # [왜] 'VRWM | VALUE: 5.5 - 171'은 계열 전체 범위다. 품번 값으로 붙이면 양방향 품번이 조건에서 떨어졌다(h4-15, 11-09)
    card = {'chunk_id': 21, 'document': RATING, 'page': 1, 'table': 'KEY PARAMETERS', 'row': 'VRWM',
            'content': f'[{RATING} · 1쪽 · KEY PARAMETERS] PARAMETER: VRWM | VALUE: 5.5 - 171 | UNIT: V'}

    def chat(node, system, user, schema):
        return CardRead(readings=[reading(part='*', code='VRRM', slot='max', value='171', unit='V', quote='VALUE: 5.5 - 171 | UNIT: V', chunk_id=21),
                                  reading(part='*', code='VRRM', slot='min', value='5.5', unit='V', quote='VALUE: 5.5 - 171', chunk_id=21)])
    rows, rejected = read_values([card], CODES, DOC_PARTS, chat=chat)
    assert rows == [] and {r['reason'] for r in rejected} == {'series_range'}


def test_many_cards_are_read_in_batches_and_merged():
    """카드가 BATCH장보다 많으면 나눠 부르고(호출마다 BATCH장 이하), 각 호출의 읽기를 빠짐없이 합친다."""
    import re
    from backend.rag import card_read
    cards = [{**CARDS[2], 'chunk_id': 100 + i} for i in range(card_read.BATCH * 2 + 1)]
    calls = []

    def chat(node, system, user, schema):
        ids = [int(x) for x in re.findall(r'\[chunk_id=(\d+)\]', user)]
        calls.append(ids)
        return CardRead(readings=[Reading(part='1N4148W', code='VRRM', slot='max', value='75', unit='V', condition='',
                                          quote='VALUE: 75', chunk_id=i) for i in ids])
    rows, rejected = read_values(cards, ['VRRM'], DOC_PARTS, chat=chat)
    assert len(calls) == 3 and all(len(ids) <= card_read.BATCH for ids in calls)
    assert sorted(r['citation']['chunk_id'] for r in rows) == [c['chunk_id'] for c in cards] and not rejected


def test_a_batch_that_keeps_breaking_format_is_skipped_not_fatal():
    """묶음 하나가 형식을 끝내 어기면(chat이 ValueError) 그 묶음만 빼고 나머지 묶음의 값은 받는다."""
    import re
    from backend.rag import card_read
    cards = [{**CARDS[2], 'chunk_id': 200 + i} for i in range(card_read.BATCH * 2)]

    def chat(node, system, user, schema):
        ids = [int(x) for x in re.findall(r'\[chunk_id=(\d+)\]', user)]
        if 200 in ids:
            raise ValueError('LLM 출력이 CardRead 형식을 3번 모두 어겼다')
        return CardRead(readings=[Reading(part='1N4148W', code='VRRM', slot='max', value='75', unit='V', condition='',
                                          quote='VALUE: 75', chunk_id=i) for i in ids])
    rows, rejected = read_values(cards, ['VRRM'], DOC_PARTS, chat=chat)
    assert len(rows) == card_read.BATCH and all(r['citation']['chunk_id'] >= 200 + card_read.BATCH for r in rows)
    assert [x['reason'] for x in rejected] == ['read_format_failed']


def test_a_long_group_cell_part_list_is_accepted():
    """묶음 칸 품번 목록이 400자를 넘어도 형식 검사에서 거절하지 않는다(제너 묶음 칸, v3-13)."""
    long_list = ', '.join(f'MMSZ52{i:02d}BH' for i in range(21, 68))
    assert len(long_list) > 400
    assert Reading(part=long_list, code='VZ', slot='typ', value='3.3', unit='V', condition='', quote='3.3', chunk_id=1).part == long_list
