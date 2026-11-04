"""검색 조합 층별 재측정 실행기(run_retrieval_layers.py)와 저장소의 층별 결과 파일 시험.

- 역할: 토큰화·nDCG·판정(개선/같음/악화) 규칙, 층 결과 파일의 요약이 문항별 값의 평균과 같은지, 나머지 스크립트 문법을 확인한다.
- 하지 않는 일: DB·API·GPU를 부르지 않는다. 측정은 evals/runners/run_retrieval_layers.py 명령으로 손으로 돌린다.
- 출처: evals/runners/run_retrieval_layers.py, evals/results/retrieval/retrieval_layer*_2026-11-03.json
"""
import ast
import importlib
import json
import os
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / 'evals/results/retrieval'


@pytest.fixture(scope='module')
def L():
    # [왜] 이 모듈은 불러오는 순간 DEMO_MODE=0·LLM_PROVIDER=openrouter를 환경에 써서, 다른 시험에 새지 않게 끝나면 되돌린다
    with mock.patch.dict(os.environ):
        yield importlib.import_module('evals.runners.run_retrieval_layers')


def rows(metric, values):
    return {'rows': [{metric: v} for v in values]}


def test_selfcheck_tokenizers_and_dcg(L):
    L.selfcheck()


def test_verdict_needs_net_five_and_interval_above_zero(L):
    base = rows('page@5', [0] * 8)
    assert L.verdict(base, rows('page@5', [1] * 6 + [0] * 2), 'page@5')[:2] == ('개선', 6)
    assert L.verdict(base, rows('page@5', [1] * 4 + [0] * 4), 'page@5')[:2] == ('같음', 4)  # 1~4문항 차이는 개선이 아니다
    assert L.verdict(rows('page@5', [1] * 8), rows('page@5', [0] * 8), 'page@5')[:2] == ('악화', -8)
    assert L.verdict(base, base, 'ndcg@5') == ('n/a', 0, (None, None))


def test_choose_carries_baseline_when_nothing_improves(L):
    mk = lambda n, v: {'name': n, 'summary': {'page@5': 0.5, 'ndcg@5': 0.5, 'mrr@5': 0.5},
                       'rows': [{'page@5': v, 'ndcg@5': v}] * 8}
    base, same = mk('base', 0), mk('same', 0)
    win, ties = L.choose(base, [base, same], 3)
    assert win['name'] == 'base' and [t['name'] for t in ties] == ['same']


@pytest.mark.parametrize('n', [1, 2, 3, 4])
def test_layer_file_summaries_equal_row_means(n):
    cells = json.load(open(RES / f'retrieval_layer{n}_2026-11-03.json', encoding='utf-8'))['cells']
    assert cells
    for c in cells:
        for k, v in c['summary'].items():
            if '@' in k:
                assert v == round(float(np.mean([r[k] for r in c['rows']])), 3), (c['name'], k)


def test_layer1_has_documented_42_cells_and_layer0_all_checks_present():
    assert len(json.load(open(RES / 'retrieval_layer1_2026-11-03.json', encoding='utf-8'))['cells']) == 42
    l0 = json.load(open(RES / 'retrieval_layer0_2026-11-03.json', encoding='utf-8'))['summary']
    assert set(l0) >= {'1_cards', '2_vectors', '3_exact_top50', '4_service_top5'}


@pytest.mark.parametrize('path', ['evals/runners/check_retrieval_db.py', 'evals/runners/report_retrieval_layers.py',
                                  'scripts/hf_jobs/hf_job.py', 'scripts/hf_jobs/hf_data.py'])
def test_other_measurement_scripts_parse(path):
    ast.parse((ROOT / path).read_text(encoding='utf-8'))  # [왜] torch·huggingface·DB 없이는 불러올 수 없어 문법만 본다
