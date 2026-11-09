"""명시적 앱 데모 전용 합성 응답·도구. 네트워크/모델/운영 DB 접근 없음."""
import json
import os
import re
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[2] / 'data/demo/scenarios.json'


def enabled():
    if os.getenv('DEMO_SCENARIOS') != '1':
        return False
    if os.getenv('DEMO_MODE') != '1':
        raise ValueError('합성 시나리오는 DEMO_MODE=1에서만 사용할 수 있습니다.')
    return True


def configuration():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def validate_question(text, conditions):
    from fastapi import HTTPException
    if text not in configuration()['questions'].values() or conditions:
        raise HTTPException(422, '합성 데모의 지원 질문을 선택하세요. 조건은 재개 질문에 입력하세요.')


def chat(node, system, user, schema):
    data = configuration()
    if node == 'supervisor':
        question = user.split('\nTarget part:', 1)[0]
        kind = max(data['questions'], key=lambda k: question.rfind(data['questions'][k]))
        if data['questions'][kind] not in question:
            raise ValueError('등록되지 않은 합성 데모 질문입니다.')
        if kind == 'refuse':
            return schema(question_type='rating', next='refuse', reason='not_found')
        task = 'candidate_judge' if kind == 'judge' else 'role'
        return schema(question_type=task, next='tasks', tasks=[{'id':1,'agent':'judge' if kind=='judge' else 'docs',
            'kind':task,'goal':'Explain or judge the synthetic demo circuit only.'}])
    if node == 'judge_read':
        return schema(role='R01', role_evidence=['합성 D1.K → RAW, D1.A → INPUT'],
                      original_part=data['original'], candidates=[data['candidate']])
    if node == 'docs_answer':
        refs = re.findall(r'"source": "(승인사례:[^"\\]+)"', user)
        return schema(grade='enough',answer=data['role_answer'],memory_refs=list(dict.fromkeys(refs))[:5])
    raise ValueError('합성 데모에 등록되지 않은 노드입니다.')


def lookup(state):
    from backend.multi_agent.supervisor import Facts
    return Facts(parts={p:True for p in configuration()['parts']})


def specs(part, codes=None):
    data = configuration(); values = data['parts'].get(part.upper(), {})
    rows = []
    for index, (code, value) in enumerate([*values.items(), ('PACKAGE','DO-41')], 1):
        if not values or (codes is not None and code not in codes):
            continue
        rows.append({'part':part.upper(),'category':'standard-rectifier','code':code,
            'min':None,'typ':None,'max':None if code=='PACKAGE' else value,
            'text':value if code=='PACKAGE' else None,'unit':'V' if code=='VRRM' else 'A' if code!='PACKAGE' else None,
            'source_value_text':str(value),'test_condition':None,
            'citation':{'document':data['document'],'page':1,'table':'합성 사양','row':code,'chunk_index':index}})
    return rows
