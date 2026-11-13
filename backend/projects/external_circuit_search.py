"""Exa의 외부 자료 후보를 반환한다. 다운로드, 파일 저장, DB 변경은 수행하지 않는다."""
import ipaddress
import json
import os
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx


class ExternalCircuitSearchError(RuntimeError):
    """응답 본문이나 인증 정보를 포함하지 않는 외부 검색 오류."""


class ExternalCircuitSearchDisabled(ExternalCircuitSearchError):
    """명시적으로 활성화되지 않은 검색 요청."""


class ExternalCircuitSearchConfigurationError(ExternalCircuitSearchError):
    """외부 검색 인증 설정 누락."""


PROJECT_RESERVED_PATHS = {
    "github.com": frozenset({"features", "topics", "explore", "marketplace", "settings", "orgs", "users", "login", "signup"}),
    "gitlab.com": frozenset({"explore", "users", "groups", "help", "dashboard", "projects", "admin", "login"}),
    "codeberg.org": frozenset({"explore", "users", "user", "groups", "help", "dashboard", "projects", "admin", "login"}),
}


def _safe_url(value: object) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    if any(char.isspace() or ord(char) < 32 for char in value):
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if parsed.scheme not in {"http", "https"} or not host or parsed.username is not None or parsed.password is not None:
            return None
        if parsed.port is not None and parsed.port != {"http": 80, "https": 443}[parsed.scheme]:
            return None
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")) or "." not in host:
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            # Numeric legacy IPv4 spellings can resolve to loopback/private addresses.
            if re.fullmatch(r"[0-9.]+|0x[0-9a-f]+", host, re.IGNORECASE):
                return None
            if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host, re.IGNORECASE):
                return None
        return value
    except ValueError:
        return None


def _require_external_search_configuration() -> str:
    if os.getenv("EXA_WEB_SEARCH_ENABLED") != "1" or os.getenv("DEMO_MODE") != "0":
        raise ExternalCircuitSearchDisabled("외부 회로 검색이 비활성화되어 있습니다.")
    api_key = os.getenv("EXA_API_KEY", "").strip()
    if not api_key:
        raise ExternalCircuitSearchConfigurationError("외부 회로 검색 인증 설정이 필요합니다.")
    return api_key


@dataclass(frozen=True)
class GitHubRepositoryRef:
    owner: str
    repo: str
    repository_url: str


@dataclass(frozen=True)
class WebSchematicRef:
    """검색어로 발견한 공개 회로도 파일과 게시 페이지의 관계."""
    source_url: str
    page_url: str
    source_file: str
    asset_kind: str
    title: str
    attribution: str
    source_type: str = "public_web"
    evidence_grade: int | None = None
    manufacturer: str | None = None
    model: str | None = None
    revision: str | None = None
    license: str = "미확인"
    license_evidence_url: str | None = None
    source_sha256: str | None = None


def safe_public_https_url(value: object, *, allowed_hosts: frozenset[str]) -> str | None:
    url = _safe_url(value)
    if url is None:
        return None
    parsed = urlsplit(url)
    return url if parsed.scheme == "https" and parsed.hostname in allowed_hosts else None


def github_repository_ref(value: object) -> GitHubRepositoryRef | None:
    url = safe_public_https_url(value, allowed_hosts=frozenset({"github.com"}))
    if not url:
        return None
    parts = urlsplit(url)
    match = re.fullmatch(r"/([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+)/?", parts.path)
    if not match or parts.query or parts.fragment:
        return None
    owner, repo = match[1], match[2].removesuffix(".git")
    if owner.lower() in PROJECT_RESERVED_PATHS["github.com"] or repo in {"", ".", ".."}:
        return None
    return GitHubRepositoryRef(owner, repo, f"https://github.com/{owner}/{repo}")


def read_bounded_body(response: httpx.Response, max_bytes: int) -> bytes:
    """Read an identity-encoded response without decompressing untrusted content."""
    length = response.headers.get("content-length")
    if length is not None and not 0 <= int(length) <= max_bytes:
        raise ValueError("invalid length")
    if response.headers.get("content-encoding", "identity").lower() != "identity":
        raise ValueError("unexpected encoding")
    chunks = [response.content] if response.is_stream_consumed else response.iter_raw()
    data = bytearray()
    for chunk in chunks:
        if len(data) + len(chunk) > max_bytes:
            raise ValueError("response too large")
        data.extend(chunk)
    return bytes(data)


