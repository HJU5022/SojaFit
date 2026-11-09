"""채점기 기준선 계산(사전 등록 #36): 지금 채점이 정답 쪽을 얼마나 유지하는지 잰다.

- 하는 일: 문항마다 "검색 청크가 정답 쪽을 다 가졌나(검색 판정)"와 "채점이 통과시킨 청크가 다 가졌나(통과 판정)"를
  충분 · 부분 · 부족으로 계산하고, 정답 쪽 유지율 · 판정 표 · 비관련 통과 0개 비율 · 쪽 재현율을 낸다.
  `collect-r1`은 R1 dev 46문항을 서비스 검색 + 지금 채점 노드로 1번씩 돌려 스냅샷을 만든다(사전 등록 #34).
- 하지 않는 일: `run`은 LLM · API · DB를 부르지 않는다(`collect-r1`만 부른다). 스냅샷에는 청크 번호 · 파일 · 쪽만 있고 본문은 저장하지 않는다.
- 출처: evals/guides/preregister.md #36 · #34, evals/inputs/qrels_v2_pages.json, evals/inputs/grader_cases_v2.json

실행(저장소 루트)
  재측정:  uv run python -m evals.runners.eval_grader run [--snapshot <스냅샷 json>] [--out <결과 json>]
  R1 dev:  uv run python -m evals.runners.eval_grader collect-r1   (운영 DB 읽기 · Voyage · OpenRouter 호출, 스냅샷을 새로 만든다)
  스냅샷:  uv run python -m evals.runners.eval_grader build <Langfuse 루트 trace 내보내기 json> [--out <스냅샷 json>]
    내보내기 파일은 session 루트 trace의 output(그래프 최종 상태)을 모은 것이고, 청크 본문이 있어 저장소에 두지 않는다.
"""
import argparse
import collections
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / 'evals/inputs/grader_cases_v2.json'
QRELS = ROOT / 'evals/inputs/qrels_v2_pages.json'
GRAPH_RESULT = ROOT / 'evals/results/graph/graph_dataset_v2_2026-11-04.json'
R1_DATA = ROOT / 'evals/samples/retrieval_r1.jsonl'
R1_REWRITE = ROOT / 'evals/samples/retrieval_r1_rewrite_q3.json'
R1_SNAPSHOT = ROOT / 'evals/inputs/grader_cases_r1_dev.json'
MAX_ERRORS = 3  # [왜] 사전 등록 #34: 연속 오류 3번이면 멈춘다(키 한도 · 결제 신호를 끝없이 부르지 않는다)


def verdict(required, pages):
    """필요 쪽을 pages가 전부 가지면 충분, 일부면 부분, 하나도 없으면 부족."""
    hit = set(required) & set(pages)
    return '충분' if required and hit == set(required) else '부분' if hit else '부족'


def _pages(chunks):
    """청크 목록의 (파일, 쪽) 집합. 쪽이 없는 표지 청크는 뺀다."""
    return {(c['file'], c['page']) for c in chunks if c['page'] is not None}


def evaluate(cases):
    """스냅샷 문항 목록으로 #36의 지표 ①~④를 계산한다."""
    table, kept, sufficient, recalls = collections.Counter(), 0, 0, []
    irrelevant = zero = 0
    for c in cases:
        passed_ids = set(map(str, c['passed']))
        passed = [d for d in c['retrieved'] if str(d['chunk_id']) in passed_ids]
        if c['kind'] == 'irrelevant':
            irrelevant += 1
            zero += not passed_ids
            continue
        need = {tuple(p) for p in c['required_pages']} - {tuple(u) for u in c['unrecoverable']}
        got, kept_pages = verdict(need, _pages(c['retrieved'])), verdict(need, _pages(passed))
        table[f'{got}>{kept_pages}'] += 1
        if got == '충분':
            sufficient += 1
            kept += kept_pages == '충분'
        recalls.append(len(need & _pages(passed)) / len(need) if need else 0.0)
    return {'relevant': len(recalls), 'irrelevant': irrelevant, 'retrieved_sufficient': sufficient,
            'retention': {'kept': kept, 'of': sufficient}, 'table': dict(sorted(table.items())),
            'irrelevant_zero_pass': {'zero': zero, 'of': irrelevant},
            'page_recall_mean': round(sum(recalls) / len(recalls), 3) if recalls else None}


def case_from_state(cid, kind, required, unrecoverable, docs, passed):
    """검색 청크 docs와 통과 청크 번호 passed를 스냅샷 문항으로 만든다. 청크 본문은 버리고 번호 · 파일 · 쪽만 남긴다."""
    return {'id': cid, 'kind': kind, 'required_pages': required, 'unrecoverable': unrecoverable,
            'retrieved': [{'chunk_id': str(d['chunk_id']), 'file': d['file'],
                           'page': None if d.get('page') in (None, 'None') else int(d['page'])} for d in docs],
            'passed': [str(i) for i in passed]}


