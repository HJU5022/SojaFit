"""chunk_source_check 행 검사(`row_check`)의 변이 시험. PDF·DB·네트워크 없이 합성 표 격자만 쓴다.

확인하는 것: 값 하나를 같은 쪽 다른 행 값 / 같은 행 다른 열 값 / 다른 행 단위로 바꾼 청크를 기존 쪽 검사(`page_check`)는
전부 통과시키고 행 검사는 전부 잡는다. 깨끗한 청크는 막지 않는다. 행을 못 찾으면 일치가 아니라 미확인이다.
하지 않는 것: pdfplumber 어댑터(`page_grids`) 시험(원본 PDF가 저장소 밖이라 실제 표본 재실행으로 확인한다).
"""
from scripts.eval import chunk_source_check as C

# TBS606 SERIES 2쪽 ELECTRICAL 표와 같은 모양. 병합 칸은 어댑터가 풀어 놓은 결과(걸친 행마다 같은 글자)로 적었다.
# 아래첨자는 줄 끝으로 간다(`V\nF`, `I = 3A, T = 25°C\nF J`).
ELEC = [
    ["ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)"] * 8,
    ["PARAMETER", "", "CONDITIONS", "SYMBOL", "TYP", "MAX", "UNIT", ""],
    ["Forward voltage per diode(1)", "", "I = 3A, T = 25°C\nF J", "V\nF", "0.90", "-", "V", ""],
    ["Forward voltage per diode(1)", "", "I = 6A, T = 25°C\nF J", "V\nF", "0.96", "1.00", "V", ""],
    ["Forward voltage per diode(1)", "", "I = 3A, T = 125°C\nF J", "V\nF", "0.79", "-", "V", ""],
    ["Forward voltage per diode(1)", "", "I = 6A, T = 125°C\nF J", "V\nF", "0.86", "0.96", "V", ""],
    ["Reverse current @ rated V per diode(2)\nR", "", "T = 25°C\nJ", "I\nR", "-", "2", "µA", ""],
    ["Reverse current @ rated V per diode(2)\nR", "", "T = 125°C\nJ", "I\nR", "-", "200", "µA", ""],
    ["Junction capacitance per diode", "", "1MHz, V = 4.0V\nR", "C\nJ", "51", "-", "pF", ""],
]
ELEC_CHUNKS = [  # (PARAMETER, CONDITIONS, SYMBOL, TYP, MAX, UNIT)
    ("Forward voltage per diode(1)", "IF = 3A,TJ = 25°C", "VF", "0.90", "-", "V"),
    ("Forward voltage per diode(1)", "IF = 6A,TJ = 25°C", "VF", "0.96", "1.00", "V"),
    ("Forward voltage per diode(1)", "IF = 3A,TJ = 125°C", "VF", "0.79", "-", "V"),
    ("Forward voltage per diode(1)", "IF = 6A,TJ = 125°C", "VF", "0.86", "0.96", "V"),
    ("Reverse current @ rated VR per diode(2)", "TJ = 25°C", "IR", "-", "2", "µA"),
    ("Reverse current @ rated VR per diode(2)", "TJ = 125°C", "IR", "-", "200", "µA"),
    ("Junction capacitance per diode", "1MHz, VR = 4.0V", "CJ", "51", "-", "pF"),
]
# ABS15J SERIES 1쪽 ABSOLUTE MAXIMUM RATINGS 표와 같은 모양(품번 열 2개, 가로·세로 병합).
RATE = [
    ["ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)"] * 7,
    ["PARAMETER", "", "", "SYMBOL", "ABS15J", "ABS15M", "UNIT"],
    ["Repetitive peak reverse voltage", "", "", "V\nRRM", "600", "1000", "V"],
    ["Reverse voltage, total rms value", "", "", "V\nR(RMS)", "420", "700", "V"],
    ["Forward current", "On glass-epoxy", "", "I\nF", "1.5", "1.5", "A"],
    ["Forward current", "On aluminum substrate", "", "I\nF", "2.0", "2.0", "A"],
    ["Rating for fusing (t<8.3ms)", "", "", "I2t", "6.64", "6.64", "A2s"],
]
RATE_CHUNKS = [  # (PARAMETER 목록, SYMBOL, ABS15J, ABS15M, UNIT)
    (["Repetitive peak reverse voltage"], "VRRM", "600", "1000", "V"),
    (["Reverse voltage, total rms value"], "VR(RMS)", "420", "700", "V"),
    (["Forward current", "On glass-epoxy"], "IF", "1.5", "1.5", "A"),
    (["Forward current", "On aluminum substrate"], "IF", "2.0", "2.0", "A"),
    (["Rating for fusing (t<8.3ms)"], "I2t", "6.64", "6.64", "A2s"),
]
GRIDS = [ELEC, RATE]
HEAD = "[X.pdf · 2쪽 · ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)] "


