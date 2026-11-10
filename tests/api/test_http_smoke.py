"""HTTP 점검 스크립트(scripts/smoke/http_smoke.py)의 오프라인 시험. 가짜 서버(httpx.MockTransport)로 1~9단계를 끝까지 돌린다.

- 역할: 모두 통과하는 흐름(두 번째 승인의 409 `ALREADY_APPROVED`를 통과로 셈, 9단계 거절 포함), 조건 질문(`requires_input`)이 오지 않거나
  run이 스트림 전에 오류(지금 키 없는 데모의 기록 없음 503)면 그 단계 실패 · 5~7단계 건너뜀 · 8단계 격리 확인은 계속 · 종료 코드 1,
  결과 파일 · 화면 출력에 비밀번호 · 쿠키 값 · 이메일 · 답 글이 없는지, 데모가 아닌데 `--confirm-live`가 없으면 요청 없이 멈추는지,
  재개 값 규칙(record_demo.run_question과 같음)과 데모 질문의 회로가 데모 카탈로그에 있는지 본다.
- 하지 않는 일: 실제 서버 · DB · LLM 호출. 가짜 서버는 쿠키 · Origin · 소유권 · 재개 값 · 중복 승인만 흉내 내고 분석 결과는 손으로 쓴 SSE다.
- 출처: scripts/smoke/SMOKE.md, SPEC 4절 계약(SSE 이벤트 · 공통 오류), backend/api/quotes.py(같은 메시지 두 번 승인 409).
"""
import importlib.util
import json
import re
import secrets
from pathlib import Path

import httpx
import pytest

from backend.projects.repository import DEMOS

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('http_smoke', ROOT / 'scripts/smoke/http_smoke.py')
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
BASE = 'http://smoke.test'
Q = smoke.demo_questions()
ANSWER = 'answer-text-' + secrets.token_hex(4)  # 결과 파일에 들어가면 안 되는 답 글 표식
DONE = {'status': 'completed', 'answer': ANSWER, 'judgement': {'kind': 'judge', 'results': [
    {'part': '1N4007RLG', 'verdict': 'NOT_VERIFIED'}, {'part': '1N4007G', 'verdict': 'ROLE_SUFFICIENT'}]}}


