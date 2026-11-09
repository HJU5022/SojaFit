# Circuit Context Diagram Implementation Plan

> **For agentic workers:** 이 작업은 사용자의 지시에 따라 현재 세션의 메인 에이전트가 인라인으로 실행한다. 새 서브에이전트, 브랜치, 커밋, push, PR을 만들지 않는다. 단계는 checkbox로 추적한다.

**Goal:** 기존 프로젝트 연결 데이터와 안전한 D5 분석 결과를 결합해 대상 부품 중심의 1·2단계 SVG 연결 개념도를 제공한다.

**Architecture:** 프로젝트 상세의 `connections`를 기존 `circuit_around` 규칙과 같은 순수 TypeScript adapter로 변환한다. 역할명은 `roles.yaml` 정본에서 코드·이름만 반환하는 인증된 읽기 API로 받고, 역할 근거·조건·후보는 기존 run DTO를 사용한다. SVG는 표시만 담당하고 후보 선택은 기존 판정·근거 패널의 공통 상태로 연결한다.

**Tech Stack:** React 19, TypeScript, Vite, TanStack Query, Testing Library/Vitest, FastAPI, Pydantic, pytest

## Global Constraints

- 루트 `SPEC.md`와 `docs/adr/`는 수정하지 않는다.
- production에서 fixture로 폴백하지 않는다.
- 새 그래프·이미지 라이브러리를 추가하지 않고 SVG와 기존 CSS만 사용한다.
- 방향, 전압, 전류, 역할을 추정하지 않는다.
- 숫자 비교와 단위 비교는 `backend/judge/` 밖에 추가하지 않는다.
- 업로드 파일·견적·가격·재고 저장 범위를 넓히지 않는다.
- 기존 사용자 변경을 보존하고 커밋·push·PR을 만들지 않는다.

---

### Task 1: 역할명 읽기 계약

**Files:**
- Modify: `tests/api/test_conversations.py`
- Modify: `backend/api/conversations.py`
- Modify: `backend/api/API.md`
- Modify: `frontend/src/api/conversations.ts`

**Interfaces:**
- Produces: `GET /api/judge/roles -> Array<{code: string; name: string}>`
- Consumes: `backend.judge.conditions.load() -> dict[str, dict]`

- [ ] `test_role_catalog_requires_login_and_exposes_only_code_and_name`를 먼저 작성한다. 비로그인은 401, 인증 응답은 `R01`의 이름을 포함하고 각 항목 key가 `code`, `name`뿐인지 검사한다.
- [ ] `uv run pytest -q tests/api/test_conversations.py -k role_catalog`을 실행해 404로 실패하는지 확인한다.
- [ ] `conversations.py`에 `RoleLabel(BaseModel)`과 인증된 `GET /judge/roles`를 추가한다. `conditions.load()`의 각 규칙에서 이름만 뽑고 역할 코드 순서로 반환한다.
- [ ] 프론트에 `RoleLabel`과 `listJudgeRoles(signal?)`를 추가하고 API 문서에 인증·읽기 전용·노출 필드를 기록한다.
- [ ] 같은 pytest 명령을 다시 실행해 통과를 확인한다.

### Task 2: 연결 adapter

**Files:**
- Create: `frontend/src/components/circuitContext.ts`
- Create: `frontend/src/components/circuitContext.test.ts`
- Modify: `frontend/src/api/projects.ts`

**Interfaces:**
- Produces: `buildCircuitContext(project: Project, targetRef: string, judgement?: JudgementDto, roleLabels?: RoleLabel[], missing?: string[]): CircuitContext`
- Produces: `CircuitContext`의 `target`, `nets`, `nodes`, `role`, `conditions`, `missing`, `candidates`, `state`
- Consumes: 프로젝트의 `parts|components`, `nets`; 기존 judgement의 `roles`, `role_evidence`, 후보 `checks|missing`

- [ ] `breadboard_supply`의 실제 모양을 축약한 fixture로 D1 중앙, S1·F1 직접 연결, J1·U1 2단계 연결을 기대하는 실패 테스트를 작성한다.
- [ ] 빈 nets, 존재하지 않는 target, 값·패키지 누락, 역할명·근거, 조건 누락의 `정보 필요`를 각각 검사한다.
- [ ] `npm test -- --run src/components/circuitContext.test.ts`를 실행해 module 미존재 실패를 확인한다.
- [ ] `MAX_NET_NODES=8`, `MAX_PASS_THROUGH_PINS=3`과 같은 경계로 연결을 변환하되 원본 DTO를 변경하지 않는 순수 함수를 구현한다. 방향 필드는 실제 입력에 있을 때만 전달하고 기본값을 만들지 않는다.
- [ ] 같은 Vitest 명령으로 adapter 테스트 통과를 확인한다.

