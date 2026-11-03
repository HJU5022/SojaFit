# runners

## 역할
- 이 폴더: 평가셋을 동결하고 검색·그래프·Skill 평가를 돌리는 실행 코드를 둡니다. 저장소 루트에서 `uv run python -m evals.runners.<이름>`으로 실행합니다.
- 넣는 것: 평가 실행기(`run_*.py`), 동결 스크립트(`freeze.py`), 임베딩 프록시 측정(`benchmark_embeddings.py`).
- 넣지 않는 것: 평가셋·동결 기록(`evals/`의 `dataset_v1.jsonl`, `FROZEN.json`), 평가 원시 결과(`evals/results/`), 평가셋 명세·사전 등록(`evals/guides/`), 평가가 아닌 측정 스크립트(`scripts/`).
- 담당: 평가

## 파일
- `freeze.py` — 평가셋 sha256·건수를 `../FROZEN.json`에 기록. `uv run python evals/runners/freeze.py dataset_v1.jsonl`(동결), `--check`(동결 뒤 바뀐 파일 검사)
- `benchmark_embeddings.py` — 프록시 표본([embedding_sample_v0.jsonl](../samples/embedding_sample_v0.jsonl))의 dense Recall@5·MRR·지연 측정. `uv run python -m evals.runners.benchmark_embeddings --model bge-m3 --output evals/results/embedding/embedding_bge_m3_proxy_<날짜>.json`
- `run_retrieval.py` — 평가셋 관련 문항으로 `retrieve()`의 문서 Recall@k·MRR·쪽 적중@k를 재고 결과 json을 남김. `uv run python -m evals.runners.run_retrieval <평가셋 jsonl> <결과 json> [k] [method]`. 검색 방식은 `hybrid`(기본)·`dense`·`bm25`. 결과는 `../results/retrieval/`에 둠
- `run_graph.py` — 평가셋 문항(전부 또는 고른 id)을 줄기 그래프로 끝까지 돌려 문항마다 Langfuse 트레이스와 실행 점수(경로·검색 횟수·LLM 호출 수·인용 검사·5지표 `answer_metric`·시간)를 남김. `uv run python -m evals.runners.run_graph <평가셋 jsonl> [문항 id ...]`
- `score_answer.py` — 평가셋 문항과 그래프 실행 상태를 대조해 답변·거절 5지표(`cited_gold`, `wrong_citation`, `over_refusal`, `correct_refusal`, `hallucination_risk`)를 규칙 기반으로 채점([작업서](../../docs/experiments/answer-refusal-scorer.md)). `uv run python -m evals.runners.score_answer <평가셋 jsonl> <실행 결과 json> [채점 결과 json]`
- `run_skill_pair.py` — preregister #17 순차 평가 실행기. `DEMO_MODE=0 uv run python -m evals.runners.run_skill_pair <새 결과 폴더>`. 동일 상태에서 Skill 유무 답변을 비교하고 요약만 `../results/skill/`에 둠

실행기별 세부 동작(질의 필드, 검색 방식 기록, 비용 계산 등)은 [EVALS.md](../EVALS.md)를 봅니다.
