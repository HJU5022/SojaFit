# 완성 회로도 외부 전달 Implementation Plan


**Goal:** 사용자가 부품명이나 회로 용도를 입력하면, 백엔드가 공개 GitHub 프로젝트에서 라이선스와 고정 commit이 검증된 완성 회로도 전체 시트를 찾아 PNG로 전달한다.

**Architecture:** 기존 Exa 검색 경계는 GitHub 저장소 후보만 찾도록 확장하고, 새 `backend/projects/external_schematic.py`가 GitHub metadata·commit·tree 검증, 전체 회로도 판정, 안전한 다운로드·변환, 서명 token, 15분 bounded memory cache와 요청 병합을 담당한다. 기존 `backend/api/external_circuits.py`에 인증된 manifest·PNG endpoint를 추가하며 LLM, 부품 유통 API, DB와 프런트엔드는 사용하지 않는다.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx, Pillow, CairoSVG, pypdfium2, KiCad CLI, pytest, Docker.

## Global Constraints

- 반환 대상은 프로젝트 전체 부품과 배선이 보이는 완성 schematic뿐이다. 데이터시트 응용 회로, 블록도, PCB·layout·3D render·제품 사진은 반환하지 않는다.
- 후보는 `github.com/<owner>/<repo>` 저장소 루트, 허용 SPDX 라이선스, 40자리 고정 commit, `.kicad_sch` 또는 legacy `.sch`, 해당 EDA 원본과 연결된 전체 PNG·SVG·PDF 또는 변환 가능한 원본을 모두 갖춰야 한다.
- 라이선스 허용 목록은 `MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`, `ISC`, `CC-BY-3.0`, `CC-BY-4.0`, `CC-BY-SA-3.0`, `CC-BY-SA-4.0`, `CERN-OHL-P-2.0`, `CERN-OHL-W-2.0`, `CERN-OHL-S-2.0`, `GPL-2.0-only`, `GPL-2.0-or-later`, `GPL-3.0-only`, `GPL-3.0-or-later`만 허용한다. `NOASSERTION`과 사용자 정의 라이선스는 거절한다.
- Exa는 검색당 1회, GitHub 결과는 최대 5개, 저장소 검사는 순서대로 최대 3개이며 첫 유효 저장소에서 멈춘다.
- 외부 응답 상한은 Exa 256 KiB, GitHub metadata 256 KiB, commit 256 KiB, recursive tree 2 MiB·5,000항목, PNG·SVG 10 MiB, PDF 20 MiB·20쪽, archive 25 MiB 압축·100 MiB 해제, 출력 40메가픽셀/시트다.
- 허용 외부 host는 `api.exa.ai`, `api.github.com`, `raw.githubusercontent.com`, `github.com`, `codeload.github.com`으로 고정하고 HTTPS·공개 IP·표준 port·사용자정보 없음 조건을 모든 redirect hop에 다시 적용한다.
- 변환 우선순위는 짝이 맞는 전체 PNG → 안전한 SVG → 전체 PDF 모든 페이지 → KiCad 원본 전체 시트다. 다중 시트를 확인할 수 없는 단일 미리보기 이미지는 사용하지 않고 KiCad 변환으로 내린다.
- 검색·변환 cache는 프로세스 내부 TTL 900초, 검색 128항목, 이미지 64 source·총 128 MiB로 제한한다. HTTP 응답은 항상 `Cache-Control: private, no-store`이며 cache는 DB·파일·대화 상태에 영구 저장하지 않는다.
- signed token은 기존 운영 필수값 `AUTH_SECRET`으로 HMAC-SHA256 서명하고 저장소·commit·source·asset·시트 수·만료 시각을 담는다. token 원문과 외부 응답 본문은 로그에 기록하지 않는다.
- 기존 `/api/external-circuits/search`와 `/answer`, 15종 demo catalog, 업로드 schematic API는 유지한다. 기존 답변 endpoint를 호출하거나 삭제하지 않는다.
- 구현 범위는 백엔드와 재현 가능한 검증 도구뿐이다. `frontend/` 파일, 프런트 테스트와 build는 이 계획에서 변경·실행하지 않는다.
- 현재 dirty worktree의 다른 변경을 보존한다. task별 commit은 사용자가 구현 단계에서 별도로 명시 승인한 경우에만 수행하며 push·PR은 이 계획의 범위가 아니다.

---

## File Structure

- `backend/projects/external_circuit_search.py` — 기존 검색을 유지하면서 GitHub 저장소 루트 후보와 공통 HTTPS/public-host 검사를 제공한다.
- `backend/projects/external_schematic.py` — GitHub 검증, 후보 선택, 다운로드, 렌더링, cache, single-flight와 signed token의 단일 service 경계다.
- `backend/projects/schematic.py` — 업로드 경로를 유지하고 shell 없는 KiCad PDF export runner만 공용으로 추가한다.
- `backend/api/external_circuits.py` — manifest와 PNG HTTP 계약, 인증, 입력·오류·header 경계다.
- `backend/main.py` — route는 추가하지 않고 새 schematic 두 경로의 `private, no-store`를 공통 오류·미들웨어가 덮어쓰지 않게 한다.
- `tests/projects/test_external_circuit_search.py` — Exa GitHub 검색과 URL 경계 시험이다.
- `tests/projects/test_external_schematic.py` — GitHub 검증, 렌더링, 보안 상한, token, cache·동시성 시험이다.
- `tests/projects/test_schematic.py` — 공용 KiCad PDF runner의 subprocess·환경 격리 시험이다.
- `tests/api/test_external_circuits.py` — manifest·binary endpoint와 기존 endpoint 회귀 시험이다.
- `tests/api/test_openapi.py` — 새 두 route와 `image/png` schema를 고정한다.
- `scripts/smoke/verify_external_schematics.py` — 실제 Exa→GitHub→PNG 두 검색과 KiCad fallback을 메모리에서 검증하는 수동 smoke다.
- `pyproject.toml`, `uv.lock`, `.env.example`, 폴더 설명 문서와 `SOJAFIT.md` — 런타임 의존성·설정·호출 위치를 기록한다.

---

### Task 1: GitHub 저장소 전용 Exa 검색과 URL 경계

**Files:**
- Modify: `backend/projects/external_circuit_search.py`
- Modify: `tests/projects/test_external_circuit_search.py`
- Modify: `backend/projects/PROJECTS.md`
- Modify: `tests/projects/PROJECTS.md`

