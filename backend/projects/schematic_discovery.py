"""GitHub의 고정 commit에서 회로 원본과 짝지어진 공개 도면을 확인한다."""
import ipaddress
import json
import os
import re
import socket
import time
from hashlib import sha256
from pathlib import PurePosixPath
from urllib.parse import quote, unquote, urljoin, urlsplit

import httpx

from .external_schematic import _Cache

from .external_circuit_search import (
    GitHubRepositoryRef, github_repository_ref, read_bounded_body, safe_public_https_url,
)
from .schematic_source import (
    ALLOWED_LICENSES, ExternalSchematicConfigurationError, ExternalSchematicInvalidSource,
    ExternalSchematicRateLimited, ExternalSchematicUpstreamError, VerifiedSchematicSource,
    normalize_license_id,
    provider_rate_limit, remember_provider_limit,
)

# Match the renderer's bounded selected-hierarchy input limit. This remains a
# repository-wide cap; file and sheet limits below still apply independently.
MAX_DISCOVERY_BYTES = 25 * 1024**2

_API = frozenset({"api.github.com"})
_RAW = frozenset({"raw.githubusercontent.com"})
_DOWNLOAD_HOSTS = _API | _RAW | {"codeload.github.com"}
_SHA = re.compile(r"[a-fA-F0-9]{40}")
_GITHUB_API_CACHE = _Cache(128, 16 * 1024**2, lambda entry: entry[1], 900, time.monotonic)
_EXCLUDED = re.compile(r"datasheet|application[-_ ]?note|block[-_ ]?diagram|(?:^|[/_. -])(?:pcb|layout|renders?|rendering|3d|photo|preview|partial|detail|pinout|old|deprecated|obsolete|draft|backup|archive|archived|stage|excerpt|subsystem|section|fragment)(?:$|[/_. -])", re.I)
_CERN_SHORT_NOTICE = re.compile(
    r"^CERN Open Hardware Licence Version 2\s*[–-]\s*"
    r"(?:Permissive|Weakly Reciprocal|Strongly Reciprocal)\s*"
    r"\(CERN-OHL-(?:P|W|S)-2\.0\)\s+Copyright\s+\(c\)\s+[^\r\n]+$",
    re.I,
)


