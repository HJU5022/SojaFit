"""서비스 경로 재측정 실행기(evals/runners/run_retrieval_service.py)의 순수 함수 시험.

- 역할: 지표 정의(적중 · 회수율 · 모든 근거 · MRR), R1 1위 칸과의 상위 5개 대조, 백분위, 파일 이름 대응, 오류 문항 건너뛰기를 가짜 retrieve로 확인한다.
- 하지 않는 일: DB · Voyage · OpenRouter를 부르지 않는다(실제 측정은 사전 등록 #26).
- 출처: evals/guides/preregister.md #26
"""
from evals.runners import run_retrieval_service as S


def test_metrics_match_d3_definitions():
    gold = [('A.pdf', 1), ('A.pdf', 2), ('A.pdf', 5)]
    m = S.metrics([('B.pdf', 1), ('A.pdf', 2), ('A.pdf', 1)], gold, rec=[('A.pdf', 1), ('A.pdf', 2)])
    assert m['page_hit@1'] == 0.0 and m['page_hit@3'] == 1.0 and m['page_mrr'] == 0.5
    assert abs(m['page_recall@5'] - 2 / 3) < 1e-9 and m['page_recall_rec@5'] == 1.0
    assert m['all_evidence@5'] == 0.0 and S.metrics([('A.pdf', 1)], [('A.pdf', 1)])['all_evidence@1'] == 1.0


def test_parity_counts_identical_and_lists_differences():
    r1 = [{'id': 'q1', 'top': [[1, 's', 'A.pdf', 1], [2, 's', 'A.pdf', 2]]}, {'id': 'q2', 'top': [[3, 's', 'B.pdf', 1], [4, 's', 'B.pdf', 2]]}]
    rows = [{'id': 'q1', 'top': [('A.pdf', 1), ('A.pdf', 2)]}, {'id': 'q2', 'top': [('B.pdf', 2), ('B.pdf', 1)]}, {'id': 'q3', 'error': 'X'}]
    p = S.parity(rows, r1)
    assert (p['n'], p['same'], p['different']) == (2, 1, 1)
    assert p['differences'][0]['id'] == 'q2' and p['differences'][0]['same_set'] is True


def test_percentiles_and_cap():
    assert S.pct([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50) == 5 and S.pct([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 95) == 10 and S.pct([], 50) is None
    assert S.over_cap(1.0) and not S.over_cap(0.99) and not S.over_cap(None)


def test_run_questions_maps_names_and_skips_errors():
    def fake(text, k, parts):
        if text == 'boom':
            raise RuntimeError('postgres://secret')
        return [{'file': 'x.pdf', 'document_key': 'tsc-a', 'page': 1}, {'file': 'B.pdf', 'document_key': 'tsc-b', 'page': 2}]
    qs = [{'id': 'q1', 'text': 'ok', 'parts': ['P1'], 'gold': [('A.pdf', 1)]}, {'id': 'q2', 'text': 'boom', 'parts': [], 'gold': [('A.pdf', 1)]}]
    rows = S.run_questions(qs, fake, {'A.pdf', 'B.pdf'}, {'tsc-a': 'A.pdf'})
    assert rows[0]['top'][0] == ('A.pdf', 1) and rows[0]['name_mapped'] == 1 and rows[0]['page_hit@1'] == 1.0
    assert rows[1] == {'id': 'q2', 'error': 'RuntimeError'}  # 오류 메시지(접속 정보 가능)는 남기지 않는다
