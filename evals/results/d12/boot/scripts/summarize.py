"""d12: run<n>/timeline_cold.json · smoke_cold.json을 모아 회차별 시간 표(summary.json)를 만든다. 사용: python summarize.py <boot 폴더>"""
import json, statistics, sys
from pathlib import Path

root = Path(sys.argv[1])
rows = []
for run in sorted(root.glob('run*/timeline_cold.json'), key=lambda p: int(p.parent.name[3:])):
    t = json.load(open(run))
    ev = {e['event']: e for e in t['events']}
    smoke = json.load(open(run.parent / 'smoke_cold.json')) if (run.parent / 'smoke_cold.json').exists() else {}
    up, h = ev['compose_up_issued']['t_sec'], ev.get('health_200', {}).get('t_sec')
    rows.append({'run': run.parent.name, 'commit': t.get('commit'), 'main_at_clone': t.get('main_at_clone'),
                 'clone_s': ev['git_clone_end']['t_sec'], 'clone_to_health_s': h, 'up_to_health_s': None if h is None else round(h - up, 3),
                 'clone_to_smoke_end_s': ev.get('smoke_end', {}).get('t_sec'), 'smoke_counts': smoke.get('counts'),
                 'rx_bytes_at_health': ev.get('health_200', {}).get('rx_bytes'),
                 'load_at_up': ev['host_load_at_up']['load1_5_15'], 'load_end': ev.get('host_load_end', {}).get('load1_5_15'),
                 'started_kst': ev['t0_git_clone_start']['iso_kst']})
ok = [r for r in rows if r['clone_to_health_s'] is not None]
med = {k: statistics.median(r[k] for r in ok) for k in ('clone_to_health_s', 'up_to_health_s')} if ok else {}
json.dump({'runs': rows, 'n_ok': len(ok), 'median': med,
           'range': {k: [min(r[k] for r in ok), max(r[k] for r in ok)] for k in med}}, open(root / 'summary.json', 'w'), ensure_ascii=False, indent=1)
for r in rows:
    print(r['run'], r['started_kst'][11:19], r['clone_s'], r['clone_to_health_s'], r['up_to_health_s'], r['smoke_counts'], r['load_at_up'], round((r['rx_bytes_at_health'] or 0) / 1e6))
print('median', med)
