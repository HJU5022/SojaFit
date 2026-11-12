# RAG 파이프라인: 데이터시트 수집부터 하이브리드 검색까지

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(정본: [SPEC.md](../../SPEC.md) 6절 데이터·코퍼스 경계, 청크 수는 [data/DATA.md](../../data/DATA.md))
- 관련 문서: [backend/rag/RAG.md](../../backend/rag/RAG.md), [data/DATA.md](../../data/DATA.md), [corpus-storage-budget.md](../experiments/corpus-storage-budget.md)

현재 구성: 청킹 `tsc-v4h-2026-11-08`(`backend/rag/pipeline/chunk.py` `CHUNKER_VERSION`), 임베딩 `voyage-4-large` 1024차원(차원 없는 `halfvec` 열), 재정렬 Voyage `rerank-3`(`backend/rag/retrieve.py`). 저장소의 `data/manifest.jsonl`(1,360줄)은 v1 청킹 당시 문서 목록이다.

## Why

- 페르소나: 판정 노드와 평가 실행기(검색을 부르는 쪽), 같은 코퍼스를 다시 만들어야 하는 조원과 평가자
- 상황: TSC 다이오드 데이터시트 1,360건(`data/manifest.jsonl`)의 수집·파싱·청킹·임베딩·검색 경로가 필요하다(측정은 [EVAL_REPORT.md](../../EVAL_REPORT.md) 1장).
- 문제:
  1. 서비스와 평가 실행기가 같은 검색 함수를 불러야 한다.
  2. 조원과 평가자가 같은 코퍼스를 저장소 명령으로 다시 만들 수 있어야 한다.
  3. 동결한 평가셋의 검색 기준선을 저장소 코드로 재야 한다.
- 측정 지표: 동결 평가셋 관련 문항의 문서 Recall@5, MRR, Page Hit@5

## Goal

- 해결 목표: `python -m backend.rag.pipeline.<모듈>`(모듈: `collect`, `parse`, `chunk`, `ingest`)로 수집 → 파싱 → 청킹 → 적재를 다시 하고, `retrieve()`로 하이브리드 검색을 부른다.
- 성공 기준:
  - 고정한 전체 입력으로 v4h 청킹을 두 번 실행했을 때 `summary.json`의 `chunker_version`, 카드 수, 종류별 수, 서로 다른 본문 수와 산출물 해시가 같다
  - 전체 입력으로 만든 카드와 Voyage 임베딩이 로컬 DB에 문서 1,360건과 함께 들어간다. 카드 수의 정본은 [data/DATA.md](../../data/DATA.md)
  - 평가셋 관련 문항으로 검색 지표가 오류 없이 나온다
- Out of Scope: 질문에서 품번 뽑기(에이전트가 `parts`로 준다), 증분 수집 자동화, 운영 Supabase 적용, 공개 문서(KiCad 등) 수집. 임베딩 후보 비교는 과거 실험 문서에서 다루며 현재 서비스 모델은 Voyage로 고정한다

## What

