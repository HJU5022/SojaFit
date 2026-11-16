"""공개 완성 회로도의 검색, 15분 메모리 재사용, 서명된 시트 조회. 업로드한 회로도(#52)의 그림도 같은 메모리 캐시에 둔다."""
import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
import re
import time
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import ContextVar, copy_context
from dataclasses import dataclass, replace
from math import ceil
from threading import Lock
from urllib.parse import urlsplit

from backend.projects.schematic_source import (
    ALLOWED_LICENSES, ExternalSchematicConfigurationError, ExternalSchematicInvalidSource,
    ExternalSchematicInvalidToken, ExternalSchematicNotFound, ExternalSchematicRateLimited,
    ExternalSchematicUpstreamError,
    VerifiedSchematicSource,
    provider_rate_key, provider_rate_limit, remember_provider_limit,
)

TTL = 900
LOGGER = logging.getLogger(__name__)
# [왜] 회로 연결이 있는 찾기(작업대가 프로젝트를 열 때 자동으로 부름)는 #146 공식 제조사 갈래를 건너뛰고 9c87ba36 길(GitHub 대체 포함)로 간다.
#      search · fallback_search가 (query, limit)만 받아 시험 가짜와 맞추려고 이 값으로 알린다
_CONNECTED_LOOKUP = ContextVar('connected_schematic_lookup', default=False)


@dataclass(frozen=True)
class _SearchFailure:
    reason: str


@dataclass(frozen=True)
class ExternalSchematicChoice:
    title: str
    source_url: str
    source_type: str
    revision: str | None
    manufacturer: str | None = None
    model: str | None = None
    source_file: str | None = None
    evidence_grade: int | None = None
    source_sha256: str | None = None
    commit: str | None = None
    license: str | None = None
    attribution: str | None = None
    repository_url: str | None = None
    license_evidence_url: str | None = None


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
    payload = {"version": 3, "repository": source.repository, "commit": source.commit,
               "license": source.license, "attribution": source.attribution,
               "repository_url": source.repository_url, "source_url": source.source_url,
               "source_file": source.source_file, "asset_kind": source.asset_kind,
               "asset_paths": source.asset_paths, "root_schematic": source.root_schematic,
               "count": count, "expires": expires, "source_type": source.source_type,
               "evidence_grade": source.evidence_grade, "manufacturer": source.manufacturer,
               "model": source.model, "revision": source.revision,
               "source_sha256": source.source_sha256,
               "license_evidence_url": source.license_evidence_url,
               "circuit_sha256": source.circuit_sha256}
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
        if not isinstance(fields, dict) or fields.get("version") != 3:
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
        circuit_hash = fields.get('circuit_sha256')
        if circuit_hash is not None and (not community or kind != 'kicad' or not isinstance(circuit_hash, str)
                                         or not re.fullmatch(r'[0-9a-f]{64}', circuit_hash)):
            raise ValueError
        if (not (community or public) or fields.get("evidence_grade") != expected_grade
                or not isinstance(credit, str) or not credit or not _relative(path)
                or not _relative(root) or (community and not root.lower().endswith((".sch", ".kicad_sch")))
                or kind not in ("png", "svg", "pdf", "kicad") or not isinstance(assets, list)
                or (community and (kind != 'kicad' or len(assets) > 20 or not all(_relative(p) and p.endswith('.kicad_sch') for p in assets)))
                or (public and assets) or type(count) is not int or not 1 <= count <= 20
                or type(expires) is not int or now >= expires):
            raise ValueError
        repository_url = fields.get("repository_url") or (f"https://github.com/{repo}" if community else source_url)
        return VerifiedSchematicSource(repo or "", sha or "", license_id, credit, repository_url,
                                       source_url or repository_url, path, kind, tuple(assets), root, count,
                                       source_type, fields["evidence_grade"], fields.get("manufacturer"),
                                       fields.get("model"), fields.get("revision"), source_hash,
                                       fields.get("license_evidence_url"), circuit_hash), count
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

    def replace(self, key, value):
        weight = self.weight(value)
        with self.lock:
            old = self.entries.pop(key, None)
            if old is not None:
                self.size -= old[2]
            if weight <= self.byte_capacity:
                self.entries[key] = self.clock() + self.ttl, value, weight
                self.size += weight
                while len(self.entries) > self.capacity or self.size > self.byte_capacity:
                    _, (_, _, discarded) = self.entries.popitem(last=False)
                    self.size -= discarded

    def delete(self, key):
        with self.lock:
            entry = self.entries.pop(key, None)
            if entry is not None:
                self.size -= entry[2]

    def delete_matching(self, predicate):
        with self.lock:
            for key, entry in tuple(self.entries.items()):
                if predicate(key):
                    self.entries.pop(key, None)
                    self.size -= entry[2]


