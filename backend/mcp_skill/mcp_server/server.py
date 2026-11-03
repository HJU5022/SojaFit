"""SojaFit 검색·문서·회로 기능 5종을 노출하는 stdio FastMCP 서버.

호출자는 MCP 클라이언트와 ``backend.graph.mcp_retriever``다. 코퍼스 검색은 기존
RAG를 재사용하고, 웹 검색은 명시적으로 활성화된 경우에만 제한된 TSC 문서 후보를
찾는다. 숫자·단위 판정은 하지 않는다. 계약과 실행 조건은
``backend/mcp_skill/MCP_SKILL.md``와 ``SPEC.md`` 8.7~8.8을 따른다.
"""
import json
import hashlib
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from mcp.server.fastmcp import FastMCP

from backend.graph.nodes import circuit_around
from backend.rag.retrieve import retrieve


mcp = FastMCP("sojafit-search")
MANIFEST_PATH = Path(__file__).resolve().parents[3] / "data" / "manifest.jsonl"
REPO = MANIFEST_PATH.parent.parent
CIRCUITS = {
    'breadboard_supply': 'data/circuits/collected/samples/breadboard_supply/converted/connections.json',
    'mosfet_driver': 'data/circuits/collected/samples/mosfet_driver/converted/connections.json',
    'attiny85_dev': 'data/circuits/collected/samples/attiny85_dev/converted/connections.json',
    'pro_micro': 'data/circuits/collected/samples/pro_micro/converted/connections.json',
    'franzininho_diy': 'data/circuits/collected/received-20261030/c09/connections.json',
}


def _validate_query(query: str) -> None:
    if not isinstance(query, str) or not query.strip() or len(query) > 500:
        raise ValueError("query must contain 1 to 500 characters")


@mcp.tool()
def search_corpus(query: str, k: int = 5, parts: list[str] | None = None) -> list[dict]:
    """프로젝트 코퍼스에서 질문과 품번에 맞는 데이터시트 카드를 찾습니다."""
    _validate_query(query)
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 10:
        raise ValueError("k must be between 1 and 10")
    return retrieve(query, k=k, parts=parts, method='hybrid')


@mcp.tool()
def verify_tsc_pdf(doc_id: str) -> dict:
    """로컬에 포함된 TSC 표본 PDF의 서명·크기·SHA-256을 manifest와 대조합니다."""
    if not isinstance(doc_id, str) or not doc_id.strip() or len(doc_id) > 200:
        raise ValueError("doc_id must contain 1 to 200 characters")
    record = get_corpus_document(doc_id)
    if record['status'] != 'found':
        return {'status': record['status'], 'integrity_verified': False, 'content_verified': False}
    document = record['document']
    sample_files = {
        'tsc-1n4148-series_k2301': '1N4148-SERIES_K2301.pdf',
        'tsc-1n5817-series_h2104': '1N5817-SERIES_H2104.pdf',
        'tsc-bzt52c2v4-series_g1804': 'BZT52C2V4-SERIES_G1804.pdf',
    }
    filename = sample_files.get(doc_id)
    if filename is None:
        return {'status': 'not_available_locally', 'integrity_verified': False, 'content_verified': False}
    path = REPO / 'data' / 'corpus' / 'tsc' / filename
    try:
        content = path.read_bytes()
    except OSError:
        return {'status': 'unavailable', 'integrity_verified': False, 'content_verified': False}
    valid = (content.startswith(b'%PDF-') and len(content) == document.get('bytes')
             and hashlib.sha256(content).hexdigest() == document.get('sha256'))
    return {'status': 'integrity_verified' if valid else 'integrity_mismatch',
            'integrity_verified': valid, 'content_verified': False}


