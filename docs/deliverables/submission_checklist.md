# 제출 체크리스트

- 상태: 현행
- 기준일: 2026-11-17
- 기준 커밋: 최종 동결 태그 `final-2026-11-17`(11-17 레포 정리 커밋 `a468c0ba`. 배포 소스 `main` `2030f846`(PR #160 병합)과 비교해 서비스 코드는 주석만 다르고, 측정 스크립트 2개(`scripts/smoke/http_smoke.py` `allow_duplicate`, `evals/runners/run_skill_pair.py` `--max-seconds`)가 바뀌었다). 그 뒤 발표 폴더(PR #162), 랜딩 그림 4장(`b4a02113`, PR #163), 제출물 검수에서 찾은 문서 · 주석 정리, 큰 파일 주석 보강, 쓰지 않는 prop · 중복 함수 2곳 삭제(동작 같음, 배포하지 않음)만 바꿨고 태그는 옮기지 않았다. 배포 리비전 `sojafit-api-pre-b4a02113-1117`(측정은 그 전 `sojafit-api-pre-ef0138b2-rs`)
- 정본 여부: 비정본(제출물 점검표). 게이트 상태의 정본은 [GATES.md](../GATES.md)
- 관련 문서: [GATES.md](../GATES.md), [DELIVERABLES.md](DELIVERABLES.md), [README.md](../../README.md)

최종 제출 11-17(화) 24:00, 발표 11-18(수).

## 1. 제출물

| 항목 | 요구 | 상태 | 증거 |
|---|---|---|---|
| 조 저장소 | main에 최종본 | 됨: 최종 동결 태그 `final-2026-11-17`(레포 정리 PR 병합 뒤 붙임. 그 전 태그 `freeze-2026-11-17`은 옮기지 않음) | GitHub `aihuman-7th/proj3-b` |
| README | 한 줄 정의 · 지표 표 · compose 실행 · 데모 모드 실행 | 됨 | [README.md](../../README.md) |
| SPEC.md · AGENTS.md | 지금 코드와 맞음 | 됨(11-17 맞춤) | [SPEC.md](../../SPEC.md), [AGENTS.md](../../AGENTS.md) |
| 배포 주소 | `/health` 200, 발표일까지 유지 | 됨: 리비전 `sojafit-api-pre-b4a02113-1117` 100%(11-17 20:45부터, 그 전 19:52 ~ `sojafit-api-pre-ef0138b2-rs`) | README 「배포 리비전」 |
| 평가용 계정 2개 | 비공개 제출 | **하정운이 제출 양식에 넣는다** | - |
| 운영 리비전 25단계 | 평가용 계정으로 핵심 시나리오 | 됨: 11-17 운영 리비전 `sojafit-api-pre-ef0138b2-rs` 25단계 점검(재시작 단계 제외 24개) 24/24(19:56), 재시작 뒤 재개는 19:50 실행에서 통과 | [GATES.md](../GATES.md) G1 · G4, `scripts/results/smoke/` 11-17 `195049` · `195638` |
| manifest | 원문 길이 · 보존 길이 · 잘림 여부 | 됨: 1,360행 | `evals/results/chunking/v4h-2026-11-08/manifest.jsonl` |
| 평가셋 · 동결 해시 · 원시 결과 | `freeze.py --check` 통과 | 됨(11-17 바뀐 파일 없음) | `evals/results/d12/checks/freeze_check.txt` |
| EVAL_REPORT | 전후 · 지표 · 단일 대 멀티 · 대체재 · 실패 유형 · 신뢰 경계 | 됨 | [EVAL_REPORT.md](../../EVAL_REPORT.md) |
| Langfuse 스크린샷 | 3장 이상, 트레이스 상세 1장 | 됨: 7장 | [langfuse/](langfuse/) |
| 시연 영상 | 3분 이내, 정상 1 + 실패 1, 화면마다 한 문장 | 됨: 1분 35초, 정상 1 + 실패 3 | [video/](video/) |
| 비밀값 | 커밋 이력에 비밀값 없음 | 됨: gitleaks 1,250 커밋 0건(11-17) | `evals/results/d12/checks/` |

## 2. D12 항목

| 항목 | 상태 | 증거 |
|---|---|---|
| 실패 사례 분석(되돌린 결정 1건과 이유, 미채택 실험, 막지 못한 것, 판정자 한계) | 됨 | [failure_analysis.md](failure_analysis.md) 6 · 7 · 8 · 9절 |
| 포트폴리오 1장 × 3명(LangGraph · 멀티 에이전트 · 평가 · 관측 수치, EVAL_REPORT 값만) | 됨: 3장 있음 | [portfolio-jeongun.md](portfolio-jeongun.md) · [portfolio-osc.md](portfolio-osc.md) · [portfolio-sth.md](portfolio-sth.md) |
| AI 코딩 도구 사용 기록 | 됨: 3명 행 있음(오세창 행은 도구 이름이 작업 기록에 없음) | [ai_tools_log.md](ai_tools_log.md) |
| 발표 자료(전원 파트) | 20장, 파트 배정, 장마다 노트에 "왜 이렇게 했나" | [presentation/](presentation/) |
| 리허설 2회 | **전원**. 11-17 1회 · 11-18 발표 전 1회 | - |
| 인젝션 막은 것 · 못 막은 것 | 됨 | [failure_analysis.md](failure_analysis.md) 9-0절 |
| 포트폴리오 · 스크린샷 개인정보 · 비밀값 | 됨(11-17 점검, 0건) | [GATES.md](../GATES.md) G7 「개인정보 · 비밀값 점검」 |
