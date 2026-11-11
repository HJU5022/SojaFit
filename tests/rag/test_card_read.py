"""카드 읽기(`backend.rag.card_read`)를 가짜 chat으로 확인한다.

- 역할: (1) LLM 읽기(`llm_read`): LLM이 낸 읽기를 코드가 카드 글과 대조해 받거나(사양 행 모양 · SI 값) 사유와 함께 버리는지 본다.
  인용이 카드에 없음, 숫자가 인용에 없음, 단위 차원이 다름, 품번 없는 정격 행, 다른 문서 품번, mA → A, chat 한 번 호출.
  (2) 코드 먼저(`read_values`): 로컬 DB `sojafit_v4`의 실제 카드 글로, 코드가 읽는 모양은 LLM을 부르지 않고 LLM 읽기와 같은 행을 내는지,
  읽을 값이 없는 행은 어디에도 보내지 않는지, 코드가 못 읽는 모양(여러 값 칸 · 앞 머리의 공칭 표시 · 가운데 머리의 Min · (C) 품번 ·
  일부 품번 전용 · 모르는 단위)은 그 카드만 LLM에 보내는지 본다.
- 하지 않는 일: 실제 LLM · DB 호출(가짜 chat, 카드 글은 옮겨 둔 것), 카드 찾기, 판정.
- 출처: backend/rag/card_read.py, backend/rag/spec_lookup.py `_row`, 사전 등록 #43
"""
import pytest

from backend.rag.card_read import SI, CardRead, Reading, llm_read, read_values
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
    rows, rejected = llm_read(CARDS, CODES, DOC_PARTS, chat=chat)
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
    assert llm_read([], CODES, DOC_PARTS, chat=lambda *a: calls.append(a)) == ([], [])
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
    rows, rejected = llm_read(CARDS, CODES, {**DOC_PARTS, SS14: ['SS14ALH', 'SS16ALH', 'SS110ALH']}, chat=chat)
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
    rows, rejected = llm_read([card], CODES, DOC_PARTS, chat=chat)
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
    rows, rejected = llm_read(cards, ['VRRM'], DOC_PARTS, chat=chat)
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
    rows, rejected = llm_read(cards, ['VRRM'], DOC_PARTS, chat=chat)
    assert len(rows) == card_read.BATCH and all(r['citation']['chunk_id'] >= 200 + card_read.BATCH for r in rows)
    assert [x['reason'] for x in rejected] == ['read_format_failed']


def test_a_long_group_cell_part_list_is_accepted():
    """묶음 칸 품번 목록이 400자를 넘어도 형식 검사에서 거절하지 않는다(제너 묶음 칸, v3-13)."""
    long_list = ', '.join(f'MMSZ52{i:02d}BH' for i in range(21, 68))
    assert len(long_list) > 400
    assert Reading(part=long_list, code='VZ', slot='typ', value='3.3', unit='V', condition='', quote='3.3', chunk_id=1).part == long_list


# ---- 코드 먼저 읽기(read_values): 로컬 DB sojafit_v4의 실제 카드 글(11-09에 옮김) ----
TOP = 'ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)'
ELEC = 'ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)'
ALL = list(SI)  # 코드 17종 전부


def real(chunk_id, document, page, table, row, body):
    """DB 카드 한 장(load_cards 모양). 글은 '[파일 · 쪽 · 표] 머리: 값 | …' 그대로다."""
    return {'chunk_id': chunk_id, 'document': document, 'page': page, 'table': table, 'row': row,
            'content': f'[{document} · {page}쪽 · {table}] {body}'}


SS14_PARTS = {'SS14ALH SERIES_B2103.pdf': ['SS110ALH', 'SS115ALH', 'SS120ALH', 'SS14ALH', 'SS16ALH']}
SS14_IR = real(36639, 'SS14ALH SERIES_B2103.pdf', 2, ELEC, 'Reverse current @ rated VR(2)',
               'PARAMETER: Reverse current @ rated VR(2) | PARAMETER: SS14ALH SS16ALH | CONDITIONS: TJ = 25°C | SYMBOL: IR | TYP: - | MAX: 100'
               ' | UNIT: µA\n주: 2. Pulse test with PW = 30ms')
