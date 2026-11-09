# D5 Frontend Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a React + Vite workbench that lets authenticated users create circuit projects, run the existing D5 multi-agent pipeline, inspect evidence and judgements, resume interrupts, and save approved quotes and cases.

**Architecture:** Keep D5 in `backend/multi_agent/` as the only service execution engine and add thin FastAPI routers, focused service modules, PostgreSQL persistence, and a safe browser DTO around it. Serve the Vite production build from the same FastAPI origin; stream node-level progress through the run POST response and keep Mouser data outside graph state and persistent storage.

**Tech Stack:** Python 3.12, FastAPI, LangGraph with PostgreSQL checkpointer, PostgreSQL, React, Vite, TypeScript, React Router, TanStack Query, Vitest, Testing Library, Playwright, Docker multi-stage build.

## Global Constraints

- Work only on `OSC`; never push without the team leader's explicit approval in this conversation.
- D5 (`backend/multi_agent/build.py`) is the service engine. Do not expose a D4 selector or reproduce D5 routing in React.
- Keep LLM and embedding calls in `backend/services/llm.py`; keep numeric and unit comparison in `backend/judge/`.
- The browser receives safe DTOs, never raw prompts, model responses, `Plan`, `TaskReport`, exceptions, server paths, secrets, or chain-of-thought.
- Accept only UTF-8 KiCad `.net` text up to 5 MiB. Discard original bytes after normalization; persist normalized connections, source SHA-256, parser version, and timestamps only.
- Never persist Mouser responses, price, stock, product URLs, or fetched-at values in DB, messages, checkpoints, quotes, traces, logs, browser storage, or test fixtures.
- Preserve the common `error.code/message/request_id` JSON contract and server-generated `X-Request-ID`.
- One active run per thread. Never auto-resubmit a question after a stream failure.
- Every judgement screen states that identical behavior is not guaranteed.
- Root `SPEC.md` and `docs/adr/` are leader-owned. Record exact requested edits for the leader instead of changing those files on `OSC`.
- Use `uv` for Python dependencies and `npm` with a committed `package-lock.json` for frontend dependencies.
- Each PR has one purpose, updates folder docs/tree/worklog, runs its focused tests, then runs `uv run pytest -q` when the risk justifies it.

---

## PR 1 — Contract, frontend foundation, and existing APIs

### Task 1: Write the feature contract before code

**Files:**
- Create: `docs/specs/d5-frontend-service.md`
- Modify: `docs/specs/SPECS.md`
- Modify: `SOJAFIT.md`
- Modify: `docs/worklog/osc.md`

**Interfaces:**
- Consumes: approved design `docs/superpowers/specs/2026-11-09-d5-frontend-service-design.md`.
- Produces: five-section Why/Goal/What/How/AC contract used by every later task.

- [ ] **Step 1: Write the contract with measurable ACs**

Use exactly these top-level sections and include at least the listed AC identifiers:

```markdown
## Why
## Goal
## What
## How
## AC (Given-When-Then)

AC-01 same-origin login and session restore
AC-02 demo project creation
AC-03 upload normalization and original disposal
AC-04 D5 run completion
AC-05 interrupt and resume
AC-06 evidence and five verdicts
AC-07 price response is not persisted
AC-08 approval before quote
AC-09 per-user authorization
AC-10 project cascade deletion
```

- [ ] **Step 2: Record leader-owned root document changes**

Add a section named `조장 반영 요청` containing exact proposed paragraphs for `SPEC.md` sections 2, 4, 8.4, and 8.5 and a proposed ADR title `React·Vite 화면은 FastAPI와 같은 출처로 배포한다`. Do not edit `SPEC.md` or `docs/adr/`.

- [ ] **Step 3: Validate document placement**

