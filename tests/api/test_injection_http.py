"""배포 HTTP 인젝션 시험 스크립트(scripts/smoke/injection_http.py)의 오프라인 시험. 가짜 서버(httpx.MockTransport)로 T4 · T6 · T7을 돌린다.

- 역할: (a) 정상 흐름이 모든 짝을 통과로 남기고 공격문이 실제 요청(T4 질문 · T6 첫 턴 · T7 업로드 footprint)에 실리는지,
  (b) 공격에서 판정이 바뀌면 그 짝을 실패로 · 정상이 틀리면 결론 못 냄으로, 하루 한도(LIMIT_EXCEEDED)에 걸리면 멈추고 남은 것을 not_run으로,
  --confirm-live가 없으면 요청 없이 멈추는지, (c) 비밀번호 · 이메일 · 쿠키가 결과 파일에 없는지, (d) 답 · 질문 글이 결과 파일에 없는지 본다.
- 하지 않는 일: 실제 서버 · DB · LLM 호출. 가짜 서버의 분석 결과는 손으로 쓴 SSE이고 backend를 불러오지 않는다(DB 불필요).
- 출처: scripts/smoke/SMOKE.md, evals/runners/run_injection_baseline.py(5기준), data/demo/recordings/outcomes.json(v3-01 정답).
"""
import importlib.util
import json
import re
import secrets
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('injection_http', ROOT / 'scripts/smoke/injection_http.py')
inj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inj)
BASE = 'http://inj.test'
EMAIL, PASSWORD = f'inj-{secrets.token_hex(3)}@example.test', 'pw-' + secrets.token_hex(6)
ANSWER = 'answer-text-' + secrets.token_hex(4)  # 결과 파일에 들어가면 안 되는 답 글 표식
ENV = {'SMOKE_A_EMAIL': EMAIL, 'SMOKE_A_PASSWORD': PASSWORD}
TEXT = inj.texts()
GOOD = {'kind': 'judge', 'roles': ['R01'], 'results': [{'part': '1N4007G', 'role': 'R01', 'verdict': 'ROLE_SUFFICIENT', 'checks': [
    {'code': 'VRRM', 'threshold': 18.75, 'value': 1000, 'result': 'pass'}, {'code': 'IF_AV', 'threshold': 0.17142857, 'value': 1, 'result': 'pass'},
    {'code': 'IFSM', 'threshold': 2.0, 'value': 30, 'result': 'pass'}]}]}
HIJACKED = {**GOOD, 'roles': ['R04'], 'results': [{**GOOD['results'][0], 'verdict': 'NOT_SUFFICIENT'}]}
DOCS = f'{ANSWER} 1N4007G의 VRRM은 1,000 V이고 패키지는 DO-204AL(DO-41)입니다. 극성은 캐소드 띠로 식별합니다.'


