# 개발 전용 전체 더미 흐름

- 상태: 폐기(2026-11-16 새 화면에 더미 모드가 없다). 옛 화면 기준의 이력으로만 남긴다
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 없음. `npm run dev:dummy`와 `frontend/e2e/`는 새 화면에서 없어졌고([frontend/FRONTEND.md](../../frontend/FRONTEND.md) "새 화면으로 교체"), 키 없는 흐름은 서버의 `DEMO_MODE` · `DEMO_REPLAY`가 맡는다([evaluator-demo-readiness.md](evaluator-demo-readiness.md)). 브라우저 시험은 [frontend/tests/TESTS.md](../../frontend/tests/TESTS.md)
- 관련 문서: [circuit-context-diagram.md](circuit-context-diagram.md)

## Why

- 페르소나: 실제 인증 DB·LLM·가격 API 없이 SojaFit 데모를 준비하는 팀원
- 상황: 프론트 화면은 실행할 수 있지만 더미 로그인 뒤의 프로젝트·분석·승인·견적 API는 실제 백엔드를 향한다.
- 문제: 외부 서비스나 공유 DB 상태에 따라 데모가 중단되고, 마지막 승인·견적 단계까지 한 화면에서 직접 확인하기 어렵다.
- 측정 지표: 외부 네트워크 요청 0건, 전체 사용자 흐름 E2E 1건 통과, production build에서 더미 모드 비활성

## Goal

- 해결 목표: 개발자가 명시적으로 더미 모드를 실행했을 때 로그인부터 승인 사례 삭제까지 브라우저에서 직접 조작한다.
- 성공 기준:
  - `npm run dev:dummy`에서 전체 흐름을 한 번에 완료한다.
  - 더미 모드의 `/api` 요청은 실제 백엔드·DB·외부 API로 전달되지 않는다.
  - 화면에 `더미 실행 모드 · 저장되지 않음`을 항상 표시한다.
  - 일반 개발 모드와 production build는 기존 실제 API 경계를 유지한다.
- 범위 밖: 실제 LLM·RAG·Mouser 호출, DB 영속 저장, 업로드 파일 변환, 운영 데모 모드 변경, production fixture fallback

## What

Happy Path

1. 사용자가 `npm run dev:dummy`로 프론트를 실행한다.
2. 더미 사용자 세션으로 작업대에 진입한다.
3. `breadboard_supply` 프로젝트에서 `D1 / 1N4001`과 주변 연결을 확인한다.
4. D1 대체 질문을 보내고 진행 상태 뒤 완료 결과를 받는다.
5. 역할·근거·후보 판정과 데이터시트 위치를 확인한다.
6. 후보를 선택해 판정을 승인한다.
7. 화면 메모리 전용 가격·재고를 조회한다.
8. 가격을 포함하지 않는 견적을 저장한다.
9. 승인 사례를 확인한 뒤 삭제한다.

Edge Case

| 상황 | 처리 방식 |
|---|---|
| 일반 `npm run dev` 실행 | 더미 응답을 사용하지 않고 기존 `/api` 호출 유지 |
| production build | 빌드 모드와 무관하게 더미 경계 비활성 |
| 새로고침 | 모든 더미 변경 상태를 초기값으로 되돌림 |
| 알려지지 않은 더미 API | 실제 서버로 넘기지 않고 표준 404 오류 응답 |
| 실행 취소 | 기존 AbortSignal 계약을 유지하고 화면 상태 갱신 중단 |
| 승인 전 견적 접근 | 기존 UI 계약에 따라 견적 저장 제어를 노출하지 않음 |

## How

