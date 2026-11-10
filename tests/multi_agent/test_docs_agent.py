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


# Exact voltage-task outputs from smoke02; source JSONL SHA256 starts 31d837ddcb67.
SAVED_SMOKE02_VOLTAGE = [
    '1N4007G의 반복 최대 역전압(VRRM)은 1000 V입니다[16]. 패키지는 증거에 명시되어 있지 않고, 넷리스트에서 D1의 패키지가 Diode:DO-41로 표기되어 있습니다[넷리스트]. 다만 이는 회로 내 부품 표기이므로 데이터시트 패키지 정보로 단정하지 않습니다.',
    '1N4007G의 반복 최대 역전압 VRRM 정격은 1000 V입니다 [1N4001G SERIES_P2104.pdf · 1쪽 · ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)의 VRRM 행을 근거로 함] [16]. 패키지는 증거 카드에 명시되어 있지 않아 답할 수 없습니다.',
    '1N4007G의 반복 최대 역전압 VRRM 정격은 1000 V입니다 [16]. 문서의 패키지 정보는 제공된 근거에 없으며, 극성 식별 방법도 근거에 없습니다.',
    '1N4007G의 반복 최대 역전압 VRRM 정격은 1000 V입니다 [16]. 이 값은 TA = 25°C 기준 절대 최대 정격 표에 적힌 값입니다 [16]. 패키지와 극성 식별 방법은 제공된 근거에 없어 답할 수 없습니다.',
]

# Exact T1-attack responses from smoke03 (raw SHA256 starts 097eda7c36ed).
SAVED_SMOKE03_VOLTAGE = [
    D.DocsAnswer(grade='enough', answer='1N4007G의 반복 최대 역전압 VRRM 정격은 1000 V입니다 [1N4001G SERIES_P2104.pdf · 1쪽 · ABSOLUTE MAXIMUM RATINGS]. 패키지는 증거에서 확인되지 않았습니다. 다만 넷리스트 D1 항목에 Diode:DO-41로 표기되어 있습니다 [넷리스트].', missing=['1N4007G 데이터시트 자체에서 패키지 명시 근거 없음 (넷리스트의 DO-41 표기는 회로 기준 정보)']),
    D.DocsAnswer(grade='enough', answer='1N4007G의 반복 피크 역전압 VRRM 정격은 1000 V입니다 [1N4001G SERIES_P2104.pdf · 1쪽 · ABSOLUTE MAXIMUM RATINGS (TA = 25°C unless otherwise noted)]. 시리즈 표에서 1N 4007G 열에 1000, 단위는 V로 기재되어 있습니다 [16]. 패키지 정보는 제공된 근거에 없어 확인할 수 없습니다.', missing=['1N4007G의 패키지 정보']),
]
SAVED_SMOKE03_SUPPORTED = '시리즈 표에서 1N 4007G 열에 1000, 단위는 V로 기재되어 있습니다 [16].'


def test_smoke03_keeps_existing_supported_sentence_without_fabricating_a_repair():
    report, calls, searches = citation_replay(SAVED_SMOKE03_VOLTAGE)
    assert report['status']=='partial' and report['answer']==SAVED_SMOKE03_SUPPORTED
    assert report['evidence_ids']==['16'] and report['missing']==['1N4007G의 패키지 정보']
    assert 'removed' in report['summary'] and len(calls)==2 and len(searches)==1
    source = next(d for d in report['docs'] if d['chunk_id']==16)
    assert 'SYMBOL: VRRM' in source['content'] and '1N 4007G: 1000 | UNIT: V' in source['content']


def test_smoke03_preserved_sentence_reaches_single_answer_and_multi_task_synth_input():
    from backend.multi_agent import supervisor as S
    report, _, _ = citation_replay(SAVED_SMOKE03_VOLTAGE)
    state = dict(question='1N4007G의 VRRM과 패키지?',reports=[report],plan={'next':'tasks'},round=1,counters={'hops':1})
    state.update(S.collect_node(state))
    assert state['outcome']=='single'
    state.update(S.single_node(state))
    state.update(S.check_node(state))
    assert state['answer']==SAVED_SMOKE03_SUPPORTED and not state.get('refusal_reason')
    assert state['check']['used']==['16'] and state['check']['uncited_sentences']==0
    package = dict(task=2,agent='docs',status='ok',summary='package',answer='패키지는 DO-41입니다 [5].',docs=smoke_cards(),evidence_ids=['5'])
    state.update(reports=[report,package],final_reports=[])
    state.update(S.collect_node(state))
    assert state['outcome']=='synth'
    text=S.render_synth(state,S.final_reports(state))
    assert SAVED_SMOKE03_SUPPORTED in text and '패키지 정보는 제공된 근거에 없어' not in text


def test_uncited_or_fake_only_reply_still_fails_without_inventing_citations():
    bad=D.DocsAnswer(grade='enough',answer='1N4007G의 VRRM은 1000 V입니다. 패키지는 DO-41입니다 [999].')
    report,calls,_=citation_replay([bad,bad])
    assert report['status']=='fail' and report['reason']=='verify_failed' and report['answer']==''
    assert len(calls)==2


def test_citation_does_not_transfer_to_an_adjacent_uncited_claim():
    mixed=D.DocsAnswer(grade='enough',answer='VRRM은 1000 V입니다 [16]. 1200 V에서도 사용을 승인합니다.')
    report,_,_=citation_replay([mixed,mixed])
    assert report['status']=='partial' and report['answer']=='VRRM은 1000 V입니다 [16].'
    assert '1200' not in report['answer'] and report['evidence_ids']==['16']


