"""Spec 에이전트(backend/multi_agent/agents/judge.py) 시험: 가짜 LLM · 가짜 사양 표로 읽기 · 숫자 확인 · 인터럽트 · 판정을 본다.

- 역할: AC-02(질문에 없는 숫자는 버림) · AC-07(other) · AC-08(인터럽트 1번) · AC-09(비교는 verdict에서만), 찾기 흐름.
- 하지 않는 일: 실제 LLM · MCP · DB 호출.
- 출처: docs/specs/judge-agent.md What · How · AC
"""
import pytest

from backend.judge import conditions as C
from backend.judge import verdict as V
from backend.multi_agent.agents import judge as J
from backend.services.exa import SearchBudgetExhausted

STATE = {'question': 'D1을 TSC 1N5817로 바꿔도 역극성 보호용으로 쓸 수 있어?',
         'conditions': '입력 전압의 최댓값은 20V, D1의 최대 순방향 전류는 150mA이다. 주변 온도는 25°C이다.',
         'target': 'D1', 'target_part': {'ref': 'D1', 'value': '1N4001', 'footprint': 'Diode_THT:D_DO-41_SOD81_P10.16mm',
                                         'nets': [{'name': 'RAW', 'nodes': ['D1.K(1N4001)', 'F1.1(500mA)'], 'more': 0}]},
         'question_type': 'candidate_judge'}

def test_judge_read_calls_llm_once_with_roles_and_circuit():
    seen = []

    def chat(node, system, user, schema):
        seen.append((node, user))
        return J.JudgeRead(role='R01', role_evidence=['D1.K → RAW'])
    out = J.judge_read_agent(STATE, chat=chat)
    assert len(seen) == 1 and seen[0][0] == 'judge_read'
    assert 'R01' in seen[0][1] and 'D1.K(1N4001)' in seen[0][1] and '150mA' in seen[0][1]
    assert out['judge_read']['role'] == 'R01' and out['path'] == ['판정 읽기']


def test_read_is_single_and_env_votes_change_nothing(monkeypatch):
    """[왜] 3번 다수결을 없앴다(단일 읽기 + 품번 바로잡기가 정확도 같음, v3 50문항 50/50). 옛 환경값을 줘도 읽기는 한 번이다."""
    monkeypatch.setenv('JUDGE_READ_VOTES', '3')
    monkeypatch.setenv('LAB_READ_VOTES', '3')
    calls = []

    def chat(node, system, user, schema):
        calls.append(node)
        return J.JudgeRead(role='R01')
    J.judge_read_agent(STATE, chat=chat)
    assert calls == ['judge_read']


def test_read_format_error_propagates_after_one_call():
    calls = []

    def chat(node, system, user, schema):
        calls.append(node)
        raise ValueError('형식 위반')
    with pytest.raises(ValueError):
        J.judge_read_agent(STATE, chat=chat)
    assert calls == ['judge_read']


def test_part_names_are_grounded_after_the_read(monkeypatch):
    order = []
    monkeypatch.setattr(J, 'ground_part_names', lambda o, c, st: (order.append('ground'), ('SS26', ['SS26H']))[1])

    def chat(node, system, user, schema):
        order.append('read')
        return J.JudgeRead(role='R01', original_part='SS34', candidates=['SS26H'])
    out = J.judge_read_agent(STATE, chat=chat)
    assert order == ['read', 'ground'] and out['judge_read']['original_part'] == 'SS26'


RATINGS = 'ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)'


def specs_of(table):
    def specs(part, codes=None):
        return table.get(part.upper(), [])
    return specs


def r(part, code, mx, unit='V', cond=None, text=None):
    return {'part': part, 'code': code, 'min': None, 'typ': None, 'max': mx, 'text': text, 'unit': unit, 'source_value_text': str(mx),
            'test_condition': cond, 'citation': {'document': f'{part}.pdf', 'page': 1, 'table': RATINGS, 'row': code, 'chunk_index': 1}}


SPECS = {'1N5817': [r('1N5817', 'VRRM', 20.0), r('1N5817', 'IF_AV', 1.0, 'A'), r('1N5817', 'PACKAGE', None, None, text='DO-41')],
         'SS14': [r('SS14', 'VRRM', 40.0), r('SS14', 'IF_AV', 1.0, 'A'), r('SS14', 'PACKAGE', None, None, text='SMA')]}
READ = J.JudgeRead(role='R01', candidates=['1N5817'], values=[
    J.Value(name='v_in_max', number=20, unit='V', quote='입력 전압의 최댓값은 20V'),
    J.Value(name='i_max', number=150, unit='mA', quote='최대 순방향 전류는 150mA'),
    J.Value(name='temp', condition='TA=25°C', quote='주변 온도는 25°C')]).model_dump(mode='json')


def no_interrupt(*a, **k):
    pytest.fail('물을 것이 없는데 인터럽트를 불렀다')


def unknown(payload):
    """사용자가 아무것도 답하지 않은 재개(= 모름). R01의 조건부(허용 전압 강하)는 발동 여부를 늘 묻는다."""
    return {'answers': {}}


