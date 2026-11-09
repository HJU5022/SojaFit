"""데이터시트 표 행 청크를 읽는 공용 규칙: 코드 · 단위 · 기호 · 낱말 표, 패키지 이름 찾기, 분류 이름, 양방향 · AEC-Q101 문장.

- 역할: 카드 도구(`backend/rag/card_find.py` · `card_specs.py`)와 적재(`ingest.py`)가 import하는 규칙만 둔다.
  `SI`(코드 17종의 SI 단위), `SYMS`(데이터시트 기호 → 코드), `KEYWORDS`(설명 낱말 → 코드), `PKG` · `packages_of`(패키지 이름),
  `family`(TSC 분류 이름에서 번호를 뗀 것, `source_documents.category` 값), `BOTH_DIRECTIONS` · `AEC_H` · `AEC_ALL`(문서가 밝힌 문장).
- 하지 않는 일: 사양 표 만들기 · 적재(11-09에 지움, ADR 0016), LLM · 임베딩 호출, 값 비교 · 판정(`backend/judge/`), 단위 환산(`backend/rag/units.py`).
- 출처: ADR 0016(사양 표를 버리고 카드 읽기를 기본으로), ADR 0013(규칙의 원래 결정, 대체됨), 11-05 · 11-06 PDF 대조에서 고친 규칙
"""
import re

# 코드마다 정규화(SI) 단위
SI = {'VRRM': 'V', 'VR': 'V', 'VRWM': 'V', 'VBR': 'V', 'VC': 'V', 'VZ': 'V', 'VF': 'V', 'VESD': 'V',
      'IF_AV': 'A', 'IFSM': 'A', 'IR': 'A', 'IPP': 'A', 'PD': 'W', 'PPPM': 'W', 'TRR': 's', 'CJ': 'F', 'TJ_MAX': 'degC'}
# 데이터시트 기호 → 코드. 기호 칸(SYMBOL)이나 머리 글에서 앞쪽 기호부터 찾는다
SYMS = {s: code for code, ss in {
    'VRRM': ['VRRM'], 'VR': ['VR', 'VDC', 'VRDC', 'VR(DC)'], 'VRWM': ['VRWM', 'VWM'],
    'VBR': ['VBR', 'V(BR)'], 'VC': ['VC', 'VCL', 'VCLAMP'], 'IPP': ['IPP', 'IPPM', 'IPPSM'],
    # [주의] TVS 순간 최대 전력(PPK)은 정상 소비전력 PD가 아니다(원형 1차 대조 오류 2건)
    'PPPM': ['PPK', 'PPP', 'PPPM', 'PPPSM', 'PPSM'], 'VESD': ['VESD', 'ESD'], 'VZ': ['VZ'],
    'IF_AV': ['IF(AV)', 'IFAV', 'IO', 'IF', 'I(AV)', 'IAV', 'IO(AV)'], 'IFSM': ['IFSM'], 'VF': ['VF', 'VFM'],
    'IR': ['IR', 'IRM', 'ID', 'IIB'], 'TRR': ['TRR'], 'PD': ['PD', 'PTOT', 'P(AV)', 'PM(AV)', 'PD(AV)'],
    'CJ': ['CJ', 'CD', 'CT'], 'TJ_MAX': ['TJ', 'TJMAX', 'TJ(MAX)']}.items() for s in ss}
# 기호로 못 정하면 설명 글의 낱말로 정한다. 앞줄이 먼저다(예: '반복 첨두 역전압'을 '작동 첨두 역전압'보다 먼저).
# [주의] IFSM은 'forward'가 붙어야 한다. TVS 표의 'Maximum Peak Surge Current IPP'는 IPP다
KEYWORDS = [(re.compile(p, re.I), c) for p, c in [
    (r'clamping voltage', 'VC'), (r'breakdown voltage', 'VBR'), (r'zener voltage', 'VZ'),
    (r'repetitive peak reverse voltage|peak repetitive reverse voltage|recurrent peak reverse', 'VRRM'),
    (r'stand-?\s*off|reverse working voltage|working peak reverse', 'VRWM'),
    (r'peak (pulse |impulse )?power|pulse power', 'PPPM'), (r'peak (pulse|impulse) current|pulse current', 'IPP'),
    (r'\besd\b|electrostatic', 'VESD'), (r'forward surge|surge (peak )?forward', 'IFSM'),
    (r'forward voltage', 'VF'), (r'recovery time', 'TRR'),
    (r'reverse (leakage )?current|leakage current|reverse leakage', 'IR'),
    # [주의] 'Surge peak forward current'(IFSM)·'Peak forward current'(IFM)는 평균 전류가 아니다
    (r'average (rectified )?(forward|output)|(?<!peak )forward (rectified |continuous )?current|output current', 'IF_AV'),
    (r'(?<!peak )(dc )?reverse voltage|dc blocking voltage', 'VR'), (r'power dissipation', 'PD'),
    (r'capacitance', 'CJ'), (r'junction temperature|operating junction', 'TJ_MAX')]]
