# inputs

## 역할
- 이 폴더: 동결 평가셋에서 만든 측정 입력(페이지 단위 정답 qrels, 고정 재작성 질의)을 둡니다. 측정 전에 만들어 커밋하고, 측정 뒤에는 고치지 않습니다.
- 넣는 것: 평가 실행기가 읽는 고정 입력 json(qrels, 고정 질의).
- 넣지 않는 것: 동결 평가셋·동결 기록(`evals/`의 `dataset_v2.jsonl`, `FROZEN.json`), 측정 결과(`evals/results/`), 사전 등록·명세(`evals/guides/`), 청크·벡터(용량이 커서 저장소 밖).
- 담당: 평가

## 파일
- `INPUTS.md` — 이 문서
- `qrels_v2_pages.json` — v2 채점 19문항의 필수 근거 페이지((PDF, 쪽) 36개, 청크 없는 2쪽은 회수 불가로 표시). gold 줄에 적힌 쪽을 모두 센다(사전 등록 #24). `evals/runners/run_retrieval_d3.py qrels`가 만듦
- `grader_cases_v2.json` — 채점기 기준선(사전 등록 #33)의 입력. v2 관련 19 · 비관련 35문항에서 채점 노드가 마지막으로 본 검색 청크와 통과시킨 청크의 번호 · 파일 · 쪽(본문 없음), 정답 쪽과 회수 불가 쪽. `eval_grader.py build`가 11-04 70문항 실행의 Langfuse 기록에서 만듦
- `layers/` — 검색 조합 층별 재측정(11-03)의 고정 입력. `parts.json`(0층에서 고정한 질문 줄·품번·비교 여부), `queries.jsonl`(LLM이 한 번 만들어 고정한 질의 Q3~Q5), `queries_check.json`(자동 확인에 걸린 건), `query_texts.jsonl`(임베딩에 보낸 질의 글 전체). `run_retrieval_layers.py`는 `LAYERS_WORK/inputs/`에서 읽으므로 다시 돌릴 때 이 파일들을 그곳에 복사한다
- `rewrite_q3_v2.json` — 같은 19문항의 고정 재작성 질의 Q3(서비스 `rewrite()` 출력 그대로, 2026-11-03). 생성 직후 자동 확인 표시(m04 없던 숫자 123, n01 품번 1N5819 빠짐)
