# evals

## 역할
- 이 폴더: 동결 평가셋과 동결 기록을 루트에 두고, 실행 코드·문서·표본·초안·결과를 하위 폴더로 나눠 둡니다. 루트 파일의 위치와 이름은 과정 안내와 동결 시험이 가정하므로 옮기지 않습니다.
- 넣는 것: 동결 평가셋(`dataset_v1.jsonl`, `dataset_v2.jsonl`)과 동결 기록(`FROZEN.json`). 앞으로 생길 `exclusions.json`도 루트에 둡니다. `exclusions.json`은 코퍼스가 바뀔 때 생기며 지금은 없습니다([dataset-guide.md](guides/dataset-guide.md)).
- 넣지 않는 것: 실행기·동결 스크립트(`evals/runners/`), 명세·사전 등록(`evals/guides/`), 측정 입력(`evals/inputs/`), 프록시 표본(`evals/samples/`), 동결 전 초안·검수 기록(`evals/drafts/`), 지표 해석과 개선 전후 비교(루트 `EVAL_REPORT.md`), 단위 테스트(`tests/`), 평가가 아닌 측정 스크립트와 그 원시 결과(`scripts/`, `scripts/results/`).
- 담당: 평가·문서. 정답은 두 사람이 교차해서 정합니다.

평가셋 필드·정답 기준·동결·채점 방식의 정본은 [dataset-guide.md](guides/dataset-guide.md)입니다.

## 파일
- `EVALS.md` — 이 문서
- `dataset_v1.jsonl` — 동결 평가셋 v1. 50건(관련 25·비관련 25), 2026-11-02 동결. `drafts/sets/draft_50.jsonl`의 고정 키만 옮김
- `dataset_v2.jsonl` — 동결 평가셋 v2. 70건(관련 35·비관련 35), 2026-11-03 동결. v1 50건 줄에 `question_type`만 더하고 후보 찾기 20건(`drafts/sets/draft_v2add_20.jsonl`의 고정 키)을 더함
- `FROZEN.json` — 동결한 파일별 sha256·건수·관련/비관련 건수·동결일. 현재 `dataset_v1.jsonl`, `dataset_v2.jsonl` 둘. 동결 여부는 이 파일이 정함
- `runners/` — 평가 실행기와 동결 스크립트. 실행은 `uv run python -m evals.runners.<이름>`. [RUNNERS.md](runners/RUNNERS.md)
- `inputs/` — 동결 평가셋에서 만든 측정 입력(페이지 단위 qrels, 고정 재작성 질의). [INPUTS.md](inputs/INPUTS.md)
- `guides/` — 평가셋 명세(`dataset-guide.md`)와 사전 등록(`preregister.md`). [GUIDES.md](guides/GUIDES.md)
- `samples/` — 임베딩 후보를 거르는 비동결 프록시 표본. [SAMPLES.md](samples/SAMPLES.md)
- `drafts/` — 동결 전 평가셋 초안(`sets/`)과 검수 기록(`reviews/`)(실행·동결 금지, 이력 보존). [DRAFTS.md](drafts/DRAFTS.md)
- `results/` — 평가 원시 결과. 아래 "결과 폴더"에서 설명하며 폴더 설명 파일은 두지 않음. 평가가 아닌 측정은 `scripts/results/`

