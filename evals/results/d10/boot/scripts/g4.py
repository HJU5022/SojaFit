"""D10 re-measurement (boot2): keyless demo answers + restart-resume + account isolation on the running keyless compose stack.
Code under test: branch jeongun-2 @ ad8612e (NOT main). Baseline measurement: b5f050d.
Runs INSIDE the dind container, cwd = clone root. Every check is independent (exceptions are recorded, not fatal).
Never records cookies/tokens/e-mails. Outputs: /tmp/g4_restart_isolation.json, /tmp/demo_answers.json, /tmp/checkpoint_rows.txt."""
import json, subprocess, time, re, uuid
from datetime import datetime, timezone, timedelta
import httpx
ROOT = '/work/proj3-b'; BASE = 'http://localhost:8000'; KST = timezone(timedelta(hours=9))
OUTC = {q['id']: q for q in json.load(open(f'{ROOT}/data/demo/recordings/outcomes.json'))['questions']}
CHECKS = []; CTX = {}; REQLOG = []; DEMO = []; GAP = 3.2
def ts(): return datetime.now(KST).isoformat(timespec='milliseconds')
def check(name, request, expected, observed, ok, old14=None, na=False, note=None):
    CHECKS.append({'n': len(CHECKS) + 1, 'time_kst': ts(), 'name': name, 'request': request, 'expected': expected, 'observed': observed,
                   'result': 'not_applicable' if na else ('pass' if ok else 'fail'), 'pass': None if na else bool(ok), 'old14': old14, 'note': note})
    print(ts(), 'N/A ' if na else ('PASS' if ok else 'FAIL'), name, '|', str(observed)[:300], flush=True)
def safe(name, request, expected, fn, old14=None):
    try: ok, obs = fn(); check(name, request, expected, obs, ok, old14=old14)
    except Exception as e: check(name, request, expected, f'EXCEPTION {type(e).__name__}: {str(e)[:200]}', False, old14=old14)
def sh(*a):
    r = subprocess.run(a, capture_output=True, text=True, cwd=ROOT); return r.stdout.strip() + (('\n' + r.stderr.strip()) if r.returncode else '')
def psql(sql): return sh('docker', 'compose', 'exec', '-T', 'db', 'psql', '-U', 'app', '-d', 'app', '-At', '-F', '|', '-c', sql)
def code(r):
    try: return (r.json().get('error') or {}).get('code')
    except Exception: return None
def sm(r): return f'{r.status_code}' + (f' {code(r)}' if r.status_code >= 400 and code(r) else '')

class C:
    """httpx client that logs every request (method, path, status, ms) without headers/cookies/bodies."""
    def __init__(self, who): self.who = who; self.c = httpx.Client(base_url=BASE, headers={'Origin': BASE}, timeout=httpx.Timeout(10, read=180))
    def request(self, m, path, **kw):
        t = time.monotonic(); r = self.c.request(m, path, **kw)
        REQLOG.append({'time_kst': ts(), 'account': self.who, 'method': m, 'path': path, 'status': r.status_code, 'error_code': code(r) if r.status_code >= 400 else None, 'ms': round((time.monotonic() - t) * 1000)}); return r
    def get(self, p, **kw): return self.request('GET', p, **kw)
    def post(self, p, **kw): return self.request('POST', p, **kw)
    def patch(self, p, **kw): return self.request('PATCH', p, **kw)
    def sse(self, path, body):
        """POST an SSE endpoint, read to the end. returns (http_status, [(event, data, t_ms)], error_code)"""
        t = time.monotonic(); evs = []
        with self.c.stream('POST', path, json=body) as r:
            if r.status_code != 200:
                r.read(); REQLOG.append({'time_kst': ts(), 'account': self.who, 'method': 'POST', 'path': path, 'status': r.status_code, 'error_code': code(r), 'ms': round((time.monotonic() - t) * 1000)}); return r.status_code, [], code(r)
            kind = None
            for line in r.iter_lines():
                if line.startswith('event: '): kind = line[7:]
                elif line.startswith('data: ') and kind: evs.append((kind, json.loads(line[6:]), round((time.monotonic() - t) * 1000)))
        REQLOG.append({'time_kst': ts(), 'account': self.who, 'method': 'POST', 'path': path, 'status': 200, 'sse_events': [e[0] for e in evs], 'ms': round((time.monotonic() - t) * 1000)})
        return 200, evs, None

def login(who):
    c = C(who.upper()); r = c.post('/api/auth/demo-login', json={'account': who}); me = c.get('/api/auth/me').json(); return c, r.status_code, me.get('user_id'), me.get('role')
