# jeongun 작업 기록

## 2026-11-02 설계 결정 기록(사용자 흐름, 근거가 없을 때, 코퍼스 나누기, Supabase 저장)
- 한 일: 조장과 정한 설계를 `SPEC.md`와 ADR 0005~0007에 적었다. 사용자 흐름에 후보 정하기 단계를 넣고, 근거가 없을 때의 순서(코퍼스 재검색 → TSC 실시간 조회 → 후보 먼저·단서 요청 → 단서 없이 진행)와 판정 근거로 인정하는 것을 적었다. 코퍼스는 기존(동결)·증분으로 나누고 평가는 기존만, Supabase는 한 프로젝트에 `halfvec`·HNSW 없음으로 둔다.
- 바꾼 파일: `SPEC.md`(1절 하는 일·하지 않는 것, 2절 사용자 흐름·근거가 없을 때, 6절), `docs/adr/`(0005, 0006, 0007, ADR.md), 이 파일
- 실행한 명령과 결과: 로컬 compose DB 임시 스키마에서 저장 방식별 크기를 쟀다(코퍼스 829.5 → HNSW 제거 466.7 → `halfvec` 258.0 → 본문 중복 제거 237.8MB). `embedding::halfvec::vector = embedding`이 52,244/52,244였고, 카드 1,000개 질의의 정확 검색 top-5 집합이 100% 같았다. 정확 검색 중앙값은 float32 230.5ms, `halfvec` 140.2ms였다. 임시 스키마는 지웠고 기존 표는 그대로다. 서비스 DB 크기는 그래프가 없어 langgraph 1.2.18·checkpoint-postgres 3.2.0으로 오프라인 추정만 했다. 문서 확인은 ADR·SPEC 상대 링크가 실제 파일을 가리키는지 대조했다.
- 확인 못 한 것: Supabase 무료 서버의 검색 시간, Supabase가 500MB를 MB와 MiB 중 무엇으로 세는지, 실제 그래프의 체크포인트 크기, 실제 질문 임베딩으로 본 `halfvec` 비교, 평가 때 실시간 조회를 끄는 것에 대한 강사 확인, Infineon 파싱 글 저장 여부.
- 다음 할 일: 임베딩 모델 확정 뒤 `halfvec` Migration과 Supabase 적재, D4 그래프로 체크포인트 크기 실측, 그래프 입력·질문 종류·노드 정하기.