### Task 3: SVG 개념도와 상태

**Files:**
- Create: `frontend/src/components/CircuitContextDiagram.tsx`
- Create: `frontend/src/components/CircuitContextDiagram.test.tsx`
- Modify: `frontend/src/components/CircuitSummary.tsx`
- Modify: `frontend/src/components/CircuitSummary.test.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `CircuitContext`, `selectedNodeRef`, `onSelectNode(ref)`
- Produces: 중앙 대상, 직접·2단계 노드, 무방향 net 선, 선택 노드 상세, 역할 카드, 정확한 면책 문구

- [ ] SVG 렌더링 테스트에 `D1 / 1N4001`, `J1`, `S1`, `F1`, `U1`, 역할명·근거와 면책 문구를 기대한다.
- [ ] 방향 없는 데이터에서 `marker-end`, `<marker>`가 없고, 노드 선택 시 ref·value·footprint가 보이는지 검사한다.
- [ ] loading, 연결 정보 없음, 대상 부품을 찾을 수 없음, 역할 분석 전, 사용 조건 부족, 판정 완료, 분석 오류 문구 테스트를 작성한다.
- [ ] focused Vitest를 실행해 컴포넌트 미존재 또는 기대 요소 부재로 실패하는지 확인한다.
- [ ] 고정 좌표 SVG로 중앙·안쪽·바깥쪽을 배치하고 기존 `CircuitSummary`의 대상 select 아래에 결합한다. 좁은 화면에서는 SVG와 상세 카드가 세로로 흐르도록 기존 breakpoint에 CSS를 추가한다.
- [ ] focused Vitest와 `npm run build`를 실행해 통과를 확인한다.

### Task 4: 실제 API와 후보·근거 선택 연동

**Files:**
- Modify: `frontend/src/pages/WorkbenchPage.tsx`
- Modify: `frontend/src/pages/WorkbenchPage.test.tsx`
- Modify: `frontend/src/components/JudgementTable.tsx`
- Modify: `frontend/src/components/EvidencePanel.tsx`
- Modify: `frontend/src/components/D5Panels.test.tsx`

**Interfaces:**
- Produces: `selectedCandidate: string | null`
- Consumes: `listJudgeRoles`, `runState.result`, `CircuitSummary`의 `judgement`, `interrupt.missing`
- `JudgementTable` props: `selectedPart?: string | null`, `onSelectPart?: (part: string) => void`
- `EvidencePanel` props: 기존 evidence와 선택 후보의 `checks[].citation`, `package_citation`

- [ ] Workbench 테스트에서 실제 mock API project와 role catalog 응답이 개념도에 도달하고 API 실패 때 fixture가 나타나지 않는지 검사한다.
- [ ] 후보 행 선택 시 판정 tab의 같은 행이 선택되고 근거 tab에 후보별 데이터시트 citation이 표시되는 테스트를 작성한다.
- [ ] focused Vitest를 실행해 새 props·요청 부재로 실패하는지 확인한다.
- [ ] TanStack Query로 역할 목록을 읽고 프로젝트·run 결과와 adapter를 연결한다. 프로젝트/대상 변경 시 선택 노드·후보를 폐기한다.
- [ ] 후보 행을 키보드로 선택 가능한 button 또는 radio semantics로 만들고 EvidencePanel은 공통 근거를 보존하면서 선택 후보 citation을 별도 표시한다.
- [ ] focused Vitest와 `npm run build`를 실행해 통과를 확인한다.

### Task 5: 문서·전체 검증·diff 검토

**Files:**
- Modify: `SOJAFIT.md`
- Modify: `docs/specs/SPECS.md`
- Modify: `docs/superpowers/SUPERPOWERS.md`
- Modify: `frontend/src/SRC.md`
- Modify: `docs/worklog/osc.md`

- [ ] 새 파일의 트리 한 줄과 관련 폴더 파일 목록만 갱신하고 작업 기록에 변경 파일·명령·실제 결과·미확인·다음 할 일을 적는다.
- [ ] `uv run pytest -q tests/api/test_conversations.py -k role_catalog`을 실행한다.
- [ ] `npm test -- --run`과 `npm run build`를 `frontend/`에서 실행한다.
- [ ] `uv run pytest -q tests/repo/test_repo_layout.py`를 실행한다.
- [ ] `git diff --check`, `git status --short`, `git diff --stat`, `git diff`로 비밀값·unrelated change·fixture production import·루트 SPEC/ADR 미수정을 확인한다.
- [ ] 실제 pipeline 연결, fixture 검증 범위, 아직 없는 업로드·변환·API 부분, 정확한 `SPEC.md` 반영 문구를 최종 보고에 구분해 적는다.
