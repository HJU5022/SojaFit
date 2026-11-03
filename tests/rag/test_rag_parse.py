"""파싱 도구(backend/rag/pipeline/parse.py)의 Docling 없이 도는 부분: 숫자 세기, 표 좌표 바꾸기, 시간 제한 지원 여부.

- 역할: 숫자 세기(µ 통일), 표 좌표 바꾸기, SIGALRM 지원 여부를 확인한다.
- 하지 않는 일: Docling 변환과 실제 PDF 파싱은 하지 않는다.
- 출처: docs/specs/rag-pipeline.md What 3, EC-02·EC-10
"""
import signal

from backend.rag.pipeline import parse


def test_numbers_counts_and_unifies_micro():
    got = parse.numbers('IR 5 μA, IR 5 µA, -55 to +125, 1N4148')
    assert got['5'] == 2 and got['-55'] == 1 and got['+125'] == 1 and '4148' not in got


def test_table_box_flips_bottom_left_origin():
    bb = {'l': 10, 't': 700, 'r': 200, 'b': 600, 'coord_origin': 'BOTTOMLEFT'}
    assert parse.table_box(bb, page_h=800, page_w=600) == (10, 100, 200, 200)
    assert parse.table_box({**bb, 'r': 10}, page_h=800, page_w=600) is None  # 넓이가 없는 표


def test_alarm_support_matches_os():
    assert parse.HAS_ALARM == hasattr(signal, 'SIGALRM')
