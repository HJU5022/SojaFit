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
- `collect.py` — TSC 분류별 Export xlsx를 PDF 목록 csv로 합치기(`list`), PDF 받기(`download`). 새 clone에서는 `data/manifest.jsonl`로 받는다(sha256 대조)
- `parse.py` — Docling 파싱과 두 방향 숫자 대조(`run`, `recall`). uv 그룹 `ingest`가 필요
- `chunk.py` — Docling 결과를 카드(품번 표지, 표 밖 글, 표 한 행)로 자르고 `data/manifest.jsonl`을 씀. uv 그룹 `ingest`가 필요
- `ingest.py` — manifest와 카드를 DB 코퍼스 표에 넣고 임베딩을 붙임(벡터는 본문 해시 캐시를 다시 씀). `DATABASE_URL` 필요
- `retrieve.py` — `retrieve(question, k=5, parts=None)`: dense 정확 검색 상위 50 + BM25 상위 50을 RRF로 합친 하이브리드 검색. `parts`를 주면 그 품번이 표지에 적힌 문서의 카드 안에서만 찾고, 코퍼스에 없는 품번뿐이면 `[]`. 리랭킹은 아직 없음. `DATABASE_URL`과 임베딩 키 필요
- `subset.py` — 적용 보류 중인 독립 수동 CLI. 제조사 분류 csv로 5개 다이오드 분류의 별도 manifest·카드 사본을 선택. 서비스·초기화·적재에서 호출하지 않음. 원본 보존, 관련 gold 누락·불완전 카드 오류. DB 용량은 추정과 실측을 구분
- `storage.py` — 읽기 전용 DB/표 용량 점검, 기존 vector에서 API 없이 표본 top-5 정밀도 비교. `RAG_VECTOR_TYPE=vector|halfvec` 계약 검증

작업서는 [rag-pipeline.md](../../docs/specs/rag-pipeline.md)입니다. 원본 PDF·파싱 결과·카드는 저장소 밖 로컬 `SojaFit/corpus/tsc/`에 둡니다.

원본 코퍼스 유지·축소 보류·복제 DB 전환 순서는 [corpus-storage-budget.md](../../docs/specs/corpus-storage-budget.md)를 봅니다. 원본 float32 캐시는 보존하며 `halfvec`은 적재할 때만 변환합니다. halfvec 검색은 float32로 읽어 거리를 계산하고 수동 전환 뒤 HNSW는 만들지 않습니다. 공식 검색 품질 확인 전 기본값은 vector입니다.

기본 경로는 전체 코퍼스를 유지하며 축소 사본은 생성·적재하지 않습니다. 기존 DB의 ingest는 삭제를 하지 않아 축소 도구가 아닙니다. 원본 캐시의 복사본과 `ingest --cache-only`를 사용하면 필요한 벡터가 없을 때 API를 호출하지 않고 실패합니다.

```bash
python -m backend.rag.collect list <xlsx 폴더> <목록 csv>
python -m backend.rag.collect download data/manifest.jsonl <pdf 폴더>   # 새 clone (목록 csv도 됨)
uv run --group ingest python -m backend.rag.parse run <pdf 폴더> <출력 폴더>
uv run --group ingest python -m backend.rag.chunk <docling json 폴더> <목록 csv> <pdf 폴더> <출력 폴더> data/manifest.jsonl
python -m backend.rag.ingest data/manifest.jsonl <출력 폴더>/chunks.jsonl <벡터 폴더>
```
