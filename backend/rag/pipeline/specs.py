"""데이터시트 표 행 청크를 부품 사양 표(part_specifications) 행으로 바꾸는 오프라인 도구(서버가 import하지 않는다).

- 역할: chunks.jsonl의 표지 청크(품번 목록)와 표 행 청크("머리 경로: 값")를 읽어 품번마다 파라미터 코드 17종
  (5.7의 10종 + VR + TVS·ESD용 VRWM·VBR·VC·IPP·PPPM·VESD)의 값을 SI 단위로 뽑는다. 값 하나는 원문 칸 하나에서 나오고
  청크 번호(doc + idx)를 같이 적는다. 모호한 값은 표에 넣지 않고 review.jsonl에 사유와 청크 번호를 남긴다:
  계열 범위·여러 값(range_unsplittable), 같은 자리·같은 조건의 다른 값(conflict), 모르는 단위(unknown_unit),
  원문 청크에 없는 숫자(value_not_in_source), 음수·무한(implausible), 파서가 머리를 밀거나 행을 합친 표(garbled_table),
  일부 품번 전용인데 대상 품번을 알 수 없는 행(scope_unclear), 최소·대표·최대 표시가 없는 항복·제너 전압(slot_unclear).
  `sample`은 13개 분류에서 품번 50개를 골라 사람이 PDF와 대조할 한국어 대조표(markdown)를 쓴다.
- 하지 않는 일: LLM·임베딩 호출, DB 적재, 값 비교·판정(`backend/judge/`), 파서가 밀어 놓은 표 바로잡기, 평가셋 정답 읽기.
  결과는 데이터시트에서 나온 값이라 저장소 밖(`SojaFit/corpus/tsc/specs/`)에 쓴다.
- 출처: db/schema/table-definition.md 5.7 `part_specifications`, SPEC.md 3절(단위 환산은 `backend/rag/units.py`),
  원형 `전자_데이터시트/evidence/spec_table/build.py`와 README의 대조 오류 수정(11-03)

실행(저장소 루트):
  uv run python -m backend.rag.pipeline.specs build <chunks.jsonl> <out_dir>
  uv run python -m backend.rag.pipeline.specs sample <out_dir> <sheet.md> --n 50 --seed 0
"""
import argparse
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import random
import re

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
SKIP_SYMS = {'IFRM', 'VRSM', 'VRM', 'TSTG', 'IZT', 'IZK', 'IT', 'IZM', 'IRSM', 'VRMS', 'IRRM', 'QRR'}
# [주의] 실효값(VR(RMS) 등)은 정격 전압이 아니다(원형: 1N4934G에서 VR 70V로 잘못 들어감). 계수·저항·시험 전류 열도 값이 아니다
# ('coeffici'는 파서가 'COEFFICIEN T'로 끊은 온도 계수 열도 막는다. 1K5SMPC12APH에서 VBR 0.070이 나왔다)
EXCLUDE = re.compile(r'\brms\b|coeffici|thermal|test current|marking|impedance|resistance|repetitive peak forward|'
                     r'peak forward current|non-repetitive peak reverse voltage|reverse surge|recovery current|'
                     r'recovered charge|isolation|fusing|\bi2t\b', re.I)
