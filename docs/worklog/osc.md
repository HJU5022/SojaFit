# 오세창 작업 기록

## 2026-11-03 리랭킹 문서·공개 증거 정합성 보완

- 감사 후 보완: 최종 18행 summary와 세 외부 실행의 역할·SHA256을 `evals/results/`에 공개 가능한 형태로 추가하고, 코퍼스·벡터 경로를 환경변수로 받는 한 줄 재현 명령을 기록했다. 카드 본문·벡터·키·request ID·provider 원문 응답은 포함하지 않았다.
- 보고서 완성: `EVAL_REPORT.md`에 최고 조합의 개선 전후, e04 회귀와 n04 후보 누락, 다중근거 한계, 리랭크 비용·p50/p95, 전체 RAG 미측정 범위, 서비스 미적용 상태를 채웠다. `MRR 순위군`은 실제 값에 맞게 `MRR 순위`로 바로잡았다.
- 문서 동기화: 후보 작업서는 실행 전 양식의 역사 기록이라고 표시하고 최종 표를 연결했다. 실행 계획 완료 체크, provider별 직접 API, 52,228/52,244 카드 차이, 비용 근사치의 비상한 성격, SPEC의 현재 런타임 기본값 유지 상태를 명시했다.
- PR 범위: 사용자가 리랭킹 관련 평가기·테스트·사전등록·작업서·공개 결과·보고서를 400줄 권고와 관계없이 한 PR로 만들 계획이라고 명시했다. 실제 PR 본문에는 규모·한 PR인 이유·외부 원시 자산 제외 범위를 기록해야 한다. 이번 작업에서는 commit·push·PR 생성은 하지 않았다.
- 검증: UTF-8 전체 테스트 `173 passed / 24 skipped`, 동결 해시 변경 0건, 공개 summary와 외부 최종 summary의 논리적 동일성, 보고서 18행·9개 핵심 지표 일치, 공개 JSON의 질문·본문·request id·비밀값 부재, 변경 Markdown 로컬 링크, JSON 파싱, `git diff --check`를 확인했다.

## 2026-11-03 KURE × Qwen 실패 조합 재개 완료

- 원인 확인: 최초 실행은 동일한 Fireworks Qwen3 Reranker 8B로 19문항 중 10문항을 성공한 뒤 HTTP 503에서 멈췄다. OpenRouter 공식 endpoint는 Fireworks 한 곳뿐이며 재개 직전 최근 5분 가동률이 100%로 표시되어, 입력·모델 ID 오류가 아닌 provider의 일시적 가용성 문제로 판단했다.
- 최소 변경: 평가기에 `--embedding` 선택을 추가하고 비용 사전 계산의 search 수가 실제 선택 임베딩 수를 따르게 고쳤다. 기본 6×3 실행 순서는 그대로 유지한다. 새 동작은 RED 3건을 확인한 뒤 관련 테스트 15건을 통과시켰다.
- 실행 조건: 기존 성공 10문항과 후보 캐시를 새 결과 디렉터리에 복사하고 `KURE-v1 × qwen/qwen3-reranker-8b`만 선택했다. 전체 조합 예상 비용 `$0.090980`이 `$0.20` 상한 안임을 확인했으며, 남은 9문항에서 자동 재시도·다른 모델·다른 provider 대체는 허용하지 않았다.
- 결과: 19/19가 모두 같은 Fireworks 모델로 완성됐다. Recall@5 `0.368→0.842`, MRR `0.225→0.677`, 쪽 적중@5 `0.211→0.632`, 다중근거 Recall@5 `0.053→0.316`, p95 `1996.1ms`, 517,503토큰·`$0.103501`, 개선/회귀 11/3이다. 전체 행렬은 18/18 성공이며 1위는 기존 `Qwen3-Embedding-0.6B × Voyage rerank-3`의 MRR `0.882`로 유지됐다.
- 원시 근거: 최초 503 기록은 `SojaFit/evals/reranker-matrix-20261103/`에 보존하고, 재개 결과와 합친 18행은 `SojaFit/evals/reranker-matrix-kure-qwen-resume-20261103/`에 저장했다.

## 2026-11-03 Cohere 직접 API 6조합 완료

- 변경 범위: 기존 `cohere/rerank-4-pro` 후보와 평가 조건은 유지하고 호출 경로만 OpenRouter에서 Cohere 공식 `/v2/rerank`·`COHERE_API_KEY`로 바꿨다. 공식 모델 ID는 `rerank-v4.0-pro`다.
- 무료 키 보호: trial 제한 10 RPM에 맞춰 요청 시작 간격을 6.5초로 고정했다. 전체 114요청의 보수적 입력은 2,933,114토큰, 명목 비용은 `$0.285`였고 실제 trial 청구는 `$0`다. 자동 재시도·provider/model fallback은 없다.
- 결과: Cohere 6조합이 모두 성공해 전체 표는 18행 중 17성공·1실패(KURE × Qwen 503)가 됐다. Cohere 최고 MRR은 `Qwen3-Embedding-0.6B` 조합의 `0.702`, 최고 ΔMRR은 KURE 조합의 `+0.450`이다. 전체 1위는 기존 `Qwen3-Embedding-0.6B × Voyage rerank-3`의 MRR `0.882`로 유지됐다.
- 지연 한계: 이번 Cohere p50/p95에는 trial 호출 간 6.5초 대기가 포함돼 다른 provider의 순수 API 지연과 비교하지 않는다. 성공 호출을 지연만 재측정하려고 반복하지 않았다.
- 원시 근거: 저장소 밖 `SojaFit/evals/reranker-matrix-cohere-direct-20261103/`에 6개 progress JSON, 합친 `summary.json`, `results.md`, `preflight.json`을 보존했다. 기존 OpenRouter 404 원시는 별도 이전 디렉터리에 유지한다.

## 2026-11-03 새 Voyage 키·KURE 완료와 리랭커 18조합 측정

- 임베딩 완료: Voyage Lite/4/Large는 각각 45,898본문·5,773,370토큰을 공식 API로 생성했다. 시간은 442.5/503.6/431.7초, 계산 비용은 `$0.115467/$0.346402/$0.692804`다. KURE는 기존 오프라인 캐시만 사용해 45,898본문을 6,259.6초에 완성했다. 네 파일 모두 187,998,208바이트이며 시작·중간·끝 표본은 유한값·norm 1.0이다.
- 후보 생성: 각 임베딩에서 Dense 50·BM25 50을 RRF k=60으로 결합해 문항당 최대 100후보를 만들었다. KURE 질의 19개는 Docker 네트워크 차단 상태에서 기존 HF·uv 캐시만 사용했다.
- 비용 사전 검사: 18조합 예상 리랭커 비용 `$1.0182785`가 상한 `$5.00` 안임을 확인한 뒤 실행했다.
- 결과: 18조합 중 11조합 성공, 7조합 실패다. Cohere 6조합은 OpenRouter HTTP 404, KURE × Qwen은 HTTP 503이며 재시도·대체 호출은 하지 않았다. 성공 조합 합계는 5,020,556토큰·계산 비용 `$0.65198305`다.
- 1위: Qwen3-Embedding-0.6B × Voyage rerank-3이 Recall@5 `0.789→0.947`, MRR `0.668→0.882`, p95 `572ms`, 회귀 1건으로 가장 높은 MRR을 기록했다. Voyage rerank-3의 성공 6조합은 모두 품질 조건과 p95 2초 조건을 함께 통과했다.
- 원시 근거: 저장소 밖 `SojaFit/evals/reranker-matrix-20261103/`의 `summary.json`, `results.md`, 조합별 progress/failure JSON, 후보 JSON, 벡터 progress JSON에 보존했다.

## 2026-11-03 Voyage 전체 임베딩 최초 실행

