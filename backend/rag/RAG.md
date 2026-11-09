# rag

## 역할
- 이 폴더: 서버가 import하는 하이브리드 검색과 벡터 열 형식, 오프라인 데이터시트 도구 하위 폴더(`pipeline/`)를 둡니다(G3).
- 넣는 것: BM25 + 벡터 RRF 하이브리드 검색(`retrieve.py`), 사양 코드 목록 · 찾기 순서 규칙(`spec_lookup.py`), 카드 읽기 · 찾기 · 판정 값(`card_*.py`), 서버와 도구가 함께 쓰는 벡터 열 형식·DB 용량 점검(`storage.py`), 표 값의 단위 환산(`units.py`), 수집·파싱·청킹·적재 도구와 표 행 공용 규칙 폴더(`pipeline/`).
- 넣지 않는 것: 원본 문서(`data/corpus/`), 판정 규칙과 숫자·단위 비교(`backend/judge/`), LLM·임베딩 호출 구현(`backend/services/llm.py`), DB 표 정의(`db/`), 질문에서 품번 뽑기(`backend/graph/nodes.py`의 `find_parts`).
- 담당: 검색·데이터

## 구현 상태
- 2026-11-09 사양 표(`part_specifications`)를 버렸다(ADR 0016). 표 만들기 · 적재 코드(`pipeline/specs.py` build · sample · load)와 `db/011`을 지웠고, 서비스의 후보 찾기 · 판정 값은 카드 도구(`card_find.py` · `card_specs.py`)가 `DATABASE_URL`로 DB를 직접 읽는다. `spec_lookup.py`의 SQL 조회 2개와 MCP 사양 도구 2종은 `evals/runners/run_graph.py` 기본값이 아직 불러 남겼다.
- 있음: 수집, 파싱, 청킹, 적재, 하이브리드 검색(BM25 + dense, RRF), 품번 필터(`parts`), vector/halfvec 용량 비교, 단위 환산(`units.py`, SPEC 3절: judge가 읽기만 함), 카드 읽기 · 찾기 · 판정 값(`card_read.py` · `card_find.py` · `card_specs.py`).
- 아직 없음: GraphRAG·증분 수집 자동화는 SPEC에 없어 계획에 적지 않습니다.

## 주의
- 인덱스를 만들 때마다 `data/manifest.jsonl`에 문서 목록을 남깁니다(형식은 [data/DATA.md](../../data/DATA.md)).
- 숫자 대조에서 µ와 μ는 같은 글자로 맞춥니다(`pipeline/parse.py`).

