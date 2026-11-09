# Development-only Dummy Full Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** `npm run dev:dummy`로 로그인부터 분석·승인·가격 조회·가격 없는 견적·승인 사례 삭제까지 실제 화면에서 직접 조작하는 비영속 더미 흐름을 제공한다.

**Architecture:** 모든 JSON·SSE 요청을 공통 `apiRequest()` 경계로 통과시키고, `DEV && MODE === 'dummy'`일 때만 메모리 기반 `dummyApiFetch()`로 전달한다. 컴포넌트는 실제 API DTO를 그대로 사용하며, 더미 상태는 브라우저 저장소나 서버에 쓰지 않는다.

**Tech Stack:** React 19, TypeScript 7, Vite 8 mode, Vitest, Playwright

## Global Constraints

- 일반 `npm run dev`와 production build는 기존 실제 `/api` 호출을 유지한다.
- 더미 모드의 정의되지 않은 `/api`는 실제 서버로 fallback하지 않고 공통 404를 반환한다.
- 가격·재고는 조회 응답에만 포함하고 승인·견적·승인 사례에는 저장하지 않는다.
- localStorage, sessionStorage, IndexedDB, 쿠키, 실제 DB를 사용하지 않는다.
- 실제 LLM·RAG·Mouser·업로드 변환을 호출하지 않는다.
- 기존 사용자 변경을 보존하고 커밋·push·PR을 만들지 않는다.

---

### Task 1: 공통 전송 경계와 개발 모드 판별

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/conversations.ts`
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Produces: `dummyFlowEnabled(env): boolean`, `apiRequest(path: string, init?: RequestInit): Promise<Response>`
- Consumes: Task 2의 `dummyApiFetch(path, init)`를 동적 모드 분기에서 호출

- [x] **Step 1: 더미 모드 경계의 실패 테스트 작성**

```ts
expect(dummyFlowEnabled({ DEV: true, MODE: 'dummy' })).toBe(true)
expect(dummyFlowEnabled({ DEV: false, MODE: 'dummy' })).toBe(false)
expect(dummyFlowEnabled({ DEV: true, MODE: 'development' })).toBe(false)
```

- [x] **Step 2: focused test가 export 부재로 실패하는지 확인**

Run: `npm run test:run -- src/api/client.test.ts`
Expected: FAIL because `dummyFlowEnabled` is not exported.

- [x] **Step 3: `apiRequest`로 fetch 경계를 통합**

```ts
export const dummyFlowEnabled = (env: { DEV: boolean; MODE: string }) => env.DEV && env.MODE === 'dummy'

export function apiRequest(path: string, init: RequestInit = {}) {
  return dummyFlowEnabled(import.meta.env) ? dummyApiFetch(path, init) : fetch(path, init)
}
```

`apiFetch`와 `openRunStream`은 직접 `fetch` 대신 `apiRequest`를 사용한다. credentials, cache, signal, header, body 계약은 그대로 유지한다.

- [x] **Step 4: focused test 통과 확인**

Run: `npm run test:run -- src/api/client.test.ts src/hooks/useRunStream.test.tsx`
Expected: PASS.

### Task 2: 실제 DTO 형태의 메모리 더미 API

**Files:**
- Create: `frontend/src/api/dummy.ts`
- Create: `frontend/src/api/dummy.test.ts`
- Modify: `frontend/src/SRC.md`
- Modify: `SOJAFIT.md`

**Interfaces:**
- Produces: `dummyApiFetch(path: string, init?: RequestInit): Promise<Response>`
- Consumes: 브라우저 표준 `RequestInit`, `Response`, `AbortSignal`

- [x] **Step 1: 전체 endpoint와 비영속 상태의 실패 테스트 작성**

```ts
const projects = await dummyApiFetch('/api/projects').then(response => response.json())
expect(projects[0]).toMatchObject({ name: 'breadboard_supply', demo_id: 'breadboard_supply' })

const stream = await dummyApiFetch('/api/threads/dummy-thread/runs', {
  method: 'POST', body: JSON.stringify({ question: 'D1을 SS34로 바꿔도 되나요?', target_ref: 'D1' }),
})
expect(await stream.text()).toContain('event: completed')
```

승인 생성 → 사례 목록 → 가격 조회 → 견적 저장 → 사례 삭제와 unknown 404를 같은 파일에서 각각 검증한다. 견적 JSON에는 가격·재고 필드가 없음을 단언한다.

- [x] **Step 2: focused test가 모듈 부재로 실패하는지 확인**

Run: `npm run test:run -- src/api/dummy.test.ts`
Expected: FAIL because `./dummy` does not exist.

- [x] **Step 3: 최소 메모리 라우터 구현**

```ts
type DummyState = { approvedCase: ApprovedCaseDto | null; approval: ApprovalDto | null }
const state: DummyState = { approvedCase: null, approval: null }

