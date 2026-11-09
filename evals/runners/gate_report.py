"""감시 실행기(run_gate) 결과 세트들을 11-07 기준표로 집계한다: 정답률 · 오탐 · 검색 · 응답 시간.

- 역할: `set*.json`과 평가셋 jsonl을 읽어 세트마다 아래 지표를 계산하고 기준(기본 0.95 · 오탐 5% · p95 10초)과 비교해 표로 쓴다.
  - 관련 정답률: 관련 문항 중 통과(run_gate.passed). 후보 판정에 `verdict` 칸이 없는 옛 평가셋(v2)은 `expected` 글의 첫 판정 코드를 쓴다.
  - 무관 올바른 거절률, 지어낸 답 비율(무관에 답함), 근거 틀린 답 비율(관련 wrong_citation · 판정 불일치), 답할 수 있는데 거절 비율(관련 over_refusal)
  - 검색(에이전트 길): 정답 (PDF, 쪽)이 있는 관련 문항마다, 문서 할 일이 있으면 그 첫 검색 상위 5개, 없으면 답의 판정 표 근거 칸
    (PDF, 쪽)을 나온 순서대로 상위 5개로 보고 문서 · 쪽 Recall@5 · MRR(5위 밖 0)을 낸다. 둘 다 없으면 0으로 센다.
  - 응답 시간 p50 · p95(run_gate 정의)
- 하지 않는 일: 그래프 실행(run_gate), 평가셋 고치기.
- 출처: ADR 0015 목표 지표와 11-07 조장 결정(모든 세트 0.95, 오탐도 그에 맞게, p95 10초), docs/experiments/b-redesign/사전등록-2차.md

실행: python -m evals.runners.gate_report <평가셋 jsonl> <결과 폴더> [--min 0.95] [--max-error 0.05] [--p95 10]
"""
import json
import re
import sys
from pathlib import Path

from evals.runners.run_gate import p95, passed
from evals.runners.run_retrieval import gold_locations
from evals.runners.run_retrieval_v3 import score

VERDICT = re.compile(r'\b(SAME_PART|SPEC_EQUIVALENT|ROLE_SUFFICIENT|NOT_SUFFICIENT|NOT_VERIFIED)\b')
TABLE_LOC = re.compile(r'\|\s*([^|\n]+?\.pdf)\s+(\d+)쪽')  # 판정 표의 근거 칸(파일 이름에 빈칸이 있다)


def with_verdict(item: dict) -> dict:
    """옛 평가셋의 후보 판정 문항은 expected 글의 첫 판정 코드를 정답 판정으로 쓴다."""
    if item.get('question_type') == 'candidate_judge' and not item.get('verdict'):
        m = VERDICT.search(item.get('expected') or '')
        if m:
            return {**item, 'verdict': m.group(1)}
    return item


def found_locations(row: dict) -> list[tuple[str, int]] | None:
    """에이전트가 실제로 본 근거 위치 상위 5개: 문서 할 일의 첫 검색, 없으면 판정 표 근거 칸. 아무것도 없으면 None."""
    first = next((s for t in row.get('tasks') or [] if t.get('agent') == 'docs' for s in t.get('searches') or []), None)
    if first:
        return [tuple(x) for x in first['top']][:5]
    seen = []
    for f, p in TABLE_LOC.findall(row.get('answer') or ''):
        if (f.strip(), int(p)) not in seen:
            seen.append((f.strip(), int(p)))
    return seen[:5] or None


