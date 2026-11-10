import json
from pathlib import Path

import pytest

from backend.multi_agent.agents import docs as D


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    def deny(*a, **k):
        pytest.fail('Paid provider/database/network forbidden in citation replay')
    for name in ('backend.services.llm.node_chat', 'httpx.post', 'psycopg.connect', 'socket.socket.connect'):
        monkeypatch.setattr(name, deny)


def smoke_cards():
    # Original smoke source cards; the actual paid JSONL remains untouched.
    rows=[json.loads(s) for s in Path('data/demo/snapshot/chunks.jsonl').read_text(encoding='utf-8').splitlines()]
    return [dict(chunk_id=r['idx']+1,file=r['doc'],page=r['page'],table=r['table'],content=r['text'],doc_parts=r['parts'])
            for r in rows if r['doc']=='1N4001G SERIES_P2104.pdf' and r['idx'] in (15,4)]


def citation_replay(answers):
    cards=smoke_cards()
    calls=[];searches=[];queue=list(answers)
    def chat(node,system,user,schema):
        calls.append(user)
        assert queue, 'Citation repair must be bounded'
        reply=queue.pop(0)
        if isinstance(reply,Exception):
            raise reply
        return reply
    payload={'question':'1N4007G의 VRRM과 패키지를 알려 주세요.','task':dict(id=1,agent='docs',kind='rating',
             goal='VRRM and package',query='1N4007G VRRM',parts=['1N4007G'])}
    result=D.docs_agent(payload,retriever=lambda q,parts=None:searches.append(q) or cards,chat=chat)['reports'][0]
    return result,calls,searches


@pytest.mark.parametrize('old_answer',[
    '1N4007G의 반복 최대 역전압(VRRM) 정격은 1000 V입니다 [1N4001G SERIES_P2104.pdf · 1쪽 · ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)].',
    '1N4007G의 반복 최대 역전압 VRRM은 1000 V입니다 [1N4001G SERIES_P2104.pdf · 1쪽 · ABSOLUTE MAXIMUM RATINGS, 1N 4007G 열].',
    '1N4007G의 반복 최대 역전압 VRRM은 1000 V입니다 [1]. 이 값은 TA = 25°C 기준 절대 최대 정격 표에 적혀 있습니다 [1].',
    '1N4007G의 반복 최대 역전압 VRRM 정격은 1000 V입니다 [1]. 패키지는 DO-204AL (DO-41)입니다 [5].',
])
def test_saved_smoke_citation_errors_can_be_repaired_only_with_provided_ids(old_answer):
    fixed='1N4007G의 VRRM은 1000 V입니다 [16]. 패키지는 DO-204AL (DO-41)입니다 [5].'
    result,calls,searches=citation_replay([D.DocsAnswer(grade='enough',answer=old_answer),D.DocsAnswer(grade='enough',answer=fixed)])
    assert result['status']=='ok' and result['answer']==fixed
    assert result['evidence_ids']==['16','5'] and result['llm_calls']==2
    assert len(calls)==2 and len(searches)==1
    assert 'Allowed citation IDs:' in calls[0] and '[16]' in calls[0] and '[5]' in calls[0]
    assert 'Citation correction' in calls[1]


def test_persistently_invalid_citation_is_not_remapped_to_first_card_or_page():
    bad=D.DocsAnswer(grade='enough',answer='VRRM은 1000 V입니다 [1].')
    result,calls,searches=citation_replay([bad,bad])
    assert result['status']=='fail' and result['reason']=='verify_failed'
    assert len(calls)==2 and len(searches)==1


def test_failed_repair_keeps_supported_package_but_reports_partial():
    bad=D.DocsAnswer(grade='enough',answer='VRRM은 1000 V입니다 [1]. 패키지는 DO-41입니다 [5].')
    result,calls,_=citation_replay([bad,bad])
    assert result['status']=='partial' and '1000' not in result['answer']
    assert result['evidence_ids']==['5'] and len(calls)==2


def test_valid_citation_needs_no_repair_and_preserves_value():
    result,calls,_=citation_replay([D.DocsAnswer(grade='enough',answer='VRRM은 1000 V입니다 [16].')])
    assert result['status']=='ok' and '1000' in result['answer'] and len(calls)==1


def test_two_searches_and_one_citation_repair_are_bounded():
    result,calls,searches=citation_replay([
        D.DocsAnswer(grade='none',next_query='1N4007G ratings'),
        D.DocsAnswer(grade='enough',answer='VRRM은 1000 V입니다 [1].'),
        D.DocsAnswer(grade='enough',answer='VRRM은 1000 V입니다 [16].')])
    assert result['status']=='ok' and result['llm_calls']==3 and len(calls)==3 and len(searches)==2


def test_historical_citation_cannot_be_laundered_by_repair():
    result,calls,_=citation_replay([D.DocsAnswer(grade='enough',answer='VRRM은 1000 V입니다 [승인사례:owned:1].')])
    assert result['status']=='fail' and len(calls)==1


def test_repaired_historical_citation_is_still_rejected():
    result,calls,_=citation_replay([
        D.DocsAnswer(grade='enough',answer='VRRM은 1000 V입니다 [1].'),
        D.DocsAnswer(grade='enough',answer='VRRM은 1000 V입니다 [16, 승인사례:owned:1].')])
    assert result['status']=='fail' and result['reason']=='verify_failed' and len(calls)==2


