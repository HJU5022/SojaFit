import asyncio
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PATH = ROOT / 'evals/web-search-sample-30-v1.json'
OUT = ROOT / 'evals/results/web-search-filter-comparison-2026-11-03.json'


def normalized(url):
    try:
        parsed = urlsplit(url)
        return (parsed.hostname or '').lower().rstrip('.'), unquote(parsed.path).casefold().rstrip('/')
    except (ValueError, TypeError):
        return '', ''


def score(urls, expected):
    pairs = [normalized(url) for url in urls[:5]]
    official = [host == 'taiwansemi.com' or host.endswith('.taiwansemi.com') for host, _ in pairs]
    target = normalized(expected)
    return {'domain': any(official), 'exact': bool(target[0] and target in pairs),
            'returned': len(pairs), 'off_domain': sum(not value for value in official)}


def request_args(provider, query, filtered, key):
    if provider == 'Exa':
        body = {'query': query, 'type': 'auto', 'numResults': 5}
        if filtered:
            body['includeDomains'] = ['taiwansemi.com', '*.taiwansemi.com']
        return 'POST', 'https://api.exa.ai/search', {'headers': {'x-api-key': key}, 'json': body}
    if provider == 'Tavily':
        body = {'query': query, 'search_depth': 'basic', 'max_results': 5,
                'include_raw_content': False, 'include_answer': False, 'auto_parameters': False}
        if filtered:
            body['include_domains'] = ['taiwansemi.com']
            body['include_domains_mode'] = 'restrict'
        return 'POST', 'https://api.tavily.com/search', {'headers': {'Authorization': 'Bearer ' + key}, 'json': body}
    if provider == 'Brave':
        q = query + ' site:taiwansemi.com' if filtered else query
        return 'GET', 'https://api.search.brave.com/res/v1/web/search', {'headers': {'X-Subscription-Token': key}, 'params': {'q': q, 'count': 5}}
    raise ValueError('unknown provider')


def self_test():
    for provider in ('Exa', 'Tavily', 'Brave'):
        a = request_args(provider, 'public query', False, 'fake')
        b = request_args(provider, 'public query', True, 'fake')
        assert a[:2] == b[:2]
        assert ('site:taiwansemi.com' in b[2]['params']['q']) if provider == 'Brave' else ('includeDomains' in b[2]['json'] if provider == 'Exa' else b[2]['json']['include_domains_mode'] == 'restrict')
    assert score(['https://services.taiwansemi.com/a%20b.pdf'], 'https://services.taiwansemi.com/a b.pdf')['exact']
    assert not score(['https://taiwansemi.com.attacker.example/a'], 'https://services.taiwansemi.com/a')['domain']
    assert not score(['https://taiwansemi.com/other.pdf'], 'https://taiwansemi.com/right.pdf')['exact']
    print('offline request construction and URL scoring tests passed')


async def run():
    if OUT.exists():
        raise SystemExit('Results already exist. Refusing to overwrite or repeat searches.')
    sample_bytes = SAMPLE_PATH.read_bytes()
    sample = json.loads(sample_bytes.decode('utf8'))['questions']
    assert len(sample) == 30 and len({row['id'] for row in sample}) == 30
    keys = dotenv_values(ROOT / '.env')
    rows = []
    async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
        for provider, key_name in (('Exa', 'EXA_API_KEY'), ('Tavily', 'TAVILY_API_KEY'), ('Brave', 'BRAVE_API_KEY')):
            key = keys.get(key_name)
            if not key:
                print(json.dumps({'provider': provider, 'status': 'key_missing'}), flush=True)
                continue
            stopped = False
            for index, item in enumerate(sample):
                modes = (False, True) if index % 2 == 0 else (True, False)
                for filtered in modes:
                    method, url, kwargs = request_args(provider, item['query'], filtered, key)
                    start = time.perf_counter()
                    try:
                        response = await asyncio.wait_for(client.request(method, url, **kwargs), timeout=15)
                        ms = round((time.perf_counter() - start) * 1000, 2)
                        if response.status_code != 200:
                            result = {'status': 'HTTP_' + str(response.status_code), 'ms': ms}
                        else:
                            body = response.json()
                            results = body.get('web', {}).get('results') if provider == 'Brave' else body.get('results')
                            if not isinstance(results, list):
                                raise ValueError('invalid search response')
                            urls = [entry.get('url', '') for entry in results[:5] if isinstance(entry, dict)]
                            result = {'status': 'ok', 'ms': ms, **score(urls, item['expected_manifest_url'])}
                    except Exception as error:
                        result = {'status': type(error).__name__, 'ms': round((time.perf_counter() - start) * 1000, 2)}
                    entry = {'provider': provider, 'query_id': item['id'], 'filtered': filtered, **result}
                    rows.append(entry)
                    OUT.write_text(json.dumps({'sample_sha256': hashlib.sha256(sample_bytes).hexdigest(), 'rows': rows}, indent=2), encoding='utf8')
                    print(json.dumps(entry), flush=True)
                    if result['status'] in ('HTTP_401', 'HTTP_402', 'HTTP_403', 'HTTP_429', 'HTTP_432', 'HTTP_433'):
                        stopped = True
                        break
                if stopped:
                    break
            successes = [r for r in rows if r['provider'] == provider and r['status'] == 'ok']
            print(json.dumps({'provider': provider, 'complete_successes': len(successes), 'stopped': stopped}), flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        self_test()
    elif len(sys.argv) == 1:
        asyncio.run(run())
    else:
        raise SystemExit('Use no args to run the experiment or --self-test for offline checks.')
