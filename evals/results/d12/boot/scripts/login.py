import json, urllib.request
r = urllib.request.Request('http://localhost:8000/api/auth/demo-login', data=json.dumps({'account': 'a'}).encode(),
    headers={'Content-Type': 'application/json', 'Origin': 'http://localhost:8000'}, method='POST')
print(urllib.request.urlopen(r, timeout=10).status)
