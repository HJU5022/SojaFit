# samples

## 역할
- 이 폴더: 동결 평가셋이 아닌 보조 표본을 둡니다. 지금은 임베딩 후보를 거르는 프록시 표본 하나입니다.
- 넣는 것: 비동결 프록시 표본(jsonl).
- 넣지 않는 것: 동결 평가셋·동결 기록(`evals/`의 `dataset_v1.jsonl`, `FROZEN.json`), 동결 전 초안(`evals/drafts/`), 표본으로 잰 결과(`evals/results/embedding/`).
- 담당: 평가

## 파일
- `SAMPLES.md` — 이 문서
- `embedding_sample_v0.jsonl` — 임베딩 후보를 거르는 비동결 프록시 표본(30청크·18질의, 48행). v1·v2나 G5 건수에 포함하지 않고 `evals/runners/benchmark_embeddings.py`가 읽음
