# runners

## 역할
- 이 폴더: 평가셋을 동결하고 검색·그래프·Skill 평가를 돌리는 실행 코드를 둡니다. 저장소 루트에서 `uv run python -m evals.runners.<이름>`으로 실행합니다.
- 넣는 것: 평가 실행기(`run_*.py`), 동결 스크립트(`freeze.py`), 임베딩 프록시 측정(`benchmark_embeddings.py`).
- 넣지 않는 것: 평가셋·동결 기록(`evals/`의 `dataset_v1.jsonl`, `FROZEN.json`), 평가 원시 결과(`evals/results/`), 평가셋 명세·사전 등록(`evals/guides/`), 평가가 아닌 측정 스크립트(`scripts/`).
- 담당: 평가

## 파일
- `freeze.py` — 평가셋 sha256·건수를 `../FROZEN.json`에 기록. `uv run python evals/runners/freeze.py dataset_v1.jsonl`(동결), `--check`(동결 뒤 바뀐 파일 검사)
- `benchmark_embeddings.py` — 프록시 표본([embedding_sample_v0.jsonl](../samples/embedding_sample_v0.jsonl))의 dense Recall@5·MRR·지연 측정. `uv run python -m evals.runners.benchmark_embeddings --model bge-m3 --output evals/results/embedding/embedding_bge_m3_proxy_<날짜>.json`
- `run_retrieval.py` — 평가셋 관련 문항으로 `retrieve()`의 문서 Recall@k·MRR·Page Hit@k를 재고 결과 json을 남김. `uv run python -m evals.runners.run_retrieval <평가셋 jsonl> <결과 json> [k] [method]`. 검색 방식은 `hybrid`(기본)·`dense`·`bm25`. 결과는 `../results/retrieval/`에 둠
- `run_retrieval_d3.py` — 사전 등록 #24 D3 공식 검색 측정. 동결 v2 채점 19문항을 [qrels](../inputs/qrels_v2_pages.json)로 재고, 기준(서비스 경로)에서 한 조건씩 바꾼 E1~E8 칸과 필터 끔 재측정·no_result 임계값·탐색 격자를 `../results/retrieval/`에 남김. 청크·벡터는 저장소 밖 파일을 인자로 읽음. `uv run --with docling-core python -m evals.runners.run_retrieval_d3 qrels|official|noresult|chunks|embed <변형>|explore`
- `run_retrieval_r1.py` — 사전 등록 #25 R1 검색 측정. [검색 표본](../samples/retrieval_r1.jsonl) 84문항으로 임베딩 11 × 필터 3 × 질의 2 × 리랭커 4 = 264칸을 dev 세트 46문항에서 줄 세워 상위 3칸을 고르고, test 세트 38문항에서 지금 서비스와 한 번 비교. 검색 · 지표 · 비교는 `run_retrieval_d3.py`를 그대로 씀. `uv run python -m evals.runners.run_retrieval_r1 rewrite|qvec-api|requests|run|steps`(GPU: `gpu-qvec|gpu-rerank`). `steps`는 사전 등록 #28의 한 번에 하나씩 단계별 재측정(S0 지금 서비스 → S4 1위)
- `run_retrieval_service.py` — 사전 등록 #26 서비스 경로 재측정. 실제 `retrieve()`(DEMO_MODE=0)로 R1 84문항 · v2 19문항의 쪽 지표, R1 1위 칸과의 상위 5개 대조, `retrieve()` · `rewrite()` 시간을 재서 `../results/retrieval/service_r1_<날짜>.json`에 남김. db/008 적용과 voyage 적재 뒤 `uv run python -m evals.runners.run_retrieval_service`. `--out <경로>` · `--prereg '#27'`로 비트 후보 검색(사전 등록 #27) 결과를 다른 파일에 남기고, `--compare <정확 json> <비트 json>`은 DB 없이 두 결과 파일의 상위 5개 같음 · Page Recall · 시간을 견줌. `--stages N`은 사전 등록 #28의 단계별 시간(질문 임베딩 · rerank-3 · 나머지)과 rerank 토큰만 잰다.
- `run_graph.py` — 평가셋 문항(전부 또는 고른 id)을 줄기 그래프로 끝까지 돌려 문항마다 Langfuse 트레이스와 실행 점수(경로·검색 횟수·LLM 호출 수·인용 검사·5지표 `answer_metric`·시간)를 남김. `uv run python -m evals.runners.run_graph <평가셋 jsonl> [문항 id ...]`
- `run_supervisor_models.py` — 수퍼바이저 후보 5종을 동결 v2 70건에서 비교. `plan`은 API 없이 최대 3회용 1,050-job manifest, 1,400 pairwise A/B swap 계획, 70건 robustness 계획을 만든다. 1차 선별은 `run ... --run-index 1 --confirm-live`로 모델별 70건만 실행하고, 선정 후보만 `--run-index 2`, `--run-index 3`을 추가한다. `smoke ... --confirm-live`가 호출 가능 여부와 실제 provider를 기록해야 `run`이 같은 provider로 본 실행한다. 이미 exact model·provider 호출 결과가 있으면 `import-evidence <새 폴더> --source <과거 폴더>`가 원본 manifest·artifact hash와 dataset·prompt·provider policy를 검증해 `provider_evidence.json`으로 가져오며, 이를 새 smoke로 위장하지 않는다. schema 실패는 output 실패로 확정하고, rate limit·예산 차단은 재개 가능하게 남긴다. 재개 시 누적 raw-call·비용 상한 차감액을 전체 cap에서 차감하고 provider 오류 3회 연속이면 pause한다. objective summary는 label이 있는 관련 35건의 run별 `Question Type Accuracy`와 전체 70건 stability·usage·latency를 계산하며 gold 없는 35건은 `Known Limitation`에 남긴다
- `score_answer.py` — 평가셋 문항과 그래프 실행 상태를 대조해 답변·거절 5지표(`cited_gold`, `wrong_citation`, `over_refusal`, `correct_refusal`, `hallucination_risk`)를 규칙 기반으로 채점([작업서](../../docs/experiments/answer-refusal-scorer.md)). `uv run python -m evals.runners.score_answer <평가셋 jsonl> <실행 결과 json> [채점 결과 json]`
- `run_skill_pair.py` — preregister #17 순차 평가 실행기. `DEMO_MODE=0 uv run python -m evals.runners.run_skill_pair <새 결과 폴더>`. 동일 상태에서 Skill 유무 답변을 비교하고 요약만 `../results/skill/`에 둠

실행기별 세부 동작(질의 필드, 검색 방식 기록, 비용 계산 등)은 [EVALS.md](../EVALS.md)를 봅니다.
