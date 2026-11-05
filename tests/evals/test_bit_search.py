"""비트 후보 + 정확 재정렬 실측(scripts/bit_search/bit_search_exp.py)과 저장소의 결과 파일 시험.

- 역할: recall@50·상위 5 일치 계산 규칙, 결과 파일에서 다시 계산한 값이 문서(docs/research/bit-search-measurement-2026-11-03.md)의 값과 같은지 확인한다.
- 하지 않는 일: DB를 부르지 않는다(측정 당시 운영 DB는 지금 없다).
- 출처: scripts/bit_search/bit_search_exp.py, scripts/results/bit_search/bit_search_2026-11-03.json
"""
import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('bit_search_exp', ROOT / 'scripts/bit_search/bit_search_exp.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)
RES = json.load(open(ROOT / 'scripts/results/bit_search/bit_search_2026-11-03.json', encoding='utf-8'))


def test_scores_treats_equal_distance_as_same_rank():
    assert B.scores([[1, 0.1], [2, 0.2]], [[3, 0.1], [2, 0.2]]) == (1.0, True)
    assert B.scores([[1, 0.1], [2, 0.2]], [[1, 0.1], [9, 0.3]]) == (0.5, False)


def test_stored_result_reproduces_documented_recall_and_top5_counts():
    qs = RES['questions']
    assert len(qs) == 50
    expected = {400: (0.771, 31), 800: (0.872, 40), 1600: (0.949, 47), 3200: (0.980, 49)}
    for n, (recall, top5) in expected.items():
        r = [B.scores(q['exact'], q[f'bq{n}']) for q in qs]
        assert round(float(np.mean([x for x, _ in r])), 3) == recall
        assert sum(t for _, t in r) == top5


def test_stored_result_relevant_only_counts():
    rel = [q for q in RES['questions'] if q['kind'] == 'relevant']
    assert len(rel) == 25
    assert sum(B.scores(q['exact'], q['bq3200'])[1] for q in rel) == 25
    assert sum(B.scores(q['exact'], q['bq1600'])[1] for q in rel) == 23


def test_final_step_ranks_match_between_exact_and_bit():
    final = json.load(open(ROOT / 'scripts/results/bit_search/bit_search_final_2026-11-03.json', encoding='utf-8'))
    assert final['differ_id_rank_exact_bit'] == []  # 19문항 모두 상위 5장이 같았다
    s = final['summary']
    for k in ('doc_recall@5', 'doc_mrr', 'page_hit@5'):
        assert s['exact'][k] == s['bit3200'][k]  # 0.737 · 0.649 · 0.368
    assert s['exact']['sec_p50'] > 5 * s['bit3200']['sec_p50']