def test_ac01_judge_question_gives_not_sufficient(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', unknown)
    out = J.judge_agent({**STATE, 'judge_read': READ}, specs=specs_of(SPECS), find=None, retriever=None)
    j = out['judgement']
    assert j['kind'] == 'judge' and j['results'][0]['verdict'] == 'NOT_SUFFICIENT'
    assert out['reports'][-1]['agent'] == 'judge' and out['path'] == ['판정']


def test_grade2_official_pdf_row_is_converted_with_provenance():
    """등급2는 정확한 품번·행·수치·공식 PDF 해시가 모두 있을 때만 판정 행이 된다."""
    docs = [{
        'evidence_grade': 2, 'source_sha256': 'a' * 64,
        'source_url': 'https://www.ti.com/lit/ds/symlink/SS14.pdf',
        'doc_parts': ['SS14'], 'row': 'VRRM', 'unit': 'V',
        'cells': [('MAX', '40')], 'file': 'SS14.pdf', 'page': 2,
        'table': 'Absolute Maximum Ratings', 'content': 'VRRM 40 V',
    }]
    rows = J._grade2_rows(lambda parts, terms: docs, 'SS14', {'VRRM'})
    assert rows[0]['max'] == 40.0
    assert rows[0]['citation'] == {
        'document': 'SS14.pdf', 'page': 2, 'table': 'Absolute Maximum Ratings',
        'row': 'VRRM', 'source_url': docs[0]['source_url'],
        'source_sha256': 'a' * 64, 'evidence_grade': 2,
    }


@pytest.mark.parametrize('maker', [
    'Vishay', 'Vishay Semiconductors',
])
@pytest.mark.parametrize('symbol', ['VRRM = VRWM = VR', 'V = V = V RRM RWM R'])
def test_vishay_vrrm_equality_row_is_verified_without_borrowing_vrm(maker, symbol):
    doc = {
        'evidence_grade': 2, 'source_sha256': 'a' * 64,
        'source_url': 'https://www.vishay.com/docs/86366/bas16.pdf',
        'doc_parts': ['BAS16'], 'file': 'bas16.pdf', 'page': 1,
        'table': 'ABSOLUTE MAXIMUM RATINGS (Tamb = 25 °C, unless otherwise specified)',
        'row': 'Repetitive peak reverse voltage = working peak reverse voltage = DC blocking voltage',
        'symbol': symbol, 'cells': [('VALUE', '75')], 'unit': 'V', 'conditions': '',
        'content': f'BAS16 | Repetitive peak reverse voltage | {symbol} | VALUE = 75 V',
    }
    rows = J._grade2_rows(lambda *a: [doc], 'BAS16', {'VRRM'}, maker)
    assert len(rows) == 1 and rows[0]['max'] == 75.0
    assert rows[0]['citation']['source_url'] == doc['source_url']
    for symbol in ('VR', 'VRM', 'VRM = VR', 'VRRM or VR', 'VRRM / VRWM / VR', 'VRRM VRWM VR'):
        assert J._grade2_rows(lambda *a: [{**doc, 'symbol': symbol}], 'BAS16', {'VRRM'}, maker) == []
    # [왜] 판정은 아직 TSC 내부 행만 쓴다. 다른 제조사 지정은 등급2 행 어댑터와 별개로 maker_missing으로 거절한다(#146 회귀)
    assert J.outside_corpus(J.JudgeRead(role='R01', maker_wanted=maker), {})[0] == J.Reason.MAKER_MISSING


@pytest.mark.parametrize(('maker', 'host'), [
    ('TI', 'www.ti.com'), ('Texas Instruments', 'www.ti.com'),
    ('onsemi', 'www.onsemi.com'),
    ('ST', 'www.st.com'), ('STMicroelectronics', 'www.st.com'),
    ('ADI', 'www.analog.com'), ('Analog Devices', 'www.analog.com'),
    ('Infineon', 'www.infineon.com'), ('Vishay', 'www.vishay.com'),
    ('TSC', 'services.taiwansemi.com'), ('Taiwan Semiconductor', 'services.taiwansemi.com'),
])
def test_grade2_rows_accepts_target_manufacturer_official_host(maker, host):
    paths = {
        'www.ti.com': '/lit/ds/symlink/part.pdf',
        'www.onsemi.com': '/pdf/datasheet/part.pdf',
        'www.st.com': '/resource/en/datasheet/part.pdf',
        'www.analog.com': '/media/en/technical-documentation/data-sheets/part.pdf',
        'www.infineon.com': '/assets/row/public/documents/1/2/infineon-part-datasheet-en.pdf',
        'www.vishay.com': '/docs/86366/part.pdf',
        'services.taiwansemi.com': '/storage/resources/datasheet/part.pdf',
    }
    doc = {
        'evidence_grade': 2, 'source_sha256': 'a' * 64,
        'source_url': f'https://{host}{paths[host]}', 'doc_parts': ['LM385-ADJ'],
        'file': 'part.pdf', 'page': 1, 'table': 'MAXIMUM RATINGS', 'row': 'VRRM',
        'symbol': 'VRRM', 'cells': [('MAX', '40')], 'unit': 'V', 'conditions': '',
        'content': 'LM385-ADJ VRRM 40 V',
    }
    rows = J._grade2_rows(lambda *a: [doc], 'LM385-ADJ', {'VRRM'}, maker)
    assert len(rows) == 1 and rows[0]['max'] == 40.0


@pytest.mark.parametrize(('maker', 'host', 'path'), [
    ('Nexperia', 'assets.nexperia.com', '/documents/data-sheet/part.pdf'),
])
def test_grade2_rows_rejects_non_registered_manufacturer_rows(maker, host, path):
    """등급2 행 어댑터도 Nexperia의 공식 PDF를 등급2로 승격하지 않는다."""
    doc = {
        'evidence_grade': 2, 'source_sha256': 'a' * 64,
        'source_url': f'https://{host}{path}', 'doc_parts': ['LM385-ADJ'],
        'file': 'part.pdf', 'page': 1, 'table': 'MAXIMUM RATINGS', 'row': 'VRRM',
        'symbol': 'VRRM', 'cells': [('MAX', '40')], 'unit': 'V', 'conditions': '',
        'content': 'LM385-ADJ VRRM 40 V',
    }
    assert J._grade2_rows(lambda *a: [doc], 'LM385-ADJ', {'VRRM'}, maker) == []


def test_grade2_budget_boundary_is_not_swallowed_by_row_adapter():
    with pytest.raises(SearchBudgetExhausted) as error:
        J._grade2_rows(lambda *_args: (_ for _ in ()).throw(SearchBudgetExhausted(2)), 'SS14', {'VRRM'})
    assert error.value.grade == 2


def test_grade2_search_failure_is_logged_by_class_and_does_not_stop_judging(caplog):
    def broken(parts, terms):
        raise RuntimeError('boom SS14 repetitive peak reverse voltage secret-token')
    assert J._grade2_rows(broken, 'SS14', {'VRRM'}) == []
    assert 'grade2_rows_failed error=RuntimeError' in caplog.text
    assert 'secret-token' not in caplog.text and 'SS14' not in caplog.text


def test_explicit_revision_is_extracted_and_row_revision_is_exact():
    """지정 판본은 접두어가 비슷한 다른 개정 코드와 섞이지 않아야 한다."""
    read = J.JudgeRead(role='R01', revision_wanted='S2202판')
    assert J.requested_revisions('S1A SERIES_S2202.pdf 판본만 사용') == {'S2202'}
    assert J._row_revision({'citation': {'document': 'S1A SERIES_S2202.pdf'}}) == 'S2202'
    assert J._row_revision({'citation': {'document': 'S1A SERIES_S2102.pdf'}}) == 'S2102'
    assert J._row_revision({'citation': {'document': 'S1A SERIES.pdf'}}) == ''


def test_judge_agent_keeps_part_specific_revision_rows_separate(monkeypatch):
    """품번별 판본을 실제 판정 경로에서 교차 사용하지 않는다."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    table = {
        'SS34': [r('SS34', 'VRRM', 30.0), r('SS34', 'IF_AV', 1.0, 'A'),
                 r('SS34', 'PACKAGE', None, None, text='SMA')],
        'SS34H': [r('SS34H', 'VRRM', 40.0), r('SS34H', 'IF_AV', 1.0, 'A'),
                  r('SS34H', 'PACKAGE', None, None, text='SMA')],
    }
    table['SS34'][0]['citation']['document'] = 'SS34_F16.pdf'
    table['SS34H'][0]['citation']['document'] = 'SS34H_F20.pdf'
    read = dict(READ, original_part='SS34', candidates=['SS34', 'SS34H'])
    state = {**STATE,
             'question': 'SS34 F16 판본; SS34H F20 판본을 비교해줘',
             'judge_read': read}
    out = J.judge_agent(state, specs=specs_of(table), find=None, retriever=None)
    results = {item['part']: item for item in out['judgement']['results']}
    assert set(results) == {'SS34', 'SS34H'}
    assert results['SS34']['checks'][0]['citation']['document'] == 'SS34_F16.pdf'
    assert results['SS34H']['checks'][0]['citation']['document'] == 'SS34H_F20.pdf'

    # 각 품번에 반대 판본 행만 남기면 해당 후보는 판정에서 제외된다.
    crossed = {
        'SS34': [dict(table['SS34'][0], citation={**table['SS34'][0]['citation'], 'document': 'SS34_F20.pdf'})],
        'SS34H': [dict(table['SS34H'][0], citation={**table['SS34H'][0]['citation'], 'document': 'SS34H_F16.pdf'})],
    }
    rejected = J.judge_agent(state, specs=specs_of(crossed), find=None, retriever=None)
    assert rejected['judgement']['results'] == []


def test_grade3_references_are_reported_separately_from_judgement(monkeypatch):
    reference = {'source_url': 'https://example.com/SS14.html', 'file': 'SS14 reference',
                 'doc_parts': ['SS14'], 'retrieved_at': '2026-11-11T00:00:00+00:00'}
    monkeypatch.setattr(J, 'judge_agent', lambda *a, **k: {
        'judgement': {'kind': 'find', 'results': [], 'shown': []},
        'references': [reference], 'path': ['판정'],
        'reports': [J._report('partial', 'no official row')],
    })
    out = J.judge_task_node({'task': {'id': 1}, 'round': 1}, specs=None, find=None,
                             retriever=None, web_search=None, web_search_fallback=None)
    assert out['reports'][0]['references'] == [reference]
    assert out['reports'][0]['judgement']['results'] == []


def test_grade2_row_flows_through_judge_check(monkeypatch):
    """헬퍼 결과가 실제 judge_part 검사와 결과 인용까지 이어지는지 확인한다."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    doc = {
        'evidence_grade': 2, 'source_sha256': 'c' * 64, 'chunk_id': 'W1',
        'source_url': 'https://www.ti.com/lit/ds/symlink/1N5817.pdf',
        'doc_parts': ['1N5817'], 'row': 'Repetitive peak reverse voltage', 'unit': 'V',
        'cells': [('MAX', '20')], 'file': '1N5817.pdf', 'page': 1,
        'table': 'ABSOLUTE MAXIMUM RATINGS', 'content': '1N5817 ABSOLUTE MAXIMUM RATINGS VRRM Repetitive peak reverse voltage MAX = 20 V',
        'conditions': '',
    }
    out = J.judge_agent({**STATE, 'judge_read': READ}, specs=specs_of({}), find=None,
                        retriever=None, web_search=lambda parts, terms: [doc])
    checks = out['judgement']['results'][0]['checks']
    vrm = next(check for check in checks if check['code'] == 'VRRM')
    assert vrm['citation']['evidence_grade'] == 2
    assert vrm['citation']['chunk_id'] == 'W1'
    assert vrm['citation']['source_sha256'] == 'c' * 64


