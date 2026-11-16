# eval

## 역할
- 이 폴더: 평가 결과 파일을 사람 손 작업·서비스 DB 시각과 이어 주는 변환·집계 스크립트를 둔다. 저장소 루트에서 실행한다(집계 스크립트는 `python -m scripts.eval.<이름>`).
- 넣는 것: 사람 채점 시트 같은 외부 입력을 평가 JSONL로 되돌리는 스크립트, 평가 결과 파일과 읽기 전용 DB 연결에서 단계별 응답 시간·비용·사람 대기 시간(D8, EVAL_REPORT 8장)을 숫자만 모으는 집계 스크립트.
- 넣지 않는 것: 모델·검색을 불러 재는 평가 실행·채점·동결 스크립트와 결과(`evals/`), 시험(`tests/evals/`).
- 담당: 에이전트(변환), 평가(집계)

## 파일

| 파일 | 분류 | 분류 근거 | 설명 |
|---|---|---|---|
| `EVAL.md` | | | 이 문서 |
| `import_human_review.py` | 일회성 | 호출처는 `tests/evals/test_import_human_review.py`뿐. `--jsonl` 기본값이 인젝션 실측03 파일 | 사람 채점 시트(마크다운 O/X 표)를 인젝션 실측 JSONL의 `human_review` 칸으로 옮긴 새 사본을 쓰고, assistant 잠정 분류와 사람 판정의 일치율을 출력한다(원본 수정 없음) |
| `stage_report.py` | 재현용 | `evals/EVALS.md`·`EVAL_REPORT.md`가 D8 집계로 인용, `tests/evals/test_stage_timing.py`가 시험. 입력 결과 파일이 저장소에 있음 | `run_gate` 결과 파일의 문항 행(`stages`·`llm_call_log`·`voyage`)을 단계별 p50·p95·호출당 비용·문항당 비용으로 모은다. p50은 중앙값, p95는 가장 가까운 순위. 같은 문항 id가 여러 파일에 있으면 뒤 파일 행을 쓴다. `--retrieval`로 `run_retrieval_service --stages` 결과를 같은 정의로 다시 센다 |
| `approval_wait_report.py` | 재현용 | `EVAL_REPORT.md`가 인용, `tests/evals/test_approval_wait_report.py`가 시험. 읽기 전용 DB 연결이 필요 | 사람이 기다린 시간(조건 질문 → 재개, 완료 → 승인)을 서버 처리 시간과 떼어 `analysis_events`·`approvals` 시각에서 읽는다. 읽기 전용 연결, 출력은 건수와 초뿐(사용자 id·대화 id·본문 없음), 스모크 계정의 즉시 자동 호출은 사람 대기에서 뺀다 |
| `chunk_source_check.py` | 재현용 | `evals/results/d10/chunk_source_check/`(기본)와 `chunk_source_check_rows_2026-11-16/`(`--rows`)를 만든다. 시험은 `tests/evals/test_chunk_source_check.py`. 로컬 `../corpus/tsc/`의 v4h 청크와 PDF가 필요 | 표·수치 청크 표본(시드 고정)의 숫자와 단위가 원본 PDF 같은 쪽에 있는지 대조한다. `--rows`는 청크의 행 이름으로 PDF 표의 같은 행을 찾아 같은 열 칸 값·단위까지 대조하고(같은 쪽 다른 행·열 값으로 바뀐 오류), 실제 표본에 변이 시험을 건다. `--out`은 결과 폴더, `--rows`는 기존 폴더를 덮어쓰지 않는다. DB·네트워크 없음 |
| `run_codex_v3_isolated.py` | 재현용 | `evals/results/graph/2026-11-16-codex-v3-50-isolated/`의 `raw/`(문항별 이벤트 로그 · 답) · `runs.json`을 만든다. 사전 등록 2026-11-16 Codex 격리 재비교 | 문항마다 빈 작업 폴더에 그 문항 넷리스트만 `circuit.net`으로 넣고 `codex exec`를 부른다. 새 CODEX_HOME(로그인 파일만), 사용자 설정 · 규칙 · 메모리 끔, 읽기 전용, 웹 검색 켬. 관련/비관련 표지는 주지 않는다. Codex 사용량을 쓴다 |
| `tally_codex_v3.py` | 재현용 | `evals/results/graph/2026-11-12-codex-v3-50/`의 `tally.jsonl`·`TALLY.md` 집계와, 결과 폴더를 인자로 주면 그 폴더(예: 11-16 Codex 격리 실행, 11-16 Terra 기준선)의 `tally.jsonl`을 만든다. 답 파일은 `codex_answers.md`, 없으면 `answers.md` | Codex 답 50건을 v3 정답과 규칙으로 대조한다. 규칙으로 못 가리는 문항은 사람 판정 필요로 둔다. LLM·네트워크 없음 |

## 실행

```bash
uv run python scripts/eval/import_human_review.py <시트.md> --out <새.jsonl> --reviewer <이름> [--jsonl <원본.jsonl>]
uv run python scripts/eval/chunk_source_check.py --rows   # 결과: evals/results/d10/chunk_source_check_rows_2026-11-16/
uv run python -m scripts.eval.stage_report evals/results/graph/2026-11-11-d8-stages/set1.json evals/results/graph/2026-11-11-d8-stages-rerun/set1.json --retrieval evals/results/retrieval/service_stages_2026-11-11.json
uv run --env-file .env python -m scripts.eval.approval_wait_report --since 2026-11-11 --exclude-users <스모크 계정 id들>
```

`import_human_review.py`의 `--jsonl` 기본값은 실측03 파일이다. `--out`이 원본과 같으면 멈춘다. 시트에서 `판정`이 비어 있는 항목은 건너뛴다.