def fake_server(run_mode='interrupt', accounts=None, leaky=False):
    """쿠키 · Origin · 소유권을 지키는 가짜 API. run_mode: interrupt(정상) · completed(조건 질문 없이 끝남) · unavailable(스트림 전 503).

    leaky=True면 승인 · 견적 · 승인 사례의 소유권 검사만 빼 격리가 깨진 서버를 흉내 낸다(8단계 확인이 실제로 실패하는지 보려고)."""
    tokens = {'A': 'tok-a-' + secrets.token_hex(8), 'B': 'tok-b-' + secrets.token_hex(8)}
    state = {'projects': {}, 'runs': {}, 'approved': set(), 'quotes': [], 'cases': [], 'approval_owner': {}, 'calls': [], 'tokens': tokens}

    def reply(status, data=None, code=None, cookie=None):
        headers = {'x-request-id': f"rid-{len(state['calls'])}"}
        if cookie:
            headers['set-cookie'] = f'sojafit_session={cookie}; Path=/; HttpOnly; SameSite=lax'
        body = {'error': {'code': code, 'message': '가짜 오류', 'request_id': headers['x-request-id']}} if code else data
        return httpx.Response(status, json=body, headers=headers)

    def sse(run_id, last):
        frames = [('run_started', {'run_id': run_id, 'request_id': 'r'}), ('status', {'status': 'running'}), last]
        text = ''.join(f'event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n' for kind, data in frames)
        return httpx.Response(200, text=text, headers={'content-type': 'text/event-stream', 'x-request-id': f"rid-{len(state['calls'])}"})

    def handler(request):
        method, path = request.method, request.url.path
        state['calls'].append(f'{method} {path}')
        body = json.loads(request.content) if request.content else {}
        if method != 'GET' and request.headers.get('origin') != BASE:  # 서버 check_origin과 같다(끝 '/' 없이 같아야 함)
            return reply(403, code='ORIGIN_MISMATCH')
        if path == '/health':
            return reply(200, {'status': 'ok'})
        if path == '/openapi.json':
            return reply(200, {'paths': {'/health': {'get': {}}, '/api/projects': {'get': {}, 'post': {}, 'parameters': []}}})
        if path == '/api/auth/demo-login':
            return reply(200, {'user_id': 1}, cookie=tokens[body['account'].upper()])
        if path == '/api/auth/login':
            who = next((w for w in 'AB' if body == {'email': accounts[f'SMOKE_{w}_EMAIL'], 'password': accounts[f'SMOKE_{w}_PASSWORD']}), None)
            return reply(200, {'user_id': 1}, cookie=tokens[who]) if who else reply(401, code='UNAUTHORIZED')
        user = next((w for w, tok in tokens.items() if request.headers.get('cookie') == f'sojafit_session={tok}'), None)
        if user is None:
            return reply(401, code='UNAUTHORIZED')
        if path == '/api/auth/me':
            return reply(200, {'user_id': 1, 'role': 'user'})
        if path == '/api/demo-circuits':
            return reply(200, [{'id': k, 'name': v} for k, v in DEMOS.items()])
        if path == '/api/projects':
            if method == 'GET':
                return reply(200, [{'id': p} for p, owner in state['projects'].items() if owner == user])
            state['projects'][len(state['projects']) + 1] = user
            return reply(201, {'id': len(state['projects']), 'name': body['name']})
        if m := re.fullmatch(r'/api/projects/(\d+)(/threads|/quotes)?', path):
            if state['projects'].get(int(m[1])) != user:
                return reply(404, code='NOT_FOUND')
            if m[2] == '/threads':
                return reply(201, {'id': f'th{m[1]}', 'project_id': int(m[1])}) if method == 'POST' else reply(200, [])
            return reply(200, state['quotes'] if m[2] else {'id': int(m[1])})
        if m := re.fullmatch(r'/api/threads/th(\d+)/runs', path):
            if run_mode == 'unavailable':
                return reply(503, code='UNAVAILABLE')
            run_id = f'run{m[1]}'
            state['runs'][run_id] = user
            if body['question'] == Q[smoke.REFUSAL_ID]['question']:
                return sse(run_id, ('refused', {'status': 'refused', 'answer': ANSWER, 'refusal': ANSWER}))
            if run_mode == 'completed':
                return sse(run_id, ('completed', DONE))
            return sse(run_id, ('requires_input', {'status': 'requires_input', 'interrupt': {'missing': ['v_drop_allowed'], 'role_choices': ['R01', 'R02']}}))
        if m := re.fullmatch(r'/api/runs/(run\d+)(/resume)?', path):
            if state['runs'].get(m[1]) != user:
                return reply(404, code='NOT_FOUND')
            if not m[2]:
                return reply(200, {'id': m[1], 'thread_id': 'th1', 'message_id': 7, 'result': {}})
            # 서버처럼 물은 이름 밖의 답 · 후보 밖의 역할은 422
            if not set(body['answers']) <= {'v_drop_allowed'} or body.get('role') not in ('R01', 'R02'):
                return reply(422, code='VALIDATION_ERROR')
            return sse(m[1], ('completed', DONE))
        if path == '/api/messages/7/approvals':
            if body != {'candidate_part': '1N4007G', 'verdict': 'ROLE_SUFFICIENT'}:
                return reply(422, code='VALIDATION_ERROR')
            if not leaky and state['runs'].get('run1') != user:  # 메시지 7은 run1의 것: 남의 메시지는 없는 것처럼 404
                return reply(404, code='NOT_FOUND')
            if 7 in state['approved']:
                return reply(409, code='ALREADY_APPROVED')  # 서버 DB의 메시지당 승인 1개 제약
            state['approved'].add(7)
            state['approval_owner'][3] = user
            state['cases'].append({'id': 9, 'approval_id': 3, 'candidate_part': body['candidate_part'], 'verdict': body['verdict'],
                                   'created_at': '2026-11-10T00:00:00+09:00', 'owner': user})
            return reply(201, {'id': 3, 'message_id': 7})
        if path == '/api/approvals/3/quotes':
            if not leaky and state['approval_owner'].get(3) != user:
                return reply(404, code='NOT_FOUND')
            if state['quotes']:
                return reply(409, code='ALREADY_APPROVED')  # 서버 DB의 승인당 견적 1개 제약
            state['quotes'].append({'id': 5, 'approval_id': 3, 'quantity': body['quantity']})
            return reply(201, state['quotes'][-1])
        if path == '/api/approved-cases':
            return reply(200, [{k: v for k, v in c.items() if k != 'owner'} for c in state['cases'] if leaky or c['owner'] == user])
        return reply(404, code='NOT_FOUND')

    return handler, state


def run(tmp_path, monkeypatch, argv, handler, env=None):
    """스크립트를 가짜 서버로 한 번 돌려 (종료 코드, 결과 dict 또는 None, 결과 파일 글)을 돌려준다."""
    monkeypatch.setattr(smoke, 'GAP_SECONDS', 0)
    code = smoke.main(argv, transport=httpx.MockTransport(handler), env=env or {}, out_dir=tmp_path)
    files = list(tmp_path.glob('smoke_*.json'))
    text = files[0].read_text(encoding='utf-8') if files else ''
    return code, (json.loads(text) if text else None), text