@pytest.mark.parametrize('change', [
    {'evidence_grade': 3},
    {'source_sha256': ''},
    {'doc_parts': ['SS14A']}, {'page': 0}, {'page': True},
    {'cells': [('TYP', '100')]}, {'cells': [('VALUE', '100')]}, {'unit': 'mV'},
    {'row': 'IFSM'},
    {'cells': [('MIN', 'typical')]},
])
def test_grade2_rejects_unverified_or_mismatched_rows(change):
    doc = {
        'evidence_grade': 2, 'source_sha256': 'b' * 64,
        'source_url': 'https://www.infineon.com/assets/row/public/documents/30/49/infineon-ir-datasheet-en.pdf',
        'doc_parts': ['IR'], 'row': 'VRRM', 'unit': 'V', 'cells': [('MAX', '100')],
        'file': 'IR.pdf', 'page': 1, 'table': 'Maximum Ratings', 'content': 'IR | VRRM | 100 V',
    }
    doc.update(change)
    assert J._grade2_rows(lambda parts, terms: [doc], 'IR', {'VRRM'}) == []


def test_grade2_rejects_conflicting_official_values():
    base = {
        'evidence_grade': 2, 'source_url': 'https://www.ti.com/lit/ds/symlink/SS14.pdf',
        'doc_parts': ['SS14'], 'row': 'VRRM', 'unit': 'V', 'file': 'SS14.pdf', 'page': 1,
        'table': 'Maximum ratings', 'content': 'SS14 VRRM', 'conditions': '',
    }
    docs = [{**base, 'source_sha256': 'd' * 64, 'cells': [('MAX', '40')]},
            {**base, 'source_sha256': 'e' * 64, 'cells': [('MAX', '60')]}]
    assert J._grade2_rows(lambda parts, terms: docs, 'SS14', {'VRRM'}) == []


def test_grade2_passes_maker_to_search_and_accepts_spaced_vrrm():
    seen = []
    doc = {
        'evidence_grade': 2, 'source_sha256': 'f' * 64,
        'source_url': 'https://www.infineon.com/assets/row/public/documents/1/2/infineon-ir-datasheet-en.pdf',
        'doc_parts': ['IR'], 'row': 'V RRM', 'unit': 'V', 'cells': [('MAX', '100')],
        'file': '1.pdf', 'page': 1, 'table': 'Maximum ratings',
        'content': 'IR Maximum ratings V RRM 100 V', 'conditions': '',
    }
    rows = J._grade2_rows(lambda parts, terms: (seen.append(terms) or [doc]), 'IR', {'VRRM'}, 'Infineon')
    assert rows and 'Infineon' in seen[0]
    assert not J._grade2_rows(lambda *a: pytest.fail('unsupported manufacturer lookup'), 'IR', {'VRRM'}, 'Rohm')


def test_ac02_number_not_in_question_is_dropped_and_asked(monkeypatch):
    read = dict(READ, values=READ['values'] + [{'name': 'v_drop_allowed', 'number': 12, 'unit': 'V', 'flag': None, 'condition': '', 'quote': '12V 허용'}])
    asked = []
    monkeypatch.setattr(J, 'interrupt', lambda payload: asked.append(payload) or {'answers': {}})
    state = {**STATE, 'conditions': 'USB 최대 5.25V, 최대 전류 250mA, 역류 허용 100µA 이하.', 'judge_read': read}
    out = J.judge_agent(state, specs=specs_of(SPECS), find=None, retriever=None)
    assert 'v_drop_allowed' in out['judgement']['dropped']


def test_ac08_interrupt_once_and_reply_fills_values(monkeypatch):
    read = dict(READ, values=[v for v in READ['values'] if v['name'] != 'i_max'])
    calls = []
    monkeypatch.setattr(J, 'interrupt', lambda payload: calls.append(payload) or {'answers': {'i_max': '150mA'}})
    out = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(SPECS), find=None, retriever=None)
    assert len(calls) == 1 and 'i_max' in calls[0]['missing'] and calls[0]['question']
    assert out['judgement']['results'][0]['verdict'] == 'NOT_SUFFICIENT'


def test_empty_reply_keeps_found_values_and_is_not_verified(monkeypatch):
    read = dict(READ, values=[v for v in READ['values'] if v['name'] != 'i_max'])
    monkeypatch.setattr(J, 'interrupt', unknown)
    j = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(SPECS), find=None, retriever=None)['judgement']
    res = j['results'][0]
    assert res['verdict'] == 'NOT_SUFFICIENT'  # VRRM 실패가 확인 안 됨보다 먼저다(SPEC 3절)
    assert 'i_max' in res['missing']