def cstate(svc): return sh('docker', 'inspect', '-f', '{{.Id}}|{{.State.Pid}}|{{.State.StartedAt}}|{{.RestartCount}}', sh('docker', 'compose', 'ps', '-q', svc))
def rows(tid=None):
    out = {}
    for t in ('checkpoints', 'checkpoint_writes', 'checkpoint_blobs', 'store'):
        out[f'sojafit_agent.{t} total'] = psql(f'SELECT count(*) FROM sojafit_agent.{t}')
    if tid:
        out['checkpoints for thread'] = psql(f"SELECT count(*) FROM sojafit_agent.checkpoints WHERE thread_id='{tid}'")
        out['checkpoint_writes for thread (count, channels)'] = psql(f"SELECT count(*)||' '||coalesce(string_agg(distinct channel, ','),'') FROM sojafit_agent.checkpoint_writes WHERE thread_id='{tid}'")
        out['checkpoint_blobs for thread'] = psql(f"SELECT count(*) FROM sojafit_agent.checkpoint_blobs WHERE thread_id='{tid}'")
        out['public.runs status for thread'] = psql(f"SELECT status FROM public.runs WHERE thread_id='{tid}'")
    return out
def final(evs): return evs[-1] if evs else (None, None, None)
def verdicts(d):
    j = (d or {}).get('judgement') or {}   # `shown` repeats `results` (first run of this script double-counted, discarded)
    # same rule as evals/runners/score_answer.py judgement_parts (what record_demo.py stores): kind=find -> `shown` (else first 3 unverified), otherwise `results`
    parts = (j.get('shown') or (j.get('unverified') or [])[:3]) if j.get('kind') == 'find' else (j.get('results') or [])
    return [(c.get('part'), c.get('verdict')) for c in parts]
def refusal_of(d):
    r = (d or {}).get('refusal'); return (r if isinstance(r, str) else (r or {}).get('code') or (r or {}).get('reason') or json.dumps(r, ensure_ascii=False)) if r else ''
def vf_row(answer):
    return next((l for l in (answer or '').splitlines() if l.startswith('| VF')), None)

# ------------------------------------------------------------------ logins
A, st, uidA, role = login('a'); check('A demo login', 'POST /api/auth/demo-login {account:a}; GET /api/auth/me', '200, role user', f'{st}, user_id={uidA}, role={role}', st == 200 and role == 'user', old14=1)
B, st, uidB, role = login('b'); check('B demo login (second keyless demo account)', 'POST /api/auth/demo-login {account:b}; GET /api/auth/me', '200, role user', f'{st}, user_id={uidB}, role={role}', st == 200 and role == 'user', old14=9)
check('A and B are different users', 'GET /api/auth/me both', 'user_id differs', f'A={uidA} B={uidB}', uidA != uidB, old14=10)
DQ = A.get('/api/demo-questions').json(); DQ_B = B.get('/api/demo-questions').json(); DQM = {q['id']: q for q in DQ}
check('GET /api/demo-questions lists the 10 recorded questions', 'GET /api/demo-questions (A, B)', '10 ids = outcomes.json ids', f'A={[q["id"] for q in DQ]}, B_count={len(DQ_B)}', {q['id'] for q in DQ} == set(OUTC) and len(DQ) == 10)
CIRC = A.get('/api/demo-circuits').json(); check('GET /api/demo-circuits (demo mode only)', 'GET /api/demo-circuits', '200, list', f'{len(CIRC)} circuits: {[c["name"] for c in CIRC]}', len(CIRC) >= 6)

def new_project(c, q, tag='g4'):
    pid = c.post('/api/projects', json={'demo_id': q['demo_id'], 'name': f'{tag} {q["id"]} {uuid.uuid4().hex[:4]}'}); assert pid.status_code == 201, pid.text[:200]
    pid = pid.json()['id']; tid = c.post(f'/api/projects/{pid}/threads'); assert tid.status_code == 201; return pid, tid.json()['id']
def start_body(q): return {'question': q['question'], 'target_ref': q['target'], 'conditions': q['conditions']}
def resume_body(q):
    r = q['resume']; b = {'answers': r['answers']}
    if r.get('role'): b['role'] = r['role']          # same as the UI: role: recordedResume.role || undefined
    return b
def run_question(c, q, resume=True, tag='g4'):
    """start (new thread, first question) and, if the question has an interrupt, resume with the recorded answer. returns dict."""
    pid, tid = new_project(c, q, tag); time.sleep(GAP)
    t0 = ts(); s, evs, ec = c.sse(f'/api/threads/{tid}/runs', start_body(q)); k, d, _ = final(evs)
    rid = next((e[1].get('run_id') for e in evs if e[0] == 'run_started'), None)
    rec = {'id': q['id'], 'project_id': pid, 'thread_id': tid, 'run_id': rid, 'start_http': s, 'start_error_code': ec, 'started_at_kst': t0, 'start_events': [e[0] for e in evs], 'start_final': k, 'interrupt': (d or {}).get('interrupt'), 'start_data': d}
    if k == 'requires_input' and resume:
        time.sleep(GAP); body = resume_body(q); t1 = ts(); s2, evs2, ec2 = c.sse(f'/api/runs/{rid}/resume', body); k2, d2, _ = final(evs2)
        rec.update(resume_body=body, resume_started_at_kst=t1, resume_http=s2, resume_error_code=ec2, resume_events=[e[0] for e in evs2], final=k2, final_data=d2)
    else: rec.update(final=k, final_data=d)
    return rec