# 기호로 못 정하면 설명 글의 낱말로 정한다. 앞줄이 먼저다(예: '반복 첨두 역전압'을 '작동 첨두 역전압'보다 먼저).
# [주의] IFSM은 'forward'가 붙어야 한다. TVS 표의 'Maximum Peak Surge Current IPP'는 IPP다
KEYWORDS = [(re.compile(p, re.I), c) for p, c in [
    (r'clamping voltage', 'VC'), (r'breakdown voltage', 'VBR'), (r'zener voltage', 'VZ'),
    (r'repetitive peak reverse voltage|peak repetitive reverse voltage|recurrent peak reverse', 'VRRM'),
    (r'stand-?\s*off|reverse working voltage|working peak reverse', 'VRWM'),
    (r'peak (pulse |impulse )?power|pulse power', 'PPPM'), (r'peak (pulse|impulse) current|pulse current', 'IPP'),
    (r'\besd\b|electrostatic', 'VESD'), (r'forward surge|surge forward', 'IFSM'),
    (r'forward voltage', 'VF'), (r'recovery time', 'TRR'),
    (r'reverse (leakage )?current|leakage current|reverse leakage', 'IR'),
    (r'average (rectified )?(forward|output)|forward (rectified |continuous )?current|output current', 'IF_AV'),
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
PKG = re.compile(r'\b(SOD-?\d+\w*|SOT-?\d+\w*|SMA\w*|SMB\w*|SMC\w*|SMF\w*|SMP\w*|DO-?\d+\w*|TO-?\d+\w*|MiniMELF|MicroMELF|'
                 r'MELF|D2PAK|DPAK|DFN\w*|R-?\d\b|GBU\w*|KBP\w*|KBJ\w*|GBJ\w*|ABS\w*|MBS\w*|MBF\w*|TS\w*FL|SC-\d+\w*|'
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


def family(category):
    """'tvs-18' · 'a-14;b-16' → 'tvs' · 'a'(TSC 분류 이름에서 번호를 뗀 것)."""
    return re.sub(r'-\d+$', '', (category or '').split(';')[0])


def norm_part(s):
    """표 열 이름은 'MBR 2035 CT'처럼 띄어 쓰기도 해서 공백을 빼고 대문자로 맞춘다."""
    return re.sub(r'\s+', '', s or '').upper()


def fields(text):
    """청크 본문 → [(머리 경로, 마지막 열 이름, 값)]. chunk.py가 '경로: 값'을 ' | '로 이어 붙인 모양(원형 build.py와 같음)."""
    body = text.split('] ', 1)[1] if '] ' in text else text
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
    # [왜] '@'·'at' 뒤는 시험 조건이다('VF at IF = 100mA'의 IF, 'IR @ VR'의 VR는 잰 값이 아니다)
    main = re.split(r'@|\bat\b|,', text, maxsplit=1, flags=re.I)[0]
    toks = re.findall(r'[A-Za-z][A-Za-z0-9()]*', sym) + re.findall(r'\b[A-Z][A-Za-z0-9()]*', main)
    word = next((c for p, c in KEYWORDS if p.search(main)), None)
    for tok in toks:
        if tok.upper() in SKIP_SYMS:
            return None, None
        if tok.upper() in SYMS:
            code = SYMS[tok.upper()]
            return (None, None) if strict and word and word != code else (code, tok)
    return word, None


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
    body = squash(chunk_text.split('] ', 1)[-1])
    in_src = all(squash(n).lstrip('+') in body for n in num_texts)
    plausible = all(math.isfinite(v) and (v >= 0 or code == 'TJ_MAX') for v in values.values())
    return {'value_in_source': in_src, 'plausible': plausible}


def label_condition(label):
    """설명 글 안의 시험 조건('VF at IF = 100mA' → 'at IF = 100mA', 'ESD per IEC ... (Air)' → 'per IEC ... (Air)')."""
    s = re.sub(r'\((?:note\s*)?\d+\)', '', label or '', flags=re.I).strip()  # 각주 번호 (1)·(Note 2)는 조건이 아니다
    m = re.search(r'@|\bat\b|[A-Za-z][\w()]*\s*=|,|\(|\bper\b|\bfor\b', s, re.I)  # 'IF = 10mA'는 기호부터 조건이다
    return s[m.start():].strip(' ,') if m else ''


def at_condition(head, F):
    """품번 한 줄 표의 'VBR@IT'·'VC at IPPM' 머리에서 같은 행의 IT·IPPM 값 칸을 찾아 'IT = 1 mA'로 만든다.
    머리 안의 온도 조건('IR at VWM TJ =175°C')도 붙인다. 조건이 없으면 None."""
    # [왜] 온도는 마지막 열 이름에서만 찾는다. 표 이름의 '(TA = 25°C unless otherwise noted)'는 표 전체의 기본 조건이다
    temps = [re.sub(r'\s+', ' ', t) for t in re.findall(r'\bT[JA]\s*=\s*[-+]?\d+\s*°?C', head.split(' / ')[-1])]
    m = re.search(r'(?:@|\bat\b)\s*([A-Za-z][A-Za-z0-9()]*)', head)
    if not m:
        return '; '.join(temps) or None
    sym, cond = m.group(1), f'@{m.group(1)}'
    dim = {'V': 'V', 'I': 'A'}.get(sym[0].upper())
    for h, _, v in F:
        u = unit_of(h)
        if h != head and sym in re.findall(r'[A-Za-z][A-Za-z0-9()]*', h) and u and to_si(1.0, u)[1] == dim:
            shape, nums, _ = parse_cell(v)
            if shape == 'one':
                cond = f'{sym} = {nums[0]} {u}'
                break
    return '; '.join([cond] + temps)


class Doc:
    """문서 하나를 읽는 동안 모으는 것: 표에 넣을 후보, 검토 목록, 자동 검사 수."""

    def __init__(self, doc, parts, fam):
        self.doc, self.parts, self.family = doc, parts, fam
        self.upper = {norm_part(p): p for p in parts}
        self.cands, self.review = [], []
        self.checked = Counter()

    def flag(self, reason, parts, base, code, text, detail=''):
        self.review.append({'reason': reason, 'parts': list(parts), 'doc': self.doc, 'family': self.family,
                            'parameter_code': code, 'source_value_text': text, 'test_condition': base['test_condition'],
                            'page_number': base['page_number'], 'table_name': base['table_name'],
                            'row_label': base['row_label'], 'chunks': [base['chunk']], 'detail': detail})

    def emit(self, c, cell, targets, named, slot, code, base, units, level):
        """칸 하나를 후보 행으로 바꾼다. named: 대상 품번이 행·열 머리에 적혀 있는가(계열 범위를 나눌 수 있는 조건)."""
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

    def table_row(self, c):
        """표 행 청크 하나: 품번 한 줄(TVS·제너)이면 per_part, 아니면 파라미터 행(PARAMETER/SYMBOL/VALUE·품번 열)."""
        F = fields(c['text'])
        base = {'doc': self.doc, 'family': self.family, 'symbol': None, 'test_condition': None,
                'page_number': c['page'], 'table_name': c['table'], 'row_label': c['row'], 'text_value': None,
                'footnote_text': None, 'chunk': {'doc': self.doc, 'idx': c['idx']}}
        cols = defaultdict(list)
        for _, col, v in F:
            m = KEY_COL.search(col.upper().rstrip('.'))
            if m:
                cols[m.group(1).rstrip('S')].append(v)
        label = re.sub(r'^PARAMETER\s+', '', c['row'] or '')
        row_parts = self.row_parts(c['row'], F)
        if row_parts and not cols['PARAMETER'] and not cols['SYMBOL']:
            return self.per_part(c, F, row_parts, base)
        # [왜] 'ELECTRICAL SPECIFICATIONS: Forward voltage | PARAMETER: HS2AAH HS2BAH'처럼 파라미터 이름은 행 이름(첫 칸)에,
        # 품번 묶음은 PARAMETER 칸에 들어간 표가 많다. 행 이름을 맨 앞에 두고 나머지 PARAMETER 칸은 품번·조건으로 본다
        params = list(dict.fromkeys(x for x in [label] + cols['PARAMETER'] if x))
        # 행 이름 'Forward voltage'와 PARAMETER 칸 'Forward voltage @ IF = 50A ...'처럼 앞부분이 같으면 긴 쪽 하나만 이름으로 둔다
        params = [x for x in params if not any(y != x and y.lower().startswith(x.lower()) for y in params)]
        if not params:
            return
        code, tok = code_of(params[0], ' '.join(cols['SYMBOL']))
        if not code:
            return
        group, unknown, conds = [], False, [label_condition(params[0])]
        for _, col, v in F:
            C = col.upper().rstrip('.')
            if VALUE_COL.search(C) or self.col_parts(col) or v in (label, params[0]):
                continue
            # [왜] 품번 묶음은 PARAMETER 칸 말고도 CONDITIONS 칸('CONDITIONS: SK52BH')이나 깨진 머리 칸('(TA: SRAS2020 ...')에 들어간다
            toks = re.split(r'[\s/,&()]+', v.upper())
            hits = [self.upper[t] for t in toks if t in self.upper]
            group += [h for h in hits if h not in group]
            kind = KEY_COL.search(C)
            if not hits and kind and kind.group(1) in ('PARAMETER', 'CONDITIONS', 'CONDITION'):
                unknown |= any(PARTLIKE.fullmatch(t) and not re.fullmatch(r'[\d.]+[A-ZΜµ°]+', t) for t in toks)
                conds.append(v)
        base = {**base, 'symbol': ' '.join(cols['SYMBOL']) or tok,
                'test_condition': '; '.join(x for x in conds if x) or None}
        if not group and (unknown or re.search(r'\bonly\b', params[0], re.I)):
            # [주의] '단방향 전용'·'VWM 40V 미만 전용' 행을 모든 품번에 붙이면 틀린다(원형 2차 대조 오류 1건)
            return self.flag('scope_unclear', self.parts, base, code, params[0])
        level = 'key' if (c['table'] or '').upper().startswith('KEY PARAMETERS') else 'group' if group else 'value'
        for head, col, v in F:
            units = cols['UNIT'][:1] or [head]  # [주의] UNIT 칸이 있으면 그것만 본다(모르는 단위면 머리 글로 짐작하지 않는다)
            hits = self.col_parts(col)
            vcol = VALUE_COL.search(col.upper().rstrip('.'))
            if hits:  # 열 이름이 품번(열 하나에 품번이 여럿 적힌 경우 포함)
                self.emit(c, v, hits, True, self.slot(None, params[0], code), code, base, units, 'part')
            elif vcol:
                self.emit(c, v, group or self.parts, bool(group), self.slot(vcol.group(1), params[0], code), code, base,
                          units, level)

    def per_part(self, c, F, row_parts, base):
        """품번 한 줄 표: 열 머리('Breakdown voltage VBR@IT (V) / Min')가 코드·자리·단위를 정한다."""
        # [주의] 품번 하나인 행에서 한 칸에 숫자가 둘 이상이면 파서가 칸을 합쳐 뒤 칸 값이 한 칸씩 밀린 행이다
        # (1.5SMC15H: 'VWM (V): 12.1 1' 뒤의 IR 칸에 IPPM 값 71이 들어감). 그 행의 값은 모두 검토로 보낸다
        shifted = any(parse_cell(v)[0] == 'many' for _, _, v in F)
        for head, col, v in F:
            code, tok = code_of(head, strict=True)
            if not code:
                continue
            b = {**base, 'symbol': tok, 'test_condition': at_condition(head, F)}
            if re.search(r'(?:^|\s)[\d.]+$', col):
                # [주의] 머리 끝에 숫자가 붙으면 첫 데이터 행이 머리로 밀려 올라간 표다. 바로잡지 않고 검토로 보낸다
                self.flag('garbled_table', row_parts, b, code, v, f'열 머리 끝에 숫자: {head}')
                continue
            if len(row_parts) > 1 or shifted:
                # [주의] 품번마다 한 줄인 표에서 한 행에 품번이 둘이면 파서가 행을 합친 것이다.
                # 값 짝이 어긋난다(SMBJ110 SMBJ110A의 'Min: 111 122'에서 111은 다른 행 값). 수가 맞아도 나누지 않는다
                self.flag('garbled_table', row_parts, b, code, v, '한 행에 품번 여러 개' if len(row_parts) > 1
                          else '한 칸에 숫자 여러 개(칸 밀림)')
                continue
            # [왜] 자리는 마지막 열 이름만 본다. 'Nominal Zener Voltage / Vz@Iz'의 Nominal은 아래 칸 셋(최소·대표·최대) 모두의 머리다
            word = re.search(r'\b(min|typ|nom|max)', col, re.I)
            self.emit(c, v, row_parts, True, self.slot(word and word.group(1), '', code), code, b, [head], 'part')

    def col_parts(self, col):
        """열 이름이 이 문서의 품번이면 그 품번 목록('S1A/S1B'처럼 열 하나에 여럿도)."""
        return [self.upper[k] for k in re.split(r'[/,&]', norm_part(col).rstrip('.')) if k in self.upper]

    def row_parts(self, label, F):
        """행 이름(또는 'PART' 열 값)에 적힌 이 문서의 품번 목록.
        'Part number SMCJ5.0H'·'SMBJ5.0A SMBJ5V0A'(같은 부품의 다른 이름)는 하나, 'SMCJ16AH SMCJ17H'(합쳐진 행)는 둘이 된다."""
        for cand in [label] + [v for h, _, v in F if 'PART' in h.upper()]:
            if norm_part(cand) in self.upper:
                return [self.upper[norm_part(cand)]]
            hits = list(dict.fromkeys(self.upper[t] for t in (cand or '').upper().split() if t in self.upper))
            if hits:
                return hits
        return []

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


def build(chunks):
    """청크 목록 → {'rows', 'review', 'packages', 'stats'}. 표지 청크가 없는 문서는 품번을 몰라 건너뛴다."""
    docs = {}
    for c in chunks:
        m = c['kind'] == 'cover' and COVER.match(c['text'])
        if m:
            docs[c['doc']] = Doc(c['doc'], [p.strip() for p in m.group(1).split(', ') if p.strip()], family(c['category']))
    pkgs = defaultdict(list)
    for c in chunks:
        d = docs.get(c['doc'])
        if d is None or c['kind'] not in ('text', 'table_row'):
            continue
        pkgs[c['doc']] += packages_of(c)
        if c['kind'] == 'table_row':
            d.table_row(c)
    cands = [r for d in docs.values() for r in d.cands]
    rows, conflicts, dropped = resolve(cands)
    review = [r for d in docs.values() for r in d.review] + conflicts
    checked = sum((d.checked for d in docs.values()), Counter())
    # [주의] 패키지는 문서 단위다(원형과 같음). 한 문서에 패키지가 여럿이면 품번별로 나누지 못해 모든 품번에 같은 목록이 붙는다
    packages = [{'part': p, 'doc': d.doc, 'family': d.family, 'packages': list(dict.fromkeys(pkgs[d.doc]))}
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
    a = ap.parse_args(argv)
    if a.cmd == 'build':
        cmd_build(a.chunks, a.out_dir)
    else:
        cmd_sample(a.out_dir, a.sheet, a.n, a.seed)


if __name__ == '__main__':
    main()
