# guides

## 역할
- 이 폴더: 평가셋을 만들고 동결하고 채점하는 규칙 문서를 둔다.
- 넣는 것: 평가셋 명세(`dataset-guide.md`), 사전 등록(`preregister.md`), 평가 실행 절차.
- 넣지 않는 것: 지표 해석과 개선 전후 비교(루트 `EVAL_REPORT.md`), 동결 전 초안과 검수 기록(`evals/drafts/`), 실행 코드(`evals/runners/`), 평가 결과(`evals/results/`).
- 담당: 평가·문서

## 파일

| 파일 | 유형 | 설명 |
|---|---|---|
| `GUIDES.md` | 폴더 설명 | 이 문서 |
| `dataset-guide.md` | 명세(정본) | 평가셋 필드·관련/비관련 분류·동결·판정 방식 |
| `preregister.md` | 사전 등록(동결) | 바꾸기 전에 무엇을 바꾸고 어떤 지표를 기대하는지 먼저 적은 기록 |
| `v3_50_codex_paste.md` | 입력 원문 | v3 50문항을 Codex에 붙여넣는 평가 입력(정답·채점 없음) |
| `supervisor-prompt-v0.md` | 실행 절차 | Supervisor Prompt V0 세 후보의 준비, live 승인 gate, 실행·집계 순서 |

`v3_50_codex_paste.md`는 규칙 문서가 아니라 측정 입력이라 위 "넣는 것"과 어긋난다. `scripts/eval/run_codex_v3_isolated.py`(상수 `PASTE`), 결과 폴더 `evals/results/graph/2026-11-16-terra-v3-50-isolated-web/scripts/run_isolated_baseline.py`와 `TALLY.md`·`codex_answers.md`, `EVAL_REPORT.md`가 이 경로를 기록해 옮기지 않았다(`evals/inputs/`는 json만 두는 폴더라 옮기려면 하위 폴더도 새로 만들어야 한다).