def set_metrics(items: dict, rows: list[dict]) -> dict:
    """세트 하나의 기준표 지표."""
    rel = [r for r in rows if items[r['id']]['kind'] == 'relevant']
    irr = [r for r in rows if items[r['id']]['kind'] == 'irrelevant']
    ok = {r['id']: 'error' not in r and passed(with_verdict(items[r['id']]), r) for r in rows}
    ret = []
    for r in rel:
        gold = gold_locations(items[r['id']].get('gold_chunks') or [])
        if not any(f.endswith('.pdf') for f, _ in gold):
            continue  # 넷리스트만 근거인 역할 문항은 검색 지표에서 뺀다
        found = found_locations(r)
        s = score(found, gold) if found else {'doc_recall@5': 0.0, 'doc_mrr': 0.0, 'page_recall@5': 0.0, 'page_mrr': 0.0}
        # [왜] 재계획(설계 v2)이 다른 검색어로 다시 찾으면 첫 검색이 아닌 검색에서 정답을 찾을 수 있다. 첫 검색(기준)과 따로 '어느 검색이든'을 남긴다
        tops = [tuple(x) for t in r.get('tasks') or [] if t.get('agent') == 'docs' for q in t.get('searches') or [] for x in q['top'][:5]]
        s['page_any@5'] = float(bool(set(tops) & set(gold))) if tops else s['page_recall@5']
        ret.append(s)
    rate = lambda xs, f: round(sum(1 for x in xs if f(x)) / len(xs), 4) if xs else None
    lat = [r['latency_s'] for r in rows if 'latency_s' in r]
    out = {
        'n': len(rows), 'relevant': len(rel), 'irrelevant': len(irr),
        'relevant_correct': rate(rel, lambda r: ok[r['id']]),
        'irrelevant_refused': rate(irr, lambda r: r.get('answer_metric') == 'correct_refusal'),
        'made_up_answer': rate(irr, lambda r: r.get('answer_metric') != 'correct_refusal'),
        'wrong_answer': rate(rel, lambda r: r.get('answer_metric') == 'wrong_citation' or ('error' not in r and r.get('answer_metric') == 'cited_gold' and not ok[r['id']])),
        'over_refusal': rate(rel, lambda r: r.get('answer_metric') == 'over_refusal'),
        'errors': sum(1 for r in rows if 'error' in r),
        'parts_correct': rate([p for r in rows for p in r.get('parts_result') or []], lambda p: p['pass']),  # 여러 개를 묻는 문항의 부분별 정답률
        'retrieval_n': len(ret),
        **{k: round(sum(x[k] for x in ret) / len(ret), 4) if ret else None for k in ('doc_recall@5', 'doc_mrr', 'page_recall@5', 'page_mrr', 'page_any@5')},
        'p50_s': sorted(lat)[len(lat) // 2] if lat else None, 'p95_s': p95(lat),
        'failed': [r['id'] for r in rows if not ok[r['id']]],
    }
    return out


def check(m: dict, low: float, high: float, p95_limit: float) -> list[str]:
    """기준을 넘지 못한 지표 이름들."""
    bad = [k for k in ('relevant_correct', 'irrelevant_refused', 'doc_recall@5', 'doc_mrr', 'page_recall@5', 'page_mrr')
           if m[k] is not None and m[k] < low]
    bad += [k for k in ('made_up_answer', 'wrong_answer', 'over_refusal') if m[k] is not None and m[k] > high]
    bad += ['errors'] if m['errors'] else []
    bad += ['p95_s'] if m['p95_s'] > p95_limit else []
    return bad


def main(dataset: str, folder: str, low: float = 0.95, high: float = 0.05, p95_limit: float = 10.0) -> int:
    items = {json.loads(l)['id']: json.loads(l) for l in open(dataset, encoding='utf-8') if l.strip()}
    report = []
    for f in sorted(Path(folder).glob('set*.json')):
        d = json.loads(f.read_text(encoding='utf-8'))
        m = set_metrics(items, d['rows'])
        m['below'] = check(m, low, high, p95_limit)
        m['set'] = f.stem
        m['meta'] = {k: d['summary'].get(k) for k in ('git', 'model_env', 'db', 'llm_provider', 'claude_direct', 'session')}
        report.append(m)
        print(f"{f.stem}\t정답 {m['relevant_correct']}\t거절 {m['irrelevant_refused']}\t지어냄 {m['made_up_answer']}\t틀린답 {m['wrong_answer']}\t"
              f"과잉거절 {m['over_refusal']}\t검색 문서 {m['doc_recall@5']}/{m['doc_mrr']} 쪽 {m['page_recall@5']}/{m['page_mrr']}\t"
              f"p50 {m['p50_s']} p95 {m['p95_s']}\t미달 {m['below'] or '없음'}\t실패 {m['failed']}")
    (Path(folder) / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    return 0 if report and not any(m['below'] for m in report) else 1


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    opt = {k: float(a[a.index(k) + 1]) for k in ('--min', '--max-error', '--p95') if k in a}
    sys.exit(main(a[0], a[1], opt.get('--min', 0.95), opt.get('--max-error', 0.05), opt.get('--p95', 10.0)))