_WEB_ASSET_KIND = {".pdf": "pdf", ".png": "png", ".svg": "svg"}
_SCHEMATIC_WORDS = re.compile(r"(?:schematic|schem|(?:^|[_-])sch(?=$|[_./-])|circuit[-_ ]?(?:diagram|drawing)|회로도)", re.I)
_BAD_IMAGE_WORDS = re.compile(r"(?:photo|product|render|layout|footprint|pcb|fab|board[-_ ]?top|wiring|breadboard|hero|logo)", re.I)
_OFFICIAL_MANUFACTURERS = {
    "sparkfun.com": "SparkFun Electronics",
    "adafruit.com": "Adafruit Industries",
    "seeedstudio.com": "Seeed Studio",
    "arduino.cc": "Arduino",
    "pololu.com": "Pololu",
    "olimex.com": "Olimex",
    "raspberrypi.com": "Raspberry Pi",
    "pjrc.com": "PJRC",
}
_OFFICIAL_PUBLISHER_HOSTS = {
    "sparkfun.com": frozenset({"sparkfun.com", "www.sparkfun.com", "learn.sparkfun.com", "cdn.sparkfun.com"}),
    "adafruit.com": frozenset({"adafruit.com", "www.adafruit.com", "learn.adafruit.com", "cdn-learn.adafruit.com"}),
    "seeedstudio.com": frozenset({"seeedstudio.com", "www.seeedstudio.com", "wiki.seeedstudio.com", "files.seeedstudio.com"}),
    "arduino.cc": frozenset({"arduino.cc", "www.arduino.cc", "docs.arduino.cc", "content.arduino.cc"}),
    "pololu.com": frozenset({"pololu.com", "www.pololu.com"}),
    "olimex.com": frozenset({"olimex.com", "www.olimex.com"}),
    "raspberrypi.com": frozenset({"raspberrypi.com", "www.raspberrypi.com", "docs.raspberrypi.com", "pip.raspberrypi.com", "pip-assets.raspberrypi.com"}),
    "pjrc.com": frozenset({"pjrc.com", "www.pjrc.com"}),
}
_MANUFACTURER_ALIASES = {
    "sparkfun.com": ("sparkfun",),
    "adafruit.com": ("adafruit",),
    "seeedstudio.com": ("seeed", "xiao"),
    "arduino.cc": ("arduino",),
    "pololu.com": ("pololu",),
    "olimex.com": ("olimex",),
    "raspberrypi.com": ("raspberry pi", "raspberrypi"),
    "pjrc.com": ("teensy", "pjrc"),
}
_OFFICIAL_GITHUB_OWNERS = {
    "olimex.com": frozenset({"olimex"}),
}