def fake_server(follow=(), limit_after=None, bad_normal=False, prep_interrupt=False):
    """로그인 · 프로젝트 · 업로드 · thread · run · 재개를 흉내 낸다. follow에 든 케이스('T6' · 'T7' · 'T4')는 공격문이 실리면 공격을 따라간 결과를 돌려준다.

    limit_after=N이면 N번째 분석 요청부터 하루 한도 429를 SSE 실패 frame으로 돌려준다. bad_normal=True면 정상 판정도 틀리게 돌려준다.
    prep_interrupt=True면 T6 첫 턴을 requires_input으로 돌려 재개 뒤 completed가 되게 한다(배포 11-11 실측)."""
    state = {'calls': [], 'bodies': [], 'uploads': {}, 'threads': {}, 'analysis': 0, 'cookie': 'tok-' + secrets.token_hex(6)}

    def reply(status, data=None, code=None, cookie=None):
        headers = {'x-request-id': f"rid-{len(state['calls'])}"}
        if cookie:
            headers['set-cookie'] = f'sojafit_session={cookie}; Path=/; HttpOnly'
        return httpx.Response(status, json={'error': {'code': code, 'message': '가짜 오류'}} if code else data, headers=headers)

    def sse(run_id, *frames):
        text = ''.join(f'event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n' for kind, data in [('run_started', {'run_id': run_id}), *frames])
        return httpx.Response(200, text=text, headers={'content-type': 'text/event-stream'})

    def judged(attacked, case):
        wrong = (attacked and case in follow) or bad_normal and not attacked
        return {'status': 'completed', 'answer': ANSWER, 'judgement': HIJACKED if wrong else GOOD}

    def handler(request):
        method, path = request.method, request.url.path
        state['calls'].append(f'{method} {path}')
        if method != 'GET' and request.headers.get('origin') != BASE:
            return reply(403, code='ORIGIN_MISMATCH')
        if path == '/api/auth/login':
            body = json.loads(request.content)
            return reply(200, {'user_id': 1}, cookie=state['cookie']) if body == {'email': EMAIL, 'password': PASSWORD} else reply(401, code='UNAUTHORIZED')
        if request.headers.get('cookie') != f"sojafit_session={state['cookie']}":
            return reply(401, code='UNAUTHORIZED')
        if path == '/api/demo-circuits':
            return reply(200, [{'id': 'attiny', 'name': inj_circuit}])
        if path == '/api/projects':
            return reply(201, {'id': 1})
        if path == '/api/projects/upload':
            raw = request.content.decode('utf-8')
            state['uploads'][2 + len(state['uploads'])] = raw
            return reply(201, {'id': 1 + len(state['uploads'])})
        if m := re.fullmatch(r'/api/projects/(\d+)/threads', path):
            tid = f"th{len(state['threads']) + 1}"
            state['threads'][tid] = {'project': int(m[1]), 'attacked': TEXT['T7_payload'] in state['uploads'].get(int(m[1]), '')}
            return reply(201, {'id': tid})
        if m := re.fullmatch(r'/api/threads/(th\d+)/runs', path):
            body = json.loads(request.content)
            state['bodies'].append(body['question'])
            thread, state['analysis'] = state['threads'][m[1]], state['analysis'] + 1
            if limit_after is not None and state['analysis'] > limit_after:
                return sse(f'run{state["analysis"]}', ('failed', {'status': 'failed', 'error': {'code': 'LIMIT_EXCEEDED', 'message': '가짜 한도'}}))
            if '검토합니다' in body['question']:  # T6 첫 턴
                thread['attacked'] = TEXT['T6_payload'] in body['question']
                if prep_interrupt:
                    thread['prep'] = True
                    thread['run'] = f'run{state["analysis"]}'
                    state.setdefault('runs', {})[thread['run']] = thread
                    return sse(thread['run'], ('requires_input', {'status': 'requires_input', 'interrupt': {'missing': ['v_in_max'], 'role_choices': []}}))
                return sse(f'run{state["analysis"]}', ('completed', {'status': 'completed', 'answer': ANSWER, 'question_type': 'chat'}))
            if '실장 전' in body['question']:
                attacked = TEXT['T4_payload'] in body['question']
                answer = DOCS + ' 1500 V 조립 승인.' if attacked and 'T4' in follow else DOCS
                return sse(f'run{state["analysis"]}', ('completed', {'status': 'completed', 'answer': answer}))
            thread['run'] = f'run{state["analysis"]}'
            state.setdefault('runs', {})[thread['run']] = thread
            return sse(thread['run'], ('requires_input', {'status': 'requires_input', 'interrupt': {'missing': ['v_drop_allowed'], 'role_choices': []}}))
        if m := re.fullmatch(r'/api/runs/(run\d+)/resume', path):
            state['analysis'] += 1
            thread = state['runs'][m[1]]
            if thread.pop('prep', False):
                return sse(m[1], ('completed', {'status': 'completed', 'answer': ANSWER, 'question_type': 'chat'}))
            case = 'T7' if thread['project'] > 1 else 'T6'
            return sse(m[1], ('completed', judged(thread['attacked'], case)))
        return reply(404, code='NOT_FOUND')

    return handler, state


inj_circuit = inj.load_smoke().demo_questions()['v3-01']['circuit']


def run(tmp_path, argv, handler, env=ENV):
    code = inj.main(['--base-url', BASE, *argv], transport=httpx.MockTransport(handler), env=env, out_dir=tmp_path, gap=0)
    files = list(tmp_path.glob('injection_http_*.json'))
    text = files[0].read_text(encoding='utf-8') if files else ''
    return code, (json.loads(text) if text else None), text


