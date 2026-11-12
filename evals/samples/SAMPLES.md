# samples

## 역할
- 이 폴더: v1·v2 동결 평가셋이 아닌 보조 표본을 둔다. 임베딩 프록시, 검색 표본(R1), 수퍼바이저 V0 후보 비교 입력이 있다.
- 넣는 것: 프록시·프로토타입 비교 표본(jsonl)과 해당 표본 전용 무결성 기록(json).
- 넣지 않는 것: 동결 평가셋·동결 기록(`evals/`의 `dataset_v1.jsonl`, `FROZEN.json`), 동결 전 초안(`evals/drafts/`), 표본으로 잰 결과(`evals/results/embedding/`).
- 담당: 평가

## 파일

| 파일 | 유형 | 설명 | 읽는 실행기 |
|---|---|---|---|
| `SAMPLES.md` | 폴더 설명 | 이 문서 | |
| `embedding_sample_v0.jsonl` | 비동결 표본 | 임베딩 후보를 거르는 프록시. 30청크·18질의(48행). v1·v2·G5 건수에 포함하지 않음 | `benchmark_embeddings.py` |
| `retrieval_r1.jsonl` | 비동결 표본 | 검색 표본 84문항(preregister #25). 무리 G1 단서 많음·G2 단서 적음·G3 근거 두 쪽·G4 품번 없음, `split`은 PDF 단위 dev(46)·test(38) | `run_retrieval_r1.py` |
| `retrieval_r1_rewrite_q3.json` | 고정 질의 | 같은 84문항의 고정 재작성 질의 Q3(서비스 `rewrite()` 출력 그대로) | `run_retrieval_r1.py rewrite`가 만듦 |
| `supervisor_prompt_v0.jsonl` | 비동결 표본 | 수퍼바이저 V0 세 후보를 같은 조건에서 비교하는 13건. 같은 사용자 요청의 회로·데이터시트·승인 사례 확보 전후와 재시도 소진 상태를 포함 | `run_supervisor_prompt_v0*.py` |
| `supervisor_prompt_v0_frozen.json` | 무결성 기록 | 위 13건의 sha256·건수. 루트 `FROZEN.json`의 v1·v2 동결을 바꾸지 않음 | `supervisor_prompt_v0_common.py` |

판정 출처: `retrieval_r1.jsonl`의 정답 페이지는 사양 표 행이 있는 쪽으로 정했고 사람 판정은 없다. 질문은 사용자 말투로 자동 초안을 쓴 뒤 기계 검사·자동 O/X 검사를 통과한 것만 남겼다. 생성 스크립트는 저장소 밖(`전자_데이터시트/evidence/r1/`의 `make_items.py`·`gen_questions.py`)에 있다.
