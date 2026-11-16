"""d12 (2026-11-17): Langfuse 공개 API v3로 운영 프로젝트의 점수를 모두 읽는다(읽기 전용).
GET /api/public/v3/scores?fields=core,subject (cursor 페이지). 키는 환경변수 LANGFUSE_PUBLIC_KEY · LANGFUSE_SECRET_KEY · LANGFUSE_BASE_URL에서만 읽고 출력 · 파일에 남기지 않는다.
사용: python fetch_scores.py <out.json>"""
import base64, json, os, sys, time, urllib.parse, urllib.request
base = os.environ['LANGFUSE_BASE_URL'].rstrip('/')
auth = 'Basic ' + base64.b64encode(f"{os.environ['LANGFUSE_PUBLIC_KEY']}:{os.environ['LANGFUSE_SECRET_KEY']}".encode()).decode()
rows, cursor, pages = [], None, 0
while True:
    q = {'fields': 'core,subject', 'limit': os.environ.get('LF_LIMIT', '100')} | ({'cursor': cursor} if cursor else {})
    req = urllib.request.Request(f'{base}/api/public/v3/scores?{urllib.parse.urlencode(q)}', headers={'Authorization': auth})
    for attempt in range(5):
        try:
            d = json.load(urllib.request.urlopen(req, timeout=60)); break
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4: raise
            time.sleep(2 ** attempt)
    rows += d['data']; pages += 1
    cursor = d['meta'].get('cursor')
    if not cursor or not d['data']: break
json.dump({'endpoint': '/api/public/v3/scores?fields=core,subject', 'fetched_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'pages': pages, 'n': len(rows), 'data': rows}, open(sys.argv[1], 'w'), ensure_ascii=False)
print('pages', pages, 'scores', len(rows))