- 기준: 임베딩 대상은 본문 sha256 기준 45,898개로 확정했다. 입력 `chunks.jsonl`의 SHA256은 `aa4b9576…`이고, 최대 본문 길이는 1,980자다.
- 비용 사전 검사: Voyage 공식 단가 Lite/4/Large `$0.02/$0.06/$0.12 per 1M tokens`, 예상 593만~647만 토큰을 기준으로 모델별 상한을 `$0.20/$0.50/$1.00`으로 고정했다. 최대 예상 합계는 약 `$1.30`이다. 계정 무료 토큰은 비용 상한 계산에서 가정하지 않았다.
- 실행 결과: `voyage-4-lite`, `voyage-4`, `voyage-4-large`를 사전 지정 순서로 각각 최초 1회 실행했으나, 모두 첫 128본문 배치에서 Voyage 공식 API HTTP 429로 실패했다.
- 중단 조건 적용: 실패 모델을 재시도하지 않았고 다른 모델·provider로 대체하지 않았다. 성공 응답·usage·벡터가 없으므로 9개 조합의 지표와 비용은 `—`로 유지한다.
- 출력 검증: 세 파일은 예상 크기 187,998,208바이트지만 0번·22,949번·45,897번 표본이 모두 0벡터이고 진행 JSON도 없다. 유효 캐시로 사용하지 않는다.
- 근거: [Voyage Pricing](https://docs.voyageai.com/docs/pricing), [Voyage Text Embeddings](https://docs.voyageai.com/docs/embeddings).

## 2026-11-03 Voyage 직접 API 연결

- 목적: OpenRouter ZDR 정책 404로 비어 있던 Voyage 임베딩과 rerank-3을 모델 변경 없이 Voyage 공식 API로 직접 호출한다.
- 키 확인: 루트 `.env`의 `VOYAGE_API_KEY`가 선언되고 비어 있지 않은지만 확인했으며 값은 출력·기록하지 않았다. `.env.example`에는 빈 변수만 추가했다.
- 구현: `backend/services/llm.py`에 공식 `/v1/embeddings`·`/v1/rerank` 직접 호출, `output_dimension`·`top_k`, 응답 index·사용량 검증을 추가했다. 자동 재시도와 provider fallback은 없다.
- 평가기 연결: Voyage 4 계열의 문서·질의 임베딩과 `voyageai/rerank-3`만 직접 API로 라우팅한다. Cohere·Qwen은 기존 OpenRouter 경로를 유지한다.
- RED/GREEN: 직접 API 함수 부재 2건과 평가기 라우팅 부재 2건의 RED를 확인한 뒤 최소 구현했다. 관련 테스트는 21건 통과했다.
- 실제 smoke: 합성 입력으로 `voyage-4-lite` 1개·1,024차원·10토큰, `rerank-3` 2개 문서·33토큰·관련 문서 index 0을 최초 1회에 확인했다. 실패 재시도나 다른 모델 호출은 없었다.
- 최종 검증: `PYTHONUTF8=1 uv run pytest -q`에서 167 passed / 24 skipped, `git diff --check` 통과, `.env`가 Git 추적 대상이 아님과 `.env.example`의 빈 placeholder 1개를 확인했다.
- 다음: 전체 45,898본문 재임베딩과 18조합 재측정은 #17 실패 결과와 분리하고, 직접 API 조건의 예상 비용·명령을 확인한 뒤 실행한다.

## 2026-11-03 리랭커 18조합 실측 준비

- 목적: 임베딩 6종 × OpenRouter 리랭커 3종을 전체 동결 검색 조건에서 빠짐없이 비교한다.
- 구현: 중앙 `embed_texts()`에 모델별 옵션을 추가하고 `rerank_texts()`를 만들었다. 전체 코퍼스 벡터 생성기와 최대 100후보·비용 사전 계산·문항별 재개·18행 출력 평가기를 추가했다.
- TDD: 새 계약이 없어 실패한 서비스 테스트 3건과 평가기 import RED를 먼저 확인했다. 최소 구현 뒤 `tests/test_llm.py`, `tests/test_reranker_matrix.py`, `tests/test_frozen_evals.py` 합계 16건이 통과했다.
- 자산 검수: 전체 코퍼스는 52,228카드·45,898본문·SHA256 `aa4b9576…`다. 기존 3-small 벡터는 표본 norm 1.0으로 정상이나 Voyage Lite/4 파일은 크기만 맞고 표본이 모두 0벡터라 재사용에서 제외했다.
- 예산: 3-small의 5,392,291토큰 실측을 기준으로 Voyage 3종 새 문서 벡터 예상 비용은 약 `$1.079`다. 리랭커 비용은 후보 생성 뒤 다시 사전 계산하며 전체 상한은 `$5.00`, 자동 재시도는 0회다.
- 변경 파일: `backend/services/llm.py`, `backend/services/README.md`, `evals/build_reranker_matrix_vectors.py`, `evals/evaluate_reranker_matrix.py`, `evals/PREREGISTER.md`, `evals/README.md`, `tests/test_llm.py`, `tests/test_reranker_matrix.py`, `tests/README.md`, `docs/specs/reranker-api-candidates.md`, `docs/specs/reranker-api-evaluation-plan.md`, `docs/specs/README.md`, `docs/worklog/osc.md`.
- 다음: Voyage 3종 벡터를 새 외부 캐시에 생성하고 Qwen/KURE는 기존 캐시를 네트워크 차단 상태에서 생성한 뒤, 실제 후보 기준 비용 사전 검사를 통과할 때만 18조합을 호출한다.
- 실행 결과: Voyage Lite/4/Large는 각 모델의 최초 문서 임베딩 요청에서 OpenRouter ZDR 정책 404로 중단했고 재시도하지 않았다. Cohere 4 Pro와 Voyage rerank-3도 최초 smoke에서 HTTP 404로 중단했다. 다른 모델·provider로 대체하지 않았다.
- 로컬 결과: Qwen3-Embedding-0.6B는 네트워크 차단 Docker에서 45,898본문을 1,089.8초에 완성했고 표본 norm 1.0·유한값·파일 크기 187,998,208바이트를 확인했다. KURE는 192본문 뒤 같은 배치에서 4분 이상 정체돼 중단했으며 재시도하지 않았다.
- 리랭커 결과: 3-small × Qwen은 첫 응답 뒤 JSON 정답 위치의 list/tuple 집계 오류로 실패해 지표를 비우고 재호출하지 않았다. 오류는 회귀 테스트로 수정했다. Qwen 0.6B × Qwen 리랭커는 19문항 최초 실행을 완료해 Recall@5 `0.789→0.947`, MRR `0.668→0.728`, 쪽 적중 `0.632→0.842`, 다중근거 `0.368→0.421`, p95 `2.996초`, 548,668토큰·`$0.1097336`, 개선/회귀 5/3을 기록했다. 품질 조건은 통과했지만 p95 2초 조건은 실패했다.
- 공개: `EVAL_REPORT.md` 1-4절에 18행을 모두 기록하고 실패·미측정 17행은 0점 대신 `—`로 비웠다. 외부 실행 상태와 원시 결과는 `SojaFit/evals/reranker-matrix-20261103/`에 보존했다.
- 최종 검증: 외부 상태·성공 결과 JSON 파싱, 결과표 데이터 18행, `git diff --check`를 확인했다. Windows 기본 cp949에서 기존 subset 테스트 1건이 인코딩으로 실패했으나 `PYTHONUTF8=1` 전체 테스트는 163 passed / 24 skipped였다. 관련 평가·서비스 테스트는 기본 환경에서도 22건 통과했다.

## 2026-11-03 API 리랭커 후보 3종 선정

- 목적: 임베딩 6종에 붙일 리랭커를 최신 공식 문서와 원격 저장소 실측 이력으로 좁히고, 이후 실험과 서비스 모두 API만 사용한다는 경계를 고정한다.
- 선정: OpenRouter 단일 키 조건에서 제공되는 품질 후보 `cohere/rerank-4-pro`, 기존 원격 실측과 이어지는 `voyageai/rerank-3`, 공개 모델 계열 대조군 `qwen/qwen3-reranker-8b`를 선택했다. 공급사 최신 Cohere Rerank 5 Pro는 현재 OpenRouter에 없어 제외했다.
- 호출·다운로드 경계: 리랭커는 모두 OpenRouter `/api/v1/rerank`와 `OPENROUTER_API_KEY` 하나를 사용한다. 기존 임베딩 캐시는 사용할 수 있지만 신규 가중치·tokenizer·Hugging Face snapshot은 다운로드하지 않는다. 모든 호출은 `backend/services/llm.py` 경계를 사용하며 키는 `.env` 또는 Secret Manager 밖으로 내보내지 않는다.
- 결과 공개 형식: 6개 임베딩 × 3개 리랭커의 18개 조합을 점수 순으로 선별하지 않고 `EVAL_REPORT.md`의 단일 표에 고정 순서로 모두 싣는다. 실패 행도 삭제하지 않고 상태·사유를 남기며, 미측정값은 0점이 아닌 `—`로 표시한다.
- 바꾼 파일: `docs/specs/reranker-api-candidates.md`, `docs/specs/README.md`, `docs/worklog/osc.md`.
- 검증: OpenRouter 공식 rerank API·모델 목록·가격에서 세 모델의 제공 여부와 ID를 대조하고, 작업서의 Why·Goal·What·How·AC 다섯 절 및 단일 키·신규 다운로드 금지·과금 전 승인·실패 분리 조건을 확인했다. 모델 다운로드와 API 호출은 하지 않았다.
- 다음 할 일: 사용자가 작업서를 검토한 뒤, 평가 실행 전에 `evals/PREREGISTER.md`에 18개 조합의 예상 토큰·비용 상한·timeout·중단 조건을 기록하고 별도 실행 승인을 받는다.

## 2026-11-02 동결 100문서 API 리랭커 실행 준비

- 목적: 성공 임베딩 5종의 기존 BM25·Dense·RRF 결과에 같은 `qwen/qwen3-reranker-8b` API 리랭커만 추가해 후보 회수와 최종 순위 개선을 분리한다. 전체 1,360문서 본평가나 최종 모델 확정으로 세지 않는다.
- 고정 조건: 동결 19질의, TSC 100문서·4,305카드, 기존 문서 벡터와 모델별 query 입력, Dense/BM25 각 50, RRF k=60을 유지한다. RRF 상위 50만 리랭킹하며 후보 hit@50과 Recall@5·MRR·쪽 적중·다중근거 Recall을 기록한다.
- 예산·명령: 신규 다운로드 0, 최대 4,750쌍, 예상 `$0.05~0.25`, 질의 임베딩 포함 누적 `$0.50`, retry 0. 명령은 `evals/PREREGISTER.md`의 고정 API 리랭커 사전등록에 기록했다.
- 중단 조건: 입력 해시·벡터 크기 불일치, 키·정책·HTTP 오류, 응답 index 계약 위반, 120초 timeout, 누적 비용 상한 도달 시 중단한다. 로컬 모델로 자동 전환하거나 계정 정책을 바꾸지 않는다.
- 준비 변경: `backend/services/llm.py`에 중앙 `rerank_texts()` 경계를 추가하고, `evals/evaluate_frozen_reranker.py`와 네트워크 없는 계약 테스트를 작성한다. 실제 유료 호출 전 관련 테스트와 문서 정합성을 확인한다.
- 실행 전 미확인 항목: API endpoint 성공 여부, provider·실제 토큰·비용·지연, 후보 hit@50과 리랭킹 품질.
- 실행 결과: Qwen 임베딩 후보는 11/19 완료 뒤 OpenRouter HTTP 503으로 중단했다. 자동 재시도하지 않고 당시 오류 JSON을 보존했으며, 사용자 승인 뒤 완료 행을 건너뛰고 남은 8건을 수동 1회 재개했다. 나머지 4종은 중단 없이 완료했다.
- 품질 결과: E5+Qwen 리랭커가 문서 Recall@5/MRR `1.000/.868`, Qwen Embedding 8B+Qwen 리랭커가 쪽 적중/다중근거 `.895/.526`으로 각각 선두였다. Perplexity는 Recall이 1.000으로 올랐지만 MRR은 `.763→.739`, Qwen의 n08은 RRF 5위에서 리랭킹 Top 5 밖으로 밀려 전 지표 개선은 아니었다.
- 비용·지연: 전체 1,439,981토큰·`$0.28602983`로 승인한 `$0.50` 안이다. 리랭커 p95는 Titan 1.32초~Perplexity 1.99초였다. 모델 다운로드는 없고 API 자동 재시도는 0회다.
- 공개·한계: 평가기, 테스트, 모델별 순위 JSON, 503 오류 JSON, 요약 JSON과 비교 문서를 저장소에 둔다. 카드 본문·벡터·request id·provider 원문·키는 제외한다. 100문서 사후 표본이므로 Qwen 조합을 서비스 적합 우선 후보, E5 조합을 문서 검색 대조 후보로만 두고 런타임·DB는 바꾸지 않는다.
- 검증: UTF-8 전체 `uv run pytest -q`는 117 passed / 18 skipped, 리랭커 JSON 13건 파싱·본문/키/request id 필드 부재, 요약-비용 장부 일치, 중앙 서비스 밖 직접 API 호출 0건, 변경 문서 상대 링크 누락 0건, 비밀값 패턴 0건, `git diff --check` 통과를 확인했다. `gitleaks` 실행 파일은 로컬에 없어 동일 범위 정규식 검사를 대신했으며 실제 CI Secret Scan은 아직 실행되지 않았다.

## 2026-11-02 동결 질의·100문서 관리형 API Hybrid 사후 비교 공개

- 목적: 동결 50건 중 데이터시트 gold가 있는 19질의에서 관리형 API 후보의 Dense와 BM25/RRF Hybrid를 같은 TSC 100문서 표본으로 비교하고, 전체 1,360문서 본평가의 우선 후보를 정한다. 코퍼스 표본은 결과 전 사전 등록된 본평가 입력이 아니므로 사후 탐색으로 표시한다.
- 고정 조건: 100문서·4,305카드·고유 본문 4,056개, Dense/BM25 각 상위 50, RRF k=60, top-5, 품번 필터·리랭커·HNSW 없음, retry 0. 데이터셋 SHA-256 `2fef02c2...`, 청크 SHA-256 `0b4c81ee...`.
- 실행·비용: OpenRouter 관리형 API 8종을 시도해 5종 성공, BGE는 provider 429, Voyage 4/Lite는 ZDR 정책으로 차단됐다. 총 2,843,356토큰·$0.035611288였고 승인한 $0.10 상한 안이다. 실패 후보를 품질 0점으로 환산하지 않았다.
- 결과: Qwen3 Embedding 8B Hybrid Recall@5 17/19·MRR .695·쪽 적중 12/19로 표본 품질 우선 후보, Perplexity 0.6B는 MRR .763과 비용·지연 대안이다. Qwen의 다중근거 Recall은 Dense .474에서 Hybrid .263으로 낮아져 전 지표 우승으로 표현하지 않는다. 현재 Text Small 기본값은 유지한다.
- 공개 파일: 중앙 `embed_texts` 경계를 쓰는 `evals/evaluate_frozen_embedding_sample.py`, 입력 출처·선택·해시, 모델별 문항 순위·지표·비용·구조화 오류 JSON, Dense/Hybrid 차이 문서를 포함한다. 카드 본문, Docling 본문 JSON, 벡터, API 원문 응답, 키, 모델 캐시는 제외한다.
- 검증 계획: API 재호출 없이 입력 계약·지표·오류 정제 단위 테스트, 동결 해시, JSON 파싱, 문서 수치 대조, 전체 오프라인 pytest와 `git diff --check`를 실행한다. 실제 API 재실행과 전체 1,360문서 본평가는 하지 않는다.
- 다음 할 일: Qwen 8B·Perplexity·Text Small의 전체 코퍼스 조건과 예상 비용을 결과 확인 전에 별도 사전 등록하고 승인받아 최종 모델을 결정한다.

## 2026-11-02 동일 입력 하이브리드 smoke

- 목적·사전 조건: 156카드·9질의·gold·5종 모델 입력을 고정하고 dense → BM25+dense RRF만 변경했다. `evals/PREREGISTER.md`에 기대 Recall/MRR·각 분기 50·RRF 60·모델당 300초·재시도 0을 결과 확인 전에 기록했다.
- 실행: `docker run --rm --gpus all --network none -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e PYTHONPATH=/workspace/.tmp/hybrid-deps:/workspace -v "${PWD}:/workspace" -v sojafit-hf:/root/.cache/huggingface -v sojafit-uv:/root/.cache/uv -w /workspace ghcr.io/astral-sh/uv:python3.12-bookworm-slim sh -c 'for model in bge-m3 kure-v1 qwen3-embedding-0.6b multilingual-e5-large-instruct voyage-4-nano; do timeout 300 uv run --offline --isolated --with sentence-transformers --with torch python -m evals.compare_hybrid_embeddings --model "$model" --sample .tmp/recovered-smoke.jsonl --output "evals/results/hybrid_smoke_${model}_2026-11-02.json"; done'`
- 환경 장애: 첫 uv 의존성 해석에서 Docker 캐시에 rank-bm25가 없어 5개 프로파일 모두 추론 전에 중단됐다. Windows에 설치된 동일 라이브러리의 순수 Python 파일 rank_bm25.py를 .tmp/hybrid-deps에 복사해 네트워크 없이 실행했다.
- 결과: 5종 모두 성공, API·신규 다운로드 0. 하이브리드 Recall/MRR은 모두 dense보다 하락했다. Qwen MRR 0.256·E5 Recall 0.444는 기대 범위 아래였다. BM25 영문·숫자 토큰은 한국어 조건 설명을 반영하지 못했다. 사후 가중치·질의 튜닝은 하지 않았다.
- 검증: 다중 gold·누락 gold·질의 건수 테스트 3건 및 전체 101 passed / 18 skipped. 결과에는 카드 본문 없이 ID만 남긴다. 리랭킹·50건 본평가·API 재호출은 수행하지 않았다.

## 2026-11-02 임베딩 실행 자산 복구

- 이전 로컬 커밋 `87e8768` 전체를 저장소 밖 `backups/embedding-recovery-20261102/pre-reset-snapshot-87e8768.zip`에 보존했다. 현재 OSC는 최신 main `bd224e0`으로 fast-forward했다.
- 확장 프록시·호환성·실제 PDF 원시 JSON 20건과 Voyage 백업 JSON 4건, 평가기·테스트·질의·gold builder를 복구했다. 기존 커밋의 결과 JSON 20건은 Git blob 해시가 모두 일치한다. 동시 API 3종 작업은 별도 패치 백업 후 통합했다.
- Qwen 11-02 오프라인 30청크는 3.634621796초, 실제 PDF는 10.370309006초다. 10-30 Windows 30청크 10.372056300초와 별개 결과임을 원시로 확인했다.
- 공개 대상은 질의·gold 청크 ID·PDF 메타데이터·재생성 명령이며, 156카드 본문은 ZIP과 gitignore 대상 `.tmp/`에 보존한다. 백업 카드로 builder를 실행해 156청크·9질의 재생성을 확인했다. 전체 PDF 재파싱과 모델 추론은 재실행하지 않았다.
- main의 PR #28·#29가 병합된 뒤 복구 변경을 충돌 없이 적용했다. 동결 v1·FROZEN 내용은 변경하지 않았다. Windows CRLF 변환으로 동결 해시가 달라져 Git 원본 LF로 정규화하고 `.gitattributes`에 LF 체크아웃을 명시했다.

> **복구 범위**: 기존 로컬 확장·실제 PDF의 평가기·질의·gold·원시 JSON을 이전 커밋에서 복구했다. 카드 본문은 저장소 밖 백업 ZIP에 보존하고 공개 PDF에서 `.tmp/`에 재생성한다. 아래 과거 시점의 미반영 기록은 당시 상태이며 현재 복구 상태는 이 항목을 따른다.

## 2026-11-02 관리형 API 임베딩 3종 프록시 사전 기록

- 목적: 현재 OpenRouter 임베딩 목록에서 기존 후보와 정확히 대응하는 `openai/text-embedding-3-small`, `voyageai/voyage-4`, `baai/bge-m3`만 같은 30청크·18질의 프록시로 비교한다. 동결 본평가와 최종 모델 확정은 하지 않는다.
- 고정 조건: `evals/embedding_sample_v0.jsonl`, dense cosine `k=5`, 22,000개 exact 지연용 반복 행렬, BM25·필터·리랭커 없음. Text는 1,536차원, Voyage·BGE는 1,024차원이며 Voyage만 query/document 입력 형식을 구분한다.
- 예산: 기존 실행 기준 모델당 약 45,699토큰, 세 모델 약 137,097토큰·$0.00412 예상. 모델당 75,000토큰, 전체 225,000토큰, 총 $0.01을 중단 상한으로 둔다. 자동 재시도는 0회다.
- 중단 조건: 모델 미제공, ZDR·data-policy 차단, 차원·입력 계약 거부, rate limit, 단일 모델 75,000토큰 또는 누적 $0.01 도달 시 해당 실행 또는 전체 실행을 중단한다. 계정 정책은 바꾸지 않고 키 값을 출력하지 않는다.
- 제외: OpenRouter 목록에 없는 Qwen 0.6B, 관리형 endpoint가 동일 모델로 확인되지 않은 KURE·Voyage Nano·E5, 기존 13종 밖의 Voyage 4 Lite는 실행하지 않는다.
- 실행 결과: Text는 Recall@5 1.000, MRR 0.907, 1,000청크 6.87초, p50/p95 902.3/1,704.9ms, 45,699토큰, $0.00091398이었다. BGE API는 1.000, 0.863, 5.01초, 745.6/1,352.6ms, 50,930토큰, $0.0005093이었다.
- 정책 결과: Voyage 4는 계정 ZDR 정책이 유일 endpoint를 제외해 404로 차단됐다. retry 0을 유지하고 계정 정책을 바꾸지 않았으며 Recall@5·MRR·지연·비용을 만들지 않았다.
- 예산 결과: 성공한 두 모델 합계 96,629토큰, $0.00142328로 전체 상한 225,000토큰·$0.01 안이었다. 첫 Text 명령은 `PYTHONPATH` 누락으로 API 전에 `ModuleNotFoundError`가 발생했고 별도 로컬 오류 JSON으로 보존한 뒤 실행 환경만 바로잡았다.
- 해석: 동일 소형 프록시에서 Text가 BGE보다 MRR이 높고 BGE가 빠르고 저렴했지만 Recall@5가 둘 다 포화됐다. 실제 코퍼스와 동결 gold가 아니므로 후보를 확정하지 않는다.

## 2026-11-02 Voyage 후보 변경 독립 감사 후속

- PR #27 피드백 반영: 2026-11-02 확장 평가기·표본·원시 JSON이 저장소에 없으므로 해당 Recall@5·MRR·지연 상세값과 실행 불가능한 실제 PDF·Voyage 재현 명령을 제출용 `EVAL_REPORT.md`에서 제거하고, 로컬 탐색 이력은 `docs/embedding-candidate-investigation.md`에만 남겼다.
- 후보 정합성: 실제 PDF smoke 성공 기록은 Voyage 4 Nano를 포함한 5종으로 맞췄다. 캐시·원시 결과는 저장소 밖이므로 준비 상태를 `통과`가 아닌 `로컬 기록(저장소 밖)`으로 낮추고, 현재 main의 평가기는 확장 자산이 빠진 `일부 통과`로 표시했다.
- 범위: PR #26은 `main`에 병합됐지만, 리뷰어가 번호·판정 상태·용량·사후 등록·ADR 표현을 후속 PR에서 정리한다고 명시했다. 이 변경에서는 그 항목을 선점하지 않고 원시 근거가 없는 임베딩 상세값만 제출 보고서에서 내렸다.
- 재현성: 평가기가 모든 성공·오류·키 없음 결과에 Python과 `numpy`·`sentence-transformers`·`torch`·`transformers`·`openai` 버전을 기록하도록 바꿨다. 기존 Voyage 원시 결과 4건은 당시 버전을 사후 추정하지 않고 미기록으로 표시했다.
- API 정책: OpenRouter Terms 외에 공식 Privacy Policy·ZDR·provider 데이터 정책 출처를 라이선스 문서에 추가했다. Voyage 4는 정책 차단 상태이며 성공 호출·1,024차원 응답 검증 전 최종 모델로 선정하지 않는다. 계정 정책은 변경하지 않았다.
- 클라이언트 캐시: 지원하는 두 모델 키를 번갈아 호출해도 각 SDK 클라이언트를 한 번만 만들도록 캐시 크기를 2로 맞췄다.
- PR 규모 계획: 이번 변경은 Voyage 후보 2종의 계약·평가기·테스트·원시 결과·보고서를 함께 맞추는 단일 목적이지만 핵심 변경이 400줄을 넘는다. 계약과 결과를 분리하면 같은 PR 안에서 검증 근거가 끊기므로 PR은 나누지 않고, PR 본문에 규모·초과 이유·분리하지 않은 이유를 적는다. 커밋은 `평가기와 테스트` → `계약과 정책 문서` → `원시 결과와 보고서`의 논리 단위로 나눈다.
- 검증: 버전 메타데이터와 두 모델 캐시 테스트는 각각 실패하는 RED를 확인한 뒤 최소 구현으로 통과시켰다. 관련 테스트 41건과 전체 테스트 69건이 통과했고 2건은 기존 조건대로 skip됐다. Voyage JSON 4건 파싱, 변경 Markdown 로컬 링크, 비밀정보 모양 값, `git diff --check`도 확인했다.
- 보고서 연결 보완: `EVAL_REPORT.md`에 13종의 증거 수준별 요약을 추가하고, 후보별 선정·중단 이유의 정본인 `docs/embedding-candidate-investigation.md`와 라이선스 정본을 직접 연결했다. 보고서에는 결과·해석을, 상세 문서에는 모델별 조사 근거를 유지한다.
- 연관 문서 정합성 보완: 초기 4종 기준선 작업서의 후속 계획을 역사 기록으로 표시하고 현재 본평가 문서로 연결했다. `evals/EVALS.md`에는 API 정책 차단과 13종 상세 기록 링크를 추가했으며, 후보 평가기 작업서의 확장 전 상황을 과거형으로 고쳤다. `tests/TESTS.md`에는 Voyage 입력 계약·정책 오류·실행환경 메타데이터·두 모델 캐시 검증을 반영했다.

## 2026-11-02 Voyage 후보 계약과 서비스 경계 보완

- 한 일: Voyage 두 후보 추가가 기존 9+2 후보 작업서와 충돌하지 않도록 전용 5절 계약을 만들고, 후보 registry를 실행 11종·조사 2종으로 정렬했다. 현재 서비스 기본값은 `text-embedding-3-small`·`vector(1536)`이며 Voyage는 평가 후보라는 경계를 `SPEC.md`와 평가 문서에 명시했다.
- 해석 변경: 외부 관리형 API와 팀이 별도 추론 서버에 배포하는 자체 API는 최종 모델 확정 뒤 ADR로 결정한다. 로컬 Recall@5·MRR은 후보 선별 자료로 보존하고, 실제 운영 방식의 동일 동결 표본 결과만 최종 선택에 사용한다. 자체 API라면 모델 이미지·GPU/CPU·메모리 비용도 운영 지표에 포함한다.
- 후보 구분: `text-embedding-3-small`, `voyage-4`, `bge-m3`를 외부 관리형 API 우선 비교 대상으로 적고, Qwen 0.6B는 실행 시 provider 확인 대상으로 뒀다. KURE와 Voyage 4 Nano는 로컬 연구 기준점이면서 자체 추론 API를 택할 경우 운영 후보가 될 수 있다. `voyage-4-lite`는 Nano의 저비용 역할을 비교할 수 있는 미평가 API 후보로만 기록했으며 기존 13종 결과 수에는 넣지 않았다.
- 바꾼 파일: `SPEC.md`, `EVAL_REPORT.md`, `docs/specs/embedding-voyage-candidates.md`, `docs/specs/embedding-candidate-runner.md`, `docs/specs/embedding-candidate-runner-plan.md`, `docs/specs/SPECS.md`, `evals/benchmark_embeddings.py`, `tests/test_benchmark_embeddings.py`, Voyage 결과 JSON 4건, 후보·라이선스 문서와 작업 기록
- 확인 못 한 것: Voyage 4는 현재 계정 ZDR 정책으로 차단돼 있고, 나머지 API 후보도 동결 평가셋에서 아직 같은 조건으로 실행하지 않았다. 모델 제공 여부·가격·provider 정책은 재색인 전에 다시 확인해야 한다.
- 검증: Voyage 입력 메타데이터 테스트가 2건 실패하는 RED를 확인한 뒤 query/document 모드와 자동 prompt 기록을 구현했다. API 정책 오류가 품질 지표를 만들지 않는 테스트를 포함한 관련 테스트 39건, 전체 테스트 67건이 통과했고 2건은 기존 조건대로 skip됐다. 기존 원시 측정값은 바꾸지 않고 고정 입력 메타데이터만 보강했으며 JSON 4건을 다시 파싱했다. 5절 작업서 구조·로컬 Markdown 링크·현재 서비스 기본값·`git diff --check`도 확인했다.

## 2026-11-02 Voyage 4 후보 실행 사전 기록

- 목적: 실제 TSC PDF 3건·156청크·사전 고정 질의 9건에서 로컬 `voyage-4-nano`와 OpenRouter `voyage-4`를 기존 성공 후보와 같은 dense cosine `k=5`로 비교한다. 2차 판정 전 smoke이며 최종 선택에는 사용하지 않는다.
- 고정 조건: 두 모델 모두 1,024차원과 query/document 입력 구분을 사용한다. Nano 모델·코드 revision은 `5fb34e870f49f19e79c94d5e118f5ee730133279`, attention은 `sdpa`다. API 모델 ID는 `voyageai/voyage-4`다.
- 보안 점검: Nano 원격 코드 3,491자를 고정 revision에서 확인했다. 외부 프로세스·네트워크·동적 `eval/exec`·파일 쓰기 패턴은 발견되지 않았으며 이는 완전한 보안 감사를 뜻하지 않는다.
- 예산·중단 조건: Nano 신규 모델·패키지 다운로드 상한 2GiB, API 총비용 상한 `$0.02`, 최대 11요청, 자동 재시도 0회다. OOM·revision 불일치·상한 초과·새 호환성 오류가 나면 해당 후보를 중단한다. 키 값은 읽거나 출력하거나 결과에 저장하지 않는다.
- RED/GREEN: Voyage registry·OpenRouter allowlist·1,024차원·query/document 분리 테스트 8건이 먼저 실패했다. 최소 구현 뒤 관련 테스트 37건이 통과했다. 이 기록과 임베딩 탐색 표 #14·#15를 남길 때는 실제 모델 결과를 아직 보지 않았다.
- 실행 결과: Nano는 Recall@5 0.889, MRR 0.744, 1,000청크 5.29초, 질의 p50/p95 53.9/80.5ms였고 완전 오프라인에서 같은 순위 결과를 재현했다. HF·uv 캐시 합계 증가는 약 0.6GB로 2GiB 상한 안이었다.
- API 차단: 첫 명령은 API 호출 전 `PYTHONPATH` 누락으로 실패해 별도 JSON으로 보존했다. 환경만 교정한 요청은 OpenRouter ZDR/data-policy가 유일 endpoint를 제외해 404로 끝났으며 retry는 0이다. 성공 embedding·usage가 없어 Recall@5·MRR·비용 결과는 없고 계정 정책은 변경하지 않았다.
- 검증: Nano 온라인·오프라인의 Recall@5·MRR·문항별 순위가 모두 일치했다. 전체 테스트는 65건 통과·2건 skip이고 `git diff --check`, 후보 문서 13개 항목, 결과 JSON 상태·usage 부재 검사를 통과했다.

## 2026-11-02 임베딩 후보 11종 개별 조사 기록

- 한 일: 후보 11종을 같은 수준으로 평가했다는 오해를 막기 위해 모델별 선정 이유, 조사·실행 과정, 중단 사유, 현재 증거 수준과 다음 평가 조건을 개별 문서로 정리했다.
- 바꾼 파일: `docs/embedding-candidate-investigation.md`, `docs/model-licenses.md`, `docs/DOCS.md`, `docs/worklog/osc.md`
- 근거 구분: 실제 PDF smoke 완료 4종, 합성 프록시만 완료 1종, 호환성 차단 4종, 조사 전용 2종으로 나눴다. 오류 후보를 품질 0점으로 쓰지 않고 실행되지 않은 후보에는 Recall@5·MRR이 없다고 명시했다.
- 검증: 모델별 2차 제목 11개와 문서 내부 링크를 점검했고, `.venv-windows`의 오프라인 전체 테스트는 60건 통과·2건 skip이었다. `git diff --check`도 통과했다.
- 확인 못 한 것: 2차 판정·동결 평가셋·전체 코퍼스가 없으므로 11종 동일 조건 본평가와 최종 모델 선정은 하지 않았다.
- 다음 할 일: 동결 뒤 우선 5종을 동일 조건으로 평가하고, 호환성 후보는 고정 환경을 해결한 경우에만 추가한다. 약관·연구용 후보는 별도 승인과 결과표로 분리한다.

## 2026-11-02 임베딩 본평가 준비 상태 점검

- 한 일: 2차 판정 전 범위의 마지막 단계로 본평가 시작 조건을 저장소 실물과 Docker 캐시에서 읽기 전용으로 점검했다. 2차 판정·동결·최종 모델 선정은 수행하지 않았다.
- 확인 결과: `data/manifest.jsonl`은 1,360행·청크 수 합계 52,244의 메타데이터를 보유하지만 저장소 PDF는 smoke용 3건뿐이다. `evals/FROZEN.json`, 전체 `chunks.jsonl`, `params.jsonl`, `tsc_datasheet_list.csv`는 없고 `evals/dataset_v1.jsonl`은 2행짜리 형식 예시다. BGE·KURE·Qwen·E5의 평가기에 고정한 정확한 revision snapshot은 `sojafit-hf`에 모두 있다.
- 상태 분류: 고정 revision·오프라인 실행기·지표 기록은 통과, 2차 사람 판정·평가셋 동결·API 기준선 승인은 대기, 전체 1,360건 본문 부재는 차단이다. 이 구분을 `EVAL_REPORT.md`의 본평가 준비 표에 기록했다.
- 검증: Windows 전용 `.venv-windows`에서 `UV_PROJECT_ENVIRONMENT=.venv-windows uv run --offline pytest -q`를 실행해 60건 통과·2건 skip을 확인했고 `git diff --check`도 통과했다.
- 확인 못 한 것: 2차 판정 결과, 동결 gold의 실제 건수·해시, 전체 코퍼스 본문 위치, 동결 평가셋에서의 Recall@5·MRR, CPU 배포 지연은 아직 확인할 수 없다.
- 다음 할 일: 담당자가 2차 판정과 차이 합의를 마치고 전체 본문·동결 파일을 제공하면, 비용 상한을 다시 승인받아 동일 입력·동일 검색 조건에서 API 기준선과 로컬 후보를 실행한다. 최종 확정 뒤에만 별도 확인을 받아 탈락 후보 가중치와 평가용 임시 캐시를 삭제한다.

## 2026-11-02 2차 판정 전 임베딩 호환성 재검증 사전 기록

- 목적: 품질 점수 없이 중단된 GTE, Jina v3, Nomic v2 MoE, Arctic v2를 품질 탈락으로 오해하지 않도록 고정 revision과 공식 사용 조건을 기준으로 호환성 변수 하나씩만 바꿔 재검증한다. 이후 저장소의 실제 PDF 3건 smoke로 연결하되 2차 판정·동결·최종 선택은 하지 않는다.
- 이미 본 오류: GTE는 warmup CUDA `AcceleratorError`, Jina v3는 load의 `custom_st` `ModuleNotFoundError`, Nomic은 `einops` `ImportError`, Arctic은 warmup `AssertionError`다. 공식 고정 revision 자료는 각각 Sentence Transformers 3.0 이상, Jina의 3.1.0 지원, Nomic의 `einops`·`megablocks`, Arctic 설정의 Sentence Transformers 2.7.0·Transformers 4.39.3을 가리킨다.
- 변경 변수: GTE는 attention 구현만 `eager`, Jina는 Sentence Transformers만 3.1.0, Nomic은 공식 runtime extras만 추가, Arctic은 모델 설정의 런타임 버전 조합만 적용한다. 질의·문서·revision·batch·GPU·평가 표본은 고정한다.
- 예산: API 호출·비용 `$0`; 처음 승인한 신규 다운로드 상한은 1 GiB였다. Docling의 Linux Torch/CUDA 의존성이 병렬 다운로드되며 uv 캐시가 5.8GB에서 8.3GB로 늘어 즉시 컨테이너를 중단했고, 사용자가 2026-11-02에 실행 전 5.8GB 대비 총 증가 4 GiB(uv 캐시 9.8GB)까지 추가 승인했다. 기존 모델 가중치 캐시를 사용하며 환경변수 값과 키는 읽거나 출력하지 않는다.
- 실행·중단: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`에서 후보당 변경 후 최대 1회만 실행하며 자동 재시도는 0회다. 동일 오류, 새 오류, GPU OOM, revision 불일치가 발생하면 해당 후보를 중단한다. PDF 파싱 환경은 uv 캐시 9.8GB를 넘으면 중단하고 Hugging Face 모델은 네트워크로 받지 않는다.
- RED/GREEN: `error_metadata` 부재로 2건이 예상대로 실패한 뒤, 오류 형식·메시지 300자·단계·retry 0을 보존하는 최소 구현으로 `tests/test_benchmark_embeddings.py` 26건이 통과했다.
- 호환성 재검증 결과: GTE는 `eager` attention 단일 변경 뒤에도 같은 CUDA device-side assert가 발생해 차단됐다. Jina v3와 Arctic은 요구 버전이 오프라인 uv 캐시에 없어 모델 실행 전에 중단됐다. Nomic은 고정 README가 요구하는 `megablocks`가 커밋이 고정되지 않은 Git 설치여서 알 수 없는 외부 코드를 설치하지 않고 보안상 차단했다. 후보별 추가 재시도는 없었다.
- 비용·용량 결과: API 호출과 비용은 0이다. Hugging Face 볼륨은 실행 전후 모두 10.3GB였고 신규 모델 가중치 다운로드는 없었다. 호환성 패키지도 네트워크로 자동 다운로드하지 않았다.
- 실제 PDF smoke 사전 고정: PDF 본문이나 정답 청크를 보기 전에 `1N4148`, `1N5817`, `BZT52C2V4`에 품번·전기 정격·시험 조건 질문을 3건씩 작성했다. 총 9건이며 gold와 정답 숫자는 아직 넣지 않았다. 실제 3문서 청크 전체에서 dense cosine `k=5`로 Recall@5·MRR을 재는 조건을 임베딩 탐색 표 #13에 기록했다.
- PDF 파싱 추가 승인: Linux Torch/CUDA 패키지의 병렬 다운로드가 중단 중에도 진행돼 uv 캐시가 11.6GB까지 증가했고 사용자가 이 상태를 승인했다. 이후 네트워크 차단 상태에서 압축 해제 archive의 Docling·Torch·pdfplumber import는 성공했으나 Docling 분석 모델이 없어 PDF 3건 모두 파싱 전에 실패했다. 공식 API로 layout `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8` 171,764,371바이트와 table `fc0f2d45e2218ea24bce5045f58a389aed16dc23` 358,236,323바이트를 확인했고 사용자가 두 고정 snapshot에 한해 추가 1GB 상한을 승인했다.
- 실제 PDF 파싱·청킹 결과: 고정 layout/table snapshot과 고정 MiniLM tokenizer `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`를 로컬 경로로 전달했다. 모델 파일 사용량은 505.5MiB, tokenizer는 698,829바이트였다. PDF 3건은 각각 5/6/7쪽, 표 5/6/7개로 파싱됐고 표 숫자 witness는 81/81, 49/49, 385/385가 일치했다. 기존 card chunker는 서로 다른 카드 156개를 만들었다.
- 수동 gold: 모델 결과를 보기 전에 1N4148의 VRRM·VF 조건·trr 조건, 1N5817의 VRRM·VF 조건·IFSM 조건, BZT52C2V4의 VZ/IZT·동적 저항·패키지/전력 청크를 PDF·쪽·표 행으로 대조했다. 전체 156카드와 9질의를 `embedding_real_pdf_smoke_v0.jsonl`에 결합했으며 마지막 질문만 두 gold 청크를 가진다.
- 실제 PDF 로컬 탐색 기록: KURE·BGE·Qwen·E5의 Recall@5·MRR·지연을 기록했지만 평가기와 원시 JSON은 저장소에 반영하지 않았다. 특히 Qwen의 `10.37초`는 기존 Windows 30청크 원시값 `10.372056...초`와 같고 실제 PDF 원시 JSON이 없어 재측정값인지 확인할 수 없다. 따라서 이 상세값은 제출용 `EVAL_REPORT.md`와 모델 선정 근거에서 제외했다. 호환성 차단 4종도 저장소에서 재현할 수 있는 결과로 취급하지 않는다.
- 해석: 3문서·9질의 dense-only smoke에서는 KURE가 가장 높은 MRR이었다. 그러나 네 성공 모델 모두 패키지와 전력 두 근거가 필요한 BZT52C2V4 질문을 top-5에서 놓쳤고, 표본이 작고 품번이 직접 포함돼 최종 선택에는 사용할 수 없다. 2차 판정·동결·전체 코퍼스 본평가 전까지 모든 결과는 최종 결정 부적격이다.

## 2026-11-02 임베딩 확장 후보 프록시 실행 기록

- 목적: 기존 30청크·18질의 프록시와 동일한 dense 검색 조건에서 Qwen 재측정과 GTE, multilingual-E5, Jina v3, Nomic v2, Arctic v2의 Recall@5·MRR·1,000청크 시간·22,000벡터 질의 지연을 측정한다. 동결 전 smoke test이므로 최종 모델 확정 근거로 승격하지 않는다.
- 예산: 신규 핵심 가중치 예상 합계 약 6.8GiB, 캐시·메타데이터 포함 신규 다운로드 상한 9GiB. API는 호출하지 않으며 비용 상한은 $0이다.
- 환경: RTX 5060 Laptop GPU 8GB, Docker `sojafit-hf`·`sojafit-uv` 캐시를 사용한다. BGE-M3와 KURE-v1은 Docker 캐시에 있으며 기존 결과를 재사용한다.
- 원격 코드 점검: GTE, Jina v3, Nomic이 외부 코드 저장소를 참조함을 실행 전에 발견했다. 외부 코드 SHA를 각각 고정하고 `code_revision` 전달·결과 기록 테스트를 추가했다. Arctic는 모델 저장소 내부 코드를 모델 SHA와 같은 값으로 고정했다.
- 실행 명령: `docker run --rm --gpus all -v "${PWD}:/workspace" -v sojafit-hf:/root/.cache/huggingface -v sojafit-uv:/root/.cache/uv -w /workspace ghcr.io/astral-sh/uv:python3.12-bookworm-slim uv run --isolated --with sentence-transformers --with torch python evals/benchmark_embeddings.py --model MODEL --output evals/results/embedding_MODEL_2026-11-02.json`
- 중단 조건: 모델별 OOM·실행 오류·15분 이상 무출력 또는 누적 신규 캐시 9GiB 초과 시 해당 모델을 중단한다. 자동 재시도하지 않고 오류와 단계를 기록한다.
- 실행 결과(로컬 탐색·원시 미반영): Qwen `3.63초`, multilingual-E5의 품질·지연, GTE·Jina·Nomic·Arctic의 오류를 로컬에서 기록했지만 대응 원시 결과와 확장 평가기는 저장소에 반영하지 않았다. Qwen `3.63초`는 검수 가능한 원시가 없으므로 사용하지 않고, 저장소 원시 JSON이 있는 30청크 오프라인 값 `3.83초`만 재현 가능한 기록으로 유지한다. API는 호출하지 않았다.
- 저장·용량 결과: 온라인·오프라인 원시 JSON과 실패 JSON을 `evals/results/embedding_*_2026-11-02.json`에 저장했다. `sojafit-hf` 볼륨은 6.4GB에서 10.3GB로 약 3.9GB 늘어 9GiB 상한 안이었다. 전용 모델 Docker 이미지는 만들지 않고 공통 이미지·uv 캐시와 분리된 모델 볼륨을 사용했다.
- 해석: 성공 5종의 프록시 MRR은 API 0.907, KURE 0.894, Qwen 0.875, BGE 0.863, E5 0.785 순이다. 실패 4종은 품질 탈락이 아니라 현재 고정 환경에서 비교 불가로 둔다. 18질의 프록시 결과를 최종 모델 확정에 사용하지 않는다.
- 후속 정리: 2차 판정까지 끝내고 최종 임베딩 모델을 확정한 뒤 탈락 모델의 정확한 캐시 경로와 회수 용량을 제시해 별도 확인을 받고 로컬 가중치를 삭제한다. 평가 결과와 revision·라이선스 기록은 보존한다.

## 2026-11-02 임베딩 후보 확장 평가기 설계 및 구현

- 한 일: 팀장이 지시한 미평가·연구용 임베딩 후보 비교를 준비하기 위해 실행 후보 9종과 조사 전용 후보 2종을 확정했다. 모델별 query/document 입력 형식, 불변 revision, 라이선스·운영 분류, 키 없는 API 처리, 오프라인 로더와 오류 메타데이터를 평가기에 구현했다. Jina v3는 연구용 실행으로, EmbeddingGemma와 Jina v4는 조사 전용으로 분리했다. 최종 모델 확정은 2차 판정과 평가셋·코퍼스 표본 동결 이후로 유지했다.
- 바꾼 파일: `evals/benchmark_embeddings.py`, `tests/test_benchmark_embeddings.py`, `tests/TESTS.md`, `docs/model-licenses.md`, `docs/DOCS.md`, `docs/specs/embedding-candidate-runner.md`, `docs/specs/embedding-candidate-runner-plan.md`, `docs/specs/embedding-model-baseline.md`, `docs/specs/SPECS.md`, `docs/worklog/osc.md`
- 실행한 명령과 결과: catalog 부재 RED 4건, 입력 어댑터 부재 RED 11건, 실행 메타데이터 부재 RED 5건, 라이선스 문서 부재 RED 1건을 확인했다. GREEN에서 후보 테스트 15건과 중앙 API 경계 포함 21건이 통과했고, 최종 전체 가벼운 테스트는 46건 통과·2건 skip이었다. 공식 모델 카드와 라이선스를 2026-11-02에 다시 확인해 8개 로컬 실행 후보와 조사 후보 2개의 40자리 revision을 고정했다. 모델 다운로드와 API 호출은 하지 않았다.
- 확인 못 한 것: 신규 후보의 실제 모델 로드·다운로드 크기·VRAM, `HF_HUB_OFFLINE=1` 재실행, 프록시 Recall@5·MRR·지연, 동결 평가셋과 실제 코퍼스 표본 결과는 아직 측정하지 않았다.
- 다음 할 일: 2차 판정과 50건 평가셋·코퍼스 표본 동결 뒤 사전등록 조건을 확정하고, 비용·다운로드·중단 조건을 먼저 승인받아 실행 후보를 같은 환경에서 비교한다.

## 2026-10-30 임베딩 평가 리뷰 반영

- 한 일: 예비 기본 선택인 `text-embedding-3-small`과 본평가 기준선을 일치시켰다. `BM25 + text-embedding-3-small`을 기준선으로 두고 KURE와 Qwen 후보 구성을 각각 한 번에 하나만 바꾸도록 사전등록·평가 리포트·작업서를 정렬했다. 검색 품질 지표와 실행 환경이 다른 운영 프로파일을 분리하고, 로컬 지연이 RTX 5060 Laptop GPU 측정값이며 2026-10-30 배포 기준 Cloud Run CPU 1 vCPU·메모리 512 MiB를 대표하지 않는다는 점을 각 로컬 행에 연결했다. 로컬 모델 배포 시 메모리 증설·CPU 재측정이 필요하다는 점도 추가했다.
- 바꾼 파일: `evals/PREREGISTER.md`, `EVAL_REPORT.md`, `docs/specs/embedding-model-baseline.md`, `docs/worklog/osc.md`
- 실행한 명령과 결과: 머지된 `origin/main`을 `OSC`에 fast-forward하고 기준선 관련 문구를 `rg`로 대조했다. Docker의 `uv sync --frozen --dev --offline` 뒤 전체 테스트를 실행해 3건이 통과했다.
- 확인 못 한 것: Cloud Run CPU 환경의 실제 임베딩 지연, 로컬 모델별 최소 메모리, 100문서 실제 청크의 본평가 결과는 아직 측정하지 않았다.
- 다음 할 일: 100문서 실제 청크와 교차 라벨한 질의가 준비되면 API 기준선, KURE, Qwen을 사전등록 조건 그대로 비교한다.

## 2026-10-30 임베딩 모델 예비 기준선

- 한 일: 실제 코퍼스 수집 전에 `text-embedding-3-small`, `bge-m3`, `KURE-v1`, `Qwen3-Embedding-0.6B` 후보를 거르기 위한 30청크·18질의 프록시 표본과 재현 스크립트를 만들었다. 로컬 세 모델의 Recall@5, MRR, 1,000청크 처리 시간, 22,000벡터 exact search 지연을 같은 RTX 5060 Laptop GPU에서 측정하고 `HF_HUB_OFFLINE=1` 재실행을 확인했다. 사용자가 비용을 확인하고 약 2원 한도 실행을 승인한 뒤 OpenRouter의 `openai/text-embedding-3-small`도 같은 표본으로 측정했다. 이 실행은 결과를 보기 전 기대 범위를 적지 못한 탐색적 smoke test라 G5 개선 실험으로 세지 않는다. 원격 최신 main `44dadbf`를 fast-forward로 반영한 뒤, 최신 데모 규칙에 맞춰 미등록 질의의 BM25-only 추출형 fallback과 실제 100문서 후속 평가를 문서화했다.
- 실험 조건과 승인 근거: 목적은 네 후보의 검색 품질·지연·비용·오프라인 적합성을 같은 프록시에서 비교하는 것이다. 청크 30개, 질의 18개, dense cosine, gold 1개, 리랭커 없음, RTX 5060 Laptop GPU를 고정했다. API 예산 상한은 약 2원으로 사용자가 비용 안내 뒤 승인했고, Qwen 추가도 약 1.21GB 다운로드·API 비용 $0 안내 뒤 사용자가 명시적으로 요청했다. 오류·OOM·사용자 중단 시 반복 호출하지 않는 것을 중단 조건으로 뒀고 Qwen query instruction은 실행 전에 영문 한 문장으로 고정했다. 단, 이 조건을 저장소 worklog에 적은 시점은 실행 뒤 규칙 검수 때였으므로 다음 무거운 실험부터는 명령 실행 전에 기록한다.
- 바꾼 파일: `SPEC.md`, `backend/services/llm.py`, `backend/services/SERVICES.md`, `tests/test_llm.py`, `tests/TESTS.md`, `docs/specs/embedding-model-baseline.md`, `docs/specs/SPECS.md`, `evals/embedding_sample_v0.jsonl`, `evals/benchmark_embeddings.py`, `evals/EVALS.md`, `evals/PREREGISTER.md`, `evals/results/embedding_*_2026-10-30.json`, `EVAL_REPORT.md`, `docs/worklog/osc.md`
- 실행한 명령과 결과: 로컬 후보는 Docker의 `uv run --offline --isolated --with sentence-transformers --with torch`로 최종 비교했다. `bge-m3`는 Recall@5 1.000, MRR 0.863, 1,000청크 5.95초였고 `KURE-v1`은 Recall@5 1.000, MRR 0.894, 1,000청크 5.68초였다. Qwen은 Recall@5 1.000, MRR 0.875, 1,000청크 3.83초, 질의 p50/p95 61.8/82.9 ms였으며 캐시 snapshot 경로를 직접 로드해 `HF_HUB_OFFLINE=1`을 통과했다. 최초 Windows 임시 환경 결과는 10.37초, 43.7/49.0 ms였으나 실행 환경이 달라 비교표에서 제외하고 원시 JSON으로만 보존했다. OpenRouter API 결과는 Recall@5 1.000, MRR 0.907, 1,000청크 7.02초, 질의 p50 918.7 ms였다. 전체 API 사용량은 45,699토큰, $0.000914였다. 첫 실행에서 22,000행 생성의 `numpy.tile` 축 오류를 재현해 행 방향 반복으로 수정한 뒤 재실행했다. 저장소 규칙 검수에서 API 직접 호출을 발견해 `backend/services/llm.py`의 단일 임베딩 호출 경계로 옮겼고, `embed_texts` 부재로 실패하는 RED를 확인한 뒤 mock client 계약 테스트를 통과시켰다.
- 확인 못 한 것: 100개 PDF 실제 청크, CPU/Cloud Run 지연, 최종 Dockerfile의 압축 이미지 크기는 아직 측정하지 않았다.
- 다음 할 일: `PREREGISTER.md` #1·#2의 고정 조건대로 100개 PDF 실제 청크와 사람이 교차 라벨한 질의에서 `BM25 + text-embedding-3-small`을 기준으로 KURE와 Qwen 후보 구성을 각각 비교한다. 그 뒤에만 `vector(N)`과 Migration 2를 확정한다.

## 2026-10-30 DB 테이블 정의서 초안 작성

- 한 일: SojaFit의 사용자, 회로, 부품·문서, 분석·판정, 승인 견적 데이터를 위한 테이블 정의서 초안을 작성했다. LangGraph 관리 테이블과 직접 관리하는 업무 테이블을 구분하고, `pgvector`·ERD·Migration은 현재 범위에서 제외했다. 확정되지 않은 항목은 가정·미정 및 추가 검토 항목 A-01~A-20으로 분리했다.
- 바꾼 파일: `db/table-definition.md`, `db/DB.md`, `docs/worklog/osc.md`, `docs/worklog/WORKLOG.md`
- 실행한 명령과 결과: `git branch --show-current`로 `OSC` 브랜치를 확인했다. `git diff --check`와 Markdown 구조·미정 항목 검색으로 문서 형식과 검토 항목을 확인했다.
- 확인 못 한 것: 로그인 방식, 사용자 ID 형식, 회로 파일 저장 방식, 판정·역할·사양 코드, 삭제 정책은 팀 합의 전이라 확정하지 않았다. ERD, Migration SQL, `pgvector` 구조는 작성하지 않았다.
- 다음 할 일: 팀이 정의서와 추가 검토 항목을 검토한 뒤 관계와 코드 정책을 확정하고 ERD를 작성한다.