### Happy Path
1. `collect list`: TSC 분류별 Export xlsx를 PDF 하나당 한 줄인 목록 csv로 합친다.
2. `collect download`: 목록의 PDF를 원래 파일 이름으로 받는다.
3. `parse run`: Docling(OCR 끔, 표 구조 켬)으로 PDF마다 JSON을 저장하고, 표 숫자가 같은 쪽 pdfplumber 글자에 있는지 센다(두 번째 증인). `parse recall`은 반대 방향(표 영역 원문 숫자가 Docling 표에 있는지)을 센다.
4. `chunk`(`python -m backend.rag.pipeline.chunk`): Docling JSON과 원본 PDF를 v4h 카드로 자른다. PDF마다 품번 표지와 1쪽 제품 개요를 만들고, 표 밖 글은 소제목·쪽·1,200자 경계로 자른다. 표는 Docling과 pdfplumber 테두리선 결과를 대조해 합친 칸·머리·행을 복구하고 한 행 = 카드 하나로 만들며, 표 주석은 별도 카드와 해당 행에 연결한다. 숫자가 2개 이상 어긋난 표는 한쪽을 임의 채택하지 않고 `table_suspects.jsonl`에 기록한다. `chunks.jsonl`, `summary.json`, 문서 목록 `manifest.jsonl`을 쓰며 공통 값은 `chunk.py`의 `DOC_DEFAULTS`에 둔다.
5. `ingest`: 문서와 청크를 `source_documents`·`document_chunks`에, Voyage 1024차원 임베딩을 차원 없는 `halfvec` 열의 `chunk_embeddings`에 넣는다. 이미 만든 벡터는 본문 해시 캐시와 모델 행으로 다시 쓴다.
6. `retrieve(question, k=5, parts=None)`: dense 상위 50개와 BM25 상위 50개를 RRF로 합치고, 실제 모드의 hybrid 검색은 합친 후보를 Voyage `rerank-3`로 재정렬해 상위 k개를 돌려준다. `parts`를 주면 그 품번이 표지에 적힌 문서의 청크 안에서만 찾는다.
7. `evals/runners/run_retrieval.py`: 평가셋 관련 문항의 지표를 계산해 `evals/results/`에 남긴다.

### Edge Cases

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | 링크가 PDF 대신 오류 페이지를 준다 | `%PDF`로 시작하는지 보고, 아니면 `failed.csv`에 남긴다 |
| EC-02 | Docling 변환이 10분을 넘는다 | 그 PDF를 끊고 기록에 오류를 남긴다. 결과 파일이 없으니 다음 실행에서 다시 한다 |
| EC-03 | Docling이 칸 없는 빈 표를 낸다 | 그 표는 건너뛴다 |
| EC-04 | 같은 본문이 여러 문서에 나온다 | 청크는 문서마다 모두 저장하고, 임베딩은 본문 해시당 한 번만 계산한다 |
| EC-05 | 임베딩 호출이 실패한다 | 묶음마다 3번까지 다시 하고, 그래도 실패하면 멈춘다. 다시 돌리면 이어서 한다 |
| EC-06 | 질문의 품번에 한국어 조사가 붙는다("1N5819는") | BM25 토큰은 영문·숫자 연속만 쓴다 |
| EC-07 | 질문 단어가 어떤 청크와도 안 맞는다(BM25 점수 0) | 점수 0인 청크는 후보에서 빼고, 남는 게 없으면 BM25 후보는 빈 목록이다 |
| EC-08 | 키 없는 데모 모드(`DEMO_MODE=1`) | 임베딩 API를 부르지 않고 BM25만으로 찾는다 |
| EC-09 | 새 clone에 목록 xlsx가 없다 | `collect download data/manifest.jsonl <pdf 폴더>`로 manifest의 원본 주소에서 받고 sha256을 대조한다 |
| EC-10 | Windows에서 파싱한다(SIGALRM 없음) | PDF별 시간 제한 없이 돌고 경고를 낸다. 맥·리눅스·도커를 권장한다 |

## How

- 검색 함수: `retrieve(question: str, *, k: int = 5, parts: list[str] | None = None, method: str = 'hybrid') -> list[dict]` (`backend/rag/retrieve.py`). 서버 기동 때 `warmup()`을 한 번 불러 BM25 색인과 품번 → 문서 색인을 만든다.
  - `parts`: 에이전트가 특정 후보 품번(예: `["SS34"]`)을 확인할 때 준다. 사용자가 입력하지 않는다. 표지 청크(`이 데이터시트의 품번: ...`)에 그 품번이 적힌 문서의 청크만 dense(`WHERE chunk_id = ANY(...)`, 정확 검색)와 BM25(허용 밖 청크 제외) 후보로 쓰고 RRF는 같다. 품번은 대소문자만 무시하고 전체가 같아야 한다(SS34는 SS34L에 걸리지 않음). 코퍼스에 없는 품번뿐이면 `[]`를 돌려주고 전체 코퍼스로 넘어가지 않는다(호출 쪽이 "문서로 확인 안 됨"으로 판정). `parts`가 없으면 필터 없이 같다.
  - `method`: `'hybrid'`(기본, dense + BM25를 RRF로), `'dense'`(dense 목록만), `'bm25'`(BM25 목록만, 임베딩 API를 부르지 않음). 다른 값이면 `ValueError`. 방식별 평가 기준선을 재려고 둔다
  - 돌려주는 키: `chunk_id`, `document_key`, `file`(PDF 이름), `page`, `table`, `content`, `score`(RRF 점수), `dense_rank`, `bm25_rank`, `doc_parts`(그 문서 표지에 적힌 품번, 소문자)
  - RRF: 청크마다 `1 / (60 + 순위)`를 두 목록에서 더한다. 후보는 방식마다 50개
