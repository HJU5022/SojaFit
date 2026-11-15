"""Exa의 외부 자료 후보를 반환한다. 다운로드, 파일 저장, DB 변경은 수행하지 않는다."""
import ipaddress
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from itertools import zip_longest
from urllib.parse import quote, unquote, urljoin, urlsplit

import httpx

LOGGER = logging.getLogger(__name__)

# Keep enough independent discovery candidates for noisy public indexes to avoid
# hiding a valid repository behind the first page of unrelated results.
MAX_COMPONENT_REPOSITORIES = 24


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


def read_bounded_body(response: httpx.Response, max_bytes: int, *, deadline: float | None = None) -> bytes:
    """Read an identity-encoded response without decompressing untrusted content.

    deadline(time.monotonic() 기준)을 넘기면 TimeoutError를 낸다. 기본은 마감 없음: 정당하게 오래 걸리는 렌더 응답(90초)이 같은 함수를 쓴다.
    """
    length = response.headers.get("content-length")
    if length is not None and not 0 <= int(length) <= max_bytes:
        raise ValueError("invalid length")
    if response.headers.get("content-encoding", "identity").lower() != "identity":
        raise ValueError("unexpected encoding")
    chunks = [response.content] if response.is_stream_consumed else response.iter_raw()
    data = bytearray()
    for chunk in chunks:
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError("deadline")  # [왜] 읽기 timeout은 조각 하나마다라 15초마다 1바이트씩 흘리면 끝나지 않는다
        if len(data) + len(chunk) > max_bytes:
            raise ValueError("response too large")
        data.extend(chunk)
    return bytes(data)


_WEB_ASSET_KIND = {".pdf": "pdf", ".png": "png", ".svg": "svg"}
_SCHEMATIC_WORDS = re.compile(r"(?:schematic|schem|(?:^|[_-])sch(?=$|[_./-])|circuit[-_ ]?(?:diagram|drawing)|회로도)", re.I)
_BAD_IMAGE_WORDS = re.compile(r"(?:photo|product|render|layout|footprint|pcb|fab|board[-_ ]?top|wiring|breadboard|hero|logo)", re.I)
_NON_CIRCUIT_PATH = re.compile(
    r"(?:^|[/_.\s-])(?:symbols?|symbol[-_ ]?librar(?:y|ies)|component[-_ ]?librar(?:y|ies)|"
    r"pin[-_ ]?outs?|footprints?|parts?[-_ ]?placement|(?:block|functional)[-_ ]?diagrams?)(?=$|[/_.\s-])", re.I)
_NON_CIRCUIT_LABEL = re.compile(
    r"\b(?:(?:schematic|component|module)[-_ ]+symbol|symbol[-_ ]+librar(?:y|ies)|"
    r"pin[-_ ]?out(?:[-_ ]+diagram)?|(?:block|functional)[-_ ]+diagram)\b", re.I)
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
    "raspberrypi.com": frozenset({"raspberrypi.com", "www.raspberrypi.com", "docs.raspberrypi.com", "datasheets.raspberrypi.com", "pip.raspberrypi.com", "pip-assets.raspberrypi.com"}),
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
_KOREAN_PRODUCT_ALIASES = {
    "라즈베리파이": "Raspberry Pi",
    "피코": "Pico",
    "다이오드": "diode",
}


def canonical_product_query(query: str) -> str:
    """Recognize supported product aliases in queries and source metadata."""
    query = re.sub(r"(?<![a-z0-9])rpi(?![a-z0-9])", "Raspberry Pi", query, flags=re.I)
    query = re.sub(r"라즈베리\s+파이", "Raspberry Pi", query)
    query = re.sub(r"[가-힣]+", lambda match: _KOREAN_PRODUCT_ALIASES.get(
        match.group(), match.group()), query)
    return re.sub(r"^pico\b", "Raspberry Pi Pico", query, flags=re.I)


_DIODE_EVIDENCE = ("diode", "schottky", "rectifier", "zener", "다이오드")
_DIODE_CONFLICTS = ("radio", "transceiver", "receiver", "walkie", "ham", "무전기", "라디오")