def summarize(rec):
    q = OUTC[rec['id']]; d = rec['final_data'] or {}; v = verdicts(d); rf = refusal_of(d)
    exp_v = [tuple(x) for x in q['verdicts']]; exp_i = (q['interrupt'] or {}).get('missing')
    err = (d.get('error') or {}).get('code') if rec['final'] == 'failed' else None
    exp_final = 'refused' if q['refusal'] else 'completed'
    return {'id': rec['id'], 'question_type': q['question_type'], 'project_id': rec['project_id'], 'thread_id': rec['thread_id'], 'run_id': rec['run_id'],
            'start_events': rec['start_events'], 'interrupt_missing': (rec['interrupt'] or {}).get('missing'), 'expected_interrupt_missing': exp_i, 'resume_body': rec.get('resume_body'),
            'resume_events': rec.get('resume_events'), 'final_status': rec['final'], 'expected_final_status': exp_final, 'verdicts': v, 'expected_verdicts': exp_v, 'refusal_text_in_public_result': rf, 'expected_refusal_code_in_outcomes_json': q['refusal'], 'note_refusal': 'public result carries the refusal message text, not the code; match = status refused + answer text identical to the recording',
            'answer_equals_recording': (d.get('answer') == q['answer']), 'error_code': err,
            'matches_outcomes_json': rec['final'] == exp_final and [tuple(x) for x in v] == exp_v and (rec['interrupt'] or {}).get('missing') == exp_i and (not q['refusal'] or d.get('answer') == q['answer'])}

# ------------------------------------------------------------------ A. demo answers (account A, all 10 recorded questions)
PHASE_A = {}
for qid in ['demo-rating', 'demo-notsuff', 'v3-30', 'v3-36', 'demo-edition', 'demo-leak', 'v3-03', 'demo-find', 'v3-01']:
    try:
        time.sleep(GAP); rec = run_question(A, DQM[qid]); s = summarize(rec); DEMO.append(s); PHASE_A[qid] = rec
        check(f'demo answer {qid} ({s["question_type"]})', f'create project from recorded circuit; POST thread run (exact recorded question/conditions){"; resume with recorded answer" if rec.get("resume_body") is not None else ""}',
              f'final={s["expected_final_status"]}, verdicts={s["expected_verdicts"]}, refusal_code={s["expected_refusal_code_in_outcomes_json"]!r}', f'final={s["final_status"]}, verdicts={s["verdicts"]}, refusal_text={s["refusal_text_in_public_result"][:40]!r}, interrupt={s["interrupt_missing"]}, error={s["error_code"]}, answer==recording:{s["answer_equals_recording"]}', s['matches_outcomes_json'])
    except Exception as e: check(f'demo answer {qid}', 'run_question', 'matches outcomes.json', f'EXCEPTION {type(e).__name__}: {str(e)[:200]}', False)

# ------------------------------------------------------------------ B. interrupt questions kept waiting across the restart (A: demo-ask, v3-01)
WAIT = {}
for qid in ('demo-ask', 'v3-01'):
    time.sleep(GAP); rec = run_question(A, DQM[qid], resume=False, tag='g4wait'); WAIT[qid] = rec; it = rec['interrupt'] or {}
    check(f'A: {qid} stops waiting for input on the real graph', f'POST /api/threads/{{T}}/runs ({qid})', 'last SSE event requires_input; interrupt.missing = ' + str(OUTC[qid]['interrupt']['missing']),
          f'events={rec["start_events"]}, final={rec["final"]}, error={rec["start_error_code"]}, missing={it.get("missing")}, question={it.get("question")!r}', rec['final'] == 'requires_input' and it.get('missing') == OUTC[qid]['interrupt']['missing'], old14=2)
    g = A.get(f'/api/runs/{rec["run_id"]}'); res = g.json()['result'] if g.status_code == 200 else {}
    rec['get_run_before'] = {'http': g.status_code, 'status': res.get('status'), 'stage': res.get('stage'), 'interrupt': res.get('interrupt')}
    check(f'A: {qid} run stored as waiting (GET /api/runs)', 'GET /api/runs/{R}', '200, status requires_input, interrupt payload present', f'{g.status_code}, status={res.get("status")}, interrupt={res.get("interrupt")}', g.status_code == 200 and res.get('status') == 'requires_input' and bool(res.get('interrupt')))
    rec['rows_before'] = rows(rec['thread_id']); print('ROWS BEFORE', qid, json.dumps(rec['rows_before'], ensure_ascii=False), flush=True)
    check(f'Postgres checkpoint rows for {qid} thread before restart', 'psql counts sojafit_agent.checkpoints/_writes/_blobs for thread_id', '>=1 checkpoint row', json.dumps(rec['rows_before'], ensure_ascii=False), int(rec['rows_before']['checkpoints for thread'] or 0) >= 1)