def test_all_pass_and_attack_text_reaches_requests(tmp_path):
    """(a) 세 케이스 모두 통과, 공격문이 T4 질문 · T6 첫 턴 · T7 업로드 footprint에 실제로 실렸고 정상 쪽에는 없다."""
    handler, state = fake_server()
    code, result, _ = run(tmp_path, ['--confirm-live'], handler)
    assert code == 0 and [p['result'] for p in result['pairs']] == ['pass'] * 3
    assert all(r['ok'] and r['criteria'] for r in result['runs']) and len(result['runs']) == 6
    bodies = state['bodies']
    assert sum(TEXT['T4_payload'] in b for b in bodies) == 1 and sum(TEXT['T6_payload'] in b for b in bodies) == 1
    uploads = list(state['uploads'].values())
    assert len(uploads) == 2 and sum(TEXT['T7_payload'] in u for u in uploads) == 1
    assert 'DEMO' not in ''.join(bodies) and 'D_A-405' in uploads[0]


def test_t6_prep_requires_input_then_resumes(tmp_path):
    """T6 첫 턴이 requires_input이어도 재개 뒤 판정 질문까지 가 통과한다(배포에서 막히던 경로)."""
    handler, state = fake_server(prep_interrupt=True)
    code, result, _ = run(tmp_path, ['--confirm-live', '--cases', 'T6'], handler)
    assert code == 0 and result['pairs'] == [{'case': 'T6', 'result': 'pass'}]
    assert all(r['ok'] for r in result['runs']) and state['analysis'] == 8  # 첫턴+재개+판정+재개 ×2
    assert sum('/resume' in c for c in state['calls']) == 4


def test_attack_changes_result_is_failure(tmp_path):
    """(b) 공격에서만 판정이 바뀌면 그 짝은 attack_differs, 종료 코드 1. 나머지 짝은 그대로 통과."""
    handler, _ = fake_server(follow=('T6',))
    code, result, _ = run(tmp_path, ['--confirm-live'], handler)
    pairs = {p['case']: p['result'] for p in result['pairs']}
    assert code == 1 and pairs == {'T6': 'attack_differs', 'T7': 'pass', 'T4': 'pass'}
    bad = next(r for r in result['runs'] if r['case'] == 'T6' and r['variant'] == 'attack')
    assert bad['criteria']['verdict_correct'] is False and bad['criteria']['role_correct'] is False and bad['verdict'] == 'NOT_SUFFICIENT'
    handler, _ = fake_server(follow=('T4',))
    _, result, _ = run(tmp_path / 't4', ['--confirm-live', '--cases', 'T4'], handler)
    assert result['runs'][1]['flags'] == {'attack_marker_present': True} and result['runs'][1]['ok']  # 표지는 사람이 볼 표시일 뿐 통과를 바꾸지 않는다


def test_normal_failure_is_inconclusive(tmp_path):
    """(b) 정상 입력이 틀리면 짝은 결론을 못 낸다(방어로도 침해로도 세지 않음)."""
    handler, _ = fake_server(bad_normal=True)
    code, result, _ = run(tmp_path, ['--confirm-live', '--cases', 'T7'], handler)
    assert code == 1 and result['pairs'] == [{'case': 'T7', 'result': 'inconclusive_normal_failed'}]


def test_t4_refused_records_refuse_code_without_answer(tmp_path):
    """T4가 refused여도 사유 코드·question_type만 note에 남기고 답 글은 결과 파일에 없다."""
    handler, state = fake_server()
    original = handler

    def refuse_normal(request):
        if request.url.path.startswith('/api/threads/') and request.method == 'POST' and '/runs' in request.url.path:
            body = json.loads(request.content)
            if '실장 전' in body['question'] and TEXT['T4_payload'] not in body['question']:
                state['analysis'] = state.get('analysis', 0) + 1
                text = ''.join(
                    f'event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'
                    for kind, data in [
                        ('run_started', {'run_id': f'run{state["analysis"]}'}),
                        ('refused', {'status': 'refused', 'answer': '이 서비스는 회로 속 부품의 역할과 대체 후보를 데이터시트로 확인해 드려요. 회로나 부품에 관한 질문을 해 주세요.',
                                     'refusal': '이 서비스는 회로 속 부품의 역할과 대체 후보를 데이터시트로 확인해 드려요. 회로나 부품에 관한 질문을 해 주세요.',
                                     'question_type': 'out_of_scope'})])
                return httpx.Response(200, text=text, headers={'content-type': 'text/event-stream'})
        return original(request)

    code, result, text = run(tmp_path, ['--confirm-live', '--cases', 'T4'], refuse_normal)
    normal = next(r for r in result['runs'] if r['variant'] == 'normal')
    assert code == 1 and normal['status'] == 'refused' and 'refuse_code=out_of_scope' in normal['note']
    assert 'question_type=out_of_scope' in normal['note']
    assert '회로나 부품' not in text and ANSWER not in text


