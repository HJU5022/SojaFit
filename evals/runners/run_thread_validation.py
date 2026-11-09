"""동결 v2의 작은 품질 평가 준비. --execute 없이 API/DB를 호출하지 않는다."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def usage_rows(runs):
    """LangChain trace에서 청구 대조용 필드만 추출하고 본문은 버린다."""
    rows = []
    for run in runs:
        if run.run_type == 'llm':
            metadata = (run.outputs or {}).get('llm_output') or {}
            usage = metadata.get('token_usage') or {}
            cost = usage.get('cost')
            if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
                cost = None
            rows.append({'response_id': metadata.get('id'), 'model': metadata.get('model_name'),
                         'prompt_tokens': usage.get('prompt_tokens'), 'completion_tokens': usage.get('completion_tokens'),
                         'reported_cost_usd': cost})
        rows.extend(usage_rows(run.child_runs or []))
    return rows


def cost_total(rows):
    # 응답 없는 실패·누락 비용을 공짜로 집계하지 않는다.
    return sum(r['reported_cost_usd'] for r in rows) if rows and all(r['reported_cost_usd'] is not None for r in rows) else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ids', nargs='+', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    dataset = root/'evals/dataset_v2.jsonl'
    frozen = json.loads((root/'evals/FROZEN.json').read_text(encoding='utf-8'))
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    if digest != frozen[dataset.name]['sha256']:
        raise ValueError('동결 평가셋 해시가 다릅니다.')
    ids = {json.loads(line)['id'] for line in dataset.read_text(encoding='utf-8').splitlines() if line.strip()}
    if not 1 <= len(args.ids) <= 4 or len(set(args.ids)) != len(args.ids) or set(args.ids)-ids:
        raise ValueError('존재하는 서로 다른 v2 ID를 1~4개 지정하세요.')
    usage_path = args.out.with_suffix('.usage.json')
    if args.out.exists() or usage_path.exists():
        raise FileExistsError('기존 평가 결과를 덮어쓰지 않습니다.')
    limits = {'max_usd':0.50, 'max_calls':16, 'max_seconds':90, 'max_tokens':4096}
    print(json.dumps({'execute':args.execute,'ids':args.ids,'dataset_sha256':digest,'limits':limits}))
    if not args.execute:
        return 0

    from langchain_core.tracers.context import collect_runs
    from backend.services import llm
    from evals.runners import run_graph
    if llm.LLM_PROVIDER != 'openrouter':
        raise ValueError('예산 검증은 OpenRouter 경로만 지원합니다.')
    # callback으로 Voyage도 서비스와 같은 호출별 예약·시간 경계를 활성화한다. DB 예산은 변경하지 않는다.
    budget = llm.EvaluationBudget(**limits, prompt_rate=0.000003, completion_rate=0.000015, on_reserve=lambda cost: None)
    original_chat, error_type = llm.chat, None
    with collect_runs() as collected:
        try:
            with llm.evaluation_limits(budget):
                run_graph.main(str(dataset), args.ids, str(args.out), multi=True)
        except Exception as error:
            error_type = type(error).__name__
        finally:
            llm.chat = original_chat
    rows = usage_rows(collected.traced_runs)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    failed = json.loads(args.out.read_text(encoding='utf-8')).get('failed', []) if args.out.exists() else []
    report = {'dataset_sha256':digest,'ids':args.ids,'limits':limits,'reservations_usd':budget.reserved_usd,
              'reserved_calls':budget.calls,'calls':rows,'reported_cost_total_usd':cost_total(rows),
              'missing_response_ids':sum(not r['response_id'] for r in rows),'error_type':error_type,
              'failed_items':len(failed),'billing_reconciled':False,
              'note':'Provider reports only. Reconcile Activity IDs and separate Voyage/infrastructure bills; missing/failed responses may still be billed.'}
    usage_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return 2 if error_type or failed or cost_total(rows) is None or report['missing_response_ids'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
