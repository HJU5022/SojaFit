import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PATH = ROOT / 'evals/web-search-sample-30-v1.json'
SAMPLE = json.loads(SAMPLE_PATH.read_text(encoding='utf8'))['questions']
OUT = ROOT / 'evals/results/tavily-authenticated-30-2026-11-03.json'

def normalized(url):
    try:
        p = urlsplit(url)
        return ((p.hostname or '').lower().rstrip('.'), unquote(p.path).casefold().rstrip('/'))
    except (ValueError, TypeError):
        return ('', '')

def scores(urls, expected):
    pairs = [normalized(url) for url in urls[:5]]
    target = normalized(expected)
    return (any(h == 'taiwansemi.com' or h.endswith('.taiwansemi.com') for h, _ in pairs),
            bool(target[0] and target in pairs))

if len(sys.argv) > 1:
    from dotenv import dotenv_values
    from tavily import TavilyClient
    key = dotenv_values(ROOT / '.env').get('TAVILY_API_KEY')
    if not key:
        print(json.dumps({'status':'key_missing','ms':0}))
        sys.exit(0)
    client = TavilyClient(api_key=key)
    client.session.trust_env = False
    row = SAMPLE[int(sys.argv[1])]
    start = time.perf_counter()
    try:
        body = client.search(row['query'], search_depth='basic', max_results=5,
                             include_raw_content=False, include_answer=False,
                             auto_parameters=False, timeout=14)
        results = body.get('results')
        if not isinstance(results, list):
            raise ValueError('invalid search response')
        domain, exact = scores([x.get('url','') for x in results[:5] if isinstance(x,dict)],row['expected_manifest_url'])
        result = {'status':'ok','ms':round((time.perf_counter()-start)*1000,2), 'domain':domain,'exact':exact}
    except Exception as exc:
        result = {'status':type(exc).__name__,'ms':round((time.perf_counter()-start)*1000,2)}
    print(json.dumps(result), flush=True)
    sys.exit(0)

if OUT.exists():
    raise SystemExit('Existing result file; refuse to overwrite.')
rows=[]
for i, row in enumerate(SAMPLE):
    start=time.perf_counter()
    try:
        proc=subprocess.run([sys.executable,__file__,str(i)],capture_output=True,text=True,timeout=15)
        result=json.loads(proc.stdout) if proc.returncode==0 else {'status':'process_error','ms':round((time.perf_counter()-start)*1000,2)}
    except subprocess.TimeoutExpired:
        result={'status':'timeout','ms':round((time.perf_counter()-start)*1000,2)}
    entry={'query_id':row['id'],**result}
    rows.append(entry)
    OUT.write_text(json.dumps({'sample_sha256':hashlib.sha256(SAMPLE_PATH.read_bytes()).hexdigest(),'rows':rows},indent=2),encoding='utf8')
    print(json.dumps(entry),flush=True)
    if result['status'] in ('key_missing','UsageLimitExceededError','ForbiddenError','InvalidAPIKeyError','TavilyKeylessLimitError'):
        break