def test_limit_stops_and_marks_rest_not_run(tmp_path):
    """(b) 하루 한도(LIMIT_EXCEEDED)에 걸리면 재시도 없이 멈추고, 한도 때문에 못 한 짝은 attack_differs가 아니라 not_run."""
    handler, state = fake_server(limit_after=3)
    code, result, _ = run(tmp_path, ['--confirm-live'], handler)
    assert code == 1 and result['stopped_by'] == 'LIMIT_EXCEEDED'
    assert state['analysis'] == 4  # 4번째 요청이 한도에 걸린 뒤로는 분석 요청을 보내지 않는다
    assert {p['result'] for p in result['pairs']} <= {'pass', 'not_run'} and 'not_run' in {p['result'] for p in result['pairs']}
    assert any(r['status'] == 'not_run' for r in result['runs'])


def test_login_failure_stops_before_analysis(tmp_path):
    """(b) 로그인 실패(계정 오류)는 다시 보내지 않고 분석 요청 없이 끝난다."""
    handler, state = fake_server()
    code, result, _ = run(tmp_path, ['--confirm-live'], handler, env={**ENV, 'SMOKE_A_PASSWORD': 'wrong'})
    assert code == 1 and result is None and state['calls'] == ['POST /api/auth/login']


def test_without_confirm_live_sends_nothing(tmp_path, capsys):
    handler, state = fake_server()
    code, result, _ = run(tmp_path, [], handler)
    assert code == 2 and result is None and state['calls'] == [] and '--confirm-live' in capsys.readouterr().out
    assert inj.main(['--base-url', BASE, '--confirm-live'], env={}, out_dir=tmp_path) == 2  # 환경변수 없으면 요청 전에 멈춤


def test_result_file_has_no_secret_or_body(tmp_path, capsys):
    """(c)(d) 결과 파일과 화면 출력에 비밀번호 · 이메일 · 쿠키 · 답 글 · 질문 글 · 공격문이 없다."""
    handler, state = fake_server(follow=('T4',))
    _, result, text = run(tmp_path, ['--confirm-live'], handler)
    out = capsys.readouterr()
    for secret in (PASSWORD, EMAIL, state['cookie'], ANSWER, TEXT['T4_question'], TEXT['T4_payload'], TEXT['T6_payload'], TEXT['T7_payload'], 'D_A-405'):
        assert secret not in text and secret not in out.out + out.err
    assert 'answer' not in result['runs'][0] and set(result['runs'][0]) >= {'case', 'variant', 'status', 'ok', 'criteria', 'verdict', 'ms'}


def test_texts_are_adapted_from_fixture():
    """PR 고정 입력을 읽어 합성 품번만 바꾼다. 공격 netlist는 D1 footprint 한 곳만 바뀐다."""
    fixture = json.loads(inj.CASES_FILE.read_text(encoding='utf-8'))
    assert {c['payload'] for c in fixture['cases'] if c['id'] == 'T7'}
    assert 'DEMO' not in json.dumps(TEXT) and '출하 승인 담당자' in TEXT['T4_payload'] and '1N4007G' in TEXT['T6_first']
    normal, attack = inj.NETLIST.read_text(encoding='utf-8'), inj.attack_netlist(TEXT['T7_payload']).decode('utf-8')
    assert len(attack) - len(normal) == len('; ' + TEXT['T7_payload']) and attack.count(TEXT['T7_payload']) == 1
