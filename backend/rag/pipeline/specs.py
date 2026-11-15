"""데이터시트 표 행 청크를 읽는 규칙과 해석기. 서버는 규칙 상수(`SI` · `SYMS` · `KEYWORDS` · `PKG` · `packages_of` · `family` · `BOTH_DIRECTIONS` · `AEC_H` · `AEC_ALL`)와 카드 한 장을 질문 때 코드로 읽는 `read_card`(`card_read.read_values`)를 쓴다.

- 역할: 표 행 청크("머리 경로: 값")를 읽어 품번마다 파라미터 코드 17종
  (5.7의 10종 + VR + TVS·ESD용 VRWM·VBR·VC·IPP·PPPM·VESD)의 값을 SI 단위로 뽑는다(`Doc` 해석기, `read_card`는 카드 한 장).
  값 하나는 원문 칸 하나에서 나오고 청크 번호를 같이 적는다. 모호한 값은 후보로 내지 않고 검토 표시(사유 · 청크 번호)로 남긴다:
  계열 범위·여러 값(range_unsplittable), 같은 자리·같은 조건의 다른 값(conflict), 모르는 단위(unknown_unit),
  원문 청크에 없는 숫자(value_not_in_source), 음수·무한(implausible), 파서가 머리를 밀거나 행을 합친 표(garbled_table),
  일부 품번 전용인데 대상 품번을 알 수 없는 행(scope_unclear), 최소·대표·최대 표시가 없는 항복·제너 전압(slot_unclear).
  2차 대조 뒤: IF_AV는 평균·연속 전류만(첨두·서지·반복·IFRM·IF,MAX 행은 IFSM이거나 제외), 머리 끝 숫자는 첫 행이 빨려 든 것이라
  떼고 읽음, 조건 주기로 품번 묶음 구간을 정함, 병합 칸 값은 가운데 열에서 대칭으로 펼침, 붙은 열 이름 칸을 나눔.
- 하지 않는 일: LLM·임베딩 호출, 값 비교·판정(`backend/judge/`), 파서가 밀어 놓은 표 바로잡기, 평가셋 정답 읽기, 파일 · DB 쓰기.
  부품 사양 표(part_specifications) 만들기 · 대조표 · 적재 명령(`build` · `sample` · `load`)은 11-09에 버리고 11-10에 지웠다(ADR 0016).
- 출처: db/schema/table-definition.md 5.7(코드 목록), SPEC.md 3절(단위 환산은 `backend/rag/units.py`),
  원형 `전자_데이터시트/evidence/spec_table/build.py`와 README의 대조 오류 수정(11-03), 50개 품번 PDF 대조(11-05, ADR 0013),
  카드 값 코드 먼저 읽기(사전 등록 #43)
"""
from collections import Counter, defaultdict
import math
import re

from backend.rag.units import to_si

# 코드마다 정규화 단위. 단위 차원이 다른 칸(예: IR 열 옆의 "@ VR / V" 조건 칸)은 그 코드의 값이 아니라서 버린다
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
# [주의] 이 기호가 먼저 나오면 뽑지 않는다: 반복 첨두 순방향 전류, 비반복 역전압, 보관 온도, 시험 전류 등
SKIP_SYMS = {'IFRM', 'IFM', 'VRSM', 'VRM', 'TSTG', 'IZT', 'IZK', 'IT', 'IZM', 'IRSM', 'VRMS', 'IRRM', 'QRR'}
# [주의] 실효값(VR(RMS) 등)은 정격 전압이 아니다(원형: 1N4934G에서 VR 70V로 잘못 들어감). 계수·저항·시험 전류 열도 값이 아니다
# ('coeffici'는 파서가 'COEFFICIEN T'로 끊은 온도 계수 열도 막는다. 1K5SMPC12APH에서 VBR 0.070이 나왔다)
# ('Non-repetitive peak forward surge current'는 IFSM이라 'repetitive peak forward'(IFRM) 제외에 걸리면 안 된다)
EXCLUDE = re.compile(r'\brms\b|coeffici|thermal|test current|marking|impedance|resistance|(?<!non-)(?<!non )repetitive peak forward|'
                     r'non-repetitive peak reverse voltage|reverse surge|recovery current|'
                     r'recovered charge|isolation|fusing|\bi2t\b', re.I)
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
SLOT_WORDS = {'min': 'minimum_value', 'minimum': 'minimum_value', 'typ': 'typical_value', 'typical': 'typical_value',
              'nom': 'typical_value', 'nominal': 'typical_value', 'max': 'maximum_value', 'maximum': 'maximum_value'}
# [왜] 최소·대표·최대 표시가 없는 칸(VALUE, 품번 열)은 정격·보증값이라 최대로 둔다. 정전용량은 대표값으로 적는 표가 많아 대표로 둔다
TYPICAL_BY_DEFAULT = {'CJ'}
# [주의] 항복·제너 전압은 최소·대표·최대가 모두 쓰이는 값이라 표시 없는 칸을 짐작하지 않는다(1.5KE110A의 VBR 105는 실제로 최소)
SLOT_REQUIRED = {'VBR', 'VZ'}
KEY_COL = re.compile(r'(?:^|\s)(PARAMETER|SYMBOL|UNIT|CONDITIONS?)$')
VALUE_COL = re.compile(r'(?:^|\s)(VALUE|LIMITS?|RATINGS?|MIN|MINIMUM|TYP|TYPICAL|NOM|NOMINAL|MAX|MAXIMUM)$')
NUM = r'[-+]?\s?\d+(?:,\d{3})*(?:\.\d+)?'
PARTLIKE = re.compile(r'(?=.*[A-Z])(?=.*\d)(?!IEC|JESD|AEC|MIL|EIA|JEDEC)[A-Z0-9][A-Z0-9.\-]{3,}')  # 품번처럼 생긴 낱말(규격 이름 제외)
# [주의] 글자로만 된 패키지 이름(SMA · ABS 등)은 대소문자를 구분한다((?-i:...)). 'Case: SOD-123 small outline'의 small이 SMA로 잡혔다(11-05, 59건)
# [주의] 'Thin SMA'(38문서) · 'Micro SMA'(23) · 'Sub SMA'(20)는 SMA와 다른 패키지다. 앞말을 같이 잡아야 SMA 조건 · 기판 비교에 걸리지 않는다(11-06 v3-14)
PKG = re.compile(r'\b(SOD-?\d+\w*|SOT-?\d+\w*|(?-i:(?:Thin|Micro|Sub) SM[ABCFP]\w*|SMA\w*|SMB\w*|SMC\w*|SMF\w*|SMP\w*)|DO-?\d+\w*|TO-?\d+\w*|MiniMELF|MicroMELF|(?-i:MMELF)|'
                 r'MELF|D2PAK|DPAK|DFN\w*|R-?\d\b|(?-i:GBU\w*|KBP\w*|KBJ\w*|GBJ\w*|ABS\w*|MBS\w*|MBF\w*)|TS\w*FL|SC-\d+\w*|'
                 r'PDI\w*|SOP-?\d+)', re.I)
