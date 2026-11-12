"""내부 문서가 부족할 때만 쓰는 Exa 외부 근거 검색 서비스."""
import json
import logging
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from urllib.parse import urljoin, urlsplit
from ipaddress import ip_address

import httpx

from backend.services.datasheet_rows import (
    GRADE2_PDF_PATHS, MAX_BYTES, PDF_PATHS, grade2_pdf, official_pdf, verified_rows,
)
# Keep five search candidates so an official manufacturer PDF that ranks below
# product pages is still considered; download and returned-row caps remain 2/3.
MAX_RESULTS = 5
MAX_DOWNLOADS = 2
LOGGER = logging.getLogger(__name__)
PART = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._+/-]{1,39}$')
TOKEN = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,30}')
OTHER_MANUFACTURER = re.compile(
    r'비셰이|비쉐이|온세미|넥스페리아|텍사스\s*인스트루먼트|'
    r'\b(?:vishay|onsemi|nexperia|diodes inc|rohm|stmicroelectronics|toshiba|'
    r'texas instruments|microchip|analog devices|TI)(?![A-Za-z])', re.I)
SAFE_TERMS = {
    'absolute', 'application', 'average', 'breakdown', 'capacitance', 'characteristics', 'circuit', 'current',
    'supply', 'output', 'input', 'operating', 'standby', 'datasheet', 'diode', 'electrical', 'equivalent', 'forward', 'frequency', 'if', 'ifsm', 'ir', 'junction',
    'leakage', 'maximum', 'official', 'package', 'peak', 'pinout', 'polarity', 'power', 'rating', 'ratings',
    'recovery', 'repetitive', 'replacement', 'resistance', 'reverse', 'schematic', 'surge', 'switching',
    'temperature', 'thermal', 'time', 'trr', 'vf', 'voltage', 'vrrm', 'vz',
}


def enabled() -> bool:
    return (os.getenv('DEMO_MODE', '1') == '0' and os.getenv('EXA_WEB_SEARCH_ENABLED') == '1'
            and bool(os.getenv('EXA_API_KEY', '').strip()))


def reference_url(value: str) -> str:
    """Return a safe public HTTPS reference URL, or an empty string."""
    if (not isinstance(value, str) or len(value) > 2048 or any(ord(c) < 32 for c in value)
            or any(c.isspace() for c in value) or '\\' in value):
        return ''
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return ''
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        return ''
    host = parsed.hostname.casefold().rstrip('.')
    if '.' not in host or host.endswith(('.local', '.localhost', '.internal')) or host in {'api.exa.ai', 'exa.ai'}:
        return ''
    try:
        if not ip_address(host).is_global:
            return ''
    except ValueError:
        if not re.fullmatch(r'[a-z0-9.-]+', host):
            return ''
    return value.strip()


def _query(parts: list[str], terms: str) -> str:
    clean_parts = list(dict.fromkeys(p for p in parts if isinstance(p, str) and PART.fullmatch(p)))[:8]
    clean_terms = list(dict.fromkeys(t.lower() for t in TOKEN.findall(terms or '') if t.lower() in SAFE_TERMS))
    if not clean_parts:
        return ''
    editions = re.findall(r'(?<!\S)([A-Z][0-9]{2,4})(?!\S)', terms or '')
    words = clean_parts + clean_terms + list(dict.fromkeys(editions))[:4]
    if 'official' not in clean_terms:
        words.append('official')
    if 'datasheet' not in clean_terms:
        words.append('datasheet')
    return ' '.join(words)[:300]


def _candidate_score(hit: dict, parts: list[str]) -> int:
    """Prefer a hit naming the requested part before generic maker PDFs."""
    haystack = f"{hit.get('title', '')} {hit.get('url', '')}".upper()
    compact = re.sub(r'[^A-Z0-9]', '', haystack)
    score = 0
    for part in parts:
        token = re.sub(r'[^A-Z0-9]', '', part.upper())
        if not token:
            continue
        # A complete requested token wins.  For family sheets, a stem such as
        # BAS16 in BAS16SERIES is still useful, but never substitutes for the
        # exact row check performed after PDF download.
        if re.search(r'(?<![A-Z0-9])' + re.escape(part.upper()) + r'(?![A-Z0-9])', haystack):
            score = max(score, 2)
        stem = re.split(r'[-_]', part.upper(), maxsplit=1)[0]
        stem = re.sub(r'[^A-Z0-9]', '', stem)
        if stem and stem in compact:
            score = max(score, 1)
    return score