def _is_board_query(query):
    from backend.projects.external_circuit_search import is_board_query
    return is_board_query(query)


def _community_candidate_limit() -> int:
    """Keep verification bounded by the discovery provider's shared limit."""
    from backend.projects.external_circuit_search import MAX_COMPONENT_REPOSITORIES
    return MAX_COMPONENT_REPOSITORIES

class ExternalSchematicService:
    def __init__(self, search, inspect, render, *, clock=time.monotonic, wall=time.time,
                 fallback_search=None, public_pdf_inspect=None, match_render=None, official_search=None,
                 query_capacity=128, image_capacity=64, image_byte_capacity=128*1024*1024,
                 ttl_seconds=TTL):
        self.search, self.inspect, self.render = search, inspect, render
        self.fallback_search = fallback_search
        self.official_search = official_search
        self.public_pdf_inspect = public_pdf_inspect
        self.match_render = match_render
        self.inspections = _Cache(query_capacity*5,0,lambda _:0,ttl_seconds,clock)
        self.wall = wall
        self.queries = _Cache(query_capacity, 0, lambda _: 0, ttl_seconds, clock)
        self.candidates = _Cache(query_capacity, 0, lambda _: 0, ttl_seconds, clock)
        self.images = _Cache(image_capacity, image_byte_capacity, lambda sheets: sum(map(len, sheets)), ttl_seconds, clock)
        self.verified_choices = _Cache(query_capacity, 0, lambda value: 0, ttl_seconds, clock)
        self.validated = _Cache(query_capacity, 0, lambda value: 0, ttl_seconds, clock)
        self.retry_until = OrderedDict()
        self.retry_lock = Lock()

    def _remember_choices(self, query, sources):
        choices = list(self.verified_choices.get(query, lambda: ()))
        seen = {choice.source_url for choice in choices}
        for source in sources:
            if source.source_type != "community" or not source.source_url or source.source_url in seen:
                continue
            seen.add(source.source_url)
            title = f"{source.repository or source.attribution} · {source.root_schematic}"
            choices.append(ExternalSchematicChoice(
                title, source.source_url, source.source_type, source.revision,
                manufacturer=source.manufacturer,
                model=source.model,
                source_file=source.source_file,
                evidence_grade=source.evidence_grade,
                source_sha256=source.source_sha256,
                commit=source.commit,
                license=source.license,
                attribution=source.attribution,
                repository_url=source.repository_url,
                license_evidence_url=source.license_evidence_url,
            ))
        self.verified_choices.replace(query, tuple(choices))

    def _choices_for(self, query):
        return self.verified_choices.get(query, lambda: ())

    def _clear_query_caches(self, query):
        self.queries.delete_matching(lambda key: key == query or (isinstance(key, tuple) and key[:1] == (query,)))
        self.candidates.delete(query)
        self.validated.delete(query)
        self.verified_choices.delete(query)
        public_query = query[0] if isinstance(query, tuple) else query
        self.candidates.delete(('official-datasheet', public_query))
        self.inspections.delete_matching(lambda key: key[1] == public_query)
        with self.retry_lock:
            self.retry_until.pop(query, None)

    def _retry_deadline(self, query):
        with self.retry_lock:
            value = self.retry_until.get(query)
            if value is not None:
                self.retry_until.move_to_end(query)
            return value[0] if value is not None else None

    def _retry_error(self, query):
        with self.retry_lock:
            entry = self.retry_until.get(query)
        if entry is not None and entry[1] is not None and entry[0] > self.wall():
            host, phase, status, key = entry[1]
            if key == provider_rate_key(host):
                return ExternalSchematicRateLimited(ceil(entry[0] - self.wall()), host=host, phase=phase, status_code=status)
        return None

    def _set_retry_deadline(self, query, deadline, error=None):
        with self.retry_lock:
            previous = self.retry_until.get(query)
            if (previous is not None and previous[1] is not None and previous[0] > self.wall()
                    and previous[1][3] == provider_rate_key(previous[1][0])):
                return
            metadata = (error.host, error.phase, error.status_code, provider_rate_key(error.host)) if error is not None else None
            self.retry_until[query] = (deadline, metadata)
            self.retry_until.move_to_end(query)
            while len(self.retry_until) > self.queries.capacity:
                self.retry_until.popitem(last=False)

    def _sheets(self, source, connections=None):
        def produce():
            if connections is not None and self.match_render is None:
                raise ExternalSchematicInvalidSource()
            result = self.match_render(source, connections) if connections is not None else self.render(source)
            if not 1 <= len(result) <= 20:
                raise ExternalSchematicInvalidSource("시트 수가 허용 범위를 벗어났습니다.")
            return result
        return self.images.get(source, produce)

    def _find(self, query, connections=None, selected_url=None):
        from backend.projects.external_circuit_search import (
            WebSchematicRef, GitHubRepositoryRef, component_context, is_tsc_query,
            semiconductor_manufacturer, semiconductor_part_query, semiconductor_source_manufacturer,
            _SEMICONDUCTOR_MANUFACTURERS,
        )
        bare_part = semiconductor_part_query(query) if connections is None and not is_tsc_query(query) else None
        known_board = _is_board_query(query) and connections is None and component_context(query) is None
        if connections is not None:
            from backend.projects.netlist import circuit_fingerprint
            circuit_hash = circuit_fingerprint(connections)
        lookup_key = (query, circuit_hash) if connections is not None else query
        def scoped_sources(sources):
            if connections is None:
                return tuple(source for source in sources if source.source_type != 'community' or source.asset_kind == 'kicad')
            return tuple(replace(source,circuit_sha256=circuit_hash) for source in sources
                         if source.source_type == 'community' and source.asset_kind == 'kicad')
        saw_upstream_failure = False
        rate_error = None
        retry_budget = 1
        counts = {"candidate_count": 0, "inspect_rejected": 0, "render_rejected": 0}

        def official_pdf(candidate):
            return (connections is None and isinstance(candidate, WebSchematicRef)
                    and candidate.source_type == 'manufacturer_official' and candidate.asset_kind == 'pdf'
                    and semiconductor_source_manufacturer(candidate.source_url) is not None)

        def inspect_candidate(candidate):
            hosts = ('api.github.com', 'raw.githubusercontent.com', 'codeload.github.com') if isinstance(candidate, GitHubRepositoryRef) else (
                (urlsplit(candidate.source_url).hostname, urlsplit(candidate.page_url).hostname)
                if isinstance(candidate, WebSchematicRef) else ())
            for host in hosts:
                if limited := provider_rate_limit(host):
                    raise limited
            try:
                if official_pdf(candidate):
                    from backend.projects.schematic_render import official_pdf_inspection_slot
                    with official_pdf_inspection_slot(candidate.source_url):
                        return tuple(self.inspect(candidate, query=query))
                return tuple(self.inspect(candidate, query=query))
            except ExternalSchematicRateLimited as error:
                remember_provider_limit(error)
                raise

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

        def cached_inspection(candidate):
            return self.inspections.get((candidate, query), lambda: inspect_candidate(candidate))

        def candidate_inspections(candidates):
            index = 0
            while index < len(candidates):
                candidate = candidates[index]
                if (official_pdf(candidate) and index + 1 < len(candidates)
                        and official_pdf(candidates[index + 1])):
                    from backend.projects.schematic_render import clear_checked_pdfs
                    batch = candidates[index:index + 2]
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        futures = [pool.submit(copy_context().run, cached_inspection, item) for item in batch]
                    try:
                        yield from zip(batch, futures)
                    finally:
                        clear_checked_pdfs()
                    index += 2
                else:
                    yield candidate, None
                    index += 1

        def try_candidates(candidates):
            nonlocal saw_upstream_failure, rate_error
            verified = []
            mirrors = []

            def rendered(source):
                nonlocal saw_upstream_failure, rate_error
                try:
                    _sign(source, source.expected_sheets, int(self.wall()) + TTL)
                    sheets = retry_once(lambda: self._sheets(source, connections))
                    if len(sheets) != source.expected_sheets:
                        raise ExternalSchematicInvalidSource("원본과 시트 수가 다릅니다.")
                    return (source, len(sheets))
                except ExternalSchematicInvalidSource:
                    counts['render_rejected'] += 1
                except ExternalSchematicRateLimited as error:
                    rate_error = error
                except ExternalSchematicUpstreamError:
                    saw_upstream_failure = True
                return None

            web_limit = len(_SEMICONDUCTOR_MANUFACTURERS) if bare_part else 5
            counts["candidate_count"] += len(candidates[:web_limit])
            for candidate, prefetched in candidate_inspections(candidates[:web_limit]):
                if connections is not None and isinstance(candidate, WebSchematicRef):
                    counts['inspect_rejected'] += 1
                    continue
                if known_board and not isinstance(candidate, WebSchematicRef):
                    counts['inspect_rejected'] += 1
                    continue
                pending = [prefetched] if prefetched is not None else []
                def inspect_current():
                    return pending.pop().result() if pending else cached_inspection(candidate)
                try:
                    sources = retry_once(inspect_current)
                except ExternalSchematicInvalidSource:
                    counts["inspect_rejected"] += 1
                    continue
                except ExternalSchematicRateLimited as error:
                    rate_error = error
                    continue
                except ExternalSchematicUpstreamError:
                    saw_upstream_failure = True
                    continue
                if not sources:
                    counts["inspect_rejected"] += 1
                for source in sources:
                    if connections is not None:
                        if source.source_type != 'community' or source.asset_kind != 'kicad':
                            counts['inspect_rejected'] += 1
                            continue
                        source = replace(source, circuit_sha256=circuit_hash)
                    if source.source_type == 'public_web':
                        mirrors.append(source)
                        break
                    if source.source_type == 'community' and (known_board or source.asset_kind != 'kicad'):
                        counts['inspect_rejected'] += 1
                        continue
                    result = rendered(source)
                    if result is None:
                        continue
                    verified.append(result)
                    if source.source_type == 'community':
                        return tuple(verified)
                    break
            originals = {(s.source_sha256, s.asset_kind): s for s, _ in verified
                         if s.source_type == 'manufacturer_official' and s.source_sha256}
            for source in mirrors:
                original = originals.get((source.source_sha256, source.asset_kind))
                if original is not None and original.expected_sheets == source.expected_sheets:
                    source = replace(source, model=original.model or query, revision=original.revision,
                                     manufacturer=original.manufacturer)
                else:
                    if known_board or source.asset_kind != 'pdf' or self.public_pdf_inspect is None:
                        counts['inspect_rejected'] += 1
                        continue
                    try:
                        digest, count = retry_once(lambda: self.public_pdf_inspect(source, query=query))
                        if digest != source.source_sha256 or count != source.expected_sheets:
                            raise ExternalSchematicInvalidSource()
                    except ExternalSchematicInvalidSource:
                        counts['inspect_rejected'] += 1
                        continue
                    except ExternalSchematicRateLimited as error:
                        rate_error = error
                        continue
                    except ExternalSchematicUpstreamError:
                        saw_upstream_failure = True
                        continue
                    source = replace(source, model=query, revision=None, manufacturer=None)
                if result := rendered(source):
                    verified.append(result)
            return tuple(verified)

        search_key = ('connected', query) if connections is not None else query  # 연결 찾기와 공식 갈래 후보를 섞지 않는다
        candidates = self.candidates.get(search_key, lambda: self.search(query, _community_candidate_limit()))
        community_candidates = bool(candidates) and not any(isinstance(candidate, WebSchematicRef) for candidate in candidates)
        if community_candidates and known_board:
            return _SearchFailure('validation_failed')
        if community_candidates:
            counts["candidate_count"] += len(candidates[:_community_candidate_limit()])
            def inspect_all():
                found = []
                local_rate = None
                local_upstream = False
                inspectable = candidates[:_community_candidate_limit()]
                inspected = 0
                for candidate in inspectable:
                    inspected += 1
                    try:
                        found.extend(scoped_sources(retry_once(lambda candidate=candidate: self.inspections.get((candidate,query),lambda:inspect_candidate(candidate)))))
                    except ExternalSchematicInvalidSource:
                        continue
                    except ExternalSchematicRateLimited as error:
                        local_rate = error
                        if error.host in {'api.github.com', 'raw.githubusercontent.com', 'codeload.github.com'}:
                            break
                    except ExternalSchematicUpstreamError:
                        local_upstream = True
                        continue
                LOGGER.info(
                    "external_schematic_candidate_pool candidates=%d inspected=%d sources=%d rate_limited=%s upstream_error=%s",
                    len(candidates), inspected, len(found), bool(local_rate), local_upstream,
                )
                if local_rate is not None or local_upstream:
                    retry_after = local_rate.retry_after if local_rate is not None else 60
                    self._set_retry_deadline(lookup_key, self.wall() + retry_after, local_rate)
                if not found:
                    if local_rate is not None:
                        raise local_rate
                    if local_upstream:
                        raise ExternalSchematicUpstreamError()
                return tuple(found), local_rate, local_upstream
            sources, pool_rate, pool_upstream = self.validated.get(lookup_key, inspect_all)
            sources = tuple(sorted(sources, key=lambda source: source.expected_sheets))
            verified_sources = []
            render_rate = None
            render_upstream = False
            for source in sources:
                try:
                    _sign(source, source.expected_sheets, int(self.wall()) + TTL)
                    sheets = retry_once(lambda source=source: self._sheets(source, connections))
                    if len(sheets) != source.expected_sheets:
                        raise ExternalSchematicInvalidSource()
                except ExternalSchematicInvalidSource:
                    continue
                except ExternalSchematicRateLimited as error:
                    rate_error = error
                    render_rate = error
                    continue
                except ExternalSchematicUpstreamError:
                    saw_upstream_failure = True
                    render_upstream = True
                    continue
                verified_sources.append(source)
            sources = tuple(verified_sources)
            pool_rate = pool_rate or render_rate
            pool_upstream = pool_upstream or render_upstream
            if (render_rate is not None or render_upstream) and self._retry_deadline(lookup_key) is None:
                retry_after = pool_rate.retry_after if pool_rate is not None else 60
                self._set_retry_deadline(lookup_key, self.wall() + retry_after, pool_rate)
            self.validated.replace(lookup_key, (sources, pool_rate, pool_upstream))
            self._remember_choices(lookup_key, sources)
            if not sources:
                counts["inspect_rejected"] += 1
            if not sources:
                if pool_rate is not None:
                    raise pool_rate
                if pool_upstream:
                    raise ExternalSchematicUpstreamError()
            if selected_url is not None:
                sources = tuple(source for source in sources if source.source_url == selected_url)
                if not sources:
                    return None
                for source in sources:
                    try:
                        _sign(source, source.expected_sheets, int(self.wall()) + TTL)
                        sheets = retry_once(lambda: self._sheets(source, connections))
                        if len(sheets) != source.expected_sheets:
                            raise ExternalSchematicInvalidSource()
                        return source, len(sheets)
                    except ExternalSchematicInvalidSource:
                        continue
                    except ExternalSchematicRateLimited as error:
                        rate_error = error
                    except ExternalSchematicUpstreamError:
                        saw_upstream_failure = True
                if rate_error is not None:
                    raise rate_error
                if saw_upstream_failure:
                    raise ExternalSchematicUpstreamError()
                return None
            for source in sources:
                try:
                    _sign(source, source.expected_sheets, int(self.wall()) + TTL)
                    sheets = retry_once(lambda: self._sheets(source, connections))
                    if len(sheets) != source.expected_sheets:
                        raise ExternalSchematicInvalidSource()
                    return source, len(sheets)
                except ExternalSchematicInvalidSource:
                    continue
                except ExternalSchematicRateLimited as error:
                    rate_error = error
                except ExternalSchematicUpstreamError:
                    saw_upstream_failure = True
            if rate_error is not None:
                raise rate_error
            if saw_upstream_failure:
                raise ExternalSchematicUpstreamError()
            if pool_rate is not None:
                raise pool_rate
            if pool_upstream:
                raise ExternalSchematicUpstreamError()
            LOGGER.info("schematic_lookup_failed", extra={"reason": "validation_failed", **counts})
            return _SearchFailure('circuit_mismatch' if connections is not None else 'validation_failed')
        official_part_candidates = bare_part and any(isinstance(candidate, WebSchematicRef)
            and semiconductor_source_manufacturer(candidate.source_url) for candidate in candidates)
        result = try_candidates(candidates)
        if (not result and official_part_candidates and self.official_search
                and not rate_error and not saw_upstream_failure
                and not re.search(r'\bdatasheet\b|데이터시트', query, re.I)):
            # Application-note discovery can miss the manufacturer's product
            # datasheet. Spend at most one separate official-only query.
            datasheets = self.candidates.get(('official-datasheet', query),
                lambda: self.official_search(query, len(_SEMICONDUCTOR_MANUFACTURERS)))
            result = try_candidates(datasheets)
        if result:
            if bare_part:
                manufacturers = {semiconductor_source_manufacturer(source.source_url)
                                 for source, _ in result if source.source_type == 'manufacturer_official'} - {None}
                if len(manufacturers) > 1:
                    return _SearchFailure('ambiguous_manufacturer')
                if manufacturers and rate_error is not None:
                    raise rate_error
                if manufacturers and saw_upstream_failure:
                    raise ExternalSchematicUpstreamError()
                return result[:5]
            return result
        # Official candidates are authoritative only after rendering and hash
        # validation. If that validation fails, lazily spend the grade-3 slot.
        if (connections is not None or (not is_tsc_query(query) and semiconductor_manufacturer(query) is None)) and not official_part_candidates and not known_board and self.fallback_search and any(isinstance(candidate, WebSchematicRef) for candidate in candidates):
            repositories = self.candidates.get(('community', query), lambda: self.fallback_search(query, _community_candidate_limit()))
            if repositories and all(isinstance(candidate,GitHubRepositoryRef) for candidate in repositories):
                self.candidates.replace(search_key,repositories)
                return self._find(query,connections,selected_url)
            result = try_candidates(repositories)
            if result:
                return result
        if rate_error is not None:
            raise rate_error
        if saw_upstream_failure:
            raise ExternalSchematicUpstreamError()
        reason = 'circuit_mismatch' if connections is not None else "validation_failed" if counts["candidate_count"] else "no_candidates"
        LOGGER.info("schematic_lookup_failed", extra={"reason": reason, **counts})
        return _SearchFailure(reason)

    def find(self, query, selected_url=None, *, connections=None):
        from backend.projects.external_circuit_search import canonical_tsc_query
        normalized = canonical_tsc_query(" ".join(query.split()).casefold())
        if not 2 <= len(query.strip()) <= 200:
            raise ValueError("검색어는 2~200자여야 합니다.")
        if '://' in query:
            raise ExternalSchematicNotFound()
        if selected_url is not None and (not isinstance(selected_url, str) or len(selected_url) > 2048):
            raise ExternalSchematicNotFound()
        from backend.projects.netlist import circuit_fingerprint
        lookup_key = (normalized,circuit_fingerprint(connections)) if connections is not None else normalized
        retry_until = self._retry_deadline(lookup_key)
        if retry_until is not None and self.wall() >= retry_until:
            self._clear_query_caches(lookup_key)
        def produce():
            if limited := self._retry_error(lookup_key):
                raise limited
            try:
                from backend.projects.schematic_render import official_pdf_request
                connected = _CONNECTED_LOOKUP.set(connections is not None)
                try:
                    with official_pdf_request():
                        return self._find(normalized, connections)
                finally:
                    _CONNECTED_LOOKUP.reset(connected)
            except ExternalSchematicRateLimited as error:
                self._set_retry_deadline(lookup_key, self.wall() + error.retry_after, error)
                raise

        result = self.queries.get(lookup_key, produce)
        cached_result = result
        if selected_url is not None and result is not None and not isinstance(result, _SearchFailure):
            if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], VerifiedSchematicSource):
                result = result if result[0].source_url == selected_url else None
            else:
                result = next((item for item in result if item[0].source_url == selected_url), None)
                if result is None:
                    raise ExternalSchematicNotFound()
        if result is None:
            if selected_url is not None:
                cached = self.validated.get(lookup_key, lambda: ((), None, False))
                candidates = cached[0] if isinstance(cached, tuple) and len(cached) == 3 else ()
                match = next((source for source in candidates if source.source_url == selected_url), None)
                if match is not None:
                    try:
                        sheets = self._sheets(match, connections)
                        if len(sheets) != match.expected_sheets:
                            raise ExternalSchematicInvalidSource()
                        result = (match, len(sheets))
                    except ExternalSchematicInvalidSource:
                        result = None
            if result is None:
                raise ExternalSchematicNotFound()
        if isinstance(result, _SearchFailure):
            raise ExternalSchematicNotFound(reason=result.reason)
        verified_results = cached_result if isinstance(cached_result, tuple) and cached_result and isinstance(cached_result[0], tuple) else ()
        if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], VerifiedSchematicSource):
            source, count = result
        else:
            if not result:
                raise ExternalSchematicNotFound()
            verified_results = result
            source, count = result[0]
        choices = self._choices_for(lookup_key)
        if not choices:
            choices = tuple(
                ExternalSchematicChoice(
                    ' · '.join(dict.fromkeys(filter(None, (item[0].model, item[0].source_file)))),
                    item[0].source_url,
                    item[0].source_type,
                    item[0].revision,
                    manufacturer=item[0].manufacturer,
                    model=item[0].model,
                    source_file=item[0].source_file,
                    evidence_grade=item[0].evidence_grade,
                    source_sha256=item[0].source_sha256,
                    commit=item[0].commit,
                    license=item[0].license,
                    attribution=item[0].attribution,
                    repository_url=item[0].repository_url,
                    license_evidence_url=item[0].license_evidence_url,
                )
                for item in verified_results
                if connections is not None or item[0].source_type != "community"
            )
        token = _sign(source, count, int(self.wall()) + TTL)
        return ExternalSchematicManifest(source.repository or None, source.commit or None, source.license,
                                         source.attribution, source.repository_url, source.source_url,
                                         source.source_file, token, count, source.source_type,
                                         source.evidence_grade, source.manufacturer, source.model,
                                         source.revision, source.source_sha256, source.license_evidence_url,
                                         choices)

    def load(self, token, sheet_index, *, connections=None):
        source, count = _read_token(token, self.wall())
        from backend.projects.netlist import circuit_fingerprint
        expected_hash = circuit_fingerprint(connections) if connections is not None else None
        if source.circuit_sha256 != expected_hash:
            raise ExternalSchematicInvalidToken()
        if type(sheet_index) is not int or not 0 <= sheet_index < count:
            raise ExternalSchematicInvalidToken()
        try:
            sheets = self._sheets(source, connections)
        except ExternalSchematicInvalidSource:
            raise ExternalSchematicNotFound() from None
        if len(sheets) != count:
            raise ExternalSchematicNotFound()
        return sheets[sheet_index]