**Interfaces:**
- Consumes: 기존 `EXA_WEB_SEARCH_ENABLED`, `EXA_API_KEY`, `DEMO_MODE`, 주입 가능한 `httpx.Client`.
- Produces: `GitHubRepositoryRef(owner: str, repo: str, repository_url: str)`.
- Produces: `safe_public_https_url(value: object, *, allowed_hosts: frozenset[str]) -> str | None`.
- Produces: `search_github_repositories(query: str, limit: int = 5, *, client: httpx.Client | None = None) -> tuple[GitHubRepositoryRef, ...]`.
- Preserves: `search_external_circuits(...)`의 현재 공식 문서·공개 프로젝트 검색 계약.

`tests/projects/test_external_circuit_search.py` 안에만 `exa_client(results, status=200) -> tuple[httpx.Client, list[httpx.Request]]` helper를 두고 `httpx.MockTransport`로 request를 기록한다. 별도 global fixture 파일은 만들지 않는다.

- [ ] **Step 1: 저장소 루트와 Exa 상한 실패 시험 작성**

`tests/projects/test_external_circuit_search.py`에 저장소 root만 허용하고 `blob`, `tree`, `issues`, reserved path, 자격증명 URL, HTTP, 비표준 port를 거절하는 시험을 추가한다. 같은 저장소 중복 제거, 결과 5개 상한, 한 번의 Exa POST, 256 KiB 초과 본문 거절도 고정한다.

```python
def exa_client(results: list[dict], *, status: int = 200) -> tuple[httpx.Client, list[httpx.Request]]:
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, json={"results": results}, request=request)

    return httpx.Client(transport=httpx.MockTransport(handle)), requests


@pytest.mark.parametrize("url", [
    "https://github.com/o/r/blob/main/board.kicad_sch",
    "https://github.com/o/r/issues/1",
    "https://github.com/features/actions",
    "http://github.com/o/r",
    "https://user:pass@github.com/o/r",
    "https://github.com:8443/o/r",
])
def test_github_repository_search_rejects_non_root_or_unsafe_urls(url, provider_env):
    client, _ = exa_client([{"title": "x", "url": url}])
    with client:
        assert search_github_repositories("ATtiny85", client=client) == ()


def test_github_repository_search_uses_one_bounded_github_only_request(provider_env):
    client, requests = exa_client([
        {"title": "A", "url": "https://github.com/tomasr8/attiny85-dev-board"},
        {"title": "duplicate", "url": "https://github.com/tomasr8/attiny85-dev-board"},
    ])
    with client:
        assert search_github_repositories("ATtiny85", client=client) == (
            GitHubRepositoryRef("tomasr8", "attiny85-dev-board", "https://github.com/tomasr8/attiny85-dev-board"),
        )
    assert len(requests) == 1
    body = json.loads(requests[0].content)
    assert body["includeDomains"] == ["github.com"]
    assert body["numResults"] == 5
```

- [ ] **Step 2: Task 1 RED 확인**

Run: `uv run --no-sync pytest -q tests/projects/test_external_circuit_search.py -k "github_repository or bounded"`

Expected: `GitHubRepositoryRef`와 `search_github_repositories`가 없어 FAIL.

- [ ] **Step 3: 공통 URL 검사와 저장소 parser 구현**

기존 `_safe_url`의 동작을 깨지 않도록 공통 검사를 공개 함수로 추출하고, schematic 경로는 HTTPS와 exact allowlist를 추가로 강제한다. 기존 환경 검사도 `_require_external_search_configuration()`으로 한 번만 추출해 두 검색 함수가 같은 disabled/configuration 오류를 사용하게 한다. GitHub URL은 path segment가 정확히 두 개일 때만 canonical root로 만든다.

```python
@dataclass(frozen=True)
class GitHubRepositoryRef:
    owner: str
    repo: str
    repository_url: str


def safe_public_https_url(value: object, *, allowed_hosts: frozenset[str]) -> str | None:
    candidate = _safe_url(value)
    if candidate is None:
        return None
    parsed = urlsplit(candidate)
    if parsed.scheme != "https" or parsed.hostname not in allowed_hosts or parsed.port not in (None, 443):
        return None
    return candidate


def _github_repository(value: object) -> GitHubRepositoryRef | None:
    url = safe_public_https_url(value, allowed_hosts=frozenset({"github.com"}))
    if url is None:
        return None
    parts = [unquote(part) for part in urlsplit(url).path.split("/") if part]
    if len(parts) != 2 or parts[0].casefold() in PROJECT_RESERVED_PATHS["github.com"]:
        return None
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts):
        return None
    owner, repo = parts[0], parts[1].removesuffix(".git")
    return GitHubRepositoryRef(owner, repo, f"https://github.com/{owner}/{repo}")


def _require_external_search_configuration() -> str:
    if os.getenv("EXA_WEB_SEARCH_ENABLED") != "1" or os.getenv("DEMO_MODE") != "0":
        raise ExternalCircuitSearchDisabled("외부 회로 검색이 비활성화되어 있습니다.")
    api_key = os.getenv("EXA_API_KEY", "").strip()
    if not api_key:
        raise ExternalCircuitSearchConfigurationError("외부 회로 검색 인증 설정이 필요합니다.")
    return api_key
```

- [ ] **Step 4: GitHub-only Exa 함수와 bounded JSON reader 구현**

응답은 streaming으로 256 KiB까지만 누적한 뒤 JSON을 해석한다. 공급자 오류에는 URL·본문·key를 넣지 않고 기존 safe exception만 낸다.

```python
MAX_EXA_RESPONSE_BYTES = 256 * 1024


def search_github_repositories(query: str, limit: int = 5, *, client: httpx.Client | None = None) -> tuple[GitHubRepositoryRef, ...]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("검색어를 입력해야 합니다.")
    if type(limit) is not int or not 1 <= limit <= 5:
        raise ValueError("검색 결과 수는 1~5이어야 합니다.")
    _require_external_search_configuration()
    payload = _post_bounded_json(
        client,
        "https://api.exa.ai/search",
        headers={"x-api-key": os.environ["EXA_API_KEY"]},
        body={
            "query": f"{query.strip()} complete schematic KiCad open hardware GitHub",
            "numResults": limit,
            "includeDomains": ["github.com"],
            "contents": {"text": {"maxCharacters": 1000}},
        },
        max_bytes=MAX_EXA_RESPONSE_BYTES,
    )
    found, seen = [], set()
    for item in payload.get("results", []):
        repository = _github_repository(item.get("url") if isinstance(item, dict) else None)
        if repository is not None and repository.repository_url not in seen:
            seen.add(repository.repository_url)
            found.append(repository)
    return tuple(found[:limit])
```

- [ ] **Step 5: Task 1 GREEN과 기존 검색 회귀 확인**

Run: `uv run --no-sync pytest -q tests/projects/test_external_circuit_search.py`

Expected: 기존 `/search`용 검색 시험과 새 GitHub 저장소 검색 시험 모두 PASS.

---

