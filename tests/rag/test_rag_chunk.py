"""표 청크 규칙과 문서 키, manifest 크기를 지킨다.

- 역할: 합친 칸 채우기, 머리 행 두 줄 잇기, 빈 표 건너뛰기, 문서 키, data/manifest.jsonl이 512,000바이트 아래인지 확인한다. Docling 없이 돈다.
- 하지 않는 일: 실제 PDF 파싱·전체 청크 수(AC-03)는 확인하지 않는다.
- 출처: docs/specs/rag-pipeline.md AC-01·AC-02, EC-03
"""
import os
import sys
import copy
from types import ModuleType, SimpleNamespace

import pytest

from backend.rag.pipeline.chunk import doc_cards, doc_key, graph_condition_cards, revision, table_cards

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


def test_mixed_table_recovers_missing_text_once_without_moving_existing_cards(monkeypatch):
    doc_types = ModuleType('docling_core.types.doc')
    class TableItem:
        pass
    class TextItem:
        def __init__(self, ref, text, page):
            self.self_ref, self.text = ref, text
            self.prov = [SimpleNamespace(page_no=page)] if page else []
    doc_types.TableItem, doc_types.TextItem = TableItem, TextItem
    monkeypatch.setitem(sys.modules, 'docling_core.types.doc', doc_types)
    note = TextItem('#/texts/0', 'Pulse test 10ms', 2)
    existing = TextItem('#/texts/1', 'Already retained', 2)
    table = TableItem()
    table.captions = []
    table.self_ref, table.prov = '#/tables/0', [SimpleNamespace(page_no=2)]
    table.data = SimpleNamespace(num_rows=2, num_cols=1, table_cells=[
        SimpleNamespace(start_row_offset_idx=0, end_row_offset_idx=1, start_col_offset_idx=0,
                        end_col_offset_idx=1, text='PARAMETER', column_header=True),
        SimpleNamespace(start_row_offset_idx=1, end_row_offset_idx=2, start_col_offset_idx=0,
                        end_col_offset_idx=1, text='Value', column_header=False)])
    def chunk(*items):
        return SimpleNamespace(meta=SimpleNamespace(doc_items=items, headings=[]))
    chunks = [chunk(table, note, existing), chunk(table, note), chunk(existing)]
    chunker = SimpleNamespace(chunk=lambda doc: iter(chunks), contextualize=lambda c: 'Already retained')
    doc = SimpleNamespace(tables=[table], pictures=[], iterate_items=lambda: iter((x, 0) for x in (note, existing, table)))
    cards, original, kept = doc_cards(doc, 'sample.pdf', [], chunker)
    assert [c['kind'] for c in cards] == ['cover', 'text', 'table_row', 'text']
    assert cards[-1]['text'] == 'Pulse test 10ms'
    assert cards[-1]['page'] == 2
    assert sum('Already retained' in c['text'] for c in cards) == 1
    assert original == kept
    chunks.append(chunk(table, SimpleNamespace(self_ref='#/texts/missing')))
    with pytest.raises(ValueError, match='원문 참조'):
        doc_cards(doc, 'sample.pdf', [], chunker)