## 2026-11-02 manifest를 대시보드가 읽는 크기로 줄이기
- 한 일: PR #19 머지 뒤 Checkpoint 대시보드 G3 칸에 "manifest가 커서 읽지 못함"이 떴다(`data/manifest.jsonl` 1,012,774바이트). GitHub GraphQL `Blob.text`가 이 파일을 512,000바이트에서 자르는 것(`isTruncated=true`)을 확인했다. 1,360줄 모두 같은 값 6개(`manufacturer`, `collected_at`, `parser`, `status`, `purpose`, `usage_conditions`)를 `chunk.py`의 `DOC_DEFAULTS`로 옮기고 `ingest.py`가 읽을 때 채우게 했다. 늘 null이고 읽는 코드가 없는 `exact_original_part_match`와, 파일 이름이 `source_url` 끝과 같은 `path`를 뺐고, 공백 없는 JSON으로 쓴다. `collect.py`는 `path`가 없으면 `source_url` 끝에서 파일 이름을 얻는다.
- 바꾼 파일: `backend/rag/`(chunk.py, ingest.py, collect.py), `data/manifest.jsonl`, `data/DATA.md`, `data/corpus/CORPUS.md`, `docs/specs/rag-pipeline.md`(What 4), `SPEC.md`(6절 확장 문장), `tests/`(test_rag_chunk.py, test_rag_ingest.py, test_rag_collect.py, TESTS.md), 이 파일
- 실행한 명령과 결과: 기존 manifest를 1회용 스크립트(저장소 밖)로 새 형식으로 바꿨다. 바꾸기 전에 1,360줄 모두 뺀 값이 `DOC_DEFAULTS`와 같고 `path`의 파일 이름이 `source_url` 끝과 같은지 assert했다. 1,012,774 → 470,263바이트(1,360줄, 한 줄 평균 346바이트). `ingest.main`과 같은 식으로 채운 값 12개가 1,360줄 모두 바꾸기 전과 같고, `collect.read_targets`의 파일 이름 1,360개도 같다. `uv run --offline pytest -q` 26 passed, 2 skipped. 새 크기 시험은 바꾸기 전 manifest로 돌리면 실패한다.
- 확인 못 한 것: `chunk.py` main은 docling이 로컬에 없어 돌리지 않았다(새 쓰기 형식의 키 순서·공백은 바꾼 manifest와 같게 코드로 맞춤). DB 재실행 시험(`TEST_DATABASE_URL`)은 돌리지 않았다. 한 줄 346바이트면 약 1,480줄에서 512,000바이트를 넘으므로 Infineon(280~430건)을 넣으면 다시 넘을 수 있다. 그래서 Infineon·MOSFET 확장은 3차 범위에서 하지 않기로 하고 SPEC 6절에 지원 가능 품목으로만 적었다(11-02 조장 결정).
- 머지 뒤 확인(PR #21): GitHub GraphQL이 main의 manifest를 자르지 않고 읽는다(`byteSize` 470,263, `isTruncated=false`). Checkpoint 대시보드 G3 칸이 "문서 1360/50, 청크 52,244/10,000"으로 나온다(11-02). `docs/GATES.md` G3 상태 칸을 이에 맞게 고쳤다.
- 다음 할 일: 평가자가 서로 다른 청크 수(본문 sha256)를 확인할 방법을 강사에게 묻는다. 카드는 TSC 약관 때문에 저장소 밖에 있다.

## 2026-11-01 오세창 검수 의견 13개 반영 (PR #15~#18 후속)
- 한 일: PR #15~#18의 오세창 검수 의견 13개를 PR 하나로 반영했다. 결정 기록 2건(ADR 0003 v1 50건 동결, ADR 0004 임베딩 1536차원 임시 결정), manifest로 PDF 받기(sha256 대조), `chars_original`·`chars_kept`·`truncated` 실제 계산, `SIGALRM`이 없는 OS 처리, 벡터 캐시 끊김 복구, DB에 있는 임베딩은 다시 부르지 않기, BM25 0점 후보 제외, 데모 모드 BM25만, 평가 대상 0건 오류, 각각의 테스트.
- 바꾼 파일: `docs/adr/`(0003, 0004, ADR.md), `SPEC.md`(6·7절), `docs/specs/rag-pipeline.md`(EC-07~10, AC-10~12), `backend/rag/`(collect.py, parse.py, chunk.py, ingest.py, retrieve.py, RAG.md), `evals/run_retrieval.py`, `data/manifest.jsonl`, `data/DATA.md`, `tests/`(test_rag_collect.py, test_rag_parse.py, test_rag_ingest.py, test_rag_retrieve.py, TESTS.md), 이 파일
- 실행한 명령과 결과: `uv run --offline pytest -q` 25 passed, 2 skipped in 0.49s(DB 시험 2개는 건너뜀). DB 시험은 `TEST_DATABASE_URL`(로컬 compose DB)을 줄 때만 돌게 했고, api 이미지 컨테이너에서 `pytest tests/test_rag_ingest.py tests/test_rag_retrieve.py`를 돌려 14 passed, 시험용 임시 스키마는 남지 않았다. 처음에는 DB 시험이 `DATABASE_URL`을 읽어 .env의 Supabase 주소로 접속을 시도했다가 접속 단계에서 실패했다(만든 것 없음). 그래서 시험은 `TEST_DATABASE_URL`만 쓴다. 글자 수를 새로 재려고 `chunk`를 파서 비교용 도커 이미지에서 1,360건에 다시 돌렸고, 카드 파일은 이전과 바이트까지 같았다. 원문(본문 글 조각 + 표 칸) 5,231,811자 중 카드에 들어간 글자는 5,016,468자(95.9%, 문서 중간값 96.1%, 최저 85.6%)이고 1,356건이 `truncated`다. 빠진 글은 주로 표와 같은 조각으로 묶여 버려진 표 옆 주석이다(예: BZT52B2V4 F15의 "Notes: 1. The Zener Voltage (VZ) is tested under pulse condition…"). 처음 잴 때는 카드 앞에 붙는 소제목을 세지 않아 92.2%로 나와 고쳤다.
- 확인 못 한 것: 로컬 DB의 `source_documents` 글자 수 열은 예전 값 그대로다(`ingest`가 있는 문서를 건너뜀). Supabase 적재 때 새 manifest로 들어간다. Windows에서 직접 돌려 보지는 않았다.
- 다음 할 일: 표 옆 주석이 카드에서 빠지는 문제를 사전 등록 뒤 청킹 실험으로 본다. 50건 동결 뒤 베이스라인, Supabase 적재, 후보 찾기용 사양 표.

## 2026-11-01 retrieve()에 품번 필터 인자 parts 넣기 (PR jeongun-3)
- 한 일: `retrieve(question, *, k=5, parts=None)`에 품번 필터를 넣었다(HNSW 개선 실험 B, 사전 등록 #6의 방식). `warmup()`이 BM25 색인과 함께 표지 카드(`이 데이터시트의 품번: ...`)로 품번(소문자) → 문서 색인을 만든다. `parts`를 주면 그 품번이 적힌 문서의 카드만 dense(`WHERE chunk_id = ANY(...)`, 인덱스를 끈 정확 검색)와 BM25(허용 밖 카드는 -inf) 후보로 쓰고 RRF는 같다. 품번은 대소문자만 무시하고 전체가 같아야 걸린다. 코퍼스에 없는 품번뿐이면 `[]`를 돌려주고 전체 코퍼스로 넘어가지 않는다. 질문에서 품번을 뽑는 일은 하지 않는다(에이전트가 후보 품번을 준다).
- 바꾼 파일: `backend/rag/retrieve.py`, `backend/rag/RAG.md`, `tests/test_rag_retrieve.py`, `tests/TESTS.md`, `docs/specs/rag-pipeline.md`(What 6, Out of Scope, How, AC-08·09), `SPEC.md`(4절 검색 계약, 6절 검색), 이 파일
- 실행한 명령과 결과: `uv run --offline pytest -q` 14 passed. 로컬 compose DB에 `docker compose run --rm --no-deps -u ... -e DEMO_MODE=0 ... api python <확인 스크립트>`(스크립트는 저장소 밖 임시 폴더, 키는 compose가 .env에서 읽음). warmup 1.7초, 표지가 읽힌 문서 1,360/1,360, 색인 품번 9,589개. "SS34 정격이 어떻게 돼?" + `parts=["SS34"]` → 5장 모두 `SS32 SERIES_Q2412.pdf`(허용 카드 55장). `parts=["1N4148"]` → 5장 모두 `1N4148 SERIES_K2301.pdf`(허용 문서 1개, 1N4148W 문서는 따로). `parts=["NOPE123"]` → `[]`. parts 없이 → 5장(SS32·SS32H·SS34ALH·SS34FSH 문서가 섞임). 데이터시트 근거가 있는 관련 19문항에 질문 속 코퍼스 품번을 `parts`로 주니 19/19 필터가 걸려 문서 Recall@5 1.000, MRR 1.000, 쪽 적중@5 0.947(실험 B와 같음, 필터 없는 하이브리드는 1.000 / 0.921 / 0.737), 질문당 중간값 1.05초(임베딩 호출 포함). 쪽을 놓친 문항은 n03 하나. parts 없을 때 BM25 후보가 바꾸기 전 식과 50문항 모두 같았다(API 호출 없이). 질문 임베딩 호출 22회.
- 확인 못 한 것: 19문항·동결 전 초안이다. parts 없는 경로의 dense SQL은 바꾸기 전과 같은 문장이라 다시 재지 않았다. 에이전트가 `parts`를 정하는 노드와 서버 기동 때 `warmup()` 연결은 하지 않았다. 표지 표기와 다른 품번 표기(접미사·하이픈 차이)는 걸리지 않는다.
- 다음 할 일: 50건 동결 뒤 같은 방식으로 다시 재고, 판정 노드가 후보 품번을 `parts`로 넘기게 연결한다.

## 2026-11-01 HNSW 개선 실험 4개 (PR jeongun-3)
- 한 일: HNSW 인덱스가 한국어 질문의 가까운 카드를 놓치는 문제로, 결과를 보기 전에 `evals/PREREGISTER.md` #5~#8을 커밋하고 조건 하나씩 바꾼 실험 4개를 같은 측정 스크립트로 쟀다. A 영어 질문(번역은 정답을 모르는 서브에이전트가 미리 만든 고정 번역), B 품번 필터, C `KURE-v1`, D `Qwen3-Embedding-0.6B`(C·D는 원격 GPU 도커에서 카드 45,898개를 다시 임베딩해 로컬 DB 실험 표에 넣음). EVAL_REPORT 1장에 결과 표를 넣었다.
- 바꾼 파일: `evals/PREREGISTER.md`, `EVAL_REPORT.md`, `evals/results/hnsw_exp_*_2026-11-01.json`(5개), 이 파일
- 실행한 명령과 결과: 측정 스크립트·원격 임베딩 스크립트는 저장소 밖 `전자_데이터시트/evidence/hnsw_exp/`. 기준을 같은 스크립트로 다시 재니 HNSW 겹침(ef 100)이 사전 등록에 적은 43%가 아니라 61%였다(인덱스를 다시 만든 뒤라서). 결과: B가 정확 하이브리드 1.000/1.000/0.947(19문항 모두 필터 걸림, dense 0.0007초), D가 HNSW 겹침 76%/97%·HNSW 하이브리드 MRR 0.816, C는 겹침 38%/85%, A는 정확 하이브리드 MRR 0.512로 떨어짐. 원격 이미지 빌드 3분, KURE 임베딩 4.7분, Qwen3 3.7분. 로컬 모델이라 API 비용 없음, 질문 임베딩만 과금.
- 확인 못 한 것: 19문항·동결 전 초안이다. 차이가 1~3문항이라 개선이라 단정하지 않는다. 영어 질문을 dense에만 쓰는 방식과 품번 필터 + HNSW 조합은 재지 않았다. 로컬 모델의 서버(Cloud Run) 메모리·지연은 재지 않았다.
- 다음 할 일: 품번 필터를 `retrieve()`에 넣을지 정하고(D3 메타데이터 필터), 50건 동결 뒤 다시 잰다.

## 2026-11-01 하이브리드 검색과 검색 평가 실행기 (PR jeongun-3)
- 한 일: `backend/rag/retrieve.py` 뼈대에 `retrieve(question, k=5)`를 넣었다. dense는 `embed_texts`로 질문을 임베딩해 pgvector 정확 검색 상위 50, BM25는 `document_chunks` 본문으로 메모리 색인(`warmup()`) 상위 50, 둘을 RRF(k=60)로 합친다. `evals/run_retrieval.py`는 평가셋 관련 문항의 `gold_chunks`에서 PDF 이름과 쪽을 읽어 문서 Recall@k, MRR, 쪽 적중@k를 잰다. EVAL_REPORT 1장에 저장소 코드 결과, 9장에 재현 명령을 넣었다.
- 바꾼 파일: `backend/rag/retrieve.py`, `backend/rag/RAG.md`, `evals/run_retrieval.py`, `evals/EVALS.md`, `tests/test_rag_retrieve.py`, `tests/TESTS.md`, `EVAL_REPORT.md`, 이 파일
- 실행한 명령과 결과: `docker compose run --rm --no-deps -e DEMO_MODE=0 ... api python -m evals.run_retrieval evals/draft_50.jsonl <결과>`(키는 compose가 .env에서 읽음). 데이터시트 근거가 있는 관련 19문항(회로 근거만 있는 6문항 제외)에서 문서 Recall@5 1.000, MRR 0.921, 쪽 적중@5 0.737, 질문당 중간값 1.2초. 11-01 실험과 같은 11문항은 1.000 / 0.955 / 0.818(11-01 실험 1.000 / 0.909 / 0.727). 처음에는 dense를 HNSW로 찾아 MRR 0.553~0.816이 나왔고, 정확 검색과 비교해 HNSW가 한국어 질문의 가까운 카드를 놓치는 것을 확인해 정확 검색으로 바꿨다(m03: `ef_search` 1000에서도 정확 검색 1위 0.4177을 놓침). 같은 질문을 혼자 보낼 때와 묶어 보낼 때 임베딩은 코사인 1.0으로 같았다. `uv run --offline pytest -q` 11 passed.
- 확인 못 한 것: 동결 전 초안이라 베이스라인이 아니다. 서버 기동 때 `warmup()`을 부르는 연결과 그래프 노드 연결은 하지 않았다(D4). 리랭킹·필터 없음. 정확 검색이 Cloud Run·Supabase에서 얼마나 걸리는지 재지 않았다.
- 다음 할 일: 50건 동결 뒤 같은 명령으로 베이스라인, Supabase 적재, D3 리랭킹·필터 사전 등록.

## 2026-11-01 코퍼스 표와 임베딩 적재 (PR jeongun-2)
- 한 일: `db/02_rag_corpus.sql`로 코퍼스 표 3개(`source_documents`, `document_chunks`는 Migration 1 초안과 같은 정의에 `IF NOT EXISTS`, `chunk_embeddings`는 `vector(1536)`과 HNSW 코사인 인덱스)를 만들었다. `backend/rag/ingest.py` 뼈대 자리에 적재 코드를 넣었다. 임베딩은 본문 해시 캐시를 다시 쓰고 없는 본문만 `embed_texts`로 만든다(128개씩, 3회 재시도). 다시 돌리면 들어간 문서·카드·임베딩은 건너뛴다.
- 바꾼 파일: `db/02_rag_corpus.sql`, `db/DB.md`, `db/ERD.md`, `backend/rag/ingest.py`, `backend/rag/RAG.md`, `backend/rag/chunk.py`(설명 한 줄), `docs/specs/rag-pipeline.md`(단계 이름 index → ingest), `tests/test_rag_ingest.py`, `tests/TESTS.md`, 이 파일
- 실행한 명령과 결과: 로컬 compose DB(`sojafit-db-1`)에 SQL을 두 번 적용해 두 번째는 모두 건너뜀을 확인했다. api 이미지 컨테이너를 compose 네트워크에 붙여 `python -m backend.rag.ingest`를 돌리니 2분 5초에 문서 1,360, 카드 52,244, 임베딩 52,244행이 들어갔고 새 임베딩 호출은 0회(11-01 벡터 캐시 사용)였다. 다시 돌리면 넣은 행이 0이다. 첫 실행에서 행 이름이 500자를 넘는 카드 5장(면책 문구 표) 때문에 `row_label` VARCHAR(500) 오류가 나 트랜잭션 전체가 되돌려졌고, 이름표 열만 500자로 잘라 다시 넣었다. `uv run --offline pytest -q` 결과 8 passed in 0.49s.
- HNSW 인덱스 문제와 수정: 빈 표에 만든 HNSW 인덱스에 5만 행을 한꺼번에 넣은 상태에서 검색하니, 같은 질문("TSC 1N5817은 역전압을 몇 V까지 견뎌?")의 정확 검색 1위(1N5817, 거리 0.3452)를 놓치고 거리 0.4358 카드를 1위로 냈다(`hnsw.ef_search` 200에서도 같음). 다 넣은 뒤 인덱스를 다시 만들자 정확 검색과 상위 3개가 같아졌다. 그래서 `ingest`가 임베딩을 넣은 뒤 `REINDEX`를 한다(재적재 2분 27초). 그 뒤에도 관련 19문항의 상위 50개를 정확 검색과 비교하니 `ef_search` 100/400/1000에서 43%/79%/99%만 겹쳤다. 인덱스를 m 24·ef_construction 200으로 다시 만들어 본 측정은 100%로 나왔지만, 같은 인덱스에서 m03 질문 하나를 따로 보면 `ef_search` 1000에서도 정확 검색 1위(거리 0.4177)를 놓쳐 그 측정을 믿지 않고 인덱스 설정을 기본값으로 되돌렸다. 정확 검색은 질문당 0.33~0.55초다. 저장한 벡터는 11-01 벡터와 코사인 거리 최대 0.00000024로 같았다.
- 확인 못 한 것: Supabase에는 적용하지 않았다(조장 확인 뒤). 캐시에 없는 본문을 실제로 임베딩하는 경로는 이번 실행에서 돌지 않았다(11-01 실험의 같은 호출 방식으로 45,898개를 만든 적은 있다).
- 다음 할 일: PR jeongun-3(하이브리드 검색과 평가 실행기).

## 2026-11-01 수집·파싱·청킹 코드를 backend/rag로 옮기기 (PR jeongun-1)
- 한 일: 작업서 `docs/specs/rag-pipeline.md`와 SPEC 4절 검색 계약, 6절 청킹·검색 방식을 먼저 커밋했다. 저장소 밖 실험 스크립트(목록 합치기, PDF 받기, GPU 파싱과 두 방향 대조, 전체 청킹)를 `backend/rag/collect.py`·`parse.py`·`chunk.py`로 옮겼다. 표 카드 규칙은 Docling 없이 테스트하도록 순수 함수로 뗐다. Docling·pdfplumber는 uv 그룹 `ingest`로 추가했다. `data/manifest.jsonl`을 1,360건으로 다시 썼다.
- 바꾼 파일: `docs/specs/rag-pipeline.md`, `docs/specs/SPECS.md`, `SPEC.md`, `backend/rag/`(collect.py, parse.py, chunk.py, RAG.md), `tests/test_rag_chunk.py`, `tests/TESTS.md`, `pyproject.toml`, `uv.lock`, `data/manifest.jsonl`, `data/DATA.md`, `data/corpus/CORPUS.md`, 이 파일
- 실행한 명령과 결과: `collect list`가 11-01 목록 csv를 바이트까지 같게 다시 만들었고(PDF 1,360개), `collect download`는 1,360개 모두 이미 있어 건너뛰었다. `chunk`를 파서 비교용 도커 이미지(docling 2.145.0)에서 1,360건 전체에 돌려 5분에 카드 52,244장·서로 다른 본문 45,898개가 나왔고, 11-01 결과와 문서·순서·본문 해시·종류·쪽·표 제목이 모두 같았다. manifest는 1,360행, 쪽 합계 7,725, 저장소 표본 3건과 해시가 같다. `parse run`을 같은 이미지(CPU)에서 PDF 2건에 돌리니 표 수(5, 6)와 표 숫자 대조(81/81, 49/49)가 11-01 GPU 기록과 같았고, `parse recall`은 표 영역 원문 숫자 130개를 모두 찾았다. `uv export --no-dev`와 기본 설치에는 docling·pdfplumber·torch가 0개, `--group ingest`에는 3개다. `uv run --offline pytest -q` 결과 7 passed in 0.23s.
- 확인 못 한 것: 로컬 맥 가상환경에 `ingest` 그룹을 설치해 돌려 보지는 않았다(도커 이미지로 확인). PDF 받기는 새 파일 없이 건너뛰기만 확인했다.
- 다음 할 일: PR jeongun-2(코퍼스 표와 임베딩 적재), jeongun-3(하이브리드 검색과 평가 실행기).

## 2026-11-01 평가 문항 50건 초안과 1차 사람 판정
- 한 일: 기존 30건(관련 17, 비관련 13)에 Codex로 20건(관련 8, 비관련 12)을 더해 50건(관련 25, 비관련 25)을 만들었다. 출제와 정답은 Codex 세션 두 개로 나눴고, 정답 세션에는 출제 의도 필드를 지운 문항만 줬다. 정답의 숫자를 근거 쪽 원문과 기계로 대조하고 숫자형·비관련·판단형으로 나눈 검토표를 만들었다. 하정운이 50건 1차 판정을 마쳤고, 2차 판정은 김재훈이 11-02에 한다. 동결은 두 판정을 맞춘 뒤 50건을 v1로 한다.
- 바꾼 파일: `evals/draft_50.jsonl`, `evals/DRAFT_50_REVIEW.md`, `evals/EVALS.md`(파일 목록, 동결 계획), `README.md`·`SOJAFIT.md`(v1 50건), 이 파일
- 실행한 명령과 결과: 출제 Codex 6분·96,561토큰, 정답 Codex 5분·84,039토큰. 정답 세션의 관련/비관련과 비관련 종류가 20건 모두 출제 의도와 같았다. 기계 대조에서 원문에 없는 숫자는 오답 예시 1개(h03의 4.4)와 기준표 여유율 계산값 2개(n07의 214.3, n08의 714.3)뿐이었다. `draft_50.jsonl` 생성 스크립트의 자체 검사(50건, 관련 25, 비관련 4종, 관련 문항 근거 있음, 넷리스트 경로 있음) 통과. `uv run --offline pytest -q`는 3 passed.
- 확인 못 한 것: 2차 사람 판정 전이다. `gold_chunks`는 데이터시트 쪽·표·행과 넷리스트 위치이고 청크 id는 아직 붙이지 않았다. 출제·정답·대조 스크립트는 저장소 밖(`전자_데이터시트/evidence/eval50_codex/`)에 있다.
- 다음 할 일: 11-02 김재훈 2차 판정, 다른 문항 맞추기, 50건을 `dataset_v1.jsonl`로 옮겨 동결(11-03), 검색 베이스라인 점수.

## 2026-11-01 하이브리드 검색(BM25 + dense) 비교
- 한 일: 결과를 보기 전에 `evals/PREREGISTER.md` #4를 커밋하고, 개선 2 카드에서 검색 방식만 dense → 하이브리드(BM25 상위 50 + dense 상위 50, RRF k=60)로 바꿔 같은 11문항을 다시 쟀다. BM25만도 참고로 쟀다. `EVAL_REPORT.md` 1장에 결과를 적었다.
- 바꾼 파일: `EVAL_REPORT.md`, `evals/PREREGISTER.md`, `evals/results/hybrid_search_2026-11-01.json`, 이 파일
- 실행한 명령과 결과: `uv run --offline python ../전자_데이터시트/evidence/embed/hybrid_eval.py ../corpus/tsc/chunks <결과 json>`(BM25 색인 포함 6.4초). dense만 재실행은 0.727 / 0.568 / 0.364로 앞 결과와 같았다. 하이브리드는 문서 Recall@5 1.000, MRR 0.909, 쪽 적중@5 0.727, BM25만은 1.000 / 0.894 / 0.636이었다. 기대 5개 중 1개 맞음, 4개는 범위 위.
- 확인 못 한 것: 정답 근거는 사람 검토 전이고 문항이 11개뿐이다. 토큰 규칙과 RRF k는 하나만 써 봤다. 스크립트는 저장소 밖에 있어 재현 명령을 EVAL_REPORT 9장에 넣지 못했다.
- 다음 할 일: v1 동결 뒤 하이브리드를 기준선으로 다시 잰다. `backend/rag/retrieve.py`에 옮길 때 회로 기호(D1~D3)와 표시 코드가 겹치는 문제를 함께 본다.

## 2026-11-01 청킹 A·C 임베딩과 로컬 검색 비교
- 한 일: 전체 1,360건의 개선 전(A)·개선 2(C) 청크에서 서로 다른 본문을 `backend.services.llm.embed_texts`(`text-embedding-3-small`, 1536차원)로 임베딩하고 로컬 도커 pgvector(`sojafit-db-1`)의 실험 표 `exp_rag_chunks`에 넣었다. 결과를 보기 전에 `evals/PREREGISTER.md` #3에 기대를 적고 커밋했다. 비동결 초안 문항 중 데이터시트 근거가 필요한 11개로 상위 5개 검색을 비교해 `EVAL_REPORT.md` 1장에 적었다.
- 바꾼 파일: `EVAL_REPORT.md`, `evals/PREREGISTER.md`, `evals/results/chunking_search_2026-11-01.json`, 이 파일
- 실행한 명령과 결과: 임베딩 C 45,898개 5,391,648토큰(12.6분), A 10,723개 2,201,510토큰(3.1분), 재시도 0회. DB 행 수는 C 45,898, A 10,723으로 벡터 수와 같다. 문서 Recall@5 A 0.455 → C 0.727, MRR 0.321 → 0.568, C 쪽 적중@5 0.364. 사전 등록 기대 5개 중 4개 맞음, C 쪽 적중은 범위 아래.
- 확인 못 한 것: 정답 문서·쪽은 사람 검토 전 초안이다. 11문항이라 차이를 통계로 구별할 수 없다(부호 검정 양측 p=0.25). 비용은 대시보드가 아니라 단가로 계산했다. 임베딩·적재·검색 스크립트는 저장소 밖(`전자_데이터시트/evidence/embed/`)에 있고, `backend/rag/`로 옮길 때 넣는다.
- 다음 할 일: 품번이 정확히 맞는 카드를 찾도록 BM25나 품번 필터를 붙여 m05, h03, h04를 다시 본다. v1 동결 뒤 같은 비교를 다시 잰다.

## 2026-11-01 D1 파서 비교와 TSC 데이터시트 전체 파싱
- 한 일: TSC 다이오드 분류 13개의 제품 목록에서 데이터시트 PDF 1,360개를 모았다(저장소 밖 로컬 보관). 파서 5종(pypdf, pdfplumber, PyMuPDF, pdftotext, Docling)을 PDF 3건 원문 대조(값 41개)와 표본 100건 속도로 비교해 Docling으로 정했다. 청킹은 고정 길이 → Docling 기본 → 표 행 단위+이름표+표지 3단계를 대리 지표로 비교했다. 전체 1,360개를 원격 GPU 도커에서 Docling으로 파싱하고 표 숫자를 pdfplumber 글자와 두 방향으로 대조했다. `EVAL_REPORT.md` 1장에 원문 대조 3건, 파서 비교, 청킹 대리 지표, 파싱 방식과 검증 숫자를 채웠다.
- 바꾼 파일: `EVAL_REPORT.md`, `evals/results/`(parser_accuracy·parser_truth·parser_speed·chunking_proxy·parse_gpu_log·parse_gpu_recall·parse_gpu_witness_unmatched), 이 파일
- 실행한 명령과 결과: 원문 대조 41개 중 Docling 41, pdfplumber 36, pdftotext 33, PyMuPDF 23, pypdf 22. 표본 100건 쪽당 Docling CPU 4.58초. GPU(RTX 3080 Ti) 전체 7,725쪽 쪽당 0.385초, 오류 0. Docling 표 숫자 중 원문에 있는 비율 99.993%, 표 영역 원문 숫자 중 Docling에 있는 비율 99.89%. EVAL_REPORT의 숫자는 위 원시 결과 파일과 다시 대조했다. `git diff --check` 통과.
- 확인 못 한 것: 청킹 비교는 대리 지표이고 검색 점수(Recall, MRR)는 아직 재지 않았다. Docling이 아예 찾지 못한 표는 세지 못했다. 비교·파싱 스크립트는 수집 코드와 함께 `backend/rag/`로 옮길 때 넣는다.
- 다음 할 일: 파싱 결과로 합친 칸 채우기와 청킹, 임베딩 적재, 평가셋 v1 정답 확정과 동결, 검색 기준 점수(D2).

## 2026-11-01 CI의 setup-uv 버전 고치기
- 한 일: `ci.yml`이 없는 태그 `astral-sh/setup-uv@v10`을 가리켜 test 작업이 Set up job에서 실패했다. setup-uv의 주 버전 태그는 v1~v7까지만 있어서 있는 태그 `v10.3.3`으로 고정했다.
- 바꾼 파일: `.github/workflows/ci.yml`, 이 파일
- 실행한 명령과 결과: `gh api`로 setup-uv 태그를 조회해 `v10.3.3`(2026-10-28 릴리스)이 있고 `version` 입력을 그대로 받는 것을 확인했다. 고치기 전 PR #13의 CI 오류는 "Unable to resolve action `astral-sh/setup-uv@v10`"이었다.
- 확인 못 한 것: 고친 CI의 통과 여부는 push 뒤 PR #13에서 확인한다.
- 다음 할 일: 없음

## 2026-11-01 평가 문항 초안 30건과 회로 5종 옮기기
- 한 일: 김재훈의 PR #12(파일 245개, 808,365줄)에서 평가 문항 초안 30건과 그 문항이 쓰는 회로 5종만 옮겼다. 회로는 넷리스트, 연결 목록, 원본 LICENSE·README만 두고, 회로도 원본·PCB·재출력본·검증 JSON과 문항에 쓰지 않는 회로 18종은 넣지 않았다. 질문 파일이 경로를 직접 가리키므로 경로는 그대로 두었다. `CIRCUITS.md`에 회로 5종의 원 저장소·커밋·라이선스 표를 넣고, 검수 문서의 "사용자 검수" 같은 작성 도구 보고 문구를 작성자·검수자로 고쳤다. TSC 데이터시트 PDF 3건과 manifest도 함께 옮겼다.
- 바꾼 파일: `evals/`(draft_30.jsonl, DRAFT_30_REVIEW.md, EVALS.md), `data/circuits/`(CIRCUITS.md, collected/ 20개), `data/corpus/`(CORPUS.md, tsc/ 3개), `data/manifest.jsonl`, `data/DATA.md`, `docs/specs/`(evaluation-draft-30.md, SPECS.md), `SOJAFIT.md`, `.gitattributes`, 이 파일
- 실행한 명령과 결과: 30문항이 가리키는 넷리스트 경로가 모두 있고 sha256이 문항에 적힌 값과 같다. PDF 3건의 sha256이 manifest와 같다. 옮긴 문서의 상대 링크 중 깨진 것은 0개다(제작자 README 안의 원 저장소 그림·PDF 링크 2개는 원본 그대로 둠). `git diff --cached --check` 통과. `uv run --offline pytest -q`는 3 passed.
- 확인 못 한 것: 문항의 관련/비관련, 정답, 근거 청크는 비어 있다. 테스트는 이 파일들을 검사하지 않는다.
- 다음 할 일: 11-03 전에 하정운이 정답과 근거를 채운다. 문항을 늘릴 때 필요한 회로만 더한다.

## 2026-10-30 테이블 정의서 마무리
- 한 일: PR #6으로 들어온 `db/table-definition.md`의 추가 검토 항목 A-01~A-20을 정하고 9절을 결정 기록으로 바꿨다. 조건별 비교 표 `requirement_checks`와 청크 임베딩 표 `chunk_embeddings`를 더했고(벡터 차원 N은 임베딩 모델을 정한 뒤 채움), `analysis_runs.thread_id`, `document_chunks.chunk_sha256`, `source_documents`의 manifest 열을 넣었다. Migration은 업무 표(1)와 임베딩 표(2)로 나눈다고 11절에 적었다. SPEC 3절 판정 표에 코드·채점·뜻과 판정 순서, "문서로 확인 안 됨"일 때 하는 일을 채웠다.
- 바꾼 파일: `db/table-definition.md`, `SPEC.md`, 이 파일
- 실행한 명령과 결과: `git diff --check` 통과. 정의서에 적은 저장소 경로를 대조해 없는 경로 0개. `uv run --frozen pytest -q`는 2 passed. pgvector `vector` 타입의 HNSW 인덱스 상한 2,000차원은 pgvector README에서 확인했다.
- 확인 못 한 것: SQL로 옮겨 보지 않아 CHECK·FK가 그대로 만들어지는지는 Migration 1에서 확인한다. 역할·분류·사양 코드 목록은 규칙 파일과 코퍼스 분류를 만들며 바뀔 수 있다.
- 다음 할 일: 심태현이 ERD와 Migration 1을 쓴다. 임베딩 모델(오세창)이 정해지면 N을 채우고 Migration 2를 쓴다.

## 2026-10-30 Cloud Run 배포 주소 확보
- 한 일: `main`(790d087)의 빈 FastAPI를 GCP 프로젝트 `sojafit`의 Cloud Run 서비스 `sojafit-api`(서울 리전 `asia-northeast3`)에 올리고 공개로 열었다. 배포 주소를 README 팀 정보에 적고 GATES G1을 "진행 중"으로 바꿨다.
- 바꾼 파일: `README.md`, `docs/GATES.md`, 이 파일
- 실행한 명령과 결과:
  - `gcloud run deploy sojafit-api --source <main 내보낸 폴더> --region asia-northeast3 --port 8000 --set-env-vars DEMO_MODE=1 --max-instances 1`로 배포했다. 첫 시도는 빌드 단계에서 실패했다. 새 프로젝트의 기본 컴퓨트 서비스 계정에 소스 버킷 읽기 권한(`storage.objects.get`)이 없었다. 그 계정에 `roles/run.builder`를 준 뒤 다시 배포해 리비전 00002가 떴다.
  - 공개는 `gcloud run services add-iam-policy-binding sojafit-api --member=allUsers --role=roles/run.invoker`로 했다.
  - 토큰 없이 `curl <주소>/health`는 200, `{"status":"ok"}`. 공개 전에는 같은 요청이 403이었다. `/docs`도 200.
- 확인 못 한 것: 배포한 이미지는 `/health`만 있는 빈 앱이라 DB·Langfuse 연결은 없다. 다음 배포부터는 `main`의 새 코드를 다시 올려야 주소에 반영된다.
- 다음 할 일: 핵심 시나리오가 생기면 다시 배포하고 G1을 평가용 계정으로 확인한다.

## 2026-10-30 폴더 설명 파일 이름을 대문자로
- 한 일: 폴더 설명 파일 22개와 저장소 지도를 대문자 이름으로 바꿨다(`backend/backend.md` → `backend/BACKEND.md`, `SojaFit.md` → `SOJAFIT.md`). 이 파일들을 가리키던 링크·문구와 `<폴더명>.md` 규칙 문구를 고치고, 결정을 ADR 0002로 남겼다. ADR 0001 본문은 그대로 두고 0002를 가리키는 줄만 더했다.
- 바꾼 파일: 이름을 바꾼 23개, `AGENTS.md`, `README.md`, `SPEC.md`, `docs/EVALUATION.md`, `docs/adr/`(0001, 0002, `ADR.md`), 이 파일
- 실행한 명령과 결과: `git mv`로 이름을 바꿔 기록이 이어진다(23개 모두 R로 잡힘). 저장소의 md 44개에서 대소문자까지 구분해 상대 링크 49개를 대조해 깨진 링크 0개. 옛 소문자 이름이 남은 곳은 ADR 0001 본문 1곳(일부러 둠). `uv run --frozen pytest -q`는 2 passed.
- 확인 못 한 것: macOS처럼 대소문자를 구분하지 않는 파일 시스템에서 조원이 이 변경을 받을 때 문제가 없는지는 아직 보지 않았다.
- 다음 할 일: PR을 올리기 전에 정운이 검증한다.

## 2026-10-30 주제서 옮기기와 가산 폴더 정리
- 한 일: 통과한 주제서를 `docs/TOPIC.md`로 옮겼다(본문은 원본과 같음). 가산 중 서비스 안에서 돌아야 하는 MCP·Skill을 `extras/mcp_skill/`에서 `backend/mcp_skill/`로 옮기고, `extras/`는 이미지 밖 작업인 파인튜닝(`extras/finetune/`)만 맡게 했다. GraphRAG와 증분 수집 자동화는 `backend/rag/`에 둔다고 적었다.
- 바꾼 파일: `docs/TOPIC.md`, `backend/mcp_skill/`(옮김), `extras/EXTRAS.md`, `extras/finetune/FINETUNE.md`, `SOJAFIT.md`, `backend/BACKEND.md`, `backend/rag/RAG.md`, `SPEC.md`
- 실행한 명령과 결과: 주제서 본문을 원본과 `diff`해 차이 0줄. `uv run --frozen pytest -q`는 2 passed. 바뀐 문서 15개의 상대 링크 34개 중 깨진 링크 0개.
- 확인 못 한 것: `mcp` 패키지를 아직 넣지 않아 `server.py`는 실행해 보지 않았다. Neo4j와 수집 스케줄러를 어디서 돌릴지는 정하지 않았다.
- 다음 할 일: 조 회의에서 가산 담당과 Neo4j·스케줄러 위치를 정한다.

## 2026-10-30 문서 뼈대 추가
- 한 일: 기능 정본 `SPEC.md` 뼈대(8절), DB 관계도 `db/ERD.md`, 프롬프트 폴더 `backend/prompts/`와 버전 기록 표, 화면 디자인 규칙 `backend/web/DESIGN.md`를 만들었다. 정해진 내용은 주제서·AGENTS·ADR 0001에서 옮기고, 정하지 않은 칸은 `(정할 것)`으로 두었다.
- 바꾼 파일: `SPEC.md`, `SOJAFIT.md`, `db/ERD.md`, `db/DB.md`, `backend/prompts/PROMPTS.md`, `backend/BACKEND.md`, `backend/web/DESIGN.md`, `backend/web/WEB.md`, 이 파일
- 실행한 명령과 결과: 바뀐 문서 8개의 상대 링크 30개를 대조해 깨진 링크 0개. 커밋마다 `git diff --cached --check` 통과. ERD의 라이브러리 표 이름은 `.venv`의 `langgraph-checkpoint-postgres` 3.2.0 소스에서 확인했다.
- 확인 못 한 것: 백로그 보드(GitHub Projects)는 파일이 아니라 만들지 않았다. 데이터시트를 검색 색인용으로 나누는 것이 약관의 "비수정"에 맞는지는 SPEC 6절에 확인할 것으로 남겼다.
- 다음 할 일: 조 회의에서 SPEC의 숫자 성공 기준, 대체 판정 5종의 코드 값과 채점 처리, 그래프 노드를 정한다. 화면 방식(FastAPI 직접 또는 별도 프론트)을 정해 ADR로 남긴다.
