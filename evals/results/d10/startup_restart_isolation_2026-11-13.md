# 한 줄 기동 · 키 없는 데모 응답 · 재시작 뒤 재개 · 계정 분리 측정

- 상태: 현행
- 기준일: 2026-11-13
- 기준 커밋: `ad8612e`(트리 `6452cdfc4188942e62b1be7e2eb73c55094c3b97`)
- 정본 여부: 정본(G2 한 줄 기동의 11-13 측정, G4 재시작 뒤 재개 · 계정 분리의 11-13 측정). 요약은 [docs/GATES.md](../../../docs/GATES.md) G2 · G4가 링크한다
- 관련 문서: [README.md](README.md), [local_g4_isolation_2026-11-09.json](../threads/local_g4_isolation_2026-11-09.json)(옛 14항목), [scripts/smoke/SMOKE.md](../../../scripts/smoke/SMOKE.md), [scripts/demo/DEMO.md](../../../scripts/demo/DEMO.md)

## 측정 대상

| 항목 | 값 | 근거 |
|---|---|---|
| 브랜치 · 커밋 | `jeongun-2` @ `ad8612e61c86be4376af5cca454843bb35cdc44d`(PR #116 머리) | [boot/environment.json](boot/environment.json) `clone` · `evidence_meta` |
| 트리 | `6452cdfc4188942e62b1be7e2eb73c55094c3b97` | [boot/timeline_cold.json](boot/timeline_cold.json) `tree` |
| `main`과의 관계 | 측정 시점에 `main`이 아니다. `main`에는 아직 들어가지 않았다 | [boot/HOW.md](boot/HOW.md) 첫 단락 |
| `main`에 대한 적용 | PR이 `main`에 들어간 뒤 `git rev-parse origin/main^{tree}`가 위 트리와 같으면 이 기록은 `main`의 기록이다. 다르면 이 기록은 그 커밋의 기록일 뿐이고 `main`에서 다시 잰다 | 트리 해시는 커밋 해시와 달리 병합 방식(병합 커밋 · squash)에 따라 바뀌지 않는다 |
| 측정일 · 시각 | 2026-11-13 05:04~05:25 KST | [boot/environment.json](boot/environment.json) `date_kst` |
| 측정 방법 | 스크립트로 자동 측정. 시각은 `docker events` · compose 로그 · 요청 시각에서 얻었다 | [boot/scripts/](boot/scripts/) |

## 환경

| 항목 | 값 |
|---|---|
| 호스트 | Apple M2(arm64) 8코어, 16 GB, macOS 27.0.1. Docker 29.7.2(엔진 VM 8 CPU · 4.1 GB) |
| 측정 컨테이너 | 빈 `docker:dind`(29.9.3, compose v5.7.0, digest `sha256:08a98015…`), 이미지 0개 · 볼륨 0개에서 시작([boot/empty_before.txt](boot/empty_before.txt)). 호스트로 포트를 열지 않고 요청은 모두 dind 안에서 보냈다 |
| 코드 | dind 안에서 새 clone(`.env` 없음 · API 키 없음), `docker compose up --build`([README.md](../../../README.md)의 기동 명령) |
| 호스트 부하 | 1분 평균 5.62(T0, 부하 6 초과라 80초 기다린 뒤 시작), 8.21(냉 측정 끝). 온 측정은 4.38 → 4.25. 다른 작업이 같은 호스트에서 돌고 있었다 |

출처: [boot/environment.json](boot/environment.json), [boot/timeline_cold.json](boot/timeline_cold.json), [boot/timeline_warm.json](boot/timeline_warm.json).

## 1) 한 줄 기동

냉 측정은 이미지 · 빌드 캐시가 없는 상태, 온 측정은 냉 측정 뒤 `docker compose down -v`(컨테이너 · 볼륨 삭제, 이미지 · 빌드 캐시 유지)에서 같은 `up`을 다시 한 것이다.

| 시작점 | 끝점 | 냉(초) | 온(초) | 포함하는 것 |
|---|---|---|---|---|
| clone 시작 | `/health` 200 | 243.9 | - | clone 8.4 + 다음 줄 |
| `docker compose up --build` | `/health` 200 | 235.5 | 11.7 | 이미지 받기 · 빌드 · db 기동 · corpus-load · thread-setup · api 기동 |
| `docker compose up --build` | 스모크 종료 | 243.1 | 19.0 | 위 + 데모 A 로그인 + 스모크 실행 7.4(냉) · 7.2(온) |
| clone 시작 | 스모크 종료 | 251.6 | - | clone + 위 전부 |

게이트 기준 10분(600초, [docs/GATES.md](../../../docs/GATES.md) 게이트 표 G2)보다 짧다. 근거: [boot/timeline_cold.json](boot/timeline_cold.json) `derived_seconds`, [boot/timeline_warm.json](boot/timeline_warm.json) `derived_seconds`.

냉 측정의 구간(T0 = clone 시작):

| 구간 | T0 기준 시각(초) | 구간 길이(초) |
|---|---|---|
| clone 끝 · `up` 시작 | 8.4 | clone 8.4 |
| pgvector 이미지 받기 끝 · 빌드 시작 | 31.6 | 23.1 |
| 빌드 끝 · db 컨테이너 시작 | 233.8 | 빌드 202.2 |
| db healthy | 236.8 | |
| api 컨테이너 시작 | 239.5 | |
| `/health` 200 | 243.9 | 빌드 끝 뒤 10.1 |

시간을 정하는 것은 이미지 빌드다. 빌드 단계별 시간(BuildKit이 기록한 값, 단계끼리 일부 겹쳐 돈다):

| 단계 | 초 |
|---|---|
| `apt-get install kicad libcairo2` | 70.0 |
| 이미지 내보내기(`api` · `thread-setup` · `corpus-load` 3개 태그, 같은 이미지) | 65.9 |
| `uv sync --locked --no-dev --no-cache` | 48.6 |
| `npm ci` | 45.4 |

근거: [boot/timeline_cold.json](boot/timeline_cold.json) `build_steps_seconds`. `kicad libcairo2` 설치는 커밋 `e928d59`(2026-11-11)가 `Dockerfile`에 넣었다([Dockerfile](../../../Dockerfile)). 같은 방법의 2026-11-10 측정(55.6초, 커밋 `5631309`)은 이 설치가 들어가기 전이다. 두 측정의 차이를 단계별로 나누어 재지는 않았다.

| 항목 | 값 | 근거 |
|---|---|---|
| 내려받은 양(냉) | 852,167,151 B(약 852 MB). clone 39,374,263 B 포함 | [boot/environment.json](boot/environment.json) `network_received_bytes` |
| 내려받은 양(온) | 51,191 B | 위와 같음 |
| 이미지 크기 | `api` · `thread-setup` · `corpus-load` 각 2.51 GB(같은 이미지), `pgvector/pgvector:pg16` 640 MB | 위와 같음 `images_in_dind_after` |
| 기동 서비스 | db · corpus-load · thread-setup(종료 코드 0) · api, `/health` 200 | [boot/timeline_cold.json](boot/timeline_cold.json) `events` |

`b5f050d`에서 잰 이전 측정은 냉 313.2초이고 스모크가 15 통과 · 2 실패 · 11 건너뜀이었다(키 없는 데모 기록이 낡아 `ReplayMiss`). 이 문서의 측정이 그 값을 대체한다. 이전 측정의 원시 파일은 저장소에 없다.

## 2) 키 없는 데모 응답

`scripts/smoke/http_smoke.py --base-url http://localhost:8000 --demo --refusal`(2026-11-10 기록과 같은 옵션)을 dind 안에서 실행했다.

| 측정 | 통과 | 실패 | 건너뜀 | 단계 수 | 근거 |
|---|---|---|---|---|---|
| 냉 | 28 | 0 | 0 | 28 | [boot/smoke_cold.json](boot/smoke_cold.json), [boot/smoke_cold.log.txt](boot/smoke_cold.log.txt) |
| 온 | 28 | 0 | 0 | 28 | [boot/smoke_warm.json](boot/smoke_warm.json), [boot/smoke_warm.log.txt](boot/smoke_warm.log.txt) |

스모크 28단계는 로그인 → 데모 회로 프로젝트(`v3-01`) → 조건 질문에서 정지(`requires_input`) → 재개(`completed`) → 승인 201 · 같은 승인 409 `ALREADY_APPROVED` → 견적 저장 201 → 계정 B가 A의 프로젝트 · thread · run · 견적 · 승인에 접근하면 404 → 범위 밖 질문 `v3-30` 거절(`refused`)이다.

기록된 질문 10개를 실제 멀티 에이전트 그래프에서 끝까지 돌린 결과다. LLM 응답은 `data/demo/recordings/`에서 재생한다. 모든 질문에서 상태 · 판정 · 거절 문구가 `outcomes.json`과 같았다(`matches_outcomes_json` true, `answer_equals_recording` true).

| 질문 id | 유형 | 조건 질문 | 최종 상태 | 판정 |
|---|---|---|---|---|
| `demo-rating` | rating | 없음 | completed | - |
| `demo-notsuff` | candidate_judge | `v_drop_allowed` | completed | 1N4148 `NOT_SUFFICIENT` |
| `v3-30` | other_part | 없음 | refused | - |
| `v3-36` | rating | 없음 | refused | - |
| `demo-edition` | rating | 없음 | refused | - |
| `demo-leak` | rating | 없음 | completed | - |
| `v3-03` | candidate_judge | 없음 | completed | LL4148 L0G `IDENTICAL` |
| `demo-find` | candidate_find | `v_cc` · `i_fault` · `orig_schottky` · `high_impedance` · `fast_signal` | completed | 후보 7개 모두 `ROLE_SUFFICIENT` |
| `v3-01` | candidate_judge | `v_drop_allowed` | completed | 1N4007G `ROLE_SUFFICIENT` |
| `demo-ask` | candidate_judge | `v_drop_allowed` | 3절에서 재시작 뒤 재개 | 1N4004G `ROLE_SUFFICIENT` |

근거: [boot/demo_answers.json](boot/demo_answers.json) `questions` · `resume_after_restart`, [boot/g4_restart_isolation.json](boot/g4_restart_isolation.json) 점검 6~14번. `GET /api/demo-questions`가 10개를 돌려주었고 `GET /api/demo-circuits`는 15개 회로를 돌려주었다(점검 4 · 5번).

## 3) 재시작 뒤 재개

재생 응답 + 실제 멀티 에이전트 그래프 + 실제 PostgreSQL 체크포인터(`sojafit_agent.checkpoints` · `checkpoint_writes` · `checkpoint_blobs`)에서 확인했다. 새로 만든 DB에서 `docker compose down -v; docker compose up -d` 뒤 실행했고 이 실행은 1절 시간에 들어가지 않는다.

| 단계 | 결과 | 점검 번호 |
|---|---|---|
| 조건 질문에서 정지 | `demo-ask` · `v3-01` 모두 `run_started` → `status` → `requires_input`, 빠진 조건 `v_drop_allowed`, `GET /api/runs/{id}`가 `requires_input` | 15, 16, 18, 19 |
| 재시작 | `docker compose restart api`. api 프로세스 PID 25205 → 29452, `StartedAt` 2026-11-12T20:20:28Z → 20:22:34Z(UTC), db 컨테이너(PID 24881, `StartedAt` 20:20:23Z)는 그대로. 재시작 뒤 `/health`까지 3.6초 | 35 |
| 재시작 뒤 상태 | 같은 세션 쿠키로 다시 로그인하지 않고 `GET /api/auth/me` 200(user_id 1). 두 run 모두 `requires_input`이고 정지 내용(interrupt)이 재시작 전과 같다. 대화 목록의 마지막 run도 같다 | 37~40 |
| 재개 | `demo-ask`에 `{"answers":{"v_drop_allowed":"1.5V"}}`, `v3-01`에 `{"answers":{}}` → 둘 다 HTTP 200, `completed`, 기록과 같은 판정(`demo-ask` 1N4004G `ROLE_SUFFICIENT`, `v3-01` 1N4007G `ROLE_SUFFICIENT`) | 44, 45 |
| 완료된 run 다시 재개 | 422 `VALIDATION_ERROR` | 46 |

체크포인트 행 수(PostgreSQL 조회):

| 시점 | `checkpoints` 전체 / 이 thread | `checkpoint_writes` 전체 / 이 thread | `checkpoint_blobs` 전체 / 이 thread | `store` 전체 |
|---|---|---|---|---|
| `demo-ask` 정지 직후 | 112 / 9 | 685 / 61 | 371 / 30 | 0 |
| `v3-01` 정지 직후 | 121 / 9 | 746 / 61 | 401 / 30 | 0 |
| 재시작 직전 | 152 / 9 | 939 / 61 | 507 / 30 | 3 |
| 재시작 직후 | 152 / 9 | 939 / 61 | 507 / 30 | 3 |
| `demo-ask` 재개 뒤 | 158 / 15 | 964 / 86 | 524 / 47 | 3 |
| `v3-01` 재개 뒤 | 164 / 15 | 989 / 86 | 541 / 47 | 3 |

재시작 전후 행 수가 같다(점검 36). 승인 행은 재시작 전후 모두 `approvals` 1 · `quotes` 1이다(점검 43). 근거: [boot/checkpoint_rows.txt](boot/checkpoint_rows.txt), [boot/demo_answers.json](boot/demo_answers.json) `resume_after_restart`, [boot/api_log_summary.txt](boot/api_log_summary.txt)(api 로그의 종료 · 시작 줄 2쌍).

## 4) 계정 분리

데모 계정 A(user_id 1)와 B(user_id 2). 52개 점검이 모두 통과했다(실패 0, 해당 없음 0). 근거: [boot/g4_restart_isolation.json](boot/g4_restart_isolation.json) `passed` 52 · `total` 52, 점검별 기록 [boot/g4_restart_isolation.log.txt](boot/g4_restart_isolation.log.txt).

| 점검 묶음 | 점검 번호 | 결과 |
|---|---|---|
| 로그인 · 데모 목록 | 1~5 | A · B 로그인 200, 서로 다른 user_id, 질문 10개 · 회로 15개 |
| 기록 질문 실행 | 6~14 | 9개 질문이 기록과 같은 결과(2절) |
| 정지 run 저장 · 체크포인트 행 | 15~20 | 3절 |
| 사용자 사실 기억 | 21~26 | A가 3칸(`affiliation` · `job_role` · `mounting_preference`) 저장 200. 다른 user id를 담은 요청 본문은 422 `VALIDATION_ERROR`. B 조회는 0칸. B의 질문 결과에 `profile_hints` 없음, A의 같은 질문에는 3칸이 붙음. 임베딩 키가 없어 검색은 순위 없는 목록 |
| 승인 · 견적 | 27~29, 43 | A가 승인 201, 같은 승인 다시 409 `ALREADY_APPROVED`, DB 승인 행 1, 견적 저장 201. B가 A의 승인 · 견적 · 견적 목록 접근은 404. 승인 사례 목록은 A 1건, B 0건 |
| 재시작 전 B → A, A → B | 30~34 | 상대 계정의 프로젝트 · thread · run · 견적에 GET · PATCH · POST · DELETE · resume · recover 모두 404 `NOT_FOUND`. 서로의 목록에 상대 객체 없음. B의 접근 뒤에도 A의 프로젝트 · thread · run · 희생용 프로젝트는 200 |
| 재시작 뒤 사실 · 승인 | 41~43 | A의 사실 3칸은 저장한 값과 같고, B는 여전히 0칸. 승인은 409, B → A 승인은 404 |
| 재시작 뒤 B → A, A → B | 47~51 | B의 정지 run(`demo-notsuff`)을 재개하면 `completed`, 1N4148 `NOT_SUFFICIENT`, `profile_hints` 없음. 양방향 접근은 모두 404, 목록에 상대 객체 없음 |
| 재시작 뒤 B의 기록 질문 | 52 | 거절 질문(`v3-30`)이 기록과 같은 결과, `profile_hints` 없음 |

옛 14항목([local_g4_isolation_2026-11-09.json](../threads/local_g4_isolation_2026-11-09.json), 커밋 `f6b6d7e`)과의 대응. 옛 기록은 합성 데모 질문으로 14개를 확인했다.

| 옛 번호 | 옛 항목 | 새 점검 번호 | 달라진 점 |
|---|---|---|---|
| 1 | 데모 A 로그인 | 1 | 같음 |
| 2 | 후보 판정 질문이 조건 질문에서 정지 | 15, 18 | 기록 질문 2개에서 확인 |
| 3 | 재시작 뒤 같은 대화가 정지 상태 | 38, 39 | 정지 내용 동일 여부까지 비교 |
| 4 | 재시작 뒤 조건에 답하고 재개 → 완료 | 44, 45 | 기록과 같은 판정까지 비교. 옛 항목의 `can_approve` true 확인은 이어받지 않았다. 현재 코드의 `can_approve`는 항상 `False`([backend/conversations/memory_service.py](../../../backend/conversations/memory_service.py) 392줄)라 승인 가능 여부는 승인 요청의 201로 확인했다 |
| 5 | 같은 승인 요청 두 번 → 승인 1건 | 27 | 옛 기록은 200 · 200, 현재는 201 · 409 `ALREADY_APPROVED`. DB 승인 행은 1건으로 같다 |
| 6 | 내 설정(기억 3칸) 저장 | 21 | 같음 |
| 7 | 표현을 바꾼 질문으로 기억 검색 | 22 | 같음(순위 없는 목록) |
| 8 | 다른 사용자 id를 담은 요청 거절 | 23 | 같음(422) |
| 9 | 데모 B 로그인 | 2 | 같음 |
| 10 | A와 B는 다른 사용자 | 3 | 같음 |
| 11 | B가 A의 대화 조회 → 404 | 30, 34, 48, 49 | GET · PATCH · POST · DELETE · resume · recover로 넓히고 A → B 방향과 재시작 뒤를 더했다 |
| 12 | B가 A의 대화 승인 → 404 | 29 | 승인 · 견적 · 견적 목록 · 승인 사례로 넓혔다 |
| 13 | B의 대화 목록에 A 대화 없음 | 31, 50 | 재시작 뒤와 반대 방향을 더했다 |
| 14 | B의 기억에 A가 저장한 소속 없음 | 24, 42 | 재시작 뒤를 더했다 |

## 한계

| 항목 | 내용 |
|---|---|
| 측정 횟수 | 냉 1회, 온 1회. 반복 측정이 없어 분산을 모른다 |
| 호스트 부하 | 측정 중 같은 호스트에서 다른 작업이 돌았다(1분 평균 5.62 → 8.21). 시간이 부하의 영향을 받았을 수 있다 |
| 네트워크 | 회선 종류 · 속도를 재지 않았다. 냉 측정 시간에 내려받는 시간(852 MB)이 들어 있고 그 몫을 따로 재지 않았다 |
| 환경 | Mac 호스트 위 `docker:dind` 안에서 쟀다. Windows · Linux 호스트 · Docker Desktop은 이 측정에 없다 |
| 모델 응답 | 모든 LLM 응답이 `data/demo/recordings/`의 기록 재생이다. 실제 모델 호출 · 임베딩 · 리랭커 · 가격 조회가 아니다. 데모 코퍼스 스냅샷(DB 지문 대조) 위의 결과다 |
| 배포 환경 | 배포 주소(Cloud Run) · 배포 DB는 측정하지 않았다. 배포 서버 재시작 뒤 복원은 확인하지 않았다 |
| 재생 검사 | `scripts/demo/record_demo.py replay`(CI의 eval-replay)는 이번에 다시 돌리지 않았다. 스모크와 점검 스크립트가 기록을 서비스 경로로 재생한 것이 이 문서의 근거다 |
| 점검 스크립트 | 52개 점검 스크립트는 3회 실행했다. 앞의 2회는 비교 규칙 오류(판정 목록 이중 계산, 찾기 질문에서 잘못된 필드 비교)로 폐기했고 저장소에 없다. 이 문서는 3회째 기록이다 |
| 합성 시험 `tests/api/test_http_restart.py` | `ad8612e`의 이 시험(단일 노드 가짜 그래프 · 별도 pgvector 컨테이너)은 2회 모두 실패했다. 재시작 뒤 재개 요청이 429 `RATE_LIMITED`를 받았다. 환경 변수 `ANALYSIS_MIN_INTERVAL_SECONDS=0`만 더한 진단 실행 1회는 통과했다. 원인은 분석 호출 최소 간격 기본값 2초([backend/conversations/memory_service.py](../../../backend/conversations/memory_service.py) 180줄, `_budget` 249~262줄)이다. 실제 그래프의 재시작 · 재개는 3절이 보여 준다. 근거: [boot/http_restart_test_run1_original.txt](boot/http_restart_test_run1_original.txt), [boot/http_restart_test_run2_original.txt](boot/http_restart_test_run2_original.txt), [boot/http_restart_test_diag_interval0.txt](boot/http_restart_test_diag_interval0.txt), [boot/http_restart_test.txt](boot/http_restart_test.txt) |

## 저장소에 둔 파일 · 두지 않은 파일

원시 출력은 [boot/](boot/)에 바이트 그대로 복사했다. `.gitignore`의 `*.log` 규칙 때문에 확장자가 `.log`인 파일 7개는 이름 끝에 `.txt`만 붙였고 내용은 같다.

| 파일 | 내용 |
|---|---|
| `timeline_cold.json` · `timeline_warm.json` · `timeline_prep.json` | 시각표, 구간 시간, 빌드 단계 시간 |
| `environment.json` · `empty_before.txt` | 호스트 · 컨테이너 환경, 시작 시 빈 엔진 |
| `smoke_cold.json` · `smoke_warm.json` · `smoke_*.log.txt` | 스모크 28단계 결과와 출력 |
| `demo_answers.json` · `g4_restart_isolation.json` · `g4_restart_isolation.log.txt` · `checkpoint_rows.txt` · `api_log_summary.txt` | 기록 질문 결과, 52개 점검, 체크포인트 행 수, api 로그 요약 |
| `compose_up_cold.log.txt` · `compose_up_warm.log.txt` · `compose_down_warm.txt` · `cold_driver.log.txt` · `warm_driver.log.txt` · `docker_events_cold.jsonl` | 기동 출력과 컨테이너 이벤트 |
| `http_restart_test*.txt`(4개) | 합성 시험의 원본 2회, 간격 0 진단 1회, 요약 |
| `HOW.md` · `scripts/` | 측정 절차와 스크립트 6개(`boot.py` · `analyze.py` · `login.py` · `g4.py` · `restart_test.sh` · `restart_test_interval0.sh`) |

두지 않은 파일:

| 파일 | 이유 |
|---|---|
| `docker_events_warm.jsonl`(630,156 B) | 300 KB를 넘는다. 온 측정의 시간은 `timeline_warm.json`에 있다 |
| 진단용 시험 복사본 `test_http_restart_DIAG.py` | 이름이 `test_*.py`라 pytest가 수집할 수 있다. 진단 결과는 `http_restart_test_diag_interval0.txt`에 있다 |
| 폐기한 점검 스크립트 실행 2회(`run1_discarded/` · `run2_discarded/`) | 비교 규칙 오류로 폐기한 기록이다 |

`HOW.md`는 저장소에 없는 폴더(`../boot/`, `run1_discarded/`, `run2_discarded/`)와 위에서 두지 않은 진단 복사본을 가리킨다. 복사한 파일에 비밀값 · 토큰 · 쿠키 값 · 이메일 · 로컬 사용자 경로는 없다(정규식 검사와 gitleaks 폴더 검사 발견 0건). 복제 스크립트 `boot.py`는 GitHub 토큰을 환경 변수 `$GH_TOKEN`으로만 받으며 값은 들어 있지 않다.

## 재현

[boot/HOW.md](boot/HOW.md)의 절차다. 요약:

```bash
# 1) 빈 dind 컨테이너 (포트 공개 없음)
docker run -d --privileged --name d10b-dind-1113 -e DOCKER_TLS_CERTDIR= docker:dind
# 2) 준비: dind 안에 git python3 py3-httpx tzdata 설치, 빈 엔진 상태 기록, 도구 복사
python3 boot/scripts/boot.py prep
docker cp boot/scripts/login.py d10b-dind-1113:/tools/login.py
# 3) 냉 측정: clone → docker compose up --build → /health 폴링 → 데모 로그인 → 스모크
python3 boot/scripts/boot.py cold
# 4) 온 측정: docker compose down -v 뒤 같은 up
python3 boot/scripts/boot.py warm
# 5) 재시작 · 계정 분리 52개 점검 (새 DB에서)
docker cp boot/scripts/g4.py d10b-dind-1113:/tools/g4.py
docker exec -w /work/proj3-b d10b-dind-1113 python3 /tools/g4.py
# 6) 시간표 병합
python3 boot/scripts/analyze.py
```

`boot.py`는 비공개 저장소를 받으려고 `gh auth token`의 토큰을 쓴다. 공개 저장소이거나 다른 방법으로 clone할 수 있으면 그 단계만 바꾼다. 합성 시험 재현: `boot/scripts/restart_test.sh`(원본), `boot/scripts/restart_test_interval0.sh`(간격 0).