def _search(query, limit):
    from backend.projects.external_circuit_search import (
        ExternalCircuitSearchConfigurationError, ExternalCircuitSearchDisabled,
        ExternalCircuitSearchError, search_github_repositories, search_manufacturer_schematics,
        search_public_schematics, _search_public_schematics, WebSchematicRef,
        component_context, component_evidence_matches, search_component_repositories,
        is_tsc_query, search_tsc_schematics, semiconductor_manufacturer, search_semiconductor_schematics, semiconductor_part_query,
    )
    try:
        # TSC is an official datasheet-only path. Never mix its results with
        # community/GitHub fallback candidates.
        connected = _CONNECTED_LOOKUP.get()
        if not connected and is_tsc_query(query):
            candidates = search_tsc_schematics(query, min(3, limit))
            LOGGER.info('schematic_search_route', extra={'phase': 'tsc_official', 'candidate_count': len(candidates)})
            return candidates
        if not connected and semiconductor_manufacturer(query) is not None:
            candidates = search_semiconductor_schematics(query, min(5, limit))
            LOGGER.info('schematic_search_route', extra={'phase': 'semiconductor_official', 'candidate_count': len(candidates)})
            return candidates
        if not connected and semiconductor_part_query(query):
            candidates = search_semiconductor_schematics(query, min(5, limit))
            LOGGER.info('schematic_search_route', extra={'phase': 'semiconductor_part_official', 'candidate_count': len(candidates)})
            if candidates:
                return candidates
        failed = False
        try:
            public = search_public_schematics(query, min(5,limit))
        except ExternalCircuitSearchError:
            public, failed = (), True
        try:
            manufacturer = search_manufacturer_schematics(query, min(5,limit))
        except ExternalCircuitSearchError:
            manufacturer, failed = (), True
        publishing = ()
        if (not manufacturer and not _is_board_query(query)
                and any(isinstance(c, WebSchematicRef) and c.source_type == 'public_web'
                        and c.asset_kind == 'pdf' and c.page_url == c.source_url for c in public)
                and not any(isinstance(c, WebSchematicRef) and c.asset_kind == 'pdf'
                            and c.page_url != c.source_url for c in public)):
            try:
                publishing = _search_public_schematics(query, min(5,limit),
                    search_text=f'{query} electronics project schematic files downloads')
            except ExternalCircuitSearchError:
                failed = True
        found, seen = [], set()
        for candidate in (*manufacturer, *publishing, *public):
            if component_context(query) == 'diode' and isinstance(candidate,WebSchematicRef) and not component_evidence_matches(query,f'{candidate.title} {candidate.page_url}'):
                continue
            identity = getattr(candidate, "source_url", candidate)
            if identity not in seen:
                seen.add(identity)
                found.append(candidate)
            if len(found) == limit:
                break
        if found:
            return tuple(found)
        repositories = search_component_repositories(query,limit) if component_context(query)=='diode' else search_github_repositories(query,limit)
        if repositories:
            return repositories
        if failed:
            raise ExternalCircuitSearchError()
        return ()
    except (ExternalCircuitSearchConfigurationError, ExternalCircuitSearchDisabled):
        raise ExternalSchematicConfigurationError() from None
    except ExternalCircuitSearchError:
        raise ExternalSchematicUpstreamError() from None