@pytest.mark.parametrize('already_kept,missing_ref', [(False, False), (True, False), ('metadata_only', False), (False, True)])
def test_table_caption_without_mixed_chunk_is_preserved_once(monkeypatch, already_kept, missing_ref):
    doc_types = ModuleType('docling_core.types.doc')
    class TableItem:
        pass
    class TextItem:
        pass
    doc_types.TableItem, doc_types.TextItem = TableItem, TextItem
    monkeypatch.setitem(sys.modules, 'docling_core.types.doc', doc_types)
    note = TextItem()
    note.self_ref, note.text = '#/texts/0', 'Notes: 1. Valid provided that electrodes are kept at ambient temperature'
    note.prov = [SimpleNamespace(page_no=1)]
    table = TableItem()
    table.self_ref, table.prov = '#/tables/0', [SimpleNamespace(page_no=1)]
    ref = SimpleNamespace(cref='#/texts/missing' if missing_ref else note.self_ref)
    table.captions = [ref, ref]
    table.data = SimpleNamespace(num_rows=3, num_cols=3, table_cells=[
        SimpleNamespace(start_row_offset_idx=r0, end_row_offset_idx=r1, start_col_offset_idx=c0,
                        end_col_offset_idx=c1, text=text, column_header=head)
        for r0, r1, c0, c1, text, head in CELLS])
    chunks = [SimpleNamespace(meta=SimpleNamespace(doc_items=[table], headings=[]))]
    if already_kept:
        chunks.append(SimpleNamespace(meta=SimpleNamespace(doc_items=[note], headings=[])))
    chunker = SimpleNamespace(chunk=lambda doc: iter(chunks),
                              contextualize=lambda c: 'Mechanical data' if already_kept == 'metadata_only' else note.text)
    doc = SimpleNamespace(tables=[table], pictures=[], iterate_items=lambda: iter((x, 0) for x in (table, note)))
    if missing_ref:
        with pytest.raises(ValueError, match='원문 참조'):
            doc_cards(doc, 'sample.pdf', [], chunker)
        return
    cards, original, kept = doc_cards(doc, 'sample.pdf', [], chunker)
    assert sum(c['text'] == note.text for c in cards) == 1
    assert next(c for c in cards if c['text'] == note.text)['page'] == 1
    assert [c for c in cards if c['kind'] == 'table_row'] == table_cards('sample.pdf', 1, 3, 3, CELLS)
    assert original == kept
    if not already_kept:
        assert [c['kind'] for c in cards] == ['cover', 'table_row', 'table_row', 'text']


@pytest.fixture
def graph_document(monkeypatch):
    types = ModuleType('docling_core.types.doc')
    types.TableItem = type('TableItem', (), {})
    types.TextItem = type('TextItem', (), {})
    monkeypatch.setitem(sys.modules, 'docling_core.types.doc', types)
    nodes = {}
    def text(ref, value, box, parent='#/pictures/0'):
        node = types.TextItem()
        node.self_ref, node.text, node.parent = ref, value, SimpleNamespace(cref=parent)
        node.prov = [SimpleNamespace(page_no=3, bbox=SimpleNamespace(
            l=box[0], t=box[1], r=box[2], b=box[3], coord_origin='BOTTOMLEFT'))]
        nodes[ref] = node
        return node
    def ref(key):
        return SimpleNamespace(cref=key, resolve=lambda doc: nodes[key])
    title = text('#/texts/0', 'Fig.4 Typical Forward Characteristics', (10, 120, 190, 110))
    text('#/texts/1', 'Pulse width 300μs', (100, 40, 180, 30))
    text('#/texts/2', '1% duty cycle', (100, 25, 180, 15))
    text('#/texts/3', 'FORWARD VOLTAGE (V)', (10, 10, 190, 0))
    text('#/texts/4', '0.7 0.8 0.9 1.0', (10, 20, 190, 10))
    text('#/texts/5', 'Pulse width', (100, 60, 150, 50))
    picture = SimpleNamespace(self_ref='#/pictures/0', parent=SimpleNamespace(cref='#/body'),
        prov=[SimpleNamespace(page_no=3, bbox=SimpleNamespace(l=0, t=100, r=200, b=0, coord_origin='BOTTOMLEFT'))],
        captions=[ref(title.self_ref)], children=[ref(key) for key in nodes])
    prose = text('#/texts/6', 'Existing prose', (0, 200, 200, 180), '#/body')
    chunk = SimpleNamespace(meta=SimpleNamespace(doc_items=[prose], headings=[]))
    chunker = SimpleNamespace(chunk=lambda doc: iter([chunk]), contextualize=lambda c: prose.text)
    doc = SimpleNamespace(tables=[], pictures=[picture], texts=list(nodes.values()),
                          iterate_items=lambda: iter([(prose, 0), (title, 0)]))
    return doc, chunker, nodes, ref


def test_graph_conditions_keep_title_and_numeric_conditions_only(graph_document):
    doc, chunker, nodes, ref = graph_document
    cards, _, _ = doc_cards(doc, 'a.pdf', [], chunker)
    assert len(cards) == 3
    assert cards[-1] == {'kind': 'text', 'page': 3, 'table': None, 'row': None,
        'text': '[a.pdf · 3쪽 · Fig.4 Typical Forward Characteristics]\n[그래프 측정 조건]\nPulse width 300μs\n1% duty cycle'}
    assert cards[1]['text'] == 'Existing prose'
    doc.pictures.append(doc.pictures[0])
    repeated, _, _ = doc_cards(doc, 'a.pdf', [], chunker)
    assert repeated == cards


