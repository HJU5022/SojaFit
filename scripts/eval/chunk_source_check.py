"""표/수치 청크 vs 원본 PDF 쪽 텍스트 직접 대조 (읽기 전용, 네트워크 없음).

실행: uv run python scripts/eval/chunk_source_check.py [--seed 1116] [--per-cell 3] [--rows --out <폴더>]
입력: ../corpus/tsc/chunks-v4h/chunks.jsonl (본문, sha256을 chunk_sha256.tsv와 대조), ../corpus/tsc/pdf/*.pdf
출력: evals/results/d10/chunk_source_check/results.jsonl, summary.json (`--out`으로 폴더 변경)

두 검사:
- 쪽 검사(기본): 청크의 숫자·단위·품번 열이 그 쪽 텍스트에 있는가. 같은 쪽 다른 행의 값으로 바뀐 오류는 통과한다.
- 행 검사(`--rows`, row_check 필드 추가): 청크의 PARAMETER·CONDITIONS·SYMBOL로 PDF 표의 같은 행을 찾고,
  그 행에서 같은 열의 칸 값(TYP·MAX·VALUE·품번 열)과 UNIT이 청크와 같은지 본다. 기존 필드는 바뀌지 않는다.
하지 않는 것: 코퍼스·청커 수정, 표 각주 대조, 표 밖 글, 조건 칸 안의 숫자 순서 바꿈(문자 구성만 본다).
근거: evals/guides/preregister.md 2026-11-15 항목, 강사 11/13 코멘트(축 ②).
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
    body = body.split("\n주:")[0]  # 각주는 대상 아님(알려진 한계: 216표 각주 미부착)
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
    # shortcut: 부품 한 개당 한 행인 표(`Device: P6SMB100A | ... / Min: 95`)는 행 이름 칸이 없어 미지원. 쓰려면 Device 열을 행 이름으로 보고 두 줄 머리글을 합쳐 열을 대응시킨다.
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
    res = []
    for sc, gi, ri in cands:
        hi, heads = grid_layout(grids[gi])
        res.append((gi, ri) + _compare(grids[gi][ri], heads, vals, unit, grids[gi], hi, ri))
    states = {bool(r[2]) for r in res}
    if len(states) > 1: return {"status": "unlocated", "reason": f"같은 이름의 행 {len(cands)}개가 갈림(일부만 일치)"}
    gi, ri, bad, unchecked, n = res[0]
    if not n: return {"status": "unlocated", "reason": "비교할 열을 못 찾음", "unchecked": unchecked}
    return {"status": "row_mismatch" if bad else "ok", "table": gi, "row": ri, "same_name_rows": len(cands),
            "checked": n, "unchecked": unchecked, "mismatch": bad}


def page_grids(page):
    """pdfplumber 표 -> 칸 격자. 병합 칸(None)은 그 칸 자리를 덮는 칸의 글자로 채운다(가로·세로 병합 모두 좌표로 판단)."""
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
        out.append(grid)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1116)
    ap.add_argument("--per-cell", type=int, default=3)
    ap.add_argument("--rows", action="store_true", help="행 검사 추가(row_check 필드, 변이 시험). 출력 폴더 기본값은 OUT_ROWS")
    ap.add_argument("--out", type=Path, default=None, help="결과 폴더(기본: --rows 없으면 기존 폴더, 있으면 OUT_ROWS)")
    a = ap.parse_args()
    out_dir = a.out or (OUT_ROWS if a.rows else OUT)
    if out_dir.resolve() == OUT.resolve() and a.rows: sys.exit("기존 결과 폴더는 덮어쓰지 않는다: --out을 다른 폴더로")
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

    def grids_of(doc, page):  # 같은 쪽의 표 격자는 한 번만 만든다
        if (doc, page) not in grid_cache: grid_cache[(doc, page)] = page_grids(pdfs[doc].pages[page - 1])
        return grid_cache[(doc, page)]

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
    (out_dir / "summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))
    print(s)


if __name__ == "__main__":
    main()