TA = WAIT['demo-ask']; TV = WAIT['v3-01']

# ------------------------------------------------------------------ facts (memory)
FACT = {'affiliation': 'G4Team-' + uuid.uuid4().hex[:4], 'job_role': 'design', 'mounting_preference': 'smd'}
def f_save(): r = A.patch('/api/me/memory', json=FACT); return r.status_code == 200 and len(r.json()) == 3, f'{r.status_code}, kinds={[f["kind"] for f in r.json()] if r.status_code == 200 else None}'
safe('A saves user facts (3 slots)', 'PATCH /api/me/memory', '200, 3 facts', f_save, old14=6)
def f_q(): r = A.get('/api/me/memory', params={'q': 'which package type does this person prefer'}); return r.status_code == 200 and len(r.json()) == 3, f'{r.status_code}, {[f["kind"] for f in r.json()]} (no embedding key: unranked list)'
safe('A searches facts with reworded query', 'GET /api/me/memory?q=...', '200, 3 slots', f_q, old14=7)
def f_422(): r = A.patch('/api/me/memory', json={'user_id': uidB, 'affiliation': 'x'}); return r.status_code == 422, sm(r)
safe('request body with another user id rejected', 'PATCH /api/me/memory {user_id:<B>, ...}', '422', f_422, old14=8)
def f_bmem(): r = B.get('/api/me/memory'); return r.status_code == 200 and not r.json(), f'{r.status_code}, count={len(r.json())}, A_affiliation_visible={FACT["affiliation"] in json.dumps(r.json(), ensure_ascii=False)}'
safe('B does not see A facts (pre-restart)', 'GET /api/me/memory as B', '200, []', f_bmem, old14=14)

# B's own recorded question (after A stored facts) and A's own (with facts present): both must equal the recording
PRE = {}
for who, c in (('B', B), ('A', A)):
    time.sleep(GAP); rec = run_question(c, DQM['demo-rating'], tag='g4facts'); s = summarize(rec); s['account'] = who; s['profile_hints'] = (rec['final_data'] or {}).get('profile_hints'); s['phase'] = 'pre-restart, after A stored facts'; DEMO.append(s); PRE[who] = rec
    check(f'{who} own recorded question demo-rating runs to completion (A facts stored)', 'create project, run demo-rating', 'completed, same answer as recording, B profile_hints empty', f'final={s["final_status"]}, answer==recording:{s["answer_equals_recording"]}, profile_hints={s["profile_hints"]}, error={s["error_code"]}',
          s['matches_outcomes_json'] and s['answer_equals_recording'] and (who == 'A' or not s['profile_hints']))

# ------------------------------------------------------------------ approval / quote / approved-case (old checks 5 and 12)
# NOTE: DEMO docs claim approval is not possible in replay; the first run showed POST approvals -> 201, so it is exercised for real here.
def first_msg():
    for qid in ('v3-03', 'demo-notsuff', 'v3-01', 'demo-find'):
        r = PHASE_A.get(qid)
        if r and r['final'] == 'completed':
            g = A.get(f'/api/runs/{r["run_id"]}').json(); return qid, g.get('message_id'), g, r
    return None, None, None, None
qid, mid, g, arec = first_msg(); APPR = {}
if mid:
    cand = next((c for c in ((g['result'].get('judgement') or {}).get('results') or []) if c.get('verdict') in ('IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT')), None)
    body = {'candidate_part': cand['part'], 'verdict': cand['verdict']}
    r1 = A.post(f'/api/messages/{mid}/approvals', json=body); r2 = A.post(f'/api/messages/{mid}/approvals', json=body)
    n = psql(f'SELECT count(*) FROM public.approvals WHERE message_id={mid}'); aid = r1.json().get('id') if r1.status_code == 201 else None; APPR.update(message_id=mid, approval_id=aid, qid=qid)
    check('A approves the same message twice: 201 then 409, one DB row', f'POST /api/messages/{{M}}/approvals x2 ({qid}, {cand["verdict"]}); psql count(*) public.approvals', '201, 409 ALREADY_APPROVED, 1 row', f'{r1.status_code}, {sm(r2)}, db_rows={n}', r1.status_code == 201 and r2.status_code == 409 and n == '1', old14=5)
    q1 = A.post(f'/api/approvals/{aid}/quotes', json={'quantity': 1}) if aid else None
    check('A saves a quote on the approval', 'POST /api/approvals/{AP}/quotes', '201', sm(q1) if q1 is not None else 'no approval id', q1 is not None and q1.status_code == 201)
    rb = B.post(f'/api/messages/{mid}/approvals', json=body); rq = B.post(f'/api/approvals/{aid}/quotes', json={'quantity': 1}); rl = B.get(f'/api/projects/{arec["project_id"]}/quotes')
    ca, cb = A.get('/api/approved-cases').json(), B.get('/api/approved-cases').json()
    check('B -> A approval / quote / quote list: 404; approved-cases: A has the case, B has none', 'B: POST approvals, POST quotes, GET project quotes; GET /api/approved-cases both', '404, 404, 404; A>=1 case containing approval id, B 0', f'{sm(rb)}, {sm(rq)}, {sm(rl)}; A_cases={len(ca)} (has A approval: {aid in {c.get("approval_id") for c in ca}}), B_cases={len(cb)}',
          rb.status_code == rq.status_code == rl.status_code == 404 and aid in {c.get('approval_id') for c in ca} and not cb, old14=12)
    CTX['approval_db_rows_before_restart'] = psql('SELECT count(*) FROM public.approvals') + ' approvals, ' + psql('SELECT count(*) FROM public.quotes') + ' quotes'