Run: `uv run pytest -q tests/repo/test_repo_layout.py`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add docs/specs/d5-frontend-service.md docs/specs/SPECS.md SOJAFIT.md docs/worklog/osc.md
git commit -m "docs: D5 프론트엔드 기능 계약"
```

### Task 2: Scaffold the same-origin React application

**Files:**
- Create: `frontend/package.json`, `frontend/package-lock.json`
- Create: `frontend/index.html`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tsconfig.app.json`, `frontend/tsconfig.node.json`
- Create: `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/styles.css`
- Create: `frontend/src/test/setup.ts`, `frontend/src/App.test.tsx`
- Create: `backend/web/app.py`
- Create: `tests/api/test_frontend.py`
- Modify: `backend/main.py`, `Dockerfile`, `.gitignore`
- Modify: `backend/web/WEB.md`, `backend/BACKEND.md`, `tests/api/API.md`, `SOJAFIT.md`, `docs/worklog/osc.md`

**Interfaces:**
- Consumes: existing `FastAPI app` and `/api/*` routes.
- Produces: `mount_frontend(app: FastAPI, dist: Path, fallback: Path) -> None`; React routes `/login`, `/app`, `/admin/users`; Vite `/api` proxy.

- [ ] **Step 1: Write failing FastAPI fallback tests**

```python
def test_api_404_stays_json(client):
    response = client.get('/api/not-a-route')
    assert response.status_code == 404
    assert response.json()['error']['code'] == 'NOT_FOUND'

def test_react_route_returns_index(client, built_frontend):
    response = client.get('/app')
    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text
```

Run: `uv run pytest -q tests/api/test_frontend.py`

Expected: FAIL because the frontend mount does not exist.

- [ ] **Step 2: Create Vite React TypeScript and test dependencies**

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install react-router-dom @tanstack/react-query
npm install -D vitest jsdom @testing-library/react @testing-library/jest-dom @playwright/test
```

Set scripts to `dev`, `build`, `test`, `test:run`, and `e2e`; configure Vitest with `environment: "jsdom"` and `setupFiles: ["./src/test/setup.ts"]`.

- [ ] **Step 3: Implement API-first SPA fallback**

```python
def mount_frontend(app: FastAPI, dist: Path, fallback: Path) -> None:
    assets = dist / 'assets'
    if assets.is_dir():
        app.mount('/assets', StaticFiles(directory=assets), name='frontend-assets')

    @app.get('/{path:path}', include_in_schema=False)
    def frontend(path: str):
        if path == 'api' or path.startswith('api/'):
            raise HTTPException(status_code=404)
        index = dist / 'index.html'
        return FileResponse(index) if index.is_file() else FileResponse(fallback)
