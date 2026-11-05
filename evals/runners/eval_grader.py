"""채점기 기준선 계산(사전 등록 #33): 지금 채점이 정답 쪽을 얼마나 유지하는지 잰다.

- 하는 일: 문항마다 "검색 청크가 정답 쪽을 다 가졌나(검색 판정)"와 "채점이 통과시킨 청크가 다 가졌나(통과 판정)"를
  충분 · 부분 · 부족으로 계산하고, 정답 쪽 유지율 · 판정 표 · 비관련 통과 0개 비율 · 쪽 재현율을 낸다.
- 하지 않는 일: LLM · API · DB 호출, 청크 본문 읽기. 스냅샷에는 청크 번호 · 파일 · 쪽만 있다.
- 출처: evals/guides/preregister.md #33, evals/inputs/qrels_v2_pages.json, evals/inputs/grader_cases_v2.json

실행(저장소 루트)
  재측정:  uv run python -m evals.runners.eval_grader run [--out <결과 json>]
  스냅샷:  uv run python -m evals.runners.eval_grader build <Langfuse 루트 trace 내보내기 json> [--out <스냅샷 json>]
    내보내기 파일은 session 루트 trace의 output(그래프 최종 상태)을 모은 것이고, 청크 본문이 있어 저장소에 두지 않는다.
"""
import argparse
import collections
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / 'evals/inputs/grader_cases_v2.json'
QRELS = ROOT / 'evals/inputs/qrels_v2_pages.json'
GRAPH_RESULT = ROOT / 'evals/results/graph/graph_dataset_v2_2026-11-04.json'


def verdict(required, pages):
    """필요 쪽을 pages가 전부 가지면 충분, 일부면 부분, 하나도 없으면 부족."""
    hit = set(required) & set(pages)
    return '충분' if required and hit == set(required) else '부분' if hit else '부족'


def _pages(chunks):
    """청크 목록의 (파일, 쪽) 집합. 쪽이 없는 표지 청크는 뺀다."""
    return {(c['file'], c['page']) for c in chunks if c['page'] is not None}


def evaluate(cases):
    """스냅샷 문항 목록으로 #33의 지표 ①~④를 계산한다."""
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


def build_cases(roots, qrels, rows):
    """Langfuse 루트 trace 내보내기 + qrels + 그래프 결과 행으로 스냅샷 문항을 만든다. 청크 본문은 버린다."""
    state = {r['name'].removeprefix('graph '): json.loads(r['output']) for r in roots}
    cases = []
    for row in rows:
        q = qrels.get(row['id'])
        if row['kind'] == 'relevant' and q is None:
            continue  # 후보 찾기 · 역할은 정답 쪽이 열려 있어 뺀다(#33)
        s = state[row['id']]
        cases.append({'id': row['id'], 'kind': row['kind'],
                      'required_pages': q['pages'] if q else [], 'unrecoverable': q['unrecoverable'] if q else [],
                      'retrieved': [{'chunk_id': str(d['chunk_id']), 'file': d['file'],
                                     'page': None if d.get('page') in (None, 'None') else int(d['page'])}
                                    for d in s.get('docs') or []],
                      'passed': [str(i) for i in s.get('passed') or []]})
    return cases


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build')
    b.add_argument('roots')
    b.add_argument('--out', default=str(SNAPSHOT))
    r = sub.add_parser('run')
    r.add_argument('--out', default=str(ROOT / f'evals/results/grader/grader_baseline_{time.strftime("%Y-%m-%d")}.json'))
    a = ap.parse_args()
    if a.cmd == 'build':
        res = json.load(open(GRAPH_RESULT, encoding='utf-8'))
        cases = build_cases(json.load(open(a.roots, encoding='utf-8')), json.load(open(QRELS, encoding='utf-8'))['qrels'], res['rows'])
        meta = {'session': res['meta']['session'], 'git': res['meta']['git'], 'dataset_sha256': res['meta']['dataset_sha256'],
                'note': '채점 노드가 마지막으로 본 검색 청크와 통과 청크의 번호 · 파일 · 쪽만 담는다(본문 없음). 사전 등록 #33'}
        Path(a.out).write_text(json.dumps({'meta': meta, 'cases': cases}, ensure_ascii=False, indent=1), encoding='utf-8')
        print(f'스냅샷 {len(cases)}문항 → {a.out}')
    else:
        snap = json.load(open(SNAPSHOT, encoding='utf-8'))
        out = {'meta': snap['meta'], 'result': evaluate(snap['cases'])}
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
        print(json.dumps(out['result'], ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
