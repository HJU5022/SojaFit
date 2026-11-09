# jeongun 작업 기록

## 2026-11-09 React용 SQL 번호를 018~020으로 정리 (브랜치 `jeongun-8`)
- 한 일: 같은 번호를 분석 서비스 SQL과 나눠 쓰던 React용 SQL을 비워 둔 018~020으로 옮겼다. `db/013_projects.sql` → `db/018_projects.sql`, `db/014_conversations.sql` → `db/019_conversations.sql`, `db/015_approvals_quotes.sql` → `db/020_approvals_quotes.sql`(`git mv`, 내용 그대로). 공유 DB에 적용한 적이 없는 파일이다. 분석 서비스 SQL 013~017은 그대로다. 빈 볼륨 실행 순서는 017 다음 018~020, 그다음 021이 된다.
- 바꾼 파일: SQL 3개 이름, `db/DB.md`(실행 순서 · 파일 목록 · 021의 "018~020 비움" 문장 지움), `db/schema/erd.md`(만든 곳 · 019 문단의 체크포인트 문장을 분석 thread 기준으로), `db/schema/table-definition.md`(머리 · 표 목록 · 5.2 · 대화 · 승인 절 번호), `backend/projects/PROJECTS.md`, `SOJAFIT.md`(트리 3줄), 시험 4개의 SQL 목록(`tests/api/test_full_service_flow.py` · `test_projects.py`, `tests/conversations/test_repository.py`, `tests/projects/test_project_repository.py`), 이 파일. CI · Compose · scripts에는 옛 이름이 없었다. 지난 작업 기록과 `docs/superpowers/` 계획은 그때 기록이라 고치지 않았다.
- 실행한 명령과 결과: 키 없는 전체 1042 passed, 106 skipped(바꾸기 전과 같음). 일회용 Postgres 전체 1120 passed, 1 failed(바꾸기 전에도 같은 lifespan 시험), 27 skipped. 같은 컨테이너의 새 DB에 `db/*.sql`을 파일명 순서로 적용(007 데모 계정은 환경변수가 필요해 뺌)해 오류 없이 public 표와 `sojafit_agent` 표가 함께 생기는 것을 확인했다.
- 확인 못 한 것: Compose 새 볼륨 첫 기동(007 포함)은 돌리지 않았다.

## 2026-11-09 React 분석 실행 · 재개를 사용자 분석 서비스로 연결 (브랜치 `jeongun-8`)
- 한 일: React 작업대의 `POST /api/threads/{id}/runs` · `POST /api/runs/{id}/resume`이 `d5.production_service`(public `checkpoints` 표가 없어 바로 실패, 예외는 버려짐) 대신 `app.state.conversations`(`memory_service.Conversations`)를 거치게 했다. 첫 run에 React 대화와 같은 UUID로 분석 회로 · thread를 만들고(`Conversations.ensure_thread`, 회로 id도 같은 UUID라 동시 첫 run에도 한 행) 대상 부품을 고정한다. 다른 `target_ref`는 run을 만들기 전에 409, 회로에 없는 부품은 422, 서비스가 없으면 스트림 전에 503이다. run은 `message`, 재개는 그 thread의 현재 버전으로 `resume`을 스레드 풀에서 부르고, 결과는 그래프 상태에서 `public_state`(d5에서 `dto.py`로 옮김)로 골라 `public.runs` · `public.messages`에 저장한 뒤 보낸다. `failed` frame에 `error: {code, message}`(공통 오류 코드)를 붙이고, 4xx가 아닌 예외는 `request_id`와 함께 `LOGGER.exception`으로 남긴다. 쓰이지 않게 된 `backend/services/d5.py`(`D5Service` · `production_service` · `setup_checkpoints`)와 `tests/services/test_d5.py`를 지웠다. 프로젝트 삭제의 기본 public 체크포인트 정리를 없앴다(`checkpoint_delete` 주입 자리는 잠금 · rollback 시험용으로 남김).
- 정한 세부: ① 데모 모드에서 `ensure_thread`도 업로드와 같은 합성 회로 검사를 한다 ② React 연결 회로의 `netlist` 칸은 빈 글자(React 업로드는 원본을 저장하지 않음), 분석 회로 `filename`은 프로젝트 이름 ③ 실패 frame 코드는 `backend.main.ERROR_CODES`를 그대로 써 503은 `SERVICE_UNAVAILABLE`이다 ④ 진행 frame은 시작 때 `status` 하나다(분석 서비스가 그래프를 한 번에 돌림) ⑤ React 승인은 지금 그대로 public 승인 · 견적 · 승인 사례만 저장한다(분석 서비스 승인 · Store 기억 연결은 이번에 하지 않음).
- 바꾼 파일: `backend/api/conversations.py` · `projects.py`, `backend/conversations/memory_service.py`(`ensure_thread`) · `dto.py`(`public_state`) · `repository.py`(`get_thread`가 프로젝트 이름도 돌려줌), 지운 파일 `backend/services/d5.py` · `tests/services/test_d5.py`, 시험 `tests/api/test_conversations.py`(가짜 분석 서비스로 다시 씀) · `tests/api/test_threads.py`(DB 시험 2개) · `tests/conversations/test_dto.py` · `test_repository.py`, 문서 `backend/api/API.md` · `backend/conversations/CONVERSATIONS.md` · `backend/services/SERVICES.md` · `db/DB.md` · `docs/specs/d5-frontend-service.md`(How 대화 API · EC-07 · AC-10) · `SPEC.md`(3절 서비스 목록 한 줄) · `SOJAFIT.md`(트리) · 시험 폴더 설명 3개, 이 파일
- 실행한 명령과 결과: `env -u DATABASE_URL PYTHON_DOTENV_DISABLED=1 uv run --no-sync pytest -q` 바꾸기 전 1040 passed, 106 skipped → 뒤 1042 passed, 106 skipped. 일회용 Postgres(`docker run -d --rm --name react-connect-pg … pgvector/pgvector:pg16`, 127.0.0.1:55443)에 CI와 같이 003 · 005 · 006 · 021을 넣고 `TEST_AUTH_DATABASE_URL` · `TEST_THREAD_DATABASE_URL`로 전체: HEAD 1118 passed, 1 failed, 27 skipped → 뒤 1120 passed, 1 failed, 27 skipped. 실패 1개(`test_enabled_app_lifespan_opens_and_closes_real_persistence`, 카드 도구가 시작 때 `document_chunks`를 읽음)는 바꾸기 전 HEAD에서도 같다. 변이 확인: 실패 로그 줄을 빼면 실패 frame 시험이 실패했고 되돌렸다. 실제 LLM · MCP · Langfuse · 원격 DB 호출 없음.
- 알려진 한계: 합성 데모(`DEMO_SCENARIOS=1`)의 분석 서비스는 합성 회로와 지원 질문 3개만 받아, 키 없는 React run은 데모 보드여도 422다. 프로젝트를 지워도 같은 UUID의 분석 thread · checkpoint · 승인 · Store 기억은 남는다(기억은 `/api/memories`로 철회 · 삭제). 재개가 4xx · 429로 실패하거나 그래프 도중 실패하면 React run은 `failed`, 분석 thread는 그 상태로 남아 같은 대화의 새 질문이 409다(새 대화 필요). 프론트는 `failed` frame의 `error`를 아직 쓰지 않는다.
- 확인 못 한 것: 실제 LLM · 카드 도구로 React run 한 번(키 · 코퍼스 DB 필요), 브라우저에서 React 화면으로 확인, 팀 Supabase에 `sojafit_agent` 준비 여부.

