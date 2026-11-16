"""동결 v3 50문항을 격리한 Codex CLI에 문항마다 따로 묻고 원본 로그를 남긴다. 채점은 tally_codex_v3.py가 한다.

- 하는 일: 문항마다 빈 작업 폴더를 만들고 그 문항의 넷리스트만 `circuit.net`으로 넣은 뒤 `codex exec`를 부른다.
  우리 서비스가 받는 입력(회로 넷리스트 · 대상 · 사용 조건 · 질문)과 같게 하고, 관련/비관련 표지는 주지 않는다.
- 격리: 새 CODEX_HOME(로그인 파일 auth.json 링크 하나만), `--ignore-user-config --ignore-rules --ephemeral`, 메모리 기능 끔,
  읽기 전용 샌드박스, 웹 검색 켬. 저장소 · 위키 · Codex 메모리를 입력으로 주지 않는다(로그의 명령 목록으로 사후 확인).
- 하지 않는 일: 채점, 정답 파일 읽기(입력은 evals/guides/v3_50_codex_paste.md의 문항 글만), 우리 서비스 호출.
- 근거: 강사 11/16 코멘트 ① "Codex 원본 로그와 같은 입력 조건의 재비교가 없습니다", 사전 등록 2026-11-16 Codex 격리 재비교.

실행(저장소 루트): uv run --no-sync python scripts/eval/run_codex_v3_isolated.py --work <임시 폴더> [--jobs 5]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PASTE = ROOT / "evals/guides/v3_50_codex_paste.md"
OUT = ROOT / "evals/results/graph/2026-11-16-codex-v3-50-isolated"
MODEL = "gpt-6-astra"  # [왜] 조장이 평소 쓰는 Codex 모델. 사용자 설정을 끄므로 명시한다

RULES = """아래 질문 하나에 답해 주세요.

규칙:
- 입력은 아래 글과 이 작업 폴더의 파일뿐이다. 이 폴더 밖의 파일은 읽지 않는다.
- 데이터시트 · 제조사 자료가 필요하면 웹 검색으로 찾는다. 찾지 못하면 추측이라고 밝히거나 모른다고 답한다.
- 관련 없는 질문이면 거절 · 범위 밖이라고 답해도 된다.
- 출력은 정확히 두 줄이다. 줄바꿈 없이:
- 결론: (한두 문장)
- 근거: (수치 · 조건 · 출처 URL)
"""


def blocks():
    """문항 글을 {id: (본문, 넷리스트 경로 또는 None)}으로 읽는다. 머리의 (relevant · …) 표지는 버린다."""
    text = PASTE.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"^## (v3-\d+)[^\n]*\n(.*?)(?=^---$|\Z)", text, re.M | re.S):
        body = m[2].strip()
        net = re.search(r"^넷리스트: (\S+)$", body, re.M)
        if net:
            # [왜] 저장소 경로를 주면 저장소 구조가 드러난다. 작업 폴더의 파일 이름으로 바꾼다
            body = body.replace(net[0], "넷리스트: ./circuit.net (이 작업 폴더에 있는 KiCad 넷리스트 파일)")
        out[m[1]] = (body, net[1] if net else None)
    assert len(out) == 50, len(out)
    return out


def run_one(qid, body, net, work, home):
    """한 문항: 빈 폴더 + circuit.net, codex exec --json. 원본 이벤트와 마지막 답을 OUT/raw에 쓴다."""
    d = work / qid
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    if net:
        shutil.copyfile(ROOT / net, d / "circuit.net")
    raw = OUT / "raw"
    cmd = ["codex", "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral", "--skip-git-repo-check",
           "-s", "read-only", "-C", str(d), "-c", "web_search=live", "--disable", "memories", "-m", MODEL,
           "--json", "-o", str(raw / f"{qid}.answer.md"), RULES + "\n" + body]
    t0 = time.time()
    with open(raw / f"{qid}.events.jsonl", "w", encoding="utf-8") as ev, open(raw / f"{qid}.stderr.txt", "w", encoding="utf-8") as er:
        # [주의] 문항당 10분 상한. 넘으면 그 문항은 답 없음으로 남기고 다시 돌리지 않는다
        try:
            code = subprocess.run(cmd, cwd=d, env={**os.environ, "CODEX_HOME": str(home)}, stdin=subprocess.DEVNULL,
                                  stdout=ev, stderr=er, timeout=600).returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
    return {"id": qid, "exit": code, "seconds": round(time.time() - t0, 1), "netlist": net}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path, required=True, help="문항별 빈 작업 폴더를 만들 임시 폴더(저장소 밖)")
    ap.add_argument("--jobs", type=int, default=5)
    ap.add_argument("--only", nargs="*", help="이 id만(시험용)")
    a = ap.parse_args()
    assert ROOT not in a.work.resolve().parents, "작업 폴더는 저장소 밖이어야 한다"
    home = a.work / "codex_home"
    home.mkdir(parents=True, exist_ok=True)
    if not (home / "auth.json").exists():
        (home / "auth.json").symlink_to(Path.home() / ".codex/auth.json")  # 로그인만 쓰고 설정 · AGENTS.md · 메모리는 쓰지 않는다
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    qs = blocks()
    ids = a.only or sorted(qs)
    with ThreadPoolExecutor(a.jobs) as pool:
        runs = list(pool.map(lambda q: run_one(q, *qs[q], a.work / "q", home), ids))
    ver = subprocess.run(["codex", "--version"], capture_output=True, text=True).stdout.strip()
    # [왜] --only로 일부만 다시 돌리면(예: 사용량 한도로 시작 못 한 문항) 앞 실행 기록은 두고 그 id만 바꾼다. 바뀐 id는 attempts에 남긴다
    old = json.loads((OUT / "runs.json").read_text(encoding="utf-8")) if (OUT / "runs.json").exists() else {"runs": [], "attempts": []}
    keep = [r for r in old["runs"] if r["id"] not in {r["id"] for r in runs}]
    attempts = old.get("attempts", []) + [r for r in old["runs"] if r["id"] in {r["id"] for r in runs}]
    merged = {"codex": ver, "model": MODEL, "runs": sorted(keep + runs, key=lambda r: r["id"]), "attempts": attempts}
    (OUT / "runs.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"done": len(runs), "nonzero": [r for r in runs if r["exit"] != 0]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
