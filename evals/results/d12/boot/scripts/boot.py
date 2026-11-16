"""D12 copy (2026-11-17) of d10/boot_2026-11-16/scripts/boot.py: clone GitHub main then check out PIN (799ae636), OUT per run from BOOT_OUT, load wait record-only, metadata from the clone. Original: D10 Measurement 1 driver (runs on the host, drives a docker:dind container). Usage: boot.py prep | cold | warm
Writes timeline_<phase>.json next to this script's parent dir. Stamps are host wall clock (KST, ms)."""
import json, os, subprocess, sys, threading, time, urllib.request
from datetime import datetime, timezone, timedelta
KST = timezone(timedelta(hours=9))
D = os.environ.get('DIND', 'sojafit-boot-d12')
PIN = os.environ.get('PIN', '799ae636')
CLONE = {}
OUT = os.environ['BOOT_OUT']; os.makedirs(OUT, exist_ok=True)
REPO = '/work/proj3-b'
CMD = 'docker compose up --build'           # exact README command
ENVV = ['-e', 'COMPOSE_PROGRESS=plain', '-e', 'BUILDKIT_PROGRESS=plain']  # output format only
T0 = None; EV = []

def now(): return time.time()
def ev(name, **kw):
    t = now(); r = {'event': name, 'iso_kst': datetime.fromtimestamp(t, KST).isoformat(timespec='milliseconds'),
                    'epoch': round(t, 3), 't_sec': None if T0 is None else round(t - T0, 3)}
    r.update(kw); EV.append(r); print(name, r['t_sec'], kw, flush=True); return r
def dx(*a, env=None, check=True, timeout=None, inp=None):
    e = [] if not env else sum((['-e', k] for k in env), [])
    return subprocess.run(['docker', 'exec', *e, D, *a], capture_output=True, text=True, check=check, timeout=timeout, env={**os.environ, **(env or {})})
def rx(): return int(dx('sh', '-c', "awk '/eth0/{print $2}' /proc/net/dev").stdout.split()[0])
def health():
    r = dx('wget', '-q', '-T', '2', '-O', '-', 'http://localhost:8000/health', check=False)
    return r.returncode == 0 and '"ok"' in r.stdout
def save(phase, extra=None):
    json.dump({'phase': phase, 'T0_epoch': T0, 'events': EV, **(extra or {})}, open(f'{OUT}/timeline_{phase}.json', 'w'), ensure_ascii=False, indent=1)

def prep():
    ev('prep_start')
    r = dx('sh', '-c', 'docker images -a; echo ---; docker volume ls; echo ---; docker network ls; echo ---; docker ps -a; echo ---; docker buildx du 2>&1 | tail -3; echo ---; ls /var/lib/docker/overlay2 2>/dev/null | wc -l')
    open(f'{OUT}/empty_before.txt', 'w').write(r.stdout + r.stderr)
    b = rx(); t = now()
    dx('apk', 'add', '--no-cache', 'git', 'python3', 'py3-httpx', 'tzdata')
    ev('prep_apk_done', seconds=round(now() - t, 1), rx_bytes=rx() - b, packages='git python3 py3-httpx tzdata')
    dx('sh', '-c', 'mkdir -p /work /tools; (docker events --format "{{json .}}" > /tmp/events.jsonl 2>/dev/null &) ; sleep 1')
    save('prep')

