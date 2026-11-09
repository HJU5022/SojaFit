"""평가셋을 멀티 에이전트로 여러 세트 연달아 돌리며, 문항 하나라도 통과 못 하면 그 자리에서 멈추는 감시 실행기(v3 반복 측정용).

- 역할: 문항을 순서대로 하나씩 돌려(동시 실행 없음, 응답 시간을 그대로 재려고) 문항마다 통과를 바로 판정하고,
  처음 실패한 문항에서 멈춰 그 문항의 경로 · 지표 · 판정 · 트레이스 주소를 결과 파일과 화면에 남긴다.
  세트가 끝나면 응답 시간 p95(실행기 정의 int(0.95n)번째)가 기준을 넘는지 보고, 넘으면 거기서 멈춘다.
  - 문항 통과: 관련은 정답 (PDF, 쪽) 인용(`cited_gold`) + 후보 판정이면 첫 후보 판정 == `verdict`
    + 후보 찾기면 보여 준 후보가 모두 `qualifying_parts` 안이고 하나 이상. 무관은 올바른 거절(`correct_refusal`). 실행 오류는 실패.
- 하지 않는 일: 평가셋 고치기(사람 · 세션이 원인을 보고 고친다), 검색 지표(별도 실행기), 동시 실행.
- 출처: 정운 지시(11-06: 0.95 기준 3세트, 하나라도 이상하면 멈추고 고친 뒤 처음부터), run_graph.py(조립 · 채점 함수를 그대로 씀)

- `--keep-going`: 실패해도 멈추지 않고 세트를 끝까지 돈다(11-07 기준이 '세트마다 0.95'로 바뀌어 전체 비율을 재야 한다). 집계는 `gate_report.py`.

실행(저장소 루트): uv run python -m evals.runners.run_gate <평가셋 jsonl> --out <결과 폴더> [--sets 3] [--p95 10] [--keep-going]
"""
import json
import os
import sys
import time
from contextlib import ExitStack
from pathlib import Path

from evals.runners.run_graph import invoke_with_resume, make_app, result_row, run_scores


def verdict_ok(item: dict, row: dict) -> bool:
    """후보 판정 · 찾기 문항의 판정 조건. 다른 종류는 늘 참이다."""
    shown = row.get('verdicts') or []
    if item.get('question_type') == 'candidate_judge' and item.get('verdict'):
        return bool(shown) and shown[0][1] == item['verdict']
    if item.get('question_type') == 'candidate_find' and item.get('qualifying_parts'):
        ok = {p.upper() for p in item['qualifying_parts']}
        return bool(shown) and all((p or '').upper() in ok for p, _ in shown)
    return True


def passed(item: dict, row: dict) -> bool:
    """문항 하나의 통과 여부(모듈 설명의 정의). 여러 개를 묻는 문항(`parts`)은 부분이 모두 통과해야 한다(score_compound)."""
    if item.get('parts'):
        return bool(row.get('parts_result')) and all(p['pass'] for p in row['parts_result'])
    want = 'cited_gold' if item['kind'] == 'relevant' else 'correct_refusal'
    return row.get('answer_metric') == want and verdict_ok(item, row)


def _git_rev() -> str:
    """측정한 코드의 커밋(고친 파일이 있으면 +dirty). 결과 파일이 어느 코드로 났는지 남긴다."""
    import subprocess
    rev = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=no'], capture_output=True, text=True).stdout.strip()
    return rev + ('+dirty' if dirty else '')


def p95(values: list[float]) -> float:
    """실행기와 같은 정의의 p95: 정렬한 값의 int(0.95n)번째(0부터 셈, 끝을 넘으면 마지막)."""
    v = sorted(values)
    return v[min(int(0.95 * len(v)), len(v) - 1)] if v else 0.0


