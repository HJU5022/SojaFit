"""저장소에 검증한 공식 출처와 외형 페이지의 정확한 파일명 조회."""
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import TypedDict
from urllib.parse import unquote, urlsplit


class SourceMetadata(TypedDict):
    source_url: str
    outline_page: int


DATA = Path(__file__).resolve().parents[2] / 'data'


def official_basename(source_url: str) -> str:
    """manifest의 HTTPS PDF URL을 검사하고 URL-decode한 파일명을 돌려준다."""
    if not isinstance(source_url, str) or any(ord(char) < 32 for char in source_url):
        raise ValueError('invalid source URL')
    parsed = urlsplit(source_url)
    if (parsed.scheme != 'https' or not parsed.hostname or not re.fullmatch(r'[A-Za-z0-9.-]+', parsed.hostname)
            or parsed.username or parsed.password
            or parsed.query or parsed.fragment or '\\' in source_url):
        raise ValueError('invalid source URL')
    # port 속성도 읽어서 잘못된 포트 문법을 거부한다.
    parsed.port
    name = unquote(parsed.path.rsplit('/', 1)[-1])
    if (not name.casefold().endswith('.pdf') or '/' in name or '\\' in name
            or any(ord(char) < 32 for char in name)):
        raise ValueError('invalid source PDF basename')
    return name


@lru_cache(maxsize=1)
def _metadata_index() -> dict[str, SourceMetadata]:
    outlines = json.loads((DATA / 'package-outline-pages.json').read_text(encoding='utf-8'))
    result = {}
    for line in (DATA / 'manifest.jsonl').read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        url = json.loads(line)['source_url']
        name = official_basename(url).casefold()
        record = outlines.get(name)
        if record and record['source_url'] == url and type(record['outline_page']) is int and record['outline_page'] >= 1:
            result[name] = {'source_url': url, 'outline_page': record['outline_page']}
    return result


def source_metadata(document: str) -> SourceMetadata | None:
    """경로의 basename만 정확히 조회한다. 호출자가 준 URL은 출처로 받지 않는다."""
    if not isinstance(document, str) or any(ord(char) < 32 or ord(char) == 127 for char in document):
        return None
    # Windows drive 경로는 허용하지만 URL scheme과 protocol-relative URL은 거부한다.
    normalized = document.lstrip().replace('\\', '/')
    if '://' in normalized or normalized.startswith('//') or (re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', normalized)
            and not re.match(r'^[A-Za-z]:[\\/]', document)):
        return None
    name = unquote(document.replace('\\', '/').rsplit('/', 1)[-1]).casefold()
    metadata = _metadata_index().get(name)
    return dict(metadata) if metadata else None
