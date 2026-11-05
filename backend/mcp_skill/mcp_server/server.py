"""SojaFit의 코퍼스 검색과 미검증 TSC 문서 후보를 노출하는 stdio MCP 서버."""
import json
import hashlib
import math
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from mcp.server.fastmcp import FastMCP

from backend.graph.nodes import circuit_around
from backend.rag.retrieve import _connect, corpus_known, retrieve
from backend.rag.spec_lookup import CODES, SLOTS, find_candidates, part_specs


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


def _validate_names(name: str, values: object) -> None:
    if (not isinstance(values, list) or len(values) > 20
            or not all(isinstance(v, str) and 1 <= len(v) <= 100 for v in values)):
        raise ValueError(f"{name} must be a list of up to 20 strings of 1 to 100 characters")


@mcp.tool()
def check_corpus(parts: list[str], revisions: list[str]) -> dict:
    """품번과 데이터시트 개정 코드가 코퍼스에 있는지 확인합니다(있음/없음만 돌려주고 판단하지 않습니다)."""
    _validate_names("parts", parts)
    _validate_names("revisions", revisions)
    known_parts, known_revisions = corpus_known()
    return {"parts": {p: p.strip().lower() in known_parts for p in parts},
            "revisions": {r: r.strip().upper() in known_revisions for r in revisions}}


def _validate_codes(codes: object) -> None:
    if codes is not None and (not isinstance(codes, list) or len(codes) > len(CODES)
                              or not all(isinstance(c, str) and c in CODES for c in codes)):
        raise ValueError(f"codes must be a list of up to {len(CODES)} codes from {', '.join(CODES)}")


@mcp.tool()
def get_part_specs(part: str, codes: list[str] | None = None) -> list[dict]:
    """품번 하나의 데이터시트 사양 표 행을 돌려줍니다(값을 비교하거나 판정하지 않습니다).

    값은 SI 단위(V, A, W, s, F, degC)이고, 행마다 분류(category), 시험 조건과 인용(문서 파일 이름·쪽·표·행·청크 순번)이 있습니다.
    codes로 코드를 고를 수 있습니다(VRRM, IF_AV, IFSM, VF, IR, TRR, VZ, PD, CJ, TJ_MAX, VR, VRWM, VBR, VC, IPP, PPPM, VESD,
    PACKAGE=패키지 이름). 빈 목록이면 표에 그 품번이 없거나 값을 뺀 것이라 "문서로 확인 안 됨"으로 다룹니다.
    """
    if not isinstance(part, str) or not part.strip() or len(part) > 100:
        raise ValueError("part must contain 1 to 100 characters")
    _validate_codes(codes)
    with _connect() as conn:
        return part_specs(conn, part.strip(), codes)


def _validate_conditions(conditions: object) -> None:
    if not isinstance(conditions, list) or not 1 <= len(conditions) <= 10:
        raise ValueError("conditions must be a list of 1 to 10 conditions")
    for c in conditions:
        # [왜] 숫자는 SQL 인자로만 넘기지만 NaN·무한·True(=1)는 조건 뜻이 없어 막는다
        if (not isinstance(c, dict) or not set(c) <= {'code', 'slot', 'gte', 'lte'}
                or c.get('code') not in CODES or c['code'] == 'PACKAGE'  # 패키지는 숫자가 아니라 package 인자로 거른다
                or c.get('slot') not in (None, *SLOTS) or not ({'gte', 'lte'} & set(c))
                or not all(isinstance(c[k], (int, float)) and not isinstance(c[k], bool) and math.isfinite(c[k])
                           for k in ('gte', 'lte') if k in c)):
            raise ValueError("each condition needs a numeric code, optional slot min|typ|max, and finite gte and/or lte")


@mcp.tool()
def find_parts_by_specs(conditions: list[dict], category: str | None = None, package: str | None = None,
                        limit: int = 20) -> list[dict]:
    """숫자 사양 조건을 모두 채운 품번을 사양 표에서 찾습니다(행을 거를 뿐 대체 가능 판정은 하지 않습니다).

    conditions 예: [{"code": "VRRM", "gte": 40}, {"code": "IF_AV", "gte": 1}] 또는 제너 창
    [{"code": "VZ", "slot": "min", "gte": 3.42}, {"code": "VZ", "slot": "max", "lte": 3.78}]. 값은 SI 단위(V, A, W, s, F, degC),
    gte=이상·lte=이하(경계 포함), slot은 min|typ|max(기본 max, CJ는 typ). 조건마다 그 품번의 행 하나 이상이 채우면 됩니다.
    category는 분류 이름과 같아야 합니다: standard-rectifier, schottky-rectifier, schottky-diode, sic-schottky-diode,
    fast-recovery-trr-100-500ns, high-efficiency-trr-50-99ns, super-fast-recovery, ultra-fast-recovery, switching-diode,
    zener-diode, tvs, esd-protection, bridge. package는 패키지 이름과 같아야 합니다(대소문자·하이픈·공백 무시, 예: SMA, SOD-123. SMA는 SMAF를 잡지 않음).
    결과는 품번 순으로 limit개(1~50)까지이고, 각 품번에 조건을 채운 행과 인용, 분류, 패키지가 붙습니다.
    표에 값이 없는 품번은 결과에서 빠지며, 이는 불충족이 아니라 "문서로 확인 안 됨"입니다.
    """
    _validate_conditions(conditions)
    if category is not None and (not isinstance(category, str) or not 1 <= len(category) <= 100):
        raise ValueError("category must contain 1 to 100 characters")
    if package is not None and (not isinstance(package, str) or not re.fullmatch(r'[A-Za-z0-9.\-]{1,30}', package)):
        raise ValueError("package must be 1 to 30 letters, digits, dots or hyphens")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    with _connect() as conn:
        return find_candidates(conn, conditions, category, package, limit)


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
    if not isinstance(doc_id, str) or not doc_id.strip() or len(doc_id) > 200:
        raise ValueError("doc_id must contain 1 to 200 characters")
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
