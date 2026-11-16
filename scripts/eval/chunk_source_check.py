"""표/수치 청크 vs 원본 PDF 쪽 텍스트 직접 대조 (읽기 전용, 네트워크 없음).

실행: uv run python scripts/eval/chunk_source_check.py [--seed 1116] [--per-cell 3] [--rows | --notes] [--out <폴더>]
입력: ../corpus/tsc/chunks-v4h/chunks.jsonl (본문, sha256을 chunk_sha256.tsv와 대조), ../corpus/tsc/pdf/*.pdf
출력: evals/results/d10/chunk_source_check/results.jsonl, summary.json (`--rows`·`--notes`는 각자 새 폴더, `--out`으로 변경)

네 검사:
- 쪽 검사(기본): 청크의 숫자·단위·품번 열이 그 쪽 텍스트에 있는가. 같은 쪽 다른 행의 값으로 바뀐 오류는 통과한다.
- 행 검사(`--rows`, row_check 필드 추가): 청크의 PARAMETER·CONDITIONS·SYMBOL로 PDF 표의 같은 행을 찾고,
  그 행에서 같은 열의 칸 값(TYP·MAX·VALUE·품번 열)과 UNIT이 청크와 같은지 본다. 기존 필드는 바뀌지 않는다.
- 부품 행 검사(`--notes`, part_check 필드): 행 이름 칸이 없는 부품 한 개당 한 행인 표에서 첫 열이 청크 품번과 같은 행을 찾아
  머리글이 같은 열의 칸 값과 비교한다.
- 각주 검사(`--notes`, note_check 필드): 그 표 바로 아래 각주(Note·Notes 묶음)와 표 칸의 각주 표시로 청크에 붙어야 할 각주를 정하고
  청크의 `주:` 글에 그 각주가 있는지 본다. `--notes`는 `--rows`를 포함하고 기존 필드와 row_check는 그대로 둔다.
하지 않는 것: 코퍼스·청커 수정, 표 밖 글, 조건 칸 안의 숫자 순서 바꿈(문자 구성만 본다), 다른 쪽에 있는 각주, 괄호 없는 위첨자 각주 표시.
근거: evals/guides/preregister.md 2026-11-15 항목·2026-11-16 "부품 행 표"와 "표 각주" 항목, 강사 11/13·11/16 코멘트(축 ②).
"""
import argparse, collections, hashlib, json, random, re, sys
from pathlib import Path
import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
CHUNKS = ROOT.parent / "corpus/tsc/chunks-v4h/chunks.jsonl"
PDFDIR = ROOT.parent / "corpus/tsc/pdf"
TSV = ROOT / "evals/results/chunking/v4h-2026-11-08/chunk_sha256.tsv"
OUT = ROOT / "evals/results/d10/chunk_source_check"
OUT_ROWS = ROOT / "evals/results/d10/chunk_source_check_rows_2026-11-16"
OUT_NOTES = ROOT / "evals/results/d10/chunk_source_check_notes_2026-11-16"
TEXT_KEYS = {"PARAMETER", "SYMBOL", "PACKAGE", "MARKING CODE", "UNIT", "CONFIGURATION"}
NUM = re.compile(r"(?<![\w.])([-+]?)(\d[\d,]*(?:\.\d+)?)")


def norm(s):
    return s.replace("−", "-").replace("–", "-").replace("﹣", "-").replace("℃", "°C").replace("Ω", "Ω").replace("µ", "μ")


def ttype(t):
    t = (t or "").upper()
    if t.startswith("ABSOLUTE"): return "ratings"
    if t.startswith("THERMAL"): return "thermal"
    if "ELECTRICAL" in t: return "electrical"
    return None


def fields(text):
    body = text.split("] ", 1)[1]
    body = body.split("\n주:")[0]  # 각주는 값 대조 대상이 아님(각주가 붙었는지는 note_check가 따로 본다)
    out = []
    for f in body.split(" | "):
        k, _, v = f.partition(": ")
        out.append((k.strip(), v.strip()))
    return out


def checks(text):
    """(종류, 값) 목록: num=숫자(부호 포함), unit=단위, key=품번 열 이름."""
    items, units = [], []
    for k, v in fields(text):
        v = norm(v)
        ku = k.upper()
        if ku == "UNIT":
            if v and not NUM.fullmatch(v): units.append(v)
            continue
        if ku in TEXT_KEYS or ku.startswith(("PART", "ORDERING", "PARAMETER")):
            continue
        if ku not in ("VALUE", "TYP", "MAX", "MIN", "NOM", "CONDITIONS", "PACKING") and "/" not in k and not NUM.match(v):
            continue
        if ku not in ("VALUE", "TYP", "MAX", "MIN", "NOM", "CONDITIONS", "PACKING") and "/" not in k:
            if "(" not in k and len(k.split()) <= 2:  # 품번 열("FR 152G")만; 긴 머리글 라벨은 값이 아니므로 제외
                items.append(("key", k.split()[-1]))  # PDF 머리글은 접두("FR")와 접미("152G")가 갈라져 나와 접미만 본다
        for sg, n in NUM.findall(v):
            items.append(("num", ("-" if sg == "-" else "") + n.replace(",", "")))
    return items, units


