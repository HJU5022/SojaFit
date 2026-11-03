"""저장소 구조 규칙을 PR마다 지킨다.

- 역할: SOJAFIT.md 디렉토리 트리와 실제 파일이 한 줄도 어긋나지 않는지(빠진 파일, 없는 파일 둘 다 실패),
  폴더 설명 파일이 `<대문자 폴더명>.md`이고 README.md는 루트에만 있는지,
  대문자 마크다운을 허용한 곳에만 쓰는지, 폴더 설명 파일의 "파일" 절이 그 폴더 바로 아래를 모두 적는지,
  한 폴더 바로 아래에 종류가 다른 파일(코드·데이터·문서·SQL·설정)이 섞이지 않았는지 본다.
- 하지 않는 일: `<-` 설명 문장이 맞는지는 사람이 본다. 원시 결과·외부 원본·ADR 본문은 파일마다 보지 않고 폴더 한 줄로 본다.
  트리에서 `(예정)`이 붙은 줄은 아직 없는 파일·폴더라 있는지 보지 않는다. 빈 폴더를 지키는 `.gitkeep`은 트리 줄을 요구하지 않는다.
  git이 아는 파일(추적 + 무시하지 않은 새 파일)만 읽어 네트워크·DB가 필요 없다.
- 출처: SOJAFIT.md "디렉토리 구조"·"이름 규칙"·"파일을 만들거나 옮길 때", ADR 0012, AGENTS.md 지킬 것 9.
"""
import re
import subprocess
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[2]
ROOT_DOCS = {"README.md", "SOJAFIT.md", "SPEC.md", "AGENTS.md", "CLAUDE.md", "EVAL_REPORT.md"}
UPPER_EXCEPTIONS = {"docs/TOPIC.md", "docs/GATES.md", "backend/mcp_skill/skills/SKILL.md", ".github/PULL_REQUEST_TEMPLATE.md"}
# [왜] 트리에 파일마다 적지 않고 폴더 한 줄로 묶는 곳: 원시 결과, 외부 원본, 데이터시트 표본, 결정 본문(ADR.md가 목록)
GROUPED = ("evals/results/", "scripts/results/", "data/circuits/collected/", "data/corpus/tsc/", "docs/adr/0")
# [왜] 원시 결과·외부 원본·시험용 가공 데이터만 담는 폴더는 설명 파일 없이 위 폴더 설명이 대신한다
NO_DESCRIPTION = ("evals/results/", "scripts/results/", "data/circuits/collected/", "tests/fixtures/", ".github/")
KINDS = {".py": "코드", ".json": "데이터", ".jsonl": "데이터", ".pdf": "데이터", ".csv": "데이터", ".md": "문서",
         ".sql": "SQL", ".draft": "SQL", ".manual": "SQL", ".yml": "설정", ".yaml": "설정"}
EXTERNAL = "data/circuits/collected/"  # [왜] 받은 원본은 이름을 고치지 않는다(README.md·대문자도 원래 이름 그대로)


def repo_files() -> list[str]:
    """git이 아는 파일 경로(저장소 루트 기준, 지운 파일 제외)."""
    # [왜] -co --exclude-standard: 아직 git add 안 한 새 파일도 로컬에서 바로 검사한다. -z와 quotepath=off는 한글 파일명을 그대로 받는다
    try:
        out = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "-co", "--exclude-standard", "-z"],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git 저장소가 아니다")
    return sorted(f for f in out.split("\0") if f and (ROOT / f).is_file())


def tree_paths(planned: bool = False) -> set[str]:
    """SOJAFIT.md 디렉토리 트리 블록을 경로 집합으로 바꾼다. 폴더는 끝에 '/'가 붙는다. planned=True면 `(예정)` 줄만 돌려준다."""
    text = (ROOT / "SOJAFIT.md").read_text(encoding="utf-8")
    block = text.split("## 디렉토리 구조", 1)[1].split("```", 2)[1]
    stack: list[str] = []
    paths = set()
    for line in block.splitlines():
        m = re.search(r"[├└]── (\S+)", line)
        if not m:
            continue  # 루트 이름 줄과 설명이 다음 줄로 이어지는 줄은 항목이 아니다
        depth = m.start() // 4  # [주의] 트리 들여쓰기는 한 단계에 네 글자('│   ' 또는 '    ')라 이 폭을 바꾸면 깊이가 틀린다
        del stack[depth:]  # 같은 깊이나 더 얕은 항목이 나오면 그 아래 폴더 이름을 버린다
        path = "".join(stack) + m.group(1)
        if ("(예정" in line) == planned:  # [왜] (예정) 줄은 아직 없는 자리라 실제 파일과 따로 센다
            paths.add(path)
        if path.endswith("/"):
            stack.append(m.group(1))  # 폴더면 다음 줄들의 앞 경로가 된다
    return paths


def described_folders() -> dict[str, str]:
    """SOJAFIT.md "폴더 설명 파일과 담당" 표의 {폴더: 설명 파일 이름}."""
    text = (ROOT / "SOJAFIT.md").read_text(encoding="utf-8")
    return dict(re.findall(r"^\| `([^`]+)/` \| \[([^\]]+)\]", text, re.M))