SS14_VF = real(36620, 'SS14ALH SERIES_B2103.pdf', 2, ELEC, 'Forward voltage(1)',
               'PARAMETER: Forward voltage(1) | PARAMETER: SS14ALH | CONDITIONS: IF = 1.0A, TJ = 25°C | SYMBOL: VF | TYP: 0.44 | MAX: 0.55'
               ' | UNIT: V\n주: 1. Pulse test with PW = 0.3ms')
SS14_TJ = real(36613, 'SS14ALH SERIES_B2103.pdf', 1, TOP, 'Junction temperature',
               'PARAMETER: Junction temperature | SYMBOL: TJ | SS14 ALH: -55 to +150 | SS16 ALH: -55 to +150 | SS110 ALH: -55 to +150'
               ' | SS115 ALH: -55 to +150 | SS120 ALH: -55 to +150 | UNIT: °C')
W4148_PARTS = {'1N4148W SERIES_K1804.pdf': ['1N4148W', '1N4448W', '1N914BW']}
W4148_VRRM = real(643, '1N4148W SERIES_K1804.pdf', 1, TOP, 'Repetitive peak reverse voltage',
                  'PARAMETER: Repetitive peak reverse voltage | SYMBOL: VRRM | VALUE: 75 | UNIT: V')
MBR_PARTS = {'MBR1035CT SERIES_O2104.pdf': ['MBR10100CT', 'MBR10150CT', 'MBR10200CT', 'MBR1035CT', 'MBR1045CT', 'MBR1050CT', 'MBR1060CT',
                                           'MBR1090CT']}
MBR_IF = real(14974, 'MBR1035CT SERIES_O2104.pdf', 1, TOP, 'Forward current',
              'PARAMETER: Forward current | SYMBOL: IF | MBR 1035 CT: 10 | MBR 1045 CT: 10 | MBR 1050 CT: 10 | MBR 1060 CT: 10'
              ' | MBR 1090 CT: 10 | MBR 10100 CT: 10 | MBR 10150 CT: 10 | MBR 10200 CT: 10 | UNIT: A')
MMSZ_PARTS = {'MMSZ5221B SERIES_I2503.pdf': ['MMSZ5231B', 'MMSZ5232B']}
MMSZ = real(19739, 'MMSZ5221B SERIES_I2503.pdf', 2, ELEC, 'MMSZ5231B',
            'PART NUMBER: MMSZ5231B | MARKING CODE: Z5V1 | ZENER VOLTAGE / VZ @ IZT / V / Min: 4.85 | ZENER VOLTAGE / VZ @ IZT / V / Nom: 5.1'
            ' | ZENER VOLTAGE / VZ @ IZT / V / Max: 5.36 | TEST CURRENT / IZT / mA: 20 | REGULAR IMPEDANCE / ZZT @ IZT / Ω / Max: 17'
            ' | REGULAR IMPEDANCE / ZZK @ IZK / Ω / Max: 1600 | TEST CURRENT / IZK / mA: 0.25 | LEAKAGE CURRENT / IR @ VR / µA / Max: 5'
            ' | LEAKAGE CURRENT / IR @ VR / V: 2')
SMBJ_PARTS = {'SMBJ SERIES_R2104.pdf': ['SMBJ14A', 'SMBJ14CA']}
SMBJ = real(33939, 'SMBJ SERIES_R2104.pdf', 2, ELEC, 'SMBJ14A',
            'Part number: SMBJ14A | Marking code: LK | Breakdown voltage VBR@IT (V) (Note 1) / Min: 15.6'
            ' | Breakdown voltage VBR@IT (V) (Note 1) / Max: 17.2 | Test current IT (mA): 1 | Working stand-off voltage VWM (V): 14'
            ' | Maximum blocking leakage current ID@VWM (µA): 1 | Maximum peak impulse current IPP (A) (Note 2): 27.0'
            ' | Maximum clamping voltage VC@IPP (V): 23.2')


def no_llm(*a):
    raise AssertionError('코드가 읽는 카드인데 LLM을 불렀다')


def got(rows):
    """비교하기 쉬운 모양: (품번, 코드, 칸, 값, 조건, 인용)."""
    return [(r['part'], r['code'], next(s for s in ('min', 'typ', 'max') if r[s] is not None),
             next(r[s] for s in ('min', 'typ', 'max') if r[s] is not None), r['test_condition'], r['quote']) for r in rows]