def elec_text(p, c, s, typ, mx, u):
    return HEAD + f"PARAMETER: {p} | CONDITIONS: {c} | SYMBOL: {s} | TYP: {typ} | MAX: {mx} | UNIT: {u}"


def rate_text(ps, s, a, b, u):
    return HEAD + " | ".join(f"PARAMETER: {p}" for p in ps) + f" | SYMBOL: {s} | ABS15J: {a} | ABS15M: {b} | UNIT: {u}"


def page_lines(grids):
    """합성 표를 쪽 텍스트처럼 편 줄 목록(칸을 공백으로 이어 한 줄, 걸친 칸의 반복은 한 번만)."""
    out = []
    for g in grids:
        for row in g:
            cells = [c.replace("\n", " ") for i, c in enumerate(row) if c and (i == 0 or c != row[i - 1])]
            out.append(C.norm(" ".join(cells)))
    return out


LINES = page_lines(GRIDS)
CLEAN = [elec_text(*c) for c in ELEC_CHUNKS] + [rate_text(*c) for c in RATE_CHUNKS]


def old_caught(text):
    return bool(C.page_check(text, LINES)[2])


def new_status(text):
    return C.row_check(text, GRIDS)["status"]


def mutants(kind):
    """값 칸 하나를 바꾼 가짜 청크 목록: kind = row(같은 열 다른 행 값) | col(같은 행 다른 열 값) | unit(다른 행 단위)."""
    out = []
    for text in CLEAN:
        ident, vals, unit = C.chunk_cells(text)
        pool = {"row": {}, "col": {}}
        # 같은 쪽 모든 표의 값 칸을 (열 이름, 행 번호, 값)으로 모은다
        for g in GRIDS:
            hi, heads = C.grid_layout(g)
            for ri in range(hi + 1, len(g)):
                for j, h in enumerate(heads):
                    if h and h not in C.IDENT_HEADS | C.UNIT_HEADS: pool["row"].setdefault(h, []).append((ri, g[ri][j], g[ri]))
        for k, v in vals:
            if not C.NUM.search(v): continue
            col = C._key(k)
            same_row = next(r for ri, val, r in pool["row"][col] if C._canon(val) == C._canon(v) and C._ident_bag(C._row_ident(r, C.grid_layout(ELEC if col in ("TYP", "MAX") else RATE)[1])) == C._ident_bag(ident))
            if kind == "row":
                news = {val for _, val, r in pool["row"][col] if r is not same_row and C.NUM.search(val) and C._canon(val) != C._canon(v)}
            elif kind == "col":
                heads = C.grid_layout(ELEC if col in ("TYP", "MAX") else RATE)[1]
                news = {same_row[j] for j, h in enumerate(heads) if h and h != col and h not in C.IDENT_HEADS | C.UNIT_HEADS
                        and C.NUM.search(same_row[j]) and C._canon(same_row[j]) != C._canon(v)}
            else:
                continue
            out += [text.replace(f" | {k}: {v}", f" | {k}: {n}", 1) for n in sorted(news)]
        if kind == "unit":
            units = {u for g in GRIDS for r in g[2:] for u in [r[C.grid_layout(g)[1].index("UNIT")]] if u and C._canon(u) != C._canon(unit)}
            out += [text.replace(f" | UNIT: {unit}", f" | UNIT: {u}", 1) for u in sorted(units)]
    return out


