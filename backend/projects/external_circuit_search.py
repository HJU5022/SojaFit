"""Exa의 외부 자료 후보를 반환한다. 다운로드, 파일 저장, DB 변경은 수행하지 않는다."""
import ipaddress
import json
import os
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

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
class OfficialSchematicRef:
    """카탈로그가 이미 검증한 제조사 원본 후보."""
    demo_id: str
    manufacturer: str
    model: str
    revision: str | None
    source_url: str
    source_file: str
    asset_kind: str
    source_sha256: str
    license: str
    license_evidence_url: str
    attribution: str
    source_type: str = "manufacturer_official"
    evidence_grade: int = 2


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


_OFFICIAL_HOSTS = frozenset({
    "cdn.sparkfun.com", "www.sparkfun.com", "learn.sparkfun.com",
    "cdn-learn.adafruit.com", "learn.adafruit.com", "www.adafruit.com",
})
_OFFICIAL_GITHUB_ORGS = frozenset({"sparkfun", "adafruit"})
_ASSET_KIND_BY_SUFFIX = {".pdf": "pdf", ".png": "png", ".svg": "svg"}


def _official_catalog_matches(query: str):
    # Import lazily so ordinary GitHub search and its unit tests do not load the
    # frontend asset catalog.
    from backend.projects.catalog import catalog_by_id
    from backend.projects.visuals import load_demo_visuals

    needle = " ".join(query.split()).casefold()
    query_tokens = set(re.findall(r"[a-z0-9]+", needle))
    records = load_demo_visuals()
    matches = []
    for item in catalog_by_id().values():
        visual = records.get(item.id)
        if visual is None:
            continue
        name_tokens = set(re.findall(r"[a-z0-9]+", item.name.casefold()))
        if not name_tokens.issubset(query_tokens):
            continue
        parsed = urlsplit(visual.original_url)
        host = parsed.hostname or ""
        if host not in _OFFICIAL_HOSTS:
            continue
        repo_parts = urlsplit(visual.source_repo).path.strip("/").split("/")
        if len(repo_parts) < 2 or repo_parts[0].casefold() not in _OFFICIAL_GITHUB_ORGS:
            continue
        suffix = next((suffix for suffix in _ASSET_KIND_BY_SUFFIX if parsed.path.casefold().endswith(suffix)), None)
        if suffix is None:
            continue
        revision_match = re.search(r"(?:^|[_-])(v\d+(?:\.\d+)?[a-z]?)(?:\.[^.]+)$", parsed.path, re.IGNORECASE)
        matches.append(OfficialSchematicRef(
            demo_id=item.id, manufacturer=visual.attribution, model=item.name,
            revision=revision_match.group(1) if revision_match else None,
            source_url=visual.original_url, source_file=parsed.path.rsplit("/", 1)[-1],
            asset_kind=_ASSET_KIND_BY_SUFFIX[suffix], source_sha256=visual.source_sha256,
            license=visual.license, license_evidence_url=visual.license_evidence_url,
            attribution=visual.attribution,
        ))
    return matches


def search_official_schematics(query: str, limit: int = 5, *, client: httpx.Client | None = None) -> tuple[OfficialSchematicRef, ...]:
    """Exa에서 찾은 URL이 신뢰 카탈로그의 제조사 원본과 정확히 일치할 때만 반환한다."""
    if not isinstance(query, str) or not query.strip() or type(limit) is not int or not 1 <= limit <= 5:
        raise ValueError("검색어 또는 결과 수가 유효하지 않습니다.")
    key = _require_external_search_configuration()
    candidates = _official_catalog_matches(query)
    if not candidates:
        return ()
    by_url = {candidate.source_url: candidate for candidate in candidates}
    domains = sorted({urlsplit(candidate.source_url).hostname for candidate in candidates})
    if client is None:
        with httpx.Client(trust_env=False) as owned:
            return search_official_schematics(query, limit, client=owned)
    try:
        with client.stream(
            "POST", "https://api.exa.ai/search", timeout=20, follow_redirects=False,
            headers={"x-api-key": key, "Accept-Encoding": "identity"},
            json={"query": f"{query.strip()} official schematic", "numResults": limit,
                  "includeDomains": domains},
        ) as response:
            response.raise_for_status()
            rows = json.loads(read_bounded_body(response, 256 * 1024))["results"]
        if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
            raise ValueError()
    except (httpx.HTTPError, KeyError, ValueError, TypeError, RecursionError):
        raise ExternalCircuitSearchError("외부 회로 검색 요청 또는 응답 처리에 실패했습니다.") from None
    found = []
    for item in rows:
        url = item.get("url")
        parsed = urlsplit(url) if isinstance(url, str) else None
        if parsed is None or parsed.hostname not in domains:
            continue
        if url in by_url and url not in {candidate.source_url for candidate in found}:
            found.append(by_url[url])
        if len(found) == limit:
            break
    return tuple(found)
