"""채점기 기준선 계산(evals/runners/eval_grader.py)과 입력 스냅샷 시험.

- 역할: 충분 · 부분 · 부족 판정 규칙, 지표 계산, 스냅샷 만들기, 스냅샷이 사전 등록 #33의 숫자를 재현하는지 확인한다.
- 하지 않는 일: LLM · API · DB를 부르지 않는다.
- 출처: evals/guides/preregister.md #33, evals/inputs/grader_cases_v2.json
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
