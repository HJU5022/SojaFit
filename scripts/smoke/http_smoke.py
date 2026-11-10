"""정상 사용자 흐름을 HTTP로 처음부터 끝까지 한 번 돌려 단계마다 통과 · 실패를 남기는 점검(스모크). 저장소 루트에서 손으로 돌린다.

- 역할: 로컬 compose나 배포 주소(Cloud Run)의 API를 화면 대신 불러, SPEC 2절 "목표 사용자 흐름"(로그인 → 데모 회로 프로젝트 →
  판정 질문 → 조건 질문 재개 → 승인 → 견적)과 계정 격리(B가 A의 프로젝트 · thread 목록 · run · 견적 · 승인 · 승인 사례에 접근하면 404, 승인 사례 목록에 A 것 없음)가 지금 서버에서 이어지는지 본다.
  요청마다 HTTP 상태 · `error.code` · `X-Request-ID` · 걸린 ms를, run · 재개는 SSE 이벤트 이름 순서를 적는다.
  `/openapi.json`의 경로 · 연산 수와 이 작업 트리의 커밋을 함께 남겨 배포가 어느 코드인지 대조한다.
- 하지 않는 일: 답 · 판정이 맞는지 채점(`evals/`), 서버 · docker · DB 띄우기, 만든 프로젝트 · 승인 · 견적 지우기,
  가입 · 업로드 · 가격 · 내 설정 경로. 결과 파일에 비밀번호 · 쿠키 · 세션 · 이메일(계정은 A · B로만) · 답 글 · 오류 문구를 적지 않는다.
- 출처: SPEC 2절 목표 사용자 흐름, 4절 계약(HTTP API 표 · 공통 오류 · SSE 이벤트), 8.4 견적서 승인, 8.6 로그인,
  backend/api/*.py(로그인 경로는 backend/api/auth.py), backend/auth.py `check_origin`.
  질문 · 조건 글은 scripts/demo/record_demo.py의 `QUESTIONS`(v3-01 · v3-30)를 그대로 읽는다.
- 입력: `--base-url`. `--demo`면 데모 버튼 로그인(`POST /api/auth/demo-login`, A · B), 아니면 환경변수
  SMOKE_A_EMAIL · SMOKE_A_PASSWORD · SMOKE_B_EMAIL · SMOKE_B_PASSWORD(비밀번호는 명령줄 인자로 받지 않는다).
  데모가 아니면 4 · 5단계(`--refusal`이면 9단계도)가 실제 LLM을 불러 `--confirm-live`가 있어야 요청을 시작한다.
  [주의] `--demo`는 서버가 기록 응답을 재생한다(`DEMO_REPLAY=1`)고 보고 비용 확인을 하지 않는다. 키를 넣고 재생을 끈 서버에는 쓰지 않는다.
- 원시 결과: scripts/results/smoke/smoke_<호스트>_<KST 날짜>_<시각>.json. 통과 못 한 단계가 하나라도 있으면 종료 코드 1, 요청 전에 멈추면 2.
- 실행 예(저장소 루트, 전체 명령은 scripts/smoke/SMOKE.md):
  uv run python scripts/smoke/http_smoke.py --base-url http://localhost:8000 --demo --refusal
  uv run python scripts/smoke/http_smoke.py --base-url https://<배포 주소> --confirm-live   (SMOKE_* 환경변수를 먼저 넣는다)
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / 'scripts/results/smoke'
KST = ZoneInfo('Asia/Seoul')
JUDGE_ID, REFUSAL_ID = 'v3-01', 'v3-30'  # 판정 + 조건 질문, 범위 밖 거절(scripts/demo/DEMO.md 데모 질문 표)
APPROVABLE = ('IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT')  # 사람이 승인할 수 있는 판정 3종(backend/api/quotes.py `Approvable`)
TERMINAL = ('requires_input', 'completed', 'refused', 'failed')  # SSE 마지막 이벤트(SPEC 4절 이벤트 표)
METHODS = {'get', 'post', 'put', 'patch', 'delete'}  # OpenAPI 경로 항목에서 연산으로 세는 키
ACCOUNT_VARS = ('SMOKE_A_EMAIL', 'SMOKE_A_PASSWORD', 'SMOKE_B_EMAIL', 'SMOKE_B_PASSWORD')
# [왜] 서버는 사용자마다 분석 호출 사이를 ANALYSIS_MIN_INTERVAL_SECONDS(기본 2초) 띄운다. 너무 빨리 재개하면 그 run이
#      RATE_LIMITED로 실패 저장돼 다시 재개할 수 없으므로, 분석 호출(재개 · 9단계 run) 앞에서 이만큼 기다린다
GAP_SECONDS = 3
# [왜] 분석 한 번의 시간 상한이 90초(ANALYSIS_MAX_SECONDS)라 SSE 읽기는 그보다 길게 기다린다. 연결 · 보통 요청은 10초면 충분하다
TIMEOUT = httpx.Timeout(10, read=180)


def demo_questions() -> dict:
    """record_demo.py의 데모 질문을 id로 찾는 dict. 질문 · 조건 글을 이 파일에 옮겨 적지 않는다(글자 하나만 달라도 데모 재생이 422)."""
    spec = importlib.util.spec_from_file_location('record_demo', ROOT / 'scripts/demo/record_demo.py')
    module = importlib.util.module_from_spec(spec)
    # [주의] record_demo.py는 맨 위에서 표준 라이브러리만 읽고 backend는 함수 안에서만 import한다. 그래서 읽어도 .env · DB를 건드리지 않는다
    spec.loader.exec_module(module)
    return {q['id']: q for q in module.QUESTIONS}


def parse(response) -> tuple:
    """(JSON 본문, 공통 오류의 error 칸). JSON이 아니면 ({}, {})."""
    try:
        data = response.json()
    except ValueError:
        return {}, {}
    error = data.get('error') if isinstance(data, dict) else None
    return data, error if isinstance(error, dict) else {}


class Smoke:
    """단계 기록(rows)을 쌓고 계정별 HTTP 클라이언트를 만든다."""

    def __init__(self, base_url: str, transport=None):
        self.base = base_url.rstrip('/')
        self.transport = transport  # 시험이 가짜 서버(httpx.MockTransport)를 끼우는 자리. 평소에는 None(실제 네트워크)
        self.rows = []
        self.openapi = None

    def client(self) -> httpx.Client:
        """계정 하나의 클라이언트. 계정마다 따로 만들어 쿠키 통(cookie jar)을 나눈다."""
        # [왜] 바꾸는 요청은 서버가 Origin을 AUTH_ORIGIN과 대조한다(다르면 403 ORIGIN_MISMATCH). 화면과 같은 출처를 모든 요청에 붙인다
        return httpx.Client(base_url=self.base, headers={'Origin': self.base}, timeout=TIMEOUT, transport=self.transport)

    def add(self, step, check, who, request, expect, result, response=None, started=None, code=None, note='', **extra):
        """한 줄을 남기고 화면에 찍는다. result는 pass · fail · skip."""
        row = {'step': step, 'check': check, 'account': who, 'request': request, 'expect': expect, 'result': result,
               'status': response.status_code if response is not None else None, 'code': code,
               'request_id': response.headers.get('x-request-id') if response is not None else None,
               'ms': round((time.monotonic() - started) * 1000) if started else None, 'note': note, **extra}
        self.rows.append(row)
        events = '>'.join(extra.get('events') or [])
        print(f"[{result}] {step} {check} ({who or '-'}) {request} → {row['status'] or '-'} {code or ''} "
              f"{events} {row['ms'] if row['ms'] is not None else '-'}ms {note}".rstrip(), flush=True)

    def fail(self, step, check, who, note):
        """요청 없이 판정한 실패 한 줄(예: 승인할 후보가 없음)."""
        self.add(step, check, who, '-', '-', 'fail', note=note)

    def skipped(self, step, check, who, request, expect, needs) -> bool:
        """앞 단계 값(needs) 중 None이 있으면 보내지 않고 건너뜀 한 줄을 남긴다."""
        if any(value is None for value in needs):
            self.add(step, check, who, request, expect, 'skip', note='앞 단계가 통과하지 않아 보내지 않음')
            return True
        return False

    def call(self, step, check, who, client, method, path, status, *, code=None, label=None, needs=(), body=None):
        """요청 하나를 보내고 한 줄을 남긴다. 기대한 상태(와 error.code)면 JSON 본문, 아니면 None."""
        # [왜] 결과 파일에는 id를 뺀 경로 모양(label)만 적어 실행끼리 비교하기 쉽게 한다. 요청을 찾을 때는 request_id를 쓴다
        request, expect = f'{method} {label or path}', f"{status} {code or ''}".strip()
        if self.skipped(step, check, who, request, expect, needs):
            return None
        started = time.monotonic()
        try:
            response = client.request(method, path, json=body)
        except httpx.HTTPError as exc:
            self.add(step, check, who, request, expect, 'fail', started=started, note=type(exc).__name__)
            return None
        data, error = parse(response)
        ok = response.status_code == status and (code is None or error.get('code') == code)
        self.add(step, check, who, request, expect, 'pass' if ok else 'fail', response, started, error.get('code'))
        if not ok and error.get('message'):
            print(f"    서버 문구: {error['message'][:200]}")  # [왜] 원인을 바로 보이게 화면에만 찍고 결과 파일에는 남기지 않는다
        return data if ok else None

    def stream(self, step, check, who, client, path, body, expect, *, label, needs=()):
        """run · 재개 SSE를 마지막 이벤트까지 읽고 한 줄을 남긴다. (run_id, 기대한 마지막 이벤트면 그 data 아니면 None)."""
        request = f'POST {label}'
        if self.skipped(step, check, who, request, expect, needs):
            return None, None
        started, events, run_id, last, data, response, note = time.monotonic(), [], None, None, None, None, ''
        try:
            with client.stream('POST', path, json=body) as response:
                if response.status_code != 200:
                    # [왜] 스트림을 열기 전 거절(429 상한 · 422 데모 질문 다름 · 503 기록 없음 등)은 보통 JSON 공통 오류다
                    response.read()
                    _, error = parse(response)
                    self.add(step, check, who, request, expect, 'fail', response, started, error.get('code'), '스트림 전 오류', events=events)
                    if error.get('message'):
                        print(f"    서버 문구: {error['message'][:200]}")
                    return None, None
                kind = None
                for line in response.iter_lines():  # frame마다 `event: 이름`과 `data: JSON` 한 줄(SPEC 4절)
                    if line.startswith('event: '):
                        kind = line[len('event: '):]
                    elif line.startswith('data: ') and kind:
                        payload = json.loads(line[len('data: '):])
                        events.append(kind)
                        if kind == 'run_started':
                            run_id = payload.get('run_id')
                        if kind in TERMINAL:
                            last, data = kind, payload
                            break
        except (httpx.HTTPError, ValueError) as exc:
            note = type(exc).__name__
        if last is None and not note:
            note = '마지막 이벤트 없이 스트림이 끝남'  # [주의] 실패 상태도 저장하지 못하면 서버는 마지막 frame 없이 끝낸다(SPEC 4절)
        error = ((data or {}).get('error') or {}) if last == 'failed' else {}  # failed frame의 error.code는 공통 오류 표와 같다
        self.add(step, check, who, request, expect, 'pass' if last == expect else 'fail', response, started, error.get('code'), note, events=events)
        if error.get('message'):
            print(f"    서버 문구: {error['message'][:200]}")
        return run_id, data if last == expect else None


def login(smoke, client, who, demo, env):
    """데모 버튼(a · b) 또는 환경변수 계정으로 한 번만 로그인한다. 통과면 본문, 아니면 None."""
    # [주의] 실패해도 다시 보내지 않는다. 같은 계정이 15분에 5번 틀리면 15분 잠긴다(SPEC 8.6)
    step = '2' if who == 'A' else '8'
    if demo:
        return smoke.call(step, f'{who} 데모 로그인', who, client, 'POST', '/api/auth/demo-login', 200, body={'account': who.lower()})
    # [주의] 본문에 비밀번호가 들어가므로 이 본문은 어디에도 기록하지 않는다(call은 본문을 남기지 않는다)
    return smoke.call(step, f'{who} 로그인', who, client, 'POST', '/api/auth/login', 200,
                      body={'email': env[f'SMOKE_{who}_EMAIL'], 'password': env[f'SMOKE_{who}_PASSWORD']})


def make_project(smoke, client, circuits, q, step):
    """데모 질문의 회로 이름과 같은 데모 회로로 프로젝트를 만든다. 프로젝트 id 또는 None."""
    # [왜] backend를 import하지 않는다(.env를 읽고, 다른 작업이 고치는 중일 수 있다). 서버가 준 데모 회로 목록의 이름으로 잇는다
    demo_id = next((c.get('id') for c in circuits or [] if c.get('name') == q['circuit']), None)
    if circuits is not None and demo_id is None:
        smoke.fail(step, f"{q['id']} 회로 찾기", 'A', f"데모 회로 목록에 '{q['circuit']}'이 없음")
    name = f"smoke {q['id']} {datetime.now(KST):%m-%d %H:%M}"  # 사람이 화면에서 점검용 프로젝트를 알아보게 붙인다
    made = smoke.call(step, f"프로젝트 만들기({q['id']})", 'A', client, 'POST', '/api/projects', 201,
                      needs=(demo_id,), body={'demo_id': demo_id, 'name': name})
    return (made or {}).get('id')


def make_thread(smoke, client, project_id, step):
    """프로젝트에 새 대화(thread)를 만든다. thread id 또는 None."""
    made = smoke.call(step, 'thread 만들기', 'A', client, 'POST', f'/api/projects/{project_id}/threads', 201,
                      label='/api/projects/{id}/threads', needs=(project_id,))
    return (made or {}).get('id')


def start_body(q) -> dict:
    """run 시작 본문(StartRun). 질문 · 조건 글은 기록과 글자까지 같아야 데모 재생이 받는다."""
    return {'question': q['question'], 'target_ref': q['target'], 'conditions': q['conditions']}


def resume_body(q, asked) -> dict:
    """재개 본문(ResumeRun). record_demo.run_question과 같은 규칙이라 데모 재생이 받는 기록 답 · 역할과 같아진다."""
    interrupt = (asked or {}).get('interrupt') or {}
    choices = interrupt.get('role_choices') or []
    body = {'answers': {k: v for k, v in q['answers'].items() if k in (interrupt.get('missing') or [])}}  # 물은 이름의 답만(비면 '모름')
    if choices:
        # [주의] 역할을 묻지 않았으면 role을 보내지 않는다. API가 422로 막고, 빈 글자는 R01~R23 형식에도 어긋난다
        body['role'] = q.get('role') if q.get('role') in choices else choices[0]
    return body


def approvable(done):
    """완료 결과의 판정 후보(results · shown) 중 사람이 승인할 수 있는 첫 후보. 없으면 None(서버 approval_snapshot과 같은 칸)."""
    judgement = (done or {}).get('judgement') or {}
    return next((c for key in ('results', 'shown') for c in judgement.get(key) or [] if c.get('verdict') in APPROVABLE), None)


def flow(smoke, questions, demo, refusal, env):
    """1~9단계를 차례로 부른다. 앞 단계 값이 없으면 뒤 단계는 건너뜀으로 남는다(8단계 격리 확인은 있는 값으로 계속)."""
    judge, refuse = questions[JUDGE_ID], questions[REFUSAL_ID]
    a = smoke.client()
    # 1. 생존 확인과 배포 대조: 경로 · 연산 수가 이 작업 트리 코드와 다르면 배포가 다른 커밋이다
    smoke.call('1', '생존 확인', None, a, 'GET', '/health', 200)
    spec = smoke.call('1', 'OpenAPI 경로 수', None, a, 'GET', '/openapi.json', 200)
    if spec is not None:
        paths = spec.get('paths') or {}
        # [왜] SPEC 4절의 "/docs에 32개"는 메서드 + 경로(연산) 수라 경로 키 수와 다르다. 둘 다 남긴다
        smoke.openapi = {'paths': len(paths), 'operations': sum(m in METHODS for item in paths.values() for m in item)}
    # 2. A 로그인과 세션 확인(SPEC 2절 1단계)
    login(smoke, a, 'A', demo, env)
    smoke.call('2', 'A 세션 확인', 'A', a, 'GET', '/api/auth/me', 200)
    # 3. 판정 질문의 데모 회로로 프로젝트를 만들고 다시 읽는다(2단계)
    circuits = smoke.call('3', '데모 회로 목록', 'A', a, 'GET', '/api/demo-circuits', 200)
    pid = make_project(smoke, a, circuits, judge, '3')
    smoke.call('3', '프로젝트 읽기', 'A', a, 'GET', f'/api/projects/{pid}', 200, label='/api/projects/{id}', needs=(pid,))
    # 4. 새 대화의 첫 질문으로 판정 질문을 보낸다. 조건 질문(requires_input)에서 멈춰야 한다(3~6단계, 사람 확인)
    tid = make_thread(smoke, a, pid, '4')
    run_id, asked = smoke.stream('4', f"run 시작({judge['id']})", 'A', a, f'/api/threads/{tid}/runs', start_body(judge),
                                 'requires_input', label='/api/threads/{id}/runs', needs=(tid,))
    # 5. 같은 run을 기록과 같은 규칙의 답 · 역할로 재개한다. 완료(completed)여야 한다
    if asked is not None:
        time.sleep(GAP_SECONDS)
    _, done = smoke.stream('5', '조건 재개', 'A', a, f'/api/runs/{run_id}/resume', resume_body(judge, asked), 'completed',
                           label='/api/runs/{id}/resume', needs=(asked,))
    # 6. 완료 판정을 사람이 승인한다. 같은 승인을 다시 보내면 409 ALREADY_APPROVED(8.4). message_id는 SSE에 없고 run 조회에 있다
    run = smoke.call('6', 'run 읽기(message_id)', 'A', a, 'GET', f'/api/runs/{run_id}', 200, label='/api/runs/{id}', needs=(done,))
    message_id = (run or {}).get('message_id')
    pick = approvable(done)
    if done is not None and pick is None:
        smoke.fail('6', '승인할 후보 고르기', 'A', '완료 결과에 동일품 · 사양 동등 · 역할상 충분 판정이 없음')
    approve = {'candidate_part': pick['part'], 'verdict': pick['verdict']} if pick else None
    approval = smoke.call('6', '승인', 'A', a, 'POST', f'/api/messages/{message_id}/approvals', 201,
                          label='/api/messages/{id}/approvals', needs=(message_id, approve), body=approve)
    smoke.call('6', '같은 승인 다시', 'A', a, 'POST', f'/api/messages/{message_id}/approvals', 409, code='ALREADY_APPROVED',
               label='/api/messages/{id}/approvals', needs=(approval,), body=approve)
    # 7. 승인한 후보로 가격 없는 견적을 저장하고 프로젝트 견적 목록에서 다시 읽는다(7단계)
    aid = (approval or {}).get('id')
    quote = smoke.call('7', '견적 저장', 'A', a, 'POST', f'/api/approvals/{aid}/quotes', 201,
                       label='/api/approvals/{id}/quotes', needs=(aid,), body={'quantity': 1})
    quotes = smoke.call('7', '견적 목록', 'A', a, 'GET', f'/api/projects/{pid}/quotes', 200, label='/api/projects/{id}/quotes', needs=(quote,))
    if quotes is not None and quote.get('id') not in {item.get('id') for item in quotes}:
        smoke.fail('7', '저장한 견적이 목록에 있음', 'A', '저장한 견적이 프로젝트 견적 목록에 없음')
    # 8. B는 A의 자료를 404로만 본다(남의 자료도 404, SPEC 4절). 먼저 GET만 보내고, 승인 · 견적의 POST는 아래 8-2에서만 보낸다
    b = smoke.client()
    signed = login(smoke, b, 'B', demo, env)
    for what, path, label, need in (('프로젝트', f'/api/projects/{pid}', '/api/projects/{A}', pid),
                                    ('thread 목록', f'/api/projects/{pid}/threads', '/api/projects/{A}/threads', pid),
                                    ('run', f'/api/runs/{run_id}', '/api/runs/{A}', run_id)):
        smoke.call('8', f'B가 A의 {what} 읽기', 'B', b, 'GET', path, 404, code='NOT_FOUND', label=label, needs=(signed, need))
    listed = smoke.call('8', 'B 프로젝트 목록', 'B', b, 'GET', '/api/projects', 200, needs=(signed, pid))
    if listed is not None and pid in {item.get('id') for item in listed}:
        smoke.fail('8', 'B 목록에 A 프로젝트 없음', 'B', 'A의 프로젝트가 B의 목록에 보임')
    # 8-2. 승인 · 견적 · 승인 사례도 B에게 404로 숨겨지는지 본다. B의 POST 두 개는 A가 이미 승인 · 견적을 만들어 둔 뒤에만 보내며
    #      DB가 막는 것은 메시지당 승인 1개(approvals.message_id UNIQUE)뿐이라 B의 승인 POST는 격리가 깨져도 409로 끝나지만,
    #      견적은 승인당 여러 건이 허용돼(quotes에 UNIQUE 없음) 격리가 깨지면 B의 견적 POST가 A의 승인에 견적을 실제로 더한다(201, 실패로 남음).
    #      그래서 현재 서버가 격리를 지킬 때(404)만 안전한 점검이다. DELETE는 보내지 않는다
    smoke.call('8', 'B가 A의 견적 목록 읽기', 'B', b, 'GET', f'/api/projects/{pid}/quotes', 404, code='NOT_FOUND',
               label='/api/projects/{A}/quotes', needs=(signed, quote))
    smoke.call('8', 'B가 A의 메시지 승인', 'B', b, 'POST', f'/api/messages/{message_id}/approvals', 404, code='NOT_FOUND',
               label='/api/messages/{A}/approvals', needs=(signed, approval, message_id, approve), body=approve)
    smoke.call('8', 'B가 A의 승인으로 견적 저장', 'B', b, 'POST', f'/api/approvals/{aid}/quotes', 404, code='NOT_FOUND',
               label='/api/approvals/{A}/quotes', needs=(signed, quote, aid), body={'quantity': 1})
    mine = smoke.call('8', 'A 승인 사례 목록', 'A', a, 'GET', '/api/approved-cases', 200, needs=(quote,))
    theirs = smoke.call('8', 'B 승인 사례 목록', 'B', b, 'GET', '/api/approved-cases', 200, needs=(signed, quote))
    # [왜] A 목록에 A의 사례가 보여야 "B 목록에 없다"가 의미가 있다(둘 다 비어 있으면 겹침이 없어 보일 뿐이다)
    if mine is not None and aid not in {item.get('approval_id') for item in mine}:
        smoke.fail('8', 'A 목록에 A 승인 사례 있음', 'A', 'A의 승인 사례가 A의 목록에 없어 격리를 비교할 수 없음')
    if mine is not None and theirs is not None and {item.get('id') for item in mine} & {item.get('id') for item in theirs}:
        smoke.fail('8', 'B 목록에 A 승인 사례 없음', 'B', 'A의 승인 사례가 B의 목록에 보임')
    # 9. (선택) 범위 밖 질문은 거절(refused)로 끝난다. 거절은 오류가 아니라 분석 결과다(SPEC 4절)
    if refusal:
        tid2 = make_thread(smoke, a, make_project(smoke, a, circuits, refuse, '9'), '9')
        if tid2 is not None:
            time.sleep(GAP_SECONDS)
        smoke.stream('9', f"run 시작({refuse['id']})", 'A', a, f'/api/threads/{tid2}/runs', start_body(refuse), 'refused',
                     label='/api/threads/{id}/runs', needs=(tid2,))


def commit():
    """이 작업 트리 HEAD의 짧은 커밋(배포된 코드의 커밋이 아니다). git이 없으면 None."""
    try:
        return subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def main(argv=None, *, transport=None, env=None, out_dir=RESULTS) -> int:
    """한 번 돌리고 결과 파일을 쓴다. 모두 통과 0, 통과 못 한 단계가 있으면 1, 요청 전에 멈추면 2."""
    parser = argparse.ArgumentParser(description='SojaFit 정상 사용자 흐름 HTTP 점검')
    parser.add_argument('--base-url', required=True, help='예: http://localhost:8000 또는 배포 주소(서버의 AUTH_ORIGIN과 같아야 함)')
    parser.add_argument('--demo', action='store_true', help='데모 버튼 로그인(A · B). 키 없는 compose용')
    parser.add_argument('--refusal', action='store_true', help=f'9단계: 범위 밖 질문({REFUSAL_ID})이 거절로 끝나는지도 본다')
    parser.add_argument('--confirm-live', action='store_true', help='데모가 아닐 때 실제 LLM을 부르는 4 · 5(· 9)단계를 허락한다')
    args = parser.parse_args(argv)
    if urlsplit(args.base_url).scheme not in ('http', 'https'):
        parser.error('--base-url은 http:// 또는 https://로 시작해야 합니다')
    env = os.environ if env is None else env
    questions = demo_questions()
    if not args.demo:
        if missing := [key for key in ACCOUNT_VARS if not env.get(key)]:
            print(f"멈춤: 환경변수 {', '.join(missing)}가 없습니다. 비밀번호는 명령줄 인자로 받지 않습니다", file=sys.stderr)
            return 2
        if env['SMOKE_A_EMAIL'].strip().lower() == env['SMOKE_B_EMAIL'].strip().lower():
            print('멈춤: A와 B가 같은 계정이면 격리(8단계)를 볼 수 없습니다', file=sys.stderr)
            return 2
        used = [questions[JUDGE_ID]] + ([questions[REFUSAL_ID]] if args.refusal else [])
        low, high = sum(q['calls'][0] for q in used), sum(q['calls'][1] for q in used)
        print(f"실제 계정 모드: 4 · 5단계{'와 9단계' if args.refusal else ''}가 실제 LLM을 부릅니다"
              f"(어림 {low}~{high}회 [추정, record_demo.py의 calls], 서버의 실행당 상한 ANALYSIS_MAX_CALLS · ANALYSIS_MAX_USD가 걸림).", flush=True)
        if not args.confirm_live:
            print('요청을 보내기 전에 멈췄습니다. 부르려면 --confirm-live를 붙이세요.')
            return 2
    started_at, started = datetime.now(KST), time.monotonic()
    smoke = Smoke(args.base_url, transport)
    flow(smoke, questions, args.demo, args.refusal, env)
    counts = Counter(row['result'] for row in smoke.rows)
    host = urlsplit(smoke.base).netloc
    result = {'base_host': host, 'mode': 'demo' if args.demo else 'accounts', 'commit': commit(),
              'started_at': started_at.isoformat(timespec='seconds'), 'total_ms': round((time.monotonic() - started) * 1000),
              'openapi': smoke.openapi, 'counts': dict(counts), 'steps': smoke.rows}
    out_dir.mkdir(parents=True, exist_ok=True)
    # [왜] 같은 날 로컬 · 배포를 여러 번 돌려 비교하므로 날짜 뒤에 시각을 붙여 덮어쓰지 않는다. ':'(포트)는 파일 이름에서 뺀다
    path = out_dir / f"smoke_{re.sub(r'[^A-Za-z0-9.-]+', '-', host)}_{started_at:%Y-%m-%d_%H%M%S}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f"통과 {counts['pass']} · 실패 {counts['fail']} · 건너뜀 {counts['skip']}. 결과: {path}")
    return 0 if counts['pass'] == len(smoke.rows) else 1


if __name__ == '__main__':
    sys.exit(main())
