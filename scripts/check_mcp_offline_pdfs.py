"""DB·네트워크 없이 저장소의 TSC PDF 표본과 manifest를 대조한다.

실행: uv run --no-project --offline --with pypdf==6.21.4 python scripts/check_mcp_offline_pdfs.py
"""
import hashlib
import json
import time
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
CASES = [
    ('1N4148-SERIES_K2301.pdf', 'tsc-1n4148-series_k2301'),
    ('1N5817-SERIES_H2104.pdf', 'tsc-1n5817-series_h2104'),
    ('BZT52C2V4-SERIES_G1804.pdf', 'tsc-bzt52c2v4-series_g1804'),
]


def compact(value):
    return ''.join(c for c in value.casefold() if c.isalnum())


def main():
    manifest = ROOT / 'data/manifest.jsonl'
    docs = {x['doc_id']: x for x in (json.loads(line) for line in manifest.read_text(encoding='utf8').splitlines() if line)}
    for filename, doc_id in CASES:
        path = ROOT / 'data/corpus/tsc' / filename
        meta = docs[doc_id]
        started = time.perf_counter()
        raw = path.read_bytes()
        pdf = PdfReader(str(path))
        content = ' '.join(page.extract_text() or '' for page in pdf.pages)
        title_token = meta['title'].split()[0]
        row = {
            'doc_id': doc_id,
            'file': filename,
            'signature_ok': raw.startswith(b'%PDF-'),
            'sha256_match': hashlib.sha256(raw).hexdigest() == meta['sha256'],
            'pages': len(pdf.pages),
            'manifest_pages': meta['pages'],
            'title_text_seen': compact(meta['title']) in compact(content),
            'part_token_seen': compact(title_token) in compact(content),
            'series_word_seen': compact('SERIES') in compact(content),
            'revision_text_seen': compact(meta['revision']) in compact(content),
            'extract_ms': round((time.perf_counter() - started) * 1000, 2),
        }
        print(json.dumps(row))
        if not row['signature_ok'] or not row['sha256_match'] or row['pages'] != row['manifest_pages']:
            raise SystemExit('PDF signature, manifest hash or page count mismatch')


if __name__ == '__main__':
    main()
