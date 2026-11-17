# 필수 게이트 자기 점검

- 상태: 현행
- 기준일: 2026-11-17(배포 리비전 측정: v3 50문항 2세트 · 25단계, 대상 `main` `2030f846` = 운영 리비전 `sojafit-api-pre-ef0138b2-rs`. 그 전 11-17 새벽 재측정은 [evals/results/d12/](../evals/results/d12/README.md), 대상 `799ae636`)
- 동결: 채점 기준 `9c87ba36`(11-16 24:00). 최종 동결 태그 `final-2026-11-17`(11-17 레포 정리 커밋 `a468c0ba`. 배포 소스 `2030f846`과 비교해 서비스 코드는 주석만 다르고, 측정 스크립트 2개(`scripts/smoke/http_smoke.py` `allow_duplicate`, `evals/runners/run_skill_pair.py` `--max-seconds`)가 바뀌었다). 그 뒤 발표 폴더(PR #162), 랜딩 그림 4장(`b4a02113`, PR #163), 제출물 검수에서 찾은 문서 · 주석 정리, 큰 파일 주석 보강, 쓰지 않는 prop · 중복 함수 2곳 삭제(동작 같음, 배포하지 않음)만 바꿨고 태그는 옮기지 않았다. 그 전 태그 `freeze-2026-11-17`(PR #150)도 옮기지 않았다.
- 기준 커밋: `2030f846`(`main`, PR #160 병합). 운영 리비전과 그 소스는 [README.md](../README.md) 표 「배포 리비전」이 정본이다(11-17 20:45 KST `sojafit-api-pre-b4a02113-1117`, 서비스 동작에서는 랜딩 그림 4장만 다름(그 밖은 주석 · 측정 스크립트, 위 「동결」 줄). 측정은 그 전 19:52 `sojafit-api-pre-ef0138b2-rs` · 19:27 `sojafit-api-pre-ef0138b2-1117`(같은 이미지)에서 했다).
- 정본 여부: 정본(게이트 증거). 배포 리비전은 비정본(정본: [README.md](../README.md) 맨 위 표). 게이트 정의의 정본은 3차 프로젝트 가이드
- 관련 문서: [README.md](../README.md), [SPEC.md](../SPEC.md), [EVAL_REPORT.md](../EVAL_REPORT.md), [evals/results/d10/README.md](../evals/results/d10/README.md), [mutation_2026-11-13.md](../evals/results/d10/mutation_2026-11-13.md), [secret_scan_2026-11-13.md](../evals/results/d10/secret_scan_2026-11-13.md), [startup_restart_isolation_2026-11-13.md](../evals/results/d10/startup_restart_isolation_2026-11-13.md)

게이트는 점수가 아니라 못 지키면 고정으로 깎이는 조건이다. 가산점은 7개를 모두 충족한 조만 받는다. 이 문서는 게이트마다 상태, 증거 경로, 확인 못 한 것을 적는다. 외부 DB · 배포 · 대시보드의 날짜가 적힌 결과는 그 시점의 스냅샷이다. G2 · G4의 2026-11-13 측정은 `jeongun-2` @ `ad8612e`(트리 `6452cdfc4188942e62b1be7e2eb73c55094c3b97`)에서 했다. `main` `ea5797c`(PR #115 · #116 병합, 2026-11-13 05:31 KST)의 트리가 같으므로 그 측정은 `main` 파일의 기록이다.

## 상태 표기

`미착수` / `진행 중` / `충족` / `증거 보강 필요` 중 하나로 적고, 충족이면 증거 링크(파일, PR, 대시보드)를 같이 적는다. 링크 없는 충족은 인정되지 않는다.

## 게이트 표

| 게이트 | 증명하는 곳 | 평가자가 확인하는 방법 | 상태 |
|---|---|---|---|
| G1 배포 주소 | README 맨 위 표의 배포 주소 | 평가용 계정으로 접속해 핵심 시나리오를 끝까지 본다 | 충족 (11-17 19:56 운영 리비전 `sojafit-api-pre-ef0138b2-rs`에서 평가용 계정 A · B 25단계 점검(재시작 단계 제외 24개) **24/24**(업로드 · 질문 · 조건 질문 멈춤 · 재개 · 판정 · 승인 · 같은 승인 409 · 견적 저장 · 목록 · 계정 B의 A 자원 7개 모두 404), 재시작 뒤 재개는 19:50 실행에서 통과(G4), 결과 [smoke_…_2026-11-17_195638.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-17_195638.json). 그 전 11-13 `574de79-rs`, [deploy_574de79](../evals/results/d10/deploy_574de79/README.md)) |
| G2 한 줄 기동 | `docker-compose.yml`, `.env.example`, 데모 모드 | 새 clone에서 `docker compose up`, 10분 안에 뜨는지 실측 | 충족 (기준 600초: 11-17 `main` `799ae636` 새 clone → `/health` 200 6회 중앙값 239.4초(148.9 ~ 296.0), 스모크 6회 모두 28/28, 원시 로그 [d12/boot](../evals/results/d12/README.md). 11-16 `3ce5abdc` 1회 242.8초. 한계는 G2 절) |
| G3 코퍼스 | `data/manifest.jsonl`, `data/corpus/` | 서로 다른 청크(본문 sha256 기준) 1만 개 이상, 문서 50건 이상, 파싱 1종 이상 | 충족 (운영 DB 청크 본문 51,967개를 직접 열어 다시 계산한 sha256이 모두 서로 다르고 저장소 해시 목록과 같다(11-16, [db_content_hash_check](../evals/results/d10/db_content_hash_check_2026-11-16.md)), 문서 1,360, 파싱 Docling + pdfplumber. 한계는 G3 절) |
| G4 에이전트 | `backend/graph/`, `backend/multi_agent/`, `backend/auth.py`, `backend/graph/memory.py` | 코드와 시연. 평가용 계정 2개로 대화와 기억이 섞이지 않는지 | 충족 (11-17 운영 리비전에서 조건 질문으로 멈춘 뒤 서버 재시작(같은 이미지의 새 리비전 `sojafit-api-pre-ef0138b2-rs`로 트래픽 이동, 19:52) → 재개 → 판정 완료 통과, [smoke_…_2026-11-17_195049.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-17_195049.json)(이 회차는 B 비밀번호 입력 실수로 B 단계 401 · 건너뜀, B 격리는 19:56 회차에서 통과). 그 전 11-13 [deploy_574de79](../evals/results/d10/deploy_574de79/README.md). 시연 영상은 G7) |
| G5 평가 | `evals/`, `EVAL_REPORT.md` 2장, 3장 | 평가셋 50건 이상(동결 시점 기준, 관련과 비관련 각각 절반), 개선 전후 두 번 이상, 차이는 문항 목록과 함께 | 충족 (v3 50건 동결 · 개선 전후 3-A ~ 3-D · 달라진 문항 목록, [EVAL_REPORT.md](../EVAL_REPORT.md) 2 · 3절, `evals/results/graph/2026-11-12-d9-improve2/set1.json` 50/50(`DEMO_MODE` 미기록). 11-17 배포 리비전 코드(`2030f846`) 웹 켬 2세트 50/50 · 49/50(실패 v3-41 지어낸 답 1, [2026-11-17-deploy-ef0138b2-v3](../evals/results/graph/2026-11-17-deploy-ef0138b2-v3/report.txt)). 그 전 새벽 `799ae636` 49/50 · 49/50([d12](../evals/results/d12/README.md)). 원시 미보관 항목은 12장, 확인 못 한 것은 아래 G5. 응답 시간 p95 10초는 일부 조건에서만 충족: 8.2절) |
| G6 트레이스 | Langfuse 프로젝트, `EVAL_REPORT.md` 7장 | 대시보드에서 트레이스와 평가 점수가 연결되어 있는지 | 충족 (점수 연결은 API로 확인(11-17: 트레이스 4,109개에 점수 57,198개, [d12](../evals/results/d12/README.md)). 화면은 7장: 11-13 배포본 트레이스 3장, 11-17 배포 리비전 코드 v3 실행의 RAGAS 점수 트레이스 상세 · 점수 탭, Spec · RAG 두 에이전트 Timeline, 홈 대시보드 4장([langfuse/](deliverables/langfuse/) `04` ~ `07`)) |
| G7 제출물 | README, `.env.example`, `docs/deliverables/` | 비밀값 커밋 없음, 3분 이내 시연 영상(정상 경로와 실패 경로) | 충족 (비밀값: gitleaks 1,250 커밋 0건(11-17). 시연 영상 [sojafit-demo-2026-11-17.mp4](deliverables/video/sojafit-demo-2026-11-17.mp4) 4분 49초, 정상 경로 3 + 실패 경로 2(운영 리비전 녹화, 필수 제출 목록의 5분 이내, 가이드 G7의 3분은 넘는다). 포트폴리오 3건 · AI 도구 기록 있음) |

## 게이트별 증거

### G1 배포 주소

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 배포 리비전 | [README.md](../README.md) 표 | `docs/worklog/jeongun.md` 11-13 항목 |
| 이전 리비전 `sojafit-api-main76fadcb4-1116`(소스 `76fadcb4`, 2026-11-16 04:07 ~ 04:36 KST)과 `sojafit-api-main7ba86325-1115`(소스 `7ba86325`, 11-15 22:29 ~ 11-16 04:07 KST, KiCad 렌더러 분리: `KICAD_RENDERER_URL` 설정). 지금 리비전은 README 「배포 리비전」 칸 | 리비전 이름은 `gcloud run revisions list`로 확인했다(11-16 04:37 KST). 두 리비전 모두 로그인 뒤 25단계 점검 기록은 없다(확인 못 함) | [README.md](../README.md) 표 |
| 운영 시작 실패와 복구(2026-11-14 22:43 ~ 11-15 21:26 KST) | Secret Manager `EXA_API_KEY` 버전 1이 파기(DESTROYED)됐는데 서비스 설정이 그 버전을 고정해, 최소 인스턴스 0대인 운영 리비전 `574de79-rs`의 새 인스턴스가 시작하지 못했다(21:22 KST `/health` · `/login` · `/` 500). 같은 이미지에 `EXA_API_KEY:2`만 바꾼 리비전 `sojafit-api-574de79-exa2`를 21:26 KST에 100%로 돌려 복구했고, 22:29 KST에 위 현재 리비전으로 바꿨다. 누가 · 왜 버전 1을 파기했는지는 확인하지 못했다 | `docs/worklog/jeongun.md` 11-15 항목 「운영 다운 복구」 |
| 리비전 `sojafit-api-main-799ae636-1117`(소스 `main` `799ae636`, 11-17 04:52 ~ 06:07 KST 운영) 로그인 없는 점검(2026-11-17 05:03 KST). 그 뒤 운영 `sojafit-api-main-28b14600-1117`(PR #148)도 06:06 ~ 06:07 KST 같은 GET 점검 200 · 401, 오류 로그 0 | `gcloud run services describe`(읽기만)로 트래픽 100% 확인. `/health` 200(0.09초), `/login` · `/` · `/app` 200, `/api/auth/me` 401, `/openapi.json` 동작 53 · 경로 42(코드 전체 동작 60 · 경로 49 중 문서에 보이는 것, [routes.txt](../evals/results/d12/checks/routes.txt)). 로그인 뒤 25단계는 하지 않았다 | [unauth_checks.txt](../evals/results/d12/prod_unauth/unauth_checks.txt) |
| 경보 설정 재조회(2026-11-17 04:55 KST, 읽기만) | 가동 확인 1개(`sojafit-api /health`, 5분 주기, 2xx만 통과, 6개 지역)와 경보 정책 1개(`SojaFit 운영 다운: /health 가동 확인 실패`, 켜짐, 메일 채널 1개)가 있다. 11-16 09:41 ~ 11-17 04:55 KST의 `uptime_check/check_passed` 시계열 점 8,292개(6개 지역)가 모두 참이었다(거짓 0). 새로 만들거나 바꾼 것은 없다 | [monitoring/](../evals/results/d12/monitoring/) |
| 운영 다운 경보(2026-11-16) | 위 다운을 사람이 발견한 뒤 Cloud Monitoring에 `/health` 가동 확인(5분 주기, 2xx만 통과)과 경보 정책(실패 지역이 1개를 넘으면 메일)을 걸었다. 일부러 401을 주는 임시 확인으로 시험해 09:43:30 KST에 경보가 OPEN 되는 것을 API로 확인하고 임시 설정은 지웠다. 메일 도착 · 실제 다운 발령은 확인하지 않았다 | [alerting_2026-11-16.md](../evals/results/d10/alerting_2026-11-16.md) |
| 리비전 `sojafit-api-574de79-rs`(소스 `main` `574de79`, 2026-11-13 12:07 KST 100% 전환, 11-15 21:26 KST까지 100%) 평가용 계정 25단계 | 배포 서버 · 실제 모델로 평가용 계정 A · B 로그인 200, 넷리스트 업로드, 판정 질문, 조건 질문에서 멈춤, 서버 재시작(같은 이미지 다이제스트의 새 리비전), 같은 run 재개 200, 승인, 같은 승인 409, 견적, 계정 B의 접근 404. 통과 25 · 실패 0 · 건너뜀 0. 환경변수 32개(`EXA_WEB_SEARCH_ENABLED=1` 포함). 재개 요청을 이 리비전이 처리한 것은 서버 로그로 확인했다. 이 리비전은 `574de79`의 설정 그대로다 | [deploy_574de79/README.md](../evals/results/d10/deploy_574de79/README.md), [서버 로그 발췌](../evals/results/d10/deploy_574de79/restart_server_log_2026-11-13.txt), [smoke_..._2026-11-13_120624.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-13_120624.json) |
| 리비전 `sojafit-api-574de79`(소스 `main` `574de79`) 로그인 없는 점검 | 2026-11-13 10:53 KST: `/health` 200(0.11초), `/login` 200, `/app` 200, `/openapi.json` 200 · 동작 41 · 경로 34, `/api/auth/me` 401, `/api/auth/demo-login` 404(`DEMO_MODE=0`) | [unauth_checks_raw.txt](../evals/results/d10/deploy_574de79/unauth_checks_raw.txt) |
| 리비전 `sojafit-api-fadde2a`(소스 `main` `fadde2a`, 2026-11-13) 인증 없는 점검 | 소스를 `git archive origin/main`으로 올려 `--no-traffic --tag main-fadde2a --revision-suffix fadde2a`로 만든 뒤(빌드 08:12~08:17 KST, 이미지 `sha256:95d6f571…`) 0% 점검 주소에서: `/health` 200(냉 기동 11.1초), `/login` 200, `/app` 200, `/openapi.json` 200 · 동작 41 · 경로 34(전환 전 공개 서비스와 같음), `/api/auth/me` 401(로그인 없음), `/app`이 가리키는 주 JS 번들(`/assets/index-BFnytjKy.js`)에 `모두 모름으로 계속` · `원하는 정격도 적어 주세요` 문구가 둘 다 있음(새 화면이 이미지에 들어갔다), 오류 로그(심각도 ERROR 이상, 10분) 없음. 08:17 KST에 100% 전환. 공개 주소: `/health` 200(0.13초), `/login` 200, `/app` 200, `/api/auth/me` 401, `/openapi.json` 동작 41 · 경로 34, 같은 번들 문구 둘 다 있음, 응답 헤더 `x-content-type-options: nosniff` · `x-frame-options: DENY` · `strict-transport-security: max-age=31536000`. 환경변수는 지정하지 않아 서비스의 기존 설정을 그대로 이었다. 측정 커밋 `ad8612e`와 `fadde2a` 사이에서 `backend`, `db`, `Dockerfile`, `docker-compose.yml`, `pyproject.toml`, `uv.lock`, `frontend/package.json`, `frontend/package-lock.json`의 `git diff --stat`은 비어 있다. `ae3de0b`와 `fadde2a` 사이에는 `frontend/src` 2개 파일(예시 질문 · 안내 문구)과 문서만 바뀌었다. 이전 100% 리비전 `sojafit-api-ae3de0b`(11-13 08:07 KST 전환)가 되돌릴 대상이다 | `docs/worklog/jeongun.md` 11-13 항목 |
| 리비전 `sojafit-api-ae3de0b`(소스 `main` `ae3de0b`, 2026-11-13) 인증 없는 점검 | 소스를 `git archive origin/main`으로 올려 `--no-traffic --tag main-ae3de0b --revision-suffix ae3de0b`로 만든 뒤(빌드 08:02~08:07 KST, 이미지 `sha256:618ad9a5…`) 0% 점검 주소에서: `/health` 200(냉 기동 12.3초), `/login` 200, `/app` 200, `/openapi.json` 200 · 동작 41 · 경로 34(전환 전 공개 서비스와 같음), `/api/auth/me` 401(로그인 없음), `/app`이 가리키는 주 JS 번들(`/assets/index-BvxFKySW.js`)에 `모두 모름으로 계속` 문구 있음(새 화면이 이미지에 들어갔다), 오류 로그(심각도 ERROR 이상, 10분) 없음. 08:07 KST에 100% 전환. 공개 주소: `/health` 200(0.09초), `/login` 200, `/app` 200, `/api/auth/me` 401, `/openapi.json` 동작 41 · 경로 34, 같은 번들 문구 있음, 응답 헤더 `x-content-type-options: nosniff` · `x-frame-options: DENY` · `strict-transport-security: max-age=31536000`. 환경변수는 지정하지 않아 서비스의 기존 설정을 그대로 이었다. `c9d2c36`과 `ae3de0b` 사이에서 `backend`, `Dockerfile`, `docker-compose.yml`, `db`, `pyproject.toml`, `uv.lock`, `frontend/package.json`, `frontend/package-lock.json`의 `git diff --stat`은 비어 있고 `frontend/src`(와 문서)만 바뀌었다: 질문 바로 시작 · 답변 전체 마크다운 표시 · 이전 답 유지 · 조건 질문 '모름' 처리 · 사용자 화면의 오류 코드 · 요청 ID 숨김 | `docs/worklog/jeongun.md` 11-13 항목 |
| 이전 리비전 `sojafit-api-c9d2c36`(소스 `main` `c9d2c36`, 2026-11-13) 인증 없는 점검 | 소스를 `git archive origin/main`으로 올려 `--no-traffic --tag main-c9d2c36 --revision-suffix c9d2c36`로 만든 뒤(빌드 07:34~07:38 KST, 이미지 `sha256:9c180b82…`) 0% 점검 주소에서: `/health` 200(냉 기동 13.7초), `/login` 200, `/openapi.json` 200 · 동작 41 · 경로 34(전환 전 공개 서비스와 같음), `/api/auth/me` 401(로그인 없음), 오류 로그(심각도 ERROR 이상, 10분) 없음. 07:39 KST에 100% 전환. 공개 주소: `/health` 200(0.09초), `/login` 200, `/api/auth/me` 401, `/openapi.json` 동작 41 · 경로 34, 응답 헤더 `x-content-type-options: nosniff` · `x-frame-options: DENY` · `strict-transport-security: max-age=31536000`. 환경변수는 지정하지 않아 서비스의 기존 설정을 그대로 이었다. `ea5797c`와 `c9d2c36` 사이 서비스 코드(`backend`, `frontend`, `Dockerfile`, `docker-compose.yml`, `db`, `pyproject.toml`, `uv.lock`)의 `git diff --stat`은 비어 있다 | `docs/worklog/jeongun.md` 11-13 항목 |
| 이전 리비전 `sojafit-api-ea5797c`(소스 `main` `ea5797c`, 2026-11-13) 인증 없는 점검 | 소스를 `git archive`로 올려 `--no-traffic --tag main-ea5797c`로 만든 뒤 0% 점검 주소에서: `/health` 200(냉 기동 12.1초), `/login` 200, `/openapi.json` 동작 41 · 경로 34, `/api/demo-circuits` · `/api/auth/me` 401(로그인 없음), 오류 로그 없음. 05:38 KST에 100% 전환. 공개 주소: `/health` 200(0.15초), `/login` 200, `/api/auth/me` 401, 응답 헤더 `x-content-type-options: nosniff` · `x-frame-options: DENY` · `strict-transport-security`. 환경변수 30개는 이전 리비전과 같다(`DEMO_MODE=0`, `GOOGLE_AUTH_ENABLED=1`, `THREADS_ENABLED=1`, DB 비밀 `DATABASE_URL_NEW`). Exa 변수가 없어 `/api/external-circuits`는 비활성이다(`EXA_WEB_SEARCH_ENABLED=1`과 `EXA_API_KEY`가 없으면 설정 오류, `backend/projects/external_schematic.py:213`) | `docs/worklog/jeongun.md` 11-13 항목 |
| 이전 리비전 `sojafit-api-e0a5e30`(2026-11-12)에서 측정 | `/health` 200, 가입 · 데모 로그인 404(`DEMO_MODE=0`). 인증 통합 PR #109(커밋 `3152ffc`)는 이 리비전보다 뒤라, 이후 코드는 `POST /api/auth/signup`을 `DEMO_MODE`로 막지 않는다([SPEC.md](../SPEC.md) 4절) | `docs/worklog/jeongun.md` 11-12 항목 |
| 새 DB 전환 후 스모크(2026-11-11, 리비전 `sojafit-api-27a410d-live`) | 0% 점검 주소 28/0/0(통과/실패/건너뜀), 100% 전환 뒤 기본 주소 28/0/0. 구글 로그인 실제 왕복 확인. DB는 새 Supabase 프로젝트(서울, Postgres 17.11), 기준선 SQL과 코퍼스 4표(청크 51,967행)만 이전 | [smoke_newdb---sojafit-api-q5lzmlc4wq-du.a.run.app_2026-11-11_041537.json](../scripts/results/smoke/smoke_newdb---sojafit-api-q5lzmlc4wq-du.a.run.app_2026-11-11_041537.json), [smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_042439.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_042439.json) |
| 같은 날 앞선 두 실행 | 2/4/22, 19/1/8. B 계정 비밀번호 입력 문제로 실패(서비스 문제 아님) | [_042105.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_042105.json), [_042119.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_042119.json) |
| 옛 DB 기준(2026-11-10) 배포 주소 점검 | 리비전 `sojafit-api-b884849` 23단계 통과 · 실패 0 · 건너뜀 0(31.0초, 실제 LLM): 로그인 → 데모 회로 프로젝트(v3-01) → 조건 질문 정지 → 재개 → 승인 201 · 같은 승인 409 → 견적 → 계정 B의 A 자료 404 → 범위 밖 질문 거절 | [..._2026-11-10_225316.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-10_225316.json) |
| 같은 날 28단계 재점검 | 리비전 `sojafit-api-716c6d6`, 28/0/0. 승인 · 견적 · 승인 사례까지 계정 격리 확인 | [..._232639.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-10_232639.json), [..._232814.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-10_232814.json) |
| 되돌리기 리비전 | `sojafit-api-c9d2c36`(소스 `main` `c9d2c36`, 2026-11-13 07:39 KST 전환부터 08:07 KST 전환 전까지 100%). 명령: `gcloud run services update-traffic sojafit-api --project sojafit --region asia-northeast3`에 `--to-revisions` 옵션으로 이 리비전을 100% 지정한다(이름은 `sojafit-api-` 뒤에 `c9d2c36`) | `docs/worklog/jeongun.md` 11-13 항목 |
| 그 앞의 되돌리기 리비전 | `sojafit-api-ea5797c`(2026-11-13 05:38~07:39 KST 100%) | `docs/worklog/jeongun.md` 11-13 항목 |
| 11-11 시점의 되돌리기 리비전 | `sojafit-api-716c6d6`(옛 DB 비밀 사용) | `docs/worklog/jeongun.md` 11-11 항목 |
| 배포 Mouser 키 | 없음. 가격 조회는 `available:false` | 11-10 점검 기록. 11-13 리비전 설정에도 `MOUSER` 변수가 없다 |

확인 못 한 것:

| 항목 | 이유 |
|---|---|
| 리비전 `ea5797c` · `c9d2c36` · `ae3de0b` · `fadde2a`의 로그인 뒤 시나리오 | 그 리비전들에서는 하지 않았다. `574de79`에서 25단계로 했다(위 표). 25단계 스모크는 `--upload`로 실제 업로드 경로를 쓴다. 11-11 28단계 스모크의 데모 회로(v3-01) 시작은 `DEMO_MODE=0` 배포에서 404라 같은 방식으로는 재현되지 않는다. 평가용 계정은 레포에 두지 않는다 |
| 배포 서버 재시작 뒤 재개 | `574de79`에서 했다(위 표 · G4). 한계: 체크포인트 행을 직접 대조하지 않았고 근거는 이벤트 순서와 시간(재개 3초 대 처음 19초)이다. 이전 리비전들에서는 하지 않았다 |
| Google 로그인 왕복 · 이메일 가입 왕복 | `574de79`를 포함해 11-13 리비전들에서 하지 않았다. Google 왕복은 11-11 리비전 `27a410d-live`에서만 확인했다 |
| 서버 로그의 Langfuse `Failed to export spans 403 Forbidden` | 원인을 찾았다: 옛 Langfuse 프로젝트의 키가 거부당했고, 11-12 12:29 KST에 새 프로젝트 키로 바꾼 뒤 실패 로그가 없다([langfuse_403_2026-11-13.md](../evals/results/d10/langfuse_403_2026-11-13.md)). 옛 프로젝트가 거부한 이유(사용량 한도인지 정지인지)는 그 계정 화면을 못 봐 확인하지 못했다 |

### G2 한 줄 기동

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 키 없는 첫 기동 사전 점검(2026-11-13, `main` `574de79`의 `git archive` 사본, `.env` 없음, Apple M2 Docker Desktop) | `docker compose build --no-cache` 89.6초, `up --build -d` 반환 7.8초 · `/health` 200까지 11.0초(빌드 층 캐시 적중), 합계 약 100초. db healthy, thread-setup · corpus-load 정상 종료, 적재 문서 42 · 청크 1,556. 호스트 8000 포트 충돌로 사본에서만 18000으로 바꿨다 | [keyless_boot_574de79.md](../evals/results/d10/keyless_boot_574de79.md) |
| 배포본의 평가용 계정 로그인(`574de79`, 2026-11-13) | 평가용 계정 A · B 로그인 200(0.96초 · 0.85초). 로컬 기동과 별개로 배포 주소에서의 로그인이다 | [deploy_574de79/README.md](../evals/results/d10/deploy_574de79/README.md) |
| 현행 측정(2026-11-17, GitHub `main` clone → `799ae636` checkout, 6회) | 회차마다 새 빈 `docker:dind`(29.9.3), `.env` 없음 · 키 없음, `docker compose up --build`. clone 시작 → `/health` 200: 266.3 · 296.0 · 244.5 · 234.3 · 148.9 · 207.6초(중앙값 **239.4초**), `up` → `/health` 중앙값 231.4초, 스모크 `--demo --refusal` 6회 모두 28 통과 · 0 실패 · 0 건너뜀, 내려받은 양 591 ~ 594 MB. 같은 호스트에서 다른 작업이 함께 돌아 1분 부하 4.95 ~ 14.70(시간 차이는 부하 탓, 코드 차이 아님). 1회차 dind에서 CI 재생 검사(기록 질문 10개)도 "기록과 같음" | [d12 README](../evals/results/d12/README.md) 「새 clone 기동」, 회차별 [run1](../evals/results/d12/boot/run1/) ~ run6 · [summary.json](../evals/results/d12/boot/summary.json), [replay_check.txt](../evals/results/d12/checks/replay_check.txt) |
| 빈 엔진 6회 표(11-13 ~ 14, `docs/research/docker-cold-start-measurements.md` 1 · 4절)의 원시 | 회차별 값 · 단계 시각은 저장소에 있다: [scripts/results/docker_performance/](../scripts/results/docker_performance/)(`profile_lazyload_six_run_*` · `kicad_in_api_vs_renderer_split_*`). compose · 빌드 원시 로그는 실험 PC에만 있다(그 문서 7절). 그 표는 Engine 27.5.1의 `up` → `/health`라 위 dind 측정(clone 시작 기준)과 다른 계열이다 | [d12 README](../evals/results/d12/README.md) 「빈 엔진 기동 6회 측정의 원시 로그」 |
| 현행 측정(2026-11-16, GitHub `main` `3ce5abdc`) | 빈 `docker:dind`(29.9.3)에서 새 clone, `.env` 없음 · 키 없음, `docker compose up --build`. clone 시작 → `/health` 200 **242.8초**, → 스모크 끝 251.4초, 스모크 `--demo --refusal` 28 통과 · 0 실패 · 0 건너뜀. 내려받은 양 585 MB. 호스트 부하가 높은 때(1분 평균 10)였다 | [boot_2026-11-16/README.md](../evals/results/d10/boot_2026-11-16/README.md) |
| 현행 측정(2026-11-13, `jeongun-2` @ `ad8612e` = `main` `ea5797c`과 같은 트리 `6452cdfc…`) | 빈 `docker:dind`(29.9.3)에서 새 clone, `.env` 없음 · 키 없음, `docker compose up --build`. 냉: clone 시작 → `/health` 200 243.9초, `up` → `/health` 200 235.5초, `up` → 스모크 종료 243.1초, clone 시작 → 스모크 종료 251.6초(clone 8.4초). 온(`down -v` 뒤): `up` → `/health` 200 11.7초, → 스모크 종료 19.0초. 스모크 `--demo --refusal` 28 통과 · 0 실패 · 0 건너뜀(냉 · 온). 내려받은 양 852 MB(냉) | [startup_restart_isolation_2026-11-13.md](../evals/results/d10/startup_restart_isolation_2026-11-13.md), [timeline_cold.json](../evals/results/d10/boot/timeline_cold.json), [timeline_warm.json](../evals/results/d10/boot/timeline_warm.json), [smoke_cold.json](../evals/results/d10/boot/smoke_cold.json), [smoke_warm.json](../evals/results/d10/boot/smoke_warm.json) |
| 시간이 늘어난 이유 | 시간은 이미지 빌드가 정한다(빌드 202.2초: `apt-get install kicad libcairo2` 70.0초, 이미지 내보내기 65.9초, `uv sync` 48.6초, `npm ci` 45.4초, 일부 겹침). `kicad libcairo2` 설치는 커밋 `e928d59`(11-11)가 `Dockerfile`에 넣었고 아래 11-10 측정은 그 전이다. 11-10과의 차이를 단계별로 나누어 재지는 않았다. 이미지 2.51 GB | [timeline_cold.json](../evals/results/d10/boot/timeline_cold.json) `build_steps_seconds`, [Dockerfile](../Dockerfile) |
| 이전 측정(2026-11-10, 커밋 `5631309`, kicad 설치 전) | 이미지 0개 · 볼륨 0개인 빈 Docker 엔진(`docker:dind` 29.9.3), 번들에서 clone, `.env` 없이 `docker compose up -d` 한 줄 | `scripts/results/smoke/smoke_localhost-18000_2026-11-10_055128.json`(맥), `_055423.json`(WSL) |
| 이전 측정: 맥(Apple M2, arm64) | `/health` 200 55.6초, 데모 A 로그인 200 55.7초, `scripts/smoke/http_smoke.py --demo --refusal` 23단계 통과 62.9초 | 위와 같음 |
| 이전 측정: WSL2(i9-12900KF, x86_64, WSL 안 Docker 29.1.3 위의 dind) | `/health` 59.8초, 로그인 59.9초, 스모크 23단계 통과 67.5초 | 위와 같음 |
| 기동되는 서비스 | db · thread-setup · corpus-load(42문서 · 청크 1,556개) · api가 정상(11-10: 맥 · WSL, 11-13: 맥) | 위와 같음 |
| 임베딩 · 리랭커 | API 호출(Voyage)이라 로컬 모델 내려받기가 없다. 데모 모드의 검색은 BM25만 쓴다 | [SPEC.md](../SPEC.md) 6 · 7절 |

확인 못 한 것:

| 항목 | 이유 |
|---|---|
| 평가자 환경에서의 기동 | 발표 때 평가자가 하는 실행은 이 측정과 별개다. 이 측정은 Mac 호스트의 docker-in-docker 1회(냉)다 |
| WSL에서 11-13 측정 | 하지 않았다. WSL 값은 11-10 측정뿐이다 |
| 11-13 측정의 반복 · 회선 속도 | 냉 1회 · 온 1회, 호스트 부하 5.62 → 8.21, 회선 속도 미측정([측정 문서](../evals/results/d10/startup_restart_isolation_2026-11-13.md) 한계). 11-17에 냉 6회를 쟀다(위 표). 부하를 고정하지 못했고 온 재기동은 다시 재지 않았다 |
| Windows Docker Desktop | 확인하지 않았다 |
| WSL의 GitHub clone 시간 | 자격 증명이 없어 재지 않았다. 맥은 main clone 3.6초(저장소가 비공개라 저장된 자격 증명으로 받음) |

### G3 코퍼스

문서·쪽·청크 수의 정본은 [data/DATA.md](../data/DATA.md#코퍼스-수치)다. 아래 표는 게이트 증거로 측정 시점의 값과 원시 경로를 적는다.

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 문서 수 | 1,360건 | `data/manifest.jsonl` 1,360행, `evals/results/chunking/v4h-2026-11-08/manifest.jsonl` 1,360행 |
| v4h 청크 | `cards` 51,967, `distinct_text` 51,967(청커 `tsc-v4h-2026-11-08`). 게이트 1만 개 기준 초과 | [summary.json](../evals/results/chunking/v4h-2026-11-08/summary.json), [corpus_v4h_fingerprint_2026-11-12.md](../evals/results/d10/corpus_v4h_fingerprint_2026-11-12.md) |
| 결과 파일 sha256 | `manifest.jsonl` · `summary.json` · `table_suspects.jsonl` | `evals/results/chunking/v4h-2026-11-08/SHA256.txt` |
| 청크별 sha256 목록 | 51,967행, 서로 다른 해시 51,967, 문서 1,360. 해시는 `chunks.jsonl`의 `text`(UTF-8, LF) 51,967건 전부 재계산과 일치. 청크 본문 없음 | [chunk_sha256.tsv](../evals/results/chunking/v4h-2026-11-08/chunk_sha256.tsv), 형식·확인·재생성 명령 [chunk_sha256.md](../evals/results/chunking/v4h-2026-11-08/chunk_sha256.md) |
| 새 Supabase 프로젝트 | 문서 1,360 · 청크 51,967 · 임베딩 51,967(옛 운영 DB에서 복사할 때 센 값, 2026-11-11) | `docs/worklog/jeongun.md` 11-11 항목 |
| 운영 DB 청크 본문 직접 대조(2026-11-16 09:38 KST) | 운영 DB `document_chunks` 51,967행의 본문을 읽기 전용으로 열어 sha256을 다시 계산: 저장된 `chunk_sha256`과 같은 행 51,967/51,967, 서로 다른 값 51,967. 정렬한 해시 목록의 sha256(`82dff159…`)이 저장소 `chunk_sha256.tsv`의 같은 값과 같다(본문 집합이 해시 목록과 정확히 같다) | [db_content_hash_check_2026-11-16.md](../evals/results/d10/db_content_hash_check_2026-11-16.md) |
| v1 manifest | 문서 1,360행, 청크 합 52,244, 서로 다른 본문 45,898(외부 스냅샷). v4h와 서로 다른 버전이라 섞어 세지 않는다 | `data/manifest.jsonl` |
| 파싱 | Docling 2.145.0 + pdfplumber 대조 | [EVAL_REPORT.md](../EVAL_REPORT.md) 1-1절 |

확인 못 한 것:

| 항목 | 이유 |
|---|---|
| 새 clone에서 청킹 전체 재실행 | `chunks.jsonl`이 저장소에 없어 불가. 해시 목록과의 대조에도 필요하다 |

### G4 에이전트

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 서비스 그래프 | D5 멀티 그래프(Supervisor + RAG 에이전트 · Spec 에이전트). D4 v2 단일 그래프는 비교 기준선 | `backend/multi_agent/build.py`, `backend/graph/build.py` |
| 영속 체크포인트 · 승인 · 견적 | 사용자별 분석 thread(PostgreSQL 체크포인트, 조건 질문 interrupt · 재개, 판정 승인)가 서비스에 있다(PR #73 이후) | `backend/conversations/memory_service.py` |
| 배포 주소 스모크(2026-11-10~11) | 조건 질문 정지 `requires_input` → 재개 `completed` → 승인 201 · 같은 승인 409 → 견적 저장. 계정 B가 A의 프로젝트 · thread · run · 견적 · 승인을 읽거나 쓰면 404 | G1 증거의 28단계 JSON |
| 로컬 compose 재시작 복원(2026-11-09, `jeongun-8` `f6b6d7e`) | 조건 질문에서 멈춘 대화가 `docker compose restart api` 뒤에도 WAITING, 답하고 재개하면 DONE. 같은 승인 요청 두 번은 둘 다 200이고 DB 승인 원본은 1건. 데모 사용자 B는 A의 대화 조회 · 승인이 404. 시험 14개 통과 | [local_g4_isolation_2026-11-09.json](../evals/results/threads/local_g4_isolation_2026-11-09.json), `tests/api/test_http_restart.py` |
| 재시작 뒤 재개 · 계정 분리, 현재 코드(2026-11-13, `jeongun-2` @ `ad8612e` = `main` `ea5797c`과 같은 트리, 로컬 compose, 키 없는 재생) | 실제 멀티 에이전트 그래프 + PostgreSQL 체크포인터로 52개 점검 52 통과. `demo-ask` · `v3-01`이 `requires_input`에서 멈춘 채 `docker compose restart api`(api PID 25205 → 29452, db 그대로) → 같은 세션 쿠키로 같은 정지 내용 → 재개하면 `completed`, 기록과 같은 판정(`ROLE_SUFFICIENT`). 체크포인트 행(thread별 `checkpoints` 9 · `checkpoint_writes` 61 · `checkpoint_blobs` 30)은 재시작 전후 같음. 계정 B ↔ A의 프로젝트 · thread · run · 메시지에 GET · PATCH · POST · DELETE · resume · recover가 양방향 · 재시작 전후 모두 404 `NOT_FOUND`, 목록에 상대 객체 없음, A의 사실 기억 3칸은 B에게 보이지 않고 재시작 뒤에도 A에게 남음. 승인 201 · 같은 승인 409 `ALREADY_APPROVED`(행 1), 견적 저장 201, 재시작 뒤에도 같음 | [startup_restart_isolation_2026-11-13.md](../evals/results/d10/startup_restart_isolation_2026-11-13.md), [g4_restart_isolation.json](../evals/results/d10/boot/g4_restart_isolation.json), [checkpoint_rows.txt](../evals/results/d10/boot/checkpoint_rows.txt) |
| 배포 서버 재시작 뒤 재개 · 계정 분리(2026-11-13, 리비전 `sojafit-api-574de79` → `sojafit-api-574de79-rs`, `main` `574de79`, 실제 모델) | 평가용 계정 A · B 25단계 통과. 4단계 run `1d9ef35f…`이 `requires_input`에서 멈춘 채 같은 이미지의 새 리비전으로 100% 전환(`maxScale 1`이라 새 프로세스) → 재개 `POST /api/runs/1d9ef35f…/resume` 200을 새 리비전이 처리 → `run_started>status>completed` 3.0초(처음 시작은 19초) → 승인 → 같은 승인 409 `ALREADY_APPROVED` → 견적. 계정 B가 A의 프로젝트 · thread 목록 · run · 견적 목록 읽기, 승인, 견적 저장은 모두 404 | [deploy_574de79/README.md](../evals/results/d10/deploy_574de79/README.md), [서버 로그 발췌](../evals/results/d10/deploy_574de79/restart_server_log_2026-11-13.txt) |
| 사용자 사실 기억 | 사용자 사실 3칸을 Store `(user_id, "profile")`에 두고 문장 임베딩 색인으로 찾는다(`backend/conversations/profile.py`). 순위 · 사용자 격리 · 수정 뒤 재임베딩 · 삭제는 결정적 가짜 임베딩으로 DB 시험 통과. 키 없는 로컬 compose에서 저장 · 사용자 격리 · 남의 id 거절(422) 확인 | [test_profile.py](../tests/conversations/test_profile.py), [test_threads.py](../tests/api/test_threads.py) |
| 변이 확인 | 변이 28건 모두 시험이 잡는다(2026-11-13, 2차 시험 추가 전 25건 잡음 · 3건 못 잡음, 추가 후 28건 · 0건). 아래 "변이 확인" 표는 9건과 대표 6건 | [mutation_2026-11-13.md](../evals/results/d10/mutation_2026-11-13.md) |
| 기준 미달 시 pytest 실패 | 인젝션 결과 검사: 충족 시 종료 0, 깨뜨린 사본 3개는 위반 1건 · 종료 1. 종료 코드 1과 빈 최종 답 위반을 고정하는 시험 2개(`tests/evals/test_check_injection_result.py:31`, `:37`)가 있고, 해당 코드 줄을 깨뜨리면 실패한다 | [threshold_pass_2026-11-13.txt](../evals/results/d10/threshold_pass_2026-11-13.txt), [threshold_fail_2026-11-13.txt](../evals/results/d10/threshold_fail_2026-11-13.txt), 변이 N10 · N11([mutation_2026-11-13.md](../evals/results/d10/mutation_2026-11-13.md)) |

확인 못 한 것:

| 항목 | 이유 |
|---|---|
| 배포 서버 재시작 뒤 복원의 내부 근거 | 배포에서 확인했다([deploy_574de79](../evals/results/d10/deploy_574de79/README.md)). 다만 재개가 처음부터 다시 돈 것이 아니라는 근거는 이벤트 순서와 시간(3초 대 19초)이고 DB 체크포인트 행은 직접 대조하지 않았다 |
| 평가용 계정 2개로 한 기억(사용자 사실) 분리 점검 | 배포 25단계는 프로젝트 · thread · run · 견적의 계정 분리(404)를 확인했다. 사용자 사실 3칸의 계정 분리는 배포 주소에서 따로 확인하지 않았다(로컬 compose에서만) |
| 실제 임베딩에서의 재시작 뒤 재개(로컬) | 11-13 로컬 측정의 모델 응답은 기록 재생이다. 실제 모델 호출로는 배포 `574de79`에서 확인했다(위 표). 로컬 compose에서 실제 호출로는 하지 않았다 |
| 합성 시험 `tests/api/test_http_restart.py` | `ad8612e`에서 2회 모두 429 `RATE_LIMITED`로 실패했다(호출 간격 2초 안에 재개). 간격 0 진단은 통과. 시험 쪽 수정(간격 0 지정)은 `main`에 있다(`a944c34`). 수정 뒤에는 실행하지 않았다. 상세: 측정 문서 한계 |
| 배포 DB에서 실제 Voyage 임베딩으로 한 사용자 기억 의미 검색 | 확인하지 않았다. 키 없는 로컬 compose의 검색은 순위 없는 목록이다 |

### G5 평가

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 기준 평가셋 | v3 50건(관련 25 · 비관련 25, 2026-11-10 동결). v1 50건(11-02), v2 70건(11-03)도 동결 | `evals/FROZEN.json`, [ADR 0015](adr/0015-평가셋-v3를-새로-만들고-청킹부터-다시-잰다.md) |
| 개선 전후 비교 | 3-A 검색 5단계, 3-B 판정 길 8단계, 3-C v3 검색 길 2단계, 3-D 현재 스택 확인. 달라진 문항 목록과 회귀 문항 포함 | [EVAL_REPORT.md](../EVAL_REPORT.md) 3절 |
| v3 현재 값 | 2026-11-17 19:58 ~ 20:07 배포 리비전 코드(`backend/` · `data/` · 평가셋이 `2030f846`과 같은 로컬 트리) · `DEMO_MODE=0` 웹 켬 + 미리 출발(운영 리비전 설정과 같음) 1세트씩 2번: **50/50 · 49/50**(2세트 실패 v3-41 `hallucination_risk`: 답할 수 없는 수명 질문에 거절 대신 LL4148 역할 판정을 붙임. 1세트의 같은 문항은 거절해 통과), 무관 거절 25/25 · 24/25, p50 · p95 5.2 · 15.5초와 4.4 · 7.5초 | [set1.json](../evals/results/graph/2026-11-17-deploy-ef0138b2-v3/set1.json) · [set2.json](../evals/results/graph/2026-11-17-deploy-ef0138b2-v3/set2.json) |
| v3 그 전 값 | 2026-11-17 새벽 코드 `799ae636` · `DEMO_MODE=0` 웹 켬 + 미리 출발(`WEB_PREFETCH=1`, 운영 리비전에는 없음) 1세트씩 2번: 두 번 모두 **49/50**(실패 v3-16 `wrong_citation`, 무관 거절 25/25), p50 · p95 5.5 · 16.7초와 4.8 · 9.1초. 이전 헤드라인 50/50(`DEMO_MODE` 미기록, 11-12 `520988c`+작업 트리). `DEMO_MODE=0` 기록 측정은 47 ~ 50/50([EVAL_REPORT.md](../EVAL_REPORT.md) 8.2절 통과 열) | [d12/gate/set1.json](../evals/results/d12/gate/set1.json) · [set_b/set1.json](../evals/results/d12/gate/set_b/set1.json), `evals/results/graph/2026-11-12-d9-improve2/set1.json` |
| 검색 기준선(v1) | 하이브리드 Recall@5 0.737 · MRR 0.649 | `evals/results/retrieval/retrieval_baseline_2026-11-03.json` |
| 서비스 검색 재측정(2026-11-17, `799ae636`) | 같은 실행기(`run_retrieval_service`, 사전 등록 #26 설정) 11-04 → 11-17: R1 고르기용 46 Page Recall@5 0.8587 → 0.8152, 확인용 38 0.9079 → 0.9079, v2 19 0.7939(11-04 0.8246). 달라진 문항 R1 4개(r1-042 · 086 · 098 내려감, r1-097 올라감), v2 2개(draft30-m04 · draft50-n04 내려감). 사이에 코퍼스(v1 → v4h)와 검색 코드가 함께 바뀌었다 | [d12/retrieval/service_r1_2026-11-17.json](../evals/results/d12/retrieval/service_r1_2026-11-17.json), `evals/results/retrieval/service_r1_2026-11-04.json` |
| 사전 등록 | 바꾸기 전 기대를 기록 | `evals/guides/preregister.md` |

확인 못 한 것:

| 항목 | 이유 |
|---|---|
| v3 검색 Recall@5 · MRR의 해석 | 측정했다. 검색만 돌리는 실행기(`run_retrieval_v3.py`) 21문항에서 v1 · v4h 모두 문서 · 쪽 Recall@5 · MRR 0.8095(상한 17/21: 후보 찾기 4문항은 품번 필터가 빈 결과를 만듦)이고 청커를 구별하지 못한다([chunking/v1-vs-v4h-2026-11-13](../evals/results/chunking/v1-vs-v4h-2026-11-13/README.md)). 전체 그래프 실행 `2026-11-13-citecheck-v3`의 검색 21문항은 문서 · 쪽 Recall@5 1.0, 쪽 MRR 0.9762다([report.json](../evals/results/graph/2026-11-13-citecheck-v3/report.json)). 목표 0.95는 후자 기준으로 넘었고, 전자의 0.8095는 실행기 한계다 |
| 3-C 14행의 원시 결과 | 원시 미보관(EVAL_REPORT 12장) |
| 3-A 5행(비트 후보)에서 기대 중 두 항목 | 합계 ±0.02와 시간 3배 이상은 기대와 달랐다. 유지를 정한 기록이 없다(EVAL_REPORT 3절 5행) |

### G6 트레이스

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 평가 실행의 점수 연결 | 그래프 평가 실행기(`evals/runners/run_graph.py`)가 단계 · 토큰 · 비용 · 실행 점수 · 답 5지표(`answer_metric`)를 트레이스 점수로 기록. 동결 v2 70문항 실행(#31, 11-04)에서 트레이스 70개와 `answer_metric` 70건이 결과 파일과 맞음 | `evals/guides/preregister.md` #31 결과, `evals/results/graph/` |
| 반복 평가 | v3 50문항 4세트(#50)가 세트마다 Langfuse 세션 하나에 트레이스 50개와 문항 점수를 남김 | [EVAL_REPORT.md](../EVAL_REPORT.md) 7장 |
| 서비스 분석 트레이스 | `user_id`(사용자) · `session_id`(대화)를 붙이고 질문 · 답 글은 보내지 않음(시험으로 확인) | `tests/services/test_langfuse_prompts.py` |
| Skill 대표 흐름 | 대표 4건 · 직접 생성 13건의 generation 23개를 API로 확인, 상황별 기준 12/13 충족 | `evals/results/skill/skill_tool_summary_2026-11-03.json` |
| 대시보드 스크린샷 7장 | `01-trace-list.jpg`(트레이스 목록) · `02-model-call-detail.jpg`(트레이스 타임라인과 모델 호출 상세: 모델 · 시간 · 토큰 · 비용) · `03-cost-dashboard.jpg`(비용 대시보드)는 2026-11-13 10:13~10:15 KST 캡처, 프로젝트 `SojaFit_v2`. `04` ~ `07`(RAGAS 점수가 붙은 트레이스 상세 · 점수 탭, Spec · RAG 에이전트 Timeline, 홈 대시보드)은 2026-11-17 밤 캡처(배포 리비전 코드 로컬 v3 실행 트레이스) | [docs/deliverables/langfuse/](deliverables/langfuse/), [DELIVERABLES.md](deliverables/DELIVERABLES.md) |
| 느림 원인 사례 | 2건과 LLM 단계별 시간 · 비용 | [EVAL_REPORT.md](../EVAL_REPORT.md) 7 · 8장 |

확인 못 한 것:

| 항목 | 이유 |
|---|---|
| 운영 리비전 트레이스의 점수 화면 | 점수가 붙은 화면은 11-17 배포 리비전 코드(`2030f846` 백엔드)의 로컬 v3 실행 트레이스로 캡처했다(`04` ~ `07`). 운영 리비전 트레이스로는 캡처하지 않았다. 점수가 트레이스에 붙어 있는 것은 2026-11-16에 Langfuse v3 점수 API로 확인했다: 11-15 v3 웹 끔 측정의 v3-01 트레이스에 점수 15개(`pass`=True 등, 결과 파일 값과 같음), [langfuse_scores_2026-11-16.md](../evals/results/d10/langfuse_scores_2026-11-16.md). 2026-11-17 재조회: 운영 프로젝트 점수 57,198개(숫자 · 참거짓 40,826 + 범주 16,372)가 트레이스 4,109개에 붙어 있고, 11-17 `799ae636` 게이트 세트의 트레이스 50개에 700개가 붙었다. 캡처할 트레이스: `5fa5c6c56187c8a38326de96fd57dfa5`(v3-01, 점수 15개), [d12 README](../evals/results/d12/README.md) |
| 배포본 서비스 분석 트레이스의 Langfuse 수신 | 수신을 확인했다: 11-13 09:38~10:10 배포본 요청이 트레이스로 보인다(스크린샷 `01`, 최근 1일 루트 관측 약 101건). 403 원인은 [langfuse_403_2026-11-13.md](../evals/results/d10/langfuse_403_2026-11-13.md). 확인 시점의 리비전은 `fadde2a`이고 그 뒤의 100% 리비전(`574de79-rs`, 지금 리비전은 README 표 「배포 리비전」)에서 새로 캡처하지는 않았다 |
| 현재 Skill 실행 UI | 확인하지 않았다 |

### G7 제출물

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 시연 영상 · 스크립트 | 영상 4분 49초(정상 3 + 실패 2, 11-17 운영 리비전 `sojafit-api-pre-b4a02113-1117`에서 녹화). 스크립트는 녹화 전 계획 | [sojafit-demo-2026-11-17.mp4](deliverables/video/sojafit-demo-2026-11-17.mp4) · [demo_script.md](deliverables/demo_script.md) |
| 실패 분석 | 있음 | [failure_analysis.md](deliverables/failure_analysis.md) |
| AI 도구 사용 기록 | 있음 | [ai_tools_log.md](deliverables/ai_tools_log.md) |
| 포트폴리오 | 3건 있음(수치는 EVAL_REPORT 값만, 11-17) | [portfolio-jeongun.md](deliverables/portfolio-jeongun.md) · [portfolio-osc.md](deliverables/portfolio-osc.md) · [portfolio-sth.md](deliverables/portfolio-sth.md) |
| 개인정보 · 비밀값 점검 | 2026-11-17: 제출 문서 · 덱에서 메일 · 키 형식 검색 0건, Langfuse 화면 7장과 영상 프레임에 개인 메일 · 키 없음(영상의 계정은 `@sojafit.test` 시연 계정, 화면 왼쪽 아래 `DNS`는 Langfuse 계정 표시 이름). 서비스 트레이스는 남길 칸만 두고 입력 · 출력을 `[redacted]`로 바꿔 보냄(`backend/services/service_trace.py` `mask_otel_spans`), `user_id`는 숫자 로그인 id | [DELIVERABLES.md](deliverables/DELIVERABLES.md) |
| 비밀값 검사(재검사) | 2026-11-17, `main` `799ae636`, gitleaks `v8.30.1`(같은 이미지 digest), 저장소 `.gitleaks.toml`(허용 5) · `.gitleaksignore`(지문 14줄), `--redact`, 이력 전체 1,250 커밋 검사(`git rev-list --count` 1,494, 병합 제외 1,252), **발견 0건 · 종료 코드 0** | [gitleaks_full_history.txt](../evals/results/d12/checks/gitleaks_full_history.txt) |
| 비밀값 검사 | 2026-11-13, `b5f050d`(`origin/main`), gitleaks `v8.30.1`, 이력 전체 801 커밋, 발견 0건. 최근 207 커밋도 0건. 허용 목록이 가리는 항목 1,366건은 모두 비밀이 아니다(해시 · 식별 값 · 시험 값). 시험 값 10건은 `.gitleaksignore` 지문으로, 해시 · 식별 값 · 파일 이름은 `.gitleaks.toml` 경로로 가린다. 시험 값 이전 뒤 `jeongun`(`c020389`) 이력 검사는 1건(`extra_checks.md:10`, SQL 파일 이름 인용 줄, 이전 전에도 있음)이다. 알려진 키 형식 정규식 검사도 파일 · 이력 0건 | [secret_scan_2026-11-13.md](../evals/results/d10/secret_scan_2026-11-13.md), [secrets/](../evals/results/d10/secrets/), 현재 HEAD 재검사: [secrets/after_2026-11-13_556384b.md](../evals/results/d10/secrets/after_2026-11-13_556384b.md) |

확인 못 한 것(없는 것):

| 항목 | 상태 |
|---|---|
| GitHub Actions 비밀값 검사 실행 결과 | 확인하지 못했다. Actions는 조직 결제 한도로 2026-11-09(PR #73)부터 시작되지 않았다(`docs/worklog/jeongun.md`). 로컬 gitleaks 결과만 있다(11-17 `799ae636`에서 다시 돌려 0건, 위 G7 행) |
| 허용 목록이 gitleaks 검사에서 빼는 파일 3개(리랭크 캐시 · 인젝션 결과 2개) | gitleaks는 이 파일을 보지 않는다(캐시는 모든 규칙, 인젝션 결과는 `generic-api-key`). 정규식 검사로 0건을 확인했고 건별 목록은 없다 |
## 변이 확인

핵심 코드를 한 줄 깨뜨렸을 때 테스트가 실제로 실패하는지 확인한 기록이다(G4 · G5). 28건 전체 표와 재현 명령은 [mutation_2026-11-13.md](../evals/results/d10/mutation_2026-11-13.md)(정본)에 있고, 여기에는 기존 9건과 영역이 다른 대표 6건을 적는다. 28건을 모두 시험이 잡는다(N3b · N7 · N15는 처음에 못 잡았고 시험을 더해 잡게 됐다. 1차 기록은 `mutation/raw_25_of_28/`). 재작성 횟수 상한 테스트가 상수끼리 비교하면(`assert n == MAX_REWRITES`) 상한을 99로 올려도 통과하므로 리터럴과 비교한다(`assert n == 2`).

| # | 깨뜨린 곳 (파일:줄, 변이) | 실패해야 하는 테스트 | 실제로 실패했는가 | 확인한 날 · 커밋 |
|---|---|---|---|---|
| 1 | `backend/graph/build.py:24` `MAX_TRIES = 2` → `MAX_TRIES = 99` (재검색 횟수 상한 무력화) | `tests/graph/test_graph_rewrite.py::test_after_grade_rewrites_once_then_refuses`, `tests/graph/test_graph_build.py::test_still_no_pass_refuses_after_two_searches` | 실패 (`AssertionError: assert '재작성' == '거절'`, 2 failed), 원복 후 통과 | 2026-11-13 · `9c32d12` |
| 2 | `backend/graph/nodes.py:270` `other_part_row` 반환식을 `return False`로 변경 (같은 문서 내 다른 품번 행 결정적 필터 제거) | `tests/graph/test_graph_grade.py::test_other_part_row_dropped_before_llm` | 실패 (1 failed, 다른 품번 행이 통과해 `passed` 목록이 달라짐), 원복 후 통과 | 2026-11-13 · `9c32d12` |
| 3 | `backend/graph/nodes.py:460` `generate`의 `"fake_citations": sorted(cited - valid)` → `[]` (없는 근거 번호 인용 검출 무력화) | `tests/graph/test_graph_generate.py::test_generate_counts_fake_and_uncited` | 실패 (1 failed, `fake_citations`가 빈 목록), 원복 후 통과 | 2026-11-13 · `9c32d12` |
| 4 | `backend/graph/build.py:24` `MAX_TRIES = 2` → `3` (검색 상한 2회 → 3회) | `tests/graph/test_graph_build.py::test_still_no_pass_refuses_after_two_searches` | 실패 (세 번째 채점에서 `StopIteration`), 원복 후 통과 | 2026-11-13 · `9c32d12` |
| 5 | `backend/graph/nodes.py:237` MCP 장애의 `retrieval_error`를 `None`으로 변경 | `tests/graph/test_graph_build.py::test_retrieval_failure_is_not_reported_as_empty_corpus` | 실패 (`assert None == {'kind': 'timeout'}`), 원복 후 통과 | 2026-11-13 · `9c32d12` |
| 6 | `backend/graph/build.py:49` MCP 장애도 채점으로 분기 (`return "채점"`) | `tests/graph/test_graph_build.py::test_retrieval_failure_is_not_reported_as_empty_corpus` | 실패 (path에 불필요한 `채점` 추가), 원복 후 통과 | 2026-11-13 · `9c32d12` |
| 7 | `backend/multi_agent/supervisor.py:351` `check_node`: 종합 숫자 검사 `problem = bool(…)` → `problem = False` | `tests/multi_agent/test_build.py::test_synth_that_invents_a_number_is_refused_by_the_check` | 실패 (`KeyError: 'refusal_reason'`), 원복 후 깨끗 | 2026-11-13 · `9c32d12` |
| 8 | `backend/multi_agent/supervisor.py:241` `_judgement_reply` 첫 줄 `return None` | `tests/multi_agent/test_supervisor.py::test_partial_judgement_does_not_fall_back_to_unsafe_prose` (single · synth) | 실패 (2 failed, 문서 사용 권고가 최종 답에 남음 / synth fallback), 원복 후 깨끗 | 2026-11-13 · `9c32d12` |
| 9 | `backend/multi_agent/contracts.py:18` `MAX_AGENT_RUNS = 6` → `99` | `tests/multi_agent/test_contracts.py::test_limits_match_agreed_numbers`, `tests/multi_agent/test_supervisor.py::test_collect_refuses_over_the_agent_limit` | 첫째 시험 실패 (`99 != 6`), 둘째는 상수를 쓰므로 통과 (1 failed, 1 passed). 원복 후 깨끗. 상한 가드 자체는 변이 N13이 잡는다 | 2026-11-13 · `9c32d12` |
| N1 | `backend/multi_agent/agents/docs.py:230` RAG 가짜 인용 번호 목록 `fake = sorted(…)` → `[]` | `tests/multi_agent/test_docs_agent.py::test_nested_fake_id_is_removed_without_losing_the_provided_id` | 실패 (2 failed), 원복 후 깨끗 | 2026-11-13 · `9c32d12` |
| N4 | `backend/judge/verdict.py:405` 필수 조건 실패 시 불충분 판정 `elif any(… == 'fail' …)` → `elif False` | `tests/judge/test_judge_conditions.py::test_tolerance_class_excludes_tighter_grades_too` | 실패 (`'ROLE_SUFFICIENT' == 'NOT_SUFFICIENT'`), 원복 후 깨끗 | 2026-11-13 · `9c32d12` |
| N6 | `backend/conversations/memory_service.py:192` 하루 토큰 한도 조건에서 사용량 항 제거 | `tests/api/test_errors.py::test_token_cap_is_limit_exceeded` | 실패 (`DID NOT RAISE ApiError`), 원복 후 깨끗 | 2026-11-13 · `9c32d12` |
| N8 | `backend/auth.py:310` Origin 검사 `if request.headers.get("origin") != origin:` → `if False:` | `tests/api/test_health.py::test_forbidden_uses_error_contract` | 실패 (`assert 200 == 403`), 원복 후 깨끗 | 2026-11-13 · `9c32d12` |
| N10 | `evals/runners/check_injection_result.py:45` 위반 시 종료 코드 `return 1 if found else 0` → `return 0` | `tests/evals/test_check_injection_result.py::test_main_exits_1_on_violation_and_0_otherwise` | 실패 (`assert 0 == 1`), 원복 후 깨끗. 시험 추가 전에는 못 잡았다 | 2026-11-13 · `9c32d12` |
| N12 | `evals/dataset_v1.jsonl` 끝에 공백 1바이트 추가 (동결 해시) | `tests/evals/test_frozen_evals.py::test_frozen_files_unchanged` | 실패 (`dataset_v1.jsonl: 동결 후 바뀌었습니다`), 원복 후 깨끗 | 2026-11-13 · `9c32d12` |

나머지 변이(N2 · N3 · N3c · N5 · N9 · N11 · N13 · N14 등)의 줄 · 시험 id · 첫 실패 메시지는 [mutation_2026-11-13.md](../evals/results/d10/mutation_2026-11-13.md) 3절에 있다. 원시 pytest 출력: [mutation/raw/](../evals/results/d10/mutation/raw/). 이전 기록: [mutation_2026-11-12.md](../evals/results/d10/mutation_2026-11-12.md)(대체됨). D10 재현 · 기준 미달 출력 · 코퍼스 지문: [evals/results/d10/README.md](../evals/results/d10/README.md).

## G4 추가 확인

| 항목 | 상태 | 증거 |
|---|---|---|
| 승인 대기 상태를 영속 체크포인트에 저장하고 서버 재시작 뒤 복원 · 재개. 승인 전 부작용 없음, 같은 승인 요청 반복 시 실행 중복 없음 | 로컬 compose에서 확인(2026-11-13, `jeongun-2` `ad8612e` = `main` `ea5797c`과 같은 트리; 2026-11-09, `jeongun-8` `f6b6d7e`). 배포 주소에서는 2026-11-13 리비전 `sojafit-api-574de79-rs`에서 재시작 뒤 재개 · 승인 · 같은 승인 409를 확인했다(위 G4 표 "배포 서버 재시작 뒤 재개 · 계정 분리" 행). 2026-11-17 운영 리비전에서도 재시작 뒤 재개 · 판정 완료를 다시 확인했다(G4 행, `sojafit-api-pre-ef0138b2-rs`) | [startup_restart_isolation_2026-11-13.md](../evals/results/d10/startup_restart_isolation_2026-11-13.md), [local_g4_isolation_2026-11-09.json](../evals/results/threads/local_g4_isolation_2026-11-09.json) |
| 사용자별 DB Store에 기억 저장, 의미 검색 · 활용 · 잘못된 기억 수정. thread 체크포인트나 코퍼스 벡터만으로 사용자 장기 기억을 대신하지 않음 | 일부 확인. 저장 · 격리 · 수정 · 삭제는 가짜 임베딩 DB 시험과 로컬 compose에서 확인. 실제 Voyage 임베딩과 배포 DB에서의 의미 검색은 확인하지 않음 | [test_profile.py](../tests/conversations/test_profile.py), [test_threads.py](../tests/api/test_threads.py) |
