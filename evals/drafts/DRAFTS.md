# drafts

## 역할
- 이 폴더: 동결 전 평가셋 초안과 검수 기록을 둡니다. 실행·동결 금지, 이력으로 보존합니다.
- 넣는 것: 동결 전 평가셋 초안(`draft_*.jsonl`)과 그 검수·검증 기록(`*_review.md`).
- 넣지 않는 것: 동결 평가셋·동결 기록·평가셋 명세(`evals/`의 `dataset_v1.jsonl`, `FROZEN.json`, `dataset-guide.md`), 초안 검증의 원시 json(`evals/results/`).
- 담당: 평가·문서

초안 안의 `status` 값(`not_frozen`, `draft_..._do_not_freeze`, `codex_draft` 등)은 작성 당시 상태의 기록입니다. 무엇이 동결됐는지는 [FROZEN.json](../FROZEN.json)이 정하고, 동결 절차와 필드는 [dataset-guide.md](../dataset-guide.md)를 봅니다. 이 폴더의 파일은 평가 실행기나 `freeze.py`에 넘기지 않습니다.

## 파일
- `DRAFTS.md` — 이 문서
- `draft_30.jsonl` — 난이도별 30건 첫 초안(30행). `kind`와 정답이 비어 있고 정답은 `draft_50.jsonl`에 채움
- `draft_30_review.md` — 30건 초안의 질문·가정·예상 답 검수 목록
- `draft_50.jsonl` — 50건(관련 25·비관련 25) 검수 초안(50행). 고정 키만 `../dataset_v1.jsonl`로 옮겨 동결했고 이 파일은 검수 이력으로 남김
- `draft_50_review.md` — 50건 검토표와 합의 기록
- `second_pass_50_review.md` — 11-02 동결 전 보조 검증 기록. 원시 기록은 `../results/draft50_second_pass_2026-11-02.json`
