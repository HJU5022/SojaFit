# tests

## 역할
- 이 폴더: PR마다 CI가 돌리는 회귀 테스트를 둡니다. `pytest.ini`의 `testpaths = tests`가 이 폴더를 가리키므로 하위 폴더 없이 `tests/` 바로 아래에 둡니다.
- 넣는 것: 모듈별 테스트(`test_<모듈>.py`), 동결 감시, 핵심 질문이 근거를 붙여 답하는지 보는 평가 회귀 테스트, 단위 테스트용 가공 회로(`fixtures/`).
- 넣지 않는 것: 평가셋 전체 실행(`evals/`). GitHub Actions 무료 한도가 있어 PR마다 평가 전체를 돌리지 않고 샘플만 돌립니다. 샘플 평가 회귀 테스트는 답변 생성이 생긴 뒤 더하며, 지금은 없습니다.
- 담당: 각 모듈의 담당 (`test_frozen_evals.py`는 평가·문서)

## 파일
- `test_health.py` — `/health` 응답과 미구현 루트 화면의 404 확인
- `test_auth.py` — 인증 단위 및 DB 통합 테스트(세션 HMAC과 키 누락·교체, 데모 시드 기본값·사용자 지정·불완전 설정·모드 제한, 두 사용자 세션 격리, 관리자와 일반 사용자 권한, 비활성 사용자와 세션 폐기, 실패 구간·잠금 경계, 30분 유휴·8시간 절대 만료 경계, scrypt 동시 검증 상한, HTTPS 쿠키·출처, DB 오류, 비밀번호 해시 전용 CLI). CI는 격리 PostgreSQL을 제공하며, 로컬에서는 테스트 전용 `TEST_AUTH_DATABASE_URL`이 없으면 DB 시험을 건너뜀
- `test_frozen_evals.py` — `evals/FROZEN.json`에 기록된 파일의 해시가 바뀌지 않았는지 확인. 지금은 v1(`dataset_v1.jsonl`, 2026-11-02 동결)을 검사하며, `FROZEN.json`이 없으면 검사하지 않고 통과합니다
- `test_llm.py` — API 호출 없이 가짜 모델로 임베딩 반환 계약과 `chat()`의 형식 검증·재시도 상한(호출 3번)·구독 CLI 명령 확인
- `test_graph_state.py` — 그래프 상태의 `tries`·`path`는 쌓이고 나머지 칸은 덮어써지는지 확인
- `test_graph_route.py` — 라우팅 노드: 가짜 LLM으로 `route.md` 프롬프트와 대상·질문이 넘어가고 질문 종류가 메모장에 적히는지 확인
- `test_graph_generate.py` — 생성 노드: 통과 카드와 넷리스트만 넘기는지, 없는 근거 인용(999)·인용 없는 문장을 세는지, "문서로 확인 안 됨"은 인용 없는 문장으로 세지 않는지, 근거가 없으면 LLM을 부르지 않는지 가짜 LLM으로 확인
- `test_graph_grade.py` — 채점 노드: 같은 문서의 다른 품번 줄(1N5817 줄)은 빼고 패키지 줄·글 카드는 남기는지, 다른 개정판만 남으면 LLM을 부르지 않는지, LLM이 낸 없는 번호는 버리는지 가짜 LLM으로 확인
- `test_graph_refuse.py` — 거절 노드: 범위 밖이면 범위 안내만, 품번 문서가 없으면 그 품번과 단서 요청, 찾은 문서에 답이 없으면 찾아본 문서 이름(중복 없이)과 검색 횟수를 남기는지 확인
- `test_graph_rewrite.py` — 재작성 노드와 채점 뒤 갈림길: 1차 검색어가 아니라 원래 질문을 고치는지(가짜 LLM), 통과 있으면 생성, 검색 1번이면 재작성·2번이면 거절(리터럴 2와 비교), 검색 0장이면 재작성 없이 거절인지 확인
- `test_graph_search.py` — 검색 노드: 회로 기호·값·개정 코드를 뺀 품번 뽑기, 질문 품번이 대상 값보다 앞서는지(평가셋 n11), 품번이 없으면 전체 검색, 재작성한 검색어로 찾는지 가짜 검색기로 확인
- `test_graph_read_input.py` — 입력 읽기 노드: 입력 글 나누기, e01에서 J1 → S1 → D1 → F1 → RAW 경로가 보이는지, 큰 넷 자르기, 평가셋 v1 50문항 모두 대상 부품을 읽는지 확인
- `test_rag_chunk.py` — 표 카드 규칙(합친 칸 채우기, 머리 행 두 줄 잇기, 빈 표)과 문서 키, `data/manifest.jsonl`이 512,000바이트 아래인지
- `test_rag_ingest.py` — 벡터 캐시 다시 열기와 끊긴 쓰기 복구, 없는 본문만 임베딩. DB 재실행(행이 늘지 않고 API를 다시 안 부름, manifest에 없는 공통 값을 `DOC_DEFAULTS`로 채움) 시험은 `TEST_DATABASE_URL`을 줄 때만
- `test_rag_retrieve.py` — RRF 순서, BM25 토큰(한국어 조사), `gold_chunks`에서 정답 문서·쪽 읽기, 표지 카드 → 품번 색인과 품번 전체 일치 필터, BM25 0점 제외, 데모 모드에서 임베딩 API 안 부름, `method='bm25'`에서 임베딩 API 안 부름, 없는 `method`는 `ValueError`, 평가 대상 0건 오류, 결과마다 문서 표지 품번(`doc_parts`). 실제 DB 시험은 `TEST_DATABASE_URL`(로컬 compose DB)을 줄 때만
- `test_rag_collect.py` — xlsx 목록 합치기, manifest로 받기(파일 이름은 `source_url` 끝, sha256 대조, PDF 아님·해시 다름은 failed.csv), 다시 돌리면 건너뛰기
- `test_rag_parse.py` — 숫자 세기(µ 통일), 표 좌표 바꾸기, SIGALRM 지원 여부
- `test_rag_subset.py` — 분류별 사본·입력 보존·관련 gold 누락·기존 출력·불완전/중복 카드 오류, 카드 수 기준 벡터 payload 추정
- `test_rag_storage.py` — 형식 설정 검증, 실제 시험 DB의 halfvec 전환·재실행·이진 재적재·정확 검색, 같은 본문 제외·시간/표본 부족 표시. DB 시험은 전용 TEST_DATABASE_URL 필요
