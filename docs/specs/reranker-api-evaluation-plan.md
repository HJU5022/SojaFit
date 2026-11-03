# 임베딩 6종 × API 리랭커 3종 실측 실행 계획

작성일: 2026-11-03

상태: **완료(18/18 성공)**. 최초 OpenRouter·Voyage 실패, Cohere 직접 API 후속, KURE × Qwen 수동 재개를 서로 다른 원시 실행으로 보존하고 최종 공개 요약만 저장소에 넣었다. 평가 1위 후보는 `Qwen3-Embedding-0.6B × Voyage rerank-3`이며 런타임 기본값은 바꾸지 않았다.

PR 묶음은 평가기·테스트·사전등록·작업서·공개 결과·보고서를 한 목적의 리랭킹 증거로 함께 검토해야 하므로, 사용자가 이번 리랭킹 PR에 한해 400줄 권고를 넘는 단일 PR 구성을 요청했다. PR 본문에는 규모·한 PR로 묶는 이유·원시 자산 제외 범위를 명시한다.

## 기대 결과

동결 평가셋 v1의 데이터시트 근거 19문항과 재구성 TSC 코퍼스에서 같은 하이브리드 후보를 만들고, Cohere·Voyage 직접 API와 OpenRouter Qwen 리랭커를 각각 적용한다. `EVAL_REPORT.md`에는 18개 조합을 한 표로 남긴다. 재구성 코퍼스는 공식 기준보다 16카드 적으므로 동일 실행으로 표현하지 않는다.

## 실행 단계

1. 중앙 API 경계 확장 → verify: `backend/services/llm.py`가 OpenRouter 임베딩 옵션과 rerank 응답을 정규화하고, 가짜 응답 단위 테스트가 통과한다.
2. 전체 코퍼스 후보 캐시 작성 → verify: 각 임베딩마다 Dense 50 + BM25 50, RRF `k=60`, 최대 100개 후보와 입력 해시가 저장된다.
3. 비용 사전 계산 → verify: 실제 후보 본문의 근사 토큰 예상치와 Cohere search 수를 이용해 모델별·전체 예상 비용이 `$5` 이하인지 API 호출 전에 판정한다. 근사치는 청구 상한이 아니므로 여유 있는 중단 상한을 둔다.
4. 18개 조합 실행 → verify: 조합마다 19문항이 완료되거나 구조화된 실패 상태가 기록되고 자동 재시도 횟수는 0이다.
5. 결과 집계 → verify: 원시 JSON과 `EVAL_REPORT.md`의 18행 값이 재계산 결과와 일치한다.

## 고정 조건

- 평가셋: `evals/dataset_v1.jsonl`, SHA256 `2fef02c2dcd8b49e6edb620e23cbf3860ec95912e1a345ed2b719c9a3db7e42b`
- 평가 문항: 관련 25건 중 데이터시트 위치 근거가 있는 19건
- 코퍼스: `C:/Users/user/Documents/ChatGPT/3차 프로젝트 2/SojaFit/corpus/tsc/chunked-gpu/chunks.jsonl`
- 코퍼스 SHA256: `aa4b9576dfe9a0ac27b178efb9575526e0be4f3442f6f59de328501ebf8871a9`
- 코퍼스 크기: 카드 52,228개, 서로 다른 본문 45,898개
- 질의 글: 동결본의 `input` 전체
- 검색: 정확 cosine Dense 상위 50 + BM25 양수 점수 상위 50 → RRF `k=60`
- 리랭크 후보: RRF 합집합 최대 100개
- 최종 검색 결과: 상위 5개
- 품번 필터·질문 축약·청킹·평가 정답은 변경하지 않는다.

## 자산 재사용과 신규 생성

| 임베딩 | 전체 문서 벡터 | 처리 |
|---|---|---|
| `text-embedding-3-small` | 기존 45,898개 캐시 | 해시·크기 검증 후 재사용 |
| `voyage-4-lite` | 45,898개 완성 | Voyage 직접 API로 새 경로에 생성 |
| `voyage-4` | 45,898개 완성 | Voyage 직접 API로 새 경로에 생성 |
| `voyage-4-large` | 45,898개 완성 | Voyage 직접 API로 새 경로에 생성 |
| `Qwen3-Embedding-0.6B` | 45,898개 완성 | 기존 Docker/Hugging Face snapshot을 네트워크 차단 상태에서 사용 |
| `KURE-v1` | 45,898개 완성 | 기존 Docker/Hugging Face snapshot을 네트워크 차단 상태에서 사용 |

