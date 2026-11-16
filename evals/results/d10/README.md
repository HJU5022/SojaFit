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
| `mutation_2026-11-13.md` | 4 | 코드 한 줄 변이 28건의 결과와 재현법. `mutation_2026-11-12.md`를 대체 |
| `mutation/` | 4 | 재현 스크립트(`reproduce.sh`), 변이 정의(`mutation_spec.json`), 변이별 pytest 원시 출력(`raw/`), 시험 추가 전 판정(`raw_before_tests/`) |
| `threshold_pass_2026-11-13.txt` | 3 | 저장 결과 기준 충족 시 종료 0 |
| `threshold_fail_2026-11-13.txt` | 3 | 깨뜨린 사본 3개(답 비움·판정 값 틀림·1행 삭제) → 위반 1건 · 종료 1 |
| `secret_scan_2026-11-13.md` | - | gitleaks 이력 검사와 추가 패턴 검사 결과 |
| `secrets/` | - | 비밀값 검사 원시 증거: 실행 기록, 요약, 이력 검사 보고서 2개, 추가 검사 노트 |
| `startup_restart_isolation_2026-11-13.md` | - | 한 줄 기동 시간(냉 · 온), 키 없는 데모 응답, 재시작 뒤 재개, 계정 분리 52개 점검의 결과와 재현법 |
| `boot/` | - | 위 측정의 원시 출력: 시각표, 스모크 28단계, 52개 점검, 체크포인트 행 수, 합성 시험 출력, 측정 스크립트(`.log` 파일은 `.txt`를 덧붙여 둠) |
| `corpus_v4h_fingerprint_2026-11-12.md` | 5 | v4h 카드·distinct_text·파일 sha256 |
| `index_row_count_2026-11-13.md` | - | 운영 DB `SojaFit_2` 코퍼스 표 행 수 읽기 전용 조회(문서 1,360 · 청크 51,967), 다시 보는 쿼리, 52,244 → 51,967 날짜와 이유 |
| `db_content_hash_check_2026-11-16.md` | - | 운영 DB 청크 본문 51,967개를 읽기 전용으로 열어 sha256을 다시 계산: 저장 해시와 51,967/51,967 같음, 정렬 해시 목록 sha256이 저장소 `chunk_sha256.tsv`와 같음(G3). 다시 보는 쿼리 |
| `alerting_2026-11-16.md` | - | 운영 다운 경보: Cloud Monitoring `/health` 가동 확인(5분) + 경보 정책 + 메일 채널, 일부러 401을 주는 임시 확인으로 경보 OPEN 시험(09:43:30 KST) 뒤 임시 설정 삭제 |
| `langfuse_scores_2026-11-16.md`, `.json` | - | Langfuse 평가 트레이스(v3-01, 11-15 웹 끔 측정)에 붙은 점수 15개를 v3 점수 API로 읽은 기록(G6). 옛 공개 API 410 제거 확인 |
| `corpus_swap_2026-11-09/` | - | 11-09 운영 DB 코퍼스 교체 전(`check.log.txt`) · 후(`verify.log.txt`) 행 수 원본(`.log` 파일은 `.txt`를 덧붙여 둠) |
| `chunk_source_check/` | - | 표·수치 청크 표본 123개를 원본 PDF 같은 쪽과 대조한 결과(`scripts/eval/chunk_source_check.py`) |
| `chunk_source_check_rows_2026-11-16/` | - | 같은 123개를 PDF 표의 같은 행·열 칸 값까지 대조한 결과(`--rows`): 행 검사 117 일치 · 0 불일치 · 6 미확인(부품 행 표), 변이 시험, 남은 한계 |
| `v3_gate_fail_2026-11-13.txt` | 5 | v3 게이트(`gate_report.py`)가 기준 미달 사본 4종에서 종료 1로 실패하는 출력(`mutation/v3_gate_demo.py`) |
| `pytest_full_2026-11-13.txt` | - | 전체 pytest 실행 로그(macOS 로컬) |
| `pytest_full_linux_2026-11-13.txt` | - | 전체 pytest 실행 로그(Linux 컨테이너, 저장소 Dockerfile 이미지 + 컨테이너 안 dev 설치). 실행 A(git 없음) 8 failed, 실행 B 0 failed |
| `keyless_boot_574de79.md` | G1 · G2 | 키 없는 첫 기동 사전 점검(빌드 · 기동 시간, 로그인 · 데모 질문 단계별 ms, 한계) |
| `langfuse_403_2026-11-13.md` | - | 배포본 Langfuse 403 원인: 11-12 키 교체 전후의 비밀 버전과 내보내기 실패 로그 |
| `deploy_574de79/` | G1 · G2 · G4 | 배포 `574de79`에서 평가용 계정 로그인부터 서버 재시작 뒤 재개 · 409 · 계정 B 404까지 25단계 통과(`README.md`, 원시는 `scripts/results/smoke/`의 11-13 120624 파일) |

## 청크 본문

저장소에 `chunks.jsonl` 본문은 없다(용량). 대신 v4h `summary.json`의 `cards`=`distinct_text`=51967과 결과 파일 sha256 목록을 `corpus_v4h_fingerprint_2026-11-12.md`에 둔다. 운영 DB 행 조회는 배포/DB 접근이 필요할 때 따로 남긴다. 청크별 본문 sha256 목록은 `../chunking/v4h-2026-11-08/chunk_sha256.tsv`에 있다.