def _public_addresses(host: str) -> tuple[str, ...]:
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or not all(ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        return ()
    return tuple(dict.fromkeys(a[4][0] for a in addresses))


def _retry_after(headers: httpx.Headers) -> int:
    try:
        if "retry-after" in headers:
            return min(3600, max(1, int(headers["retry-after"])))
        return min(3600, max(1, int(headers["x-ratelimit-reset"]) - int(time.time())))
    except (ValueError, KeyError):
        return 60


def download_bounded(url: str, *, max_bytes: int, allowed_hosts: frozenset[str],
                     client: httpx.Client | None = None,
                     phase: str = "download", deadline_seconds: float | None = None) -> tuple[bytes, str]:
    """Only the API receives credentials. Never follow redirects to a different resource.

    deadline_seconds: 리다이렉트 · 본문 읽기를 합친 전체 시간 상한(넘으면 ExternalSchematicUpstreamError). httpx timeout은 읽기 한 번마다라
    느리게 흘리는 서버가 스레드를 오래 붙잡을 수 있다(점검 A #7). 기본은 마감 없음이라 기존 호출은 그대로다.
    """
    if client is None:
        with httpx.Client(trust_env=False) as owned:
            return download_bounded(url, max_bytes=max_bytes, allowed_hosts=allowed_hosts, client=owned,
                                    phase=phase, deadline_seconds=deadline_seconds)
    original = urlsplit(url)
    deadline = None if deadline_seconds is None else time.monotonic() + deadline_seconds
    try:
        for _ in range(4):
            if deadline is not None and time.monotonic() > deadline:
                raise TimeoutError("deadline")
            if not safe_public_https_url(url, allowed_hosts=allowed_hosts):
                raise ExternalSchematicInvalidSource()
            parsed = urlsplit(url)
            if limited := provider_rate_limit(parsed.hostname):
                raise limited
            # Resolve once and connect to that inspected public address. Host and
            # TLS SNI retain the original hostname for certificate verification.
            mock = isinstance(client._transport, httpx.MockTransport)
            request_url = url
            extensions = None
            if not mock:
                addresses = _public_addresses(parsed.hostname)
                if not addresses:
                    raise ExternalSchematicInvalidSource()
                address = next((ip for ip in addresses if ":" not in ip), addresses[0])
                request_url = parsed._replace(netloc=f"[{address}]" if ":" in address else address).geturl()
                extensions = {"sni_hostname": parsed.hostname}
            if (parsed.path, parsed.query) != (original.path, original.query) or parsed.fragment:
                raise ExternalSchematicInvalidSource()
            headers = {"Accept-Encoding": "identity"}
            if phase == "public_asset":
                headers["User-Agent"] = "SojaFit/1.0 (schematic viewer)"
            if not mock:
                headers["Host"] = parsed.hostname
            if parsed.hostname in _API:
                headers.update({"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"})
                if token := os.getenv("GITHUB_TOKEN", "").strip():
                    headers["Authorization"] = f"Bearer {token}"
            with client.stream("GET", request_url, headers=headers, extensions=extensions,
                               timeout=15, follow_redirects=False) as response:
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
                    limited = ExternalSchematicRateLimited(
                        _retry_after(response.headers), host=parsed.hostname,
                        phase=phase, status_code=response.status_code,
                    )
                    remember_provider_limit(limited)
                    raise limited
                if response.status_code == 401 and parsed.hostname in _API:
                    raise ExternalSchematicConfigurationError()
                if response.status_code in {404, 410, 451}:
                    raise ExternalSchematicInvalidSource()
                response.raise_for_status()
                try:
                    data = read_bounded_body(response, max_bytes, deadline=deadline)
                except ValueError:
                    raise ExternalSchematicInvalidSource() from None
                return data, response.headers.get("content-type", "").partition(";")[0].strip().lower()
        raise ExternalSchematicInvalidSource()
    except (httpx.HTTPError, OSError, ValueError):
        raise ExternalSchematicUpstreamError() from None


def _api(url, cap, client):
    def produce():
        data, _ = download_bounded(url, max_bytes=cap, allowed_hosts=_API, client=client,
                                    phase="github_api")
        try:
            value = json.loads(data)
            if not isinstance(value, dict):
                raise ValueError()
            return value, len(data)
        except (ValueError, RecursionError):
            raise ExternalSchematicUpstreamError() from None

    if isinstance(client._transport, httpx.MockTransport):
        return produce()[0]
    credential = sha256(os.getenv("GITHUB_TOKEN", "").strip().encode()).digest()
    return _GITHUB_API_CACHE.get((url, cap, credential), produce)[0]


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
_REFERENCE = re.compile(r'\s+"Reference"\s+"([^"\\]{1,64})"')
_UUID = re.compile(r'\s+"?([0-9a-fA-F-]{8,64})"?')
_FILE = re.compile(r'\s+"Sheet\s*file"\s+"([^"\\]{1,1024})"', re.I)


_NUMBER = r"(-?\d{1,12}(?:\.\d{1,12})?)"
_WIRE_POINTS = re.compile(r"\s+\(xy\s+" + _NUMBER + r"\s+" + _NUMBER +
                          r"\)\s+\(xy\s+" + _NUMBER + r"\s+" + _NUMBER + r"\)\s*\)")
_LEGACY_WIRE_POINTS = re.compile(r"\s*" + r"\s+".join([_NUMBER] * 4) + r"\s*")

# KiCad's generic Device:D symbols carry the actual part number in Value.  Do
# not require a diode-specific library id for those symbols: Device:D,
# Device:D_Small, Device:D_Schottky, and Device:D_Zener are all normal placed
# diode symbols.  The exclusions are intentional so an LED/photodiode cannot
# become a diode merely because its reference starts with D.
_DIODE_VALUE_EXCLUDED = re.compile(r"(?:^|[^a-z0-9])(?:led|photo(?:diode)?|photodiode)(?:$|[^a-z0-9])", re.I)
_DIODE_LIBRARY_EXCLUDED = re.compile(
    r"(?:^|[:_])(?:led|photo(?:diode)?|photodiode|laser(?:diode)?)(?:$|[:_])", re.I,
)


def _is_placed_diode(reference, value, library):
    if not re.fullmatch(r"d\d+", reference.casefold()):
        return False
    lib_name = library.rsplit(":", 1)[-1].casefold()
    if _DIODE_VALUE_EXCLUDED.search(value) or _DIODE_LIBRARY_EXCLUDED.search(library):
        return False
    if re.search(r"(?:diode|schottky|rectifier|zener)", library, re.I):
        return True
    # Generic KiCad Device:D variants are classified by their symbol name,
    # while D_Photo/D_LED remain explicitly excluded above.
    if lib_name == "d" or (lib_name.startswith("d_") and not re.search(
            r"(?:led|photo|laser)", lib_name, re.I)):
        return True
    # Keep support for legacy symbols whose library name itself is SS33/SS34.
    # The Value field alone is never enough: a resistor can be labelled SS33.
    return bool(re.fullmatch(r"ss\d+[a-z0-9-]*", lib_name))


def _nonzero_segment(match):
    if not match:
        return False
    x1, y1, x2, y2 = map(float, match.groups())
    return (x1, y1) != (x2, y2)


def _embedded_diode(source):
    """Classify a custom library definition by its description and electrical pins."""
    from backend.graph.netlist import _sexpr

    try:
        normalized = re.sub(r'"(?:\\.|[^"\\])*"',
                            lambda m: json.dumps(json.loads(m[0], strict=False)), source)
        symbol = _sexpr(normalized)
    except (ValueError, RecursionError):
        return None
    if len(symbol) < 2 or not isinstance(symbol[1], str):
        return None
    description = " ".join(item[2] for item in symbol[2:]
                           if isinstance(item, list) and len(item) >= 3
                           and item[0] == "property" and isinstance(item[1], str)
                           and item[1] in {"Description", "ki_keywords"}
                           and isinstance(item[2], str))
    if (not re.search(r"\b(?:diode|schottky|rectifier|zener)\b", description, re.I)
            or re.search(r"led|photo|laser", description, re.I)
            or _DIODE_LIBRARY_EXCLUDED.search(symbol[1])):
        return None
    pins = []
    pending = [symbol]
    while pending:
        node = pending.pop()
        if node and node[0] == "pin":
            if len(node) < 2 or not isinstance(node[1], str) or node[1] not in {"passive", "no_connect"}:
                return None
            if node[1] == "passive":
                names = [x[1] for x in node if isinstance(x, list) and len(x) >= 2
                         and x[0] == "name" and isinstance(x[1], str)]
                if len(names) != 1:
                    return None
                pins.append(names[0].casefold())
        pending.extend(x for x in node if isinstance(x, list))
    anodes = {"a", "anode"}
    cathodes = {"k", "c", "cathode"}
    if len(pins) != 2 or not (set(pins) & anodes) or not (set(pins) & cathodes):
        return None
    return symbol[1]


def _sheet_data(path, source):
    """Read placed components and direct child sheets; embedded symbol libraries are not instances."""
    children, values = [], []
    count = 0
    child_start = 0
    symbols = 0
    has_wire = False
    instances = []
    embedded_diodes = set()
    library_start = 0
    instance_start = 0
    instance_values = {}
    current_ref = current_value = current_lib = current_uuid = None
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
                if stack == ["kicad_sch", "symbol_instances", "path"]:
                    from backend.graph.netlist import _sexpr
                    try:
                        block = source[instance_start:token.end()]
                        block = re.sub(r'"(?:\\.|[^"\\])*"',
                                       lambda m: json.dumps(json.loads(m[0], strict=False)), block)
                        node = _sexpr(block)
                        if len(node) < 2 or not isinstance(node[1], str):
                            raise ValueError()
                        key = node[1].rsplit("/", 1)[-1].casefold()
                        fields = {x[0]: x[1] for x in node[2:] if isinstance(x, list)
                                  and len(x) == 2 and x[0] in {"reference", "value"}}
                        value = (fields["reference"], fields["value"])
                        if (not re.fullmatch(r"[0-9a-f-]{8,64}", key)
                                or not all(isinstance(item, str) for item in value)
                                or (key in instance_values and instance_values[key] != value)):
                            raise ValueError()
                        instance_values[key] = value
                    except (ValueError, TypeError, KeyError, IndexError):
                        raise ExternalSchematicInvalidSource() from None
                if stack == ["kicad_sch", "lib_symbols", "symbol"]:
                    if library := _embedded_diode(source[library_start:token.end()]):
                        embedded_diodes.add(library)
                if stack == ["kicad_sch", "sheet"] and len(children) != child_start + 1:
                    raise ExternalSchematicInvalidSource()
                if stack == ["kicad_sch", "symbol"] and current_ref:
                    instances.append((current_ref, current_value or "", current_lib or "", current_uuid))
                if not stack or stack.pop() is None:
                    raise ExternalSchematicInvalidSource()
                finished = not stack
            elif not stack or part == '"':
                raise ExternalSchematicInvalidSource()
            elif stack[-1] is None:
                stack[-1] = part
                if stack == ["kicad_sch", "symbol_instances", "path"]:
                    instance_start = source.rfind("(", 0, token.start())
                if stack == ["kicad_sch", "lib_symbols", "symbol"]:
                    library_start = source.rfind("(", 0, token.start())
                if len(stack) == 1 and part != "kicad_sch":
                    raise ExternalSchematicInvalidSource()
                if len(stack) == 2 and part == "symbol":
                    symbols += 1
                    current_ref = current_value = current_lib = current_uuid = None
                if stack == ["kicad_sch", "wire", "pts"]:
                    has_wire |= _nonzero_segment(_WIRE_POINTS.match(source, token.end()))
                if len(stack) == 2 and part == "sheet":
                    count += 1
                    child_start = len(children)
                if len(stack) == 3 and part == "lib_id" and stack[1] == "symbol":
                    if match := re.match(r'\s+"([^"\\]{1,256})"', source[token.end():token.end()+260]):
                        lib = match[1].rsplit(":", 1)[-1]
                        values.append(lib)
                        if len(stack) == 3 and stack[0] == "kicad_sch":
                            current_lib = match[1]
                if len(stack) == 3 and part == "uuid" and stack[1] == "symbol":
                    if match := _UUID.match(source, token.end()):
                        current_uuid = match[1].casefold()
                if len(stack) == 3 and part == "property" and stack[1] in {"symbol", "sheet"}:
                    pattern = _VALUE if stack[1] == "symbol" else _FILE
                    if match := pattern.match(source, token.end()):
                        (values if stack[1] == "symbol" else children).append(match[1])
                    if stack == ["kicad_sch", "symbol", "property"]:
                        ref = _REFERENCE.match(source, token.end())
                        value = _VALUE.match(source, token.end())
                        if ref:
                            current_ref = ref[1]
                        if value:
                            current_value = value[1]
        if not finished:
            raise ExternalSchematicInvalidSource()
    else:
        if not source.startswith("EESchema Schematic File Version ") or not source.rstrip().endswith("$EndSCHEMATC"):
            raise ExternalSchematicInvalidSource()
        active = ""
        wire_points_next = False
        legacy_reference = legacy_value = legacy_lib = None
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
                if line == "$Comp":
                    legacy_reference = legacy_value = legacy_lib = None
                child_start = len(children)
            elif line in {"$EndSheet", "$EndComp"}:
                if active == "$Sheet" and len(children) != child_start + 1:
                    raise ExternalSchematicInvalidSource()
                if active != line.replace("$End", "$"):
                    raise ExternalSchematicInvalidSource()
                if active == "$Comp" and legacy_reference and legacy_value:
                    instances.append((legacy_reference, legacy_value or "", legacy_lib or "", None))
                active = ""
            elif active == "$Sheet" and (match := re.match(r'^F1\s+"([^"\\]+)"', line)):
                children.append(match[1])
            elif active == "$Comp" and line.startswith("L "):
                fields = line.split()
                if len(fields) == 3:
                    legacy_lib = fields[1]
                    values.append(legacy_lib.rsplit(":", 1)[-1])
            elif active == "$Comp" and (match := re.match(r'^F 0 "([^"]+)"', line)):
                legacy_reference = match[1]
            elif active == "$Comp" and (match := re.match(r'^F 1 "([^"]+)"', line)):
                legacy_value = match[1]
                values.append(legacy_value)
        if active:
            raise ExternalSchematicInvalidSource()
    if not (values or children) or len(children) != count or not all(_valid_path(ref) for ref in children):
        raise ExternalSchematicInvalidSource()
    for reference, value, prefix, placed_uuid in instances:
        fallback = instance_values.get(placed_uuid.casefold()) if placed_uuid else None
        if fallback and fallback[0] == reference and fallback[1]:
            if value and value != fallback[1]:
                raise ExternalSchematicInvalidSource()
            if not value:
                value = fallback[1]
        if not value:
            continue
        if (_is_placed_diode(reference, value, prefix)
                or (prefix in embedded_diodes and _is_placed_diode(reference, value, "Device:D"))):
            values.append(f"diode:{value.casefold()}")
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
    query = re.sub(r'(?<=[a-z0-9])(?=[A-Z][a-z])', ' ', query)
    readme = re.sub(r'(?<=[a-z0-9])(?=[A-Z][a-z])', ' ', readme)
    query = re.sub(r'\btiny(?=\d+\b)', 'ATtiny', query, flags=re.I)
    query = re.sub(r'\bdev(?=\s+board\b)', 'development', query, flags=re.I)
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
    # Keywords may be prefixes; numeric models still require placed components.
    for term in terms:
        text = context
        quantity = re.fullmatch(r"(\d+)(mv|v|ma|a|hz|khz|mhz)", term)
        if quantity:
            pattern = quantity[1] + r"\s*" + quantity[2] + r"(?![a-z0-9])"
        elif re.search(r"[a-z]", term) and re.search(r"\d", term):
            text = placed
            pattern = re.escape(term) + (r"(?!\d)" if len(term) < 3 else "")
            # A board README may identify an LM7805 using the KiCad L7805 symbol.
            if term == "lm7805" and _documents_7805(readme):
                pattern = r"(?:lm7805|l7805)(?!\d)"
        else:
            pattern = re.escape(term) + (r"(?![a-z0-9])" if len(term) < 3 else "")
        if not re.search(r"(?<![a-z0-9])" + pattern, text):
            return False
    if "diode" in terms:
        model_terms = [t for t in terms if t != "diode" and re.search(r"[a-z]", t) and re.search(r"\d", t)]
        if model_terms and not any(re.search(r"diode:" + re.escape(t) + (r"(?:[^a-z0-9]|$)" if len(t) < 3 else ""), placed) for t in model_terms):
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


def _select_query_root(graph, evidence_by_path, symbols, wires, query, readme):
    """Find complete matching hierarchies without mixing independent projects."""
    children = set().union(*graph.values()) if graph else set()
    roots = sorted(set(graph) - children)
    if not roots:
        raise ExternalSchematicInvalidSource()
    # A repository root may contain an unrelated broken sibling. Try complete
    # nested hierarchies as well, while preferring a complete matching parent
    # when one exists so the same child is not returned twice.
    matches = []
    candidates = roots + sorted(set(graph) - set(roots))
    for candidate in candidates:
        visited = set()

        def walk(node, active):
            if node in active or node not in graph:
                raise ExternalSchematicInvalidSource()
            if node in visited:
                return
            visited.add(node)
            for child in graph[node]:
                walk(child, active | {node})

        try:
            walk(candidate, set())
            _, count = _root({node: graph[node] for node in visited})
        except ExternalSchematicInvalidSource:
            continue
        placed = sum(symbols[node] for node in visited)
        has_wire = any(wires[node] for node in visited)
        evidence = " ".join(value for node in visited for value in evidence_by_path[node])
        if placed >= 2 and has_wire and _matches_query(query, evidence, readme):
            matches.append((candidate, count, frozenset(visited)))
    if not matches:
        raise ExternalSchematicInvalidSource()
    complete = []
    for match in matches:
        if any(match[2] < other[2] for other in matches):
            continue
        complete.append(match)
    return tuple(complete)


def _short_cern_license(license_text, readme):
    """Accept only the repository's structured short CERN-OHL declaration."""
    lines = [line.strip() for line in license_text.replace("\r\n", "\n").split("\n") if line.strip()]
    if len(lines) != 3:
        return None
    notice = " ".join(lines[:2]) + " " + lines[2]
    match = _CERN_SHORT_NOTICE.fullmatch(notice)
    if not match:
        return None
    license_id = re.search(r"\((CERN-OHL-[PWS]-2\.0)\)", notice, re.I)[1].upper()
    names = {"P": "Permissive", "W": "Weakly Reciprocal", "S": "Strongly Reciprocal"}
    expected = f"CERN Open Hardware Licence Version 2 - {names[license_id[9]]}"
    if lines[0].replace("–", "-").casefold() != expected.casefold():
        return None
    if re.search(r"non.?commercial|all rights reserved|additional terms|no derivatives|proprietary", notice, re.I):
        return None
    scope = re.sub(r"\s+", " ", re.sub(r"[`*_]", "", readme)).casefold()
    if re.search(r"non.?commercial|commercial.{0,30}prohibited|no derivatives|additional terms|proprietary|all rights reserved", scope):
        return None
    declaration = (r"all hardware design files(?:\s*\([^)]{0,300}\))?\s+are licensed under (?:the )?"
                   r"(?:cern open hardware licence version 2\s*[–-]\s*"
                   + re.escape(names[license_id[9]].casefold()) + r"\s*\()?"
                   + re.escape(license_id.casefold()) + r"\)?\.")
    if not re.search(declaration, scope):
        return None
    return license_id


def _inspect(ref, query, client):
    slug = f"{ref.owner}/{ref.repo}"
    api = f"https://api.github.com/repos/{slug}"
    cap = 256 * 1024
    metadata = _api(api, cap, client)
    # GitHub preserves repository casing in archive roots; use its canonical name.
    canonical = metadata.get("full_name")
    if isinstance(canonical, str):
        actual = github_repository_ref(f"https://github.com/{canonical}")
        if actual is None or actual.repository_url.casefold() != ref.repository_url.casefold():
            return ()
        ref = actual
        slug = f"{ref.owner}/{ref.repo}"
        api = f"https://api.github.com/repos/{slug}"
    license_data = metadata.get("license")
    license_id = normalize_license_id(license_data.get("spdx_id")
                                     if isinstance(license_data, dict) else None)
    metadata_license_unknown = license_id == "NOASSERTION"
    if (not isinstance(license_id, str)
            or (license_id not in ALLOWED_LICENSES and not metadata_license_unknown)
            or metadata.get("private") is True):
        return ()
    branch = metadata.get("default_branch")
    if not _valid_path(branch):
        return ()
    # The commits endpoint can include a large commit object and exceed the
    # bounded metadata response. The branch endpoint returns the same pinned
    # commit/tree SHAs in a compact response.
    head = _api(f"{api}/branches/{quote(branch, safe='')}", cap, client)
    try:
        commit = head["commit"]["sha"]
        tree_sha = head["commit"]["commit"]["tree"]["sha"]
    except (KeyError, TypeError):
        raise ExternalSchematicUpstreamError() from None
    if any(not isinstance(s, str) or not _SHA.fullmatch(s) for s in (commit, tree_sha)):
        return ()
    files = _blobs(_api(f"{api}/git/trees/{tree_sha}?recursive=1", 2 * 1024**2, client))
    eda = sorted((p for p in files if p.lower().endswith((".kicad_sch", ".sch"))),
                 key=lambda p: (not p.lower().endswith(".kicad_sch"), p))
    if not 1 <= len(eda) <= 128:
        return ()
    raw = f"https://raw.githubusercontent.com/{slug}/{commit}/"

    def fetch(path, limit):
        data, _ = download_bounded(raw + quote(path), max_bytes=limit, allowed_hosts=_RAW,
                                    client=client, phase="github_raw")
        try:
            return data.decode("utf-8-sig"), len(data)
        except UnicodeError:
            raise ExternalSchematicInvalidSource() from None

    graph, evidence, evidence_by_path, symbols, wires = {}, [], {}, {}, {}
    has_wire = False
    remaining = MAX_DISCOVERY_BYTES
    for path in eda:
        if remaining <= 0:
            if query:
                break
            raise ExternalSchematicInvalidSource()
        file_cap = min(remaining, 4 * 1024**2)
        try:
            source, size = fetch(path, file_cap)
        except ExternalSchematicInvalidSource:
            if not query:
                raise
            # A failed/partial read must still consume its worst-case budget.
            remaining -= file_cap
            continue
        remaining -= size
        try:
            child_paths, placed_values, placed_count, sheet_has_wire = _sheet_data(path, source)
        except ExternalSchematicInvalidSource:
            if not query:
                raise
            continue
        graph[path] = child_paths
        symbols[path] = placed_count
        evidence_by_path[path] = placed_values
        wires[path] = sheet_has_wire
        has_wire |= sheet_has_wire
        evidence.extend(placed_values)
    readme = ""
    readme_path = next((p for p in sorted(files) if p.casefold() in {"readme", "readme.md", "readme.rst"}), None)
    if readme_path:
        readme, _ = fetch(readme_path, cap)
    license_path = next((p for p in sorted(files)
                         if p.casefold() in {"license", "license.md", "license.txt"}), None)
    license_evidence_url = None
    if metadata_license_unknown:
        if not license_path or not readme:
            return ()
        license_text, _ = fetch(license_path, cap)
        license_id = _short_cern_license(license_text, readme)
        if license_id not in ALLOWED_LICENSES:
            return ()
    if license_path:
        license_evidence_url = f"{raw}{quote(license_path)}"
    part_evidence = " ".join(evidence)
    if query:
        selections = _select_query_root(
            graph, evidence_by_path, symbols, wires, query, readme)
    else:
        root, sheet_count = _root(graph)
        selected_paths = frozenset(graph)
        pending, placed = [root], 0
        while pending:
            sheet = pending.pop()
            placed += symbols[sheet]
            pending.extend(graph[sheet])
        if placed < 2 or not has_wire:
            return ()
        if not _matches_query(query, part_evidence, readme):
            return ()
        selections = ((root, sheet_count, selected_paths),)
    linked = _readme_links(readme)
    captioned = _schematic_captions(readme)
    def sources_for(root, sheet_count, selected_paths):
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
            checked_path = path
            if same_root_pdf:
                checked_path = "/".join([p for p in file.parent.parts if p.casefold() != "pcb"] + [file.name])
            if _EXCLUDED.search(checked_path):
                continue
            named = same_root_pdf or _full_drawing_name(stem)
            if not named:
                for prefix in {root_path.stem.casefold(), ref.repo.casefold()}:
                    if stem.startswith(prefix) and stem[len(prefix):len(prefix)+1] in {"-", "_", " "}:
                        named = _full_drawing_name(stem[len(prefix)+1:])
                        if named:
                            break
            if path in captioned and not re.search(r"schematic|circuit[-_ ]?diagram", stem):
                named = True
            paired = same_stem or file.parent == root_path.parent or path in linked
            if len(selections) > 1:
                paired = file.parent == root_path.parent and same_stem
            if named and paired:
                assets.append((("pdf", "png", "svg").index(kind), not same_root_pdf, len(file.parts),
                               path.casefold(), kind, path))
        def candidate(kind, paths):
            return VerifiedSchematicSource(slug, commit, license_id, slug + " contributors", ref.repository_url,
                                           f"{ref.repository_url}/blob/{commit}/{quote(root)}", root, kind, paths, root,
                                           expected_sheets=sheet_count, license_evidence_url=license_evidence_url)

        formats = {}
        for *_, kind, asset in sorted(assets):
            if kind not in formats:
                formats[kind] = candidate(kind, (asset,))
        if all(PurePosixPath(path).suffix.casefold() == ".kicad_sch" for path in selected_paths):
            formats["kicad"] = candidate("kicad", tuple(sorted(selected_paths)))
        return tuple(formats.values())

    return tuple(source for selection in selections for source in sources_for(*selection))
