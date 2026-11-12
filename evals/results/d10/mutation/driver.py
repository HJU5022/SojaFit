"""usage: driver.py WORKTREE SPEC OUTDIR PYTHON [ids...]  -- applies each mutation, runs tests, restores, verifies clean."""
import json, subprocess, sys, pathlib, datetime
wt, spec, out, py = map(pathlib.Path, sys.argv[1:5]); ids = sys.argv[5:]
def sh(*a):
    return subprocess.run(a, cwd=wt, capture_output=True, text=True)
def pytest(tests):
    r = sh(str(py), '-m', 'pytest', *tests, '-q', '-p', 'no:cacheprovider', '--tb=short')
    return r.returncode, r.stdout + r.stderr
def clean():
    return sh('git', 'status', '--porcelain').stdout == '' and sh('git', 'diff', '--stat').stdout == ''
res = []
for m in json.loads(spec.read_text()):
    if ids and m['id'] not in ids: continue
    f = wt / m['file']; text = f.read_bytes().decode('utf-8')
    if m['before'] == '__APPEND_BYTE__':      # flip: append one byte to the dataset
        new, line = text + ' ', len(text.splitlines())
    else:
        if text.count(m['before']) != 1:
            print(m['id'], 'SKIP before-text count =', text.count(m['before'])); res.append({**m, 'verdict': 'NO_MATCH'}); continue
        new = text.replace(m['before'], m['after']); line = text[:text.index(m['before'])].count('\n') + 1
    f.write_bytes(new.encode('utf-8'))
    t = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S KST')
    rc1, o1 = pytest(m['tests'])
    sh('git', 'checkout', '--', m['file']); c1 = clean()
    rc2, o2 = pytest(m['tests']); c2 = clean()
    (out / f"{m['id']}_mutated.txt").write_text(o1); (out / f"{m['id']}_restored.txt").write_text(o2)
    v = 'CAUGHT' if rc1 != 0 and rc2 == 0 and c1 and c2 else ('NOT_CAUGHT' if rc1 == 0 else 'CHECK')
    print(f"{m['id']:4} {v:10} mutated_rc={rc1} restored_rc={rc2} clean={c1 and c2} line={line}  {o1.strip().splitlines()[-1] if o1.strip() else ''}")
    res.append({**m, 'line': line, 'verdict': v, 'mutated_rc': rc1, 'restored_rc': rc2, 'clean': c1 and c2, 'at': t,
                'mutated_summary': o1.strip().splitlines()[-1], 'restored_summary': o2.strip().splitlines()[-1]})
(out / 'results_raw.json').write_text(json.dumps(res, ensure_ascii=False, indent=1))
