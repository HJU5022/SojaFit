"""동시 로그인에서 scrypt 검증 상한(2건)과 프로세스 메모리를 재는 일회성 실측. 인증 담당이 Windows에서 손으로 돌린다.

- 역할: 로그인 1건과 동시 2건이 쓰는 작업 집합·전용 메모리는 얼마인가, 검증 슬롯 2개가 찬 동안 세 번째 로그인이
  503으로 막히는가, 두 사용자의 세션이 서로 격리되는가를 본다.
- 하지 않는 일: 평가셋 평가(evals/)가 아니다. 경계 시각은 재지 않는다(auth_boundary_after_merge.py). Windows 밖에서는 돌지 않는다.
  외부 API·키는 쓰지 않는다.
- 출처: SPEC 8.6(로그인 AC), docs/specs/login-auth.md, docs/research/auth-login-verification.md
- 입력: 환경변수 TEST_AUTH_DATABASE_URL. 값에 127.0.0.1:55434/ci_auth가 없으면 실행을 거부한다(격리된 테스트 DB 전용).
- 원시 결과: scripts/results/scrypt_concurrent_<KST 날짜>.json(같은 날 다시 돌리면 덮어쓴다).
  시험용 사용자와 로그인 시도 기록은 끝에 지운다.
- 필요한 것: Windows(ctypes.windll의 GetProcessMemoryInfo 사용, 다른 OS는 import에서 실패), 인증 SQL을 적용한 격리 PostgreSQL.

실행(저장소 루트에서, Windows): uv run python scripts/measure_scrypt_concurrent.py
"""
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

# [왜] 저장소 루트를 import 경로에 넣어 `backend`를 어느 위치에서 실행해도 찾게 한다
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zoneinfo import ZoneInfo

import fastapi
import psycopg
from fastapi.testclient import TestClient
from backend import auth
from backend.main import app

database_url = os.environ['TEST_AUTH_DATABASE_URL']
# [주의] DB 안전장치: 로컬 격리 테스트 DB 주소가 아니면 사용자 INSERT·DELETE를 하기 전에 거부한다
if '127.0.0.1:55434/ci_auth' not in database_url:
    raise RuntimeError('isolated test DB required')
os.environ['DATABASE_URL'] = database_url  # [왜] 서버 코드(backend.auth)가 DATABASE_URL을 읽으므로 테스트 DB로 맞춘다
os.environ['AUTH_ORIGIN'] = 'http://testserver'


class Memory(ctypes.Structure):
    """Windows PROCESS_MEMORY_COUNTERS_EX 구조체. 작업 집합(WorkingSetSize)과 전용 사용량(PrivateUsage)을 읽는다."""
    _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            'PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage',
            'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage',
            'PagefileUsage', 'PeakPagefileUsage', 'PrivateUsage')]


# [주의] ctypes.windll는 Windows에만 있어, 다른 OS에서는 이 줄에서 AttributeError로 실패한다
ctypes.windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
handle = ctypes.windll.kernel32.GetCurrentProcess()
get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
# 인자·반환 형을 선언해야 64비트 핸들이 잘리지 않는다
get_memory.argtypes = (wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD)
get_memory.restype = wintypes.BOOL


def memory():
    """현재 프로세스의 (작업 집합 바이트, 전용 사용 바이트)를 돌려준다."""
    data = Memory()
    data.cb = ctypes.sizeof(data)
    if not get_memory(handle, ctypes.byref(data), data.cb):
        raise ctypes.WinError()
    return data.WorkingSetSize, data.PrivateUsage


def measure(operation):
    """operation을 실행하는 동안 2ms마다 메모리를 표집해 기준값·최고값·증가량(MiB)과 operation의 반환값을 돌려준다."""
    baseline = memory()  # operation 시작 직전의 메모리(증가량의 기준)
    values = [baseline]
    stop = threading.Event()
    def sample():
        while not stop.wait(0.002):  # 2ms마다 별도 스레드에서 표집. 더 짧은 순간 최고값은 놓칠 수 있다
            values.append(memory())
    worker = threading.Thread(target=sample)
    worker.start()
    try:
        result = operation()
    finally:
        values.append(memory())
        stop.set()
        worker.join()
    # 최고값 = 표집한 값 중 작업 집합(0번)·전용 사용(1번) 각각의 최댓값
    peak = tuple(max(v[i] for v in values) for i in range(2))
    return {'baseline_working_mib': round(baseline[0]/2**20, 2),
            'peak_working_mib': round(peak[0]/2**20, 2),
            'delta_working_mib': round((peak[0]-baseline[0])/2**20, 2),
            'baseline_private_mib': round(baseline[1]/2**20, 2),
            'peak_private_mib': round(peak[1]/2**20, 2),
            'delta_private_mib': round((peak[1]-baseline[1])/2**20, 2),
            'samples': len(values), 'result': result}


