# RAG 파이프라인 — 데이터시트 수집부터 하이브리드 검색까지

## Why

- **페르소나**: 판정 노드와 평가 실행기(검색을 부르는 쪽), 같은 코퍼스를 다시 만들어야 하는 조원과 평가자
- **상황**: 11-01에 TSC 다이오드 데이터시트 1,360건의 수집·파싱·청킹·임베딩·검색을 저장소 밖 실험 스크립트로 했다(`EVAL_REPORT.md` 1장).
- **문제**:
  1. 서비스와 평가 실행기가 이 검색을 부를 수 없다.
  2. 조원과 평가자가 같은 코퍼스를 저장소 명령으로 다시 만들 수 없다.
  3. 동결한 평가셋의 검색 베이스라인을 저장소 코드로 재야 한다.
- **측정 지표**: 동결 평가셋 관련 문항의 문서 Recall@5, MRR, 쪽 적중@5

## Goal

- **해결 목표**: `python -m backend.rag.<모듈>`로 수집 → 파싱 → 청킹 → 적재를 다시 하고, `retrieve()`로 하이브리드 검색을 부른다.
- **성공 기준**:
  - 청킹 결과가 11-01 실험과 같다: 카드 52,244장, 서로 다른 본문 45,898개
  - 로컬 DB에 문서 1,360건, 청크 52,244개, 임베딩 52,244개(1536차원)가 들어간다
  - 평가셋 관련 문항으로 검색 지표가 오류 없이 나온다. 베이스라인 점수는 v1 동결 뒤 잰다
