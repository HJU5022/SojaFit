"""표 청크 규칙과 문서 키, manifest 크기를 지킨다.

- 역할: 합친 칸 채우기, 머리 행 두 줄 잇기, 빈 표 건너뛰기, 행이 가리키는 주석만 붙이기, 문서 키, data/manifest.jsonl이 512,000바이트 아래인지 확인한다.
  문서 한 개를 청크로 바꾸는 시험(개요 · 표 주석 · 머리글 쓰레기)만 docling_core가 있어야 돌고(없으면 건너뜀), 나머지는 Docling 없이 돈다.
- 하지 않는 일: 실제 PDF 파싱·전체 청크 수(AC-03)는 확인하지 않는다.
- 출처: docs/specs/rag-pipeline.md AC-01·AC-02, EC-03, ADR 0015(표 주석 누락)
"""
import os

import pytest

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


def test_row_gets_only_the_note_it_marks():
    # [왜] 주석을 행과 떼어 두면 LLM이 행의 "(1)"이 무슨 뜻인지 모른다(11-06). 표시한 주석만 붙여 행 본문을 흐리지 않는다
    cells = [(0, 1, 0, 1, 'PARAMETER', True), (0, 1, 1, 2, 'MAX', True),
             (1, 2, 0, 1, 'Forward voltage (1)', False), (1, 2, 1, 2, '1', False),
             (2, 3, 0, 1, 'Reverse current (2)', False), (2, 3, 1, 2, '25', False)]
    vf, ir = table_cards('a.pdf', 2, 3, 2, cells, ['1. Pulse test with PW = 0.3ms', '2. Pulse test with PW = 30ms'])
    assert vf['text'].endswith('MAX: 1\n주: 1. Pulse test with PW = 0.3ms')
    assert ir['text'].endswith('MAX: 25\n주: 2. Pulse test with PW = 30ms')


def test_doc_cards_keeps_title_and_table_notes():
    pytest.importorskip('docling_core')
    from docling_core.types.doc import BoundingBox, DocItemLabel, DoclingDocument, ProvenanceItem, TableCell, TableData

    from backend.rag.pipeline.chunk import doc_cards

    def at(page):
        return ProvenanceItem(page_no=page, bbox=BoundingBox(l=0, t=0, r=1, b=1), charspan=(0, 0))
    doc = DoclingDocument(name='a')
    pic = doc.add_picture(prov=at(1))
    doc.add_text(label=DocItemLabel.TEXT, text='150mA, 100V Switching Diode', parent=pic, prov=at(1))
    doc.add_text(label=DocItemLabel.TEXT, text='Taiwan Semiconductor', prov=at(1))  # 머리글이 본문으로 잡힌 쓰레기
    doc.add_text(label=DocItemLabel.SECTION_HEADER, text='MECHANICAL DATA', prov=at(1))
    doc.add_text(label=DocItemLabel.LIST_ITEM, text='Case: DO-35', prov=at(1))
    cell = lambda r, c, t, h: TableCell(text=t, start_row_offset_idx=r, end_row_offset_idx=r + 1,  # noqa: E731
                                        start_col_offset_idx=c, end_col_offset_idx=c + 1, column_header=h)
    doc.add_table(data=TableData(num_rows=2, num_cols=2, table_cells=[
        cell(0, 0, 'ORDERING CODE (1)', True), cell(0, 1, 'PACKAGE', True), cell(1, 0, '1N4148 R0G', False), cell(1, 1, 'DO-35', False)]),
        prov=at(2))
    doc.add_text(label=DocItemLabel.SECTION_HEADER, text='Notes:', prov=at(2))
    doc.add_text(label=DocItemLabel.TEXT, text='1. Above ordering codes refer to physically identical parts', prov=at(2))
    doc.add_text(label=DocItemLabel.SECTION_HEADER, text='Notice', prov=at(3))
    doc.add_text(label=DocItemLabel.TEXT, text='Specifications are subject to change without notice.', prov=at(3))
    cards, _, _ = doc_cards(doc, 'a.pdf', ['1N4148'])
    by = {}
    for c in cards:
        by.setdefault(c['kind'], []).append(c)
    assert by['cover'][0]['text'] == '[a.pdf] 이 데이터시트의 품번: 1N4148'
    assert by['overview'][0] == {'kind': 'overview', 'page': 1, 'table': None, 'row': None,
                                 'text': '[a.pdf · 1쪽 · 제품 개요] 150mA, 100V Switching Diode'}
    assert [c['text'] for c in by['text']] == ['[a.pdf · 1쪽 · MECHANICAL DATA] Case: DO-35']  # 쓰레기 · 법적 고지는 없다
    assert by['table_row'][0]['text'].endswith('PACKAGE: DO-35\n주: 1. Above ordering codes refer to physically identical parts')
    assert by['note'][0]['page'] == 2 and 'physically identical parts' in by['note'][0]['text']