새 모델·tokenizer·snapshot은 다운로드하지 않는다. 로컬 두 모델은 `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, Docker `--network none`에서만 실행한다.

## 구현 파일

- `backend/services/llm.py`: `embed_texts()`의 OpenRouter 모델 옵션과 `rerank_texts()` 중앙 호출 경계
- `tests/test_llm.py`: 인증·요청 형식·응답 정렬·사용량·오류 계약 테스트
- `evals/evaluate_reranker_matrix.py`: 입력 검증, 벡터 재사용/생성, 후보 캐시, 18조합 재개 실행, 비용 장부, 결과 표 생성
- `tests/test_reranker_matrix.py`: 6×3 격자, 최대 100 후보, 지표·비용·실패 행·Markdown 18행 테스트
- `evals/PREREGISTER.md`: 예상 호출량·비용·중단 조건·실행 명령
- `evals/results/reranker_matrix_2026-11-03_summary.json`: 카드 본문을 제외한 최종 18행 공개 결과
- `evals/results/reranker_matrix_2026-11-03_provenance.json`: 세 외부 원시 실행의 역할·해시·코퍼스 차이·한계
- `evals/results/reranker_matrix_2026-11-03_README.md`: 자산 전제·비용 사전 검사·한 줄 재현 명령
- `EVAL_REPORT.md`: 18개 조합 단일 표와 해석

## 비용·중단·재개 계약

- Cohere 리랭커는 `COHERE_API_KEY`, Qwen 리랭커는 `OPENROUTER_API_KEY`, Voyage 임베딩·리랭커는 `VOYAGE_API_KEY`를 사용한다.
- provider 실패 시 다른 모델이나 provider로 자동 전환하지 않는다.
- 전체 비용 상한은 `$5.00`, 자동 재시도는 0회다.
- 첫 유료 요청 전에 실제 후보 텍스트로 근사 토큰·Cohere search 수를 계산한다. KURE × Qwen은 예상 `$0.090980`보다 명목 실측 `$0.103501`이 높았으므로 이 값을 보수적 상한이라고 부르지 않는다.
- 예상액이 `$5.00`을 넘으면 호출하지 않고 `blocked_budget_preflight`로 중단한다.
- 실제 누적 비용 추정이 상한에 닿으면 다음 요청 전에 중단한다.
- 429, 5xx, timeout, 응답 index 중복·범위 초과, 코퍼스/평가셋 해시 불일치가 발생하면 해당 조합을 실패로 기록하고 다음 조합으로 넘어간다.
- 실패 마커가 있는 조합은 이후 평가기 재실행에서도 다시 호출하지 않으며 점수 칸을 비워 둔다. 다른 모델이나 provider로 대체하지 않는다.
- 문항별 진행 JSON을 원자적으로 교체해, 수동 재실행 시 완료된 문항은 다시 과금하지 않는다.
- 키, Authorization 헤더, 원문 API 응답, request ID, 전체 카드 본문은 저장소 결과에 기록하지 않는다.

## 테스트 순서

1. 새 계약 테스트를 먼저 작성하고 부재로 실패하는 RED를 확인한다.
2. `backend/services/llm.py`의 최소 구현 후 서비스 테스트를 GREEN으로 만든다.
3. 격자 평가기 테스트를 작성해 RED를 확인하고 최소 구현으로 GREEN을 만든다.
4. `uv run pytest -q tests/test_llm.py tests/test_reranker_matrix.py tests/test_frozen_evals.py`를 실행한다.
5. 검증된 후보 캐시가 있는 output 디렉터리에서 `--preflight-only`로 입력 해시·벡터·18행·예상 리랭커 비용을 검증한다. 새 디렉터리에서는 후보 생성을 위해 API 질의 임베딩이 발생할 수 있으므로 API 없는 검사라고 부르지 않는다.
6. 비용 상한 통과 시 실제 실행 후 결과 재계산 테스트와 `git diff --check`를 실행한다.

## 완료 기준

- [x] API 호출이 모두 `backend/services/llm.py`를 통과한다.
- [x] 신규 모델 다운로드가 0바이트이며 로컬 모델은 네트워크 차단 상태에서만 실행된다.
- [x] 6개 임베딩의 후보 캐시가 같은 평가 조건으로 생성된다.
- [x] 18개 조합 모두 성공 상태를 가진다.
- [x] 기준·리랭크 지표, ΔMRR, p50/p95, 사용량, 비용, 개선·회귀 문항이 기록된다.
- [x] 공개 summary와 Markdown 표의 18행·9개 핵심 지표가 일치한다.
- [x] 실행 명령·명목 비용·미검증 사항·외부 원시 해시가 작업 기록과 공개 provenance에 남는다.