@pytest.mark.parametrize('invalid', ['page', 'parent', 'position', 'title_position', 'no_numbered_title', 'two_titles', 'two_values', 'no_values'])
def test_ambiguous_graphs_are_not_added(graph_document, invalid):
    doc, chunker, nodes, ref = graph_document
    if invalid == 'page':
        nodes['#/texts/1'].prov[0].page_no = 2
    elif invalid == 'parent':
        nodes['#/texts/1'].parent.cref = '#/pictures/other'
    elif invalid == 'position':
        nodes['#/texts/1'].prov[0].bbox.r = 999
    elif invalid == 'title_position':
        nodes['#/texts/0'].prov[0].bbox.b = -100
    elif invalid == 'no_numbered_title':
        doc.pictures[0].captions = []
        nodes['#/texts/0'].text = 'Graph without numbered title'
    elif invalid == 'two_titles':
        doc.pictures[0].captions *= 2
    elif invalid == 'two_values':
        nodes['#/texts/5'].text = 'Pulse width 1ms'
    elif invalid == 'no_values':
        nodes['#/texts/1'].text = 'Pulse width (μs)'
        nodes['#/texts/2'].text = 'DUTY CYCLE (%)'
    cards, _, _ = doc_cards(doc, 'a.pdf', [], chunker)
    assert len(cards) == 2
    _, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert diagnostics[0]['status'] != 'accepted'


@pytest.mark.parametrize('pulse,duty', [('PW = 0.3ms', 'Duty cycle=1%'), ('tp ≤ 300us', '1% Duty Cycle')])
def test_graph_condition_spelling_variants_keep_original_text(graph_document, pulse, duty):
    doc, chunker, nodes, ref = graph_document
    nodes['#/texts/1'].text, nodes['#/texts/2'].text = pulse, duty
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 1 and diagnostics[0]['status'] == 'accepted'
    assert cards[0]['text'].endswith(pulse + '\n' + duty)


def test_graph_missing_source_reference_fails(graph_document):
    doc, chunker, nodes, ref = graph_document
    del nodes['#/texts/1']
    with pytest.raises(ValueError, match='그래프 원문 참조'):
        graph_condition_cards(doc, 'a.pdf')


@pytest.mark.parametrize('broken', ['missing_link', 'other_column', 'wrong_parent'])
def test_graph_title_relinks_only_to_unique_same_page_position(graph_document, broken):
    doc, chunker, nodes, ref = graph_document
    picture = doc.pictures[0]
    if broken == 'missing_link':
        picture.captions = []
    elif broken == 'wrong_parent':
        nodes['#/texts/0'].parent.cref = '#/pictures/other'
    else:
        wrong = copy.deepcopy(nodes['#/texts/0'])
        wrong.self_ref, wrong.text = '#/texts/other', 'Fig.5 Other Characteristics'
        wrong.prov[0].bbox.l, wrong.prov[0].bbox.r = 310, 490
        nodes[wrong.self_ref] = wrong
        doc.texts.append(wrong)
        picture.captions = [ref(wrong.self_ref)]
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 1 and 'Fig.4 Typical Forward Characteristics' in cards[0]['text']
    assert diagnostics[0]['title_method'] == 'spatial_fallback'
    assert diagnostics[0]['title_ref'] == '#/texts/0'


@pytest.mark.parametrize('bad', ['two_candidates', 'other_page'])
def test_spatial_title_ambiguity_is_not_guessed(graph_document, bad):
    doc, chunker, nodes, ref = graph_document
    doc.pictures[0].captions = []
    if bad == 'other_page':
        nodes['#/texts/0'].prov[0].page_no = 2
    else:
        other = copy.deepcopy(nodes['#/texts/0'])
        other.self_ref, other.text = '#/texts/other', 'Fig.6 Other Characteristics'
        doc.texts.append(other)
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert cards == [] and diagnostics[0]['status'] != 'accepted'


@pytest.mark.parametrize('keep_primary', [False, True])
def test_spatial_title_shared_with_other_picture_is_rejected(graph_document, keep_primary):
    doc, chunker, nodes, ref = graph_document
    first = doc.pictures[0]
    if not keep_primary:
        first.captions = []
    second = copy.deepcopy(first)
    second.self_ref, second.captions = '#/pictures/1', []
    children = []
    for old_ref in ['#/texts/1', '#/texts/2']:
        node = copy.deepcopy(nodes[old_ref])
        node.self_ref += '-second'
        node.parent.cref = second.self_ref
        nodes[node.self_ref] = node
        doc.texts.append(node)
        children.append(ref(node.self_ref))
    second.children = children
    doc.pictures.append(second)
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == int(keep_primary)
    assert diagnostics[-1]['status'] == 'spatial_title_shared'


