# rag

## 역할
- 이 폴더: 데이터시트 수집·파싱·청킹·적재·검색(`backend/rag/`)의 회귀 테스트를 둡니다.
- 넣는 것: `test_rag_<모듈>.py`. 외부 호출은 가짜로 바꾸고, DB 시험은 `TEST_DATABASE_URL`이 있을 때만 돌립니다.
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 임베딩·채팅 호출 계약(`tests/services/`), 검색 성능 실험 결과(`scripts/results/hnsw/`).
- 담당: 검색·데이터

실행: `uv run pytest -q tests/rag`(저장소 루트).

## 파일
- `RAG.md` — 이 문서
- `test_card_find.py` — 카드 찾기(가짜 검색 · 카드 적재 · 카드 읽기 · 문서 분류, DB · LLM 없음): 검색 문장, 분류 · 개수로 문서 고르기, 카드 거르기, 같은 사양 행에서 `find_candidates`(가짜 연결)와 같은 거르기 · 순서, 양방향 품번 값 붙이기
- `test_card_read.py` — 카드 읽기(가짜 chat): 사양 행 모양 · SI 값(mA → A), 인용이 카드에 없음 · 숫자가 인용에 없음 · 단위 차원 다름 · 다른 문서 품번이면 사유와 함께 버림, chat 한 번 호출, 많은 카드는 나눠 읽고 합침
- `test_card_specs.py` — 카드에서 판정 값 읽기(가짜 의존, 실제 LLM · DB 없음): 미리 읽은 품번은 다시 읽지 않고, 글 카드의 행(패키지 등)을 붙임
- `test_rag_chunk.py` — 표 청크 규칙(합친 칸 채우기, 머리 행 잇기, 빈 표)과 문서 키, `data/manifest.jsonl`이 512,000바이트 아래인지
- `test_rag_collect.py` — xlsx 목록 합치기, manifest로 받기(sha256 대조, 실패는 failed.csv), 다시 돌리면 건너뛰기
- `test_rag_ingest.py` — 벡터 캐시 다시 열기와 끊긴 쓰기 복구, 없는 본문만 임베딩, DB 재실행(전용 DB 필요), `load_voyage`가 비트 코드 표를 채움(가짜 연결)
- `test_rag_parse.py` — 숫자 세기(µ 통일), 표 좌표 바꾸기, SIGALRM 지원 여부
- `test_rag_retrieve.py` — RRF 순서, BM25 토큰, 품번 색인·필터, `method` 분기와 임베딩 API 호출 여부, 표지 청크 제외, 리랭크 순서 뒤 상위 k개, 데모 모드의 리랭크 생략, 평가 대상 0건 오류, 문서 표지 품번, dense 비트 1단계가 허용 청크 > N_BIT일 때만 쓰이고 품번 필터 없을 때 아이디 목록을 보내지 않음(가짜 연결). 실제 DB 시험은 `TEST_DATABASE_URL` 필요
- `test_rag_specs.py` — 표 행 청크 공용 규칙(가짜 청크, 코퍼스 파일 없음): 패키지 이름 정규식(소문자 낱말 · Thin/Micro/Sub SMA는 SMA가 아님), `packages_of`(본문 Case 글 · Package 행의 VALUE 칸). 사양 표 변환 시험은 11-09에 변환 코드와 함께 지웠다(ADR 0016)
- `test_rag_spec_lookup.py` — `find_candidates` 찾기 순위(가짜 연결, DB 없음): 자르기 전에 모두 줄 세움, 패키지 → 분류 → 기준에 가까운 순, 가장 먼 조건의 비율. 사양 표 SQL · 적재 · DB 조회 시험은 11-09에 지웠다(ADR 0016)
- `test_rag_storage.py` — 형식 설정 검증, halfvec 전환·재실행·이진 재적재·정확 검색, 시간/표본 부족 표시. DB 시험은 `TEST_DATABASE_URL` 필요
- `test_rag_subset.py` — 분류별 사본·입력 보존·gold 누락·기존 출력·불완전/중복 청크 오류, 벡터 payload 추정
- `test_rag_units.py` — 단위 환산(mA·µA(µ/μ/u)·nA·ns·pF·kV(KV)·mW·°C)과 모르는 단위(MA·Ω·°C/W 등)는 None
- `test_voyage_rollout.py` — `scripts/db/voyage_rollout.py`의 STOP 규칙(열 형식 · 예상 크기 420 MB)과 `db/008` SQL의 halfvec(n) 무USING 분기, STOP이면 migrate가 DB를 건드리지 않는 것(가짜 연결)