def test_title_leak_is_removed_and_header_word_returns():
    # [왜] 표 위 세로 제목이 첫 데이터 행에 섞이면(BZV55B · SMAJ 등 245개 표) 값 칸이 '낱말 + 숫자'가 되고 열 이름이 비어 사양 표가 값을 못 읽었다(11-06)
    cells = [(0, 1, 0, 1, 'PART NUMBER', True), (0, 1, 1, 2, 'ZENER', True), (0, 1, 2, 3, 'IZT mA', True),
             (1, 2, 0, 1, 'ELECTRICAL BZV55B2V4', False), (1, 2, 1, 2, 'Min 2.35', False), (1, 2, 2, 3, 'unless 5', False),
             (2, 3, 0, 1, 'BZV55B3V3', False), (2, 3, 1, 2, '3.23', False), (2, 3, 2, 3, '5', False),
             (3, 4, 0, 1, 'BZV55B3V6', False), (3, 4, 1, 2, '3.53', False), (3, 4, 2, 3, '5', False)]
    first, second, _ = table_cards('a.pdf', 2, 4, 3, cells)  # [주의] 숫자 열 판정(60%)이 실제 표처럼 서려면 행이 셋은 있어야 한다
    assert first['text'].endswith('PART NUMBER: BZV55B2V4 | ZENER / Min: 2.35 | IZT mA: 5')
    assert second['text'].endswith('PART NUMBER: BZV55B3V3 | ZENER / Min: 3.23 | IZT mA: 5')


def test_merged_row_splits_only_when_every_cell_splits():
    head = [(0, 1, 0, 1, 'Part number', True), (0, 1, 1, 2, 'VWM', True), (0, 1, 2, 3, 'VC', True)]
    ok = head + [(1, 2, 0, 1, 'SMBJ5.0A SMBJ6.0A', False), (1, 2, 1, 2, '5.0 6.0', False), (1, 2, 2, 3, '9.2 10.3', False)]
    assert [c['text'].split('] ')[1] for c in table_cards('a.pdf', 2, 2, 3, ok)] == [
        'Part number: SMBJ5.0A | VWM: 5.0 | VC: 9.2', 'Part number: SMBJ6.0A | VWM: 6.0 | VC: 10.3']
    # [주의] 값이 하나뿐인 칸이 있으면 어느 품번 값인지 몰라 나누지 않는다(SMBJH '14 1 15 1 | 23.1')
    bad = head + [(1, 2, 0, 1, 'SMBJ14AH SMBJ15H', False), (1, 2, 1, 2, '14 15', False), (1, 2, 2, 3, '23.1', False)]
    assert len(table_cards('a.pdf', 2, 2, 3, bad)) == 1