### Task 2: GitHub commit·라이선스·완성 회로도 source 검증

**Files:**
- Create: `backend/projects/external_schematic.py`
- Create: `tests/projects/test_external_schematic.py`
- Modify: `backend/projects/PROJECTS.md`
- Modify: `tests/projects/PROJECTS.md`

**Interfaces:**
- Consumes: `GitHubRepositoryRef`, `safe_public_https_url`, 주입 가능한 `httpx.Client`, 선택적 `GITHUB_TOKEN`.
- Produces: `VerifiedSchematicSource(repository, commit, license, attribution, repository_url, source_url, source_file, asset_kind, asset_paths, root_schematic)`.
- Produces: `inspect_github_repository(repository: GitHubRepositoryRef, *, client: httpx.Client | None = None) -> VerifiedSchematicSource | None`.
- Raises: `ExternalSchematicRateLimited(retry_after: int)`, `ExternalSchematicUpstreamError`, `ExternalSchematicConfigurationError`; source 판정 실패는 내부 `ExternalSchematicInvalidSource` 또는 `None`으로 처리한다.

`tests/projects/test_external_schematic.py`에 `REPOSITORY = GitHubRepositoryRef("owner", "repo", "https://github.com/owner/repo")`를 고정한다. 같은 파일의 `GitHubStub`은 exact URL별 `(status, headers, JSON 또는 bytes)` 응답 map과 `requests` 목록을 가지고, `client` fixture는 `httpx.Client(transport=httpx.MockTransport(stub.handle))`를 반환한다. `metadata()`, `valid_repository(paths=...)` helper는 metadata·commit·tree endpoint 세 응답을 그 map에 등록한다.

- [ ] **Step 1: GitHub 검증 규칙 실패 시험 작성**

metadata → commit → recursive tree 순서를 고정하고 아래 후보가 `None`이 되는 시험을 작성한다.

```python
@pytest.mark.parametrize("license_spdx", [None, "NOASSERTION", "Proprietary"])
def test_rejects_missing_or_unapproved_license(github, license_spdx):
    github.metadata(license_spdx=license_spdx)
    assert inspect_github_repository(REPOSITORY, client=github) is None


@pytest.mark.parametrize("paths", [
    ["README.md", "docs/schematic.png"],
    ["board.kicad_sch", "docs/block-diagram.png"],
    ["board.kicad_sch", "renders/board-3d.png"],
    ["board.kicad_sch", "pcb/board-layout.pdf"],
])
def test_rejects_image_without_eda_pair_or_full_schematic(github, paths):
    github.valid_repository(paths=paths)
    assert inspect_github_repository(REPOSITORY, client=github) is None
```

허용 라이선스 전체 parameterize, SHA가 40자리 hex가 아닌 응답, tree 2 MiB·5,000항목 초과, symlink/submodule tree entry, branch 이름을 raw URL에 사용한 경우도 거절한다.

- [ ] **Step 2: source pairing과 우선순위 실패 시험 작성**

동일 directory, 동일 stem, README의 명시적 상대 링크를 각각 통과시키고 PNG → SVG → PDF → KiCad 순서를 확인한다. `datasheet`, `application-note`, `block-diagram`, `pcb`, `layout`, `render`, `3d` path는 후보에서 제외한다.

```python
def test_selects_paired_png_and_pins_exact_commit(github):
    github.valid_repository(paths=["hardware/board.kicad_sch", "hardware/schematic.png"])
    source = inspect_github_repository(REPOSITORY, client=github)
    assert source == VerifiedSchematicSource(
        repository="owner/repo",
        commit="a" * 40,
        license="MIT",
        attribution="owner/repo contributors",
        repository_url="https://github.com/owner/repo",
        source_url=f"https://github.com/owner/repo/tree/{'a' * 40}",
        source_file="hardware/board.kicad_sch",
        asset_kind="png",
        asset_paths=("hardware/schematic.png",),
        root_schematic="hardware/board.kicad_sch",
    )


def test_single_preview_falls_back_to_kicad_when_tree_has_multiple_sheets(github):
    github.valid_repository(paths=[
        "hardware/board.kicad_sch", "hardware/power.kicad_sch", "hardware/schematic.png",
    ])
    source = inspect_github_repository(REPOSITORY, client=github)
    assert source.asset_kind == "kicad"
    assert source.asset_paths == ()
```

- [ ] **Step 3: Task 2 RED 확인**

Run: `uv run --no-sync pytest -q tests/projects/test_external_schematic.py -k "license or pair or source or tree"`

Expected: 새 module이 없어 collection FAIL.

- [ ] **Step 4: GitHub client와 exact commit tree 검사 구현**

GitHub API 요청마다 `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`를 설정하고 `GITHUB_TOKEN`이 있을 때만 `Authorization: Bearer ...`를 추가한다. metadata의 `default_branch`로 commit endpoint를 조회한 뒤 그 응답의 commit·tree SHA만 사용한다.

```python
ALLOWED_LICENSES = frozenset({
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
    "CC-BY-3.0", "CC-BY-4.0", "CC-BY-SA-3.0", "CC-BY-SA-4.0",
    "CERN-OHL-P-2.0", "CERN-OHL-W-2.0", "CERN-OHL-S-2.0",
    "GPL-2.0-only", "GPL-2.0-or-later", "GPL-3.0-only", "GPL-3.0-or-later",
})


@dataclass(frozen=True)
class VerifiedSchematicSource:
    repository: str
    commit: str
    license: str
    attribution: str
    repository_url: str
    source_url: str
    source_file: str
    asset_kind: Literal["png", "svg", "pdf", "kicad"]
    asset_paths: tuple[str, ...]
    root_schematic: str


@dataclass(frozen=True)
class AssetCandidate:
    kind: Literal["png", "svg", "pdf", "kicad"]
    path: str
    root_schematic: str


class ExternalSchematicError(RuntimeError):
    pass


class ExternalSchematicConfigurationError(ExternalSchematicError):
    pass


class ExternalSchematicUpstreamError(ExternalSchematicError):
    pass


class ExternalSchematicInvalidSource(ExternalSchematicError):
    pass


class ExternalSchematicRateLimited(ExternalSchematicError):
    def __init__(self, retry_after: int):
        super().__init__("GitHub rate limit")
        self.retry_after = retry_after
```

`_github_json()`은 선언 `Content-Length`와 streaming 누적량을 모두 검사한다. 403/429와 `X-RateLimit-Remaining: 0`은 `Retry-After` 또는 reset 시각으로 1~3600초를 계산해 `ExternalSchematicRateLimited`로 바꾸고, 나머지 transport·schema 오류는 외부 본문 없이 `ExternalSchematicUpstreamError`로 바꾼다. README pairing에 필요한 고정 commit raw text도 256 KiB까지만 읽는다.

