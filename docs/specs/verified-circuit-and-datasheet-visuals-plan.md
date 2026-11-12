# Verified Circuit and Datasheet Visuals Implementation Plan


**Status:** 구현 완료. 명시적 승인 없이 commit·push·PR은 만들지 않았다.

**Goal:** 수집된 공개 회로와의 일치까지 검증된 15종 전체의 원본 회로도와 후보 부품의 공식 데이터시트·패키지 외형 페이지를 React 작업대에서 근거와 함께 제공한다.

**Architecture:** 데모 회로도는 런타임 생성이나 외부 hotlink 대신 검증된 정적 PNG와 provenance catalog로 고정하고, 기존 연결 개념도와 별도의 보기로 표시한다. 후보 문서 링크는 LLM 출력이나 브라우저 입력을 신뢰하지 않고 `data/manifest.jsonl`과 사전 생성한 package-outline page index에서 서버가 보강한 안전한 DTO만 사용한다. 업로드 회로에는 원본 회로도를 발명하지 않고 기존 연결 개념도만 유지한다.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, React 19, TypeScript, Vite, TanStack Query, Vitest, Testing Library, Playwright, pytest, 기존 CSS와 정적 PNG

## Global Constraints

- 구현 대상 브랜치는 `OSC`다. 기존 사용자 변경을 보존하고, 명시적 승인 없이 commit, push, PR을 만들지 않는다.
- 정확한 원본 회로도는 수집된 공개 데모 15종 모두에 제공한다. 공식 PNG·PDF가 없으면 고정 commit의 KiCad 원본을 재현 가능한 변환기로 렌더링한다.
- 업로드 `.net`에는 원본 회로도나 부품 좌표가 없으므로 이미지를 생성하거나 추정하지 않는다.
- 원본 회로도와 `CircuitContextDiagram`은 각각 `원본 회로도`와 `연결 개념도`로 표시한다. 연결 개념도를 실제 설계 원본처럼 표현하지 않는다.
- 회로 방향, 신호 흐름, 핀 재배선, 어댑터, 납땜 및 기판 수정 방법을 생성하지 않는다.
- 후보 결과에는 `동일 패키지`, `기판 변경 가능성 있음`, `확인 필요`만 표시한다. `board_change=false`를 물리적 직접 교체 보증으로 바꾸지 않는다.
- 데이터시트 URL은 `data/manifest.jsonl`에서 exact document match로만 가져온다. LLM이나 API 입력의 URL은 브라우저로 전달하지 않는다.
- 브라우저에는 `https` 공식 링크만 노출하고 `target="_blank"`와 `rel="noreferrer noopener"`를 함께 사용한다.
- 외부 PDF를 iframe/object로 삽입하거나 런타임 프록시하지 않는다. 페이지 번호를 명시한 공식 링크로 새 탭에서 연다.
- 새 그래프, PDF viewer, 이미지 zoom 라이브러리를 추가하지 않는다.
- 회로도 자산의 원본 URL, license 근거 URL, 저장소 맥락의 고정 commit, attribution, SHA-256을 catalog에 기록하고 빌드 전 검증한다. CDN 자산의 commit은 해당 CDN 바이트의 출처 증명으로 표현하지 않는다.
- 루트 `SPEC.md`와 `docs/adr/`는 수정하지 않는다. 관련 계약 변경은 `docs/specs/SPECS.md`와 폴더 문서에 기록한다.

---

## File Map

### New files

- `data/circuits/catalog.json`, `visuals.json` — 15개 데모의 ID·연결 경로와 원본·배포 이미지 SHA-256, 저장소 맥락, license 근거, attribution 정본.
- `frontend/public/circuit-schematics/*.png` — 브라우저에 제공할 검증된 정적 회로도 15개.
- `backend/projects/visuals.py` — catalog를 strict validation하고 데모 API용 안전한 metadata를 반환.
- `tests/projects/test_visuals.py` — catalog 완전성, 해시, 경로, DEMOS 일치 검증.
- `backend/rag/pipeline/package_outlines.py` — Docling JSON에서 패키지 외형 페이지 index를 결정적으로 생성하는 오프라인 도구.
- `data/package-outline-pages.json` — 1,360개 문서의 패키지 외형 페이지 번호와 검출 표제.
- `backend/rag/source_metadata.py` — manifest와 outline index를 exact document name으로 결합하는 런타임 읽기 모듈.
- `tests/rag/test_package_outlines.py` — 생성기와 1,360건 index 계약 검증.
- `frontend/src/components/CircuitSchematic.tsx` — 원본 회로도 figure와 provenance 링크를 표시.
- `frontend/src/components/CircuitSchematic.test.tsx` — 데모, 업로드, 오류, 접근성 표시 검증.

### Existing files to modify