```

Register this after all API routes with `mount_frontend(app, FRONTEND_DIST, LOGIN_PAGE)`. Keep `/health` and Google callbacks unchanged.

- [ ] **Step 4: Build frontend in Docker**

Use a Node build stage that runs `npm ci` and `npm run build`, then copy `frontend/dist` to `/app/frontend/dist` in the Python runtime stage. Do not copy `node_modules`.

- [ ] **Step 5: Run focused tests and build**

```bash
uv run pytest -q tests/api/test_frontend.py tests/api/test_health.py
cd frontend && npm run test:run && npm run build
```

Expected: all tests PASS and `frontend/dist/index.html` exists.

- [ ] **Step 6: Commit**

```bash
git add frontend backend/web/app.py backend/main.py Dockerfile .gitignore backend/web/WEB.md backend/BACKEND.md tests/api SOJAFIT.md docs/worklog/osc.md
git commit -m "feat(web): React Vite 같은 출처 기반"
```

### Task 3: Connect login, admin users, and transient prices

**Files:**
- Create: `frontend/src/api/client.ts`, `frontend/src/api/auth.ts`, `frontend/src/api/admin.ts`, `frontend/src/api/prices.ts`
- Create: `frontend/src/auth/AuthProvider.tsx`, `frontend/src/auth/RequireAuth.tsx`
- Create: `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/AdminUsersPage.tsx`, `frontend/src/pages/WorkbenchPage.tsx`
- Create: `frontend/src/components/PricePanel.tsx`
- Create tests beside each page/component as `*.test.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/styles.css`

**Interfaces:**
- Consumes: `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`, `/api/auth/google/status`, `/api/admin/users`, `/api/prices`.
- Produces: `apiFetch<T>(path, init)`, `AuthProvider`, protected routes, non-persistent `PricePanel`.

- [ ] **Step 1: Write failing API client and auth tests**

```ts
it('keeps the request id from common errors', async () => {
  server.use(http.get('/api/auth/me', () => HttpResponse.json(
    { error: { code: 'UNAUTHORIZED', message: '로그인이 필요합니다.', request_id: 'req-1' } },
    { status: 401 },
  )))
  await expect(apiFetch('/api/auth/me')).rejects.toMatchObject({ code: 'UNAUTHORIZED', requestId: 'req-1' })
})
```

Run: `cd frontend && npm run test:run`

Expected: FAIL because `apiFetch` and auth pages do not exist.

- [ ] **Step 2: Implement the typed fetch boundary**

```ts
export type ApiError = { code: string; message: string; requestId: string }

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { ...init, credentials: 'same-origin' })
  if (!response.ok) {
    const body = await response.json()
    throw { code: body.error.code, message: body.error.message, requestId: body.error.request_id } satisfies ApiError
  }
  return response.json() as Promise<T>
}
```

Do not read or write auth tokens in `localStorage` or `sessionStorage`.

- [ ] **Step 3: Implement protected routes and pages**

`AuthProvider` restores `/api/auth/me`, redirects 401 to `/login`, and exposes `login`, `logout`, and `user`. `AdminUsersPage` renders only for `role === 'admin'`. `PricePanel` keeps responses in component memory, sets no persistent query cache, and clears data when its part list changes.

- [ ] **Step 4: Verify**

```bash
cd frontend && npm run test:run && npm run build
cd .. && uv run pytest -q tests/api/test_auth.py tests/api/test_prices.py tests/api/test_frontend.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat(web): 인증 관리자 가격 화면 연결"
```

## PR 2 — Projects, demo circuits, and upload normalization

### Task 4: Add user-owned project persistence

**Files:**
- Create: `db/013_projects.sql`
- Create: `backend/projects/repository.py`, `backend/projects/models.py`, `backend/projects/PROJECTS.md`, `backend/projects/__init__.py`
- Create: `backend/api/projects.py`, `backend/api/API.md`, `backend/api/__init__.py`
- Create: `tests/projects/test_project_repository.py`, `tests/api/test_projects.py`, `tests/projects/PROJECTS.md`
- Modify: `backend/main.py`, `db/DB.md`, `db/schema/erd.md`, `db/schema/table-definition.md`, `backend/BACKEND.md`, `tests/TESTS.md`, `SOJAFIT.md`, `docs/worklog/osc.md`

**Interfaces:**
- Produces: `ProjectRepository.create_demo(user_id, demo_id, name)`, `list_owned(user_id)`, `get_owned(user_id, project_id)`, `rename_owned(...)`, `delete_owned(...)`.
- Produces HTTP: `GET/POST /api/projects`, `GET/PATCH/DELETE /api/projects/{id}`, `GET /api/demo-circuits`.

- [ ] **Step 1: Write failing repository authorization tests**

```python
def test_project_is_visible_only_to_owner(repo, users):
    project = repo.create_demo(users.a, 'breadboard_supply', '전원 회로')
    assert repo.get_owned(users.a, project.id).id == project.id
    with pytest.raises(ProjectNotFound):
        repo.get_owned(users.b, project.id)
