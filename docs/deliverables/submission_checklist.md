# 제출 체크리스트

- 상태: 초안
- 기준일: 2026-11-13
- 기준 커밋: 미기록(작업 트리에 미커밋 변경이 있는 상태에서 작성)
- 정본 여부: 비정본(제출물 점검표). 게이트 상태의 정본은 [GATES.md](../GATES.md), 제출 문서별 남은 일의 정본은 [DELIVERABLES.md](DELIVERABLES.md)
- 관련 문서: [GATES.md](../GATES.md), [DELIVERABLES.md](DELIVERABLES.md), [README.md](../../README.md)

과제 가이드 원문 사본은 저장소에 없다(`guide_v5`, "과제 가이드"를 grep해도 가이드 파일은 나오지 않는다). 항목은 `GATES.md`와 `DELIVERABLES.md`가 인용한 요구(게이트 G1~G7, 제출물 G7, 일정 D11·D12)만 옮겼다. 가이드에만 있고 이 두 문서에 없는 요구는 이 표에 없다.

상태 기준: 충족 = 증거 파일이 있고 요구를 채운다. 부분 = 파일은 있으나 요구의 일부만 채운다. 없음 = 파일 없음. 상태는 2026-11-13에 경로 존재를 확인하고 `GATES.md`·`DELIVERABLES.md`의 서술과 맞춰 적었다. 이 표를 위해 서비스나 평가를 새로 실행하지 않았다.