def page_lines(pdf, pno):
    return [norm(l) for l in (pdf.pages[pno - 1].extract_text() or "").split("\n")]


def has_num(s, n):
    neg = n.startswith("-")
    p = re.escape(n.lstrip("-"))
    return bool(re.search((r"(?<![\w.])-\s?" if neg else r"(?<![\w.])") + p + r"(?![\d]|\.\d)", s.replace(",", "")))


def page_check(text, lines):
    """쪽 검사: (값 목록, 단위 목록, 쪽에 없는 것, 6줄 창 통과 여부). main에서 꺼냈을 뿐 계산은 그대로."""
    items, units = checks(text)
    page = "\n".join(lines)
    flat = page.replace(" ", "")
    miss = []
    for kind, v in items:
        if kind == "num" and not has_num(page, v): miss.append(f"num {v}")
        if kind == "key" and v.replace(" ", "") not in flat: miss.append(f"col {v}")
    for u in units:
        if norm(u).replace(" ", "") not in flat: miss.append(f"unit {u}")
    nums = [v for k, v in items if k == "num"]
    # 행 근접: 모든 숫자가 연속 6줄 창 안에 함께 있는가
    win = any(all(has_num("\n".join(lines[i:i + 6]), n) for n in nums) for i in range(max(1, len(lines)))) if nums else None
    return items, units, miss, win


# ───────── 행 검사 (--rows) ─────────
# [왜] 쪽 검사는 "이 숫자가 쪽에 있나"만 묻는다. 행 검사는 청크의 행 이름(PARAMETER·CONDITIONS·SYMBOL)으로
# PDF 표의 같은 행을 찾고, 그 행의 같은 열 칸 값과 비교한다. 판정 함수는 PDF를 모르고 칸 격자(grid)만 받는다.
# grid = 표 하나의 행 목록, 행 = 칸 글자 목록. 병합 칸은 어댑터가 풀어서 걸친 칸마다 같은 글자를 넣는다.
IDENT_HEADS = {"PARAMETER", "CONDITIONS", "TESTCONDITIONS", "SYMBOL", ""}  # 행 이름을 이루는 열 머리글
UNIT_HEADS = {"UNIT", "UNITS"}
MATCH_MIN = 0.9  # 행 이름 문자 구성 유사도(Dice) 하한


def _key(s):
    """공백·기호를 빼고 대문자로: 머리글·행 이름 비교용."""
    return re.sub(r"[\W_]+", "", norm(s or "")).upper()


def _canon(s):
    """칸 값 비교용: 공백·쉼표 제거, 유니코드 부호 정규화."""
    return re.sub(r"[\s,]+", "", norm(s or "")).lower()


def _dice(a, b):
    t = sum(a.values()) + sum(b.values())
    return 2 * sum((a & b).values()) / t if t else 0.0


def _ident_bag(cells):
    """연속으로 같은 글자(걸친 칸)는 한 번만 세고 문자 구성(Counter)으로 만든다.
    [주의] PDF 표는 아래첨자(`I = 3A, T = 25°C\\nF J`)를 줄 끝으로 보내므로 순서가 달라서 문자 구성으로 비교한다."""
    out, prev = [], None
    for c in cells:
        if c and c != prev: out.append(c)
        prev = c
    return collections.Counter(_key("".join(out)))


def chunk_cells(text):
    """청크 본문 -> (행 이름 글자 목록, [(열 이름, 값)], 단위 또는 None)."""
    ident, vals, unit = [], [], None
    for k, v in fields(text):
        ku = _key(k)
        if ku in ("PARAMETER", "CONDITIONS", "SYMBOL"): ident.append(v)
        elif ku == "UNIT": unit = v
        else: vals.append((k.strip(), v))
    return ident, vals, unit


def grid_layout(grid):
    """머리글 행(PARAMETER 칸이 있는 행)을 찾아 (머리글 행 번호, 열별 머리글)을 돌려준다. 없으면 None."""
    for i, row in enumerate(grid):
        if any(_key(c) == "PARAMETER" for c in row): return i, [_key(c) for c in row]
    return None


def _row_ident(row, heads):
    return [c for c, h in zip(row, heads) if h in IDENT_HEADS]


def _label(row, heads):
    return re.sub(r"\s+", " ", " ".join(dict.fromkeys(c for c in _row_ident(row, heads) if c))).strip()[:70]


def _col_for(key, heads):
    """청크 열 이름에 대응하는 열 번호. 정확히 같거나(공백·기호 무시) 품번 열 머리글이 접두·접미로 갈라진 경우."""
    k = _key(key)
    cols = [j for j, h in enumerate(heads) if h and h not in IDENT_HEADS | UNIT_HEADS]
    for j in cols:
        if heads[j] == k: return j
    part = [j for j in cols if len(heads[j]) >= 3 and (heads[j].endswith(k) or k.endswith(heads[j]))]
    return part[0] if len(part) == 1 else None