- [ ] **Step 5: 결정론적 source 선택 구현**

tree의 blob path만 정규화하고 절대 경로, `..`, NUL, backslash와 casefold 중복을 거절한다. EDA 원본을 기준으로 같은 directory·stem을 먼저 매칭하고 README는 고정 commit raw text에서 명시적으로 연결된 relative path만 인정한다. `(asset 우선순위, path segment 수, casefold path)` 순으로 정렬하며 동점도 같은 결과를 낸다.

```python
def _candidate_key(candidate: AssetCandidate) -> tuple[int, int, str]:
    priority = {"png": 0, "svg": 1, "pdf": 2, "kicad": 3}[candidate.kind]
    return priority, len(PurePosixPath(candidate.path).parts), candidate.path.casefold()


def inspect_github_repository(repository: GitHubRepositoryRef, *, client=None) -> VerifiedSchematicSource | None:
    metadata = _github_json(client, f"https://api.github.com/repos/{repository.owner}/{repository.repo}", 256 * 1024)
    license_spdx = _license_spdx(metadata)
    if license_spdx not in ALLOWED_LICENSES:
        return None
    commit = _load_head_commit(client, repository, metadata["default_branch"])
    tree = _load_recursive_tree(client, repository, commit.tree_sha)
    return _select_verified_source(repository, license_spdx, commit.sha, tree, client=client)
```

- [ ] **Step 6: Task 2 GREEN 확인**

Run: `uv run --no-sync pytest -q tests/projects/test_external_schematic.py -k "license or pair or source or tree or rate"`

Expected: 허용 source만 정확한 commit으로 선택되고 안전 오류 시험이 모두 PASS.

---

### Task 3: 안전한 PNG·SVG·PDF·KiCad 전체 시트 렌더링

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `backend/projects/external_schematic.py`
- Modify: `backend/projects/schematic.py`
- Modify: `tests/projects/test_external_schematic.py`
- Modify: `tests/projects/test_schematic.py`

**Interfaces:**
- Consumes: `VerifiedSchematicSource`와 고정 commit raw/archive URL.
- Produces: `render_external_schematic(source: VerifiedSchematicSource, *, client: httpx.Client | None = None, kicad_export: Callable = run_kicad_pdf) -> tuple[bytes, ...]`.
- Produces: `run_kicad_pdf(root: Path, output: Path) -> tuple[str, Path]`.
- Guarantees: 반환 tuple은 1~20개 PNG이고 각 PNG는 signature·dimensions·40 MP·10 MiB 상한을 통과한다.

renderer 시험 fixture는 `tests/projects/test_external_schematic.py` 안에 둔다. `source`는 Task 2의 `VerifiedSchematicSource`를 반환하고, `png_bytes(width, height)`는 Pillow로 메모리 PNG를 만든다. `two_page_pdf`는 파일에 고정한 최소 2-page PDF base64 상수를 `base64.b64decode`한 bytes라서 외부 도구나 network가 필요 없다. `make_raw_client(mapping) -> httpx.Client`는 exact URL별 `(status, headers, bytes)` map을 `httpx.MockTransport`로 제공한다. `FakeKicad`는 받은 root 목록을 기록한 뒤 `two_page_pdf`를 output path에 쓰고 `(\"test-kicad\", pdf_path)`를 반환한다.

- [ ] **Step 1: renderer runtime 의존성 추가**

Pillow는 PNG magic·dimensions 검증, CairoSVG는 sanitize 후 SVG→PNG, pypdfium2는 PDF 모든 page→PNG에만 사용한다.

Run: `uv add "pillow>=11,<13" "cairosvg>=2.7,<3" "pypdfium2>=4.30,<5"`

Expected: `pyproject.toml`의 운영 dependencies와 `uv.lock`이 함께 갱신되고 `uv lock --check`가 PASS.

- [ ] **Step 2: format별 RED 시험 작성**

`tests/projects/test_external_schematic.py`에 다음을 추가한다.

```python
def test_png_is_validated_and_returned_as_one_sheet(valid_png, source):
    url = f"https://raw.githubusercontent.com/owner/repo/{source.commit}/{source.asset_paths[0]}"
    with make_raw_client({url: (200, {"Content-Type": "image/png"}, valid_png)}) as client:
        assert render_external_schematic(source, client=client) == (valid_png,)


def test_pdf_renders_every_page_in_order(two_page_pdf, source):
    source = replace(source, asset_kind="pdf", asset_paths=("hardware/schematic.pdf",))
    url = f"https://raw.githubusercontent.com/owner/repo/{source.commit}/hardware/schematic.pdf"
    with make_raw_client({url: (200, {"Content-Type": "application/pdf"}, two_page_pdf)}) as client:
        sheets = render_external_schematic(source, client=client)
    assert len(sheets) == 2
    assert all(sheet.startswith(b"\x89PNG\r\n\x1a\n") for sheet in sheets)


def test_kicad_fallback_exports_pdf_then_renders_all_pages(source, archive_bytes, fake_kicad):
    source = replace(source, asset_kind="kicad", asset_paths=())
    url = f"https://codeload.github.com/owner/repo/zip/{source.commit}"
    with make_raw_client({url: (200, {"Content-Type": "application/zip"}, archive_bytes)}) as client:
        sheets = render_external_schematic(source, client=client, kicad_export=fake_kicad)
    assert fake_kicad.roots == ["board.kicad_sch"]
    assert len(sheets) == 2
```

안전 SVG 1건과 `script`, `foreignObject`, `on*`, 외부 `href`, entity/doctype, 50,000 node 초과 거절을 시험한다. PNG 10 MiB·40 MP, PDF 20 MiB·20쪽, archive 25/100 MiB, redirect host 변경, MIME·magic 불일치, path escape·symlink·중복 경로와 subprocess timeout도 각각 고정한다.

- [ ] **Step 3: KiCad PDF runner RED와 구현**

Run: `uv run --no-sync pytest -q tests/projects/test_schematic.py -k "kicad_pdf"`

Expected: `run_kicad_pdf`가 없어 FAIL.

`backend/projects/schematic.py`에 기존 `run_kicad_cli`와 같은 최소 환경·timeout·shell 없는 인자 규칙을 쓰는 runner를 추가한다.

