import asyncio, json, os, re, statistics, subprocess, sys, time
from pathlib import Path
from urllib.parse import unquote, urlsplit
import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = json.loads((ROOT / 'evals/web-search-sample-30-v1.json').read_text(encoding='utf8'))['questions']
OUT = ROOT / 'evals/results/web-search-30-2026-11-03.json'

def normalized(url):
    try:
        p=urlsplit(url)
        return ((p.hostname or '').lower().rstrip('.'), unquote(p.path).casefold().rstrip('/'))
    except (ValueError, TypeError):
        return ('','')

def scores(urls, expected):
    pairs=[normalized(u) for u in urls[:5]]
    target=normalized(expected)
    domain=any(host=='taiwansemi.com' or host.endswith('.taiwansemi.com') for host,_ in pairs)
    exact=bool(target[0] and target in pairs)
    return domain,exact

if len(sys.argv)>1:
    from tavily import TavilyClient
    row=SAMPLE[int(sys.argv[1])]
    for name in list(os.environ):
        if name.startswith('TAVILY_'):
            del os.environ[name]
    c=TavilyClient()
    c.session.trust_env=False
    assert c._keyless
    t=time.perf_counter()
    try:
        body=c.search(row['query'],search_depth='basic',max_results=5,include_raw_content=False,include_answer=False,auto_parameters=False,timeout=14)
        urls=[item.get('url','') for item in body.get('results',[])[:5]]
        domain,exact=scores(urls,row['expected_manifest_url'])
        result={'status':'ok','ms':round((time.perf_counter()-t)*1000,2),'domain':domain,'exact':exact}
    except Exception as exc:
        result={'status':type(exc).__name__,'ms':round((time.perf_counter()-t)*1000,2)}
    print(json.dumps(result),flush=True)
    sys.exit(0)

def save(rows):
    OUT.write_text(json.dumps({'questions_sha256':SAMPLE_SHA,'rows':rows},indent=2),encoding='utf8')

import hashlib
SAMPLE_SHA=hashlib.sha256((ROOT/'evals/web-search-sample-30-v1.json').read_bytes()).hexdigest()

def record(rows, provider, qid, result):
    row={'provider':provider,'query_id':qid,**result}
    rows.append(row)
    save(rows)
    print(json.dumps(row),flush=True)

async def main():
    rows=[]
    for i,row in enumerate(SAMPLE):
        t=time.perf_counter()
        try:
            child=subprocess.run([sys.executable,__file__,str(i)],capture_output=True,text=True,timeout=15)
            result=json.loads(child.stdout) if child.returncode==0 else {'status':'process_error','ms':round((time.perf_counter()-t)*1000,2)}
        except subprocess.TimeoutExpired:
            result={'status':'timeout','ms':round((time.perf_counter()-t)*1000,2)}
        record(rows,'Tavily',row['id'],result)
        if result['status'] in ('TavilyKeylessLimitError','UsageLimitExceededError','ForbiddenError','InvalidAPIKeyError'):
            break
    headers={'Accept':'application/json, text/event-stream','Content-Type':'application/json'}
    async with httpx.AsyncClient(timeout=15,trust_env=False,follow_redirects=False) as client:
        init={'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'sojafit-eval','version':'0.1'}}}
        try:
            resp=await asyncio.wait_for(client.post('https://mcp.exa.ai/mcp',headers=headers,json=init),15)
            if resp.status_code!=200: raise RuntimeError('init_http_error')
            if resp.headers.get('mcp-session-id'): headers['Mcp-Session-Id']=resp.headers['mcp-session-id']
        except Exception as exc:
            record(rows,'Exa','init',{'status':type(exc).__name__,'ms':0})
        else:
            for i,row in enumerate(SAMPLE):
                payload={'jsonrpc':'2.0','id':i+2,'method':'tools/call','params':{'name':'web_search_exa','arguments':{'query':row['query'],'objective':'Find the official manufacturer datasheet matching the exact part and revision and provide source URLs.','numResults':5}}}
                t=time.perf_counter()
                try:
                    resp=await asyncio.wait_for(client.post('https://mcp.exa.ai/mcp',headers=headers,json=payload),15)
                    ms=round((time.perf_counter()-t)*1000,2)
                    if resp.status_code!=200:
                        result={'status':'HTTP_'+str(resp.status_code),'ms':ms}
                    else:
                        obj=json.loads(next(x[6:] for x in resp.text.splitlines() if x.startswith('data: ')))
                        body=obj.get('result',{})
                        if body.get('isError') or 'error' in obj:
                            limited=body.get('_meta',{}).get('ai.exa/rateLimited',False)
                            result={'status':'rate_limited' if limited else 'tool_error','ms':ms}
                        else:
                            content='\n'.join(x.get('text','') for x in body.get('content',[]))
                            urls=re.findall(r'(?m)^URL:\s*(\S+)',content)[:5]
                            domain,exact=scores(urls,row['expected_manifest_url'])
                            result={'status':'ok','ms':ms,'domain':domain,'exact':exact}
                except Exception as exc:
                    result={'status':type(exc).__name__,'ms':round((time.perf_counter()-t)*1000,2)}
                record(rows,'Exa',row['id'],result)
                if result['status'] in ('rate_limited','HTTP_429','HTTP_401','HTTP_403'): break
        key=dotenv_values(ROOT/'.env').get('BRAVE_API_KEY')
        if not key:
            record(rows,'Brave','init',{'status':'key_missing','ms':0})
            return
        for row in SAMPLE:
            t=time.perf_counter()
            try:
                resp=await asyncio.wait_for(client.get('https://api.search.brave.com/res/v1/web/search',params={'q':row['query'],'count':5},headers={'Accept':'application/json','X-Subscription-Token':key}),15)
                ms=round((time.perf_counter()-t)*1000,2)
                if resp.status_code!=200:
                    result={'status':'HTTP_'+str(resp.status_code),'ms':ms}
                else:
                    items=resp.json().get('web',{}).get('results',[])
                    if not isinstance(items,list): raise ValueError('invalid')
                    urls=[x.get('url','') for x in items[:5] if isinstance(x,dict)]
                    domain,exact=scores(urls,row['expected_manifest_url'])
                    result={'status':'ok','ms':ms,'domain':domain,'exact':exact}
            except Exception as exc:
                result={'status':type(exc).__name__,'ms':round((time.perf_counter()-t)*1000,2)}
            record(rows,'Brave',row['id'],result)
            if result['status'].startswith('HTTP_'): break

if OUT.exists():
    raise SystemExit('Existing results found; preregister and choose a new output before running again.')
asyncio.run(main())