def _compare(row, heads, vals, unit, grid, hi, ri):
    """한 후보 행에서 청크 값·단위를 같은 열 칸과 비교. (불일치 목록, 확인 못 한 항목 목록, 확인한 칸 수)."""
    bad, unchecked, n = [], [], 0
    for k, v in vals:
        j = _col_for(k, heads)
        if j is None:
            unchecked.append(f"col {k}"); continue
        n += 1
        if _canon(row[j]) != _canon(v):
            bad.append({"field": k, "chunk": v, "pdf": row[j], "found_elsewhere": _where(grid, hi, heads, ri, j, v)})
    if unit is not None:
        uj = next((j for j, h in enumerate(heads) if h in UNIT_HEADS), None)
        if uj is None or not row[uj].strip(): unchecked.append("unit(PDF 칸 없음)")
        else:
            n += 1
            if _canon(row[uj]) != _canon(unit):
                bad.append({"field": "UNIT", "chunk": unit, "pdf": row[uj], "found_elsewhere": _where(grid, hi, heads, ri, uj, unit)})
    return bad, unchecked, n


def _where(grid, hi, heads, ri, cj, value, cap=3):
    """청크 값이 이 표의 다른 칸에 있는지(원인 진단용): 같은 행 다른 열 / 다른 행 같은 열 / 다른 행 다른 열."""
    out, v = [], _canon(value)
    for i in range(hi + 1, len(grid)):
        for j, c in enumerate(grid[i]):
            if heads[j] in IDENT_HEADS or (i, j) == (ri, cj) or _canon(c) != v: continue
            kind = "같은 행 다른 열" if i == ri else "다른 행 같은 열" if j == cj else "다른 행 다른 열"
            out.append({"kind": kind, "row": _label(grid[i], heads), "col": heads[j]})
    return sorted(out, key=lambda x: x["kind"] != "다른 행 같은 열")[:cap]


def row_check(text, grids):
    """행 검사: 청크의 행 이름으로 `grids` 안의 같은 행을 찾아 같은 열 칸 값과 비교한다.
    status: ok(찾았고 전부 같음) / row_mismatch(찾았고 다른 칸 있음) / unlocated(행을 못 찾음·여럿이라 판단 보류 = 미확인).
    [주의] unlocated와 unchecked는 일치로 세지 않는다."""
    ident, vals, unit = chunk_cells(text)
    want = _ident_bag(ident)
    if not vals: return {"status": "unlocated", "reason": "값 칸 없음"}
    # [주의] 부품 한 개당 한 행인 표(`Device: P6SMB100A | ... / Min: 95`)는 행 이름 칸이 없어 여기서는 unlocated로 둔다(11-16 결과 유지). 그 표는 part_check가 본다.
    if not ident: return {"status": "unlocated", "reason": "행 이름 칸(PARAMETER·CONDITIONS·SYMBOL) 없음: 부품 행(Device) 표 형식은 미지원"}
    best, tables = [], 0
    for gi, grid in enumerate(grids):
        lay = grid_layout(grid)
        if not lay: continue
        tables += 1
        hi, heads = lay
        for ri in range(hi + 1, len(grid)):
            row = grid[ri]
            if len(row) != len(heads): continue
            sc = _dice(want, _ident_bag(_row_ident(row, heads)))
            if sc >= MATCH_MIN: best.append((sc, gi, ri))
    if not tables: return {"status": "unlocated", "reason": "PARAMETER 머리글이 있는 표를 못 찾음"}
    if not best: return {"status": "unlocated", "reason": "행 이름이 같은 행 없음"}
    top = max(b[0] for b in best)
    cands = [b for b in best if b[0] >= top - 1e-9]
    if top < 1 - 1e-9:
        # [왜] 0.9 이상이면 가장 가까운 행에 붙여 값만 비교하던 허점: 조건 숫자가 바뀐 청크(`TJ = 125°C` -> `TJ = 6°C`)가 통과했다.
        # 행 이름이 정확히 같은 행이 없으면 일치로 세지 않고 가장 가까운 행을 적어 표시한다.
        near = [_label(grids[gi][ri], grid_layout(grids[gi])[1]) for _, gi, ri in cands[:3]]
        return {"status": "row_mismatch", "name_score": round(top, 3), "checked": 0, "unchecked": [],
                "mismatch": [{"field": "행 이름", "chunk": " | ".join(ident), "pdf": " / ".join(near), "found_elsewhere": []}]}
    res = []
    for sc, gi, ri in cands:
        hi, heads = grid_layout(grids[gi])
        res.append((gi, ri) + _compare(grids[gi][ri], heads, vals, unit, grids[gi], hi, ri))
    states = {bool(r[2]) for r in res}
    if len(states) > 1: return {"status": "unlocated", "reason": f"같은 이름의 행 {len(cands)}개가 갈림(일부만 일치)"}
    gi, ri, bad, unchecked, n = res[0]
    if not n: return {"status": "unlocated", "reason": "비교할 열을 못 찾음", "unchecked": unchecked}
    return {"status": "row_mismatch" if bad else "ok", "table": gi, "row": ri, "same_name_rows": len(cands), "name_score": round(top, 3),
            "checked": n, "unchecked": unchecked, "mismatch": bad}