SLOT_KO = {'minimum_value': '최소', 'typical_value': '대표', 'maximum_value': '최대'}
# 11-05 PDF 대조 뒤 더한 규칙의 글 모양들
BOTH_DIRECTIONS = re.compile(r'characteristics apply in both directions', re.I)  # TVS 문서 17건의 1쪽 주석(실측)
# 시험 조건 한 토막: 'IF = 7.5A', 'TJ = 125°C', 'VR = 4.0V'. 'TA'(표 전체 기본 온도)는 조건에서 뺀다
ATOM = re.compile(r'\b(I[A-Z]{1,3}|V[A-Z]{1,3}|T[A-Z])\s*=\s*([-+]?\d+(?:\.\d+)?)\s*([mµμun]?A|[mk]?V|°C)?(?!\w)')
BARE = re.compile(r'(열\d+|PARAMETER|SYMBOL|UNIT|CONDITIONS?|VALUE|LIMITS?|MIN|MINIMUM|TYP|TYPICAL|NOM|NOMINAL|MAX|MAXIMUM)\.?',
                  re.I)  # 표 제목 없이 열 이름만 있는 머리(이어지는 행)
GLUED_SLOT = re.compile(r'.*?\b(min|typ|nom|max)\.?\s+([-+]?\d+(?:\.\d+)?)', re.I)  # 'SPECIFICATIONS Min 2.35'
TITLE_WORDS = {'AND', 'ELECTRICAL', 'CHARACTERISTICS', 'RATINGS', 'MAXIMUM', 'SPECIFICATIONS', 'SPECIFICATION', 'TA',
               'UNLESS', 'OTHERWISE', 'NOTED'}  # 여러 줄 표 제목이 열 머리로 흩어진 낱말
SIZE = re.compile(r'\b(0201|0402|0603|0805|1206|1210|2010|2512)\b')  # 칩 크기 패키지(TS4148의 0603·0805·1206)
RANGE = re.compile(r'([A-Z0-9][A-Z0-9.\-]*?)\s*(?:~|–|\s-\s|\bTO\b)\s*([A-Z0-9][A-Z0-9.\-]*)')  # 품번 범위(대문자로 바꾼 글)
NAME = re.compile(r'(.*?)(\d+(?:\.\d+)?)([A-Z\-]*)')  # 품번 = 앞 글자 + 번호 + 뒤 글자('SFA' + 1001 + 'G')
# [주의] 평균·연속 전류(IF_AV)가 아닌 행: 첨두·서지·반복 낱말이나 IFRM·IFM·IF,MAX·IFSM 기호(2차 대조: MBRF1635의 IFRM 32 A,
# TSCDAH15120G2H의 'IF, MAX' 1158 A가 IF_AV로 들어갔다)
NOT_AVERAGE = re.compile(r'peak|surge|repetitive|\bIF\s*,\s*MAX\b|\bIFRM\b|\bIFM\b|\bIFSM\b', re.I)
GLUE_NAMES = {'CONDITIONS', 'CONDITION', 'SYMBOL', 'MIN', 'TYP', 'NOM', 'MAX', 'UNIT', 'VALUE'}  # 한 머리에 붙은 열 이름들
WAVE = re.compile(r'\d+\s*/\s*\d+\s*[uµμ]s', re.I)  # 펄스 파형 '10/1000us'·'8/20us'


def pkg_keys(text):
    """패키지 이름 → 비교용 열쇠 집합('DO-214AC (SMA)' → {'DO214AC', 'SMA'}, '0805 (Ceramics)' → {'0805'})."""
    return {re.sub(r'[^A-Z0-9]', '', x.upper()) for x in PKG.findall(text or '') + SIZE.findall(text or '')}


def junk_word(tok, upper):
    """열 이름 앞에 붙은 표 제목 조각인가('otherwise', 'noted)'). 품번·열 이름 낱말·품번처럼 생긴 낱말이면 아니다.
    [주의] 'CONDITIONS MBR3035PT MBR3045PT'는 품번 열이 아니라 조건 열 머리다(MBR3035PT SERIES에서 실측)."""
    t = tok.strip('()')
    return (norm_part(t) not in upper and not PARTLIKE.fullmatch(t.upper())
            and not re.fullmatch(r'(PARAMETERS?|SYMBOL|UNIT|CONDITIONS?|VALUE|MIN|TYP|NOM|MAX)\.?', t, re.I))


def title_only(head):
    """열 머리에 표 제목 조각·단위·자리 낱말·각주 번호만 있는가('AND / V / Nom (2)(3)')."""
    words = [w for w in re.findall(r'[A-Za-z]+', head) if not to_si(1.0, w)]
    return all(w.upper() in TITLE_WORDS or w.lower() in SLOT_WORDS for w in words)


def family(category):
    """'tvs-18' · 'a-14;b-16' → 'tvs' · 'a'(TSC 분류 이름에서 번호를 뗀 것)."""
    return re.sub(r'-\d+$', '', (category or '').split(';')[0])


def norm_part(s):
    """표 열 이름은 'MBR 2035 CT'처럼 띄어 쓰기도 해서 공백을 빼고 대문자로 맞춘다."""
    return re.sub(r'\s+', '', s or '').upper()


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