- `backend/api/projects.py`, `tests/api/test_projects.py` — `/api/demo-circuits`에 schematic metadata 추가.
- `backend/conversations/models.py`, `backend/conversations/dto.py`, `tests/conversations/test_dto.py` — canonical `source_url`과 `outline_page`를 안전한 citation에 추가.
- `frontend/src/api/projects.ts`, `frontend/src/api/conversations.ts` — 새 DTO 타입 반영.
- `frontend/src/components/CircuitSummary.tsx`, `frontend/src/components/CircuitSummary.test.tsx` — 원본/개념 보기 전환.
- `frontend/src/components/EvidencePanel.tsx`, `frontend/src/components/D5Panels.test.tsx` — 공식 데이터시트와 패키지 외형 페이지 링크 표시.
- `frontend/src/pages/WorkbenchPage.tsx`, `frontend/src/pages/WorkbenchPage.test.tsx` — 선택 프로젝트의 demo visual metadata 전달.
- `frontend/vite.config.ts`, `frontend/src/dummy-circuits.d.ts`, `frontend/src/api/dummy.ts`, `frontend/src/api/dummy.test.ts` — 단일 catalog의 실제 15종 연결 JSON과 검증 visual catalog를 사용하는 production 계약 동일 dummy 응답.
- `frontend/src/styles.css`, `frontend/e2e/workbench.spec.ts` — 반응형 회로도와 사용자 흐름 검증.
- `data/circuits/CIRCUITS.md`, `backend/projects/PROJECTS.md`, `backend/rag/RAG.md`, `frontend/src/SRC.md`, `tests/projects/PROJECTS.md`, `tests/rag/RAG.md`, `docs/specs/SPECS.md`, `docs/worklog/osc.md`, `SOJAFIT.md` — 소유권, 트리, 검증 범위 기록.

---

### Task 1: 고정 회로도 자산과 provenance catalog

**Files:**
- Create: `data/circuits/visuals.json`
- Create: `frontend/public/circuit-schematics/mosfet_driver.png`
- Create: `frontend/public/circuit-schematics/attiny85_dev.png`
- Create: `frontend/public/circuit-schematics/franzininho_diy.png`
- Create: `frontend/public/circuit-schematics/pro_micro.png`
- Create: `backend/projects/visuals.py`
- Create: `tests/projects/test_visuals.py`
- Modify: `data/circuits/CIRCUITS.md`
- Modify: `backend/projects/PROJECTS.md`
- Modify: `tests/projects/PROJECTS.md`

**Interfaces:**
- Produces internally: `DemoVisualRecord(image_url, original_url, source_repo, source_commit, license, license_evidence_url, attribution, source_sha256, sha256)`.
- Produces publicly: `DemoSchematic(image_url, original_url, source_repo, source_commit, license, license_evidence_url, attribution)`; `sha256` is validation-only and is not returned by the API. `source_commit`은 저장소 맥락이며 CDN 파일 바이트의 provenance로 사용하지 않는다.
- Produces: `load_demo_visuals() -> dict[str, DemoVisualRecord]`.
- Consumes: `backend.projects.repository.DEMOS`와 `frontend/public/circuit-schematics/*.png`.
- Catalog key는 수집된 데모 15개 ID와 정확히 일치한다. 업로드 프로젝트에는 원본을 발명하지 않는다.

- [x] **Step 1: catalog 계약의 실패 테스트를 작성한다**

```python
def test_visual_catalog_matches_demo_catalog_and_assets():
    from backend.projects.visuals import load_demo_visuals

    visuals = load_demo_visuals()
    assert set(visuals) == {
        'breadboard_supply', 'mosfet_driver', 'attiny85_dev',
        'franzininho_diy', 'pro_micro', 'attiny85_time_switch',
    }
    for demo_id, item in visuals.items():
        assert item.image_url == f"/circuit-schematics/{demo_id}.png"
        assert item.original_url.startswith("https://")
        assert item.license_evidence_url.startswith("https://")
        assert len(item.source_commit) == 40
        assert len(item.source_sha256) == 64
        assert item.license
        assert item.attribution
```

```python
def test_visual_asset_hashes_match_catalog():
    import hashlib
    from pathlib import Path
    from backend.projects.visuals import load_demo_visuals

    root = Path(__file__).resolve().parents[2]
    for item in load_demo_visuals().values():
        asset = root / "frontend/public" / item.image_url.removeprefix("/")
        assert asset.is_file()
        assert hashlib.sha256(asset.read_bytes()).hexdigest() == item.sha256
```

Run: `uv run pytest -q tests/projects/test_visuals.py`

Expected: FAIL because the catalog loader and assets do not exist.

- [x] **Step 2: 검증된 원본에서 정적 PNG 15개를 만든다**

Use these exact sources:

| demo_id | visual source | pinned source |
|---|---|---|
| `breadboard_supply` | `https://cdn.sparkfun.com/datasheets/Kits/Breadboard%20Power%20Supply%20v10.pdf`, page 1 | repo commit `6e4b69f6b8ca4871a802177e6a615fdfc8e82f1b` |
| `mosfet_driver` | `https://cdn-learn.adafruit.com/assets/assets/000/117/028/large1024/adafruit_products_schem.png?1670851887` | repo commit `ea11049753a79330cc2651df233909c0191a5af4` |
| `attiny85_dev` | pinned repo `assets/schematic.png` | repo commit `488b99063b6bdbafa0f367ecc25901b55c4c7144` |
| `franzininho_diy` | pinned repo `Franzininho.pdf`, page 1 | `https://github.com/Franzininho/franzininho-diy-board`, repo commit `abdb4b48d867190d6b9794280be8b85b81aa1772` |
| `pro_micro` | `https://cdn.sparkfun.com/datasheets/Dev/Arduino/Boards/Pro_Micro_v13b.pdf`, page 1 | repo commit `df836f3bf2955c4f1199a852f618d2ac80866d47` |
| `attiny85_time_switch` | pinned repo `pcb/attiny85_time_switch_rev1/attiny85_time_switch_schematic.pdf`, page 1 | repo commit `3566a94ffc17471e3f0a592bacc63480a2898641` |
| `fc_rom_vomitter` | pinned repo `docs/nescart-fc-schematic.pdf`, page 1 | repo commit `f64502c301ca5e11add76efdf7dd52b343f8baaf` |
| `attiny2313a_thermostat` | pinned repo `hardware/hardware/hardware.kicad_sch`, KiCad 9.0.5 export page 1 | repo commit `4e956f152368fc8a6f68e9e2e0d273ea25249840` |
| `tiny85_fan_control` | pinned repo `schematic/info/tiny85fancontrol.png` | repo commit `66366bd10b66e4bc3e944902f9e6c93a44ddeac4` |
| `ug56_pwm_controller` | pinned repo `img/sch.png` | repo commit `91f19385e76a92e9b58c681f22e9891ba1c8aebe` |
| `car_radio_acc_delay` | pinned repo `hardware/auto-acc-timer/auto-acc-timer.pdf`, page 1 | repo commit `5d5048f196ea539ae2464c6bc766384444ea8696` |
| `overengineered_psu` | pinned repo `Hardware/OverEngineered-PSU.pdf`, page 1 | repo commit `5b8b7757e9742b4f97ddf61c434c7cf2e48b1867` |
| `tinydimmer` | pinned repo `images/tinydimmer.sch.pdf`, page 1 | repo commit `52ee6077344b044bf046e6c616cefe3675091b46` |
| `hrem` | pinned repo `hardware/hrem.sch`, KiCad 9.0.5 export page 1 | repo commit `7d6d56d1a7d75231c0d7109d90839474f59f3f1d` |
| `zr7_taillight` | pinned repo `hardware/KiCad/zr7-taillight.kicad_sch`, KiCad 9.0.5 export page 1 | repo commit `777c5d5f034361a6d143fedeb3de9a8bb81ca532` |

For PDF assets, render exactly page 1 with:

```powershell
pdftoppm -f 1 -singlefile -png -r 160 SOURCE.pdf OUTPUT_WITHOUT_EXTENSION
```

For PNG sources, copy the original bytes without resizing or recompression. Do not crop component labels, title blocks, revision, or license marks.

- [x] **Step 3: 실제 자산 해시를 기록한다**

Run:

```powershell
Get-ChildItem frontend/public/circuit-schematics/*.png |
  Get-FileHash -Algorithm SHA256 |
  Select-Object Path,Hash
```

Copy the 15 returned 64-character lowercase hashes into `data/circuits/visuals.json` as `sha256`. Also hash the exact bytes downloaded from every `original_url` into `source_sha256`; copied PNG sources may have the same two hashes, while rendered PDF or KiCad sources must retain distinct source and rendered hashes. Record these visual licenses and attributions:

- `mosfet_driver`: `CC BY-SA 3.0`, `Adafruit Industries`.
- `attiny85_dev`: `MIT`, `tomasr8/attiny85-dev-board contributors`.
- `franzininho_diy`: `CC BY-SA 4.0`, `Franzininho DIY contributors`.
- `pro_micro`: `CC BY-SA 4.0`, `SparkFun Electronics`.
- `breadboard_supply`: `CC BY-SA 4.0`, `SparkFun Electronics`.
- `attiny85_time_switch`: `MIT`, `UCSIG/attiny85_time_switch contributors`.
- `fc_rom_vomitter`: `CC BY-SA 4.0`, `Keitark contributors`.
- `attiny2313a_thermostat`: `MIT`, `Sergey Yarkov`.
- `tiny85_fan_control`: `MIT`, `Colahall, LLC`.
- `ug56_pwm_controller`: `MIT`, `UG56 contributors`.
- `car_radio_acc_delay`: `MIT`, `Alexander Warg`.
- `overengineered_psu`: `MIT`, `MAATHES-THILAK-K`.
- `tinydimmer`: `CC BY-SA 4.0`, `virtual-machinist contributors`.
- `hrem`: `MIT`, `Denis Bazhenov`.
- `zr7_taillight`: `MIT`, `Salvatore La Bua`.

The catalog must contain only `image_url`, `original_url`, `source_repo`, `source_commit`, `license`, `license_evidence_url`, `attribution`, `source_sha256`, and `sha256` per circuit. `original_url` identifies the exact downloaded bytes; `source_sha256` pins those source bytes; `sha256` pins the served PNG derivative; `license_evidence_url` points to the pinned authoritative license text. For CDN assets, `source_commit` records repository context only and must not be described as proving the CDN file's byte origin. Do not commit sentinel values or an all-zero hash.

- [x] **Step 4: strict catalog loader를 구현한다**

`backend/projects/visuals.py`에서 Pydantic `DemoVisualRecord`를 정의한다. `ConfigDict(extra="forbid", frozen=True)`를 사용하고 URL은 문자열로 유지하되 `https://` prefix, image path는 `/circuit-schematics/{demo_id}.png`, commit과 SHA는 lowercase hex 정규식으로 검증한다. `lru_cache(maxsize=1)`로 한 번만 읽고 unknown/missing demo, missing asset, hash mismatch에서는 시작 시 또는 API 호출 시 명시적 예외를 낸다. API 응답용 `DemoSchematic`은 Task 2의 공개 필드만 따로 직렬화한다.