def test_recover_rows_reads_pdf_lines_only_when_counts_match():
    # [왜] Docling이 여러 행을 한 칸에 섞은 TVS 표는 PDF 배치 줄(pdftotext -layout)에서 품번마다 값을 다시 읽는다(SMBJ 2쪽, 11-06)
    from backend.rag.pipeline.chunk import recover_rows
    lines = [['SMBJ13A', 'LG', '14.4', '15.9'], ['SMBJ5.0A'], ['KE', '6.40', '7.00'], ['SMBJ14', 'LH', '15.6']]
    assert recover_rows(['SMBJ13A', 'SMBJ5.0A', 'SMBJ14', 'SMBJ99'], lines, 4) == [
        ['SMBJ13A', 'LG', '14.4', '15.9'], ['SMBJ5.0A', 'KE', '6.40', '7.00']]  # 값이 모자란 SMBJ14 · 없는 SMBJ99는 빼낸다


def test_merged_numeric_column_is_split_and_named():
    # [왜] SMBJH 2쪽은 VWM과 누설전류 ID 열이 한 열('5.0 800')로 합쳐지고 빠진 열 이름이 첫 행에 섞였다(11-06)
    from backend.rag.pipeline.chunk import split_merged_columns
    grid = [['Part', 'VWM (V)'], ['SMBJ5.0AH', 'ID@VWM (µA) 5.0 800'], ['SMBJ6.0AH', '6.0 800'], ['SMBJ6.5AH', '6.5 500'],
            ['SMBJ14AH SMBJ15H', '14 1 15 1'], ['SMBJ7.0AH', '7.0 200'], ['SMBJ7.5AH', '7.5 100']]
    out, _ = split_merged_columns(grid, [True] + [False] * 6)  # 숫자 둘 칸 4/6 ≥ 60%
    assert out[0] == ['Part', 'VWM (V)', 'ID@VWM (µA)']
    assert out[1][1:] == ['5.0', '800'] and out[3][1:] == ['6.5', '500'] and out[4][1:] == ['14 15', '1 1']


def test_generic_table_title_is_recovered_from_the_pdf_line_above_its_header():
    """[왜] 제목이 머리 칸('PARAMETER')이거나 잘리면 표 기본 조건 TA = 25°C를 잃어 25°C 행 고르기에서 '확인 안 됨'이 됐다(11-06 v3-12)."""
    from backend.rag.pipeline import chunk
    page = [l.split() for l in [
        'HER101G – HER108G', 'THERMAL PERFORMANCE', 'PARAMETER SYMBOL TYP UNIT', 'Junction-to-ambient thermal resistance RӨJA 60 °C/W',
        'ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)', 'PARAMETER CONDITIONS SYMBOL TYP MAX UNIT', 'HER101G',
        'Forward voltage IF = 1A, TJ = 25°C VF']]
    names = ['PARAMETER', 'CONDITIONS', 'SYMBOL', 'TYP', 'MAX', 'UNIT']
    assert chunk.needs_title('PARAMETER') and chunk.needs_title('ELECTRICAL SPECIFICATIONS (TA') and not chunk.needs_title('KEY PARAMETERS')
    assert chunk.page_title(page, 'PARAMETER', names) == 'ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)'
    assert chunk.page_title(page, 'PARAMETER', ['PARAMETER', 'SYMBOL', 'TYP', 'UNIT']) == 'THERMAL PERFORMANCE'
    assert chunk.page_title(page, 'ELECTRICAL SPECIFICATIONS (TA', names) == 'ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)'
    split = [l.split() for l in ['ELECTRICAL SPECIFICATIONS (TA = 25°C unless', 'otherwise noted)', 'PART NUMBER VZ', 'BZT52C2V4 2.28']]
    assert chunk.page_title(split, 'PART NUMBER', ['PART NUMBER', 'VZ']) == 'ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)'
    assert chunk.page_title(page, 'DIM.', ['DIM.', 'MIN']) is None  # 찾지 못하면 원래 제목을 그대로 둔다