- **Out of Scope**: 리랭킹과 품번 밖 메타데이터 필터(D3, 사전 등록 뒤), 질문에서 품번 뽑기(에이전트가 `parts`로 준다), 임베딩 모델 비교(`evals/PREREGISTER.md` #1·#2), 증분 수집 자동화, Supabase 적용, 공개 문서(KiCad 등) 수집

## What

**Happy Path**
1. `collect list`: TSC 분류별 Export xlsx 13개를 PDF 하나당 한 줄인 목록 csv로 합친다(PDF 1,360개).
2. `collect download`: 목록의 PDF를 원래 파일 이름으로 받는다.
3. `parse run`: Docling(OCR 끔, 표 구조 켬)으로 PDF마다 JSON을 저장하고, 표 숫자가 같은 쪽 pdfplumber 글자에 있는지 센다(두 번째 증인). `parse recall`은 반대 방향(표 영역 원문 숫자가 Docling 표에 있는지)을 센다.
4. `chunk`: Docling JSON을 카드로 자른다. PDF마다 품번 표지 1장, 표 밖 글은 HybridChunker, 표는 한 행 = 카드 한 장(합친 칸 채움, `[파일 · 쪽 · 표 제목]` 이름표). 문서 목록 `data/manifest.jsonl`도 쓴다.
5. `ingest`: 문서와 카드를 `source_documents`·`document_chunks`에, 임베딩을 `chunk_embeddings`에 넣는다. 이미 만든 벡터는 본문 해시로 다시 쓴다.
6. `retrieve(question, k=5, parts=None)`: dense 상위 50개와 BM25 상위 50개를 RRF로 합쳐 상위 k개를 돌려준다. `parts`를 주면 그 품번이 표지에 적힌 문서의 카드 안에서만 찾는다.
7. `evals/run_retrieval.py`: 평가셋 관련 문항의 지표를 계산해 `evals/results/`에 남긴다.

**Edge Cases**

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | 링크가 PDF 대신 오류 페이지를 준다 | `%PDF`로 시작하는지 보고, 아니면 `failed.csv`에 남긴다 |
| EC-02 | Docling 변환이 10분을 넘는다 | 그 PDF를 끊고 기록에 오류를 남긴다. 결과 파일이 없으니 다음 실행에서 다시 한다 |
| EC-03 | Docling이 칸 없는 빈 표를 낸다 | 그 표는 건너뛴다 |
| EC-04 | 같은 본문이 여러 문서에 나온다 | 청크는 문서마다 모두 저장하고, 임베딩은 본문 해시당 한 번만 계산한다 |
| EC-05 | 임베딩 호출이 실패한다 | 묶음마다 3번까지 다시 하고, 그래도 실패하면 멈춘다. 다시 돌리면 이어서 한다 |
| EC-06 | 질문의 품번에 한국어 조사가 붙는다("1N5819는") | BM25 토큰은 영문·숫자 연속만 쓴다 |

## How

- **검색 함수**: `retrieve(question: str, *, k: int = 5, parts: list[str] | None = None) -> list[dict]` (`backend/rag/retrieve.py`). 서버 기동 때 `warmup()`을 한 번 불러 BM25 색인과 품번 → 문서 색인을 만든다.
  - `parts`: 에이전트가 특정 후보 품번(예: `["SS34"]`)을 확인할 때 준다. 사용자가 입력하지 않는다. 표지 카드(`이 데이터시트의 품번: ...`)에 그 품번이 적힌 문서의 카드만 dense(`WHERE chunk_id = ANY(...)`, 정확 검색)와 BM25(허용 밖 카드 제외) 후보로 쓰고 RRF는 같다. 품번은 대소문자만 무시하고 전체가 같아야 한다(SS34는 SS34L에 걸리지 않음). 코퍼스에 없는 품번뿐이면 `[]`를 돌려주고 전체 코퍼스로 넘어가지 않는다(호출 쪽이 "문서로 확인 안 됨"으로 판정). `parts`가 없으면 필터 없이 같다.
  - 돌려주는 키: `chunk_id`, `document_key`, `file`(PDF 이름), `page`, `table`, `content`, `score`(RRF 점수), `dense_rank`, `bm25_rank`
  - RRF: 카드마다 `1 / (60 + 순위)`를 두 목록에서 더한다. 후보는 방식마다 50개
- **데이터**: `db/02_rag_corpus.sql`
  - `source_documents`, `document_chunks`: Migration 1 초안(`db/001_create_business_tables.sql.draft`)과 같은 정의에 `IF NOT EXISTS`
  - `chunk_embeddings`: `vector(1536)`, HNSW(`vector_cosine_ops`)
- **모델과 도구**: 임베딩 `text-embedding-3-small`(`backend/services/llm.py`의 `embed_texts`). Docling 2.145.0과 pdfplumber는 uv 의존성 그룹 `ingest`로 두어 서버 이미지에 넣지 않는다.
- **제약**: 임베딩 호출은 `llm.py`로만 한다. 재시도에는 상한을 둔다. 코퍼스 문장은 지시가 아니라 데이터다.
- **원본 위치**: PDF·파싱 결과·카드·벡터는 저장소 밖 로컬 `SojaFit/corpus/tsc/`에 둔다.

## AC

- **AC-01** Given 칸 하나가 두 행에 걸친 표, When 표 카드를 만들면, Then 두 행 카드 모두에 그 칸의 글자가 들어간다.
- **AC-02** Given 머리 행이 두 줄인 표, When 열 이름을 만들면, Then 두 줄의 글자를 ` / `로 잇고 같은 글자는 한 번만 쓴다.
- **AC-03** Given 11-01 Docling JSON 1,360건, When `chunk`를 돌리면, Then 카드 52,244장, 서로 다른 본문 45,898개가 나온다.
- **AC-04** Given 카드 파일과 벡터, When `ingest`를 돌리면, Then 문서 1,360행, 청크 52,244행, 임베딩 52,244행이 생긴다.
- **AC-05** Given 순위 목록 두 개, When RRF로 합치면, Then 두 목록에 모두 있는 카드가 한쪽에만 있는 카드보다 위에 온다.
- **AC-06** Given 질문 "TSC 1N5819는", When BM25 토큰을 만들면, Then `["tsc", "1n5819"]`이다.
- **AC-07** Given `gold_chunks`의 "X.pdf, 2쪽, …", When 정답 위치를 읽으면, Then 문서 `X.pdf`, 쪽 2다.
- **AC-08** Given 표지에 SS34가 적힌 문서와 SS34L만 적힌 문서, When `parts=["ss34"]`로 허용 카드를 고르면, Then SS34가 적힌 문서의 카드만 고르고 SS34L 문서의 카드는 고르지 않는다.
- **AC-09** Given 코퍼스 표지에 없는 품번만 든 `parts`(예: `["NOPE123"]`), When 검색하면, Then 허용 카드가 없어 `[]`를 돌려준다.
