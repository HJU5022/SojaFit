"""usage: v3_gate_demo.py WORKTREE OUTFILE PYTHON -- runs the v3 gate checker (evals.runners.gate_report, dataset_v3.jsonl) offline on a stored v3 result and on degraded temp copies; prints the real output and exit codes."""
import json, subprocess, sys, pathlib, tempfile, shutil
wt, outf, py = map(pathlib.Path, sys.argv[1:4])
src = wt / 'evals/results/graph/2026-11-12-d9-improve2/set1.json'
data = json.loads(src.read_text(encoding='utf-8'))
head = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=wt, capture_output=True, text=True).stdout.strip()

def run(edit):
    d = json.loads(json.dumps(data)); edit(d['rows'])
    tmp = pathlib.Path(tempfile.mkdtemp())  # gate_report reads set*.json from a folder and writes report.json there
    (tmp / 'set1.json').write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    r = subprocess.run([str(py), '-m', 'evals.runners.gate_report', 'evals/dataset_v3.jsonl', str(tmp)], cwd=wt, capture_output=True, text=True)
    shutil.rmtree(tmp)
    return r.stdout + r.stderr + f'EXIT:{r.returncode}\n'

def pick(rows, kind, n): return [r for r in rows if r['kind'] == kind][:n]
def made_up(rows):
    for r in pick(rows, 'irrelevant', 3): r['answer_metric'] = 'cited_gold'
def over_refuse(rows):
    for r in pick(rows, 'relevant', 3): r['answer_metric'] = 'over_refusal'
def slow(rows):
    for r in rows[:5]: r['latency_s'] = 30.0
def no_retrieval(rows):
    for r in pick(rows, 'relevant', 4): r['tasks'] = []; r['answer'] = ''

cases = [('unmodified stored result (expect pass, EXIT:0)', lambda r: None),
         ('3 irrelevant rows answered instead of refused (answer_metric=cited_gold)', made_up),
         ('3 relevant rows over_refusal (answer_metric=over_refusal)', over_refuse),
         ('latency_s=30 on 5 rows (p95 over 10s)', slow),
         ('4 relevant rows lose retrieval evidence (tasks=[] and answer empty)', no_retrieval)]
txt = (f'# v3 gate below-threshold demo (offline, no LLM/DB/server)\n# date: 2026-11-13  commit: {head}\n'
       f'# command: .venv/bin/python evals/results/d10/mutation/v3_gate_demo.py . evals/results/d10/v3_gate_fail_2026-11-13.txt .venv/bin/python\n'
       f'# each case runs: python -m evals.runners.gate_report evals/dataset_v3.jsonl <temp folder with mutated set1.json>   (thresholds: --min 0.95 --max-error 0.05 --p95 10)\n'
       f'# base: {src.relative_to(wt)} (50 rows, unmodified in repo; mutations are applied to temp copies only)\n\n')
for why, edit in cases:
    txt += f'## {why}\n' + run(edit) + '\n'
outf.write_text(txt, encoding='utf-8'); print(txt)