def main(dataset_path: str, out_dir: str, sets: int = 3, p95_limit: float = 10.0, keep_going: bool = False) -> int:
    """세트를 연달아 돌려 처음 실패에서 멈춘다(keep_going이면 끝까지 돈다). 모두 통과하면 0, 멈추면 1을 돌려준다."""
    os.environ.setdefault('LANGFUSE_TRACING_ENVIRONMENT', 'eval')
    from langfuse import get_client
    from langfuse.langchain import CallbackHandler
    from backend.services import llm
    items = [json.loads(line) for line in open(dataset_path, encoding='utf-8') if line.strip()]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    client = get_client()
    stamp = time.strftime('%m%d-%H%M')
    with ExitStack() as stack:
        app = make_app(True, stack)
        for s in range(1, sets + 1):
            rows, session = [], f'gate-{Path(dataset_path).stem}-{stamp}-set{s}'
            for it in items:
                trace_id = client.create_trace_id()
                meta = {'question_id': it['id'], 'kind': it['kind'], 'langfuse_session_id': session,
                        'langfuse_tags': ['gate', it['id'], f'set{s}']}
                config = {'callbacks': [CallbackHandler(trace_context={'trace_id': trace_id})], 'run_name': f'gate {it["id"]}',
                          'metadata': meta, 'configurable': {'thread_id': f'{session}-{it["id"]}'}}
                start = time.perf_counter()
                try:
                    state = invoke_with_resume(app, {'input': it['input']}, config)
                    seconds = time.perf_counter() - start
                    scores = run_scores(state, seconds, [], item=it)
                    row = result_row(it, state, scores, client.get_trace_url(trace_id=trace_id))
                    row['answer'] = state.get('answer', '')  # [왜] 멈춘 문항의 원인을 보려면 답 글이 필요하다(로컬 결과 폴더에만 남긴다)
                    # [왜] 검색 지표(Recall@5 · MRR)를 에이전트가 실제로 쓴 검색어 · 상위 5개로 계산하려고 RAG 에이전트의 검색 기록을 남긴다.
                    #      gate_report가 읽는 모양(tasks[].agent · searches)은 그대로 둔다(11-09부터 에이전트는 하나라 줄도 하나)
                    row['tasks'] = [{'agent': 'docs', 'searches': state['searches']}] if state.get('searches') else []
                    if it.get('parts'):
                        from evals.runners.score_compound import score_parts
                        row['parts_result'] = score_parts(it, state)  # [왜] 여러 개를 묻는 질문은 부분마다 채점한다(B-지시서 4-5.3)
                except Exception as error:  # [왜] 실행 오류도 "이상한 데이터"다. 멈추고 오류를 남긴다
                    import traceback  # [왜] 멈춘 오류의 자리를 다시 재현하지 않고 보려고 마지막 몇 줄을 남긴다
                    row = {'id': it['id'], 'kind': it['kind'], 'error': f'{type(error).__name__}: {str(error)[:300]}',
                           'trace': traceback.format_exc(limit=6)[-1500:], 'latency_s': round(time.perf_counter() - start, 1)}
                row['pass'] = 'error' not in row and passed(it, row)
                rows.append(row)
                print(f'set{s}\t{it["id"]}\t{"PASS" if row["pass"] else "FAIL"}\t{row.get("answer_metric", row.get("error"))}\t'
                      f'{row.get("verdicts", "")}\t{row.get("latency_s")}초', flush=True)
                if not row['pass'] and not keep_going:
                    break
            lat = [r['latency_s'] for r in rows if 'latency_s' in r]
            summary = {'set': s, 'done': len(rows), 'total': len(items), 'passed': sum(r['pass'] for r in rows),
                       'p95_s': p95(lat), 'p50_s': sorted(lat)[len(lat) // 2] if lat else 0.0, 'session': session,
                       'stopped_at': next((r['id'] for r in rows if not r['pass']), None),
                       'model_env': {k: os.getenv(k, '') for k in ('LAB_THINKING', 'LAB_THINKING_ON', 'LAB_NODE_MODELS', 'LAB_EFFORT', 'LAB_READ_VOTES')},
                       'db': os.getenv('DATABASE_URL', '').rsplit('/', 1)[-1],  # DB 이름만(접속 정보는 남기지 않는다)
                       'llm_provider': llm.LLM_PROVIDER, 'claude_direct': llm.LLM_PROVIDER == 'openrouter' and bool(os.getenv('ANTHROPIC_API_KEY')),  # [왜] Anthropic 직통인지 OpenRouter인지(응답 시간이 다르다). claude_cli는 키를 빼고 구독으로 부르므로 직통이 아니다
                       'git': _git_rev()}
            (out / f'set{s}.json').write_text(json.dumps({'summary': summary, 'rows': rows}, ensure_ascii=False, indent=1) + '\n',
                                               encoding='utf-8')
            print(json.dumps(summary, ensure_ascii=False), flush=True)
            if not keep_going and (summary['stopped_at'] or (len(rows) == len(items) and summary['p95_s'] > p95_limit)):
                client.flush()
                return 1
    client.flush()
    return 0


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 3 or '--out' not in a:
        sys.exit(__doc__)
    opt = {k: a[a.index(k) + 1] for k in ('--out', '--sets', '--p95') if k in a}
    sys.exit(main(a[0], opt['--out'], int(opt.get('--sets', 3)), float(opt.get('--p95', 10)), '--keep-going' in a))
