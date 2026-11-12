"""공개 완성 회로도의 검색, 15분 메모리 재사용, 서명된 시트 조회."""
import base64
import binascii
import hmac
import json
import os
import re
import time
from collections import OrderedDict
from concurrent.futures import Future
from dataclasses import dataclass
from threading import Lock

from backend.projects.schematic_source import (
    ALLOWED_LICENSES, ExternalSchematicConfigurationError, ExternalSchematicInvalidSource,
    ExternalSchematicInvalidToken, ExternalSchematicNotFound, ExternalSchematicUpstreamError,
    VerifiedSchematicSource,
)

TTL = 900


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


def _key():
    secret = os.getenv("AUTH_SECRET", "").encode()
    if len(secret) < 32:
        raise ExternalSchematicConfigurationError("회로도 서명 키가 필요합니다.")
    return hmac.digest(secret, b"sojafit/external-schematic/v1", "sha256")


def _encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


def _sign(source, count, expires):
    payload = [source.repository, source.commit, source.license, source.attribution, source.source_file,
               source.asset_kind, source.asset_paths, source.root_schematic, count, expires]
    part = _encode(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode())
    token = (part + b"." + _encode(hmac.digest(_key(), part, "sha256"))).decode()
    if len(token) > 4096:
        raise ExternalSchematicInvalidSource("원본 식별자가 너무 깁니다.")
    return token


def _relative(path):
    return (isinstance(path, str) and bool(path) and not re.search(r"[\\:\x00-\x1f\x7f]", path)
            and all(piece not in ("", ".", "..") for piece in path.split("/")))


def _read_token(token, now):
    try:
        if len(token) > 4096 or not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]{43}", token):
            raise ValueError
        part, signature = token.encode("ascii").split(b".")
        if not hmac.compare_digest(signature, _encode(hmac.digest(_key(), part, "sha256"))):
            raise ValueError
        fields = json.loads(base64.b64decode(part + b"=" * (-len(part) % 4), altchars=b"-_", validate=True))
        repo, sha, license_id, credit, path, kind, assets, root, count, expires = fields
        if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not _relative(repo)
                or not re.fullmatch(r"[0-9a-f]{40}", sha) or license_id not in ALLOWED_LICENSES
                or not isinstance(credit, str) or not credit or not _relative(path) or not _relative(root)
                or not root.lower().endswith((".sch", ".kicad_sch"))
                or kind not in ("png", "svg", "pdf", "kicad") or not isinstance(assets, list)
                or not all(_relative(p) for p in assets) or bool(assets) == (kind == "kicad")
                or type(count) is not int or not 1 <= count <= 20 or type(expires) is not int or now >= expires):
            raise ValueError
        url = f"https://github.com/{repo}"
        return VerifiedSchematicSource(repo, sha, license_id, credit, url, f"{url}/tree/{sha}",
                                       path, kind, tuple(assets), root, count), count
    except (ValueError, UnicodeError, TypeError, binascii.Error):
        raise ExternalSchematicInvalidToken("시트 주소가 올바르지 않거나 만료되었습니다.") from None


class _Cache:
    """동일 key는 진행 중 Future를 공유한다. 네트워크와 변환 중에는 lock을 풀어 둔다."""

    def __init__(self, capacity, byte_capacity, weight, ttl, clock):
        self.entries = OrderedDict()
        self.pending = {}
        self.lock = Lock()
        self.capacity, self.byte_capacity, self.weight = capacity, byte_capacity, weight
        self.ttl, self.clock, self.size = ttl, clock, 0

    def get(self, key, produce):
        with self.lock:
            entry = self.entries.pop(key, None)
            if entry is not None:
                expires, value, weight = entry
                if self.clock() < expires:
                    self.entries[key] = entry
                    return value
                self.size -= weight
            flight = self.pending.get(key)
            leader = flight is None
            if leader:
                flight = self.pending[key] = Future()
        if not leader:
            return flight.result()
        try:
            value = produce()
            weight = self.weight(value)
            with self.lock:
                if weight <= self.byte_capacity:
                    self.entries[key] = self.clock() + self.ttl, value, weight
                    self.size += weight
                    while len(self.entries) > self.capacity or self.size > self.byte_capacity:
                        _, (_, _, discarded) = self.entries.popitem(last=False)
                        self.size -= discarded
                flight.set_result(value)
            return value
        except BaseException as exc:
            flight.set_exception(exc)
            raise
        finally:
            with self.lock:
                self.pending.pop(key, None)


