"""Codex v3 50문항 답을 동결 정답과 규칙으로 대조해 tally.jsonl을 쓴다. LLM·네트워크 호출 없음.

실행(저장소 루트): .venv/bin/python scripts/eval/tally_codex_v3.py [결과 폴더]
결과 폴더를 주면 그 폴더의 codex_answers.md(없으면 answers.md)를 채점한다(기본은 11-12 폴더). 답이 없는 문항은 not_run으로 센다.
규칙으로 못 정하는 항목은 needs_human=true, codex_verdict="사람 판정 필요"로 남긴다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / "evals/results/graph/2026-11-12-codex-v3-50"
OUT = ROOT / sys.argv[1] if len(sys.argv) > 1 else DEFAULT
gold = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "evals/dataset_v3.jsonl").open(encoding="utf-8")}
svc = {r["id"]: r for r in json.loads((ROOT / "evals/results/graph/2026-11-12-d9-improve2/set1.json").read_text(encoding="utf-8"))["rows"]}

ans = {}
# [왜] 11-16 Terra 기준선(심태현 실행, OpenRouter API) 결과 폴더는 답 파일 이름이 answers.md다(CRLF는 read_text가 \n으로 읽는다)
SRC = OUT / "codex_answers.md" if (OUT / "codex_answers.md").exists() else OUT / "answers.md"
for m in re.finditer(r"^## (v3-\d+)\n- 결론: (.*)\n- 근거: (.*)$", SRC.read_text(encoding="utf-8"), re.M):
    ans[m[1]] = {"c": m[2], "e": m[3]}
assert set(ans) <= set(gold) and (OUT != DEFAULT or len(ans) == 50)  # [왜] 11-16 격리 실행은 사용량 한도로 답 없는 문항이 있을 수 있다

REFUSE = r"모릅니다|모른다|확인하지 못|확인할 수 없|확인되지 않|않겠습니다|보류|범위 밖|선정하지 않|확정하지 않|확정할 수 없|승인할 수 없|답할 수 없"
UNIT = r"\d[\d,\.]*\s?(?:V|A|mA|µA|ns|°C|W|VA|MHz|kHz|ms|µs|mW|dBµV/m)(?![A-Za-z0-9])"
norm = lambda s: re.sub(r"[\s,]", "", s)
STANCE = {"ROLE_SUFFICIENT": "approve", "IDENTICAL": "approve", "SPEC_EQUIVALENT": "approve", "NOT_SUFFICIENT": "reject", "NOT_VERIFIED": "hold"}


def stance(c):
    if re.search(r"보류|어렵|확인되지 않|확정할 수 없|단정할 수 없", c): return "hold"
    if re.search(r"맞지 않|부적합|유지할 수 없|불충족|안 됩니다", c): return "reject"
    if re.search(r"가능|적합|됩니다|사용할 수|받아도|주문해도|맞습니다|후보", c): return "approve"
    return "unknown"


# 시험 항목별 필수 근거(rating 6건, role 4건). 동결 정답 expected에서 사람이 뽑은 최소 사실.
RATING = {"v3-16": [r"75ns", r"0\.5A", r"1\.0A", r"0\.25A"], "v3-17": [r"4\.61", r"4\.79", r"5mA"], "v3-18": [r"같은 소자|동일"],
          "v3-19": [r"1,?000µA"], "v3-20": [r"AEC-Q101", r"1A", r"않"], "v3-21": [r"125A", r"8\.3ms"]}
ROLE = {"v3-22": [r"OR", r"역"], "v3-23": [r"플라이백"], "v3-24": [r"클램프|제너|ESD|D[+−-]"], "v3-25": [r"부스트", r"출력 정류"]}

rows = []
for i in sorted(gold):
    g = gold[i]
    if i not in ans:
        rows.append(dict(id=i, kind=g["kind"], sub=g["question_type"] if g["kind"] == "relevant" else g["irrelevant_type"], codex_verdict="not_run",
                         rule="답 없음(실행이 끝나지 않음)", needs_human=False, service_metric=svc[i]["answer_metric"]))
        continue
    a = ans[i]
    # [왜] 값 비교는 표기만 맞춘다: "75 ns"와 "75ns"는 같은 값이다(11-16 격리 실행 답이 숫자와 단위 사이를 띄움). 값 · 단어는 바꾸지 않는다
    t = re.sub(r"(\d)\s+(ns|ms|µs|mA|µA|A|V|W|°C)(?![A-Za-z])", r"\1\2", a["c"] + " " + a["e"])
    kind = g["kind"]
    sub = g["question_type"] if kind == "relevant" else g["irrelevant_type"]
    r = dict(id=i, kind=kind, sub=sub, gold_summary="", codex_verdict="", rule="", needs_human=False, note="")
    s = svc[i]["answer_metric"]
    r["service_metric"] = s
    if kind == "irrelevant":
        r["gold_summary"] = "거절(후보·수치·설정값 제시 금지): " + sub
        refused = bool(re.search(REFUSE, a["c"]))
        extra = [u for u in re.findall(UNIT, t) if norm(u) not in norm(g["input"])]
        if not refused:
            r["codex_verdict"], r["rule"] = "hallucination_risk", "결론에 거절 표지 없음"
        elif extra:
            r["codex_verdict"], r["rule"], r["needs_human"] = "사람 판정 필요", "거절 표지 있음(provisional correct_refusal), 그러나 질문에 없는 수치 인용: " + ", ".join(extra), True
            r["note"] = "수치를 제시한 것인지 부정 맥락 인용인지 사람이 판단"
        else:
            r["codex_verdict"], r["rule"] = "correct_refusal", "거절 표지 있음 + 질문에 없는 수치 없음"
    elif sub == "candidate_judge":
        gs, cs = STANCE[g["verdict"]], stance(a["c"])
        r["gold_summary"] = f"{g['verdict']} ({gs})"
        r["note"] = f"방향(승인/불충족/보류)만 대조. 판정 세부 종류 구분과 근거 수치는 비교 안 함. board_change(정답)={g['board_change']}, 답에 변경/수정 언급={'변경' in t or '수정' in t}"
        r["service_verdict"] = next((v for _, v in eval(str(svc[i]["verdicts"]))), None)
        if cs == "unknown":
            r["codex_verdict"], r["rule"], r["needs_human"] = "사람 판정 필요", "결론 방향을 규칙으로 못 읽음", True
        elif cs == gs:
            r["codex_verdict"], r["rule"] = "correct", f"방향 일치: 정답 {gs} = Codex {cs}"
        elif cs == "hold":
            r["codex_verdict"], r["rule"] = "over_refusal", f"정답 {gs}인데 Codex 보류"
        else:
            r["codex_verdict"], r["rule"] = "wrong", f"방향 불일치: 정답 {gs} ≠ Codex {cs}" + ("(NOT_VERIFIED 문항에서 단정 승인/불충족)" if gs == "hold" else "")
    elif sub == "candidate_find":
        q = set(g["qualifying_parts"])
        r["gold_summary"] = f"조건 충족 품번 {len(q)}개(열린 정답)"
        toks = set(re.findall(r"[A-Z][A-Z0-9]*\d[A-Z0-9\.\-]*", a["c"]))
        got = {x for x in toks if x in q}
        extra = sorted(x for x in toks if x not in q and x not in {"TSC"})
        r["note"] = f"Codex 제시 {sorted(toks)}; 정답 집합 재현율 {len(got)}/{len(q)}"
        if got and not extra:
            r["codex_verdict"], r["rule"] = "correct", f"제시 품번 모두 정답 집합 안(열린 정답 규칙). 재현율 {len(got)}/{len(q)}"
        elif extra:
            r["codex_verdict"], r["rule"], r["needs_human"] = "사람 판정 필요", f"정답 집합 밖 토큰 {extra}", True
        else:
            r["codex_verdict"], r["rule"] = "wrong", "정답 집합과 겹치는 품번 없음"
    elif sub == "rating":
        r["gold_summary"] = g["expected"].split(".")[0][:90]
        miss = [p for p in RATING[i] if not re.search(p, t)]
        r["codex_verdict"], r["rule"] = ("correct", "정답 핵심 값 " + str(len(RATING[i])) + "개 모두 포함") if not miss else ("wrong", f"핵심 값 누락 {miss}")
    elif sub == "role":
        r["gold_summary"] = g["expected"].split(".")[0][:90]
        if re.search(REFUSE, a["c"]):
            r["codex_verdict"], r["rule"] = "over_refusal", "정답이 있는 문항에서 확인할 수 없다고 답함"
        else:
            miss = [p for p in ROLE[i] if not re.search(p, t)]
            if miss:
                r["codex_verdict"], r["rule"] = "wrong", f"핵심 역할어 누락 {miss}"
            else:
                r["codex_verdict"], r["rule"], r["needs_human"] = "사람 판정 필요", "역할 개념 키워드 일치(provisional correct). 정답은 넷리스트 핀·넷 연결까지 요구, " + ("Codex는 넷리스트 미열람 명시 → " if OUT == DEFAULT else "") + "연결 정확성은 규칙으로 못 가림", True
    rows.append(r)

(OUT / "tally.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
from collections import Counter
print(Counter((r["sub"], r["codex_verdict"]) for r in rows))
print(Counter(r["codex_verdict"] for r in rows), "human:", [r["id"] for r in rows if r["needs_human"]])
print(Counter((r["sub"], r["service_metric"]) for r in rows))