@pytest.mark.parametrize('card, parts, want', [
    # 묶음 칸 품번 둘 · '@ rated VR'과 CONDITIONS 칸 조건 · µA → A
    (SS14_IR, SS14_PARTS, [('SS14ALH', 'IR', 'max', 1e-4, '@ rated VR; TJ = 25°C', 'MAX: 100'),
                           ('SS16ALH', 'IR', 'max', 1e-4, '@ rated VR; TJ = 25°C', 'MAX: 100')]),
    # TYP · MAX 칸
    (SS14_VF, SS14_PARTS, [('SS14ALH', 'VF', 'typ', 0.44, 'IF = 1.0A, TJ = 25°C', 'TYP: 0.44'),
                           ('SS14ALH', 'VF', 'max', 0.55, 'IF = 1.0A, TJ = 25°C', 'MAX: 0.55')]),
    # 품번 없는 정격 행은 그 문서 품번 모두
    (W4148_VRRM, W4148_PARTS, [(p, 'VRRM', 'max', 75.0, None, 'VALUE: 75') for p in ('1N4148W', '1N4448W', '1N914BW')]),
    # 품번 열(띄어 쓴 품번) · 같은 값이 든 다른 품번 열을 인용하지 않는다
    (MBR_IF, MBR_PARTS, [(p, 'IF_AV', 'max', 10.0, None, f"{p[:3]} {p[3:-2]} CT: 10") for p in
                         ('MBR1035CT', 'MBR1045CT', 'MBR1050CT', 'MBR1060CT', 'MBR1090CT', 'MBR10100CT', 'MBR10150CT', 'MBR10200CT')]),
    # 온도 범위는 최소 · 최대 두 줄
    (SS14_TJ, {'SS14ALH SERIES_B2103.pdf': ['SS14ALH']}, [('SS14ALH', 'TJ_MAX', 'min', -55.0, None, 'SS14 ALH: -55 to +150'),
                                                          ('SS14ALH', 'TJ_MAX', 'max', 150.0, None, 'SS14 ALH: -55 to +150')]),
    # 품번 한 줄 제너 표: Min · Nom · Max와 같은 행 시험 전류 조건, IR 칸의 시험 전압
    (MMSZ, MMSZ_PARTS, [('MMSZ5231B', 'VZ', 'min', 4.85, 'IZT = 20 mA', 'ZENER VOLTAGE / VZ @ IZT / V / Min: 4.85'),
                        ('MMSZ5231B', 'VZ', 'typ', 5.1, 'IZT = 20 mA', 'ZENER VOLTAGE / VZ @ IZT / V / Nom: 5.1'),
                        ('MMSZ5231B', 'VZ', 'max', 5.36, 'IZT = 20 mA', 'ZENER VOLTAGE / VZ @ IZT / V / Max: 5.36'),
                        ('MMSZ5231B', 'IR', 'max', 5e-6, 'VR = 2 V', 'LEAKAGE CURRENT / IR @ VR / µA / Max: 5')]),
    # 품번 한 줄 TVS 표: IR 1 µA는 'Test current IT (mA): 1'이 아니라 누설 전류 칸을 인용한다
    (SMBJ, SMBJ_PARTS, [('SMBJ14A', 'VBR', 'min', 15.6, 'IT = 1 mA', 'Breakdown voltage VBR@IT (V) (Note 1) / Min: 15.6'),
                        ('SMBJ14A', 'VBR', 'max', 17.2, 'IT = 1 mA', 'Breakdown voltage VBR@IT (V) (Note 1) / Max: 17.2'),
                        ('SMBJ14A', 'VRWM', 'max', 14.0, None, 'Working stand-off voltage VWM (V): 14'),
                        ('SMBJ14A', 'IR', 'max', 1e-6, 'VWM = 14 V', 'Maximum blocking leakage current ID@VWM (µA): 1'),
                        ('SMBJ14A', 'IPP', 'max', 27.0, None, 'Maximum peak impulse current IPP (A) (Note 2): 27.0'),
                        ('SMBJ14A', 'VC', 'max', 23.2, 'IPP = 27.0 A', 'Maximum clamping voltage VC@IPP (V): 23.2')]),
])
def test_code_reads_clean_cards_without_llm(card, parts, want):
    rows, rejected = read_values([card], ALL, parts, chat=no_llm)
    assert rejected == []
    assert got(rows) == [(*w[:3], pytest.approx(w[3]), *w[4:]) for w in want]
    assert all(r['citation']['chunk_id'] == card['chunk_id'] for r in rows)


