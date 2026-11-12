# D10 제출물 점검 증거 (2026-11-12)

Checkpoint D10 카드용. 새 기능 없음. 기준은 GitHub `main`에 올릴 커밋과 배포 tip 일치(푸시·배포는 별도).

## 재현 한 줄

```bash
# 인젝션 저장 결과 기준 충족(키·네트워크 없음). 위반 있으면 종료 코드 1
uv run --no-sync python -m evals.runners.check_injection_result

# 일부러 1행 답을 비우면 실패 출력이 난다(아래 fail txt와 같은 모양)
python - <<'PY'
from pathlib import Path
import json, subprocess, sys
src = Path('evals/results/threads/injection_baseline_live_2026-11-11_03.jsonl')
rows = [json.loads(l) for l in src.read_text().splitlines() if l.strip()]
rows[0]['answer'] = ''
p = Path('/tmp/sojafit_injection_broken.jsonl')
p.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rows) + '\n')
sys.exit(subprocess.call([sys.executable, '-m', 'evals.runners.check_injection_result', str(p)]))
PY

# 검색 재현(유료·DB 필요). METHOD=hybrid|dense|bm25
docker compose run --rm --no-deps -e DEMO_MODE=0 -v "${PWD}/evals:/app/evals" -v "${PWD}/backend:/app/backend" \
  api python -m evals.runners.run_retrieval evals/dataset_v1.jsonl evals/results/retrieval/retrieval.json 5 METHOD
```

## 이 폴더 파일

| 파일 | D10 항 | 내용 |
|---|---|---|
| `injection_check_pass_2026-11-12.txt` | 3 | 기준 충족 시 종료 0 |
| `injection_check_fail_2026-11-12.txt` | 3 | 1행 답 비움 → 위반 1 · 종료 1 |
| `mutation_2026-11-12.md` | 4 | 멀티 그래프 현행 코드 변이 3건(실패 후 원복) |
| `corpus_v4h_fingerprint_2026-11-12.md` | 5 | v4h 카드·distinct_text·파일 sha256 |

## 청크 본문

저장소에 `chunks.jsonl` 본문은 없다(용량). 대신 v4h `summary.json`의 `cards`=`distinct_text`=51967과 결과 파일 sha256 목록을 `corpus_v4h_fingerprint_2026-11-12.md`에 둔다. 운영 DB 행 조회는 배포/DB 접근이 필요할 때 따로 남긴다.
