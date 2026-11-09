"""데이터시트 표 행 청크를 부품 사양 표(part_specifications) 행으로 바꾸는 오프라인 도구(서버가 import하지 않는다).

- 역할: chunks.jsonl의 표지 청크(품번 목록)와 표 행 청크("머리 경로: 값")를 읽어 품번마다 파라미터 코드 17종
  (5.7의 10종 + VR + TVS·ESD용 VRWM·VBR·VC·IPP·PPPM·VESD)의 값을 SI 단위로 뽑는다. 값 하나는 원문 칸 하나에서 나오고
  청크 번호(doc + idx)를 같이 적는다. 모호한 값은 표에 넣지 않고 review.jsonl에 사유와 청크 번호를 남긴다:
  계열 범위·여러 값(range_unsplittable), 같은 자리·같은 조건의 다른 값(conflict), 모르는 단위(unknown_unit),
  원문 청크에 없는 숫자(value_not_in_source), 음수·무한(implausible), 파서가 머리를 밀거나 행을 합친 표(garbled_table),
  일부 품번 전용인데 대상 품번을 알 수 없는 행(scope_unclear), 최소·대표·최대 표시가 없는 항복·제너 전압(slot_unclear).
  문서마다 표 단서(주문표의 품번별 패키지, 'Package' 행의 열별 패키지, 첫 행에 붙은 Min·Nom·Max)를 먼저 모으고,
  이어지는 행(이름 없이 TYP·MAX만), 세로로 합친 품번·조건 칸은 같은 파라미터 행 묶음 안에서 채운다(11-05 PDF 대조 뒤).
  문서가 'Electrical characteristics apply in both directions'라고 밝힐 때만 양방향(C·CA) 품번에 단방향 행 값을 붙인다.
  2차 대조 뒤: IF_AV는 평균·연속 전류만(첨두·서지·반복·IFRM·IF,MAX 행은 IFSM이거나 제외), 머리 끝 숫자는 첫 행이 빨려 든 것이라
  떼고 읽음, 조건 주기로 품번 묶음 구간을 정함, 병합 칸 값은 가운데 열에서 대칭으로 펼침, 붙은 열 이름 칸을 나눔.
  `sample`은 13개 분류에서 품번 50개를 골라 사람이 PDF와 대조할 한국어 대조표(markdown)를 쓴다.
  `load`는 build 결과(part_specifications.jsonl·packages.jsonl)를 DB `part_specifications`(db/011)에 문서 단위로 바꿔 넣는다:
  한 트랜잭션 안에서 대상 문서의 행을 지우고 새 행을 넣어, 다시 돌려도 같고 새·고친 데이터시트 하나만(`--docs`) 다시 넣을 수 있다(ADR 0007).
- 하지 않는 일: LLM·임베딩 호출, 값 비교·판정(`backend/judge/`), 파서가 밀어 놓은 표 바로잡기, 평가셋 정답 읽기.
  결과는 데이터시트에서 나온 값이라 저장소 밖(`SojaFit/corpus/tsc/specs/`)에 쓴다. review.jsonl(뺀 값)은 DB에 넣지 않는다.
  [주의] `load`는 DATABASE_URL을 읽지 않는다. 운영 DB에 실수로 쓰지 않도록 접속 주소를 `--dsn`으로만 받는다.
- 출처: db/schema/table-definition.md 5.7 `part_specifications`, SPEC.md 3절(단위 환산은 `backend/rag/units.py`),
  원형 `전자_데이터시트/evidence/spec_table/build.py`와 README의 대조 오류 수정(11-03), 50개 품번 PDF 대조(11-05, ADR 0013)

실행(저장소 루트):
  uv run python -m backend.rag.pipeline.specs build <chunks.jsonl> <out_dir>
  uv run python -m backend.rag.pipeline.specs sample <out_dir> <sheet.md> --n 50 --seed 0
  uv run python -m backend.rag.pipeline.specs load <out_dir> --dsn <postgres 주소> [--docs <PDF 파일 이름> ...]
"""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
import re
import time

from backend.rag.retrieve import COVER
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
# 출처 우선순위: 품번 열·품번 한 줄(part) > 품번 묶음이 적힌 행의 값 칸(group) > 문서 전체에 붙는 값 칸(value) > KEY PARAMETERS(key, 계열 요약)
# [왜] 파서가 둘째 묶음 행의 품번 칸을 잃으면(HERF1001G SERIES 21·22행) 그 행이 모든 품번에 붙는다. 품번을 적은 행이 이긴다
LEVELS = ('part', 'group', 'value', 'key')
# [주의] 글자로만 된 패키지 이름(SMA · ABS 등)은 대소문자를 구분한다((?-i:...)). 'Case: SOD-123 small outline'의 small이 SMA로 잡혔다(11-05, 59건)
# [주의] 'Thin SMA'(38문서) · 'Micro SMA'(23) · 'Sub SMA'(20)는 SMA와 다른 패키지다. 앞말을 같이 잡아야 SMA 조건 · 기판 비교에 걸리지 않는다(11-06 v3-14)
PKG = re.compile(r'\b(SOD-?\d+\w*|SOT-?\d+\w*|(?-i:(?:Thin|Micro|Sub) SM[ABCFP]\w*|SMA\w*|SMB\w*|SMC\w*|SMF\w*|SMP\w*)|DO-?\d+\w*|TO-?\d+\w*|MiniMELF|MicroMELF|(?-i:MMELF)|'
                 r'MELF|D2PAK|DPAK|DFN\w*|R-?\d\b|(?-i:GBU\w*|KBP\w*|KBJ\w*|GBJ\w*|ABS\w*|MBS\w*|MBF\w*)|TS\w*FL|SC-\d+\w*|'
                 r'PDI\w*|SOP-?\d+)', re.I)
