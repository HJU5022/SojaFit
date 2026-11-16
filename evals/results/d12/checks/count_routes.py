from backend.main import app
from fastapi.testclient import TestClient

routes = [r for g in app.routes if hasattr(g, 'original_router') for r in g.original_router.routes]
ops = [(m, r) for r in routes for m in r.methods]
print('ops', len(ops), 'paths', len({r.path for r in routes}))
vis = [(m, r) for m, r in ops if r.include_in_schema]
print('docs ops', len(vis), 'docs paths', len({r.path for m, r in vis}))
print('mutating', len([1 for m, r in ops if m in ('POST', 'PATCH', 'DELETE')]))
print('response_model', len([1 for m, r in ops if getattr(r, 'response_model', None) is not None]))
spec = TestClient(app).get('/openapi.json').json()
refs = {op['requestBody']['content']['application/json']['schema']['$ref'].rsplit('/', 1)[-1]
        for item in spec['paths'].values() for op in item.values()
        if 'application/json' in op.get('requestBody', {}).get('content', {})}
print('json body models', len(refs))
print('204', [(m, r.path) for m, r in ops if r.status_code == 204])
