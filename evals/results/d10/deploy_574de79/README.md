# 배포 574de79 점검: 재시작 뒤 재개(G4) · 평가용 계정 로그인(G1·G2)

결과: **둘 다 통과.** 배포 서버와 실제 모델로 평가용 계정 A · B 로그인, 넷리스트 업로드, 판정 질문, 조건 질문에서 멈춤, **서버 재시작**, 같은 run 재개, 승인, 같은 승인 다시(409), 견적, 계정 B의 접근 404까지 25단계가 모두 통과했다.

- 대상: Cloud Run `sojafit-api`(project `sojafit`, asia-northeast3), 공개 주소. 코드 `main` `574de79`, 이미지 `…/sojafit-api@sha256:87101e5c…1cab7`
- 원시 결과: [scripts/results/smoke/smoke_sojafit-api-…_2026-11-13_120624.json](../../../../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-13_120624.json)(비밀번호 · 이메일 · 답 글 없음). 같은 폴더의 `…_115305.json`은 업로드 옵션 전 첫 시도(3단계 데모 회로 404), 로그인 없는 점검: [unauth_checks_raw.txt](unauth_checks_raw.txt)
- 명령: `uv run python scripts/smoke/http_smoke.py --base-url https://sojafit-api-559369539072.asia-northeast3.run.app --confirm-live --pause-before-resume --upload`(계정은 `SMOKE_*` 환경변수, 하정운 터미널에서 실행). `--upload`는 `DEMO_MODE=0` 배포본에서 데모 회로 목록이 404라 실제 사용자와 같은 업로드 경로로 프로젝트를 만든다. `--pause-before-resume`은 4단계 뒤 Enter까지 멈춘다.

## 재시작 절차 (2026-11-13 KST)

| 시각 | 일 |
|---|---|
| 12:06:24 | 스모크 시작. 4단계 run `1d9ef35f…`가 `requires_input`에서 멈춤(18.8초, 리비전 `sojafit-api-574de79`) |
| 12:06:52~12:07:08 | 같은 이미지 다이제스트로 새 리비전 `sojafit-api-574de79-rs`를 `--no-traffic`으로 만든 뒤 100% 전환. 서비스는 `maxScale 1`이라 새 리비전은 새 프로세스다 |
| 12:07 | 공개 `/health` 200, 냉 기동 7.8초(새 인스턴스가 뜬 것) |
| 12:08:35 | Enter. 5단계 재개 |
| 12:08:38 | `POST /api/runs/1d9ef35f…/resume` 200을 **`sojafit-api-574de79-rs`**가 처리(Cloud Logging 요청 로그) |

명령: `gcloud run deploy sojafit-api --image <위 다이제스트> --revision-suffix 574de79-rs --no-traffic --tag restart-574de79`, `gcloud run services update-traffic sojafit-api --to-revisions sojafit-api-574de79-rs=100`.

## 결과

| 확인 | 결과 |
|---|---|
| 재시작 뒤 같은 run 재개 | `run_started>status>completed`, 3.0초(처음 시작은 19초). 재시작 전 프로세스에 없던 상태를 DB 체크포인트에서 읽어 이어 감 |
| 같은 승인 다시 | 409 `ALREADY_APPROVED` |
| 계정 B가 A의 프로젝트 · thread 목록 · run · 견적 목록 읽기, 메시지 승인, 견적 저장 | 모두 404 `NOT_FOUND` |
| 평가용 계정 로그인 A · B | 200(0.96초, 0.85초) |
| 합계 | 통과 25 · 실패 0 · 건너뜀 0 |

## 한계

- 재개가 처음부터 다시 돌지 않았다는 근거는 이벤트 순서와 시간(3초 대 19초)이다. 체크포인트 행을 직접 대조하지는 않았다.
- 비용은 서버 로그에서 따로 집계하지 않았다(실제 모델 호출 2~5회 어림, `record_demo.py`의 calls).
- Google 로그인 왕복과 이메일 가입은 보지 않았다.
- 지금 100% 리비전은 `sojafit-api-574de79-rs`(코드 · 이미지 · 설정이 `574de79`와 같음)다.