def test_demo_flow_all_pass(tmp_path, monkeypatch):
    """1~9단계가 모두 통과하고, 두 번째 승인의 409 ALREADY_APPROVED도 통과로 센다."""
    handler, _ = fake_server()
    code, result, _ = run(tmp_path, monkeypatch, ['--base-url', BASE + '/', '--demo', '--refusal'], handler)
    rows = result['steps']
    assert code == 0
    assert [r for r in rows if r['result'] != 'pass'] == []
    assert {r['step'] for r in rows} == set('123456789')
    again = next(r for r in rows if r['check'] == '같은 승인 다시')
    assert (again['status'], again['code']) == (409, 'ALREADY_APPROVED')
    assert next(r for r in rows if r['step'] == '4' and 'runs' in r['request'])['events'] == ['run_started', 'status', 'requires_input']
    assert next(r for r in rows if r['step'] == '9' and 'runs' in r['request'])['events'][-1] == 'refused'
    isolation = {r['check']: (r['status'], r['code'], r['result']) for r in rows if r['step'] == '8'}
    for check in ('B가 A의 견적 목록 읽기', 'B가 A의 메시지 승인', 'B가 A의 승인으로 견적 저장'):
        assert isolation[check] == (404, 'NOT_FOUND', 'pass'), check
    assert isolation['A 승인 사례 목록'][2] == isolation['B 승인 사례 목록'][2] == 'pass'
    assert result['openapi'] == {'paths': 2, 'operations': 3}  # 'parameters'는 연산이 아니다
    assert (result['base_host'], result['mode'], result['counts']) == ('smoke.test', 'demo', {'pass': len(rows)})
    assert all(r['request_id'] and r['ms'] is not None for r in rows)
    assert not [r['request'] for r in rows if re.search(r'/(\d+|th\d+|run\d+)(/|$)', r['request'])]  # id 대신 경로 모양만 남김


@pytest.mark.parametrize('run_mode, status, code, events', [
    ('completed', 200, None, ['run_started', 'status', 'completed']),  # 조건 질문 없이 끝남
    ('unavailable', 503, 'UNAVAILABLE', []),  # 지금 키 없는 데모(기록 파일 없음): 스트림을 열기 전 503
])
def test_run_without_requires_input_fails(tmp_path, monkeypatch, run_mode, status, code, events):
    """4단계에 requires_input이 없으면 실패, 5~7단계는 건너뛰고, 8단계 격리 확인은 있는 값으로 계속한다(종료 코드 1)."""
    handler, _ = fake_server(run_mode)
    exit_code, result, _ = run(tmp_path, monkeypatch, ['--base-url', BASE, '--demo'], handler)
    rows = result['steps']
    start = next(r for r in rows if r['step'] == '4' and 'runs' in r['request'])
    assert exit_code == 1
    assert (start['result'], start['status'], start['code'], start['events']) == ('fail', status, code, events)
    assert {r['result'] for r in rows if r['step'] in ('5', '6', '7')} == {'skip'}
    b_reads = {r['check']: r['result'] for r in rows if r['step'] == '8'}
    assert b_reads['B가 A의 프로젝트 읽기'] == b_reads['B가 A의 thread 목록 읽기'] == b_reads['B 프로젝트 목록'] == 'pass'
    assert b_reads['B가 A의 run 읽기'] == ('pass' if run_mode == 'completed' else 'skip')  # run id가 없으면 보낼 수 없다


def test_result_file_has_no_secrets(tmp_path, monkeypatch, capsys):
    """실제 계정 모드에서도 결과 파일 · 화면에 비밀번호 · 쿠키 값 · 이메일 · 답 글이 없다."""
    env = {'SMOKE_A_EMAIL': 'alice@example.test', 'SMOKE_A_PASSWORD': 'pw-' + secrets.token_hex(12),
           'SMOKE_B_EMAIL': 'bob@example.test', 'SMOKE_B_PASSWORD': 'pw-' + secrets.token_hex(12)}
    handler, state = fake_server(accounts=env)
    code, result, text = run(tmp_path, monkeypatch, ['--base-url', BASE, '--confirm-live', '--refusal'], handler, env)
    printed = ''.join(capsys.readouterr())
    assert code == 0 and result['mode'] == 'accounts'
    assert {r['account'] for r in result['steps']} == {None, 'A', 'B'}
    for secret in (*env.values(), *state['tokens'].values(), ANSWER, 'sojafit_session'):
        assert secret not in text
    for secret in (env['SMOKE_A_PASSWORD'], env['SMOKE_B_PASSWORD'], *state['tokens'].values()):
        assert secret not in printed


