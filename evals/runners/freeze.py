"""평가셋을 동결한다: sha256, 건수, 관련/비관련 건수를 evals/FROZEN.json에 기록. 평가 담당이 손으로 돌린다.

- 역할: 동결한 평가셋이 동결 이후 한 글자라도 바뀌었는지 가린다(정답을 고쳐 점수를 맞추는 일을 막는다).
- 하지 않는 일: 평가셋 내용 검증·수정, 점수 측정. 측정 결과 파일은 만들지 않는다.
- 출처: ADR 0003(평가셋 v1 동결), evals/guides/dataset-guide.md "동결" 절, AGENTS.md 지킬 것 1. 같은 해시 검사는 tests/evals/test_frozen_evals.py도 한다.
- 입력: evals/ 아래 평가셋 jsonl 파일 이름. 줄마다 kind(relevant·irrelevant)가 있어야 건수가 맞게 센다.
- 쓰는 곳: evals/FROZEN.json(동결 기록, 이미 동결한 파일은 덮어쓰지 않는다).
- 필요한 것: 없음(키·DB·네트워크 불필요).

    uv run python evals/runners/freeze.py dataset_v1.jsonl   # 동결
    uv run python evals/runners/freeze.py --check            # 동결 이후 바뀐 파일이 있으면 실패
"""
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

EVALS = Path(__file__).resolve().parents[1]
FROZEN = EVALS / "FROZEN.json"


def _stats(path: Path) -> dict:
    """평가셋 파일의 sha256·건수·관련/비관련 건수를 dict로 돌려준다."""
    # [주의] 해시는 줄 수가 아니라 파일 바이트 전체로 구한다. 공백 한 칸만 바뀌어도 해시가 달라져야 동결이 의미가 있다
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "count": len(rows),
        "relevant": sum(r.get("kind") == "relevant" for r in rows),
        "irrelevant": sum(r.get("kind") == "irrelevant" for r in rows),
    }


def main(argv: list[str]) -> int:
    """동결(argv=[파일 이름]) 또는 검사(argv=["--check"])를 하고 종료 코드(0 정상, 1 변경 발견·이미 동결, 2 사용법 오류)를 돌려준다."""
    frozen = json.loads(FROZEN.read_text(encoding="utf-8")) if FROZEN.exists() else {}
    if argv == ["--check"]:  # 기록된 해시와 지금 파일의 해시를 비교해 다른 파일 이름만 모은다
        bad = [n for n, m in frozen.items() if _stats(EVALS / n)["sha256"] != m["sha256"]]
        print("동결 이후 바뀐 파일:", bad or "없음")
        return 1 if bad else 0
    if len(argv) != 1 or not (EVALS / argv[0]).exists():
        print(__doc__)
        return 2
    name = argv[0]
    if name in frozen:  # [주의] 이미 동결한 파일은 다시 동결(덮어쓰기)하지 않는다. 동결 해시가 바뀌면 동결의 의미가 없다
        print(f"{name}은 이미 동결됐습니다. 동결한 평가셋은 고치지 않습니다.")
        return 1
    # frozen_at은 동결 실행일(오늘 날짜)이다. FROZEN.json 파일이 곧 "동결 여부"의 기준이다
    frozen[name] = {**_stats(EVALS / name), "frozen_at": date.today().isoformat()}
    FROZEN.write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(name, frozen[name])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