def test_same_condition_alias_refs_are_kept_without_duplicate_text(graph_document):
    doc, chunker, nodes, ref = graph_document
    nodes['#/texts/5'].text = 'Pulse width 300µs'
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 1
    assert cards[0]['text'].splitlines()[-2:] == ['Pulse width 300μs', '1% duty cycle']
    assert diagnostics[0]['conditions'][0]['source_refs'] == ['#/texts/1', '#/texts/5']


def test_fallback_cards_follow_existing_metadata_graph_order(graph_document):
    doc, chunker, nodes, ref = graph_document
    first = doc.pictures[0]
    first.captions = []
    second = copy.deepcopy(first)
    second.self_ref = '#/pictures/1'
    second.prov[0].bbox.l += 300
    second.prov[0].bbox.r += 300
    children = []
    for key in ['#/texts/0', '#/texts/1', '#/texts/2']:
        node = copy.deepcopy(nodes[key])
        node.self_ref += '-second'
        node.parent.cref = second.self_ref
        node.prov[0].bbox.l += 300
        node.prov[0].bbox.r += 300
        if key == '#/texts/0':
            node.text = 'Fig.6 Typical Forward Characteristics'
            second.captions = [ref(node.self_ref)]
        nodes[node.self_ref] = node
        doc.texts.append(node)
        children.append(ref(node.self_ref))
    second.children = children
    doc.pictures.append(second)
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 2
    assert 'Fig.6' in cards[0]['text'] and 'Fig.4' in cards[1]['text']


def test_single_sfig_prefix_is_recognized_without_rewriting_title(graph_document):
    doc, chunker, nodes, ref = graph_document
    nodes['#/texts/0'].text = 'sFig.4 Typical Forward Characteristics'
    doc.pictures[0].captions = []
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 1 and 'sFig.4 Typical Forward Characteristics' in cards[0]['text']
    assert diagnostics[0]['title_recognition'] == 'leading_s'
    assert diagnostics[0]['condition_role'] == 'common_measurement'


@pytest.mark.parametrize('title', ['xFig.4 Typical Forward Characteristics', 'ssFig.4 Typical Forward Characteristics'])
def test_arbitrary_title_prefixes_are_not_accepted(graph_document, title):
    doc, chunker, nodes, ref = graph_document
    nodes['#/texts/0'].text = title
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert cards == []


@pytest.mark.parametrize('title,values', [
    ('Fig.10 Maximum Surge Power', ['20% DUTY CYCLE', '10% DUTY CYCLE', '5% DUTY CYCLE']),
    ('Fig.9 Clamping Voltage Curve', ['tp=20μs', 'tp=1ms', 'tp=10ms'])])
def test_reviewed_multiple_values_are_curve_legends_not_common_conditions(graph_document, title, values):
    doc, chunker, nodes, ref = graph_document
    nodes['#/texts/0'].text = title
    for key, value in zip(['#/texts/1', '#/texts/2', '#/texts/5'], values):
        nodes[key].text = value
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 1 and diagnostics[0]['condition_role'] == 'curve_legend'
    assert '[곡선별 범례' in cards[0]['text'] and '공통 측정 조건이 아님' in cards[0]['text']
    assert '[그래프 측정 조건]' not in cards[0]['text']
    assert cards[0]['text'].splitlines()[-3:] == values
    assert len(diagnostics[0]['conditions']) == 3


def test_mixed_multi_value_types_remain_ambiguous(graph_document):
    doc, chunker, nodes, ref = graph_document
    nodes['#/texts/0'].text = 'Fig.10 Maximum Surge Power'
    nodes['#/texts/1'].text = '20% DUTY CYCLE'
    nodes['#/texts/2'].text = '10% DUTY CYCLE'
    nodes['#/texts/5'].text = 'Pulse width 1ms'
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert cards == [] and diagnostics[0]['status'] == 'ambiguous_condition_values'