def _search_official_datasheets(query, limit):
    from backend.projects.external_circuit_search import (
        semiconductor_part_query, search_semiconductor_schematics,
        ExternalCircuitSearchDisabled, ExternalCircuitSearchConfigurationError, ExternalCircuitSearchError,
    )
    part = semiconductor_part_query(query)
    if not part:
        return ()
    try:
        return search_semiconductor_schematics(f'{part} datasheet', min(5, limit))
    except (ExternalCircuitSearchDisabled, ExternalCircuitSearchConfigurationError):
        raise ExternalSchematicConfigurationError() from None
    except ExternalCircuitSearchError:
        raise ExternalSchematicUpstreamError() from None


def _search_community(query, limit):
    from backend.projects.external_circuit_search import (
        ExternalCircuitSearchConfigurationError, ExternalCircuitSearchDisabled,
        ExternalCircuitSearchError, search_github_repositories, search_component_repositories, component_context,
        is_tsc_query, semiconductor_manufacturer,
    )
    if not _CONNECTED_LOOKUP.get() and (is_tsc_query(query) or semiconductor_manufacturer(query) is not None):
        return ()
    try:
        return search_component_repositories(query,limit) if component_context(query)=='diode' else search_github_repositories(query,limit)
    except (ExternalCircuitSearchConfigurationError, ExternalCircuitSearchDisabled):
        raise ExternalSchematicConfigurationError() from None
    except ExternalCircuitSearchError:
        raise ExternalSchematicUpstreamError() from None