def page_tables(page):
    """pdfplumber 표 -> [(표 테두리 bbox, 칸 격자)]. 병합 칸(None)은 그 칸 자리를 덮는 칸의 글자로 채운다(가로·세로 병합 모두 좌표로 판단).
    (11-16 `--rows`의 page_grids를 각주 검사용 bbox까지 돌려주게 바꾼 것. 격자 계산은 같다.)"""
    out = []
    for t in page.find_tables():
        data, rows = t.extract(), t.rows
        cells = [(bb, data[r][c] or "") for r, row in enumerate(rows) for c, bb in enumerate(row.cells) if bb]
        if not cells: continue
        xs = sorted({bb[0] for bb, _ in cells}); ys = sorted({bb[1] for bb, _ in cells})
        x_end = max(bb[2] for bb, _ in cells); y_end = max(bb[3] for bb, _ in cells)
        xc = [(x + (xs[i + 1] if i + 1 < len(xs) else x_end)) / 2 for i, x in enumerate(xs)]
        yc = [(y + (ys[i + 1] if i + 1 < len(ys) else y_end)) / 2 for i, y in enumerate(ys)]
        grid = []
        for y in yc:
            grid.append([next((txt for bb, txt in cells if bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]), "") for x in xc])
        out.append((t.bbox, grid))
    return out


# ───────── 부품 행 검사 (--notes, part_check) ─────────
# [왜] 부품 한 개당 한 행인 표(`Device: P6SMB100A | ... / Min: 95`)는 행 이름 칸이 없어 row_check가 unlocated로 남겼다(11-16 6건).
# 첫 열 칸이 청크의 품번과 정확히 같은 행을 찾고, 여러 줄 머리글을 열마다 위에서 아래로 이어 청크의 열 이름과 맞춘다.
PART_VAL = re.compile(r"^[-+]?\d[\d.,]*$|^-$")  # 값 칸 하나(숫자 또는 빈 값 표시 '-')


def _bag(s):
    """열 이름 문자 구성. [주의] PDF는 아래첨자를 줄 끝으로 보내(`V (V)\\nBR` vs `VBR (V)`) 순서가 달라서 구성으로 비교한다."""
    return collections.Counter(_key(s))


def part_layout(grid):
    """부품 행 표 -> (첫 데이터 행 번호, 열별 머리글 이름). 데이터 행 = 첫 칸에 숫자가 있고 다른 칸에 값이 있는 첫 행. 없으면 None."""
    d0 = next((i for i, r in enumerate(grid) if re.search(r"\d", r[0]) and any(PART_VAL.match(c.strip()) for c in r[1:])), None)
    heads = [r for r in grid[:d0 or 0] if len(set(r)) > 1]  # [왜] 모든 칸이 같은 행은 표 제목(가로 병합)이라 머리글에서 뺀다
    if not heads: return None
    labels = []
    for j in range(len(grid[d0])):
        col = [h[j] for k, h in enumerate(heads) if h[j] and (k == 0 or h[j] != heads[k - 1][j])]  # 세로 병합(같은 글자 반복)은 한 번만
        labels.append(" / ".join(re.sub(r"\s+", " ", c).strip() for c in col))
    return d0, labels


def part_check(text, grids):
    """부품 행 검사: 청크 첫 칸 값(품번)과 첫 열이 정확히 같은 행을 찾아 머리글 이름이 같은 열의 칸 값과 비교한다.
    status는 row_check와 같은 뜻(ok / row_mismatch / unlocated). 행 이름 칸(PARAMETER 등)이 있는 청크는 None(row_check 몫)."""
    fs = fields(text)
    if any(_key(k) in ("PARAMETER", "CONDITIONS", "SYMBOL") for k, _ in fs): return None
    part, vals = fs[0][1], fs[1:]
    found = [(gi, ri) for gi, g in enumerate(grids) for lay in [part_layout(g)] if lay
             for ri in range(lay[0], len(g)) if _canon(g[ri][0]) == _canon(part)]
    if not found: return {"status": "unlocated", "reason": "첫 열이 품번과 같은 행 없음"}
    res = []
    for gi, ri in found:
        grid = grids[gi]
        d0, labels = part_layout(grid)
        heads = ["PARAMETER"] + labels[1:]  # _where·_label이 첫 열(품번)을 행 이름으로 보게 한다
        bad, unchecked, n = [], [], 0
        for k, v in vals:
            js = [j for j in range(1, len(labels)) if _bag(labels[j]) == _bag(k)]
            if len(js) != 1:  # [주의] 못 찾았거나 이름이 같은 열이 둘 이상이면 일치로 세지 않는다
                unchecked.append(f"col {k}"); continue
            n += 1
            if _canon(grid[ri][js[0]]) != _canon(v):
                bad.append({"field": k, "chunk": v, "pdf": grid[ri][js[0]], "found_elsewhere": _where(grid, d0 - 1, heads, ri, js[0], v)})
        res.append((gi, ri, bad, unchecked, n))
    if len({bool(r[2]) for r in res}) > 1: return {"status": "unlocated", "reason": f"품번이 같은 행 {len(res)}개가 갈림(일부만 일치)"}
    gi, ri, bad, unchecked, n = res[0]
    if not n: return {"status": "unlocated", "reason": "비교할 열을 못 찾음", "unchecked": unchecked}
    return {"status": "row_mismatch" if bad else "ok", "table": gi, "row": ri, "same_part_rows": len(res),
            "checked": n, "unchecked": unchecked, "mismatch": bad}