def test_ac07_other_role_gives_no_verdict(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', no_interrupt)
    out = J.judge_agent({**STATE, 'judge_read': dict(READ, role='other')}, specs=specs_of(SPECS), find=None, retriever=None)
    assert out['judgement']['kind'] == 'no_rule' and out['judgement']['results'] == []


def test_find_question_filters_judges_and_ranks(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', unknown)
    seen = []

    def find(conditions, category, package, limit, **near):
        seen.append(conditions)
        return [{'part': 'SS14', 'category': 'schottky-rectifier', 'packages': ['SMA'], 'matches': []},
                {'part': '1N5817', 'category': 'schottky-rectifier', 'packages': ['DO-41'], 'matches': []}]
    read = dict(READ, candidates=[], values=[dict(v, number=12, quote='입력 전압의 최댓값은 12V') if v['name'] == 'v_in_max' else v
                                             for v in READ['values']])
    state = {**STATE, 'question_type': 'candidate_find', 'conditions': STATE['conditions'].replace('20V', '12V'), 'judge_read': read}
    j = J.judge_agent(state, specs=specs_of(SPECS), find=find, retriever=None)['judgement']
    assert seen[0][0] == {'code': 'VRRM', 'gte': pytest.approx(15.0)}
    assert [x['part'] for x in j['shown']] == ['1N5817', 'SS14']  # 1N5817은 DO-41이라 기판 수정 없음 → 먼저
    assert j['kind'] == 'find' and j['capped'] is False and j['preferred_mount'] == ''  # 선호 없음(Store 없는 평가 실행기와 같음)


def find_state(read=None, **extra):
    """찾기 질문 상태. 대상 풋프린트가 없어 두 후보(SS14 SMA · 1N5817 DO-41)의 기판 수정 여부가 같다(모름)."""
    base = dict(READ, candidates=[], values=[dict(v, number=12, quote='입력 전압의 최댓값은 12V') if v['name'] == 'v_in_max' else v
                                             for v in READ['values']])
    return {**STATE, 'question_type': 'candidate_find', 'conditions': STATE['conditions'].replace('20V', '12V'),
            'target_part': {**STATE['target_part'], 'footprint': ''}, 'judge_read': {**base, **(read or {})}, **extra}


def two_found(conditions, category, package, limit, **near):
    return [{'part': 'SS14', 'category': 'schottky-rectifier', 'packages': ['SMA']},
            {'part': '1N5817', 'category': 'schottky-rectifier', 'packages': ['DO-41']}]


def test_stored_mount_preference_reorders_shown_without_changing_verdicts(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', unknown)
    run = lambda **extra: J.judge_agent(find_state(**extra), specs=specs_of(SPECS), find=two_found, retriever=None)['judgement']
    none, smd, tht = run(), run(mount_preference='smd'), run(mount_preference='tht')
    assert [x['part'] for x in none['shown']] == ['1N5817', 'SS14'] and none['preferred_mount'] == ''  # 같은 판정 · 기판 수정 모름이면 품번 순
    assert [x['part'] for x in smd['shown']] == ['SS14', '1N5817'] and smd['preferred_mount'] == 'smd'
    assert [x['part'] for x in tht['shown']] == ['1N5817', 'SS14'] and tht['preferred_mount'] == 'tht'
    assert smd['results'] == none['results']  # 판정 · 후보 목록은 그대로(거르지 않음)


def test_mount_asked_in_the_question_wins_over_the_stored_preference(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', unknown)
    asked = {'required_specs': [{'words': '스루홀 부품', 'code': 'none'}]}
    j = J.judge_agent(find_state(read=asked, mount_preference='smd'), specs=specs_of(SPECS), find=two_found, retriever=None)['judgement']
    # [왜] 질문이 스루홀을 요구했으면 그 요구로 거르고, 내 설정(SMD)은 쓰지 않는다(SPEC 8.5)
    assert [x['part'] for x in j['shown']] == ['1N5817'] and j['preferred_mount'] == ''


def test_find_does_not_filter_by_original_part_values(monkeypatch):
    """원래 부품 값(orig.*)을 쓰는 조건(R11 TRR ≤ 원래 TRR)은 거르기에 쓰지 않는다. 판정에서 같은 시험 조건 행끼리 본다."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    seen = []

    def find(conditions, category, package, limit, **near):
        seen.append(conditions)
        return []
    table = {**SPECS, '1N5819': [r('1N5819', 'VRRM', 40.0), r('1N5819', 'TRR', 5e-8, 's')]}
    read = dict(READ, role='R11', original_part='1N5819', candidates=[],
                values=[READ['values'][0], dict(READ['values'][1], name='i_out')])
    j = J.judge_agent({**STATE, 'question_type': 'candidate_find', 'judge_read': read}, specs=specs_of(table), find=find,
                      retriever=None)['judgement']
    assert [t['code'] for t in seen[0]] == ['VRRM', 'IF_AV'] and j['terms'] == seen[0]


def test_find_without_circuit_values_searches_by_original_part_ratings(monkeypatch):
    """회로 값을 하나도 모르면 원래 부품의 같은 정격을 기준으로 후보를 모은다(11-17). 판정은 그대로 '문서로 확인 안 됨'이다."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    seen = []

    def find(conditions, category, package, limit, **near):
        seen.append(conditions)
        return [{'part': 'SS14', 'category': 'schottky-rectifier', 'packages': ['SMA']}]
    table = {**SPECS, '1N4001': [r('1N4001', 'VRRM', 50.0), r('1N4001', 'IF_AV', 1.0, 'A')]}
    read = dict(READ, original_part='1N4001', candidates=[], values=[])
    out = J.judge_agent({**STATE, 'question': 'D1 다른 걸로 바꿀 거 있어?', 'conditions': '', 'question_type': 'candidate_find',
                         'judge_read': read}, specs=specs_of(table), find=find, retriever=None)
    j = out['judgement']
    assert seen[0] == [{'code': 'VRRM', 'gte': 50.0}, {'code': 'IF_AV', 'gte': 1.0}] and j['terms'] == seen[0]
    assert j['terms_from_original'] is True
    assert [x['verdict'] for x in j['results']] == ['NOT_VERIFIED'] and j['shown'] == []  # 값이 없어 판정은 확인 안 됨, 견적 대상 아님
    assert [x['part'] for x in j['unverified']] == ['SS14'] and 'v_in_max' in j['results'][0]['missing']
    assert out['reports'][-1]['status'] == 'ok'  # 후보가 있는 답이라 거절로 가지 않는다


def test_find_with_circuit_values_does_not_use_original_part_ratings(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', unknown)
    table = {**SPECS, '1N4001': [r('1N4001', 'VRRM', 50.0), r('1N4001', 'IF_AV', 1.0, 'A')]}
    j = J.judge_agent(find_state(read={'original_part': '1N4001'}), specs=specs_of(table), find=two_found, retriever=None)['judgement']
    assert j['terms_from_original'] is False and j['terms'][0] == {'code': 'VRRM', 'gte': pytest.approx(15.0)}


def test_find_without_values_and_without_original_rows_still_finds_nothing(monkeypatch):
    """원래 부품 문서도 없으면 대신할 기준이 없어 찾지 않는다(전과 같음). 거절 문구가 읽은 역할을 보여 준다(test_build)."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    read = dict(READ, original_part='', candidates=[], values=[])
    out = J.judge_agent({**STATE, 'conditions': '', 'question_type': 'candidate_find', 'judge_read': read},
                        specs=specs_of(SPECS), find=lambda *a, **k: pytest.fail('조건 없이 찾기를 불렀다'), retriever=None)
    assert out['judgement']['results'] == [] and out['judgement']['terms'] == [] and out['judgement']['terms_from_original'] is False


@pytest.mark.parametrize('name, text, want', [
    ('hot_test', '125', {'TJ': 125.0}), ('hot_test', '125°C', {'TJ': 125.0}), ('hot_test', '125도', {'TJ': 125.0}),
    ('temp', '85', {'TA': 85.0}), ('temp', '-40 C', {'TA': -40.0}),
    ('hot_test', 'TA=100°C', {'TA': 100.0}),  # 기호를 적었으면 적은 대로
    ('vf_test', '1', None), ('hot_test', '뜨거움', None),  # 전류까지 받는 조건 · 숫자가 아닌 답은 전과 같이 버린다(= 모름)
])
def test_resume_reply_accepts_a_bare_number_for_temperature_only_conditions(name, text, want):
    kinds = {'hot_test': 'condition', 'temp': 'condition', 'vf_test': 'condition'}
    assert J.merge_reply({name: text}, {}, {}, kinds)[1].get(name) == want


def test_find_passes_original_package_and_category_for_ranking(monkeypatch):
    """찾기는 원래 부품의 패키지 · 분류를 도구에 넘겨 50개로 자르기 전에 그 순서로 줄 세우게 한다(SPEC 8.3 찾기 순위). 모르면 None."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    seen = []

    def find(conditions, category, package, limit, **near):
        seen.append(near)
        return []
    rows = [dict(x, category='standard-rectifier') for x in [r('1N4001', 'VRRM', 50.0), r('1N4001', 'PACKAGE', None, None, text='DO-41'),
                                                              r('1N4001', 'PACKAGE', None, None, text='DO-204AL')]]
    for original in ('TSC 1N4001', ''):
        read = dict(READ, original_part=original, candidates=[])
        J.judge_agent({**STATE, 'question_type': 'candidate_find', 'judge_read': read}, specs=specs_of({'1N4001': rows}), find=find,
                      retriever=None)
    # [왜] 원래 부품을 알면 그 순서로 한 번, 기준에 가까운 순으로 한 번 더 찾는다(같은 패키지 계열로 50개가 다 차는 것을 막음, 11-07 v2 찾기)
    assert seen == [{'original_packages': ['DO-41', 'DO-204AL'], 'original_category': 'standard-rectifier'}, {},
                    {'original_packages': None, 'original_category': None}]


def test_ac09_numbers_are_compared_in_verdict_only(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', unknown)
    called = []
    real = V.judge_part
    monkeypatch.setattr(J.V, 'judge_part', lambda *a, **k: called.append(1) or real(*a, **k))
    J.judge_agent({**STATE, 'judge_read': READ}, specs=specs_of(SPECS), find=None, retriever=None)
    assert called


def test_ec02_two_roles_ask_once_and_keep_both_without_answer(monkeypatch):
    asked = []
    monkeypatch.setattr(J, 'interrupt', lambda payload: asked.append(payload) or {'answers': {}})
    out = J.judge_agent({**STATE, 'judge_read': dict(READ, role_alt='R08')}, specs=specs_of(SPECS), find=None, retriever=None)
    assert len(asked) == 1 and asked[0]['role_choices'] == ['R01', 'R08']
    assert out['judgement']['roles'] == ['R01', 'R08']
    assert out['judgement']['results'][0]['verdict'] == 'NOT_SUFFICIENT'  # 두 역할 중 더 나쁜 판정


def test_role_evidence_selects_role_with_complete_required_inputs(monkeypatch):
    """회로 근거가 있고 한 역할만 필수 입력을 갖추면 선택 질문을 만들지 않는다."""
    asked = []
    monkeypatch.setattr(J, 'interrupt', lambda payload: asked.append(payload) or {'answers': {}})
    read = dict(READ, role='R02', role_alt='R01', role_evidence=['USB 입력 → 배터리 전원 역류 방지'], values=[
        {'name': 'v_reverse_max', 'number': 5.25, 'unit': 'V', 'flag': None, 'condition': '', 'quote': '최대 5.25V'},
        {'name': 'i_max', 'number': 0.25, 'unit': 'A', 'flag': None, 'condition': '', 'quote': '최대 전류 250mA'},
        {'name': 'ir_allowed', 'number': 0.0001, 'unit': 'A', 'flag': None, 'condition': '', 'quote': '역류 허용 100µA 이하'},
    ])
    state = {**STATE, 'conditions': 'USB 최대 5.25V, 최대 전류 250mA, 역류 허용 100µA 이하.', 'judge_read': read}
    out = J.judge_agent(state, specs=specs_of(SPECS), find=None, retriever=None)
    assert asked == [] and out['judgement']['roles'] == ['R02']


def test_ec10_order_code_variant_with_identical_statement_is_identical(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', unknown)
    table = {**SPECS, '1N4148': [r('1N4148', 'VRRM', 100.0), r('1N4148', 'IF_AV', 0.15, 'A')]}
    read = dict(READ, original_part='1N4148 A0G', candidates=['1N4148 R0G'])
    docs = [{'chunk_id': 7, 'content': 'A0, A0G, R0 and R0G are physically identical; only packing differs.'}]
    out = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(table), find=None, retriever=lambda q, parts=None: docs)
    res = out['judgement']['results'][0]
    assert res['verdict'] == 'IDENTICAL' and res['checks']  # 주문 코드 품번은 기본 품번의 사양 표 행으로 본다


def ordering_row(code, chunk_id, page=2):
    """검색이 돌려주는 주문 정보 표 한 줄 청크(실제 1N4148 SERIES_K2301.pdf 2쪽 모양)."""
    return {'chunk_id': chunk_id, 'file': '1N4148 SERIES_K2301.pdf', 'page': page, 'table': 'ORDERING INFORMATION',
            'content': f'[1N4148 SERIES_K2301.pdf · {page}쪽 · ORDERING INFORMATION] ORDERING INFORMATION / ORDERING CODE (1): {code}'
                       ' | ORDERING INFORMATION / PACKAGE: DO-35 | ORDERING INFORMATION / PACKING: 10,000 / 14" Reel'}


ORDER_DOCS = [ordering_row('1N4148 R0', 26965), ordering_row('1N4448 R0G', 26973), ordering_row('1N4148 R0G', 26971),
              ordering_row('1N4148 A0G', 99)]


@pytest.mark.parametrize('original,candidate', [('1N4148 A0G', '1N4148 R0G'), ('TSC 1N4148 A0G', '1N4148 r0g'), ('1N4148 A0G', '1N4148')])
def test_order_code_only_difference_is_identical_with_ordering_table_citation(monkeypatch, original, candidate):
    """같은 기본 품번에 주문 코드(R · A · L · M + 글자 하나 + 선택 G)만 다르면 동일품이고, 주문 정보 표의 그 주문 코드 행을 인용한다(SPEC 8.3 주문 코드 동일품)."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    table = {**SPECS, '1N4148': [r('1N4148', 'VRRM', 100.0), r('1N4148', 'IF_AV', 0.15, 'A')]}
    asked = []
    out = J.judge_agent({**STATE, 'judge_read': dict(READ, original_part=original, candidates=[candidate])}, specs=specs_of(table),
                        find=None, retriever=lambda q, parts=None: asked.append(parts) or ORDER_DOCS)
    res = out['judgement']['results'][0]
    assert res['verdict'] == 'IDENTICAL' and asked[0] == ['1N4148']
    cite = res['checks'][0]['citation']
    # 'R0'이 'R0G' 안에 있어도 'R0' 행은 고르지 않는다. 후보가 기본 품번뿐이면 원래 품번의 주문 코드 행이다
    want = '1N4148 R0G' if candidate != '1N4148' else None
    assert cite['table'] == 'ORDERING INFORMATION' and cite['page'] == 2 and cite['document'] == '1N4148 SERIES_K2301.pdf'
    assert (cite['row'], cite['chunk_id']) == ((want, 26971) if want else ('1N4148 A0G', 99))


@pytest.mark.parametrize('original,candidate', [('1N4148 A0G', '1N4448 R0G'), ('1N4148', '1N4148 BAT85'), ('1N4148 A0G', '1N4148 R0G')])
def test_order_code_rule_needs_same_base_order_code_shape_and_a_found_row(monkeypatch, original, candidate):
    """기본 품번이 다르거나, 꼬리가 주문 코드 모양이 아니거나, 주문 정보 표에서 그 행을 못 찾으면 코드 규칙으로 동일품을 내지 않는다."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    table = {**SPECS, '1N4148': [r('1N4148', 'VRRM', 100.0)], '1N4448': [r('1N4448', 'VRRM', 100.0)]}
    docs = [] if candidate == '1N4148 R0G' else ORDER_DOCS  # 마지막 경우: 검색이 주문 정보 행을 못 찾음(지어낸 인용 없음)
    out = J.judge_agent({**STATE, 'judge_read': dict(READ, original_part=original, candidates=[candidate])}, specs=specs_of(table),
                        find=None, retriever=lambda q, parts=None: docs)
    assert out['judgement']['results'][0]['verdict'] != 'IDENTICAL'


def test_identical_by_order_code_survives_schottky_exemption(monkeypatch):
    """쇼트키 후보는 면제 뒤 판정을 다시 정한다. 그때도 주문 코드 동일품은 빠진 값(확인 안 됨)이 있어도 동일품이다."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    rows = [dict(x, category='schottky-rectifier') for x in SPECS['1N5817']]
    docs = [dict(ordering_row('1N5817 R0G', 5), file='1N5817 SERIES_H2104.pdf')]
    read = dict(READ, original_part='1N5817 A0G', candidates=['1N5817 R0G'], values=READ['values'][2:])  # 입력 전압 · 전류 없음
    out = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of({'1N5817': rows}), find=None, retriever=lambda q, parts=None: docs)
    res = out['judgement']['results'][0]
    assert res['verdict'] == 'IDENTICAL' and 'unverified' in [c['result'] for c in res['checks']]


def test_original_part_with_order_code_reads_base_part_rows(monkeypatch):
    """원래 품번에 주문 코드가 붙어도(1N4148 A0G) 사양 표의 기본 품번(1N4148) 행을 원래 부품 행으로 쓴다."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    seen = []
    real = V.judge_part
    monkeypatch.setattr(J.V, 'judge_part', lambda *a, **k: seen.append(k['original_rows']) or real(*a, **k))
    table = {**SPECS, '1N4148': [r('1N4148', 'VRRM', 100.0), r('1N4148', 'IF_AV', 0.15, 'A')]}
    read = dict(READ, original_part='1N4148 A0G', candidates=['SS14'])
    J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(table), find=None, retriever=None)
    assert seen == [table['1N4148']]


def test_manufacturer_name_before_part_number_is_dropped_for_spec_lookup(monkeypatch):
    """'TSC 1N5817' · 'Taiwan Semiconductor 1N5817'은 사양 표의 1N5817 행으로 판정한다. 제조사 이름은 품번이 아니다(B1, 11-06)."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    seen = []
    real = V.judge_part
    monkeypatch.setattr(J.V, 'judge_part', lambda *a, **k: seen.append(k['original_rows']) or real(*a, **k))
    table = {**SPECS, '1N4148': [r('1N4148', 'VRRM', 100.0)]}
    for name in ('TSC 1N5817', 'tsc 1N5817', 'Taiwan Semiconductor 1N5817'):
        read = dict(READ, original_part='TSC 1N4148 A0G', candidates=[name])
        res = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(table), find=None, retriever=None)['judgement']['results'][0]
        assert res['part'] == name  # 이름은 질문에 쓴 대로 보인다
        assert res['checks'][0]['citation']['document'] == '1N5817.pdf'
    assert seen == [table['1N4148']] * 3


def test_schottky_exemption_follows_the_condition_exempt_key():
    """보통 TRR 조건은 쇼트키 계열 모두 면제, exempt: sic 조건(R14 100 kHz 초과)은 SiC 쇼트키만 면제한다."""
    def trr(exempt):
        return V.Check(code='TRR', tier='required', op='<=', basis='35e-9', threshold=35e-9, value=5e-8, result='fail', exempt=exempt)
    j = V.Judgement(part='X', role='R14', verdict='NOT_SUFFICIENT', checks=[trr('schottky'), trr('sic')])
    general = J._schottky_exempt(j, 'schottky-rectifier')
    assert [c.result for c in general.checks] == ['pass', 'fail'] and general.verdict == 'NOT_SUFFICIENT'
    sic = J._schottky_exempt(j, 'sic-schottky-diode')
    assert [c.result for c in sic.checks] == ['pass', 'pass'] and sic.verdict == 'ROLE_SUFFICIENT'


def test_grounded_requires_quote_in_text_and_same_number():
    text = '입력 전압의 최댓값은 20V'
    assert J.grounded(text, J.Value(name='v_in_max', number=20, unit='V', quote='최댓값은 20V'))
    assert not J.grounded(text, J.Value(name='v_in_max', number=12, unit='V', quote='최댓값은 20V'))
    assert not J.grounded(text, J.Value(name='v_in_max', number=20, unit='V', quote='최댓값은 20 볼트'))


def test_numbers_in_role_rules_do_not_ground_values(monkeypatch):
    """규칙 파일의 알아보는 법 글(R10 '5V 출력과 3.3V 입력')에 있는 숫자는 사용자가 준 숫자가 아니다(AC-02)."""
    monkeypatch.setattr(J, 'interrupt', unknown)
    read = dict(READ, values=READ['values'] + [{'name': 'v_drop_allowed', 'number': 3.3, 'unit': 'V', 'flag': None,
                                                 'condition': '', 'quote': '3.3V 입력'}])
    out = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(SPECS), find=None, retriever=None)
    assert 'v_drop_allowed' in out['judgement']['dropped']


def test_identical_statement_chunk_is_cited_when_order_table_uses_x(monkeypatch):
    # [왜] 주문 표가 'BZV55Cx L0G'처럼 x로 적으면 주문 코드 행을 못 찾는다. 같은 부품이라고 밝힌 청크를 근거로 인용해야 답이 정답 쪽을 가리킨다(11-06 dev)
    monkeypatch.setattr(J, 'interrupt', unknown)
    table = {**SPECS, '1N4148': [r('1N4148', 'VRRM', 100.0), r('1N4148', 'IF_AV', 0.15, 'A')]}
    read = dict(READ, original_part='1N4148 A0G', candidates=['1N4148 R0G'])
    docs = [{'chunk_id': 7, 'file': '1N4148 SERIES_K2301.pdf', 'page': 2, 'table': 'ORDERING INFORMATION',
             'content': '[1N4148 SERIES_K2301.pdf · 2쪽 · ORDERING INFORMATION] ORDERING CODE (1): 1N41xx R0G\n주: 1. physically identical parts'}]
    out = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(table), find=None, retriever=lambda q, parts=None: docs)
    res = out['judgement']['results'][0]
    assert res['verdict'] == 'IDENTICAL'
    assert res['checks'][0]['citation'] == {'document': '1N4148 SERIES_K2301.pdf', 'page': 2, 'table': 'ORDERING INFORMATION',
                                            'row': '1N4148', 'chunk_id': 7}


def test_tvs_direction_and_aec_requirement_become_checks():
    # [왜] 방향(C · CA)과 AEC-Q101은 품번 · 문서로 정해진다. 사양 표 밖 요구로 보고 거절하던 것을 조건 줄로 판정한다(11-06 v3-10 · 14 · 15)
    from backend.judge.verdict import Judgement
    read = J.JudgeRead(role='R06', original_part='SMAJ5.0A', candidates=['SMAJ6.0CA'],
                       required_specs=[{'words': 'AEC-Q101 적합', 'code': 'AEC_Q101'}])
    base = Judgement(part='SMAJ6.0CA', role='R06', verdict='ROLE_SUFFICIENT')
    out = J._extra_checks(base, read, 'tvs-18', [], ['R06'])
    assert out.verdict == 'NOT_SUFFICIENT' and [(c.code, c.result) for c in out.checks] == [('AEC_Q101', 'fail'), ('DIRECTION', 'fail')]
    aec = [{'code': 'AEC_Q101', 'text': 'AEC-Q101 qualified', 'citation': {'document': 'a.pdf', 'page': 1}}]
    ok = J._extra_checks(base.model_copy(update={'part': 'SMAJ5.0AH'}), read, 'tvs-18', aec, ['R06'])
    assert ok.verdict == 'ROLE_SUFFICIENT' and all(c.result == 'pass' for c in ok.checks)


def test_mount_words_filter_candidates_by_package_kind_not_by_package_name():
    read = J.JudgeRead(role='R01', required_specs=[{'words': '표면실장', 'code': 'none'}])
    assert J.mount_wanted(read) == 'smd' and J.mount_wanted(J.JudgeRead(role='R01', package_wanted='SMA')) == ''
    assert J.mount_wanted(J.JudgeRead(role='R01', required_specs=[{'words': 'through-hole part', 'code': 'none'}])) == 'tht'
    # [왜] 스루홀 17종 밖은 표면실장(SMA · SOD-123F · Thin SMA), DO-41 · DO-204AL은 스루홀(11-07 v2 n01)
    assert J.mount_of(['DO-41', 'DO-204AL']) == {'tht'} and J.mount_of(['SOD-123F']) == {'smd'} and J.mount_of(['THIN SMA']) == {'smd'}


def test_operator_words_come_from_the_users_own_clause():
    text = '서지는 피크 10A의 단발 10/1000µs 파형이며 보호 노드에서 허용하는 전압은 최대 23.2V이다. 기판 수정은 가능하다.'
    # [왜] 읽기가 'below 23.2 V'로 옮겨도 원문 '최대 23.2V'(이하)를 믿는다(11-07 m2 v3-09)
    grounded = J._ground_ops('clamping voltage below 23.2 V', text)
    assert '최대 23.2V' in grounded and C.user_conditions([(grounded, 'VC')])[0]['op'] == '<='
    assert J._ground_ops('VZ 3.42~3.78V', text) == 'VZ 3.42~3.78V'  # 범위는 그대로
    assert J._ground_ops('surge current 0.25 A', '전류는 250mA 이하') == 'surge current 0.25 A'  # 단위를 바꿔 쓴 말은 그대로
    # [왜] 시험 조건 숫자(10A · 10/1000µs)가 섞여도 그 항목 단위(V)의 숫자가 하나면 원문을 믿는다(11-10 v3-09, 사전 등록 #50)
    mixed = J._ground_ops('clamping voltage at 10A 10/1000µs at or below 23.2V', text, 'VC')
    assert '최대 23.2V' in mixed and C.user_conditions([(mixed, 'VC')])[0]['op'] == '<='
    assert J._ground_ops('clamping voltage at 10A at or below 23.2V', text) == 'clamping voltage at 10A at or below 23.2V'  # 항목을 모르면 그대로


def test_an_original_of_unknown_or_other_maker_is_not_read_from_the_tsc_document():
    # [왜] '제조사 미상 1N5819'의 원래 값을 TSC 1N5819 문서로 대신하지 않는다(v3-01 근거, 11-07 c20-04)
    assert J.original_not_tsc('1N5819', '현재 D1~D4는 제조사 미상의 1N5819이다.')
    assert J.original_not_tsc('onsemi 1N4007RLG', '현재 부품은 onsemi 1N4007RLG')
    assert not J.original_not_tsc('TSC 1N5819', '현재 부품은 TSC 1N5819이다.')


@pytest.mark.parametrize('text', ['현재 부품의 표기는 SS34지만 제조사는 확인하지 못했다.', '제조사 불명의 SS34이다.', '제조사가 확인하지 못한 상태다.'])
def test_unknown_maker_wording_from_v3_02_is_read(text):
    assert J.original_not_tsc('SS34', text)


@pytest.mark.parametrize('text', ['VRRM은 확인하지 못했다.', '제조사는 TSC로 확인했다.', '역방향 전류는 확인하지 못했다. 제조사는 TSC이다.'])
def test_unknown_maker_does_not_match_other_unconfirmed_facts(text):
    assert not J.original_not_tsc('SS34', text)


def test_find_widens_to_sibling_categories_and_keeps_a_family_the_user_named(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', unknown)
    seen = []

    def find(conditions, category, package, limit, **near):
        seen.append(category)
        return [{'part': 'SS210H', 'category': 'schottky-rectifier', 'packages': ['SMB']}] if category == 'schottky-diode' else []
    read = dict(READ, candidates=[], original_part='', category_wanted='schottky-rectifier')
    asked = {**STATE, 'question_type': 'candidate_find', 'judge_read': read, 'question': 'D1용 쇼트키 후보를 찾아 줘'}
    J.judge_agent(asked, specs=specs_of({}), find=find, retriever=None)
    # [왜] 같은 계열(쇼트키 소신호)로 먼저 넓히고, 사용자가 '쇼트키'를 말했으면 분류를 통째로 빼지 않는다(11-07 h4-14)
    assert seen[0] == 'schottky-rectifier' and 'schottky-diode' in seen and None not in seen


def test_displayed_conditions_drop_ungrounded_reads_and_use_resume_values(monkeypatch):
    read = {**READ, 'values': [v for v in READ['values'] if v['name'] != 'i_max'] +
            [{'name': 'i_max', 'number': 999, 'unit': 'A', 'quote': '사용자가 적지 않은 999A'}]}
    def reply(payload):
        assert 'i_max' in payload['missing']
        return {'answers': {'i_max': '250mA', 'v_drop_allowed': '0.8V'}}
    monkeypatch.setattr(J, 'interrupt', reply)
    result = J.judge_agent({**STATE, 'conditions': '', 'question': STATE['question'] + ' ' + STATE['conditions'], 'judge_read': read}, specs=specs_of(SPECS), find=None, retriever=None)
    rows = {x['code']: x['value'] for x in result['judgement']['input_conditions']}
    assert rows['i_max'] == '0.25 A' and rows['v_drop_allowed'] == '0.8 V'
    assert '999' not in str(rows)


def test_identical_checks_run_concurrently_but_are_consumed_in_candidate_order(monkeypatch):
    """_identical를 후보마다 동시에 시작해도 결과 순서 · 판정은 차례로 부른 것과 같다."""
    import threading
    monkeypatch.setattr(J, 'interrupt', unknown)
    table = {'1N4148': [r('1N4148', 'VRRM', 100.0), r('1N4148', 'IF_AV', 0.15, 'A')]}
    cands = ['1N4148 R0G', '1N4148 T0G', '1N4148 A0G']
    read = dict(READ, original_part='1N4148 A0G', candidates=cands)
    docs = [{'chunk_id': 7, 'content': 'A0G, R0G and T0G are physically identical.'}]
    running, peak, lock = [0], [0], threading.Lock()

    def retriever(q, parts=None):
        with lock:
            running[0] += 1
            peak[0] = max(peak[0], running[0])
        threading.Event().wait(0.05)
        with lock:
            running[0] -= 1
        return docs
    out = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(table), find=None, retriever=retriever)
    assert [x['part'] for x in out['judgement']['results']] == cands and peak[0] > 1
    serial = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(table), find=None, retriever=lambda q, parts=None: docs)
    assert out['judgement']['results'] == serial['judgement']['results']


def test_identical_error_surfaces_at_the_failing_candidates_turn(monkeypatch):
    """검색 오류는 원래처럼 판정 도구 실패 보고로 끝난다."""
    from backend.graph.mcp_retriever import RetrievalUnavailableError
    monkeypatch.setattr(J, 'interrupt', unknown)
    table = {'1N4148': [r('1N4148', 'VRRM', 100.0), r('1N4148', 'IF_AV', 0.15, 'A')]}
    read = dict(READ, original_part='1N4148 A0G', candidates=['1N4148 R0G'])

    def boom(q, parts=None):
        raise RetrievalUnavailableError('down')
    out = J.judge_agent({**STATE, 'judge_read': read}, specs=specs_of(table), find=None, retriever=boom)
    assert out['path'] == ['판정'] and 'spec table tool failed' in out['reports'][-1]['message' if 'message' in out['reports'][-1] else 'summary']


# #65: 원래 부품과 같은 품번을 물으면 회로 값 · 역할을 묻지 않고 동일품이다
SAME_SPECS = {**SPECS, 'SS34': [r('SS34', 'VRRM', 40.0), r('SS34', 'IF_AV', 3.0, 'A'), r('SS34', 'PACKAGE', None, None, text='SMA')]}
SAME = {**STATE, 'question': 'D1을 SS34로 그대로 둬도 돼?', 'conditions': '', 'target_part': {**STATE['target_part'], 'value': 'SS34'}}
SAME_READ = J.JudgeRead(role='R01', role_alt='R02', original_part='SS34', candidates=['SS34']).model_dump(mode='json')


@pytest.mark.parametrize('original,candidate', [('SS34', 'SS34'), ('TSC SS34', 'SS34'), ('SS34', 'tsc ss34')])
def test_same_part_is_identical_without_asking_values_or_role(monkeypatch, original, candidate):
    """같은 품번(제조사 이름 · 대소문자만 다름)이면 인터럽트 없이 동일품이고, 빠진 값을 남기지 않으며 사양 표 행 인용은 그대로다."""
    from backend.multi_agent.messages import render_judgement
    monkeypatch.setattr(J, 'interrupt', no_interrupt)
    out = J.judge_agent({**SAME, 'judge_read': dict(SAME_READ, original_part=original, candidates=[candidate])},
                        specs=specs_of(SAME_SPECS), find=None, retriever=None)
    j = out['judgement']
    res = j['results'][0]
    assert res['verdict'] == 'IDENTICAL' and res['missing'] == [] and out['reports'][-1]['missing'] == []
    assert j['asked'] == [] and j['roles'] == ['R01', 'R02']  # 역할을 고르지 않으면 두 역할로 판정한다(EC-02)
    assert any(c.get('citation') for c in res['checks'])
    assert '알려 주시면' not in render_judgement(j)


@pytest.mark.parametrize('original,candidates,conditions', [
    ('SS34', ['SS14'], ''),               # 다른 품번
    ('SS34', ['SS34 R0G'], ''),           # 주문 코드만 다름: 주문 정보 표 행을 찾아야 동일품이라 지금처럼 묻는다
    ('', ['SS34'], ''),                   # 원래 품번을 모름(EC-05)
    ('SS34', ['SS34'], '현재 SS34의 제조사는 모르고 기판은 그대로다.'),  # 원래 부품의 제조사를 모름(EC-05)
])
def test_not_same_part_still_asks_values_and_role(monkeypatch, original, candidates, conditions):
    asked = []
    monkeypatch.setattr(J, 'interrupt', lambda payload: asked.append(payload) or {'answers': {}})
    J.judge_agent({**SAME, 'conditions': conditions, 'judge_read': dict(SAME_READ, original_part=original, candidates=candidates)},
                  specs=specs_of(SAME_SPECS), find=None, retriever=None)
    assert len(asked) == 1 and asked[0]['missing'] and asked[0]['role_choices'] == ['R01', 'R02']


def test_mixed_same_and_other_part_asks_once_and_keeps_identical(monkeypatch):
    """같은 품번과 다른 품번을 함께 물으면 지금처럼 한 번 묻는다(묻는 값은 역할마다 같다). 같은 품번은 그대로 동일품이다."""
    asked = []
    monkeypatch.setattr(J, 'interrupt', lambda payload: asked.append(payload) or {'answers': {}})
    out = J.judge_agent({**SAME, 'judge_read': dict(SAME_READ, candidates=['SS34', 'SS14'])}, specs=specs_of(SAME_SPECS), find=None, retriever=None)
    verdicts = {x['part']: x['verdict'] for x in out['judgement']['results']}
    assert len(asked) == 1 and verdicts['SS34'] == 'IDENTICAL' and verdicts['SS14'] != 'IDENTICAL'

@pytest.mark.parametrize('text', [
    '추가 조건으로 확인할 수 있는 내용은 없어',
    '사용 조건을 모르겠어.',
    '사용 조건 모름',
    '모름',
    '추가 사용 조건은 알려줄 수 없어.',
])
def test_declined_conditions_do_not_interrupt_or_invent_inputs(monkeypatch, text):
    monkeypatch.setattr(J, 'interrupt', no_interrupt)
    read = J.JudgeRead(role='R01', original_part='1N4001', candidates=['1N5817']).model_dump(mode='json')
    out = J.judge_agent({**STATE, 'conditions': text, 'judge_read': read}, specs=specs_of(SPECS), find=None, retriever=None)
    j = out['judgement']
    assert j['asked'] == []
    assert j['analysis_inputs']['values_si'] == {}
    assert j['results'][0]['verdict'] == 'NOT_VERIFIED'
    assert j['results'][0]['missing']


@pytest.mark.parametrize('text', [
    '', '사용 조건을 알려줘.', '사용 조건을 모르면 어떻게 되나요?',
    '제조사를 모르겠어.', '온도는 모르겠어.', '사용 조건 중 온도를 모르겠어.', '사용 조건을 모르겠다는 뜻은 아니야.',
])
def test_other_unknowns_do_not_skip_all_condition_questions(monkeypatch, text):
    asked = []
    monkeypatch.setattr(J, 'interrupt', lambda payload: asked.append(payload) or {'answers': {}})
    read = J.JudgeRead(role='R01', original_part='1N4001', candidates=['1N5817']).model_dump(mode='json')
    J.judge_agent({**STATE, 'conditions': text, 'judge_read': read}, specs=specs_of(SPECS), find=None, retriever=None)
    assert len(asked) == 1 and 'v_in_max' in asked[0]['missing']


def test_declining_more_conditions_preserves_known_inputs_and_failures(monkeypatch):
    monkeypatch.setattr(J, 'interrupt', no_interrupt)
    out = J.judge_agent({**STATE, 'conditions': STATE['conditions'] + '\n추가 조건으로 확인할 수 있는 내용은 없어', 'judge_read': READ}, specs=specs_of(SPECS), find=None, retriever=None)
    assert out['judgement']['analysis_inputs']['values_si']['v_in_max'] == 20
    assert out['judgement']['results'][0]['verdict'] == 'NOT_SUFFICIENT'


def test_declining_conditions_does_not_skip_role_choice(monkeypatch):
    asked = []
    monkeypatch.setattr(J, 'interrupt', lambda payload: asked.append(payload) or {'answers': {}, 'role': 'R01'})
    read = J.JudgeRead(role='R01', role_alt='R02', original_part='1N4001', candidates=['1N5817']).model_dump(mode='json')
    J.judge_agent({**STATE, 'conditions': '사용 조건을 모르겠어.', 'judge_read': read}, specs=specs_of(SPECS), find=None, retriever=None)
    assert len(asked) == 1 and asked[0]['missing'] == []
    assert asked[0]['role_choices'] == ['R01', 'R02']
@pytest.mark.parametrize('source', ['history', 'circuit'])
def test_unknown_conditions_only_apply_to_current_user_words(monkeypatch, source):
    asked = []
    monkeypatch.setattr(J, 'interrupt', lambda payload: asked.append(payload) or {'answers': {}})
    read = J.JudgeRead(role='R01', original_part='1N4001', candidates=['1N5817']).model_dump(mode='json')
    state = {**STATE, 'conditions': '', 'judge_read': read}
    if source == 'history':
        state['conversation_history'] = ['사용 조건을 모르겠어.']
    else:
        state['target_part'] = {**STATE['target_part'], 'nets': [{'name': '사용 조건을 모르겠어.', 'nodes': []}]}
    J.judge_agent(state, specs=specs_of(SPECS), find=None, retriever=None)
    assert len(asked) == 1 and asked[0]['missing']