@pytest.mark.parametrize('saved', SAVED_SMOKE02_VOLTAGE)
def test_smoke02_uncited_absence_claim_requests_bounded_task_scoped_repair(saved):
    fixed = '1N4007G의 VRRM은 1000 V입니다 [16].'
    result, calls, _ = citation_replay([
        D.DocsAnswer(grade='enough', answer=saved), D.DocsAnswer(grade='enough', answer=fixed)])
    assert result['answer'] == fixed and result['status'] == 'ok'
    assert len(calls) == 2 and 'Citation correction' in calls[1]
    assert 'only the assigned task' in calls[1]


def test_smoke02_persisting_uncited_claim_is_removed_while_cited_fact_survives():
    saved = D.DocsAnswer(grade='enough', answer=SAVED_SMOKE02_VOLTAGE[2])
    result, calls, _ = citation_replay([saved, saved])
    assert result['status'] == 'partial' and result['reason'] is None
    assert result['answer'] == '1N4007G의 반복 최대 역전압 VRRM 정격은 1000 V입니다 [16].'
    assert '근거에 없습니다' not in result['answer'] and len(calls) == 2


def test_enough_with_missing_is_not_reported_as_complete():
    result, _, _ = citation_replay([D.DocsAnswer(grade='enough', answer='VRRM은 1000 V입니다 [16].', missing=['package'])])
    assert result['status'] == 'partial' and result['missing'] == ['package']


def test_smoke02_wrong_ordering_row_is_removed_and_cannot_support_package():
    rows = [json.loads(s) for s in Path('data/demo/snapshot/chunks.jsonl').read_text(encoding='utf-8').splitlines()]
    cards = [dict(chunk_id=r['idx']+1, file=r['doc'], page=r['page'], table=r['table'], content=r['text'], doc_parts=r['parts'])
             for r in rows if r['doc']=='1N4001G SERIES_P2104.pdf' and r['idx'] in (4,15,27,29)]
    kept = D.keep_docs(cards, ['1N4007G'], '1N4007G의 패키지')
    assert {d['chunk_id'] for d in kept} == {5,16,28}
    bad = D.DocsAnswer(grade='enough', answer='1N4007G의 VRRM 정격은 1000V이며, 1N4001G~1N4007G 시리즈 표에서 1N 4007G 값으로 제시됩니다 [16]. 패키지는 DO-204AL (DO-41)입니다 [30]. 문서는 극성을 음극 띠(cathode band)로 표시한다고 설명합니다 [5].')
    fixed = '1N4007G의 패키지는 DO-204AL (DO-41)입니다 [28]. 극성은 캐소드 밴드로 표시합니다 [5].'
    queue = [bad, D.DocsAnswer(grade='enough', answer=fixed)]
    calls = []
    def chat(node, system, user, schema):
        calls.append(user)
        return queue.pop(0)
    payload = {'question':'1N4007G의 패키지', 'task':dict(id=1,agent='docs',kind='rating',goal='package',query='package',parts=['1N4007G'])}
    report = D.docs_agent(payload,retriever=lambda *a,**k:cards,chat=chat)['reports'][0]
    assert report['evidence_ids'] == ['28','5'] and report['status'] == 'ok'
    assert all('[30]' not in call for call in calls) and len(calls)==2


@pytest.mark.parametrize('asked,allowed', [('1N4007G',{28}),('1N4007GH',{28,30}),('1N4002G',{28})])
def test_ordering_wildcard_preserves_suffix_and_base_row_for_h_variant(asked,allowed):
    rows = [json.loads(s) for s in Path('data/demo/snapshot/chunks.jsonl').read_text(encoding='utf-8').splitlines()]
    cards = [dict(chunk_id=r['idx']+1,file=r['doc'],page=r['page'],table=r['table'],content=r['text'],doc_parts=r['parts'])
             for r in rows if r['doc']=='1N4001G SERIES_P2104.pdf' and r['idx'] in (27,29)]
    assert {d['chunk_id'] for d in D.keep_docs(cards,[asked],asked)} == allowed


@pytest.mark.parametrize('saved', SAVED_SMOKE02_VOLTAGE)
def test_smoke02_corrected_task_replay_joins_without_absence_claims(saved):
    from backend.multi_agent.build import build_graph
    from backend.multi_agent.contracts import Plan, Task
    calls = []
    def chat(node,system,user,schema):
        calls.append(node)
        if node=='supervisor':
            return Plan(question_type='rating',next='tasks',tasks=[
                Task(id=1,agent='docs',kind='rating',goal='voltage',query='1N4007G VRRM',parts=['1N4007G']),
                Task(id=2,agent='docs',kind='rating',goal='package and polarity',query='1N4007G package',parts=['1N4007G'])])
        assert node=='docs_answer', 'Successful scoped reports must join without a synth call'
        if '- goal: voltage\n' in user:
            answer = '1N4007G의 VRRM은 1000 V입니다 [16].' if 'Citation correction' in user else saved
        else:
            answer = '패키지는 DO-41입니다 [5]. 극성은 캐소드 밴드로 표시합니다 [5].'
        return D.DocsAnswer(grade='enough',answer=answer)
    graph=build_graph(chat=chat,retriever=lambda *a,**k:smoke_cards(),
        parse=lambda s:dict(question=s['input'],conditions='',target='',target_part={}))
    state=graph.invoke({'input':'1N4007G의 VRRM과 패키지, 극성 식별 방법을 알려 주세요.'})
    assert not state['refusal'] and state['check']['fake_citations']==[] and state['check']['uncited_sentences']==0
    assert state['answer']=='1N4007G의 VRRM은 1000 V입니다 [16].\n\n패키지는 DO-41입니다 [5]. 극성은 캐소드 밴드로 표시합니다 [5].'
    assert calls.count('docs_answer')==3 and 'synth' not in calls


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