tag = secrets.token_hex(8)  # 실행마다 다른 값으로 시험 계정 이메일이 겹치지 않게 한다
emails = [f'memory-{tag}-{i}@example.test' for i in (1, 2)]
passwords = [secrets.token_urlsafe(24) for _ in emails]
ids = []
original = auth.verify_password  # 진짜 scrypt 검증. 측정 뒤 반드시 되돌린다
gate = threading.Event()     # 열릴 때까지 두 검증을 문 앞에 세워 둔다
ready = threading.Event()    # 두 건이 모두 문 앞에 도착했다는 신호
running = threading.Event()  # 두 건의 scrypt가 모두 시작했다는 신호
mutex = threading.Lock()
intervals = []  # 각 scrypt 실행 구간 (시작, 끝)
starts = []
entered = 0
headers = {'origin': 'http://testserver'}
try:
    # 시험 사용자 2명을 넣는다. [주의] 커밋되므로 끝의 finally에서 지운다
    with psycopg.connect(database_url) as conn:
        version = conn.execute('SHOW server_version').fetchone()[0]
        for email, password in zip(emails, passwords):
            ids.append(conn.execute('INSERT INTO users(login_id,password_hash) VALUES (%s,%s) RETURNING id', (email, auth.hash_password(password))).fetchone()[0])

    def single():
        """로그인 1건 + 로그아웃의 응답 시간을 잰다(메모리 기준선 측정용)."""
        with TestClient(app) as client:
            start = time.perf_counter()
            response = client.post('/api/auth/login', headers=headers, json={'email': emails[0], 'password': passwords[0]})
            elapsed = round((time.perf_counter()-start)*1000, 2)
            assert response.status_code == 200 and response.json()['user_id'] == ids[0]
            assert client.post('/api/auth/logout', headers=headers).status_code == 200
        return {'login_status': response.status_code, 'login_ms': elapsed}

    one = measure(single)  # 1건 로그인의 메모리 기준선

    def guarded_verify(password, encoded):
        """auth.verify_password 대용. 두 건이 모두 들어올 때까지 문을 닫았다가 열어 실제 scrypt가 겹치게 하고 구간을 기록한다."""
        global entered
        # [왜] 문을 닫아 두 건이 동시에 scrypt에 들어가게 맞춰야 "동시 2건"의 메모리를 잴 수 있다
        with mutex:
            entered += 1
            if entered == 2:
                ready.set()
        if not gate.wait(20):  # [주의] 20초 안에 문이 안 열리면 측정이 영영 멈추지 않게 실패시킨다
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
        """두 사용자가 동시에 로그인하는 동안 세 번째 로그인이 503으로 막히는지, 세션이 서로 격리되는지 확인하고 수치를 돌려준다."""
        auth.verify_password = guarded_verify  # [주의] 전역 교체. 아래 finally에서 원래대로 되돌린다
        clients = [TestClient(app), TestClient(app)]
        try:
            def login(index):
                """index번째 사용자로 로그인해 (응답, 걸린 ms)를 돌려준다."""
                start = time.perf_counter()
                response = clients[index].post('/api/auth/login', headers=headers, json={'email': emails[index], 'password': passwords[index]})
                return response, round((time.perf_counter()-start)*1000, 2)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(login, i) for i in (0, 1)]
                try:
                    assert ready.wait(15), 'two verification slots were not reached'
                    # 검증 슬롯 2개가 찬 상태에서 세 번째 로그인은 503이어야 한다(상한 2건)
                    with TestClient(app) as third:
                        blocked = third.post('/api/auth/login', headers=headers, json={'email': 'third@example.test', 'password': 'not-used'})
                    assert blocked.status_code == 503
                finally:
                    gate.set()
                assert running.wait(15), 'two scrypt operations did not start'
                # 두 scrypt가 실제로 도는 동안에도 세 번째가 503인지 한 번 더 본다
                with TestClient(app) as third:
                    third_start = time.perf_counter()
                    during = third.post('/api/auth/login', headers=headers, json={'email': 'third@example.test', 'password': 'not-used'})
                    third_end = time.perf_counter()
                assert during.status_code == 503
                results = [future.result(timeout=30) for future in futures]
            for i, (response, _) in enumerate(results):
                assert response.status_code == 200 and response.json()['user_id'] == ids[i]
            # 세션 격리: A만 로그아웃해도 B는 살아 있고, B 로그아웃 뒤에는 둘 다 401이어야 한다
            before = [clients[i].get('/api/auth/me') for i in (0, 1)]
            assert all(r.status_code == 200 and r.json()['user_id'] == ids[i] for i, r in enumerate(before))
            a_logout = clients[0].post('/api/auth/logout', headers=headers)
            a_after = clients[0].get('/api/auth/me')
            b_after_a = clients[1].get('/api/auth/me')
            b_logout = clients[1].post('/api/auth/logout', headers=headers)
            b_after = clients[1].get('/api/auth/me')
            assert (a_logout.status_code, a_after.status_code, b_after_a.status_code, b_logout.status_code, b_after.status_code) == (200, 401, 200, 200, 401)
            assert b_after_a.json()['user_id'] == ids[1]
            # 두 scrypt 구간이 실제로 겹쳤는지(겹침 = 늦은 시작 ~ 이른 끝)
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

    two = measure(parallel)  # 2건 동시 로그인의 메모리
    result = {'measured_at_kst': datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds'),
              'python': platform.python_version(), 'fastapi': fastapi.__version__, 'os': platform.platform(),
              'postgres': version, 'method': 'FastAPI TestClient in one Windows process; real scrypt; local isolated PostgreSQL; process memory sampled every 2ms',
              'scrypt': {'n': auth.N, 'r': auth.R, 'p': auth.P}, 'single': one, 'two_concurrent': two}
    # [주의] 같은 날 다시 돌리면 같은 이름의 결과 파일을 덮어쓴다
    out = Path(__file__).resolve().parents[1] / 'scripts' / 'results' / f"scrypt_concurrent_{result['measured_at_kst'][:10]}.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
finally:
    gate.set()  # 대기 중인 스레드가 있으면 풀어 준다
    auth.verify_password = original
    if ids:  # 시험 사용자와 로그인 시도 기록을 지운다(DB에 남기지 않기)
        with psycopg.connect(database_url) as conn:
            conn.execute('DELETE FROM users WHERE id=ANY(%s)', (ids,))
            conn.execute('DELETE FROM auth_login_attempts WHERE login_hash=ANY(%s)', ([hashlib.sha256(email.encode()).hexdigest() for email in emails],))