def test_code_row_is_the_same_row_the_llm_path_gives():
    """같은 값을 LLM이 읽어 확인을 거친 행과 코드가 읽은 행이 칸 하나까지 같다(판정 · 찾기가 바뀌지 않는다)."""
    code_rows, _ = read_values([SS14_IR], ['IR'], SS14_PARTS, chat=no_llm)
    llm = Reading(part='SS14ALH, SS16ALH', code='IR', slot='max', value='100', unit='µA', condition='@ rated VR; TJ = 25°C',
                  quote='MAX: 100', chunk_id=SS14_IR['chunk_id'])
    llm_rows, _ = llm_read([SS14_IR], ['IR'], SS14_PARTS, chat=lambda *a: CardRead(readings=[llm]))
    assert code_rows == llm_rows


@pytest.mark.parametrize('card, parts, codes', [
    # 프롬프트가 읽지 말라는 실효값 행(VR(RMS))
    (real(564, '1N4001G-K SERIES_B2104.pdf', 1, TOP, 'Reverse voltage, total rms value',
          'PARAMETER: Reverse voltage, total rms value | SYMBOL: VR(RMS) | 1N 4001G -K: 35 | 1N 4002G -K: 70 | UNIT: V'),
     {'1N4001G-K SERIES_B2104.pdf': ['1N4001G-K', '1N4002G-K']}, ['VR', 'VRRM']),
    # 원하지 않는 코드의 행(VF 행의 조건 'IF = 1.0A'가 IF_AV 낱말에 걸려 넘어온다)
    (SS14_VF, SS14_PARTS, ['IF_AV']),
    # 품번 없는 계열 범위
    (real(21, RATING, 1, 'KEY PARAMETERS', 'VRWM', 'PARAMETER: VRWM | VALUE: 5.5 - 171 | UNIT: V'), DOC_PARTS, ['VRWM']),
])
def test_rows_with_nothing_to_read_go_nowhere(card, parts, codes):
    assert read_values([card], codes, parts, chat=no_llm) == ([], [])


