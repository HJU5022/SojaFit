# tests

## 역할
- 이 폴더: PR마다 CI가 돌리는 회귀 테스트를 둡니다. `pytest.ini`가 이 폴더를 가리키므로 루트 직속에 평면으로 둡니다.
- 넣는 것: 모듈별 테스트(`test_<모듈>.py`), 동결 감시, 핵심 질문이 근거를 붙여 답하는지 보는 평가 회귀 테스트, 단위 테스트용 가공 회로(`fixtures/`).
- 넣지 않는 것: 평가셋 전체 실행(`evals/`). GitHub Actions 무료 한도가 있어 PR마다 평가 전체를 돌리지 않고 샘플만 돌립니다.
- 담당: 각 모듈의 담당 (`test_frozen_evals.py`는 평가·문서)

## 파일
- `test_health.py` — `/health` 응답 확인
- `test_auth.py` — 인증 단위 및 DB 통합 테스트(두 사용자 세션 격리, 비활성 사용자, 실패 구간·잠금 경계, 30분 유휴·8시간 절대 만료 경계, scrypt 동시 검증 상한, HTTPS 쿠키·출처, DB 오류). CI는 격리 PostgreSQL을 제공하며, 로컬에서는 테스트 전용 `TEST_AUTH_DATABASE_URL`이 없으면 DB 시험을 건너뜀
- `test_frozen_evals.py` — `evals/FROZEN.json`에 기록된 파일의 해시가 바뀌지 않았는지 확인. `FROZEN.json`이 없으면 검사하지 않고 통과합니다
- `test_llm.py` — API 호출 없이 mock client로 중앙 임베딩 호출의 벡터·사용량·provider metadata 반환 계약 확인
- `test_rag_chunk.py` — 표 카드 규칙(합친 칸 채우기, 머리 행 두 줄 잇기, 빈 표)과 문서 키, `data/manifest.jsonl`이 512,000바이트 아래인지
- `test_rag_ingest.py` — 벡터 캐시 다시 열기와 끊긴 쓰기 복구, 없는 본문만 임베딩. DB 재실행(행이 늘지 않고 API를 다시 안 부름, manifest에 없는 공통 값을 `DOC_DEFAULTS`로 채움) 시험은 `TEST_DATABASE_URL`을 줄 때만
- `test_rag_retrieve.py` — RRF 순서, BM25 토큰(한국어 조사), `gold_chunks`에서 정답 문서·쪽 읽기, 표지 카드 → 품번 색인과 품번 전체 일치 필터, BM25 0점 제외, 데모 모드에서 임베딩 API 안 부름, 평가 대상 0건 오류. 실제 DB 시험은 `TEST_DATABASE_URL`(로컬 compose DB)을 줄 때만
- `test_rag_collect.py` — xlsx 목록 합치기, manifest로 받기(파일 이름은 `source_url` 끝, sha256 대조, PDF 아님·해시 다름은 failed.csv), 다시 돌리면 건너뛰기
- `test_rag_parse.py` — 숫자 세기(µ 통일), 표 좌표 바꾸기, SIGALRM 지원 여부
- `test_rag_subset.py` — 분류별 사본·입력 보존·관련 gold 누락·기존 출력·불완전/중복 카드 오류, 카드 수 기준 벡터 payload 추정
- `test_rag_storage.py` — 형식 설정 검증, 실제 시험 DB의 halfvec 전환·재실행·이진 재적재·정확 검색, 같은 본문 제외·시간/표본 부족 표시. DB 시험은 전용 TEST_DATABASE_URL 필요