# LangGraph copies context to worker threads; they share the same per-invocation lock.
_budget = ContextVar('datasheet_search_slot', default=None)


@contextmanager
def request_scope():
    # Permit one official lookup and one grade-3 fallback in the same request,
    # while retaining the per-grade single-call guard for concurrent retries.
    token = _budget.set({'grade2': Lock(), 'grade3': Lock()})
    try:
        yield
    finally:
        _budget.reset(token)


def _body(client, method, url, limit, *, redirect_validator=None, **kwargs):
    deadline = monotonic() + 12
    for _ in range(2):
        with client.stream(method, url, headers={'Accept-Encoding': 'identity', **kwargs.pop('headers', {})}, **kwargs) as response:
            if response.is_redirect:
                location = response.headers.get('location')
                if not redirect_validator or not location:
                    raise ValueError('redirect not allowed')
                next_url = redirect_validator(urljoin(url, location))
                if not next_url or urlsplit(next_url).hostname != urlsplit(url).hostname:
                    raise ValueError('redirect host not allowed')
                url = next_url
                continue
            response.raise_for_status()
            if response.headers.get('content-encoding', 'identity') != 'identity':
                raise ValueError('unexpected encoding')
            data = bytearray()
            for block in response.iter_bytes(chunk_size=65536):
                if monotonic() > deadline or len(data) + len(block) > limit:
                    raise ValueError('response too large')
                data.extend(block)
            return bytes(data), url
    raise ValueError('too many redirects')


def search_evidence(parts: list[str], terms: str, *, grade=None, transport=None) -> list[dict]:
    query = _query(parts, terms)
    words = sorted({t.lower() for t in TOKEN.findall(terms or '') if t.lower() in SAFE_TERMS}
                   - {'datasheet', 'official', 'circuit', 'diode', 'replacement'})
    if not enabled() or not query or not words:
        return []
    slots = _budget.get()
    slot = slots.get('grade2' if grade == 2 else 'grade3') if isinstance(slots, dict) else slots
    if slot is not None and not slot.acquire(blocking=False):
        return []
    parts = list(dict.fromkeys(p for p in parts if isinstance(p, str) and PART.fullmatch(p)))[:8]
    paths = GRADE2_PDF_PATHS if grade == 2 else PDF_PATHS
    raw_terms = terms or ''
    if grade == 2:
        # Preserve an explicitly requested manufacturer.  The host name is not
        # enough for aliases such as “Taiwan Semiconductor” or Korean names.
        makers = []
        if re.search(r'(?:\btsc\b|\btaiwan\s+semiconductor\b|\uB300\uB9CC\s*\uBC18\uB3C4\uCCB4|\uD0C0\uC774\uC644\s*\uC138\uBBF8)', raw_terms, re.I):
            makers.append('services.taiwansemi.com')
        if re.search(r'(?:\binfineon\b|\uC778\uD53C\uB2C8\uC5B8)', raw_terms, re.I):
            makers.append('www.infineon.com')
    else:
        tokens = {t.lower() for t in TOKEN.findall(raw_terms)}
        makers = [host for host in paths if host.split('.')[-2] in tokens]
    filters = [host + paths[host] for host in makers or paths]
    LOGGER.debug('datasheet_lookup stage=query query=%s domains=%s grade=%s', query, filters, grade)
    docs, seen = [], set()
    with httpx.Client(transport=transport, timeout=10, trust_env=False, follow_redirects=False) as client:
        try:
            response_body, _ = _body(client, 'POST', 'https://api.exa.ai/search', 256 * 1024,
                                       headers={'x-api-key': os.environ['EXA_API_KEY']},
                                       json={'query': query, 'numResults': MAX_RESULTS,
                                             'includeDomains': filters, 'type': 'auto'})
            payload = json.loads(response_body)
        except (httpx.HTTPError, ValueError, TypeError, KeyError, RecursionError):
            return []
        results = payload.get('results') if isinstance(payload, dict) else None
        if not isinstance(results, list):
            return []
        candidates = [hit for hit in results[:MAX_RESULTS] if isinstance(hit, dict)]
        candidates.sort(key=lambda hit: _candidate_score(hit, parts), reverse=True)
        for hit in candidates:
            raw_url = hit.get('url') if isinstance(hit, dict) else ''
            url = official_pdf(raw_url, grade=grade)
            if not url:
                LOGGER.debug('datasheet_candidate_rejected stage=url_filter reason=not_official_pdf')
                continue
            if url in seen:
                LOGGER.debug('datasheet_candidate_rejected stage=dedupe reason=duplicate url=%s', urlsplit(url).path[:160])
                continue
            if makers and urlsplit(url).hostname not in makers:
                LOGGER.debug('datasheet_candidate_rejected stage=maker_filter reason=host_mismatch url=%s', urlsplit(url).path[:160])
                continue
            seen.add(url)
            try:
                raw, url = _body(client, 'GET', url, MAX_BYTES,
                            redirect_validator=(grade2_pdf if grade == 2 else None))
                rows = verified_rows(raw, url, parts, words, grade=grade) if raw.startswith(b'%PDF-') else []
            except (ValueError, httpx.HTTPError):
                LOGGER.debug('datasheet_candidate_rejected stage=fetch reason=unreadable_pdf url=%s', urlsplit(url).path[:160])
                rows = []
            if not rows:
                LOGGER.debug('datasheet_candidate_rejected stage=row_parser reason=no_exact_verified_row url=%s', urlsplit(url).path[:160])
            title = urlsplit(url).path.rsplit('/', 1)[-1]
            for row in rows[:MAX_RESULTS - len(docs)]:
                docs.append({**row, 'chunk_id': f'W{len(docs)+1}', 'file': title,
                             'title': title, 'source_type': 'external_web', 'source_url': url,
                             'retrieved_at': datetime.now(timezone.utc).isoformat()})
            if len(docs) == MAX_RESULTS or len(seen) >= MAX_DOWNLOADS:
                break
    return docs


