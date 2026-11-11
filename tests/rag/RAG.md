# rag

## 역할
- 이 폴더: 데이터시트 수집·파싱·청킹·적재·검색(`backend/rag/`)의 회귀 테스트를 둡니다.
- 넣는 것: `test_rag_<모듈>.py`. 외부 호출은 가짜로 바꾸고, DB 시험은 `TEST_DATABASE_URL`이 있을 때만 돌립니다.
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 임베딩·채팅 호출 계약(`tests/services/`), 검색 성능 실험 결과(`scripts/results/hnsw/`).
- 담당: 검색·데이터

실행: `uv run pytest -q tests/rag`(저장소 루트).

## 파일
- `RAG.md` — 이 문서
- `test_package_outlines.py` — 외형 제목과 같은 페이지의 그림 교집합, 정확한 파일명 일치, 누락·중복·잘못된 URL 거부, 결정적 CLI 출력, 체크인한 1,360문서 색인 완전성과 공식 출처의 런타임 정확 조회. 실제 Docling 코퍼스나 외부 API 없이 fixture와 체크인한 색인을 사용한다
- `test_card_find.py` — 카드 찾기(가짜 검색 · 카드 적재 · 카드 읽기 · 문서 분류, DB · LLM 없음): 검색 문장, 분류 · 개수로 문서 고르기, 개요 줄(제목) 값 읽기와 코드 고르기(버리기 · 순서 · LLM으로 넘기는 경우), 카드 거르기, 이상 · 이하 · 자리(slot) 거르기와 찾기 순위(패키지 → 분류 → 기준에 가까운 순, 가장 먼 조건의 비율), 양방향 품번 값 붙이기
- `test_card_read.py` — 카드 읽기(가짜 chat): 사양 행 모양 · SI 값(mA → A), 인용이 카드에 없음 · 숫자가 인용에 없음 · 단위 차원 다름 · 다른 문서 품번이면 사유와 함께 버림, chat 한 번 호출, 많은 카드는 나눠 읽고 합침. 코드 먼저: 실제 카드 글(로컬 DB)로 코드가 읽는 모양은 LLM 없이 LLM 길과 같은 행 · 맞는 칸 인용, 읽을 값 없는 행은 어디에도 안 보냄, 코드가 못 읽는 모양(여러 값 칸 · 공칭 · 가운데 Min · (C) 품번 · 일부 품번 전용 · 모르는 단위)은 그 카드만 LLM, LLM 행도 확인 · 카드 순서
- `test_card_specs.py` — 카드에서 판정 값 읽기(가짜 의존, 실제 LLM · DB 없음): 미리 읽은 품번은 다시 읽지 않고, 글 카드의 행(패키지 등)을 붙임, 품번 색인은 첫 찾기 때 한 번만 DB를 읽음
- `test_rag_chunk.py` — 표 청크 규칙(합친 칸 채우기, 머리 행 잇기, 빈 표)과 문서 키, `data/manifest.jsonl`이 512,000바이트 아래인지
- `test_rag_collect.py` — xlsx 목록 합치기, manifest로 받기(sha256 대조, 실패는 failed.csv), 다시 돌리면 건너뛰기
- `test_rag_ingest.py` — 벡터 캐시 다시 열기와 끊긴 쓰기 복구, 없는 본문만 임베딩, DB 재실행(전용 DB 필요), `load_voyage`가 비트 코드 표를 채움(가짜 연결)
- `test_rag_parse.py` — 숫자 세기(µ 통일), 표 좌표 바꾸기, SIGALRM 지원 여부
- `test_rag_retrieve.py` — RRF 순서, BM25 토큰, 품번 색인·필터, `method` 분기와 임베딩 API 호출 여부, 표지 청크 제외, 리랭크 순서 뒤 상위 k개, 데모 모드의 리랭크 생략, 평가 대상 0건 오류, 문서 표지 품번, dense 비트 1단계가 허용 청크 > N_BIT일 때만 쓰이고 품번 필터 없을 때 아이디 목록을 보내지 않음(가짜 연결). 실제 DB 시험은 `TEST_DATABASE_URL` 필요
- `test_rag_specs.py` — 표 행 청크 공용 규칙(가짜 청크, 코퍼스 파일 없음): 패키지 이름 정규식(소문자 낱말 · Thin/Micro/Sub SMA는 SMA가 아님), `packages_of`(본문 Case 글 · Package 행의 VALUE 칸). 사양 표 변환 시험은 11-09에 변환 코드와 함께 지웠다(ADR 0016)
- `test_rag_storage.py` — 형식 설정 검증, halfvec 전환·재실행·이진 재적재·정확 검색, 시간/표본 부족 표시. DB 시험은 `TEST_DATABASE_URL` 필요
- `test_rag_subset.py` — 분류별 사본·입력 보존·gold 누락·기존 출력·불완전/중복 청크 오류, 벡터 payload 추정
- `test_demo_snapshot.py` — 데모 코퍼스 스냅샷(`data/demo/snapshot/`): 두 파일 sha256 · 문서 · 청크 수가 SNAPSHOT.md와 같음, manifest 문서마다 청크 0..n-1, 고르기 규칙 1~4와 같은 분류 상한(가짜 원본), 원본에서 다시 뽑은 바이트가 같음(`DEMO_SNAPSHOT_SOURCE`가 있을 때만)
- `test_rag_units.py` — 단위 환산(mA·µA(µ/μ/u)·nA·ns·pF·kV(KV)·mW·°C)과 모르는 단위(MA·Ω·°C/W 등)는 None
- `test_voyage_rollout.py` — `scripts/db/voyage_rollout.py`의 STOP 규칙(열 형식 · 예상 크기 420 MB)과 `db/008` SQL의 halfvec(n) 무USING 분기, STOP이면 migrate가 DB를 건드리지 않는 것(가짜 연결)
