"""Merge docker-events (dind clock) + BuildKit log into timeline_<phase>.json and compute the candidate start-point durations."""
import json, re, sys, os
from datetime import datetime, timezone, timedelta
K = timezone(timedelta(hours=9)); OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def iso(t): return datetime.fromtimestamp(t, K).isoformat(timespec='milliseconds')
summary = {}
for phase in ('cold', 'warm'):
    tl = json.load(open(f'{OUT}/timeline_{phase}.json')); T0 = tl['T0_epoch']; ev = {e['event']: e for e in tl['events']}
    up = ev['compose_up_issued']['epoch']; lo = (ev['t0_git_clone_start']['epoch'] if phase == 'cold' else up) - 1
    hi = ev['smoke_end']['epoch'] + 5; extra = []
    for l in open(f'{OUT}/docker_events_{phase}.jsonl'):
        if not l.strip(): continue
        e = json.loads(l); t = e['timeNano'] / 1e9
        if not lo <= t <= hi: continue
        a = e.get('Action', ''); n = e['Actor']['Attributes'].get('name', '')
        if e['Type'] == 'container' and a.split(':')[0] in ('create', 'start', 'die', 'health_status') and n.startswith('proj3-b-'):
            extra.append({'event': f'docker_{a.split(":")[0]}_{n}' + (f'_{a.split(": ")[1]}' if a.startswith('health_status') else ''), 'iso_kst': iso(t), 'epoch': round(t, 3), 't_sec': round(t - T0, 3), 'source': 'docker events (dind clock)', 'exit_code': e['Actor']['Attributes'].get('exitCode')})
        elif e['Type'] == 'image' and a == 'pull': extra.append({'event': f'docker_image_pull_{n}', 'iso_kst': iso(t), 'epoch': round(t, 3), 't_sec': round(t - T0, 3), 'source': 'docker events (dind clock)'})
        elif e['Type'] == 'image' and a == 'tag': extra.append({'event': f'docker_image_built_{n}', 'iso_kst': iso(t), 'epoch': round(t, 3), 't_sec': round(t - T0, 3), 'source': 'docker events (dind clock)'})
    log = open(f'{OUT}/compose_up_{phase}.log').read().splitlines(); pat = []
    def first(rx):
        for l in log:
            if re.search(rx, l):
                t = datetime.fromisoformat(l.split(' ', 1)[0]).timestamp(); return t
    marks = {'pgvector_pull_start': r'Image pgvector/pgvector:pg16 Pulling', 'pgvector_pull_end': r'Image pgvector/pgvector:pg16 Pulled', 'build_start': r'Image proj3-b-api Building',
             'build_end': r'Image proj3-b-thread-setup Built'}
    for k, rx in marks.items():
        t = first(rx)
        if t: extra.append({'event': k, 'iso_kst': iso(t), 'epoch': round(t, 3), 't_sec': round(t - T0, 3), 'source': 'compose log line (host-stamped when relayed; +-1s because compose output is buffered)'})
    steps = {}
    for l in log:
        m = re.match(r'\S+ #(\d+) DONE ([0-9.]+)s', l)
        if m: steps[m.group(1)] = float(m.group(2))
    names = {}
    for l in log:
        m = re.match(r'\S+ #(\d+) \[(.*?)\] (.*)', l)
        if m and m.group(1) not in names and m.group(1) in steps: names[m.group(1)] = f'{m.group(2)} {m.group(3)}'[:110]
    tl['events'] = sorted(tl['events'] + extra, key=lambda e: e['epoch'])
    tl['build_steps_seconds'] = {f'#{k}': {'seconds': v, 'step': names.get(k)} for k, v in steps.items() if v >= 1.0}
    d = lambda a, b: round(ev[b]['epoch'] - ev[a]['epoch'], 1)
    t0e = ev['t0_git_clone_start']['epoch'] if phase == 'cold' else up
    der = {'b_up_issued_to_health_200': d('compose_up_issued', 'health_200'), 'c_up_issued_to_smoke_end': d('compose_up_issued', 'smoke_end'),
           'health_to_login': d('health_200', 'demo_login_A_done'), 'smoke_run_seconds': d('smoke_start', 'smoke_end')}
    if phase == 'cold': der.update({'a_clone_start_to_health_200': round(ev['health_200']['epoch'] - t0e, 1), 'd_clone_start_to_smoke_end': round(ev['smoke_end']['epoch'] - t0e, 1), 'clone_seconds': d('t0_git_clone_start', 'git_clone_end')})
    tl['derived_seconds'] = der; json.dump(tl, open(f'{OUT}/timeline_{phase}.json', 'w'), ensure_ascii=False, indent=1); summary[phase] = der; print(phase, json.dumps(der))
    if phase == 'cold': print(json.dumps(tl['build_steps_seconds'], ensure_ascii=False, indent=0)[:2500])
