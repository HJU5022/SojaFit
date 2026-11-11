"""내부 문서가 부족할 때만 쓰는 Exa 외부 근거 검색 서비스."""
import json
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit

import httpx

from backend.services.datasheet_rows import MAX_BYTES, PDF_PATHS, official_pdf, verified_rows
MAX_RESULTS = 3
MAX_DOWNLOADS = 2
PART = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._+/-]{1,39}$')
TOKEN = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,30}')
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


def _query(parts: list[str], terms: str) -> str:
    clean_parts = list(dict.fromkeys(p for p in parts if isinstance(p, str) and PART.fullmatch(p)))[:8]
    clean_terms = list(dict.fromkeys(t.lower() for t in TOKEN.findall(terms or '') if t.lower() in SAFE_TERMS))
    if not clean_parts:
        return ''
    words = clean_parts + clean_terms
    if 'official' not in clean_terms:
        words.append('official')
    if 'datasheet' not in clean_terms:
        words.append('datasheet')
    return ' '.join(words)[:300]


# LangGraph copies context to worker threads; they share the same per-invocation lock.
_budget = ContextVar('datasheet_search_slot', default=None)


@contextmanager
def request_scope():
    token = _budget.set(Lock())
    try:
        yield
    finally:
        _budget.reset(token)


def _body(client, method, url, limit, **kwargs):
    deadline = monotonic() + 12
    with client.stream(method, url, headers={'Accept-Encoding': 'identity', **kwargs.pop('headers', {})}, **kwargs) as response:
        response.raise_for_status()
        if response.headers.get('content-encoding', 'identity') != 'identity':
            raise ValueError('unexpected encoding')
        data = bytearray()
        for block in response.iter_bytes(chunk_size=65536):
            if monotonic() > deadline or len(data) + len(block) > limit:
                raise ValueError('response too large')
            data.extend(block)
        return bytes(data)


def search_evidence(parts: list[str], terms: str, *, transport=None) -> list[dict]:
    query = _query(parts, terms)
    words = sorted({t.lower() for t in TOKEN.findall(terms or '') if t.lower() in SAFE_TERMS}
                   - {'datasheet', 'official', 'circuit', 'diode', 'replacement'})
    if not enabled() or not query or not words:
        return []
    slot = _budget.get()
    if slot is not None and not slot.acquire(blocking=False):
        return []
    parts = list(dict.fromkeys(p for p in parts if isinstance(p, str) and PART.fullmatch(p)))[:8]
    tokens = {t.lower() for t in TOKEN.findall(terms or '')}
    makers = [host for host in PDF_PATHS if host.split('.')[-2] in tokens]
    filters = [host + PDF_PATHS[host] for host in makers or PDF_PATHS]
    docs, seen = [], set()
    with httpx.Client(transport=transport, timeout=10, trust_env=False, follow_redirects=False) as client:
        try:
            payload = json.loads(_body(client, 'POST', 'https://api.exa.ai/search', 256 * 1024,
                                       headers={'x-api-key': os.environ['EXA_API_KEY']},
                                       json={'query': query, 'numResults': MAX_RESULTS,
                                             'includeDomains': filters, 'type': 'auto'}))
        except (httpx.HTTPError, ValueError, TypeError, KeyError, RecursionError):
            return []
        results = payload.get('results') if isinstance(payload, dict) else None
        if not isinstance(results, list):
            return []
        for hit in results[:MAX_RESULTS]:
            url = official_pdf(hit.get('url')) if isinstance(hit, dict) else ''
            if not url or url in seen or (makers and urlsplit(url).hostname not in makers):
                continue
            seen.add(url)
            try:
                raw = _body(client, 'GET', url, MAX_BYTES)
                rows = verified_rows(raw, url, parts, words) if raw.startswith(b'%PDF-') else []
            except (ValueError, httpx.HTTPError):
                rows = []
            title = urlsplit(url).path.rsplit('/', 1)[-1]
            for row in rows[:MAX_RESULTS - len(docs)]:
                docs.append({**row, 'chunk_id': f'W{len(docs)+1}', 'file': title,
                             'title': title, 'source_type': 'external_web', 'source_url': url,
                             'retrieved_at': datetime.now(timezone.utc).isoformat()})
            if len(docs) == MAX_RESULTS or len(seen) >= MAX_DOWNLOADS:
                break
    return docs
