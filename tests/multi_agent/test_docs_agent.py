

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