def component_context(query: str) -> str | None:
    """Return the narrow component intent carried by a search query."""
    text = query.casefold()
    return "diode" if any(term in text for term in _DIODE_EVIDENCE) else None


def component_evidence_matches(query: str, text: str) -> bool:
    """Require component evidence and reject a conflicting product family."""
    if component_context(query) != "diode":
        return True
    tokens = set(re.findall(r"[a-z0-9]+|[가-힣]+", str(text).casefold()))
    if any(marker in tokens for marker in _DIODE_CONFLICTS):
        return False
    return any(marker in tokens for marker in _DIODE_EVIDENCE)


_OFFICIAL_GITHUB_OWNERS = {
    "olimex.com": frozenset({"olimex"}),
}


class _SchematicPageParser(HTMLParser):
    """페이지에 공개된 회로도 링크만 수집한다. 스크립트는 해석하지 않는다."""
    def __init__(self, *, require_schematic_context: bool = False):
        super().__init__(convert_charrefs=True)
        self.require_schematic_context = require_schematic_context
        self.links: list[tuple[str, str]] = []
        self.schematic_links: set[str] = set()
        self._heading: list[str] = []
        self._sections: dict[int, list[str]] = {}
        self._media: list[dict] = []
        self._heading_active = False
        self._heading_link = None
        self._title = ""
        self._title_active = False
        self._anchor: tuple[str, list[str]] | None = None

    def _add_link(self, url: str, local_label: str) -> None:
        section = " ".join(text for level, heading in self._sections.items() if level > 1 for text in heading)
        if _SCHEMATIC_WORDS.search(urlsplit(url).path):
            section += " " + " ".join(self._sections.get(1, []))
        schematic = re.search(r"\bschematics?\b|\bcircuit[-_ ]+diagram\b|회로도", f"{section} {local_label}", re.I)
        if self.require_schematic_context and not schematic:
            return
        if schematic:
            self.schematic_links.add(url)
        self.links.append((url, " ".join([self._title, *(text for heading in self._sections.values() for text in heading), local_label]).strip()))

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._heading = []
            level = int(tag[1])
            self._sections = {number: text for number, text in self._sections.items() if number < level}
            self._sections[level] = self._heading
            self._heading_active = True
            self._heading_link = values.get('data-href')
        if tag in {"figure", "table"}:
            if len(self._media) >= 8:
                raise ValueError("image context nesting limit")
            self._media.append({"tag": tag, "images": [], "caption": [], "caption_depth": 0,
                                "sections": self._sections.copy()})
        if tag in {"figcaption", "caption", "th"}:
            for scope in self._media:
                scope["caption_depth"] += 1
        if tag == "title":
            self._title = ""
            self._title_active = True
        if tag == "a" and values.get("href"):
            self._anchor = (values["href"], [])
        image_urls = []
        for key in ("href", "src", "data-src"):
            value = values.get(key)
            if value and tag != "a":
                self._add_link(value, values.get("alt") or "")
                image_urls.append(value)
        srcset = values.get("srcset")
        if srcset:
            for item in srcset.split(","):
                value = item.strip().split()[0]
                if value:
                    self._add_link(value, values.get("alt") or "")
                    image_urls.append(value)
        if tag == "img":
            if self._anchor is not None:
                image_urls.append(self._anchor[0])
            for scope in self._media:
                scope["images"].append(image_urls)

    def handle_data(self, data):
        for scope in self._media:
            if scope["caption_depth"]:
                scope["caption"].append(data)
        if self._anchor is not None:
            self._anchor[1].append(data)
        elif self._heading_active:
            self._heading.append(data)
        if self._title_active:
            # The title is copied into every link's bounded identity evidence.
            self._title = (self._title + data)[:200]

    def handle_endtag(self, tag):
        if tag in {"figcaption", "caption", "th"}:
            for scope in self._media:
                scope["caption_depth"] = max(0, scope["caption_depth"] - 1)
        if self._media and tag == self._media[-1]["tag"]:
            scope = self._media.pop()
            caption = " ".join(scope["caption"])
            if len(scope["images"]) == 1 and re.search(r"\bschematics?\b|\bcircuit[-_ ]+diagram\b|회로도", caption, re.I):
                for url in dict.fromkeys(scope["images"][0]):
                    self._add_link(url, caption)
            self._sections = scope["sections"]
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            if self._heading_link:
                self._add_link(self._heading_link, ' '.join(self._heading))
                self._heading_link = None
            self._heading_active = False
        if tag == "title":
            self._title_active = False
        if tag == "a" and self._anchor is not None:
            href, text = self._anchor
            self._add_link(href, " ".join(text))
            self._anchor = None


