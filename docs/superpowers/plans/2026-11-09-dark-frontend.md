# SojaFit Default Dark Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 로그인·관리자·회로 작업대 전체를 Flux형 PCB 편집기 셸을 참고한 기본 다크 테마로 만든다.

**Architecture:** 기존 React 구조와 데이터 흐름은 유지하고 `frontend/src/styles.css`의 의미 토큰과 기존 selector만 바꾼다. 다크 테마의 존재는 현재 로그인 화면 테스트에서 CSS 계약으로 고정하며, 실제 UI는 기존 가짜 API 브라우저 흐름으로 확인한다.

**Tech Stack:** React 19, Vite 8, TypeScript, Vitest, Testing Library, Playwright, CSS custom properties

## Global Constraints

- 전체 프론트에 기본 다크 테마를 적용하고 라이트 모드·전환 버튼·브라우저 저장소는 추가하지 않는다.
- 외부 폰트, 이미지, UI·그래프 라이브러리를 추가하지 않는다.
- 기존 API·인증·소유권·가격 비저장·라우팅·3열 작업대·모바일 drawer와 결과 tab 동작을 바꾸지 않는다.
- 연결 방향 데이터가 없으므로 SVG 선에 화살표나 marker를 추가하지 않는다.
- 기존 사용자 변경을 보존하고 커밋·push·PR을 만들지 않는다.

---

### Task 1: 기본 다크 토큰과 공통 셸

**Files:**
- Modify: `frontend/src/pages/LoginPage.test.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: 기존 `.shell`, `.topbar`, `.panel`, form, table, alert selector
- Produces: `:root`의 `color-scheme: dark`, `--canvas`, `--surface`, `--surface-raised`, `--line`, `--text`, `--muted`, `--trace`, `--warning`, `--danger` CSS 토큰

- [x] **Step 1: 기본 테마 계약의 실패 테스트 작성**

`LoginPage.test.tsx`에서 `../styles.css`를 import하고 다음 검사를 추가한다.

```tsx
it('uses the dark editor theme by default', () => {
  const root = getComputedStyle(document.documentElement)
  expect(root.colorScheme).toBe('dark')
  expect(root.getPropertyValue('--canvas').trim()).toBe('#0b0f14')
  expect(root.getPropertyValue('--trace').trim()).toBe('#35d0ba')
})
```

- [x] **Step 2: RED 확인**

Run: `npm run test:run -- src/pages/LoginPage.test.tsx`

Expected: `colorScheme` 또는 `--canvas` 기대값 불일치로 FAIL.

- [x] **Step 3: 공통 다크 토큰과 셸 구현**

`styles.css`의 `:root`를 승인 색상으로 바꾸고 `body`, `.topbar`, `.panel`, form, button, table, alert, focus selector가 의미 토큰만 사용하게 한다. 입력과 버튼은 최소 높이 40px, 모서리는 최대 6px, focus outline은 `--trace`로 유지한다.

- [x] **Step 4: 로그인·관리자·기본 계약 확인**

Run: `npm run test:run -- src/pages/LoginPage.test.tsx src/pages/AdminUsersPage.test.tsx`

Expected: 두 파일 전체 PASS.

---

### Task 2: 작업대·상태·SVG 편집기 표면

**Files:**
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/components/CircuitContextDiagram.test.tsx`

**Interfaces:**
- Consumes: 기존 `.workbench-grid`, `.project-list`, `.result-tabs`, `.run-status`, `.context-*`, `.candidate-*`, `.disclaimer` selector와 SVG DOM
- Produces: 다크 도구 panel 계층, 선택·상태 표면, 격자 SVG 배경, 청록 직접 연결·청회색 2단계 연결

- [x] **Step 1: SVG 방향 계약을 유지하는 테스트 확인**

`CircuitContextDiagram.test.tsx`의 렌더링 결과에 `marker-end`가 없다는 기존 assertion을 유지하고, `.context-diagram`이 존재하는지 명시한다.

```tsx
expect(container.querySelector('.context-diagram')).toBeInTheDocument()
expect(container.querySelector('[marker-end]')).not.toBeInTheDocument()
```

- [x] **Step 2: 작업대 표면 구현**

`styles.css`에서 프로젝트 선택, 후보 선택, tab, 진행·거절·실패, 경고, drawer, 근거·표를 승인된 다크 토큰으로 바꾼다. SVG에는 CSS `linear-gradient` 두 개로 20px 격자를 만들고 target node에 한정된 낮은 강도의 `drop-shadow`를 적용한다. text·edge stroke와 세부 panel 배경을 다크 대비에 맞춘다.

- [x] **Step 3: 관련 컴포넌트 테스트**

Run: `npm run test:run -- src/components/CircuitContextDiagram.test.tsx src/components/D5Panels.test.tsx src/pages/WorkbenchPage.test.tsx`

Expected: 세 파일 전체 PASS.

---

### Task 3: 전체 회귀와 브라우저 확인

**Files:**
- Modify: `docs/worklog/osc.md`

**Interfaces:**
- Consumes: Task 1·2의 CSS와 기존 Vite 개발 서버
- Produces: 테스트·빌드·브라우저·diff 결과가 기록된 작업 로그

- [x] **Step 1: 전체 프론트 검증**

Run: `npm run test:run`

Expected: 모든 Vitest 테스트 PASS.

Run: `npm run build`

Expected: TypeScript와 Vite production build PASS.

- [x] **Step 2: 브라우저 확인**

개발 서버의 로그인 또는 더미 로그인 작업대를 새로고침한다. 기본 배경, 상단 바, panel, form, 오류, 표, SVG 격자, 선택 상태를 확인한다. 900px 이하에서는 프로젝트 drawer와 결과 tab이 기존대로 노출되는지 확인한다.

- [x] **Step 3: 저장소 경계와 최종 diff 확인**

Run: `uv run pytest -q tests/repo/test_repo_layout.py`

Expected: 전체 PASS.

Run: `git diff --check`

Expected: 출력 없이 종료 코드 0.

`git diff -- frontend docs/superpowers docs/worklog/osc.md SOJAFIT.md`에서 API·인증·데이터 계약에 새 변경이 없는지 확인한다.

- [x] **Step 4: 작업 기록 갱신**

`docs/worklog/osc.md`에 바꾼 파일, RED/GREEN 결과, 전체 테스트·build·브라우저 확인, 확인하지 못한 항목과 다음 작업을 기록한다.