# [주의] 글자로만 된 패키지 이름(SMA · ABS 등)은 대소문자를 구분한다((?-i:...)). 'Case: SOD-123 small outline'의 small이 SMA로 잡혔다(11-05, 59건)
# [주의] 'Thin SMA'(38문서) · 'Micro SMA'(23) · 'Sub SMA'(20)는 SMA와 다른 패키지다. 앞말을 같이 잡아야 SMA 조건 · 기판 비교에 걸리지 않는다(11-06 v3-14)
PKG = re.compile(r'\b(SOD-?\d+\w*|SOT-?\d+\w*|(?-i:(?:Thin|Micro|Sub) SM[ABCFP]\w*|SMA\w*|SMB\w*|SMC\w*|SMF\w*|SMP\w*)|DO-?\d+\w*|TO-?\d+\w*|MiniMELF|MicroMELF|(?-i:MMELF)|'
                 r'MELF|D2PAK|DPAK|DFN\w*|R-?\d\b|(?-i:GBU\w*|KBP\w*|KBJ\w*|GBJ\w*|ABS\w*|MBS\w*|MBF\w*)|TS\w*FL|SC-\d+\w*|'
                 r'PDI\w*|SOP-?\d+)', re.I)
BOTH_DIRECTIONS = re.compile(r'characteristics apply in both directions', re.I)  # TVS 문서 17건의 1쪽 주석(실측)
AEC_H = re.compile(r'"H"\s*means\s*AEC[- ]?Q101\s+qualified', re.I)  # 주문 정보 주석: H로 끝나는 품번만 인증품
AEC_ALL = re.compile(r'AEC[- ]?Q101\s+qualified(?!\s+available)', re.I)    # FEATURES: 그 문서 품번 전체가 인증품


def family(category):
    """'tvs-18' · 'a-14;b-16' → 'tvs' · 'a'(TSC 분류 이름에서 번호를 뗀 것)."""
    return re.sub(r'-\d+$', '', (category or '').split(';')[0])


def fields(text):
    """청크 본문 → [(머리 경로, 마지막 열 이름, 값)]. chunk.py가 '경로: 값'을 ' | '로 이어 붙인 모양(원형 build.py와 같음)."""
    body = text.split('] ', 1)[1] if '] ' in text else text
    body = body.split('\n주: ', 1)[0]  # [왜] chunk.py v3가 행 끝에 붙인 표 주석은 값 칸이 아니다
    out = []
    for f in body.split(' | '):
        head, sep, val = f.rpartition(': ')
        if sep:
            out.append((head, head.split(' / ')[-1].strip(), val.strip()))
    return out


def packages_of(c):
    """패키지 이름: 본문 'Case:' 글, KEY PARAMETERS의 Package 행, ORDERING INFORMATION의 PACKAGE 열(문서 단위)."""
    if c['kind'] == 'text':
        return [x.upper() for m in re.finditer(r'Case\s*:\s*([^\n;]+)', c['text']) for x in PKG.findall(m.group(1))]
    out = []
    F = fields(c['text'])
    is_pkg_row = any(col.upper().endswith('PARAMETER') and v.strip().lower() == 'package' for _, col, v in F)
    for _, col, v in F:
        if col.strip().upper() == 'PACKAGE' or (is_pkg_row and col.strip().upper() == 'VALUE'):
            out += [x.upper() for x in PKG.findall(v)]
    return out
