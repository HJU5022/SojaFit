# evals

T3 스모크07은 `results/threads/injection_t3_smoke_live_2026-11-11_07.jsonl`과 동명 `.meta.json`/`.budget.json`, `injection_t3_smoke_approval_2026-11-11_07.json`에 별도 기록한다. 정상·공격/current 2작업이며 기존110회03과 합산하지 않는다.

T4 수정 포함110회03 원시는 results/threads/injection_baseline_live_2026-11-11_03.jsonl·동명.meta.json·동명.budget.json, 승인은injection_baseline_approval_2026-11-11_03.json에별도보존한다. baseline_t2_t4_revised_v3는02와같은짝구성에서T4재검색/미완료안내수정을측정하며이전원시와합산하지않는다.

실측01·02와 스모크01~06의 원시·메타·예산·승인 32개는 저장소 밖 원본 백업으로 옮겼다(2026-11-11). 최신03의4개만저장소에남기고, [보관·해시 인덱스](results/threads/injection_baseline_artifact_index_2026-11-10.json#/measured_runs_archive)에36개전체의크기/SHA256·보관위치·복원방법을기록한다. 이전32개는Git미추적파일이었으므로Git이력복구를대체수단으로가정하지않는다. 백업은현재로컬전용이며이전실측의내용/판정을변경하지않았다.

## 역할
- 이 폴더: 동결 평가셋과 동결 기록을 루트에 두고, 실행 코드·문서·표본·초안·결과를 하위 폴더로 나눠 둡니다. 루트 파일의 위치와 이름은 과정 안내와 동결 시험이 가정하므로 옮기지 않습니다.
- 넣는 것: 동결 평가셋(`dataset_v1.jsonl`, `dataset_v2.jsonl`, `dataset_v3.jsonl`)과 동결 기록(`FROZEN.json`). 앞으로 생길 `exclusions.json`도 루트에 둡니다. `exclusions.json`은 코퍼스가 바뀔 때 생기며 지금은 없습니다([dataset-guide.md](guides/dataset-guide.md)).
- 넣지 않는 것: 실행기·동결 스크립트(`evals/runners/`), 명세·사전 등록(`evals/guides/`), 측정 입력(`evals/inputs/`), 프록시 표본(`evals/samples/`), 동결 전 초안·검수 기록(`evals/drafts/`), 지표 해석과 개선 전후 비교(루트 `EVAL_REPORT.md`), 단위 테스트(`tests/`), 평가가 아닌 측정 스크립트와 그 원시 결과(`scripts/`, `scripts/results/`).
- 담당: 평가·문서. 정답은 두 사람이 교차해서 정합니다.

평가셋 필드·정답 기준·동결·채점 방식의 정본은 [dataset-guide.md](guides/dataset-guide.md)입니다.

## 파일
- `EVALS.md` — 이 문서
- `dataset_v1.jsonl` — 동결 평가셋 v1. 50건(관련 25·비관련 25), 2026-11-02 동결. `drafts/sets/draft_50.jsonl`의 고정 키만 옮김
- `dataset_v2.jsonl` — 동결 평가셋 v2. 70건(관련 35·비관련 35), 2026-11-03 동결. v1 50건 줄에 `question_type`만 더하고 후보 찾기 20건(`drafts/sets/draft_v2add_20.jsonl`의 고정 키)을 더함
- `dataset_v3.jsonl` — 동결 평가셋 v3(기준 평가셋, ADR 0015). 50건(관련 25 · 비관련 25), 2026-11-10 동결. lab `evals/drafts/v3/v3_draft.jsonl`을 그대로 옮김(#43 ~ #50 측정에 쓴 파일). 쓰는 회로 넷리스트는 `data/circuits/collected/`에 모두 있음
- `FROZEN.json` — 동결한 파일별 sha256·건수·관련/비관련 건수·동결일. 현재 `dataset_v1.jsonl`, `dataset_v2.jsonl`, `dataset_v3.jsonl` 셋. 동결 여부는 이 파일이 정함
- 기준 평가셋은 v3입니다(2026-11-06 결정, 2026-11-10 동결, [ADR 0015](../docs/adr/0015-평가셋-v3를-새로-만들고-청킹부터-다시-잰다.md)). v1 · v2는 지금까지의 측정 기록으로 둡니다
- `runners/` — 평가 실행기와 동결 스크립트. 실행은 `uv run python -m evals.runners.<이름>`. [RUNNERS.md](runners/RUNNERS.md)
- `docker/` — 평가 실험용 컨테이너 이미지 정의(원격 GPU·실험 DB). [DOCKER.md](docker/DOCKER.md)
- `inputs/` — 동결 평가셋에서 만든 측정 입력(페이지 단위 qrels, 고정 재작성 질의). [INPUTS.md](inputs/INPUTS.md)
- `guides/` — 평가셋 명세(`dataset-guide.md`)와 사전 등록(`preregister.md`). [GUIDES.md](guides/GUIDES.md)
- `samples/` — 임베딩 후보를 거르는 비동결 프록시 표본. [SAMPLES.md](samples/SAMPLES.md)
- `drafts/` — 동결 전 평가셋 초안(`sets/`)과 검수 기록(`reviews/`)(실행·동결 금지, 이력 보존). [DRAFTS.md](drafts/DRAFTS.md)
- `results/` — 평가 원시 결과. 아래 "결과 폴더"에서 설명하며 폴더 설명 파일은 두지 않음. 평가가 아닌 측정은 `scripts/results/`

## 실행기 동작 메모
- `run_retrieval.py` — 검색 방식(`hybrid` 기본·`dense`·`bm25`)은 summary의 `method`에 적음. 회로 근거만 있는 문항과 후보 찾기 문항(`question_type` `candidate_find`, 열린 정답)은 세지 않음. 문항에 `question` 키가 있으면 그것으로, 없으면 `input` 전체로 검색함. `dataset_v1.jsonl`에는 `question`이 없어 v1 기준선은 회로명·넷리스트 경로·조건이 붙은 `input` 전체로 검색하고, 11-01 실험(preregister #4~#8, `drafts/sets/draft_50.jsonl`)은 `question`만으로 검색했으므로 두 점수는 바로 비교할 수 없음. 질의 필드를 바꾸려면 먼저 [preregister.md](guides/preregister.md)에 등록
- `run_graph.py` — 한 번 실행한 문항은 session 하나로 묶고 환경 이름은 `eval`. 문항별 결과 파일(`results/graph/`)에는 지표와 id만 남기고 답변 문장·청크 원문은 넣지 않음. 비용은 Langfuse 프로젝트에 등록한 OpenRouter 가격표(노드별 모델, ADR 0014)로 계산됨
- `score_answer.py` — 평가셋 문항(`kind`, `expected`, `gold_chunks`, `question_type`)과 그래프 실행 상태(`state` 또는 `run_skill_pair.py` 출력)를 대조해 답변·거절 5지표를 결정적으로 채점함([작업서](../docs/experiments/answer-refusal-scorer.md)). `n01, n02`처럼 `relevant + NOT_VERIFIED`가 정답인 문항에서 정답 근거 청크를 인용해 조건 부족을 설명한 답은 과잉 거절로 세지 않음
- `run_skill_pair.py` — 그림의 노드 순서로 준비 상태를 저장한 뒤 동일 상태에서 Skill 유무 답변을 비교. 생성 거절 경로·부분 결과·해시·예약비용을 기록하며 expected 충족률은 검토 전 null. 서비스 그래프·MCP 통합 검증은 아님

## 결과 폴더
`results/`의 파일은 `<무엇>_<YYYY-MM-DD>.json`이고 하위 폴더 아홉 개로 묶습니다.
- `results/retrieval/` — `retrieval_baseline_2026-11-03.json`·`retrieval_dense_2026-11-03.json`·`retrieval_bm25_2026-11-03.json`: v1 데이터시트 근거 19문항의 검색 지표(`run_retrieval.py`, k=5). 각각 하이브리드·dense만·BM25만. 하이브리드 파일은 `method` 인자가 생기기 전에 만들어 summary에 `method`가 없음
  - `d3_official_2026-11-03.json`·`d3_official_gpu_2026-11-03.json`: 사전 등록 #24 D3 공식 측정(동결 v2 채점 19문항, 조건 E1~E8을 하나씩 바꾼 칸과 칸별 비교, GPU 칸은 로컬 리랭커·late chunking). `d3_noresult_2026-11-03.json`: 관련 19·비관련 35문항의 1위 점수 분포와 no_result 임계값. `d3_explore_2026-11-03.json`: 탐색 격자 276칸(판정에 쓰지 않음)
  - `r1_2026-11-03.json`: 사전 등록 #25 R1 검색 평가셋 84문항, dev 세트 264개 조합·답안지 검사·test 세트 확인 4칸(줄인 판). `r1_steps_2026-11-04.json`: 사전 등록 #28 단계별 재측정(S0 → S4, 앞 단계와 짝 비교·실패 유형)
  - `retrieval_layer0~4_2026-11-03.json`·`retrieval_layers_report_2026-11-03.json`·`retrieval_layers_final_2026-11-03.json`: 검색 조합 층별 재측정(0층 DB 점검, 1층 질의 글, 2층 토큰화·RRF·필터·청킹, 3층 임베딩 11종, 4층 리랭커). 사전 등록 #24 이전의 탐색이며 해석은 [retrieval-layered-rerun-2026-11-03.md](../docs/research/retrieval-layered-rerun-2026-11-03.md)
  - `service_r1_2026-11-04.json`·`service_r1_bits_2026-11-04.json`: 사전 등록 #26·#27 서비스 경로 재측정(운영 DB, 정확 검색 / 비트 후보 + 정확 재정렬). `service_stages_2026-11-04.json`: 사전 등록 #28 `retrieve()` 단계별 시간과 rerank 토큰
  - 1 MB가 넘는 `r1_2026-11-03.json`(4.3 MB)·`d3_official_2026-11-03.json`(3.5 MB)·`retrieval_layer3_2026-11-03.json`(1.5 MB)은 칸마다 문항별 원시 행(`rows`)을 담은 파일이라 측정 근거로 그대로 둡니다
- `results/embedding/` — `grid_2026-11-02.json`: 사전 등록 #16 임베딩 6종 × 검색 방식 격자 본평가 78칸(칸별 요약, 문항별 순위·상위 5·단계별 시간). `grid_embed_<모델>_2026-11-02.json` 6개: 모델별 카드 임베딩 기록(차원·토큰·초). `grid_rerank_cache_2026-11-02.jsonl`: 리랭크 응답 순서·토큰·시간. 해석은 [embedding-grid-eval-2026-11-02.md](../docs/research/embedding-grid-eval-2026-11-02.md)
  - `embedding_<모델>_proxy_2026-10-30.json`·`embedding_<모델>_proxy_offline_2026-10-30.json`: 임베딩 프록시 측정(`benchmark_embeddings.py`). 모델은 `bge_m3`·`kure_v1`·`qwen3_0_6b`, `text_embedding_3_small`은 온라인 한 파일만 있음(7개)
- `results/search_compare/` — 검색 방식·청킹 비교. `chunking_proxy_2026-11-01.json`·`chunking_search_2026-11-01.json`(청킹 개선 전후: 프록시 청크 수·해석 가능 값 / 11문항 검색 지표), `hybrid_search_2026-11-01.json`(dense·BM25·하이브리드 비교, 11문항, RRF k=60)
- `results/drafts/` — `draft50_second_pass_2026-11-02.json`(50건 초안의 문항 구조·NET 해시·PDF 해시 및 문항별 보조 검증 원시 기록, `drafts/reviews/second_pass_50_review.md`의 원본), `draft52_validation_2026-11-02.json`(추가 두 건의 2차 O 기록 전 스냅샷. 당시 52건 구성·기존 질문 보존·변경 이력·NET/PDF 해시 확인. 사람 검수·평가 실행·동결 결과가 아님)
- `results/graph/` — `graph_<평가셋>_<YYYY-MM-DD>.json`(멀티 에이전트는 `multi_…`): 평가셋 문항을 줄기 그래프로 끝까지 돌린 문항별 지표(경로·검색 횟수·LLM 호출 수·통과 청크 id·인용 검사·5지표·시간·트레이스 주소), 실행 조건(커밋·모델·노드별 모델·프롬프트 해시·평가셋 sha256·Langfuse 세션), 5지표 요약(`run_graph.py`). 답변 문장과 청크 원문은 넣지 않고 Langfuse 트레이스에서 본다
  - `graph/2026-11-06-judge-steps/`: 사전 등록 #39 · #40 · #41 · #42(11-06, 동결 v2 70문항)의 원시 결과 29개를 저장소 밖 lab 작업 폴더에서 바이트 그대로 옮긴 것(11-10, 합 약 1.0 MB). 답변 문장 · 청크 원문 칸이 없어 거른 것은 없다. `p39_single_set<n>` · `p40_multi_set<n>`(#39 단일 · #40 멀티 + 판정, 2세트), `step_S<2~9>_set<n>`(#41 단계별 단일 그래프), `e03_<단계>_set<n>`(그 세트에서 실패한 draft30-e03만 다시 돌림), `dev_S2` · `dev_S9`(dev셋 44문항, 그 평가셋 파일은 저장소에 없음), `step_S9multi_set<n>`(#42), 이름 끝은 모두 `_2026-11-06.json`. 원본 경로 · sha256 · 크기 · 단계 커밋은 `sources_2026-11-10.json`. 해석은 루트 [EVAL_REPORT.md](../EVAL_REPORT.md) 3절 3-B · 4절 · 5절
- `results/threads/` — 사용자 분석 thread 확인(11-09). `local_g4_isolation_2026-11-09.json`: 키 없는 compose(합성 데모)에서 체크포인트 재개 · 서버 재시작 · 사용자 A · B 격리 · 같은 승인 두 번을 확인한 14개 항목(모두 통과). `input_regression_2026-11-09.json`: 동결 v1 · v2 120문항의 회로 입력을 기존 connections 경로와 업로드 파서로 읽은 결과가 같은지 대조(모두 같음). `live_smoke_2026-11-09.json`: 동결 v2 4문항을 실제 모델로 돌린 smoke(BM25, 지표 · 예산, 본문 없음)
- `results/grader/` — `grader_baseline_<YYYY-MM-DD>.json`(v2, #36) · `grader_baseline_r1_dev_<YYYY-MM-DD>.json`(R1 dev, #34): 채점기 기준선. 지금 2갈래 채점이 v2 관련 19문항에서 정답 쪽을 얼마나 통과시키는지(정답 쪽 유지율 12/15), 비관련 35문항 중 통과 0개 34건(`eval_grader.py run`)
- `results/skill/` — `skill_tool_summary_2026-11-03.json`: Skill·도구 판단 개발 검증 요약, 미충족 사례·트레이스와 원본 6개 해시. 상세 실행 JSON은 저장소 밖에 보관하며 동결 평가 점수와 구분
- `results/supervisor/2026-11-04-stage1-v1/` — 후보 5종의 `manifest.json`, 문항별 `rows_*.json`, `stage1_summary.json`, `provider_evidence.json`. 1차 선정은 run index 1만 사용하며 manifest의 2·3회차 계획은 실행 결과가 아님
- `results/supervisor/2026-11-04-preflight-v5/`, `2026-11-04-routing-fix-smoke-v1/` — provider evidence가 참조하는 manifest와 호출 증거만 보존. smoke를 1차 품질 점수에 합산하지 않음
- `results/supervisor/2026-11-04-jev-stage1-ready-v1/` — Jev 1차 manifest·70문항 행·smoke·summary. 2차와 짝 비교하는 원본
- `results/supervisor/2026-11-05-stage2-five-v1/`, `2026-11-05-jev-stage2-v1/` — 2차 6종의 manifest·smoke·원시 행. 5종 raw summary는 3회 계획 분모를 쓰므로 2차 집계에는 원시 `run_index=2` 행만 사용
- `results/supervisor/2026-11-05-stage2-comparison-v1/stage2_summary_v2.json` — 2차 6종 정정 집계 정본. 앞서 만든 정의 오류 파일은 PR에 포함하지 않음
- `results/supervisor/2026-11-05-stage3-five-v1/`, `2026-11-05-jev-stage3-v1/` — 3차 사전 등록 #36의 manifest·smoke·문항별 행. 5종 폴더에 6종 공통 공개 catalog preflight·실행 metadata·환경 버전을 함께 보존한다. 5종 manifest의 전체 계획 1,050건 중 `run_index=3`의 350건만 실행하고 Jev는 3차 70건을 실행한다
- `results/supervisor/2026-11-05-stage3-comparison-v1/stage3_summary.json` — 원시 1~3차 행에서 API 없이 재계산한 3차 정본. gold 35문항 점수·전체 70문항 형식 통과·자체 범위 밖 예측의 라우팅 모순·비교 가능한 3회 coverage·agreement/flip과 모든 출처 hash를 담음
- `results/supervisor/2026-11-06-prompt-v0-v1/` — 사전 등록 #37의 Supervisor Prompt V0 세 후보 exact-provider smoke·13건 원시 행·통합 summary·실행 상한과 출처 hash. `langfuse_import.json`은 기존 결과를 가져온 Dataset·Experiment 식별자와 외부 재조회 검증을 기록한다. 기존 v2 70문항 결과와 별도이며 운영 모델을 자동 확정하지 않음

임베딩 결과의 수치와 공통 해석은 루트 [EVAL_REPORT.md](../EVAL_REPORT.md), 후보 13종을 선정한 이유·개별 실행 과정·중단 사유·다음 조건은 [embedding-candidate-investigation.md](../docs/research/embedding-candidate-investigation.md)를 봅니다. 2026-11-02 확장 평가기·실제 PDF 표본·원시 결과는 저장소에 없어 재현할 수 없습니다. 차단 결과는 Recall@5·MRR 0점이나 품질 탈락으로 환산하지 않습니다.

`embedding_sample_v0.jsonl`은 후보를 거른 2026-10-30 비동결 프록시이며 v1·v2나 G5 건수에 포함하지 않습니다. 서비스 임베딩 결정은 이후 TSC 1,360건 실제 청크를 사용한 사전 등록 #25의 R1 dev/test 비교에서 `voyage-4-large` 1024차원으로 완료됐고, 선택 과정과 한계는 루트 [EVAL_REPORT.md](../EVAL_REPORT.md) 1-4절을 따릅니다. 이 결정은 새 v3 평가셋과 v4h 코퍼스의 공식 재측정이 끝났다는 뜻이 아닙니다.

평가셋 필드·정답 기준·동결·채점 방식은 [dataset-guide.md](guides/dataset-guide.md)가 정본입니다.


### 인젝션 준비 산출물 통합(2026-11-10)

`results/threads/`의 기존 인젝션 준비33개는 다음4개로 정리했다. 결과 폴더는 개별 파일을 루트 트리에 나열하지 않는다.
- `injection_baseline_review_2026-11-10.json` — 전체/노출 계획, 최신 모의 실행 메타데이터, 사용자 조건부 승인. 실행 승인 파일 아님
- `injection_baseline_checks_2026-11-10.json` — 서로 다른 무료 검사8건을 원래 해시/시점/범위 그대로 보존. 통과 수나 사람 판정을 합산하지 않음
- `injection_baseline_artifact_index_2026-11-10.json` — 원래33개 경로·Git/작업트리 해시·통합 위치·과거20개 복구 안내·중복/실패 이력
- `injection_exposure_simulated_v3_2026-11-10.jsonl` — 최신4작업 모의 실행 원시 기록, 원래바이트 보존

과거 원본은 STH의 현재 이력에서 분리했고, 로컬 복구 참조 `refs/archive/injection-pre-consolidation-20261110`가 커밋107aaa3을 보존한다. 이 복구 참조는 STH를 공유하는 것만으로 함께 공유되지 않는다. Windows CRLF를 포함한 작업트리 원본의 해시까지 복구 검증했다. 앞으로 실행기가 새 JSONL/meta를 생성하는 동작은 변경하지 않았다. 기존 code_freeze 기록은 이번33개 밖의 파일이므로 유지한다.