def build_cases(roots, qrels, rows):
    """Langfuse 루트 trace 내보내기 + qrels + 그래프 결과 행으로 v2 스냅샷 문항을 만든다."""
    state = {r['name'].removeprefix('graph '): json.loads(r['output']) for r in roots}
    cases = []
    for row in rows:
        q = qrels.get(row['id'])
        if row['kind'] == 'relevant' and q is None:
            continue  # 후보 찾기 · 역할은 정답 쪽이 열려 있어 뺀다(#36)
        s = state[row['id']]
        cases.append(case_from_state(row['id'], row['kind'], q['pages'] if q else [], q['unrecoverable'] if q else [],
                                     s.get('docs') or [], s.get('passed') or []))
    return cases


def collect(rows, queries, find_parts, retrieve, grade, max_errors=MAX_ERRORS):
    """R1 문항마다 고정 질의로 retrieve를 1번 부르고 그 결과에 grade를 1번 돌려 스냅샷 문항을 만든다.

    오류가 난 문항은 건너뛰고 id를 돌려주며, 연속 max_errors번이면 RuntimeError로 멈춘다.
    """
    cases, errors, streak = [], [], 0
    for row in rows:
        parts = find_parts(row['question'], set())
        try:
            docs = retrieve(queries[row['id']], parts=parts or None)  # 품번이 없으면 None: 코퍼스 전체에서 찾는다(search 노드와 같음)
            passed = grade({'question': row['question'], 'docs': docs, 'parts': parts})['passed']
        except Exception as error:  # noqa: BLE001  API · DB 오류를 문항 단위로 세어 상한까지만 건너뛴다
            errors.append(row['id'])
            streak += 1
            if streak >= max_errors:
                raise RuntimeError(f'연속 {streak}문항 오류로 멈춤: {errors[-streak:]} ({type(error).__name__})') from error
            continue
        streak = 0
        cases.append(case_from_state(row['id'], 'relevant', [list(g) for g in row['gold']], [], docs, passed))
    return cases, errors


def openrouter_usage():
    """OpenRouter 키 누적 사용액(달러). 키가 없으면 None."""
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        return None
    import httpx
    return float(httpx.get('https://openrouter.ai/api/v1/key', timeout=20, headers={'Authorization': f'Bearer {key}'}).json()['data']['usage'])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('roots')
    b.add_argument('--out', default=str(SNAPSHOT))
    r = sub.add_parser('run')
    r.add_argument('--snapshot', default=str(SNAPSHOT))
    r.add_argument('--out', default=str(ROOT / f'evals/results/grader/grader_baseline_{time.strftime("%Y-%m-%d")}.json'))
    c = sub.add_parser('collect-r1')
    c.add_argument('--out', default=str(R1_SNAPSHOT))
    a = ap.parse_args()
    if a.cmd == 'build':
        res = json.load(open(GRAPH_RESULT, encoding='utf-8'))
        cases = build_cases(json.load(open(a.roots, encoding='utf-8')), json.load(open(QRELS, encoding='utf-8'))['qrels'], res['rows'])
        meta = {'session': res['meta']['session'], 'git': res['meta']['git'], 'dataset_sha256': res['meta']['dataset_sha256'],
                'note': '채점 노드가 마지막으로 본 검색 청크와 통과 청크의 번호 · 파일 · 쪽만 담는다(본문 없음). 사전 등록 #36'}
        Path(a.out).write_text(json.dumps({'meta': meta, 'cases': cases}, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'스냅샷 {len(cases)}문항 → {a.out}')
    elif a.cmd == 'collect-r1':
        os.environ['DEMO_MODE'] = '0'  # [주의] llm이 import 때 읽으므로 backend를 부르기 전에 정한다
        from backend.graph.nodes import find_parts, grade
        from backend.rag import retrieve as R
        from backend.services import llm
        if llm.DEMO_MODE:
            raise SystemExit('DEMO_MODE가 꺼지지 않았다')
        rows = [r for r in map(json.loads, filter(str.strip, open(R1_DATA, encoding='utf-8'))) if r['split'] == 'dev']
        queries = json.load(open(R1_REWRITE, encoding='utf-8'))['queries']
        start = openrouter_usage()
        R.warmup()
        cases, errors = collect(rows, queries, find_parts, R.retrieve, grade)
        spent = None if start is None else round(openrouter_usage() - start, 4)
        meta = {'preregister': '#34', 'set': 'R1 dev', 'run_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'commit': subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
                'config': '고정 Q3 질의 + find_parts 품번 필터, retrieve(k=5), 지금 채점 노드 1번(재작성 · 재검색 없음)',
                'errors': errors, 'openrouter_spent_usd': spent,
                'note': '채점 노드가 본 검색 청크와 통과 청크의 번호 · 파일 · 쪽만 담는다(본문 없음)'}
        Path(a.out).write_text(json.dumps({'meta': meta, 'cases': cases}, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'스냅샷 {len(cases)}문항, 오류 {errors}, OpenRouter 사용액 {spent} → {a.out}')
    else:
        snap = json.load(open(a.snapshot, encoding='utf-8'))
        out = {'meta': snap['meta'], 'result': evaluate(snap['cases'])}
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
        print(json.dumps(out['result'], ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
