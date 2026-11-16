"""d12 (2026-11-17): 운영 Langfuse 프로젝트의 점수가 트레이스에 붙어 있는지 공개 API로 읽는다(읽기 전용).
- GET /api/public/v2/metrics: 점수 이름별 개수 · 날짜별 개수 · 점수가 붙은 트레이스 수(scores-numeric, scores-categorical)
- GET /api/public/v3/scores?fields=core,subject&traceId=: 화면 확인용 트레이스 하나의 점수 전부
- GET /api/public/v3/scores?fields=core,subject&fromTimestamp=: 11-17 게이트 세트의 점수(cursor 페이지)
키는 환경변수 LANGFUSE_PUBLIC_KEY · LANGFUSE_SECRET_KEY · LANGFUSE_BASE_URL에서만 읽고 출력 · 파일에 남기지 않는다.
옛 /api/public/scores · /api/public/metrics(v1)는 2026-11-16 제거(응답의 _deprecation 문구).
사용: python query_scores.py <out_dir> <trace_id> <from_iso>"""
import base64, json, os, sys, time, urllib.error, urllib.parse, urllib.request
base = os.environ['LANGFUSE_BASE_URL'].rstrip('/')
auth = 'Basic ' + base64.b64encode(f"{os.environ['LANGFUSE_PUBLIC_KEY']}:{os.environ['LANGFUSE_SECRET_KEY']}".encode()).decode()
out, trace_id, since = sys.argv[1], sys.argv[2], sys.argv[3]
FROM, TO = '2026-10-01T00:00:00Z', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def get(path, params):
    req = urllib.request.Request(f'{base}{path}?{urllib.parse.urlencode(params)}', headers={'Authorization': auth})
    for attempt in range(30):
        try:
            return json.load(urllib.request.urlopen(req, timeout=60))
        except urllib.error.HTTPError as e:  # 429: 공개 API 한도. 응답의 retryAfterSeconds만큼 기다린다
            if e.code != 429 or attempt == 29:
                raise
            time.sleep(json.loads(e.read() or b'{}').get('details', {}).get('retryAfterSeconds', 5) + 1)


def metrics(view, dims, time_dim=None, frm=FROM, to=TO):
    q = {'view': view, 'metrics': [{'measure': 'count', 'aggregation': 'count'}], 'dimensions': [{'field': d} for d in dims],
         'filters': [], 'fromTimestamp': frm, 'toTimestamp': to} | ({'timeDimension': {'granularity': time_dim}} if time_dim else {})
    if 'traceId' in dims:  # [왜] 트레이스 id 차원은 row_limit(최대 1000)과 내림차순 정렬이 있어야 받는다. 그래서 하루씩 묻는다
        q |= {'orderBy': [{'field': 'count_count', 'direction': 'desc'}], 'config': {'row_limit': 1000}}
    return {'query': q, 'response': get('/api/public/v2/metrics', {'query': json.dumps(q)})}


res = {'fetched_at_utc': TO, 'window': [FROM, TO]}
for view in ('scores-numeric', 'scores-categorical'):
    res[view] = {'by_name': metrics(view, ['name']), 'by_day': metrics(view, [], 'day')}
days = sorted({x['time_dimension'] for v in ('scores-numeric', 'scores-categorical') for x in res[v]['by_day']['response']['data'] if x['count_count']})
res['traces_by_day'] = {d: metrics('scores-numeric', ['traceId'], frm=f'{d}T00:00:00Z', to=f'{d}T23:59:59.999Z') for d in days}
for d in [d for d, v in res['traces_by_day'].items() if len(v['response']['data']) >= 1000]:  # 상한에 걸린 날은 3시간씩 나눠 다시 묻는다
    res['traces_by_day'][d] = {'split_3h': [metrics('scores-numeric', ['traceId'], frm=f'{d}T{h:02d}:00:00Z', to=f'{d}T{h + 2:02d}:59:59.999Z') for h in range(0, 24, 3)]}
    for i, w in enumerate(res['traces_by_day'][d]['split_3h']):
        if len(w['response']['data']) >= 1000:  # 3시간도 상한이면 1시간씩
            res['traces_by_day'][d]['split_3h'][i] = {'response': {'data': [r for h in range(3 * i, 3 * i + 3) for r in metrics('scores-numeric', ['traceId'], frm=f'{d}T{h:02d}:00:00Z', to=f'{d}T{h:02d}:59:59.999Z')['response']['data']]}, 'split_1h': True}
ntr = lambda v: sum(len(x['response']['data']) for x in v['split_3h']) if 'split_3h' in v else len(v['response']['data'])
json.dump(res, open(f'{out}/metrics_v2.json', 'w'), ensure_ascii=False, indent=1)
one = get('/api/public/v3/scores', {'fields': 'core,subject', 'limit': 100, 'traceId': trace_id})
json.dump({'endpoint': '/api/public/v3/scores?fields=core,subject&traceId=', 'trace_id': trace_id, **one}, open(f'{out}/trace_{trace_id}.json', 'w'), ensure_ascii=False, indent=1)
rows, cursor = [], None
while True:
    d = get('/api/public/v3/scores', {'fields': 'core,subject', 'limit': 100, 'fromTimestamp': since} | ({'cursor': cursor} if cursor else {}))
    rows += d['data']; cursor = d['meta'].get('cursor')
    if not cursor or not d['data']:
        break
json.dump({'endpoint': '/api/public/v3/scores?fields=core,subject&fromTimestamp=', 'from': since, 'n': len(rows), 'data': rows},
          open(f'{out}/scores_since_{since[:10]}.json', 'w'), ensure_ascii=False)
for view in ('scores-numeric', 'scores-categorical'):
    r = res[view]
    print(view, {x['name']: x['count_count'] for x in r['by_name']['response']['data']},
          [(x['time_dimension'], x['count_count']) for x in r['by_day']['response']['data'] if x['count_count']])
print('traces with numeric scores by day (UTC)', {d: ntr(v) for d, v in res['traces_by_day'].items()}, 'max rows per query', max(len(x['response']['data']) for v in res['traces_by_day'].values() for x in (v.get('split_3h') or [v])))
print('trace', trace_id, 'scores', len(one.get('data', [])), '| since', since, 'scores', len(rows))
