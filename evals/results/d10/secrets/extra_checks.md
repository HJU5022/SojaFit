# 추가 검사 (origin/main b5f050d, 값은 앞 4자까지만)

## 2d. .gitleaksignore/허용목록이 가리는 항목 (전부 generic-api-key, 1366건)
| 건수 | 파일:줄 (커밋) | 무엇 | 분류 |
|---|---|---|---|
| 986 | evals/results/embedding/grid_rerank_cache_2026-11-02.jsonl (key 필드) | 64자리 16진 sha256 해시 | 문서 예시 아님·비밀 아님(해시) |
| 360 | evals/results/threads/injection_baseline_live_2026-11-11_03.jsonl 240 + ..._human_jeongun.jsonl 120 (pair_key) | "baseline_t#_..:ablated" 식별자 | 비밀 아님(측정 ID). toml 주석은 "document_key 60건"이라 낡음 |
| 8 | docs/worklog/jeongun.md 줄 34,54,70,80 (현재) / 커밋 6a0015f 외 | `--to-revisions=sojafit-api-<커밋해시>` Cloud Run 리비전 이름 | 문서 예시 |
| 1 | evals/results/graph/memory_operations_2026-11-09.json:121 (ccadd3f) | "backend/auth.py": 64자리 SHA-256 | 파일 해시(.gitleaksignore 유일 항목) |
| 1 | backend/conversations/memory_service.py:109 (aeff44e) | '022_token_limits.sql','023_retention.sql' | 문서/코드 상수(파일명) |
| 7 | tests/api/test_auth.py 903,922,964,965,1004,1017 (36be8bf,f3918c3,d6b0b04) | password 값 'synt…'(18자) | 시험용 값(synthetic-) |
| 2 | tests/api/test_errors.py 73,226 (ee8808f) | password 'synt…' | 시험용 값 |
| 1 | tests/api/test_deletion.py:53 (799b325) | AUTH_SECRET 'isol…'(38자, isolated-) | 시험용 값 |
-> 실제 비밀로 보이는 것 0건. 첫 4자 기준 접두어: synt / isol / 5166(해시) / 022_ / sojafit-api.
-> 허용목록은 파일 전체를 제외(rerank cache, injection_baseline): 그 안의 실제 키는 gitleaks가 못 봄. 이를 보완하려고 아래 정규식 검사를 이 파일들 포함 전체에 실행해 0건 확인.
-> .gitleaksignore의 1건(ccadd3f:...memory_operations...:121)은 현재 규칙으로 실제로 걸림(무시 목록 없으면 1366, 있으면 1365 -> 허용목록 후 0).

## 3-1. .env.example
- 43줄 중 값 줄 43개: 빈 값(`NAME=`) 15개. 나머지 28개는 비밀 아님: 스위치(0/1), 숫자 한도, 공개 URL(cloud.langfuse.com, localhost:8000), `DATABASE_URL=postgresql://app:app..@localhost:5432/app`(로컬 docker 기본 계정, 자리표시), `SMTP_USERNAME=sender@example.test`(자리표시). 실제처럼 보이는 값 0개.

