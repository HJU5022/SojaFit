"""GitHub의 고정 commit에서 회로 원본과 짝지어진 공개 도면을 확인한다."""
import ipaddress
import json
import os
import re
import socket
import time
from pathlib import PurePosixPath
from urllib.parse import quote, unquote, urljoin, urlsplit

import httpx

from .external_circuit_search import (
    GitHubRepositoryRef, github_repository_ref, read_bounded_body, safe_public_https_url,
)
from .schematic_source import (
    ALLOWED_LICENSES, ExternalSchematicConfigurationError, ExternalSchematicInvalidSource,
    ExternalSchematicRateLimited, ExternalSchematicUpstreamError, VerifiedSchematicSource,
)

_API = frozenset({"api.github.com"})
_RAW = frozenset({"raw.githubusercontent.com"})
_DOWNLOAD_HOSTS = _API | _RAW | {"codeload.github.com"}
_SHA = re.compile(r"[a-fA-F0-9]{40}")
_EXCLUDED = re.compile(r"datasheet|application[-_ ]?note|block[-_ ]?diagram|(?:^|[/_. -])(?:pcb|layout|renders?|rendering|3d|photo|preview|partial|detail|pinout|old|deprecated|obsolete|draft|backup|archive|archived|stage|excerpt|subsystem|section|fragment)(?:$|[/_. -])", re.I)


def _public_addresses(host: str) -> bool:
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    return bool(addresses) and all(ipaddress.ip_address(a[4][0]).is_global for a in addresses)


def _retry_after(headers: httpx.Headers) -> int:
    try:
        if "retry-after" in headers:
            return min(3600, max(1, int(headers["retry-after"])))
        return min(3600, max(1, int(headers["x-ratelimit-reset"]) - int(time.time())))
    except (ValueError, KeyError):
        return 60


def download_bounded(url: str, *, max_bytes: int, allowed_hosts: frozenset[str],
                     client: httpx.Client | None = None) -> tuple[bytes, str]:
    """Only the API receives credentials. Never follow redirects to a different resource."""
    if client is None:
        with httpx.Client(trust_env=False) as owned:
            return download_bounded(url, max_bytes=max_bytes, allowed_hosts=allowed_hosts, client=owned)
    original = urlsplit(url)
    try:
        for _ in range(4):
            if not safe_public_https_url(url, allowed_hosts=allowed_hosts):
                raise ExternalSchematicInvalidSource()
            parsed = urlsplit(url)
            # MockTransport does not connect to a peer. Real requests validate DNS before each hop.
            if not isinstance(client._transport, httpx.MockTransport) and not _public_addresses(parsed.hostname):
                raise ExternalSchematicInvalidSource()
            if (parsed.path, parsed.query) != (original.path, original.query) or parsed.fragment:
                raise ExternalSchematicInvalidSource()
            headers = {"Accept-Encoding": "identity"}
            if parsed.hostname in _API:
                headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
                if token := os.getenv("GITHUB_TOKEN", "").strip():
                    headers["Authorization"] = f"Bearer {token}"
            with client.stream("GET", url, headers=headers, timeout=15, follow_redirects=False) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise ExternalSchematicInvalidSource()
                    url = urljoin(url, location)
                    continue
                if response.status_code == 429 or (
                    response.status_code == 403 and (
                        response.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in response.headers
                    )
                ):
                    raise ExternalSchematicRateLimited(_retry_after(response.headers))
                if response.status_code == 401 and parsed.hostname in _API:
                    raise ExternalSchematicConfigurationError()
                if response.status_code in {404, 410, 451}:
                    raise ExternalSchematicInvalidSource()
                response.raise_for_status()
                try:
                    data = read_bounded_body(response, max_bytes)
                except ValueError:
                    raise ExternalSchematicInvalidSource() from None
                return data, response.headers.get("content-type", "").partition(";")[0].strip().lower()
        raise ExternalSchematicInvalidSource()
    except (httpx.HTTPError, OSError, ValueError):
        raise ExternalSchematicUpstreamError() from None