def code_of(text, sym='', strict=False):
    """설명 글(과 기호 칸) → (코드, 찾은 기호) 또는 (None, None).
    strict: 품번 한 줄 표의 열 머리용. 기호와 낱말이 다른 코드를 가리키면 다른 값의 하위 칸이라 버린다
    ('LEAKAGE CURRENT / VR V'는 VR 정격이 아니라 IR을 잰 전압)."""
    if EXCLUDE.search(f'{text} {sym}') or (re.search(r'storage', text, re.I) and not re.search(r'junction', text, re.I)):
        return None, None
    # [왜] '@'·'at' 뒤는 시험 조건이다('VF at IF = 100mA'의 IF, 'IR @ VR'의 VR는 잰 값이 아니다).
    # 머리 경로는 칸(' / ')마다 자른다: 'Clamping Voltage @IPPM (8/20us) / IPPM / A'의 마지막 칸 IPPM은 이 열의 기호다
    main = ' / '.join(re.split(r'@|\bat\b|,', seg, maxsplit=1, flags=re.I)[0] for seg in text.split(' / '))
    toks = re.findall(r'[A-Za-z][A-Za-z0-9()]*', sym) + re.findall(r'\b[A-Z][A-Za-z0-9()]*', main)
    word = next((c for p, c in KEYWORDS if p.search(main)), None)
    code, found = word, None
    for tok in toks:
        if tok.upper() in SKIP_SYMS:
            # [왜] 'Zener Voltage / IZT / Min'처럼 시험 전류 기호가 붙은 머리도 낱말이 정하면 그 값이다(낱말이 없으면 뽑지 않음)
            break
        if tok.upper() in SYMS:
            code, found = SYMS[tok.upper()], tok
            # [왜] 기호와 낱말이 다르면 다른 값의 하위 칸이다(IR을 잰 VR 칸). 단 IPP·VRWM은 VC·IR의 조건 칸이면서 TVS 정격이다
            if strict and word and word != code and code not in ('IPP', 'VRWM'):
                return None, None
            break
    if code == 'IF_AV' and NOT_AVERAGE.search(f'{text} {sym}'):
        # 비반복 서지는 IFSM(펄스 조건과 함께), 반복 첨두(IFRM·IFM)는 뽑지 않는다
        code = 'IFSM' if re.search(r'surge|non-?\s?repetitive|IF\s*,\s*MAX', f'{text} {sym}', re.I) else None
    return (code, found) if code else (None, None)


def unit_of(*texts):
    """UNIT 칸이나 머리 경로에서 처음 나오는 단위 낱말."""
    for t in texts:
        # [주의] '/'로는 나누지 않는다: 'mW/°C'(감쇠율)·'°C/W'(열저항) 같은 비율 단위를 mW·W로 읽으면 안 된다.
        # 머리 경로 구분자 ' / '는 앞뒤 공백으로 나뉜다
        for tok in re.split(r'[\s()\[\],@:=]+', t or ''):
            if tok and to_si(1.0, tok):
                return tok
    return None


def parse_cell(cell):
    """칸 글 → (모양, 숫자 글 목록, 칸 안 단위). 모양: one(값 하나) · range(a - b) · many(빈칸으로 나뉜 여러 값) · None(숫자 아님)."""
    s = re.sub(r'[–−]', '-', cell.replace('±', '')).strip()
    unit = None
    m = re.fullmatch(r'(.*?\d)\s*([A-Za-zµμ°℃]+)', s)
    if m and to_si(1.0, m.group(2)):  # '150 mA'처럼 값 칸에 단위가 붙은 경우
        s, unit = m.group(1), m.group(2)
    m = re.fullmatch(rf'({NUM})\s*(?:-|~|to)\s*({NUM})', s)
    if m:
        return 'range', [m.group(1).replace(' ', ''), m.group(2).replace(' ', '')], unit
    if re.fullmatch(rf'(?:[<>≤≥]?\s*{NUM}\s*)+', s):
        nums = [x.replace(' ', '') for x in re.findall(NUM, s)]
        return ('one' if len(nums) == 1 else 'many'), nums, unit
    return None, [], unit


def to_float(num_text):
    return float(num_text.replace(',', '').replace(' ', ''))


def auto_checks(num_texts, values, code, chunk_text):
    """표에 넣기 전 자동 검사: 숫자 글이 원문 청크 본문에 그대로 있는가, 값이 유한하고 (온도 말고는) 음수가 아닌가."""
    squash = lambda s: re.sub(r'[\s,]', '', s)  # noqa: E731  [왜] '1,500'과 '1500', '- 55'와 '-55'를 같게 본다
    body = squash(chunk_text.split('] ', 1)[-1].split('\n주: ', 1)[0])  # 행 끝 주석의 숫자로 값을 확인하지 않는다
    in_src = all(squash(n).lstrip('+') in body for n in num_texts)
    plausible = all(math.isfinite(v) and (v >= 0 or code == 'TJ_MAX') for v in values.values())
    return {'value_in_source': in_src, 'plausible': plausible}


def label_condition(label):
    """설명 글 안의 시험 조건('VF at IF = 100mA' → 'at IF = 100mA', 'ESD per IEC ... (Air)' → 'per IEC ... (Air)')."""
    s = re.sub(r'\((?:note\s*)?\d+\)', '', label or '', flags=re.I).strip()  # 각주 번호 (1)·(Note 2)는 조건이 아니다
    # 'IF = 10mA'는 기호부터 조건이다. 'according to IEC61000-4-2 air discharge'는 시험 방법이라 조건이다
    # 펄스 폭('8.3ms', '10/1000µs')도 조건의 시작이다(TSS54U의 'Peak Forward Surge Current 8.3ms Single Half Sine-Wave')
    m = re.search(r'@|\bat\b|[A-Za-z][\w()]*\s*=|,|\(|\bper\b|\bfor\b|\baccording to\b|\b\d+(?:\.\d+)?\s*(?:ms|[uµμ]s)\b|'
                  r'\b\d+\s*/\s*\d+\s*[uµμ]s', s, re.I)
    rest = s[m.start():].strip(' ,') if m else ''
    return '' if rest.lower() in ('per', 'for', 'at', '@') else rest  # [왜] 'Forward voltage per'처럼 잘린 글의 끝 낱말은 조건이 아니다


