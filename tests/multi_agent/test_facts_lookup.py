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
