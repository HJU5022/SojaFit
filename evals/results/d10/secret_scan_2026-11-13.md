# 비밀값 검사: gitleaks 이력 검사와 패턴 검사

- 상태: 현행
- 기준일: 2026-11-13
- 기준 커밋: `b5f050d`(`origin/main`)
- 정본 여부: 정본(비밀값 검사 증거). 요약은 [docs/GATES.md](../../../docs/GATES.md) G7이 링크한다
- 관련 문서: [.gitleaks.toml](../../../.gitleaks.toml), [.gitleaksignore](../../../.gitleaksignore), [.github/workflows/secret-scan.yml](../../../.github/workflows/secret-scan.yml), [README.md](README.md)

## 1. 결과

| 항목 | 값 | 근거 |
|---|---|---|
| 도구 | gitleaks `v8.30.1`, 이미지 `ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f` | [secrets/summary.json](secrets/summary.json) |
| 설정 | 저장소의 `.gitleaks.toml`·`.gitleaksignore`(자동 로드), `--redact` | [secrets/commands.md](secrets/commands.md) |
| 이력 전체 | 801 커밋(병합 제외, 병합 포함 948) 발견 0건 | [secrets/2a_full_history.json](secrets/2a_full_history.json) |
| 11-11 설정 커밋 `db77a11` 이후 | 207 커밋(병합 포함 246) 발견 0건 | [secrets/2b_since_1111.json](secrets/2b_since_1111.json) |
| 파일 시스템 모드(`origin/main` 내보내기) | 9건, 모두 아래 3절의 허용 항목 | [secrets/summary.json](secrets/summary.json) `2c_worktree_no_git` |
| 설정·무시 목록 없이 이력 전체 | 1,366건, 모두 `generic-api-key`, 실제 비밀 0건 | [secrets/summary.json](secrets/summary.json) `2d_history_no_ignore_no_allowlist` |

## 2. 범위와 방법

| 검사 | 대상 | 설정 |
|---|---|---|
| 2a | `origin/main` 전체 이력 | 저장소 설정 적용 |
| 2b | `db77a11..origin/main` | 저장소 설정 적용 |
| 2c | `git archive origin/main` 내보내기(이력 없음) | 저장소 설정 적용. 경로를 `^`로 고정한 허용 규칙이 맞지 않아 허용 항목 9건이 보인다 |
| 2d | 설정·`.gitleaksignore`가 없는 빈 bare 저장소에 `origin/main`을 받아 이력 전체 | 허용 규칙 없음 |

명령은 [secrets/commands.md](secrets/commands.md)에 있다. `secrets/`를 `scripts/results/`가 아니라 `d10/`에 둔 이유: `d10/`은 GATES가 링크하는 점검 증거 폴더이고 평가 지표가 아닌 변이·지문 증거도 이미 담는다. 컨테이너는 읽기 전용으로 마운트했고 `--rm`으로 종료 시 삭제된다. 라이브 `.env`와 `scratchpad/`는 읽지 않았다.

## 3. 허용 목록이 가린 항목의 분류

설정 없이 돌린 2d의 1,366건이다. 값은 모두 앞 4자까지만 확인했다. 분류 상세는 [secrets/extra_checks.md](secrets/extra_checks.md) 2d.

| 건수 | 위치 | 값의 정체 | 분류 | 허용 방식 |
|---|---|---|---|---|
| 986 | `evals/results/embedding/grid_rerank_cache_2026-11-02.jsonl` `key` 필드 | 64자리 16진 sha256 해시 | 비밀 아님 | `.gitleaks.toml` 파일 경로 허용(모든 규칙) |
| 360 | `evals/results/threads/injection_baseline_live_2026-11-11_03.jsonl` 240, `..._03_human_jeongun.jsonl` 120 | `document_key`(코퍼스 문서 식별 값). 원시 Match는 `document_key": "REDACTED"` | 비밀 아님 | `.gitleaks.toml` 파일 경로 허용(`generic-api-key` 규칙만) |
| 8 | `docs/worklog/jeongun.md` | `--to-revisions=sojafit-api-<커밋 해시>` 배포 리비전 이름 | 비밀 아님 | `.gitleaks.toml` 경로 + 정규식 허용 |
| 7 | `tests/api/test_auth.py` | 시험용 비밀번호(`synt…`) | 시험 값 | `.gitleaks.toml` `tests/` 경로 + 접두어 허용 |
| 2 | `tests/api/test_errors.py` | 시험용 비밀번호(`synt…`) | 시험 값 | 같음 |
| 1 | `tests/api/test_deletion.py:53` | 시험용 `AUTH_SECRET`(`isol…`) | 시험 값 | 같음 |
| 1 | `backend/conversations/memory_service.py:109` | SQL 파일 이름 상수(`022_token_limits.sql` 등) | 비밀 아님 | `.gitleaks.toml` 경로 + 정규식 허용 |
| 1 | `evals/results/graph/memory_operations_2026-11-09.json:121`(커밋 `ccadd3f`) | `backend/auth.py`의 64자리 SHA-256 | 파일 해시 | `.gitleaksignore` fingerprint(무시 목록이 이 1건만 가려 1,366 → 1,365, 나머지는 위 허용 규칙이 가려 0) |

