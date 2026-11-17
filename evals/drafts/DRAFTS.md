# drafts

## 역할
- 이 폴더: 동결 전 평가셋 초안과 검수 기록을 종류별 하위 폴더로 나눠 둔다. 실행·동결 금지, 이력으로 보존한다.
- 넣는 것: 동결 전 평가셋 초안(`sets/`의 `draft_*.jsonl`)과 그 검수·검증 기록(`reviews/`의 `*_review.md`).
- 넣지 않는 것: 동결 평가셋·동결 기록(`evals/`의 `dataset_v1.jsonl`, `FROZEN.json`), 평가셋 명세([dataset-guide.md](../guides/dataset-guide.md)), 초안 검증의 원시 json(`evals/results/drafts/`).
- 담당: 평가·문서

초안 안의 `status` 값(`not_frozen`, `draft_..._do_not_freeze`, `codex_draft` 등)은 작성 당시 상태의 기록이다. 동결 여부는 [FROZEN.json](../FROZEN.json)이 정하고, 동결 절차와 필드는 [dataset-guide.md](../guides/dataset-guide.md)에 있다. 이 폴더의 파일은 평가 실행기나 `freeze.py`에 넘기지 않는다.

## 파일

| 파일·폴더 | 유형 | 설명 |
|---|---|---|
| `DRAFTS.md` | 폴더 설명 | 이 문서 |
| `sets/` | 초안 | 평가셋 초안 jsonl |
| `sets/draft_30.jsonl` | 초안 | 난이도별 30건 첫 초안. `kind`와 정답이 비어 있음 |
| `sets/draft_50.jsonl` | 초안 | 50건(관련 25·비관련 25) 검수 초안. 고정 키만 `../dataset_v1.jsonl`로 옮겨 동결 |
| `sets/draft_v2add_20.jsonl` | 초안 | v2 추가 후보 찾기 20건(관련 10·비관련 10). 고정 키만 `../dataset_v2.jsonl`로 옮겨 동결 |
| `reviews/` | 검수 기록 | 초안 검수·검증 md |
| `reviews/draft_30_review.md` | 검수 기록 | 30건 초안의 질문·가정·예상 답 검수 목록 |
| `reviews/draft_50_review.md` | 검수 기록 | 50건 검토표와 합의 기록 |
| `reviews/draft_v2add_20_review.md` | 검수 기록 | v2 추가 20건 검토표와 1·2차 사람 판정 기록 |
| `reviews/second_pass_50_review.md` | 검수 기록 | 동결 전 보조 검증. 원시 기록은 `../results/drafts/draft50_second_pass_2026-11-02.json` |
| `reviews/v3_judging_record.md` | 검수 기록 | v3 50건의 판정 역할(초안 Codex·하정운, 1차 심태현, 최종 하정운). 11-13 작성 |

판정 출처: `sets/draft_v2add_20.jsonl`은 Codex가 출제하고 정답 초안을 썼다. 사람 판정은 1차 하정운, 2차 김재훈이며 `review` 필드에 있다.