class ExternalSchematicService:
    def __init__(self, search, inspect, render, *, clock=time.monotonic, wall=time.time,
                 query_capacity=128, image_capacity=64, image_byte_capacity=128*1024*1024,
                 ttl_seconds=TTL):
        self.search, self.inspect, self.render = search, inspect, render
        self.wall = wall
        self.queries = _Cache(query_capacity, 0, lambda _: 0, ttl_seconds, clock)
        self.images = _Cache(image_capacity, image_byte_capacity, lambda sheets: sum(map(len, sheets)), ttl_seconds, clock)

    def _sheets(self, source):
        def produce():
            result = self.render(source)
            if not 1 <= len(result) <= 20:
                raise ExternalSchematicInvalidSource("시트 수가 허용 범위를 벗어났습니다.")
            return result
        return self.images.get(source, produce)

    def _find(self, query):
        for repository in self.search(query, 5)[:3]:
            for source in self.inspect(repository, query=query):
                try:
                    _sign(source, source.expected_sheets, int(self.wall()) + TTL)
                    sheets = self._sheets(source)
                    if len(sheets) != source.expected_sheets:
                        raise ExternalSchematicInvalidSource("원본과 시트 수가 다릅니다.")
                except ExternalSchematicInvalidSource:
                    continue
                return source, len(sheets)
        return None

    def find(self, query):
        normalized = " ".join(query.split()).casefold()
        if not 2 <= len(query.strip()) <= 200:
            raise ValueError("검색어는 2~200자여야 합니다.")
        result = self.queries.get(normalized, lambda: self._find(normalized))
        if result is None:
            raise ExternalSchematicNotFound()
        source, count = result
        token = _sign(source, count, int(self.wall()) + TTL)
        return ExternalSchematicManifest(source.repository, source.commit, source.license, source.attribution,
                                         source.repository_url, source.source_url, source.source_file, token, count)

    def load(self, token, sheet_index):
        source, count = _read_token(token, self.wall())
        if type(sheet_index) is not int or not 0 <= sheet_index < count:
            raise ExternalSchematicInvalidToken()
        try:
            sheets = self._sheets(source)
        except ExternalSchematicInvalidSource:
            raise ExternalSchematicNotFound() from None
        if len(sheets) != count:
            raise ExternalSchematicNotFound()
        return sheets[sheet_index]


def _search(query, limit):
    from backend.projects.external_circuit_search import (
        ExternalCircuitSearchConfigurationError, ExternalCircuitSearchDisabled,
        ExternalCircuitSearchError, search_github_repositories,
    )
    try:
        return search_github_repositories(query, limit)
    except (ExternalCircuitSearchConfigurationError, ExternalCircuitSearchDisabled):
        raise ExternalSchematicConfigurationError() from None
    except ExternalCircuitSearchError:
        raise ExternalSchematicUpstreamError() from None


def _inspect(repo, *, query):
    from backend.projects.schematic_discovery import inspect_github_candidates
    return inspect_github_candidates(repo, query=query)


def _render(source):
    from backend.projects.schematic_render import render_external_schematic
    return render_external_schematic(source)


_SERVICE = ExternalSchematicService(_search, _inspect, _render)


def _enabled():
    if os.getenv("DEMO_MODE") != "0" or os.getenv("EXA_WEB_SEARCH_ENABLED") != "1" or not os.getenv("EXA_API_KEY", "").strip():
        raise ExternalSchematicConfigurationError()
    _key()


def find_external_schematic(query: str) -> ExternalSchematicManifest:
    _enabled()
    return _SERVICE.find(query)


def load_external_schematic_sheet(token: str, sheet_index: int) -> bytes:
    _enabled()
    return _SERVICE.load(token, sheet_index)
