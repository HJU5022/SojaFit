# rag

## 역할
- 이 폴더: 데이터시트 수집, PDF 표 파싱, 단위 환산, 청킹, 인덱싱, 하이브리드 검색(BM25와 벡터), 리랭킹을 둡니다(G3).
- 넣는 것: 파싱·청킹·manifest 기록, 검색과 리랭킹, 단위 환산(`units.py`), 수집·표 파싱·스냅샷 만들기 코드. 수집·표 파싱·스냅샷 코드는 서버가 import하지 않고 `python -m backend.rag.<모듈>`로 돌립니다.
- 넣지 않는 것: 원본 문서(`data/corpus/`), 판정 규칙(`backend/judge/`), LLM·임베딩 호출 구현(`backend/services/llm.py`).
- 담당: 검색·데이터

## 주의
- 인덱스를 만들 때마다 `data/manifest.jsonl`에 문서와 청크 목록을 남깁니다(형식은 [data.md](../../data/data.md)).
- pdftotext가 μ를 m으로 바꿔 단위가 1000배 틀어지는 데이터시트가 있습니다. 표에서 뽑은 값은 단위 보정을 거칩니다.

## 파일
- `ingest.py` — 문서 파싱, 청킹, manifest 기록
- `retrieve.py` — 하이브리드 검색, 리랭킹, 메타데이터 필터
