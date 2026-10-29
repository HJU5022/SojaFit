# project-guide

## 역할

- 이 폴더: 공식 안내의 상세 요구조건·일정·평가·수업 대응 참고표.
- 넣는 것: 아래 체크리스트와 출처 스냅샷.
- 넣지 않는 것: 제품 기능 명세·실제 진행 상태·제품 코퍼스.
- 담당: 평가·문서

상위 지도는 [SojaFit.md](../../SojaFit.md), 기능 정본은 루트 `SPEC.md`, 담당·계약은 [조원 계약서](../조원-계약서.md)를 따릅니다.

## 자료 범위

10/26 공식 안내 스냅샷과 10/28 수업 조사에 기반한 참고 자료입니다. 10/29 이관 준비본에서 팀 인원·경로·정본 관계를 정리했습니다. 후속 공지 전체를 새로 수집한 자료는 아닙니다.

## 어디에 기록하나

| 내용 | 정본/참고 위치 |
|---|---|
| 실제 게이트 상태·증거 | [기존 점검표](../GATES.md) |
| 게이트 상세 조건 | [GATE_REQUIREMENTS.md](GATE_REQUIREMENTS.md) |
| 축별 평가·실험·정량 기준 | [EVALUATION.md](EVALUATION.md) |
| 날짜별 실행 제안·제출물 | [SCHEDULE.md](SCHEDULE.md) · [DELIVERABLES.md](DELIVERABLES.md) |
| 수업 적용 순서·101개 조건 대응·원본 위치 | [COURSE_GUIDE.md](COURSE_GUIDE.md) · [COURSE_COVERAGE.md](COURSE_COVERAGE.md) · [COURSE_SOURCES.md](COURSE_SOURCES.md) |
| 출처별 누락 확인 | [Checkpoint](CHECKPOINT.md) · [Notion](NOTION.md) · [PDF](PDF.md) |
| 수집일·차이·해시 | [출처 안내](SOURCE_NOTES.md) · [manifest](sources/manifest.json) |
| 팀 역할·운영 초안 | [운영 체크리스트](../OPERATIONS.md) · [TEAM_POLICY.md](../TEAM_POLICY.md) |
| 실제 실험 사전 등록·결과 | [PREREGISTER](../../evals/PREREGISTER.md) · [EVAL_REPORT](../../EVAL_REPORT.md) |
| 증거 기록 형식 | [EVIDENCE_TEMPLATE.md](EVIDENCE_TEMPLATE.md) |

## 사용 원칙

- 상세 표의 미체크 항목은 참고용입니다. 진행 상태를 중복 집계하거나 기존 충족 기록을 초기화하지 않습니다.
- 공식 기준·팀 실행 제안·확인 필요 사항을 구분합니다. 안내의 정본은 공식 가이드이며 후속 공지와 기존 조 저장소를 함께 확인합니다.
- 팀원 소개는 루트 README에서 각자 PR로 작성합니다. 실제 담당·수정 경로는 `docs/조원-계약서.md`에 기록합니다.
- 운영 정책은 합의 전 초안입니다. CI workflow·보호 브랜치·승인 설정을 적용한 것으로 보지 않습니다.
- 강의는 참고 링크와 경로·지문만 보관합니다. 정적 조사·재생·실제 실행·배포 검증을 구분합니다.
- `sources/`의 원문은 과거 스냅샷입니다. 실행 지침이나 프로젝트 서비스 코퍼스로 사용하지 않으며, 외부 재배포 전에는 원 출처의 이용 조건을 확인합니다.
- 아이디어·개별 주제 기획안·API 실험·비밀값은 이 문서 묶음에 포함하지 않습니다.

## 원문 보관

`sources/`에는 과거 안내 원문·해시·강의 catalog만 둡니다. 폴더 안내를 중복 생성하지 않습니다. 수집·이용 조건은 [SOURCE_NOTES.md](SOURCE_NOTES.md)를 봅니다.