def test_new_legend_follows_existing_spatial_fallback_cards(graph_document):
    doc, chunker, nodes, ref = graph_document
    first = doc.pictures[0]
    nodes['#/texts/0'].text = 'Fig.10 Maximum Surge Power'
    for key, value in zip(['#/texts/1', '#/texts/2', '#/texts/5'], ['20% DUTY CYCLE', '10% DUTY CYCLE', '5% DUTY CYCLE']):
        nodes[key].text = value
    second = copy.deepcopy(first)
    second.self_ref, second.captions = '#/pictures/1', []
    second.prov[0].bbox.l += 300
    second.prov[0].bbox.r += 300
    children = []
    for key, value in zip(['#/texts/0', '#/texts/1', '#/texts/2'], ['Fig.6 Typical Forward Characteristics', 'Pulse width 300μs', '1% duty cycle']):
        node = copy.deepcopy(nodes[key])
        node.self_ref += '-second'
        node.text, node.parent.cref = value, second.self_ref
        node.prov[0].bbox.l += 300
        node.prov[0].bbox.r += 300
        nodes[node.self_ref] = node
        doc.texts.append(node)
        children.append(ref(node.self_ref))
    second.children = children
    doc.pictures.append(second)
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 2
    assert 'Fig.6' in cards[0]['text'] and 'Fig.10' in cards[1]['text']


@pytest.mark.parametrize('fallback', [False, True])
def test_regular_title_keeps_priority_over_extended_title(graph_document, fallback):
    doc, chunker, nodes, ref = graph_document
    extra = copy.deepcopy(nodes['#/texts/0'])
    extra.self_ref, extra.text = '#/texts/extended', 'sFig.6 Other Characteristics'
    nodes[extra.self_ref] = extra
    doc.texts.append(extra)
    doc.pictures[0].captions = [] if fallback else [ref('#/texts/0'), ref(extra.self_ref)]
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 1 and 'Fig.4 Typical Forward Characteristics' in cards[0]['text']
    assert diagnostics[0]['title_recognition'] == 'numbered'


@pytest.mark.parametrize('title,values', [
    ('Fig.9 Clamping Voltage Curve', ['20% DUTY CYCLE', '10% DUTY CYCLE', '5% DUTY CYCLE']),
    ('Fig.10 Maximum Surge Power', ['tp=20μs', 'tp=1ms', 'tp=10ms'])])
def test_curve_legend_title_and_value_type_must_match(graph_document, title, values):
    doc, chunker, nodes, ref = graph_document
    nodes['#/texts/0'].text = title
    for key, value in zip(['#/texts/1', '#/texts/2', '#/texts/5'], values):
        nodes[key].text = value
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert cards == [] and diagnostics[0]['status'] == 'ambiguous_condition_values'


def _graph_context(doc, nodes, ref, title, lines):
    nodes['#/texts/0'].text = title
    for key in ['#/texts/1', '#/texts/2', '#/texts/5']:
        nodes[key].text = 'AXIS LABEL'
    for i, value in enumerate(lines):
        node = copy.deepcopy(nodes['#/texts/1'])
        node.self_ref, node.text = f'#/texts/context-{i}', value
        node.prov[0].bbox.t, node.prov[0].bbox.b = 95 - i * 10, 87 - i * 10
        nodes[node.self_ref] = node
        doc.texts.append(node)
        doc.pictures[0].children.append(ref(node.self_ref))