def at_condition(head, F, code=None, own=None):
    """품번 한 줄 표의 'VBR@IT'·'VC at IPPM' 머리에서 같은 행의 IT·IPPM 값 칸을 찾아 'IT = 1 mA'로 만든다.
    같은 기호 칸이 여럿이면 머리 경로 앞부분이 가장 많이 같은 칸(같은 열 묶음)을 쓴다. 머리 안의 온도·펄스 파형도 붙인다.
    VZ·VBR 머리에 '@'가 없으면 같은 행의 시험 전류 칸('TEST CURRENT IZT mA: 5')을 조건으로 쓴다. 조건이 없으면 None."""
    # [왜] 온도는 마지막 열 이름에서만 찾는다. 표 이름의 '(TA = 25°C unless otherwise noted)'는 표 전체의 기본 조건이다
    extra = [re.sub(r'\s+', ' ', t) for t in re.findall(r'\bT[JA]\s*=\s*[-+]?\d+\s*°?C', head.split(' / ')[-1])]
    extra += [re.sub(r'\s+', '', w) for w in WAVE.findall(head)]  # [왜] 10/1000us와 8/20us 값은 다른 조건이다(BZW06)
    m = re.search(r'(?:@|\bat\b)\s*([A-Za-z][A-Za-z0-9()]*)', head)
    cond = None
    if m:
        sym = m.group(1)
        cond, dim, best = f'@{sym}', {'V': 'V', 'I': 'A'}.get(sym[0].upper()), -1
        segs = head.split(' / ')
        for h, _, v in F:
            u = unit_of(h)
            if h not in (head, own) and sym in re.findall(r'[A-Za-z][A-Za-z0-9()]*', h) and u and to_si(1.0, u)[1] == dim:
                shape, nums, _ = parse_cell(v)
                same = next((i for i, (a, b) in enumerate(zip(segs, h.split(' / '))) if a != b), min(len(segs), len(h.split(' / '))))
                if shape == 'one' and same > best:
                    cond, best = f'{sym} = {nums[0]} {u}', same
    if code in ('VZ', 'VBR') and (cond is None or cond.startswith('@')):
        cond = test_current(F) or cond
    return '; '.join(x for x in [cond] + extra if x) or None


def test_current(F):
    """같은 행의 시험 전류 칸('TEST CURRENT IZT mA: 5', 'Test Current IT (mA): 1') → 'IZT = 5 mA'."""
    for h, _, v in F:
        sym = re.findall(r'\bI(?:ZT|Z|T)\b', h)
        u = unit_of(h)
        if re.search(r'test current', h, re.I) and sym and u and to_si(1.0, u)[1] == 'A' and parse_cell(v)[0] == 'one':
            return f'{sym[0]} = {parse_cell(v)[1][0]} {u}'
    return None


def split_glued(F):
    """열 이름 여럿이 한 머리로 붙은 칸('CONDITIONS SYMBOL TYP MAX UNIT: IF = 3A, TJ = 25°C - 0.50 V')을 열마다 나눈다.
    뒤에서부터 단위·값(MAX·TYP·MIN)·기호를 떼고 남는 앞부분이 조건이다(SK32BH SERIES)."""
    out = []
    for h, col, v in F:
        names = col.upper().replace('.', '').split()
        n = len(names)
        while n and names[n - 1] in GLUE_NAMES:
            n -= 1
        names = names[n:]
        if len(names) < 3:
            out.append((h, col, v))
            continue
        toks, cells = v.split(), {}
        if 'UNIT' in names and toks and to_si(1.0, toks[-1]):
            cells['UNIT'] = toks.pop()
        for name in reversed([x for x in names if x in ('MIN', 'TYP', 'NOM', 'MAX', 'VALUE')]):
            if not toks or not re.fullmatch(r'-|[-+]?\d+(?:\.\d+)?', toks[-1]):
                break
            cells[name] = toks.pop()
        if 'SYMBOL' in names and toks and toks[-1].upper() in SYMS:
            cells['SYMBOL'] = toks.pop()
        if toks and any(x.startswith('CONDITION') for x in names):
            cells['CONDITIONS'] = ' '.join(toks)
        out += [(name, name, cells[name]) for name in names if name in cells]
    return out