def _api(url, cap, client):
    data, _ = download_bounded(url, max_bytes=cap, allowed_hosts=_API, client=client)
    try:
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, RecursionError):
        raise ExternalSchematicUpstreamError() from None


def _valid_path(path):
    return (isinstance(path, str) and 0 < len(path) <= 1024 and
            not any(ord(c) < 32 or c in "\\:\x7f" for c in path) and
            all(part not in {"", ".", ".."} for part in path.split("/")))


def _blobs(tree):
    rows = tree.get("tree")
    if tree.get("truncated") is not False or not isinstance(rows, list) or len(rows) > 5000:
        raise ExternalSchematicInvalidSource()
    files, seen = set(), set()
    for row in rows:
        if not isinstance(row, dict):
            raise ExternalSchematicUpstreamError()
        path = row.get("path")
        if not _valid_path(path) or path.casefold() in seen:
            raise ExternalSchematicInvalidSource()
        seen.add(path.casefold())
        if (row.get("mode"), row.get("type")) in {("040000", "tree"), ("160000", "commit")}:
            # A gitlink has no file bytes in this commit. Never resolve or descend into it.
            continue
        if row.get("type") != "blob" or row.get("mode") not in {"100644", "100755"}:
            raise ExternalSchematicInvalidSource()
        files.add(path)
    return files


