"""채점기 기준선 계산(evals/runners/eval_grader.py)과 입력 스냅샷 시험.

- 역할: 충분 · 부분 · 부족 판정 규칙, 지표 계산, 스냅샷 만들기, 스냅샷이 사전 등록 #36의 숫자를 재현하는지 확인한다.
- 하지 않는 일: LLM · API · DB를 부르지 않는다.
- 출처: evals/guides/preregister.md #36, evals/inputs/grader_cases_v2.json
"""
import json
from pathlib import Path

from evals.runners import eval_grader as G

ROOT = Path(__file__).resolve().parents[2]


def case(cid, kind, required, retrieved, passed, unrecoverable=()):
    """시험용 문항. retrieved는 [(청크 번호, 파일, 쪽)], required · unrecoverable는 [(파일, 쪽)]."""
    return {'id': cid, 'kind': kind, 'required_pages': [list(p) for p in required],
            'unrecoverable': [list(p) for p in unrecoverable],
            'retrieved': [{'chunk_id': c, 'file': f, 'page': p} for c, f, p in retrieved], 'passed': list(passed)}


def test_verdict_all_some_none():
    need = {('a.pdf', 1), ('a.pdf', 2)}
    assert G.verdict(need, {('a.pdf', 1), ('a.pdf', 2), ('b.pdf', 1)}) == '충분'
    assert G.verdict(need, {('a.pdf', 1)}) == '부분'
    assert G.verdict(need, {('b.pdf', 1)}) == '부족'
    assert G.verdict(need, set()) == '부족'


def test_evaluate_retention_table_and_recall():
    cases = [
        # 검색에 정답 쪽이 다 있고 채점도 다 통과시킴
        case('r1', 'relevant', [('a.pdf', 1)], [('1', 'a.pdf', 1), ('2', 'b.pdf', 3)], ['1']),
        # 검색엔 다 있는데 채점이 정답 쪽을 버림
        case('r2', 'relevant', [('a.pdf', 1), ('a.pdf', 2)], [('3', 'a.pdf', 1), ('4', 'a.pdf', 2)], ['3']),
        # 검색 자체가 일부만 가져옴(회수 불가 쪽은 필요 쪽에서 뺀다)
        case('r3', 'relevant', [('a.pdf', 1), ('a.pdf', 9)], [('5', 'a.pdf', 1)], ['5'], unrecoverable=[('a.pdf', 9)]),
        case('n1', 'irrelevant', [], [('6', 'a.pdf', 1)], []),
        case('n2', 'irrelevant', [], [('7', 'a.pdf', 1)], ['7']),
    ]
    r = G.evaluate(cases)
    assert r['relevant'] == 3 and r['irrelevant'] == 2
    assert r['retrieved_sufficient'] == 3 and r['retention'] == {'kept': 2, 'of': 3}  # r3도 회수 불가 쪽을 뺀 필요 쪽으로는 충분
    assert r['table'] == {'충분>부분': 1, '충분>충분': 2}
    assert r['irrelevant_zero_pass'] == {'zero': 1, 'of': 2}
    assert r['page_recall_mean'] == round((1 + 0.5 + 1) / 3, 3)


def test_build_cases_uses_ids_and_pages_only():
    roots = [{'name': 'graph q1', 'output': json.dumps({
        'docs': [{'chunk_id': '10', 'file': 'a.pdf', 'page': '2', 'content': '데이터시트 글'},
                 {'chunk_id': '11', 'file': 'a.pdf', 'page': 'None', 'content': '표지'}], 'passed': [10]})}]
    qrels = {'q1': {'pages': [['a.pdf', 2], ['a.pdf', 5]], 'unrecoverable': [['a.pdf', 5]]}}
    rows = [{'id': 'q1', 'kind': 'relevant'}]
    out = G.build_cases(roots, qrels, rows)
    c = out[0]
    assert c['retrieved'] == [{'chunk_id': '10', 'file': 'a.pdf', 'page': 2}, {'chunk_id': '11', 'file': 'a.pdf', 'page': None}]
    assert c['passed'] == ['10'] and c['unrecoverable'] == [['a.pdf', 5]]
    assert 'content' not in json.dumps(out)  # 데이터시트 글은 저장하지 않는다


