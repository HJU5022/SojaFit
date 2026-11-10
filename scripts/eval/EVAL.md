# eval

## 역할
- 이 폴더: 평가 실행기(`evals/runners/`)가 남긴 결과 파일과 서비스 DB 시각에서 단계별 응답 시간 · 비용 · 사람 대기 시간을 집계하는 스크립트를 둡니다(D8, EVAL_REPORT 8장). 저장소 루트에서 `python -m scripts.eval.<이름>`으로 실행합니다.
- 넣는 것: 모델 호출 없이 결과 파일 또는 읽기 전용 DB 연결로 숫자만 모으는 집계 스크립트.
- 넣지 않는 것: 모델 · 검색 호출로 재는 평가 실행기(`evals/runners/`), 원시 결과(`evals/results/`), 시험(`tests/evals/`).
- 담당: 평가

## 파일
- `EVAL.md` — 이 문서
- `stage_report.py` — `run_gate` 결과 파일의 문항 행(`stages` · `llm_call_log` · `voyage`)을 단계별 p50 · p95 · 호출당 비용 · 문항당 비용으로 모은다. p50은 진짜 중앙값, p95는 가장 가까운 순위. 같은 문항 id가 여러 파일에 있으면 뒤 파일 행을 쓴다. `--retrieval`로 `run_retrieval_service --stages` 결과를 같은 정의로 다시 센다
- `approval_wait_report.py` — 사람이 기다린 시간(조건 질문 → 재개, 완료 → 승인)을 서버 처리 시간과 떼어 `analysis_events` · `approvals` 시각에서 읽는다. 읽기 전용 연결, 출력은 건수와 초뿐(사용자 id · 대화 id · 본문 없음), 스모크 계정의 즉시 자동 호출은 사람 대기에서 뺀다

## 실행

```bash
uv run python -m scripts.eval.stage_report evals/results/graph/2026-11-11-d8-stages/set1.json evals/results/graph/2026-11-11-d8-stages-rerun/set1.json --retrieval evals/results/retrieval/service_stages_2026-11-11.json
uv run --env-file .env python -m scripts.eval.approval_wait_report --since 2026-11-11 --exclude-users <스모크 계정 id들>
```