@pytest.mark.parametrize('card, parts', [
    # 한 칸에 값 여럿(TJ MAX: 125, 150 · IF: 20 / 40)
    (real(30880, 'SBS34 SERIES_F2103.pdf', 1, TOP, 'TJ MAX', 'PARAMETER: TJ MAX | VALUE: 125, 150 | UNIT: °C'),
     {'SBS34 SERIES_F2103.pdf': ['SBS34', 'SBS36']}),
    (real(43523, 'TSCDH40065G1_A2404.pdf', 1, TOP, 'Continuous Rectified Forward Current @ TJ = 156°C per leg / per device',
          'PARAMETER: Continuous Rectified Forward Current @ TJ = 156°C per leg / per device | SYMBOL: IF | VALUE: 20 / 40 | UNIT: A'),
     {'TSCDH40065G1_A2404.pdf': ['TSCDH40065G1']}),
    # 공칭 표시가 앞 머리에 있음(Nominal Zener voltage / VZ @ IZ / V)
    (real(1630, '1SMA4737 SERIES_P2102.pdf', 2, ELEC, '1SMA4737',
          'Part number (Note 1): 1SMA4737 | Marking code: 737A | Nominal Zener voltage / VZ @ IZ / V / (Note 2) (Note 3): 7.5'
          ' | Test current / IZT / mA: 34 | Zener Impedance / ZZT @ IZT / Ω: 4 | Leakage current / IR @ VR / µA / Max: 5'
          ' | Leakage current / IR @ VR / V: 5.0 | Surge current / IR / mA: 605'),
     {'1SMA4737 SERIES_P2102.pdf': ['1SMA4737']}),
    # VBR의 Min이 가운데 머리(VBR at IT(1) / Min / V)
    (real(2514, '5KSMC10(C)AH SERIES_B2509.pdf', 2, ELEC, '5KSMC10AH',
          'Part number (Uni-directional): 5KSMC10AH | Marking code: 5K10A | IR max at VWM / µA: 5 | IR max at VWM / V: 10'
          ' | VBR at IT(1) / Min / V: 11.4 | VBR at IT(1) / Typ / V: 12.0 | VBR at IT(1) / Max / mA: 12.6 | VBR at IT(1) / IT / mA: 1'),
     {'5KSMC10(C)AH SERIES_B2509.pdf': ['5KSMC10AH', '5KSMC10CAH']}),
    # (C)로 적은 품번(1V5KE6V8(C)A)
    (real(2110, '1V5KE SERIES_D2112.pdf', 2, ELEC, '1N6267A',
          'JEDEC type number: 1N6267A | Uni-directional Bi-directional (C) Device: 1V5KE6V8(C)A | Breakdown voltage VBR@IT (V) / Min: 6.45'
          ' | Breakdown voltage VBR@IT (V) / Max: 7.14 | Test current IT (mA): 10 | Reverse stand-Off voltage VRWM (V): 5.80'),
     {'1V5KE SERIES_D2112.pdf': ['1V5KE6V8A', '1V5KE6V8CA']}),
    # 대상 품번이 불분명(for Uni-directional only)
    (real(14, '1.5KE SERIES_O2104.pdf', 1, TOP, 'Peak forward surge current, 8.3ms single half sine-wave superimposed on rated load'
          ' for Uni-directional only', 'PARAMETER: Peak forward surge current, 8.3ms single half sine-wave superimposed on rated load'
          ' for Uni-directional only | SYMBOL: IFSM | VALUE: 200 | UNIT: A'),
     {'1.5KE SERIES_O2104.pdf': ['1.5KE10', '1.5KE10A']}),
    # 모르는 단위(mW/°C)
    (real(918, '1N4740A SERIES_O2104.pdf', 1, TOP, 'Derate above 50°C(1)',
          'PARAMETER: Derate above 50°C(1) | SYMBOL: Ptot | VALUE: 6.67 | UNIT: mW/°C\n주: Mounted on Cu-Pad size 5mm x 5mm'),
     {'1N4740A SERIES_O2104.pdf': ['1N4740A', '1N4740AH']}),
])
def test_shapes_code_cannot_read_go_to_llm(card, parts):
    import re
    sent = []

    def chat(node, system, user, schema):
        sent.append([int(x) for x in re.findall(r'\[chunk_id=(\d+)\]', user)])
        return CardRead()
    # [왜] 코드가 읽는 카드(W4148_VRRM)와 섞어 넘겨도 LLM에는 못 읽는 카드 한 장만 간다
    rows, _ = read_values([card, W4148_VRRM], ALL, {**parts, **W4148_PARTS}, chat=chat)
    assert sent == [[card['chunk_id']]]
    assert {r['code'] for r in rows} == {'VRRM'}


def test_llm_fallback_rows_are_checked_and_kept_in_card_order():
    """LLM이 읽은 카드의 값도 같은 확인을 거치고, 행은 카드 순서(LLM 카드가 앞이면 앞)로 돌려준다."""
    tj = real(30880, 'SBS34 SERIES_F2103.pdf', 1, TOP, 'TJ MAX', 'PARAMETER: TJ MAX | VALUE: 125, 150 | UNIT: °C')
    parts = {'SBS34 SERIES_F2103.pdf': ['SBS34', 'SBS36'], **W4148_PARTS}

    def chat(node, system, user, schema):
        return CardRead(readings=[Reading(part='SBS36', code='TJ_MAX', slot='max', value='150', unit='°C', quote='VALUE: 125, 150', chunk_id=30880),
                                  Reading(part='SBS34', code='TJ_MAX', slot='max', value='175', unit='°C', quote='VALUE: 125, 150', chunk_id=30880)])
    rows, rejected = read_values([tj, W4148_VRRM], ['TJ_MAX', 'VRRM'], parts, chat=chat)
    assert [(r['part'], r['code']) for r in rows] == [('SBS36', 'TJ_MAX'), ('1N4148W', 'VRRM'), ('1N4448W', 'VRRM'), ('1N914BW', 'VRRM')]
    assert [(r['part'], r['reason']) for r in rejected] == [('SBS34', 'value_not_in_quote')]