```python
def run_kicad_pdf(root: Path, output: Path) -> tuple[str, Path]:
    pdf = output / "schematic.pdf"
    cli_home = output / "home"
    cli_home.mkdir(parents=True, exist_ok=True)
    cli_env = {"HOME": str(cli_home), "PATH": os.environ.get("PATH", os.defpath)}
    try:
        version = subprocess.run(
            [KICAD_CLI, "--version"], check=True, capture_output=True, text=True,
            timeout=COMMAND_TIMEOUT_SECONDS, env=cli_env,
        ).stdout.strip()
        subprocess.run(
            [KICAD_CLI, "sch", "export", "pdf", "--output", str(pdf), str(root)],
            cwd=root.parent, check=True, capture_output=True,
            timeout=COMMAND_TIMEOUT_SECONDS, env=cli_env,
        )
    except (FileNotFoundError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise KicadServiceUnavailable("KiCad 변환 서비스를 사용할 수 없습니다.") from None
    return version, pdf
```

- [ ] **Step 4: bounded downloader와 PNG·SVG·PDF renderer 구현**

raw URL은 `https://raw.githubusercontent.com/{owner}/{repo}/{commit}/{quoted_path}`만 조립하고 사용자 URL은 받지 않는다. 모든 request는 `follow_redirects=False`로 보내고 redirect는 최대 3회 직접 처리한다. 매 hop의 `Location`을 현재 URL에 resolve한 뒤 scheme·host·port·userinfo와 DNS 결과의 모든 IP가 public인지 다시 검사한다. `Content-Length` 선검사 후 64 KiB chunk로 누적 상한을 재검사한다.

```python
def _validate_png(data: bytes) -> bytes:
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > MAX_IMAGE_BYTES:
        raise ExternalSchematicInvalidSource("invalid PNG")
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size
    if width <= 0 or height <= 0 or width * height > MAX_SHEET_PIXELS:
        raise ExternalSchematicInvalidSource("invalid PNG dimensions")
    return data


def _page_to_png(page) -> bytes:
    width, height = page.get_size()
    scale = min(2.0, math.sqrt(MAX_SHEET_PIXELS / (width * height)))
    if scale <= 0:
        raise ExternalSchematicInvalidSource("invalid PDF dimensions")
    bitmap = page.render(scale=scale)
    output = io.BytesIO()
    bitmap.to_pil().save(output, format="PNG")
    return _validate_png(output.getvalue())


def _render_pdf(data: bytes) -> tuple[bytes, ...]:
    if not data.startswith(b"%PDF-") or len(data) > MAX_PDF_BYTES:
        raise ExternalSchematicInvalidSource("invalid PDF")
    document = pypdfium2.PdfDocument(data)
    if not 1 <= len(document) <= MAX_PDF_PAGES:
        raise ExternalSchematicInvalidSource("invalid PDF page count")
    return tuple(_page_to_png(document[index]) for index in range(len(document)))
```

SVG는 `defusedxml`을 새로 추가하지 않고 표준 `ElementTree` 전에 `<!DOCTYPE`·`<!ENTITY`를 byte scan으로 거절하고 node·attribute를 순회 검증한 뒤에만 `cairosvg.svg2png`로 넘긴다. 변환 PNG는 다시 `_validate_png()`를 통과시킨다.

- [ ] **Step 5: archive 검사와 KiCad fallback 구현**

GitHub archive는 `https://codeload.github.com/{owner}/{repo}/zip/{commit}`만 사용한다. 전체 archive를 먼저 검사하고 absolute·`..`·backslash·NUL·symlink·special file·casefold duplicate·파일 수 5,000·압축/해제 상한을 통과한 뒤 임시 directory에 쓴다. token의 `root_schematic`과 정확히 일치하는 파일만 `run_kicad_pdf`에 넘기고 PDF 모든 page를 렌더링한다. `TemporaryDirectory` scope 밖에는 source·archive·PNG를 쓰지 않는다.

```python
def _render_kicad_archive(source: VerifiedSchematicSource, archive: bytes, *, kicad_export) -> tuple[bytes, ...]:
    if len(archive) > MAX_ARCHIVE_BYTES:
        raise ExternalSchematicInvalidSource("archive too large")
    with tempfile.TemporaryDirectory(prefix="sojafit-external-schematic-") as temporary:
        root = _extract_verified_archive(
            archive,
            Path(temporary) / "source",
            repository=source.repository,
            commit=source.commit,
            root_schematic=source.root_schematic,
            max_files=MAX_TREE_ITEMS,
            max_uncompressed_bytes=MAX_ARCHIVE_UNCOMPRESSED_BYTES,
        )
        output = Path(temporary) / "output"
        output.mkdir()
        _, pdf_path = kicad_export(root, output)
        if not pdf_path.is_file():
            raise ExternalSchematicInvalidSource("KiCad PDF missing")
        return _render_pdf(pdf_path.read_bytes())
```

- [ ] **Step 6: Task 3 GREEN 확인**

Run: `uv run --no-sync pytest -q tests/projects/test_schematic.py tests/projects/test_external_schematic.py -k "png or svg or pdf or archive or kicad or redirect or magic or pixel"`

Expected: 네 변환 경로와 모든 자원·보안 상한 시험 PASS.

---

### Task 4: signed token, bounded TTL cache와 요청 병합

**Files:**
- Modify: `backend/projects/external_schematic.py`
- Modify: `tests/projects/test_external_schematic.py`

**Interfaces:**
- Produces: `ExternalSchematicManifest(project, commit, license, attribution, repository_url, source_url, source_file, token, sheet_count)`.
- Produces: `find_external_schematic(query: str) -> ExternalSchematicManifest`.
- Produces: `load_external_schematic_sheet(token: str, sheet_index: int) -> bytes`.
- Raises: `ExternalSchematicNotFound`, `ExternalSchematicInvalidToken`, `ExternalSchematicRateLimited`, `ExternalSchematicUpstreamError`, `ExternalSchematicConfigurationError`.
- Cache keys: normalized query 또는 `repository + commit + root_schematic + asset_kind + asset_paths`.
- Service constructor: `ExternalSchematicService(search, inspect, render, clock=time.monotonic, query_capacity=128, image_capacity=64, image_byte_capacity=128 * 1024 * 1024, ttl_seconds=900)`; `find(normalized_query) -> ExternalSchematicManifest`; `load(payload, sheet_index) -> bytes`.

cache 시험용 `providers` fixture는 `search`, `inspect`, `render` callable과 각 호출 counter, `fail_if_called` flag를 가진다. `service` fixture는 fake clock, 이 세 callable, 검색 128항목·image 64 source·128 MiB 상한을 주입한 `ExternalSchematicService`다. production module global `_SERVICE`도 같은 class를 real callable로 한 번 구성한다.

- [ ] **Step 1: token 정상·만료·변조 RED 시험 작성**

