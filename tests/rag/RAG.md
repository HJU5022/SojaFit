# rag

## 역할
- 이 폴더: 데이터시트 수집·파싱·청킹·적재·검색(`backend/rag/`)의 회귀 테스트를 둡니다.
- 넣는 것: `test_rag_<모듈>.py`. 외부 호출은 가짜로 바꾸고, DB 시험은 `TEST_DATABASE_URL`이 있을 때만 돌립니다.
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 임베딩·채팅 호출 계약(`tests/services/`), 검색 성능 실험 결과(`scripts/results/hnsw/`).
- 담당: 검색·데이터

실행: `uv run pytest -q tests/rag`(저장소 루트).

## 파일
- `RAG.md` — 이 문서
- `test_rag_chunk.py` — 표 카드 규칙(합친 칸 채우기, 머리 행 잇기, 빈 표)과 문서 키, `data/manifest.jsonl`이 512,000바이트 아래인지
- `test_rag_collect.py` — xlsx 목록 합치기, manifest로 받기(sha256 대조, 실패는 failed.csv), 다시 돌리면 건너뛰기
- `test_rag_ingest.py` — 벡터 캐시 다시 열기와 끊긴 쓰기 복구, 없는 본문만 임베딩, DB 재실행(전용 DB 필요)
- `test_rag_parse.py` — 숫자 세기(µ 통일), 표 좌표 바꾸기, SIGALRM 지원 여부
- `test_rag_retrieve.py` — RRF 순서, BM25 토큰, 품번 색인·필터, `method` 분기와 임베딩 API 호출 여부, 평가 대상 0건 오류, 문서 표지 품번. 실제 DB 시험은 `TEST_DATABASE_URL` 필요
- `test_rag_storage.py` — 형식 설정 검증, halfvec 전환·재실행·이진 재적재·정확 검색, 시간/표본 부족 표시. DB 시험은 `TEST_DATABASE_URL` 필요
- `test_rag_subset.py` — 분류별 사본·입력 보존·gold 누락·기존 출력·불완전/중복 카드 오류, 벡터 payload 추정
