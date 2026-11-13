# 키 없는 첫 기동 점검 (G1 · G2) -- 커밋 574de79

2026-11-13 10:4x~11:0x KST. 강사가 라이브로 재는 흐름을 같은 순서로 한 번 미리 돌렸다. 코드 수정·커밋·푸시·배포 없음, 외부 API 호출 없음(`.env`와 키 전부 없음).

## 환경

| 항목 | 값 |
|---|---|
| 코드 | `origin/main` 574de79 (`git archive`로 뽑은 깨끗한 사본, `.env` 없음) |
| 호스트 | macOS, Apple M2 (arm64), Docker Desktop 29.7.2 (Engine 29.7.2), Compose v5.5.0 |
| Docker VM | 8 CPU, 메모리 약 3.8 GiB, aarch64 |
| 프로젝트 이름 | `sojafit-keyless-1113` (기존 `sojafit-db-1` · `marvia-v2-db-1` 컨테이너와 볼륨은 건드리지 않음) |
| 이미지 크기 | api 이미지 579.7 MB(`docker image inspect`) / `docker images`는 2.51 GB로 표시(Docker Desktop 표시값). 세 서비스(api · thread-setup · corpus-load)가 같은 이미지 id를 공유 |

## 호스트 쪽에서 바꾼 것 (사본 안에서만)

| 변경 | 이유 |
|---|---|
| `docker-compose.yml`의 `"8000:8000"` -> `"18000:8000"` | 호스트 8000을 다른 프로세스(python3)가 쓰고 있었다 |
| 로그인 단계부터 `DEMO_AUTH_ORIGIN=http://localhost:18000`로 api만 재생성(`up -d --no-deps --force-recreate api`) | compose가 `AUTH_ORIGIN`을 `http://localhost:8000`으로 고정해 둬서 포트가 다르면 `POST /api/auth/demo-login`이 Origin 검사로 403이었다 (실측). 8000을 쓸 수 있는 강사 환경에서는 필요 없다 |

## 명령과 시간

| 단계 | 명령 | 결과 |
|---|---|---|
| 빌드 | `docker compose build --no-cache` | 89.6 s (이미지 3개 모두 처음부터. 베이스 이미지 node:24-slim · python:3.12-slim · pgvector는 이미 로컬에 있었음 -> 베이스 pull 시간은 빠졌다) |
| 기동 | `docker compose up --build -d` (README는 `-d` 없는 `docker compose up --build`. 같은 동작, 로그만 파일로) | 명령 반환 7.8 s, `/health` 200까지 11.0 s (빌드 층 캐시 적중 상태) |
| 합계(근사) | 빌드 + 기동 | 약 100 s. G2 한도 10분 대비 여유 |
| 서비스 상태 | `docker compose ps -a` | db healthy, thread-setup · corpus-load Exited (0), api Up. corpus-load 적재 확인: source_documents 42 · document_chunks 1556 |
| 정리 | `docker compose down -v` (내 프로젝트만) | 컨테이너 · 네트워크 · 볼륨 제거, 남은 `keyless` 컨테이너 0 |

## 단계별 상태 · ms

curl 4단계는 직접 쟀고(`time_total`), 이후는 저장소의 `scripts/smoke/http_smoke.py --base-url http://localhost:18000 --demo --refusal`(README · SMOKE.md의 점검 스크립트)이 낸 값이다. 값은 로컬 1회 측정이다.

| # | 요청 | 상태 | ms |
|---|---|---|---|
| 1 | `GET /health` | 200 | 14 (smoke 7) |
| 2 | `GET /login` (화면 HTML) | 200 | 95 |
| 3 | `GET /api/auth/demo` (데모 버튼 표시 여부) | 200 | 3 |
| 4 | `POST /api/auth/demo-login` {"account":"a"} -- 화면의 "데모 사용자 A로 들어가기" 버튼이 부르는 API | 200 | 28 (smoke 9) |
| 5 | `GET /api/demo-circuits` (회로 15개) | 200 | 23 (smoke 8) |
| 6 | `GET /api/demo-questions` (기록 질문 10개) | 200 | 32 |
| 7 | 프로젝트 만들기(v3-01) `POST /api/projects` | 201 | 17 |
| 8 | thread 만들기 `POST /api/projects/{id}/threads` | 201 | 11 |
| 9 | 데모 질문 v3-01 `POST /api/threads/{id}/runs` (SSE: run_started > status > requires_input) | 200 | 185 |
| 10 | 조건 재개 `POST /api/runs/{id}/resume` (SSE: ... > completed) | 200 | 158 |
| 11 | 승인 `POST /api/messages/{id}/approvals` / 같은 승인 다시 | 201 / 409 ALREADY_APPROVED | 13 / 12 |
| 12 | 견적 저장 `POST /api/approvals/{id}/quotes` | 201 | 12 |
| 13 | 사용자 B의 A 자원 접근 6종 | 모두 404 | 9~11 |
| 14 | 거절 질문 v3-30 run | 200 (SSE ... > refused) | 104 |

smoke 합계: 통과 28 · 실패 0 · 건너뜀 0.

## 강사가 볼 것과의 차이 (한계)

- 빌드는 `--no-cache`로 층을 다시 만들었지만 베이스 이미지 3종은 이미 로컬에 있었다. 강사 PC에서 처음이면 pull 시간(node · python · pgvector 약 1.6 GB 규모)과 PyPI · npm 다운로드 속도가 더해진다. 이 값은 재지 않았다.
- 호스트 포트 18000을 썼다. 8000이 비어 있으면 compose 기본값 그대로 동작한다(Origin 문제도 없다).
- 브라우저 화면은 보지 않았다. 로그인 버튼이 부르는 API까지만 확인했고 React 화면 조작(질문 버튼 클릭, 두 창 격리)은 점검하지 않았다.
- x86(amd64) 호스트는 아니다. Apple Silicon(arm64) 네이티브 이미지였다. 강사가 x86이면 이미지가 달라진다.
- 시간은 호스트 부하(다른 컨테이너 sojafit-db-1 · marvia-v2-db-1 · neo4j 등이 동시에 떠 있음)에서 잰 1회 값이다.
- 재생 답은 기록한 질문 10개뿐이다(README §5). 새 질문은 422이므로 강사가 임의 질문을 하면 답이 나오지 않는 것이 정상 동작이다.
- api 로그의 "error|traceback" 문자열 9줄을 셌지만 내용은 `down -v` 전에 읽지 못했다(4xx 응답 로그로 추정, 확인 못 함). smoke의 의도한 404 · 409가 해당할 가능성이 크다.
