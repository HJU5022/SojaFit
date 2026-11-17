"""다음 턴에 싣는 직전 판정 요약(`memory_service._last_judgement`): 실제 모델에서는 싣고, 기록 재생(데모)에서는 싣지 않는다(DB 없이 순수 함수)."""
from backend.conversations.memory_service import _last_judgement

JUDGED = {'target': 'D2', 'judgement': {'kind': 'find', 'roles': ['R02'], 'results': [{'part': 'SS34L', 'verdict': 'SPEC_EQUIVALENT', 'board_change': True}]}}


def test_live_mode_carries_the_summary_and_keeps_it_across_turns_without_a_judgement():
    last = _last_judgement('live', JUDGED)
    assert last['target'] == 'D2' and last['kind'] == 'find' and [c['part'] for c in last['candidates']] == ['SS34L']
    # 판정 없는 턴(일상 대화 · 견적 안내)을 지나도 앞 요약이 남는다
    assert _last_judgement('live', {'target': 'D2', 'judgement': {}, 'last_judgement': last}) == last
    assert _last_judgement('live', {}) == {}  # 새 대화


def test_demo_replay_never_carries_it():
    """기록 재생에서 요약을 실으면 계획 입력에 앞 턴 글이 붙어 기록에 없는 LLM 호출이 된다(ReplayMiss). 한 대화에서 기록 질문을 이어 물어도 싣지 않는다."""
    assert _last_judgement('demo', JUDGED) == {}
    assert _last_judgement('demo', {'last_judgement': {'candidates': [{'part': 'SS34L', 'verdict': 'SPEC_EQUIVALENT'}]}}) == {}