| 항목 | 요구 | 증거 경로 | 상태 | 마감 |
|---|---|---|---|---|
| G1 배포 주소 | README 맨 위 표의 배포 주소. 평가용 계정으로 핵심 시나리오 | [README.md](../../README.md), [GATES.md](../GATES.md) G1, [deploy_574de79](../../evals/results/d10/deploy_574de79/README.md) | 충족: 배포 `574de79`(100% 리비전 `sojafit-api-574de79-rs`)에서 평가용 계정 A · B 25단계 통과. `main` `c24c007`은 아직 배포하지 않았다 | 발표 11/18 |
| 배포 유지 | 발표일까지 배포 유지, 제출 링크·경로·발표 시각 | 없음 | 없음: 확인 기록 없음 | 발표 11/18 |
| G2 한 줄 기동 | `docker compose up`으로 10분 안에 기동 | [docker-compose.yml](../../docker-compose.yml), [.env.example](../../.env.example), [startup_restart_isolation_2026-11-13.md](../../evals/results/d10/startup_restart_isolation_2026-11-13.md) | 충족: 냉 기동 243.9초, 스모크 28/28(Mac dind 1회) | D11 11/16 |
| G3 코퍼스 | 서로 다른 청크 1만 개 이상, 문서 50건 이상, 파싱 1종 이상 | [data/manifest.jsonl](../../data/manifest.jsonl), [chunk_sha256.md](../../evals/results/chunking/v4h-2026-11-08/chunk_sha256.md), [GATES.md](../GATES.md) G3 | 부분: 문서 1,360 · 청크 51,967로 수치는 넘지만 GATES 표가 "증거 보강 필요"로 둠(DB에서 본문 해시 재계산 안 함) | D11 11/16 |
| G4 에이전트 | 코드와 시연. 평가용 계정 2개로 대화·기억 분리 | [GATES.md](../GATES.md) G4, [deploy_574de79](../../evals/results/d10/deploy_574de79/README.md), [startup_restart_isolation_2026-11-13.md](../../evals/results/d10/startup_restart_isolation_2026-11-13.md), [mutation_2026-11-13.md](../../evals/results/d10/mutation_2026-11-13.md) | 충족: 배포 서버에서 재시작 뒤 재개 · 409 · 계정 B 404 확인(`574de79`, 25단계). 로컬 compose 52개 점검도 있음. 시연 영상은 G7 | D11 11/16 |
| G5 평가 | 동결 평가셋 50건 이상(관련·비관련 절반), 개선 전후 2회 이상, 문항 목록 | [evals/FROZEN.json](../../evals/FROZEN.json), [EVAL_REPORT.md](../../EVAL_REPORT.md) 2·3절, `evals/results/graph/2026-11-12-d9-improve2/set1.json` | 충족: v3 50건 동결, 50/50. GATES 표의 상태 칸은 "진행 중"이라 갱신 필요 | D11 11/16 |
| 평가 비교 | 대체재(Codex)와 비교 | [EVAL_REPORT.md](../../EVAL_REPORT.md) 10절, [TALLY.md](../../evals/results/graph/2026-11-12-codex-v3-50/TALLY.md) | 충족: Codex 45/50, 우리 50/50. 규칙 확정 43건 + 사람 판정 5건 완료(2026-11-13, [human_judgments.jsonl](../../evals/results/graph/2026-11-12-codex-v3-50/human_judgments.jsonl)). 한계: 정답 초안과 같은 도구, 규칙 집계는 쪽 인용을 보지 않음 | D12 11/17 |
| G6 트레이스 | Langfuse 트레이스와 평가 점수 연결, 대시보드 | [EVAL_REPORT.md](../../EVAL_REPORT.md) 7장, [langfuse_403_2026-11-13.md](../../evals/results/d10/langfuse_403_2026-11-13.md) | 부분: 스크린샷 3장 · 배포본 트레이스 수신 · 403 원인 확인. 평가 점수가 트레이스에 붙어 보이는 화면은 없음(GATES G6 "증거 보강 필요") | D11 11/16 |
| Langfuse 스크린샷 | 3장 이상, 트레이스 상세 1장 이상 | [langfuse/](langfuse/) `01-trace-list.jpg` `02-model-call-detail.jpg` `03-cost-dashboard.jpg` | 충족: 3장(트레이스 상세 포함), 11-13 배포본 기준 | D11 11/16 |
| G7 비밀값 | 비밀값 커밋 없음 | [secret_scan_2026-11-13.md](../../evals/results/d10/secret_scan_2026-11-13.md), [.env.example](../../.env.example) | 충족: gitleaks 이력 801 커밋 발견 0건(로컬 실행. GitHub Actions 결과는 확인 못 함) | D11 11/16 |
| 시연 영상 | 3분 이내, 정상·실패 경로, 원본, 동결 커밋 SHA, 배포 리비전 번호 | [demo_script.md](demo_script.md) | 부분: 스크립트만 있고 영상 파일 없음 | D11 11/16 |
| 실패 사례 분석 | 코드로 되돌린 결정 1건과 이유, 미채택 실험, 판정자 한계 | [failure_analysis.md](failure_analysis.md) | 부분: 11-13에 3항목, 11-16에 9절(인젝션 사례 1건 · Luna 한계)을 채움. 남은 일은 정답 초안 작성자 서술 불일치([DELIVERABLES.md](DELIVERABLES.md)) | D12 11/17 |
| AI 도구 사용 기록 | 팀의 AI 코딩 도구 사용 기록 | [ai_tools_log.md](ai_tools_log.md) | 부분: 하정운 기록만. 다른 조원 기록 없음 | D12 11/17 |
| 포트폴리오 | 조원 수(3명)만큼 | [portfolio-jeongun.md](portfolio-jeongun.md) | 부분: 1/3(`portfolio-osc.md`, `portfolio-sth.md` 없음) | D12 11/17 |
| 발표 자료 | 전원 파트 분담 | 없음 | 없음 | D12 11/17 |
| 제출 체크리스트 | 최종 제출 때 확인 | 이 파일 | 부분: 초안 | D12 11/17 |
| 동결 직전 배포 점검: 고정 비밀 버전 | 서비스 설정이 고정한 Secret Manager 버전(`이름:숫자`)이 모두 enabled인지 확인하거나 `:latest`로 바꾼다. 최소 인스턴스 0대라 버전이 파기되면 새 인스턴스가 모두 시작하지 못한다(11-14 22:43 ~ 11-15 21:26 KST, `EXA_API_KEY` 버전 1 파기) | [GATES.md](../GATES.md) G1, `docs/worklog/jeongun.md` 11-15 항목 | 없음: 동결 전 점검 기록 없음. 11-15 복구 때 다른 비밀값의 고정 버전은 모두 enabled였다 | D11 11/16 |
| 개인정보·비밀값 점검 | 포트폴리오·스크린샷에 개인정보나 비밀값 없음 | [DELIVERABLES.md](DELIVERABLES.md) 남은 일 표의 점검 기록 | 부분: 2026-11-13 1차 점검 기록 있음. 포트폴리오 최종본 기준 재점검 필요 | D12 11/17 |