# 대조표에서 분류별로 보여 줄 핵심 코드. 'VRRM|VR'은 VRRM이 없으면 VR을 본다
KEY_CODES = {'zener-diode': ['VZ', 'PD'], 'tvs': ['VRWM', 'VBR', 'VC', 'IPP', 'PPPM'],
             'esd-protection': ['VRWM', 'VBR', 'VC', 'CJ', 'VESD']}
RECTIFIER_KEYS = ['VRRM|VR', 'IF_AV', 'IFSM', 'VF']
REASONS_KO = {'range_unsplittable': '계열 범위·여러 값이라 품번별로 나눌 수 없음', 'conflict': '같은 자리·같은 조건에 값이 둘 이상',
              'unknown_unit': '단위를 알 수 없음', 'value_not_in_source': '숫자가 원문 청크에 없음',
              'implausible': '음수·무한 등 있을 수 없는 값', 'garbled_table': '파서가 표 머리를 밀거나 행을 합친 것으로 보임',
              'scope_unclear': '일부 품번 전용 행인데 대상 품번을 알 수 없음',
              'slot_unclear': '최소·대표·최대 중 어느 칸인지 표시가 없음'}
SLOT_KO = {'minimum_value': '최소', 'typical_value': '대표', 'maximum_value': '최대'}
# 11-05 PDF 대조 뒤 더한 규칙의 글 모양들
BOTH_NOTE = 'Electrical characteristics apply in both directions'
BOTH_DIRECTIONS = re.compile(r'characteristics apply in both directions', re.I)  # TVS 문서 17건의 1쪽 주석(실측)
# 시험 조건 한 토막: 'IF = 7.5A', 'TJ = 125°C', 'VR = 4.0V'. 'TA'(표 전체 기본 온도)는 cond_sets에서 뺀다
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


