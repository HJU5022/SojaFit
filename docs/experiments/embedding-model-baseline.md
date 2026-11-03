# 임베딩 모델 예비 기준선

## Why

- **페르소나**: Taiwan Semiconductor 다이오드 데이터시트를 검색하는 SojaFit 검색·데이터 담당자
- **상황**: TSC 데이터시트 1,360건을 본격 수집·색인하기 전에 API와 로컬 임베딩 후보를 줄여야 한다.
- **문제**: 공개 벤치마크만으로는 영문 부품명·기호와 한국어 질의가 섞인 프로젝트 검색 품질, 비용, 오프라인 배포성을 판단할 수 없다.
- **측정 지표**: Recall@5, MRR, 1,000청크 임베딩 시간·비용, 질의 1건 지연, 22,000청크 벡터 용량, Docker·오프라인·키 없는 데모 적합성

## Goal

- **해결 목표**: `text-embedding-3-small`, `BAAI/bge-m3`, `nlpai-lab/KURE-v1`, `Qwen/Qwen3-Embedding-0.6B`를 동일한 표본과 검색 조건으로 비교하고 100문서 본평가에 올릴 후보를 정한다.
- **성공 기준**: 30청크·18질의 프록시 표본에서 네 후보의 결과를 같은 형식으로 기록하고, 실행하지 못한 값은 추정치와 구분하며, 한 줄 재현 명령을 남긴다.
- **Out of Scope**: 100개 PDF 수집·재배포, PDF 파싱 품질 평가, 청킹 최적화, BM25·리랭커 결합, 생성 답변 평가, 최종 모델 확정

## What

**Happy Path**

1. 고정된 프록시 청크와 질의를 읽는다.
2. 모델별로 청크와 질의를 dense embedding한다.
3. cosine 유사도 상위 5개를 검색해 Recall@5와 MRR을 계산한다.
4. 1,000청크 임베딩 및 22,000벡터 검색 지연을 측정한다.
5. 원시 JSON과 비교표에 실측 환경·한계를 함께 기록한다.

**Edge Cases**

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | OpenAI·OpenRouter 키 없음 | 벤치마크에서는 API 호출을 생략하고 `not_run_no_key`로 기록한다. 서비스 데모는 등록 질의를 재생하고 미등록 질의는 BM25-only로 검색한다. |
| EC-02 | 로컬 모델 캐시 없음 + 오프라인 | 명시적으로 실패시키며 온라인 다운로드로 자동 전환하지 않는다. |
| EC-03 | 질의의 gold 청크가 없음 | 평가 입력 오류로 종료한다. |
| EC-04 | 모델별 벡터 차원 불일치 | 모델별 별도 행렬에서 검색하고 결과에 실제 차원을 기록한다. |
| EC-05 | CUDA 사용 불가 | CPU 실행 사실을 결과 환경에 기록하고 GPU 결과와 섞지 않는다. |
| EC-06 | 데모 모드의 미등록 질의 | API·벡터 검색을 호출하지 않고 BM25-only로 근거를 찾은 뒤 근거 문장을 추출해 반환한다. |

## How

- 표본: `evals/embedding_sample_v0.jsonl`; 실제 코퍼스가 아니며 공식 제품표의 대표 사양을 재서술한 프록시다.
- 지표: 질의당 gold 1개, `Recall@5 = hit 질의 수 / 전체 질의 수`, `MRR = mean(1 / 첫 gold 순위)`.
- 검색: L2 정규화한 dense vector의 내적, 리랭커 없음.
- Qwen 질의 형식: 문서는 원문 그대로 임베딩하고 질의에만 사전 고정한 영문 instruction을 붙인다. 이는 Qwen 후보 구성의 일부이며 결과를 본 뒤 문구를 튜닝하지 않는다.
- 비교 해석: Recall@5·MRR·다중 근거 Recall@5는 동일한 평가셋과 검색 파이프라인의 품질 비교다. API와 로컬 후보의 지연·시간·비용은 실행 환경이 다른 운영 프로파일이므로 모델 자체의 속도 차이로 해석하지 않는다.
- 지연: warm-up 뒤 wall-clock. 1,000청크 배치와 질의별 임베딩 + 22,000개 exact matrix search를 구분해 기록한다.
- 비용 가정: API는 실제 usage가 없을 때 평균 350토큰/청크와 공식 단가를 사용하며 추정치로 표시한다.
- 용량: pgvector `vector`의 float32 원시 벡터만 계산한다. 본문·메타데이터·행 오버헤드·인덱스는 별도다.
- 결과 표기: 모든 원시 결과에 `proxy_smoke_test`, `dense_only`, 실제 코퍼스가 아님, 22,000개 지연 행렬은 반복 벡터라는 메타데이터를 남긴다.
- 당시 후속 본평가 계획(역사 기록): TSC 데이터시트 1,360건의 실제 청크에서 예비 기본 선택인 `BM25 + text-embedding-3-small`을 기준선으로 두고 임베딩 후보 구성만 KURE와 Qwen으로 각각 바꾸는 계획이었다. 이후 후보군과 운영 방식 검토가 확장됐으므로 현재 본평가 대상·순서·고정 조건은 루트 [EVAL_REPORT.md](../../EVAL_REPORT.md)의 「다음 본평가」와 [embedding-candidate-runner.md](embedding-candidate-runner.md), [embedding-voyage-candidates.md](embedding-voyage-candidates.md)를 따른다.

후속 후보 확장 준비는 `embedding-candidate-runner.md`를 따른다. 추가 후보의 동결 전 실행은 프록시 smoke test이며 이 문서의 기존 4종 결과와 함께 최종 선택 근거로 승격하지 않는다.

## AC (Given-When-Then)

**AC-01 · 검색 지표 계산**
- GIVEN: 모든 질의에 존재하는 gold 청크가 지정됨
- WHEN: 모델 평가를 실행함
- THEN: Recall@5와 MRR, 질의별 첫 gold 순위를 JSON에 기록함

**AC-02 · 실행 불가를 수치로 위장하지 않음**
- GIVEN: API 키 또는 로컬 캐시가 없음
- WHEN: 해당 모델을 평가함
- THEN: 0점 대신 명시적 미실행 상태와 사유를 기록함

**AC-03 · 오프라인 재현**
- GIVEN: 로컬 모델을 한 번 내려받아 캐시에 보관함
- WHEN: 새 프로세스에서 `HF_HUB_OFFLINE=1`로 같은 평가를 실행함
- THEN: 네트워크 다운로드 없이 모델이 로드되고 같은 검색 지표를 냄

**AC-04 · 키 없는 미등록 데모 질의**
- GIVEN: `DEMO_MODE=1`이고 입력 해시에 저장된 응답이 없음
- WHEN: 사용자가 새로운 질의를 입력함
- THEN: 외부 API와 벡터 검색을 호출하지 않고 BM25-only 근거와 추출형 답변을 반환하며 `live_vector_search=false`를 표시함
