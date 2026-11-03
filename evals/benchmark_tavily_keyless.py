import json
import os
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).parent
QUERIES = [
    ('W02', 'Taiwan Semiconductor 1N4148W SERIES K1804 datasheet'),
    ('W03', 'Taiwan Semiconductor 1N4148W-G D1601 datasheet'),
    ('W04', 'Taiwan Semiconductor 1N4148WH A2501 datasheet'),
    ('W05', 'Taiwan Semiconductor 1N5817 SERIES H2104 datasheet'),
    ('W06', 'Taiwan Semiconductor BZT52B2V4-G SERIES H2002 datasheet'),
    ('W07', 'Taiwan Semiconductor SS34L SERIES C2103 datasheet'),
    ('W08', 'Taiwan Semiconductor SS34ALH SERIES B2103 datasheet'),
]

if len(sys.argv) > 1:
    from tavily import TavilyClient
    for name in list(os.environ):
        if name.startswith('TAVILY_'):
            del os.environ[name]
    client = TavilyClient()
    client.session.trust_env = False
    assert client._keyless
    start = time.perf_counter()
    try:
        result = client.search(sys.argv[1], search_depth='basic', max_results=5,
                               include_raw_content=False, include_answer=False,
                               auto_parameters=False, timeout=14)
        data = {'elapsed_ms': round((time.perf_counter()-start)*1000, 2),
                'results': [{'title': r.get('title'), 'url': r.get('url')} for r in result.get('results', [])]}
    except Exception as exc:
        data = {'elapsed_ms': round((time.perf_counter()-start)*1000, 2), 'error': type(exc).__name__}
    print(json.dumps(data, ensure_ascii=True))
else:
    if any((ROOT / 'results' / ('tavily-' + qid.lower() + '-raw.json')).exists() for qid, _ in QUERIES):
        raise SystemExit('Existing results found; archive them and preregister before a new run.')
    for qid, query in QUERIES:
        start = time.perf_counter()
        try:
            child = subprocess.run([sys.executable, __file__, query], text=True, capture_output=True, timeout=15)
            data = json.loads(child.stdout) if child.returncode == 0 else {'error': 'ProcessError'}
        except subprocess.TimeoutExpired:
            data = {'error': 'TimeoutExpired', 'elapsed_ms': round((time.perf_counter()-start)*1000, 2)}
        data['query_id'] = qid
        (ROOT / 'results' / ('tavily-' + qid.lower() + '-raw.json')).write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding='utf-8')
        print(qid, data.get('error', 'success'), data.get('elapsed_ms'), flush=True)
