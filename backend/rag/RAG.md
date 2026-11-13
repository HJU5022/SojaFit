# rag

## 역할
- 이 폴더: 서버가 import하는 하이브리드 검색, 카드(표 행 청크) 읽기·찾기, 단위 환산, 벡터 열 형식과 DB 용량 점검, 오프라인 데이터시트 도구 하위 폴더(`pipeline/`).
- 넣는 것: BM25 + 벡터 RRF 하이브리드 검색(`retrieve.py`), 사양 코드 목록과 찾기 순서 규칙(`spec_lookup.py`), 카드 읽기·찾기·판정 값(`card_*.py`), 표 값 단위 환산(`units.py`), 벡터 열 형식과 용량 점검(`storage.py`), 공식 출처·외형 페이지 조회(`source_metadata.py`), 수집·파싱·청킹·적재 도구와 표 행 공용 규칙(`pipeline/`).
- 넣지 않는 것: 원본 문서(`data/corpus/`), 판정 규칙과 숫자·단위 비교(`backend/judge/`), LLM·임베딩 호출 구현(`backend/services/llm.py`), DB 표 정의(`db/`), 질문에서 품번 뽑기(`backend/graph/nodes.py`의 `find_parts`).
- 담당: 검색·데이터

서비스의 후보 찾기·판정 값은 카드 도구(`card_find.py`, `card_specs.py`)가 `DATABASE_URL`로 DB를 직접 읽고 그때그때 카드를 읽는다. 사양 표를 따로 저장하지 않는다(ADR 0016). 인덱스를 만들 때마다 `data/manifest.jsonl`에 문서 목록을 남기고 형식은 [DATA.md](../../data/DATA.md)가 정한다. 숫자 대조에서 µ와 μ는 같은 글자로 맞춘다(`pipeline/parse.py`). 작업서는 [rag-pipeline.md](../../docs/specs/rag-pipeline.md), 코퍼스 저장 용량 검토는 [corpus-storage-budget.md](../../docs/experiments/corpus-storage-budget.md)다.

## 파일
| 파일 | 하는 일 |
|---|---|
| `RAG.md` | 이 문서 |
| `__init__.py` | 패키지 표시 |
| `retrieve.py` | `retrieve(question, *, k=5, parts=None, method='hybrid')`: dense + BM25를 RRF로 합치고 `rerank-3`로 다시 세움. 표지 청크 제외, `parts` 필터, `corpus_known`. `DEMO_MODE=1`이면 BM25만 |
| `spec_lookup.py` | 사양 코드 목록 `CODES`, 조건 자리 기본값 `DEFAULT_SLOT`, 삽입형 패키지 이름 `THT_PACKAGES`. DB를 읽지 않음 |
| `card_read.py` | 카드 → 값·원문 인용. `pipeline/specs.py` 규칙(`read_card`)으로 먼저 읽고, 원하는 코드 값을 못 받았거나 검토 표시가 난 카드만 LLM(`card_read` 프롬프트)으로 읽음. 두 길 모두 같은 코드 확인(카드 번호·인용·숫자·단위 차원·품번)을 거침 |
| `card_find.py` | 후보 찾기 `make_find`·`default_find`: 분류 문서의 개요 줄로 읽을 문서를 고르고(`code_pick`, 못 줄 세울 때만 LLM `card_pick`) 문서별 카드 읽기를 동시에 불러 조건에 맞는 품번을 거른 뒤 정렬. 계약은 SPEC.md 8.7 |
| `card_specs.py` | 판정 값 `make_specs`·`default_specs`: 품번의 사양 행(최소/대표/최대 SI 값, 단위, 원문, 시험 조건, 인용)을 카드에서 읽음. 사실 확인용 `doc_rows`(LLM 없음). 품번 → 문서 색인은 첫 찾기 때 읽음 |
| `units.py` | `to_si(값, 단위)`: 표 단위를 SI 기본 단위로 바꿈. 모르는 단위·비율 단위는 `None` |
| `storage.py` | 벡터 열 형식 `RAG_VECTOR_TYPE=vector\|halfvec` 계약(`vector_type`은 서버와 적재 도구가 import), 읽기 전용 DB/표 용량 점검과 vector → halfvec 비교(`python -m backend.rag.storage`) |
| `source_metadata.py` | `source_metadata(document)`: 경로의 basename을 manifest와 `data/package-outline-pages.json`에서 정확히 찾아 공식 HTTPS URL·외형 페이지를 돌려줌. 브라우저 DTO에만 붙이고 DB 저장 형식에는 넣지 않음 |
| `pipeline/` | 오프라인 데이터시트 도구. 서버는 `pipeline/specs.py`의 규칙만 import하고 나머지는 import하지 않음. `python -m backend.rag.pipeline.<모듈>`로 실행 |

### pipeline/ 모듈
| 모듈 | 하는 일 |
|---|---|
| `pipeline/__init__.py` | 패키지 표시 |
| `pipeline/collect.py` | TSC 분류별 Export xlsx를 PDF 목록 csv로 합치기(`list`), PDF 받기(`download`, `data/manifest.jsonl`의 sha256 대조) |
| `pipeline/parse.py` | Docling 파싱과 두 방향 숫자 대조(`run`, `recall`). uv 그룹 `ingest` 필요 |
| `pipeline/chunk.py` | Docling 결과를 청크(품번 표지, 표 밖 글, 표 한 행)로 자르고 `data/manifest.jsonl`을 씀. uv 그룹 `ingest` 필요 |
| `pipeline/ingest.py` | manifest와 청크를 DB 코퍼스 표에 넣고 임베딩을 붙임(`--voyage`, `--voyage-fill`, `--cache-only`, `--chunks-only`). `DATABASE_URL` 필요 |
| `pipeline/specs.py` | 표 행 청크 공용 규칙: 코드별 SI 단위(`SI`), 기호·낱말 → 코드(`SYMS`·`KEYWORDS`), 패키지 이름(`PKG`·`packages_of`), 분류 이름(`family`), 양방향·AEC-Q101 문장. `read_card`가 카드 한 장을 같은 해석기로 읽음 |
| `pipeline/subset.py` | 손으로만 돌리는 도구: 분류 csv로 일부 분류만 고른 manifest·청크 사본을 새 폴더에 만듦. 서비스·적재에서 부르지 않고 시험(`tests/rag/test_rag_subset.py`)만 부름 |
| `pipeline/demo_snapshot.py` | 전체 manifest·청크에서 데모용 문서를 골라 `data/demo/snapshot/`에 씀. 키 없는 compose의 `corpus-load`가 `ingest.py --chunks-only`로 적재([SNAPSHOT.md](../../data/demo/snapshot/SNAPSHOT.md)) |
| `pipeline/package_outlines.py` | manifest URL basename과 Docling `origin.filename`을 대조해 외형 제목과 그림이 함께 있는 가장 이른 페이지를 `data/package-outline-pages.json`에 기록. 누락·중복·잘못된 URL은 실패 |

실행 순서:

```bash
python -m backend.rag.pipeline.collect list <xlsx 폴더> <목록 csv>
python -m backend.rag.pipeline.collect download data/manifest.jsonl <pdf 폴더>   # 새 clone (목록 csv도 됨)
uv run --group ingest python -m backend.rag.pipeline.parse run <pdf 폴더> <출력 폴더>
uv run --group ingest python -m backend.rag.pipeline.chunk <docling json 폴더> <목록 csv> <pdf 폴더> <출력 폴더> data/manifest.jsonl
python -m backend.rag.pipeline.ingest data/manifest.jsonl <출력 폴더>/chunks.jsonl <벡터 폴더>
```
