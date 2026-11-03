# drafts

## 역할
- 이 폴더: 동결 전 평가셋 초안과 검수 기록을 종류별 하위 폴더로 나눠 둡니다. 실행·동결 금지, 이력으로 보존합니다.
- 넣는 것: 동결 전 평가셋 초안(`sets/`의 `draft_*.jsonl`)과 그 검수·검증 기록(`reviews/`의 `*_review.md`).
- 넣지 않는 것: 동결 평가셋·동결 기록(`evals/`의 `dataset_v1.jsonl`, `FROZEN.json`), 평가셋 명세(`evals/guides/dataset-guide.md`), 초안 검증의 원시 json(`evals/results/drafts/`).
- 담당: 평가·문서

초안 안의 `status` 값(`not_frozen`, `draft_..._do_not_freeze`, `codex_draft` 등)은 작성 당시 상태의 기록입니다. 무엇이 동결됐는지는 [FROZEN.json](../FROZEN.json)이 정하고, 동결 절차와 필드는 [dataset-guide.md](../guides/dataset-guide.md)를 봅니다. 이 폴더의 파일은 평가 실행기나 `freeze.py`에 넘기지 않습니다.

## 파일
- `DRAFTS.md` — 이 문서
- `sets/` — 평가셋 초안 jsonl
  - `draft_30.jsonl` — 난이도별 30건 첫 초안(30행). `kind`와 정답이 비어 있고 정답은 `draft_50.jsonl`에 채움
  - `draft_50.jsonl` — 50건(관련 25·비관련 25) 검수 초안(50행). 고정 키만 `../dataset_v1.jsonl`로 옮겨 동결했고 이 파일은 검수 이력으로 남김
  - `draft_v2add_20.jsonl` — v2 추가 후보 찾기 20건(관련 10·비관련 10) 초안(20행). Codex 출제·정답(11-01)과 사람 판정 기록(`review`: 1차 하정운·2차 김재훈, 11-03 모두 O). 고정 키만 `../dataset_v2.jsonl`로 옮겨 동결
- `reviews/` — 초안 검수·검증 기록 md
  - `draft_30_review.md` — 30건 초안의 질문·가정·예상 답 검수 목록
  - `draft_50_review.md` — 50건 검토표와 합의 기록
  - `draft_v2add_20_review.md` — v2 추가 20건 검토표와 1·2차 사람 판정 기록
  - `second_pass_50_review.md` — 11-02 동결 전 보조 검증 기록. 원시 기록은 `../results/drafts/draft50_second_pass_2026-11-02.json`
