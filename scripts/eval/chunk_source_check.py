"""표/수치 청크 vs 원본 PDF 쪽 텍스트 직접 대조 (읽기 전용, 네트워크 없음).

실행: .venv/bin/python scripts/eval/chunk_source_check.py [--seed 1116] [--per-cell 3]
입력: ../corpus/tsc/chunks-v4h/chunks.jsonl (본문, sha256을 chunk_sha256.tsv와 대조), ../corpus/tsc/pdf/*.pdf
출력: evals/results/d10/chunk_source_check/results.jsonl, summary.json
"""
import argparse, collections, hashlib, json, random, re
from pathlib import Path
import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
CHUNKS = ROOT.parent / "corpus/tsc/chunks-v4h/chunks.jsonl"
PDFDIR = ROOT.parent / "corpus/tsc/pdf"
TSV = ROOT / "evals/results/chunking/v4h-2026-11-08/chunk_sha256.tsv"
OUT = ROOT / "evals/results/d10/chunk_source_check"
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1116)
    ap.add_argument("--per-cell", type=int, default=3)
    a = ap.parse_args()
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
    pdfs, res = {}, []
    for r in sample:
        pdf = pdfs.get(r["doc"]) or pdfs.setdefault(r["doc"], pdfplumber.open(PDFDIR / r["doc"]))
        items, units = checks(r["text"])
        lines = page_lines(pdf, r["page"])
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
        other = [p for p in range(1, len(pdf.pages) + 1) if p != r["page"] and not miss] or None
        if miss:
            other = [p for p in range(1, len(pdf.pages) + 1) if p != r["page"] and all(has_num("\n".join(page_lines(pdf, p)), v) for k, v in items if k == "num")] or None
        res.append({"doc": r["doc"], "idx": r["idx"], "category": r["category"], "table_type": ttype(r["table"]),
                    "page": r["page"], "row": r["row"], "text": r["text"], "values_checked": [f"{k} {v}" for k, v in items] + [f"unit {u}" for u in units],
                    "result": "mismatch" if miss else "match", "row_window_ok": win, "mismatch": miss, "found_on_other_pages": other if miss else None})
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
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "results.jsonl", "w") as f:
        for x in res: f.write(json.dumps(x, ensure_ascii=False) + "\n")
    s = {"seed": a.seed, "per_cell": a.per_cell, "n": len(res), "match": sum(x["result"] == "match" for x in res),
         "mismatch": sum(x["result"] == "mismatch" for x in res), "match_but_window_fail": sum(x["result"] == "match" and x["row_window_ok"] is False for x in res),
         "by_type": collections.Counter(x["table_type"] for x in res), "n_categories": len({x["category"] for x in res}), "n_docs": len({x["doc"] for x in res}), "negative_control": ctl}
    (OUT / "summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))
    print(s)


if __name__ == "__main__":
    main()
