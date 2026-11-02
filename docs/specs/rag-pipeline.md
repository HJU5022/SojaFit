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
4. `chunk`: Docling JSON을 카드로 자른다. PDF마다 품번 표지 1장, 표 밖 글은 HybridChunker, 표는 한 행 = 카드 한 장(합친 칸 채움, `[파일 · 쪽 · 표 제목]` 이름표). 문서 목록 `data/manifest.jsonl`도 쓴다. manifest에는 문서마다 다른 값만 쓰고, 모든 문서에 같은 값은 `chunk.py`의 `DOC_DEFAULTS`에 둔다(512,000바이트 아래, Checkpoint 대시보드가 읽는 크기).
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
| EC-07 | 질문 단어가 어떤 카드와도 안 맞는다(BM25 점수 0) | 점수 0인 카드는 후보에서 빼고, 남는 게 없으면 BM25 후보는 빈 목록이다 |
| EC-08 | 키 없는 데모 모드(`DEMO_MODE=1`) | 임베딩 API를 부르지 않고 BM25만으로 찾는다 |
| EC-09 | 새 clone에 목록 xlsx가 없다 | `collect download data/manifest.jsonl <pdf 폴더>`로 manifest의 원본 주소에서 받고 sha256을 대조한다 |
| EC-10 | Windows에서 파싱한다(SIGALRM 없음) | PDF별 시간 제한 없이 돌고 경고를 낸다. 맥·리눅스·도커를 권장한다 |

## How

- **검색 함수**: `retrieve(question: str, *, k: int = 5, parts: list[str] | None = None) -> list[dict]` (`backend/rag/retrieve.py`). 서버 기동 때 `warmup()`을 한 번 불러 BM25 색인과 품번 → 문서 색인을 만든다.
  - `parts`: 에이전트가 특정 후보 품번(예: `["SS34"]`)을 확인할 때 준다. 사용자가 입력하지 않는다. 표지 카드(`이 데이터시트의 품번: ...`)에 그 품번이 적힌 문서의 카드만 dense(`WHERE chunk_id = ANY(...)`, 정확 검색)와 BM25(허용 밖 카드 제외) 후보로 쓰고 RRF는 같다. 품번은 대소문자만 무시하고 전체가 같아야 한다(SS34는 SS34L에 걸리지 않음). 코퍼스에 없는 품번뿐이면 `[]`를 돌려주고 전체 코퍼스로 넘어가지 않는다(호출 쪽이 "문서로 확인 안 됨"으로 판정). `parts`가 없으면 필터 없이 같다.
  - 돌려주는 키: `chunk_id`, `document_key`, `file`(PDF 이름), `page`, `table`, `content`, `score`(RRF 점수), `dense_rank`, `bm25_rank`
  - RRF: 카드마다 `1 / (60 + 순위)`를 두 목록에서 더한다. 후보는 방식마다 50개
- **데이터**: `db/002_rag_corpus.sql`
  - `source_documents`, `document_chunks`: 이 SQL이 생성하고 업무 테이블 초안이 참조한다. `IF NOT EXISTS`는 기존 정의의 일치를 검증하지 않는다.
  - `chunk_embeddings`: `vector(1536)`, HNSW(`vector_cosine_ops`)
- **모델과 도구**: 임베딩 `text-embedding-3-small`(`backend/services/llm.py`의 `embed_texts`). Docling 2.145.0과 pdfplumber는 uv 의존성 그룹 `ingest`로 두어 서버 이미지에 넣지 않는다.
- **제약**: 임베딩 호출은 `llm.py`로만 한다. 재시도에는 상한을 둔다. 코퍼스 문장은 지시가 아니라 데이터다.
- **원본 위치**: PDF·파싱 결과·카드·벡터는 저장소 밖 로컬 `SojaFit/corpus/tsc/`에 둔다.

## 후속 필요사항: 요청 판본 확인 (미구현)

별도 저장 용량 작업은 [corpus-storage-budget.md](corpus-storage-budget.md)를 따릅니다. 현재 기본은 vector(1536)이며, halfvec은 복제 DB에서 설정과 수동 SQL을 함께 바꿔 검증하는 선택 경로입니다. 전체 코퍼스 축소나 halfvec 최종 채택이 완료됐다는 뜻은 아닙니다.

- 2026-11-02 평가셋 `wrong_period` 문항 검토에서 확인한 요구다. 현재 파일명에서 개정 코드를 추출해 manifest에 기록하지만, 요청 판본과의 일치 여부를 자동 판정하는 절차는 없다.
- 질문이 지정한 품번·개정 코드·연도를 보유 문서의 판본 정보와 대조하는 절차가 필요하다. 파일명 코드와 PDF 내부 판본 표시의 대조 방법도 정해야 한다.
- 연도와 개정 코드의 대응은 제조사의 명시적 근거가 필요하다. 수집일·NET 내보내기 날짜를 발행연도로 쓰거나 개정 코드를 임의로 연도로 해석하지 않는다.
- “고정 코퍼스에 요청 판본이 없음”과 “그 판본이 실제로 존재하지 않음”을 구분해야 한다. 제조사 사이트 등에서 실제 존재를 확인하는 외부 조회는 현재 구현 범위 밖이며, 도입 여부와 확인 방법은 별도 결정이 필요하다.
- 구현 전 담당·입출력·판본 필터·확인 불가 처리와 테스트 기준을 작업서에 확정해야 한다. 이 메모는 구현 완료나 평가셋 정답 변경을 뜻하지 않는다.

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
- **AC-10** Given BM25 점수가 모두 0인 질문, When 키워드 후보를 만들면, Then 빈 목록이다.
- **AC-11** Given `DEMO_MODE=1`, When 검색하면, Then 임베딩 API를 부르지 않고 dense 후보 없이 BM25로만 찾는다.
- **AC-12** Given DB에 임베딩이 이미 있고 벡터 캐시가 없다, When `ingest`를 다시 돌리면, Then 임베딩 API를 부르지 않고 행도 늘지 않는다.