```python
def test_signed_token_round_trip_uses_exact_source(monkeypatch, source):
    monkeypatch.setenv("AUTH_SECRET", "x" * 32)
    token = sign_schematic_source(source, sheet_count=2, now=1_000)
    decoded = verify_schematic_token(token, now=1_100)
    assert decoded.source == source
    assert decoded.sheet_count == 2


def flip_last_character(value: str) -> str:
    return value[:-1] + ("A" if value[-1] != "A" else "B")


@pytest.mark.parametrize("mutation", ["expired", "payload", "signature"])
def test_signed_token_rejects_expired_or_tampered_values(monkeypatch, source, mutation):
    monkeypatch.setenv("AUTH_SECRET", "x" * 32)
    token = sign_schematic_source(source, sheet_count=1, now=1_000)
    encoded, signature = token.split(".", 1)
    if mutation == "payload":
        token = f"{flip_last_character(encoded)}.{signature}"
    elif mutation == "signature":
        token = f"{encoded}.{flip_last_character(signature)}"
    with pytest.raises(ExternalSchematicInvalidToken):
        verify_schematic_token(token, now=1_901 if mutation == "expired" else 1_001)
```

token payload는 canonical compact JSON을 base64url로 만들고 `hmac.new(AUTH_SECRET, payload, sha256)`을 붙인다. `hmac.compare_digest`, 900초 expiry, 4 KiB token 상한, strict key set과 path·SHA·license 재검증을 시험한다.

- [ ] **Step 2: cache·LRU·byte 상한·single-flight RED 시험 작성**

fake clock과 `ThreadPoolExecutor`로 아래를 고정한다.

```python
def test_second_search_and_sheet_read_use_memory_cache(service, providers):
    first = service.find("ATtiny85")
    first_sheet = service.load(first.token, 0)
    providers.fail_if_called = True
    assert service.find("  attiny85  ") == first
    assert service.load(first.token, 0) == first_sheet


def test_concurrent_same_query_executes_discovery_and_render_once(service, providers):
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: service.find("LM7805 power supply"), range(8)))
    assert len({item.token for item in results}) == 1
    assert providers.exa_calls == 1
    assert providers.render_calls == 1
```

TTL 직전 hit·900초 뒤 miss, 검색 cache 128개 LRU, image source 64개, 총 128 MiB 초과 시 오래된 source 전체 시트 퇴출, 실패한 single-flight가 waiter 모두에게 안전 오류를 전달하고 inflight slot을 제거하는 시험도 추가한다.

비저장 경계 시험도 같은 단계에서 추가한다. `caplog`에는 query, signed token, upstream body marker가 없어야 하고, `TemporaryDirectory` factory가 만든 fallback directory는 성공·실패 뒤 모두 사라져야 한다. `psycopg.connect`와 `app.state.conversations`를 fail-fast spy/sentinel로 두고 service·API 호출이 DB connection이나 대화 상태를 건드리지 않는지 확인한다.

- [ ] **Step 3: Task 4 RED 확인**

Run: `uv run --no-sync pytest -q tests/projects/test_external_schematic.py -k "token or cache or ttl or lru or concurrent or single_flight"`

Expected: signing·service·cache API가 없어 FAIL.

- [ ] **Step 4: stateless HMAC token 구현**

```python
TOKEN_TTL_SECONDS = 900


@dataclass(frozen=True)
class VerifiedSchematicToken:
    source: VerifiedSchematicSource
    sheet_count: int
    expires_at: int


class ExternalSchematicNotFound(ExternalSchematicError):
    pass


class ExternalSchematicInvalidToken(ExternalSchematicError):
    pass


def sign_schematic_source(source: VerifiedSchematicSource, *, sheet_count: int, now: int | None = None) -> str:
    secret = os.getenv("AUTH_SECRET", "")
    if len(secret.encode("utf-8")) < 32:
        raise ExternalSchematicConfigurationError("schematic token signing is unavailable")
    issued_at = int(time.time()) if now is None else now
    payload = _canonical_token_payload(source, sheet_count, expires_at=issued_at + TOKEN_TTL_SECONDS)
    encoded = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64url(hmac.new(secret.encode("utf-8"), encoded.encode("ascii"), hashlib.sha256).digest())
    return f"{encoded}.{signature}"
```

`verify_schematic_token()`은 signature를 먼저 확인한 뒤 payload schema·expiry·허용 license·commit·safe paths·sheet_count를 검증한다. 로그·오류에는 token과 payload를 넣지 않는다.

- [ ] **Step 5: TTL LRU와 single-flight service 구현**

`threading.Lock` 아래에서는 cache bookkeeping만 수행하고 외부 I/O·변환은 lock 밖에서 실행한다. key별 leader 하나가 실행하고 waiter는 `Condition`으로 같은 결과를 받는다. 실패도 영구 cache하지 않으며 `ExternalSchematicNotFound`만 15분 negative cache한다.

```python
@dataclass(frozen=True)
class ExternalSchematicManifest:
    project: str
    commit: str
    license: str
    attribution: str
    repository_url: str
    source_url: str
    source_file: str
    token: str
    sheet_count: int


def find_external_schematic(query: str) -> ExternalSchematicManifest:
    normalized = " ".join(query.split()).casefold()
    return _SERVICE.find(normalized)


def load_external_schematic_sheet(token: str, sheet_index: int) -> bytes:
    payload = verify_schematic_token(token)
    if type(sheet_index) is not int or not 0 <= sheet_index < payload.sheet_count:
        raise ExternalSchematicInvalidToken("invalid sheet")
    return _SERVICE.load(payload, sheet_index)
```

`find()`는 Exa 후보 최대 5개 중 앞의 3개만 순차 검사하고 첫 valid source를 렌더링한다. cache miss `load()`는 token의 고정 source를 다시 다운로드·렌더링하므로 다른 인스턴스에서도 동일 commit을 재구성한다.

- [ ] **Step 6: Task 4 GREEN 확인**

Run: `uv run --no-sync pytest -q tests/projects/test_external_schematic.py -k "token or cache or ttl or lru or concurrent or single_flight or first_valid"`

Expected: cache hit에서 provider 0회, 동시 요청에서 discovery·render 각 1회, 만료·변조·범위 오류 안전 거절 PASS.

---

### Task 5: 인증된 manifest와 PNG API 계약

**Files:**
- Modify: `backend/api/external_circuits.py`
- Modify: `backend/main.py`
- Modify: `tests/api/test_external_circuits.py`
- Modify: `tests/api/test_openapi.py`
- Modify: `backend/api/API.md`
- Modify: `tests/api/API.md`

**Interfaces:**
- Consumes: `find_external_schematic(q)`, `load_external_schematic_sheet(token, sheet_index)`.
- Produces: `GET /api/external-circuits/schematics?q=<2..200 chars>`.
- Produces: `GET /api/external-circuits/schematics/{signed_token}/{sheet_index}` with `image/png`.
- Preserves: existing `/search`와 `/answer` response·오류·budget 계약.