def test_clean_chunks_pass_both_checks():
    # 깨끗한 청크 12개: 쪽 검사도 행 검사도 막지 않는다(오탐 0). 행 검사는 값·단위 칸을 실제로 비교했다(미확인 아님).
    assert len(CLEAN) == 12
    for t in CLEAN:
        assert not old_caught(t), t
        rc = C.row_check(t, GRIDS)
        assert rc["status"] == "ok" and rc["checked"] >= 2 and not rc["unchecked"], (t, rc)


def test_other_row_value_passes_page_check_but_row_check_flags():
    ms = mutants("row")
    assert len(ms) >= 40
    assert sum(old_caught(m) for m in ms) == 0  # 쪽 검사: 바뀐 값이 같은 쪽 다른 행에 있어 전부 통과
    assert [new_status(m) for m in ms].count("row_mismatch") == len(ms)  # 행 검사: 전부 잡음


def test_other_column_value_in_same_row_is_flagged():
    ms = mutants("col")
    assert len(ms) >= 6  # TYP<->MAX, 품번 열 사이(ABS15J<->ABS15M은 값이 다른 행만)
    assert sum(old_caught(m) for m in ms) == 0
    assert [new_status(m) for m in ms].count("row_mismatch") == len(ms)


def test_other_row_unit_is_flagged():
    ms = mutants("unit")
    assert len(ms) >= 20
    assert sum(old_caught(m) for m in ms) == 0  # 단위 문자열이 쪽에 있으니 쪽 검사는 통과
    assert [new_status(m) for m in ms].count("row_mismatch") == len(ms)


def test_mismatch_details_name_where_the_value_came_from():
    # IF=6A,TJ=25°C 행의 TYP 0.96을 IF=3A,TJ=125°C 행의 값 0.79로 바꾸면 "다른 행 같은 열", MAX 1.00과 맞바꾸면 "같은 행 다른 열".
    base = ELEC_CHUNKS[1]
    other_row = C.row_check(elec_text(base[0], base[1], base[2], "0.79", base[4], base[5]), GRIDS)
    other_col = C.row_check(elec_text(base[0], base[1], base[2], "1.00", "0.96", base[5]), GRIDS)
    assert other_row["mismatch"][0]["pdf"] == "0.96" and other_row["mismatch"][0]["found_elsewhere"][0]["kind"] == "다른 행 같은 열"
    assert {m["field"] for m in other_col["mismatch"]} == {"TYP", "MAX"}
    assert other_col["mismatch"][0]["found_elsewhere"][0]["kind"] == "같은 행 다른 열"


def test_merged_part_column_is_checked_by_geometry_result():
    # ABS15M의 1.5는 PDF에서 ABS15J 칸에서 이어진 병합 칸(풀린 격자에서 같은 글자). 알맞은 값은 통과, 다른 행 값(2.0)은 잡는다.
    ok = rate_text(["Forward current", "On glass-epoxy"], "IF", "1.5", "1.5", "A")
    bad = rate_text(["Forward current", "On glass-epoxy"], "IF", "1.5", "2.0", "A")
    assert new_status(ok) == "ok" and new_status(bad) == "row_mismatch"
    assert not old_caught(bad)


def test_unknown_row_or_layout_is_unlocated_not_match():
    wrong_name = elec_text("Total power dissipation", "TJ = 25°C", "PD", "0.90", "-", "W")
    device_row = HEAD + "Device: P6SMB100A | Device Marking Code: MXJ | Breakdown Voltage VBR (V) / Min: 95 | Test Current IT (mA): 1.0"
    assert C.row_check(wrong_name, GRIDS)["status"] == "unlocated"
    assert C.row_check(device_row, GRIDS)["status"] == "unlocated"
    assert C.row_check(CLEAN[0], [])["status"] == "unlocated"  # 표가 하나도 없는 쪽
