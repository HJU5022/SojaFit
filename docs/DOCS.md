# docs

## 역할
- 이 폴더: 주제서, 조원 계약서, 게이트 증거, 조 결정 기록, 작업서, 제출물, 작업 기록, 평가 보충·조사·실측 기록을 둡니다.
- 넣는 것: 아래 파일과 하위 폴더.
- 넣지 않는 것: 기능의 정본(루트 `SPEC.md`), 평가 리포트(루트 `EVAL_REPORT.md`), 저장소 지도(루트 `SOJAFIT.md`).
- 담당: 평가·문서

## 파일
- `TOPIC.md` — 강사에게 낸 주제서를 옮겨 두는 곳
- `조원-계약서.md` — 조원 간 계약서(각자 수정하는 경로, 모듈 사이 함수, 코드가 읽는 파일과 환경변수, 오프라인 규칙)와 강사가 준 요청 흐름·설계 질문
- `GATES.md` — 필수 게이트 G1~G7을 어디서 채우는지와 증거, 테스트를 일부러 깨뜨려 본 기록 표(3건 이상 채울 곳)
- `adr/` — 조 결정 기록. [ADR.md](adr/ADR.md)
- `specs/` — SPEC에 없는 기능이 생길 때 쓰는 작업서. [SPECS.md](specs/SPECS.md)
- `deliverables/` — 제출물. [DELIVERABLES.md](deliverables/DELIVERABLES.md)
- `worklog/` — 조원별 작업 기록. [WORKLOG.md](worklog/WORKLOG.md)
- [EVALUATION.md](EVALUATION.md) — 기존 문서에 없는 평가 축·시장 근거·가산 준비 항목
- [CI_PROPOSAL.md](CI_PROPOSAL.md) — 현재 workflow에 대한 절감 보완 제안(미적용)
- [auth-login-verification.md](auth-login-verification.md) — 인증 세션·시간 경계·scrypt 로컬 실측 기록
- [auth-feedback-key-verification.md](auth-feedback-key-verification.md) — 로그인 피드백·AUTH_SECRET 실제 키 사용과 역할별 실측
- `auth_boundary_after_merge.py` / `.json` — 로그인 잠금·세션 만료 경계 실측 도구와 원시 결과
- `measure_scrypt_concurrent.py` / `scrypt_concurrent_final_measurement.json` — 동시 scrypt·프로세스 메모리 실측 도구와 원시 결과
- [model-licenses.md](model-licenses.md) — 임베딩 후보별 고정 revision, 라이선스·약관, 운영/연구 분류와 GitHub 포함 여부
- [embedding-candidate-investigation.md](embedding-candidate-investigation.md) — 임베딩 후보 13종을 넣은 이유, 개별 조사·실행 과정, 중단 사유와 다음 평가 조건
