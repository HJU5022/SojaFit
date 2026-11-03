"""표 청크 규칙과 문서 키, manifest 크기를 지킨다.

- 역할: 합친 칸 채우기, 머리 행 두 줄 잇기, 빈 표 건너뛰기, 문서 키, data/manifest.jsonl이 512,000바이트 아래인지 확인한다. Docling 없이 돈다.
- 하지 않는 일: 실제 PDF 파싱·전체 청크 수(AC-03)는 확인하지 않는다.
- 출처: docs/specs/rag-pipeline.md AC-01·AC-02, EC-03
"""
import os

from backend.rag.pipeline.chunk import doc_key, revision, table_cards

# 3행 3열 표: 0행이 머리. 1열(VRRM) 칸 하나가 1~2행에 걸쳐 합쳐져 있다.
CELLS = [
    (0, 1, 0, 1, 'PARAMETER', True), (0, 1, 1, 2, 'SYMBOL', True), (0, 1, 2, 3, '1N5817', True),
    (1, 3, 0, 1, 'Reverse voltage', False), (1, 2, 1, 2, 'VRRM', False), (1, 2, 2, 3, '20', False),
    (2, 3, 1, 2, 'VR(RMS)', False), (2, 3, 2, 3, '14', False),
]


def test_merged_cell_fills_every_row():
    cards = table_cards('1N5817 SERIES_H2104.pdf', 1, 3, 3, CELLS)
    assert len(cards) == 2
    assert all('PARAMETER: Reverse voltage' in c['text'] for c in cards)
    assert cards[1]['text'] == '[1N5817 SERIES_H2104.pdf · 1쪽 · PARAMETER] PARAMETER: Reverse voltage | SYMBOL: VR(RMS) | 1N5817: 14'


def test_two_header_rows_join_once():
    cells = [(0, 2, 0, 1, 'PARAMETER', True), (0, 1, 1, 2, 'VF', True), (1, 2, 1, 2, 'MAX', True),
             (2, 3, 0, 1, 'IF = 1A', False), (2, 3, 1, 2, '0.45', False)]
    (card,) = table_cards('a.pdf', 2, 3, 2, cells)
    assert card['text'].endswith('PARAMETER: IF = 1A | VF / MAX: 0.45')


def test_empty_table_gives_no_card():
    assert table_cards('a.pdf', 1, 0, 3, []) == []


def test_doc_key_and_revision():
    assert doc_key('1N4148 SERIES_K2301.pdf') == 'tsc-1n4148-series_k2301'
    assert revision('1N4148 SERIES_K2301.pdf') == 'K2301'


def test_manifest_fits_checkpoint_dashboard():
    # [왜] Checkpoint 대시보드가 1,012,774바이트 manifest를 "커서 읽지 못함"으로 표시했다(11-02). GitHub GraphQL은 512,000바이트에서 자른다
    assert os.path.getsize('data/manifest.jsonl') < 512_000