```

- [ ] **Step 2: Add migration and repository**

Create `projects(id bigserial, user_id bigint references users, name text, source_kind text check in ('demo','upload'), demo_id text null, created_at timestamptz, updated_at timestamptz)` and `circuits(project_id bigint primary key references projects on delete cascade, connections jsonb, source_sha256 text, parser_version text, created_at timestamptz)`. Revoke public roles like existing business tables.

- [ ] **Step 3: Add router and common errors**

Map missing or foreign resources to the same 404 response to avoid ownership disclosure. Require `auth.check_origin` for POST, PATCH, and DELETE.

- [ ] **Step 4: Verify and commit**

```bash
uv run pytest -q tests/projects tests/api/test_projects.py tests/repo/test_repo_layout.py
git add db/013_projects.sql backend/projects backend/api tests/projects tests/api/test_projects.py backend/main.py db backend/BACKEND.md tests/TESTS.md SOJAFIT.md docs/worklog/osc.md
git commit -m "feat(projects): 사용자별 회로 프로젝트"
```

### Task 5: Normalize KiCad uploads without retaining originals

**Files:**
- Create: `backend/projects/netlist.py`
- Create: `tests/projects/test_netlist.py`, `tests/fixtures/netlists/minimal.net`, `tests/fixtures/netlists/invalid.net`
- Modify: `backend/api/projects.py`, `tests/api/test_projects.py`, `pyproject.toml`, `uv.lock`

**Interfaces:**
- Produces: `normalize_netlist(raw: bytes) -> NormalizedCircuit`; `NormalizedCircuit.connections`, `.source_sha256`, `.parts`.
- Produces HTTP: `POST /api/projects/upload` multipart field `file`, text field `name`.

- [ ] **Step 1: Add RED tests for size, encoding, structure, and normalization**

```python
def test_normalize_returns_only_required_connections():
    result = normalize_netlist(MINIMAL.read_bytes())
    assert result.parts == ('D1', 'R1')
    assert set(result.connections) == {'parts', 'nets'}
    assert 'source' not in result.connections