@pytest.mark.parametrize('title,lines,common,legends', [
    ('Fig.1 Steady State Power Derating', ['Heat sink', '5mm x 5mm', 'Cu pad test board'], 1, 0),
    ('Fig.1 Power Temperature Derating Curve', ['Mounted on PCB with', 'Cu-pad size 5mm x 5mm'], 1, 0),
    ('Fig.2 Pulse Derating Curve', ['With heat sink', 'Without heat sink'], 0, 2),
    ('Fig.1 Forward Current Derating Curve', ['Heat-sink', 'Mounting', '2"x3"x0.25"', 'Al-Plate', 'P.C.B.', 'Mounting', '0.5"x0.5"', 'copper pads'], 0, 2),
    ('Fig.5 Typical Junction Capacitance', ['f=1.0MHz', 'Vsig=50mVp-p', 'VR=0', 'MEASURED at', 'STAND-OFF', 'VOLTAGE,Vwm'], 2, 2),
    ('Fig.4 Total Capacitance', ['Measured at zero bias', 'Measured at Stand-Off', 'Voltage V WM', 'f = 1MHz', 'V sig = 50mV P-P'], 2, 2),
    ('Fig.6 Typical Reverse Characteristics', ['MEASURED AT DEVICES', 'STAND-OFF VOLTAGE, V WM'], 1, 0),
])
def test_thermal_bias_context_preserves_roles_and_raw_lines(graph_document, title, lines, common, legends):
    doc, chunker, nodes, ref = graph_document
    _graph_context(doc, nodes, ref, title, lines)
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 1
    context = next(d for d in diagnostics if d.get('source_kind') == 'thermal_bias_context')
    assert context['status'] == 'accepted'
    assert sum(c['role'] == 'common_measurement' for c in context['conditions']) == common
    assert sum(c['role'] == 'curve_legend' for c in context['conditions']) == legends
    assert set(r for c in context['conditions'] for r in c['source_refs']) == {f'#/texts/context-{i}' for i in range(len(lines))}
    assert all(value in cards[0]['text'] for value in lines)
    assert ('[그래프 공통 측정 조건]' in cards[0]['text']) == bool(common)
    assert ('[곡선별 범례' in cards[0]['text']) == bool(legends)
    assert 'AXIS LABEL' not in cards[0]['text']


@pytest.mark.parametrize('broken', ['page', 'parent', 'position', 'gap', 'branch', 'title', 'incomplete', 'conflict'])
def test_thermal_bias_context_does_not_guess(graph_document, broken):
    doc, chunker, nodes, ref = graph_document
    _graph_context(doc, nodes, ref, 'Fig.1 Power Temperature Derating Curve', ['Mounted on PCB with', 'Cu-pad size 5mm x 5mm'])
    second = nodes['#/texts/context-1']
    if broken == 'page': second.prov[0].page_no = 2
    elif broken == 'parent': second.parent.cref = '#/pictures/other'
    elif broken == 'position': second.prov[0].bbox.r = 999
    elif broken == 'gap': second.prov[0].bbox.t, second.prov[0].bbox.b = 25, 17
    elif broken == 'branch':
        other = copy.deepcopy(second); other.self_ref = '#/texts/branch'; other.text = 'Cu-pad size 10mm x 10mm'
        nodes[other.self_ref] = other; doc.pictures[0].children.append(ref(other.self_ref))
    elif broken == 'title': nodes['#/texts/0'].text = 'Fig.1 Unknown Graph'
    elif broken == 'incomplete': second.text = 'Cu-pad size'
    elif broken == 'conflict':
        nodes['#/texts/0'].text = 'Fig.1 Typical Junction Capacitance'
        nodes['#/texts/context-0'].text, second.text = 'f=1MHz', 'f=2MHz'
    cards, _ = graph_condition_cards(doc, 'a.pdf')
    assert cards == []


def test_thermal_bias_additions_follow_existing_numeric_cards(graph_document):
    doc, chunker, nodes, ref = graph_document
    before, _ = graph_condition_cards(doc, 'a.pdf')
    node = copy.deepcopy(nodes['#/texts/1']);node.self_ref, node.text = '#/texts/new', 'f=1MHz'
    nodes[node.self_ref] = node;doc.pictures[0].children.append(ref(node.self_ref))
    # Unsupported title must not add frequency text to a forward graph.
    assert graph_condition_cards(doc, 'a.pdf')[0] == before
    nodes['#/texts/0'].text = 'Fig.4 Typical Junction Capacitance'
    cards, _ = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 2 and 'Pulse width 300μs' in cards[0]['text'] and 'f=1MHz' in cards[1]['text']
    doc.pictures.append(doc.pictures[0])
    first, _, _ = doc_cards(doc, 'a.pdf', [], chunker)
    assert sum('f=1MHz' in c['text'] for c in first) == 1


def test_context_lines_allow_small_pdf_glyph_overlap(graph_document):
    doc, chunker, nodes, ref = graph_document
    _graph_context(doc, nodes, ref, 'Fig.1 Power Temperature Derating Curve', ['Mounted on PCB with', 'Cu-pad size 5mm x 5mm'])
    second = nodes['#/texts/context-1'].prov[0].bbox
    second.t, second.b = 87.15, 79.15
    cards, _ = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 1 and 'Cu-pad size 5mm x 5mm' in cards[0]['text']