합계 986 + 360 + 8 + 7 + 2 + 1 + 1 + 1 = 1,366.

## 4. 추가 검사

원문: [secrets/extra_checks.md](secrets/extra_checks.md). 대상은 현재 추적 파일 전체와 `origin/main` 이력의 추가된 줄이다. 허용 목록이 gitleaks 대신 가리는 파일도 포함한다.

| 검사 | 결과 |
|---|---|
| 알려진 키 형식(`sk-or-`·`sk-ant-`·`pa-`·`AIza`·`ghp_`·`github_pat_`·`xox`·JWT·`BEGIN PRIVATE KEY`·`AKIA`·`GOCSPX`·`sk-`·`Bearer`·`*_SECRET/TOKEN/KEY=` 긴 값) | 파일·이력 모두 0건 |
| `.env.example` | 값 줄 43개 중 빈 값 15, 나머지 28은 스위치·숫자 한도·공개 URL·로컬 자리표시 값. 실제 비밀 형태 0 |
| 위험 파일(`.env`, `*.pem`, `*.key`, `credentials*.json`, 서비스 계정 JSON, `id_rsa`, `.npmrc`, `*.sqlite`, 덤프) | 현재 추적 파일과 전 이력 추가 파일 0개. `.env*`는 `.env.example`뿐 |
| `postgres://user:pw@` 형태 | 파일 12건, 이력 15건. 모두 자리표시·로컬 도커·CI 서비스 DB 값 |
| `pk-lf-`·`sk-lf-` | 시험용 가짜 키(`tests/services/test_service_trace.py`, `tests/services/test_langfuse_prompts.py`) |
| 이메일(자리표시 제외) | 현재 파일 4개에서 5건: 시험 URL 2건, 작업 기록의 데모 계정 주소 2건, 제3자 오픈소스 README의 연락처 1건. 이력에는 [docs/GATES.md](../../../docs/GATES.md)·`EVAL_REPORT.md`에 데모 계정 주소와 개발용 주소가 있었고 현재 파일에는 없다 |
| 데모 이메일 옆 비밀번호 | 전 이력 0건 |
| 한국 전화번호·GCP 프로젝트 번호 정규식 | 해시·바이너리 문자열·트레이스 id의 우연한 일치. 실제 전화번호 0. GCP 번호는 공개 배포 주소의 일부 |
| Supabase 프로젝트 ref | `docs/worklog/sth.md:1425` 한 곳과 이력의 같은 곳. 프로젝트 식별자이며 키가 아니다 |
| `docs/research/evidence/**` | `@` 문자 0개, 이름·전화·이메일 필드 없음 |

## 5. 한계

| 항목 | 내용 |
|---|---|
| Actions 결과 | GitHub Actions(`secret-scan.yml`)에서 실제로 돈 결과는 확인하지 못했다. 워크플로는 이미지를 `:latest`로 쓰므로 이 문서의 고정 digest와 규칙이 다를 수 있다 |
| 허용 목록이 못 보는 파일 | `grid_rerank_cache_2026-11-02.jsonl`은 모든 규칙을, `injection_baseline_live_2026-11-11_03.jsonl`과 `..._03_human_jeongun.jsonl`은 `generic-api-key` 규칙을 gitleaks가 보지 않는다. 이 세 파일은 4절의 키 형식 정규식 검사로 0건을 확인했다. 정규식 검사의 건별 목록은 보관하지 않았다 |
| 2d 보고서 | 1,366건 보고서(1.1MB)에는 작성자 이메일 필드가 있어 저장소에 넣지 않았다. 건수와 파일별 분포는 [secrets/summary.json](secrets/summary.json)에 있다 |
| 2c 보고서 | 9건 보고서는 저장소에 넣지 않았다. 건수는 `docs/worklog/jeongun.md` 4, `tests/api/test_errors.py` 2, `evals/results/graph/memory_operations_2026-11-09.json` 1, `tests/api/test_deletion.py` 1, `tests/api/test_auth.py` 1 |
| 패턴 검사 스크립트 | 4절의 검사에 쓴 스크립트와 건별 목록(앞 4자만 기록)은 저장소에 없다. 결과 요약만 `extra_checks.md`에 있다 |
| 데모 계정 | 작업 기록의 데모 계정이 평가용 계정과 같은지 확인하지 못했다 |
| 작업 트리 | 검사 대상은 `origin/main`이다. 커밋하지 않은 작업 트리와 `.env`는 검사하지 않았다 |
| 개인정보 가림 | `secrets/extra_checks.md`에서 이메일 앞부분·Supabase ref 앞 4자·데모 계정 표기를 일반 표현으로 바꿨다. 가린 것은 이 값뿐이다. 같은 파일 2d 표의 360건 행은 필드를 `pair_key`로 적지만 2d 원시 Match는 `document_key`이다(3절이 정정 값). |