def test_snapshot_reproduces_preregistered_baseline():
    snap = json.load(open(ROOT / 'evals/inputs/grader_cases_v2.json', encoding='utf-8'))
    r = G.evaluate(snap['cases'])
    assert (r['relevant'], r['irrelevant']) == (19, 35)
    assert r['retrieved_sufficient'] == 15 and r['retention'] == {'kept': 12, 'of': 15}
    assert {k: v for k, v in r['table'].items()} == {'충분>충분': 12, '충분>부분': 2, '충분>부족': 1, '부분>부분': 4}
    assert r['irrelevant_zero_pass'] == {'zero': 34, 'of': 35}


def test_snapshot_has_no_datasheet_text():
    text = (ROOT / 'evals/inputs/grader_cases_v2.json').read_text(encoding='utf-8')
    assert '"content"' not in text


def test_case_from_state_normalizes_pages_and_drops_text():
    docs = [{'chunk_id': 7, 'file': 'a.pdf', 'page': '3', 'content': '데이터시트 글'},
            {'chunk_id': '8', 'file': 'a.pdf', 'page': None, 'content': '표지'}]
    c = G.case_from_state('q', 'relevant', [['a.pdf', 3]], [], docs, [7])
    assert c['retrieved'] == [{'chunk_id': '7', 'file': 'a.pdf', 'page': 3}, {'chunk_id': '8', 'file': 'a.pdf', 'page': None}]
    assert c['passed'] == ['7'] and 'content' not in json.dumps(c)


def test_collect_runs_retrieve_then_grade_per_question_and_skips_errors():
    rows = [{'id': 'r1', 'question': 'Q 1N4148', 'gold': [['a.pdf', 1]]}, {'id': 'r2', 'question': 'Q2', 'gold': [['b.pdf', 2]]}]
    queries = {'r1': 'query one', 'r2': 'query two'}
    seen = []

    def retrieve(query, parts=None):
        seen.append((query, parts))
        if query == 'query two':
            raise RuntimeError('검색 실패')
        return [{'chunk_id': 1, 'file': 'a.pdf', 'page': '1', 'content': 'x'}]

    cases, errors = G.collect(rows, queries, lambda q, refs: ['1N4148'] if '1N4148' in q else [], retrieve,
                              lambda state: {'passed': [1]})
    assert seen == [('query one', ['1N4148']), ('query two', None)]  # 품번이 없으면 None으로 코퍼스 전체
    assert [c['id'] for c in cases] == ['r1'] and cases[0]['passed'] == ['1'] and errors == ['r2']


def test_collect_stops_after_three_errors_in_a_row():
    rows = [{'id': f'r{i}', 'question': 'q', 'gold': [['a.pdf', 1]]} for i in range(5)]

    def boom(query, parts=None):
        raise RuntimeError('x')

    import pytest
    with pytest.raises(RuntimeError, match='연속'):
        G.collect(rows, {r['id']: 'q' for r in rows}, lambda q, refs: [], boom, lambda state: {'passed': []})


def test_r1_dev_snapshot_reproduces_registered_result():
    snap = json.load(open(ROOT / 'evals/inputs/grader_cases_r1_dev.json', encoding='utf-8'))
    r = G.evaluate(snap['cases'])
    assert (r['relevant'], r['irrelevant']) == (46, 0)
    assert r['retrieved_sufficient'] == 39 and r['retention'] == {'kept': 36, 'of': 39}
    assert r['table'] == {'부분>부분': 1, '부족>부족': 6, '충분>부분': 1, '충분>부족': 2, '충분>충분': 36}
    assert r['page_recall_mean'] == 0.804
    assert '"content"' not in (ROOT / 'evals/inputs/grader_cases_r1_dev.json').read_text(encoding='utf-8')
