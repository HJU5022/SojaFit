# jeongun 작업 기록

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
