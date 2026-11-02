"""파싱 도구(backend/rag/parse.py)의 Docling 없이 도는 부분: 숫자 세기, 표 좌표 바꾸기, 시간 제한 지원 여부."""
import signal

from backend.rag import parse


def test_numbers_counts_and_unifies_micro():
    got = parse.numbers('IR 5 μA, IR 5 µA, -55 to +125, 1N4148')
    assert got['5'] == 2 and got['-55'] == 1 and got['+125'] == 1 and '4148' not in got


def test_table_box_flips_bottom_left_origin():
    bb = {'l': 10, 't': 700, 'r': 200, 'b': 600, 'coord_origin': 'BOTTOMLEFT'}
    assert parse.table_box(bb, page_h=800, page_w=600) == (10, 100, 200, 200)
    assert parse.table_box({**bb, 'r': 10}, page_h=800, page_w=600) is None  # 넓이가 없는 표


def test_alarm_support_matches_os():
    assert parse.HAS_ALARM == hasattr(signal, 'SIGALRM')