def test_incomplete_bias_alternative_is_not_mislabeled_common(graph_document):
    doc, chunker, nodes, ref = graph_document
    _graph_context(doc, nodes, ref, 'Fig.1 Typical Junction Capacitance', ['Measured at zero bias', 'Measured at'])
    assert graph_condition_cards(doc, 'a.pdf')[0] == []


def test_invalid_second_bias_cannot_turn_first_into_common(graph_document):
    doc, chunker, nodes, ref = graph_document
    _graph_context(doc, nodes, ref, 'Fig.1 Typical Junction Capacitance', ['Measured at zero bias', 'Measured at stand-off voltage, V WM'])
    nodes['#/texts/context-1'].prov[0].bbox.r = 999
    assert graph_condition_cards(doc, 'a.pdf')[0] == []


@pytest.mark.parametrize('title,lines,role', [
    ('Fig.3 Clamping Power Pulse Waveform', ['Pulse width(td) is defined', 'as the point where the peak', 'current decays to 50% of I PPM'], 'waveform_definition'),
    ('Fig.6 10/1000μs pulse waveform', ['Pulse Width (td)', 'is defined as the Point', 'where the Peak Current', 'decays to 50% of I PPM'], 'waveform_definition'),
    ('Fig.2 Pulse Waveform', ['PULSE WIDTH (tp) IS DEFINED', 'AS THAT POINT WHERE THE', 'PEAK CURRENT DECAY = 8us'], 'waveform_definition'),
    ('Fig.9 Typical Thermal Response', ['NOTE BELOW 0.1 SECOND,', 'THERMAL RESPONSE', 'CURVE IS APPLICABLE TO', 'ANY LEAD LENGTH(L)'], 'graph_applicability_note'),
    ('Fig.9 Effect Of Zener Current', ['NOTE:BELOW 3 VOLTAGE ABOVE a', 'VOLTS CHANGES IN ZENER CURRENT', 'NOT AFFECT TEMPERATURE', 'COEFFICIENTS'], 'graph_interpretation_note'),
    ('Fig.9 Effect Of Zener Current', ['NOTE:BELOW 3 VOLTAGE ABOVE a', 'VOLTS CHANGES IN ZENER CURRENT', 'NOT AFFECT TEMPERATURE COEFFICIENTS'], 'graph_interpretation_note'),
])
def test_graph_notes_keep_complete_unedited_source(graph_document, title, lines, role):
    doc, chunker, nodes, ref = graph_document
    _graph_context(doc, nodes, ref, title, lines)
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 1
    e = next(e for e in diagnostics if e.get('source_kind') == 'graph_note')
    assert e['condition_role'] == role and e['status'] == 'accepted'
    assert e['conditions'][0]['text'] == '\n'.join(lines)
    assert e['conditions'][0]['source_refs'] == [f'#/texts/context-{i}' for i in range(len(lines))]
    assert '\n'.join(lines) in cards[0]['text'] and 'AXIS LABEL' not in cards[0]['text']


@pytest.mark.parametrize('broken', ['incomplete', 'branch', 'page', 'parent', 'position', 'gap', 'wrong_title'])
def test_incomplete_or_ambiguous_graph_notes_are_not_added(graph_document, broken):
    doc, chunker, nodes, ref = graph_document
    _graph_context(doc, nodes, ref, 'Fig.3 Pulse Waveform', ['Pulse width(td) is defined', 'as the point where the peak', 'current decays to 50% of I PPM'])
    last = nodes['#/texts/context-2']
    if broken == 'incomplete': last.text = 'current decays to'
    elif broken == 'branch':
        extra = copy.deepcopy(last);extra.self_ref = '#/texts/branch';nodes[extra.self_ref] = extra;doc.pictures[0].children.append(ref(extra.self_ref))
        extra.text = 'current decays to 50% of IPPM'
    elif broken == 'page': last.prov[0].page_no = 2
    elif broken == 'parent': last.parent.cref = '#/pictures/other'
    elif broken == 'position': last.prov[0].bbox.r = 999
    elif broken == 'gap': last.prov[0].bbox.t, last.prov[0].bbox.b = 25, 17
    elif broken == 'wrong_title': nodes['#/texts/0'].text = 'Fig.3 Forward Characteristics'
    assert graph_condition_cards(doc, 'a.pdf')[0] == []