def search_grade2_evidence(parts: list[str], terms: str, *, transport=None) -> list[dict]:
    """Search only validated manufacturer PDFs for evidence grade 2."""
    if OTHER_MANUFACTURER.search(terms or ''):
        return []
    return search_evidence(parts, terms, grade=2, transport=transport)


def search_grade3_reference(parts: list[str], terms: str, *, transport=None) -> list[dict]:
    """Search public web references without downloading or injecting page text."""
    if not enabled():
        return []
    wanted = list(dict.fromkeys(p.upper() for p in parts if isinstance(p, str) and PART.fullmatch(p)))[:8]
    query = _query(parts, terms)
    if not wanted or not query:
        return []
    slot = _budget.get()
    if isinstance(slot, dict):
        slot = slot.get('grade3')
    if slot is not None and not slot.acquire(blocking=False):
        return []
    try:
        with httpx.Client(transport=transport, timeout=10, trust_env=False, follow_redirects=False) as client:
            body, _ = _body(client, 'POST', 'https://api.exa.ai/search', 256 * 1024,
                            headers={'x-api-key': os.environ['EXA_API_KEY']},
                            json={'query': query, 'numResults': MAX_RESULTS, 'type': 'auto'})
        payload = json.loads(body)
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return []
    results = payload.get('results') if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return []
    found = []
    for hit in results:
        if not isinstance(hit, dict):
            continue
        url = reference_url(hit.get('url', ''))
        title = str(hit.get('title') or '').strip()[:240]
        haystack = f'{title} {url}'.upper()
        matched = [p for p in wanted if re.search(r'(?<![A-Z0-9])' + re.escape(p) + r'(?![A-Z0-9])', haystack)]
        if not url or not matched:
            continue
        found.append({'source_type': 'external_web_reference', 'source_url': url,
                      'title': title or url, 'file': title or url, 'doc_parts': matched,
                      'retrieved_at': datetime.now(timezone.utc).isoformat(),
                      'evidence_grade': 3})
        if len(found) >= MAX_RESULTS:
            break
    return found