- [x] **Step 5: focused test를 통과시킨다**

Run: `uv run pytest -q tests/projects/test_visuals.py tests/repo/test_repo_layout.py`

Expected: PASS; catalog 15건과 asset 15건이 exact match한다.

- [x] **Step 6: 명시적 승인 없음 — commit을 생략한다**

```bash
git add data/circuits/visuals.json data/circuits/CIRCUITS.md frontend/public/circuit-schematics backend/projects/visuals.py backend/projects/PROJECTS.md tests/projects/test_visuals.py tests/projects/PROJECTS.md
git commit -m "feat: 검증된 데모 회로도 자산 등록"
```

---

### Task 2: 데모 API에 안전한 회로도 metadata 추가

**Files:**
- Modify: `backend/api/projects.py`
- Modify: `tests/api/test_projects.py`
- Modify: `backend/api/API.md`
- Modify: `frontend/src/api/projects.ts`
- Modify: `frontend/src/api/dummy.ts`
- Modify: `frontend/src/api/dummy.test.ts`

**Interfaces:**
- Consumes: `load_demo_visuals() -> dict[str, DemoSchematic]`.
- Produces: `GET /api/demo-circuits -> DemoCircuit[]`.
- Produces frontend type:

```ts
export type DemoSchematic = {
  image_url: string
  original_url: string
  source_repo: string
  source_commit: string
  license: string
  license_evidence_url: string
  attribution: string
}
export type DemoCircuit = { id: string; name: string; schematic: DemoSchematic | null }
```

- [x] **Step 1: 인증·허용 필드 API 테스트를 먼저 작성한다**

```python
def test_demo_catalog_exposes_verified_schematic_metadata(client, logged_in_headers):
    from backend.projects.repository import DEMOS

    response = client.get('/api/demo-circuits', headers=logged_in_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == len(DEMOS)
    breadboard = next(item for item in body if item['id'] == 'breadboard_supply')
    mosfet = next(item for item in body if item['id'] == 'mosfet_driver')
    assert set(breadboard) == {'id', 'name', 'schematic'}
    assert set(breadboard['schematic']) == {
        'image_url', 'original_url', 'source_repo', 'source_commit', 'license', 'license_evidence_url', 'attribution'
    }
    assert breadboard['schematic']['image_url'] == '/circuit-schematics/breadboard_supply.png'
    assert mosfet['schematic']['image_url'] == '/circuit-schematics/mosfet_driver.png'
    time_switch = next(item for item in body if item['id'] == 'attiny85_time_switch')
    assert time_switch['schematic']['image_url'] == '/circuit-schematics/attiny85_time_switch.png'
```

Also assert that a request without a session returns 401 and that the response contains no local path, SHA-256, source checkout path, or filesystem metadata.

Run: `uv run pytest -q tests/api/test_projects.py -k demo_catalog`

Expected: FAIL because the current response contains only `id` and `name`.

- [x] **Step 2: response models와 endpoint를 최소 변경한다**

Add `DemoCircuitResponse(BaseModel)` in `backend/api/projects.py` and build the response by joining `DEMOS` with `load_demo_visuals()`. Do not read arbitrary client paths and do not add a second visual endpoint.

- [x] **Step 3: TypeScript와 dummy 계약을 같은 모양으로 갱신한다**

Update `DemoCircuit` in `frontend/src/api/projects.ts`. The dummy must expose all 15 repository demos from the single catalog and canonical `connections.json`; all 15 demos use the same visual catalog as production. Do not maintain a hand-written shortened circuit or use a fabricated external domain.

- [x] **Step 4: focused tests를 통과시킨다**

Run:

```bash
uv run pytest -q tests/api/test_projects.py -k demo_catalog
cd frontend
npm test -- --run src/api/dummy.test.ts src/components/CircuitSetup.test.tsx
```

Expected: PASS.

- [x] **Step 5: 명시적 승인 없음 — commit을 생략한다**

```bash
git add backend/api/projects.py backend/api/API.md tests/api/test_projects.py frontend/src/api/projects.ts frontend/src/api/dummy.ts frontend/src/api/dummy.test.ts
git commit -m "feat: 데모 회로도 메타데이터 공개"
```

---

### Task 3: 원본 회로도와 연결 개념도 분리 표시

**Files:**
- Create: `frontend/src/components/CircuitSchematic.tsx`
- Create: `frontend/src/components/CircuitSchematic.test.tsx`
- Modify: `frontend/src/components/CircuitSummary.tsx`
- Modify: `frontend/src/components/CircuitSummary.test.tsx`
- Modify: `frontend/src/pages/WorkbenchPage.tsx`
- Modify: `frontend/src/pages/WorkbenchPage.test.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: `DemoSchematic | undefined`, `project.source_kind`, `targetRef`.
- Produces: `CircuitSchematic({ schematic, circuitName, targetRef })`.
- `CircuitSummary`에 `demo?: DemoCircuit` prop을 추가한다.
- `WorkbenchPage`는 `demos.data`를 `Map<demo_id, DemoCircuit>`로 만들고 현재 `project.demo_id`의 항목만 전달한다.

- [x] **Step 1: 원본 회로도 접근성 테스트를 먼저 작성한다**

```tsx
render(<CircuitSchematic
  circuitName="SparkFun Pro Micro v13"
  targetRef="D2"
  schematic={demo.schematic}
/>)

