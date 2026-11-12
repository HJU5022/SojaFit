# inputs

## 역할
- 이 폴더: 동결 평가셋에서 만든 측정 입력(페이지 단위 정답 qrels, 고정 재작성 질의, 채점기 입력)을 둔다. 측정 전에 만들어 커밋하고 측정 뒤에는 고치지 않는다.
- 넣는 것: 평가 실행기가 읽는 고정 입력 json.
- 넣지 않는 것: 동결 평가셋·동결 기록(`evals/`의 `dataset_v2.jsonl`, `FROZEN.json`), 측정 결과(`evals/results/`), 사전 등록·명세(`evals/guides/`), 청크·벡터(용량이 커서 저장소 밖).
- 담당: 평가

## 파일

| 파일 | 유형 | 설명 | 만든 실행기 |
|---|---|---|---|
| `INPUTS.md` | 폴더 설명 | 이 문서 | |
| `qrels_v2_pages.json` | 측정 입력 | v2 채점 19문항의 필수 근거 (PDF, 쪽). 청크 없는 쪽은 회수 불가로 표시(preregister #24). 최상위 `meta`·`qrels` | `run_retrieval_d3.py qrels` |
| `grader_cases_v2.json` | 측정 입력 | 채점기 기준선(#36)의 입력. v2 관련·비관련 문항(54건)에서 채점 노드가 본 검색 청크와 통과시킨 청크의 번호·파일·쪽(본문 없음). 최상위 `meta`·`cases` | `eval_grader.py build` |
| `grader_cases_r1_dev.json` | 측정 입력 | 채점기 기준선 R1 dev(#34)의 입력. R1 dev 46문항에 고정 Q3 질의와 품번 필터로 `retrieve()`와 채점 노드를 1회씩 돌린 청크 번호·파일·쪽(본문 없음) | `eval_grader.py collect-r1` |
| `layers/` | 측정 입력 | 검색 조합 층별 재측정의 고정 입력: `parts.json`(질문 줄·품번·비교 여부), `queries.jsonl`(LLM이 한 번 만들어 고정한 질의 Q3~Q5), `queries_check.json`(자동 확인에 걸린 건), `query_texts.jsonl`(임베딩에 보낸 질의 글 전체) | `run_retrieval_layers.py`, `check_retrieval_db.py` |
| `rewrite_q3_v2.json` | 측정 입력 | 같은 19문항의 고정 재작성 질의 Q3(서비스 `rewrite()` 출력 그대로) | 서비스 `rewrite()` |

`run_retrieval_layers.py`는 `$LAYERS_WORK/inputs/`에서 읽으므로 `layers/`의 파일을 그곳에 복사해 쓴다.

## 한계

- `rewrite_q3_v2.json`은 생성 직후 자동 확인에서 m04(없던 숫자 123)와 n01(품번 1N5819 빠짐)이 표시됐다.