class Doc:
    """문서 하나의 행을 읽는다(describe → emit_row). 서비스는 `read_card`로 카드 한 장씩만 쓴다."""

    def __init__(self, doc, parts, fam):
        self.doc, self.parts, self.family = doc, parts, fam
        self.upper = {norm_part(p): p for p in parts}
        self.cands, self.review = [], []
        self.checked = Counter()
        # [주의] 아래 표 단서 칸(part_pkg · col_pkg · slot_hint · part_cols · pkg_universe)을 채우던 문서 전체 읽기는 지웠다. 지금은 늘 비어 있다
        self.part_pkg = defaultdict(set)  # 품번 → 패키지 열쇠(주문표 PACKAGE 칸). TS4148 RBG → {'0805'}
        self.col_pkg = {}  # (쪽, 표) → {열 머리: [패키지 열쇠, ...]}: 'Package' 행이 열마다 패키지를 적은 표
        self.slot_hint = {}  # ((쪽, 표), 칸 순서, 열 머리) → 'Min'·'Nom'·'Max': 첫 데이터 행에 붙어 들어온 머리 행
        self.split_head = {}  # ((쪽, 표), 잘린 열 머리) → (코드, 기호, 원래 머리): 앞 행에서 'AND / V / Nom'이 이어받은 코드
        self.part_cols = {}  # (쪽, 표) → 품번 열 머리 목록(순서대로). 품번 열이 가장 많은 행에서 배운다
        self.pkg_universe = set()

    def flag(self, reason, parts, base, code, text, detail=''):
        self.review.append({'reason': reason, 'parts': list(parts), 'doc': self.doc, 'family': self.family,
                            'parameter_code': code, 'source_value_text': text, 'test_condition': base['test_condition'],
                            'page_number': base['page_number'], 'table_name': base['table_name'],
                            'row_label': base['row_label'], 'chunks': [base['chunk']], 'detail': detail})

    def emit(self, c, cell, targets, named, slot, code, base, units, level):
        """칸 하나를 후보 행으로 바꾼다. named: 대상 품번이 행·열 머리에 적혀 있는가(계열 범위를 나눌 수 있는 조건)."""
        m = re.fullmatch(r'([A-Za-z][A-Za-z()]*)\s+([-+]?\d+(?:\.\d+)?)', cell.strip())
        if m and m.group(1).upper() in SYMS:
            cell = m.group(2)  # [왜] 'TYP: VF 0.97'처럼 기호 칸 글이 값 칸에 밀려 들어왔다(ES2BFSH·RS2DFL SERIES)
        shape, nums, cell_unit = parse_cell(cell)
        if not shape:
            return
        unit = cell_unit or unit_of(*units)
        written = unit
        if unit is None:
            # [왜] 전압은 단위 없이 적는 표가 많아 V로 둔다(원형과 같음). ESD 내압은 kV라서 짐작하지 않는다
            unit = 'V' if SI[code] == 'V' and code != 'VESD' else '°C' if code == 'TJ_MAX' else None
        if unit is None:
            return self.flag('unknown_unit', targets, base, code, cell)
        factor = to_si(1.0, unit)
        if factor[1] != SI[code]:
            return  # [주의] 단위 차원이 다르면 이 코드의 값이 아니라 옆 조건 칸이다(예: 'IR @ VR / V')
        txt = lambda n: f'{n} {written}' if written else n  # noqa: E731
        if code == 'TJ_MAX' and shape == 'range':  # 온도 범위 '-55 to +150'은 그 부품의 최소·최대다(계열 범위가 아님)
            groups = [(targets, {'minimum_value': to_float(nums[0]), 'maximum_value': to_float(nums[1])}, nums,
                       txt(f'{nums[0]} to {nums[1]}'))]
        elif len(nums) > 1 and not (named and len(targets) == len(nums)):
            return self.flag('range_unsplittable', targets, base, code, cell,
                             f'품번 {len(targets)}개({"머리에 적힘" if named else "문서 전체"}), 값 {len(nums)}개')
        elif slot is None:
            return self.flag('slot_unclear', targets, base, code, cell)
        elif len(nums) == 1:
            groups = [(targets, {slot: to_float(nums[0])}, nums, txt(nums[0]))]
        else:
            # 행·열 머리에 적힌 품번 수와 칸의 값 수가 같으면 적힌 순서대로 나눈다
            groups = [([p], {slot: to_float(n)}, [n], txt(n)) for p, n in zip(targets, nums)]
        for parts, vals, ns, text in groups:
            si = {k: v * factor[0] for k, v in vals.items()}
            checks = auto_checks(ns, si, code, c['text'])
            self.checked.update(k for k, ok in checks.items() if not ok)
            self.checked['candidates'] += 1
            if not all(checks.values()):
                reason = 'value_not_in_source' if not checks['value_in_source'] else 'implausible'
                self.flag(reason, parts, base, code, text)
                continue
            for p in parts:
                self.cands.append({**base, 'part': p, 'parameter_code': code, 'minimum_value': si.get('minimum_value'),
                                   'typical_value': si.get('typical_value'), 'maximum_value': si.get('maximum_value'),
                                   'source_value_text': text, 'source_unit': written, 'normalized_unit': SI[code],
                                   'source_level': level, 'checks': checks})

    def describe(self, c):
        """표 행 하나를 읽는다. 품번 한 줄(TVS·제너) 행은 바로 per_part로 내고 None, 파라미터 행은 정보 사전을 돌려준다."""
        F = split_glued(fields(c['text']))
        base = {'doc': self.doc, 'family': self.family, 'symbol': None, 'test_condition': None,
                'page_number': c['page'], 'table_name': c['table'], 'row_label': c['row'], 'text_value': None,
                'footnote_text': None, 'chunk': {'doc': self.doc, 'idx': c['idx']}}
        cols = defaultdict(list)
        for _, col, v in F:
            m = KEY_COL.search(col.upper().rstrip('.'))
            if m:
                cols[m.group(1).rstrip('S')].append(v)
        label = re.sub(r'^PARAMETER\s+', '', c['row'] or '')
        row_parts, merged = self.row_parts(c['row'], F)
        # [왜] 머리가 'TYP'·'MAX'·'열2'뿐인 행은 위 파라미터 행을 이어받는 행이다(SFS1601G의 둘째 묶음 행)
        bare = all(BARE.fullmatch(h.strip()) for h, _, _ in F)
        if row_parts and not cols['PARAMETER'] and not cols['SYMBOL'] and not bare:
            return self.per_part(c, F, row_parts, merged, base)
        # [왜] 'ELECTRICAL SPECIFICATIONS: Forward voltage | PARAMETER: HS2AAH HS2BAH'처럼 파라미터 이름은 행 이름(첫 칸)에,
        # 품번 묶음은 PARAMETER 칸에 들어간 표가 많다. 행 이름을 맨 앞에 두고 나머지 PARAMETER 칸은 품번·조건으로 본다
        params = list(dict.fromkeys(x for x in [label] + cols['PARAMETER'] if x))
        # 행 이름 'Forward voltage'와 PARAMETER 칸 'Forward voltage @ IF = 50A ...'처럼 앞부분이 같으면 긴 쪽 하나만 이름으로 둔다
        params = [x for x in params if not any(y != x and y.lower().startswith(x.lower()) for y in params)] or ['']
        code, tok = code_of(params[0], ' '.join(cols['SYMBOL'])) if params[0] else (None, None)
        if not code and not bare:
            return None
        group, pkgs, unknown, conds, scan, garbled = [], set(), False, [label_condition(params[0]) if code else ''], [], None
        colpkg = self.col_pkg.get((c['page'], c['table']), {})
        for h, col, v in F:
            C = col.upper().rstrip('.')
            kind = KEY_COL.search(C)
            if VALUE_COL.search(C):
                if parse_cell(v)[0] is None and v.strip(' -'):
                    scan.append(v)  # [왜] 'TYP: 25°C -'처럼 쪼개진 조건 조각이 값 칸에 들어온다(MBRF1545CT-Y)
                continue
            if self.col_parts(h) or h in colpkg or (kind and kind.group(1) in ('SYMBOL', 'UNIT')):
                continue
            if code and v in (label, params[0]):
                continue  # 파라미터 이름 칸
            # [왜] 품번 묶음은 PARAMETER 칸 말고도 CONDITIONS 칸('CONDITIONS: SK52BH')이나 깨진 머리 칸('(TA: SRAS2020 ...')에 들어간다
            hits = self.cell_parts(v)
            group += [p for p in hits if p not in group]
            rest = self.residue(v) if hits else v
            if hits and self.parts_around_condition(v):
                # [주의] 'SFF1002G SFF1003G IF = 5A,TJ = 25°C SFF1005G ...': 세로로 합친 품번 묶음 여럿과 조건이 한 칸이 됐다.
                # 어느 행이 어느 묶음인지 알 수 없다(SFF1001G·SFA1001G SERIES)
                garbled = '품번 묶음 여럿과 조건이 한 칸에 합쳐져 값과 짝을 지을 수 없음'
            scan.append(rest)
            if hits:
                if ATOM.search(rest):
                    conds.append(rest)  # 'BAT42W IF = 50mA'에서 품번을 뺀 'IF = 50mA'는 시험 조건이다
            elif len(self.pkg_universe) > 1 and pkg_keys(v) & self.pkg_universe:
                pkgs |= pkg_keys(v)  # 'PARAMETER: 0603, 1206 (Ceramics)': 그 패키지 품번 전용 행
            elif kind and kind.group(1) in ('PARAMETER', 'CONDITIONS', 'CONDITION'):
                toks = re.split(r'[\s/,&]+', v.upper())
                unknown |= any(PARTLIKE.fullmatch(t) and not re.fullmatch(r'[\d.]+[A-ZΜµ°]+', t) for t in toks)
                conds.append(v)
            elif ATOM.search(v):
                conds.append(v)  # '열3: IF = 10A, TJ = 25°C'처럼 이름 없는 머리 아래 조건 칸
        return {'c': c, 'F': F, 'base': base, 'label': label, 'params': params, 'code': code, 'tok': tok,
                'symbol': ' '.join(cols['SYMBOL']) or tok, 'unit': cols['UNIT'][:1], 'group': group, 'pkgs': pkgs,
                'unknown': unknown, 'conds': conds, 'scan': scan, 'bare': bare, 'garbled': garbled}

    def emit_row(self, info):
        """파라미터 행 하나의 값 칸을 후보로: 품번 열 > 패키지 열 > MIN·TYP·MAX·VALUE 칸."""
        c, F, code, params0 = info['c'], info['F'], info['code'], info['params'][0]
        if not code:
            return
        base = {**info['base'], 'symbol': info['symbol'], 'test_condition': '; '.join(x for x in info['conds'] if x) or None}
        group = info['group']
        if info['pkgs'] and not group:
            group = [p for p in self.parts if self.part_pkg.get(p, set()) & info['pkgs']]
        if info['garbled']:
            for _, col, v in F:
                if VALUE_COL.search(col.upper().rstrip('.')) and parse_cell(v)[0]:
                    self.flag('garbled_table', group or self.parts, base, code, v, info['garbled'])
            return
        if not group and (info['unknown'] or re.search(r'\bonly\b', params0, re.I)):
            # [주의] '단방향 전용'·'VWM 40V 미만 전용' 행을 모든 품번에 붙이면 틀린다(원형 2차 대조 오류 1건)
            return self.flag('scope_unclear', self.parts, base, code, params0)
        level = 'key' if (c['table'] or '').upper().startswith('KEY PARAMETERS') else 'group' if group else 'value'
        colpkg, seen, unclear = self.col_pkg.get((c['page'], c['table']), {}), Counter(), False
        spans = self.merged_spans(c, F)
        for head, col, v in F:
            units = info['unit'] or [head]  # [주의] UNIT 칸이 있으면 그것만 본다(모르는 단위면 머리 글로 짐작하지 않는다)
            hits = self.col_parts(head) + spans.get(head, [])
            vcol = VALUE_COL.search(col.upper().rstrip('.'))
            if hits:  # 열 이름이 품번(열 하나에 품번이 여럿 적힌 경우 포함)
                self.emit(c, v, hits, True, self.slot(None, params0, code), code, base, units, 'part')
            elif head in colpkg:
                # [왜] 'Package' 행이 열마다 패키지를 적은 표: n번째 열은 n번째 패키지 품번의 값이다(TS4148의 0603·0805·1206)
                keys = colpkg[head][seen[head]] if seen[head] < len(colpkg[head]) else set()
                seen[head] += 1
                pp = [p for p in self.parts if self.part_pkg.get(p, set()) & keys]
                if pp:
                    self.emit(c, v, pp, True, self.slot(None, params0, code), code, base, units, 'part')
                elif parse_cell(v)[0] and not unclear:
                    unclear = True
                    self.flag('scope_unclear', self.parts, base, code, v, '패키지별 열인데 품번의 패키지를 모름')
            elif vcol:
                self.emit(c, v, group or self.parts, bool(group), self.slot(vcol.group(1), params0, code), code, base,
                          units, level)
        if info['pkgs'] and not group:
            self.flag('scope_unclear', self.parts, base, code, params0, '패키지 전용 행인데 품번의 패키지를 모름')

    def per_part(self, c, F, row_parts, merged, base):
        """품번 한 줄 표: 열 머리('Breakdown voltage VBR@IT (V) / Min')가 코드·자리·단위를 정한다."""
        # [주의] 품번 하나인 행에서 한 칸에 숫자가 둘 이상이면 파서가 칸을 합쳐 뒤 칸 값이 한 칸씩 밀린 행이다
        # (1.5SMC15H: 'VWM (V): 12.1 1' 뒤의 IR 칸에 IPPM 값 71이 들어감). 그 행의 값은 모두 검토로 보낸다
        shifted = any(parse_cell(v)[0] == 'many' for _, _, v in F)
        start, prev, key = len(self.cands), None, (c['page'], c['table'])
        for pos, (raw, _, v) in enumerate(F):
            # [왜] 머리 끝의 숫자는 머리로 빨려 들어간 첫 데이터 행의 값이다('Min 6.12', '/ 5'). 이 행 값은 맞으니 떼고 읽는다
            # (2차 PDF 대조: 5KSMC10(C)AH·1.5KE·P6KE의 행 값이 모두 PDF와 같았다. 1차에서는 검토로 보냈다)
            segs = raw.split(' / ')
            segs[-1] = re.sub(r'(?:^|\s+)[\d.]+$', '', segs[-1]).strip()
            head = ' / '.join(x for x in segs if x) or raw
            col = head.split(' / ')[-1]
            code, tok = code_of(head, strict=True)
            word = re.search(r'\b(min|typ|nom|max)', col, re.I)
            cond = at_condition(head, F, code, raw) if code else None
            if not code and word and title_only(head):
                if prev and prev[0] in SLOT_REQUIRED:
                    # [왜] 'AND / V / Nom'처럼 표 제목 조각만 남은 머리는 앞 칸(VZ·VBR)의 대표·최대 칸이다
                    code, tok, cond = prev[:3]
                    self.split_head[(key, head)] = (code, tok, prev[3])
                elif (key, head) in self.split_head:
                    # 같은 표의 앞 행에서 배운 것: 이 행은 앞 칸(Min)이 빠졌어도 그 머리는 같은 코드다(1M130Z)
                    code, tok, first = self.split_head[(key, head)]
                    cond = at_condition(first, F, code)
            if not code:
                prev = prev if word else None
                continue
            prev = (code, tok, cond, prev[3] if prev and prev[:3] == (code, tok, cond) else head)
            b = {**base, 'symbol': tok, 'test_condition': cond}
            if merged or shifted:
                # [주의] 품번마다 한 줄인 표에서 한 칸에 품번이 둘이면 파서가 행을 합친 것이다.
                # 값 짝이 어긋난다(SMBJ110 SMBJ110A의 'Min: 111 122'에서 111은 다른 행 값). 수가 맞아도 나누지 않는다
                self.flag('garbled_table', row_parts, b, code, v, '한 행에 품번 여러 개' if merged
                          else '한 칸에 숫자 여러 개(칸 밀림)')
                continue
            glued = GLUED_SLOT.fullmatch(v) if parse_cell(v)[0] is None else None
            if glued:  # 'SPECIFICATIONS Min 2.35': 머리 행 글이 붙은 첫 데이터 행
                v = glued.group(2)
            # [왜] 자리는 마지막 열 이름만 본다. 'Nominal Zener Voltage / Vz@Iz'의 Nominal은 아래 칸 셋(최소·대표·최대) 모두의 머리다
            hint = (word and word.group(1)) or (glued and glued.group(1)) or \
                self.slot_hint.get(((c['page'], c['table']), pos, raw))
            self.emit(c, v, row_parts, True, self.slot(hint, '', code), code, b, [head], 'part')
        self.check_order(start)

    def check_order(self, start):
        """한 행에서 같은 품번·코드·조건의 최소 ≤ 대표 ≤ 최대가 어긋나면 파서가 옆 행과 값을 바꾼 것이라 검토로 보낸다(1M130Z)."""
        new = self.cands[start:]
        slots = defaultdict(dict)
        for r in new:
            for s in SLOT_KO:
                if r[s] is not None:
                    slots[(r['part'], r['parameter_code'], r['test_condition'])][s] = r[s]
        bad = {k for k, d in slots.items() if [d[s] for s in SLOT_KO if s in d] != sorted(d.values())}
        if bad:
            self.cands[start:] = [r for r in new if (r['part'], r['parameter_code'], r['test_condition']) not in bad]
            for r in new:
                if (r['part'], r['parameter_code'], r['test_condition']) in bad:
                    self.flag('garbled_table', [r['part']], r, r['parameter_code'], r['source_value_text'],
                              '최소 ≤ 대표 ≤ 최대가 어긋남(옆 행과 값이 바뀐 것으로 보임)')

    def merged_spans(self, c, F):
        """품번 열 표에서 이 행에 빠진 품번 열이 있으면, 병합 칸 값은 그 칸 가운데 열에만 적힌다(DBLS101G: 101G~105G 칸의 40이 103G에).
        있는 열 c마다 양옆이 함께 비어 있는 만큼 대칭으로 넓힌 구간을 그 칸으로 본다. 빈 열이 정확히 한 구간에만 들 때만 펼친다.
        돌려주는 것: {있는 열 머리: [더 붙일 품번]}"""
        full = self.part_cols.get((c['page'], c['table']), [])
        here = [h for h, _, _ in F if self.col_parts(h)]
        if not here or len(here) >= len(full) or any(h not in full for h in here):
            return {}
        have = {full.index(h) for h in here}
        cover = defaultdict(list)
        for i in sorted(have):
            r = 1
            while i - r >= 0 and i + r < len(full) and i - r not in have and i + r not in have:
                cover[full[i]] += [full[i - r], full[i + r]]
                r += 1
        missing = [full[j] for j in range(len(full)) if j not in have]
        counted = Counter(h for hs in cover.values() for h in hs)
        if any(counted[h] != 1 for h in missing):
            return {}  # [주의] 어느 칸에 드는지 하나로 정해지지 않으면 비워 둔다
        return {h: [p for x in hs for p in self.col_parts(x)] for h, hs in cover.items()}

    def parts_around_condition(self, v):
        """칸 글에서 품번이 조건 토막(TA 제외) 앞과 뒤에 모두 있는가."""
        atoms = [m for m in ATOM.finditer(v) if m.group(1) != 'TA']
        if not atoms:
            return False
        pos = [m.start() for m in re.finditer(r'\S+', v) if norm_part(m.group().strip('(),')) in self.upper]
        return any(p < atoms[0].start() for p in pos) and any(p > atoms[-1].end() for p in pos)

    def col_parts(self, head):
        """열 이름이 이 문서의 품번이면 그 품번 목록.
        'S1A/S1B'(열 하나에 여럿), 'otherwise GBU25J GA'(표 제목 조각이 앞에 붙음), 'GBPC15, 25, 35 / 005'(계열 묶음 열)."""
        segs = head.split(' / ')
        col, hits = segs[-1], []
        for piece in re.split(r'[/,&]', col):
            toks = piece.split()
            for i in range(len(toks)):  # [왜] 뒤에서부터 낱말을 붙여 품번이 되는 가장 긴 꼬리를 찾는다(낱말 경계에서만)
                k = norm_part(''.join(toks[i:])).rstrip('.')
                if k in self.upper and all(junk_word(t, self.upper) for t in toks[:i]):
                    hits.append(self.upper[k])
                    break
        m = len(segs) > 1 and re.fullmatch(r'\d+\w*', col.strip()) and \
            re.fullmatch(r'([A-Z]+)(\d+)((?:\s*,\s*\d+)+)', segs[-2].strip())
        if not hits and m:
            nums = [m.group(2)] + re.findall(r'\d+', m.group(3))
            hits = [self.upper[k] for k in (m.group(1) + n + col.strip() for n in nums) if k in self.upper]
        return list(dict.fromkeys(hits))

    def cell_parts(self, v):
        """칸 글에 적힌 이 문서의 품번. 'SFA1001G - SFA1004G'·'SFA1001G~1004G' 범위는 안쪽 품번으로 펼친다."""
        V = v.upper()
        hits = [p for m in RANGE.finditer(V) for p in self.expand(m.group(1), m.group(2))]
        hits += [self.upper[t] for t in re.split(r'[\s/,&()~]+', V) if t in self.upper]
        return list(dict.fromkeys(hits))

    def expand(self, a, b):
        """범위 양 끝(뒤 끝은 앞부분 생략 가능) → 앞·뒤 글자가 같고 번호가 사이인 품번(번호 순)."""
        pa = NAME.fullmatch(a)
        if a not in self.upper or not pa:
            return []
        b = b if b in self.upper else pa.group(1) + b
        pb = NAME.fullmatch(b)
        if b not in self.upper or not pb or pa.group(1, 3) != pb.group(1, 3):
            return []
        lo, hi = float(pa.group(2)), float(pb.group(2))
        inside = [(float(m.group(2)), p) for k, p in self.upper.items()
                  if (m := NAME.fullmatch(k)) and m.group(1, 3) == pa.group(1, 3) and lo <= float(m.group(2)) <= hi]
        return [p for _, p in sorted(inside)]

    def residue(self, v):
        """칸 글에서 품번과 각주 번호를 뺀 나머지('BAT42W IF = 50mA' → 'IF = 50mA')."""
        toks = [t for t in v.split() if norm_part(t.strip('(),')) not in self.upper]
        return re.sub(r'\(\d\)', '', ' '.join(toks)).strip()

    def row_parts(self, label, F):
        """행 이름과 'PART'·'ORDERING CODE' 칸에 적힌 이 문서의 품번 목록, 그리고 한 칸에 품번이 둘 이상인지(행 합침).
        'Part number / Uni: SMDJ60AH | Part number / Bi: SMDJ60CAH'는 칸이 달라 합침이 아니다."""
        parts, merged = [], False
        for cell in [label] + [v for h, _, v in F if 'PART' in h.upper() or 'ORDERING CODE' in h.upper()]:
            if norm_part(cell) in self.upper:
                hits = [self.upper[norm_part(cell)]]
            else:
                hits = list(dict.fromkeys(self.upper[t] for t in (cell or '').upper().split() if t in self.upper))
            merged |= len(hits) > 1
            parts += [p for p in hits if p not in parts]
        return parts, merged

    @staticmethod
    def slot(word, text, code):
        """MIN·TYP·MAX 열 이름 > 설명 글의 typical·nominal·minimum·maximum > 코드 기본값. 항복·제너 전압은 기본값 없이 None."""
        if word and word.lower() in SLOT_WORDS:
            return SLOT_WORDS[word.lower()]
        m = re.search(r'\b(typical|nominal|minimum|maximum)\b', text or '', re.I)
        if m:
            return SLOT_WORDS[m.group(1).lower()]
        if code in SLOT_REQUIRED:
            return None
        return 'typical_value' if code in TYPICAL_BY_DEFAULT else 'maximum_value'


