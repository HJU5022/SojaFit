"""판정 연습 문제(evals/samples/judge_dev.jsonl)를 멀티 그래프로 돌려 역할 정답률 · 판정 일치율을 잰다.

- 역할: 문항마다 그래프를 돌리고(인터럽트는 빈 값으로 한 번 재개), 판정 결과를 기대 역할 · 판정과 비교해 결과 파일을 쓴다.
- 하지 않는 일: 동결 평가셋 채점(run_graph.py), 정답 고치기.
- 출처: docs/specs/judge-agent.md Goal · How "연습 문제와 측정"
- 실행(조장 승인 뒤, lab 컨테이너): uv run python -m evals.runners.run_judge_dev evals/samples/judge_dev.jsonl
"""
import json
import sys
import time
from contextlib import ExitStack
from pathlib import Path

from evals.runners.run_graph import invoke_with_resume, make_app

OUT = Path('evals/results/judge')


def score_item(item: dict, judgement: dict | None) -> dict:
    """문항 하나: 역할이 맞는지, 판정(찾기면 보여 준 후보와 판정 집합)이 기대와 같은지."""
    judgement = judgement or {}
    role = (judgement.get('roles') or [''])[0]
    if item.get('question_type') == 'candidate_find':
        got = {(j['part'], j['verdict']) for j in judgement.get('shown', [])}
        want = {(e['part'], e['verdict']) for e in item.get('expected_shown', [])}
        verdict, ok = sorted(got), got == want
    else:
        results = judgement.get('results') or []
        verdict = results[0]['verdict'] if results else ''
        ok = verdict == item.get('verdict')
    return {'id': item['id'], 'role_ok': role == item.get('role'), 'verdict_ok': ok, 'role': role, 'verdict': verdict}


def summarize(rows: list[dict]) -> dict:
    """역할 정답률 · 판정 일치율."""
    n = len(rows)
    return {'n': n, 'role_rate': sum(r['role_ok'] for r in rows) / n if n else 0.0,
            'verdict_rate': sum(r['verdict_ok'] for r in rows) / n if n else 0.0}


def main(path: str) -> None:
    items = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    rows = []
    with ExitStack() as stack:
        app = make_app(True, stack)
        for it in items:
            config = {'configurable': {'thread_id': it['id']}}
            try:
                state = invoke_with_resume(app, {'input': it['input']}, config)
            except Exception as error:  # [왜] 한 문항이 죽어도 나머지는 잰다
                rows.append({'id': it['id'], 'role_ok': False, 'verdict_ok': False, 'error': f'{type(error).__name__}: {error}'[:200]})
                continue
            rows.append(score_item(it, state.get('judgement')))
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"judge_dev_{time.strftime('%Y-%m-%d-%H%M')}.json"
    out.write_text(json.dumps({'summary': summarize(rows), 'rows': rows}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(summarize(rows), ensure_ascii=False), out)


if __name__ == '__main__':
    main(sys.argv[1])
