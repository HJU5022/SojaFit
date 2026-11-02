"""Local Windows measurement. Uses only the isolated authentication test DB."""
import concurrent.futures
import ctypes
import hashlib
import json
import os
import platform
import secrets
import sys
import threading
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zoneinfo import ZoneInfo

import fastapi
import psycopg
from fastapi.testclient import TestClient
from backend import auth
from backend.main import app

database_url = os.environ['TEST_AUTH_DATABASE_URL']
if '127.0.0.1:55434/ci_auth' not in database_url:
    raise RuntimeError('isolated test DB required')
os.environ['DATABASE_URL'] = database_url
os.environ['AUTH_ORIGIN'] = 'http://testserver'


class Memory(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
            'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
            'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]


ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
handle = ctypes.windll.kernel32.GetCurrentProcess()
get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
get_memory.argtypes = (wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD)
get_memory.restype = wintypes.BOOL


def memory():
    data = Memory()
    data.cb = ctypes.sizeof(data)
    if not get_memory(handle, ctypes.byref(data), data.cb):
        raise ctypes.WinError()
    return data.WorkingSetSize, data.PrivateUsage


def measure(operation):
    baseline = memory()
    values = [baseline]
    stop = threading.Event()
    def sample():
        while not stop.wait(0.002):
            values.append(memory())
    worker = threading.Thread(target=sample)
    worker.start()
    try:
        result = operation()
    finally:
        values.append(memory())
        stop.set()
        worker.join()
    peak = tuple(max(v[i] for v in values) for i in range(2))
    return {'baseline_working_mib': round(baseline[0]/2**20, 2),
            'peak_working_mib': round(peak[0]/2**20, 2),
            'delta_working_mib': round((peak[0]-baseline[0])/2**20, 2),
            'baseline_private_mib': round(baseline[1]/2**20, 2),
            'peak_private_mib': round(peak[1]/2**20, 2),
            'delta_private_mib': round((peak[1]-baseline[1])/2**20, 2),
            'samples': len(values), 'result': result}


tag = secrets.token_hex(8)
emails = [f'memory-{tag}-{i}@example.test' for i in (1, 2)]
passwords = [secrets.token_urlsafe(24) for _ in emails]
ids = []
original = auth.verify_password
gate = threading.Event()
ready = threading.Event()
running = threading.Event()
mutex = threading.Lock()
intervals = []
starts = []
entered = 0
headers = {'origin': 'http://testserver'}
try:
    with psycopg.connect(database_url) as conn:
        version = conn.execute('SHOW server_version').fetchone()[0]
        for email, password in zip(emails, passwords):
            ids.append(conn.execute('INSERT INTO users(login_id,password_hash) VALUES (%s,%s) RETURNING id', (email, auth.hash_password(password))).fetchone()[0])

    def single():
        with TestClient(app) as client:
            start = time.perf_counter()
            response = client.post('/api/auth/login', headers=headers, json={'email': emails[0], 'password': passwords[0]})
            elapsed = round((time.perf_counter()-start)*1000, 2)
            assert response.status_code == 200 and response.json()['user_id'] == ids[0]
            assert client.post('/api/auth/logout', headers=headers).status_code == 200
        return {'login_status': response.status_code, 'login_ms': elapsed}

    one = measure(single)

    def guarded_verify(password, encoded):
        global entered
        with mutex:
            entered += 1
            if entered == 2:
                ready.set()
        if not gate.wait(20):
            raise RuntimeError('measurement gate timed out')
        start = time.perf_counter()
        with mutex:
            starts.append(start)
            if len(starts) == 2:
                running.set()
        try:
            return original(password, encoded)
        finally:
            with mutex:
                intervals.append((start, time.perf_counter()))

    def parallel():
        auth.verify_password = guarded_verify
        clients = [TestClient(app), TestClient(app)]
        try:
            def login(index):
                start = time.perf_counter()
                response = clients[index].post('/api/auth/login', headers=headers, json={'email': emails[index], 'password': passwords[index]})
                return response, round((time.perf_counter()-start)*1000, 2)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(login, i) for i in (0, 1)]
                try:
                    assert ready.wait(15), 'two verification slots were not reached'
                    with TestClient(app) as third:
                        blocked = third.post('/api/auth/login', headers=headers, json={'email': 'third@example.test', 'password': 'not-used'})
                    assert blocked.status_code == 503
                finally:
                    gate.set()
                assert running.wait(15), 'two scrypt operations did not start'
                with TestClient(app) as third:
                    third_start = time.perf_counter()
                    during = third.post('/api/auth/login', headers=headers, json={'email': 'third@example.test', 'password': 'not-used'})
                    third_end = time.perf_counter()
                assert during.status_code == 503
                results = [future.result(timeout=30) for future in futures]
            for i, (response, _) in enumerate(results):
                assert response.status_code == 200 and response.json()['user_id'] == ids[i]
            before = [clients[i].get('/api/auth/me') for i in (0, 1)]
            assert all(r.status_code == 200 and r.json()['user_id'] == ids[i] for i, r in enumerate(before))
            a_logout = clients[0].post('/api/auth/logout', headers=headers)
            a_after = clients[0].get('/api/auth/me')
            b_after_a = clients[1].get('/api/auth/me')
            b_logout = clients[1].post('/api/auth/logout', headers=headers)
            b_after = clients[1].get('/api/auth/me')
            assert (a_logout.status_code, a_after.status_code, b_after_a.status_code, b_logout.status_code, b_after.status_code) == (200, 401, 200, 200, 401)
            assert b_after_a.json()['user_id'] == ids[1]
            overlap = max(0, min(i[1] for i in intervals) - max(i[0] for i in intervals))
            assert len(intervals) == 2 and overlap > 0
            assert third_start >= max(starts) and third_end <= min(i[1] for i in intervals)
            return {'login_statuses': [r.status_code for r, _ in results],
                    'elapsed_including_gate_ms': [ms for _, ms in results],
                    'third_status_while_two_slots_held': blocked.status_code,
                    'third_status_during_both_scrypt_calls': during.status_code,
                    'third_request_ms': round((third_end-third_start)*1000, 2),
                    'actual_scrypt_overlap_ms': round(overlap*1000, 2),
                    'session_checks': {'a_me_before': before[0].status_code, 'b_me_before': before[1].status_code,
                                       'a_logout': a_logout.status_code, 'a_after_logout': a_after.status_code,
                                       'b_after_a_logout': b_after_a.status_code, 'b_logout': b_logout.status_code,
                                       'b_after_logout': b_after.status_code}}
        finally:
            gate.set()
            auth.verify_password = original
            for client in clients:
                client.close()

    two = measure(parallel)
    result = {'measured_at_kst': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds'),
              'python': platform.python_version(), 'fastapi': fastapi.__version__, 'os': platform.platform(),
              'postgres': version, 'method': 'FastAPI TestClient in one Windows process; real scrypt; local isolated PostgreSQL; process memory sampled every 2ms',
              'scrypt': {'n': auth.N, 'r': auth.R, 'p': auth.P}, 'single': one, 'two_concurrent': two}
    Path(__file__).with_name('scrypt_concurrent_final_measurement.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
finally:
    gate.set()
    auth.verify_password = original
    if ids:
        with psycopg.connect(database_url) as conn:
            conn.execute('DELETE FROM users WHERE id=ANY(%s)', (ids,))
            conn.execute('DELETE FROM auth_login_attempts WHERE login_hash=ANY(%s)', ([hashlib.sha256(email.encode()).hexdigest() for email in emails],))
