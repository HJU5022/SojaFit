"""표 행 청크 공용 규칙(backend.rag.pipeline.specs) 계약: 코퍼스 파일 없이 작은 가짜 청크로 확인한다.

- 역할: 패키지 이름 정규식(`PKG`)이 소문자 낱말 · Thin/Micro/Sub SMA를 SMA로 잡지 않는지, `packages_of`가 본문 'Case:' 글과
  KEY PARAMETERS의 Package 행에서 패키지 이름을 읽는지 본다(카드 찾기 · 판정 값 읽기가 쓴다).
- 하지 않는 일: 사양 표 변환 · 적재(11-09에 지웠다, ADR 0016). 카드 도구 동작은 `test_card_find.py` · `test_card_specs.py`가 본다.
- 출처: 11-05 · 11-06 PDF 대조에서 고친 패키지 규칙, ADR 0016
"""
from backend.rag.pipeline import specs


def row(doc, idx, table, label, cells, cat='standard-rectifier-12', page=1):
    """chunk.py가 만드는 표 행 청크 모양: '[파일 · 쪽 · 표] 머리 경로: 값 | ...'."""
    body = ' | '.join(f'{h}: {v}' for h, v in cells)
    return {'doc': doc, 'category': cat, 'idx': idx, 'kind': 'table_row', 'page': page, 'table': table, 'row': label,
            'text': f'[{doc} · {page}쪽 · {table}] {body}'}


def test_lowercase_words_are_not_package_names():
    """'Case: SOD-123 small outline package'의 small은 SMA 패키지가 아니다(11-05 SMALL 59건). 패키지 이름은 대문자로 적힌다."""
    assert specs.PKG.findall('Bend lead SOD-123 small outline plastic package') == ['SOD-123']
    assert specs.PKG.findall('SMA (DO-214AC), SMAF, SMB') == ['SMA', 'DO-214AC', 'SMAF', 'SMB']
    assert specs.PKG.findall('MiniMELF, absolute maximum') == ['MiniMELF']


def test_thin_micro_sub_sma_are_their_own_packages():
    """[왜] 'Thin SMA' · 'Micro SMA' · 'Sub SMA'가 SMA로 잡혀 SMA를 원한 찾기에 SS14ALH(Thin SMA) · SS14LH(Sub SMA)가 나왔다(11-06 v3-14)."""
    assert specs.PKG.findall('Case: Thin SMA') == ['Thin SMA'] and specs.PKG.findall('Micro SMA, Sub SMA') == ['Micro SMA', 'Sub SMA']


def test_packages_of_reads_case_text_and_package_row():
    doc = 'S1A SERIES_A01.pdf'
    text = {'doc': doc, 'category': 'standard-rectifier-12', 'idx': 5, 'kind': 'text', 'page': 1, 'table': None,
            'row': None, 'text': f'[{doc} · 1쪽] Case: SMA (DO-214AC), molded plastic'}
    package_row = row(doc, 6, 'KEY PARAMETERS', 'Package',
                      [('KEY PARAMETERS / PARAMETER', 'Package'), ('KEY PARAMETERS / VALUE', 'SMA'),
                       ('KEY PARAMETERS / UNIT', 'SMA')])
    assert specs.packages_of(text) == ['SMA', 'DO-214AC']
    assert specs.packages_of(package_row) == ['SMA']  # [왜] UNIT 칸은 패키지 칸이 아니다. Package 행의 VALUE 칸만 읽는다