def test_note_title_can_overlap_picture_top_without_changing_numeric_linking(graph_document):
    doc, chunker, nodes, ref = graph_document
    _graph_context(doc, nodes, ref, 'Fig.2 Pulse Waveform', ['PULSE WIDTH (tp) IS DEFINED', 'AS THAT POINT WHERE THE', 'PEAK CURRENT DECAY = 8us'])
    title = nodes['#/texts/0'];title.prov[0].bbox.t, title.prov[0].bbox.b = 103, 93
    for i in range(3):
        b = nodes[f'#/texts/context-{i}'].prov[0].bbox
        b.t, b.b = b.t - 10, b.b - 10
    cards, diagnostics = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 1 and 'PEAK CURRENT DECAY = 8us' in cards[0]['text']
    assert diagnostics[0]['status'] == 'no_spatial_title'


def test_merged_picture_note_uses_its_own_title(graph_document):
    doc, chunker, nodes, ref = graph_document
    _graph_context(doc, nodes, ref, 'Fig.9 Effect Of Zener Current', ['NOTE:BELOW 3 VOLTAGE ABOVE a', 'VOLTS CHANGES IN ZENER CURRENT', 'NOT AFFECT TEMPERATURE COEFFICIENTS'])
    doc.pictures[0].prov[0].bbox.r = 500
    other = copy.deepcopy(nodes['#/texts/0']);other.self_ref, other.text = '#/texts/other', 'Fig.10 Thermal Resistance versus Lead Length'
    other.prov[0].bbox.l, other.prov[0].bbox.r = 310, 490
    nodes[other.self_ref] = other;doc.texts.append(other);doc.pictures[0].captions = [ref(other.self_ref)]
    cards, _ = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 1 and 'Fig.9 Effect Of Zener Current' in cards[0]['text'] and 'Fig.10' not in cards[0]['text']


def test_new_graph_notes_follow_existing_context_cards(graph_document):
    doc, chunker, nodes, ref = graph_document
    before, _ = graph_condition_cards(doc, 'a.pdf')
    for i,value in enumerate(['Pulse width(td) is defined', 'as the point where the peak', 'current decays to 50% of I PPM']):
        n = copy.deepcopy(nodes['#/texts/1']);n.self_ref, n.text = f'#/texts/note-{i}', value
        n.prov[0].bbox.t, n.prov[0].bbox.b = 95-i*10,87-i*10;nodes[n.self_ref] = n;doc.pictures[0].children.append(ref(n.self_ref))
    nodes['#/texts/0'].text = 'Fig.4 Pulse Waveform'
    cards, _ = graph_condition_cards(doc, 'a.pdf')
    assert len(cards) == 2 and 'Pulse width 300μs' in cards[0]['text'] and 'current decays to 50%' in cards[1]['text']


def test_waveform_auxiliary_keeps_source_times_without_orphan_labels(graph_document):
    doc, chunker, nodes, ref = graph_document
    _graph_context(doc, nodes, ref, 'Fig.2 Pulse Waveform', ['PULSE WIDTH (tp) IS DEFINED', 'AS THAT POINT WHERE THE', 'PEAK CURRENT DECAY = 8us'])
    for i,value in enumerate(['I RSM @8us', 'HALF VALUE I RSM /2@20us', 'Peak value']):
        n = copy.deepcopy(nodes['#/texts/1']);n.self_ref,n.text = f'#/texts/annotation-{i}',value
        n.prov[0].bbox.t,n.prov[0].bbox.b = 55-i*10,47-i*10;nodes[n.self_ref]=n;doc.pictures[0].children.append(ref(n.self_ref))
    cards,_ = graph_condition_cards(doc,'a.pdf')
    assert 'PEAK CURRENT DECAY = 8us' in cards[0]['text'] and 'HALF VALUE I RSM /2@20us' in cards[0]['text']
    assert 'I RSM @8us' in cards[0]['text'] and 'Peak value' not in cards[0]['text']


def test_graph_note_skips_non_text_group_child(graph_document):
    doc,chunker,nodes,ref = graph_document
    _graph_context(doc,nodes,ref,'Fig.3 Pulse Waveform',['Pulse width(td) is defined','as the point where the peak','current decays to 50% of I PPM'])
    group = SimpleNamespace(self_ref='#/groups/nested',label='list',children=[])
    nodes[group.self_ref]=group;doc.pictures[0].children.append(ref(group.self_ref))
    cards,_=graph_condition_cards(doc,'a.pdf')
    assert len(cards)==1 and 'current decays to 50%' in cards[0]['text']