def part_mutants(text, grid, ri):
    """부품 행 청크의 숫자 값 칸 하나를 바꾼 가짜 청크 {다른행: 다른 품번 행의 같은 열 값, 다른열: 같은 행의 다른 열 값}. 원래 값과 같으면 뺀다."""
    d0, labels = part_layout(grid)
    out = {"다른행": [], "다른열": []}
    for k, v in fields(text)[1:]:
        js = [j for j in range(1, len(labels)) if _bag(labels[j]) == _bag(k)]
        if len(js) != 1 or not NUM.search(v): continue
        swap = lambda new: text.replace(f" | {k}: {v}", f" | {k}: {new}", 1)
        out["다른행"] += [swap(grid[i][js[0]]) for i in range(d0, len(grid)) if i != ri and NUM.search(grid[i][js[0]]) and _canon(grid[i][js[0]]) != _canon(v)]
        out["다른열"] += [swap(grid[ri][j]) for j in range(1, len(labels)) if j != js[0] and NUM.search(grid[ri][j]) and _canon(grid[ri][j]) != _canon(v)]
    return out


# ───────── 각주 검사 (--notes, note_check) ─────────
# [왜] 표 아래 각주(측정 조건 "Pulse test with PW = 0.3ms", 실장 조건 "Units mounted on PCB")가 행에 안 붙으면 값의 조건을 잃는다.
# 청커와 따로, PDF에서 (1) 그 표 바로 아래 각주 묶음과 (2) 표 칸의 각주 표시를 읽어 청크에 붙어야 할 각주를 정한다.
# [주의] 청커의 NOTE_HEAD(`^notes?`)를 다시 쓰지 않는다: "Thermal Performance Note:"처럼 앞말이 붙은 머리를 받아야 한다.
NOTE_HEAD = re.compile(r"^(?:[A-Za-z][A-Za-z ]{0,40}\s)?notes?\s*(?:([1-9])\s*)?(?:[:：]\s*(.*))?$", re.I)  # "Notes:", "Thermal Performance Note:", "Note 1 : …"
NOTE_ITEM = re.compile(r"^(?:\(?([1-9])[.)]\s|notes?\s*([1-9])\s*[:：]|(\*))\s*(.*)$", re.I)  # "1. …", "(2) …", "Note 2 : …", "* …"
MARK = re.compile(r"\((?:note\s*)?([1-9])\)|\bnotes?\s*([1-9])\b", re.I)  # 칸 안 표시 "(1)", "(Note 1)", "Note 1"
NOTE_GAP = 20   # 각주 줄 사이 상한(pt). [왜] 각주 줄 간격은 약 14pt, 그보다 크게 떨어진 줄(바닥글 "Version:")은 다른 글
NOTE_SUB = 8    # 앞 줄과 이보다 가까운 줄은 아래첨자 조각(`BR T T`, 앞 줄과 약 4.4pt)이라 건너뛴다
NOTE_HIT, NOTE_MISS = 0.9, 0.3  # 각주 낱말 중 청크 `주:`에 있는 비율: 0.9 이상 있음, 0.3 이하 없음, 그 사이는 판단 보류


def parse_notes(lines):
    """표 바로 아래 줄 목록 [{top, x0, text}] -> 각주 [(번호 또는 None, 글)]. 첫 줄이 각주 머리가 아니면 []."""
    if not lines: return []
    h = NOTE_HEAD.match(norm(lines[0]["text"]).strip())
    if not h: return []
    notes = [[h.group(1), h.group(2)]] if h.group(2) else []  # 머리 줄 안의 각주("Notes: Units mounted …", "Note 1: …")
    margin, prev = lines[0]["x0"], lines[0]["top"]
    for ln in lines[1:]:
        if ln["top"] - prev < NOTE_SUB: continue
        if ln["top"] - prev > NOTE_GAP: break
        prev, t = ln["top"], norm(ln["text"]).strip()
        m = NOTE_ITEM.match(t)
        if m: notes.append([m.group(1) or m.group(2) or m.group(3), m.group(4)])
        elif ln["x0"] > margin + 3 and notes: notes[-1][1] += " " + t  # 들여 쓴 줄은 앞 각주가 이어지는 줄
        else: break  # [왜] 들여 쓰지 않은 번호 없는 줄은 새 글("Devices for Bipolar Applications" 아래 1.·2.가 또 나온다, 1.5KE)
    return [(n, t) for n, t in notes]


def page_notes(page, boxes):
    """쪽의 표마다 바로 아래 각주 목록. 표 bottom과 그 아래 다음 표 top 사이에서 표 밖 줄만 본다(표 아래 첫 줄이 머리여야 함)."""
    lines = [ln for ln in page.extract_text_lines() if not any(b[1] <= ln["top"] < b[3] for b in boxes)]
    out = []
    for b in boxes:
        nxt = min([c[1] for c in boxes if c[1] >= b[3]] or [page.height])
        out.append(parse_notes([ln for ln in lines if b[3] <= ln["top"] < nxt]))
    return out


