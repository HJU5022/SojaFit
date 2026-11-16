# Docker Cold Start, Build Time, and Time to First Schematic PNG

2026년 11월 13~14일(KST) SojaFit 실험 기록. 로컬 개발 및 첫 기능 실험은 OSC `39a57f0`, G2 전후 비교는 `38506fb`와 `5f697b2`가 기준이다. 운영 수치는 시험 당시 리비전의 기록이다. 표의 시간은 초 단위이며, 별도 표시가 없으면 조건별 성공 회차의 중앙값이다.

| 측정 항목 | 실측 결과 | 적용 상태·범위 |
|---|---|---|
| 빈 Docker 환경에서 KiCad 포함·분리 비교 | 포함 → 분리 시 API 이미지는 **41.77% 감소**. 첫 `/health`는 **109.37 → 110.58초**, 첫 PNG는 **110.53 → 111.98초** | `main`의 **KiCad 포함·프로필 지연 로딩** 유지. 각 3회 중앙값(4절) |
| 빈 Docker 환경에서 `docker compose up`부터 첫 `/health` 응답까지 | 현재 OSC의 순차 설치 **114.159초**, 별도 재측정 **114.228초**. 같은 재측정에서 병렬 설치 **117.010초** | G2 반복 시험 모두 600초 이내 성공. 프로필 지연 로딩은 OSC에 반영했고, 병렬 설치는 적용하지 않았다. |
| 로컬 API의 첫 질문 목록 수신 시간 | 같은 조건에서 새 API **4.892초**, 미리 준비한 API에 첫 요청 **0.104초**. 준비 시간까지 포함하면 **5.118초** | 인증된 질문 목록의 JSON 수신까지. 새 API끼리 비교하면 로컬 2 CPU **4.531초** |
| 첫 회로도 PNG 수신 시간 | 새 API에서 고정 도면을 미리 PNG로 만들어 두면 **5.805 → 4.850초**. 새 도면은 **6.247 → 6.570초** | 고정 원본에 효과. 따로 준비된 API에서 실시간 변환을 요청하면 첫 PNG까지 **1.193초** |
| 운영 서비스 유휴 후 첫 응답 | 최소 0대 → 1대에서 유휴 후 프로젝트 목록 서버 응답 **14.498 → 0.324초**. 적용 후 브라우저의 검색 시작 → 첫 PNG **5.210초** | 같은 리비전 각 1회. 유휴 과금 때문에 0대로 복원. 적용 전 브라우저 PNG 시간은 미수집 |

## 1. G2 — 이미지·빌드 캐시·컨테이너·DB 볼륨이 없는 첫 실행

매회 비어 있는 Docker Engine 27.5.1과 Compose 2.33.0을 준비하고, 같은 로컬 Git 번들의 해당 소스에서 `.env` 없이 `docker compose up`을 실행했다. 명령 시작부터 `/health`가 HTTP 200과 `{"status":"ok"}`를 반환할 때까지 이미지 다운로드·빌드·DB 초기화를 포함한다. 엔진 준비와 Git 복제는 표의 시간에서 제외했다. 각 비교는 기존 → 후보를 세 번 반복했다.

| 비교 | 구성 | 1회 | 2회 | 3회 | 중앙값 |
|---|---|---:|---:|---:|---:|
| 프로필 지연 로딩 | 적용 전 `38506fb` | 112.539 | 123.556 | 117.774 | 117.774 |
| 프로필 지연 로딩 | 적용 후 `5f697b2` | 125.362 | 112.534 | 114.159 | **114.159** |
| 설치 순서 | 같은 `5f697b2`, 순차 설치 | 110.891 | 114.616 | 114.228 | **114.228** |
| 설치 순서 | 같은 소스, KiCad·Python 설치 병렬화 | 120.885 | 117.010 | 109.489 | 117.010 |