def cold_or_warm(phase):
    global T0
    tok = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True).stdout.strip()
    env = {'GH_TOKEN': tok}
    dx('sh', '-c', 'echo "" > /tmp/events.jsonl.mark')
    rx0 = rx()
    if phase == 'cold':
        la = os.getloadavg(); ev('host_load_before_cold', load1_5_15=[round(x, 2) for x in la])
        ev('host_load_no_wait', note='d12: record only, no wait (other agents share the host)')
        rx0 = rx()
        T0 = now(); ev('t0_git_clone_start', rx_bytes_total=0, branch='main')
        r = dx('sh', '-c', f'cd /work && git clone -q -b main https://x-access-token:$GH_TOKEN@github.com/aihuman-7th/proj3-b.git 2>&1 | sed "s/$GH_TOKEN/***/g"; cd proj3-b && git rev-parse HEAD > /tmp/main_at_clone && git checkout -q {PIN} && git remote set-url origin https://github.com/aihuman-7th/proj3-b.git && git rev-parse HEAD && git rev-parse HEAD^{{tree}} && git rev-parse --abbrev-ref HEAD && git config --get remote.origin.url && du -sk .git | cut -f1 && du -sk . | cut -f1 && ls -a | tr "\\n" " "', env=env)
        parts = r.stdout.strip().splitlines()
        CLONE.update(commit=parts[0], tree=parts[1], main_at_clone=dx('cat', '/tmp/main_at_clone').stdout.strip())
        ev('git_clone_end', main_at_clone=CLONE['main_at_clone'], commit=parts[0], tree=parts[1], branch=parts[2], origin_url_after=parts[3], git_dir_kb=int(parts[4]), total_kb=int(parts[5]), has_env_file='.env' in parts[6].split(), rx_bytes=rx() - rx0)
        assert parts[0].startswith(PIN), parts
        assert '.env' not in parts[6].split() , 'unexpected .env'
    else:
        ev('compose_down_v_start', command='docker compose down -v (removes containers+volumes, keeps images and build cache)')
        d = dx('sh', '-c', f'cd {REPO} && docker compose down -v 2>&1 | tail -15', check=False)
        ev('compose_down_v_end', tail=d.stdout[-600:])
        open(f'{OUT}/compose_down_warm.txt', 'w').write(d.stdout)
        T0 = now(); rx0 = rx()
    ev('host_load_at_up', load1_5_15=[round(x, 2) for x in os.getloadavg()])
    ev('compose_up_issued', command=CMD, cwd=REPO, env_set='COMPOSE_PROGRESS=plain BUILDKIT_PROGRESS=plain (output format only)')
    dx('sh', '-c', 'rm -f /tmp/up.log; : > /tmp/up.log')
    subprocess.run(['docker', 'exec', '-d', *ENVV, '-w', REPO, D, 'sh', '-c', f'{CMD} > /tmp/up.log 2>&1'], check=True)
    up_issue = now()
    # relay log lines with host stamps
    stamped = []
    p = subprocess.Popen(['docker', 'exec', D, 'tail', '-n', '+1', '-F', '/tmp/up.log'], stdout=subprocess.PIPE, text=True, bufsize=1)
    def relay():
        for line in p.stdout: stamped.append((now(), line.rstrip('\n')))
    th = threading.Thread(target=relay, daemon=True); th.start()
    deadline = up_issue + 25 * 60; ok = False
    while now() < deadline:
        if health(): ok = True; break
        time.sleep(0.4)
    if not ok:
        ev('health_timeout_25min'); save(phase); p.kill(); return
    ev('health_200', rx_bytes=rx() - rx0)
    # demo login (A) with exact origin
    t = now()
    r = dx('python3', '/tools/login.py', check=False)
    ev('demo_login_A_done', status=r.stdout.strip() or r.stderr[-200:], seconds=round(now() - t, 3))
    # smoke
    ev('smoke_start', flags='--base-url http://localhost:8000 --demo --refusal', python='alpine python3 + py3-httpx inside dind (host network of dind)')
    r = dx('python3', '-I', 'scripts/smoke/http_smoke.py', '--base-url', 'http://localhost:8000', '--demo', '--refusal', check=False) if False else subprocess.run(
        ['docker', 'exec', '-w', REPO, D, 'python3', 'scripts/smoke/http_smoke.py', '--base-url', 'http://localhost:8000', '--demo', '--refusal'], capture_output=True, text=True)
    ev('smoke_end', exit_code=r.returncode, rx_bytes=rx() - rx0)
    open(f'{OUT}/smoke_{phase}.log', 'w').write(r.stdout + r.stderr)
    res = dx('sh', '-c', f'ls -t {REPO}/scripts/results/smoke/*.json | head -1').stdout.strip()
    subprocess.run(['docker', 'cp', f'{D}:{res}', f'{OUT}/smoke_{phase}.json'], check=True)
    time.sleep(2)
    p.kill()
    log = [{'epoch': round(t, 3), 'iso_kst': datetime.fromtimestamp(t, KST).isoformat(timespec='milliseconds'), 'line': l} for t, l in stamped]
    open(f'{OUT}/compose_up_{phase}.log', 'w').write('\n'.join(f"{x['iso_kst']} {x['line']}" for x in log) + '\n')
    sub = subprocess.run(['docker', 'exec', D, 'cat', '/tmp/events.jsonl'], capture_output=True, text=True).stdout
    open(f'{OUT}/docker_events_{phase}.jsonl', 'w').write(sub)
    ev('host_load_end', load1_5_15=[round(x, 2) for x in os.getloadavg()])
    save(phase, {'rx_total_bytes': rx() - rx0, **CLONE, 'checkout': f'GitHub main clone, then git checkout {PIN}'})

if __name__ == '__main__':
    {'prep': prep}.get(sys.argv[1], lambda: cold_or_warm(sys.argv[1]))()