def _tokens(s):
    """각주 비교 낱말: 세 글자 이상 글자 묶음과 숫자. [왜] 아래첨자가 갈라 놓은 짧은 조각(V·BR·T)은 PDF와 청크가 다르게 붙어 뺀다."""
    return set(re.findall(r"[^\W\d_]{3,}|\d+(?:\.\d+)?", norm(s).lower()))


def note_check(text, grid, hi, ri, notes):
    """각주 검사: 머리글(0~hi행)과 ri행 칸의 각주 표시, 표 바로 아래 각주 `notes`로 이 청크에 붙어야 할 각주를 정하고 청크 `주:` 글과 대조한다.
    status: none(표 아래 각주 없음) / unmarked(표에 표시가 있으나 이 행·머리글엔 없음) / attached / missing / unclear(판단 보류).
    [주의] 표에 표시가 하나도 없으면 표 아래 각주 전부를 모든 행의 것으로 본다. 표시한 번호가 표 아래에 없으면 unclear."""
    marks = lambda cells: {a or b for c in cells for a, b in MARK.findall(c)} | ({"*"} if any("*" in c for c in cells) else set())
    want = sorted(marks([c for r in grid[:hi + 1] + [grid[ri]] for c in r]))
    table = marks([c for r in grid for c in r])
    if not notes:
        return {"status": "unclear", "reason": "표시한 각주가 이 쪽 표 바로 아래에 없음", "marks": want} if want else {"status": "none", "reason": "표 아래 각주 없음"}
    nums = [n for n, _ in notes]
    unref = [n for n in dict.fromkeys(nums) if n not in table]  # 표 어디에서도 가리키지 않는 각주(기록만, 판정에 안 씀)
    if table and not want: return {"status": "unmarked", "reason": "이 행·머리글에 각주 표시 없음", "unreferenced": unref}
    use = [(n, t) for n, t in notes if n in want] if table else notes
    have = _tokens(text.split("\n주:", 1)[1] if "\n주:" in text else "")
    got = []
    for n, t in use:
        w = _tokens(t)
        got.append({"no": n, "coverage": round(len(w & have) / len(w), 3) if w else None, "text": t[:90]})
    lost = [m for m in want if m not in nums] if table else []
    if any(g["coverage"] is not None and g["coverage"] <= NOTE_MISS for g in got): st = "missing"
    elif lost or any(g["coverage"] is None or g["coverage"] < NOTE_HIT for g in got): st = "unclear"
    else: st = "attached"
    out = {"status": st, "marks": want, "notes": got}
    if lost: out["marks_without_note"] = lost
    if table: out["unreferenced"] = unref
    return out


def mutation_control(res, sample, pdfs, grids_of, seed):
    """변이 시험(실제 표본): 행 검사가 `ok`로 찾은 청크마다 값 하나를 (a) 같은 표 다른 행의 같은 열 칸 값, (b) 같은 행 다른 열 칸 값으로
    바꾼 가짜 청크를 만들어 쪽 검사 · 6줄 창 · 행 검사가 잡는지 센다. 원래 칸과 같은 값으로 바꾸는 경우는 변이로 세지 않는다."""
    rng, ctl = random.Random(seed), collections.Counter()
    for x, r in zip(res, sample):
        rc = x["row_check"]
        if rc["status"] != "ok": continue
        grids = grids_of(r["doc"], r["page"])
        hi, heads = grid_layout(grids[rc["table"]])
        grid, ri = grids[rc["table"]], rc["row"]
        _, vals, _ = chunk_cells(r["text"])
        pool = {"다른행": [], "다른열": []}  # (열 이름, 원래 값, 바꿀 값)
        for k, v in vals:
            j = _col_for(k, heads)
            if j is None or not NUM.search(v): continue
            for i in range(hi + 1, len(grid)):
                if i != ri and len(grid[i]) == len(heads) and NUM.search(grid[i][j]) and _canon(grid[i][j]) != _canon(v): pool["다른행"].append((k, v, grid[i][j]))
            for j2, h in enumerate(heads):
                if j2 != j and h and h not in IDENT_HEADS | UNIT_HEADS and NUM.search(grid[ri][j2]) and _canon(grid[ri][j2]) != _canon(v): pool["다른열"].append((k, v, grid[ri][j2]))
        lines = page_lines(pdfs[r["doc"]], r["page"])
        for kind, cands in pool.items():
            if not cands: ctl[f"{kind}_변이불가"] += 1; continue
            k, v, new = rng.choice(cands)
            mut = r["text"].replace(f" | {k}: {v}", f" | {k}: {new}", 1)
            if mut == r["text"]: continue
            _, _, miss, win = page_check(mut, lines)
            st = row_check(mut, grids)["status"]
            ctl[f"{kind}_시도"] += 1
            ctl[f"{kind}_쪽검사_탐지"] += bool(miss)
            ctl[f"{kind}_6줄창_탐지"] += win is False  # 쪽 검사가 잡은 것도 포함(창은 쪽보다 엄격)
            ctl[f"{kind}_행검사_탐지"] += st == "row_mismatch"
            ctl[f"{kind}_행검사_놓침"] += st == "ok"
            ctl[f"{kind}_행검사_미확인"] += st == "unlocated"
    return dict(sorted(ctl.items()))