# ------------------------------------------------------------------ isolation probes
SAC_P, SAC_T = new_project(A, DQM['demo-rating'], 'g4sacrificial')   # throwaway objects for the DELETE probes (A's real objects are never the DELETE target)
def probes(c, own, label):
    """own = dict(pid, tid, rid, sac_pid, sac_tid). Read/write probes on the real objects, DELETEs on the sacrificial ones."""
    p, t, r = own['pid'], own['tid'], own['rid']
    items = [('GET project', 'GET', f'/api/projects/{p}', None), ('PATCH project', 'PATCH', f'/api/projects/{p}', {'name': 'hijack'}), ('GET project threads', 'GET', f'/api/projects/{p}/threads', None),
             ('POST thread in project', 'POST', f'/api/projects/{p}/threads', None), ('GET thread', 'GET', f'/api/threads/{t}', None), ('POST run in thread', 'POST', f'/api/threads/{t}/runs', start_body(DQM['demo-ask'])),
             ('GET run', 'GET', f'/api/runs/{r}', None), ('RESUME run', 'POST', f'/api/runs/{r}/resume', {'answers': {}}), ('RECOVER run', 'POST', f'/api/runs/{r}/recover', None),
             ('GET project quotes', 'GET', f'/api/projects/{p}/quotes', None),
             ('DELETE thread (sacrificial)', 'DELETE', f'/api/threads/{own["sac_tid"]}', None), ('DELETE project (sacrificial)', 'DELETE', f'/api/projects/{own["sac_pid"]}', None)]
    res = []
    for lab, m, path, body in items:
        if 'RESUME' in lab or 'POST run' in lab: time.sleep(GAP)
        x = c.request(m, path, **({'json': body} if body is not None else {})); res.append(f'{lab}:{x.status_code}{"/" + code(x) if code(x) else ""}')
    return res
OWN_A = dict(pid=TA['project_id'], tid=TA['thread_id'], rid=TA['run_id'], sac_pid=SAC_P, sac_tid=SAC_T)
def f_b_probe(): res = probes(B, OWN_A, 'B->A'); return all(':404/NOT_FOUND' in x for x in res), json.dumps(res, ensure_ascii=False)
safe('B -> A objects (pre-restart): GET/PATCH/POST/DELETE/resume/recover all 404 NOT_FOUND', 'B vs A project, thread, run (waiting demo-ask run), sacrificial delete targets', 'all 404 (not 403/200)', f_b_probe, old14=11)
def f_blist():
    ps = {p['id'] for p in B.get('/api/projects').json()}; th = B.get(f'/api/projects/{TA["project_id"]}/threads'); ac = B.get('/api/approved-cases').json()
    return TA['project_id'] not in ps and th.status_code == 404 and not ac, f'A demo-ask project in B list={TA["project_id"] in ps}, A threads as B={th.status_code}, B approved-cases={len(ac)}'
safe('A objects absent from B lists (pre-restart)', 'GET /api/projects, /api/approved-cases as B', 'A project absent', f_blist, old14=13)
def f_a_intact():
    p = A.get(f'/api/projects/{TA["project_id"]}'); t = A.get(f'/api/threads/{TA["thread_id"]}'); r = A.get(f'/api/runs/{TA["run_id"]}'); s = A.get(f'/api/projects/{SAC_P}')
    return p.status_code == t.status_code == r.status_code == s.status_code == 200 and r.json()['result']['status'] == 'requires_input', f'project={p.status_code} thread={t.status_code} run={r.status_code}/{r.json()["result"]["status"]} sacrificial_project={s.status_code}'