class _SchematicPageParser(HTMLParser):
    """페이지에 공개된 회로도 링크만 수집한다. 스크립트는 해석하지 않는다."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._heading: list[str] = []
        self._heading_active = False
        self._title: list[str] = []
        self._title_active = False
        self._anchor: tuple[str, list[str]] | None = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading = []
            self._heading_active = True
        if tag == "title":
            self._title = []
            self._title_active = True
        if tag == "a" and values.get("href"):
            self._anchor = (values["href"], [])
        for key in ("href", "src", "data-src"):
            value = values.get(key)
            if value and tag != "a":
                self.links.append((value, " ".join([*self._heading, *self._title, values.get("alt") or ""]).strip()))
        srcset = values.get("srcset")
        if srcset:
            for item in srcset.split(","):
                value = item.strip().split()[0]
                if value:
                    self.links.append((value, " ".join([*self._heading, *self._title, values.get("alt") or ""]).strip()))

    def handle_data(self, data):
        if self._anchor is not None:
            self._anchor[1].append(data)
        elif self._heading_active:
            self._heading.append(data)
        if self._title_active:
            self._title.append(data)

    def handle_endtag(self, tag):
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading_active = False
        if tag == "title":
            self._title_active = False
        if tag == "a" and self._anchor is not None:
            href, text = self._anchor
            self.links.append((href, " ".join([*self._heading, *text]).strip()))
            self._anchor = None


def _asset_kind(url: str, label: str = "") -> str | None:
    path = urlsplit(url).path.casefold()
    suffix = next((suffix for suffix in _WEB_ASSET_KIND if path.endswith(suffix)), None)
    if suffix is None:
        return None
    text = f"{path} {label}"
    path_has_schematic_marker = bool(_SCHEMATIC_WORDS.search(path))
    if not path_has_schematic_marker and not _SCHEMATIC_WORDS.search(label):
        return None
    if suffix != ".pdf" and _BAD_IMAGE_WORDS.search(text) and not path_has_schematic_marker:
        return None
    return _WEB_ASSET_KIND[suffix]


def _manufacturer_for(url: str) -> str | None:
    host = (urlsplit(url).hostname or "").casefold()
    for domain, name in _OFFICIAL_MANUFACTURERS.items():
        if host in _OFFICIAL_PUBLISHER_HOSTS[domain]:
            return name
    return None


def _same_publisher_host(first: str, second: str) -> bool:
    first, second = first.casefold().rstrip("."), second.casefold().rstrip(".")
    if first == second:
        return True
    # Known manufacturer CDNs are sibling hosts (learn.adafruit.com and
    # cdn-learn.adafruit.com), so a simple suffix check is insufficient.
    for domain in _OFFICIAL_MANUFACTURERS:
        if (first == domain or first.endswith("." + domain)) and (second == domain or second.endswith("." + domain)):
            return True
    if ((first == "pololu.com" or first.endswith(".pololu.com") or first.endswith(".pololu-files.com"))
            and (second == "pololu.com" or second.endswith(".pololu.com") or second.endswith(".pololu-files.com"))):
        return True
    first_base = ".".join(first.split(".")[-2:])
    second_base = ".".join(second.split(".")[-2:])
    return first_base == second_base


def _official_github_asset(url: str, page_url: str) -> str | None:
    """공식 제조사 페이지가 가리킨 허용 조직의 GitHub blob만 raw로 바꾼다."""
    page_host = urlsplit(page_url).hostname or ""
    domain = next((key for key in _OFFICIAL_GITHUB_OWNERS
                   if page_host == key or page_host.endswith("." + key)), None)
    if domain is None:
        return None
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.query or parsed.fragment:
        return None
    if parsed.hostname == "github.com":
        match = re.fullmatch(r"/([^/]+)/([^/]+)/blob/([^/]+)/(.+)", parsed.path)
    elif parsed.hostname == "raw.githubusercontent.com":
        match = re.fullmatch(r"/([^/]+)/([^/]+)/([^/]+)/(.+)", parsed.path)
    else:
        return None
    if not match or match[1].casefold() not in _OFFICIAL_GITHUB_OWNERS[domain]:
        return None
    path = match[4]
    if any(part in {"", ".", ".."} for part in path.split("/")):
        return None
    if parsed.hostname == "raw.githubusercontent.com":
        return url
    return f"https://raw.githubusercontent.com/{match[1]}/{match[2]}/{match[3]}/{path}"


def _page_asset_host_allowed(asset_url: str, page_url: str) -> bool:
    asset_host = urlsplit(asset_url).hostname or ""
    page_host = urlsplit(page_url).hostname or ""
    return _same_publisher_host(asset_host, page_host) or _official_github_asset(asset_url, page_url) is not None


def _page_assets(page_url: str, *, client: httpx.Client) -> tuple[tuple[str, str], ...]:
    """Fetch one public HTML page, bounded, to locate its schematic asset."""
    if _safe_url(page_url) is None or not page_url.startswith("https://"):
        return ()
    try:
        from backend.projects.schematic_discovery import download_bounded
        body, mime = download_bounded(
            page_url, max_bytes=512 * 1024,
            allowed_hosts=frozenset({urlsplit(page_url).hostname or ""}), client=client,
            phase="page_html",
        )
        if "text/html" not in mime.lower():
            return ()
        parser = _SchematicPageParser()
        parser.feed(body.decode("utf-8", "replace"))
    except (httpx.HTTPError, ValueError, UnicodeError, RuntimeError):
        return ()
    found = []
    for raw, label in parser.links:
        url = urljoin(page_url, raw)
        url = _official_github_asset(url, page_url) or url
        if url == page_url or _safe_url(url) is None or not _page_asset_host_allowed(url, page_url):
            continue
        kind = _asset_kind(url, label)
        if kind is None and _SCHEMATIC_WORDS.search(label) and not urlsplit(url).path.rsplit("/", 1)[-1].count("."):
            kind = "png"
        if kind and (_SCHEMATIC_WORDS.search(urlsplit(url).path) or _SCHEMATIC_WORDS.search(label)):
            found.append((url, label))
    def resolution(item):
        match = re.search(r"(?:large|medium|small)(\d+)", urlsplit(item[0]).path, re.I)
        return int(match.group(1)) if match else 0
    return tuple(sorted(dict.fromkeys(found), key=resolution, reverse=True))


def _candidate_priority(source_type: str, kind: str, url: str) -> tuple[int, int]:
    """제조사 schematic 이미지가 안내서 PDF보다 먼저 선택되도록 정렬한다."""
    official = source_type == "manufacturer_official"
    image = kind in {"png", "svg"}
    match = re.search(r"(?:large|medium|small)(\d+)", urlsplit(url).path, re.I)
    resolution = int(match.group(1)) if match else 0
    return (0 if official and image else 1 if official else 2, -resolution)


def _relevance_score(query: str, ref: WebSchematicRef) -> tuple[int, int]:
    def compact(value: str) -> str:
        return "".join(re.findall(r"[a-z0-9가-힣]+", value.casefold()))
    generic = {"schematic", "schematics", "circuit", "diagram", "original", "회로도", "원본"}
    query_tokens = set(re.findall(r"[a-z0-9가-힣]+", query.casefold())) - generic
    q = compact("".join(word for word in re.findall(r"[a-z0-9가-힣]+", query.casefold()) if word not in generic))
    context_tokens = set(re.findall(r"[a-z0-9가-힣]+", f"{ref.title} {ref.page_url}".casefold()))
    exact = bool(q) and any(q in compact(value) for value in (ref.title, ref.page_url, ref.source_file))
    return (int(exact), len(query_tokens & context_tokens))


def _search_public_schematics(query: str, limit: int = 5, *, client: httpx.Client | None = None,
                              include_domains: tuple[str, ...] | None = None,
                              search_text: str | None = None) -> tuple[WebSchematicRef, ...]:
    """회로도 이름으로 공개 웹 후보를 찾고, 게시 페이지와 파일 URL을 함께 반환한다."""
    if not isinstance(query, str) or not query.strip() or type(limit) is not int or not 1 <= limit <= 5:
        raise ValueError("검색어 또는 결과 수가 유효하지 않습니다.")
    key = _require_external_search_configuration()
    if client is None:
        with httpx.Client(trust_env=False) as owned:
            return _search_public_schematics(query, limit, client=owned,
                                             include_domains=include_domains, search_text=search_text)
    query_text = query.strip()
    query_tokens = {token.casefold() for token in re.findall(r"[A-Za-z0-9]+|[가-힣]+", query_text) if len(token) > 1}
    model_tokens = {token for token in query_tokens if any(char.isdigit() for char in token)}
    try:
        with client.stream(
            "POST", "https://api.exa.ai/search", timeout=20, follow_redirects=False,
            headers={"x-api-key": key, "Accept-Encoding": "identity"},
            json={"query": search_text or f"{query_text} schematic circuit diagram original PDF PNG SVG",
                  "numResults": min(10, max(limit * 2, 5)),
                  **({"includeDomains": list(include_domains)} if include_domains else {}),
                  "contents": {"highlights": True, "extras": {"imageLinks": 5}}},
        ) as response:
            response.raise_for_status()
            rows = json.loads(read_bounded_body(response, 512 * 1024))["results"]
        if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
            raise ValueError()
    except (httpx.HTTPError, KeyError, ValueError, TypeError, RecursionError):
        raise ExternalCircuitSearchError("외부 회로 검색 요청 또는 응답 처리에 실패했습니다.") from None
    found: list[WebSchematicRef] = []
    seen: set[str] = set()
    for item in rows:
        page_url = _safe_url(item.get("url"))
        if not page_url:
            continue
        title = item.get("title") if isinstance(item.get("title"), str) else ""
        highlights = item.get("highlights") if isinstance(item.get("highlights"), list) else []
        context = " ".join([title, *(value for value in highlights if isinstance(value, str))])
        context_tokens = {token.casefold() for token in re.findall(
            r"[A-Za-z0-9]+|[가-힣]+", context + " " + urlsplit(page_url).path)}
        if query_tokens and len(query_tokens & context_tokens) < min(2, len(query_tokens)):
            continue
        candidates: list[tuple[str, str]] = []
        if _asset_kind(page_url, context):
            candidates.append((page_url, title))
        extras = item.get("extras") if isinstance(item.get("extras"), dict) else {}
        image_links = extras.get("imageLinks") if isinstance(extras.get("imageLinks"), list) else []
        for raw in image_links:
            if (isinstance(raw, str) and _safe_url(raw) and _asset_kind(raw, context)
                    and _SCHEMATIC_WORDS.search(urlsplit(raw).path)):
                candidates.append((raw, title))
        page_path = urlsplit(page_url).path.casefold()
        if page_path.endswith(("/downloads", "/download", "/resources", ".html", ".htm", ".md")) or not urlsplit(page_url).path.rsplit("/", 1)[-1].count("."):
            if not candidates or page_path.endswith(".md"):
                candidates.extend(_page_assets(page_url, client=client))
            if page_path.endswith(".md"):
                candidates.extend(_page_assets(page_url[:-3], client=client))
        identity = re.sub(r"[^a-z0-9]", "", " ".join(
            [title, page_url, *(f"{url} {label}" for url, label in candidates)]).casefold())
        if not all(token in identity for token in model_tokens):
            continue
        manufacturer = _manufacturer_for(page_url)
        ranked_candidates = []
        for source_url, label in candidates:
            kind = _asset_kind(source_url, f"{context} {label}")
            if kind is None and _SCHEMATIC_WORDS.search(label) and not urlsplit(source_url).path.rsplit("/", 1)[-1].count("."):
                kind = "png"
            if kind is None:
                continue
            ranked_candidates.append((source_url, label, kind))
        ranked_candidates.sort(key=lambda item: _candidate_priority(
            "manufacturer_official" if manufacturer and _page_asset_host_allowed(item[0], page_url) else "public_web",
            item[2], item[0]))
        for source_url, label, kind in ranked_candidates:
            if source_url in seen:
                continue
            seen.add(source_url)
            path = urlsplit(source_url).path
            source_file = path.rsplit("/", 1)[-1] or "schematic." + kind
            label_identity = re.sub(r"[^a-z0-9]", "", label.casefold())
            display_title = (label.strip()[:200] if label and model_tokens
                             and all(token in label_identity for token in model_tokens) else title)
            official = bool(manufacturer and _page_asset_host_allowed(source_url, page_url))
            found.append(WebSchematicRef(
                source_url=source_url, page_url=page_url, source_file=source_file,
                asset_kind=kind, title=display_title or source_file, attribution=manufacturer if official else (urlsplit(page_url).hostname or "공개 웹 출처"),
                source_type="manufacturer_official" if official else "public_web",
                evidence_grade=2 if official else None, manufacturer=manufacturer if official else None,
                model=display_title or None,
            ))
    def priority(ref):
        exact, matched = _relevance_score(query_text, ref)
        model_words = {word.casefold() for word in re.findall(r"[A-Za-z0-9]+|[가-힣]+", query_text)} - {
            "schematic", "schematics", "circuit", "diagram", "original", "회로도", "원본",
        }
        credible_official = ref.source_type == "manufacturer_official" and matched >= max(1, len(model_words) * .6)
        tier = 0 if credible_official else 1 if exact else 2 if ref.source_type == "manufacturer_official" else 3
        return (tier, -exact, -matched, *_candidate_priority(ref.source_type, ref.asset_kind, ref.source_url))

    found.sort(key=priority)
    distinct = []
    identities = set()
    for ref in found:
        parsed = urlsplit(ref.source_url)
        # Publisher CDNs often expose the same drawing at several resolutions.
        identity = (parsed.hostname, re.sub(r"/(?:small|medium|large)\d+/", "/{size}/",
                                            parsed.path, flags=re.I), parsed.query)
        if identity in identities:
            continue
        identities.add(identity)
        distinct.append(ref)
        if len(distinct) >= limit:
            break
    return tuple(distinct)


def search_public_schematics(query: str, limit: int = 5, *, client: httpx.Client | None = None) -> tuple[WebSchematicRef, ...]:
    """회로도 이름으로 공개 웹 후보를 찾는다."""
    return _search_public_schematics(query, limit, client=client)


def search_manufacturer_schematics(query: str, limit: int = 5, *, client: httpx.Client | None = None) -> tuple[WebSchematicRef, ...]:
    """제조사 공식 도메인만 대상으로 공개 회로도 후보를 재검색한다.

    도메인 범위는 제조사 도메인 집합으로만 제한하며 특정 모델 URL은 등록하지 않는다.
    """
    if not isinstance(query, str) or not query.strip() or type(limit) is not int or not 1 <= limit <= 5:
        raise ValueError("검색어 또는 결과 수가 유효하지 않습니다.")
    _require_external_search_configuration()
    if client is None:
        with httpx.Client(trust_env=False) as owned:
            return search_manufacturer_schematics(query, limit, client=owned)
    query_lower = query.casefold()
    domains = tuple(domain for domain in _OFFICIAL_MANUFACTURERS
                    if any(alias in query_lower for alias in _MANUFACTURER_ALIASES[domain]))
    if not domains:
        return ()
    found: list[WebSchematicRef] = []
    seen: set[str] = set()
    for domain in domains:
        board_name = re.sub(r"\s+(?:schematics?|회로도)\s*$", "", query.strip(), flags=re.I)
        search_host = "learn.adafruit.com" if domain == "adafruit.com" else domain
        try:
            candidates = _search_public_schematics(query, limit, client=client,
                                                    include_domains=(domain,),
                                                    search_text=f"{board_name} downloads schematic {search_host}")
        except ExternalCircuitSearchError:
            continue
        for candidate in candidates:
            if candidate.source_type != "manufacturer_official" or candidate.source_url in seen:
                continue
            seen.add(candidate.source_url)
            found.append(candidate)
            if len(found) >= limit:
                return tuple(found)
    return tuple(found)


def search_github_repositories(query: str, limit: int = 5, *, client: httpx.Client | None = None) -> tuple[GitHubRepositoryRef, ...]:
    if not isinstance(query, str) or not query.strip() or type(limit) is not int or not 1 <= limit <= 5:
        raise ValueError("검색어 또는 결과 수가 유효하지 않습니다.")
    key = _require_external_search_configuration()
    if client is None:
        with httpx.Client(trust_env=False) as owned:
            return search_github_repositories(query, limit, client=owned)
    try:
        with client.stream(
            "POST", "https://api.exa.ai/search", timeout=20, follow_redirects=False,
            headers={"x-api-key": key, "Accept-Encoding": "identity"},
            json={"query": f"{query.strip()} complete schematic KiCad open hardware GitHub",
                  "numResults": limit, "includeDomains": ["github.com"]},
        ) as response:
            response.raise_for_status()
            rows = json.loads(read_bounded_body(response, 256 * 1024))["results"]
        if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
            raise ValueError()
    except (httpx.HTTPError, KeyError, ValueError, TypeError, RecursionError):
        raise ExternalCircuitSearchError("외부 회로 검색 요청 또는 응답 처리에 실패했습니다.") from None
    found = {}
    for item in rows:
        ref = github_repository_ref(item.get("url"))
        if ref:
            found.setdefault(ref.repository_url.casefold(), ref)
        if len(found) == limit:
            break
    return tuple(found.values())