expect(screen.getByRole('img', { name: 'SparkFun Pro Micro v13 원본 회로도' })).toHaveAttribute(
  'src', '/circuit-schematics/pro_micro.png'
)
expect(screen.getByText('선택 대상 D2')).toBeInTheDocument()
expect(screen.getByRole('link', { name: '원본 자료 열기' })).toHaveAttribute('rel', 'noreferrer noopener')
expect(screen.getByText(/CC BY-SA 4.0/)).toBeInTheDocument()
```

Add tests for missing schematic metadata and broken image state. The fallback copy must be `검증된 원본 회로도를 제공할 수 없습니다.` and must not display a generic or generated image.

Run: `cd frontend && npm test -- --run src/components/CircuitSchematic.test.tsx`

Expected: FAIL because the component does not exist.

- [x] **Step 2: 읽기 전용 figure를 구현한다**

`CircuitSchematic.tsx` must render:

- `<figure>` and `<img loading="lazy" decoding="async">`.
- circuit name, selected target badge, attribution and license.
- `원본 자료 열기` and `원본 저장소 열기` links.
- exact copy: `이 이미지는 공개 원본 회로도입니다. 선택 부품의 연결 해석은 연결 개념도에서 확인하세요.`
- `onError` after image failure, hiding the broken image and showing the verified fallback.

Do not draw target boxes on the original schematic because verified coordinates are not part of the source contract.

- [x] **Step 3: CircuitSummary에 명확한 보기 전환을 추가한다**

For demo projects with visual metadata, render two tab buttons with `role="tab"`:

- `원본 회로도` — default for a newly selected demo project.
- `연결 개념도` — existing `CircuitContextDiagram`; selected target remains centered here.

For upload projects, do not render the original tab. Render the existing concept diagram and exact copy `업로드한 넷리스트에는 원본 회로도 이미지와 부품 좌표가 포함되지 않습니다.`

Project or target changes must not retain a stale visual error. Key the schematic component by `project.id` and reset local tab state when `project.id` changes.

- [x] **Step 4: Workbench wiring test를 작성하고 구현한다**

Test the actual flow:

1. `/api/demo-circuits` returns the seven-field public schematic object.
2. `/api/projects/11` returns `source_kind='demo'`, `demo_id='pro_micro'`.
3. The circuit tab shows the Pro Micro original image.
4. Clicking `연결 개념도` shows the existing target-centered diagram.
5. Selecting an uploaded project removes the original schematic tab.

Run:

```bash
cd frontend
npm test -- --run src/components/CircuitSchematic.test.tsx src/components/CircuitSummary.test.tsx src/pages/WorkbenchPage.test.tsx
npm run build
```

Expected: PASS with no new frontend dependency.

- [x] **Step 5: 반응형 CSS를 추가한다**

Use the existing result panel width. `.circuit-schematic-scroll` gets `overflow:auto`, the image gets `display:block; width:100%; min-width:720px; height:auto`, and at the existing mobile breakpoint set `min-width:560px`. Preserve labels and title blocks; do not use `object-fit: cover`.

- [x] **Step 6: 명시적 승인 없음 — commit을 생략한다**

```bash
git add frontend/src/components/CircuitSchematic.tsx frontend/src/components/CircuitSchematic.test.tsx frontend/src/components/CircuitSummary.tsx frontend/src/components/CircuitSummary.test.tsx frontend/src/pages/WorkbenchPage.tsx frontend/src/pages/WorkbenchPage.test.tsx frontend/src/styles.css
git commit -m "feat: 원본 회로도와 연결 개념도 분리"
```

---

### Task 4: 1,360개 문서의 공식 링크와 패키지 외형 페이지 index

**Files:**
- Create: `backend/rag/pipeline/package_outlines.py`
- Create: `data/package-outline-pages.json`
- Create: `backend/rag/source_metadata.py`
- Create: `tests/rag/test_package_outlines.py`
- Modify: `backend/rag/RAG.md`
- Modify: `tests/rag/RAG.md`

**Interfaces:**
- Offline producer: `build_outline_index(docling_dir: Path, manifest_path: Path) -> dict[str, OutlineRecord]`.
- Runtime producer: `source_metadata(document: str) -> SourceMetadata | None`.
- `OutlineRecord`: `{source_url: str, outline_page: int, heading: str}`.
- Lookup key: URL-decoded official PDF basename, case-folded; no substring or fuzzy matching.

- [x] **Step 1: 생성 규칙의 실패 테스트를 작성한다**

```python
def test_outline_index_picks_first_heading_page_with_picture(tmp_path):
    doc = {
        'origin': {'filename': 'SS34.pdf'},
        'texts': [
            {'text': 'PACKAGE OUTLINE', 'prov': [{'page_no': 5}]},
            {'text': 'DIMENSIONS', 'prov': [{'page_no': 6}]},
        ],
        'pictures': [
            {'prov': [{'page_no': 5}]},
            {'prov': [{'page_no': 6}]},
        ],
    }
    # fixture and manifest are written under tmp_path
    result = build_outline_index(tmp_path / 'docling', tmp_path / 'manifest.jsonl')
    assert result['ss34.pdf']['outline_page'] == 5
    assert result['ss34.pdf']['heading'] == 'PACKAGE OUTLINE'
