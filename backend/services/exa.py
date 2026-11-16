"""내부 문서가 부족할 때만 쓰는 Exa 외부 근거 검색 서비스."""
import json
import logging
import os
import re
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
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


def _failure(stage: str, error: BaseException) -> None:
    """외부 호출 실패를 운영 로그(WARNING)에 남긴다. 단계 · 예외 종류 · 상태 코드만 적는다(키 · 질의 · 주소 · 예외 글은 적지 않는다)."""
    status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
    LOGGER.warning('exa_failure stage=%s error=%s status=%s', stage, type(error).__name__, status)
    # [왜] Exa 검색 호출 실패(402 · 429 · 시간 초과 등)도 []라 화면에서 '못 찾음'과 같았다(#28). 이 요청에 표시만 남긴다.
    #      PDF 받기 · 미리 받기 실패는 웹 검색을 못 쓴 것이 아니라 넣지 않는다
    if stage.startswith('search') and (seen := _unavailable.get()) is not None:
        seen['web_search_unavailable'] = True


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
_unavailable = ContextVar('web_search_unavailable', default=None)  # 요청마다 하나의 dict를 하위 스레드가 같이 고친다(_budget과 같은 방식)


class SearchBudgetExhausted(RuntimeError):
    """The request's single slot for an external search is already in use."""

    def __init__(self, grade: int):
        self.grade = grade
        super().__init__(f'grade {grade} external search budget is already in use')


@contextmanager
def _claim_slot(grade):
    slots = _budget.get()
    slot = slots.get('grade2' if grade == 2 else 'grade3') if isinstance(slots, dict) else slots
    if slot is not None:
        if not slot.acquire(blocking=False):
            raise SearchBudgetExhausted(grade)
    # Deliberately keep the lock until request_scope() resets the ContextVar.
    # This is a per-request one-call budget, not merely a concurrent-call guard;
    # releasing here would allow a second sequential provider call.
    yield


def slot_in_use(grade: int) -> bool:
    """이 요청에서 그 등급의 외부 검색 1번 예산을 이미 누가 쓰고 있는지(요청 밖이면 False)."""
    slots = _budget.get()
    slot = slots.get('grade2' if grade == 2 else 'grade3') if isinstance(slots, dict) else slots
    return slot is not None and slot.locked()


@contextmanager
def request_scope():
    # Permit one official lookup and one grade-3 fallback in the same request,
    # while retaining the per-grade single-call guard for concurrent retries.
    token = _budget.set({'grade2': Lock(), 'grade3': Lock()})
    prefetch_token = _prefetched.set({})  # [왜] 미리 받은 PDF는 이 요청 안에서만 쓰고 끝나면 버린다(저장하지 않음)
    seen = {'web_search_unavailable': False}
    unavailable_token = _unavailable.set(seen)
    try:
        yield seen  # 끝난 뒤 web_search_unavailable: 이 요청에서 Exa 검색 호출이 한 번이라도 실패했는지(#28)
    finally:
        _unavailable.reset(unavailable_token)
        _prefetched.reset(prefetch_token)
        _budget.reset(token)


# 미리 출발(사전 등록 2026-11-14): 품번이 확인되면 공식 PDF 검색 · 내려받기를 옆 스레드에서 먼저 시작한다.
# 웹 근거가 필요해진 시점에 같은 URL이 이미 받아져 있으면 다시 받지 않는다. 근거 검증(verified_rows) · 요청당 1번 제한은 그대로다.
_prefetched = ContextVar('datasheet_prefetch', default=None)
_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix='exa-prefetch')
PREFETCH_WAIT_SECONDS = 12  # 받는 중인 PDF를 기다리는 상한. 기존 내려받기 상한(_body 12초)과 같다


def prefetch_enabled() -> bool:
    return os.getenv('WEB_PREFETCH') == '1' and enabled()


def prefetch(parts: list[str]) -> None:
    """질문 속 품번의 공식 PDF를 미리 찾고 내려받기 시작한다. 결과는 기다리지 않는다(실패해도 본 경로는 원래대로 받는다)."""
    store = _prefetched.get()
    clean = list(dict.fromkeys(p for p in parts if isinstance(p, str) and PART.fullmatch(p)))[:2]
    if store is None or not clean or not prefetch_enabled() or 'job' in store:
        return
    # [주의] 요청 범위 칸(store)은 dict라 다른 스레드에서 같은 객체를 채운다. 예산 슬롯은 쓰지 않는다(근거 호출이 아니라 받기만 함)
    store['job'] = _POOL.submit(_prefetch_pdfs, clean)


