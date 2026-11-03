import asyncio
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = json.loads((ROOT / 'evals/web-search-sample-30-v1.json').read_text(encoding='utf8'))['questions']
OUT = ROOT / 'evals/results/web-search-pdf-smoke-2026-11-03.json'


def compact(value):
    return ''.join(ch for ch in value.casefold() if ch.isalnum())


async def main():
    if OUT.exists():
        raise SystemExit('Existing results: refuse to repeat or overwrite.')
    docs = {d['doc_id']: d for d in (json.loads(line) for line in (ROOT / 'data/manifest.jsonl').read_text(encoding='utf8').splitlines() if line)}
    rows = []
    async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
        for qid in ('S23', 'S13', 'S29'):
            question = next(x for x in SAMPLE if x['id'] == qid)
            doc = docs[question['doc_id']]
            parsed = urlsplit(doc['source_url'])
            result = {'query_id': qid, 'doc_id': doc['doc_id']}
            try:
                if parsed.scheme != 'https' or parsed.hostname != 'services.taiwansemi.com':
                    raise ValueError('nonallowed URL')
                async with asyncio.timeout(15):
                    async with client.stream('GET', doc['source_url']) as response:
                        result['http_status'] = response.status_code
                        response.raise_for_status()
                        chunks = bytearray()
                        async for chunk in response.aiter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > 8 * 1024 * 1024:
                                raise ValueError('PDF exceeds 8 MiB')
                result['pdf_signature'] = chunks.startswith(b'%PDF-')
                if not result['pdf_signature']:
                    raise ValueError('not PDF')
                result['sha256_matches_manifest'] = hashlib.sha256(chunks).hexdigest() == doc['sha256']
                pdf = PdfReader(io.BytesIO(chunks))
                text = ' '.join(page.extract_text() or '' for page in pdf.pages)
                result.update({'status': 'ok', 'pages': len(pdf.pages),
                               'title_text_seen': compact(doc['title']) in compact(text),
                               'revision_text_seen': compact(doc['revision']) in compact(text)})
            except Exception as error:
                result['status'] = type(error).__name__
            rows.append(result)
            OUT.write_text(json.dumps({'rows': rows}, indent=2), encoding='utf8')
            print(json.dumps(result), flush=True)


asyncio.run(main())
