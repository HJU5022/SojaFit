"""usage: threshold_demo.py WORKTREE OUTDIR PYTHON -- shows the injection-result check passing on the saved result and failing (exit 1) on broken copies."""
import json, subprocess, sys, pathlib, tempfile
wt, out, py = map(pathlib.Path, sys.argv[1:4])
src = wt / 'evals/results/threads/injection_baseline_live_2026-11-11_03.jsonl'
rows = [json.loads(l) for l in src.read_text(encoding='utf-8').splitlines() if l.strip()]
def run(path):
    r = subprocess.run([str(py), '-m', 'evals.runners.check_injection_result', str(path)], cwd=wt, capture_output=True, text=True)
    return r.stdout + f'EXIT:{r.returncode}\n'
tmp = pathlib.Path(tempfile.mkdtemp())
def variant(name, edit):
    rs = json.loads(json.dumps(rows)); edit(rs)
    p = tmp / name; p.write_text('\n'.join(json.dumps(r, ensure_ascii=False) for r in rs) + '\n', encoding='utf-8'); return p
(out / 'threshold_pass.txt').write_text('# python -m evals.runners.check_injection_result  (saved result, unmodified)\n' + run(src))
cases = [('broken_empty_answer.jsonl', lambda r: r[0].update(answer=''), 'row 0 answer emptied'),
         ('broken_verdict.jsonl', lambda r: next(x for x in r if x['case'] == 'T5')['automatic'].update(verdict_correct=False), 'first T5 row verdict_correct=false'),
         ('broken_dropped_row.jsonl', lambda r: r.pop(), 'last row removed (109 rows)')]
txt = ''
for name, edit, why in cases:
    txt += f'# {why}\n' + run(variant(name, edit))
(out / 'threshold_fail.txt').write_text(txt)
print((out / 'threshold_pass.txt').read_text() + txt)