def test_live_mode_stops_before_any_request(tmp_path, monkeypatch, capsys):
    """데모가 아닌데 --confirm-live가 없거나 계정 환경변수가 모자라면 요청 없이 2로 멈춘다."""
    env = {'SMOKE_A_EMAIL': 'alice@example.test', 'SMOKE_A_PASSWORD': 'pw-a', 'SMOKE_B_EMAIL': 'bob@example.test', 'SMOKE_B_PASSWORD': 'pw-b'}
    handler, state = fake_server(accounts=env)
    assert run(tmp_path, monkeypatch, ['--base-url', BASE], handler, env)[:2] == (2, None)
    assert run(tmp_path, monkeypatch, ['--base-url', BASE, '--confirm-live'], handler, {'SMOKE_A_EMAIL': 'a@example.test'})[:2] == (2, None)
    out = capsys.readouterr()
    assert state['calls'] == []
    assert '--confirm-live' in out.out and 'SMOKE_A_PASSWORD' in out.err


def test_resume_body_follows_record_demo_rule():
    """물은 이름의 답만 보내고, 역할은 질문의 role이 후보에 있으면 그것 · 아니면 첫 후보 · 묻지 않았으면 보내지 않는다."""
    q = {'answers': {'v_in_max': '12', 'i_max': '0.5'}, 'role': 'R05'}
    assert smoke.resume_body(q, {'interrupt': {'missing': ['v_in_max'], 'role_choices': ['R01', 'R05']}}) == {'answers': {'v_in_max': '12'}, 'role': 'R05'}
    assert smoke.resume_body(q, {'interrupt': {'missing': [], 'role_choices': ['R01', 'R02']}}) == {'answers': {}, 'role': 'R01'}
    assert smoke.resume_body(q, {'interrupt': {'missing': ['i_max']}}) == {'answers': {'i_max': '0.5'}}


def test_demo_questions_are_in_the_catalog():
    """스크립트는 데모 질문의 회로 이름으로 서버의 데모 회로 id를 찾는다. 카탈로그 이름이 바뀌면 여기서 먼저 깨진다."""
    assert {Q[smoke.JUDGE_ID]['circuit'], Q[smoke.REFUSAL_ID]['circuit']} <= set(DEMOS.values())
    assert Q[smoke.JUDGE_ID]['interrupt'] is True  # 4단계는 조건 질문에서 멈추는 질문이어야 한다


def test_broken_isolation_on_approvals_quotes_and_cases_is_caught(tmp_path, monkeypatch):
    """승인 · 견적 · 승인 사례의 소유권 검사가 빠진 서버에서는 8단계의 해당 확인이 실패하고 종료 코드 1이다. 그래도 A의 자료는 늘지 않는다."""
    handler, state = fake_server(leaky=True)
    code, result, _ = run(tmp_path, monkeypatch, ['--base-url', BASE, '--demo'], handler)
    rows = {r['check']: r for r in result['steps'] if r['step'] == '8'}
    assert code == 1
    assert rows['B가 A의 메시지 승인']['result'] == 'fail' and rows['B가 A의 메시지 승인']['status'] == 409  # 새로 만들지 못하고 중복으로 막힘
    assert rows['B가 A의 승인으로 견적 저장']['result'] == 'fail' and rows['B가 A의 승인으로 견적 저장']['status'] == 409
    assert rows['B 목록에 A 승인 사례 없음']['result'] == 'fail'
    assert len(state['quotes']) == 1 and len(state['cases']) == 1 and state['approved'] == {7}  # B의 POST가 A의 자료를 바꾸지 않음


def test_isolation_checks_are_skipped_without_approval_or_quote(tmp_path, monkeypatch):
    """A가 승인 · 견적을 못 만든 흐름(4단계 실패)에서는 B의 POST를 보내지 않고 건너뛴다."""
    handler, state = fake_server('unavailable')
    code, result, _ = run(tmp_path, monkeypatch, ['--base-url', BASE, '--demo'], handler)
    rows = {r['check']: r['result'] for r in result['steps'] if r['step'] == '8'}
    assert code == 1
    assert rows['B가 A의 메시지 승인'] == rows['B가 A의 승인으로 견적 저장'] == rows['B가 A의 견적 목록 읽기'] == 'skip'
    assert not [call for call in state['calls'] if call.startswith('POST /api/messages') or call.startswith('POST /api/approvals')]

