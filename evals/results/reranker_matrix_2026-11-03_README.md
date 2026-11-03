# 리랭커 18조합 공개 결과

이 폴더의 `reranker_matrix_2026-11-03_summary.json`은 임베딩 6종 × API 리랭커 3종의 최종 18행 요약이다. 카드 본문·벡터·키·Authorization 헤더·request ID는 포함하지 않는다. 원시 실행 파일은 크기와 공개 경계 때문에 저장소 밖에 보존하며, 세 실행 묶음의 역할과 SHA256은 `reranker_matrix_2026-11-03_provenance.json`에 기록한다.

## 결과 범위

- 평가셋: 동결 v1 50건 중 데이터시트 위치 gold가 있는 관련 문항 19건
- 코퍼스: 재구성 카드 52,228개, 서로 다른 본문 45,898개
- 공식 기준 52,244카드보다 16카드 적으므로 공식 전체 코퍼스와 동일한 실행으로 간주하지 않는다.
- 검색: 정확 cosine Dense 50 + BM25 양수 점수 50 → RRF `k=60` → 최대 100후보 → 리랭커 → 상위 5개
- 결과: 18조합 모두 성공, 자동 재시도 0회

## 재현 전 준비

다음 환경변수는 키가 아니라 로컬 평가 자산의 경로다. 벡터 6개와 코퍼스는 용량 때문에 저장소에 포함하지 않는다.

```powershell
$env:SOJAFIT_RERANK_CHUNKS = 'C:\path\to\chunks.jsonl'
$env:SOJAFIT_RERANK_OUTPUT = 'C:\path\to\reranker-output'
$env:SOJAFIT_VECTOR_TEXT_SMALL = 'C:\path\to\text-embedding-3-small.f32'
$env:SOJAFIT_VECTOR_QWEN = 'C:\path\to\Qwen3-Embedding-0.6B.f32'
$env:SOJAFIT_VECTOR_VOYAGE_LITE = 'C:\path\to\voyage-4-lite.f32'
$env:SOJAFIT_VECTOR_VOYAGE_4 = 'C:\path\to\voyage-4.f32'
$env:SOJAFIT_VECTOR_VOYAGE_LARGE = 'C:\path\to\voyage-4-large.f32'
$env:SOJAFIT_VECTOR_KURE = 'C:\path\to\KURE-v1.f32'
```

`.env`에는 실행할 provider에 맞는 `OPENROUTER_API_KEY`, `VOYAGE_API_KEY`, `COHERE_API_KEY`가 필요하다. Qwen·KURE 질의 벡터를 새로 만들 때는 이미 검증된 로컬 모델 캐시만 사용하고 신규 모델을 내려받지 않는다.

## 비용 사전 검사

아래 명령의 끝에 `--preflight-only`를 붙여 먼저 실행한다. 예상 비용이 `--cost-ceiling`을 넘으면 실제 리랭커 요청을 보내지 않는다. 이 상한은 **리랭커 비용만** 다루며 문서·질의 임베딩 비용은 별도다. 또한 새 output 디렉터리에 후보 캐시가 없으면 preflight 과정에서 API 임베딩 모델의 질의 벡터를 만들 수 있다. API 호출 없이 리랭커 비용만 다시 계산하려면 검증된 `candidates-*.json` 캐시가 output 디렉터리에 먼저 있어야 한다. 토큰 계산은 근사 예상치이며 청구 상한을 보장하지 않으므로 별도 여유를 둔다.

## 한 줄 재현 명령

```powershell
uv run python -m evals.evaluate_reranker_matrix --chunks "$env:SOJAFIT_RERANK_CHUNKS" --dataset evals/dataset_v1.jsonl --vector "text-embedding-3-small=$env:SOJAFIT_VECTOR_TEXT_SMALL" --vector "Qwen3-Embedding-0.6B=$env:SOJAFIT_VECTOR_QWEN" --vector "voyage-4-lite=$env:SOJAFIT_VECTOR_VOYAGE_LITE" --vector "voyage-4=$env:SOJAFIT_VECTOR_VOYAGE_4" --vector "voyage-4-large=$env:SOJAFIT_VECTOR_VOYAGE_LARGE" --vector "KURE-v1=$env:SOJAFIT_VECTOR_KURE" --output-dir "$env:SOJAFIT_RERANK_OUTPUT" --cost-ceiling 5.00 --stop-on-first-error
```

실패한 요청은 자동 재시도하거나 다른 모델·provider로 바꾸지 않는다. 재개할 때는 같은 output 디렉터리를 사용하면 완료된 문항을 건너뛴다. 특정 조합만 재개하려면 `--embedding`과 `--reranker`를 함께 지정한다.