@mcp.tool()
def get_circuit_info(circuit_id: str, target: str) -> dict:
    """공개 예제 회로 카탈로그에서 지정 부품과 주변 넷 정보를 읽습니다."""
    if not isinstance(circuit_id, str) or not re.fullmatch(r'[a-z0-9_]{1,50}', circuit_id):
        raise ValueError("invalid circuit_id")
    if not isinstance(target, str) or not re.fullmatch(r'[A-Za-z0-9_.+-]{1,100}', target):
        raise ValueError("invalid target")
    relative_path = CIRCUITS.get(circuit_id)
    if relative_path is None:
        return {'status': 'not_found', 'data': None}
    try:
        connections = json.loads((REPO / relative_path).read_text(encoding='utf-8'))
        data = circuit_around(connections, target)
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        return {'status': 'unavailable', 'data': None}
    return {'status': 'found' if data else 'not_found', 'data': data or None}



@mcp.tool()
def get_corpus_document(doc_id: str) -> dict:
    """기존 코퍼스 문서 ID로 manifest의 출처와 개정 정보를 조회합니다."""
    if not isinstance(doc_id, str) or not doc_id.strip() or len(doc_id) > 200:
        raise ValueError("doc_id must contain 1 to 200 characters")
    result = {'status': 'not_found', 'document': None, 'pdf_verified': False}
    fields = ('doc_id', 'title', 'revision', 'source_url', 'sha256', 'bytes', 'pages')
    try:
        with MANIFEST_PATH.open(encoding='utf-8') as manifest:
            for line in manifest:
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict) or not isinstance(row.get('doc_id'), str):
                    raise ValueError("invalid manifest record")
                if row['doc_id'] == doc_id:
                    result['document'] = {name: row[name] for name in fields}
                    result['status'] = 'found'
                    break
    except (OSError, UnicodeError, ValueError, KeyError):
        return {'status': 'unavailable', 'document': None, 'pdf_verified': False}
    return result


def _is_tsc_url(url: object) -> bool:
    if not isinstance(url, str) or any(c.isspace() for c in url):
        return False
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower()
        return (
            parsed.scheme == 'https'
            and parsed.username is None
            and parsed.password is None
            and parsed.port in (None, 443)
            and (host == 'taiwansemi.com' or host.endswith('.taiwansemi.com'))
        )
    except ValueError:
        return False


@mcp.tool()
def search_tsc_web(doc_id: str) -> dict:
    """공개 TSC 목록에 있는 문서의 미검증 웹 후보를 찾습니다."""
    _validate_query(doc_id)
    empty = {'status': 'disabled', 'candidates': []}
    if os.getenv('DEMO_MODE', '1') != '0' or os.getenv('EXA_WEB_SEARCH_ENABLED') != '1':
        return empty
    key = os.getenv('EXA_API_KEY', '').strip()
    if not key:
        return {'status': 'missing_key', 'candidates': []}

    record = get_corpus_document(doc_id)
    if record['status'] == 'unavailable':
        return {'status': 'unavailable', 'candidates': []}
    if record['status'] != 'found':
        return {'status': 'unverified', 'candidates': []}
    document = record['document']
    title, revision, source = (document.get(field) for field in ('title', 'revision', 'source_url'))
    # shortcut: only the corpus's known TSC filename format; extend after public provenance is verified.
    if (not isinstance(title, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*(?: SERIES)?', title)
            or not isinstance(revision, str) or not re.fullmatch(r'[A-Z][0-9]{4}', revision)
            or source != f'https://services.taiwansemi.com/storage/resources/datasheet/{title}_{revision}.pdf'):
        return {'status': 'unverified', 'candidates': []}
    query = f'Taiwan Semiconductor {title} {revision} datasheet'

    try:
        response = httpx.post(
            'https://api.exa.ai/search',
            headers={'x-api-key': key},
            json={'query': query, 'type': 'auto', 'numResults': 5,
                  'includeDomains': ['taiwansemi.com', '*.taiwansemi.com']},
            timeout=15,
            follow_redirects=False,
            trust_env=False,
        )
        response.raise_for_status()
        results = response.json()['results']
        if not isinstance(results, list):
            raise ValueError('invalid results')
        candidates = [
            {'url': item['url'], 'verified': False}
            for item in results[:5]
            if isinstance(item, dict) and _is_tsc_url(item.get('url'))
        ]
        return {'status': 'ok', 'candidates': candidates}
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        return {'status': 'unavailable', 'candidates': []}


if __name__ == '__main__':
    mcp.run()