## 파일
- `RAG.md` — 이 문서
- `__init__.py` — 패키지 표시
- `retrieve.py` — `retrieve(question, k=5, parts=None, method='hybrid')`: dense(`voyage-4-large` 1024차원) 상위 50(허용 청크가 3,200장보다 많으면 `chunk_embedding_bits`의 1비트 Hamming 거리로 3,200장을 먼저 거르고 그 안에서 정확 코사인, `db/009` 필요, 사전 등록 #27) + BM25 상위 50을 RRF로 합치고 후보 전부를 `rerank-3`로 다시 세워 상위 k개을 돌려주는 하이브리드 검색. 표지 청크(`page_number` 없음)는 언제나 뺌. `method='dense'`·`'bm25'`면 그 목록 하나만 쓰고 리랭크하지 않음(`bm25`는 임베딩 API를 부르지 않음). `parts`를 주면 그 품번이 표지에 적힌 문서의 청크 안에서만 찾고, 코퍼스에 없는 품번뿐이면 `[]`. 청크마다 그 문서 표지의 품번 목록(`doc_parts`)을 같이 돌려줌. `DATABASE_URL` 필요. `VOYAGE_API_KEY` 필요(`DEMO_MODE=0`). 기본값 `DEMO_MODE=1`에서는 임베딩·리랭크 API를 부르지 않고 BM25만 씀
- `spec_lookup.py` — 사양 코드 목록(`CODES`, 판정 에이전트 import)과 찾기 순서 규칙(`DEFAULT_SLOT` · `_norm_package` · `_ratio`, 카드 찾기 import). SQL 조회 2개(`part_specs` · `find_candidates`)는 사양 표를 지운 뒤에도 `run_graph.py` 기본값이 MCP로 불러 남겼다(`jeongun` 브랜치 병합 때 지움). 연결은 부르는 쪽이 넘긴다. `part_specs(conn, part, codes=None)`: 품번(대소문자 무시)의 모든 행을 값(SI)·단위·시험 조건·인용(문서 파일 이름·쪽·표·행·청크 순번)과 함께. `find_candidates(conn, conditions, category=None, package=None, limit=50, original_packages=None, original_category=None)`: 조건(`code`, `slot` min|typ|max(기본 max, CJ는 typ), `gte`·`lte`)마다 그 품번의 행 하나 이상이 채우면 통과, 모두 통과한 품번을 전부 줄 세운 뒤 `limit`개(원래 부품과 같은 패키지 → 같은 분류 → 기준에 가까운 것(조건별 값/기준 · 기준/값 중 가장 큰 비율) → 품번 순). `package`는 패키지 이름이 같은 품번만(대소문자 · 하이픈 무시, SMA는 SMAF에 걸리지 않음). 행 거르기만 하고 판정은 `backend/judge/`
- `card_read.py` — 카드(표 행 청크) → 값 · 원문 인용(LLM `card_read`) + 코드 확인(카드 번호 · 인용 · 숫자 · 단위 차원 · 품번). 사양 표 대신 그때그때 읽는다. 카드는 4장씩 나눠 동시에 읽고 합친다
- `card_find.py` — 서비스 기본 후보 찾기(ADR 0016): `source_documents.category`로 모은 분류 문서의 개요 줄을 보고 문서를 고르고(LLM `card_pick`) 문서별 `card_read`를 동시에 불러 `spec_lookup.find_candidates`와 같은 인자 · 같은 반환 모양 · 같은 규칙으로 거르고 줄 세움. 양방향 · H 품번 값 붙이기. `DATABASE_URL`로 DB를 직접 읽음(MCP 서버를 거치지 않음)
- `card_specs.py` — 서비스 기본 판정 값(ADR 0016), 카드에서 읽음: `specs(part, codes)`가 `spec_lookup.part_specs`(MCP `get_part_specs`)와 같은 모양으로 돌려줌(PACKAGE · AEC_Q101 행 포함), 사실 확인용 `doc_rows`(LLM 없음). `DATABASE_URL`로 DB를 직접 읽음
- `units.py` — `to_si(값, 단위)`: 표 단위(mA·µA·nA·ns·pF·kV·mW·°C 등)를 SI 기본 단위(V, A, W, s, F, degC) 값으로. 모르는 단위·비율 단위(°C/W)는 None
- `storage.py` — 벡터 열 형식 `RAG_VECTOR_TYPE=vector|halfvec` 계약(서버와 적재 도구가 함께 씀), 읽기 전용 DB/표 용량 점검(`inspect`), 기존 vector에서 API 없이 표본 top-5 정밀도 비교(`compare`)
- `pipeline/` — 오프라인 데이터시트 도구(서버가 import하지 않음, `specs.py` 공용 규칙만 카드 도구가 import). `python -m backend.rag.pipeline.<모듈>`로 돌립니다. 아래 여섯 모듈과 `__init__.py`(패키지 표시)가 있습니다
  - `pipeline/collect.py` — TSC 분류별 Export xlsx를 PDF 목록 csv로 합치기(`list`), PDF 받기(`download`). 새 clone에서는 `data/manifest.jsonl`로 받는다(sha256 대조)
  - `pipeline/parse.py` — Docling 파싱과 두 방향 숫자 대조(`run`, `recall`). uv 그룹 `ingest`가 필요
  - `pipeline/chunk.py` — Docling 결과를 청크(품번 표지, 표 밖 글, 표 한 행)로 자르고 `data/manifest.jsonl`을 씀. uv 그룹 `ingest`가 필요
  - `pipeline/ingest.py` — manifest와 청크를 DB 코퍼스 표에 넣고 임베딩을 붙임(벡터는 본문 해시 캐시를 다시 씀). `--voyage <벡터 폴더>`는 미리 만든 `v4large.f32`·`v4large.sha.txt`를 API 없이 붙임. `DATABASE_URL` 필요
  - `pipeline/specs.py` — 표 행 청크 공용 규칙만 둠: 코드 17종의 SI 단위(`SI`), 기호 · 설명 낱말 → 코드(`SYMS` · `KEYWORDS`), 패키지 이름(`PKG` · `packages_of`), 분류 이름(`family`, `ingest.py`가 `source_documents.category`에 넣음), 양방향 · AEC-Q101 문장(`BOTH_DIRECTIONS` · `AEC_H` · `AEC_ALL`). 사양 표 만들기 · 적재(`build` · `sample` · `load`)는 11-09에 지웠다(ADR 0016)
  - `pipeline/subset.py` — (보류) 손으로만 돌리는 도구. 제조사 분류 csv로 5개 다이오드 분류만 고른 manifest·청크 사본을 새 폴더에 만듦. 원본은 고치지 않고, 서비스·초기화·적재에서 부르지 않음

작업서는 [rag-pipeline.md](../../docs/specs/rag-pipeline.md)입니다. 원본 PDF·파싱 결과·청크는 저장소 밖 로컬 `SojaFit/corpus/tsc/`에 둡니다.

원본 코퍼스 유지·축소 보류·복제 DB 전환 순서는 [corpus-storage-budget.md](../../docs/experiments/corpus-storage-budget.md)를 봅니다. 원본 float32 캐시는 보존하며 `halfvec`은 적재할 때만 변환합니다. 공식 검색 품질 확인 전 기본값은 vector입니다. `ingest`는 행을 지우지 않으므로 이미 적재한 DB를 줄이는 데 쓸 수 없습니다. 원본 캐시의 복사본과 `ingest --cache-only`를 쓰면 캐시에 없는 벡터가 있을 때 API를 부르지 않고 멈춥니다.

## 실행 순서

```bash
python -m backend.rag.pipeline.collect list <xlsx 폴더> <목록 csv>
python -m backend.rag.pipeline.collect download data/manifest.jsonl <pdf 폴더>   # 새 clone (목록 csv도 됨)
uv run --group ingest python -m backend.rag.pipeline.parse run <pdf 폴더> <출력 폴더>
uv run --group ingest python -m backend.rag.pipeline.chunk <docling json 폴더> <목록 csv> <pdf 폴더> <출력 폴더> data/manifest.jsonl
python -m backend.rag.pipeline.ingest data/manifest.jsonl <출력 폴더>/chunks.jsonl <벡터 폴더>
```