_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[()]|[^\s()"]+|"')
_VALUE = re.compile(r'\s+"Value"\s+"([^"\\]{1,256})"')
_FILE = re.compile(r'\s+"Sheet\s*file"\s+"([^"\\]{1,1024})"', re.I)


_NUMBER = r"(-?\d{1,12}(?:\.\d{1,12})?)"
_WIRE_POINTS = re.compile(r"\s+\(xy\s+" + _NUMBER + r"\s+" + _NUMBER +
                          r"\)\s+\(xy\s+" + _NUMBER + r"\s+" + _NUMBER + r"\)\s*\)")
_LEGACY_WIRE_POINTS = re.compile(r"\s*" + r"\s+".join([_NUMBER] * 4) + r"\s*")


def _nonzero_segment(match):
    if not match:
        return False
    x1, y1, x2, y2 = map(float, match.groups())
    return (x1, y1) != (x2, y2)


def _sheet_data(path, source):
    """Read placed components and direct child sheets; embedded symbol libraries are not instances."""
    children, values = [], []
    count = 0
    child_start = 0
    symbols = 0
    has_wire = False
    if path.lower().endswith(".kicad_sch"):
        stack = []
        finished = False
        for token in _TOKEN.finditer(source):
            part = token.group()
            if finished:
                raise ExternalSchematicInvalidSource()
            if part == "(":
                if len(stack) >= 120:
                    raise ExternalSchematicInvalidSource()
                stack.append(None)
            elif part == ")":
                if stack == ["kicad_sch", "sheet"] and len(children) != child_start + 1:
                    raise ExternalSchematicInvalidSource()
                if not stack or stack.pop() is None:
                    raise ExternalSchematicInvalidSource()
                finished = not stack
            elif not stack or part == '"':
                raise ExternalSchematicInvalidSource()
            elif stack[-1] is None:
                stack[-1] = part
                if len(stack) == 1 and part != "kicad_sch":
                    raise ExternalSchematicInvalidSource()
                if len(stack) == 2 and part == "symbol":
                    symbols += 1
                if stack == ["kicad_sch", "wire", "pts"]:
                    has_wire |= _nonzero_segment(_WIRE_POINTS.match(source, token.end()))
                if len(stack) == 2 and part == "sheet":
                    count += 1
                    child_start = len(children)
                if len(stack) == 3 and part == "lib_id" and stack[1] == "symbol":
                    if match := re.match(r'\s+"([^"\\]{1,256})"', source[token.end():token.end()+260]):
                        values.append(match[1].rsplit(":", 1)[-1])
                if len(stack) == 3 and part == "property" and stack[1] in {"symbol", "sheet"}:
                    pattern = _VALUE if stack[1] == "symbol" else _FILE
                    if match := pattern.match(source, token.end()):
                        (values if stack[1] == "symbol" else children).append(match[1])
        if not finished:
            raise ExternalSchematicInvalidSource()
    else:
        if not source.startswith("EESchema Schematic File Version ") or not source.rstrip().endswith("$EndSCHEMATC"):
            raise ExternalSchematicInvalidSource()
        active = ""
        wire_points_next = False
        for line in source.splitlines():
            if wire_points_next:
                has_wire |= _nonzero_segment(_LEGACY_WIRE_POINTS.fullmatch(line))
            wire_points_next = not active and line.strip() == "Wire Wire Line"
            if line in {"$Sheet", "$Comp"}:
                if active:
                    raise ExternalSchematicInvalidSource()
                active = line
                count += line == "$Sheet"
                symbols += line == "$Comp"
                child_start = len(children)
            elif line in {"$EndSheet", "$EndComp"}:
                if active == "$Sheet" and len(children) != child_start + 1:
                    raise ExternalSchematicInvalidSource()
                if active != line.replace("$End", "$"):
                    raise ExternalSchematicInvalidSource()
                active = ""
            elif active == "$Sheet" and (match := re.match(r'^F1\s+"([^"\\]+)"', line)):
                children.append(match[1])
            elif active == "$Comp" and line.startswith("L "):
                fields = line.split()
                if len(fields) == 3:
                    values.append(fields[1].rsplit(":", 1)[-1])
            elif active == "$Comp" and (match := re.match(r'^F 1 "([^"]+)"', line)):
                values.append(match[1])
        if active:
            raise ExternalSchematicInvalidSource()
    if not (values or children) or len(children) != count or not all(_valid_path(ref) for ref in children):
        raise ExternalSchematicInvalidSource()
    return [str(PurePosixPath(path).parent / ref) for ref in children], values, symbols, has_wire


def _root(graph):
    children = set().union(*graph.values())
    roots = set(graph) - children
    if len(roots) != 1 or not children.issubset(graph):
        raise ExternalSchematicInvalidSource()
    root, = roots
    sizes = {}

    def sheet_count(node, active):
        if node in active:
            raise ExternalSchematicInvalidSource()
        if node not in sizes:
            size = 1
            for child in graph[node]:
                size += sheet_count(child, active | {node})
                if size > 20:
                    raise ExternalSchematicInvalidSource()
            sizes[node] = size
        return sizes[node]

    count = sheet_count(root, set())
    if len(sizes) != len(graph):
        raise ExternalSchematicInvalidSource()
    return root, count


def _readme_links(readme):
    links = re.findall(r'\]\(\s*<?([^)\n>]+)>?\s*\)|(?:src|href)\s*=\s*["\x27]([^"\x27]+)["\x27]', readme, re.I)
    result = set()
    for markdown, html in links:
        target = unquote((markdown or html).strip())
        if target.startswith("./"):
            target = target[2:]
        if _valid_path(target):
            result.add(target)
    return result


def _full_drawing_name(name):
    words = re.sub(r"[-_ ]+", " ", name.strip().casefold())
    return bool(re.fullmatch(r"(?:(?:full|complete|entire|project|board) )?"
                             r"(?:schematic(?: diagram)?|circuit diagram|회로도)", words))


def _schematic_captions(readme):
    result = set()
    for label, path in re.findall(r"\[([^\]\n]{0,180})\]\(\s*<?([^)\n>]+)>?\s*\)", readme):
        if _full_drawing_name(label):
            result.update(_readme_links(f"[{label}]({path})"))
    return result


def _documents_7805(readme):
    # Accept an explicit component description, excluding negated/unsupported variants.
    for sentence in re.split(r"[.!?;\n]", readme.casefold().replace("*", "")):
        if re.search(r"\b(?:not|no|unsupported|incompatible|instead|without)\b", sentence):
            continue
        if re.search(r"\blm7805\s+(?:(?:linear|voltage)\s+)*regulator\b|"
                     r"\b(?:regulator\s*[:|=]\s*|built around (?:the )?)lm7805\b", sentence):
            return True
    return False


def _matches_query(query, evidence, readme):
    if not query:
        return True
    # Korean particles often directly follow the model number; preserve part identifiers.
    phrase = re.sub(r"(?<=[a-z0-9])(?:으로|에서|의|을|를|은|는|이|가|로)(?=\s|$)", " ", query.casefold())
    purposes = {"전원 공급": "power supply", "전원공급": "power supply", "전원": "power",
                "전압 조정기": "voltage regulator", "레귤레이터": "regulator", "정류기": "rectifier",
                "개발 보드": "development board", "증폭기": "amplifier", "충전기": "charger"}
    for korean, english in purposes.items():
        phrase = phrase.replace(korean, english)
    phrase = re.sub(r"(?:회로도?|보여\s*줘|찾아\s*줘|보여\s*주세요|찾아\s*주세요)(?:를|을|의|는)?", " ", phrase)
    terms = re.findall(r"[^\W_]+(?:-[^\W_]+)*", phrase)
    terms = [t for t in terms if t not in {"a", "the", "for", "of", "schematic", "circuit"}]
    if not terms:
        return False
    placed = evidence.casefold()
    context = placed + "\n" + readme.casefold()
    # Allow standard part suffixes (ATtiny85-20PU, LM7805CT) and 5 V / 5V spellings.
    for term in terms:
        text = context
        quantity = re.fullmatch(r"(\d+)(mv|v|ma|a|hz|khz|mhz)", term)
        if quantity:
            pattern = quantity[1] + r"\s*" + quantity[2] + r"(?![a-z0-9])"
        elif re.search(r"[a-z]", term) and re.search(r"\d", term):
            text = placed
            pattern = re.escape(term) + r"(?!\d)"
            # A board README may identify an LM7805 using the KiCad L7805 symbol.
            if term == "lm7805" and _documents_7805(readme):
                pattern = r"(?:lm7805|l7805)(?!\d)"
        else:
            pattern = re.escape(term) + r"(?![a-z0-9])"
        if not re.search(r"(?<![a-z0-9])" + pattern, text):
            return False
    return True


def inspect_github_repository(repository: GitHubRepositoryRef, *, query: str = "",
                              client: httpx.Client | None = None) -> VerifiedSchematicSource | None:
    candidates = inspect_github_candidates(repository, query=query, client=client)
    return candidates[0] if candidates else None


def inspect_github_candidates(repository: GitHubRepositoryRef, *, query: str = "",
                              client: httpx.Client | None = None) -> tuple[VerifiedSchematicSource, ...]:
    if github_repository_ref(repository.repository_url) != repository:
        return ()
    if client is None:
        with httpx.Client(trust_env=False) as owned:
            return inspect_github_candidates(repository, query=query, client=owned)
    try:
        return _inspect(repository, query, client)
    except ExternalSchematicInvalidSource:
        return ()


def _inspect(ref, query, client):
    slug = f"{ref.owner}/{ref.repo}"
    api = f"https://api.github.com/repos/{slug}"
    cap = 256 * 1024
    metadata = _api(api, cap, client)
    license_data = metadata.get("license")
    license_id = license_data.get("spdx_id") if isinstance(license_data, dict) else None
    if not isinstance(license_id, str) or license_id not in ALLOWED_LICENSES or metadata.get("private") is True:
        return ()
    branch = metadata.get("default_branch")
    if not _valid_path(branch):
        return ()
    head = _api(f"{api}/commits/{quote(branch, safe='')}", cap, client)
    try:
        commit, tree_sha = head["sha"], head["commit"]["tree"]["sha"]
    except (KeyError, TypeError):
        raise ExternalSchematicUpstreamError() from None
    if any(not isinstance(s, str) or not _SHA.fullmatch(s) for s in (commit, tree_sha)):
        return ()
    files = _blobs(_api(f"{api}/git/trees/{tree_sha}?recursive=1", 2 * 1024**2, client))
    eda = sorted(p for p in files if p.lower().endswith((".kicad_sch", ".sch")))
    if not 1 <= len(eda) <= 20:
        return ()
    raw = f"https://raw.githubusercontent.com/{slug}/{commit}/"

    def fetch(path, limit):
        data, _ = download_bounded(raw + quote(path), max_bytes=limit, allowed_hosts=_RAW, client=client)
        try:
            return data.decode("utf-8-sig"), len(data)
        except UnicodeError:
            raise ExternalSchematicInvalidSource() from None

    graph, evidence, symbols = {}, [], {}
    has_wire = False
    remaining = 12 * 1024**2
    for path in eda:
        source, size = fetch(path, min(remaining, 4 * 1024**2))
        remaining -= size
        graph[path], placed_values, symbols[path], sheet_has_wire = _sheet_data(path, source)
        has_wire |= sheet_has_wire
        evidence.extend(placed_values)
    root, sheet_count = _root(graph)
    # Count placements in each sheet instance, including repeated children.
    pending, placed = [root], 0
    while pending:
        sheet = pending.pop()
        placed += symbols[sheet]
        pending.extend(graph[sheet])
    if placed < 2 or not has_wire:
        return ()
    readme = ""
    readme_path = next((p for p in sorted(files) if p.casefold() in {"readme", "readme.md", "readme.rst"}), None)
    if readme_path:
        readme, _ = fetch(readme_path, cap)
    part_evidence = " ".join(evidence)
    if not _matches_query(query, part_evidence, readme):
        return ()
    linked = _readme_links(readme)
    captioned = _schematic_captions(readme)
    assets = []
    root_path = PurePosixPath(root)
    for path in files:
        file = PurePosixPath(path)
        kind = file.suffix.lower().lstrip(".")
        if kind not in {"png", "svg", "pdf"}:
            continue
        if sheet_count > 1 and kind != "pdf":
            continue
        stem = file.stem.casefold()
        same_stem = stem == root_path.stem.casefold()
        same_root_pdf = kind == "pdf" and same_stem and file.parent == root_path.parent
        # KiCad projects often keep both the schematic and the PCB in a folder named PCB.
        checked_path = path
        if same_root_pdf:
            checked_path = "/".join([p for p in file.parent.parts if p.casefold() != "pcb"] + [file.name])
        if _EXCLUDED.search(checked_path):
            continue
        # A PDF beside the root EDA file is the project's exported original
        # schematic even when its basename is a board name.
        named = same_root_pdf
        if not named:
            named = _full_drawing_name(stem)
        if not named:
            # A matched EDA/project stem can prefix an explicit schematic designation.
            for prefix in {root_path.stem.casefold(), ref.repo.casefold()}:
                if stem.startswith(prefix) and stem[len(prefix):len(prefix)+1] in {"-", "_", " "}:
                    named = _full_drawing_name(stem[len(prefix)+1:])
                    if named:
                        break
        if path in captioned and not re.search(r"schematic|circuit[-_ ]?diagram", stem):
            named = True
        paired = same_stem or file.parent == root_path.parent or path in linked
        if named and paired:
            assets.append((("pdf", "png", "svg").index(kind), not same_root_pdf, len(file.parts),
                           path.casefold(), kind, path))
    def candidate(kind, paths):
        return VerifiedSchematicSource(slug, commit, license_id, slug + " contributors", ref.repository_url,
                                       f"{ref.repository_url}/tree/{commit}", root, kind, paths, root,
                                       expected_sheets=sheet_count)

    # Keep one preferred asset per format and the original EDA as the final fallback.
    formats = {}
    for *_, kind, asset in sorted(assets):
        if kind not in formats:
            formats[kind] = candidate(kind, (asset,))
    return (*formats.values(), candidate("kicad", ()))