def _inspect(repo, *, query):
    from backend.projects.external_circuit_search import WebSchematicRef, is_tsc_query
    if isinstance(repo, WebSchematicRef):
        from backend.projects.schematic_render import inspect_public_schematic, fingerprint_public_schematic

        if repo.source_type == 'manufacturer_official':
            source_hash, sheets = inspect_public_schematic(
                repo.source_url, repo.asset_kind, repo.model if is_tsc_query(query) else query, title=repo.title,
                page_url=repo.page_url, source_file=repo.source_file,
            )
        else:
            source_hash, sheets = fingerprint_public_schematic(repo.source_url, repo.asset_kind)
        return (VerifiedSchematicSource(
            "", "", repo.license, repo.attribution, repo.page_url,
            repo.source_url, repo.source_file, repo.asset_kind, (), repo.source_file,
            sheets, repo.source_type, repo.evidence_grade, repo.manufacturer,
            (repo.model if is_tsc_query(query) else query) if repo.source_type == 'manufacturer_official' else repo.model,
            repo.revision, source_hash, repo.license_evidence_url),)
    from backend.projects.schematic_discovery import inspect_github_candidates
    return inspect_github_candidates(repo, query=query)


def _render(source):
    from backend.projects.schematic_render import render_external_schematic, render_public_schematic
    if source.source_type != "community":
        return render_public_schematic(source)
    if source.asset_kind == "kicad" and os.getenv("KICAD_RENDERER_URL"):
        from backend.projects.schematic import KicadServiceUnavailable, render_remote_kicad

        try:
            return render_remote_kicad(source)
        except KicadServiceUnavailable:
            raise ExternalSchematicUpstreamError("KiCad 렌더러를 사용할 수 없습니다.") from None
    return render_external_schematic(source)