def test_shared_symbol_goes_before_a_slot_word_glued_to_the_end_of_a_piece():
    """[왜] 'ZENER / VOLTAGE 2) Max.'에 기호를 뒤에 붙여 열 이름 끝이 'VZ @ IZT'가 되자 사양 표가 최대 칸을 못 알아봤다(BZX84C 30품번)."""
    from backend.rag.pipeline import chunk
    names = ['ZENER / VZ @ IZT / Nom.', 'ZENER / V / (Note Min.', 'ZENER / VOLTAGE 2) Max.']
    out = chunk.share_symbol(names)
    assert out[2] == 'ZENER / VOLTAGE 2) / VZ @ IZT / Max.' and out[1] == 'ZENER / V / (Note / VZ @ IZT / Min.'


def test_h_variants_come_from_ordering_templates_with_the_aec_note():
    """[왜] H(AEC-Q101) 품번이 주문 정보의 틀('1N581xH')로만 적힌 문서가 142개다. 표지 품번에 넣어야 1N5819H를 코퍼스 품번으로 안다(판정 dev 14)."""
    from backend.rag.pipeline import chunk
    row = {'kind': 'table_row', 'text': 'ORDERING CODE (1)(2): 1N581xHA0G | PACKAGE: DO-41\n주: 2. "H" means AEC-Q101 qualified'}
    assert chunk.h_variants([row], ['1N5817', '1N5819', '1N5819H']) == ['1N5817H']  # 이미 있는 품번은 다시 만들지 않는다
    assert chunk.h_variants([{**row, 'text': 'ORDERING CODE: 1N581xH | PACKAGE: DO-41'}], ['1N5817']) == []  # 주석이 없으면 만들지 않는다


def test_merged_cell_over_two_slots_is_written_once():
    # [왜] pdfplumber 칸에서 합쳐진 칸이 자리 둘에 걸치면 'UNIT: V | UNIT: V'처럼 되풀이됐다(11-08). 바로 옆의 같은 '이름: 값'은 한 번만 쓴다
    cells = [(0, 1, 0, 2, 'PARAMETER', True), (0, 1, 2, 3, 'MAX', True), (0, 1, 3, 5, 'UNIT', True),
             (1, 2, 0, 2, 'Forward voltage', False), (1, 2, 2, 3, '0.63', False), (1, 2, 3, 5, 'V', False)]
    cards = table_cards('X.pdf', 2, 2, 5, cells)
    assert cards[0]['text'].endswith('PARAMETER: Forward voltage | MAX: 0.63 | UNIT: V')


# 아래 세 시험은 실제 PDF와 Docling 캐시로 표 칸 읽기(결정 22)를 지킨다. 기대값은 코덱스가 PDF 2쪽과 대조한 값이다
# (evals/drafts/chunkcheck/check_notes.md, 11-08). 코퍼스가 없는 환경에서는 건너뛴다.
CORPUS = os.getenv('SOJAFIT_CORPUS') or os.path.join(os.path.dirname(__file__), *['..'] * 4, 'corpus', 'tsc')


def _page2_rows(file):
    pytest.importorskip('docling_core')
    pytest.importorskip('pdfplumber')
    json_path, pdf_path = os.path.join(CORPUS, 'parsed', 'docling', file + '.json'), os.path.join(CORPUS, 'pdf', file)
    if not (os.path.exists(json_path) and os.path.exists(pdf_path)):
        pytest.skip('코퍼스 PDF · Docling 캐시가 없다')
    from docling_core.types.doc import DoclingDocument
    from backend.rag.pipeline.chunk import doc_cards
    log = {}
    cards, *_ = doc_cards(DoclingDocument.load_from_json(json_path), file, [], pdf_path, log)
    assert dict(log['tables']).get('pdfplumber', 0) >= 1
    return [c['text'] for c in cards if c['kind'] == 'table_row' and c['page'] == 2]


def test_es2a_shared_values_follow_the_merged_part_cell():
    rows = _page2_rows('ES2A SERIES_L2102.pdf')
    cj20 = [r for r in rows if 'SYMBOL: CJ' in r and 'TYP: 20' in r]
    assert len(cj20) == 1 and 'ES2F ES2G ES2H ES2J' in cj20[0]  # Docling은 ES2J를 다음 줄(TRR)로 넘겼다
    trr = [r for r in rows if 'SYMBOL: trr' in r]
    assert len(trr) == 1 and 'MAX: 35' in trr[0] and 'ES2J' not in trr[0]  # TRR 35ns는 계열 전체 값이다