```

Also test:

- a heading without a picture on the same page is rejected.
- a manifest document without Docling JSON is rejected.
- a Docling document not present in manifest is rejected.
- duplicate normalized basenames are rejected.
- `http`, local path and malformed source URL are rejected.

Run: `uv run pytest -q tests/rag/test_package_outlines.py`

Expected: FAIL because the generator does not exist.

- [x] **Step 2: deterministic generator를 구현한다**

Search only these case-insensitive heading patterns:

```python
OUTLINE = re.compile(
    r"\b(?:PACKAGE\s+OUTLINE|OUTLINE\s+DIMENSIONS?|PACKAGE\s+DIMENSIONS?|DIMENSIONS?)\b",
    re.I,
)
```

For every document, collect heading page numbers and picture page numbers from Docling `prov[].page_no`, take the smallest intersection, and store the matched heading text. Do not use OCR text outside the parsed JSON and do not guess a last page.

- [x] **Step 3: full index를 생성하고 완전성을 검증한다**

Run from the repository root:

```powershell
uv run python -m backend.rag.pipeline.package_outlines `
  "C:\Users\user\Documents\ChatGPT\3차 프로젝트 2\SojaFit\corpus\tsc\parsed-gpu-all\docling" `
  data/manifest.jsonl `
  data/package-outline-pages.json
```

The command must print and the test must assert:

```text
manifest=1360 docling=1360 indexed=1360 exceptions=0
```

The output file is sorted by normalized PDF basename and uses UTF-8 JSON with no absolute local paths.

- [x] **Step 4: runtime exact lookup을 구현한다**

`backend/rag/source_metadata.py` loads `data/manifest.jsonl` and `data/package-outline-pages.json` once with `lru_cache(maxsize=1)`. It strips a supplied document to a basename, URL-decodes it, case-folds it, and returns metadata only on exact key match. It returns `None` for unknown documents and never accepts a caller-supplied URL.

- [x] **Step 5: full contract tests를 통과시킨다**

```python
def test_checked_in_index_covers_the_manifest():
    manifest = read_manifest(Path('data/manifest.jsonl'))
    index = read_outline_index(Path('data/package-outline-pages.json'))
    assert len(manifest) == 1360
    assert len(index) == 1360
    assert set(normalized_names(manifest)) == set(index)
    assert all(record['source_url'].startswith('https://') for record in index.values())
    assert all(record['outline_page'] >= 1 for record in index.values())
```

Run: `uv run pytest -q tests/rag/test_package_outlines.py tests/rag/test_rag_storage.py`

Expected: PASS.

- [x] **Step 6: 명시적 승인 없음 — commit을 생략한다**

```bash
git add backend/rag/pipeline/package_outlines.py backend/rag/source_metadata.py data/package-outline-pages.json tests/rag/test_package_outlines.py backend/rag/RAG.md tests/rag/RAG.md
git commit -m "feat: 공식 데이터시트 외형 페이지 색인"
```

---

### Task 5: 안전한 citation DTO에 공식 출처 추가

**Files:**
- Modify: `backend/conversations/models.py`
- Modify: `backend/conversations/dto.py`
- Modify: `tests/conversations/test_dto.py`
- Modify: `frontend/src/api/conversations.ts`

**Interfaces:**
- Consumes: `source_metadata(document: str)`.
- Keeps persisted `SafeCitation`, `SafeEvidence`, `SafeResult`, `public_state` and DB JSON unchanged.
- Produces `source_url` and `outline_page` only in the browser-facing `BrowserResult` judgement/evidence dictionaries and frontend `CitationDto`/`EvidenceDto`.
- Canonical source metadata overrides and discards any same-named values from graph, model output, or stored safe result.

- [x] **Step 1: URL injection 방지 테스트를 먼저 작성한다**

```python
def test_citation_uses_canonical_manifest_url_not_model_url():
    from backend.conversations.dto import result_dto

    state = {'judgement': {'kind': 'judge', 'results': [{
        'part': '1N4148',
        'verdict': 'ROLE_SUFFICIENT',
        'checks': [{'code': 'VRRM', 'citation': {
            'document': '1N4148 SERIES_K2301.pdf',
            'page': 2,
            'source_url': 'javascript:alert(1)',
            'outline_page': 999,
        }}],
    }]}}
    body = result_dto(state, request_id='req').model_dump()
    citation = body['judgement']['results'][0]['checks'][0]['citation']
    assert citation['source_url'] == 'https://services.taiwansemi.com/storage/resources/datasheet/1N4148 SERIES_K2301.pdf'
    assert citation['outline_page'] == 4
    assert 'javascript:' not in str(body)
```

이 문서의 Docling 원본에서 `PACKAGE OUTLINE DIMENSIONS`가 4페이지임을 확인했으므로 assertion은 4로 고정한다. Add an unknown-document test asserting `source_url == ''` and `outline_page is None`.

Run: `uv run pytest -q tests/conversations/test_dto.py`

Expected: FAIL because safe DTOs do not contain canonical source metadata.

- [x] **Step 2: one enrichment helper를 구현한다**