def read_card(file, parts, card):
    """카드 한 장(card_read 모양: chunk_id · page · table · row · content) → (후보 행, 검토 표시, 행 코드). 표를 만들거나 저장하지 않는다.

    행 코드: 파라미터 행이면 그 코드, 품번 한 줄 행이면 'per_part', 읽을 행이 아니면 None. `card_read`가 질문 때 LLM보다 먼저 부른다.
    [왜] 문서 전체로 읽으면 이웃 행 규칙이 SSA1H60H VRRM에 RMS 행 값(42 V)을 붙였다(11-09 조사). 카드 하나만 보고 표 단서도 쓰지 않는다
    """
    D = Doc(file, parts, '')
    info = D.describe({'kind': 'table_row', 'text': card['content'], 'idx': card['chunk_id'], 'page': card['page'],
                       'table': card['table'], 'row': card['row']})
    if info:  # 파라미터 행. 품번 한 줄 행은 describe가 이미 후보를 냈다(per_part)
        D.emit_row(info)
    return D.cands, D.review, info['code'] if info else 'per_part' if D.cands or D.review else None


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


AEC_H = re.compile(r'"H"\s*means\s*AEC[- ]?Q101\s+qualified', re.I)  # 주문 정보 주석: H로 끝나는 품번만 인증품
AEC_ALL = re.compile(r'AEC[- ]?Q101\s+qualified(?!\s+available)', re.I)    # FEATURES: 그 문서 품번 전체가 인증품