def test_rs1dal_two_line_part_cell_covers_four_rows_and_trr_keeps_its_symbol():
    rows = _page2_rows('RS1DAL SERIES_C2304.pdf')
    vf_km = [r for r in rows if 'SYMBOL: VF' in r and 'RS1KAL' in r]
    assert len(vf_km) == 4 and all('RS1KAL RS1MAL' in r for r in vf_km)  # Docling은 RS1KAL · RS1MAL을 두 칸으로 나눴다
    assert len([r for r in rows if 'SYMBOL: trr' in r]) == 3  # Docling은 IR · trr 기호를 한 칸으로 합쳤다


def test_mbrf1635_each_temperature_block_keeps_its_own_condition():
    rows = [r for r in _page2_rows('MBRF1635 SERIES_K2105.pdf') if 'SYMBOL: VF' in r]
    for value, cond in [('0.63', '25°C'), ('0.85', '25°C'), ('0.95', '25°C'), ('0.57', '125°C'), ('0.65', '125°C'), ('0.92', '125°C')]:
        row = next(r for r in rows if f'MAX: {value} ' in r)
        other = '125°C' if cond == '25°C' else 'TJ = 25°C'
        assert f'TJ = {cond}' in row and other not in row  # Docling은 두 온도 조건을 한 칸으로 합쳐 앞 4줄에만 걸었다


def _page_rows(file, page):
    """_page2_rows와 같되 쪽을 고른다. 표 행과 표 주석을 함께 돌려준다."""
    pytest.importorskip('docling_core')
    pytest.importorskip('pdfplumber')
    json_path, pdf_path = os.path.join(CORPUS, 'parsed', 'docling', file + '.json'), os.path.join(CORPUS, 'pdf', file)
    if not (os.path.exists(json_path) and os.path.exists(pdf_path)):
        pytest.skip('코퍼스 PDF · Docling 캐시가 없다')
    from docling_core.types.doc import DoclingDocument
    from backend.rag.pipeline.chunk import doc_cards
    cards, *_ = doc_cards(DoclingDocument.load_from_json(json_path), file, [], pdf_path, {})
    return [c for c in cards if c['page'] == page and c['kind'] in ('table_row', 'note')]


def test_subscripts_join_without_mixing_two_lines_of_a_cell():
    # [왜] 줄 허용 폭 6에서 HER601G trr 조건이 'I I F rr = = 0 0 . . 5 2 A'로 섞였다(11-08). 작은 글자만 가까운 줄에 붙인다
    trr = [c['text'] for c in _page_rows('HER601G SERIES_H2104.pdf', 2) if 'SYMBOL: trr' in c['text']]
    assert len(trr) == 2 and all('IF = 0.5A' in r and 'Irr = 0.25A' in r for r in trr)


def test_condition_lines_without_ruling_go_to_their_own_rows():
    # [왜] B0520LWF 1쪽 VF 조건 6줄이 가로선 없는 한 칸이라 모든 행에 붙었다(11-08). 줄마다 자기 행에 둔다
    vf = [c['text'] for c in _page_rows('B0520LWF SERIES_C14.pdf', 1) if 'SYMBOL: VF' in c['text']]
    assert len(vf) == 6
    first = next(r for r in vf if 'B0520LWF: 0.300' in r)
    assert 'IF= 0.1 A' in first and 'IF= 0.5 A' not in first and '100°C' not in first
    assert any('100°C' in r and 'B0520LWF: 0.220' in r for r in vf)  # 위첨자 o를 도(°)로 읽는다


def test_two_cell_header_row_is_not_taken_as_a_title():
    # [왜] 'Part No. | Marking' 머리를 제목으로 지워 첫 값 행(BAV19WS-G · A8)이 머리가 됐다(11-08)
    rows = [c['text'] for c in _page_rows('BAV19WS-G SERIES_A15.pdf', 3) if 'Marking: ' in c['text']]
    assert any('Part No.: BAV19WS-G | Marking: A8' in r for r in rows) and len(rows) == 3


