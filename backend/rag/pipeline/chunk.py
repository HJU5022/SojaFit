"""Docling 파싱 결과를 검색 청크로 자르고 문서 목록(manifest)을 쓴다(오프라인 도구).

- 역할: 오프라인 CLI(`python -m backend.rag.pipeline.chunk`). 서버가 import하지 않는다.
  - PDF마다 청크(v3, 11-06): 품번 표지 1개 + 제품 개요(1쪽 제목 줄) + 소제목 단위 글 + 표 한 행 = 한 장 + 표 주석.
    - 모든 청크(표지 제외) 앞에 [파일 · 쪽 · 소제목 또는 표 제목] 이름표를 붙인다.
    - 표 바로 뒤 주석(Notes: 아래 항목, 표 각주)은 그 표의 것으로 모아 주석 청크 하나로 남기고,
      행이 가리키는 주석(행·열 이름의 "(1)"·"Note 1")을 그 행 끝에 "\n주: ..."로 붙인다. 표에 주석 표시가 하나도 없으면 모든 행에 붙인다.
    - 글은 소제목 하나 또는 쪽이 바뀔 때, TEXT_MAX 글자를 넘을 때 자른다.
    - 표 칸(v4, 11-08 결정 22): Docling이 찾은 표 자리에 pdfplumber(PDF 테두리선)가 찾은 표가 있으면 그 칸 · 합쳐진 칸 범위를 쓰고,
      없으면 Docling 칸을 쓴다. 두 결과의 숫자가 2개 이상 다르면 한쪽을 믿지 않고 <출력>/table_suspects.jsonl에 남긴다.
    - 버리는 것: 머리글이 본문으로 잡힌 글(회사 이름, 판 번호, 쪽 번호, 쪽마다 반복되는 계열 이름), 법적 고지(Notice) 절,
      그림만 딸린 소제목(값 없는 제목만의 청크가 검색 1위를 차지했다).
  - <출력>/chunks.jsonl(청크 하나 = 한 줄), <출력>/summary.json(청크 수, 서로 다른 본문 수), manifest.jsonl(문서 한 개 = 한 줄)
  - manifest에는 문서마다 다른 값만 쓴다. 모든 문서에 같은 값은 DOC_DEFAULTS에 두고 ingest.py가 읽을 때 채운다.
- 하지 않는 일: 임베딩·DB 적재(`ingest.py`), 파싱(`parse.py`), 그림 안 글(축 눈금·범례, 1쪽 제목 줄만 씀).
  단 `doc_key`·`DOC_DEFAULTS`·`CHUNKER_VERSION`은 `ingest.py`가 import해 쓴다.
- 출처: docs/specs/rag-pipeline.md What 4·AC-01~03·EC-03, ADR 0015(표가 든 조각의 주석 누락), 위키 원장 "청크에서 빠진 글"(11-06)
- 의존성: 표 청크 함수는 표준 라이브러리만 쓴다. 실행(main)에는 uv 그룹 ingest(docling)가 필요하다.

실행: uv run --group ingest python -m backend.rag.pipeline.chunk <docling json 폴더> <목록 csv> <pdf 폴더> <출력 폴더> <manifest.jsonl>
"""
import csv
from collections import defaultdict
import hashlib
import json
import os
import re
import subprocess
import sys

CHUNKER_VERSION = 'tsc-v4h-2026-11-08'  # document_chunks.chunker_version에 들어가는 규칙 이름
PARSER = 'docling 2.145.0 (OCR off)'
USAGE = 'See data/corpus/CORPUS.md; informational/non-commercial, unmodified PDF, notices retained and source attributed.'
# [왜] 1,360줄에 같은 값을 되풀이하면 manifest가 1MB를 넘어 Checkpoint 대시보드가 읽지 못한다(512,000바이트 아래로 둔다).
# [주의] 이 값과 다른 문서(다른 제조사, 인젝션 시험 문서)는 manifest 줄에 그 키를 적으면 줄의 값이 앞선다.
DOC_DEFAULTS = {'manufacturer': 'Taiwan Semiconductor', 'collected_at': '2026-11-01', 'parser': PARSER,
                'status': 'parsed_chunked', 'purpose': 'corpus', 'usage_conditions': USAGE}
TEXT_MAX = 1200  # 글 청크 하나의 본문 글자 상한. [왜] 11-01 C의 글 청크 p90이 1,224자였다. 이 안에서 항목 경계로 자른다
NOTE_MAX = 400  # 표 행 하나에 붙이는 주석 글자 상한. [왜] 주석이 길면 행 본문보다 주석이 임베딩을 끌고 간다
JUNK = re.compile(r'^(taiwan semiconductor\b.*|version\s*:.*|page\s*\d+|\d+)$', re.I)  # 머리글·바닥글이 본문으로 잡힌 글
SERIES = re.compile(r'^[A-Z0-9][A-Z0-9().,/\- ]*\d[A-Z0-9().,/\- ]*$')  # 'BZT52C2V4 - BZT52C75'처럼 대문자·숫자만인 계열 이름
NOTE_HEAD = re.compile(r'^notes?\s*(?:[:：]\s*(.*))?$', re.I)  # "Notes:" 머리. 전각 쌍점과 같은 줄 첫 주석("Notes： 1. …", BZT52B 11-08)도 받는다
PREAMBLE = re.compile(r'unless otherwise|ratings at|for all part', re.I)  # 표 바로 위 공통 조건 문장("(Ratings at TA=25°C … for all part numbers)")
NOTICE_HEAD = re.compile(r'^(notice|disclaimer|important notice)\s*:?\s*$', re.I)
NOTE_LABELS = ('list_item', 'text', 'footnote', 'checkbox_unselected', 'checkbox_selected')  # 주석 묶음에 드는 글 종류
MARK = re.compile(r'\((?:note\s*)?([1-9])\)|\bnotes?\s*([1-9])\b', re.I)  # 행·열 이름 안의 주석 표시 "(1)", "(Note 1)", "Note 1"
NOTE_NO = re.compile(r'^\(?([1-9])[.)]\s*')  # 주석 글 앞 번호 "1. ", "(2) "
TITLEISH = re.compile(r'\d\s*(m?A|k?V|W)\b')  # 1쪽 제품 제목 줄 '200mA, 30V Schottky Barrier Diode'
# 표 위에 세로로 겹친 제목 "ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)"가 칸마다 흩어져 들어간 조각(Docling 결함, 245개 표)
# 강한 제목 낱말: 표 값 · 조건 칸에 원래 나오지 않는 낱말. 이것이 있어야 그 칸 · 그 표를 결함으로 본다
TITLE_TOK = re.compile(r'^(ELECTRICAL|SPECIFICATIONS|CHARACTERISTICS|\(TA|\(TA=25°C|unless|otherwise|noted\)?)$', re.I)
# 약한 낱말: 제목에서도 나오지만 진짜 시험 조건에도 나오는 낱말('25°C', '='), 다른 표 제목 낱말, 주석 · 단위 조각.
# [주의] 강한 낱말과 같은 칸에 있을 때만 지운다. MBRS2035CT는 넘친 조건 'TJ = … | 25°C -'의 25°C로 조건을 되살린다(11-06 대조)
TITLE_WEAK = re.compile(r'^(=|25°C|MAXIMUM|RATINGS|AND|\(\d\)|\([A-Za-zµμ]+\))$', re.I)
TITLE_FRAG = re.compile(r'\b(ELECTRICAL|SPECIFICATIONS)\b|\(TA\s*=\s*25\s*°C|\(TA(?=\s|$)|\bunless\b|\botherwise\b|\bnoted\)', re.I)
SLOT_WORD = re.compile(r'^(min|nom|typ|max)\.?$', re.I)  # 열 이름 끝의 칸 표시
NUMERIC = re.compile(r'^([-+]?\d+(\.\d+)?|[-–])$')  # 표 값 칸 하나(숫자 · 빈 값 표시 '-')
PART_TOK = re.compile(r'^[A-Z0-9][A-Z0-9.\-()/]*\d[A-Z0-9.\-()/]*$')  # 품번 낱말(대문자 · 숫자)