## 3-2. 위험 파일
- 현재 추적 목록과 origin/main 전 이력 추가(A) 파일 중 `.env`(실제), *.pem, *.key, credentials*.json, 서비스계정 JSON, id_rsa, .npmrc, *.sqlite, 덤프 = 0. 이름에 걸린 것은 `.env.example`뿐 (db/*.sql은 스키마 마이그레이션).
- 모든 ref(`--all`)로 봐도 `.env*`는 `.env.example`만.

## 3-3. 패턴 검색 (추적 파일 전체 + origin/main 전 이력의 추가된 줄)
| 규칙 | 결과 |
|---|---|
| sk-or- / sk-ant- / pa-(Voyage) / AIza / ghp_·github_pat_ / xox / JWT eyJ.eyJ / BEGIN PRIVATE KEY / AKIA / GOCSPX / 일반 sk- / Bearer / *_SECRET·TOKEN·KEY=긴값 | 0건 (파일, 이력 모두) |
| postgres://user:pw@ | 파일 12건/이력 15건, 전부 자리표시: docker-compose.yml:21,36,47, .env.example:39, tests/evals/test_judgement_bundle.py:57-59, tests/evals/test_injection_baseline.py:268 (test:test), tests/api/test_http_restart.py:10, scripts/db/verify_redesign/lib/rd_struct.py:11 (app:app 로컬), .github/workflows/ci.yml:29,30 (ci_auth, CI 서비스 DB) |
| pk-lf-/sk-lf- | tests/services/test_service_trace.py:59,61, tests/services/test_langfuse_prompts.py:125,126,376,377,379 — 시험용 가짜 키(base_url example.invalid) |
| Supabase 프로젝트 ref `[a-z]{20}.supabase.co` | docs/worklog/sth.md:1425 한 곳(20자, 값 가림) + 이력 같은 곳. 프로젝트 식별자이며 키 아님. 공개해도 키 없이는 접근 불가하지만 주소 노출 [추정] |
| Cloud Run URL의 GCP 프로젝트 번호(12자리) | README.md:13,21, docs/worklog/sth.md:948,963,977, scripts/SCRIPTS.md:69, docs/GATES.md, scripts/results/smoke/*.json — 공개 배포 주소 자체. 비밀 아님 |
| gcp-number 정규식 182건·한국 전화번호 정규식 58건 | 거의 전부 오탐: 16진 해시 안 숫자(chunk_sha256.tsv 38, uv.lock 6, 측정 jsonl), 데이터시트 바이너리 문자열(c02-fc-rom-vomitter.net 88), langfuse trace id. 실제 전화번호 0 (이력 포함) |
| 이메일(자리표시 제외) | 파일 5: tests/projects/test_external_circuit_search.py:29 (u@github.com, URL 시험), tests/mcp_skill/test_mcp_server.py:169 (pw@..taiwansemi URL 시험), docs/worklog/jeongun.md:79 (데모 계정 2개 gmail, 아래), data/circuits/collected/received-20261030/c09/original/README.md:68 (제3자 오픈소스 README의 연락처). 이력 한정: docs/GATES.md·EVAL_REPORT.md에 데모 계정 2개 및 개발용 gmail 주소(앞 부분 가림, 6a0015f, 5f0cc7e) — 현재 파일에는 없음; docs/specs/login-auth.md 3152ffc 발신 주소 후보(앞 부분 가림, 사용 전 주소) |

## 3-4. "평가용 계정"
- README.md:286: "평가용 계정은 저장소에 적지 않고 강사에게 따로 제출한다."
- docs/worklog/jeongun.md:79: 데모 계정 이메일 2개(gmail 주소, 줄에 `demo` 계정 두 개) + "비밀번호는 기록하지 않음". 이메일만, 비밀번호 없음. 이 계정이 평가용 계정과 같은지는 확인 못 함 [추정: 같을 가능성].
- 같은 이메일이 이력에서 docs/GATES.md(커밋 2501e1c, 73ef606, 6a0015f, 41b407f 등)에도 있었음: 이메일만. 데모 이메일 옆 비밀번호 값: 전 이력 0건 (정규식으로 demo[12]@ 줄 대조).
- 데모 모드 버튼 계정(demo-a/demo-b)은 비밀번호 없음(README:186).

## 3-5. docs/research/evidence/** (2.0MB, 파일 10개: md 2, json 8)
- job-postings/*.json (공고 237건 합본, 원티드·점핏·사람인·잡코리아·회사 채용페이지): 회사명, 직무명, 공고 URL, 경력·마감 등. 이메일·전화·채용담당자 이름 0. 필드에 사람 이름 칸 없음.
- corpus/manifest_*.json: 공개 문서/데이터시트 조각 수 실측, 공개 레포 URL(espressif, zephyrproject-rtos, raspberrypi, arduino), 라이선스 해시. 개인정보 0.
- netlist/manifest_diodes.json (495KB): raw.githubusercontent.com 공개 URL 216개, 공개 GitHub 소유자 핸들 143개. `@` 0개. 공개 핸들만.
- 모든 evidence 파일의 `@` 개수 0.