def _prefetch_pdfs(parts: list[str]) -> dict:
    """공식 PDF 후보를 Exa로 찾아 최대 MAX_DOWNLOADS개를 받는다. {요청 URL: (바이트, 최종 URL)}."""
    query = _query(parts, 'datasheet')
    filters = [host + GRADE2_PDF_PATHS[host] for host in GRADE2_PDF_PATHS]
    found = {}
    try:
        with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
            body, _ = _body(client, 'POST', 'https://api.exa.ai/search', 256 * 1024,
                            headers={'x-api-key': os.environ['EXA_API_KEY']},
                            json={'query': query, 'numResults': MAX_RESULTS, 'includeDomains': filters, 'type': 'auto'})
            results = json.loads(body).get('results') or []
            hits = sorted((h for h in results[:MAX_RESULTS] if isinstance(h, dict)),
                          key=lambda h: _candidate_score(h, parts), reverse=True)
            urls = list(dict.fromkeys(u for u in (official_pdf(h.get('url') or '', grade=2) for h in hits) if u))
            for url in urls[:MAX_DOWNLOADS]:
                try:
                    found[url] = _body(client, 'GET', url, MAX_BYTES, redirect_validator=grade2_pdf)
                except (ValueError, httpx.HTTPError):
                    continue
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as error:
        _failure('prefetch', error)
    return found


def _from_prefetch(url: str):
    """미리 받은 같은 URL의 (바이트, 최종 URL). 없거나 아직 못 받았으면 None(원래대로 받는다)."""
    store = _prefetched.get()
    job = store.get('job') if isinstance(store, dict) else None
    if job is None:
        return None
    try:
        return job.result(timeout=PREFETCH_WAIT_SECONDS).get(url)
    except Exception:  # [왜] 미리 받기 실패 · 시간 초과는 본 경로를 막지 않는다
        return None


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


def _search_evidence(parts: list[str], terms: str, *, grade=None, transport=None) -> list[dict]:
    query = _query(parts, terms)
    words = sorted({t.lower() for t in TOKEN.findall(terms or '') if t.lower() in SAFE_TERMS}
                   - {'datasheet', 'official', 'circuit', 'diode', 'replacement'})
    if not enabled() or not query or not words:
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
        except (httpx.HTTPError, ValueError, TypeError, KeyError, RecursionError) as error:
            _failure('search_grade2' if grade == 2 else 'search', error)
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
                cached = _from_prefetch(url) if grade == 2 else None
                raw, url = cached or _body(client, 'GET', url, MAX_BYTES,
                                           redirect_validator=(grade2_pdf if grade == 2 else None))
                rows = verified_rows(raw, url, parts, words, grade=grade) if raw.startswith(b'%PDF-') else []
            except (ValueError, httpx.HTTPError) as error:
                _failure('pdf_fetch', error)
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


def search_evidence(parts: list[str], terms: str, *, grade=None, transport=None) -> list[dict]:
    query = _query(parts, terms)
    words = sorted({t.lower() for t in TOKEN.findall(terms or '') if t.lower() in SAFE_TERMS}
                   - {'datasheet', 'official', 'circuit', 'diode', 'replacement'})
    if not enabled() or not query or not words:
        return []
    with _claim_slot(2 if grade == 2 else 3):
        return _search_evidence(parts, terms, grade=grade, transport=transport)


def search_grade2_evidence(parts: list[str], terms: str, *, transport=None) -> list[dict]:
    """Search only validated manufacturer PDFs for evidence grade 2."""
    if OTHER_MANUFACTURER.search(terms or ''):
        return []
    return search_evidence(parts, terms, grade=2, transport=transport)


def _search_grade3_reference(parts: list[str], terms: str, *, transport=None) -> list[dict]:
    """Search public web references without downloading or injecting page text."""
    if not enabled():
        return []
    wanted = list(dict.fromkeys(p.upper() for p in parts if isinstance(p, str) and PART.fullmatch(p)))[:8]
    query = _query(parts, terms)
    if not wanted or not query:
        return []
    try:
        with httpx.Client(transport=transport, timeout=10, trust_env=False, follow_redirects=False) as client:
            body, _ = _body(client, 'POST', 'https://api.exa.ai/search', 256 * 1024,
                            headers={'x-api-key': os.environ['EXA_API_KEY']},
                            json={'query': query, 'numResults': MAX_RESULTS, 'type': 'auto'})
        payload = json.loads(body)
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as error:
        _failure('search_grade3', error)
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


def search_grade3_reference(parts: list[str], terms: str, *, transport=None) -> list[dict]:
    if not enabled() or not _query(parts, terms):
        return []
    wanted = [p for p in parts if isinstance(p, str) and PART.fullmatch(p)]
    if not wanted:
        return []
    with _claim_slot(3):
        return _search_grade3_reference(parts, terms, transport=transport)