FULL_TITLE = re.compile(r'\(TA\s*=\s*25\s*°C\s+unless\s+otherwise\s+noted\)', re.I)  # 제목 줄 끝의 온전한 조건 문구


def clean_head(text, leak):
    """머리 칸 하나의 제목 조각을 지운다. 온전한 제목('ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)')과 제목 낱말만인 칸은 그대로 둔다."""
    toks = text.split()
    if not toks or FULL_TITLE.search(text) or all(TITLE_TOK.match(t) or TITLE_WEAK.match(t) for t in toks):
        return text
    # [왜] 제목 낱말이 열 이름과 한 칸에 섞였으면('(TA Breakdown voltage VBR@IT (V)', SMBJ 2쪽) 지운다. 데이터 칸에 섞인 표는 머리 칸의 조각도 지운다
    if leak or any(TITLE_TOK.match(t) for t in toks):
        return re.sub(r'\s+', ' ', TITLE_FRAG.sub(' ', text)).strip()
    return text


def split_merged_columns(grid, is_head):
    """Docling이 두 열을 한 열로 합친 표를 되돌린다 → (grid, is_head). 데이터 칸의 60% 이상이 숫자 2개인 열을 두 열로 나눈다.

    [왜] SMBJH 2쪽은 VWM과 누설전류 ID 열이 'VWM (V)' 한 열에 '5.0 800'으로 들어가고, 빠진 열 이름은 첫 데이터 행에 섞였다(11-06).
    숫자가 2m개인 칸(품번 m개가 합쳐진 행)은 홀수 번째 · 짝수 번째로 나눈다. 앞의 낱말은 새 열 이름으로 쓴다.
    """
    n_cols = len(grid[0]) if grid else 0
    data = [r for r in range(len(grid)) if not is_head[r]]
    k = 0
    while k < n_cols:
        vals = [grid[r][k].split() for r in data if grid[r][k]]
        pairs = [v for v in vals if len(v) == 2 and all(NUMERIC.match(t) for t in v)]
        if len(vals) >= 3 and len(pairs) >= 0.6 * len(vals):  # [왜] 0.8이면 SMBJH(28/41)를 놓쳤다. 깨진 행이 섞여도 숫자 둘 칸이 다수면 합친 열이다
            name2 = ''
            for r in range(len(grid)):
                toks = grid[r][k].split()
                if is_head[r]:
                    grid[r] = grid[r][:k + 1] + [grid[r][k]] + grid[r][k + 1:]
                    continue
                nums = [t for t in toks if NUMERIC.match(t)]
                words = [t for t in toks if not NUMERIC.match(t)]
                if words and not name2:
                    name2 = ' '.join(words)  # 'Maximum blocking leakage current ID@VWM (µA)'
                if nums and len(nums) % 2 == 0:
                    first, second = ' '.join(nums[0::2]), ' '.join(nums[1::2])
                else:
                    first, second = grid[r][k], ''
                grid[r] = grid[r][:k] + [first, second] + grid[r][k + 1:]
            if name2:
                for r in range(len(grid)):
                    if is_head[r]:
                        grid[r][k + 1] = name2
            n_cols += 1
            k += 2
            continue
        k += 1
    return grid, is_head


def repair_grid(grid, is_head):
    """Docling 표 결함 두 가지를 고친 (grid, is_head, 열마다 덧붙일 머리 조각)을 돌려준다. 고칠 것이 없으면 그대로 돌려준다.

    1) 제목 조각이 칸에 섞임: 숫자 열의 '낱말 + 숫자' 칸은 숫자만 값으로 두고, 제목 낱말은 버리고, 남은 낱말(Min, VZ @ IZT Nom)은 그 열 이름에 붙인다.
       글 열(품번)은 앞의 제목 낱말만 뗀다. 이런 표에서는 머리 칸의 제목 조각도 지운다.
    2) 두 행이 한 행으로 합쳐짐: 첫 칸이 품번 n개이고 값이 있는 다른 칸이 모두 낱말 n개이면 n행으로 나눈다.
    """
    n_cols = len(grid[0]) if grid else 0
    data = [r for r in range(len(grid)) if not is_head[r]]
    leak = any(len(grid[r][k].split()) > 1 and TITLE_TOK.match(grid[r][k].split()[0]) for r in data for k in range(n_cols))
    extra = [[] for _ in range(n_cols)]
    for r in range(len(grid)):
        if is_head[r]:
            grid[r] = [clean_head(x, leak) for x in grid[r]]
    if leak:
        for k in range(n_cols):
            vals = [grid[r][k] for r in data if grid[r][k]]
            numeric_col = vals and sum(bool(NUMERIC.match(v)) for v in vals) >= 0.6 * len(vals)
            for r in data:
                toks = grid[r][k].split()
                if len(toks) < 2:
                    continue
                strong = any(TITLE_TOK.match(t) for t in toks)
                if numeric_col and NUMERIC.match(toks[-1]):
                    words = [t for t in toks[:-1] if not TITLE_TOK.match(t) and not (strong and TITLE_WEAK.match(t))]
                    if any(NUMERIC.match(t) for t in words) or (not strong and any(TITLE_WEAK.match(t) for t in words)):
                        continue  # [주의] 값이 둘인 칸('49.98 66.64', 행이 합쳐짐)과 넘친 조건('25°C -')은 그대로 둔다
                    grid[r][k] = toks[-1]
                    if words and ' '.join(words) not in extra[k]:
                        extra[k].append(' '.join(words))  # 'Min', 'VZ @ IZT Nom'처럼 데이터 칸으로 내려온 머리 조각
                elif TITLE_TOK.match(toks[0]):
                    while toks and TITLE_TOK.match(toks[0]):
                        toks.pop(0)
                    grid[r][k] = ' '.join(toks)
    out_grid, out_head = [], []
    for r, row in enumerate(grid):
        toks = row[0].split()
        n = len(toks)
        counts = [len(x.split()) for x in row[1:] if x]
        # [주의] 모든 칸이 정확히 n개로 나뉠 때만 나눈다. 값이 하나뿐인 칸을 모든 품번에 붙이면 틀린 값이 된다(SMBJH '14 1 15 1 | 23.1 | 26.9', 11-06 확인)
        if not is_head[r] and n >= 2 and all(PART_TOK.match(t) for t in toks) and len(counts) >= 2 and all(c == n for c in counts):
            for i in range(n):  # [왜] 'BZT… BZT… | 3.4 3.7 | …'를 품번마다 한 행으로 나눠야 그 품번의 값이 사양 표 · 검색에 잡힌다
                out_grid.append([x.split()[i] if x else x for x in row])
                out_head.append(False)
        else:
            out_grid.append(row)
            out_head.append(is_head[r])
    return out_grid, out_head, extra