def cond_sets(text):
    """글 → 조건 묶음 목록. 같은 기호가 다시 나오면 새 묶음이다('IF = 10A, TJ = 25°C IF = 5A, TJ = 125°C' → 2개)."""
    sets, cur = [], {}
    for m in ATOM.finditer(text):
        if m.group(1) == 'TA':
            continue
        if m.group(1) in cur:
            sets.append(cur)
            cur = {}
        cur[m.group(1)] = f'{m.group(1)} = {m.group(2)}{m.group(3) or ""}'
    if cur:
        sets.append(cur)
    out = []
    for x in sets:
        if list(x.values()) not in out:
            out.append(list(x.values()))
    return out


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
    """문서 하나: 표 단위 단서를 먼저 모으고(learn), 행을 읽고(describe), 행 묶음 규칙을 적용한 뒤(run) 후보를 낸다(emit_row)."""

    def __init__(self, doc, parts, fam):
        self.doc, self.parts, self.family = doc, parts, fam
        self.upper = {norm_part(p): p for p in parts}
        self.cands, self.review = [], []
        self.checked = Counter()
        self.part_pkg = defaultdict(set)  # 품번 → 패키지 열쇠(주문표 PACKAGE 칸). TS4148 RBG → {'0805'}
        self.col_pkg = {}  # (쪽, 표) → {열 머리: [패키지 열쇠, ...]}: 'Package' 행이 열마다 패키지를 적은 표
        self.slot_hint = {}  # ((쪽, 표), 칸 순서, 열 머리) → 'Min'·'Nom'·'Max': 첫 데이터 행에 붙어 들어온 머리 행
        self.split_head = {}  # ((쪽, 표), 잘린 열 머리) → (코드, 기호, 원래 머리): 앞 행에서 'AND / V / Nom'이 이어받은 코드
        self.part_cols = {}  # (쪽, 표) → 품번 열 머리 목록(순서대로). 품번 열이 가장 많은 행에서 배운다
        self.pkg_universe = set()

    def run(self, chunks):
        rows = [c for c in chunks if c['kind'] == 'table_row']
        self.learn(rows)
        infos = [i for i in (self.describe(c) for c in rows) if i]
        self.continue_rows(infos)
        for run in self.runs(infos):
            self.spread_groups(run)
            self.spread_conditions(run)
        for info in infos:
            self.emit_row(info)
        if any(c['kind'] in ('text', 'note') and BOTH_DIRECTIONS.search(c['text']) for c in chunks):  # v3는 표 주석을 note로 둔다
            self.copy_bidirectional()

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

    def learn(self, rows):
        """표 단위 단서: 주문표의 품번별 패키지, 'Package' 행의 열별 패키지, 첫 데이터 행에 붙어 들어온 Min·Nom·Max."""
        for c in rows:
            F = fields(c['text'])
            key = (c['page'], c['table'])
            pkg = [v for _, col, v in F if col.strip().upper() == 'PACKAGE']
            if pkg:  # ORDERING INFORMATION: 'TS4148 RBG | PACKAGE: 0805 (Ceramics)'
                for p in self.row_parts(c['row'], F)[0]:
                    self.part_pkg[p] |= pkg_keys(pkg[0])
            if any(KEY_COL.search(col.upper()) and v.strip().lower() == 'package' for _, col, v in F):
                heads = defaultdict(list)
                for h, col, v in F:
                    C = col.upper().rstrip('.')
                    if not KEY_COL.search(C) and not VALUE_COL.search(C) and pkg_keys(v):
                        heads[h].append(pkg_keys(v))
                if sum(map(len, heads.values())) > 1:
                    self.col_pkg[key] = dict(heads)
            for pos, (h, _, v) in enumerate(F):
                m = GLUED_SLOT.fullmatch(v) or re.fullmatch(r'(min|typ|nom|max)\.?', v.strip(), re.I)
                if m and parse_cell(v)[0] is None:  # 'SPECIFICATIONS Min 2.35'(첫 행에 붙음) 또는 'Min'(따로 된 머리 행, BZW06)
                    self.slot_hint[(key, pos, h)] = m.group(1)
            pc = [h for h, _, _ in F if self.col_parts(h)]
            if len(pc) > len(self.part_cols.get(key, [])):
                self.part_cols[key] = pc  # 이 표의 품번 열 전체(병합 칸 펼치기에 씀)
        self.pkg_universe = set().union(*self.part_pkg.values()) if self.part_pkg else set()

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

    def continue_rows(self, infos):
        """이름 없는 이어지는 행(TYP·MAX·품번 칸만)은 바로 위 파라미터 행의 이름·코드·조건을 이어받는다.
        첫 행에 품번 묶음이 있는데 이어지는 행에 묶음이 없으면, 묶음 여럿이 첫 행 한 칸에 합쳐진 것이라 모두 검토로 보낸다."""
        head, run, prev = None, [], None

        def close():
            if head and head['group'] and any(not r['group'] for r in run[1:]):
                for r in run:
                    r['garbled'] = '품번 묶음 여럿이 첫 행 한 칸에 합쳐져 값과 짝을 지을 수 없음'
        for info in infos:
            c = info['c']
            numeric = any(VALUE_COL.search(col.upper().rstrip('.')) and parse_cell(v)[0] for _, col, v in info['F'])
            if (info['code'] is None and info['bare'] and numeric and head and run[-1] is prev
                    and (c['page'], c['table']) == (head['c']['page'], head['c']['table'])):
                own = [x for x in info['conds'][1:] if x]
                # 자기 조건 칸이 있으면 그것을, 없으면 위 행의 조건(세로로 합친 조건 칸)을 쓴다
                conds = head['conds'][:1] + own if any(ATOM.search(x) for x in own) else head['conds'] + own
                info.update(code=head['code'], tok=head['tok'], symbol=head['symbol'], params=head['params'], conds=conds,
                            scan=info['scan'] + [x for x in head['conds'] if ATOM.search(x)])  # 묶음 조건 찾기에도 쓴다
                run.append(info)
            else:
                close()
                head, run = (info, [info]) if info['code'] else (None, [])
            prev = info
        close()

    @staticmethod
    def runs(infos):
        """같은 쪽·표·코드·파라미터 이름이 이어지는 행 묶음."""
        out = []
        for info in infos:
            k = (info['c']['page'], info['c']['table'], info['code'], info['params'][0])
            if info['code'] and out and out[-1][0] == k:
                out[-1][1].append(info)
            elif info['code']:
                out.append((k, [info]))
        return [rows for _, rows in out]

    @staticmethod
    def spread_groups(run):
        """세로로 합친 품번 칸.
        1) 행마다 조건이 p행 주기로 되풀이되면 p행이 한 묶음이다. 그 구간에 적힌 품번을 모두 합쳐 구간 모든 행에 붙인다
           (TUAU6D: 조건 4개 × 묶음 3개인데 가운데 묶음 이름 'TUAU6G'·'TUAU6J'가 두 행에 나뉨).
        2) 주기가 없으면: 행 n개에 품번 묶음 k개가 한 번씩, 크기 n/k 구간마다 하나씩 있으면 그 구간 행에 그 묶음을 붙인다
           (BAT42W: 'IF = 10mA'·'BAT42W IF = 50mA'·'IF = 200mA'가 BAT42W 행 셋)"""
        if all(r['group'] for r in run) or not any(r['group'] for r in run):
            return
        n = len(run)
        keys = [tuple(map(tuple, cond_sets(' '.join(r['conds'])))) for r in run]
        period = next((p for p in range(2, n // 2 + 1) if n % p == 0 and all(keys) and len(set(keys[:p])) == p
                       and all(keys[i] == keys[i % p] for i in range(n))), None)
        if period:
            segs = [run[i:i + period] for i in range(0, n, period)]
            unions = [list(dict.fromkeys(x for r in seg for x in r['group'])) for seg in segs]
            if all(unions) and len({x for u in unions for x in u}) == sum(map(len, unions)):
                for seg, u in zip(segs, unions):
                    for r in seg:
                        r['group'] = list(u)
            return  # [주의] 주기가 있는데 구간이 맞지 않으면 짐작하지 않는다
        grouped = [i for i, r in enumerate(run) if r['group']]
        keys = [tuple(run[i]['group']) for i in grouped]
        k = len(keys)
        if k < 2 or len(set(keys)) != k or len(run) % k or len(grouped) == len(run):
            return
        size = len(run) // k
        if [i // size for i in grouped] != list(range(k)):
            return
        for i, r in enumerate(run):
            if not r['group']:
                r['group'] = list(run[grouped[i // size]]['group'])

    @staticmethod
    def spread_conditions(run):
        """세로로 합친 조건 칸: 같은 품번 묶음이 되풀이되면 되풀이마다 조건 묶음 하나다. 묶음 안 어느 행에서든 찾은 조건을
        그 묶음 모든 행에 붙인다. 한 칸에 조건 k개가 있고 그 칸이 이어진 묶음 k개에 똑같이 나오면 순서대로 나눈다(MBRS1035CT)."""
        if any(r['group'] for r in run):
            blocks, seen = [[]], set()
            for r in run:
                g = frozenset(r['group'])
                if g and g in seen:
                    blocks.append([])
                    seen = set()
                blocks[-1].append(r)
                if g:
                    seen.add(g)
        else:
            blocks = [[r] for r in run]  # 품번 묶음이 없는 표: 한 행이 한 묶음
        sets = [cond_sets(' '.join(x for r in b for x in r['scan'])) for b in blocks]
        own = lambda r: cond_sets(' '.join(x for x in r['conds'] if ATOM.search(x)))  # noqa: E731
        if len(blocks) == 1:
            # 묶음이 하나: 조건이 한 가지뿐이고 두 행 이상에 적혀 있으면 조건 칸이 빠진 행도 그 조건이다(SK35BH)
            if len(sets[0]) == 1 and sum(own(r) == sets[0] for r in run) >= 2:
                for r in run:
                    if not own(r):
                        r['conds'] = r['conds'] + [', '.join(sets[0][0])]
            return
        chosen = [s[0] if len(s) == 1 else None for s in sets]
        for i, s in enumerate(sets):
            # 한 칸에 조건 k개: 뒤 k-1개 묶음이 같은 칸이거나 조건이 비어 있으면 순서대로 나눈다(MBRS1035CT, MBRF1635)
            k = len(s)
            if k > 1 and i + k <= len(blocks) and all(sets[j] in (s, []) for j in range(i + 1, i + k)):
                chosen[i:i + k] = s
        for b, s in zip(blocks, chosen):
            for r in b if s else []:
                if own(r) != [s]:  # 자기 조건이 이미 이 조건 하나면 원문 글 그대로 둔다
                    r['conds'] = [x for x in r['conds'] if not ATOM.search(x)] + [', '.join(s)]

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

    def copy_bidirectional(self):
        """문서가 '특성은 양방향 모두 적용'이라고 적었을 때만, 자기 행이 없는 양방향 품번(…C·…CA·…CH·…CAH)에
        단방향 품번(C를 뺀 이름) 행의 값을 붙인다. 출처 청크·행 이름은 단방향 행 그대로 두고 각주에 그 문장을 적는다."""
        own = defaultdict(set)
        for r in self.cands:
            if r['source_level'] == 'part':
                own[r['part']].add(r['parameter_code'])
        names = set(self.parts)
        new = []
        for p in self.parts:
            u = re.sub(r'C(A?H?)$', r'\1', p)
            if u == p or u not in names:
                continue
            new += [{**r, 'part': p, 'footnote_text': BOTH_NOTE} for r in self.cands
                    if r['part'] == u and r['source_level'] == 'part' and r['parameter_code'] not in own[p]]
        self.cands += new

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


def resolve(cands):
    """출처 우선순위로 거르고, 같은 품번·코드·자리·조건에 값이 갈리면 모두 빼서 conflict 검토로 보낸다."""
    best = {}
    for r in cands:
        k = (r['part'], r['doc'], r['parameter_code'])
        best[k] = min(best.get(k, 9), LEVELS.index(r['source_level']))
    kept = [r for r in cands if LEVELS.index(r['source_level']) == best[(r['part'], r['doc'], r['parameter_code'])]]
    dropped = len(cands) - len(kept)
    groups = defaultdict(list)
    for r in kept:
        slots = tuple(s for s in SLOT_KO if r[s] is not None)
        groups[(r['part'], r['doc'], r['parameter_code'], slots, r['test_condition'])].append(r)
    rows, review = [], []
    for (part, doc, code, slots, cond), rs in groups.items():
        values = {tuple(f'{r[s]:.6g}' for s in slots) for r in rs}  # [왜] 150 mA와 0.15 A는 같은 값이다
        if len(values) == 1:
            rows.append(rs[0])  # 같은 값이 여러 청크에 있으면 첫 청크 하나만 남긴다
            continue
        r = rs[0]
        review.append({'reason': 'conflict', 'parts': [part], 'doc': doc, 'family': r['family'], 'parameter_code': code,
                       'source_value_text': ' ≠ '.join(dict.fromkeys(x['source_value_text'] for x in rs)),
                       'test_condition': cond, 'page_number': r['page_number'], 'table_name': r['table_name'],
                       'row_label': r['row_label'], 'chunks': [x['chunk'] for x in rs],
                       'detail': f'자리 {"·".join(SLOT_KO[s] for s in slots)}, 출처 {r["source_level"]}'})
    return rows, review, dropped


AEC_H = re.compile(r'"H"\s*means\s*AEC[- ]?Q101\s+qualified', re.I)  # 주문 정보 주석: H로 끝나는 품번만 인증품
AEC_ALL = re.compile(r'AEC[- ]?Q101\s+qualified(?!\s+available)', re.I)    # FEATURES: 그 문서 품번 전체가 인증품


def aec_of(chunks, part):
    """품번의 AEC-Q101 근거 청크 {'idx', 'page', 'text'} 또는 None. 문서가 밝힌 문장만 본다(값 추정 없음).

    '"H" means AEC-Q101 qualified' 주석이 있으면 H로 끝나는 품번만, 없으면 FEATURES의 'AEC-Q101 qualified'(뒤에 available 없음)로 문서 전체를 본다.
    [주의] 'AEC-Q101 qualified available' · 'AEC-Q101 available' · 'Qualification reference AEC-Q101'은 인증품이라는 문장이 아니라 쓰지 않는다
    """
    note = next((c for c in chunks if c['kind'] in ('note', 'text', 'table_row') and AEC_H.search(c['text'])), None)
    if note is not None:
        return {'idx': note['idx'], 'page': note['page'], 'text': 'AEC-Q101 qualified ("H")'} if part.upper().endswith('H') else None
    feat = next((c for c in chunks if c['kind'] == 'text' and '· FEATURES]' in c['text'] and AEC_ALL.search(c['text'])), None)
    return {'idx': feat['idx'], 'page': feat['page'], 'text': 'AEC-Q101 qualified'} if feat is not None else None


def h_copies(rows, docs, by_doc):
    """주문 정보 틀로만 적힌 H 품번(표지 품번 목록의 'XH', 표에는 X만)에 기본 품번 X의 행을 그대로 붙인다(인용도 X의 행 그대로).

    [왜] 문서가 '"H" means AEC-Q101 qualified'라고만 밝히고 값 표는 기본 품번으로 적는다. H 품번 행이 없으면 1N5819H가 '사양 표에 값 없음'이었다
         (11-06 판정 dev 14). AEC-Q101 행은 aec_of가 H로 끝나는 품번에 따로 단다
    """
    out = []
    for name, d in docs.items():
        if not any(AEC_H.search(c['text']) for c in by_doc[name]):
            continue
        mine = defaultdict(list)
        for r in rows:
            if r['doc'] == name:
                mine[r['part'].upper()].append(r)
        for p in d.parts:
            P = p.upper()
            if P.endswith('H') and P[:-1] in mine:
                # [주의] 문서 전체에 붙는 값(KEY PARAMETERS의 IF_AV 등)은 H 품번에도 이미 붙는다. 품번별 행(key 밖)이 있는 코드만 두고 나머지는 붙인다.
                #        key 행만 있는 코드를 두면 시험 조건이 없어 원래 품번 행과 짝이 안 맞아 사양 동등을 못 냈다(11-06 판정 dev 14 IFSM)
                have = {r['parameter_code'] for r in mine.get(P, []) if r.get('source_level') != 'key'}
                out += [{**r, 'part': p} for r in mine[P[:-1]] if r['parameter_code'] not in have]
    return out


def build(chunks):
    """청크 목록 → {'rows', 'review', 'packages', 'stats'}. 표지 청크가 없는 문서는 품번을 몰라 건너뛴다."""
    docs, by_doc = {}, defaultdict(list)
    for c in chunks:
        m = c['kind'] == 'cover' and COVER.match(c['text'])
        if m:
            docs[c['doc']] = Doc(c['doc'], [p.strip() for p in m.group(1).split(', ') if p.strip()], family(c['category']))
        by_doc[c['doc']].append(c)
    pkgs = defaultdict(list)
    for name, d in docs.items():
        pkgs[name] = [(x, c) for c in by_doc[name] if c['kind'] in ('text', 'table_row') for x in packages_of(c)]
        d.run(by_doc[name])
    cands = [r for d in docs.values() for r in d.cands]
    rows, conflicts, dropped = resolve(cands)
    rows += h_copies(rows, docs, by_doc)
    review = [r for d in docs.values() for r in d.review] + conflicts
    checked = sum((d.checked for d in docs.values()), Counter())
    # [주의] 패키지는 문서 단위다(원형과 같음). 한 문서에 패키지가 여럿이면 품번별로 나누지 못해 모든 품번에 같은 목록이 붙는다
    where = {}  # (문서, 패키지 이름) → 그 이름이 처음 나온 청크의 {idx, page}. [왜] 판정 답이 패키지 근거의 쪽을 인용해야 한다(11-06 손실)
    for doc_name, found in pkgs.items():
        for x, c in found:
            where.setdefault((doc_name, x), {'idx': c['idx'], 'page': c['page']})
    packages = [{'part': p, 'doc': d.doc, 'family': d.family, 'packages': list(dict.fromkeys(x for x, _ in pkgs[d.doc])),
                 'where': {x: where[(d.doc, x)] for x, _ in pkgs[d.doc]}, 'aec': aec_of(by_doc[d.doc], p)}
                for d in docs.values() for p in d.parts]
    return {'rows': rows, 'review': review, 'packages': packages,
            'stats': {'candidates_checked': checked['candidates'], 'value_not_in_source': checked['value_in_source'],
                      'implausible': checked['plausible'], 'dropped_lower_precedence': dropped}}


def has_code(codes, key):
    return any(k in codes for k in key.split('|'))


def summarize(out):
    """분류 × 코드 채움률(값이 하나라도 있는 품번 / 품번), 검토 사유별 수, 자동 검사 수."""
    have = defaultdict(set)
    for r in out['rows']:
        have[(r['part'], r['doc'])].add(r['parameter_code'])
    fams = defaultdict(list)
    for p in out['packages']:
        fams[p['family']].append(have[(p['part'], p['doc'])])
    coverage, key_complete = {}, {}
    for fam, sets in sorted(fams.items()):
        coverage[fam] = {code: {'parts_with_value': sum(code in s for s in sets), 'parts': len(sets)} for code in SI}
        keys = KEY_CODES.get(fam, RECTIFIER_KEYS)
        key_complete[fam] = {'keys': keys, 'parts_with_every_key': sum(all(has_code(s, k) for k in keys) for s in sets),
                             'parts': len(sets)}
    return {'totals': {'docs': len({p['doc'] for p in out['packages']}), 'parts': len(out['packages']),
                       'rows': len(out['rows']), 'rows_by_code': dict(Counter(r['parameter_code'] for r in out['rows']).most_common())},
            'review_by_reason': dict(Counter(r['reason'] for r in out['review']).most_common()),
            'auto_checks': out['stats'], 'key_complete': key_complete, 'coverage': coverage}


def write_jsonl(path, items):
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(json.dumps(x, ensure_ascii=False) + '\n' for x in items)


def read_jsonl(path):
    with open(path, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def cmd_build(chunks_path, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = build(read_jsonl(chunks_path))
    write_jsonl(out_dir / 'part_specifications.jsonl', out['rows'])
    write_jsonl(out_dir / 'review.jsonl', out['review'])
    write_jsonl(out_dir / 'packages.jsonl', out['packages'])
    summary = summarize(out)
    (out_dir / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('totals', 'review_by_reason', 'auto_checks')}, ensure_ascii=False))


def allocate(counts, n=50, floor=3, cap=5):
    """분류별 표본 수: 모두 floor개씩 준 뒤 남은 수를 품번 수 비례 몫이 가장 모자란 분류부터 1개씩(cap까지)."""
    fams = sorted(counts)
    alloc = {f: min(floor, counts[f]) for f in fams}
    total = sum(counts.values())
    while sum(alloc.values()) < n:
        open_ = [f for f in fams if alloc[f] < min(cap, counts[f])]
        if not open_:
            break
        f = max(open_, key=lambda f: n * counts[f] / total - alloc[f])  # 같으면 이름순 앞(max는 첫 최댓값을 고른다)
        alloc[f] += 1
    return alloc


def cell(s):
    return str(s if s not in (None, '') else '-').replace('|', '\\|').replace('\n', ' ')


def fmt(v, unit):
    return f'{v:.6g} {unit}'


def cmd_sample(out_dir, sheet, n=50, seed=0):
    """대조표: 분류마다 3~5개 품번을 고정 seed로 뽑아 핵심 값과 출처, 빠진 값의 검토 사유를 적는다."""
    out_dir = Path(out_dir)
    rows, review, parts = (read_jsonl(out_dir / f) for f in ('part_specifications.jsonl', 'review.jsonl', 'packages.jsonl'))
    by_fam = defaultdict(list)
    for p in parts:
        by_fam[p['family']].append((p['part'], p['doc']))
    alloc = allocate({f: len(v) for f, v in by_fam.items()}, n)
    rng = random.Random(seed)
    picked = [(fam, part, doc) for fam in sorted(by_fam) for part, doc in rng.sample(sorted(by_fam[fam]), alloc[fam])]
    have = defaultdict(list)
    for r in rows:
        have[(r['part'], r['doc'], r['parameter_code'])].append(r)
    why = defaultdict(list)
    for r in review:
        for p in r['parts']:
            why[(p, r['doc'], r['parameter_code'])].append(r)
    lines = [f'# 부품 사양 표 대조표 ({len(picked)}개 품번, seed {seed})', '',
             '부품 사양 표(part_specifications)에 규칙으로 뽑아 넣은 값이 데이터시트 PDF와 같은지 사람이 확인하는 표입니다.',
             '',
             '확인 방법',
             '1. 품번 제목 아래 PDF 경로(`SojaFit/` 폴더 기준)를 열고, 각 줄의 `쪽`으로 갑니다.',
             '2. `표`·`행` 이름으로 그 칸을 찾아 `원문 표기`(숫자와 단위)와 `시험 조건`이 PDF와 같은지 봅니다. '
             '`표에 넣은 값`은 SI 기본 단위(V, A, W, s, F, °C)로 바꾼 값입니다(예: 150 mA → 0.15 A).',
             '3. 같으면 `O/X` 칸에 O, 다르면 X를 적고 `메모`에 PDF의 실제 값을 적습니다. 판단이 어려우면 `?`와 이유를 적습니다.',
             '4. `빠진 값`은 표에 넣지 않은 핵심 값과 그 이유입니다. PDF에 그 값이 정말 있는지(있으면 놓친 것) 보고 메모합니다.',
             '', '자리: 최소·대표·최대는 데이터시트의 Min·Typ(Nom)·Max 칸입니다. 표시가 없는 정격 칸은 최대로, 정전용량은 대표로 넣었고, '
             '항복·제너 전압은 표시가 없으면 넣지 않았습니다.',
             'TVS의 C·CA(양방향) 품번은 데이터시트 표에 자기 행이 없는 경우가 많아 값이 비어 있습니다'
             '(단방향 행의 값을 옮겨 적지 않았습니다).', '']
    complete = 0
    for i, (fam, part, doc) in enumerate(picked, 1):
        keys = KEY_CODES.get(fam, RECTIFIER_KEYS)
        lines += [f'## {i}. {part} ({fam})', '', f'- 문서: `{doc}` · PDF: `corpus/tsc/pdf/{doc}`', '',
                  '| 코드 | 자리 | 표에 넣은 값 | 원문 표기 | 시험 조건 | 쪽 | 표 | 행 | O/X | 메모 |',
                  '|---|---|---|---|---|---|---|---|---|---|']
        missing = []
        for key in keys:
            code = next((c for c in key.split('|') if have[(part, doc, c)]), None)
            if code is None:
                missing.append(key)
                continue
            for r in have[(part, doc, code)]:
                slots = [s for s in SLOT_KO if r[s] is not None]
                lines.append('| ' + ' | '.join(cell(x) for x in [
                    code, '·'.join(SLOT_KO[s] for s in slots), ' / '.join(fmt(r[s], r['normalized_unit']) for s in slots),
                    r['source_value_text'], r['test_condition'], r['page_number'], r['table_name'], r['row_label']])
                    + ' |  |  |')  # O/X·메모는 사람이 채우는 빈칸
        complete += not missing
        lines.append('')
        for key in missing:
            # [왜] KEY PARAMETERS의 계열 범위(range_unsplittable)는 거의 모든 품번에 걸려 있어, 더 구체적인 사유를 먼저 보여 준다
            rs = sorted((r for c in key.split('|') for r in why[(part, doc, c)]),
                        key=lambda r: r['reason'] == 'range_unsplittable')
            if rs:
                ex = rs[0]
                lines.append(f'- 빠진 값 {key}: {REASONS_KO[ex["reason"]]} ({ex["reason"]}, {ex["page_number"]}쪽 '
                             f'`{cell(ex["table_name"])}` 행 `{cell(ex["row_label"])}`, 원문 `{cell(ex["source_value_text"])}`)'
                             + (f' 외 검토 {len(rs) - 1}건' if len(rs) > 1 else ''))
            else:
                lines.append(f'- 빠진 값 {key}: 검토 목록에도 없음(표에서 그 값을 찾지 못함)')
        if missing:
            lines.append('')
    lines.insert(2, f'핵심 값이 모두 있는 품번: {complete}/{len(picked)}개. 분류별 표본 수: '
                 + ', '.join(f'{f} {k}' for f, k in sorted(alloc.items())) + '.')
    lines.insert(3, '')
    Path(sheet).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'대조표 {sheet}: 품번 {len(picked)}개, 핵심 값 모두 있음 {complete}개')


# DB part_specifications에 넣는 열 순서(db/011). id·created_at은 DB가 채운다
LOAD_COLS = ('document_id', 'part_number', 'chunk_index', 'category', 'parameter_code', 'symbol', 'minimum_value',
             'typical_value', 'maximum_value', 'text_value', 'source_value_text', 'source_unit', 'normalized_unit',
             'test_condition', 'page_number', 'table_name', 'row_label', 'footnote_text')


def num(v):
    """SI 값(float)을 NUMERIC 글자로. 유효숫자 15자리로 적는다."""
    # [왜] 환산한 float에는 이진 꼬리가 붙는다(200 µA → 0.00019999999999999998). 그대로 넣으면 '0.0002 이상' 조건에서 빠진다.
    # 15자리는 float가 정확히 담는 자릿수이고 Postgres가 float8을 NUMERIC으로 바꿀 때도 15자리다. 데이터시트 값은 4자리 안팎이라 잃는 값이 없다
    return None if v is None else format(v, '.15g')


def load(specs_dir, dsn, docs=None):
    """사양 표 폴더를 DB part_specifications에 문서 단위로 바꿔 넣는다. 반환: 바꾼 문서 수, DB에 없는 문서, 코드별 넣은 행 수."""
    import psycopg
    from backend.rag.pipeline.chunk import doc_key  # 'SS32 SERIES_Q2412.pdf' → source_documents.document_key
    specs_dir = Path(specs_dir)
    by_doc = defaultdict(list)  # PDF 파일 이름 → document_id를 뺀 행(LOAD_COLS[1:] 순서) 목록
    for r in read_jsonl(specs_dir / 'part_specifications.jsonl'):
        by_doc[r['doc']].append((r['part'], r['chunk']['idx'], r['family'], r['parameter_code'], r['symbol'],
                                 num(r['minimum_value']), num(r['typical_value']), num(r['maximum_value']), r['text_value'],
                                 r['source_value_text'], r['source_unit'], r['normalized_unit'], r['test_condition'],
                                 r['page_number'], r['table_name'], r['row_label'], r['footnote_text']))
    for p in read_jsonl(specs_dir / 'packages.jsonl'):
        # [왜] 패키지는 숫자가 아니라 PACKAGE 코드 행의 text_value에 둔다. 문서 단위 목록이라 표는 없고, 이름이 처음 나온 청크 · 쪽을 단다
        # [주의] 'where'가 없는 옛 packages.jsonl이면 청크 · 쪽 없이 넣는다
        for name in p['packages']:
            at = (p.get('where') or {}).get(name) or {}
            by_doc[p['doc']].append((p['part'], at.get('idx'), p['family'], 'PACKAGE', None, None, None, None, name, name,
                                     None, None, None, at.get('page'), None, None, None))
        if p.get('aec'):  # [왜] 찾기 · 판정이 'AEC-Q101 적합' 요구를 근거 쪽과 함께 확인하게 문서가 밝힌 문장을 행으로 둔다(11-06 v3-14)
            a = p['aec']
            by_doc[p['doc']].append((p['part'], a['idx'], p['family'], 'AEC_Q101', None, None, None, None, a['text'], a['text'],
                                     None, None, None, a['page'], None, None, None))
    targets = list(docs) if docs else sorted(by_doc)
    start = time.monotonic()
    with psycopg.connect(dsn) as conn:  # with: 오류 없이 끝나면 커밋, 예외면 롤백한다(지우기와 넣기가 한 트랜잭션)
        doc_id = dict(conn.execute('SELECT document_key, id FROM source_documents').fetchall())
        found = {d: doc_id[doc_key(d)] for d in targets if doc_key(d) in doc_id}
        missing = [d for d in targets if d not in found]  # [주의] DB에 문서가 없으면 FK를 못 걸어 건너뛴다(먼저 ingest로 문서를 넣는다)
        conn.execute('DELETE FROM part_specifications WHERE document_id = ANY(%s)', (list(found.values()),))
        counts = Counter()
        with conn.cursor().copy(f'COPY part_specifications ({", ".join(LOAD_COLS)}) FROM STDIN') as cp:
            for d, i in found.items():
                for row in by_doc.get(d, []):  # 파일에 행이 없는 문서는 지우기만 한다(새 판에서 값이 다 빠진 경우)
                    cp.write_row((i,) + row)
                    counts[row[3]] += 1
        total = conn.execute('SELECT count(*) FROM part_specifications').fetchone()[0]
    out = {'docs': len(found), 'missing_docs': missing, 'rows_by_code': dict(counts.most_common())}
    print(json.dumps({**out, 'missing_docs': len(missing), 'rows': sum(counts.values()), 'table_rows': total,
                      'seconds': round(time.monotonic() - start, 2)}, ensure_ascii=False))
    if missing:
        print('DB에 없는 문서(건너뜀):', ', '.join(missing[:20]) + (f' 외 {len(missing) - 20}건' if len(missing) > 20 else ''))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='부품 사양 표 만들기·대조표 표본')
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build', help='chunks.jsonl → part_specifications·review·packages·summary')
    b.add_argument('chunks')
    b.add_argument('out_dir')
    s = sub.add_parser('sample', help='사람 대조표(markdown) 쓰기')
    s.add_argument('out_dir')
    s.add_argument('sheet')
    s.add_argument('--n', type=int, default=50)
    s.add_argument('--seed', type=int, default=0)
    d = sub.add_parser('load', help='사양 표 폴더 → DB part_specifications(문서 단위로 바꿔 넣기)')
    d.add_argument('out_dir')
    d.add_argument('--dsn', required=True, help='Postgres 접속 주소. DATABASE_URL은 읽지 않는다')
    d.add_argument('--docs', nargs='+', help='이 PDF 파일 이름의 문서만 다시 넣는다(기본: 폴더의 모든 문서)')
    a = ap.parse_args(argv)
    if a.cmd == 'build':
        cmd_build(a.chunks, a.out_dir)
    elif a.cmd == 'sample':
        cmd_sample(a.out_dir, a.sheet, a.n, a.seed)
    else:
        load(a.out_dir, a.dsn, a.docs)


if __name__ == '__main__':
    main()