def _inspect_published_pdf(source, *, query):
    from backend.projects.schematic_render import inspect_published_pdf
    return inspect_published_pdf(source.source_url, query, page_url=source.repository_url,
                                 source_file=source.source_file)


def _render_matching(source, connections):
    from backend.projects.schematic_render import render_external_schematic
    if os.getenv('KICAD_RENDERER_URL'):
        from backend.projects.schematic import render_remote_kicad, KicadServiceUnavailable
        try:return render_remote_kicad(source,connections=connections)
        except KicadServiceUnavailable:raise ExternalSchematicUpstreamError() from None
    return render_external_schematic(source, expected_connections=connections)


_SERVICE = ExternalSchematicService(_search, _inspect, _render, fallback_search=_search_community,
                                   public_pdf_inspect=_inspect_published_pdf, match_render=_render_matching,
                                   official_search=_search_official_datasheets)


def _enabled():
    if os.getenv("DEMO_MODE") != "0" or os.getenv("EXA_WEB_SEARCH_ENABLED") != "1" or not os.getenv("EXA_API_KEY", "").strip():
        raise ExternalSchematicConfigurationError()
    _key()


def find_external_schematic(query: str, selected_url: str | None = None, component_type: str | None = None, *, connections=None) -> ExternalSchematicManifest:
    _enabled()
    if component_type == 'diode' and 'diode' not in query.casefold() and '다이오드' not in query:
        query = f'{query.strip()} diode'
    return _SERVICE.find(query, selected_url, connections=connections)


