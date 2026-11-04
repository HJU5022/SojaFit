"""임베딩 격자 본평가 실행기(embed_cards.py, run_embedding_grid.py)와 저장소의 결과 파일 시험.

- 역할: 문항 읽기(동결 v1에서 19건), 순위·쪽 적중 계산, 요약, 카드 묶기 규칙, 모델 표와 결과 파일의 일치를 확인한다.
- 하지 않는 일: DB·임베딩·리랭크 API를 부르지 않는다. 실제 측정은 evals/docker/DOCKER.md의 컨테이너에서 손으로 돌린다.
- 출처: evals/runners/run_embedding_grid.py, evals/runners/embed_cards.py, evals/results/embedding/grid_*_2026-11-02.json
"""
import json
from pathlib import Path

from evals.runners import embed_cards as E
from evals.runners import run_embedding_grid as G

ROOT = Path(__file__).resolve().parents[2]
GRID = json.load(open(ROOT / 'evals/results/embedding/grid_2026-11-02.json', encoding='utf-8'))


def test_load_questions_reads_19_relevant_questions_with_gold(monkeypatch):
    monkeypatch.setattr(G, 'DATASET', str(ROOT / 'evals/dataset_v1.jsonl'))  # [왜] 원래 값은 컨테이너 경로(/work/repo)다
    qs = G.load_questions()
    assert len(qs) == 19  # 관련 25건 중 데이터시트 gold가 있는 것
    assert all(set(v) == {'input', 'question'} and v['question'] for _, _, v in qs)


def test_score_rank_page_hit_and_all_gold():
    meta = {1: ('a.pdf', 1), 2: ('b.pdf', 2), 3: ('a.pdf', 3)}
    gold = [('a.pdf', 3), ('a.pdf', 9)]
    assert G.score([2, 1, 3], meta, gold) == (2, True, False)  # 정답 문서는 2위, 정답 쪽은 있으나 gold 쪽이 다 들어오진 않음
    assert G.score([2], meta, gold) == (None, False, False)
    assert G.score([3], meta, [('a.pdf', 3)]) == (1, True, True)


def test_summarize_means_and_percentiles():
    rows = [{'rank': 1, 'page_hit': True, 'all_gold': True, 'search_sec': 0.1},
            {'rank': 2, 'page_hit': False, 'all_gold': False, 'search_sec': 0.3},
            {'rank': None, 'page_hit': False, 'all_gold': False, 'search_sec': 0.2}]
    s = G.summarize(rows)
    assert (s['doc_recall@5'], s['doc_mrr'], s['page_hit@5'], s['multi_gold@5']) == (0.667, 0.5, 0.333, 0.333)
    assert s['search_p50_p95'] == [0.2, 0.29] and 'embed_p50_p95' not in s


def test_stored_grid_cells_match_recomputed_summaries():
    assert len(GRID['cells']) == 78  # 모델 6 × 2(dense·hybrid) × 3(리랭커) × 2(질의 글) + BM25 6칸
    for c in GRID['cells']:
        assert G.summarize(c['rows']) == c['summary'], (c['model'], c['method'], c['reranker'], c['variant'])


def test_models_table_matches_stored_embed_logs():
    logs = GRID['meta']['embed_logs']
    for key, log in logs.items():
        assert E.MODELS[key]['name'].endswith(log['model']) and E.MODELS[key]['dim'] == log['dim']
        assert log['runs'][-1]['cards'] == 52244 == log['runs'][-1]['table_rows']


def test_batches_split_by_count_and_by_token_limit():
    text = {f's{i}': 'x' * 100 for i in range(300)}
    parts = list(E.batches(list(text), text, E.MODELS['v4large']))
    assert all(len(p) <= E.BATCH for p in parts) and sum(map(len, parts)) == 300
    long = {'a': 'x' * 200_000, 'b': 'x' * 200_000}  # 글자 수 / 2로 어림한 토큰이 한도(max_tokens / 2)를 넘으면 따로 보낸다
    assert [len(p) for p in E.batches(['a', 'b'], long, E.MODELS['v4large'])] == [1, 1]
    local = list(E.batches([str(i) for i in range(E.ST_BLOCK + 1)], {}, E.MODELS['kure']))
    assert [len(p) for p in local] == [E.ST_BLOCK, 1]
