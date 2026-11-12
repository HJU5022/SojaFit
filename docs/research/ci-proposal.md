# CI 사용량 절감 제안

- 상태: 계획
- 기준일: 2026-11-12 (workflow 대조일)
- 기준 커밋: 6707002
- 정본 여부: 비정본(제안). 합의 전이며 workflow를 변경하지 않는다. 브랜치, push, 리뷰, 병합, uv 규칙의 정본은 [AGENTS.md](../../AGENTS.md)
- 관련 문서: [.github/workflows/ci.yml](../../.github/workflows/ci.yml), [secret-scan.yml](../../.github/workflows/secret-scan.yml), [eval-live.yml](../../.github/workflows/eval-live.yml)

## 1. 질문과 결론

질문: PR마다 도는 검증의 Actions 사용량을 어떻게 줄이는가. 결정은 없다. 적용 여부와 시점은 합의 뒤에 정한다.

## 2. 현재 설정

| 항목 | 현재 | 근거 |
|---|---|---|
| 실행 이벤트 | `ci.yml`과 `secret-scan.yml` 모두 `pull_request`와 `main` push | `ci.yml:4-7`, `secret-scan.yml:11-14` |
| `ci.yml` job | `test`, `frontend`, `eval-replay`, `eval-injection-replay` 4개. 경로·변경 범위 필터 없음 | `ci.yml` |
| 오래된 검증 취소 | `concurrency` 설정 없음 | 세 workflow에 `concurrency` 문자열 없음 |
| 실행 시간 상한 | `timeout-minutes`는 `eval-live.yml`의 30분만 있다. `ci.yml` job에는 없다 | `eval-live.yml:16` |
| 설치 | Python job은 `uv sync --locked`. 캐시 옵션은 지정하지 않았다. `frontend` job만 npm 캐시 사용 | `ci.yml:37,93,61-62` |
| 실제 모델 평가 | `workflow_dispatch` 버튼 실행만(`eval-live.yml`). PR 검증은 키 없는 재생(`eval-replay`, `eval-injection-replay`) | `eval-live.yml:8-14`, `ci.yml` 주석 |

## 3. 제안

| # | 대상 | 내용 | SPEC·결정 링크 |
|---|---|---|---|
| 1 | 오래된 검증 취소 | PR별 그룹으로 이전 검증만 취소한다. 배포·DB 변경처럼 부수효과가 있는 실행은 분리한다 | 없음 |
| 2 | 실행 시간 | 각 job과 외부 호출에 유한 대기 시간을 둔다 | 없음 |
| 3 | 설치·캐시 | uv 캐시를 런타임, `pyproject.toml`, `uv.lock`에 맞춰 구성한다. 필요한 의존성만 설치한다 | 없음 |
| 4 | 변경 범위 | 순수 설명 문서는 저비용 검증, 제품·공통 계약·평가 변경은 관련 검증을 실행한다 | 5절 조건 |
| 5 | 무거운 검증 | 실제 모델·전체 평가·긴 E2E는 책임자, 시점, 증거를 정해 분리한다. 필요한 검증을 생략하는 뜻이 아니다 | 없음 |
| 6 | 보존·matrix | 검토에 필요한 결과(artifact)만 보존하고 환경 조합은 실제 지원 범위로 제한한다 | 없음 |

## 4. 선택 실행을 도입할 때의 조건

- `docs/**`나 확장자만으로 설명 문서를 판정하지 않는다. AGENTS, Spec, Skill, 평가 규칙처럼 동작에 영향을 주는 문서는 관련 검증 대상이다.
- 삭제·이름 변경의 이전 경로와 새 경로, 혼합 변경을 포함한다. 분류되지 않은 경로는 검증 범위를 넓히고, 변경 파일 목록을 얻지 못하면 실패로 처리한다.
- 모든 PR에 결과를 남기는 필수 집계를 둔다. 실행 대상의 실패, 취소, 결과 누락, 예상 밖 skip을 통과시키지 않는다. 순수 설명 문서에서도 비밀값 검사는 유지한다.
- 동결 해시와 가벼운 평가 회귀는 일반 검증에 남긴다. 실제 모델 평가를 재생·fixture 결과로 대체하지 않는다.
- 재실행은 일시 장애 원인을 확인한 뒤 제한적으로 한다. 절감 효과는 실행 job 수, 사용 시간, 캐시, artifact 사용량으로 확인한다.

## 5. 한계

- 실제 workflow 변경, 선택 분류, 집계 검증은 구현하지 않았다. 문서 작성, 로컬 정적 검사, Actions 실행 성공, 관리자 설정 완료는 서로 다른 단계이며, 러너가 뜨지 않은 것을 검사 통과로 보고하지 않는다.
- 절감량은 측정하지 않았다.
