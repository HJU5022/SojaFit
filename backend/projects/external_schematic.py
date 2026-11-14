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
    ExternalSchematicInvalidToken, ExternalSchematicNotFound, ExternalSchematicRateLimited,
    ExternalSchematicUpstreamError,
    VerifiedSchematicSource,
)

TTL = 900


@dataclass(frozen=True)
class ExternalSchematicChoice:
    title: str
    source_url: str
    source_type: str
    revision: str | None


@dataclass(frozen=True)
class ExternalSchematicManifest:
    project: str | None
    commit: str | None
    license: str
    attribution: str
    repository_url: str
    source_url: str
    source_file: str
    token: str
    sheet_count: int
    source_type: str = "community"
    evidence_grade: int | None = 3
    manufacturer: str | None = None
    model: str | None = None
    revision: str | None = None
    source_sha256: str | None = None
    license_evidence_url: str | None = None
    choices: tuple[ExternalSchematicChoice, ...] = ()


def _key():
    secret = os.getenv("AUTH_SECRET", "").encode()
    if len(secret) < 32:
        raise ExternalSchematicConfigurationError("회로도 서명 키가 필요합니다.")
    return hmac.digest(secret, b"sojafit/external-schematic/v1", "sha256")


def _encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=")


def _sign(source, count, expires):
    payload = {"version": 2, "repository": source.repository, "commit": source.commit,
               "license": source.license, "attribution": source.attribution,
               "repository_url": source.repository_url, "source_url": source.source_url,
               "source_file": source.source_file, "asset_kind": source.asset_kind,
               "asset_paths": source.asset_paths, "root_schematic": source.root_schematic,
               "count": count, "expires": expires, "source_type": source.source_type,
               "evidence_grade": source.evidence_grade, "manufacturer": source.manufacturer,
               "model": source.model, "revision": source.revision,
               "source_sha256": source.source_sha256,
               "license_evidence_url": source.license_evidence_url}
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
        if not isinstance(fields, dict) or fields.get("version") != 2:
            raise ValueError
        source_type = fields.get("source_type")
        repo, sha = fields.get("repository"), fields.get("commit")
        license_id, credit = fields.get("license"), fields.get("attribution")
        path, kind, assets, root = (fields.get(key) for key in ("source_file", "asset_kind", "asset_paths", "root_schematic"))
        count, expires = fields.get("count"), fields.get("expires")
        source_url, source_hash = fields.get("source_url"), fields.get("source_sha256")
        community = (source_type == "community" and isinstance(repo, str)
                     and bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo))
                     and bool(re.fullmatch(r"[0-9a-f]{40}", sha or ""))
                     and license_id in ALLOWED_LICENSES)
        public = (source_type in {"manufacturer_official", "public_web"} and isinstance(source_url, str)
                    and bool(re.fullmatch(r"https://[^\s]+", source_url))
                    and isinstance(source_hash, str) and bool(re.fullmatch(r"[0-9a-f]{64}", source_hash)))
        expected_grade = 3 if community else 2 if source_type == "manufacturer_official" else None
        if (not (community or public) or fields.get("evidence_grade") != expected_grade
                or not isinstance(credit, str) or not credit or not _relative(path)
                or not _relative(root) or (community and not root.lower().endswith((".sch", ".kicad_sch")))
                or kind not in ("png", "svg", "pdf", "kicad") or not isinstance(assets, list)
                or (community and (not all(_relative(p) for p in assets) or bool(assets) == (kind == "kicad")))
                or (public and assets) or type(count) is not int or not 1 <= count <= 20
                or type(expires) is not int or now >= expires):
            raise ValueError
        repository_url = fields.get("repository_url") or (f"https://github.com/{repo}" if community else source_url)
        return VerifiedSchematicSource(repo or "", sha or "", license_id, credit, repository_url,
                                       source_url or repository_url, path, kind, tuple(assets), root, count,
                                       source_type, fields["evidence_grade"], fields.get("manufacturer"),
                                       fields.get("model"), fields.get("revision"), source_hash,
                                       fields.get("license_evidence_url")), count
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
                 fallback_search=None,
                 query_capacity=128, image_capacity=64, image_byte_capacity=128*1024*1024,
                 ttl_seconds=TTL):
        self.search, self.inspect, self.render = search, inspect, render
        self.fallback_search = fallback_search
        self.wall = wall
        self.queries = _Cache(query_capacity, 0, lambda _: 0, ttl_seconds, clock)
        self.candidates = _Cache(query_capacity, 0, lambda _: 0, ttl_seconds, clock)
        self.images = _Cache(image_capacity, image_byte_capacity, lambda sheets: sum(map(len, sheets)), ttl_seconds, clock)

    def _sheets(self, source):
        def produce():
            result = self.render(source)
            if not 1 <= len(result) <= 20:
                raise ExternalSchematicInvalidSource("시트 수가 허용 범위를 벗어났습니다.")
            return result
        return self.images.get(source, produce)

    def _find(self, query):
        from backend.projects.external_circuit_search import WebSchematicRef
        saw_upstream_failure = False
        rate_error = None
        retry_budget = 1

        def retry_once(operation):
            nonlocal saw_upstream_failure, retry_budget
            try:
                return operation()
            except ExternalSchematicUpstreamError:
                saw_upstream_failure = True
                if not retry_budget:
                    raise
                retry_budget -= 1
                return operation()

        def try_candidates(candidates):
            nonlocal saw_upstream_failure, rate_error
            verified = []
            for candidate in candidates[:5]:
                try:
                    sources = retry_once(lambda: tuple(self.inspect(candidate, query=query)))
                except ExternalSchematicInvalidSource:
                    continue
                except ExternalSchematicRateLimited as error:
                    rate_error = error
                    continue
                except ExternalSchematicUpstreamError:
                    saw_upstream_failure = True
                    continue
                for source in sources:
                    try:
                        _sign(source, source.expected_sheets, int(self.wall()) + TTL)
                        sheets = retry_once(lambda: self._sheets(source))
                        if len(sheets) != source.expected_sheets:
                            raise ExternalSchematicInvalidSource("원본과 시트 수가 다릅니다.")
                    except ExternalSchematicInvalidSource:
                        continue
                    except ExternalSchematicRateLimited as error:
                        rate_error = error
                        continue
                    except ExternalSchematicUpstreamError:
                        saw_upstream_failure = True
                        continue
                    verified.append((source, len(sheets)))
                    if not isinstance(candidate, WebSchematicRef):
                        return tuple(verified)
                    break
            return tuple(verified)

        candidates = self.candidates.get(query, lambda: self.search(query, 5))
        result = try_candidates(candidates)
        if result:
            return result
        # Official candidates are authoritative only after rendering and hash
        # validation. If that validation fails, lazily spend the grade-3 slot.
        if self.fallback_search and any(isinstance(candidate, WebSchematicRef) for candidate in candidates):
            result = try_candidates(self.fallback_search(query, 5))
            if result:
                return result
        if rate_error is not None:
            raise rate_error
        if saw_upstream_failure:
            raise ExternalSchematicUpstreamError()
        return None

    def find(self, query, selected_url=None):
        normalized = " ".join(query.split()).casefold()
        if not 2 <= len(query.strip()) <= 200:
            raise ValueError("검색어는 2~200자여야 합니다.")
        if selected_url is not None and (not isinstance(selected_url, str) or len(selected_url) > 2048):
            raise ExternalSchematicNotFound()
        results = self.queries.get(normalized, lambda: self._find(normalized))
        if not results:
            raise ExternalSchematicNotFound()
        result = results[0] if selected_url is None else next(
            (result for result in results if result[0].source_type != "community"
             and result[0].source_url == selected_url), None)
        if result is None:
            raise ExternalSchematicNotFound()
        source, count = result
        choices = tuple(ExternalSchematicChoice(candidate.model or candidate.source_file, candidate.source_url,
                                               candidate.source_type, candidate.revision)
                        for candidate, _ in results if candidate.source_type != "community")
        token = _sign(source, count, int(self.wall()) + TTL)
        return ExternalSchematicManifest(source.repository or None, source.commit or None, source.license,
                                         source.attribution, source.repository_url, source.source_url,
                                         source.source_file, token, count, source.source_type,
                                         source.evidence_grade, source.manufacturer, source.model,
                                         source.revision, source.source_sha256, source.license_evidence_url,
                                         choices)

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
        ExternalCircuitSearchError, search_github_repositories, search_manufacturer_schematics,
        search_public_schematics,
    )
    try:
        failed = False
        try:
            public = search_public_schematics(query, limit)
        except ExternalCircuitSearchError:
            public, failed = (), True
        try:
            manufacturer = search_manufacturer_schematics(query, limit)
        except ExternalCircuitSearchError:
            manufacturer, failed = (), True
        found, seen = [], set()
        for candidate in (*manufacturer, *public):
            identity = getattr(candidate, "source_url", candidate)
            if identity not in seen:
                seen.add(identity)
                found.append(candidate)
            if len(found) == limit:
                break
        if found:
            return tuple(found)
        repositories = search_github_repositories(query, limit)
        if repositories:
            return repositories
        if failed:
            raise ExternalCircuitSearchError()
        return ()
    except (ExternalCircuitSearchConfigurationError, ExternalCircuitSearchDisabled):
        raise ExternalSchematicConfigurationError() from None
    except ExternalCircuitSearchError:
        raise ExternalSchematicUpstreamError() from None