## 2026-11-09 자기 가입: 가입 API, IP 가입 하루 3회 · 로그인 실패 15분 30회 한도 (브랜치 `jeongun-8`)
- 한 일: 정운 결정(11-09)대로 승인 없이 바로 `user`가 되는 자기 가입을 넣었다. 1차는 `POST /api/auth/signup`(이메일 + 8자 이상 비밀번호, 이메일 인증 없음)과 클라이언트 IP당 UTC 하루 3회 한도까지다. 성공하면 로그인과 같은 세션 쿠키를 심고 `{"user_id"}`를 돌려준다. 중복 이메일 409, 입력 오류 422(입력값 미노출), Origin 없음·불일치 403, 한도 초과 429. Spec 먼저: `login-auth.md`의 Why·Goal·What·How·AC와 SPEC 4절(가입 계약 한 줄)·8.6절을 고쳤고, 로그인 실패 IP 한도(15분 30회)와 LLM 토큰 한도(사용자 하루 200,000·서비스 하루 2,000,000)는 "다음 작업"으로 적었다. 주요 문서(SPEC.md)를 이 브랜치에서 고친 것은 조장이 이 기능에 한해 허락한 예외다.
- 한 일(2차): 계정당 15분 5회 잠금에 더해 클라이언트 IP당 15분 로그인 실패 30회 한도를 `authenticate()` 같은 트랜잭션 안에 넣었다. 30번째 실패 시점부터 15분 동안 그 IP의 로그인은 비밀번호가 맞아도 일반 실패와 같은 401이다. 표 `auth_login_ip_attempts`는 `auth_login_attempts`와 같은 열(횟수 · 창 시작 · 잠금 끝)이고, 창 · 잠금이 끝난 행은 계정 행과 같은 조건으로 로그인 때 지운다. 두 IP 표를 한 파일에 두려고 아직 어디에도 적용하지 않은 `db/021_signup_limits.sql`을 `db/021_auth_ip_limits.sql`로 바꿨다. `login-auth.md`(Goal · How · AC · 로그인 실패 제한 절)와 SPEC 8.6을 고쳤다.
- 정한 세부: ① 클라이언트 IP는 Cloud Run(`K_SERVICE` 있음)에서 `X-Forwarded-For`의 마지막 값, 그 밖에서는 소켓 주소. 근거는 Google 문서(부하분산기가 덧붙인 값만 신뢰, https://docs.cloud.google.com/load-balancing/docs/https#x-forwarded-for_header), Google Cloud Run 샘플의 프록시 1단 신뢰(https://github.com/GoogleCloudPlatform/nodejs-docs-samples/pull/3586), `K_SERVICE`(https://docs.cloud.google.com/run/docs/container-contract). run.app 직접 호출의 형식을 못 박은 공식 문서는 찾지 못했다 ② 중복 이메일(409)도 1회로 센다(409가 계정 존재를 알려 주므로 존재 확인도 하루 3회로 묶음). 429·503은 트랜잭션이 되돌려져 세지 않는다 ③ IP 원문은 저장하지 않고 세션 토큰과 같은 키 해시(`session_token_hash`)만 둔다 ④ 가입의 scrypt도 로그인과 같은 advisory lock 2칸을 나눠 써 동시 계산을 2개로 묶는다(칸이 차면 503) ⑤ 날짜는 기존 분석 한도와 같은 UTC ⑥(2차) 로그인 성공은 IP 횟수를 지우지 않는다(자기 계정 로그인을 끼워 넣어 횟수를 되돌리는 것을 막음). 다른 IP 횟수도 건드리지 않는다 ⑦(2차) 잠긴 동안의 요청은 계정 · IP 횟수를 올리지 않는다(계정 잠금과 같은 규칙) ⑧(2차) 잠그는 순서는 계정 시도 행 → IP 행 → 사용자 행으로 고정했다 ⑨(2차) `authenticate(email, password, ip)`로 `ip`를 필수 인자로 바꿨다(빠뜨리면 한도가 조용히 꺼지지 않게). 가짜 함수를 쓰던 시험 2곳(`test_auth.py`, `test_health.py`)도 맞췄다 ⑩(2차) TestClient는 모든 요청을 같은 주소 'testclient'로 보내 시험 사이에 실패가 쌓이므로, `test_auth.py`에 DB 시험마다 IP 실패 표를 비우는 autouse fixture를 두었다.
- 바꾼 파일: `docs/specs/login-auth.md` · `SPECS.md`(목록 한 줄), `SPEC.md`(4절 · 8.6절), `backend/auth.py`(`client_ip` · `signup`, 머리 설명), `backend/main.py`(`Signup` · `/api/auth/signup`, 로그인과 같은 쿠키를 `set_session_cookie`로 묶음), `backend/BACKEND.md`, `db/021_auth_ip_limits.sql`(새, 018~020은 번호 정리용으로 비움) · `db/DB.md`, `SOJAFIT.md`(트리 한 줄), `.github/workflows/ci.yml`(인증 DB 초기화 목록에 021), `tests/api/test_auth.py`(시험 9개 + fixture, 기존 가짜 함수 3곳) · `tests/api/test_health.py`(가짜 함수 인자) · `tests/api/API.md`, 이 파일
- 실행한 명령과 결과: 바꾸기 전 `env -u DATABASE_URL PYTHON_DOTENV_DISABLED=1 uv run --no-sync pytest -q` 1074 passed, 113 skipped → 바꾼 뒤 1079 passed, 116 skipped(새 DB 시험 3개는 키 없이 건너뜀). 일회용 Postgres(`docker run --rm --name signup-test-pg … pgvector/pgvector:pg16`, 127.0.0.1:55442)에 003 · 005 · 006 · 021을 CI와 같은 방식으로 적용하고 `TEST_AUTH_DATABASE_URL=… pytest -q tests/api/test_auth.py` 59 passed(건너뜀 0). 같은 DB로 CI처럼 전체(`TEST_AUTH_DATABASE_URL` · `TEST_THREAD_DATABASE_URL`) 1157 passed, 38 skipped. 끝나고 `docker stop signup-test-pg`(자동 삭제 확인). 팀 Supabase · Cloud Run · `.env` 값은 쓰지 않았다. `git diff --check` 통과.
- 실행한 명령과 결과(2차): 키 없는 전체 1079 passed, 117 skipped. 같은 방식의 일회용 Postgres(55442)에 003 · 005 · 006 · 021 적용 뒤 `tests/api/test_auth.py` 60 passed(건너뜀 0, 새 IP 시험 14초), 같은 DB로 CI처럼 전체 1158 passed, 38 skipped(같은 DB에서 15분 안에 두 번째로 돌린 실행). 변이 확인: `LOGIN_IP_FAILURES`를 1000으로 바꾸면 새 IP 시험이 실패했고 되돌렸다. 끝나고 `docker stop signup-test-pg`(자동 삭제 확인).
- 확인 못 한 것: 실제 Cloud Run에서 `X-Forwarded-For` 마지막 값이 정말 내 공인 IP인지(배포 안 함). 팀 Supabase에 021 적용(안 함). [주의] 2차부터 로그인도 이 표를 쓰므로 021 없이 이 코드를 배포하면 비밀번호 로그인과 가입이 모두 503이 된다. 같은 NAT · 통신사 뒤 사용자들이 한 IP 한도를 나눠 쓰는 문제, 여러 IP에서 나눠 보내는 대입은 IP 한도로 막지 못한다. 1 · 2차를 로컬 커밋 하나로 남겼다(푸시 안 함).
- 다음 할 일: LLM 토큰 한도(사용자 · 서비스 하루) → React 가입 화면 → 데모 계정 정리.

## 2026-11-09 사양 표 버리고 서비스 기본을 카드 도구로(ADR 0016)
- 한 일: 정운 결정(11-09)대로 서비스 두 곳이 카드 도구를 전환 스위치 없이 쓰게 했다. `memory_service.py`의 분석 그래프와 `d5.py`의 `production_service`는 `card_find.default_find()` · `card_specs.default_specs()` · `make_lookup(mcp.check, specs.doc_rows)`를 넘긴다(`run_graph.py`의 `LAB_FIND=cards` · `LAB_SPECS=cards`와 같은 조립). `memory_service`는 `timed_tool`로 감싼 도구가 `prefetch` · `doc_rows` · `also_read` 속성을 잃어 `functools.update_wrapper`로 옮겼다(판정 에이전트가 `getattr`로 찾는다). 사양 표를 만들고 넣던 `db/011_part_specifications.sql`과 `pipeline/specs.py`의 build · sample · load · CLI(1,151줄 → 78줄)를 지우고, 카드 도구 · `ingest.py`가 import하는 규칙만 남겼다. `run_graph.py` 기본값이 아직 부르는 `spec_lookup.part_specs` · `find_candidates`, MCP `get_part_specs` · `find_parts_by_specs`, `mcp_retriever.part_specs` · `find_parts`에는 `shortcut:` 줄을 달아 남겼다. ADR 0016을 쓰고 0013을 대체됨으로 바꿨다.
- 바꾼 파일: `backend/conversations/memory_service.py`, `backend/services/d5.py`, `backend/rag/pipeline/specs.py`, `backend/rag/spec_lookup.py`, `backend/mcp_skill/mcp_server/server.py`, `backend/graph/mcp_retriever.py`, 지운 함수를 가리키던 주석 `backend/rag/card_find.py` · `card_specs.py` · `card_read.py` · `units.py` · `pipeline/ingest.py`, 지운 파일 `db/011_part_specifications.sql`, 시험 `tests/rag/test_rag_specs.py`(43개 → 3개, 패키지 규칙만) · `tests/rag/test_rag_spec_lookup.py`(DB · SQL 시험 11개 지움, 가짜 연결 순위 시험 2개 남김) · `tests/api/test_threads.py`(새 시험 1개: 실제 경로 조립이 카드 도구와 속성을 넘기는지, DB 없음), `SPEC.md`(2절 표, 3절, 5절 Skill 줄, 8.3, 8.7), `docs/adr/0016-사양-표를-버리고-카드-읽기를-기본으로-한다.md`(새) · `0013-…` 상태 · `ADR.md`, `db/DB.md`, `db/schema/table-definition.md`(머리 · 표 목록 · 5.7), `SOJAFIT.md` 트리, 폴더 설명 `backend/rag/RAG.md` · `backend/mcp_skill/MCP_SKILL.md` · `tests/rag/RAG.md` · `tests/api/API.md`, 이 파일
- 실행한 명령과 결과: `uv sync` 뒤 `env -u DATABASE_URL PYTHON_DOTENV_DISABLED=1 uv run --no-sync pytest -q` 시작 1074 passed, 113 skipped → 끝 1035 passed, 102 skipped(지운 시험 40 + DB 시험 11, 더한 시험 1). 새 시험은 `update_wrapper`를 빼면 실패하는 것을 확인하고 되돌렸다. 저장소 밖 일회성 스크립트로 가짜 MCP · 가짜 카드 도구를 끼워 `memory_service._graph()`와 `d5.production_service`가 카드 도구를 넘기는지 확인했다. 실제 LLM · DB · MCP 서버 · Langfuse 호출 없음. 원격 DB와 `evals/runners/run_graph.py` · `backend/multi_agent/` · `backend/prompts/` · `llm.py` · `langfuse_prompts.py`는 고치지 않았다.
- 확인 못 한 것: 실제 DB · LLM으로 서비스 분석 한 번 돌리기(카드 도구는 `DATABASE_URL`로 DB를 직접 읽고 `default_specs()`가 시작 때 표지 색인을 읽는다). 측정 4의 원시 결과 파일(이 저장소에 없음, 숫자는 정운 전달). 카드 도구의 DB · LLM 오류는 판정 코드가 `search_error`로 바꾸지 않아 실행 실패로 끝난다(`judge.py`는 MCP 장애만 받음, 고칠 곳이 `backend/multi_agent/`라 손대지 않음). 이미 만든 로컬 Compose 볼륨에는 `part_specifications` 표가 남는다.
- 다음 할 일: (운영 DB 표는 11-09에 지움) `jeongun` 브랜치 병합 때 `run_graph.py` 기본값을 카드로 바꾸고 `shortcut:` 6곳(사양 SQL 조회 · MCP 사양 도구 · 클라이언트 메서드)과 `db/012` 주석의 사양 표 언급을 지운다.

## 2026-11-08 밤 청킹 v4d ~ v4h 커밋, v4h 임베딩 · 검색만 재기, 청킹 멈춤 기준(결정 23)
- 한 일: lab 청킹 v4d ~ v4h(`tsc-v4h-2026-11-08`)를 커밋했다(lab `v3` 브랜치 8003f82, 원격에 푸시하지 않음). v4h 카드 51,967개를 다시 임베딩해 로컬 DB `sojafit_v4`에 넣고, 검색만(LLM 없음) 잰 결과와 청킹을 멈추는 기준을 문서에 적었다.
- 바꾼 파일: `backend/rag/pipeline/chunk.py` · `tests/rag/test_rag_chunk.py`(커밋), `docs/experiments/b-redesign/3차-청킹-진단.md` 13절, `decisions.md` 23, `raw/r3/`에 원본 7개(`ret_v4h.json` · `regress.py` · `chunk_diff.py` · `gather.py` · `sample_new.py` · `partial.py` · `spec_cmp_v4h.json`), 이 파일. 문서는 정운 확인 전이라 커밋하지 않았다.
- 실행한 명령과 결과: `PYTHONPATH=. .venv/bin/python -m pytest -q tests/rag/` 156 passed, 21 skipped. 예전 사양 표 대조 v4h 같음 73,349 · 예전만 121, v4e 대비 잃은 값 0. 임베딩 467초, 적재 11초. 검색만 103질의 오류 0, p95 1.25초, 상위 5 밖으로 나간 문항 0.
- 확인 못 한 것: 에이전트 길(LLM이 검색어를 씀) v4h 재측정, 값 읽기(`specs.py`) 문제 고침, 전체 시험.
- 다음 할 일: 카드 기반 에이전트(사양 표 없이, 결정 21의 다음 단계).

## 2026-11-06 평가셋 v3 · 청킹부터 다시 재기 결정(ADR 0015)과 main 바로잡기 준비
- 한 일: 정운 결정(11-06)과 중간 점검 강사 최소 기준을 ADR 0015로 적고, 관련 문서를 맞췄다. 기준 평가셋은 판정 분야를 늘린 v3로 새로 만들고(v1 · v2 파일과 해시는 기록으로 둠), 청킹 결함을 고친 코퍼스부터 다시 잰다. 목표는 질문 1건 p95 10초 이내, 문서 · 페이지 단위 Recall@5 · MRR 0.95 이상이다.
- 같이 찾은 것: 11-06 쌓아 올린 PR #58 ~ #63이 main이 아니라 바로 아래 브랜치(`jeongun-1` ~ `jeongun-6`)로 merge되어, main에는 #57만 들어갔다. main과 로컬 `jeongun`의 차이는 111개 파일 +11,883줄이고, 전부 모인 곳은 `origin/jeongun-6`이다(로컬 `jeongun`과 내용 같음). `origin/main`을 `jeongun`에 합쳤다(62d427a, 충돌 없음, 합친 뒤에도 `jeongun-6`과 내용 같음).
- 바꾼 파일: `docs/adr/0015-평가셋-v3를-새로-만들고-청킹부터-다시-잰다.md`(새), `docs/adr/ADR.md`, `SPEC.md`(1절 숫자 성공 기준), `evals/guides/dataset-guide.md`(동결 계획 v3 줄, 기준 평가셋 문단), `evals/EVALS.md`, `EVAL_REPORT.md`(2장 머리), `docs/GATES.md`(G5 상태), `SOJAFIT.md`(트리 `dataset_v3.jsonl` 예정), 이 파일
- 실행한 명령과 결과: `git fetch` 뒤 `git rev-list` · `git diff --shortstat`로 브랜치별 내용 차이를 대조했다. `gh pr list`로 #57 ~ #63의 base를 확인했다. p95는 #41 S9 · #42 결과 파일 `rows`의 `latency_s`에서 실행기와 같은 정의(`int(0.95n)`번째)로 다시 계산했다. `uv run --frozen pytest -q tests/repo tests/evals` 170 passed.
- 확인 못 한 것: v3 문항 수 · 구성 · 2차 판정자, 판정 정확도 목표. 문서 단위 Recall@5 · MRR 1.000은 v1 관련 19문항 값이라 v3로 다시 재야 한다.
- 다음 할 일: 정운 승인 뒤 `jeongun` push와 `jeongun → main` PR(#58 ~ #63 내용과 이 기록) → 지금 청크로 dev 세트 검색 실패 진단 → 청킹 고침.

## 2026-11-06 후보 품번의 실시간 가격·재고(Mouser Search API, 저장 안 함)
- 한 일: 정운 요청으로 실시간 가격·재고를 서비스가 하는 일로 옮겼다(SPEC 1절, 실제 주문·결제와 판매처 찾기·비교는 그대로 범위 밖). ADR 0009(Mouser 응답은 저장·기록하지 않음) 때문에 Mouser 호출은 그래프 밖에 둔다. 두 그래프는 질문 종류 `price`를 받아 가격 안내 노드(같은 코드 `nodes.price_answer`)에서 물은 품번만 `price_parts`에 남기고 정해진 안내(`messages.price_message`)로 끝낸다. 값은 새 API `GET /api/prices`(로그인 필요)가 요청 때 `backend/services/mouser.py`로 한 번 조회해 응답으로만 내보낸다.
- 정한 세부: ① 품번 고르기는 검색 노드와 같은 규칙(질문 속 품번, 없으면 대상 값의 품번), LLM 없음 ② Mouser 요청은 문서(https://api.mouser.com/api/docs/V1)대로 `POST /api/v1/search/partnumber`, 키는 `apiKey` 쿼리, 품번은 `|`로 이어 한 번에 최대 10개, 품번마다 3~40자. 재시도 없음, 제한 시간 10초(연결 5초), 프로세스당 누적 300회 상한(값은 추정, 날이 바뀌어도 줄지 않음) ③ 돌려주는 칸은 품번(`ManufacturerPartNumber`) · 제조사 · 수량별 가격과 통화 · 재고 표시(`Availability`) · 상품 주소와 조회 시각(UTC)뿐이다 ④ 키가 요청 주소에 들어가므로 httpx 예외는 `from None`으로 끊고 종류(`MouserError.kind`)만 올린다. httpx가 INFO로 남기는 "HTTP Request: POST <주소>" 줄은 필터로 버린다(필터를 빼면 가짜 키가 로그에 찍히는 것을 확인했다) ⑤ API는 데모 모드에서도 품번 규칙(422)을 먼저 보고, `DEMO_MODE=1` · 키 없음 · 상한 · Mouser 실패면 `available: false`와 `reason`만 돌려준다. 모든 응답에 `Cache-Control: no-store`, 아무것도 로그에 쓰지 않는다 ⑥ `supervisor.md`의 범위 밖에 주문 · 결제 · 판매처 찾기 · 비교를 적어 `route.md`와 맞췄다(D4 · D5 같은 기준).
- 바꾼 파일: `SPEC.md`(1 · 2 · 4 · 6 · 7절, 8.4 수용 기준), `docs/specs/judge-agent.md`(Out of Scope 한 줄), `backend/graph/nodes.py` · `build.py` · `state.py` · `GRAPH.md`, `backend/multi_agent/contracts.py` · `messages.py` · `build.py` · `state.py` · `supervisor.py` · `MULTI_AGENT.md`, `backend/prompts/route.md` · `supervisor.md` · `PROMPTS.md`, `backend/services/mouser.py`(새) · `SERVICES.md`, `backend/main.py` · `BACKEND.md`, `.env.example`(`MOUSER_API_KEY` 묶음, 맨 끝), 시험 `tests/services/test_mouser.py`(새) · `tests/api/test_prices.py`(새) · `tests/graph/test_graph_build.py` · `tests/multi_agent/test_build.py`와 폴더 설명 3개, `SOJAFIT.md`, `README.md`, 이 파일
- 실행한 명령과 결과: 커밋마다 `uv run --frozen pytest -q` 전체 통과 뒤 커밋. 시작 680 passed, 43 skipped → 마지막 710 passed, 43 skipped. 시험의 Mouser 응답은 모두 손으로 쓴 가짜 값(통화 XXX, example.test 주소)이다. 그래프 시험은 `httpx.Client.send`를 막아 두고 돌려 HTTP 호출이 없고 상태에 가격 · 재고 칸이 `price_parts`뿐인 것을 확인했다. 모든 시험이 끝난 뒤 저장소 밖 일회성 스크립트로 `search_parts(["1N4148"])`를 한 번만 실제로 불렀고, 화면에는 상태 · 키 수락 여부 · 개수 · 칸 이름 유무만 찍었다(값은 찍거나 파일로 남기지 않았고 스크립트는 지웠다): HTTP 200, 키 수락, 부품 50개, `ManufacturerPartNumber` · `Manufacturer` · `PriceBreaks`(`Quantity` · `Price` · `Currency`) · `ProductDetailUrl`은 50개 모두에 있음, `Availability`는 일부 부품에만 있음. 실제 LLM · Langfuse · 운영 DB 호출 없음. 동결 평가셋 변경 없음.
- 확인 못 한 것: 답 · 견적 화면이 아직 없어 가격·재고 칸(출처 Mouser Electronics · 조회 시각 · 저장 안 함 표기)은 만들지 않았다(API까지). 데모 가격표(`data/demo/`)도 아직 없다. `1N4148`처럼 짧은 품번은 여러 제조사 부품이 50개까지 와서 TSC 부품만 고르는 일은 하지 않았다. Mouser 호출 한도(문서에 없음)와 300회 상한이 맞는지. 새 `route.md` · `supervisor.md`로 실제 모델이 가격 질문을 `price`로 고르는지, Langfuse 등록(하지 않음). 동결 v1 · v2의 n18("SS34 판매처 · 재고 수량 · 개당 가격")은 정답이 범위 밖 거절이라, 라우팅이 `price`로 보내면 채점에서 `hallucination_risk`로 셀 수 있다.
- 다음 할 일: 정운 결정(n18 처리, 제조사 거르기, 상한 값) → 답 · 견적 화면에 가격·재고 칸 → `route` · `supervisor` 새 본문 Langfuse 등록 → 측정.

## 2026-11-06 D4 v2 단일 그래프(강사 검토 반영)와 문서 맞추기
- 한 일: 강사가 D4 그래프를 두 가지("범위 판정을 첫 단에서 먼저 하라", "지금 것은 단순 직렬 흐름이다")로 돌려보내, 정운이 승인한 흐름대로 단일 그래프를 고쳤다. 입력 읽기 → 사실 확인(새, 멀티의 `facts_node` · `make_lookup` 그대로) → 라우팅(질문 종류 7가지, 확인된 사실을 멀티 Supervisor와 같은 글 `render_facts`로 받고 검색 전 거절 사유 `reason` · 일상 대화 답 `reply`를 냄) → 거절(검색 없음) / 짧은 답(새) / 생성(역할) / 재작성 → 검색 → 채점 고리(정격, 그대로) / 판정 읽기 → 판정 → 답 틀(새, 멀티 판정 에이전트 코드와 `render_judgement`). 거절은 이유 코드를 `refusal: {code, message}`에 남기고, 라우팅 거절 문구는 멀티와 같은 함수(`messages.refusal_for`, 멀티 `refuse_node`에서 꺼냄)로 만든다. 평가 실행기는 단일도 MCP 서버를 열어 사실 확인 · 사양 표 도구 · 메모리 체크포인터를 넘기고, `refusal_code` 점수를 멀티와 같이 센다. 이어서 11-05~11-06 커밋과 지금 코드에 비춰 틀린 문서 줄을 고쳤다.
- 정한 세부: ① 범위 밖 · 다른 부품은 라우팅이 `reason`을 비워 와도 종류에서 채운다(out_of_scope → `out_of_scope`, other_part → `not_found`, 멀티 Supervisor 규칙과 같음). 비었다고 형식 재시도(유료)로 다시 부르지 않으려는 것이다. 일상 대화의 `reply`는 비면 형식 오류다 ② 라우팅 답안지는 새 칸 `route`(question_type · reason · reply)에 둔다. 지시받은 칸(`facts` · `judge_read` · `judgement` · `refusal`) 말고 하나 더 늘었다 ③ 판정 노드는 멀티 `judge_agent`의 보고서(`reports`)를 버리고, 사양 표 도구 장애 보고는 `retrieval_error: {kind: spec_table}`로 옮겨 거절(`search_error`)로 보낸다 ④ 검색 고리의 거절 코드는 `not_found`(0장 · 2번 실패 모두), 검색 장애는 `search_error` ⑤ `specs` · `find`를 둘 다 주지 않으면 판정 · 찾기는 예전처럼 검색 고리로 가고, 하나만 주거나 체크포인터가 없으면 `ValueError` ⑥ D4의 예전 범위 밖 문구("이 질문은 SojaFit 범위 밖입니다…")는 멀티 문구로 바뀌었다(채점기는 path 끝 '거절'로 거절을 본다).
- 바꾼 파일: `backend/graph/build.py` · `nodes.py` · `state.py` · `GRAPH.md`, `backend/prompts/route.md` · `PROMPTS.md`, `backend/multi_agent/supervisor.py`(`render_facts`) · `messages.py`(`refusal_for`) · `build.py` · `MULTI_AGENT.md`, `evals/runners/run_graph.py` · `RUNNERS.md`, 시험 `tests/graph/test_graph_build.py` · `test_graph_route.py` · `test_graph_refuse.py` · `test_graph_read_input.py` · `test_graph_mcp_retriever.py` · `test_graph_mcp_stdio.py`(경로에 '사실 확인'), `tests/evals/test_run_graph.py`, 폴더 설명 `tests/graph/GRAPH.md` · `tests/evals/EVALS.md` · `tests/TESTS.md`, `SPEC.md`(2 · 3 · 5 · 8.3 · 8.7절), `SOJAFIT.md`(트리 설명 줄), `README.md`(에이전트 구조), `docs/GATES.md`(G4 · G5 · G6), `EVAL_REPORT.md`(7장 점수 연결 줄), `backend/BACKEND.md` · `judge/JUDGE.md` · `rag/RAG.md` · `services/SERVICES.md` · `mcp_skill/MCP_SKILL.md`, `evals/EVALS.md`, 이 파일
- 실행한 명령과 결과: 커밋마다 `uv run --frozen pytest -q` 전체 통과 뒤 커밋. 시작 658 passed, 43 skipped → 마지막 680 passed, 43 skipped. 갈래마다 가짜 LLM · 가짜 검색기 · 가짜 사양 표로 확인: 없는 품번 · 없는 개정판 · 범위 밖 · 다른 부품 거절은 검색기 호출 0번, 일상 대화는 `reply`가 답, 역할은 생성, 정격 고리 경로 · 검색 횟수는 그대로('사실 확인'만 경로에 더함), 판정 길은 인터럽트 1번을 `{'answers': {}}`로 재개해 판정 읽기 1번 · 답 틀로 끝남, 사양 표 장애는 거절. 평가 실행기는 가짜 MCP로 단일 앱을 열어 `check_corpus` 호출과 `part_missing` 거절까지 확인. 변이 확인 3건(갈림길의 거절 사유 검사 끔 → 5개 실패, 입력 읽기의 판정 · 사실 칸 비우기 뺌 → 1개 실패, 사양 표 장애 옮기기 끔 → 1개 실패, 모두 되돌림). 실제 LLM · MCP 서버 · DB · Langfuse 호출 없음. 동결 평가셋 3개 파일 변경 없음(`git diff`).
- 확인 못 한 것: 새 `route.md`로 실제 모델이 7가지를 맞게 고르는지와 `reason`을 사실대로 내는지, D4 v2 점수(동결 v2 70문항). `route.md` 새 본문은 Langfuse에 등록하지 않았다(지금 `route` 등록 본문과 다르다). `evals/runners/run_skill_pair.py`(Skill 비교 실행기)는 예전 흐름 그대로라 일상 대화 · 다른 부품 질문도 검색 고리로 보낸다(고치지 않음). 문서에서 틀린 줄만 고쳤고, `EVAL_REPORT.md` 4장 단일 대 멀티 표 빈칸, SPEC 8.1 · 8.2 "(정할 것)", SPEC 3절 "문서로 확인 안 됨이면 질의를 고쳐 다시 찾는다"와 판정 길(사양 표만 봄)의 차이, README 로그인 줄과 SPEC 4절에 Google 관리자 로그인이 없는 것은 그대로 두었다.
- 다음 할 일: 정운 승인 뒤 `route` 새 본문 Langfuse 등록 → D4 v2 사전 등록 · 동결 v2 70문항 측정(#37 · #38과 비교).

## 2026-11-06 판정 코드 고침 5가지(정운 승인)
- 한 일: 판정 에이전트 구현 뒤 정운이 승인한 5가지를 시험 먼저 쓰고 커밋 하나씩으로 고쳤다. ① 역전압 정격(VRRM · VR · VRWM)은 사용 온도(`temp`)를 맞추지 않는다(85°C나 TJ만 준 질문에서 VRRM까지 확인 안 됨이던 것). 전류 · 전력 정격과 특성 값은 그대로 맞춘다 ② `orig.<코드>`는 후보 행과 시험 조건이 같은 원래 행의 값이다. 없으면 "원래 부품의 같은 시험 조건 값 없음"으로 확인 안 됨이고, `orig.*` 조건은 찾기 거르기에서 뺀다 ③ 원래 품번에 주문 코드가 붙어도(`1N4148 A0G`) 기본 품번 행으로 찾는다 ④ 규칙 형식에 "A 또는 B" 묶음(`any`)을 더했다. R03 IFSM(펄스가 같을 때) 또는 IF_AV, R06 PPPM 또는 IPP, R10 CJ 또는 TRR은 `any`로, R14 "클램프 전압을 모르면 VDSS × 1.1"과 R15 "과도 전압이 없으면 버스 × 1.25"는 `basis` · `default`로 옮겼다(전에는 둘 다 필수) ⑤ TRR 쇼트키 면제 범위 `exempt`(`schottky` 기본 · `sic` · `none`)를 조건마다 두고, R14 100 kHz 초과 35 ns 조건은 `sic`로 했다. 그 밖에 `node_chat` 설명의 노드 목록에 `judge_read`를 더했다.
- 정한 세부: ② 기준식이 비교하는 코드와 다른 코드를 쓰면(R04 · R18 PD 기준식의 `orig.VZ`) 시험 조건을 맞출 수 없어 원래 부품의 첫 행 값을 쓴다. 같은 시험 조건인지는 두 행 모두 표 제목 기본 조건을 채운 뒤(`sheet_conditions.fill`) 양쪽으로 비교한다. 같은 조건 행이 여럿이면 여유가 가장 작은 행으로 판정하고 그 행을 인용한다. ④ 기본값 식이 회로 값을 쓰면 기준식 값이 없을 때 그 값을 묻는다(R14 `v_dss`, R15 `v_bus`. 전에는 R14가 `v_clamp` · `v_dss`, R15가 `v_bus` · `v_sw_transient`를 물었다). R03은 `i_coil`이 있으면 IF_AV 멤버를 계산할 수 있어 `pulse_test`를 묻지 않는다. 통과하지 못한 묶음은 TRR 멤버가 있으면 그 멤버로 알린다(판정 노드의 쇼트키 면제가 묶음에 닿게).
- 바꾼 파일: `backend/judge/verdict.py` · `conditions.py` · `sheet_conditions.py` · `rules/roles.yaml`, `backend/multi_agent/agents/judge.py`, `backend/services/llm.py`(설명 한 줄), `docs/specs/judge-agent.md`(EC-06, 규칙 형식 줄 3개), 시험 `tests/judge/test_judge_verdict.py` · `test_judge_conditions.py` · `test_judge_rules_file.py` · `tests/multi_agent/test_judge.py`, 이 파일
- 실행한 명령과 결과: 커밋마다 `uv run --frozen pytest -q` 전체 통과 뒤 커밋. 시작 640 passed, 43 skipped → 마지막 658 passed, 43 skipped. 실제 LLM · MCP · DB 호출 없음(가짜 사양 표 행). 동결 평가셋 변경 없음(`git diff`).
- 확인 못 한 것: 실제 사양 표 행으로 바뀐 역할(R03 · R06 · R10 · R14 · R15)과 같은 조건 비교를 돌려 보지 않았다. R12 "IC에 과전압 보호 문턱이 있으면 그 값"은 지금 형식(필수 `v_out` + 조건부 `v_ovp`)이 `v_out`을 모르고 `v_ovp`만 알 때만 더 엄격해서 바꾸지 않았다(정운 확인 필요). 사양 동등 판정(`_not_worse`)의 같은 조건 비교는 한쪽 방향이고 표 기본 조건을 한쪽에만 채운다(이번에 바꾸지 않음). 기본값으로 판정한 조건의 답 표 "기준" 칸은 기본값 식이 아니라 원래 기준식 이름을 보여 준다(불확실 메모에는 기본값이라고 적힘).
- 다음 할 일: 정운 R12 확인 → 연습 문제 정답 다시 달기(Task 10 Step 1) → 옮기기 → 사전 등록 · 첫 측정(Task 11).

## 2026-11-06 판정 에이전트 구현(계획 Task 1~9, Task 10 채점기)
- 한 일: `docs/specs/judge-agent-plan.md`를 Task마다 시험 먼저 쓰고 커밋 하나씩으로 실행했다. 시험 조건 읽기(`sheet_conditions.py`), 규칙 읽기 · 기준식 계산(`conditions.py`), 판정 5종 · 찾기 조건 · 정렬(`verdict.py`), 역할 23개 규칙(`rules/roles.yaml`, 원본 3개 파일에서 옮김), MCP 사양 표 도구 호출과 큰 넷의 대상 핀, 판정 읽기 노드 · 프롬프트(`judge_read`, Haiku), 판정 노드(인터럽트 1번), 그래프 연결 · 코드 틀 답, 평가 실행기의 판정 켜기 · 인터럽트 빈 값 재개, 연습 문제 채점기(`run_judge_dev.py`). Task 10의 연습 문제 · 회로 옮기기와 Task 11 측정은 하지 않았다(정답을 새 규칙으로 다시 단 뒤).
- 계획과 다르게 한 것: ① `verdict._check`가 기본값 기준식(default)으로 바꿀 때 그 식의 빠진 값을 알리지 않아 고쳤다(R17 처짐 기본값이 `v_peak` · `c_hold`를 씀, 따로 커밋) ② 판정 노드의 숫자 확인 글에서 역할 목록을 뺐다(R10 "3.3V" 같은 알아보는 법 글의 숫자가 질문의 숫자로 통과했다) ③ 입력 읽기가 새 턴마다 `judgement` · `judge_read`도 비운다(같은 thread 다음 질문에 앞 판정 틀이 나가지 않게) ④ `supervisor.md`의 `judge` 설명에 candidate_find를 더했다(규칙 1번과 어긋남) ⑤ R01 주의 글이 YAML 흐름 목록의 쉼표로 둘로 쪼개져 따옴표로 묶었다 ⑥ R03 `[왜]` 주석의 "펄스 조건이 없으면 평균 전류로 본다"는 코드 동작과 달라 `[주의]`로 고쳤다 ⑦ `test_make_app_multi…`의 가짜 MCP에 `part_specs` · `find_parts`를 더했다 ⑧ Task 10 커밋 메시지에서 "연습 문제와 회로 10개를 넣고"를 뺐다.
- 규칙 형식에 그대로 못 옮긴 것(더 엄격한 쪽이나 주의로 둠): R03 "펄스가 다르면 IF_AV ≥ 코일 전류"(펄스를 모르면 확인 안 됨), R04 VZ "허용 오차 안에서 같음"(원래 최대 VZ와 같은지로만, IZT 2배 · 기준 용도 오차는 주의), R06 "PPPM 또는 IPP"(둘 다 필수), R10 "CJ 또는 TRR"(둘 다), R14 "클램프 전압을 모르면 VDSS × 1.1"(늘 필수), R15 "과도 전압을 주면 그 값, 없으면 버스 × 1.25"(둘 다), R09 VF 하한(주의), R11 · R22 (1 − D) 완화(주의), R07 퓨즈 협조(주의). 저항 값(직렬 · 풀업 · 부트)은 kΩ 환산이 안 돼 회로 값으로 두지 않고 결과 전류(`i_z` · `i_fault` · `i_boot_peak`)로 받는다.
- 바꾼 파일: `backend/judge/`(`__init__.py` · `sheet_conditions.py` · `conditions.py` · `verdict.py` · `rules/roles.yaml` 새 파일, `JUDGE.md`), `backend/multi_agent/agents/judge.py`(새), `backend/prompts/judge_read.md`(새), `evals/runners/run_judge_dev.py`(새), `backend/multi_agent/`(`build.py` · `state.py` · `messages.py` · `supervisor.py` · `agents/writer.py` · `agents/verifier.py` · `MULTI_AGENT.md`), `backend/prompts/supervisor.md` · `PROMPTS.md`, `backend/services/langfuse_prompts.py`, `backend/graph/mcp_retriever.py` · `nodes.py`, `backend/rag/spec_lookup.py`, `backend/mcp_skill/mcp_server/server.py`, `evals/runners/run_graph.py` · `RUNNERS.md`, 시험(`tests/judge/` 4개 새 파일, `tests/multi_agent/test_judge.py` 새 파일, `tests/evals/test_run_judge_dev.py` 새 파일, 그 밖 수정 6개)과 폴더 설명, `pyproject.toml` · `uv.lock`(`pyyaml`), `SOJAFIT.md`, `SPEC.md`(5절 · 8.3), 이 파일
- 실행한 명령과 결과: Task마다 `uv run --frozen pytest -q` 전체 통과 뒤 커밋. 마지막 전체 640 passed, 43 skipped. `TEST_DATABASE_URL`(로컬 DB)을 켜면 660 passed, 21 skipped, 2 failed이고 실패 2개는 `tests/rag/test_rag_storage.py` halfvec(이번에 바꾼 파일을 쓰지 않음, 11-05 기록과 같은 실패). `test_rag_spec_lookup.py`는 DB로 통과. 동결 평가셋 3개 파일 변경 없음(`git diff`). 실제 LLM · MCP 서버 · Langfuse 호출 없음(가짜 LLM · 가짜 사양 표).
- 확인 못 한 것: `roles.yaml`이 원본과 맞는지(판정자 하정운 대조 필요). 실제 사양 표 행으로 23개 역할을 돌려 보지 않았다. `orig.<코드>`는 원래 부품의 첫 행 값이라 VF · IR처럼 시험 조건이 여럿인 코드는 다른 조건끼리 비교될 수 있다. 사용 온도(`temp`)가 25°C가 아니거나 TA와 TJ가 섞이면 정격 행이 모두 확인 안 됨이 된다. 원래 품번에 주문 코드가 붙으면(`1N4148 A0G`) 원래 부품 행을 기본 품번으로 다시 찾지 않는다. 읽기 프롬프트 · Supervisor 새 버전은 Langfuse에 등록하지 않았다.
- 다음 할 일: 정운 `roles.yaml` 대조 → Langfuse에 `judge_read` v1 · `supervisor` 새 버전 등록(승인) → 연습 문제 정답 다시 달기(Task 10 Step 1) → 옮기기 → 사전 등록 · 첫 측정(Task 11).

## 2026-11-06 판정 에이전트 · 대체품 찾기 작업서
- 한 일: 11-05~11-06 설계 대화에서 정한 것을 `docs/specs/judge-agent.md`로 남겼다. 판정과 대체품 찾기를 한 흐름으로 두고(읽기 LLM 1번 → 숫자 확인 → 규칙 → 인터럽트 → 사양 표 조회 → 코드 비교 · 판정), 역할 23개 · 조건 세 층 · 시험 조건이 같은 값끼리만 비교 · "확인 안 됨"이어도 찾은 것은 보여 주기 · 찾기 후보 정렬(판정 → 기판 수정 불필요 → 품번, 최대 5개)을 적었다. SPEC 5절 규칙 파일 형식과 8.3을 작업서로 잇고, `docs/specs/SPECS.md` 파일 목록에 한 줄을 넣었다.
- 바꾼 파일: `docs/specs/judge-agent.md`(새 파일), `docs/specs/SPECS.md`, `SPEC.md`(5절 · 8.3), 이 파일
- 확인: 작업서에 적은 저장소 경로(`backend/multi_agent/build.py` · `supervisor.py` · `agents/writer.py`, `backend/graph/nodes.py` `MAX_NET_NODES = 8`, `backend/prompts/supervisor.md`)를 코드와 대조했다. #38 과잉 거절 판정 8 · 찾기 8은 `evals/guides/preregister.md` #38 결과 줄과 대조했다.
- 확인 못 한 것: 성공 기준 숫자(역할 정답률 80%, 판정 일치율 70%, v2 과잉 거절 8건 이하)는 측정 전 목표값이다. 규칙 원본은 저장소 밖 `전자_데이터시트/`에 있고 아직 `roles.yaml`로 옮기지 않았다.
- 이어서 한 일: 정운 검토 뒤 구현 계획 `docs/specs/judge-agent-plan.md`(Task 11개, 테스트 우선, 커밋 단위)를 썼다. 쓰기 전에 LangGraph 1.2.18 인터럽트를 작은 그래프로 돌려 봤다: 멈추면 `__interrupt__`가 돌아오고, 재개하면 멈춘 노드만 다시 돌고 앞 노드(읽기)는 다시 돌지 않는다. 다만 빈 dict(`{}`)로 재개하면 재개로 보지 않고 다시 멈춰서, 재개 값을 `{"answers": {...}}`로 정하고 작업서 How도 고쳤다. `to_si(10, '')`가 `None`인 것, `spec_lookup._COLUMNS`가 이미 분류를 읽지만 결과에 빠진 것도 확인해 계획에 넣었다.
- 다음 할 일: 정운 계획 확인 → Task 1부터 실행.

## 2026-11-05 노드별 모델 결정 기록(ADR 0014)
- 한 일: Supervisor를 Sonnet으로 바꾼 이유를 ADR 0014로 남겼다. 근거는 #33(오세창, Supervisor 후보 6종 3회)에서 Haiku의 질문 종류 정답 21~23/35 · 형식 유효 46~50/70, Luna는 채점 모델과 같아져 제외(조장 판단), #38 Sonnet 결과(질문 종류 일치 32/32, 비용 #37의 약 43배)다. ADR 0010에 "일부 바뀜", ADR 목록, SPEC 2절 LLM 줄, AGENTS 기술 스택, README 기술 표의 "Haiku 하나"를 노드별 모델로 고쳤다.
- 바꾼 파일: `docs/adr/0014-supervisor는-sonnet-서브에이전트는-haiku-채점은-luna.md`(새 파일), `docs/adr/0010-*.md`, `docs/adr/ADR.md`, `SPEC.md`, `AGENTS.md`, `README.md`, 이 파일
- 확인: #33 숫자는 `evals/results/supervisor/2026-11-05-stage3-comparison-v1/stage3_summary.json`에서 직접 읽었다. `tests/repo` 5 passed.
- 확인 못 한 것: Sonnet과 Luna를 Supervisor 자리에서 같은 조건으로 비교하지 않았다.

## 2026-11-05 부품 사양 표 운영 DB(Supabase) 적용
- 한 일: 정운 승인으로 운영 DB에 `db/011_part_specifications.sql`을 적용하고 사양 표를 적재했다. 적용 전 읽기 전용으로 보니 다른 public 표 10개는 모두 RLS가 켜져 있고 정책이 0개인데, Supabase 기본 권한(`pg_default_acl`)이 새 표를 anon·authenticated에 모든 권한으로 열어 둔다. 그래서 011 끝에 `ENABLE ROW LEVEL SECURITY`를 더해 적용했다(서버는 표 주인 `postgres`로 접속해 영향 없음). 로컬 볼륨에도 같은 RLS를 켰다.
- 바꾼 파일: `db/011_part_specifications.sql`(RLS 한 줄), `db/DB.md`(적용 기록), `tests/rag/test_rag_spec_lookup.py`(RLS 확인 한 줄), 이 파일
- 실행한 명령과 결과: 접속 주소는 `.env`에서 읽어 화면에 찍지 않고 넘겼다. 011 적용 → 표 RLS 켜짐 · 인덱스 4개 · 0행. `specs.load('../corpus/tsc/specs', <운영 주소>)` → 문서 1,360(빠진 문서 0) · 90,961행(숫자 77,340 + PACKAGE 13,621) · 품번 9,589개 · 6.44초 → `ANALYZE`. 표 22.7 MB, DB 전체 207.2 → 230.0 MB. 맥에서 운영 DB로 조회: `part_specs('1N5817')` 10행 22 ms, VRRM ≥ 40 · IF_AV ≥ 1 50건(상한) 387 ms, VRRM ≤ 20 · 패키지 SMA 14건 103 ms(네트워크 왕복 포함). 시험: 로컬 DB `TEST_DATABASE_URL`로 `test_rag_spec_lookup.py` 11 passed, 맥 전체 567 passed · 43 skipped.
- 이어서 확인한 것:
  - 공개 API 차단: 운영 DB에서 공개 API가 쓰는 역할로 바꿔(`SET LOCAL ROLE anon` · `authenticated`, 끝나면 되돌림) 시험했다. 두 역할 모두 읽기 0행(비교: `source_documents`도 0행), 고치기 · 지우기 영향 0행, 넣기는 `new row violates row-level security policy`로 거부됐다. 시험 뒤 행 수 90,961 그대로, 시험 행 0.
  - MCP 도구: 실제 stdio MCP 서버(`backend.mcp_skill.mcp_server.server`)를 띄워 운영 DB로 불렀다. 도구 목록에 두 도구가 있고, `get_part_specs('1n5817')`(소문자) 4행 · VRRM 20 V · IF_AV 1 A, 제너 VZ 3.42~3.78 V 15건(로컬과 같음), VRRM ≥ 40 · IF_AV ≥ 1 · 패키지 SMA 50건(상한), SMAF 36건(로컬과 같음), 없는 품번 0행, `PACKAGE` 숫자 조건은 오류로 거절. 한 번에 0.4~0.6초.
  - 고친 것: `find_parts_by_specs` 도구 설명이 75bf517 뒤에도 "패키지 이름 일부"로 남아 있어 "이름과 같아야 함"으로 고쳤다(`tests/rag/RAG.md` 시험 설명도 함께).
- 확인 못 한 것: anon 키로 HTTP 요청을 보내 보지는 않았다(`.env`에 anon 키가 없고, 있는 서비스 키는 RLS를 우회해 시험에 맞지 않음). 공개 API가 DB에서 쓰는 역할로 같은 동작을 확인했다. 배포된 서비스 코드는 아직 이 표를 읽지 않는다(코드가 로컬 브랜치에만 있음).
- 다음 할 일: 판정 에이전트(`backend/judge/` + 조회 도구 연결).

## 2026-11-05 부품 사양 표 DB 적재와 조회 도구(로컬 DB)
- 한 일: 사양 표를 DB 표로 만들고(`db/011_part_specifications.sql`, 정의서 5.7 + `part_number` 글자 칸 · `chunk_index` · `category` · 코드 `PACKAGE`, 문서 FK는 CASCADE), 적재 명령 `specs.py load`(접속 주소는 `--dsn`으로만 받고 `DATABASE_URL`은 읽지 않음, 한 번 실행을 한 트랜잭션으로 문서 단위 지우고 COPY), 조회 모듈 `backend/rag/spec_lookup.py`(`part_specs` · `find_candidates`)와 MCP 도구 `get_part_specs` · `find_parts_by_specs`를 넣었다. 운영 DB에는 넣지 않았다.
- 바꾼 파일: `db/011_part_specifications.sql`, `db/DB.md`, `db/schema/table-definition.md`, `backend/rag/pipeline/specs.py`, `backend/rag/spec_lookup.py`, `backend/mcp_skill/mcp_server/server.py`, 시험 `tests/rag/test_rag_spec_lookup.py` · `tests/mcp_skill/test_mcp_server.py`, `SPEC.md` 8.7, `SOJAFIT.md` 트리, `RAG.md` · `MCP_SKILL.md` 폴더 설명, 이 파일
- 실행한 명령과 결과: 맥 `uv run --frozen pytest -q` 566 passed, 43 skipped. 로컬 DB 컨테이너에서 `TEST_DATABASE_URL` DB 시험 143개 통과. 로컬 compose DB에 SQL 두 번 적용(두 번째 변경 없음), 적재 두 번(문서 1,360 모두 연결, 91,020행 = 숫자 77,340 + PACKAGE 13,680, 1.1 · 1.2초, 코드별 행 수 같음). 조회: `part_specs('1N5819')` 10행 0.5~6.9 ms, VRRM ≥ 40 · IF_AV ≥ 1 · 패키지 SMA 포함 564개 20~48 ms, 제너 VZ 3.42~3.78 V 15개(BZT52C3V6 포함) 14~18 ms. 표 크기 22 MB(데이터 18 + 인덱스 4.2). 운영 DB는 읽기 전용 조회로 207.2 MB라 넣으면 약 229 MB(무료 500 MB, ADR 0005 경보선 400 MB).
- 확인 못 한 것: MCP 도구를 실제 stdio 클라이언트로 부르지 않았다. 패키지 이름에 일반 낱말 "SMALL"이 59건 잘못 들어갔고, 패키지 거르기가 부분 일치라 "SMA"가 SMAF까지 잡는다(564개 중 36개). `db/manual/004` 초안에도 `part_specifications`가 있어 겹치고, 초안 `requirement_checks`의 RESTRICT 참조와 다시 적재가 부딪힐 수 있다(정의서 1절 주의). 다시 적재하면 지운 행 때문에 정리 전까지 크기가 약 22 MB 더 는다.
- 이어서 한 일: 패키지 이름 두 가지를 고쳤다. ① 글자로만 된 패키지 이름(SMA · SMB · ABS 등)은 대소문자를 구분해 "Case: SOD-123 small outline"의 small이 SMA로 잡히지 않게 함(PACKAGE 13,680 → 13,621행, 59건 제거) ② 패키지 거르기를 부분 일치에서 이름 같음(대소문자 · 하이픈 무시)으로 바꿈(SMA 조건 564 → 528개, SMAF 36개는 따로). 맥 567 passed, 컨테이너 DB 시험은 `test_rag_storage.py` halfvec 2개만 실패하는데 변경 전 코드에서도 같게 실패한다(로컬 DB 상태 관련, 고치지 않음). 로컬 DB에 다시 적재 90,961행.
- 다음 할 일: 운영 DB 적용(정운 승인) → 판정 에이전트.

## 2026-11-05 부품 사양 표 2차 규칙 수정(새 표본 seed 1 대조 결과)
- 한 일: 처음 보는 50개 품번(seed 1) PDF 대조에서 310줄 중 O 303 · X 7이 나왔고, X 중 IF_AV 4줄(반복 첨두 IFRM, 비반복 서지 IF,MAX를 평균 전류로 분류)이 ADR 0013 기준(거르는 값 틀린 값 0)을 넘지 못해 규칙을 고쳤다. IF_AV는 평균 · 연속 · 정격 순방향 전류만 받고 peak · surge · repetitive · IFRM · IFM · IF,MAX · IFSM 행은 IF_AV가 아님(비반복 서지는 펄스 조건과 함께 IFSM). 그 밖에 반복 조건으로 품번 묶음 구간 찾기, 합쳐진 조건 칸 나누기, 품번 열 병합 칸 펼치기, 붙은 열 이름 칸 나누기, 머리로 빨려 든 첫 행 값 떼기, TVS 하위 머리 행의 자리와 파형 조건, 값 칸에 붙은 기호 떼기, 시험 전류 칸을 VZ · VBR 조건으로.
- 바꾼 파일: `backend/rag/pipeline/specs.py`, `tests/rag/test_rag_specs.py`(새 시험 10개), `tests/rag/RAG.md`, 이 파일
- 실행한 명령과 결과: `uv run --frozen pytest -q` 535 passed, 32 skipped(세 번). 다시 `build`: 사양 행 75,840 → 77,340, 검토는 같은 조건 다른 값 508 → 320 · 파서가 밀어 놓은 표 4,133 → 3,213 · 자리 불명 214 → 133. IF_AV 4,138행 중 peak · surge · repetitive 계열 이름 · 기호 0, 100 A 초과 0. 핵심 값 완비율 TVS 46 → 53% · 제너 84 → 87% · 스위칭 78 → 82%. 회귀(seed 0 · seed 1): 이전 O 568개 모두 그대로, X 7줄 모두 PDF 값으로 바뀌거나 사라짐, 기대값 38개 중 4항목(SFA1005G · 1M130Z · SFF1002G는 파서가 표를 망가뜨려 검토, TSS54U VF는 청크 안 값 순서가 PDF와 반대라 검토)만 남음.
- 확인 못 한 것: 두 표본 밖의 새 값은 PDF로 보지 않았다. 세 번째 표본(seed 2, 50개, 핵심 값 모두 있음 43개, 값 304줄) 대조표를 만들었고 대조 전이다. TSS54U처럼 값 순서가 뒤집힌 청크를 어떻게 다룰지는 정하지 않았다.
- 이어서 한 일: 세 번째 표본(seed 2) 50개를 PDF 쪽 그림과 대조했다(판정 하정운). 값 304줄 중 O 303 · X 1(ES3HB VF, 옆 묶음 행 값), 거르는 값(VRRM · VR · IF_AV · VZ · VRWM) 오류 0으로 ADR 0013 기준을 넘었다. 빠진 값 14줄 중 12줄은 PDF에 있었다(TVS 깨진 표 · 양방향 SMAJ14CH, 묶음 행 VF, 조건 다른 VF를 충돌로 버림).
- 다음 할 일: DB 적재(로컬 먼저) → 조회 도구. 남은 비거르는 값 문제(VF 묶음 행 · 조건 글자 섞임, SMAJ 양방향)는 따로 고친다.

## 2026-11-05 부품 사양 표 규칙 수정(PDF 대조 50개에서 나온 8가지)
- 한 일: 표본 50개 PDF 대조에서 나온 놓친 값 · 오류를 일반 규칙으로 고쳤다. ① 문서가 "characteristics apply in both directions"를 밝힐 때만 양방향(C · CA · CH · CAH) 품번에 단방향 행 값을 붙이고, `Bi` 칸 품번을 그 행 품번으로 읽음 ② 합쳐진 조건 칸을 되살려 조건이 다른 값을 충돌로 보지 않음(공기 · 접촉 방전 포함) ③ 열 이름 끝의 품번 · `GBPC15, 25, 35 / 005` 같은 계열 열을 품번 열로 읽음 ④ 제너 VZ 최소 · 대표 · 최대 자리를 표 머리에서 되찾고 순서가 어긋나면 검토로 ⑤ 패키지별 칸은 그 패키지 품번에만 ⑥ 이름 없는 이어지는 행이 위 행 파라미터를 이어받고 `SFA1001G - SFA1004G` 범위를 안쪽 품번으로만 펼침 ⑦ 칸 안의 `IF = 50mA` 같은 조건을 살림 ⑧ IFSM을 펄스 폭(8.3ms · 1.0ms)마다 조건과 함께 따로 넣음(제외어가 IFSM 행까지 지우던 버그 수정).
- 바꾼 파일: `backend/rag/pipeline/specs.py`(907줄), `tests/rag/test_rag_specs.py`(새 시험 11개), `backend/rag/RAG.md`, `tests/rag/RAG.md`, 이 파일
- 실행한 명령과 결과: `uv run --frozen pytest -q` 526 passed, 32 skipped(세 번 돌려 모두 통과, 작업 중 한 번 나온 1 failed는 다시 나오지 않음). 다시 `build`: 사양 행 67,728 → 75,840, 핵심 값 모두 가진 비율 TVS 27 → 46% · 제너 74 → 84% · 표준 정류 94 → 100% · 초고속 78 → 100% 등. 회귀 확인(PDF 판정 jsonl과 대조): 이전 O 265개 그대로, X 4줄 모두 해결, 빠진 값 · IFSM 46개 기대값 중 42개가 PDF 값과 같고 4개(SFA1005G VF, 1M130Z VZ 3자리)는 파서가 표를 망가뜨려 틀린 값 대신 검토 목록으로 감.
- 확인 못 한 것: 새로 들어간 값 약 8,000행 중 PDF로 본 것은 표본 50개분뿐이다(같은 표본으로 고쳤으므로 낙관적이다). 새 표본 대조표(seed 1, 50개)를 만들었고 아직 대조하지 않았다. TVS는 C형 품번 848개가 여전히 비어 있다(옮길 단방향 행이 파서에 깨짐).
- 다음 할 일: seed 1 대조표를 PDF와 대조 → DB 적재 마이그레이션 → 판정 에이전트.

## 2026-11-05 노드별 모델 변경, 단일 #37, lab(Anthropic 직통), 멀티 첫 측정 #38
- 한 일: 정운 결정으로 노드별 모델을 Supervisor Sonnet · 서브에이전트 노드 Haiku · 채점 Luna로 바꾸고(f385ff7) Langfuse `supervisor` v4를 등록했다. 멀티 측정 전에 `not_found`를 단일과 같은 뜻으로 맞췄다(14b724a). 사전 등록 #37 · #38을 측정 전에 적었다. 팀 레포는 그대로 두고 로컬 복제본(`../lab/repo`, 브랜치 `lab-anthropic`, 푸시 막음)과 Docker 컨테이너 `sojafit-lab`을 만들어, 정운 개인 Anthropic 키로 Supervisor(Sonnet)만 Anthropic API에 직접 부르게 했다(lab 커밋 e86b1e6, `langchain-anthropic` 1.7.7, 구조화 출력은 `output_config.format`).
- 바꾼 파일: `backend/services/langfuse_prompts.py` · `llm.py`, `backend/prompts/PROMPTS.md`, `evals/runners/run_graph.py`, 시험 4개, `evals/guides/preregister.md`(#37 · #38), 결과 `evals/results/graph/graph_dataset_v2_2026-11-05-2054.json` · `multi_dataset_v2_2026-11-05-1226.json`, 이 파일
- 실행한 명령과 결과: #37 단일(채점 Luna) 70문항 실패 0, cited_gold 13 · over_refusal 22 · correct_refusal 35, p50 8.6초, 0.0426달러, #35와 같은 문항 69/70. #38 멀티(lab 컨테이너) 70문항 중 67 끝남 · 실패 3(Supervisor `brief` 300자 초과로 형식 검사 3번 실패), cited_gold 10 · over_refusal 22 · correct_refusal 35, 질문 종류 32/32, 판단 중앙값 3, p50 18.9초, 약 1.82달러(Sonnet 1.77). 두 측정 모두 사전 등록 기대 범위 안. Langfuse는 Sonnet 직통 호출 하나를 `ChatAnthropic` · `anthropic.messages.create` 두 생성으로 기록해 비용이 두 배로 보여 `ChatAnthropic`만 셌다. 서브에이전트가 시험을 먼저 돌리다 lab `.env`의 OpenRouter 키로 Sonnet을 1번 실제 호출했다(1센트 미만 추정).
- 확인 못 한 것: 실패 3건 중 원인을 Langfuse에서 본 것은 1건이다(나머지 2건은 같은 입력으로 3번 부른 것까지만 확인). 답이 한국어인지 보지 않았다. 각 측정은 1회다.
- 다음 할 일: Supervisor `brief` 길이 처리(제한을 늘리거나 프롬프트) 결정, 판정 에이전트(사양 표 DB 적재 뒤), 사람 승인 · 체크포인트, 중간 점검 자료.

## 2026-11-05 부품 사양 표 변환기(ADR 0013)와 단위 환산
- 한 일: 데이터시트 표 행 청크를 규칙으로 부품 사양 표(`part_specifications` 모양 + 청크 번호)로 바꾸는 `backend/rag/pipeline/specs.py`(`build` · `sample`)와 단위 환산 `backend/rag/units.py`(`to_si`)를 넣었다. 13종 전부, 항목 코드 17종(A-07 10종 + VR + VRWM · VBR · VC · IPP · PPPM · VESD). 애매한 값은 표에 넣지 않고 사유와 함께 검토 목록에 남긴다(계열 범위 · 여러 값, 같은 조건의 다른 값, 모르는 단위, 원문에 없는 숫자, 음수, 파서가 밀어 놓은 표, 대상 품번을 모르는 행, 최소 · 대표 · 최대 표시가 없는 항복 · 제너 전압). 11-03 원형(저장소 밖 `build.py`)의 규칙과 대조 오류 수정을 옮겼고, 평가셋 정답을 쓰던 후보 거르기는 옮기지 않았다(시험 세트 누수).
- 바꾼 파일: `backend/rag/units.py` · `backend/rag/pipeline/specs.py`(새 파일), `tests/rag/test_rag_units.py` · `tests/rag/test_rag_specs.py`(새 파일), `SOJAFIT.md` 트리, `backend/rag/RAG.md`, `tests/rag/RAG.md`, 이 파일
- 실행한 명령과 결과: `uv run --frozen pytest -q` 514 passed, 32 skipped(새 시험 41개, 구현 전 실패 확인). 로컬 청크 전체에 `build`: 문서 1,360 · 품번 9,589 · 사양 행 67,728. 검토 목록은 파서가 밀어 놓은 표 3,950 · 계열 범위 851 · 같은 조건 다른 값 800 · 자리 불명 795 · 모르는 단위 283 · 대상 품번 불명 56 · 음수 4건, 원문에 없는 숫자 0건. 분류별로 핵심 값을 모두 가진 품번 비율은 SiC 쇼트키 100% · 고속 회복 98% · 표준 정류 94% · 쇼트키 정류 79% · 초고속 78% · 제너 74% · 브리지 72% · 고효율 69% · 쇼트키 67% · 스위칭 66% · ESD 65% · 수퍼 고속 60% · TVS 27%. 결과는 저장소 밖 `corpus/tsc/specs/`, 사람 대조표(품번 50개, 값 269줄, 핵심 값 모두 있는 품번 39개)는 저장소 밖 `전자_데이터시트/사양표-대조표-2026-11-05.md`.
- 확인 못 한 것: 표본 대조 전이라 값이 맞는지는 모른다(무작위 약 65행을 원문과 비교해 찾은 오류만 고쳤다). TVS 양방향(C · CA) 품번 1,590개는 자기 행이 없어 비어 있고, 제너는 최소 · 대표 · 최대 표시가 없는 표 때문에 195개 품번의 VZ가 비어 있다. DB 적재(`part_specifications` 표)와 판정 코드는 아직 없다. 코드와 시험이 약 1,010줄이라 PR로 올릴 때 400줄 안팎 규칙을 넘는다.
- 이어서 한 일(11-05 밤): 대조표 50개를 PDF 쪽 화면과 대조해 O/X를 채웠다(저장소 밖 대조표, 판정 하정운). 값 269줄 중 O 265 · X 4 · ? 0, 거르는 값(VRRM · VR · IF_AV · VZ · VRWM) X 0. X 4줄은 모두 VF(형제 묶음 행 1, 다른 패키지 행 2, 시험 조건 누락 1). 빠진 값 21줄은 모두 PDF에 있었다: 양방향 TVS(문서가 양방향 적용을 밝힘), 조건이 다른 값의 거짓 충돌, 계열 범위만 보고 품번 열 정격표를 안 봄, 제너 표 머리 누락, 묶음 · 패키지 행. IFSM은 8.3ms · 1.0ms 값이 품번마다 섞여 있다. ADR 0013에 "일부 바뀜"(표본 대조 판정자)을 적었다.
- 다음 할 일: 놓친 값 규칙과 VF 오류 고치기(정운 결정 뒤) → DB 적재 마이그레이션 → 판정 에이전트.

## 2026-11-05 origin/main(PR #55 · #56) 병합과 사전 등록 번호 겹침 정리
- 한 일: `origin/main`(PR #55 수퍼바이저 3차 · #56 Google 관리자 로그인)을 `jeongun`에 병합했다. 충돌 3파일은 `backend/BACKEND.md`(main.py · auth.py 설명은 main, `multi_agent/` 줄은 jeongun), `evals/runners/RUNNERS.md`(두 줄 모두), `evals/guides/preregister.md`(main의 #33 다음에 jeongun의 #33~#35)로 풀었다. jeongun의 사전 등록 #33(채점기 기준선)이 main의 #33(수퍼바이저 3차, 오세창)과 겹쳐 #36으로 바꿨다(사전 등록 본문에 번호 변경 줄, 결과 · 입력 JSON의 note 문구, 코드 주석, 폴더 설명, 트리).
- 바꾼 파일: 병합 커밋의 충돌 3파일, 번호 변경 11파일(`preregister.md` · `SOJAFIT.md` · `evals/EVALS.md` · `INPUTS.md` · `RUNNERS.md` · `eval_grader.py` · `grader_cases_v2.json` · `grader_baseline_2026-11-05.json` · `test_eval_grader.py` · `tests/evals/EVALS.md` · 이 파일)
- 실행한 명령과 결과: 병합 뒤 `uv sync --frozen`(authlib · joserfc 추가), `uv run --frozen pytest -q` 472 passed, 32 skipped. 번호 변경 뒤에도 같다. `git diff --check` 통과.
- 확인 못 한 것: main에서 `/api/ask`가 빠져(커밋 2b2769f) 질문 API가 없다. CI는 푸시 전이라 돌지 않았다.
- 다음 할 일: 푸시와 PR 나누기, `--multi` 시험 2문항 실제 실행.

## 2026-11-05 Supervisor에 일상 대화(chat) · 다이오드 외 부품(other_part) 추가
- 한 일: 질문 종류에 `chat` · `other_part`를 더하고 결정서에 `reply`(한국어 300자 이하)를 넣었다. 일상 대화는 Supervisor가 `reply`로 직접 답하고 `finish`로 끝낸다(작성 · 검색 없음, `finish_node`가 `reply`를 답으로 쓴다). `out_of_scope`는 서비스와 전혀 무관한 질문만 뜻하며 거절 문구를 "회로나 부품에 관한 질문을 해 주세요"로 부드럽게 바꿨다. 다이오드가 아닌 전자 부품은 `web`(켜져 있을 때) 아니면 `not_found` 거절. 프롬프트는 영어로 다시 써 Langfuse `supervisor` v3로 등록했다. 단일 그래프(D4)는 건드리지 않았다.
- 바꾼 파일: `backend/multi_agent/contracts.py` · `build.py` · `messages.py`, `backend/prompts/supervisor.md` · `PROMPTS.md`, 시험 `tests/multi_agent/test_contracts.py` · `test_supervisor.py` · `test_build.py`
- 실행한 명령과 결과: `uv run --frozen pytest -q` 460 passed, 27 skipped(새 시험 7개를 먼저 쓰고 실패를 확인). 실제 Luna 4문장: 인사 → chat 답, 날씨 → out_of_scope 거절, MOSFET → other_part 못 찾음 거절(웹 꺼짐), "다이오드가 뭐야?" → chat 일반 설명 + 데이터시트 근거 아님 표시. `load_development` 대조 통과.
- 확인 못 한 것: 4문장은 연결 확인일 뿐 정확도 근거가 아니다. 70문항에서 일상 대화 · 무관 질문 경계는 재지 않았다(평가셋에 일상 대화 문항이 없다). `web` 노드(TSC · Infineon 웹 조회)는 아직 연결하지 않았다.
- 다음 할 일: `web` 노드를 TSC · Infineon 웹 조회 도구와 연결, 일상 대화 · 경계 질문 소규모 개발용 문항 만들기.

## 2026-11-05 평가 실행기에 멀티 에이전트 실행(`--multi`)과 노드별 모델 기록
- 한 일: `evals/runners/run_graph.py`에 `--multi`를 더했다. 같은 평가셋 · 같은 5지표 채점으로 멀티 에이전트(`backend/multi_agent`)를 재며, MCP 서버(`check_corpus`)를 전 문항 동안 한 번 열어 사실 확인에 쓴다(`make_app`). 멀티 점수로 검색 횟수 `tries`(counters.searches) · Supervisor 판단 횟수 `hops` · 거절 사유 `refusal_code`를 더했다. session · run_name · 태그 · 결과 파일 이름 앞에 `multi`를 붙인다(`multi_<평가셋>_<날짜>.json`). 단일 · 멀티 모두 결과 파일 meta와 Langfuse 메타데이터에 노드별 모델 `node_models`를 남긴다. 플래그 없이 돌리면 이전과 같게 줄기 그래프를 잰다.
- 바꾼 파일: `evals/runners/run_graph.py`, `tests/evals/test_run_graph.py`, `evals/runners/RUNNERS.md`, `evals/EVALS.md`, `SOJAFIT.md`
- 실행한 명령과 결과: `uv run --frozen pytest -q` 453 passed, 27 skipped. 시험 6개를 먼저 써서 실패를 확인한 뒤 구현(멀티 점수, 결과 파일 이름, 노드별 모델 기록, 멀티 · 단일 그래프 조립과 MCP 열고 닫기, 모두 가짜).
- 확인 못 한 것: 실제 LLM · DB · MCP 서버로 `--multi`를 돌려 보지 않았다(유료 호출이라 하지 않음). 멀티 그래프가 실제 문항에서 상태 칸(`passed` · `docs` · `answer`)을 채점기(`score_answer`)가 읽는 모양으로 채우는지는 실행해 봐야 안다. 멀티 실행의 Langfuse 트레이스에는 노드(입력 읽기 · 사실 확인 · 판단 …) 단계가 CallbackHandler로 남지만 실제 모양은 확인하지 않았다.
- 다음 할 일: 시험 2문항으로 `--multi`를 실제로 돌려 트레이스와 점수를 확인 → 사전 등록(다음 빈 번호는 origin/main 확인 후) → 70문항 측정.

## 2026-11-05 노드별 모델 표와 호출 경로(시험까지)
- 한 일: 노드마다 쓸 모델을 `NODE_MODELS` 표 하나로 정하게 했다(시작값: `supervisor` · `grade` Luna, 나머지 Haiku, 최종 아님). `_chat_model(model)`이 모델별로 객체를 캐시하고 Luna에는 `temperature`를 보내지 않는다. `node_chat`이 그 노드의 모델로 부르고, Langfuse 등록 설정(`node_config`)과 검사도 노드별로 바꿨다. 환경변수 `LLM_MODEL`은 전 노드 덮어쓰기로 남겼다.
- 바꾼 파일: `backend/services/llm.py`, `backend/services/langfuse_prompts.py`, `backend/prompts/PROMPTS.md`, 시험 `tests/services/test_llm.py` · `tests/services/test_langfuse_prompts.py` · `tests/evals/test_skill_pair.py`(가짜 모델 함수가 모델 이름 인자를 받게)
- 실행한 명령과 결과: `uv run --frozen pytest -q` 447 passed, 27 skipped. 새 시험 6개를 먼저 쓰고 실패를 확인한 뒤 구현.
- 확인 못 한 것: 진짜 Luna 호출은 아직 하지 않았다(`temperature` 생략, 출력 상한 이름이 실제로 통하는지는 가짜 모델 시험만). Langfuse에는 아직 새 설정으로 등록하지 않았다(`grade` · `supervisor`가 새 버전이 된다). 기본값이 바뀌어 단일 그래프의 `grade`도 Luna를 쓰므로, 11-04/#35 기준선을 재현하려면 `LLM_MODEL=anthropic/claude-haiku-5.5`를 정해야 한다. 평가 실행기 결과 파일의 `model`은 아직 노드별로 적지 않는다.
- 다음 할 일: 진짜 Luna 한두 호출 확인 → Langfuse 새 설정 등록 → 평가 실행기에 노드별 모델 기록과 `--multi`.

## 2026-11-05 코퍼스 확인 MCP 도구(`check_corpus`)와 사실 확인 연결
- 한 일: 품번 · 개정 코드가 코퍼스에 있는지 있음/없음만 알려 주는 MCP 도구 `check_corpus`를 서버에 더했다(도구 1개로 합침, 판단하지 않음). 클라이언트 `StdioMcpRetriever.check`(같은 세션)와 응답 검증 `decode_check_result`, 사실 확인 노드용 `make_lookup(check)`를 만들었다. 코퍼스 목록은 `retrieve.corpus_known()`(품번 색인 + 문서 파일 이름의 개정 코드).
- 바꾼 파일: `backend/mcp_skill/mcp_server/server.py`, `backend/rag/retrieve.py`, `backend/graph/mcp_retriever.py`, `backend/multi_agent/facts.py`, 시험 3개(`tests/mcp_skill/test_mcp_server.py`, `tests/graph/test_graph_mcp_retriever.py`, `tests/multi_agent/test_facts_lookup.py`), `SPEC.md` 8.7, 폴더 설명과 트리
- 실행한 명령과 결과: `uv run --frozen pytest -q` 441 passed, 27 skipped. 실제 DB 읽기 전용 확인: 품번 9,589개 · 개정 코드 295개, `check_corpus`가 1N5819 · 1N4148 · H2104 · K2301은 있음, 1N4001 · TEST001 · Q2611은 없음으로 답했다(5.1초, 첫 호출은 색인 적재 포함). 실제 MCP(stdio) 서버를 띄워 질문 → 도구 호출 → Facts까지 확인했다.
- 확인 못 한 것: 질문의 TEST001처럼 회로 이름이 품번으로 뽑혀 "없음"으로 알려지는지(실제로 TEST001은 코퍼스에 없다고 답함)는 입력 읽기가 회로 이름을 빼는지 확인하지 않았다. 도구 장애 시 사실 확인은 예외를 그대로 올린다.
- 다음 할 일: 실제 DB에서 `corpus_known()` 한 번 확인 → Supervisor를 실제 LLM에 연결하고 평가 실행기에 `--multi` 추가.

## 2026-11-05 기존 프롬프트 4개 영어 번역(측정 전)
- 한 일: `route` · `grade` · `rewrite` · `generate` 프롬프트를 영어로 번역했다(규칙 내용 같음, 답변은 한국어, "문서로 확인 안 됨"은 그대로). 사전 등록 #35에 기대 범위를 먼저 적었다.
- 바꾼 파일: `backend/prompts/{route,grade,rewrite,generate}.md`, `backend/prompts/PROMPTS.md`, `evals/guides/preregister.md`, `tests/graph/test_graph_{route,grade,rewrite,generate}.py`(프롬프트 문구 확인을 영어로)
- 실행한 명령과 결과: `uv run --frozen pytest -q` 423 passed, 27 skipped. origin/main의 사전 등록 마지막 번호는 #32라 #35를 썼다.
- 이어서 한 일: 번역본을 Langfuse에 v2로 등록(`load_development` 대조 통과)하고 시험 2문항 뒤 v2 70문항을 측정했다. 결과 `evals/results/graph/graph_dataset_v2_2026-11-05.json`: cited_gold 12 · over_refusal 23 · correct_refusal 35(#31과 같음), 라우팅 32/35, p50 6.25초, 호출 215, 0.0463달러(#31 0.0519). #31과 지표가 다른 문항 2개(e02 · h02).
- 확인 못 한 것: 답변이 한국어인지 확인하지 않았다. 응답 변동 폭은 재지 않았다.
- 다음 할 일: 영어 프롬프트 기준으로 멀티 에이전트 구현을 이어 간다.

## 2026-11-05 Supervisor 프롬프트 영어 전환과 Langfuse 등록
- 한 일: `backend/prompts/supervisor.md`를 영어로 다시 썼고(`brief`도 영어), Supervisor 입력 글(`render`)과 에이전트 보고 요약 문구를 영어로 바꿨다. `NODES`에 `supervisor`를 더해 Langfuse에 v1로 등록했다.
- 바꾼 파일: `backend/prompts/supervisor.md`, `backend/prompts/PROMPTS.md`, `backend/multi_agent/supervisor.py`, `backend/multi_agent/agents/{search,writer,verifier}.py`, `backend/services/langfuse_prompts.py`, `backend/services/llm.py`(docstring), `tests/multi_agent/*`
- 실행한 명령과 결과: `uv run --frozen pytest -q` 423 passed, 27 skipped. 등록 후 `load_development`로 5개 프롬프트가 로컬과 같고 라벨이 development · latest임을 확인.
- 확인 못 한 것: 실제 LLM으로 Supervisor를 돌려 보지 않았다(가짜 LLM 시험만).
- 다음 할 일: 기존 프롬프트 4개 영어 번역을 사전 등록(다음 빈 번호는 origin/main 확인 후)하고 v2 70문항으로 단일 그래프 재측정.

## 2026-11-05 Langfuse 프롬프트 이름에서 폴더 빼기, Supervisor 입력에 질문 종류
- 한 일: Langfuse 프롬프트 등록 이름에서 `sojafit/` 폴더를 뺐다(`route` · `grade` · `rewrite` · `generate`, Skill은 `skill-diode-evidence`). 코드(`backend/services/langfuse_prompts.py`)와 시험(`tests/services/test_langfuse_prompts.py`), `SPEC.md` 5절 이름을 고치고 새 이름으로 등록했다(development · latest 라벨, 버전 1). 본문은 그대로라 동작은 안 바뀐다. 이전 `sojafit/` 폴더 프롬프트는 과거 트레이스가 가리켜서 지우지 않았고 정운이 화면에서 확인해 지우면 된다. 별개로 Supervisor 입력에 "질문 종류"가 빠져 두 번째 판단부터 판정 필요 여부를 못 읽던 것을 고쳤다.
- 바꾼 파일: `backend/services/langfuse_prompts.py`, `tests/services/test_langfuse_prompts.py`, `SPEC.md`, `backend/prompts/PROMPTS.md`, `backend/multi_agent/supervisor.py`, `tests/multi_agent/test_supervisor.py` · `test_build.py`, 이 파일
- 실행한 명령과 결과: `uv run --frozen pytest -q` 423 passed, 27 skipped. 새 이름으로 Langfuse에 등록한 뒤 `load_development`로 등록본과 로컬 소스를 대조해 일치를 확인했다.
- 확인 못 한 것: `sojafit/tool-use`는 이 코드가 등록하지 않아 이름을 바꾸지 않았다(문서에는 옛 이름이 기록으로 남아 있다). 이전 폴더 프롬프트를 가리키는 과거 트레이스는 그대로다.
- 다음 할 일: Supervisor 프롬프트를 영어로 다시 쓰고 등록 대상(`NODES`)에 더한다 → 기존 프롬프트 4개 영어 번역을 사전 등록한 개선 실험으로 측정한다.

## 2026-11-05 서브에이전트 3개와 조립(가짜 LLM 시험)
- 한 일: 시험 먼저 멀티 에이전트의 나머지 뼈대를 만들었다. 검색 에이전트(`agents/search.py`: 재작성 · 검색 · 채점 한 번, 통과 청크 번호와 실패 사유 3종(결과 없음 · 전부 탈락 · 검색 장애)을 보고, "결과 없음" 뒤 재시도에는 품번 필터를 풀어 다르게 시도), 작성 에이전트(`writer.py`: 단일 그래프의 `generate`를 감싸고 "문서로 확인 안 됨"이면 실패 보고), 검증 에이전트(`verifier.py`: 작성의 자체 검사를 믿지 않고 인용을 다시 계산, `enforce=False`면 기록만), 사실 확인(`facts.py`), 거절 문구(`messages.py`: 일상어, 내부 코드와 분리), 공용 메모장(`state.py`), 조립(`build.py`: 서브에이전트가 끝나면 반드시 Supervisor로 돌아오는 허브). Supervisor에 판정 스위치(`judge_enabled`)를 더했고 켜지지 않은 판정 · 웹은 선택지에서 빼며 `build_graph`가 켜려 하면 거부한다.
- 바꾼 파일: `backend/multi_agent/`(`state.py` · `facts.py` · `messages.py` · `build.py` · `supervisor.py` · `agents/` 3개), `backend/prompts/supervisor.md`(판정 줄 한 곳), `tests/multi_agent/`(`test_agents.py` · `test_build.py` · `test_supervisor.py`), `MULTI_AGENT.md` 두 개, `SOJAFIT.md`, 이 파일
- 실행한 명령과 결과: `uv run --frozen pytest -q` 422 passed, 27 skipped(멀티 에이전트 시험 39개). 조립 시험은 다섯 길(역할 직행, 검색 → 작성 → 검증 → 끝, 검색 두 번 실패 → 못 찾음 거절, 범위 밖 거절, 검증 실패 뒤 다시 쓰기 한 번 → 검증 실패 거절)을 가짜 LLM · 검색기로 끝까지 돌렸다.
- 확인 못 한 것: 실제 LLM · 검색 · DB로는 한 번도 안 돌렸다. `llm.node_chat`은 노드 이름이 정해져 있고 Langfuse 추적 때 프롬프트 등록이 필요해 `supervisor`를 더하는 작업이 남았다. 사실 확인의 코퍼스 목록을 가져오는 도구(MCP)가 없다. 채점이 아직 2갈래라 검색 보고의 `partial`은 안 나온다. 판정 · 웹 에이전트, 평가 실행기(`run_multi`), 사람 승인(interrupt)과 체크포인트는 없다.
- 다음 할 일: 정운이 프롬프트와 전체 구조를 한 번 점검한 뒤(측정 전), 사실 확인 도구 · Langfuse 연결 · 평가 실행기를 붙여 실제 70문항으로 Supervisor 결정과 5지표를 D4 기준선과 비교한다.

## 2026-11-05 Supervisor 노드(가짜 LLM 시험)
- 한 일: 시험 먼저 Supervisor를 만들었다. `backend/multi_agent/supervisor.py`는 질문 · 확인된 사실(`Facts`: 품번 · 개정판이 코퍼스에 있나) · 지금까지의 보고 · 한도 현황 · 고를 수 있는 노드를 글로 만들어 LLM에 주고 결정서(`Decision`)를 받는다(`decide`). 한도를 넘거나 꺼져 있는 웹으로 가려 하면 거절로 바꾸고(품번이 목록에 없었으면 `part_missing`, 아니면 `not_found`), 끝내는 길(`finish` · `refuse`)은 한도로 막지 않는다. 판단 횟수 세기(`count_decision` · `count_report`). 프롬프트 `backend/prompts/supervisor.md` v1. 결정서에 질문 종류(`question_type`)를 더했다.
- 바꾼 파일: `backend/multi_agent/supervisor.py` · `contracts.py`, `backend/prompts/supervisor.md` · `PROMPTS.md`, `tests/multi_agent/test_supervisor.py` · `test_contracts.py`, `MULTI_AGENT.md` 두 개, `SOJAFIT.md` 트리, 이 파일
- 실행한 명령과 결과: `uv run --frozen pytest -q` 404 passed, 27 skipped(멀티 에이전트 시험 21개 포함).
- 확인 못 한 것: LLM이 실제로 좋은 결정을 내리는지는 안 쟀다(가짜 LLM 시험은 글 만들기와 한도 처리만 본다). `llm.node_chat`은 노드 이름이 route · grade · rewrite · generate로 정해져 있고 Langfuse 추적이 켜져 있으면 프롬프트 등록이 필요해서, 실제 연결 때 `supervisor`를 더하는 작업이 남았다. 사실 조회(`Facts`를 만드는 도구)는 아직 없다.
- 다음 할 일: 서브에이전트(처음에는 단일의 검색 · 채점 · 재작성을 감싸기) → 조립 → 같은 70문항으로 Supervisor의 질문 종류 · 거절 결정을 D4 기준선과 비교.

## 2026-11-05 멀티 에이전트 폴더 뼈대와 약속(contracts.py)
- 한 일: 정운과의 설계 대화 결과로 새 구조의 첫 조각을 만들었다. D4 단일 그래프를 비교 기준선으로 지키려고 `backend/multi_agent/`를 `graph/`와 분리했고(이유는 폴더 설명 `MULTI_AGENT.md`), 시험 먼저 `contracts.py`를 썼다: Supervisor의 결정서 `Decision`, 서브에이전트의 보고서 `AgentReport`, 이유 코드 `Reason`(거절 7종 · 재시도 3종), 한도 `MAX_HOPS` 8 · `MAX_SEARCHES` 2 · `MAX_WRITES` 2와 한도 검사 `check_limit`.
- 바꾼 파일: `backend/multi_agent/`(`MULTI_AGENT.md` · `__init__.py` · `contracts.py`), `tests/multi_agent/`(`MULTI_AGENT.md` · `test_contracts.py`), `SOJAFIT.md` 트리와 담당 표, `backend/BACKEND.md` · `tests/TESTS.md` · `backend/graph/GRAPH.md`의 목록, 이 파일
- 실행한 명령과 결과: `uv run --frozen pytest tests/multi_agent -q` 10 passed. 폴더 구조 시험 통과.
- 확인 못 한 것: 이 조각은 데이터 모양과 한도 규칙뿐이라 LLM · 검색 · 측정은 아직 없다. 사용자에게 보일 거절 문구(일상어)와 Langfuse에 남길 항목은 다음 조각에서 정한다.
- 다음 할 일: Supervisor 노드(가짜 LLM으로 시험) → 서브에이전트(단일의 검색 · 채점 · 재작성을 감싸기) → 조립 → D4 점수와 비교.

## 2026-11-05 채점기 기준선(사전 등록 #36)
- 한 일: 로컬 `jeongun`을 `origin/main`(PR #54)에 맞추고 임시 브랜치 3개와 오래된 작업 폴더를 지웠다. 채점을 3갈래로 바꾸기 전 기준선으로, 지금 2갈래 채점이 정답 쪽을 얼마나 유지하는지 측정했다. 사전 등록 #36(처음 #33으로 적었으나 `main`의 오세창 #33과 겹쳐 11-05에 #36으로 바꿈), 시험 먼저, 계산기와 스냅샷 만들기(`evals/runners/eval_grader.py`), 입력 스냅샷(`evals/inputs/grader_cases_v2.json`, 청크 번호 · 파일 · 쪽만), 결과(`evals/results/grader/grader_baseline_2026-11-05.json`).
- 바꾼 파일: `evals/guides/preregister.md`(#36), `evals/runners/eval_grader.py`, `evals/inputs/grader_cases_v2.json`, `evals/results/grader/`, `tests/evals/test_eval_grader.py`, `SOJAFIT.md` · `INPUTS.md` · `RUNNERS.md` · `EVALS.md` · `tests/evals/EVALS.md`의 파일 줄, 이 파일
- 실제 결과: v2 관련 19문항에서 검색 청크가 정답 쪽을 다 가진 문항 15 · 일부 4. 채점이 통과시킨 청크 기준으로 충분 → 충분 12 · 충분 → 부분 2 · 충분 → 부족 1 · 부분 → 부분 4(정답 쪽 유지율 12/15, 쪽 재현율 평균 0.776). 비관련 35문항 중 34문항이 통과 0개. 사전 등록한 숫자와 같게 재현됐다(예측이 아니라 재현이며, 같은 스냅샷을 11-05에 임시로 먼저 계산해 본 것은 #36에 적었다). LLM · API 호출 0, 비용 0.
- 같이 알게 된 것: 정답 쪽이 검색에 다 있는 15문항 중 과잉 거절은 8건이고, 원인이 채점이 3(h04 · n01 · n04), 채점은 통과시켰는데 생성이 거절이 5(h05 · n06 · n07 · n08 · n21)다. 3갈래 채점으로 바뀌는 것은 앞쪽뿐이라 판정 노드 · 거절 형식 · 라우팅을 따로 다뤄야 한다.
- 확인 못 한 것: 스냅샷은 11-04 실행 한 번의 검색 결과라 재검색한 문항은 마지막 검색만 본다. R1 dev 46문항은 아직 안 만들었다(새로 검색해야 해서 호출이 든다).
- R1 dev 기준선(사전 등록 #34): R1 dev 46문항에 서비스 검색 + 지금 채점을 1번씩 돌려 측정했다(`eval_grader.py collect-r1`, 오류 0, OpenRouter 0.0133달러). 검색이 정답 쪽을 다 가져온 문항 39 · 일부 1 · 못 가져옴 6, 채점이 정답 쪽을 다 남긴 것 36/39(0.923, r1-050 · r1-078은 전부, r1-071은 일부 버림), 필요 쪽 통과 재현율 평균 0.804. 사전 등록 기대 세 가지 모두 범위 안. v2의 유지율은 0.80(12/15)이라 두 평가셋을 합치지 않고 따로 적는다.
- 확인 못 한 것(추가): R1 dev는 첫 검색 1번만 본다. 필터가 품번만이라 R1 1위 조합과 같지 않다. 같은 질문에 LLM 채점이 흔들리는 폭은 1번만 재서 모른다.
- 다음 할 일: 새 구조(Supervisor + 서브에이전트) 설계를 끝내고 골격을 만든 뒤, 3갈래 채점기를 R1 dev로 개발해 v2로 한 번 측정한다. 비교 기준은 이 두 기준선이다.

## 2026-11-04 단일 에이전트 기준 점수 측정(사전 등록 #31, D4)
- 한 일: 사전 등록 #28 결과 기록과 #31를 측정 전에 커밋(`a630454`)하고, 시험 2문항(draft30-m01 · draftv2-n16)과 Langfuse 확인 1~6 뒤 동결 v2 70문항을 줄기 그래프로 돌렸다(`LLM_PROVIDER=openrouter DEMO_MODE=0 uv run python -m evals.runners.run_graph evals/dataset_v2.jsonl`).
- 바꾼 파일: `evals/guides/preregister.md`(#31 결과), `evals/results/graph/graph_dataset_v2_2026-11-04.json`(새 파일), 이 파일
- 실제 결과: 70문항 실패 0. 관련 35는 cited_gold 12 · over_refusal 23, 무관 35는 correct_refusal 35, wrong_citation · hallucination_risk 0. over_refusal 23 중 candidate_find 10 · candidate_judge 9(후보 찾기 · 판정 19문항 전부 거절), role 3, rating 1. 라우팅 일치 31/35. p50 7.4초, 227 호출, 0.0519달러. 사전 등록 기대 11개 중 10개 범위 안, 1개(관련 hallucination_risk)는 채점기가 부여하지 않아 해당 없음, 저장소 밖 실행기 기록과 67문항 중 65 같음. Langfuse 확인 6개 통과.
- 확인 못 한 것: 같은 설정을 한 번만 돌렸다(OpenRouter 응답이 흔들리는 폭은 모름, 저장소 밖 기록과 2문항이 갈린 것이 단서). 답 지표는 규칙 채점이라 판정 5종의 정확도가 아니다.
- 다음 할 일: D5 단일 대 멀티 비교의 기준으로 쓴다. 후보 찾기 · 판정 19문항이 전부 거절이라 사양 표 거르기와 판정 노드가 필요하다. `EVAL_REPORT.md` 4장에 반영한다.

## 2026-11-04 임베딩 선정 실측 원시 결과와 해석 문서를 저장소에 올린다
- 한 일: 저장소 밖(`전자_데이터시트/evidence/`)에만 있던 임베딩 선정 실측을 트리 규칙에 맞춰 올렸다. 원시 결과: 임베딩 격자 본평가 78칸·카드 임베딩 기록 6개·리랭크 캐시(`evals/results/embedding/grid_*`), 검색 층별 재측정 0~4층·요약·최종 조합(`evals/results/retrieval/retrieval_layer*`, `retrieval_layers_*`), 비트 검색 3개(`scripts/results/bit_search/`). 해석: `docs/research/`에 문서 3개. `EVAL_REPORT.md` 1-3절에 원시 위치를 적고 1-4절(D3 #24, R1 #25, 비트 검색, 서비스 반영 #26·#27)을 더했다.
- 바꾼 파일: 위 결과 파일 18개와 문서 3개, 스크립트·시험·폴더 설명 파일(아래), `SOJAFIT.md`(트리 줄과 담당 표), `evals/EVALS.md`, `evals/runners/RUNNERS.md`, `evals/inputs/INPUTS.md`, `tests/evals/EVALS.md`, `scripts/SCRIPTS.md`, `docs/research/RESEARCH.md`, `EVAL_REPORT.md`, 이 파일
- 실행한 명령과 결과: 올릴 파일에서 키·비밀번호·절대 경로 패턴을 검색해 0건(`embed.py`의 로컬 기본 DB 접속 글은 스크립트라 올리지 않음). `uv run --frozen pytest -q` 전체 295 passed, 26 skipped(구조 시험 포함). 원시 결과 합계 약 4.5MB.
- 확인 못 한 것: 문서 표는 위키 원장과 원본 README에서 옮겼다(시험이 대조하는 건 원시 JSON 안의 요약·recall 값이다). 스크립트는 import와 문법, 순수 함수만 시험했고 실제 실행(DB·API·GPU)은 하지 않았다. 푸시는 하지 않았다.
- 스크립트도 올렸다(재현·시험용): `evals/runners/`에 `embed_cards.py`·`run_embedding_grid.py`(격자 #16), `check_retrieval_db.py`·`run_retrieval_layers.py`·`report_retrieval_layers.py`(층별 재측정), `scripts/bit_search/bit_search_exp.py`, `scripts/hf_jobs/hf_job.py`·`hf_data.py`, `evals/docker/Dockerfile.*` 2개, 고정 질의 `evals/inputs/layers/`. 새 폴더 `evals/docker/`·`scripts/bit_search/`·`scripts/hf_jobs/`는 폴더 설명 파일과 트리 줄을 같이 넣었다. 시험 3개(`tests/evals/test_embedding_grid.py`, `test_retrieval_layers.py`, `test_bit_search.py`)는 순수 계산과 결과 파일 재계산 대조(격자 78칸 요약, 층별 요약, 비트 recall 값이 문서 값과 같은지)를 본다.
- 스크립트를 고친 범위: import 경로(`evals.run_retrieval` → `evals.runners.run_retrieval` 등), 입출력 폴더(환경변수 `LAYERS_WORK`·`BIT_SEARCH_WORK`), 하드코딩 경로(`/Users/...`, 임시 폴더) 제거, 코드에 있던 실험 DB 접속 문자열을 `EMBED_DB` 환경변수로 바꿈. 측정 로직은 바꾸지 않았다.
- 올리지 않은 것: 질문·카드 벡터(`.npz`/`.npy`/`.f32`, 약 2.8GB), 실행 로그(`*.log`는 .gitignore), 78칸 비교 그래프(`compare.html`), `hnsw_exp`(405MB)와 11-01 `embed/` 스크립트, `v2_check.py`, 코덱스 검토 메모.
- 다음 할 일: 스크립트를 실제로 다시 돌려 본다(컨테이너·실험 DB·API 비용이 필요해 이번에는 안 함). `bit_search_exp.py`는 운영 DB가 voyage만 있어 그대로는 돌지 않는다.

## 2026-11-04 그래프 평가 실행기가 문항별 지표를 레포에 남기게 한다(D4 기준 점수 준비)
- 목적: D4 단일 기준 점수와 D5 단일 · 멀티 비교를 같은 형식으로 남기고, 평가자가 레포에서 숫자를 맞춰 볼 수 있게 한다(가이드 v5 제출물 "평가셋과 원시 결과, 재현 명령은 레포 내"). 지금까지는 Langfuse에만 남았다.
- 바꾼 파일: `evals/runners/run_graph.py`(`result_row` · `summarize` · `default_out`, 결과 파일 `evals/results/graph/graph_<평가셋>_<날짜>.json`, `--out`, 표준출력에 5지표), `tests/evals/test_run_graph.py`(시험 4개 추가, main을 Langfuse · LLM · DB 없이 가짜로 돌리는 시험 포함), `evals/EVALS.md`(결과 폴더에 `graph/` · D3 결과 파일 9개 설명), `evals/runners/RUNNERS.md`, 이 파일.
- 결과 파일에 넣는 것: 문항 id · 관련/비관련 · 정답 질문 종류 · 라우팅이 고른 종류 · 경로 · 검색 횟수 · LLM 호출 수 · 통과 청크 id · 인용 검사 · 5지표 · 시간 · 트레이스 주소, 실행 조건(커밋 · 모델 · 프롬프트 해시 · 평가셋 sha256 · Langfuse 세션), 요약(5지표 건수 전체 · 종류별, 라우팅이 맞은 관련 문항 수, 시간 중앙값, LLM 호출 합). 답변 문장과 청크 원문은 넣지 않는다(SPEC 6절).
- 확인한 것: `uv run --offline pytest -q` 273 passed, 26 skipped. 실제 OpenRouter · Langfuse로는 아직 돌리지 않았다(유료, 사전 등록 #29 뒤).
- 다음 할 일: 사전 등록 #31(v2 70건 단일 기준 점수) → 10문항 시험 실행 → 70건.

## 2026-11-04 용어를 개발자 표준 용어로 바꾸고 용어집을 둔다
- 목적: 강사 · 다른 조가 문서를 바로 읽게, 우리끼리 쓰던 말(카드, 고르기용 · 확인용, 쪽 적중 등)을 흔히 쓰는 말로 맞춘다.
- 바꾼 파일: `docs/glossary.md`(새 용어집), `docs/DOCS.md` · `SOJAFIT.md`(파일 목록 · 트리 한 줄), 마크다운 문서 전체와 파이썬 주석 · docstring(75파일). 카드 → 청크, 고르기용 · 확인용 → dev 세트 · test 세트, 쪽 적중 · 쪽 회수율 · 모든 근거 → Page Hit · Page Recall · Full Recall, 정답 쪽 → 정답 페이지, 표지 빼기 → 표지 청크 제외, 질의 재작성 → 쿼리 재작성, 차이 입증 못 함 → 유의차 없음. 조사가 받침에 맞게 바뀌도록 바꿨다.
- 바꾸지 않은 것: LLM이 읽는 글(`backend/prompts/` 프롬프트, `backend/mcp_skill/` 도구 설명, `backend/graph/nodes.py`의 채점 입력 · 스키마 설명), 데이터(동결 평가셋, `evals/samples/` jsonl, `evals/results/`), `db/` SQL, "모델 카드". 사전 등록 지난 항목은 용어만 바꿨고 조건 · 숫자 · 기대 범위는 그대로다.
- 확인한 것: `uv run --offline pytest -q` 269 passed, 26 skipped. 바뀐 파이썬 29파일은 주석 · docstring만 다르고, 코드 문자열은 오류 · Langfuse 점수 설명 · 시험 실패 메시지 4곳만 바꿨다(`ast` 비교). 잘못 붙은 조사 · 겹친 말(`청크(청크)` 등)을 검색해 0곳으로 맞췄다.
- 다음 할 일: 없음.

## 2026-11-04 한 번에 하나씩 단계별 재측정 · 실패 유형 · 리랭커 비용과 시간(사전 등록 #28)
- 목적: #25 최종 비교는 지금 서비스에서 네 가지(재작성 Q3 · 표지 청크 제외 · rerank-3 · voyage-4-large)를 한꺼번에 바꾼 것이라, 과제 가이드의 "한 번에 하나만 바꿔 잰다"를 단계별로 따로 보인다. 단계 순서와 기대는 `evals/guides/preregister.md` #28(측정 전 커밋 39229a9).
- 바꾼 파일: `evals/runners/run_retrieval_r1.py`(`steps`: S0 → S4 단계별 재측정 · 앞 단계와 짝 비교 · 실패 유형), `evals/runners/run_retrieval_service.py`(`--stages N`: 질문 임베딩 · rerank-3 · 나머지 시간과 rerank 토큰), `evals/runners/RUNNERS.md`, 이 파일.
- 실행한 명령과 결과: `run_retrieval_r1 steps`(#25 캐시, 새 리랭크 호출 0) → `evals/results/retrieval/r1_steps_2026-11-04.json`, `run_retrieval_service --stages 20` → `service_stages_2026-11-04.json`. test 세트 38 Page Recall@5 S0 0.5789 → S1 0.7632(9승 2패, 개선) → S2 0.7895 → S3 0.8289 → S4 0.9079, S2~S4는 1~3문항 차이라 문항 id만 적었다. rerank-3 p50 0.35초, 호출당 평균 5,122토큰(질문당 약 0.00026달러). 숫자 전체는 #28 결과 줄.
- 확인 못 한 것: 단계 순서를 바꾸면 단계별 차이가 달라질 수 있다(순서는 하나만 쟀다). 시간은 R1 앞 20문항 · 맥에서 운영 DB로 잰 값이다.
- 다음 할 일: 없음.

## 2026-11-04 운영 DB 정리와 Cloud Run 배포(검색 설정 반영)
- 목적: PR #46 · #47 머지 뒤 운영 Supabase에서 쓰지 않는 3-small 벡터를 빼 DB를 줄이고, main을 Cloud Run에 실제 모드로 배포한다.
- 바꾼 것: 운영 DB `chunk_embeddings`를 비우고(TRUNCATE) voyage-4-large 52,244행만 다시 넣었다(`ingest --voyage`). Secret Manager를 켜고 비밀값 7개(DATABASE_URL · OPENROUTER_API_KEY · VOYAGE_API_KEY · AUTH_SECRET · LANGFUSE_PUBLIC_KEY · LANGFUSE_SECRET_KEY · LANGFUSE_BASE_URL)를 정운이 `.env`에서 등록했다. main(`0b01656`)을 `gcloud run deploy sojafit-api --source . --project sojafit --region asia-northeast3 --port 8000 --memory 1Gi --max-instances 1 --set-env-vars DEMO_MODE=0 --set-secrets ...`로 배포하고 트래픽을 최신으로 옮겼다.
- 실행한 명령과 결과: DB 441.7MB → 비운 뒤 64.9MB → 다시 넣은 뒤 206.9MB(voyage 52,244행, 무작위 5건 코사인 1.0). 다시 넣은 뒤 103문항 재측정은 #27과 같은 값(Page Recall@5 dev 세트 0.8587 · test 세트 0.9342 · v2 0.8246, 오류 0, R1과 상위 5 같음 80/84). 새 리비전 `sojafit-api-00007-7dc`(1Gi), 트래픽 100%, `/health` 200(0.08~0.17초).
- 확인 못 한 것: 검색 · 그래프는 HTTP 경로가 없어 배포된 서비스로 질문을 보내 재지 못했다. 로그인은 `AUTH_ORIGIN`이 비어 403이고, 운영 DB에 인증 표(003 · 005 · 006 · 007)가 없다. 정확 검색 SQL에 동점 순서 기준이 없어 표를 다시 쓰면 같은 거리 청크의 순서가 바뀔 수 있다(위 80/84).
- 다음 할 일: 정운이 로그인 설정(AUTH_ORIGIN, 인증 SQL 적용)과 질문 API를 언제 열지 정한다. 3-small 벡터는 로컬 `corpus/tsc/embeddings/`에만 둔다.

## 2026-11-04 dense 비트 후보 + 정확 재정렬 구현(사전 등록 #27, 코드 · 문서만, DB 단계는 실행 안 함)
- 목적: 운영 DB 실측(3-small, `../전자_데이터시트/evidence/bq_exp`)에서 recall@50 0.980, 상위 5개 19/19 같음, `retrieve()` 중앙값 6.22초 → 0.89초였던 "1비트 후보 + 정확 재정렬"을 voyage-4-large 1024차원 서비스 검색에 옮긴다. 기대 · 비교 조건은 `evals/guides/preregister.md` #27(측정 전 커밋). 예산은 #26과 같다.
- 바꾼 파일: `db/009_chunk_embedding_bits.sql`(`chunk_embedding_bits` 표, 인덱스 없음, 기존 voyage 행에서 채움) · `db/DB.md` · `db/schema/erd.md`, `backend/rag/retrieve.py`(`N_BIT = 3200`, `_dense` 1단계 Hamming `<~>` → 2단계 정확 코사인, 허용 청크 <= N_BIT면 기존 정확 검색, 품번 필터가 없으면 표지 제외를 JOIN으로 해 아이디 5만 개를 안 보냄), `backend/rag/pipeline/ingest.py`(`load_voyage`가 비트 행도 채움, 009 미적용이면 건너뜀), `evals/runners/run_retrieval_service.py`(`--out` · `--prereg` · `--compare`), 시험 `tests/rag/test_rag_retrieve.py` · `test_rag_ingest.py` · `tests/evals/test_retrieval_service.py`, `SPEC.md` · ADR 0004 · `backend/rag/RAG.md` · `RUNNERS.md` · `tests/rag/RAG.md` · `SOJAFIT.md`, 이 파일.
- 실행한 명령과 결과: `uv run --offline pytest -q` 245 passed, 24 skipped(가짜 연결, DB · 네트워크 · API 없음, `.env`를 열지 않음).
- 확인 못 한 것: 009 적용 · 비트 채우기 · 비트 검색 측정 · pgvector 0.8.2에서 `binary_quantize(vector(1024))::bit(1024)`와 `bit <~> bit`가 실제로 도는지(SQL 글만 시험함, 실제 DB 시험 없음). 1024차원 voyage에서 N=3,200의 recall은 미측정이다. 009를 적용하기 전에 이 코드로 `retrieve()`를 부르면 비트 표가 없어 오류가 난다(허용 청크가 3,200장보다 많을 때).
- 다음 할 일: `db/009_chunk_embedding_bits.sql` 적용 → `run_retrieval_service --out evals/results/retrieval/service_r1_bits_2026-11-04.json --prereg '#27'` → `--compare`로 #26 결과와 대조 → #27 결과 줄과 이 항목에 값을 적는다.

## 2026-11-04 운영 DB 적용 · 서비스 경로 재측정 준비(사전 등록 #26, DB 단계는 실행 안 함)
- 목적: 서비스 검색 설정(voyage-4-large · rerank-3 · 재작성)을 운영 Supabase에 올리고, 실제 `retrieve()`로 R1 · v2 질문을 다시 재서 #25 값과 맞는지 본다. 이 기록은 스크립트와 기대를 준비한 단계다.
- 비교 조건 · 예산 · 중단 조건: `evals/guides/preregister.md` #26(측정 전 커밋 `4a86d4c`). OpenRouter 1달러(키 사용액 차이, 넘으면 멈춤), Voyage 상한 없음. `check`가 STOP이면 `migrate`는 하지 않는다(열 형식이 halfvec이 아니거나 적재 뒤 예상 크기 420 MB 초과).
- 바꾼 파일: `db/008_multi_dim_embeddings.sql`(halfvec(n)이면 `USING` 없이 차원 표시만 떼고 vector(n)일 때만 `USING embedding::halfvec`), `scripts/db/voyage_rollout.py`(+ `DB.md`), `evals/runners/run_retrieval_service.py`, `evals/runners/run_retrieval_d3.py`(`context()`의 v2 질문 만들기를 `v2_questions()`로 뺌, 동작 같음), 시험 `tests/rag/test_voyage_rollout.py` · `tests/evals/test_retrieval_service.py`, `SOJAFIT.md` · 폴더 설명 파일.
- 실행한 명령과 결과: `uv run --offline pytest -q` 240 passed, 24 skipped(오프라인, 가짜 연결 · 가짜 retrieve). DB · 네트워크 · API는 부르지 않았고 `.env`를 열지 않았다.
- 확인 못 한 것: `ALTER ... TYPE halfvec`(USING 없음)이 실제로 표를 다시 쓰지 않는지는 운영 DB에서 `migrate`의 filenode 전후로만 알 수 있다(SQL 글과 STOP 규칙만 시험함). 예상 크기는 행당 100바이트 어림이다. 재측정 값과 시간은 아직 없다.
- 다음 할 일: `voyage_rollout.py check` → `migrate` → `ingest --voyage <벡터 폴더>` → `verify` → `run_retrieval_service`. 측정 뒤 #26 결과 줄과 이 항목에 값 · 시간 · 비용을 적는다.

## 2026-11-04 서비스 검색을 R1 1위 설정으로 변경(사전 등록 #25 반영, 코드 · 문서만)
- 목적: 사전 등록 #25에서 잰 1위 설정(voyage-4-large 1024차원 · 재작성 질의 · 품번+청크 종류 필터 · rerank-3)을 서비스 검색에 그대로 옮긴다. 기준 구현은 `evals/runners/run_retrieval_d3.py`의 `search()` · `Index.allowed()`(`part+kind`) · `Reranker.voyage()`와 `run_retrieval_r1.py`의 `SortedReranker`.
- 바꾼 파일: `backend/services/llm.py`(`voyage_embed` · `voyage_rerank`), `backend/rag/retrieve.py`(모델 · 차원 · 표지 청크 제외 · 리랭크), `backend/graph/build.py`(라우팅 → 재작성 → 검색), `backend/rag/pipeline/ingest.py`(`--voyage` 적재 · `VectorCache` 파일 이름 · 차원 인자), `db/008_multi_dim_embeddings.sql`, `.env.example`, `tests/rag/test_rag_retrieve.py` · `tests/graph/test_graph_build.py` · `tests/services/test_llm.py`, `SPEC.md` · `AGENTS.md` · ADR 0004(갱신 2026-11-03) · `backend/rag/RAG.md` · `backend/services/SERVICES.md` · `backend/graph/GRAPH.md` · `db/DB.md` · `SOJAFIT.md`, 이 파일
- 실행한 명령과 결과: 아래 "확인" 줄에 적은 시험만 돌렸다(오프라인, 가짜 llm · 가짜 DB).
- 확인 못 한 것: DB 마이그레이션(db/008)과 voyage 벡터 적재(`ingest.py --voyage`)는 실행하지 않았다. 서비스로 다시 잰 값(재측정)은 아직 없다. 적용 전에는 `retrieve()`가 voyage 행을 찾지 못한다. 실제 Voyage 호출 · 응답 시간 · 비용, 열 형식 변경 때 Supabase 여유 용량(표를 다시 쓰는 동안 옛 표와 새 표가 같이 차지함)도 보지 않았다.
- 다음 할 일: 복제 DB에서 db/008 적용 → `ingest.py --voyage` 적재 → 서비스 설정으로 같은 평가셋 재측정, 값이 #25와 맞으면 운영 DB에 적용. `README.md` 74행의 임베딩 표기는 이번에 고치지 않았다.

## 2026-11-03 R1 검색 측정(사전 등록 #25): 문서 구조 정답 84문항으로 임베딩 × 필터 × 질의 × 리랭커 264칸
- 목적: #24는 채점 19문항이라 어떤 칸도 개선을 입증하지 못했다. 정답을 문서 구조로 정한 문항을 늘리고 dev 세트 · test 세트를 나눠 임베딩 · 리랭커를 고른다.
- 비교 조건 · 예산 · 중단 조건: `evals/guides/preregister.md` #25(측정 전 커밋 `309b55f` 21:29). OpenRouter 상한 5달러, Voyage 상한 없음, HF 없음, 칸 오류는 그 칸만 건너뜀(정운 결정 11-03).
- 바꾼 파일: `evals/samples/retrieval_r1.jsonl` · `retrieval_r1_rewrite_q3.json`, `evals/runners/run_retrieval_r1.py`(`d9c9f9d` BM25 점수 재사용), `evals/results/retrieval/r1_2026-11-03.json`, 사전 등록 #25, `SOJAFIT.md` · `SAMPLES.md` · `RUNNERS.md`, 이 파일
- 실행한 명령과 결과: `python -m evals.runners.run_retrieval_r1 rewrite|qvec-api|requests|run`(맥), `gpu-qvec` · Qwen 리랭크(desktop-gpu 도커). test 세트 38문항에서 지금 서비스(3-small · 품번 필터 · 질문 줄 · 리랭커 없음) Page Recall@5 0.579 → voyage-4-large · 재작성 Q3 · 품번+청크 종류 · rerank-3 0.908(14승 1패, 95% 구간 +0.184~+0.487, 개선). 요약 = 문항 평균, 고른 3칸 = dev 세트 상위 3, 짝 비교 9개를 따로 다시 계산해 모두 일치. 지출 OpenRouter 0.0091달러, Voyage 57,134,574토큰.
- 확인 못 한 것: 서비스에 넣었을 때의 응답 시간과 비용(질문마다 재작성 LLM 1회 + Voyage 리랭크 1회), Supabase에 voyage-4-large 벡터를 올렸을 때의 정확 검색 속도. 정답은 사양 표 규칙 추출에 기대고, 질문은 값 찾기뿐이다.
- 다음 할 일: 정운이 표를 보고 임베딩 · 리랭커 · 재작성 · 필터를 정한다. 정하면 ADR 0004(임베딩) 갱신, 서비스 반영, 그래프 70건 평가.

## 2026-11-03 D3 공식 검색 측정 시작 전 기록(사전 등록 #24)
- 목적: 동결 v2 채점 19문항을 페이지 단위 정답(qrels 36쪽)으로, 서비스 검색 경로를 기준으로 한 조건씩 바꿔 잰다(E1 방식 · E2 리랭커 · E3 필터 · E4 질의 · E5 임베딩 · E6 청킹 · E7 토큰화 · E8 RRF, 칸마다 필터 끔 재측정). 기대 수치는 `evals/guides/preregister.md` #24.
- 비교 조건: 기준은 3-small · 하이브리드(BM25 50 + dense 50, RRF 60) · "질문:" 줄 · 품번 필터 · 리랭커 없음 · 청킹 C · k=5. 동점은 거리 → 청크 순서.
- 예산: OpenRouter $1.00(E6 다시 임베딩 · 질문 임베딩), Voyage 무료 한도만, Upstage · HF 없음. GPU 칸(bge-reranker, Qwen3-Reranker, late chunking)은 GPU PC를 켠 뒤.
- 명령: `uv run --with docling-core python -m evals.runners.run_retrieval_d3 chunks`, `embed <변형>`, `official`, `noresult`, `explore`. 청크 · 벡터는 저장소 밖(`../corpus/tsc/`, `../전자_데이터시트/evidence/full_grid/vectors/`).
- 중단 조건: v2 해시가 다르면 모두 멈춘다. 그 밖에는 그 부분만 건너뛰고 이유를 결과에 남긴다. Voyage 결제 신호면 남은 Voyage를 건너뛴다.
- 바꾼 파일: `evals/runners/run_retrieval_d3.py`, `evals/inputs/`(INPUTS.md · qrels_v2_pages.json · rewrite_q3_v2.json), `tests/evals/test_retrieval_d3.py`, `evals/guides/preregister.md` #24, `SOJAFIT.md` 트리 · 폴더 표, `evals/EVALS.md`, `evals/runners/RUNNERS.md`, `tests/evals/EVALS.md`
- 확인: `uv run --offline python -m pytest -q tests/repo/test_repo_layout.py tests/evals/test_retrieval_d3.py tests/evals/test_frozen_evals.py` 12개 통과. 측정 결과는 아직 보지 않았다.
- 실행과 결과(측정 끝)
  - 커밋: `d8febee`(사전 등록 · qrels · 실행기, 측정 전), `08b3dd6`(첫 실행에서 `search()`의 옛 import 경로 때문에 64칸이 모두 건너뛰어져 고침. 조건 변경 없음), `11adefa`(GPU 단계 조건 덧붙임, 측정 전).
  - 맥: `official`(E1~E8, E6L만 GPU로 미룸), `noresult`, `explore`(276칸, 탐색). E6 변형 6종은 `chunks` 뒤 `embed`로 3-small 다시 임베딩(semantic은 OpenRouter 시간 초과 1회 뒤 이어서 끝냄).
  - GPU(desktop-gpu RTX 3080 Ti 도커): `gpu_embed fixed1000_100 --mode bgem3`(120초) · `bgem3late`(112초, CLS 대체 0), `official --exps E2,E6L`(로컬 리랭커 bge-reranker-v2-m3 · Qwen3-Reranker 0.6B/4B). 기준 칸 값이 맥과 같다. 새 로컬 리랭크 114줄은 맥 캐시에 키 기준으로 합쳤다.
  - 원시 결과: `evals/results/retrieval/d3_official_2026-11-03.json`, `d3_official_gpu_2026-11-03.json`, `d3_noresult_2026-11-03.json`, `d3_explore_2026-11-03.json`. 작업 사본은 `../전자_데이터시트/evidence/d3/`.
  - 지출: OpenRouter $0.338(시작 뒤 키 사용액 차이, 상한 $1.00). Voyage 탐색 격자 새 호출 3,154회 · 31,879,036토큰과 공식 E2 76회 이하, 결제 신호 없음. HF 없음. Upstage 건너뜀(키 없음).
  - 확인 못 한 것: 기대 범위 대조(맞음/틀림)는 적지 않았다. no_result 임계값은 같은 54문항 안에서 골랐다. GPU 결과의 커밋 칸은 컨테이너에 git이 없어 실행 뒤 `11adefa`로 적었다.
  - 다음 할 일: 정운 검토 뒤 #24 맞음/틀림을 채우고 `EVAL_REPORT.md` 반영 여부를 정한다.

## 2026-11-03 폴더 안에서도 성격별로 묶는다(구조 2차 정리)
- 한 일
  - 한 폴더 바로 아래에 코드·데이터·문서가 섞인 곳을 하위 폴더로 나눴다. `evals/`는 루트에 동결 평가셋만 두고 `runners/`·`guides/`·`samples/`·`drafts/sets/`·`drafts/reviews/`·`results/<주제>/`로, `scripts/`는 `auth/`·`langfuse/`·`results/<주제>/`로, `db/` 문서는 `schema/`로, `backend/rag/`의 오프라인 도구는 `pipeline/`로, `memory.py`는 `graph/`로, `tests/`는 `api/`·`graph/`·`rag/`·`services/`·`evals/`·`judge/`·`repo/`로 옮겼다.
  - 모듈 이름이 바뀌었다: `python -m backend.rag.pipeline.<모듈>`, `python -m evals.runners.<이름>`. 코드·시험·문서의 경로와 import를 같이 고쳤다.
  - 문서가 정한 앞으로의 자리를 만들었다: `.gitkeep` 폴더 7개(`backend/judge/rules/`, `backend/web/templates/`·`static/`, `data/corpus/public/`·`injection_tests/`, `docs/deliverables/langfuse/`, `tests/fixtures/`)와 `tests/judge/`. 아직 없는 파일은 `SOJAFIT.md` 트리에 `(예정)`으로 적었다(judge 파일 이름은 후보).
  - `tests/repo/test_repo_layout.py`에 한 폴더 한 종류 시험과 `(예정)` 처리를 더했다. 규칙은 `SOJAFIT.md` 이름 규칙과 AGENTS.md 지킬 것 9번에 적었다.
  - v2 동결 작업(위 항목)의 초안·검토표도 `drafts/sets/`·`drafts/reviews/`로 옮겼다.
- 실행한 명령과 결과: `uv run --frozen pytest -q` 165 passed, 24 skipped. 상대 링크 검사 깨진 링크 0.
- 확인 못 한 것: 팀원 브랜치(OSC·STH)는 옛 경로로 작업 중이라 main을 받을 때 충돌한다. 저장소 밖 실험 스크립트가 옛 경로(`evals/results/` 바로 아래 등)에 쓰는지는 보지 않았다.
- 다음 할 일: PR 뒤 OSC·STH에 새 경로를 알린다.

## 2026-11-03 평가셋 v2 동결: v1 50건 + 후보 찾기 20건, 질문 종류 칸
- 한 일
  - `evals/dataset_v2.jsonl` 70건(관련 35·비관련 35)을 만들고 `evals/freeze.py`로 동결했다(sha256 `81582c59…`, `FROZEN.json`). v1 50건 줄에는 `question_type`만 더했고, 추가 20건은 Codex 초안(11-01)을 하정운 1차·김재훈 2차 사람 판정에서 모두 O로 받은 것이다.
  - `question_type`은 그래프 라우팅 코드(`role`·`rating`·`candidate_judge`·`candidate_find`)를 쓴다. 비관련은 `null`. v1 관련 25건은 역할 6·정격 10·후보 판정 9, 추가 관련 10건은 후보 찾기다. e04·e05·m05·n21은 라우팅 LLM(11-02) 라벨과 달리 값을 묻는 질문이라 정격으로 뒀다.
  - 후보 찾기는 열린 정답이라 `evals/run_retrieval.py`가 검색 순위로 채점하지 않고 `candidate_find_skipped`에 id만 적게 했다.
  - 초안과 검토표를 `evals/drafts/draft_v2add_20.jsonl`·`draft_v2add_20_review.md`로 옮기고, `SOJAFIT.md` 트리·`EVALS.md`·`DRAFTS.md`·`dataset-guide.md`·`EVAL_REPORT.md` 2장 v2 칸을 고쳤다.
  - `tests/test_frozen_evals.py`에 v2 앞 50건이 v1과 같은지(`question_type` 빼고) 보는 시험을 더했다.
- 만든 방법: 저장소 밖 `전자_데이터시트/evidence/v2_build/make_v2.py`(Codex 근거 `corpus_txt/○○.txt, N쪽`을 `○○.pdf, N쪽`으로, `netlists/○○.net`을 문항의 레포 넷리스트 경로로 바꿈. 비관련은 v1처럼 `gold_chunks` 빈 목록).
- 확인: v2 앞 50건 == v1(`question_type` 빼면), v1 해시 그대로(`2fef02c2…`), `freeze.py --check` 통과, `uv run --offline pytest -q` 164 passed · 24 skipped.
- 확인 못 한 것: v2로 다시 잰 검색·그래프 점수(아직 안 잼), 후보 찾기 공식 채점 방법(사양 표 조건 거르기, 저장소 밖 탐색 `전자_데이터시트/evidence/spec_table/`만 있음).
- 다음 할 일: v2로 단일 에이전트 기준 점수 다시 재기(`dataset-guide.md` 동결 계획), 후보 찾기 경로에서 원래 부품 품번 필터를 끄고 사양 표로 후보 내기.

## 2026-11-03 저장소 구조 정리: 폴더 설명 파일을 `<대문자 폴더명>.md`로 되돌리고 파일 위치를 SOJAFIT.md 트리로 묶는다(ADR 0012)
- 한 일
  - origin/main(e25558a)으로 빠르게 맞춘 뒤 문서·코드 전체를 다시 읽었다.
  - 폴더 설명 파일 24개를 `README.md`에서 `<대문자 폴더명>.md`로 되돌렸다. ADR 0011은 대체됨, 0012를 새로 썼다.
  - 역할이 다른 파일을 옮겼다: 실험·평가 작업서는 `docs/experiments/`, 조사·실측은 `docs/research/`, 동결 전 초안은 `evals/drafts/`, 평가가 아닌 측정 결과는 `scripts/results/`, 평가셋 명세는 `evals/dataset-guide.md`로 분리했다.
  - 대문자 문서는 소문자로 바꿨다(`preregister.md`, `erd.md`, `design.md`, `sth.md`). macOS `core.ignorecase=true`라 대소문자만 바꾸는 이름은 `git mv`를 두 번 거쳤다.
  - `SOJAFIT.md`에 모든 파일의 `<-` 설명 트리를 넣었다. AGENTS.md 지킬 것 9번에 트리를 따르는 규칙을, 팀 규칙 3번에 주요 문서는 조장만 고치는 규칙을 넣었다. 폴더 설명 27개와 README를 다시 썼다.
  - `tests/test_repo_layout.py`가 트리·이름 규칙·폴더 설명 파일 목록을 검사한다.
  - 코드 리뷰(graphify·ponytail-review)로 결함을 고쳤다.
    - 같은 thread 다음 턴에 앞 턴 검색 칸이 남던 버그(위 항목의 다음 할 일)
    - 넷리스트 경로의 저장소 밖 탈출
    - 로그인 시도·만료 세션 표의 무한 증가
    - 수집 URL 이중 인코딩·파일명 검증
    - 임베딩 개수 불일치를 조용히 자르던 문제
    - 파싱 시간 제한 범위와 파일 핸들 누수
    - 평가 실행의 없는 문항 id 무시
  - 모든 파이썬 파일의 머리말(역할·하지 않는 일·출처)과 주석을 정리했다. 프롬프트 해시는 `PROMPTS.md`를 빼도록 맞췄다.
- 바꾼 파일: 151개(이름 변경 60개 포함). 목록은 `git status`.
- 실행한 명령과 결과
  - `uv run --frozen pytest -q`: 163 passed, 24 skipped(작업 전 151 passed, 24 skipped).
  - 상대 링크 검사: 깨진 링크 0.
  - 구조 검사 테스트: 트리에 없는 파일, 대문자 문서, 폴더별 README, 트리 줄 삭제, 설명 없는 새 폴더의 5종 변이를 모두 잡았다.
  - graph 수정 2건: 수정을 빼면 각 테스트가 실패하는 것을 확인했다.
  - 코드 변경 범위: HEAD 대비 docstring을 뺀 AST 비교로, 주석만 바뀐 파일과 코드가 바뀐 파일을 나눠 확인했다.
- 확인 못 한 것
  - 로그인 정리 DELETE를 실제 PostgreSQL에서 돌려 보지 않았다.
  - 유료 API·DB가 필요한 스크립트는 실행하지 않았다.
  - OSC·STH 브랜치와의 병합 충돌은 아직 보지 않았다. 두 브랜치가 옛 `README.md`·`PREREGISTER.md` 경로와 `docs/` 루트에 파일을 더한다.
  - VS Code·Finder의 정렬 방식은 문서 기준이다. GitHub 정렬은 화면으로 확인했다.
- 다음 할 일: 커밋을 목적별로 나눈다. OSC·STH에 새 위치를 알린다. SPEC 검토 결과를 반영한다(조장).

## 2026-11-03 그래프 평가 실행을 Langfuse에 남긴다(`evals/run_graph.py`)
- 한 일: 정운 결정(11-03)으로 SPEC 7절의 "프롬프트·응답은 Langfuse에 기록하지 않는다"를 바꿔, 그래프 평가 실행이 문항마다 트레이스를 남기게 했다. 아래 "줄기 그래프 조립" 항목의 임시 스크립트를 정식 파일로 옮겼다. 노드 코드는 그대로이고, 실행하는 쪽이 `CallbackHandler`를 넘긴다. 트레이스에는 단계별 입력·출력(청크 내용 포함), LLM 토큰·비용, 실행 조건 메타데이터(공급자·모델·검색 방식·데이터셋·코퍼스 판·git 커밋·프롬프트 해시)와 실행 점수 10종(path·question_type·not_found·tries·llm_calls·docs_found·passed_cards·latency_s·fake_citations·uncited_sentences)이 붙는다. 한 실행은 session 하나, 환경 이름은 `eval`이다. 문항별 결과 파일은 청크 내용이 들어가 저장소에 남기지 않는다. `LANGFUSE_BASE_URL` 끝에 `/`가 있으면 트레이스가 버려지므로 실행 전에 멈춘다.
- 바꾼 파일: `evals/run_graph.py`(새 파일), `tests/test_run_graph.py`(새 파일), `SPEC.md`(7절 Langfuse 줄), `docs/GATES.md`(G6 상태), `backend/services/llm.py`(맨 위 설명 한 줄), `evals/README.md`, `tests/README.md`, 이 파일
- 실행한 명령과 결과: `uv run pytest tests/test_run_graph.py tests/test_graph_build.py -q` 8 passed. 로컬 `.env` 그대로 실행하면 "LANGFUSE_BASE_URL 끝의 /를 지우세요"로 LLM 호출 전에 멈춘다. `LANGFUSE_BASE_URL=https://cloud.langfuse.com LLM_PROVIDER=openrouter DEMO_MODE=1 uv run python -m evals.run_graph evals/dataset_v1.jsonl draft30-e01 draft30-e03 draft30-e06 draft30-e07`로 4문항 실패 0건, 문항당 1.8~9.8초. e03 트레이스를 API로 다시 읽어 환경 `eval`, session 하나, LLM 호출 3건 비용, 점수 10종이 들어간 것을 확인했다.
- 확인 못 한 것: Langfuse 가격표 금액과 실제 OpenRouter 청구액이 같은지. 무료 플랜 한도. 정운 로컬 `.env`의 Langfuse 주소 끝 `/`는 아직 그대로다(정운이 고친다).
- 데모 모드 없이(`.env` `DEMO_MODE=0`, 하이브리드 검색) 같은 4문항: 실패 0건, 경로는 BM25 때와 같고 문항당 1.9~11.7초. e03은 하이브리드에서 1N5817 절대 최대 정격 VRRM 줄(청크 1186, dense 4위·BM25 11위)이 상위 5개에 들어와 "VRRM 20 V"로 답했다(BM25만일 때는 "20 - 40 V 범위"). 트레이스 메타데이터 `retrieval`은 `hybrid`.
- 정운 결정(11-03): 첫 검색어를 영어 재작성으로 바꿀지는 임베딩 모델 결과가 나와 동결이 확정된 뒤 그래프 파이프라인을 다시 검사할 때 정한다. 지금은 단일 에이전트가 데모 없이 도는지만 가볍게 본다.
- 속도(e03 11.7초): 라우팅 1.5초, 검색 4.9초, 채점 1.2초, 생성 4.1초(답 133토큰에 추론 토큰 282개). 정운 결정(11-03): DB 적재와 검색 속도 개선(후보 추림 뒤 재정렬, 검색 담당)이 적용된 뒤 다시 잰다. 추론 토큰을 끌지는 그 뒤 사전 등록 실험으로 본다.
- 다음 할 일: 같은 thread 이월 버그를 고친다. 검색 속도 개선이 들어오면 같은 4문항으로 단계별 시간을 다시 잰다.

## 2026-11-03 줄기 그래프 조립(`build_graph`)과 진짜 연결 4문항
- 한 일: `build_graph(retriever, checkpointer)`로 줄기 노드 7개를 강의 2주 20강 방식으로 이었다. 라우팅 뒤 갈림길 `after_route`(범위 밖은 거절, 역할은 생성, 나머지는 검색)를 새로 넣고, 채점 뒤는 기존 `after_grade`를 쓴다. 검색기를 넘기지 않으면 함수 안에서 `backend.rag.retrieve.retrieve`를 불러온다. 체크포인터는 `compile`에 그대로 넘긴다. Supervisor·interrupt는 아직 없다.
- 바꾼 파일: `backend/graph/build.py`, `backend/graph/README.md`, `tests/test_graph_build.py`(새 파일), `tests/README.md`, 이 파일
- 실행한 명령과 결과:
  - `uv run pytest tests/test_graph_*.py -q` 32 passed. 새 시험 6개: 통과 → 생성(검색기는 입력 전체가 아니라 질문 줄만 받는다), 재작성 → 재검색 → 생성, 두 번 다 통과 없음 → 검색 2번 뒤 거절, 검색 0장 → 재작성 없이 거절, 범위 밖·역할 → 검색 없이 거절·생성. `MAX_TRIES`를 3으로 바꾸면 검색 2번 시험이 실패한다(변이 확인).
  - 진짜 연결: `LLM_PROVIDER=claude_cli DEMO_MODE=1`(LLM은 `claude -p --model haiku`, `.env`의 `ANTHROPIC_API_KEY`가 환경으로 넘어감. 검색은 Supabase BM25만)로 v1 4문항을 돌렸다. 실행 스크립트는 저장소 밖에 두었다. 4문항 모두 설계한 경로로 갔다(e01 라우팅 → 생성, e03 검색 → 채점 → 생성, e06 라우팅 → 거절, e07 검색 0장 → 거절). LLM 호출 7번, 문항당 5.5~27.9초.
  - 답 내용: e01(D1 역할)은 넷리스트 근거(J1 → S1 → D1 → F1 → RAW)를 받고도 "문서로 확인 안 됨"으로 답했다. e03(1N5817 역전압)은 BM25 상위 5개에 1N5817 VRRM 줄이 없어(같은 표의 Marking code 줄만 있음) 시리즈 범위 "20 - 40 V"만 인용하고 단독 값은 특정할 수 없다고 답했다(정답 20 V). 두 문항 모두 없는 근거 인용·인용 없는 문장은 0건.
  - 같은 thread의 두 번째 메시지(메모리 체크포인터, 가짜 LLM·검색기): 새 질문 대신 앞 질문의 재작성 검색어로 찾았고 `tries`가 2에서 3으로 이어졌다.
  - Langfuse 트레이스: 실행 때 `config={"callbacks": [CallbackHandler(trace_context={"trace_id": ...})]}`만 넘겨(노드 코드는 그대로) 같은 4문항을 다시 돌렸다. 4문항 모두 Langfuse에 단계 이름(입력 읽기·라우팅·after_route·검색·채점·after_grade·생성/거절)으로 올라간 것을 API로 다시 읽어 확인했다. 첫 시도는 로컬 `.env`의 Langfuse 주소 끝 `/` 때문에 전송 주소가 `//api/public/otel/v1/traces`가 되어 308을 받고 버려졌다. 실행 명령에 `LANGFUSE_BASE_URL=https://cloud.langfuse.com`을 붙이자 200. 핸들러의 `last_trace_id`는 실제 전송된 트레이스 id와 달라서 id를 직접 정해 넘긴다. 실행 스크립트는 저장소 밖이고, SPEC 7절("프롬프트·응답은 기록하지 않는다")은 아직 그대로다.
  - `claude -p` 시간: 라우팅과 같은 호출 1번이 전체 6.3초, 그중 API 1.8초였고 나머지 약 4.4초는 CLI 기동이다. 입력이 13,999토큰(캐시 생성)으로 지시문보다 훨씬 커서, CLI가 개인 `~/.claude` 설정을 같이 싣는 것으로 본다(추정). 비용 0.0019달러.
  - 정운 결정(11-03): 진짜 연결 실행은 OpenRouter로 한다. 같은 4문항을 `LLM_PROVIDER=openrouter`(팀 키, `anthropic/claude-haiku-5.5`)로 돌려 팀 키 호출이 된다는 것을 확인했다. 경로와 답은 CLI 때와 같고(e01 "문서로 확인 안 됨", e03 "20 - 40 V 범위"), 문항당 0.9~10.6초(CLI 5.7~26.9초). 호출당 입력 1,015~1,598토큰. Langfuse에 LLM 호출 7건이 토큰 수와 함께 남았다(비용 칸은 비어 있음). e01 생성·e03 채점으로 보이는 호출에 추론 토큰(218·598)이 붙었다(입력 토큰 수로 노드를 짐작함).
  - Langfuse 정보 보강(정운 요청): 비용 칸이 빈 이유는 OpenRouter 모델 이름 `anthropic/claude-haiku-5.5`(점)가 Langfuse 기본 가격표 `claude-haiku-5-5`(하이픈)와 맞지 않아서였다. 팀 Langfuse 프로젝트에 가격표 `openrouter/anthropic/claude-haiku-5.5`(입력·출력·추론 토큰, ADR 0010 가격, id `cmw04bb4y0f58ad0j6amsjnur`)를 등록했다. 실행 스크립트가 트레이스에 실행 묶음(session `graph-smoke-<월일-시분>-<공급자>`), 환경(`local-dev`), 태그, 메타데이터(문항 id·종류·기대 경로·공급자·모델·검색 방식·k·데이터셋·코퍼스 판·git 커밋·프롬프트 4개 해시), 점수 9종(path_match·not_found·tries·llm_calls·docs_found·passed_cards·latency_s·fake_citations·uncited_sentences)을 남기게 하고 OpenRouter로 다시 돌렸다. API로 다시 읽어 모두 들어간 것과 호출별 비용(4문항 합계 0.00136달러)을 확인했다.
- 확인 못 한 것: `claude -p`가 구독이 아니라 API 키로 결제됐는지와 4문항 비용. e01·e03 원인은 추정이다(e01은 `generate.md`의 "근거에 적힌 내용만 쓴다"가 연결로 역할을 해석하는 답을 막는다, e03은 BM25가 질문의 한국어 "역전압"을 쓰지 못하고 채점이 범위 청크를 통과시켜 재작성까지 가지 않았다).
- 다음 할 일: 같은 thread 이월 문제, e01·e03을 고칠지 정한다. SPEC 7절을 고치고 그래프 평가 실행에 Langfuse를 붙인다. OpenRouter로 10문항 확인.

## 2026-11-03 검색 방식 인자와 v1 방식별 검색 베이스라인
- 한 일: `retrieve()`에 `method`(`hybrid` 기본·`dense`·`bm25`)를 넣었다. `hybrid`는 지금 동작 그대로이고, `dense`는 dense 목록만, `bm25`는 BM25 목록만 쓰며 임베딩 API를 부르지 않는다. 다른 값은 `ValueError`. `run_retrieval.py`가 네 번째 위치 인자로 방식을 받고 summary에 `method`를 적는다. 같은 코드로 v1의 dense만·BM25만 베이스라인을 재서 하이브리드 베이스라인 옆에 두었다.
- 바꾼 파일: `backend/rag/retrieve.py`, `evals/run_retrieval.py`, `tests/`(test_rag_retrieve.py, README.md), `SPEC.md`(4절 검색 시그니처), `docs/specs/rag-pipeline.md`(How), `backend/rag/README.md`, `evals/README.md`, `evals/results/retrieval_{baseline,dense,bm25}_2026-11-03.json`, `EVAL_REPORT.md`(9장 재현 명령), 이 파일
- 실행한 명령과 결과: `uv run --offline pytest -q` 91 passed, 18 skipped(새 시험 2개: `bm25`에서 임베딩 호출 없음, 없는 방식은 `ValueError`). `bm25` 분기가 `_dense`를 부르게 바꾸면 새 시험이 실패한다(변이 확인). 로컬 compose DB(`sojafit-db-1`)에 EVAL_REPORT 9장 명령으로 `dataset_v1.jsonl` 데이터시트 근거 19문항, k=5를 쟀다. 문서 Recall@5 / MRR / Page Hit@5는 하이브리드 0.737 / 0.649 / 0.368, dense만 0.684 / 0.589 / 0.263, BM25만 0.263 / 0.195 / 0.211이다. 질문당 중간값은 dense 1.39초, BM25 0.20초. dense 결과에는 `bm25_rank`가, BM25 결과에는 `dense_rank`가 19문항 모두 비어 있다. 질문 임베딩 호출은 dense 19회, BM25 0회.
- 확인 못 한 것: 임베딩 비용은 따로 재지 않았다. `DEMO_MODE=1`에서 `method='dense'`는 늘 `[]`이다(dense 목록이 비어서). 하이브리드 파일은 `method` 인자가 생기기 전 코드로 만든 결과다.
- 다음 할 일: `build_graph` 조립.

## 2026-11-02 줄기 그래프 노드: 상태, 입력 읽기, 라우팅, 검색, 채점, 재작성, 생성, 거절
- 한 일: 강의 2주 20강 구조로 줄기 그래프를 노드 하나씩 만들고 있다. 상태(`AgentState`, `tries`·`path`만 쌓고 나머지는 덮어씀), 입력 읽기(입력 글 나누기, `connections.json`에서 대상 부품과 핀 3개 이하 이웃 너머까지 2단계 넷), 라우팅(질문 종류 5가지, `backend/prompts/route.md` v1), 검색(`search`)을 넣었다. 검색은 질문에 나온 품번을 `parts`로 넘기고, 질문에 품번이 없을 때만 대상 값의 품번을 넘긴다(11-02 조장 결정). 둘을 합치면 n11 "D3 대체 후보 1N60P"처럼 코퍼스에 없는 후보를 물었을 때 D3 값 1N4148 문서가 나와 그 수치로 답하게 된다. 품번은 영문과 숫자가 섞인 낱말로 보고, 회로 기호(대상과 주변 넷 부품), 값(3.6V·100pF), 개정 코드(K2611)는 뺀다. 코퍼스에 없는 품번도 남겨 `retrieve`가 `[]`를 돌려주게 한다. 채점(`grade`)은 LLM 전에 규칙으로 두 가지를 뺀다. 표 한 줄 청크가 같은 문서 표지의 다른 품번만 적힌 줄이면 빼고(1N5819를 물었는데 1N5817 순방향 전압 0.45V 줄), 질문에 개정 코드가 있으면 파일 이름의 개정 코드가 다른 청크를 뺀다(11-02 조장 결정: 형제 품번 줄은 LLM이 아니라 코드로 막는다). 이를 위해 `retrieve`가 청크마다 문서 표지 품번 목록 `doc_parts`를 같이 돌려준다. 남은 청크는 `grade.md` 프롬프트로 LLM 1회 채점하고, LLM이 보여 주지 않은 번호를 내면 버린다. 재작성(`rewrite`)은 1차 검색어가 아니라 원래 질문을 데이터시트 영어 용어로 된 검색어 한 줄로 바꾸고(`rewrite.md` v1), 품번 필터는 바꾸지 않는다. 채점 뒤 갈림길 `after_grade`(build.py)는 통과 청크가 있으면 생성, 검색 결과가 0장이면 재작성 없이 거절(11-02 조장 결정: 재작성해도 품번 필터가 같아 다시 0장), 검색이 2번이면 거절, 아니면 재작성으로 보낸다. 거절 뒤에 이어지는 노드는 나중에 만든다(11-02 조장 결정). 생성(`generate`)은 강의 20강처럼 통과 청크와 넷리스트(`[넷리스트]`)만 근거로 넘겨 문장마다 번호를 붙여 답하게 하고(`generate.md` v1), 없는 근거 인용과 인용 없는 문장을 코드로 세어 `check`에 남긴다. 검사에 걸려도 답은 그대로 내고 기록만 한다(11-02 조장 결정). 값을 비교한 판정은 하지 않고(`backend/judge/` 몫), 근거가 없으면 LLM을 부르지 않고 "문서로 확인 안 됨"으로 답한다. 거절(`refuse`)은 강의 20강처럼 LLM 없이 이유를 답으로 남긴다. 범위 밖이면 범위만 안내하고, 근거 없음은 품번 문서가 없을 때(검색 0장, 그 품번을 적음)와 찾은 문서에 답이 없을 때(찾아본 문서 이름, 검색 횟수)로 나눈 뒤 단서(부품 윗면 글자, 사진, 데이터시트, 주문 코드)를 묻는다.
- 바꾼 파일: `backend/graph/`(state.py, nodes.py, GRAPH.md), `backend/prompts/`(route.md, grade.md, PROMPTS.md), `backend/rag/`(retrieve.py, RAG.md), `docs/specs/rag-pipeline.md`(돌려주는 키), `SPEC.md`(2절 검색·채점 줄), `tests/`(test_graph_state.py, test_graph_read_input.py, test_graph_route.py, test_graph_search.py, test_graph_grade.py, test_rag_retrieve.py, TESTS.md), 이 파일. 재작성 때(폴더 설명 파일 이름이 README.md로 바뀐 뒤): `backend/graph/`(nodes.py, build.py, README.md), `backend/prompts/`(rewrite.md, README.md), `SPEC.md`(2절 재작성 줄), `tests/`(test_graph_rewrite.py, README.md). 생성 때: `backend/graph/`(nodes.py, README.md), `backend/prompts/`(generate.md, README.md), `SPEC.md`(2절 생성 줄), `tests/`(test_graph_generate.py, README.md). 거절 때: `backend/graph/`(nodes.py, README.md), `SPEC.md`(2절 거절 줄), `tests/`(test_graph_refuse.py, README.md)
- 실행한 명령과 결과: `uv run --offline pytest -q` 89 passed, 18 skipped. 채점 시험은 품번 검사를 끄면 실패한다(변이 확인). 갈림길 시험은 `MAX_TRIES`를 3으로 바꾸거나 0장 거절 규칙을 끄면 각각 실패한다(변이 확인). 생성 시험은 없는 근거 인용 세기를 끄거나 "문서로 확인 안 됨" 예외를 끄면 각각 실패한다(변이 확인). `rewrite.md`의 영어 용어 예시는 로컬 청크 파일에서 많이 나오는 PARAMETER 이름(Forward voltage 3,100줄, Repetitive peak reverse voltage 1,464줄 등)에서 골랐다. 품번 뽑기 규칙은 코퍼스 목록(`datasheet_list.csv`, 품번 9,589개)에서 값 모양·개정 코드 모양 품번이 0개임을 확인하고 정했다. 평가셋 v1에서 라우팅이 검색으로 보내는 36문항에 가짜 검색기로 검색 노드를 돌려 `parts`를 봤다. 관련 문항은 모두 질문 품번으로 찾고, 비관련 unknown_entity 6건(1N4001·SS1P3L·BAT85·1N5711·1N60P·1N34A)은 코퍼스에 없는 품번만 넘어가며, h08·h09는 품번이 없어 전체 검색이다. 다른 품번 줄 빼기는 로컬 청크 파일(`chunks.jsonl`)로 쟀다. 1N5819를 물으면 1N5817 SERIES 표 줄 26개 중 1N5817·1N5818 순방향 전압 2줄만 빠지고 패키지 줄(DO-41)은 남는다. 영문과 숫자가 섞인 낱말을 모두 품번으로 보면 BZT52C3V6 문서 표 줄 62개 중 40개가 빠지고 패키지 줄(SOD-123F)도 빠져서 이 방법은 쓰지 않았다. 라우팅은 `LLM_PROVIDER=claude_cli`로 50문항을 돌려 out_of_domain 6/6이 out_of_scope로 갔고, e09(보드 실측값)는 out_of_scope, h10(2026 USB-C판)은 role로 갔다(PROMPTS.md).
- 확인 못 한 것: 실제 DB `retrieve`로 검색·채점 노드를 돌리지 않았고(`doc_parts` DB 시험은 `TEST_DATABASE_URL`이 없어 건너뜀), `grade.md`·`rewrite.md`·`generate.md`로 LLM을 실제로 부르지 않았다. 답에 원본 PDF 주소는 아직 붙이지 않는다(SPEC 6절, 파일 이름·쪽만). 대상 주변이 아닌 회로 기호(U3, SJ1)는 품번으로 잘못 뽑힌다(코드에 shortcut 주석). 후보 판정 질문에서 원래 부품 데이터시트는 이 검색으로 나오지 않는다(평가셋에서 해당 문항 없음).
- 실측 필요(중요, 구독으로 10문항 돌릴 때 같이 본다): ① 검색이 질문 품번을 먼저 쓰는 정책이 관련 문항에서 맞는 청크를 찾는지, ② 채점 LLM이 맞는 청크를 고르는지, ③ 재작성이 검색 결과를 실제로 낫게 하는지, ④ 생성 인용 검사(없는 근거 인용·인용 없는 문장)에 걸리는 비율. ④를 보고 검사에 걸린 답을 다시 쓰게 할지 거절로 보낼지 정한다.
- 다음 할 일: `build_graph` 조립.

## 2026-11-02 그래프 줄기 설계와 LLM 호출 입구
- 한 일: D4 줄기 그래프의 노드 7개와 상한을 SPEC 2절에 적고, 그래프 LLM을 `anthropic/claude-haiku-5.5`로 시작한다는 결정을 ADR 0010으로 남겼다. `llm.py`에 그래프 노드가 쓰는 `chat(system, user, schema)`를 넣었다. OpenRouter 호출은 강의 2주 20강처럼 LangChain `ChatOpenAI(...).with_structured_output(schema)`로 하고(`langchain-openai` 1.7.3 추가), Pydantic 형식으로 검증하고, 형식이 틀리면 2회까지 다시 부른다. 공급자는 `LLM_PROVIDER`로 고르며 `openrouter`(기록용 측정·서비스)와 `claude_cli`(개발 중 같은 모델을 구독으로)를 둔다.
- 바꾼 파일: `SPEC.md`(2절 그래프), `AGENTS.md`(LLM 모델 줄), `docs/adr/`(0010, ADR.md), `backend/services/llm.py`, `backend/services/SERVICES.md`, `tests/test_llm.py`, `.env.example`(LLM 3줄), `pyproject.toml`·`uv.lock`(`langchain-openai`), 이 파일
- 실행한 명령과 결과: `uv run --offline pytest -q` 63 passed, 18 skipped(새 `chat()` 시험 5개 포함: 형식 검증, 코드 블록 안 JSON, 재시도 뒤 성공, 호출 3번에서 멈춤, CLI 명령에 도구 끄기와 스키마 포함). `LLM_PROVIDER=claude_cli`로 라우팅 분류 3문항을 실제로 불러 role·rating은 맞았고, MOSFET 선정 질문은 out_of_scope가 아니라 candidate_find로 분류됐다. 프롬프트에 "다이오드가 아닌 부품 선정은 out_of_scope"를 넣자 out_of_scope로 분류됐다(라우팅 노드 프롬프트에 넣을 것). 모델 선택 근거인 10문항 비교(Haiku·Sonnet 모두 JSON 10/10, 없는 근거 인용 0, 비관련 거절 5/5)는 ADR 0010에 적었다.
- 확인 못 한 것: 팀 OpenRouter 키로 `chat()` 실제 호출(구조화 출력 포함)은 아직 하지 않았다. `claude -p`와 OpenRouter의 같은 모델 출력이 같은지는 재지 않았다.
- 다음 할 일: 팀 키로 Haiku 5.5 1회 호출 확인, `backend/graph/state.py`·`build.py`에 줄기 노드 7개 구현과 가짜 검색기 시험.

## 2026-11-02 v1 동결 뒤 문서 정리
- 한 일: v1 동결(11-02) 뒤 저장소 문서를 처음부터 끝까지 다시 읽고, 지난 상태(동결 전·예정·확인 전), 숫자·이름 불일치(30/50/52건, ADR 0008·0009), 문서 사이 모순, 이전 주제(DART·공시)와 강사 템플릿 잔재, 작업 메모가 새어 나온 문장을 고쳤다. 동결 파일과 코드 동작은 바꾸지 않았다. 숫자형 7건(e03·e05·e08·m03·m07·n03·n05)은 1차 사람 판정과 숫자 기계 대조로 동결했다는 사실을 평가 문서에 적었고, v1에 `question` 키가 없어 `run_retrieval.py`가 `input` 전체로 검색한다는 점(11-01 #4~#8과 바로 비교 불가)을 적었다.
- 바꾼 파일: 루트 `README.md`·`SOJAFIT.md`·`SPEC.md`·`AGENTS.md`·`EVAL_REPORT.md`·`.env.example`(주석), `evals/`(md 5개, py 3개 docstring), `docs/`(GATES·DOCS·EVALUATION·조원-계약서, ADR 0003~0008·ADR.md, specs 7개, WORKLOG.md, 이 파일), `backend/`·`data/`·`db/`·`tests/`의 폴더 설명 파일과 주석·docstring(코드 문자열은 `FastAPI(title="SojaFit API")` 하나)
- 실행한 명령과 결과: `uv run --offline pytest -q` 56 passed, 18 skipped. `uv run --offline python evals/freeze.py --check` "동결 이후 바뀐 파일: 없음". 저장소 md의 상대 링크 185개(원 저작자 `original/` 제외)를 NFC·NFD로 대조해 깨진 링크 0개. diff에서 비밀값 패턴 0건, `*.jsonl`·`FROZEN.json`·`docs/TOPIC.md`·다른 조원 작업 기록 변경 0건.
- 확인 못 한 것: 동결본 v1의 일본어 가운뎃점(・, 26문항 134곳)·id 접두사·`corpus_version` 표기 차이는 동결 파일이라 고치지 않고 `evals/EVALS.md`에 적었다. `db/table-definition.md`의 `analysis_runs.thread_id` UNIQUE와 `auth_sessions` FK `ON DELETE CASCADE`(문서는 "모든 FK RESTRICT"), 규칙 파일 경로(`rules/*.yaml`, SPEC 5절 미정)는 설계 결정이라 문구를 고치지 않았다. 영어 주석(auth.py·subset.py·llm.py·일부 테스트·SQL)은 그대로 두었다.
- 다음 할 일: 위 설계 결정 2건을 담당과 정하고, 김재훈·오세창·심태현 작업 기록의 "사용자" 표기와 끝난 상태 문구는 본인에게 알린다.

## 2026-11-02 평가 초안 4건 하정운 검수 기록
- 한 일: 평가 초안의 남은 검수 4건에 하정운 O를 기록했다. n01·n02(relevant + NOT_VERIFIED)와 h03(irrelevant / missing_attribute)은 김재훈이 바꾼 답안을 1차 재검수해 합의했고, n21은 1차 O로 두 사람 O가 됐다. 본편 50건은 사람 합의 43건·숫자형 기계 대조 7건이 되었고, 공식 동결은 하지 않았다.
- 바꾼 파일: `evals/draft_50.jsonl`(n01·n02·h03·n21 네 줄만), `evals/DRAFT_50_REVIEW.md`, `evals/EVALS.md`, `EVAL_REPORT.md`, `docs/adr/0008-평가-정보부족-구분과-52건-초안.md`, `docs/adr/ADR.md`, `docs/specs/evaluation-draft-52.md`, 이 파일
- 실행한 명령과 결과: 바꾸기 전에 `draft_50.jsonl` 모든 줄이 같은 직렬화로 되돌아오는지 확인하고 네 줄만 바꿨다(4줄 변경). 상태 집계는 `draft_reviewers_agreed_change_hold_not_frozen` 43건, `draft_human1_reviewed_do_not_freeze` 7건이다. `uv run --offline pytest -q`는 56 passed, 18 skipped(DB 시험은 `TEST_DATABASE_URL`이 없어 건너뜀)였다.
- 확인 못 한 것: n02의 BAS70 3쪽 Fig.2 8.3ms 곡선 값은 텍스트로 읽지 못했다. 네 건의 판정은 하정운 확인(11-02)에 따랐다.
- 동결: `draft_50.jsonl` 50건의 고정 키 9개만 `evals/dataset_v1.jsonl`로 옮기고(모든 값이 초안과 같은지 확인) `uv run --offline python evals/freeze.py dataset_v1.jsonl`로 동결했다. sha256 2fef02c2dcd8b49e6edb620e23cbf3860ec95912e1a345ed2b719c9a3db7e42b, 50건(관련 25·비관련 25), `--check` "바뀐 파일 없음". n21만 `corpus_version`이 manifest sha256(PR #19 판, 같은 1,360건)으로 적혀 있어 다른 49건의 글자 표기와 다르다.
- 다음 할 일: 같은 저장소 코드로 v1 검색 베이스라인을 잰다.

## 2026-11-02 PR #23·#24 머지 뒤 리뷰 의견 반영
- 한 일: PR #21·#23·#24의 리뷰와 코멘트를 다시 읽고, 머지 뒤에도 남은 것을 고쳤다. 두 PR이 같이 쓴 ADR 0008 번호를 나눠 Mouser ADR을 0009로 옮겼다. SPEC 3절에 원래 부품의 근거가 없을 때도 동일품·사양 동등을 내지 않는다고 적어 2절·ADR 0006과 맞췄다. halfvec 전환 조건(모델 확정, 동결 평가셋 Recall@5·MRR 무하락, 그 전까지 기본 `vector`)을 SPEC 6절·ADR 0005에 PR #24 내용과 같게 적었다. SPEC 6절 이용 조건에 Infineon 약관을 넣었다.
- 바꾼 파일: `SPEC.md`(3절, 6절, Mouser 링크), `docs/adr/`(0005, 0008 → 0009 이름 바꿈, ADR.md 목록 순서), 이 파일
- 실행한 명령과 결과: `gh api .../pulls/{21,23,24}/reviews|comments`, `issues/{21,23,24}/comments`로 의견을 모았다. 문서 확인은 `SPEC.md`와 `docs/adr/*.md`의 상대 링크가 모두 실제 파일을 가리키는지 대조했다. `uv run --offline pytest -q`는 51 passed, 10 skipped(DB 시험은 `TEST_DATABASE_URL`이 없어 건너뜀)였다.
- 확인 못 한 것: 코멘트 밖 검토 의견(`retrieve.py` halfvec 경로의 행마다 float32 변환 시간, SQL의 `1536` 상수화, 쓰지 않는 `subset.py` 유지 여부)은 고치지 않았다.
- 다음 할 일: 위 세 가지는 임베딩 모델 확정 뒤 halfvec 전환 때 함께 정한다.

## 2026-11-02 Mouser 응답을 저장하지 않는다는 결정 기록
- 한 일: Mouser Search API 약관을 읽고, 가격·재고를 저장하지 않고 견적서를 열 때마다 다시 조회한다는 조장 결정을 ADR 0009(처음 0008, 평가 ADR과 번호가 겹쳐 옮김)와 `SPEC.md`에 적었다. 데모 모드는 Mouser 칸을 비운다.
- 바꾼 파일: `docs/adr/`(0009, ADR.md), `SPEC.md`(1절 하지 않는 것, 6절, 7절, 8.4), 이 파일
- 실행한 명령과 결과: 약관 원문(https://www.mouser.com/apiterms/, 최종 수정 2013-03-11)의 1·2·4·5절을 읽었다. API 문서 V2 정의(https://api.mouser.com/api/docs/ui/index)에서 검색 엔드포인트 3개와 부품 응답 칸(`LifecycleStatus`, `IsDiscontinued`, `SuggestedReplacement`, `PriceBreaks`, `AvailabilityInStock`, `DataSheetUrl` 등)을 확인했다. 문서 확인은 바뀐 문서의 ADR 상대 링크가 실제 파일을 가리키는지 대조했다.
- 확인 못 한 것: 키 발급 승인 여부, 호출 한도(API 문서에 없음), 견적서 PDF 내려받기가 저장에 해당하는지. `docs/TOPIC.md` 범위 칸과 `db/table-definition.md` 10절의 Mouser 관련 줄은 고치지 않았다(ADR 0009 결과 절).
- 다음 할 일: 확장 단계 전에 Search API 키를 신청하고, 신청서에 견적서 용도를 적는다.

## 2026-11-02 설계 결정 기록(사용자 흐름, 근거가 없을 때, 코퍼스 나누기, Supabase 저장)
- 한 일: 조장과 정한 설계를 `SPEC.md`와 ADR 0005~0007에 적었다. 사용자 흐름에 후보 정하기 단계를 넣고, 근거가 없을 때의 순서(코퍼스 재검색 → TSC 실시간 조회 → 후보 먼저·단서 요청 → 단서 없이 진행)와 판정 근거로 인정하는 것을 적었다. 코퍼스는 기존(동결)·증분으로 나누고 평가는 기존만, Supabase는 한 프로젝트에 `halfvec`·HNSW 없음으로 둔다.
- 바꾼 파일: `SPEC.md`(1절 하는 일·하지 않는 것, 2절 사용자 흐름·근거가 없을 때, 6절), `docs/adr/`(0005, 0006, 0007, ADR.md), 이 파일
- 실행한 명령과 결과: 로컬 compose DB 임시 스키마에서 저장 방식별 크기를 쟀다(코퍼스 829.5 → HNSW 제거 466.7 → `halfvec` 258.0 → 본문 중복 제거 237.8MB). `embedding::halfvec::vector = embedding`이 52,244/52,244였고, 청크 1,000개 질의의 정확 검색 top-5 집합이 100% 같았다. 정확 검색 중앙값은 float32 230.5ms, `halfvec` 140.2ms였다. 임시 스키마는 지웠고 기존 표는 그대로다. 서비스 DB 크기는 그래프가 없어 langgraph 1.2.18·checkpoint-postgres 3.2.0으로 오프라인 추정만 했다. 문서 확인은 ADR·SPEC 상대 링크가 실제 파일을 가리키는지 대조했다.
- PR #23 리뷰(nanocode00) 반영: 원래 부품이 확인 안 될 때와 후보가 확인 안 될 때의 견적 조건을 SPEC 2절·ADR 0006에 나눠 적어 SPEC 3절과 맞췄다. 벡터 표만 다른 DB로 옮기는 안은 `retrieve.py`가 연결 하나를 전제로 하므로 미확정 대안으로 바꾸고, 나누기 전에 정할 항목을 적었다(SPEC 6절, ADR 0005).
- 확인 못 한 것: Supabase 무료 서버의 검색 시간, Supabase가 500MB를 MB와 MiB 중 무엇으로 세는지, 실제 그래프의 체크포인트 크기, 실제 질문 임베딩으로 본 `halfvec` 비교, 평가 때 실시간 조회를 끄는 것에 대한 강사 확인, Infineon 파싱 글 저장 여부.
- 다음 할 일: 임베딩 모델 확정 뒤 `halfvec` Migration과 Supabase 적재, D4 그래프로 체크포인트 크기 실측, 그래프 입력·질문 종류·노드 정하기.

## 2026-11-02 manifest를 대시보드가 읽는 크기로 줄이기
- 한 일: PR #19 머지 뒤 Checkpoint 대시보드 G3 칸에 "manifest가 커서 읽지 못함"이 떴다(`data/manifest.jsonl` 1,012,774바이트). GitHub GraphQL `Blob.text`가 이 파일을 512,000바이트에서 자르는 것(`isTruncated=true`)을 확인했다. 1,360줄 모두 같은 값 6개(`manufacturer`, `collected_at`, `parser`, `status`, `purpose`, `usage_conditions`)를 `chunk.py`의 `DOC_DEFAULTS`로 옮기고 `ingest.py`가 읽을 때 채우게 했다. 늘 null이고 읽는 코드가 없는 `exact_original_part_match`와, 파일 이름이 `source_url` 끝과 같은 `path`를 뺐고, 공백 없는 JSON으로 쓴다. `collect.py`는 `path`가 없으면 `source_url` 끝에서 파일 이름을 얻는다.
- 바꾼 파일: `backend/rag/`(chunk.py, ingest.py, collect.py), `data/manifest.jsonl`, `data/DATA.md`, `data/corpus/CORPUS.md`, `docs/specs/rag-pipeline.md`(What 4), `SPEC.md`(6절 확장 문장), `tests/`(test_rag_chunk.py, test_rag_ingest.py, test_rag_collect.py, TESTS.md), 이 파일
- 실행한 명령과 결과: 기존 manifest를 1회용 스크립트(저장소 밖)로 새 형식으로 바꿨다. 바꾸기 전에 1,360줄 모두 뺀 값이 `DOC_DEFAULTS`와 같고 `path`의 파일 이름이 `source_url` 끝과 같은지 assert했다. 1,012,774 → 470,263바이트(1,360줄, 한 줄 평균 346바이트). `ingest.main`과 같은 식으로 채운 값 12개가 1,360줄 모두 바꾸기 전과 같고, `collect.read_targets`의 파일 이름 1,360개도 같다. `uv run --offline pytest -q` 26 passed, 2 skipped. 새 크기 시험은 바꾸기 전 manifest로 돌리면 실패한다.
- 확인 못 한 것: `chunk.py` main은 docling이 로컬에 없어 돌리지 않았다(새 쓰기 형식의 키 순서·공백은 바꾼 manifest와 같게 코드로 맞춤). DB 재실행 시험(`TEST_DATABASE_URL`)은 돌리지 않았다. 한 줄 346바이트면 약 1,480줄에서 512,000바이트를 넘으므로 Infineon(280~430건)을 넣으면 다시 넘을 수 있다. 그래서 Infineon·MOSFET 확장은 3차 범위에서 하지 않기로 하고 SPEC 6절에 지원 가능 품목으로만 적었다(11-02 조장 결정).
- 머지 뒤 확인(PR #21): GitHub GraphQL이 main의 manifest를 자르지 않고 읽는다(`byteSize` 470,263, `isTruncated=false`). Checkpoint 대시보드 G3 칸이 "문서 1360/50, 청크 52,244/10,000"으로 나온다(11-02). `docs/GATES.md` G3 상태 칸을 이에 맞게 고쳤다.
- 다음 할 일: 평가자가 서로 다른 청크 수(본문 sha256)를 확인할 방법을 강사에게 묻는다. 청크는 TSC 약관 때문에 저장소 밖에 있다.

## 2026-11-01 오세창 검수 의견 13개 반영 (PR #15~#18 후속)
- 한 일: PR #15~#18의 오세창 검수 의견 13개를 PR 하나로 반영했다. 결정 기록 2건(ADR 0003 v1 50건 동결, ADR 0004 임베딩 1536차원 임시 결정), manifest로 PDF 받기(sha256 대조), `chars_original`·`chars_kept`·`truncated` 실제 계산, `SIGALRM`이 없는 OS 처리, 벡터 캐시 끊김 복구, DB에 있는 임베딩은 다시 부르지 않기, BM25 0점 후보 제외, 데모 모드 BM25만, 평가 대상 0건 오류, 각각의 테스트.
- 바꾼 파일: `docs/adr/`(0003, 0004, ADR.md), `SPEC.md`(6·7절), `docs/specs/rag-pipeline.md`(EC-07~10, AC-10~12), `backend/rag/`(collect.py, parse.py, chunk.py, ingest.py, retrieve.py, RAG.md), `evals/run_retrieval.py`, `data/manifest.jsonl`, `data/DATA.md`, `tests/`(test_rag_collect.py, test_rag_parse.py, test_rag_ingest.py, test_rag_retrieve.py, TESTS.md), 이 파일
- 실행한 명령과 결과: `uv run --offline pytest -q` 25 passed, 2 skipped in 0.49s(DB 시험 2개는 건너뜀). DB 시험은 `TEST_DATABASE_URL`(로컬 compose DB)을 줄 때만 돌게 했고, api 이미지 컨테이너에서 `pytest tests/test_rag_ingest.py tests/test_rag_retrieve.py`를 돌려 14 passed, 시험용 임시 스키마는 남지 않았다. 처음에는 DB 시험이 `DATABASE_URL`을 읽어 .env의 Supabase 주소로 접속을 시도했다가 접속 단계에서 실패했다(만든 것 없음). 그래서 시험은 `TEST_DATABASE_URL`만 쓴다. 글자 수를 새로 재려고 `chunk`를 파서 비교용 도커 이미지에서 1,360건에 다시 돌렸고, 청크 파일은 이전과 바이트까지 같았다. 원문(본문 글 조각 + 표 칸) 5,231,811자 중 청크에 들어간 글자는 5,016,468자(95.9%, 문서 중간값 96.1%, 최저 85.6%)이고 1,356건이 `truncated`다. 빠진 글은 주로 표와 같은 조각으로 묶여 버려진 표 옆 주석이다(예: BZT52B2V4 F15의 "Notes: 1. The Zener Voltage (VZ) is tested under pulse condition…"). 처음 잴 때는 청크 앞에 붙는 소제목을 세지 않아 92.2%로 나와 고쳤다.
- 확인 못 한 것: 로컬 DB의 `source_documents` 글자 수 열은 예전 값 그대로다(`ingest`가 있는 문서를 건너뜀). Supabase 적재 때 새 manifest로 들어간다. Windows에서 직접 돌려 보지는 않았다.
- 다음 할 일: 표 옆 주석이 청크에서 빠지는 문제를 사전 등록 뒤 청킹 실험으로 본다. 50건 동결 뒤 베이스라인, Supabase 적재, 후보 찾기용 사양 표.

## 2026-11-01 retrieve()에 품번 필터 인자 parts 넣기 (PR #18)
- 한 일: `retrieve(question, *, k=5, parts=None)`에 품번 필터를 넣었다(HNSW 개선 실험 B, 사전 등록 #6의 방식). `warmup()`이 BM25 색인과 함께 표지 청크(`이 데이터시트의 품번: ...`)로 품번(소문자) → 문서 색인을 만든다. `parts`를 주면 그 품번이 적힌 문서의 청크만 dense(`WHERE chunk_id = ANY(...)`, 인덱스를 끈 정확 검색)와 BM25(허용 밖 청크는 -inf) 후보로 쓰고 RRF는 같다. 품번은 대소문자만 무시하고 전체가 같아야 걸린다. 코퍼스에 없는 품번뿐이면 `[]`를 돌려주고 전체 코퍼스로 넘어가지 않는다. 질문에서 품번을 뽑는 일은 하지 않는다(에이전트가 후보 품번을 준다).
- 바꾼 파일: `backend/rag/retrieve.py`, `backend/rag/RAG.md`, `tests/test_rag_retrieve.py`, `tests/TESTS.md`, `docs/specs/rag-pipeline.md`(What 6, Out of Scope, How, AC-08·09), `SPEC.md`(4절 검색 계약, 6절 검색), 이 파일
- 실행한 명령과 결과: `uv run --offline pytest -q` 14 passed. 로컬 compose DB에 `docker compose run --rm --no-deps -u ... -e DEMO_MODE=0 ... api python <확인 스크립트>`(스크립트는 저장소 밖 임시 폴더, 키는 compose가 .env에서 읽음). warmup 1.7초, 표지가 읽힌 문서 1,360/1,360, 색인 품번 9,589개. "SS34 정격이 어떻게 돼?" + `parts=["SS34"]` → 5장 모두 `SS32 SERIES_Q2412.pdf`(허용 청크 55개). `parts=["1N4148"]` → 5장 모두 `1N4148 SERIES_K2301.pdf`(허용 문서 1개, 1N4148W 문서는 따로). `parts=["NOPE123"]` → `[]`. parts 없이 → 5장(SS32·SS32H·SS34ALH·SS34FSH 문서가 섞임). 데이터시트 근거가 있는 관련 19문항에 질문 속 코퍼스 품번을 `parts`로 주니 19/19 필터가 걸려 문서 Recall@5 1.000, MRR 1.000, Page Hit@5 0.947(실험 B와 같음, 필터 없는 하이브리드는 1.000 / 0.921 / 0.737), 질문당 중간값 1.05초(임베딩 호출 포함). 쪽을 놓친 문항은 n03 하나. parts 없을 때 BM25 후보가 바꾸기 전 식과 50문항 모두 같았다(API 호출 없이). 질문 임베딩 호출 22회.
- 확인 못 한 것: 19문항·동결 전 초안이다. parts 없는 경로의 dense SQL은 바꾸기 전과 같은 문장이라 다시 재지 않았다. 에이전트가 `parts`를 정하는 노드와 서버 기동 때 `warmup()` 연결은 하지 않았다. 표지 표기와 다른 품번 표기(접미사·하이픈 차이)는 걸리지 않는다.
- 다음 할 일: 50건 동결 뒤 같은 방식으로 다시 재고, 판정 노드가 후보 품번을 `parts`로 넘기게 연결한다.

## 2026-11-01 HNSW 개선 실험 4개 (PR #18)
- 한 일: HNSW 인덱스가 한국어 질문의 가까운 청크를 놓치는 문제로, 결과를 보기 전에 `evals/PREREGISTER.md` #5~#8을 커밋하고 조건 하나씩 바꾼 실험 4개를 같은 측정 스크립트로 쟀다. A 영어 질문(번역은 정답을 모르는 서브에이전트가 미리 만든 고정 번역), B 품번 필터, C `KURE-v1`, D `Qwen3-Embedding-0.6B`(C·D는 원격 GPU 도커에서 청크 45,898개를 다시 임베딩해 로컬 DB 실험 표에 넣음). EVAL_REPORT 1장에 결과 표를 넣었다.
- 바꾼 파일: `evals/PREREGISTER.md`, `EVAL_REPORT.md`, `evals/results/hnsw_exp_*_2026-11-01.json`(5개), 이 파일
- 실행한 명령과 결과: 측정 스크립트·원격 임베딩 스크립트는 저장소 밖 `전자_데이터시트/evidence/hnsw_exp/`. 기준을 같은 스크립트로 다시 재니 HNSW 겹침(ef 100)이 사전 등록에 적은 43%가 아니라 61%였다(인덱스를 다시 만든 뒤라서). 결과: B가 정확 하이브리드 1.000/1.000/0.947(19문항 모두 필터 걸림, dense 0.0007초), D가 HNSW 겹침 76%/97%·HNSW 하이브리드 MRR 0.816, C는 겹침 38%/85%, A는 정확 하이브리드 MRR 0.512로 떨어짐. 원격 이미지 빌드 3분, KURE 임베딩 4.7분, Qwen3 3.7분. 로컬 모델이라 API 비용 없음, 질문 임베딩만 과금.
- 확인 못 한 것: 19문항·동결 전 초안이다. 차이가 1~3문항이라 개선이라 단정하지 않는다. 영어 질문을 dense에만 쓰는 방식과 품번 필터 + HNSW 조합은 재지 않았다. 로컬 모델의 서버(Cloud Run) 메모리·지연은 재지 않았다.
- 다음 할 일: 품번 필터를 `retrieve()`에 넣을지 정하고(D3 메타데이터 필터), 50건 동결 뒤 다시 잰다.

## 2026-11-01 하이브리드 검색과 검색 평가 실행기 (PR #18)
- 한 일: `backend/rag/retrieve.py` 뼈대에 `retrieve(question, k=5)`를 넣었다. dense는 `embed_texts`로 질문을 임베딩해 pgvector 정확 검색 상위 50, BM25는 `document_chunks` 본문으로 메모리 색인(`warmup()`) 상위 50, 둘을 RRF(k=60)로 합친다. `evals/run_retrieval.py`는 평가셋 관련 문항의 `gold_chunks`에서 PDF 이름과 쪽을 읽어 문서 Recall@k, MRR, Page Hit@k를 잰다. EVAL_REPORT 1장에 저장소 코드 결과, 9장에 재현 명령을 넣었다.
- 바꾼 파일: `backend/rag/retrieve.py`, `backend/rag/RAG.md`, `evals/run_retrieval.py`, `evals/EVALS.md`, `tests/test_rag_retrieve.py`, `tests/TESTS.md`, `EVAL_REPORT.md`, 이 파일
- 실행한 명령과 결과: `docker compose run --rm --no-deps -e DEMO_MODE=0 ... api python -m evals.run_retrieval evals/draft_50.jsonl <결과>`(키는 compose가 .env에서 읽음). 데이터시트 근거가 있는 관련 19문항(회로 근거만 있는 6문항 제외)에서 문서 Recall@5 1.000, MRR 0.921, Page Hit@5 0.737, 질문당 중간값 1.2초. 11-01 실험과 같은 11문항은 1.000 / 0.955 / 0.818(11-01 실험 1.000 / 0.909 / 0.727). 처음에는 dense를 HNSW로 찾아 MRR 0.553~0.816이 나왔고, 정확 검색과 비교해 HNSW가 한국어 질문의 가까운 청크를 놓치는 것을 확인해 정확 검색으로 바꿨다(m03: `ef_search` 1000에서도 정확 검색 1위 0.4177을 놓침). 같은 질문을 혼자 보낼 때와 묶어 보낼 때 임베딩은 코사인 1.0으로 같았다. `uv run --offline pytest -q` 11 passed.
- 확인 못 한 것: 동결 전 초안이라 베이스라인이 아니다. 서버 기동 때 `warmup()`을 부르는 연결과 그래프 노드 연결은 하지 않았다(D4). 리랭킹·필터 없음. 정확 검색이 Cloud Run·Supabase에서 얼마나 걸리는지 재지 않았다.
- 다음 할 일: 50건 동결 뒤 같은 명령으로 베이스라인, Supabase 적재, D3 리랭킹·필터 사전 등록.

## 2026-11-01 코퍼스 표와 임베딩 적재 (PR #17)
- 한 일: `db/02_rag_corpus.sql`로 코퍼스 표 3개(`source_documents`, `document_chunks`는 Migration 1 초안과 같은 정의에 `IF NOT EXISTS`, `chunk_embeddings`는 `vector(1536)`과 HNSW 코사인 인덱스)를 만들었다. `backend/rag/ingest.py` 뼈대 자리에 적재 코드를 넣었다. 임베딩은 본문 해시 캐시를 다시 쓰고 없는 본문만 `embed_texts`로 만든다(128개씩, 3회 재시도). 다시 돌리면 들어간 문서·청크·임베딩은 건너뛴다.
- 바꾼 파일: `db/02_rag_corpus.sql`, `db/DB.md`, `db/ERD.md`, `backend/rag/ingest.py`, `backend/rag/RAG.md`, `backend/rag/chunk.py`(설명 한 줄), `docs/specs/rag-pipeline.md`(단계 이름 index → ingest), `tests/test_rag_ingest.py`, `tests/TESTS.md`, 이 파일
- 실행한 명령과 결과: 로컬 compose DB(`sojafit-db-1`)에 SQL을 두 번 적용해 두 번째는 모두 건너뜀을 확인했다. api 이미지 컨테이너를 compose 네트워크에 붙여 `python -m backend.rag.ingest`를 돌리니 2분 5초에 문서 1,360, 청크 52,244, 임베딩 52,244행이 들어갔고 새 임베딩 호출은 0회(11-01 벡터 캐시 사용)였다. 다시 돌리면 넣은 행이 0이다. 첫 실행에서 행 이름이 500자를 넘는 청크 5개(면책 문구 표) 때문에 `row_label` VARCHAR(500) 오류가 나 트랜잭션 전체가 되돌려졌고, 이름표 열만 500자로 잘라 다시 넣었다. `uv run --offline pytest -q` 결과 8 passed in 0.49s.
- HNSW 인덱스 문제와 수정: 빈 표에 만든 HNSW 인덱스에 5만 행을 한꺼번에 넣은 상태에서 검색하니, 같은 질문("TSC 1N5817은 역전압을 몇 V까지 견뎌?")의 정확 검색 1위(1N5817, 거리 0.3452)를 놓치고 거리 0.4358 청크를 1위로 냈다(`hnsw.ef_search` 200에서도 같음). 다 넣은 뒤 인덱스를 다시 만들자 정확 검색과 상위 3개가 같아졌다. 그래서 `ingest`가 임베딩을 넣은 뒤 `REINDEX`를 한다(재적재 2분 27초). 그 뒤에도 관련 19문항의 상위 50개를 정확 검색과 비교하니 `ef_search` 100/400/1000에서 43%/79%/99%만 겹쳤다. 인덱스를 m 24·ef_construction 200으로 다시 만들어 본 측정은 100%로 나왔지만, 같은 인덱스에서 m03 질문 하나를 따로 보면 `ef_search` 1000에서도 정확 검색 1위(거리 0.4177)를 놓쳐 그 측정을 믿지 않고 인덱스 설정을 기본값으로 되돌렸다. 정확 검색은 질문당 0.33~0.55초다. 저장한 벡터는 11-01 벡터와 코사인 거리 최대 0.00000024로 같았다.
- 확인 못 한 것: Supabase에는 적용하지 않았다(조장 확인 뒤). 캐시에 없는 본문을 실제로 임베딩하는 경로는 이번 실행에서 돌지 않았다(11-01 실험의 같은 호출 방식으로 45,898개를 만든 적은 있다).
- 다음 할 일: PR #18(하이브리드 검색과 평가 실행기).

## 2026-11-01 수집·파싱·청킹 코드를 backend/rag로 옮기기 (PR #16)
- 한 일: 작업서 `docs/specs/rag-pipeline.md`와 SPEC 4절 검색 계약, 6절 청킹·검색 방식을 먼저 커밋했다. 저장소 밖 실험 스크립트(목록 합치기, PDF 받기, GPU 파싱과 두 방향 대조, 전체 청킹)를 `backend/rag/collect.py`·`parse.py`·`chunk.py`로 옮겼다. 표 청크 규칙은 Docling 없이 테스트하도록 순수 함수로 뗐다. Docling·pdfplumber는 uv 그룹 `ingest`로 추가했다. `data/manifest.jsonl`을 1,360건으로 다시 썼다.
- 바꾼 파일: `docs/specs/rag-pipeline.md`, `docs/specs/SPECS.md`, `SPEC.md`, `backend/rag/`(collect.py, parse.py, chunk.py, RAG.md), `tests/test_rag_chunk.py`, `tests/TESTS.md`, `pyproject.toml`, `uv.lock`, `data/manifest.jsonl`, `data/DATA.md`, `data/corpus/CORPUS.md`, 이 파일
- 실행한 명령과 결과: `collect list`가 11-01 목록 csv를 바이트까지 같게 다시 만들었고(PDF 1,360개), `collect download`는 1,360개 모두 이미 있어 건너뛰었다. `chunk`를 파서 비교용 도커 이미지(docling 2.145.0)에서 1,360건 전체에 돌려 5분에 청크 52,244개·서로 다른 본문 45,898개가 나왔고, 11-01 결과와 문서·순서·본문 해시·종류·쪽·표 제목이 모두 같았다. manifest는 1,360행, 쪽 합계 7,725, 저장소 표본 3건과 해시가 같다. `parse run`을 같은 이미지(CPU)에서 PDF 2건에 돌리니 표 수(5, 6)와 표 숫자 대조(81/81, 49/49)가 11-01 GPU 기록과 같았고, `parse recall`은 표 영역 원문 숫자 130개를 모두 찾았다. `uv export --no-dev`와 기본 설치에는 docling·pdfplumber·torch가 0개, `--group ingest`에는 3개다. `uv run --offline pytest -q` 결과 7 passed in 0.23s.
- 확인 못 한 것: 로컬 맥 가상환경에 `ingest` 그룹을 설치해 돌려 보지는 않았다(도커 이미지로 확인). PDF 받기는 새 파일 없이 건너뛰기만 확인했다.
- 다음 할 일: PR #17(코퍼스 표와 임베딩 적재), PR #18(하이브리드 검색과 평가 실행기).

## 2026-11-01 평가 문항 50건 초안과 1차 사람 판정
- 한 일: 기존 30건(관련 17, 비관련 13)에 Codex로 20건(관련 8, 비관련 12)을 더해 50건(관련 25, 비관련 25)을 만들었다. 출제와 정답은 Codex 세션 두 개로 나눴고, 정답 세션에는 출제 의도 필드를 지운 문항만 줬다. 정답의 숫자를 근거 페이지 원문과 기계로 대조하고 숫자형·비관련·판단형으로 나눈 검토표를 만들었다. 하정운이 50건 1차 판정을 마쳤고, 2차 판정은 김재훈이 11-02에 한다. 동결은 두 판정을 맞춘 뒤 50건을 v1로 한다.
- 바꾼 파일: `evals/draft_50.jsonl`, `evals/DRAFT_50_REVIEW.md`, `evals/EVALS.md`(파일 목록, 동결 계획), `README.md`·`SOJAFIT.md`(v1 50건), 이 파일
- 실행한 명령과 결과: 출제 Codex 6분·96,561토큰, 정답 Codex 5분·84,039토큰. 정답 세션의 관련/비관련과 비관련 종류가 20건 모두 출제 의도와 같았다. 기계 대조에서 원문에 없는 숫자는 오답 예시 1개(h03의 4.4)와 기준표 여유율 계산값 2개(n07의 214.3, n08의 714.3)뿐이었다. `draft_50.jsonl` 생성 스크립트의 자체 검사(50건, 관련 25, 비관련 4종, 관련 문항 근거 있음, 넷리스트 경로 있음) 통과. `uv run --offline pytest -q`는 3 passed.
- 확인 못 한 것: 2차 사람 판정 전이다. `gold_chunks`는 데이터시트 쪽·표·행과 넷리스트 위치이고 청크 id는 아직 붙이지 않았다. 출제·정답·대조 스크립트는 저장소 밖(`전자_데이터시트/evidence/eval50_codex/`)에 있다.
- 다음 할 일: 11-02 김재훈 2차 판정, 다른 문항 맞추기, 50건을 `dataset_v1.jsonl`로 옮겨 동결(11-03), 검색 베이스라인 점수.

## 2026-11-01 하이브리드 검색(BM25 + dense) 비교
- 한 일: 결과를 보기 전에 `evals/PREREGISTER.md` #4를 커밋하고, 개선 2 청크에서 검색 방식만 dense → 하이브리드(BM25 상위 50 + dense 상위 50, RRF k=60)로 바꿔 같은 11문항을 다시 쟀다. BM25만도 참고로 쟀다. `EVAL_REPORT.md` 1장에 결과를 적었다.
- 바꾼 파일: `EVAL_REPORT.md`, `evals/PREREGISTER.md`, `evals/results/hybrid_search_2026-11-01.json`, 이 파일
- 실행한 명령과 결과: `uv run --offline python ../전자_데이터시트/evidence/embed/hybrid_eval.py ../corpus/tsc/chunks <결과 json>`(BM25 색인 포함 6.4초). dense만 재실행은 0.727 / 0.568 / 0.364로 앞 결과와 같았다. 하이브리드는 문서 Recall@5 1.000, MRR 0.909, Page Hit@5 0.727, BM25만은 1.000 / 0.894 / 0.636이었다. 기대 5개 중 1개 맞음, 4개는 범위 위.
- 확인 못 한 것: 정답 근거는 사람 검토 전이고 문항이 11개뿐이다. 토큰 규칙과 RRF k는 하나만 써 봤다. 스크립트는 저장소 밖에 있어 재현 명령을 EVAL_REPORT 9장에 넣지 못했다.
- 다음 할 일: v1 동결 뒤 하이브리드를 기준선으로 다시 잰다. `backend/rag/retrieve.py`에 옮길 때 회로 기호(D1~D3)와 표시 코드가 겹치는 문제를 함께 본다.

## 2026-11-01 청킹 A·C 임베딩과 로컬 검색 비교
- 한 일: 전체 1,360건의 개선 전(A)·개선 2(C) 청크에서 서로 다른 본문을 `backend.services.llm.embed_texts`(`text-embedding-3-small`, 1536차원)로 임베딩하고 로컬 도커 pgvector(`sojafit-db-1`)의 실험 표 `exp_rag_chunks`에 넣었다. 결과를 보기 전에 `evals/PREREGISTER.md` #3에 기대를 적고 커밋했다. 비동결 초안 문항 중 데이터시트 근거가 필요한 11개로 상위 5개 검색을 비교해 `EVAL_REPORT.md` 1장에 적었다.
- 바꾼 파일: `EVAL_REPORT.md`, `evals/PREREGISTER.md`, `evals/results/chunking_search_2026-11-01.json`, 이 파일
- 실행한 명령과 결과: 임베딩 C 45,898개 5,391,648토큰(12.6분), A 10,723개 2,201,510토큰(3.1분), 재시도 0회. DB 행 수는 C 45,898, A 10,723으로 벡터 수와 같다. 문서 Recall@5 A 0.455 → C 0.727, MRR 0.321 → 0.568, C Page Hit@5 0.364. 사전 등록 기대 5개 중 4개 맞음, C Page Hit는 범위 아래.
- 확인 못 한 것: 정답 문서·쪽은 사람 검토 전 초안이다. 11문항이라 차이를 통계로 구별할 수 없다(부호 검정 양측 p=0.25). 비용은 대시보드가 아니라 단가로 계산했다. 임베딩·적재·검색 스크립트는 저장소 밖(`전자_데이터시트/evidence/embed/`)에 있고, `backend/rag/`로 옮길 때 넣는다.
- 다음 할 일: 품번이 정확히 맞는 청크를 찾도록 BM25나 품번 필터를 붙여 m05, h03, h04를 다시 본다. v1 동결 뒤 같은 비교를 다시 잰다.

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
