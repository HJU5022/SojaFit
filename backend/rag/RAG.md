# rag

## 역할
- 이 폴더: 데이터시트 수집, PDF 표 파싱, 단위 환산, 청킹, 인덱싱, 하이브리드 검색(BM25와 벡터), 리랭킹을 둡니다(G3).
- 넣는 것: 파싱·청킹·manifest 기록, 검색과 리랭킹, 단위 환산(`units.py`), 수집·표 파싱·스냅샷 만들기 코드. 수집·표 파싱·스냅샷 코드는 서버가 import하지 않고 `python -m backend.rag.<모듈>`로 돌립니다. 가산의 그래프 검색(GraphRAG)과 증분 수집 자동화도 이 폴더에 둡니다.
- 넣지 않는 것: 원본 문서(`data/corpus/`), 판정 규칙(`backend/judge/`), LLM·임베딩 호출 구현(`backend/services/llm.py`).
- 담당: 검색·데이터

## 주의
- 인덱스를 만들 때마다 `data/manifest.jsonl`에 문서와 청크 목록을 남깁니다(형식은 [DATA.md](../../data/DATA.md)).
- pdftotext가 μ를 m으로 바꿔 단위가 1000배 틀어지는 데이터시트가 있습니다. 표에서 뽑은 값은 단위 보정을 거칩니다.

## 파일
- `collect.py` — TSC 분류별 Export xlsx를 PDF 목록 csv로 합치기(`list`), PDF 받기(`download`)
- `parse.py` — Docling 파싱과 두 방향 숫자 대조(`run`, `recall`). uv 그룹 `ingest`가 필요
- `chunk.py` — Docling 결과를 카드(품번 표지, 표 밖 글, 표 한 행)로 자르고 `data/manifest.jsonl`을 씀. uv 그룹 `ingest`가 필요
- `ingest.py` — manifest와 카드를 DB 코퍼스 표에 넣고 임베딩을 붙임(벡터는 본문 해시 캐시를 다시 씀). `DATABASE_URL` 필요
- `retrieve.py` — 하이브리드 검색, 리랭킹, 메타데이터 필터 (미구현 뼈대)

작업서는 [rag-pipeline.md](../../docs/specs/rag-pipeline.md)입니다. 원본 PDF·파싱 결과·카드는 저장소 밖 로컬 `SojaFit/corpus/tsc/`에 둡니다.

```bash
python -m backend.rag.collect list <xlsx 폴더> <목록 csv>
python -m backend.rag.collect download <목록 csv> <pdf 폴더>
uv run --group ingest python -m backend.rag.parse run <pdf 폴더> <출력 폴더>
uv run --group ingest python -m backend.rag.chunk <docling json 폴더> <목록 csv> <pdf 폴더> <출력 폴더> data/manifest.jsonl
python -m backend.rag.ingest data/manifest.jsonl <출력 폴더>/chunks.jsonl <벡터 폴더>
```