def _search_community(query, limit):
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
    from backend.projects.external_circuit_search import WebSchematicRef
    if isinstance(repo, WebSchematicRef):
        from backend.projects.schematic_render import inspect_public_schematic

        source_hash, sheets = inspect_public_schematic(
            repo.source_url, repo.asset_kind, query, title=repo.title,
            page_url=repo.page_url, source_file=repo.source_file,
        )
        return (VerifiedSchematicSource(
            "", "", repo.license, repo.attribution, repo.page_url,
            repo.source_url, repo.source_file, repo.asset_kind, (), repo.source_file,
            sheets, repo.source_type, repo.evidence_grade, repo.manufacturer,
            repo.model, repo.revision, source_hash, repo.license_evidence_url),)
    from backend.projects.schematic_discovery import inspect_github_candidates
    return inspect_github_candidates(repo, query=query)


def _render(source):
    from backend.projects.schematic_render import render_external_schematic, render_public_schematic
    return render_external_schematic(source) if source.source_type == "community" else render_public_schematic(source)


_SERVICE = ExternalSchematicService(_search, _inspect, _render, fallback_search=_search_community)


def _enabled():
    if os.getenv("DEMO_MODE") != "0" or os.getenv("EXA_WEB_SEARCH_ENABLED") != "1" or not os.getenv("EXA_API_KEY", "").strip():
        raise ExternalSchematicConfigurationError()
    _key()


def find_external_schematic(query: str, selected_url: str | None = None) -> ExternalSchematicManifest:
    _enabled()
    return _SERVICE.find(query, selected_url)


def load_external_schematic_sheet(token: str, sheet_index: int) -> bytes:
    _enabled()
    return _SERVICE.load(token, sheet_index)