export async function dummyApiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  init.signal?.throwIfAborted()
  const { pathname, searchParams } = new URL(path, 'http://dummy.local')
  // method + pathname으로 실제 DTO Response를 반환하고 unknown은 404로 끝낸다.
}
```

회로는 D1 중앙, J1·S1·F1·U1 주변 연결을 포함한다. 결과는 R01 역할과 SS34 후보, 판정 근거, 데이터시트 위치를 포함한다. 가격은 `/api/prices` 응답에만 둔다.

- [x] **Step 4: endpoint와 상태 테스트 통과 확인**

Run: `npm run test:run -- src/api/dummy.test.ts src/api/client.test.ts src/hooks/useRunStream.test.tsx`
Expected: PASS.

### Task 3: 명시적 실행 명령과 화면 고지

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/auth/AuthProvider.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/FRONTEND.md`
- Test: `frontend/src/auth/AuthProvider.test.tsx`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: `dummyFlowEnabled(import.meta.env)`
- Produces: `npm run dev:dummy`, 화면 문구 `더미 실행 모드 · 저장되지 않음`

- [x] **Step 1: mode 판별과 배지의 실패 테스트 작성**

```tsx
expect(dummyAuthEnabled({ DEV: true, MODE: 'dummy' })).toBe(true)
render(<DummyModeNotice enabled />)
expect(screen.getByText('더미 실행 모드 · 저장되지 않음')).toBeVisible()
```

- [x] **Step 2: focused test가 새 mode와 표시 부재로 실패하는지 확인**

Run: `npm run test:run -- src/auth/AuthProvider.test.tsx src/App.test.tsx`
Expected: FAIL on dummy mode authentication or missing notice.

- [x] **Step 3: 실행 명령과 공통 배지 구현**

```json
"dev:dummy": "vite --mode dummy"
```

`dummyAuthEnabled`는 기존 `VITE_DUMMY_AUTH=1` 또는 `MODE === 'dummy'`인 개발 모드만 허용한다. `App` 상단에는 `dummyFlowEnabled(import.meta.env)`일 때만 `demo-mode-notice`를 렌더링한다.

- [x] **Step 4: focused test와 build 통과 확인**

Run: `npm run test:run -- src/auth/AuthProvider.test.tsx src/App.test.tsx && npm run build`
Expected: PASS; production build succeeds.

### Task 4: route 가로채기 없는 전체 브라우저 흐름

**Files:**
- Create: `frontend/e2e/dummy-mode.spec.ts`
- Modify: `frontend/playwright.config.ts`
- Modify: `frontend/e2e/E2E.md`
- Modify: `SOJAFIT.md`

**Interfaces:**
- Consumes: `npm run dev:dummy` and the real frontend API boundary
- Produces: manual dummy flow browser regression without `page.route`

- [x] **Step 1: 실제 더미 서버만 사용하는 E2E 작성**

```ts
await page.goto('/app')
await expect(page.getByText('더미 실행 모드 · 저장되지 않음')).toBeVisible()
await page.getByRole('button', { name: 'breadboard_supply' }).click()
await page.getByLabel('대상 부품').selectOption('D1')
await page.getByLabel('질문').fill('D1을 SS34로 바꿔도 되나요?')
await page.getByRole('button', { name: 'D5에 질문하기' }).click()
await expect(page.getByRole('cell', { name: '역할상 충분' })).toBeVisible()
```

이후 후보 승인, 가격 조회, 수량 2 견적 저장, 승인 사례 삭제와 빈 상태까지 기존 accessible name으로 클릭한다. `page.route`는 사용하지 않는다.

- [x] **Step 2: Playwright 서버를 더미 mode로 실행**

`playwright.config.ts`의 webServer command를 `npm run dev:dummy -- --host 127.0.0.1 --port 4173`으로 바꾼다. 기존 route 기반 E2E도 동일 화면에서 계속 동작해야 한다.

- [x] **Step 3: 전체 E2E 통과 확인**

Run: `npm run e2e`
Expected: 기존 2건과 새 더미 mode 1건 모두 PASS.

### Task 5: 문서·작업 기록·전체 검증과 수동 실행

**Files:**
- Modify: `docs/worklog/osc.md`
- Modify: `docs/superpowers/plans/2026-11-09-dummy-full-flow.md`

**Interfaces:**
- Consumes: Tasks 1-4의 테스트 결과와 실제 브라우저 상태
- Produces: 재현 가능한 실행 기록과 사용자가 조작할 수 있는 실행 URL

- [x] **Step 1: 전체 프론트 검증**

Run: `npm run test:run`
Expected: all Vitest tests PASS.

Run: `npm run build`
Expected: TypeScript and Vite production build PASS.

Run: `npm run e2e`
Expected: all Playwright tests PASS.

- [x] **Step 2: 저장소와 diff 검증**

Run: `uv run pytest -q tests/repo/test_repo_layout.py`
Expected: PASS.

Run: `git diff --check`
Expected: no whitespace errors.

- [x] **Step 3: 수동 조작용 서버 실행과 브라우저 검증**

Run: `npm run dev:dummy -- --host 127.0.0.1 --port 5173`
Expected: `/app`에서 더미 배지가 보이고 외부 API 없이 마지막 사례 삭제까지 조작 가능.

- [x] **Step 4: 작업 기록과 계획 체크박스 갱신**

`docs/worklog/osc.md`에 바꾼 파일, 실행 명령, 실제 결과, 확인하지 못한 항목, 다음 할 일을 기록한다. 완료한 계획 단계의 `[ ]`를 `[x]`로 바꾼다.

- [x] **Step 5: 최종 diff 검토**

인증·사용자 소유권·DB 무결성·가격·재고 비저장·비밀값 경계가 약화되지 않았고 기존 사용자 변경을 되돌리지 않았는지 확인한다. 커밋·push·PR은 실행하지 않는다.