def load_external_schematic_sheet(token: str, sheet_index: int, *, connections=None) -> bytes:
    _enabled()
    return _SERVICE.load(token, sheet_index, connections=connections)


def _uploaded_key(source: str):
    return ("upload", hashlib.sha256(source.encode("utf-8")).hexdigest())


def remember_uploaded_sheets(source: str, sheets: tuple[bytes, ...]) -> None:
    """업로드 때 렌더러가 함께 준 그림을 캐시에 넣어 첫 화면이 다시 그리지 않게 한다."""
    _SERVICE.images.replace(_uploaded_key(source), sheets)


def uploaded_schematic_sheet(source: str) -> bytes:
    """업로드한 회로도 원문의 PNG. 15분 캐시에 없으면(만료 · 다른 인스턴스) 렌더러로 다시 그린다.

    [주의] 소유 확인은 호출자가 원문을 DB에서 읽을 때 이미 했다. 키가 원문 해시라 같은 파일은 그림 하나를 같이 쓴다.
    외부 검색이 아니므로 Exa 설정(_enabled)과 서명 키를 보지 않는다.
    """
    from backend.projects.schematic import export_uploaded_kicad
    return _SERVICE.images.get(_uploaded_key(source), lambda: export_uploaded_kicad(source)[1])[0]