```

Also assert rejection of non-UTF-8, more than `5 * 1024 * 1024` bytes, missing `(export`, no components, and no nets.

- [ ] **Step 2: Add multipart dependency**

Run: `uv add python-multipart`

- [ ] **Step 3: Implement a bounded S-expression parser**

Parse only KiCad export nodes needed for `parts` and `nets`; cap nesting depth at 64, token count at 500,000, component count at 100,000, and net count at 100,000. Hash raw bytes before decoding, return immutable normalized data, and keep no file path or raw text on the result.

- [ ] **Step 4: Prove original disposal at the API boundary**

Use `UploadFile`, read at most 5 MiB + 1 byte, normalize in memory, insert only `connections`, `source_sha256`, and `parser_version`, then close the upload in `finally`. Tests must inspect the inserted repository payload and assert that the raw marker text is absent.

- [ ] **Step 5: Verify and commit**

```bash
uv run pytest -q tests/projects/test_netlist.py tests/api/test_projects.py
git add backend/projects/netlist.py backend/api/projects.py tests pyproject.toml uv.lock
git commit -m "feat(projects): KiCad 넷리스트 안전한 정규화"
```

### Task 6: Build project and circuit setup UI

**Files:**
- Create: `frontend/src/api/projects.ts`
- Create: `frontend/src/components/ProjectSidebar.tsx`, `frontend/src/components/CircuitSetup.tsx`, `frontend/src/components/CircuitSummary.tsx`
- Create corresponding `*.test.tsx`
- Modify: `frontend/src/pages/WorkbenchPage.tsx`, `frontend/src/styles.css`

**Interfaces:**
- Consumes: project and demo circuit endpoints from Tasks 4–5.
- Produces: selected `projectId` and `targetRef` in route/query state; no circuit parsing in React.

- [ ] **Step 1: Write failing interaction tests**

Test demo creation, upload 413/400 messages with request ID, target selection, rename, and delete confirmation. Assert file inputs accept `.net` only and are cleared after success or failure.

- [ ] **Step 2: Implement minimal project components**

Use TanStack Query keys `['projects']`, `['project', id]`, and `['demo-circuits']`. Invalidate project queries after mutations. Do not store normalized circuit JSON in browser storage.

- [ ] **Step 3: Verify and commit**

```bash
cd frontend && npm run test:run && npm run build
git add frontend/src
git commit -m "feat(web): 회로 프로젝트와 대상 선택"
```

## PR 3 — Persistent D5 threads, runs, interrupts, and safe DTOs

### Task 7: Assemble D5 with production dependencies and PostgreSQL checkpoints

**Files:**
- Create: `backend/services/d5.py`
- Create: `backend/conversations/models.py`, `backend/conversations/repository.py`, `backend/conversations/CONVERSATIONS.md`, `backend/conversations/__init__.py`
- Create: `db/014_conversations.sql`
- Create: `tests/services/test_d5.py`, `tests/conversations/test_repository.py`, `tests/conversations/CONVERSATIONS.md`
- Modify: `backend/services/SERVICES.md`, `db/DB.md`, `db/schema/erd.md`, `db/schema/table-definition.md`, `SOJAFIT.md`, `docs/worklog/osc.md`

**Interfaces:**
- Produces: `D5Service.start(thread_id: str, run_input: RunInput) -> AsyncIterator[RunEvent]`; `resume(thread_id, answers) -> AsyncIterator[RunEvent]`.
- Uses: `multi_agent.build_graph(chat=llm.node_chat, retriever=..., lookup=..., specs=..., find=..., checkpointer=...)` with `judge_enabled=True`.

- [ ] **Step 1: Write failing dependency and interrupt tests**

Use fakes for chat, retriever, lookup, specs, and find. Assert the service passes one stable LangGraph `thread_id`, produces `requires_input`, resumes with `Command(resume={'answers': ...})`, and does not rerun `judge_read`.

- [ ] **Step 2: Add conversation schema**

Create `threads`, `messages`, and `runs` tables with user ownership through project, one partial unique index for active run states `running` and `requires_input`, JSONB safe result, and no price columns. Install LangGraph PostgreSQL checkpoint tables through the library setup path, not copied hand-written SQL.

- [ ] **Step 3: Implement dependency assembly**

Keep all model calls in `backend/services/llm.py`; wrap existing MCP/repository functions without changing D5 nodes. Convert stored normalized circuit to the same `target_part` structure that `read_input` produces.

- [ ] **Step 4: Verify and commit**

```bash
uv run pytest -q tests/services/test_d5.py tests/conversations tests/multi_agent
git add backend/services/d5.py backend/conversations db/014_conversations.sql tests/services/test_d5.py tests/conversations backend/services/SERVICES.md db SOJAFIT.md docs/worklog/osc.md
git commit -m "feat(d5): 영속 대화와 인터럽트 재개"
```

### Task 8: Add streaming run API and safe result DTO

**Files:**
- Create: `backend/api/conversations.py`, `backend/conversations/dto.py`
- Create: `tests/api/test_conversations.py`, `tests/conversations/test_dto.py`
- Modify: `backend/main.py`, `backend/api/API.md`, `tests/api/API.md`

**Interfaces:**
- Produces HTTP: thread list/create/get, streaming run start, run get, streaming resume.
- Produces DTO fields: `answer`, `status`, `stage`, `question_type`, `evidence`, `judgement`, `price_parts`, `refusal`, `interrupt`, `request_id`.

- [ ] **Step 1: Write DTO allow-list tests**

```python
def test_browser_dto_excludes_internal_state():
    dto = result_dto(STATE_WITH_INTERNAL_FIELDS, request_id='req-1')
    body = dto.model_dump()
    assert set(body) == {'answer','status','stage','question_type','evidence','judgement','price_parts','refusal','interrupt','request_id'}
    assert not {'facts','plan','reports','counters','check'} & body.keys()
```

- [ ] **Step 2: Write streaming and concurrency tests**

Assert event order `run_started → status* → terminal`, DB terminal state is committed before the terminal event, a second active run gets 409, foreign threads get 404, and disconnect recovery uses `GET /api/runs/{id}` without starting another D5 invocation.

- [ ] **Step 3: Implement routers and SSE encoder**

Use `StreamingResponse(iterator, media_type='text/event-stream')`. Each frame is `event: <type>\ndata: <json>\n\n`; JSON contains only public event fields. Check origin on POST and resume. Never log event data.

- [ ] **Step 4: Verify and commit**

```bash
uv run pytest -q tests/api/test_conversations.py tests/conversations/test_dto.py tests/services/test_d5.py
git add backend/api/conversations.py backend/conversations/dto.py backend/main.py tests/api tests/conversations backend/api/API.md
git commit -m "feat(api): D5 실행 스트림과 안전한 결과"
```

## PR 4 — D5 workbench UI

### Task 9: Implement conversation, progress, interrupt, evidence, and judgement panels

**Files:**
- Create: `frontend/src/api/conversations.ts`, `frontend/src/hooks/useRunStream.ts`
- Create: `frontend/src/components/ConversationPanel.tsx`, `RunStatus.tsx`, `InterruptForm.tsx`, `EvidencePanel.tsx`, `JudgementTable.tsx`, `ApprovalPanel.tsx`
- Create corresponding `*.test.tsx`
- Modify: `frontend/src/pages/WorkbenchPage.tsx`, `frontend/src/styles.css`

**Interfaces:**
- Consumes safe DTO and SSE events from Task 8.
- Produces three-pane workbench; `ApprovalPanel` remains disabled until PR 5 supplies approval endpoints.

- [ ] **Step 1: Write failing stream state-machine tests**

Test start, ordered stage updates, interrupt form, resume, completed, refused, failed, malformed frame, network close followed by status fetch, and no automatic question resubmission.

- [ ] **Step 2: Implement streaming fetch hook**

```ts
type RunState =
  | { status: 'idle' }
  | { status: 'running'; runId: string; stage: string }
  | { status: 'requires_input'; runId: string; interrupt: InterruptDto }
  | { status: 'completed' | 'refused'; runId: string; result: ResultDto }
  | { status: 'failed'; runId?: string; error: ApiError }
```

Abort only on route change or explicit cancel. On network close call `GET /api/runs/{runId}` once, then poll only while the server reports `running`.

- [ ] **Step 3: Render evidence and verdicts without inference**

Map only backend verdict codes to the five Korean labels. Render document, page, table/row or section exactly as sent. Show package change separately and show “같은 동작은 보장하지 않습니다.” whenever a judgement exists.

- [ ] **Step 4: Verify and commit**

```bash
cd frontend && npm run test:run && npm run build
git add frontend/src
git commit -m "feat(web): D5 대화 근거 판정 작업대"
```

### Task 10: Finish responsive layout and accessibility

**Files:**
- Modify: `frontend/src/styles.css` and workbench components
- Create: `frontend/e2e/workbench.spec.ts`
- Create: `frontend/playwright.config.ts`

**Interfaces:**
- Produces: desktop three panes; narrow-screen project drawer and right-side tabs; keyboard and screen-reader contracts.

- [ ] **Step 1: Add failing accessibility-oriented component tests**

Assert labelled inputs, visible focus, `aria-live` run status, error summary focus, keyboard tab activation, and dialog focus return after project deletion.

- [ ] **Step 2: Implement responsive CSS and interaction**

Use a desktop grid `18rem minmax(24rem, 1fr) minmax(20rem, 28rem)`. Below 900 px keep conversation visible, move projects to a modal drawer, and render right panels as tabs.

- [ ] **Step 3: Add Playwright smoke**

Cover login → demo project → target selection → fake D5 completed response → evidence and judgement visible. Use a local fake backend fixture; do not call live models or Mouser.

- [ ] **Step 4: Verify and commit**

```bash
cd frontend && npm run test:run && npm run build && npx playwright test
git add frontend
git commit -m "test(web): 작업대 반응형 접근성 흐름"
```

## PR 5 — Human approval, quotes, and approved cases

### Task 11: Add approval and quote persistence with price exclusion

**Files:**
- Create: `db/015_approvals_quotes.sql`
- Create: `backend/services/quotes.py`, `backend/api/quotes.py`
- Create: `tests/services/test_quotes.py`, `tests/api/test_quotes.py`
- Modify: `backend/main.py`, `backend/services/SERVICES.md`, `backend/api/API.md`, `db/DB.md`, `db/schema/erd.md`, `db/schema/table-definition.md`, `SOJAFIT.md`, `docs/worklog/osc.md`

**Interfaces:**
- Produces: approve completed judgement once; create quote only from approval; list/delete user approved cases.
- Enforces: immutable judgement/evidence snapshot; recursive rejection of forbidden price keys.

- [ ] **Step 1: Write failing business-rule tests**

Test no judgement, `NOT_SUFFICIENT` or `NOT_VERIFIED` result, failed result, approval twice, quote before approval, foreign resource, case deletion, and forbidden keys `price`, `price_breaks`, `availability`, `product_url`, `fetched_at` anywhere in a snapshot.

- [ ] **Step 2: Add schema and service**

Create `approvals`, `quotes`, and `approved_cases` tables with ownership, foreign keys, unique approval per message, JSONB snapshots, and cascade behavior. `quotes.py` must call `assert_no_price_data(snapshot)` before every insert.

- [ ] **Step 3: Add API and verify**

```bash
uv run pytest -q tests/services/test_quotes.py tests/api/test_quotes.py tests/api/test_prices.py
git add db/015_approvals_quotes.sql backend/services/quotes.py backend/api/quotes.py backend/main.py tests db backend/services/SERVICES.md backend/api/API.md SOJAFIT.md docs/worklog/osc.md
git commit -m "feat(quotes): 사람 승인 견적과 사례 기억"
```

### Task 12: Connect approval, quote, and case UI

**Files:**
- Create: `frontend/src/api/quotes.ts`, `frontend/src/components/QuotePanel.tsx`, `frontend/src/components/ApprovedCasesPanel.tsx`
- Create corresponding `*.test.tsx`
- Modify: `frontend/src/components/ApprovalPanel.tsx`, `frontend/src/pages/WorkbenchPage.tsx`

**Interfaces:**
- Consumes PR 5 approval/quote/case endpoints and existing transient `/api/prices`.
- Produces: explicit human approval, saved quote without price, live price display refreshed when quote opens.

- [ ] **Step 1: Write failing UI contract tests**

Assert approval confirmation names the candidate and verdict, quote button is disabled before approval, saved quote JSON never receives price fields, opening a quote calls `/api/prices`, and case deletion requires confirmation.

- [ ] **Step 2: Implement and verify**

```bash
cd frontend && npm run test:run && npm run build
git add frontend/src
git commit -m "feat(web): 승인 견적 사례 화면"
```

## PR 6 — Integration, security, and release verification

### Task 13: Verify the complete service without paid external calls

**Files:**
- Create: `frontend/e2e/full-flow.spec.ts`
- Create: `tests/api/test_full_service_flow.py`
- Modify: `README.md`, `backend/web/design.md`, relevant folder docs, `SOJAFIT.md`, `docs/worklog/osc.md`

**Interfaces:**
- Consumes all earlier PR contracts.
- Produces: reproducible local demo and CI evidence for the full user flow.

- [ ] **Step 1: Add backend full-flow test**

Use a temporary PostgreSQL database, fake D5 dependencies, fake price transport, and two users. Cover login → upload → target → run interrupt → resume → result → approval → quote → reload → forbidden cross-user access → delete cascade.

- [ ] **Step 2: Add browser full-flow test**

Run the same visible path with API fakes and assert the disclaimer, evidence, verdict, transient price, approval, quote reload, and deletion UI. No live LLM, embedding, Langfuse, MCP network, or Mouser calls.

- [ ] **Step 3: Run all verification**

```bash
uv lock --check
uv run pytest -q
cd frontend
npm ci
npm run test:run
npm run build
npx playwright test
cd ..
docker build -t sojafit:d5-frontend .
```

Expected: every command exits 0; no secret or generated `frontend/dist` file is staged.

- [ ] **Step 4: Review final diff and documentation**

Confirm `git diff --check`, no raw netlist fixtures contain private data, no price response appears in DB/message fixtures, and every new file appears in `SOJAFIT.md` and its folder description.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/full-flow.spec.ts tests/api/test_full_service_flow.py README.md backend/web/design.md SOJAFIT.md docs/worklog/osc.md
git commit -m "test(web): D5 서비스 전체 사용자 흐름"
```

## Execution stop conditions

- Stop before any `git push`, PR creation, shared DB migration, live model call, live Mouser call, or deployment unless separately authorized.
- Stop if the leader-owned `SPEC.md`/ADR updates are required for the next PR and no leader review path is available; report the exact proposed text already recorded in the feature spec.
- Stop if current `origin/main` changes D5 contracts, auth cookie behavior, or DB migration numbers; rebase the plan against the new source before coding.
- Do not claim completion until the full backend, frontend, Playwright, and Docker checks in Task 13 pass or the unverified checks are explicitly reported.