def test_table_preamble_and_full_width_notes_reach_the_rows():
    # [왜] 표 위 공통 조건 문장과 'Notes：'(전각 쌍점) 주석이 표 행에 붙지 않았다(BZT52B 2쪽 11-08)
    rows = _page_rows('BZT52B2V4 SERIES_F15.pdf', 2)
    row = next(c['text'] for c in rows if c['kind'] == 'table_row' and 'BZT52B2V4 |' in c['text'])
    assert 'TA=25°C' in row and 'IF = 10 mA for all part numbers' in row  # 이름표(표 제목)에 공통 조건
    assert 'tested under pulse condition of 10ms' in row  # 행이 가리키는 주석 1
    assert any(c['kind'] == 'note' for c in rows)


def test_attached_notes_are_whole_not_cut_mid_sentence():
    # [왜] 주석 상한에서 글자 단위로 잘라 '… derived from the 60'처럼 끊겼다(BZT52B 11-08). 주석은 통째로만 붙인다
    rows = [c['text'] for c in _page_rows('BZT52B2V4 SERIES_F15.pdf', 2) if c['kind'] == 'table_row']
    assert rows and not any(r.rstrip().endswith('derived from the 60') for r in rows)


def test_numbered_note_moves_to_the_table_that_marks_it():
    # [왜] B0520LWF 1쪽 주석 2(RθJA 행의 '(Note 2)')가 PDF에서 아래 표 밑에 있어 VF · IR 행 모두에 붙었다(11-08)
    rows = _page_rows('B0520LWF SERIES_C14.pdf', 1)
    vf = [c['text'] for c in rows if c['kind'] == 'table_row' and 'SYMBOL: VF' in c['text']]
    assert vf and not any('electrodes are kept at ambient' in r for r in vf)
    rja = next(c['text'] for c in rows if c['kind'] == 'table_row' and 'RθJA' in c['text'])
    assert 'electrodes are kept at ambient' in rja


def test_text_only_value_row_is_not_taken_as_header():
    # [왜] 'Marking code on the device'(숫자 없는 값 행)를 머리로 읽어 품번 열 이름이 'S2A H / S2A'가 됐고,
    #      사양 값 읽기가 VRRM을 놓쳤다(S2AH 등 344문서, 11-08 사양 표 대조). 첫 칸이 위 행과 다르면 값 행이다
    rows = [c['text'] for c in _page_rows('S2AH SERIES_A2102.pdf', 1) if c['kind'] == 'table_row' and 'SYMBOL: VRRM' in c['text']]
    assert rows and 'S2A H: 50' in rows[0] and 'S2A H / S2A' not in rows[0]
    marks = [c['text'] for c in _page_rows('S2AH SERIES_A2102.pdf', 1) if 'Marking code on the device' in c['text']]
    assert marks and ': S2A ' in marks[0] + ' '  # 표시 코드 행이 값 행으로 남는다


def test_subscript_on_cell_border_goes_to_one_cell():
    # [왜] 기호 행 아래로 삐져나온 아래첨자(I_R의 R)가 아래 단위 칸에도 들어가 'µAR'·'Z V Z'가 됐고,
    #      사양 값 읽기가 단위를 몰라 제너 IR 246개를 놓쳤다(M3Z2V0C 2쪽, 11-08). 글자는 가운데가 든 칸에만 넣는다
    row = next(c['text'] for c in _page_rows('M3Z2V0C SERIES_B2008.pdf', 2) if 'PART NUMBER: M3Z36VC ' in c['text'])
    assert 'LEAKAGE CURRENT / IR @ VR / µA / Max: 0.1' in row and 'LEAKAGE CURRENT / IR @ VR / V: 27' in row  # 4행 머리(Max)까지
    assert 'µAR' not in row and 'Z V Z' not in row and 'VOLTAG(1)E' not in row