def is_non_circuit_asset(url: str, label: str = "") -> bool:
    return bool(_NON_CIRCUIT_PATH.search(unquote(urlsplit(url).path))
                or _NON_CIRCUIT_LABEL.search(label))


def _asset_kind(url: str, label: str = "") -> str | None:
    if is_non_circuit_asset(url, label):
        return None
    path = urlsplit(url).path.casefold()
    if path.endswith(".zip"):
        return "pdf" if _manufacturer_for(url) else None
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


PAGE_DEADLINE_SECONDS = 30  # 공개 웹 HTML 한 페이지를 받는 데 쓰는 전체 시간 상한(점검 A #7)


def _page_assets(page_url: str, *, client: httpx.Client, required: bool = False,
                 require_schematic_context: bool = False) -> tuple[tuple[str, str], ...]:
    """Fetch one public HTML page, bounded, to locate its schematic asset."""
    if _safe_url(page_url) is None or not page_url.startswith("https://"):
        return ()
    from backend.projects.schematic_source import ExternalSchematicError
    try:
        from backend.projects.schematic_discovery import download_bounded
        body, mime = download_bounded(
            page_url, max_bytes=512 * 1024,
            allowed_hosts=frozenset({urlsplit(page_url).hostname or ""}), client=client,
            phase="page_html", deadline_seconds=PAGE_DEADLINE_SECONDS,
        )
        if "text/html" not in mime.lower():
            return ()
        parser = _SchematicPageParser(require_schematic_context=require_schematic_context)
        parser.feed(body.decode("utf-8", "replace"))
    except ExternalSchematicError:
        if required:
            raise
        return ()
    except (httpx.HTTPError, ValueError, UnicodeError, RuntimeError):
        return ()
    found = []
    for raw, label in parser.links:
        url = urljoin(page_url, raw).replace(' ', '%20')
        url = _official_github_asset(url, page_url) or url
        if (url == page_url or _safe_url(url) is None or not _page_asset_host_allowed(url, page_url)
                or is_non_circuit_asset(url, label)):
            continue
        kind = _asset_kind(url, label)
        if kind is None and raw in parser.schematic_links and not _BAD_IMAGE_WORDS.search(urlsplit(url).path):
            kind = next((kind for suffix, kind in _WEB_ASSET_KIND.items()
                         if urlsplit(url).path.casefold().endswith(suffix)), None)
        if kind is None and _SCHEMATIC_WORDS.search(label) and not urlsplit(url).path.rsplit("/", 1)[-1].count("."):
            kind = "png"
        if kind and (_SCHEMATIC_WORDS.search(urlsplit(url).path) or _SCHEMATIC_WORDS.search(label)
                     or urlsplit(url).path.casefold().endswith(".zip")):
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
        return "".join(re.findall(r"[a-z0-9가-힣]+", canonical_product_query(value).casefold()))
    generic = {"schematic", "schematics", "circuit", "diagram", "original", "회로도", "원본"}
    query_tokens = set(re.findall(r"[a-z0-9가-힣]+", query.casefold())) - generic
    q = compact("".join(word for word in re.findall(r"[a-z0-9가-힣]+", query.casefold()) if word not in generic))
    context_tokens = set(re.findall(r"[a-z0-9가-힣]+", canonical_product_query(f"{ref.title} {ref.page_url}").casefold()))
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
    query_text = canonical_product_query(query.strip())
    component = component_context(query_text)
    query_tokens = {token.casefold() for token in re.findall(r"[A-Za-z0-9]+|[가-힣]+", query_text) if len(token) > 1}
    model_tokens = {token for token in query_tokens if any(char.isdigit() for char in token)}
    try:
        with client.stream(
            "POST", "https://api.exa.ai/search", timeout=20, follow_redirects=False,
            headers={"x-api-key": key, "Accept-Encoding": "identity"},
            json={"query": search_text or f"{query_text}{' diode application circuit' if component == 'diode' else ''} schematic circuit diagram original PDF PNG SVG",
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
    seen: dict[str, int] = {}
    for item in rows:
        page_url = _safe_url(item.get("url"))
        if not page_url:
            continue
        title = item.get("title") if isinstance(item.get("title"), str) else ""
        highlights = item.get("highlights") if isinstance(item.get("highlights"), list) else []
        context = " ".join([title, *(value for value in highlights if isinstance(value, str))])
        context_tokens = {token.casefold() for token in re.findall(
            r"[A-Za-z0-9]+|[가-힣]+", context + " " + urlsplit(page_url).path)}
        required_tokens = model_tokens if component == "diode" else query_tokens
        matched_tokens = {term for term in required_tokens if any(
            word == term or (len(term) >= 3 and word.startswith(term)) for word in context_tokens)}
        if required_tokens and len(matched_tokens) < min(2, len(required_tokens)):
            continue
        if component == "diode" and not component_evidence_matches(
                query_text, f"{context} {page_url}"):
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
            if kind is None or is_non_circuit_asset(source_url, label):
                continue
            ranked_candidates.append((source_url, label, kind))
        ranked_candidates.sort(key=lambda item: _candidate_priority(
            "manufacturer_official" if manufacturer and _page_asset_host_allowed(item[0], page_url) else "public_web",
            item[2], item[0]))
        for source_url, label, kind in ranked_candidates:
            previous = seen.get(source_url)
            if previous is not None and (page_url == source_url or found[previous].page_url != source_url):
                continue
            path = urlsplit(source_url).path
            source_file = path.rsplit("/", 1)[-1] or "schematic." + kind
            label_identity = re.sub(r"[^a-z0-9]", "", label.casefold())
            display_title = (label.strip()[:200] if label and model_tokens
                             and all(token in label_identity for token in model_tokens) else title)
            official = bool(manufacturer and _page_asset_host_allowed(source_url, page_url))
            candidate = WebSchematicRef(
                source_url=source_url, page_url=page_url, source_file=source_file,
                asset_kind=kind, title=display_title or source_file, attribution=manufacturer if official else (urlsplit(page_url).hostname or "공개 웹 출처"),
                source_type="manufacturer_official" if official else "public_web",
                evidence_grade=2 if official else None, manufacturer=manufacturer if official else None,
                model=display_title or None,
            )
            if previous is None:
                seen[source_url] = len(found)
                found.append(candidate)
            else:
                found[previous] = candidate
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
    LOGGER.info("schematic_search_candidates", extra={"phase": "manufacturer" if include_domains else "public",
                                                     "raw_result_count": len(rows), "candidate_count": len(distinct)})
    return tuple(distinct)


def search_public_schematics(query: str, limit: int = 5, *, client: httpx.Client | None = None) -> tuple[WebSchematicRef, ...]:
    """회로도 이름으로 공개 웹 후보를 찾는다."""
    return _search_public_schematics(query, limit, client=client)


def _raspberrypi_portal_schematics(query: str, *, client: httpx.Client) -> tuple[WebSchematicRef, ...]:
    """Look up the exact product category, without registering a model URL."""
    from backend.projects.schematic_discovery import download_bounded
    from backend.projects.schematic_render import _verify_artifact_name
    from backend.projects.schematic_source import ExternalSchematicInvalidSource
    url = 'https://pip.raspberrypi.com/search?q=' + quote(query, safe='')
    body, mime = download_bounded(url, max_bytes=512 * 1024,
        allowed_hosts=frozenset({'pip.raspberrypi.com'}), client=client, phase='official_product_search',
        deadline_seconds=PAGE_DEADLINE_SECONDS)
    if 'text/html' not in mime:
        return ()
    parser = _SchematicPageParser()
    parser.feed(body.decode('utf-8', 'replace'))
    product = re.sub(r'[^a-z0-9]', '', canonical_product_query(query).casefold())
    for raw, _ in parser.links:
        page = urljoin(url, raw)
        parsed = urlsplit(page)
        category = re.fullmatch(r'/categories/\d+-(.+)', parsed.path)
        if parsed.hostname != 'pip.raspberrypi.com' or not category:
            continue
        if re.sub(r'[^a-z0-9]', '', category[1].casefold()) != product:
            continue
        refs = []
        for asset, label in _page_assets(page, client=client, required=True):
            filename = urlsplit(asset).path.rsplit('/', 1)[-1]
            try:
                _verify_artifact_name(query, filename, asset, label)
            except ExternalSchematicInvalidSource:
                continue
            refs.append(WebSchematicRef(asset, page, filename, _asset_kind(asset, label) or 'png',
                label[:200], 'Raspberry Pi', source_type='manufacturer_official', evidence_grade=2,
                manufacturer='Raspberry Pi', model=query))
        return tuple(refs[:5])
    return ()


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
    query_lower = canonical_product_query(query).casefold()
    domains = tuple(domain for domain in _OFFICIAL_MANUFACTURERS
                    if any(alias in query_lower for alias in _MANUFACTURER_ALIASES[domain]))
    if not domains:
        return ()
    found: list[WebSchematicRef] = []
    seen: set[str] = set()
    for domain in domains:
        board_name = re.sub(r"\s+(?:schematics?|회로도)\s*$", "", canonical_product_query(query.strip()), flags=re.I)
        if domain == 'raspberrypi.com':
            for candidate in _raspberrypi_portal_schematics(board_name, client=client):
                if candidate.source_url not in seen:
                    found.append(candidate)
                    seen.add(candidate.source_url)
        search_host = "learn.adafruit.com" if domain == "adafruit.com" else domain
        try:
            candidates = _search_public_schematics(query, limit, client=client,
                                                    include_domains=(domain,),
                                                    search_text=f"{board_name} downloads schematic design files {search_host}")
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


def _component_repository_ref(value):
    """File search hits nominate a repository, never a trusted schematic URL."""
    if root := github_repository_ref(value):
        return root
    url = safe_public_https_url(value, allowed_hosts=frozenset({"github.com"}))
    if not url:
        return None
    parsed = urlsplit(url)
    if parsed.query or parsed.fragment:
        return None
    match = re.fullmatch(r"/([A-Za-z0-9-]+)/([A-Za-z0-9_.-]+)/(?:blob|tree)/[^/]+/.+", parsed.path)
    if not match or any(piece in {".", ".."} for piece in parsed.path.split("/")):
        return None
    return github_repository_ref(f"https://github.com/{match[1]}/{match[2]}")


def search_github_repositories(query: str, limit: int = 5, *, client: httpx.Client | None = None,
                               include_files: bool = False, search_text: str | None = None) -> tuple[GitHubRepositoryRef, ...]:
    if not isinstance(query, str) or not query.strip() or type(limit) is not int or not 1 <= limit <= MAX_COMPONENT_REPOSITORIES:
        raise ValueError("검색어 또는 결과 수가 유효하지 않습니다.")
    key = _require_external_search_configuration()
    if client is None:
        with httpx.Client(trust_env=False) as owned:
            return search_github_repositories(query, limit, client=owned,
                                              include_files=include_files, search_text=search_text)
    try:
        with client.stream(
            "POST", "https://api.exa.ai/search", timeout=20, follow_redirects=False,
            headers={"x-api-key": key, "Accept-Encoding": "identity"},
            json={"query": search_text or f"{query.strip()} complete schematic KiCad open hardware GitHub",
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
        ref = (_component_repository_ref if include_files else github_repository_ref)(item.get("url"))
        if ref:
            found.setdefault(ref.repository_url.casefold(), ref)
        if len(found) == limit:
            break
    LOGGER.info("schematic_search_candidates", extra={"phase": "github", "raw_result_count": len(rows),
                                                     "candidate_count": len(found)})
    return tuple(found.values())


def search_component_repositories(query: str, limit: int = 5, *, client: httpx.Client | None = None) -> tuple[GitHubRepositoryRef, ...]:
    """Discover component-bearing projects through repository search and a BOM index.

    Index pages nominate repositories only; placed components, license and commit
    are verified later from the original repository, never trusted from the index.
    """
    if not isinstance(query, str) or not query.strip() or type(limit) is not int or not 1 <= limit <= MAX_COMPONENT_REPOSITORIES:
        raise ValueError("invalid component search")
    if client is None:
        with httpx.Client(trust_env=False) as owned:
            return search_component_repositories(query, limit, client=owned)
    terms = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", query.casefold())
    part_query = " ".join(term for term in terms if any(char.isdigit() for char in term))
    if not part_query:
        return search_github_repositories(query, limit, client=client, include_files=True)
    from backend.projects.schematic_discovery import download_bounded
    indexed = {}
    try:
        with client.stream("POST", "https://api.exa.ai/search", timeout=20, follow_redirects=False,
                           headers={"x-api-key": _require_external_search_configuration(), "Accept-Encoding": "identity"},
                           json={"query": part_query, "numResults": MAX_COMPONENT_REPOSITORIES,
                                 "includeDomains": ["hardlabs.io"]}) as response:
            response.raise_for_status()
            rows = json.loads(read_bounded_body(response, 512 * 1024))["results"]
        if not isinstance(rows, list):
            raise ValueError()
        pages = []
        for row in rows:
            url = _safe_url(row.get("url")) if isinstance(row, dict) else None
            if url and urlsplit(url).hostname in {"hardlabs.io", "www.hardlabs.io"} and url.startswith("https://") and url not in pages:
                pages.append(url)
        for url in pages[:MAX_COMPONENT_REPOSITORIES]:
            try:
                body, mime = download_bounded(url, max_bytes=512 * 1024,
                                             allowed_hosts=frozenset({urlsplit(url).hostname}),
                                             client=client, phase="page_html", deadline_seconds=PAGE_DEADLINE_SECONDS)
                if mime != "text/html":
                    continue
                html = body.decode("utf-8", "replace")
                if not all(re.search(r"(?<![a-z0-9])" + re.escape(term) + (r"(?![a-z0-9])" if len(term) < 3 else ""), html, re.I)
                           for term in part_query.split()):
                    continue
                parser = _SchematicPageParser()
                parser.feed(html)
                for link, _ in parser.links:
                    ref = github_repository_ref(link)
                    if ref:
                        indexed.setdefault(ref.repository_url.casefold(), ref)
                        break
            except (ValueError, RuntimeError, httpx.HTTPError):
                continue
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        pass  # An index outage must not disable independent repository discovery.
    groups = [tuple(indexed.values())]
    failed = False
    for search_text in (None, f'"{part_query}" kicad_sch circuit'):
        try:
            groups.append(search_github_repositories(part_query, MAX_COMPONENT_REPOSITORIES,
                                                     client=client, include_files=True,
                                                     search_text=search_text))
        except (ExternalCircuitSearchConfigurationError, ExternalCircuitSearchDisabled):
            raise
        except ExternalCircuitSearchError:
            failed = True
    found = {}
    # Interleave independent discovery paths so an index cannot fill every slot.
    for row in zip_longest(*groups):
        for ref in row:
            if ref:
                found.setdefault(ref.repository_url.casefold(), ref)
    if not found and failed:
        raise ExternalCircuitSearchError("외부 회로 검색 요청 또는 응답 처리에 실패했습니다.")
    return tuple(found.values())[:limit]