`tests/api/test_external_circuits.py`의 local `schematic_boundary` fixture는 `find_external_schematic`과 `load_external_schematic_sheet`를 monkeypatch하고 `manifest`, `queries`, `sheet_calls`, `png`, `error`를 담는 `SimpleNamespace`를 반환한다. 따라서 provider·DB 없이 HTTP 경계만 결정론적으로 시험한다.

- [ ] **Step 1: manifest endpoint RED 시험 작성**

인증, trim, 2·200자 경계, 1·201자 422, 완성 회로도 없음 404 `SCHEMATIC_NOT_FOUND`, 공급자 502, 비활성·키 누락·GitHub rate limit 503와 `Retry-After`, 모든 응답 no-store를 검증한다.

```python
def test_external_schematic_manifest_returns_all_sheet_urls(client, schematic_boundary):
    schematic_boundary.manifest.sheet_count = 2
    response = client.get("/api/external-circuits/schematics", params={"q": "  ATtiny85  "})
    assert response.status_code == 200
    assert schematic_boundary.queries == ["ATtiny85"]
    assert response.json() == {
        "project": "owner/repo",
        "commit": "a" * 40,
        "license": "MIT",
        "attribution": "owner/repo contributors",
        "repository_url": "https://github.com/owner/repo",
        "source_url": f"https://github.com/owner/repo/tree/{'a' * 40}",
        "source_file": "hardware/board.kicad_sch",
        "images": [
            {"sheet": 0, "url": "/api/external-circuits/schematics/signed-token/0"},
            {"sheet": 1, "url": "/api/external-circuits/schematics/signed-token/1"},
        ],
    }
    assert response.headers["Cache-Control"] == "private, no-store"
```

- [ ] **Step 2: PNG endpoint RED 시험 작성**

정상 PNG body와 `Content-Type: image/png`, `X-Content-Type-Options: nosniff`, `Content-Disposition: inline`, `Cache-Control: private, no-store`를 고정한다. 비인증, 변조·만료 token, 음수·범위 밖 sheet는 service 호출 전 또는 service 경계에서 404 `SCHEMATIC_NOT_FOUND`로 통일한다.

```python
def test_external_schematic_sheet_returns_hardened_png(client, schematic_boundary, valid_png):
    schematic_boundary.png = valid_png
    response = client.get("/api/external-circuits/schematics/signed-token/0")
    assert response.status_code == 200
    assert response.content == valid_png
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == "inline"
    assert response.headers["cache-control"] == "private, no-store"
```

- [ ] **Step 3: API RED 확인**

Run: `uv run --no-sync pytest -q tests/api/test_external_circuits.py -k "schematic"`

Expected: 새 route가 없어 404로 FAIL.

- [ ] **Step 4: Pydantic response와 manifest route 구현**

```python
class ExternalSchematicImage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sheet: int = Field(ge=0)
    url: str


class ExternalSchematicResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str
    commit: str
    license: str
    attribution: str
    repository_url: str
    source_url: str
    source_file: str
    images: list[ExternalSchematicImage]


@router.get("/schematics", dependencies=[Depends(auth.current_user_id)], response_model=ExternalSchematicResponse)
def external_schematic_manifest(
    response: Response,
    q: Annotated[str, Query(min_length=2, max_length=200), BeforeValidator(str.strip)],
):
    response.headers["Cache-Control"] = "private, no-store"
    manifest = find_external_schematic(q)
    return _schematic_response(manifest)
```

`ExternalSchematicNotFound`와 `ExternalSchematicInvalidToken`은 `ApiError(404, "검증된 완성 회로도를 찾지 못했습니다.", code="SCHEMATIC_NOT_FOUND")`, configuration/rate-limit은 503, provider·render transport는 502로 바꾼다. `Retry-After`는 503 rate-limit에서만 전달한다.

- [ ] **Step 5: schematic 전용 private no-store 정책 보존**

현재 `backend/main.py`의 공통 오류와 `conversation_boundary`가 모든 `/api/external-circuits` 응답을 `no-store`로 덮어쓴다. 기존 `/search`·`/answer`는 그대로 두고 `/api/external-circuits/schematics` prefix만 `private, no-store`로 설정한다. route 함수는 `backend/main.py`에 추가하지 않는다.

```python
def _external_cache_control(path: str) -> str | None:
    if path.startswith("/api/external-circuits/schematics"):
        return "private, no-store"
    if path.startswith("/api/external-circuits"):
        return "no-store"
    return None
```

`error_response()`와 `conversation_boundary()`가 이 helper 결과를 사용하도록 바꾸고, 기존 search·answer header assertion과 새 schematic 성공·401·404·502·503 header assertion을 모두 유지한다.

- [ ] **Step 6: binary route와 OpenAPI schema 구현**

```python
@router.get(
    "/schematics/{signed_token}/{sheet_index}",
    dependencies=[Depends(auth.current_user_id)],
    response_class=Response,
    responses={200: {"content": {"image/png": {"schema": {"type": "string", "format": "binary"}}}}},
)
def external_schematic_sheet(signed_token: str, sheet_index: int):
    png = load_external_schematic_sheet(signed_token, sheet_index)
    return Response(
        content=png,
        media_type="image/png",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )
```

`tests/api/test_openapi.py`의 `ROUTES`에 두 GET을 추가해 총 route 수 주석을 45개로 갱신하고, binary success content가 `image/png`와 `format: binary`인지 별도 assertion을 둔다. `backend/main.py`에는 경로 함수를 추가하지 않는다.

- [ ] **Step 7: Task 5 GREEN과 기존 endpoint 회귀 확인**

Run: `uv run --no-sync pytest -q tests/api/test_external_circuits.py tests/api/test_openapi.py`

Expected: 새 두 endpoint와 기존 `/search`·`/answer` 시험 모두 PASS.

---

### Task 6: 실제 외부·Docker 검증, 문서와 전체 backend 회귀

**Files:**
- Create: `scripts/smoke/verify_external_schematics.py`
- Modify: `scripts/smoke/SMOKE.md`
- Modify: `scripts/SCRIPTS.md`
- Modify: `.env.example`
- Modify: `SOJAFIT.md`
- Modify: `backend/projects/PROJECTS.md`
- Modify: `backend/api/API.md`
- Modify: `tests/projects/PROJECTS.md`
- Modify: `tests/api/API.md`
- Modify: `docs/worklog/osc.md`
- Verify only: `Dockerfile`
- Verify only: all backend tests and repository checks

**Interfaces:**
- Consumes: Task 1~5 service·API, 현재 shell의 `EXA_API_KEY`, 선택적 `GITHUB_TOKEN`, production 조건의 `AUTH_SECRET`.
- Produces: `python scripts/smoke/verify_external_schematics.py --query ATtiny85` exit 0/1 smoke command.
- Produces: 실행한 날짜·명령·실제 pass/fail만 기록한 worklog 증거.