def test_tree_matches_files():
    """트리에 빠진 파일도, 트리에만 있는 항목도 없다."""
    files = repo_files()
    tree = tree_paths()
    missing = [f for f in files if not f.startswith(GROUPED) and not f.endswith("/.gitkeep") and f not in tree]
    groups = {g for g in GROUPED if any(f.startswith(g) for f in files)}
    missing += [g for g in groups if g.endswith("/") and g not in tree]
    real_dirs = {str(p) + "/" for f in files for p in PurePosixPath(f).parents if str(p) != "."}
    stale = [p for p in tree if p not in real_dirs and p not in files]
    born = [p for p in tree_paths(planned=True) if p in files]  # [주의] 만들었으면 (예정) 표시를 지운다
    assert not missing, f"SOJAFIT.md 트리에 없는 파일(같은 PR에서 <- 설명과 함께 넣는다): {missing}"
    assert not stale, f"SOJAFIT.md 트리에 있지만 저장소에 없는 항목(아직 없으면 (예정)을 붙인다): {stale}"
    assert not born, f"이미 있는데 트리에 (예정)으로 남은 항목: {born}"


def test_folder_description_names():
    """두 단계까지의 폴더는 모두 `<대문자 폴더명>.md`를 갖고, README.md는 루트에만 있다."""
    folders = described_folders()
    assert folders, "SOJAFIT.md 표를 읽지 못했다"
    for folder, name in folders.items():
        assert name == PurePosixPath(folder).name.upper() + ".md", f"{folder}의 설명 파일은 <대문자 폴더명>.md: {name}"
        assert (ROOT / folder / name).is_file(), f"설명 파일이 없다: {folder}/{name}"
    files = repo_files()
    # 두 단계까지의 폴더는 원시 결과·외부 원본·.github을 빼고 모두 설명 파일을 가진다(SOJAFIT.md 이름 규칙)
    dirs = {str(PurePosixPath(f).parent) for f in files}
    dirs |= {str(PurePosixPath(d).parent) for d in dirs}
    shallow = {d for d in dirs if d != "." and len(PurePosixPath(d).parts) <= 2
               and not (d + "/").startswith(NO_DESCRIPTION)}
    assert shallow <= set(folders), f"설명 파일 표에 없는 폴더: {sorted(shallow - set(folders))}"
    readmes = [f for f in files if PurePosixPath(f).name.lower() == "readme.md" and f != "README.md"
               and not f.startswith(EXTERNAL)]
    assert not readmes, f"README.md는 루트 대표 문서 하나만 둔다: {readmes}"


def test_uppercase_markdown_only_where_allowed():
    """대문자 마크다운은 허용한 곳에만 있고, 대소문자만 다른 두 경로는 없다."""
    # [왜] GitHub·ls는 대문자를 먼저 정렬해 설명 파일이 위에 오는데, 다른 대문자 문서가 섞이면 그 구분이 사라진다
    files = repo_files()
    bad = []
    for f in files:
        p = PurePosixPath(f)
        if p.suffix != ".md" or p.name == p.name.lower() or f.startswith(EXTERNAL):
            continue
        is_description = p.stem == p.parent.name.upper()
        if f not in ROOT_DOCS and f not in UPPER_EXCEPTIONS and not is_description:
            bad.append(f)
    assert not bad, f"대문자 마크다운은 루트 대표 문서·폴더 설명 파일·예외 4개만: {bad}"
    # [주의] macOS 기본 파일시스템은 대소문자를 구분하지 않아 readme.md와 README.md가 한 파일로 겹친다
    lowered = [f.lower() for f in files]
    clash = sorted({f for f in files if lowered.count(f.lower()) > 1})
    assert not clash, f"대소문자만 다른 경로는 macOS에서 한 파일이 된다: {clash}"


def test_folder_description_lists_every_child():
    """폴더 설명 파일의 '## 파일' 절에 그 폴더 바로 아래 파일과 하위 폴더 이름이 모두 있다."""
    files = repo_files()
    for folder, name in described_folders().items():
        text = (ROOT / folder / name).read_text(encoding="utf-8")
        section = text.split("## 파일", 1)[1].split("\n## ", 1)[0] if "## 파일" in text else ""
        # 바로 아래 항목만 센다: 'a/b/c.py'는 폴더 'a'의 자식 'b/'로 본다
        children = {f[len(folder) + 1:].split("/")[0] + ("/" if f[len(folder) + 1:].count("/") else "")
                    for f in files if f.startswith(folder + "/")}
        children.discard(name)
        children.discard(".gitkeep")
        unlisted = sorted(c for c in children if c.rstrip("/") not in section)
        assert not unlisted, f"{folder}/{name}의 '## 파일' 절에 빠진 항목: {unlisted}"


def test_one_kind_of_file_per_folder():
    """한 폴더 바로 아래 파일은 한 종류다(설명 파일·.gitkeep 제외). 섞이면 성격별 하위 폴더로 나눈다."""
    # [왜] 조장 규칙(ADR 0012 보강): 코드·데이터·문서·SQL이 한 높이에 흩어지면 폴더 역할이 흐려진다
    by_dir: dict[str, set[str]] = {}
    for f in repo_files():
        p = PurePosixPath(f)
        d = str(p.parent)
        if d == "." or f.startswith((".github/", EXTERNAL)) or p.name == ".gitkeep" or p.name == p.parent.name.upper() + ".md":
            continue
        by_dir.setdefault(d, set()).add(KINDS.get(p.suffix, "기타"))
    mixed = {d: sorted(k) for d, k in by_dir.items() if len(k) > 1}
    assert not mixed, f"한 폴더에 종류가 섞였다(하위 폴더로 나눈다): {mixed}"