- 데이터: `db/002_rag_corpus.sql`, `db/008_multi_dim_embeddings.sql`, `db/009_chunk_embedding_bits.sql`
  - `source_documents`, `document_chunks`: 이 SQL이 생성하고 업무 테이블 초안이 참조한다. `IF NOT EXISTS`는 기존 정의의 일치를 검증하지 않는다.
  - `chunk_embeddings`: `002`가 만든 과거 `vector(1536)` 열을 `008`이 모델별 차원을 함께 담는 차원 없는 `halfvec`으로 전환한다. `retrieve()`는 Voyage 행을 1024차원 vector로 바꿔 정확 거리를 계산하며, 후보가 많으면 `009`의 1비트 코드를 1차 후보 축소에 쓴다
  - 기존 DB는 `008` 적용 여부와 `RAG_VECTOR_TYPE`이 실제 열 형식과 맞는지 별도로 확인한다. 저장 용량 작업의 과거 비교 절차는 [corpus-storage-budget.md](../experiments/corpus-storage-budget.md)를 따른다
- 모델과 도구: 임베딩 `voyage-4-large` 1024차원과 리랭킹 `rerank-3`(`backend/services/llm.py`). Docling 2.145.0과 pdfplumber는 uv 의존성 그룹 `ingest`로 두어 서버 이미지에 넣지 않는다.
- 제약: 임베딩 호출은 `llm.py`로만 한다. 재시도에는 상한을 둔다. 코퍼스 문장은 지시가 아니라 데이터다.
- 원본 위치: PDF·파싱 결과·청크·벡터는 저장소에 넣지 않는다. 예외로 키 없는 데모용 42문서 청크만 `data/demo/snapshot/`에 둔다(SPEC 6절). 실제 작업 경로와 전체 준비 상태는 실행자가 입력 수·해시로 확인한다.

## AC

| AC | Given-When-Then | 시험 |
|---|---|---|

## 구현 상태

| 항목 | 상태 | 근거 |
|---|---|---|
| 수집·파싱·청킹·적재 모듈 | 구현 | `backend/rag/pipeline/collect.py`·`parse.py`·`chunk.py`·`ingest.py` |
| 하이브리드 검색 `retrieve` | 구현(N_CAND 50, RRF_K 60) | `backend/rag/retrieve.py:24,28` |
| 요청 판본 자동 대조 | 미구현 | 아래 한계 |

## 한계

- v4h 전체 실행의 입력(Docling JSON·PDF)과 산출물(`chunks.jsonl`, `summary.json`, 임베딩)은 저장소 밖에 있다. 카드 수 51,967과 같은 전체 실행 수치는 이 저장소로 재현·확인하지 못한다. 새 clone의 재현은 별도 증거가 필요하다.
- AC-03·AC-04는 전체 입력이 없어 확인하지 못했다.
- 요청 판본 확인은 구현하지 않았다. 파일명에서 개정 코드를 추출해 manifest에 기록하지만, 질문이 지정한 품번·개정 코드·연도를 보유 문서의 판본과 자동 대조하는 절차가 없다. 연도와 개정 코드의 대응은 제조사의 명시적 근거가 필요하다. "고정 코퍼스에 요청 판본이 없음"과 "그 판본이 실제로 존재하지 않음"의 구분과 외부 조회 도입 여부는 미결이다.
