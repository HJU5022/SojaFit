"""읽기 뒤 품번 바로잡기(backend/multi_agent/agents/part_names.py) 시험: 사용자 글의 품번으로 맞추고, 지어내지 않는다.

- 역할: 11-10 읽기 6회 반복에서 흔들린 h4-02 · judgedev-16 글(작은 고정 글로 옮김)과 음성 사례.
- 하지 않는 일: LLM · MCP · DB 호출.
- 출처: SPEC 8.3 "읽기 뒤 품번 바로잡기"
"""
import pytest

from backend.multi_agent.agents.part_names import current_part, ground_part_names, part_tokens

H4_02 = {'target': 'D2', 'target_part': {'ref': 'D2', 'value': 'SS34', 'nets': []},
         'conditions': 'D2는 앞서 TSC SS26으로 교체했고 기판도 SMB로 수정한 상태다. NES_5V와 USB VBUS는 각각 최대 5.25V이고 D2 연속 전류 최대 250mA, 주변 온도 25°C이다.',
         'question': 'D2에 지금 SS26 대신 TSC SS26H를 쓰면 전원 두 개를 나눠 받는 기능을 유지할 수 있어? 끝 글자 차이까지 포함해서 검토해 줘.'}
DEV_16 = {'target': 'D5', 'target_part': {'ref': 'D5', 'value': '1N5231', 'nets': []},
          'conditions': '지금 D5는 TSC 1N5231B이다. SW_POS에는 외부 스위치를 거쳐 최대 10V가 들어온다. 주변 온도는 25°C이다.',
          'question': 'D5를 TSC MMSZ5231B로 바꿔도 ENABLE 입력 보호가 지금처럼 될까?'}


def st(question='', conditions='', value='', ref='D1'):
    return {'target': ref, 'target_part': {'ref': ref, 'value': value, 'nets': []}, 'question': question, 'conditions': conditions}


@pytest.mark.parametrize('orig', ['SS34', 'SS26', 'TSC SS26', ''])
@pytest.mark.parametrize('cand', ['SS26H', 'TSC SS26H'])
def test_h4_02_current_part_wins_over_netlist_value(orig, cand):
    assert ground_part_names(orig, [cand], H4_02) == ('SS26', ['SS26H'])


@pytest.mark.parametrize('orig', ['1N5231', '1N5231B', 'TSC 1N5231B'])
@pytest.mark.parametrize('cand', ['MMSZ5231B', 'TSC MMSZ5231B'])
def test_judgedev_16_names_come_from_text(orig, cand):
    assert ground_part_names(orig, [cand], DEV_16) == ('1N5231B', ['MMSZ5231B'])


def test_truncated_name_extends_to_unique_text_token_without_current_rule():
    s = st('D1을 SMAJ5.0A로 바꿔도 돼?', 'D1은 SMAJ5.0 계열이 아니다.', value='SMAJ5.0A')
    assert ground_part_names('SMAJ5', ['SMAJ5.0A'], s)[1] == ['SMAJ5.0A']
    assert ground_part_names('SMAJ5.0', [], st('SMAJ5.0A를 쓴다'))[0] == 'SMAJ5.0A'


def test_no_part_in_text_leaves_read_untouched():
    assert ground_part_names('1N4148', ['BAT54'], st('이 다이오드를 바꿔도 돼?')) == ('1N4148', ['BAT54'])


def test_ambiguous_prefix_is_not_guessed():
    s = st('1N5231B와 1N5231C 중 어느 쪽이 좋아?')
    assert ground_part_names('1N5231', [], s) == ('1N5231', [])


def test_two_current_parts_do_nothing():
    s = st('D1을 SS26H로 바꿔도 돼?', 'D1은 SS14로 교체했고 SS26으로 교체했다.', value='SS34', ref='D1')
    assert current_part(s['conditions'], s['question'], 'D1', set()) is None
    assert ground_part_names('SS34', ['SS26H'], s)[0] == 'SS34'


def test_future_replacement_is_not_current():
    s = st('D1을 SS26H로 교체했다면 어때?', value='SS34')
    assert ground_part_names('SS34', ['SS26H'], s) == ('SS34', ['SS26H'])


def test_other_refs_replacement_is_ignored():
    s = st('D1을 SS26H로 바꿔도 돼?', 'D3는 SS14로 교체했다.', value='SS34')
    assert ground_part_names('SS34', ['SS26H'], s)[0] == 'SS34'


def test_candidate_never_becomes_original():
    # 지금 달린 부품이 후보와 같은 글이면(후보를 원래로 읽은 것) 따르지 않는다
    s = st('D1에 SS26H로 교체했다. D1에 지금 SS26H를 달아 쓰고 있다', value='SS34')
    assert ground_part_names('SS34', ['SS26H'], s)[0] == 'SS34'
    # 원래가 후보의 앞부분일 때 후보 품번으로 늘리지 않는다
    assert ground_part_names('SS26', ['SS26H'], st('TSC SS26H로 바꿔도 돼?'))[0] == 'SS26'


def test_order_code_forms_are_kept_with_single_space():
    s = st('D1에 쓸 LL4448 L0 대신 TSC LL4448 L0G로 바꿔도 돼?', value='LL4448')
    assert part_tokens(s['question'], {'D1'}) == ['LL4448', 'LL4448 L0', 'LL4448 L0G']
    assert ground_part_names('LL4448 L0', ['TSC LL4448  L0G'], s) == ('LL4448 L0', ['LL4448 L0G'])