가장 이른 단회 기록은 지연 로딩 전 **108.24초**, 후 **134.34초**였다. Git 복제 시작 기준은 각각 **110.84초**, **137.46초**다. 단회 최단값과 3회 중앙값은 따로 집계했다. 지연 로딩 전후에는 `backend/api/profile.py`만 달랐고 1회차는 후보가 더 느렸다. 3.615초 차이 전부를 지연 로딩으로 설명할 수 없다. [지연 로딩 커밋](https://github.com/aihuman-7th/proj3-b/commit/5f697b28b59c9c2ccf27c447ee5bde250b0243c5)

| 측정 구간별 중앙값 | 지연 로딩 전 → 후 | 순차 → 병렬 |
|---|---:|---:|
| 명령 시작 → DB 이미지 다운로드 완료 | 16.338 → 15.442 | 17.308 → 15.437 |
| DB 이미지 다운로드 완료 → API·초기화 이미지 빌드 완료 | 90.533 → 87.488 | **85.223 → 88.563** |
| 빌드 완료 → 첫 HTTP 200 | 10.804 → 10.732 | 10.427 → 10.507 |
| KiCad·libcairo2 설치 | 55.3 → 55.8 | **53.8 → 66.3** |
| Python 패키지 설치 | 17.5 → 16.8 | 16.2 → 26.1 |
| 프런트엔드 `npm ci` | 15.6 → 14.8 | 14.1 → 15.7 |

병렬 후보는 같은 Python 베이스에서 KiCad를 설치하는 동안 별도 단계에서 `uv sync`를 실행한 뒤 `.venv`를 최종 이미지로 복사했다. 로그로 추정한 두 설치의 겹침은 중앙값 26.1초, 별도 복사는 8.4초였다. 전체 대기는 **2.782초 증가**했다. 여섯 회 모두 DB healthy, 초기화 작업 2개 종료 코드 0, KiCad 9.0.2였다. 동일한 `divider.kicad_sch`를 각 API에서 PDF와 PNG로 변환한 결과는 모두 1장, 3,508 × 2,481 px, 70,865 B였고 SHA-256은 `c169f3c9afb5661e4145424572c505a23c248a9d05b9cc1864ea014ba449d85a`였다. 응답 판독을 점검하다 중단한 예비 실행 1건은 여섯 회에서 제외했다. [Docker BuildKit](https://docs.docker.com/build/buildkit/) · [uv의 다단계 Docker 이미지](https://docs.astral.sh/uv/guides/integration/docker/)

## 2. 이미지가 준비된 환경 — 로컬 개발 실험 네 가지

기준 OSC `39a57f0`, Docker Engine 29.7.2, Compose 5.5.0. 각 방법의 변경 전후에 같은 조건을 적용하고, Docker 측정은 한 번에 하나씩 실행했다. 아래에서 빈 DB는 새 볼륨, 기존 DB는 데이터를 보존한 볼륨이다.

| 실험 | 측정 구간과 결과 | 검증·출처 |
|---|---|---|
| OSC-1. DB healthcheck 3초 → 1초 | Compose 시작 → API HTTP 200. 빈 DB **10.488 → 8.644**, 기존 DB **10.215 → 8.248**. DB healthy 자체는 각각 4.239 → 1.480, 3.952 → 2.340 | 네 조건 각 3/3. KiCad PNG 1장 70,406 B. 1초는 프로젝트 시험값. [Compose 시작 순서](https://docs.docker.com/compose/how-tos/startup-order/) · [healthcheck](https://docs.docker.com/reference/compose-file/services/#healthcheck) · [Compose 사용자 사례 #12782](https://github.com/docker/compose/issues/12782) |
| OSC-2. DB를 유지하고 API만 다시 시작 | 명령 시작 → 새 API의 HTTP 200. 전체 재기동 **12.639**, `restart api` **5.080**, `up -d --no-deps --force-recreate api` **5.644** | 각 5/5. 새 프로세스 시작을 확인. 같은 이미지에서 교체 절차를 시험했고 PNG 70,865 B 확인. [restart](https://docs.docker.com/reference/cli/docker/compose/restart/) · [up](https://docs.docker.com/reference/cli/docker/compose/up/) |
| OSC-3. npm·uv 패키지 캐시 | 소스 수정 후 재빌드 **3.444 → 4.320**, 의존성 설치 단계를 다시 실행하는 재빌드 **58.168 → 51.252** | 각 3회. 일반 소스 수정에서는 양쪽 모두 설치 레이어 캐시 적중. 패키지 캐시가 남아 있는 조건에서만 재설치가 빨라졌다. 동일 PNG 70,865 B. [BuildKit 캐시](https://docs.docker.com/build/cache/optimize/#use-cache-mounts) · [uv Docker 캐시](https://docs.astral.sh/uv/guides/integration/docker/#caching) |
| OSC-4. Compose Watch | 코드 저장 → 수정된 API의 HTTP 200. 빌드·재생성 **8.197** → `sync+restart` **5.657** | 각 5/5. 컨테이너에 반영된 파일, 새 프로세스, PNG 71,526 B 확인. [Compose Watch](https://docs.docker.com/compose/how-tos/file-watch/) · [develop 액션](https://docs.docker.com/reference/compose-file/develop/#action) |

별도 공통 시험에서는 준비된 이미지로 새 컨테이너·네트워크·빈 DB를 만들어 전체 Compose 시작 → 첫 HTTP 200을 쟀다. 기준 **9.882초(3/3)**, OSC-1 **7.755초(2/3)**, OSC-2 **10.087초(3/3)**, OSC-3 **9.977초(3/3)**, OSC-4 **9.907초(3/3)**였다. OSC-1은 한 번 `corpus-load`가 종료 코드 1로 끝나 API를 띄우지 못했다.

같은 빈 DB 조건에서 프로필 지연 로딩 전후를 다시 짝지어 측정했다. 기존은 10.904 / 10.041 / 10.453초(중앙값 **10.453**), 후보는 10.879 / 10.520 / 10.213초(**10.520**). 여섯 회 모두 성공했다. 이 시험의 명령은 `docker compose up -d --no-build --pull never`였다.

## 3. 첫 기능·첫 회로도 — 콜드스타트 후보 여덟 가지

이미지와 실험용 PostgreSQL을 준비한 뒤 API를 새로 띄웠다. 첫 기능은 인증된 `GET /api/demo-questions`의 JSON 본문 전체, 첫 회로도는 고정 로컬 원본의 manifest 요청부터 서명된 URL의 PNG 본문 전체를 받는 경로다. 표의 기동 시간은 API 시작 명령부터 본문 수신까지다. 개별 실험은 조건마다 5회씩 성공했으며 6번은 플랫폼 조사만 했다.

| 실험 | 개별 측정 결과 | 방법의 출처 |
|---|---|---|
| CS-1. 프로필 지연 로딩 | 질문 목록 **4.864 → 4.624**, health 4.649 → 4.751. 지연시킨 코드가 필요해지는 첫 프로필 변경 요청은 4.414 → 4.432 | [OSC 프로필 코드](../../backend/api/profile.py) · [Python importtime](https://docs.python.org/3/using/cmdline.html#cmdoption-X) · [Cloud Run Python 가이드](https://docs.cloud.google.com/run/docs/tips/python) |
| CS-2. DB 연결 통합 | 별도 readiness 연결의 쿼리 2개를 기존 초기화 연결에서 실행. 질문 목록 **12.021 → 11.003**, health 9.894 → 12.399. 첫 대화 SSE 재측정 5.120 → 5.404 | 프로젝트의 [API 시작 코드](../../backend/main.py) · [DB 초기화 코드](../../backend/conversations/memory_service.py) |
| CS-3. CPU 1개 → 2개 | 질문 목록 **4.975 → 4.664**, health 5.008 → 4.481. 로컬 Docker CPU 제한을 변경 | [Cloud Run CPU 및 startup CPU boost](https://docs.cloud.google.com/run/docs/configuring/services/cpu). 운영 boost의 효과는 미측정 |
| CS-4. 고정 회로도 사전 변환 | 고정 원본 첫 PNG **5.805 → 4.850**, 새 원본 **6.247 → 6.570**. 고정 PNG 한 장을 미리 만드는 데 1.123초. 양쪽에서 고정 원본 70,669 B, 새 원본 69,236 B 일치 | 프로젝트의 [회로도 제공 코드](../../backend/projects/external_schematic.py) · [원본 검증 테스트](../../tests/projects/test_external_schematic.py) |
| CS-5. API 사전 준비 | 첫 요청 시 기동하면 **5.006**, 미리 띄운 API에 첫 요청을 보내면 **0.108**. 후보의 준비 시간을 포함하면 5.171 | [Cloud Run 최소 인스턴스](https://docs.cloud.google.com/run/docs/configuring/min-instances) |
| CS-6. Cloud Run gen1·gen2 | 실행 환경과 KiCad 의존성 조사. 동일 배포 조건의 전후 시간과 gen1에서의 전체 렌더링 호환성은 미검증 | [Cloud Run 실행 환경](https://docs.cloud.google.com/run/docs/configuring/execution-environments) |
| CS-7. 기능 요청 전 health 호출 | 기동 → 질문 목록 **5.254 → 5.419**. 기동 → 고정 PNG **6.412 → 6.306**. 주기 호출로 운영 인스턴스가 유지되는지는 미측정 | [Cloud Run 최소 인스턴스](https://docs.cloud.google.com/run/docs/configuring/min-instances) · [Exodus 사용자 실험](https://exodus.elim.io/blog/cloud-run-cold-start-measured) |
| CS-8. 요청 8건을 순차 → 최대 4개 동시 처리 | 로컬 인스턴스 하나에서 기동 → 첫 완료 **5.033 → 5.226**, 전체 8건 완료 **5.223 → 5.365** | [Cloud Run 동시 요청 처리](https://docs.cloud.google.com/run/docs/about/concurrency) |

같은 DB·포트·인증 상태에서 실행 순서를 회전한 추가 비교(각 5회)에서는 OSC 기준 질문 목록 **4.892초**, 프로필 지연 로딩 **4.782초**, DB 연결 통합 **4.938초**, 2 CPU **4.531초**였다. 미리 준비한 API는 기동부터 본문까지 **5.118초**, 준비 후 사용자의 첫 요청부터는 **0.104초**였다. DB 통합의 개별 실험 이점은 공통 조건에서 재현되지 않았다. DB 추가 시험 중 중단된 성공 표본 7건과 import 계측의 빈 파일은 최종 집계에서 제외했다.

## 4. KiCad 포함 API, 별도 렌더러, 렌더러 경량화

| 조건 | 실제 측정 | 해석 |
|---|---|---|
| 초기 로컬 이미지 쌍, KiCad 포함 → 제외 | `docker image inspect .Size` **594,028,265 → 340,472,560 B**(42.7% 감소). 준비된 이미지로 `docker run -d` → health **1.615 → 1.832초**, 각 3회 | 같은 API 명령을 사용. 이미지 크기 감소와 컨테이너 기동 시간을 따로 확인 |
| 이후 작업 트리 이미지 쌍, 포함 → 제외 | **609,537,543 → 355,990,413 B**(41.6% 감소). 주요 단계가 모두 캐시 적중인 빌드 1회씩 **3.266 → 6.357초** | 로컬 API에서 별도 렌더러를 호출해 실제 KiCad 원본의 PNG 1장 157,624 B 수신 |
| 준비된 이미지로 Compose 실행 | 새 DB 기본 기동 → API health 12.557초(1회). 기존 DB 볼륨 재기동 기본 / 렌더러 포함 **10.40 / 10.45초**, 각 3회. 렌더러 자체 health 6.87초 | `--profile schematic`으로 렌더러를 함께 실행한 시험 구성 |
| 같은 원본을 쓰는 분리 재실험 | 질문 목록 포함 / 분리 API **4.903 / 5.004초**. 첫 PNG까지 포함 API **6.740**, 렌더러 준비됨 **6.814**, API와 렌더러 순차 기동 **9.024초** | 각 5/5. 다른 OSC 이미지로 잰 사전 변환 PNG **4.879초**, 미리 준비한 API의 첫 실시간 변환 **1.193초**(준비 포함 **5.961초**). 70,669 B의 동일 PNG |
| 전용 렌더러 경량화 | 기존 / 경량 이미지 **609,537,543 / 351,884,332 B**(42.3% 감소). 빈 로컬 데몬에서 `docker load` → 첫 health: 1회 **50.122 → 20.730**, 2회 **40.347 → 15.778초** | 이미지 적재만 48.415 → 19.502, 37.613 → 14.405초. 적재된 이미지의 컨테이너 시작만 각 3회 중앙값 **1.280 → 1.176초** |

경량화에서는 렌더러 전용 빌드 단계에 변환용 의존성과 코드만 담았다. 같은 ECG 회로도에서 두 렌더러 모두 PNG 한 장 **218,732 B**, SHA-256 `4411a59fe71b94403d44a295f65a4d2b6620391350c3d647c85b4086b608e2e5`를 반환했다. `docker load` 시험의 시작점은 로컬 tar 적재이고, 원격 레지스트리 전송 시간은 미측정이다. [회로도 원본 고정 커밋](https://github.com/EldarTarighat/ECG-Sensor-PCB/tree/dfdd4525cd0b18d7ec1712483e8f4cf5acfc1367) · [KiCad 변환 코드](../../backend/projects/schematic.py) · [Cloud Run 컨테이너 계약](https://docs.cloud.google.com/run/docs/container-contract)

### 빈 Docker 환경에서 KiCad 포함·분리 비교 (2026-11-14)

`main` 커밋 `9186719`의 프로필 지연 로딩을 두 구성에 그대로 두고 **포함 → 분리** 순서로 세 쌍을 실행했다. 매회 Docker Engine 27.5.1과 Compose 2.33.0에서 이미지·컨테이너·볼륨·빌드 캐시가 비었는지 확인했다. 두 시간 모두 `docker compose up` 명령 시작부터 쟀다. 이미지 다운로드, 빌드, DB 초기화가 포함된다. 분리 구성은 같은 명령으로 렌더러도 빌드하고, 렌더러의 상태 확인이 끝나면 API를 시작한다.

| 측정 항목 | KiCad 포함 1 / 2 / 3회 | KiCad 분리 1 / 2 / 3회 | 포함 중앙값 | 분리 중앙값 |
|---|---:|---:|---:|---:|
| API 이미지 크기(B) | 1,793,629,138 / 1,793,629,178 / 1,793,629,178 | 1,044,507,431 / 1,044,507,486 / 1,044,507,446 | 1,793,629,178 | 1,044,507,446 |
| 첫 `/health` HTTP 200(초) | 103.501 / 109.367 / 110.468 | 121.217 / 110.580 / 109.953 | 109.367 | 110.580 |
| 첫 PNG 수신 완료(초) | 104.787 / 110.527 / 111.517 | 122.708 / 111.978 / 111.148 | 110.527 | 111.978 |

이미지 크기는 실행된 API 이미지의 `docker image inspect .Size` 값이다. 분리하면 API 이미지에서 749,121,732 B(41.77%)가 줄고, KiCad 변환에는 별도 렌더러 이미지가 필요하다. 회로도는 검색 후보와 원본 다운로드를 같은 로컬 `divider.kicad_sch`로 고정했다. 데모 로그인 후 회로도 목록에서 받은 서명 URL로 첫 PNG를 끝까지 읽었다. KiCad 9.0.2가 변환한 PNG는 6회 모두 3508 × 2481 px, 70,865 B로 바이트가 일치했다.

**KiCad 포함·프로필 지연 로딩을 유지한다.** G2에서 줄이려는 시간은 빈 환경에서 한 줄로 서비스를 띄워 첫 회로도를 받기까지의 대기 시간이다. 분리 구성이 세 번째 쌍에서 첫 PNG를 0.37초 먼저 반환했지만, 세 쌍의 중앙값은 포함 구성이 첫 `/health`에서 1.21초, 첫 PNG에서 1.45초 빨랐다.

## 5. Cloud Run 시험판과 운영 기록

| 측정 환경 | 실측 결과 |
|---|---|
| 과거 main `b5f050d`, 0% 태그, 서울, 1 CPU·1 GiB | KiCad 포함 / 제외 압축 레이어 합계 **598,433,711 / 344,857,968 B**. 첫 health 3회 **11.692 / 10.363**, **11.756 / 11.086**, **11.949 / 12.332초**(중앙값 11.756 / 11.086). Monitoring 컨테이너 시작 중앙값 11.145 / 10.556초. 순차 Cloud Build 122.13 / 49.46초에는 후행 캐시 영향 가능 |
| OSC 0% 태그와 비공개 렌더러 | 이미 기동한 API health 0.120~0.189초. 비공개 렌더러 인증 요청 PNG **157,624 B**, 첫 요청 6.203초, 다음 요청 3.893초(각 1회). 차이에는 다운로드·변환도 포함. Google 로그인 후 0% 태그 브라우저에서 전체 회로도 경로는 미검증 |
| 운영 API, 최소 인스턴스 0대 → 1대 | 같은 리비전에서 유휴 후 첫 인증 프로젝트 목록 서버 응답 **14.498 → 0.324초**. 전후 모두 HTTP 200, 각 1회. 직전 공백 약 22분 35초 / 15분 21초. 설정 적용 후 브라우저 목록 **0.675초** |
| 운영 회로도 `ATtiny85 development board` | 서버 검색 **5.238 → 4.910초**, 첫 PNG 요청 **0.211 → 0.246초**. 최소 1대 브라우저에서는 검색 **4.933초** + 결과 수신 후 PNG 수신 **0.277초** = **5.210초**, PNG 48,092 B. 기존 공개 PNG를 사용했고 적용 전 브라우저 전체 시간은 미수집 |

운영 API는 시험 당시 KiCad를 포함했다. 최소 1대는 유휴 시간도 과금 대상이어서 11월 13일 22:56 KST에 0대로 복원했다. 해당 시험만의 실제 청구액은 이 성능 기록에서 확정할 수 없다. 프로필 지연 로딩은 OSC에 반영했고 기록 종료 시점에는 운영 배포 전이었다. [최소 1대 설정 커밋](https://github.com/aihuman-7th/proj3-b/commit/a3aa92b9797492b627d6630f5b34c493618cad0b) · [최소 0대 복원](https://github.com/aihuman-7th/proj3-b/commit/38506fb2b739da0938283694880c5245636b1fdf) · [Cloud Run 성능 문서](https://docs.cloud.google.com/run/docs/tips/general) · [최소 인스턴스와 비용](https://docs.cloud.google.com/run/docs/configuring/min-instances)

배포 코드로 검색을 로컬에서 재현한 3회 중앙값도 기록했다. Linux 1 CPU에서 manifest 916.3 ms, 검색 제공자 199.9 ms, 선택한 저장소 확인 167.1 ms, PNG 준비 521.3 ms였다. PNG 준비 중 검증 프로세스는 468.6 ms로 그 안에 포함된다. Windows에서 manifest 중앙값은 1,637.2 ms였다. 운영에서 관측한 검색 4.933초의 하위 시간은 운영 로그에 남지 않았다.

## 6. 검토했으나 전후 실측하지 않은 방법

- **Ragas 분리**는 서비스에도 `ragas==0.4.3`을 설치한다는 프로젝트 요구에 따라 철회했다. 기존 다운로드 로그의 `pyarrow` 52.5 MiB, `scipy` 33.7 MiB, `pandas` 11.5 MiB는 관찰값이고, 제거 후 속도는 측정하지 않았다. [프로젝트 의존성](../../pyproject.toml) · [uv 의존성 그룹](https://docs.astral.sh/uv/concepts/projects/dependencies/#dependency-groups)
- **Python 바이트코드 사전 컴파일 해제**는 후보로만 검토했다. 기존 설정에서 13,175개 파일 컴파일에 **3.13 / 3.45 / 3.71초**가 걸렸다. 해제 후 빌드와 첫 응답의 전후 기록은 없다. [기준 Dockerfile](../../Dockerfile) · [uv 바이트코드 컴파일](https://docs.astral.sh/uv/guides/integration/docker/#compiling-bytecode)
- **정적 이미지만 제공**, **미리 빌드한 이미지 배포**, **세 Compose 서비스가 명시적으로 하나의 이미지 태그를 공유**하는 방안은 이 G2 비교에서 측정하지 않았다. 정적 이미지만 제공하면 KiCad 원본의 즉시 변환 범위가 줄어든다. 기존 BuildKit 로그에는 서비스 간 레이어 재사용이 있어 서비스 수를 설치 소요 시간에 곱할 수 없다. [Compose 구성](../../docker-compose.yml)

초기 분리 조사에서는 같은 Cloud Run 인스턴스의 sidecar, 요청 시 KiCad 설치, Cloud Run Job을 통한 비동기 변환, 전체 도면의 정적 저장도 검토했다. 네 방식의 독립적인 전후 시간은 없다. 고정 원본을 선별해 사전 변환한 직접 실험은 CS-4에 기록했다.

## 7. 측정 자료 찾기

회차별 주요 수치는 이 문서 안에 수록했다. 원래 CSV·로그·PNG·측정 스크립트는 실험 PC의 `바탕화면/3차 프로젝트/` 아래에 있다. 아래 경로는 그 폴더를 기준으로 한다. Docker·Google·Python·uv 링크는 방법의 출처이고, 다음 파일들은 SojaFit에서 나온 측정값의 출처다.

| 기록 | 보관 위치 |
|---|---|
| G2 단회·지연 로딩 교대 | `osc-local-experiments/results/oscg2-before-20261113-234257/timing.json`, `oscg2-20261113-233623/timing.json`(같은 상위 폴더), `osc-local-experiments/results/g2-six-20261114-000033/stages.csv` |
| G2 병렬 설치·PNG 원본 | `osc-local-experiments/results/g2-kicad-uv-20261114-002147/`의 `stages.csv`, `summary.csv`, `Dockerfile.patch`, 각 회차의 `sheet-01.png`와 `compose-timed.jsonl` |
| 개발 실험 네 가지 | `osc-local-experiments/results/`의 `OSC-1/pair.csv`, `OSC-2/samples.csv`, `OSC-3/run-20261113-171507-buildkit/build-results.csv`, `OSC-4/samples.csv`, `cold-start/samples.csv`, `profile-cold-20261113-233119/samples.csv` |
| 첫 기능·첫 회로도 여덟 가지 | `osc-coldstart-experiments/results/run-20261113-csA/`의 `통합-실측표.md`, `OSC-CS-1`~`OSC-CS-8` 개별 `report.md`, `split-comparison/crossover-214221.csv`, `split-comparison/first-213613.csv` |
| KiCad 이미지·렌더러 | `KiCad-Docker-기동시간-실측-및-방식-비교-2026-11-13.md`, `KiCad-렌더러-경량화-로컬-콜드스타트-실측-2026-11-13.md` |
| 운영 첫 요청·검색 단계 | `osc-coldstart-experiments/results/운영-min1-20261113/`의 `cloud-run.csv`, `browser.csv`, `검색-단계별-로컬-재현.csv`, `운영-첫응답-비교.md`. 검색 하위 단계별 CSV는 배포 코드의 로컬 재현 기록이다. |
| G2 새 clone 기동 재측정(11-17, `799ae636`, dind 29.9.3, clone 시작 기준, 6회, 원시 로그 저장소 안) | [evals/results/d12/](../../evals/results/d12/README.md). 1절 표(Engine 27.5.1, up 기준)와 다른 계열 |

## 부록. 개별 회차의 경과 시간

아래 값은 회차 순서대로 소수점 셋째 자리에서 표시한 초 단위 기록이다. 조건명은 원자료의 열 값이다. 실패한 기동에는 시간을 부여하지 않았다.

| 실험 | 조건·종점 | 회차별 시간(초) |
|---|---|---|
| OSC-1 | base / fresh | 10.351 / 11.265 / 10.488 |
| OSC-1 | base / warm | 11.580 / 10.215 / 9.761 |
| OSC-1 | candidate / fresh | 8.469 / 8.644 / 9.072 |
| OSC-1 | candidate / warm | 8.946 / 8.248 / 7.870 |
| OSC-2 | full-compose-recreate | 12.230 / 12.713 / 12.492 / 12.639 / 18.131 |
| OSC-2 | api-restart-db-kept | 5.648 / 4.782 / 4.981 / 5.202 / 5.080 |
| OSC-2 | api-force-recreate-no-deps | 5.439 / 5.644 / 5.668 / 5.371 / 5.805 |
| OSC-3 | baseline / normal | 4.576 / 2.591 / 3.444 |
| OSC-3 | candidate / normal | 6.396 / 4.320 / 2.879 |
| OSC-3 | baseline / dependency-layer-invalidated | 58.164 / 58.168 / 58.181 |
| OSC-3 | candidate / dependency-layer-invalidated | 49.314 / 56.160 / 51.252 |
| OSC-4 | baseline | 9.126 / 8.197 / 7.873 / 7.664 / 8.236 |
| OSC-4 | watch | 5.657 / 6.824 / 5.305 / 5.342 / 5.988 |
| 공통 빈 DB | OSC | 10.166 / 9.818 / 9.882 |
| 공통 빈 DB | OSC-1 | 실패 / 7.714 / 7.796 |
| 공통 빈 DB | OSC-2 | 10.017 / 10.426 / 10.087 |
| 공통 빈 DB | OSC-3 | 10.891 / 9.977 / 9.763 |
| 공통 빈 DB | OSC-4 | 9.907 / 10.136 / 9.826 |
| CS-1 | base / function | 6.843 / 4.864 / 4.580 / 4.986 / 4.597 |
| CS-1 | base / health | 4.918 / 4.890 / 4.497 / 4.649 / 4.408 |
| CS-1 | candidate / function | 4.736 / 4.586 / 4.624 / 4.480 / 4.859 |
| CS-1 | candidate / health | 4.760 / 4.751 / 4.688 / 4.733 / 4.965 |
| CS-2 | base / function | 16.970 / 9.769 / 12.380 / 12.021 / 10.064 |
| CS-2 | base / health | 9.913 / 19.691 / 9.511 / 8.992 / 9.894 |
| CS-2 | candidate / function | 11.003 / 11.209 / 9.416 / 10.580 / 11.190 |
| CS-2 | candidate / health | 10.300 / 9.924 / 14.016 / 12.399 / 14.718 |
| CS-3 | 1cpu / function | 4.975 / 5.501 / 4.865 / 4.772 / 5.366 |
| CS-3 | 1cpu / health | 5.008 / 5.321 / 4.713 / 6.187 / 4.976 |
| CS-3 | 2cpu / function | 4.797 / 4.705 / 4.349 / 4.449 / 4.664 |
| CS-3 | 2cpu / health | 5.065 / 4.949 / 4.481 / 4.233 / 4.355 |
| CS-4 | oscbench-base / known | 5.825 / 5.805 / 8.274 / 5.800 / 5.798 |
| CS-4 | oscbench-base / novel | 7.020 / 5.885 / 6.866 / 6.247 / 5.761 |
| CS-4 | oscbench-base / health | 4.520 / 5.806 / 5.408 / 4.605 / 5.038 |
| CS-4 | osc-csa-render / known | 4.711 / 4.834 / 6.026 / 5.065 / 4.850 |
| CS-4 | osc-csa-render / novel | 7.430 / 6.570 / 7.109 / 6.552 / 5.899 |
| CS-4 | osc-csa-render / health | 4.471 / 5.614 / 5.748 / 4.786 / 4.964 |
| CS-5 기동부터 | cold / function | 5.925 / 5.006 / 4.938 / 5.256 / 4.965 |
| CS-5 기동부터 | ready_unused / function | 6.286 / 4.959 / 5.106 / 6.194 / 5.171 |
| CS-5 요청부터 | cold / function | 0.097 / 0.142 / 0.117 / 0.139 / 0.113 |
| CS-5 요청부터 | ready_unused / function | 0.155 / 0.094 / 0.100 / 0.236 / 0.108 |
| CS-7 | cold / function | 5.233 / 4.980 / 5.800 / 5.254 / 5.420 |
| CS-7 | health_first / function | 5.419 / 5.468 / 4.904 / 4.895 / 5.601 |
| CS-7 도면 | cold / known | 6.412 / 6.449 / 7.279 / 5.981 / 6.093 |
| CS-7 도면 | health_first / known | 6.496 / 6.306 / 6.701 / 5.846 / 6.106 |
| CS-8 전체 완료 | serial | 5.588 / 5.249 / 5.223 / 5.067 / 5.036 |
| CS-8 전체 완료 | parallel | 5.339 / 5.365 / 5.392 / 5.598 / 4.932 |
| 교차 비교·사용자 대기 | base | 4.896 / 5.123 / 4.646 / 4.877 / 4.892 |
| 교차 비교·사용자 대기 | import | 4.740 / 4.883 / 4.782 / 5.169 / 4.769 |
| 교차 비교·사용자 대기 | cpu2 | 4.242 / 4.473 / 4.592 / 4.531 / 4.696 |
| 교차 비교·사용자 대기 | db | 4.873 / 4.881 / 5.095 / 4.938 / 5.052 |
| 교차 비교·사용자 대기 | ready_unused | 0.118 / 0.098 / 0.104 / 0.094 / 0.119 |
| KiCad 비교·사용자 대기 | mono / png | 8.874 / 6.650 / 6.893 / 6.740 / 6.268 |
| KiCad 비교·사용자 대기 | split_ready / png | 9.176 / 6.535 / 7.119 / 6.518 / 6.814 |
| KiCad 비교·사용자 대기 | split_cold / png | 9.510 / 9.024 / 8.983 / 8.575 / 9.045 |
| KiCad 비교·사용자 대기 | osc_cached / png | 5.272 / 4.819 / 4.879 / 4.831 / 4.960 |
| KiCad 비교·사용자 대기 | osc_ready / png | 1.440 / 1.205 / 1.108 / 1.096 / 1.193 |
| KiCad 비교·사용자 대기 | mono / function | 5.058 / 5.071 / 4.887 / 4.903 / 4.855 |
| KiCad 비교·사용자 대기 | split_ready / function | 5.004 / 5.038 / 4.970 / 4.714 / 5.020 |
| 첫 프로필 변경 | oscbench-base | 4.414 / 4.397 / 4.416 / 4.383 / 4.657 |
| 첫 프로필 변경 | osc-csa-import | 4.432 / 4.716 / 4.868 / 4.387 / 4.406 |
| 첫 대화 SSE | oscbench-base | 5.169 / 4.884 / 5.120 / 5.145 / 5.100 |
| 첫 대화 SSE | osc-csa-db | 5.301 / 5.406 / 5.414 / 5.404 / 5.351 |