## 실행기 동작 메모
- `run_retrieval.py` — 검색 방식(`hybrid` 기본·`dense`·`bm25`)은 summary의 `method`에 적음. 회로 근거만 있는 문항과 후보 찾기 문항(`question_type` `candidate_find`, 열린 정답)은 세지 않음. 문항에 `question` 키가 있으면 그것으로, 없으면 `input` 전체로 검색함. `dataset_v1.jsonl`에는 `question`이 없어 v1 베이스라인은 회로명·넷리스트 경로·조건이 붙은 `input` 전체로 검색하고, 11-01 실험(preregister #4~#8, `drafts/sets/draft_50.jsonl`)은 `question`만으로 검색했으므로 두 점수는 바로 비교할 수 없음. 질의 필드를 바꾸려면 먼저 [preregister.md](guides/preregister.md)에 등록
- `run_graph.py` — 한 번 실행한 문항은 session 하나로 묶고 환경 이름은 `eval`. 문항별 결과 파일은 청크 내용이 들어가 저장소에 남기지 않음. 비용은 Langfuse 프로젝트에 등록한 OpenRouter 가격표(`anthropic/claude-haiku-5.5`, ADR 0010 가격)로 계산됨
- `score_answer.py` — 평가셋 문항(`kind`, `expected`, `gold_chunks`, `question_type`)과 그래프 실행 상태(`state` 또는 `run_skill_pair.py` 출력)를 대조해 답변·거절 5지표를 결정적으로 채점함([작업서](../docs/experiments/answer-refusal-scorer.md)). `n01, n02`처럼 `relevant + NOT_VERIFIED`가 정답인 문항에서 정답 근거 청크를 인용해 조건 부족을 설명한 답은 과잉 거절로 세지 않음
- `run_skill_pair.py` — 그림의 노드 순서로 준비 상태를 저장한 뒤 동일 상태에서 Skill 유무 답변을 비교. 생성 거절 경로·부분 결과·해시·예약비용을 기록하며 expected 충족률은 검토 전 null. 서비스 그래프·MCP 통합 검증은 아님

## 결과 폴더
`results/`의 파일은 `<무엇>_<YYYY-MM-DD>.json`이고 하위 폴더 네 개로 묶습니다.
- `results/retrieval/` — `retrieval_baseline_2026-11-03.json`·`retrieval_dense_2026-11-03.json`·`retrieval_bm25_2026-11-03.json`: v1 데이터시트 근거 19문항의 검색 지표(`run_retrieval.py`, k=5). 각각 하이브리드·dense만·BM25만. 하이브리드 파일은 `method` 인자가 생기기 전에 만들어 summary에 `method`가 없음
- `results/embedding/` — `embedding_<모델>_proxy_2026-10-30.json`·`embedding_<모델>_proxy_offline_2026-10-30.json`: 임베딩 프록시 측정(`benchmark_embeddings.py`). 모델은 `bge_m3`·`kure_v1`·`qwen3_0_6b`, `text_embedding_3_small`은 온라인 한 파일만 있음(7개)
- `results/search_compare/` — 검색 방식·청킹 비교. `chunking_proxy_2026-11-01.json`·`chunking_search_2026-11-01.json`(청킹 개선 전후: 프록시 청크 수·해석 가능 값 / 11문항 검색 지표), `hybrid_search_2026-11-01.json`(dense·BM25·하이브리드 비교, 11문항, RRF k=60)
- `results/drafts/` — `draft50_second_pass_2026-11-02.json`(50건 초안의 문항 구조·NET 해시·PDF 해시 및 문항별 보조 검증 원시 기록, `drafts/reviews/second_pass_50_review.md`의 원본), `draft52_validation_2026-11-02.json`(추가 두 건의 2차 O 기록 전 스냅샷. 당시 52건 구성·기존 질문 보존·변경 이력·NET/PDF 해시 확인. 사람 검수·평가 실행·동결 결과가 아님)
- `results/skill/` — `skill_tool_summary_2026-11-03.json`: Skill·도구 판단 개발 검증 요약, 미충족 사례·트레이스와 원본 6개 해시. 상세 실행 JSON은 저장소 밖에 보관하며 동결 평가 점수와 구분

임베딩 결과의 수치와 공통 해석은 루트 [EVAL_REPORT.md](../EVAL_REPORT.md), 후보 13종을 선정한 이유·개별 실행 과정·중단 사유·다음 조건은 [embedding-candidate-investigation.md](../docs/research/embedding-candidate-investigation.md)를 봅니다. 2026-11-02 확장 평가기·실제 PDF 표본·원시 결과는 저장소에 없어 재현할 수 없습니다. 차단 결과는 Recall@5·MRR 0점이나 품질 탈락으로 환산하지 않습니다.

`embedding_sample_v0.jsonl`은 후보를 거르는 비동결 프록시이며 v1·v2나 G5 건수에 포함하지 않습니다. 실제 모델 결정은 TSC 1,360건 실제 청크 평가를 별도 사전 등록한 뒤 수행합니다.

평가셋 필드·정답 기준·동결·채점 방식은 [dataset-guide.md](guides/dataset-guide.md)가 정본입니다.
