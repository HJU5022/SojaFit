"""chunk_source_check 행 검사(`row_check`)·부품 행 검사(`part_check`)·각주 검사(`note_check`)의 변이 시험. PDF·DB·네트워크 없이 합성 표 격자만 쓴다.

확인하는 것: 값 하나를 같은 쪽 다른 행 값 / 같은 행 다른 열 값 / 다른 행 단위로 바꾼 청크를 기존 쪽 검사(`page_check`)는
전부 통과시키고 행 검사는 전부 잡는다. 부품 행 표(첫 열 = 품번)도 같은 변이를 부품 행 검사가 전부 잡는다.
각주 글을 지운 청크는 각주 검사가 `missing`으로 잡는다. 깨끗한 청크는 막지 않는다. 행을 못 찾으면 일치가 아니라 미확인이다.
하지 않는 것: pdfplumber 어댑터(`page_tables`·`page_notes`) 시험(원본 PDF가 저장소 밖이라 실제 표본 재실행으로 확인한다).
각주 줄 해석(`parse_notes`)은 실제 PDF 줄 위치를 옮겨 적은 합성 줄로 시험한다.
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


def cond_mutants():
    """CONDITIONS의 숫자 하나를 같은 쪽에 있는 다른 숫자로 바꿔, 그런 조건의 행이 표에 없게 된 청크만 모은다.
    쪽 검사는 바뀐 숫자가 쪽 어딘가에 있어 통과한다(예: `TJ = 6°C`는 `IF = 6A`의 6 때문에 통과)."""
    page_nums = sorted({n for _, n in (x for t in CLEAN for x in C.checks(t)[0]) if True} | {"2", "4.0", "6", "3", "25", "125"})
    row_bags = [C._ident_bag(C._row_ident(r, C.grid_layout(g)[1])) for g in GRIDS for r in g[C.grid_layout(g)[0] + 1:]]
    out = []
    for t in CLEAN[:7] + CLEAN[7:]:
        for k, v in C.fields(t):
            if C._key(k) != "CONDITIONS": continue
            for m in C.NUM.finditer(v):
                for n in page_nums:
                    nv = v[:m.start(2)] + n + v[m.end(2):]
                    if nv == v: continue
                    mt = t.replace(f" | {k}: {v}", f" | {k}: {nv}", 1)
                    ident, _, _ = C.chunk_cells(mt)
                    if C._ident_bag(ident) not in row_bags and not old_caught(mt): out.append(mt)
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


def test_condition_number_that_matches_no_row_is_flagged():
    # 행 이름 유사도가 0.9 이상이면 가장 가까운 행으로 붙잡아 값만 비교하던 허점: `TJ = 125°C` -> `TJ = 6°C`처럼 그런 조건의 행이 없는데도 통과했다.
    ms = cond_mutants()
    assert len(ms) >= 20
    assert sum(old_caught(m) for m in ms) == 0
    st = [new_status(m) for m in ms]
    assert st.count("row_mismatch") == len(ms), {s: st.count(s) for s in set(st)}


# ───────── 부품 행 표(part_check) ─────────
# P6SMB SERIES 3쪽 ELECTRICAL 표와 같은 모양: 제목 행, 두 줄 머리글(가로·세로 병합, 아래첨자는 줄 끝), 첫 열 = 품번. 값은 일부 지어냄.
PART = [
    ["ELECTRICAL SPECIFICATIONS (T = 25°C unless otherwise noted)\nA"] * 7,
    ["Device", "Device\nMarking\nCode", "Breakdown\nVoltage\nV (V)\nBR\n(Note 1)", "Breakdown\nVoltage\nV (V)\nBR\n(Note 1)",
     "Test\nCurrent\nI (mA)\nT", "Stand-Off\nVoltage\nV\nWM\n(V)", "Maximum\nPeak Pulse\nCurrent\nI (A)\nPPM\n(Note 2)"],
    ["Device", "Device\nMarking\nCode", "Min", "Max", "Test\nCurrent\nI (mA)\nT", "Stand-Off\nVoltage\nV\nWM\n(V)", "Maximum\nPeak Pulse\nCurrent\nI (A)\nPPM\n(Note 2)"],
    ["P6SMB91", "MTJ", "81.9", "100", "1.0", "73.7", "4.7"],
    ["P6SMB91A", "MUJ", "86.5", "95.5", "1.0", "77.8", "4.9"],
    ["P6SMB100", "MVJ", "90.0", "110", "1.0", "81.0", "4.3"],
    ["P6SMB100A", "MXJ", "95", "105", "1.0", "85.5", "4.5"],
]
PART_LINES = page_lines([PART])
PART_NOTE = "\n주: 1. VBR measure after IT applied for 30ms, IT = square wave pulse or equivalent. 2. Surge current waveform per Fig.3 and derate per Fig.2."


def part_text(row, note=PART_NOTE):
    d, mk, mn, mx, it, vwm, ipp = row
    return ("[P6SMB SERIES_Q2209.pdf · 3쪽 · ELECTRICAL SPECIFICATIONS (TA = 25°C unless otherwise noted)] "
            f"Device: {d} | Device Marking Code: {mk} | Breakdown Voltage VBR (V) (Note 1) / Min: {mn} | Breakdown Voltage VBR (V) (Note 1) / Max: {mx} | "
            f"Test Current IT (mA): {it} | Stand-Off Voltage VWM (V): {vwm} | Maximum Peak Pulse Current IPPM(A) (Note 2): {ipp}" + note)


PART_CLEAN = [part_text(r) for r in PART[3:]]


def test_part_clean_chunks_are_ok():
    # 깨끗한 부품 행 청크 4개: 쪽 검사도 부품 행 검사도 막지 않는다. 행 이름 칸이 없어 row_check는 여전히 unlocated(기존 동작 그대로).
    for t in PART_CLEAN:
        assert not C.page_check(t, PART_LINES)[2]
        pc = C.part_check(t, [PART])
        assert pc["status"] == "ok" and pc["checked"] == 6 and not pc["unchecked"], (t, pc)
        assert C.row_check(t, [PART])["status"] == "unlocated"
    assert C.part_check(PART_CLEAN[3], [PART])["row"] == 6  # P6SMB100A는 P6SMB100 행(5)과 헷갈리지 않는다(정확히 같은 품번만)


def test_part_value_from_other_part_row_or_column_is_flagged():
    # 값 하나를 다른 품번 행의 같은 열 값 / 같은 행 다른 열 값으로 바꾼 변이: 쪽 검사는 전부 통과, 부품 행 검사는 전부 잡는다.
    ms = {"다른행": [], "다른열": []}
    for ri, t in zip(range(3, 7), PART_CLEAN):
        for k, v in C.part_mutants(t, PART, ri).items(): ms[k] += v
    assert len(ms["다른행"]) >= 40 and len(ms["다른열"]) >= 60
    for kind in ms:
        assert sum(bool(C.page_check(m, PART_LINES)[2]) for m in ms[kind]) == 0
        st = [C.part_check(m, [PART])["status"] for m in ms[kind]]
        assert st.count("row_mismatch") == len(ms[kind]), (kind, {s: st.count(s) for s in set(st)})


def test_part_mismatch_names_where_the_value_came_from():
    # P6SMB100A의 Min 95를 P6SMB100 행의 Min 90.0으로 바꾸면 "다른 행 같은 열", Min·Max를 맞바꾸면 "같은 행 다른 열".
    other_row = C.part_check(part_text(["P6SMB100A", "MXJ", "90.0", "105", "1.0", "85.5", "4.5"]), [PART])
    swapped = C.part_check(part_text(["P6SMB100A", "MXJ", "105", "95", "1.0", "85.5", "4.5"]), [PART])
    assert other_row["status"] == "row_mismatch" and other_row["mismatch"][0]["pdf"] == "95"
    assert other_row["mismatch"][0]["found_elsewhere"][0] == {"kind": "다른 행 같은 열", "row": "P6SMB100", "col": C.part_layout(PART)[1][2]}
    assert {m["field"].split(" / ")[-1] for m in swapped["mismatch"]} == {"Min", "Max"}
    assert swapped["mismatch"][0]["found_elsewhere"][0]["kind"] == "같은 행 다른 열"


def test_part_unknown_part_or_column_is_not_a_match():
    assert C.part_check(part_text(["P6SMB120A", "MZJ", "114", "126", "1.0", "102", "3.7"]), [PART])["status"] == "unlocated"
    assert C.part_check(PART_CLEAN[0], [])["status"] == "unlocated"  # 표가 없는 쪽
    assert C.part_check(CLEAN[0], GRIDS) is None  # 행 이름 칸이 있는 청크는 row_check 몫
    odd = PART_CLEAN[0].replace("Test Current IT (mA)", "Test Voltage VT (V)")  # PDF 머리글에 없는 열 이름
    pc = C.part_check(odd, [PART])
    assert pc["status"] == "ok" and pc["checked"] == 5 and pc["unchecked"] == ["col Test Voltage VT (V)"]  # 확인 못 한 칸은 일치로 세지 않고 따로 적는다


# ───────── 각주(parse_notes · note_check) ─────────
def ln(top, x0, text):
    return {"top": top, "x0": x0, "text": text}


# P6SMB 3쪽 표 바로 아래 줄(위치는 pdfplumber `extract_text_lines` 값을 옮겨 적음). 아래첨자 조각 줄과 바닥글이 섞여 있다.
P6_LINES = [ln(608.3, 35.5, "Notes:"), ln(621.8, 35.5, "1. V measure after I applied for 30ms, I = square wave pulse or equivalent."),
            ln(626.2, 70.6, "BR T T"), ln(635.9, 35.5, "2. Surge current waveform per Fig.3 and derate per Fig.2."),
            ln(649.9, 35.5, "3. For bipolar types having V of 10V and under, the I limit is doubled."), ln(654.2, 179.9, "WM D"),
            ln(663.8, 35.5, "4. For bidirectional use C or CA suffix for types P6SMB6.8 - P6SMB220A."), ln(806.3, 297.5, "3 Version: Q2209")]
P6_NOTES = C.parse_notes(P6_LINES)


def test_parse_notes_reads_heads_items_and_stops():
    assert [n for n, _ in P6_NOTES] == ["1", "2", "3", "4"]  # 아래첨자 조각(BR T T)은 건너뛰고 바닥글(Version)에서 멈춤
    assert P6_NOTES[0][1].startswith("V measure after I applied")
    # 앞말이 붙은 머리, 머리 줄 안의 각주(BAS316WS·HS2DFL)
    assert C.parse_notes([ln(185.2, 42.6, "Thermal Performance Note: Units mounted on PCB (5mm x 5mm Cu pad test board)")]) == [(None, "Units mounted on PCB (5mm x 5mm Cu pad test board)")]
    assert C.parse_notes([ln(150.3, 42.6, "Thermal Performance Note:"), ln(164.4, 42.6, "1. Device mounted on an FR4 Printed-Circuit Board (PCB)")]) == [("1", "Device mounted on an FR4 Printed-Circuit Board (PCB)")]
    # "Note 1 : …" 줄마다 번호(BAV19W)
    bav = C.parse_notes([ln(793.6, 70.7, "Note 1 : Test condition : I = 100μA"), ln(798.2, 181.3, "R"), ln(809.2, 70.7, "Note 2 : Test condition : BAV19W @ V =100V")])
    assert [n for n, _ in bav] == ["1", "2"]
    # 들여 쓴 줄은 앞 각주에 잇고(AZ23C), 들여 쓰지 않은 번호 없는 줄에서 멈춘다(1.5KE "Devices for Bipolar Applications" 아래 1.·2.)
    az = C.parse_notes([ln(690.8, 42.6, "Notes:"), ln(732.4, 42.6, "3. For detailed information on price between the"), ln(746.4, 60.6, "shownand tighter voltage tolerances")])
    assert az == []  # 머리와 첫 각주 사이가 NOTE_GAP(20pt)보다 멀면 그 줄은 각주가 아니다
    az = C.parse_notes([ln(718.4, 42.6, "Notes:"), ln(732.4, 42.6, "3. For detailed information on price between the"), ln(746.4, 60.6, "shownand tighter voltage tolerances")])
    assert az == [("3", "For detailed information on price between the shownand tighter voltage tolerances")]
    ke = C.parse_notes([ln(681.6, 42.6, "Notes:"), ln(695.2, 42.6, "1. Non-repetitive Current Pulse"), ln(709.2, 42.6, "2. Mounted on Copper Pad"),
                        ln(723.0, 42.6, "Devices for Bipolar Applications"), ln(737.0, 42.6, "1. For bidirectional use C or CA suffix")])
    assert [n for n, _ in ke] == ["1", "2"]
    # 표 아래 첫 줄이 각주 머리가 아니면 각주 없음
    assert C.parse_notes([ln(280.0, 48.0, "APPLICATIONS"), ln(296.0, 48.0, "Notes:")]) == [] and C.parse_notes([]) == []


def test_part_rows_notes_attached_and_removed_text_is_missing():
    # 머리글의 (Note 1)·(Note 2) 표시는 모든 행에 해당한다. 각주 3·4는 표 어디에서도 가리키지 않아 기록만 한다.
    hi = C.part_layout(PART)[0] - 1
    for ri, t in zip(range(3, 7), PART_CLEAN):
        nc = C.note_check(t, PART, hi, ri, P6_NOTES)
        assert nc["status"] == "attached" and nc["marks"] == ["1", "2"] and nc["unreferenced"] == ["3", "4"], nc
        assert C.note_check(t.split("\n주:")[0], PART, hi, ri, P6_NOTES)["status"] == "missing"  # 각주 글을 지움
        one = t.split(" 2. Surge")[0]  # 각주 2만 지움
        assert C.note_check(one, PART, hi, ri, P6_NOTES)["status"] == "missing"


ELEC_NOTES = [("1", "Pulse test with PW = 0.3ms"), ("2", "Pulse test with PW = 30ms")]
NOTE_OF = {"(1)": "\n주: 1. Pulse test with PW = 0.3ms", "(2)": "\n주: 2. Pulse test with PW = 30ms"}


def elec_noted():
    """ELEC 깨끗한 청크에 청커처럼 표시한 각주를 붙인 것: (청크, 행 번호)."""
    out = []
    for c in ELEC_CHUNKS:
        t = elec_text(*c) + next((v for k, v in NOTE_OF.items() if k in c[0]), "")
        out.append((t, C.row_check(t, GRIDS)["row"]))
    return out


def test_marked_rows_attached_unmarked_row_and_note_mutations():
    # 행 이름 칸의 (1)·(2) 표시만 그 행에 해당. 표시 없는 행(접합 용량)은 unmarked. 지우면 missing, 다른 각주 글로 바꾸면 attached가 아니다.
    st = {"attached": 0, "unmarked": 0, "removed_missing": 0, "swapped_not_attached": 0}
    for t, ri in elec_noted():
        nc = C.note_check(t, ELEC, 1, ri, ELEC_NOTES)
        st[nc["status"]] += 1
        if nc["status"] != "attached": continue
        st["removed_missing"] += C.note_check(t.split("\n주:")[0], ELEC, 1, ri, ELEC_NOTES)["status"] == "missing"
        other = t.replace("0.3ms", "@@").replace("30ms", "0.3ms").replace("@@", "30ms").replace("주: 1.", "주: X.").replace("주: 2.", "주: 1.").replace("주: X.", "주: 2.")
        st["swapped_not_attached"] += C.note_check(other, ELEC, 1, ri, ELEC_NOTES)["status"] != "attached"
    assert st == {"attached": 6, "unmarked": 1, "removed_missing": 6, "swapped_not_attached": 6}


THERM = [["THERMAL PERFORMANCE"] * 4, ["PARAMETER", "SYMBOL", "TYP", "UNIT"],
         ["Junction-to-ambient thermal resistance(1)", "R\nӨJA", "357", "°C/W"]]
THERM_NOTE = [("1", "Device mounted on an FR4 Printed-Circuit Board (PCB), single-sided copper, tin-plated and standard footprint")]
THERM_TEXT = "[BAW56H_A2412.pdf · 2쪽 · THERMAL PERFORMANCE] PARAMETER: Junction-to-ambient thermal resistance(1) | SYMBOL: RӨJA | TYP: 357 | UNIT: °C/W"


def test_thermal_note_under_table_and_empty_cases():
    # BAW56H 2쪽 모양: 표 바로 아래 "Thermal Performance Note:" 1. … 를 청크가 안 담으면 missing, 담으면 attached.
    assert C.note_check(THERM_TEXT, THERM, 1, 2, THERM_NOTE)["status"] == "missing"
    assert C.note_check(THERM_TEXT + "\n주: " + THERM_NOTE[0][1], THERM, 1, 2, THERM_NOTE)["status"] == "attached"
    # 표시 없는 표 + 번호 없는 각주(HS2DFL 모양): 표 아래 각주 전부가 모든 행의 것
    plain = [r[:] for r in THERM]; plain[2][0] = "Junction-to-ambient thermal resistance"
    unit_note = [(None, "Units mounted on PCB (5mm x 5mm Cu pad test board)")]
    assert C.note_check(THERM_TEXT, plain, 1, 2, unit_note)["status"] == "missing"
    assert C.note_check(THERM_TEXT + "\n주: Units mounted on PCB (5mm x 5mm Cu pad test board)", plain, 1, 2, unit_note)["status"] == "attached"
    # 표 아래 각주 없음: 표시도 없으면 none, 표시가 있으면 각주가 다른 쪽·다른 표에 있을 수 있어 unclear(판단 보류)
    assert C.note_check(THERM_TEXT, plain, 1, 2, [])["status"] == "none"
    nc = C.note_check(THERM_TEXT, THERM, 1, 2, [])
    assert nc["status"] == "unclear" and nc["marks"] == ["1"]
    # 표시한 번호의 각주가 표 아래에 없으면(다음 쪽으로 넘어간 각주 2, TUAU10DH) unclear
    nc = C.note_check(THERM_TEXT.replace("(1)", "(2)"), THERM[:2] + [[THERM[2][0].replace("(1)", "(2)")] + THERM[2][1:]], 1, 2, THERM_NOTE)
    assert nc["status"] == "unclear" and nc["marks_without_note"] == ["2"]


def test_clean_chunks_never_missing():
    # 오탐 0: 각주를 제대로 담은 깨끗한 청크(부품 행 4 + ELEC 7 + THERM 1)는 missing·unclear가 되지 않는다.
    hi = C.part_layout(PART)[0] - 1
    got = [C.note_check(t, PART, hi, ri, P6_NOTES)["status"] for ri, t in zip(range(3, 7), PART_CLEAN)]
    got += [C.note_check(t, ELEC, 1, ri, ELEC_NOTES)["status"] for t, ri in elec_noted()]
    got.append(C.note_check(THERM_TEXT + "\n주: 1. " + THERM_NOTE[0][1], THERM, 1, 2, THERM_NOTE)["status"])
    assert set(got) <= {"attached", "unmarked"} and len(got) == 12
