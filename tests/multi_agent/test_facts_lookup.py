"""사실 확인 노드가 MCP 도구(`check_corpus`) 응답으로 Facts를 만드는지 확인한다(도구는 가짜 함수)."""
import pytest

from backend.multi_agent.facts import facts_node, make_lookup


def state(question, ref='D4'):
    return {'question': question, 'target_part': {'ref': ref, 'nets': [{'nodes': [f'{ref}.1', 'R1.2']}]}}


def test_lookup_asks_tool_with_parts_and_revisions_from_question():
    calls = []

    def check(parts, revisions):
        calls.append((parts, revisions))
        return {'parts': {'1N5819': True, '1N4001': False}, 'revisions': {'Q2611': False}}

    facts = make_lookup(check)(state('D4를 1N5819 또는 1N4001로 바꿀 수 있어? Q2611판 기준'))
    assert calls == [(['1N5819', '1N4001'], ['Q2611'])]  # 회로 기호 D4·R1은 품번으로 뽑지 않는다
    assert facts.parts == {'1N5819': True, '1N4001': False} and facts.revisions == {'Q2611': False}


def test_lookup_skips_tool_when_nothing_to_verify():
    def check(parts, revisions):
        raise AssertionError('도구를 부르면 안 된다')

    facts = make_lookup(check)(state('이 다이오드는 회로에서 무슨 일을 해?'))
    assert facts.parts == {} and facts.revisions == {}


def test_facts_node_stores_dict_and_path():
    out = facts_node(state('1N4001 알려줘'), lookup=make_lookup(lambda p, r: {'parts': {'1N4001': False}, 'revisions': {}}))
    assert out == {'facts': {'parts': {'1N4001': False}, 'revisions': {}}, 'path': ['사실 확인']}



@pytest.mark.parametrize('question, sent, parts', [
    # 주문 코드(R0G)는 띄어 쓴 앞 기본 품번이 있으면 있다(판정 코드와 같은 규칙)
    ('D4를 1N4148 R0G로 바꿀 수 있어?', ['1N4148', 'R0G'], {'1N4148': True, '1N4148 R0G': True}),
    ('D4를 1N9999 R0G로 바꿀 수 있어?', ['1N9999', 'R0G'], {'1N9999': False, 'R0G': False}),  # 기본 품번도 없으면 그대로 없다
    ('D4를 1N4148, BAT85 중 뭘로 바꿔?', ['1N4148', 'BAT85'], {'1N4148': True, 'BAT85': False}),  # 띄어쓰기로만 붙은 낱말이 아니면 따로 본다
    ('D4를 1N4148 BAT85 중 뭘로 바꿔?', ['1N4148', 'BAT85'], {'1N4148': True, 'BAT85': False}),  # 주문 코드 모양이 아니면 띄어 써도 따로 본다
])
def test_lookup_treats_ordering_code_as_base_part(question, sent, parts):
    calls = []

    def check(names, revisions):
        calls.append(names)
        return {'parts': {p: p == '1N4148' for p in names}, 'revisions': {}}

    facts = make_lookup(check)(state(question))
    assert calls == [sent]  # 도구에는 뽑은 낱말 그대로 묻는다(check_corpus 계약 그대로)
    assert facts.parts == parts


def test_pin_net_and_standard_names_are_not_part_numbers():
    # [왜] 'PB3 쪽 D1'의 핀 이름과 'AEC-Q101'을 코퍼스에 없는 품번으로 보고 거절했다(11-06 v3-13 · 14)
    from backend.graph.nodes import find_parts
    from backend.multi_agent.facts import refs_of
    tp = {'ref': 'D1', 'nets': [{'name': '/PB3', 'nodes': ['D1.K', 'U1.PB3', 'R2.2']}]}
    assert find_parts('PB3 쪽 D1 후보, AEC-Q101 적합, IEC61000-4-2, SS14H', refs_of(tp)) == ['SS14H']


def test_kicad_pin_names_with_alternate_functions_are_not_parts():
    """[왜] 실제 넷리스트 핀은 'U1.XTAL1/PB3_2(ATtiny85-20SU)' 모양이다. 핀 이름 PB3 · XTAL1은 빼고 괄호 속 부품 값은 남긴다(11-06 v3-13)."""
    from backend.graph.nodes import find_parts
    from backend.multi_agent.facts import refs_of
    tp = {'ref': 'D1', 'nets': [{'name': 'Net-(D1-K)', 'nodes': ['D1.K_3(BZX84C3V3)', 'U1.XTAL1/PB3_2(ATtiny85-20SU)']}]}
    refs = refs_of(tp)
    assert {'PB3', 'XTAL1', 'K'} <= refs and 'BZX84C3V3' not in refs
    assert find_parts('PB3 쪽 D1의 BZX84C3V3 대체 후보', refs) == ['BZX84C3V3']


def test_year_edition_is_checked_against_the_named_parts_document_revisions():
    from backend.multi_agent.facts import year_editions
    rows = lambda part, codes=None: [{'citation': {'document': '1N5817 SERIES_H2104.pdf'}}]
    # [왜] 연도로 요구한 판은 그 품번 문서의 개정 코드 연도(H2104 → 21)와 맞춰 본다. 없으면 '없음'(v2 draft30-e10)
    assert year_editions('TSC 1N5817의 2026년판 데이터시트에서 역전압은?', ['1N5817'], {'1N5817': True}, rows) == {'2026년판': False}
    assert year_editions('1N5817 2021년 개정판 기준', ['1N5817'], {'1N5817': True}, rows) == {'2021년개정판': True}
    # 품번 없이 회로 판을 말하면 확인할 문서가 없어 '없음'이다
    assert year_editions('Franzininho DIY 2026년 개정판에서는 D3를 뭘로 써?', [], {}, None) == {'2026년개정판': False}
    assert year_editions('Pro Micro 2026년 USB-C판에서는?', [], {}, None) == {'2026년USB-C판': False}


def test_revision_codes_are_read_from_file_names_too():
    from backend.multi_agent.facts import revisions_in
    assert revisions_in('US1A SERIES_N2602.pdf에 있는 VF를 알려 줘') == ['N2602']  # 11-07 h4-47
    assert revisions_in('K2611판과 1N4148 SERIES_K2301.pdf') == ['K2611', 'K2301']


def test_a_file_name_revision_must_belong_to_the_named_parts_documents():
    check = lambda parts, revs: {'parts': {p: True for p in parts}, 'revisions': {r: True for r in revs}}  # 전역으로는 N2602가 있다
    specs = lambda part, codes=None: [{'citation': {'document': 'US1A SERIES_N2102.pdf'}}]
    facts = make_lookup(check, specs)(state('TSC US1J를 US1A SERIES_N2602.pdf에서 확인해 줘'))
    assert facts.revisions['N2602'] is False  # 그 품번 문서는 N2102뿐이다(h4-47)