Keep `_safe_citation(value) -> dict` restricted to persisted safe fields, then add a separate browser enrichment helper in `backend/conversations/dto.py`:

1. `_pick` only `document`, `page`, `table`, `row`, `chunk_index`, `chunk_id`.
2. Validate and serialize persisted judgement/evidence through the unchanged `SafeJudgement`/`SafeEvidence` models.
3. Only inside `result_dto`, call `source_metadata(clean['document'])` and add canonical `source_url` and `outline_page` to the browser dictionary.
4. Enrich `package_citation`, every `checks[].citation`, and browser evidence without passing the new keys back through `SafeResult`.
5. Assert `public_state` and `SafeResult.model_dump()` contain neither field so the existing DB JSON constraint remains valid.

Do not add URL fields to LLM prompts, graph state schemas, approved cases, quotes, or DB tables.

- [x] **Step 3: safe models와 frontend types를 맞춘다**

Do not add these fields to Python persistence models or DB tables. Add only the optional frontend public fields:

```ts
export type CitationDto = {
  document: string
  page: number | string | null
  table: string
  row: string
  chunk_index?: number | null
  chunk_id?: string | number | null
  source_url?: string
  outline_page?: number | null
}
```

Apply the same `source_url` and `outline_page` fields to `EvidenceDto`.

- [x] **Step 4: focused tests를 통과시킨다**

Run:

```bash
uv run pytest -q tests/conversations/test_dto.py tests/api/test_conversations.py
cd frontend
npm test -- --run src/components/D5Panels.test.tsx
```

Expected: backend PASS; frontend remains compatible before UI link rendering.

- [x] **Step 5: 명시적 승인 없음 — commit을 생략한다**

```bash
git add backend/conversations/models.py backend/conversations/dto.py tests/conversations/test_dto.py frontend/src/api/conversations.ts
git commit -m "feat: 근거 DTO에 공식 문서 출처 추가"
```

---

### Task 6: 근거 패널에 공식 데이터시트와 패키지 외형 페이지 표시

**Files:**
- Modify: `frontend/src/components/EvidencePanel.tsx`
- Modify: `frontend/src/components/D5Panels.test.tsx`
- Modify: `frontend/src/pages/WorkbenchPage.test.tsx`
- Modify: `frontend/src/api/dummy.ts`
- Modify: `frontend/src/api/dummy.test.ts`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- Consumes: selected candidate의 `checks[].citation`과 `package_citation`.
- Produces: canonical datasheet link, cited page, package-outline page, explicit replacement-method boundary.
- Does not fetch external content or render a remote PDF inline.

- [x] **Step 1: 후보 근거 사용자 흐름 테스트를 작성한다**

```tsx
render(<EvidencePanel evidence={[]} candidate={{
  part: 'SS34L',
  verdict: 'ROLE_SUFFICIENT',
  board_change: true,
  checks: [{
    code: 'VRRM',
    citation: {
      document: 'SS34L SERIES_C2103.pdf', page: 1, table: 'ABSOLUTE MAXIMUM RATINGS', row: 'VRRM',
      source_url: 'https://services.taiwansemi.com/storage/resources/datasheet/SS34L SERIES_C2103.pdf',
      outline_page: 4,
    },
  }],
}} />)

expect(screen.getByRole('link', { name: 'SS34L 공식 데이터시트 열기' })).toHaveAttribute(
  'href', expect.stringContaining('#page=1')
)
expect(screen.getByRole('link', { name: '패키지 외형 4쪽 열기' })).toHaveAttribute(
  'href', expect.stringContaining('#page=4')
)
expect(screen.getByText('기판 변경 가능성 있음')).toBeInTheDocument()
expect(screen.getByText(/납땜·재배선 방법을 뜻하지 않습니다/)).toBeInTheDocument()
```

Also test:

- missing `source_url` renders document/page text but no disabled or fake link.
- `outline_page` missing hides only the package-outline link.
- `board_change=false` renders `동일 패키지 가능성` and `직접 교체 보증이 아닙니다.`.
- `board_change=null` renders `패키지 변경 여부 확인 필요`.
- duplicate citations produce one official document link.

Run: `cd frontend && npm test -- --run src/components/D5Panels.test.tsx`

Expected: FAIL because the current panel has no links or method-boundary copy.

- [x] **Step 2: 링크 URL helper를 구현한다**

Inside `EvidencePanel.tsx`, use a local helper:

```ts
function pdfPage(url: string, page?: number | string | null) {
  if (!url.startsWith('https://')) return ''
  return typeof page === 'number' && page > 0 ? `${url}#page=${page}` : url
}
```

Do not use `dangerouslySetInnerHTML`. Render links only when `pdfPage` returns a non-empty value.

- [x] **Step 3: 후보 상태 문구를 정확히 추가한다**

Use only these labels:

- `board_change === false`: `동일 패키지 가능성` / `데이터시트 패키지 기준이며 직접 교체 보증이 아닙니다.`
- `board_change === true`: `기판 변경 가능성 있음` / `패키지가 달라질 수 있다는 뜻이며 납땜·재배선 방법을 뜻하지 않습니다.`
- `board_change == null`: `패키지 변경 여부 확인 필요` / `패키지 또는 기존 footprint 정보가 부족합니다.`

Never display `교체 방법`, `바로 교체`, `핀 호환 보장`, or `무수정 교체`.

- [x] **Step 4: dummy와 Workbench 통합 테스트를 갱신한다**

The dummy SS34L candidate must use its exact TSC manifest document `SS34L SERIES_C2103.pdf`, canonical URL, and actual checked-in `outline_page=4`. In `WorkbenchPage.test.tsx`, select a candidate in the judgement tab, open the evidence tab, and assert that the selected candidate's official links—not another candidate's links—are rendered.

- [x] **Step 5: focused frontend 검증을 실행한다**

Run:

```bash
cd frontend
npm test -- --run src/components/D5Panels.test.tsx src/pages/WorkbenchPage.test.tsx src/api/dummy.test.ts
npm run build
```

Expected: PASS.

- [x] **Step 6: 명시적 승인 없음 — commit을 생략한다**

```bash
git add frontend/src/components/EvidencePanel.tsx frontend/src/components/D5Panels.test.tsx frontend/src/pages/WorkbenchPage.test.tsx frontend/src/api/dummy.ts frontend/src/api/dummy.test.ts frontend/src/styles.css
git commit -m "feat: 공식 데이터시트와 패키지 근거 표시"
```

---

### Task 7: 브라우저 흐름, 문서, 전체 회귀 검증

**Files:**
- Modify: `frontend/e2e/workbench.spec.ts`
- Modify: `frontend/src/SRC.md`
- Modify: `SOJAFIT.md`
- Modify: `docs/specs/SPECS.md`
- Modify: `docs/worklog/osc.md`

**Interfaces:**
- Consumes: Tasks 1–6의 최종 API와 UI.
- Produces: demo original → concept target → candidate judgement → official evidence의 검증된 사용자 흐름.

- [x] **Step 1: Playwright 흐름을 추가한다**

In dummy mode:

1. Login and open `pro_micro`.
2. Open the circuit result panel and assert `원본 회로도` is selected.
3. Assert the SparkFun Pro Micro schematic image and attribution are visible.
4. Choose `연결 개념도` and assert the selected Pro Micro target is central.
5. Run the candidate flow, select SS34L, open `근거`.
6. Assert an official `https://services.taiwansemi.com/` link and package-outline page link exist.
7. Assert the panel contains the non-guarantee copy and does not contain `바로 교체`.

Run: `cd frontend && npm run test:e2e -- --grep "verified circuit and datasheet flow"`

Expected: PASS.

- [x] **Step 2: 정적 자산과 API 보안 회귀를 실행한다**

Run:

```bash
uv run pytest -q tests/projects/test_visuals.py tests/api/test_projects.py tests/conversations/test_dto.py tests/rag/test_package_outlines.py tests/api/test_frontend.py
```

Expected: PASS. `/api/*` 404 remains JSON, asset paths do not expose the filesystem, and malicious model URLs never reach DTOs.

- [x] **Step 3: 전체 frontend 검증을 실행한다**

Run:

```bash
cd frontend
npm test -- --run
npm run build
```

Expected: PASS.

- [x] **Step 4: 저장소 경계와 문서를 갱신한다**

Document these exact boundaries:

- exact original schematics exist for all six registered demos.
- uploaded netlists receive the connection concept only.
- official datasheet and package-outline page links are canonical evidence.
- no physical installation, rewiring, adapter, or soldering procedure is provided.
- circuit image provenance and asset hashes live in `data/circuits/visuals.json`.
- package page provenance lives in `data/package-outline-pages.json` and is generated offline.

Run: `uv run pytest -q tests/repo/test_repo_layout.py`

Expected: PASS.

- [x] **Step 5: 최종 diff를 검토한다**

Run:

```bash
git diff --check
git status --short
git diff --stat
git diff
```

Verify:

- no root `SPEC.md` or ADR modification.
- no unrelated UI refactor.
- no local absolute path in tracked JSON or source.
- no `javascript:`, `file:`, or caller-supplied URL reaches the browser.
- exactly six circuit PNG assets exist.
- the outline index has exactly 1,360 records.
- no wording promises physical drop-in compatibility.

- [x] **Step 6: 명시적 승인 없음 — final commit을 생략한다**

```bash
git add frontend/e2e/workbench.spec.ts frontend/src/SRC.md SOJAFIT.md docs/specs/SPECS.md docs/worklog/osc.md
git commit -m "docs: 검증된 회로와 출처 흐름 기록"
```

---

## Completion Criteria

- 등록된 데모 15종 모두에서 원본 회로도, attribution, license, 원본 링크가 표시된다.
- 업로드 프로젝트에는 원본 회로도가 표시되지 않고 이유가 설명된다.
- 원본 회로도와 연결 개념도의 성격이 UI에서 분리된다.
- 선택 후보의 공식 데이터시트와 패키지 외형 페이지를 새 탭에서 열 수 있다.
- 외부 URL은 manifest의 exact match에서만 나온다.
- 물리적 교체·배선·납땜 방법을 보장하거나 생성하지 않는다.
- backend focused tests, frontend unit tests, build, focused Playwright, repo layout, `git diff --check`가 통과한다.
- 추적되는 runtime JSON, 제품 소스, 설정 어디에도 로컬 절대 경로, 원본 PDF 본문, 비밀값이 추가되지 않는다. 계획서의 실행 명령에 기록한 로컬 corpus 입력 경로만 예외다.