def test_citation_repair_does_not_swallow_shared_budget_stop():
    from backend.services.llm import EvaluationLimitError
    with pytest.raises(EvaluationLimitError):
        citation_replay([D.DocsAnswer(grade='enough',answer='VRRM은 1000 V입니다 [1].'),EvaluationLimitError('cap')])


def test_two_document_tasks_keep_corrected_vrrm_in_final_graph_answer():
    from backend.multi_agent.build import build_graph
    from backend.multi_agent.contracts import Plan, Task
    calls=[]
    def chat(node,system,user,schema):
        calls.append(node)
        if node=='supervisor':
            return Plan(question_type='rating',next='tasks',tasks=[
                Task(id=1,agent='docs',kind='rating',goal='voltage',query='1N4007G VRRM',parts=['1N4007G']),
                Task(id=2,agent='docs',kind='rating',goal='package',query='1N4007G case',parts=['1N4007G'])])
        assert node=='docs_answer', 'Validated document replies should join without a new synth call'
        if '- goal: package' in user:
            return D.DocsAnswer(grade='enough',answer='패키지는 DO-41입니다 [5].')
        cite='16' if 'Citation correction' in user else '1'
        return D.DocsAnswer(grade='enough',answer=f'VRRM은 1000 V입니다 [{cite}].')
    graph=build_graph(chat=chat,retriever=lambda *a,**k:smoke_cards(),
        parse=lambda s:dict(question=s['input'],conditions='',target='',target_part={}))
    state=graph.invoke({'input':'1N4007G의 VRRM과 패키지를 알려 주세요.'})
    assert '1000 V' in state['answer'] and 'DO-41' in state['answer']
    assert not state['refusal'] and state['check']['used']==['16','5']
    assert calls.count('docs_answer')==3 and calls.count('supervisor')==1 and 'synth' not in calls

def test_variant_part_pulls_part_rule_notes():
    # [왜] SMAJ6.5CA(양방향)를 물으면 값 표는 SMAJ6.5A 행뿐이다. 품번 규칙 주석('양방향 모두 적용' · 'IR 한도 2배')을 더 찾아 붙여야 답한다(v3-19, 11-09)
    from backend.multi_agent.agents.docs import variant_notes
    note = {'chunk_id': 9, 'file': 'SMAJ.pdf', 'page': 3, 'table': 'ELECTRICAL SPECIFICATIONS 주석',
            'content': '[SMAJ.pdf · 3쪽 · ELECTRICAL SPECIFICATIONS 주석] 4. For bi-directional devices having VR of 10V and under, the IR limit is double'}
    calls = []
    got = variant_notes(['SMAJ6.5CA'], [], lambda q, parts=None: calls.append(parts) or [note])
    assert got == [note] and calls == [['SMAJ6.5CA']]
    assert variant_notes(['SMAJ6.5A'], [], lambda q, parts=None: [note]) == []  # 기본 품번이면 더 찾지 않는다


def test_note_card_is_not_other_part_row():
    from backend.graph.nodes import other_part_row
    note = {'table': 'ABSOLUTE MAXIMUM RATINGS 주석', 'doc_parts': ['smaj5.0', 'smaj188', 'smaj6.5ca'],
            'content': '[SMAJ.pdf · 1쪽 · ABSOLUTE MAXIMUM RATINGS 주석] For bidirectional use C or CA suffix for types SMAJ5.0 - Types SMAJ188'}
    assert other_part_row(note, ['SMAJ6.5CA']) is False


def test_case_citation_cleanup_preserves_only_provided_sources():
    from backend.multi_agent.agents.docs import drop_fake_citations
    text = ('과거 승인 사례 [승인사례:owned:1, 승인사례:foreign:1]. '
            '현재 연결 [넷리스트, 승인사례:foreign:1].')
    answer, fake = drop_fake_citations(text, {'넷리스트', '승인사례:owned:1'})
    assert fake == ['승인사례:foreign:1']
    assert '승인사례:owned:1' in answer and '넷리스트' in answer and 'foreign' not in answer


def test_docs_separates_historical_references_from_current_answer():
    from backend.multi_agent.agents.docs import docs_agent, DocsAnswer
    from backend.multi_agent.contracts import Task
    memory = {'thread_id': 'owned', 'version': 1, 'part': 'SS34', 'approved_at': '2026-11-09', 'summary': '승인됨', 'context': None}
    payload = {'task': Task(id=1, agent='docs', kind='role', goal='explain').model_dump(mode='json'),
               'question': '현재 회로 설명', 'target_part': {'ref': 'D1', 'value': 'SS34', 'footprint': '', 'nets': []},
               'approved_memories': [memory]}
    for cite in ('승인사례:owned:1', '넷리스트, 승인사례:owned:1'):
        out = docs_agent(payload, retriever=None, chat=lambda *args: DocsAnswer(grade='enough', answer=f'허용 전압 999V [{cite}].'))
        assert out['reports'][0]['status'] == 'fail'
    good = docs_agent(payload, retriever=None, chat=lambda *args: DocsAnswer(
        grade='enough', answer='대상은 D1입니다 [넷리스트].', memory_refs=['승인사례:owned:1']))
    assert good['reports'][0]['memory_refs'] == ['승인사례:owned:1']
    bad = docs_agent(payload, retriever=None, chat=lambda *args: DocsAnswer(
        grade='enough', answer='대상은 D1입니다 [넷리스트].', memory_refs=['승인사례:foreign:1']))
    assert bad['reports'][0]['status'] == 'fail'
