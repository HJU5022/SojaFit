# D12 재측정 증거: 지금 코드 `799ae636` (2026-11-17)

강사 11/16 체크포인트(2조) 코멘트 중 측정이 필요한 것과, README · EVAL_REPORT · GATES의 "지금 시스템" 수치를 지금 `main`(`799ae636`, PR #147 병합, 11-17 04:45 KST)으로 다시 잰 기록이다. 코드 · 평가셋은 바꾸지 않았다. 측정 시각은 모두 KST다.

## 결과 요약 [실측]

| 수치 | 이전 → 지금 | 원시 | 비용 |
|---|---|---|---|
| 동결 v3 게이트 2세트(운영 설정 `DEMO_MODE=0 EVAL_WEB=1 WEB_PREFETCH=1`, 따로 실행한 1세트 × 2) | 마지막 채택 구성 R1(11-14 `b790004`) set1 50/50 · p50 6.8 · p95 10.5초, set2 48/50 · 5.9 · 12.1초 → **A 49/50 · p50 5.5 · p95 16.7초, B 49/50 · 4.8 · 9.1초**(두 세트 모두 실패 v3-16 `wrong_citation`, 무관 거절 25/25, 지어낸 답 0). `gate_report` 기준 미달: A는 p95, B는 없음 | A [gate/set1.json](gate/set1.json) · [gate_report.txt](gate/gate_report.txt), B [gate/set_b/set1.json](gate/set_b/set1.json) · [gate_report.txt](gate/set_b/gate_report.txt) | LLM $0.0361 · $0.0355(실행기 `cost_usd` 합) |
| 서비스 검색(`run_retrieval_service`, R1 84 + v2 19) | 11-04 #26: 고르기용 46 0.8587 · 확인용 38 0.9079 · v2 19 0.8246 · `retrieve()` p50 1.22 · p95 2.04초 → **0.8152 · 0.9079 · 0.7939 · 0.53 · 0.87초** | [retrieval/service_r1_2026-11-17.json](retrieval/service_r1_2026-11-17.json), [run.log.txt](retrieval/run.log.txt) | OpenRouter $0.0005 + Voyage(미측정) |
| 새 clone 키 없는 기동(빈 `docker:dind`, `docker compose up --build`) | 11-16 `3ce5abdc` 1회 242.8초 → **6회 중앙값 239.4초(148.9 ~ 296.0)**, 모두 600초 안 | [boot/](boot/) | 0 |
| 키 없는 데모 스모크(`--demo --refusal`) | 28/28 → **6회 모두 28 통과 · 0 실패 · 0 건너뜀** | `boot/run*/smoke_cold.json` | 0 |
| CI 재생 동일성(`record_demo.py replay`, 새 `-p` 프로젝트) | (이전 기록 없음) → **"재생 결과가 기록과 같습니다", 종료 0** | [checks/replay_check.txt](checks/replay_check.txt) | 0 |
| 전체 pytest(Linux 컨테이너) | 11-16 `4c5afc1e` 2,495 통과 · 0 실패 · 190 건너뜀(한 프로세스) → **한 프로세스 전체 실행은 3회 모두 멈춤**(84 ~ 85%, 새 스레드 시작). 폴더마다 따로 돌리면 **2,997 통과 · 0 실패 · 205 건너뜀** | [checks/pytest_by_dir_linux.txt](checks/pytest_by_dir_linux.txt), 멈춘 3회: [1](checks/pytest_full_linux_hang_run1.txt) · [2](checks/pytest_full_linux.txt) · [3](checks/pytest_full_linux_ignore_card_find.txt) | 0 |
| 동결 평가셋 검사(`freeze.py --check`) | 11-16 바뀐 파일 없음 → **바뀐 파일 없음, 종료 0** | [checks/freeze_check.txt](checks/freeze_check.txt) | 0 |
| gitleaks 이력 전체 | 11-13 `556384b` 828 커밋 0건 → **1,250 커밋 0건, 종료 0** | [checks/gitleaks_full_history.txt](checks/gitleaks_full_history.txt) | 0 |
| API 동작 · 경로 수 | SPEC 4절 동작 60 · 경로 49(문서 53 · 42) → **60 · 49(문서 53 · 42)**, 운영 `/openapi.json`도 53 · 42 | [checks/routes.txt](checks/routes.txt), [prod_unauth/unauth_checks.txt](prod_unauth/unauth_checks.txt) | 0 |
| 데모 코퍼스(compose `corpus-load`) | 42문서 · 1,556청크 → **42 · 1,556** | `boot/run1/compose_up_cold.log` | 0 |
| 로컬 DB 코퍼스(`sojafit-live-db`, 게이트 · 검색이 읽은 DB) | (운영 DB 11-16: 51,967) → **문서 1,360 · 청크 51,967 · 임베딩 51,967**, 저장 해시 목록 sha256 `82dff159…` = 저장소 목록 | [checks/local_db_counts.txt](checks/local_db_counts.txt) | 0 |
| Langfuse 점수(운영 프로젝트, v3 API) | 11-16: 트레이스 1개에 점수 15개 확인 → **숫자 · 참거짓 점수 40,826개 + 범주 점수 16,372개가 트레이스 4,109개에 붙어 있음(11-10 ~ 11-16 UTC), 11-17 게이트 50개 트레이스에 700개** | [langfuse/](langfuse/) | 0 |
| 경보(Cloud Monitoring, 읽기만) | 11-16 설정 → **가동 확인 1 · 경보 정책 1 · 메일 채널 1, 11-16 09:41 ~ 11-17 04:55 실패 0** | [monitoring/](monitoring/) | 0 |

유료 실행의 실행 전 어림과 실제 값: [cost_log.md](cost_log.md). 합계: LLM $0.0721(실행기 기록, OpenRouter 키 사용액 차 $0.0803은 다른 작업 포함 가능) + Voyage · Exa 미측정(어림 ≤ $0.6). 상한 $8 안.

## 강사 코멘트별

### ④ 현재 배포 리비전에서 로그인 뒤 25단계 — 하지 않음, 조장용 명령

운영에 평가용 계정 비밀번호를 넣는 일이라 이번 측정에서 하지 않았다. 지금 리비전은 `sojafit-api-main-799ae636-1117`(이미지 `…/sojafit-api@sha256:25aabdc8…`, 11-17 05:03 KST 트래픽 100%, `maxScale` 1 · `minScale` 0)이다.

스크립트는 `scripts/smoke/http_smoke.py`이고 계정은 환경변수 `SMOKE_A_EMAIL` · `SMOKE_A_PASSWORD` · `SMOKE_B_EMAIL` · `SMOKE_B_PASSWORD`에서만 읽는다(명령줄 인자로 받지 않음, Secret Manager에 이 이름의 비밀은 없다: `gcloud secrets list` 이름 확인). 11-13 통과 기록과 같은 옵션이다([d10/deploy_574de79](../d10/deploy_574de79/README.md)). 저장소 루트(지금 `main`)에서:

```bash
export SMOKE_A_EMAIL='<A 이메일>' SMOKE_B_EMAIL='<B 이메일>'; read -rs SMOKE_A_PASSWORD && export SMOKE_A_PASSWORD; read -rs SMOKE_B_PASSWORD && export SMOKE_B_PASSWORD
uv run python scripts/smoke/http_smoke.py --base-url https://sojafit-api-559369539072.asia-northeast3.run.app --confirm-live --upload --pause-before-resume
```

- `--pause-before-resume`은 4단계(조건 질문에서 멈춤) 뒤 Enter까지 기다린다. 그사이 서버 재시작(같은 이미지의 새 리비전, 11-13 절차)을 하려면 다른 터미널에서:
  `gcloud run deploy sojafit-api --project sojafit --region asia-northeast3 --image asia-northeast3-docker.pkg.dev/sojafit/cloud-run-source-deploy/sojafit-api@sha256:25aabdc847a7d6b0139083a092532d49af59926fbc5d3944b20cf6f6a7461366 --revision-suffix main-799ae636-rs --no-traffic --tag restart-799ae636`
  뒤 `gcloud run services update-traffic sojafit-api --project sojafit --region asia-northeast3 --to-revisions sojafit-api-main-799ae636-rs=100`. 재시작을 빼려면 `--pause-before-resume`을 지우고 Enter 없이 돈다.
- 4 · 5단계가 실제 LLM을 부른다(11-13 어림 2 ~ 5회). 계정마다 하루 예약 토큰 한도가 있고 UTC 0시(09:00 KST)에 초기화된다(`scripts/smoke/SMOKE.md`).
- 결과는 `scripts/results/smoke/smoke_<호스트>_<날짜>_<시각>.json`(비밀번호 · 이메일 · 답 글 없음). 통과 수와 이 파일을 GATES G1 · G4에 적는다.

### ④ 빈 엔진 기동 6회 측정의 원시 로그

- 그 표: [docs/research/docker-cold-start-measurements.md](../../../docs/research/docker-cold-start-measurements.md) 1절 「G2」 표(`38506fb` · `5f697b2` 각 3회, Docker Engine 27.5.1, **`docker compose up` → `/health`**)와 4절 KiCad 포함 · 분리 표(`9186719` 각 3회).
- 저장소에 있는 것: 회차별 값과 단계 시각 [scripts/results/docker_performance/](../../../scripts/results/docker_performance/)(`profile_lazyload_six_run_stages_2026-11-14.csv` · `profile_lazyload_six_run_records_2026-11-14.json`, KiCad 포함 · 분리 `kicad_in_api_vs_renderer_split_*`). 없는 것: compose · 빌드 원시 로그(실험 PC `바탕화면/3차 프로젝트/` 아래, 같은 문서 7절).
- 그래서 지금 `main`으로 새로 쟀다(아래 「새 clone 기동」). 6회 표와는 **다른 계열**이다: 이 측정은 docker-in-docker 29.9.3에서 **clone 시작 → `/health`**(11-13 · 11-16 저장소 측정과 같은 방법)이고, 6회 표는 Engine 27.5.1에서 `up` → `/health`다. 둘 다 아래 표에 적었다.

### 새 clone 기동 [실측]

빈 `docker:dind`(29.9.3, `docker@sha256:7bf70dcb…`, 11-16 측정과 같은 다이제스트)를 회차마다 새로 띄워(이미지 · 볼륨 · 빌드 캐시 0, `run<n>/empty_before.txt`) GitHub `main`을 clone하고 `799ae636`으로 checkout한 뒤(`main_at_clone`도 6회 모두 `799ae636`) `.env` 없이 README의 `docker compose up --build` 한 줄. `/health` 200 뒤 데모 A 로그인, 스모크 `scripts/smoke/http_smoke.py --base-url http://localhost:8000 --demo --refusal`. 호스트는 Apple M2, Docker 29.7.2. 스크립트 [boot.py](boot/scripts/boot.py)(11-16 사본에서 바꾼 곳: 커밋 고정 · 회차별 폴더 · 부하 대기 없앰, 첫 줄 설명), [loop.sh](boot/scripts/loop.sh), 표는 [summarize.py](boot/scripts/summarize.py) → [summary.json](boot/summary.json).

| 회차 | 시작(KST) | clone | **clone 시작 → `/health` 200** | `up` → `/health` 200 | 스모크 | 내려받은 양 | 호스트 1분 부하(`up` 때) |
|---|---|---:|---:|---:|---|---:|---:|
| 1 | 04:54:09 | 12.2초 | **266.3초** | 254.0초 | 28 통과 · 0 실패 · 0 건너뜀 | 591 MB | 4.95 |
| 2 | 05:09:55 | 7.5초 | **296.0초** | 288.4초 | 28 · 0 · 0 | 594 MB | 9.81 |
| 3 | 05:15:48 | 8.7초 | **244.5초** | 235.8초 | 28 · 0 · 0 | 591 MB | 14.70 |
| 4 | 05:20:33 | 7.3초 | **234.3초** | 227.0초 | 28 · 0 · 0 | 593 MB | 9.63 |
| 5 | 05:25:12 | 7.7초 | **148.9초** | 141.2초 | 28 · 0 · 0 | 592 MB | 8.94 |
| 6 | 05:28:33 | 13.3초 | **207.6초** | 194.3초 | 28 · 0 · 0 | 593 MB | 12.26 |
| 중앙값(범위) | | | **239.4초**(148.9 ~ 296.0) | 231.4초(141.2 ~ 288.4) | 6/6 통과 | | |

- 기준 600초 안이다. 11-16 `3ce5abdc` 1회 242.8초, 11-13 `ad8612e` 1회 243.9초와 같은 방법이다.
- 시간은 호스트 부하에 크게 흔들렸다. 같은 호스트에서 다른 작업(다른 세션의 작업, 이 측정의 v3 게이트 실행(1회차와 겹침) · pytest 컨테이너(2 ~ 5회차와 겹침))이 함께 돌았다. 회차 간 차이(최대 147초)는 코드 차이가 아니다.
- 1회차 dind에서 이어서 전체 pytest와 CI 재생 검사를 했다(아래). 그 시간은 표에 들지 않는다.
- 회차별 원시: `boot/run<n>/`의 `timeline_cold.json`(이벤트 시각) · `compose_up_cold.log`(`docker compose up --build` 전체 출력, 줄마다 호스트 시각) · `docker_events_cold.jsonl` · `smoke_cold.json` · `smoke_cold.log` · `empty_before.txt` · `timeline_prep.json`.

### ④ 동결 직전 pytest · freeze · gitleaks

대상은 `799ae636`의 깨끗한 clone이다. Linux 이미지는 저장소 Dockerfile로 만든 API 이미지(1회차: 기동 1회차 dind 안의 `proj3-b-api`, 2 ~ 4회차: 호스트 Docker에서 같은 Dockerfile로 빌드한 `sojafit-d12-api:799ae636`, arm64, python 3.12, cairo 포함)이고, 11-16 기록과 같은 방법(`--user root`, venv는 `/tmp/venv`에 따로, `uv run --locked pytest -p no:cacheprovider -rs`)이다.

| 회차 | 방법 | 결과 | 원시 |
|---|---|---|---|
| 1 | 전체를 한 프로세스로 | **멈춤**: 수집 3,202개, 84%에서 `tests/rag/test_card_find.py` 첫 시험이 5분 넘게 진행 없음 → `SIGABRT`로 스레드 덤프를 남기고 끝냄(종료 134) | [pytest_full_linux_hang_run1.txt](checks/pytest_full_linux_hang_run1.txt) |
| 2 | 같은 방법, `-o faulthandler_timeout=240` | **같은 곳에서 멈춤**(240초 덤프 뒤 `docker kill`) | [pytest_full_linux.txt](checks/pytest_full_linux.txt) |
| 3 | `--ignore=tests/rag/test_card_find.py` | **다음 파일 `tests/rag/test_card_read.py`에서 멈춤**(120초 덤프 뒤 `docker kill`) | [pytest_full_linux_ignore_card_find.txt](checks/pytest_full_linux_ignore_card_find.txt) |
| 4 | `tests/` 아래 폴더마다 따로(13개 프로세스) | **2,997 통과 · 0 실패 · 205 건너뜀**(합 3,202 = 1회차 수집 수). 건너뜀은 전용 `TEST_DATABASE_URL` 등(`-rs` 목록) | [pytest_by_dir_linux.txt](checks/pytest_by_dir_linux.txt) |

- 멈춘 곳은 세 번 모두 새 스레드 시작이다: `backend/rag/card_find.py:296`(`gather`의 `ThreadPoolExecutor.submit`) · `backend/rag/card_read.py:240`(`llm_read`) → `threading.Thread.start()`가 `_started.wait()`에서 돌아오지 않는다. 살아 있는 다른 스레드는 Langfuse 프롬프트 캐시 · OpenTelemetry 작업자뿐이었다.
- 같은 이미지에서 `tests/rag/test_card_find.py`만 돌리면 25 통과(2.41초), `tests/rag`만 돌리면 207 통과 · 26 건너뜀이다. `tests/projects` · `multi_agent` · `api` · `services` 중 하나와 `test_card_find.py`를 함께 돌려도 멈추지 않았다. 앞선 시험이 쌓은 상태에 따라 멈추는 것으로 보이며 원인은 찾지 않았다 `[추정]`. 11-16 `4c5afc1e`에서는 같은 방법으로 67초에 끝났다(`../d10/freeze_check_2026-11-16/`). 그 뒤 `card_find.py`를 바꾼 커밋은 `bf76cf5e`(프로세스 공유 캐시) · `6ca25d48`(공용 DB 풀)이다.
- 4회차 로그의 `exit(<폴더>)` 줄은 `tail`의 종료 코드다(측정 스크립트 실수). 판정은 폴더마다 마지막 요약 줄로 했다.
- macOS 호스트 전체 실행은 이번에 하지 않았다.

동결 평가셋 검사 `python evals/runners/freeze.py --check`: "동결 이후 바뀐 파일: 없음", 종료 0([freeze_check.txt](checks/freeze_check.txt)).

gitleaks `v8.30.1`(d10과 같은 이미지 digest), 저장소 `.gitleaks.toml`(허용 5) · `.gitleaksignore`(지문 14줄), `--redact`, `--log-opts="799ae636"`: **1,250 커밋 검사, 발견 0, 종료 0**([gitleaks_full_history.txt](checks/gitleaks_full_history.txt)). `git rev-list --count` 1,494(병합 제외 1,252).

CI 재생 검사(`.github/workflows/ci.yml` `eval-replay`와 같은 명령, 기동 1회차 dind, 새 프로젝트 `-p sojafit-ci`): 기록 질문 10개를 재생해 "재생 결과가 기록과 같습니다", 종료 0([replay_check.txt](checks/replay_check.txt)).

### ② 검색 품질의 새 전후 측정

같은 실행기 `evals/runners/run_retrieval_service.py`(사전 등록 #26 설정 `C|v4large|hybrid|bm25|T0|60|50|Q3|part+kind|rerank-3`, k 20)로 11-04 결과와 견줬다. 대상은 지금 코드 `799ae636`과 로컬 DB(v4h 코퍼스, 위 표). `DEMO_MODE=0`(실행기가 강제).

| | 11-04 #26 (`0194592`, v1 코퍼스 52,244청크) | 11-17 d12 (`799ae636`, v4h 51,967청크) |
|---|---:|---:|
| R1 고르기용 46 Page Recall@5 | 0.8587 | 0.8152 |
| R1 확인용 38 Page Recall@5 | 0.9079 | 0.9079 |
| R1 84 Page Recall@5 · Page MRR | 0.8810 · 0.7750 | 0.8571 · 0.7557 |
| v2 19 Page Recall@5 | 0.8246 | 0.7939 |
| `retrieve()` p50 · p95 | 1.22 · 2.04초 | 0.53 · 0.87초 |

- Page Recall@5가 달라진 문항: R1 r1-042 · r1-086 · r1-098(1 → 0), r1-097(0 → 1). v2 draft30-m04(0.5 → 0.25), draft50-n04(0.667 → 0.333).
- 두 측정 사이에 코퍼스(v1 → v4h)와 검색 코드(`backend/rag/retrieve.py` 최근 `6ca25d48` 11-16 21:08, `3204b898`)가 함께 바뀌었다. 어느 쪽 때문인지 나누지 않았다. "개선"이 아니라 지금 코드의 재측정이다.
- 11-16 후보 수 실험(R1 84 Page Recall@5 0.8810, `run_retrieval_r1 cands`)은 다른 실행기다. 위 11-04 R1 84의 0.8810은 고르기용 · 확인용을 문항 수로 합친 값이다.

### ③/④ Langfuse 점수

운영 프로젝트(`SojaFit_v2`, `cmwadynwy063mad0eyrziwgqt`, 키는 운영 서비스와 같은 Secret Manager 값)에서 읽기만 했다. 옛 `GET /api/public/scores` · `/api/public/metrics`는 2026-11-16 제거돼(응답의 `_deprecation`) `GET /api/public/v2/metrics`와 `GET /api/public/v3/scores?fields=core,subject`를 썼다. 스크립트: [query_scores.py](langfuse/query_scores.py).

| 확인 | 값 (2026-11-17 05:2x KST 조회) |
|---|---|
| 점수 이름별 개수(전 기간) | 숫자 · 참거짓: `latency_s` 4,108 · `llm_calls` 4,108 · `tries` · `not_found` · `docs_found` · `passed_cards` 각 4,093 · `hops` 3,999 · `pass` 3,965 · `cost_usd` 3,935 · `fake_citations` · `uncited_sentences` 각 2,124 · `ragas_context_precision` 46 · `ragas_faithfulness` 44 · `osc_chunk_keycheck` 1. 범주: `path` · `question_type` · `answer_metric` · `refusal_code` 각 4,093 |
| 날짜별(UTC) 점수 수 · 점수가 붙은 트레이스 수 | 11-10 13 · 1, 11-11 5,924 · 418, 11-12 2,960 · 244, 11-13 700 · 50, 11-14 9,806 · 700, 11-15 14,844 · 1,060, 11-16 22,951 · 1,636(숫자+범주 점수 합 · 숫자 점수가 붙은 트레이스. UTC 날짜라 11-16 UTC에 11-17 KST 05시 게이트가 들어 있다). 트레이스 합 4,109 = `latency_s` 4,108 + `osc_chunk_keycheck`만 있는 1개. 트레이스 id 차원은 한 번에 1,000행까지라 하루 · 3시간 · 1시간으로 나눠 물었다 |
| 11-17 게이트 세트(세션 `gate-dataset_v3-1117-0457-set1`) | 04:58:29 ~ 05:03:28 KST에 점수 700개가 트레이스 50개에 붙었다(관련 25문항 15개씩, 비관련 25문항 13개씩, 환경 `eval`). 50개 트레이스 id가 [gate/set1.json](gate/set1.json)의 `trace_url` 50개와 모두 같다 |
| 화면 확인용 트레이스 | **`5fa5c6c56187c8a38326de96fd57dfa5`**(11-17 게이트 v3-01, 점수 15개: `pass`=True · `answer_metric`=cited_gold · `latency_s`=8.2 · `path` 등, 결과 파일과 같은 값). 주소: `https://cloud.langfuse.com/project/cmwadynwy063mad0eyrziwgqt/traces/5fa5c6c56187c8a38326de96fd57dfa5` |

원시: [metrics_v2.json](langfuse/metrics_v2.json)(질의와 응답), [trace_5fa5c6c5….json](langfuse/trace_5fa5c6c56187c8a38326de96fd57dfa5.json), [scores_since_2026-11-16.json](langfuse/scores_since_2026-11-16.json)(11-17 04:50 KST 이후 점수 전부). 응답에 키 · 메일 주소는 없다(`grep` 0건). 전 기간 점수를 v3 목록으로 모두 받는 것은 공개 API 한도(30회/창, 한 번 100개)로 13분에 끝나지 않아 멈췄고 개수는 metrics로 셌다. 화면 캡처는 이 측정에 없다.

### ④ 운영 중단 경보

읽기만 했다(`gcloud monitoring uptime list-configs`, Monitoring API `alertPolicies` · `notificationChannels` · `timeSeries` GET). `gcloud alpha monitoring policies list`는 alpha 구성요소가 설치되지 않아 묻는 창에서 멈췄고, 설치하지 않고 같은 내용을 REST로 읽었다. 만들거나 바꾼 것은 없다.

| 항목 | 값 |
|---|---|
| 가동 확인 | 1개: `sojafit-api /health`(`sojafit-api-health-eRGzPUOyMbY`), 호스트 `sojafit-api-559369539072.asia-northeast3.run.app`, HTTPS GET `/health`, 5분 주기, 제한 10초, 2xx만 통과 |
| 경보 정책 | 1개: `SojaFit 운영 다운: /health 가동 확인 실패`, 켜짐, 조건 `check_passed` 거짓을 센 값이 1 초과(20분 정렬), 자동 닫힘 30분, 2026-11-16 09:40 KST 생성 |
| 알림 채널 | 1개, 종류 email, 켜짐(주소는 파일에서 지움) |
| 최근 결과 | 11-16 09:41 ~ 11-17 04:55 KST `uptime_check/check_passed` 점 8,292개(지역 6곳)가 모두 참, 거짓 0 |

원시: [uptime_configs.json](monitoring/uptime_configs.json), [alert_policies.json](monitoring/alert_policies.json), [notification_channels.json](monitoring/notification_channels.json), [uptime_check_passed_24h.json](monitoring/uptime_check_passed_24h.json)(메일 주소 지움). 이 기간에 경보가 열린 기록은 이 API로 보지 못했다(사건 목록 API는 쓰지 않았다). 11-16 시험 경보는 [d10/alerting_2026-11-16.md](../d10/alerting_2026-11-16.md).

### 지금 코드의 v3 게이트(유료)

`evals/runners/run_gate.py evals/dataset_v3.jsonl --sets 1 --keep-going`을 두 번 따로 돌렸다(A 04:57:55 ~ 05:03:31, B 05:32:51 ~ 05:36:52). 환경 `DEMO_MODE=0 DEMO_REPLAY=0 EVAL_WEB=1 WEB_PREFETCH=1 EXA_WEB_SEARCH_ENABLED=1 GATE_WARMUP=1 FIND_N_DOCS=5 RAGAS_ENABLED=0 LLM_PROVIDER=openrouter`, DB는 위 로컬 DB, 코드는 `799ae636` 깨끗한 clone(결과 파일 `git` = `799ae636`). 집계는 `gate_report.py`.

| 세트 | 통과 | p50 · p95 | 가장 느린 문항 | 세션 | 같은 시간 호스트 |
|---|---|---|---|---|---|
| A | 49/50(cited_gold 24 · correct_refusal 25 · wrong_citation 1) | 5.5 · **16.7초** | v3-15 29.5초 · v3-16 18.3초 | `gate-dataset_v3-1117-0457-set1` | 기동 1회차 빌드와 겹침, 1분 부하 12 ~ 16 |
| B | 49/50(같은 분포) | 4.8 · **9.1초** | v3-16 12.8초 · v3-15 9.9초 | `gate-dataset_v3-1117-0532-set1` | 시작 때 1분 부하 12.3 |

- 두 세트 모두 v3-16(UF4007 trr)만 `wrong_citation`이다. EVAL_REPORT 11-2절 8행(웹 켬 Docker 9회 모두 실패)과 같은 문항이다.
- 같은 코드 두 세트의 p95가 7.6초 다르다. A는 같은 호스트의 docker 빌드와 겹쳤다. p95 10초 목표 충족 여부를 한 세트로 말할 수 없다.
- LLM은 OpenRouter 경유다(`claude_direct` false). 11-14 R1 등 이전 행은 `claude_direct` true(Anthropic 직통)라 시간 비교 조건이 다르다.

## 다시 못 잰 것

예전 값과 날짜를 그대로 둔 수치다(README · EVAL_REPORT · GATES의 해당 행).

| 수치 | 그대로 둔 값(측정일) | 이유 |
|---|---|---|
| 운영 리비전에서 평가용 계정 25단계 | 25 통과(11-13 `574de79-rs`) | 운영에 계정 비밀번호를 넣지 않는다. 위 명령을 조장이 돌린다 |
| 운영 DB 청크 본문 sha256 재계산(G3) | 51,967/51,967(11-16) | 운영 DB에 접속하지 않았다. 로컬 DB의 저장 해시 목록만 대조했다 |
| 재시작 뒤 재개 · 계정 격리 52점검(G4, `g4.py`) | 52/52(11-13 로컬) · 배포 25단계(11-13) | 다시 돌리지 않았다. 키 없는 스모크 28단계(6회)가 계정 B의 404 확인을 포함한다 |
| 온(캐시 있음) 재기동 | 11.7초(11-13) | 다시 재지 않았다 |
| v3 4세트 50/50 · 무관 거절 25/25(#50, `93a497c`), 동결 병합 뒤 2세트, 단일 그래프 48/50 | 11-10 ~ 11-12 | 지금 코드로는 멀티 그래프 운영 설정만 쟀다 |
| 웹 끔 v3 게이트 | 11-15 B3 50/50 · p95 9.7초 | 시간 안에 운영 설정(웹 켬)을 먼저 쟀다 |
| v1 검색 기준선(Recall@5 0.737 등), R1 격자(#25), v3 검색 21문항 | 11-03 · 11-13 | 서비스 경로 실행기(#26)만 다시 돌렸다 |
| 인젝션 · 신뢰 경계(EVAL_REPORT 6장), 변이 28건 | 11-11 ~ 11-16 | 다시 돌리지 않았다 |
| 대체재 비교(Codex 45/50, Terra 41/50) | 11-12 · 11-16 | 다시 돌리지 않았다 |
| Voyage · Exa 실제 청구액 | - | 키 사용액 API를 보지 않았다(어림만, cost_log) |
| pytest 멈춤의 원인 | - | 찾지 않았다(측정만). 코드는 고치지 않았다 |
| Langfuse 화면 캡처 | 없음 | 다른 사람이 맡는다. 캡처할 트레이스 id는 위에 있다 |
| `docs/research/docker-cold-start-measurements.md` 7절에 이 측정 링크 | - | 이 작업의 수정 범위(README · EVAL_REPORT · GATES) 밖이다 |

## 파일

| 경로 | 내용 |
|---|---|
| `gate/` | v3 게이트 결과(`set1.json`), `gate_report` 출력, 실행 로그 |
| `retrieval/` | 서비스 검색 재측정 결과와 실행 로그 |
| `boot/` | 새 clone 기동 회차별 폴더(`run<n>/`: 시각표 · compose 출력 · docker events · 스모크), `scripts/`(`boot.py` · `login.py` · `loop.sh`), `loop_driver.log.txt` |
| `checks/` | pytest · 재생 · freeze · gitleaks · 동작 수 · 로컬 DB 수 |
| `langfuse/` | 점수 조회 스크립트와 응답 |
| `monitoring/` | 경보 설정 · 가동 확인 결과 |
| `prod_unauth/` | 운영 주소 로그인 없는 GET |
| `cost_log.md` | 유료 실행 어림 · 실제 |

비밀값: 키는 Secret Manager에서 환경변수로만 읽고 출력 · 파일에 남기지 않았다. 커밋 전 `gitleaks dir`로 이 폴더를 검사했다(0건). `.env`는 읽지 않았다.