def note_fields(text, grids, notes, rc):
    """(part_check, note_check, 찾은 표 번호). 각주 검사의 표·행은 row_check(행 이름) 또는 part_check(품번)가 찾은 것을 쓴다."""
    pc = part_check(text, grids)
    loc = rc if "table" in rc else pc if pc and "table" in pc else None
    if loc is None: return pc, {"status": "unclear", "reason": "표에서 행을 못 찾음"}, None
    g = grids[loc["table"]]
    hi = grid_layout(g)[0] if loc is rc else part_layout(g)[0] - 1  # 머리글 마지막 행
    return pc, note_check(text, g, hi, loc["row"], notes[loc["table"]]), loc["table"]


def notes_control(res, sample, pdfs, grids_of, notes_of):
    """실제 표본 변이 시험: (a) part_check가 ok인 청크의 숫자 값 칸 하나를 다른 품번 행의 같은 열 값·같은 행 다른 열 값으로 바꾼 청크 전부,
    (b) note_check가 attached인 청크에서 `주:` 글을 지운 청크를 만들어 쪽 검사·부품 행 검사·각주 검사가 잡는지 센다."""
    ctl = collections.Counter()
    for x, r in zip(res, sample):
        grids, notes, pc = grids_of(r["doc"], r["page"]), notes_of(r["doc"], r["page"]), x["part_check"]
        if pc and pc["status"] == "ok":
            lines = page_lines(pdfs[r["doc"]], r["page"])
            for kind, ms in part_mutants(r["text"], grids[pc["table"]], pc["row"]).items():
                for m in ms:
                    ctl[f"부품행_{kind}_시도"] += 1
                    ctl[f"부품행_{kind}_쪽검사_탐지"] += bool(page_check(m, lines)[2])
                    ctl[f"부품행_{kind}_부품행검사_탐지"] += part_check(m, grids)["status"] == "row_mismatch"
        if x["note_check"]["status"] == "attached":
            ctl["각주지움_시도"] += 1
            ctl["각주지움_" + note_fields(r["text"].split("\n주:")[0], grids, notes, x["row_check"])[1]["status"]] += 1
    return dict(sorted(ctl.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1116)
    ap.add_argument("--per-cell", type=int, default=3)
    ap.add_argument("--rows", action="store_true", help="행 검사 추가(row_check 필드, 변이 시험). 출력 폴더 기본값은 OUT_ROWS")
    ap.add_argument("--notes", action="store_true", help="--rows에 부품 행 검사(part_check)·각주 검사(note_check) 추가. 출력 폴더 기본값은 OUT_NOTES")
    ap.add_argument("--out", type=Path, default=None, help="결과 폴더(기본: 옵션 없으면 기존 폴더, --rows는 OUT_ROWS, --notes는 OUT_NOTES)")
    a = ap.parse_args()
    a.rows = a.rows or a.notes
    out_dir = a.out or (OUT_NOTES if a.notes else OUT_ROWS if a.rows else OUT)
    # [주의] 지난 결과 폴더는 덮어쓰지 않는다: --rows는 OUT, --notes는 OUT과 OUT_ROWS를 막는다
    if a.rows and out_dir.resolve() in {OUT.resolve()} | ({OUT_ROWS.resolve()} if a.notes else set()): sys.exit("기존 결과 폴더는 덮어쓰지 않는다: --out을 다른 폴더로")
    rows = [json.loads(l) for l in open(CHUNKS)]
    tsv = {}
    for l in list(open(TSV))[1:]:
        d, i, h = l.rstrip("\n").split("\t"); tsv[(d, int(i))] = h
    assert len(rows) == 51967 and all(hashlib.sha256(r["text"].encode()).hexdigest() == tsv[(r["doc"], r["idx"])] for r in rows), "chunks != accepted hash list"
    cells = collections.defaultdict(list)
    for r in rows:
        t = ttype(r["table"]) if r["kind"] == "table_row" and r["page"] else None
        if t and any(c[0] == "num" for c in checks(r["text"])[0]):
            cells[(r["category"], t)].append(r)
    rng = random.Random(a.seed)
    sample = []
    for key in sorted(cells):
        c = sorted(cells[key], key=lambda r: (r["doc"], r["idx"]))
        sample += rng.sample(c, min(a.per_cell, len(c)))
    pdfs, res, grid_cache = {}, [], {}

    def tables_of(doc, page):  # 같은 쪽의 표(격자, 표마다 바로 아래 각주)는 한 번만 읽는다
        if (doc, page) not in grid_cache:
            pg = pdfs[doc].pages[page - 1]
            tabs = page_tables(pg)
            grid_cache[(doc, page)] = ([g for _, g in tabs], page_notes(pg, [b for b, _ in tabs]) if a.notes else None)
        return grid_cache[(doc, page)]

    grids_of = lambda doc, page: tables_of(doc, page)[0]
    notes_of = lambda doc, page: tables_of(doc, page)[1]

    for r in sample:
        pdf = pdfs.get(r["doc"]) or pdfs.setdefault(r["doc"], pdfplumber.open(PDFDIR / r["doc"]))
        lines = page_lines(pdf, r["page"])
        items, units, miss, win = page_check(r["text"], lines)
        other = [p for p in range(1, len(pdf.pages) + 1) if p != r["page"] and not miss] or None
        if miss:
            other = [p for p in range(1, len(pdf.pages) + 1) if p != r["page"] and all(has_num("\n".join(page_lines(pdf, p)), v) for k, v in items if k == "num")] or None
        res.append({"doc": r["doc"], "idx": r["idx"], "category": r["category"], "table_type": ttype(r["table"]),
                    "page": r["page"], "row": r["row"], "text": r["text"], "values_checked": [f"{k} {v}" for k, v in items] + [f"unit {u}" for u in units],
                    "result": "mismatch" if miss else "match", "row_window_ok": win, "mismatch": miss, "found_on_other_pages": other if miss else None})
        if a.rows: res[-1]["row_check"] = row_check(r["text"], grids_of(r["doc"], r["page"]))
        if a.notes:  # 새 필드는 기존 필드 뒤에만 더한다(기존 필드 바이트 비교용)
            grids, notes = grids_of(r["doc"], r["page"]), notes_of(r["doc"], r["page"])
            pc, nc, ti = note_fields(r["text"], grids, notes, res[-1]["row_check"])
            nc["page"] = r["page"]
            owners = ["".join(dict.fromkeys(grids[i][0])).split("\n")[0][:60] for i, n in enumerate(notes) if n and i != ti]  # 표 제목(첫 행, 갈라진 칸 'O'+'RDERING…'을 이음)
            if owners and nc["status"] in ("none", "unclear"): nc["notes_under_other_tables"] = owners  # 같은 쪽 다른 표의 각주(잘못 나눴는지 보려고)
            res[-1]["part_check"], res[-1]["note_check"] = pc, nc
    # 음성 대조: 각 청크의 첫 숫자를 끝자리 +1로 바꾸면 쪽 수준/창 수준에서 잡히는가(검사기 민감도)
    ctl = collections.Counter()
    for x, r in zip(res, sample):
        nums = [v for k, v in checks(r["text"])[0] if k == "num" and "." not in v and "-" not in v]
        if x["result"] != "match" or not nums: continue
        bad = str(int(nums[0]) + 1) if nums[0][-1] != "9" else str(int(nums[0]) - 1)
        lines = page_lines(pdfs[r["doc"]], r["page"])
        others = [n for n in nums[1:]]
        ctl["tried"] += 1
        ctl["page_caught"] += not has_num("\n".join(lines), bad)
        ctl["window_caught"] += not any(all(has_num("\n".join(lines[i:i + 6]), n) for n in [bad] + others) for i in range(len(lines)))
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "results.jsonl", "w") as f:
        for x in res: f.write(json.dumps(x, ensure_ascii=False) + "\n")
    s = {"seed": a.seed, "per_cell": a.per_cell, "n": len(res), "match": sum(x["result"] == "match" for x in res),
         "mismatch": sum(x["result"] == "mismatch" for x in res), "match_but_window_fail": sum(x["result"] == "match" and x["row_window_ok"] is False for x in res),
         "by_type": collections.Counter(x["table_type"] for x in res), "n_categories": len({x["category"] for x in res}), "n_docs": len({x["doc"] for x in res}), "negative_control": ctl}
    if a.rows:
        st = collections.Counter(x["row_check"]["status"] for x in res)
        s["row_check"] = {"ok": st["ok"], "row_mismatch": st["row_mismatch"], "unlocated": st["unlocated"],
                          "unlocated_by_reason": collections.Counter(x["row_check"]["reason"] for x in res if x["row_check"]["status"] == "unlocated"),
                          "unlocated_by_type": collections.Counter(x["table_type"] for x in res if x["row_check"]["status"] == "unlocated"),
                          "with_unchecked": sum(bool(x["row_check"].get("unchecked")) for x in res if x["row_check"]["status"] != "unlocated"),
                          "mutation_control": mutation_control(res, sample, pdfs, grids_of, a.seed)}
    if a.notes:
        ps = collections.Counter(x["part_check"]["status"] for x in res if x["part_check"])
        s["part_check"] = {"applicable": sum(ps.values()), "ok": ps["ok"], "row_mismatch": ps["row_mismatch"], "unlocated": ps["unlocated"]}
        s["note_check"] = {"by_status": collections.Counter(x["note_check"]["status"] for x in res),
                           "by_type": {t: collections.Counter(x["note_check"]["status"] for x in res if x["table_type"] == t) for t in sorted({x["table_type"] for x in res})},
                           "by_reason": collections.Counter(x["note_check"]["reason"] for x in res if "reason" in x["note_check"]),
                           "mutation_control": notes_control(res, sample, pdfs, grids_of, notes_of)}
    (out_dir / "summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))
    print(s)


if __name__ == "__main__":
    main()