def sha(text):
    """글자의 sha256 16진 문자열(청크 본문 해시, chunk_sha256)."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def doc_key(file):
    """'1N4148 SERIES_K2301.pdf' → 'tsc-1n4148-series_k2301' (manifest doc_id, DB document_key)."""
    return 'tsc-' + file[:-4].lower().replace(' ', '-')


def revision(file):
    """파일 이름 끝의 개정판 코드(예: '..._H2104.pdf' → 'H2104')."""
    m = re.search(r'_([A-Z]\d{4})\.pdf$', file)
    return m.group(1) if m else None


def note_map(notes):
    """주석 글 목록 → {번호: 글}. 앞에 번호가 없으면 묶음 안 순서(1부터)를 번호로 본다."""
    out = {}
    for k, t in enumerate(notes, 1):
        m = NOTE_NO.match(t)
        out.setdefault(int(m.group(1)) if m else k, t)  # [주의] 같은 번호가 두 번이면 앞의 것을 쓴다
    return out


def pdf_lines(pdf_path, page):
    """pdftotext -layout(Poppler)으로 PDF 한 쪽의 글을 줄마다 낱말 목록으로 돌려준다. 도구가 없거나 실패하면 빈 목록."""
    # [왜] Docling이 여러 행을 한 칸에 섞은 표('SMBJ13A SMBJ14 | 14.4 15.6 …')는 Docling 결과로 되살릴 수 없다. PDF 배치 그대로의 줄은 품번마다 한 줄이다
    try:
        out = subprocess.run(['pdftotext', '-layout', '-f', str(page), '-l', str(page), pdf_path, '-'],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [line.split() for line in out.splitlines() if line.strip()]


# 표 제목으로 알려진 말(TSC 데이터시트의 절 제목). 이 말로 시작하지 않거나 괄호가 닫히지 않은 제목은 PDF 줄에서 되찾는다
KNOWN_TITLE = re.compile(r'^(ELECTRICAL (SPECIFICATIONS|CHARACTERISTICS)|ABSOLUTE MAXIMUM RATINGS|MAXIMUM RATINGS|'
                         r'THERMAL (PERFORMANCE|CHARACTERISTICS)|ORDERING INFORMATION|KEY PARAMETERS)\b')


def needs_title(title):
    """표 제목을 PDF 줄에서 되찾아야 하는가: 알려진 절 제목이 아니거나(머리 칸 'PARAMETER' 등) 괄호가 열린 채 잘렸다."""
    return not KNOWN_TITLE.match(title or '') or title.count('(') > title.count(')')


def page_title(lines, title, names):
    """PDF 줄(낱말 목록)에서 표 제목 줄을 찾는다. 머리 행과 가장 닮은 줄 → 그 줄이 제목이면 그 줄, 아니면 위 7줄 안의 첫 제목 줄. 못 찾으면 None."""
    words = {w.upper().strip('.:()') for n in [title] + list(names) for w in re.split(r'[\s/]+', n) if w}
    first = (re.split(r'[\s/]+', title.strip()) or [''])[0].upper().strip('.:()')
    cands = [k for k, toks in enumerate(lines) if toks[0].upper().strip('.:()') == first]
    if not first or not cands:
        return None
    # [왜] 한 쪽에 'PARAMETER'로 시작하는 표가 여럿(THERMAL PERFORMANCE · ELECTRICAL SPECIFICATIONS)이라 머리 낱말이 가장 많이 겹치는 줄을 고른다
    best = max(cands, key=lambda k: (len({w.upper().strip('.:()') for w in lines[k]} & words), -k))
    for k in range(best, max(best - 8, -1), -1):
        text = ' '.join(lines[k])
        if KNOWN_TITLE.match(text):
            if text.count('(') > text.count(')') and k + 1 < len(lines):
                text += ' ' + ' '.join(lines[k + 1])  # 두 줄로 나뉜 제목('… (TA = 25°C unless' / 'otherwise noted)')
            return text
    return None


def recover_rows(parts, lines, n_cols):
    """품번마다 PDF 줄에서 그 품번으로 시작하는 줄의 값 n_cols-1개를 찾아 [품번, 값 …] 행 목록으로 돌려준다(못 찾은 품번은 빠진다)."""
    out = []
    for p in parts:
        for i, toks in enumerate(lines):
            if not toks or toks[0] != p:
                continue
            vals = toks[1:]
            if not vals and i + 1 < len(lines):
                vals = lines[i + 1]  # [왜] 품번 칸이 두 줄('SMBJ5.0A / SMBJ5V0A')이면 값은 다음 줄에 있다
            if len(vals) == n_cols - 1:  # [주의] 값 개수가 표의 열 수와 정확히 맞을 때만 쓴다. 열이 합쳐진 표는 어느 값이 어느 열인지 모른다
                out.append([p] + vals)
            break
    return out


SYMBOL = re.compile(r'\b([A-Z]{1,3}[A-Z0-9]*\s*@\s*[A-Z]{1,3}[A-Z0-9]*)')  # 열 기호 'VZ @ IZT', 'IR @ VR'


TAIL_SLOT = re.compile(r'\s(Min|Typ|Nom|Max)\.?$', re.I)  # 조각 끝에 붙은 칸 표시('VOLTAGE 2) Max.')


def share_symbol(names):
    """같은 머리 묶음(첫 조각이 같은 이웃 열) 안에서 한 열에만 있는 기호('VZ @ IZT')를 기호 없는 열에도 끼운다(칸 표시 Min · Max 앞).

    [왜] BZV55B 2쪽은 세로 제목이 섞여 'ZENER / Min' · 'ZENER / V / VZ @ IZT Nom' · 'ZENER / VOLTAGE / Max'가 되어 최소 · 최대 열이 VZ로 읽히지 않았다(11-06 v3-13).
    제목 조각을 바로잡은 표에서만 부른다.
    """
    out, k = list(names), 0
    while k < len(out):
        head = out[k].split(' / ')[0]
        j = k
        while j + 1 < len(out) and out[j + 1].split(' / ')[0] == head:
            j += 1
        group = range(k, j + 1)
        syms = [m.group(1) for g in group for m in [SYMBOL.search(out[g])] if m]
        if j > k and len(set(syms)) == 1:
            for g in group:
                if not SYMBOL.search(out[g]):
                    segs = out[g].split(' / ')
                    # [주의] 칸 표시가 조각 끝에 붙은 경우('VOLTAGE 2) Max.')도 칸 표시 앞에 끼운다. 뒤에 붙이면 열 이름 끝이 기호라
                    #        사양 표가 최대 칸을 못 알아봐 BZX84C 30품번의 VZ 최대가 빠졌다(11-06 판정 dev 09 BZX84C3V6)
                    tail = TAIL_SLOT.search(segs[-1])
                    if tail and not SLOT_WORD.match(segs[-1]):
                        segs = segs[:-1] + [segs[-1][:tail.start()].rstrip(), tail.group(0).strip()]
                    at = len(segs) - 1 if SLOT_WORD.match(segs[-1]) else len(segs)
                    out[g] = ' / '.join(segs[:at] + [syms[0]] + segs[at:])
        k = j + 1
    return out


SUB_RATIO = 0.85  # 본문 글자 크기에 대한 아래 · 위첨자 크기 비율의 상한. [왜] HER601G는 본문 10.0, 아래첨자(F · R · rr) 6.5였다(11-08)
LINE_TOL = 2.0  # 본문 글자를 한 줄로 묶는 윗변 차이(pt)
NUM_TOKEN = re.compile(r'(?<![\w.])-?\d+(?:\.\d+)?(?![\w.])')  # 두 표 읽기의 숫자 대조용(0.90과 0.9는 같게 본다)


def cell_lines(page, box):
    """칸 하나의 글을 줄 목록 [(글, 줄 가운데 y)]로 돌려준다. 아래 · 위첨자(작은 글자)는 가까운 본문 줄에 x 순서로 끼운다.

    [왜] 줄 허용 폭을 6으로 넓혀 아래첨자를 붙였더니, 두 줄짜리 조건 칸에서 위아래 줄 글자가 섞였다
         ('I I F rr = = 0 0 . . 5 2 A', HER601G 2쪽 11-08). 글자 크기로 첨자만 골라 붙이면 본문 줄은 섞이지 않는다.
    [왜] 글자는 가운데가 들어 있는 칸 하나에만 넣는다. page.crop(box)는 칸 경계에 조금이라도 걸친 글자를 양쪽 칸에 다 넣어서,
         기호 행 아래로 삐져나온 아래첨자가 아래 단위 칸에도 들어가 'µA'가 'µAR', 'V'가 'Z V Z'가 됐다
         (M3Z2V0C 2쪽 IR @ VR, 제너 문서 8개의 IR 246개를 단위를 몰라 놓침, 11-08 사양 표 대조).
    """
    x0, top, x1, bottom = box
    chars = [c for c in page.chars if c['text'].strip()
             and x0 <= (c['x0'] + c['x1']) / 2 <= x1 and top <= (c['top'] + c['bottom']) / 2 <= bottom]
    if not chars:
        return []
    big = max(c['size'] for c in chars)
    lines = []  # [윗변, 아랫변, 글자들]
    for c in sorted((c for c in chars if c['size'] >= big * SUB_RATIO), key=lambda c: (c['top'], c['x0'])):
        if lines and abs(c['top'] - lines[-1][0]) <= LINE_TOL:
            lines[-1][2].append(c)
            lines[-1][1] = max(lines[-1][1], c['bottom'])
        else:
            lines.append([c['top'], c['bottom'], [c]])
    for c in (c for c in chars if c['size'] < big * SUB_RATIO):
        mid = (c['top'] + c['bottom']) / 2
        if lines:  # 첨자 가운데를 품는 줄, 없으면 윗변이 가장 가까운 줄
            near = min(lines, key=lambda ln: (not (ln[0] - 1 <= mid <= ln[1] + 1), abs(ln[0] - c['top'])))
            near[2].append(c)
        else:
            lines.append([c['top'], c['bottom'], [c]])
    out = []
    for top, bottom, cs in lines:
        cs.sort(key=lambda c: c['x0'])
        text = ''
        for i, c in enumerate(cs):
            # [왜] PDF 공백 글자는 위에서 버렸으므로, 앞 글자와 벌어진 자리에 공백을 다시 넣는다(글자 폭의 0.25배 넘게 벌어짐)
            if i and c['x0'] - cs[i - 1]['x1'] > 0.25 * cs[i - 1]['size']:
                text += ' '
            # [왜] 도(°)를 위첨자 o로 찍은 문서가 있다('Ta = 100oC', B0520LWF 1쪽 11-08). 작은 o 바로 뒤가 C면 °로 읽는다
            small_o = c['text'] == 'o' and c['size'] < big * SUB_RATIO and i + 1 < len(cs) and cs[i + 1]['text'] == 'C'
            text += '°' if small_o else c['text']
        out.append((text, (top + bottom) / 2))
    return out


SUBCOL_GAP = 8.0  # 칸 안에서 다른 덩어리(항목 이름 · 품번 · 조건)로 보는 가로 틈(pt). 낱말 사이 빈칸은 3pt 안팎이다


def sub_columns(page, box):
    """칸 안 글자를 가로 틈(SUBCOL_GAP 넘게 벌어진 곳)으로 나눈 덩어리마다 [x0, x1]. 여러 줄의 글자를 함께 본다."""
    x0, top, x1, bottom = box
    chars = sorted((c for c in page.chars if c['text'].strip()
                    and x0 <= (c['x0'] + c['x1']) / 2 <= x1 and top <= (c['top'] + c['bottom']) / 2 <= bottom), key=lambda c: c['x0'])
    spans = []
    for c in chars:
        if spans and c['x0'] <= spans[-1][1] + SUBCOL_GAP:
            spans[-1][1] = max(spans[-1][1], c['x1'])
        else:
            spans.append([c['x0'], c['x1']])
    return spans


def per_row_lines(ls, spanned, rows_y, allow_parts=False):
    """줄 수 = 걸친 행 수이고 줄마다 조건('=')이거나(allow_parts면 품번이어도) 줄 가운데가 서로 다른 행에 하나씩 들어가면 {행 번호: 줄}.

    [주의] 품번 줄은 줄 가운데가 그 행 가운데 반쪽 안에 있어야 한다. 'RS1AFL RS1BFL RS1DFL RS1FFL'처럼 품번 묶음을 세로로 적은 칸이
           마침 시험 조건 4행에 걸치면, 품번마다 다른 행으로 나눠 버릴 수 있다(묶음은 모든 행의 품번이다).
    """
    if len(ls) != len(spanned):
        return None
    parts = allow_parts and all(PART_TOK.match(s) for s, _ in ls)
    if not parts and not all('=' in s for s, _ in ls):
        return None
    where = {}
    for s, y in ls:
        for i in spanned:
            top, bottom = rows_y[i]
            half = (bottom - top) / 4
            if (top + half <= y <= bottom - half) if parts else (top <= y <= bottom):
                where[i] = s
    return where if len(where) == len(spanned) else None


def plumber_tables(page):
    """pdfplumber 쪽 하나의 표마다 {'bbox', 'cells': (시작 행, 끝 행, 시작 열, 끝 열, 글, 머리), 'n_rows', 'n_cols'} 목록.

    합쳐진 칸은 PDF 테두리선으로 정해진 칸 하나가 여러 자리를 덮으므로, 걸친 모든 자리에 같은 글을 둔다(품번 묶음 · 시험 조건 · 기호).
    단 가로선 없이 조건 · 품번을 줄마다 적은 칸(줄 수 = 걸친 행 수)은 줄을 그 행에만 둔다. 세로선 없이 항목 이름과 함께 적었으면
    가로 틈으로 덩어리를 나눠 그 덩어리만 행마다 나눈다.
    맨 위 제목 행(글 한 가지, 또는 세로선에 잘린 조각)은 빼고 제목은 table_cards가 PDF 줄에서 되찾는다. 머리 행 = 위에서부터 숫자 칸이 없는 행(최대 4).
    """
    out = []
    for t in page.find_tables():
        boxes = t.cells
        lines = {b: cell_lines(page, b) for b in boxes}
        text = {b: ' '.join(s for s, _ in lines[b]) for b in boxes}
        xs = sorted({round(v, 1) for b in boxes for v in (b[0], b[2])})
        ys = sorted({round(v, 1) for b in boxes for v in (b[1], b[3])})
        rows_y = list(zip(ys, ys[1:]))
        per_row = {}  # 칸 → {행 번호: 그 행에 둘 글}. 가로선 없이 줄마다 다른 조건 · 품번을 적은 칸만
        span = {b: [i for i, (top, bottom) in enumerate(rows_y) if b[1] <= (top + bottom) / 2 <= b[3]] for b in boxes}
        by_parts = []  # 품번 줄을 행마다 나눈 칸(아래에서 다시 확인)
        for b in boxes:
            spanned = span[b]
            if len(spanned) < 2:
                continue
            # [왜] B0520LWF 1쪽은 VF · IR 시험 조건 6 · 8줄이 가로선 없는 한 칸이라 모든 행에 조건이 다 붙었다(11-08 코덱스 대조).
            #      줄 가운데가 서로 다른 행에 하나씩 들어가면 줄을 그 행에 둔다. 조건('=')이 아닌 칸(품번 묶음 · 항목 이름)은 그대로 둔다
            where = per_row_lines(lines[b], spanned, rows_y)
            if where:
                per_row[b] = where
                continue
            # [왜] 세로선 없이 '항목 이름 | 품번 | 조건'을 한 칸에 적은 표는 줄이 섞였다('BAV19W-G Reverse voltage BAV20W-G IR=100μA
            #      BAV21W-G', BAV19W · TESDU5V0 · 1N4148W-G · RB495D, 11-08 사양 표 대조). 가로 틈으로 칸 안 덩어리를 나눠,
            #      줄마다 다른 덩어리(조건 · 품번)는 그 행에, 한 줄짜리 덩어리(항목 이름)는 모든 행에 둔다
            subs = sub_columns(page, b)
            if len(subs) < 2:
                continue
            pieces = [cell_lines(page, (sx0, b[1], sx1, b[3])) for sx0, sx1 in subs]
            split = [per_row_lines(p, spanned, rows_y, allow_parts=True) for p in pieces]
            if any(split):
                per_row[b] = {i: ' '.join(w[i] if w else ' '.join(s for s, _ in p) for p, w in zip(pieces, split)) for i in spanned}
                if any(w and all('=' not in s for s in w.values()) for w in split):
                    by_parts.append(b)
        # [주의] 다른 칸의 조건이 행마다 다르면(TJ = 25°C / 125°C) 그 행들은 조건으로 나뉜 것이고, 품번 줄은 모든 행의 품번 묶음이다.
        #        품번을 행마다 나누지 않는다('SS14ALH SS16ALH'를 TJ 두 행에 하나씩 나눠 IR 24개를 잃었다, 11-08 v4g 대조)
        for b in by_parts:
            conds = {i: tuple(sorted(per_row[o][i] if o in per_row else text[o] for o in boxes
                                     if o != b and i in span[o] and '=' in (per_row[o][i] if o in per_row else text[o])))
                     for i in span[b]}
            if len(set(conds.values())) > 1:
                del per_row[b]
        grid, owner = [], []  # owner: 자리마다 그 자리를 덮는 PDF 칸(세로로 합친 칸인지 알아보는 데 쓴다)
        for i, (top, bottom) in enumerate(rows_y):
            row, own = [], []
            for x0, x1 in zip(xs, xs[1:]):
                cx, cy = (x0 + x1) / 2, (top + bottom) / 2
                hit = next((b for b in boxes if b[0] <= cx <= b[2] and b[1] <= cy <= b[3]), None)  # 자리 가운데를 덮는 칸
                row.append('' if hit is None else per_row[hit][i] if hit in per_row else text[hit])
                own.append(hit)
            grid.append(row)
            owner.append(own)
        # [왜] 선이 조금 어긋나 한 칸이 자리 둘로 갈린 같은 행 · 열과, 글이 하나도 없는 행 · 열은 지운다
        keep_r = [i for i, r in enumerate(grid) if any(r) and (i == 0 or r != grid[i - 1])]
        if not keep_r:
            continue
        grid, owner = [grid[i] for i in keep_r], [owner[i] for i in keep_r]
        cols = [list(c) for c in zip(*grid)]
        keep = [j for j, c in enumerate(cols) if any(c) and (j == 0 or c != cols[j - 1])]
        grid, owner = [[r[j] for j in keep] for r in grid], [[r[j] for j in keep] for r in owner]
        first = {v for v in grid[0] if v}
        # [왜] 제목 행은 세로선에 잘려 'E' · 'LECTRICAL SPECIFICATIONS (T'처럼 조각난다(11-08 3쪽). 글이 두 가지면 한쪽이 두 글자 이하의
        #      조각일 때만 제목으로 본다. 'Part No. | Marking' 같은 두 칸 머리 행을 제목으로 지워 첫 값 행이 머리가 됐다(BAV19WS-G 3쪽)
        if len(grid) >= 3 and not any(NUMERIC.match(v) for v in grid[0]) and \
                (len(first) == 1 or (len(first) == 2 and min(map(len, first)) <= 2)):
            grid, owner = grid[1:], owner[1:]
        numeric = [any(NUMERIC.match(v) for v in r) for r in grid]
        # 머리 행 = 첫 행 + 그 아래로 첫 칸이 비었거나 위 행과 같은(세로로 합친 머리) 행 중 숫자 칸이 없는 행, 최대 4행.
        # 숫자 칸이 있어도 첫 칸이 위 행의 PDF 칸 그대로(세로로 합친 한 칸)면 머리다
        # [왜] 숫자만 보고 머리를 정했더니 'Marking code on the device | S2A | S2B …'(표시 코드, 숫자 없는 값 행)를 머리로 읽어
        #      품번 열 이름이 'S2A H / S2A'가 되고 사양 값 읽기가 그 열을 품번으로 못 알아봐 VRRM 1,592개를 놓쳤다(11-08 사양 표 대조)
        # [왜] 품번 끝자리 줄('PARAMETER | SYMBOL | 005 | 01 | 02 …')은 숫자처럼 보여 값 행이 됐고, 열 이름이 모두
        #      'GBPC15, 25, 35'라 GBPC2502의 VRRM 200 V를 못 찾았다(GBPC 2문서 35개, 11-08). 그 줄의 PARAMETER 칸은 위 행과 한 칸이다
        # [왜] 최대 4행: 제너 표는 '항목 이름 / 기호 / 단위 / Min · Nom · Max' 4행 머리라, 3행까지만 보면 Min · Nom · Max 줄이 값 카드로
        #      내려가 VZ 공칭값 89개를 놓쳤다(1N4740A · 1SMB5926 등 49문서, 11-08 사양 표 대조)
        # [왜] 위 행의 가로로 합친 칸('Part number')이 이 행에서 여러 칸('Uni | Bi')으로 나뉘면 두 층 머리다. 첫 칸이 위와 달라도 머리다
        #      (SMDJ 'Uni | Bi | Min | Max' 줄이 값 카드로 내려가 VBR 칸을 몰랐다, 11-08)
        # [주의] 품번처럼 생긴 칸이 있는 줄은 값 줄이다. 'PARAMETER'(두 칸) 아래 'Marking code on the device | 1N4148W | D1'을
        #        머리로 올려 PD 7개를 놓쳤다(1N4148W · MMBD3004, 11-08 v4f 대조)
        def splits(n):
            return not any(PART_TOK.match(v) for v in grid[n]) and any(
                owner[n - 1][j] is not None and owner[n - 1][j] == owner[n - 1][j + 1] and owner[n][j] != owner[n][j + 1]
                for j in range(len(owner[n]) - 1))
        n_head = 1
        while n_head < min(4, len(grid) - 1) and (
                (grid[n_head][0] in ('', grid[n_head - 1][0])
                 and (not numeric[n_head] or (owner[n_head][0] is not None and owner[n_head][0] == owner[n_head - 1][0])))
                or (not numeric[n_head] and splits(n_head))):
            n_head += 1
        cells = [(r, r + 1, k, k + 1, v, r < n_head) for r, row in enumerate(grid) for k, v in enumerate(row)]
        out.append({'bbox': t.bbox, 'cells': cells, 'n_rows': len(grid), 'n_cols': len(grid[0])})
    return out


def numbers_of(texts):
    """글 목록 → 숫자 집합(두 표 읽기의 대조용)."""
    from decimal import Decimal
    return {Decimal(m).normalize() for t in texts for m in NUM_TOKEN.findall(t or '')}


def table_cards(file, page, n_rows, n_cols, cells, notes=(), lines=None, recover=True, preamble=''):
    """표 하나를 데이터 행마다 청크 하나로 만든다(AC-01·AC-02). notes는 표 주석 글, lines는 그 쪽 PDF 줄을 돌려주는 함수(합쳐진 행 되살리기).

    recover=False면 섞인 행 되살리기를 하지 않는다(pdfplumber 칸은 행이 섞이지 않는다). 제목 되찾기는 그대로 한다.
    preamble은 표 바로 위 공통 조건 문장이다. 표 제목 뒤에 붙여 모든 행 이름표에 들어가게 한다.
    """
    # cells: (시작 행, 끝 행, 시작 열, 끝 열, 글자, 머리 칸 여부) 목록. 끝은 포함하지 않는다(Docling offset과 같음)
    if not n_rows or not n_cols:  # [주의] Docling이 칸 없는 빈 표를 낼 때가 있다(EC-03). 건너뛴다
        return []
    grid = [[''] * n_cols for _ in range(n_rows)]
    is_head = [False] * n_rows
    for r0, r1, c0, c1, text, head in cells:
        for r in range(r0, r1):  # [왜] 합친 칸은 한 자리에만 글자가 있어서, 걸친 모든 자리에 같은 글자를 채운다
            for k in range(c0, c1):
                grid[r][k] = text.strip()
            is_head[r] = is_head[r] or head
    grid, is_head = split_merged_columns(grid, is_head)
    n_cols = len(grid[0])
    grid, is_head, extra = repair_grid(grid, is_head)
    if lines is not None and recover:
        fixed_grid, fixed_head = [], []
        for row, head in zip(grid, is_head):
            toks = row[0].split()
            # 되살릴 행: 품번 여러 개가 한 칸에 섞인 행, 또는 품번만 있고 값 칸이 모두 빈 행(SMCJ 2쪽)
            broken = toks and all(PART_TOK.match(t) for t in toks) and (len(toks) >= 2 or not any(row[1:]))
            if not head and broken and (got := recover_rows(toks, lines(), n_cols)):
                fixed_grid += got  # 되살린 품번은 품번마다 한 행. 못 찾은 품번이 있으면 섞인 행도 남긴다(사양 표가 그 행은 빼낸다)
                fixed_head += [False] * len(got)
                if len(got) < len(toks):
                    fixed_grid.append(row)
                    fixed_head.append(False)
            else:
                fixed_grid.append(row)
                fixed_head.append(head)
        grid, is_head = fixed_grid, fixed_head
    n_rows = len(grid)
    heads = [r for r in range(n_rows) if is_head[r]] or [0]  # 머리 행 표시가 없으면 첫 행을 머리로 본다
    names = []  # 열 이름 = 그 열의 머리 행 글자들을 ' / '로 이은 것(같은 글자는 한 번만) + 데이터 칸에서 되찾은 머리 조각
    for k in range(n_cols):
        parts = []
        for r in heads:
            if grid[r][k] and grid[r][k] not in parts:
                parts.append(grid[r][k])
        # [왜] 열 이름 끝 조각(Min · Max …)으로 칸을 알아보므로, 이미 그것으로 끝나면 되찾은 조각은 그 앞에 끼운다('… / (V) / MAX')
        if extra[k] and parts and SLOT_WORD.match(parts[-1]):
            parts = parts[:-1] + extra[k] + parts[-1:]
        else:
            parts = parts + extra[k]
        names.append(' / '.join(parts) or f'열{k + 1}')
    if any(extra):
        names = share_symbol(names)
    # [주의] 제목 칸이 'PARAMETER'여도 Docling의 앞 소제목으로 바꾸지 않는다. 앞 소제목이 'MECHANICAL DATA'처럼 다른 절이라 정격 행에 엉뚱한 제목이 붙었다(11-06 R1 dev 실측)
    title = grid[heads[0]][0]
    if lines is not None and needs_title(title):
        # [왜] 제목이 'PARAMETER' · 'PART NUMBER'(머리 칸)이거나 'ELECTRICAL SPECIFICATIONS (TA'처럼 잘리면 표 기본 조건 'TA = 25°C'를 잃는다.
        #      판정 코드가 사용 온도 25°C 행을 고를 때 이 행들이 '확인 안 됨'이 됐다(11-06 v3-12 HER105G trr, 표 행 4,284개).
        #      PDF 배치 그대로의 줄에서 이 표 머리 행과 가장 닮은 줄을 찾고, 그 줄이나 바로 위 7줄 안의 알려진 표 제목 줄을 쓴다
        title = page_title(lines(), title, names) or title
    if preamble and preamble not in title:
        title = f'{title} {preamble}'  # [왜] 'TA=25°C', '전 품번 VF = 1V @ IF = 10 mA' 같은 공통 조건이 행마다 남는다(BZT52B 11-08)
    rows = []
    for r in range(n_rows):
        if is_head[r] or not any(grid[r]):
            continue
        pairs = []
        for k in range(n_cols):
            pair = f'{names[k]}: {grid[r][k]}'
            # [왜] 합쳐진 칸이 자리 둘 이상에 걸치면 바로 옆에 같은 '이름: 값'이 되풀이된다('UNIT: V | UNIT: V', pdfplumber 칸 11-08). 한 번만 쓴다
            if grid[r][k] and (not pairs or pairs[-1] != pair):
                pairs.append(pair)
        rows.append((r, ' | '.join(pairs)))
    numbered = note_map(notes)
    marked = any(MARK.search(t) for _, t in rows)  # 표 어디에든 주석 표시가 있으면 표시한 주석만 붙인다
    out = []
    for r, cells_text in rows:
        if marked:
            wanted = sorted({int(a or b) for a, b in MARK.findall(cells_text)})
            attach = [numbered[n] for n in wanted if n in numbered]
        else:
            attach = list(notes)
        # [왜] 상한에서 글자 단위로 자르면 주석이 문장 중간에서 끊겼다('… derived from the 60', BZT52B 11-08). 주석을 통째로만 넣는다.
        #      첫 주석 하나가 상한보다 길면 그것만은 잘라 넣는다(아무 주석도 없는 것보다 낫다)
        keep = []
        for a in attach:
            if keep and len(' '.join(keep + [a])) > NOTE_MAX:
                break
            keep.append(a)
        note = ' '.join(keep)[:NOTE_MAX]
        out.append({'kind': 'table_row', 'page': page, 'table': title, 'row': next(v for v in grid[r] if v),
                    'text': f'[{file} · {page}쪽 · {title}] {cells_text}' + (f'\n주: {note}' if note else '')})
    return out


def text_cards(file, heading, items):
    """소제목 하나 아래 (쪽, 글) 목록을 쪽이 바뀌거나 TEXT_MAX를 넘을 때 끊어 글 청크로 만든다."""
    out, buf = [], []

    def close():
        if buf:
            page = buf[0][0]
            label = f'[{file} · {page}쪽 · {heading}] ' if heading else f'[{file} · {page}쪽] '
            out.append({'kind': 'text', 'page': page, 'table': None, 'row': None, 'text': label + '\n'.join(t for _, t in buf)})
            buf.clear()
    for page, t in items:
        if buf and (page != buf[0][0] or sum(len(x) for _, x in buf) + len(t) > TEXT_MAX):
            close()
        buf.append((page, t))
    close()
    return out


H_NOTE = re.compile(r'"H"\s*means\s*AEC[- ]?Q101\s+qualified', re.I)  # 주문 정보 주석: H로 끝나는 품번이 인증품
# 주문 코드 틀: 'x'가 품번의 바뀌는 자리, 그 뒤 H, 끝에 포장 코드(A0G 등)가 붙을 수 있다('1N4xGHA0G' → 앞 '1N4', 가운데 'G')
H_TEMPLATE = re.compile(r'ORDERING CODE[^:|]*:\s*([0-9A-Z.\-]+?)x([0-9A-Z.\-]*?)H(?:[A-Z][0-9A-Z]G?)?(?=\s*(?:\||$|\n))')


def h_variants(cards, parts):
    """주문 정보 틀('1N581xH')과 '"H" means AEC-Q101 qualified' 주석이 함께 있는 문서에서, 틀에 맞는 기본 품번마다 H 품번을 만든다."""
    if not any(H_NOTE.search(c['text']) for c in cards if c['kind'] in ('table_row', 'note', 'text')):
        return []
    have = {p.upper() for p in parts}
    out = []
    for c in cards:
        if c['kind'] != 'table_row':
            continue
        for pre, mid in H_TEMPLATE.findall(c['text']):
            for p in parts:
                P = p.upper()
                if (P.startswith(pre.upper()) and P.endswith(mid.upper()) and len(P) > len(pre) + len(mid)
                        and not P.endswith('H') and P + 'H' not in have):
                    have.add(P + 'H')
                    out.append(p + 'H')
    return out


def overlap(a, b):
    """두 상자(x0, top, x1, bottom)의 겹친 넓이가 a · b 넓이에서 차지하는 몫(a 쪽, b 쪽)."""
    w = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    h = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    area = lambda x: max((x[2] - x[0]) * (x[3] - x[1]), 1e-6)
    return w * h / area(a), w * h / area(b)


def doc_cards(doc, file, parts, pdf_path=None, log=None):
    """Docling 문서 하나를 (청크 목록: 표지·개요·글·표 행·주석 순서, 원문 글자 수, 청크에 들어간 원문 글자 수)로 바꾼다.

    pdf_path가 있으면 표 칸은 pdfplumber를 먼저 쓴다(결정 22). log(dict)를 주면 표마다 읽은 도구 수('tables')와
    두 읽기의 숫자가 2개 이상 다른 표('suspects')를 채운다.
    """
    from docling_core.types.doc import PictureItem, TableItem, TextItem
    cards = [{'kind': 'cover', 'page': None, 'table': None, 'row': None,
              'text': f'[{file}] 이 데이터시트의 품번: {", ".join(parts)}'}]  # [주의] retrieve.COVER·specs.py가 이 모양을 읽는다
    body = [it for it, _ in doc.iterate_items()]
    pages_of = defaultdict(set)  # 글 → 나온 쪽들. 쪽마다 반복되는 계열 이름을 머리글로 가린다
    for it in body:
        if isinstance(it, TextItem) and it.prov:
            pages_of[it.text.strip()].add(it.prov[0].page_no)

    def junk(t):
        return not t or JUNK.match(t) or (len(t) < 60 and SERIES.match(t) and len(pages_of[t]) >= 2)
    kept = set()  # 청크에 들어간 원문 글 조각(self_ref)
    overview = []  # 1쪽 제목 줄: 그림 안 글과 항목 없는 1쪽 소제목
    for p in doc.pictures:
        if p.prov and p.prov[0].page_no == 1:
            for ch in p.children:  # [왜] 제품 설명 줄('150mA, 100V Switching Diode')이 그림 안 글로 잡히는 문서가 1,163/1,360이다(11-06)
                t = ch.resolve(doc)
                if isinstance(t, TextItem) and not junk(t.text.strip()) and t.text.strip() not in overview:
                    overview.append(t.text.strip())
    sections, tables = [], []  # 소제목 묶음 {heading, items, has_table}, 표 {item, heading, notes}
    cur, last_table, in_notes, in_notice = None, None, False, False
    pre = []  # 소제목 · 앞 표 뒤로 표 앞까지 나온 글 (쪽, 글). 표 바로 위 공통 조건 문장을 찾는다
    for it in body:
        if isinstance(it, PictureItem):
            continue
        if isinstance(it, TableItem):
            if not it.data.num_rows or not it.data.num_cols:  # [주의] 칸 없는 빈 표(EC-03)는 표로 세지 않는다. 앞 소제목을 표 제목으로 보고 버리지 않게
                continue
            notes = [f.resolve(doc) for f in it.footnotes]  # Docling이 표에 묶어 둔 각주
            page_t = it.prov[0].page_no if it.prov else None
            joined = ' '.join(s for p, s in pre if p == page_t)
            last_table = {'item': it, 'heading': cur['heading'] if cur else None,
                          'notes': [(n.prov[0].page_no if n.prov else None, n.text.strip()) for n in notes if n.text.strip()],
                          # [왜] 표 위 문장의 공통 조건(TA=25°C, 전 품번 VF = 1V @ IF = 10 mA)이 표 행에 없어 조건 없는 값이 됐다(BZT52B 2쪽 11-08 코덱스 대조)
                          'preamble': joined if PREAMBLE.search(joined) else ''}
            kept.update(n.self_ref for n in notes)
            tables.append(last_table)
            in_notes, pre = False, []
            if cur:
                cur['has_table'] = True
            continue
        if not isinstance(it, TextItem):
            continue
        t, lab = it.text.strip(), it.label.value
        page = it.prov[0].page_no if it.prov else None
        if junk(t):
            continue
        if lab == 'section_header' and NOTICE_HEAD.match(t):
            in_notice, last_table, in_notes = True, None, False
            continue
        head = NOTE_HEAD.match(t)
        if head and last_table is not None:  # 표 바로 뒤 "Notes:" 머리
            in_notes = True
            if head.group(1):  # 같은 줄에 첫 주석이 붙은 경우("Notes： 1. The Zener Voltage …")
                last_table['notes'].append((page, head.group(1).strip()))
            kept.add(it.self_ref)
            continue
        # [왜] '2. Pulse test with PW = 30ms'처럼 번호 붙은 주석이 소제목으로 잡히는 문서가 있다. 주석 묶음 안이면 주석으로 본다
        if last_table is not None and (in_notes and (lab in NOTE_LABELS or NOTE_NO.match(t)) or lab == 'footnote'):
            last_table['notes'].append((page, t))  # [왜] 이 주석은 앞 표의 측정 조건·같은 부품 설명이다(ADR 0015)
            kept.add(it.self_ref)
            continue
        last_table, in_notes = None, False  # 표 뒤에 주석이 아닌 글이 오면 그 뒤 글은 표 주석이 아니다
        if lab == 'section_header':
            in_notice = False
            cur = {'heading': t, 'items': [], 'has_table': False, 'page': page}
            sections.append(cur)
            pre = []  # 새 소제목이면 앞 글은 다음 표의 공통 조건이 아니다
            continue
        if in_notice:
            continue
        if cur is None:
            cur = {'heading': None, 'items': [], 'has_table': False, 'page': page}
            sections.append(cur)
        cur['items'].append((page, t))
        pre.append((page, t))
        kept.add(it.self_ref)
    texts = []
    for s in sections:
        if s['items']:
            texts += text_cards(file, s['heading'], s['items'])
        elif s['page'] == 1 and (not s['has_table'] or TITLEISH.search(s['heading'])):
            overview.append(s['heading'])  # 1쪽 제품 제목('500mW, 5% Tolerance SMD Zener Diodes')
        # [주의] 그림만 딸린 소제목('PACKAGE OUTLINE DIMENSIONS', 'MARKING DIAGRAM')은 청크로 만들지 않는다. 값이 없는 제목만의 청크가
        # "어떤 패키지?" 질문에서 1위를 차지해 패키지 이름이 있는 1쪽 행을 밀어냈다(11-06 R1 dev 실측)
    if overview:
        cards.append({'kind': 'overview', 'page': 1, 'table': None, 'row': None,
                      'text': f'[{file} · 1쪽 · 제품 개요] ' + '\n'.join(overview)})
    cards += texts
    # [왜] 주석은 PDF에서 아래 표 밑에 몰아 적히기도 한다. B0520LWF 1쪽의 주석 2는 위 표 RθJA 행('(Note 2)')의 것인데 아래 표(VF · IR)
    #      밑에 있어 그 표의 모든 행에 붙었다(11-08 코덱스 대조). 번호 붙은 주석을 그 번호를 가리키지 않는 표가 가졌고, 같은 쪽 앞 표가
    #      그 번호를 가리키면 앞 표로 옮긴다
    def marks(tb):
        return {int(a or b) for a, b in MARK.findall(' '.join(c.text for c in tb['item'].data.table_cells))}
    for i, tb in enumerate(tables):
        page_t = tb['item'].prov[0].page_no if tb['item'].prov else None
        for note in list(tb['notes']):
            m = NOTE_NO.match(note[1])
            if not m or int(m.group(1)) in marks(tb):
                continue
            owner = next((p for p in reversed(tables[:i]) if p['item'].prov and p['item'].prov[0].page_no == page_t
                          and int(m.group(1)) in marks(p)), None)
            if owner is not None:
                owner['notes'].append(note)
                tb['notes'].remove(note)
    kept_tables = []
    pdf = None
    if pdf_path and os.path.exists(pdf_path):
        import pdfplumber
        pdf = pdfplumber.open(pdf_path)
    plumbed = {}  # 쪽 → 그 쪽의 pdfplumber 표 목록(쪽마다 한 번 읽는다)
    for tb in tables:
        t = tb['item']
        cells = [(c.start_row_offset_idx, c.end_row_offset_idx, c.start_col_offset_idx, c.end_col_offset_idx,
                  c.text, c.column_header) for c in t.data.table_cells]
        page = t.prov[0].page_no if t.prov else None
        notes = [n for _, n in tb['notes']]
        cache = {}  # 쪽마다 pdftotext를 한 번만 부른다
        lines = (lambda pg=page: cache.setdefault(pg, pdf_lines(pdf_path, pg))) if pdf_path and page else None
        rows, covered = [], False
        if pdf is not None and page and t.prov:
            # [왜] Docling은 표 그림을 보고 칸을 추측해 세로로 합쳐진 칸(품번 묶음 · 시험 조건 · 기호)을 자주 틀리게 나눈다.
            #      pdfplumber는 PDF 테두리선으로 칸을 정해 3쪽 대조에서 6곳을 모두 맞췄고, 11-01 정답표 41/41 · 품번 열 12/12였다(결정 22)
            if page not in plumbed:
                plumbed[page] = plumber_tables(pdf.pages[page - 1])
            b = t.prov[0].bbox.to_top_left_origin(page_height=float(pdf.pages[page - 1].height))
            d_box = (b.l, b.t, b.r, b.b)
            mine = []
            for p in plumbed[page]:
                cover_p, cover_d = overlap(p['bbox'], d_box)
                if cover_p >= 0.8 or cover_d >= 0.8:
                    covered = covered or (p.get('used') and cover_d >= 0.8)  # Docling이 표 하나를 둘로 나눈 뒷부분: 이미 만든 행이다
                    if not p.get('used'):
                        mine.append(p)
            for p in mine:
                got = table_cards(file, page, p['n_rows'], p['n_cols'], p['cells'], notes, lines, recover=False,
                                  preamble=tb['preamble'])
                if got:
                    p['used'] = True
                    rows += got
            if rows and log is not None:
                # [왜] 두 읽기의 숫자를 맞대어 2개 이상 다르면 한쪽을 믿지 않고 사람 · 코덱스가 볼 목록에 남긴다(결정 22).
                #      1개 차이는 'D 2 PAK'의 2처럼 읽는 방식 차이가 대부분이었다(11-08 전체 대조 151표 중 표본 4개)
                d_nums = numbers_of(c.text for c in t.data.table_cells)
                p_nums = numbers_of(c[4] for p in mine for c in p['cells'])
                if len(d_nums - p_nums) >= 2 or len(p_nums - d_nums) >= 2:
                    log.setdefault('suspects', []).append({
                        'file': file, 'page': page, 'table': rows[0]['table'],
                        'docling_only': sorted(map(str, d_nums - p_nums))[:20], 'pdfplumber_only': sorted(map(str, p_nums - d_nums))[:20]})
        reader = 'pdfplumber' if rows else 'covered' if covered else 'docling'
        if not rows and not covered:
            rows = table_cards(file, page, t.data.num_rows, t.data.num_cols, cells, notes, lines, preamble=tb['preamble'])
        if log is not None:
            log.setdefault('tables', defaultdict(int))[reader] += 1
        cards += rows
        if rows or covered:
            kept_tables.append(t.self_ref)
        if notes:
            title = rows[0]['table'] if rows else (tb['heading'] or '표')
            note_page = tb['notes'][0][0] or page
            cards.append({'kind': 'note', 'page': note_page, 'table': title, 'row': None,
                          'text': f'[{file} · {note_page}쪽 · {title} 주석] ' + '\n'.join(notes)})
    if pdf is not None:
        pdf.close()
    # 원문 글자 수 = 본문(머리글·바닥글 제외) 글 조각 + 표 칸. 청크에 들어간 글자 수 = 청크에 든 글 조각 + 청크를 만든 표의 칸
    # [왜] 이름표·표지·반복되는 열 이름은 원문이 아니라 세지 않는다. 일부러 버린 글(머리글 쓰레기·법적 고지)은 빠진 것으로 센다
    texts_all = [it for it in body if isinstance(it, TextItem)]
    tables_all = [it for it in body if isinstance(it, TableItem)]
    table_chars = {t.self_ref: sum(len(c.text) for c in t.data.table_cells) for t in tables_all}
    original = sum(len(it.text) for it in texts_all) + sum(table_chars.values())
    heads = {s['heading'] for s in sections}
    kept_chars = sum(len(it.text) for it in texts_all if it.self_ref in kept or it.text.strip() in heads) + \
        sum(table_chars.get(r, 0) for r in kept_tables)
    variants = h_variants(cards, parts)
    if variants:
        # [왜] H(AEC-Q101) 품번이 주문 정보의 틀('1N581xH')로만 적힌 문서가 142개다. 표지 품번 목록에 넣어야 사실 확인 · 품번 필터 ·
        #      사양 표가 1N5819H를 코퍼스 품번으로 안다(11-06 판정 dev 14). [주의] parts를 제자리에서 늘린다: 청크 메타데이터 parts도 같은 목록이다
        parts.extend(variants)
        cards[0]['text'] = f'[{file}] 이 데이터시트의 품번: {", ".join(parts)}'
    return cards, original, kept_chars


def main(json_dir, list_csv, pdf_dir, out_dir, manifest_path):
    """Docling json 폴더를 청크(chunks.jsonl)와 문서 목록(manifest.jsonl)으로 바꾸고 summary.json을 쓴다."""
    # json_dir: parse.py 결과, list_csv: collect.py list 결과, pdf_dir: 원본 PDF(sha256 계산용)
    # [주의] 목록 csv에 없는 PDF가 json 폴더에 있으면 meta[...]에서 KeyError로 멈춘다(조용히 건너뛰지 않는다)
    from docling_core.types.doc import DoclingDocument
    with open(list_csv, encoding='utf-8') as fh:
        meta = {r['file']: r for r in csv.DictReader(fh)}
    os.makedirs(out_dir, exist_ok=True)
    n_cards, seen, kinds, log = 0, set(), defaultdict(int), {}
    with open(os.path.join(out_dir, 'chunks.jsonl'), 'w', encoding='utf-8') as fc, \
            open(manifest_path, 'w', encoding='utf-8') as fm:
        for f in sorted(x for x in os.listdir(json_dir) if x.endswith('.json')):
            file, m = f[:-5], meta[f[:-5]]
            doc = DoclingDocument.load_from_json(os.path.join(json_dir, f))
            parts = m['parts'].split(';')
            base = {'doc': file, 'revision': revision(file), 'category': m['categories'], 'parts': parts}
            cards, chars_original, chars_kept = doc_cards(doc, file, parts, os.path.join(pdf_dir, file), log)
            for k, card in enumerate(cards):
                fc.write(json.dumps({**base, 'idx': k, **card, 'sha256': sha(card['text'])}, ensure_ascii=False) + '\n')
                seen.add(sha(card['text']))
                kinds[card['kind']] += 1
            n_cards += len(cards)
            with open(os.path.join(pdf_dir, file), 'rb') as fp:
                pdf = fp.read()
            # [왜] 파일 이름은 source_url 끝에 있어 path를 따로 쓰지 않고, 공백 없는 JSON(separators)으로 크기를 줄인다
            fm.write(json.dumps({
                'doc_id': doc_key(file), 'title': re.sub(r'_[A-Z]\d{4}\.pdf$', '', file), 'revision': revision(file),
                'source_url': m['url'], 'sha256': hashlib.sha256(pdf).hexdigest(), 'bytes': len(pdf), 'pages': doc.num_pages(),
                'chunks': len(cards), 'chars_original': chars_original, 'chars_kept': chars_kept,
                'truncated': chars_kept < chars_original}, ensure_ascii=False, separators=(',', ':')) + '\n')
    with open(os.path.join(out_dir, 'table_suspects.jsonl'), 'w', encoding='utf-8') as fs:
        for s in log.get('suspects', []):  # 두 표 읽기의 숫자가 2개 이상 다른 표(사람 · 코덱스가 본다, 결정 22)
            fs.write(json.dumps(s, ensure_ascii=False) + '\n')
    summary = {'cards': n_cards, 'distinct_text': len(seen), 'kinds': dict(kinds), 'chunker_version': CHUNKER_VERSION,
               'tables_by_reader': dict(log.get('tables', {})), 'table_suspects': len(log.get('suspects', []))}
    with open(os.path.join(out_dir, 'summary.json'), 'w', encoding='utf-8') as fs:
        json.dump(summary, fs, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) != 6:
        sys.exit(__doc__)
    main(*sys.argv[1:6])