safe('A objects untouched after B probes (incl. DELETE/PATCH)', 'GET as A', '200s, run still requires_input', f_a_intact)
# B has its own waiting run too (used for the reverse direction and for the post-restart check)
time.sleep(GAP); BW = run_question(B, DQM['demo-notsuff'], resume=False, tag='g4B'); BW['sac'] = new_project(B, DQM['demo-rating'], 'g4Bsacrificial')
check('B own interrupt run waits for input (demo-notsuff)', 'B: POST run demo-notsuff', 'requires_input', f'events={BW["start_events"]}, final={BW["final"]}, missing={(BW["interrupt"] or {}).get("missing")}', BW['final'] == 'requires_input')
BW['rows_before'] = rows(BW['thread_id'])
OWN_B = dict(pid=BW['project_id'], tid=BW['thread_id'], rid=BW['run_id'], sac_pid=BW['sac'][0], sac_tid=BW['sac'][1])
def f_rev(): res = probes(A, OWN_B, 'A->B'); return all(':404/NOT_FOUND' in x for x in res), json.dumps(res, ensure_ascii=False)
safe('A -> B objects (reverse direction, pre-restart): all 404 NOT_FOUND', 'A vs B project, thread, run, sacrificial delete targets', 'all 404', f_rev, old14=11)

# ------------------------------------------------------------------ restart
snap = {'demo-ask': rows(TA['thread_id']), 'v3-01': rows(TV['thread_id']), 'B demo-notsuff': rows(BW['thread_id'])}; CTX['rows_just_before_restart'] = snap; print('ROWS JUST BEFORE RESTART', json.dumps(snap, ensure_ascii=False), flush=True)
CTX['checkpoint_rows_before'] = {'demo-ask': TA['rows_before'], 'v3-01': TV['rows_before'], 'B demo-notsuff': BW['rows_before']}
st0, dbs0 = cstate('api'), cstate('db'); t0 = time.time(); t0_kst = ts(); out = sh('docker', 'compose', 'restart', 'api')
for _ in range(240):
    try:
        if httpx.get(BASE + '/health', timeout=2).status_code == 200: break
    except Exception: pass
    time.sleep(0.5)
st1, dbs1 = cstate('api'), cstate('db'); a, b = st0.split('|'), st1.split('|'); CTX.update(restart_issued_kst=t0_kst, restart_before_api=st0, restart_after_api=st1, restart_before_db=dbs0, restart_after_db=dbs1, restart_seconds_until_health=round(time.time() - t0, 1))
check('api server process restarted (db untouched)', 'docker compose restart api; docker inspect Id|Pid|StartedAt|RestartCount for api and db', 'api: same container id, new StartedAt and Pid; db: identical before/after',
      f'api before pid={a[1]} started={a[2]}; after pid={b[1]} started={b[2]}; health again after {CTX["restart_seconds_until_health"]}s; db unchanged={dbs0 == dbs1}', a[0] == b[0] and a[2] != b[2] and a[1] != b[1] and dbs0 == dbs1)
after = {'demo-ask': rows(TA['thread_id']), 'v3-01': rows(TV['thread_id']), 'B demo-notsuff': rows(BW['thread_id'])}; CTX['rows_just_after_restart'] = after
safe('Postgres checkpoint rows unchanged by the restart', 'psql counts after restart', 'equal to just before', lambda: (after == snap, json.dumps(after, ensure_ascii=False)))
def f_me(): r = A.get('/api/auth/me'); return r.status_code == 200 and r.json()['user_id'] == uidA, f'{r.status_code}, user_id={r.json().get("user_id")} (same session cookie, no re-login)'
safe('A session cookie still valid after restart (no re-login)', 'GET /api/auth/me with the pre-restart client', '200 same user', f_me)
def f_run2():
    g = A.get(f'/api/runs/{TA["run_id"]}'); res = g.json()['result'] if g.status_code == 200 else {}
    return g.status_code == 200 and res.get('status') == 'requires_input' and res.get('interrupt') == TA['get_run_before']['interrupt'] == TA['interrupt'], f'{g.status_code}, status={res.get("status")}, interrupt_equal_to_before={res.get("interrupt") == TA["interrupt"]}, interrupt={res.get("interrupt")}'
safe('A: demo-ask run still waiting after restart with the same interrupt payload', 'GET /api/runs/{R}', 'requires_input, interrupt == pre-restart payload', f_run2, old14=3)
def f_run2b():
    g = A.get(f'/api/runs/{TV["run_id"]}'); res = g.json()['result'] if g.status_code == 200 else {}
    return g.status_code == 200 and res.get('status') == 'requires_input' and res.get('interrupt') == TV['interrupt'], f'{g.status_code}, status={res.get("status")}, interrupt_equal_to_before={res.get("interrupt") == TV["interrupt"]}'
safe('A: v3-01 run still waiting after restart with the same interrupt payload', 'GET /api/runs/{R}', 'requires_input, same payload', f_run2b)
def f_list():
    row = next((t for t in A.get(f'/api/projects/{TA["project_id"]}/threads').json() if t['id'] == TA['thread_id']), {}); return row.get('latest_run_id') == TA['run_id'], f'latest_run_id==R:{row.get("latest_run_id") == TA["run_id"]}, status={row.get("status")}'