- [ ] **Step 1: live smoke script 작성**

script는 이미지를 영구 저장하지 않고 process memory에서 manifest와 모든 PNG sheet를 검사한다. 기본 query는 `ATtiny85`, `LM7805 power supply` 두 개다. `--force-kicad-fallback`은 Exa를 호출하지 않고 아래 고정 source를 `render_external_schematic()`에 직접 주입해 Docker의 `kicad-cli` 경로를 실행한다.

```python
FALLBACK_SOURCE = VerifiedSchematicSource(
    repository="tomasr8/attiny85-dev-board",
    commit="488b99063b6bdbafa0f367ecc25901b55c4c7144",
    license="MIT",
    attribution="tomasr8/attiny85-dev-board contributors",
    repository_url="https://github.com/tomasr8/attiny85-dev-board",
    source_url="https://github.com/tomasr8/attiny85-dev-board/tree/488b99063b6bdbafa0f367ecc25901b55c4c7144",
    source_file="attiny85.kicad_sch",
    asset_kind="kicad",
    asset_paths=(),
    root_schematic="attiny85.kicad_sch",
)
```

```python
def verify_query(query: str) -> dict[str, object]:
    manifest = find_external_schematic(query)
    dimensions = []
    for index in range(manifest.sheet_count):
        png = load_external_schematic_sheet(manifest.token, index)
        if not png.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("sheet is not PNG")
        with Image.open(io.BytesIO(png)) as image:
            image.verify()
        with Image.open(io.BytesIO(png)) as image:
            dimensions.append(image.size)
    return {
        "query": query,
        "project": manifest.project,
        "commit": manifest.commit,
        "license": manifest.license,
        "source_file": manifest.source_file,
        "sheet_count": manifest.sheet_count,
        "dimensions": dimensions,
    }
```

출력은 key·token·외부 본문 없이 위 metadata만 JSON으로 표시한다. 같은 query를 두 번 호출하는 `--check-cache`는 두 결과가 같음을 확인하며 실제 provider 0회 여부는 Task 4의 주입형 단위 시험을 정본으로 삼는다.

- [ ] **Step 2: 설정·폴더 문서 갱신**

`.env.example`에 `GITHUB_TOKEN=`을 선택값으로 추가하고 익명 GitHub API도 동작하지만 rate limit이 낮다는 점, fixed size·TTL은 코드 상수라는 점을 기록한다. 각 폴더 문서와 `SOJAFIT.md`에는 새 module·test·smoke의 역할과 호출 위치만 기록한다. `docs/worklog/osc.md`에는 아래 검증을 실제로 실행한 뒤 관측된 수치만 2026-11-11 작업으로 적는다.

- [ ] **Step 3: 좁은 backend suite 실행**

Run: `uv run --no-sync pytest -q tests/projects/test_external_circuit_search.py tests/projects/test_schematic.py tests/projects/test_external_schematic.py tests/api/test_external_circuits.py tests/api/test_openapi.py tests/repo/test_repo_layout.py`

Expected: 기존 skip 외 모두 PASS.

- [ ] **Step 4: 실제 ATtiny85·LM7805 검색과 cache smoke 실행**

PowerShell에서 secret 값을 출력하지 않고 필요한 환경변수가 이미 설정된 shell로 실행한다.

Run: `uv run --no-sync python scripts/smoke/verify_external_schematics.py --query ATtiny85 --query "LM7805 power supply" --check-cache`

Expected: 두 query 모두 허용 license, 40자리 commit, `.kicad_sch` 또는 `.sch` source, `sheet_count >= 1`, 양수 dimensions를 출력하고 exit 0. 데이터시트 부분 응용 회로나 PCB 이미지가 선택되면 FAIL로 처리한다.

- [ ] **Step 5: 운영 Docker의 renderer와 KiCad fallback 검증**

Run: `docker build -t sojafit-complete-schematic:verify .`

Run: `docker run --rm --entrypoint sh sojafit-complete-schematic:verify -lc "kicad-cli --version && python -c 'import cairosvg,pypdfium2; from PIL import Image; print(\"renderers-ok\")'"`

PowerShell에서 실행한다.

```powershell
$workspace = (Get-Location).Path
docker run --rm `
  --env EXA_WEB_SEARCH_ENABLED=1 `
  --env DEMO_MODE=0 `
  --env EXA_API_KEY `
  --env GITHUB_TOKEN `
  --env AUTH_SECRET `
  --mount "type=bind,source=$workspace,target=/workspace,readonly" `
  --entrypoint sh sojafit-complete-schematic:verify `
  -lc "cd /app && PYTHONPATH=/app python /workspace/scripts/smoke/verify_external_schematics.py --force-kicad-fallback"
```

Expected: KiCad version과 `renderers-ok`, subprocess argv가 `kicad-cli sch export pdf --output` 뒤 임시 PDF 경로와 `attiny85.kicad_sch`를 사용해 성공, 생성 PDF의 모든 page에 대응하는 PNG dimensions, exit 0. token·key·archive·이미지는 container 종료 뒤 남지 않는다.

- [ ] **Step 6: 전체 backend 회귀와 lock·diff 검사**

Run: `uv run --no-sync pytest -q`

Run: `uv lock --check`

Run: `git diff --check`

Expected: 전체 backend suite는 기존 skip 외 PASS, lock 일치, whitespace error 없음. 이번 backend-only 기능 때문에 프런트 테스트와 build는 실행하지 않는다.

- [ ] **Step 7: 완료 기준과 final diff 검토**

`git status --short`, `git diff --stat`, 이 계획에 열거한 backend·test·script·문서 diff를 확인한다. 다음을 모두 만족하지 않으면 완료로 보고하지 않는다.

1. `ATtiny85`와 `LM7805 power supply`가 검증된 공개 프로젝트의 완성 회로도 PNG 전체 시트를 반환한다.
2. 데이터시트 부분 회로, 블록도, PCB·제품 이미지는 후보에서 탈락한다.
3. 다중 시트는 전부 순서대로 반환하고 찾지 못하면 404 `SCHEMATIC_NOT_FOUND`다.
4. cache hit과 같은-key 동시 요청은 외부 검색·변환을 반복하지 않는다.
5. LLM, Mouser, DigiKey, Nexar, DB, frontend를 호출·변경하지 않는다.
6. 실제 Docker `kicad-cli` fallback과 전체 backend pytest가 통과한다.

Task별 commit은 이 시점에도 자동 수행하지 않는다. 사용자가 별도로 승인하면 관련 파일만 stage한 뒤 task 경계별로 commit하고, 기존 dirty 변경은 포함하지 않는다.