def test_suffix_row_under_merged_head_is_header():
    # [왜] 품번 끝자리 줄('005 | 01 | 02 …')이 숫자처럼 보여 값 행이 됐고, 열 이름이 모두 'GBPC15, 25, 35'라
    #      GBPC2502의 VRRM 200 V를 못 찾았다(11-08). PARAMETER 칸이 위 행과 세로로 한 칸이면 숫자가 있어도 머리다
    rows = [c['text'] for c in _page_rows('GBPC15_25_35 SERIES_M2211.pdf', 1) if 'SYMBOL: VRRM' in c['text']]
    assert rows and 'GBPC15, 25, 35 / 02: 200' in rows[0]
    assert not any('PARAMETER: PARAMETER' in c['text'] for c in _page_rows('GBPC15_25_35 SERIES_M2211.pdf', 1))


def test_name_part_condition_in_one_cell_split_per_row():
    # [왜] 세로선 없이 '항목 이름 | 품번 | 조건'을 한 칸에 적어 줄이 섞였다('BAV19W-G Reverse voltage BAV20W-G IR=100μA BAV21W-G', 11-08).
    #      줄마다 다른 덩어리(품번 · 조건)만 그 행에 두고 항목 이름은 모든 행에 둔다
    rows = [c['text'] for c in _page_rows('BAV19W-G SERIES_D1603.pdf', 1) if 'SYMBOL: VBR' in c['text'] or 'SYMBOL: VF' in c['text']]
    assert any('PARAMETER: Reverse voltage BAV20W-G IR=100μA | SYMBOL: VBR | MIN: 200' in r for r in rows)
    assert any('PARAMETER: Forward voltage IF = 200 mA | SYMBOL: VF | MIN: - | MAX: 1.25' in r for r in rows)
    # 품번 묶음을 세로로 적은 칸(모든 행의 품번)은 나누지 않는다
    vf = [c['text'] for c in _page_rows('RS1AFL SERIES_B2103.pdf', 2) if 'SYMBOL: VF' in c['text']]
    assert vf and all('RS1AFL RS1BFL RS1DFL RS1FFL' in r or 'RS1JFL RS1KFL RS1MFL' in r for r in vf)


def test_four_row_header_and_split_sub_header():
    # [왜] 4행 머리의 Min · Nom · Max 줄(1N4740A)과 'Part number'가 'Uni | Bi'로 나뉘는 두 층 머리(SMDJ)가 값 카드로 내려갔다(11-08)
    row = next(c['text'] for c in _page_rows('1N4740A SERIES_O2104.pdf', 2) if 'Device(1): 1N4747A ' in c['text'])
    assert 'VZ @ IZT / V / Nom(2)(3): 20' in row
    assert not any(c['text'].count('Device(1): Device(1)') for c in _page_rows('1N4740A SERIES_O2104.pdf', 2))
    row = next(c['text'] for c in _page_rows('SMDJ SERIES_I2104.pdf', 2) if 'SMDJ100A ' in c['text'])
    assert 'Breakdown voltage VBR@IT (V) / Max: 123' in row
    # 'PARAMETER'(두 칸) 아래 표시 코드 줄(품번 · 코드)은 값 줄로 남는다(1N4148W, 11-08 v4f 대조)
    rows = [c['text'] for c in _page_rows('1N4148W SERIES_K1804.pdf', 1) if 'SYMBOL: PD' in c['text']]
    assert rows and 'Marking code' not in rows[0]
    # 품번 묶음 칸('SS14ALH SS16ALH')이 조건(TJ)이 다른 두 행에 걸쳐도 품번마다 나누지 않는다(11-08 v4g 대조)
    ir = [c['text'].split('] ', 1)[1] for c in _page_rows('SS14ALH SERIES_B2103.pdf', 2) if 'SYMBOL: IR' in c['text']]
    assert ir and all('SS14ALH SS16ALH' in r for r in ir if 'SS14ALH' in r or 'SS16ALH' in r)