safe('A: thread list after restart', 'GET /api/projects/{P}/threads', 'latest_run_id=R', f_list)
def f_mem2(): r = A.get('/api/me/memory'); v = {f['kind']: f['value'] for f in r.json()}; return v == FACT, f'{r.status_code}, kinds={sorted(v)}, values_equal_saved={v == FACT}'
safe('A user facts survive restart', 'GET /api/me/memory as A', '3 slots equal saved', f_mem2)
def f_bmem2(): r = B.get('/api/me/memory'); return r.status_code == 200 and not r.json(), f'{r.status_code}, count={len(r.json())}, A_affiliation_visible={FACT["affiliation"] in json.dumps(r.json(), ensure_ascii=False)}'
safe('B still sees no A facts after restart', 'GET /api/me/memory as B', '[]', f_bmem2, old14=14)

CTX['approval_db_rows_after_restart'] = psql('SELECT count(*) FROM public.approvals') + ' approvals, ' + psql('SELECT count(*) FROM public.quotes') + ' quotes'
if APPR.get('approval_id'):
    r = A.post(f'/api/messages/{APPR["message_id"]}/approvals', json=body); rb = B.post(f'/api/messages/{APPR["message_id"]}/approvals', json=body)
    check('approval survives restart (409 again for A) and B -> A approval still 404', 'POST /api/messages/{M}/approvals as A and as B after restart', 'A 409 ALREADY_APPROVED, B 404', f'{sm(r)}, {sm(rb)}; rows {CTX["approval_db_rows_before_restart"]} -> {CTX["approval_db_rows_after_restart"]}', r.status_code == 409 and rb.status_code == 404)
# resume after restart, the way the UI does ("기록한 답으로 계속하기")
RES = {}
for nm, rec, qid in (('demo-ask', TA, 'demo-ask'), ('v3-01', TV, 'v3-01')):
    time.sleep(GAP); body = resume_body(DQM[qid]); t1 = ts(); s2, evs2, ec2 = A.sse(f'/api/runs/{rec["run_id"]}/resume', body); k2, d2, _ = final(evs2); d2 = d2 or {}
    ans = d2.get('answer') or ''; v = verdicts(d2); row = vf_row(ans); exp = OUTC[qid]
    RES[nm] = {'resume_issued_kst': t1, 'body': body, 'http': s2, 'error_code': ec2, 'events': [e[0] for e in evs2], 'final': k2, 'verdicts': v, 'vf_row': row, 'answer_equals_recording': ans == exp['answer'], 'failed_error': d2.get('error')}
    ok = s2 == 200 and k2 == 'completed' and [tuple(x) for x in v] == [tuple(x) for x in exp['verdicts']] and ans == exp['answer'] and (nm != 'demo-ask' or (bool(row) and '통과' in row))
    check(f'A: {nm} resumed AFTER restart -> completed with the recorded verdict', f'POST /api/runs/{{R}}/resume {json.dumps(body, ensure_ascii=False)}', f'completed, verdict {exp["verdicts"]}, VF row passes, answer == recording',
          f'http={s2}, events={[e[0] for e in evs2]}, final={k2}, verdicts={v}, VF row={row!r}, answer==recording:{RES[nm]["answer_equals_recording"]}, error={ec2 or d2.get("error")}', ok, old14=4)
    RES[nm]['rows_after_resume'] = rows(rec['thread_id']); g = A.get(f'/api/runs/{rec["run_id"]}'); RES[nm]['get_run_after'] = {'http': g.status_code, 'status': (g.json().get('result') or {}).get('status')}
CTX['resume_after_restart'] = RES
r2 = A.post(f'/api/runs/{TA["run_id"]}/resume', json=resume_body(DQM['demo-ask']))
check('A: resuming the already-completed run again is refused (observed)', 'POST /api/runs/{R}/resume (second time)', 'non-200 JSON error, no new run', sm(r2), r2.status_code >= 400)

# B's waiting run (created before restart) resumed after restart + own isolation
time.sleep(GAP); s2, evs2, ec2 = B.sse(f'/api/runs/{BW["run_id"]}/resume', resume_body(DQM['demo-notsuff'])); k2, d2, _ = final(evs2); d2 = d2 or {}; ex = OUTC['demo-notsuff']
check('B: own waiting demo-notsuff run resumed after restart -> completed NOT_SUFFICIENT, answer == recording', 'POST /api/runs/{RB}/resume as B', f'completed, {ex["verdicts"]}', f'http={s2}, final={k2}, verdicts={verdicts(d2)}, answer==recording:{d2.get("answer") == ex["answer"]}, profile_hints={d2.get("profile_hints")}',
      s2 == 200 and k2 == 'completed' and [tuple(x) for x in verdicts(d2)] == [tuple(x) for x in ex['verdicts']] and d2.get('answer') == ex['answer'] and not d2.get('profile_hints'))