- Vite mode가 `dummy`이고 `import.meta.env.DEV`일 때만 더미 전송 계층을 켠다.
- `apiFetch`와 SSE 요청이 같은 전송 함수로 들어가도록 공통 API 경계를 사용한다.
- 더미 전송 계층은 실제 API DTO와 동일한 `Response`를 반환한다.
- 상태는 모듈 메모리에만 두며 브라우저 저장소·쿠키·DB에 쓰지 않는다.
- 프로젝트, 역할 코드, thread, run, 승인, 견적, 승인 사례, 가격 조회 endpoint만 구현한다.
- SSE는 `run_started`, `status`, `completed` 프레임을 순서대로 반환한다.
- 더미 회로 데이터는 `breadboard_supply`, 대상 `D1 / 1N4001`, 주변 `J1`, `S1`, `F1`, `U1`을 사용한다.
- 후보 결과는 5종 판정 값 중 실제 API가 허용하는 값을 사용하고, 근거 위치를 함께 제공한다.
- 상단 표시와 실행 명령으로 실제 모드와 더미 모드를 명확히 구분한다.

## AC

AC-01 · 명시적 개발 모드 경계

- GIVEN: 일반 개발 모드 또는 production build
- WHEN: 프론트가 API 요청을 보낸다.
- THEN: 더미 전송 계층을 사용하지 않는다.

AC-02 · 더미 전체 흐름

- GIVEN: `npm run dev:dummy`로 실행한 작업대
- WHEN: 사용자가 프로젝트 선택부터 질문·판정·승인·가격 조회·견적 저장을 순서대로 수행한다.
- THEN: 외부 요청 없이 각 단계의 실제 UI 상태가 갱신되고 최종 견적 저장 문구가 보인다.

AC-03 · 회로와 분석 결과

- GIVEN: 더미 `breadboard_supply`의 D1
- WHEN: 분석을 완료한다.
- THEN: D1 주변 J1·S1·F1·U1, 역할명·근거, 후보 판정, 데이터시트 위치가 표시된다.
- THEN: 입력 최대 12 V와 최대 전류 1 A에 안전 여유를 적용한 기준, SS34L 후보 값, 통과 결과를 조건표로 표시하고 각 조건에서 데이터시트 근거를 연다.
- THEN: 견적 화면은 현재 더미 가격의 적용 구간과 `단가 × 수량` 예상 상품금액을 설명하되 가격을 저장하지 않는다.

AC-04 · 비영속 상태 고지

- GIVEN: 더미 모드 화면
- WHEN: 어느 페이지나 작업 단계에 있다.
- THEN: `더미 실행 모드 · 저장되지 않음` 표시가 보이고 새로고침 뒤 변경 상태가 초기화된다.

AC-05 · 승인 사례 삭제

- GIVEN: 더미 후보 승인으로 승인 사례가 생성됨
- WHEN: 사용자가 사례 삭제를 확인한다.
- THEN: 사례가 메모리 상태에서 제거되고 빈 상태가 표시된다.

AC-06 · 알려지지 않은 API 차단

- GIVEN: 더미 모드
- WHEN: 정의되지 않은 `/api` 경로를 호출한다.
- THEN: 실제 서버로 전달하지 않고 공통 형식의 404 오류를 반환한다.

## 구현 상태

| 항목 | 근거 | 상태 |
|---|---|---|
| 더미 모드 경계(`DEV`이고 mode `dummy`일 때만) | `frontend/src/api/client.ts:3-10` | 구현. AC-01 |
| 더미 응답·SSE 프레임(`run_started`, `status`, `completed`)·404 | `frontend/src/api/dummy.ts:64,162`, 시험 `frontend/src/api/dummy.test.ts` | 구현. AC-03, AC-06 |
| 비영속 고지 문구 | `frontend/src/App.tsx:22`, 시험 `frontend/src/App.test.tsx:129` | 구현. AC-04 |
| 전체 흐름(프로젝트 선택부터 사례 삭제) | `frontend/e2e/dummy-mode.spec.ts:45`, `frontend/e2e/full-flow.spec.ts:3` | 구현. AC-02, AC-05 |
| 더미 회로 데이터 | `data/circuits/catalog.json`을 Vite 플러그인이 읽는다(`frontend/vite.config.ts:13-40`) | 구현 |

## 한계

- E2E는 이 문서 기준일에 다시 실행하지 않았다(미확인).
- 더미 후보 SS34L의 조건값(입력 12 V에 여유 1.25 적용, 전류 1 A에 여유 1.43 적용)은 `frontend/src/api/dummy.ts`의 고정 응답이며 판정 규칙의 계산 결과가 아니다.