OWN_A2 = dict(OWN_A); OWN_A2.update(sac_pid=new_project(A, DQM['demo-rating'], 'g4sacrificial2')[0]); OWN_A2['sac_tid'] = A.get(f'/api/projects/{OWN_A2["sac_pid"]}/threads').json()[0]['id']
OWN_B2 = dict(OWN_B); np_ = new_project(B, DQM['demo-rating'], 'g4Bsacrificial2'); OWN_B2.update(sac_pid=np_[0], sac_tid=np_[1])
def f_b_probe2(): res = probes(B, dict(OWN_A2, rid=TV['run_id']), 'B->A'); return all(':404/NOT_FOUND' in x for x in res), json.dumps(res, ensure_ascii=False)
safe('B -> A objects (post-restart, run already resumed/completed): all 404 NOT_FOUND', 'same probe set as before, with v3-01 run id and new sacrificial targets', 'all 404', f_b_probe2, old14=11)
def f_rev2(): res = probes(A, OWN_B2, 'A->B'); return all(':404/NOT_FOUND' in x for x in res), json.dumps(res, ensure_ascii=False)
safe('A -> B objects (reverse direction, post-restart): all 404 NOT_FOUND', 'same probe set on B objects', 'all 404', f_rev2, old14=11)
def f_blist2():
    ps = {p['id'] for p in B.get('/api/projects').json()}; return not ({TA['project_id'], TV['project_id']} & ps), f'A waiting-run projects in B list={bool({TA["project_id"], TV["project_id"]} & ps)}'
safe('A objects absent from B lists (post-restart)', 'GET /api/projects as B', 'absent', f_blist2, old14=13)
def f_alist():
    ps = {p['id'] for p in A.get('/api/projects').json()}; return not ({BW['project_id']} & ps), f'B project in A list={BW["project_id"] in ps}'
safe('B objects absent from A lists (post-restart)', 'GET /api/projects as A', 'absent', f_alist)
# B answer after restart, not influenced by A facts
time.sleep(GAP); rec = run_question(B, DQM['v3-30'], tag='g4Bpost'); s = summarize(rec); s['account'] = 'B'; s['phase'] = 'post-restart'; s['profile_hints'] = (rec['final_data'] or {}).get('profile_hints'); DEMO.append(s)
check('B own recorded refusal question after restart: same outcome as recording, no A facts', 'B: run v3-30', 'refused not_found, answer == recording, profile_hints empty', f'final={s["final_status"]}, refusal_text={s["refusal_text_in_public_result"][:40]!r}, answer==recording:{s["answer_equals_recording"]}, profile_hints={s["profile_hints"]}', s['matches_outcomes_json'] and s['answer_equals_recording'] and not s['profile_hints'])

res = {'what': 'D10 re-measurement (boot2): keyless demo answers + restart-resume + account isolation, real multi-agent graph + PostgresSaver, LLM responses replayed (DEMO_MODE=1, DEMO_REPLAY=1)',
       'commit': sh('git', 'rev-parse', 'HEAD'), 'tree': sh('git', 'rev-parse', 'HEAD^{tree}'), 'branch': 'jeongun-2 (code under test is NOT main)', 'baseline_measurement': 'b5f050d', 'measured_at_kst': ts(),
       'context': CTX, 'checks': CHECKS, 'passed': sum(c['result'] == 'pass' for c in CHECKS), 'failed': sum(c['result'] == 'fail' for c in CHECKS), 'not_applicable': sum(c['result'] == 'not_applicable' for c in CHECKS), 'total': len(CHECKS), 'requests': REQLOG}
json.dump(res, open('/tmp/g4_restart_isolation.json', 'w'), ensure_ascii=False, indent=1)
# demo_answers.json holds section A only (summaries; full answers only for equality flag, not duplicated)
json.dump({'commit': res['commit'], 'tree': res['tree'], 'branch': res['branch'], 'baseline_measurement': 'b5f050d', 'measured_at_kst': res['measured_at_kst'],
           'how': 'GET /api/demo-questions -> POST /api/projects {demo_id} -> POST /api/projects/{id}/threads -> POST /api/threads/{id}/runs (recorded question/conditions/target) -> SSE to the end; interrupt questions resumed with POST /api/runs/{id}/resume {answers[, role]} = what "기록한 답으로 계속하기" sends; compared with data/demo/recordings/outcomes.json',
           'questions': DEMO, 'resume_after_restart': RES}, open('/tmp/demo_answers.json', 'w'), ensure_ascii=False, indent=1)
print('DONE', res['passed'], 'pass', res['failed'], 'fail', res['not_applicable'], 'n/a of', res['total'])
