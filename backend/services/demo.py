"""명시적 앱 데모 전용 합성 응답·도구와, 키 없는 데모의 LLM 응답 기록(recorder)·재생(replayer).

- 역할: 합성 시나리오(`DEMO_SCENARIOS=1`)의 응답·도구, 그리고 그래프의 `chat(node, system, user, schema)` 모양 함수 두 개.
  `recorder`는 실제 chat을 감싸 호출마다 한 줄(sha256 키 · 노드 · schema 이름 · 파싱한 응답)을 기록 파일에 붙이고,
  `replayer`는 같은 키의 기록 응답을 돌려준다. 기록에 없으면 노드 이름을 담아 `ReplayMiss`로 멈춘다.
- 하지 않는 일: 실제 LLM 호출(`llm.py`만 한다, AGENTS 지킬 것 2), 기록 실행 · 재생 확인(`scripts/demo/record_demo.py`),
  서비스에 재생 연결(아직 없음. `memory_service._graph()`가 할 일), 키 · 헤더 · 가격 기록(응답 칸만 쓴다).
- 출처: SPEC 7절(데모 모드), data/demo/DEMO.md, 과제 게이트 G2(키 없는 `docker compose up`)
"""
import hashlib
import json
import os
import re
import threading
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[2] / 'data/demo/scenarios.json'
RECORDING = Path(__file__).resolve().parents[2] / 'data/demo/recordings/calls.jsonl'  # 기록 응답 파일(record_demo.py가 만든다)


class ReplayMiss(RuntimeError):
    """재생할 기록이 없는 LLM 호출.

    [주의] ValueError로 바꾸지 않는다. Supervisor · 카드 읽기 노드가 형식 실패(ValueError)를 잡아 거절 답으로 바꾸므로,
    그 길로 새면 기록에 없는 질문에 그럴듯한 거절이 나간다(지어낸 답). RuntimeError는 그래프 밖까지 올라간다.
    """


def call_key(node, system, user, schema):
    """LLM 호출 한 번의 기록 키: (노드, system, user, schema 이름)의 sha256."""
    # [왜] 네 칸을 JSON 목록으로 묶어 해시한다. 글자를 그냥 이으면 칸 경계가 달라도 같은 글자가 되어 키가 겹칠 수 있다
    text = json.dumps([node, system, user, schema.__name__], ensure_ascii=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def recorder(chat, path=RECORDING):
    """chat을 감싸 호출마다 {sha256, node, schema, response} 한 줄을 path에 붙이는 chat을 돌려준다(유료 기록 실행 전용).

    같은 키가 다시 오면 LLM을 다시 부르지 않고 첫 응답을 준다(재생도 첫 응답만 주므로 기록과 재생이 같은 길을 간다).
    응답은 schema로 다시 검증한 값을 돌려준다(재생이 돌려줄 값과 같게).
    Raises:
        RuntimeError: chat이 형식을 끝내 어겼을 때(ValueError). 노드가 거절로 바꾼 길은 재생할 수 없어 기록을 멈춘다.
    """
    seen, lock = {}, threading.Lock()  # [왜] Send로 동시에 도는 에이전트 · 카드 읽기 스레드가 같은 파일에 쓴다

    def record(node, system, user, schema):
        key = call_key(node, system, user, schema)
        with lock:
            if key in seen:
                return schema.model_validate(seen[key])
        try:
            answer = chat(node, system, user, schema)
        except ValueError as error:
            raise RuntimeError(f'{node} 응답이 형식을 끝내 어겨 기록을 멈춥니다. 기록을 다시 돌리세요.') from error
        with lock:
            if key not in seen:  # [주의] 두 스레드가 같은 키를 동시에 불렀으면 먼저 쓴 응답 하나만 남기고 둘 다 그 응답을 받는다
                # [주의] 응답 칸(model_dump)만 쓴다. 키 · 헤더 · 모델 이름 · 비용은 이 함수가 받지도 않는다(AGENTS 지킬 것 4)
                seen[key] = answer.model_dump(mode='json')
                with open(path, 'a', encoding='utf-8') as out:
                    out.write(json.dumps({'sha256': key, 'node': node, 'schema': schema.__name__, 'response': seen[key]},
                                         ensure_ascii=False) + '\n')
            return schema.model_validate(seen[key])
    return record


def replayer(path=RECORDING):
    """기록 파일에서 같은 키의 응답을 schema로 검증해 돌려주는 chat. 파일이 없으면 만들 때 FileNotFoundError."""
    recorded = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            entry = json.loads(line)
            recorded.setdefault(entry['sha256'], entry['response'])

    def replay(node, system, user, schema):
        response = recorded.get(call_key(node, system, user, schema))
        if response is None:
            # [주의] 실제 LLM으로 넘어가거나 비슷한 기록을 고르지 않는다. 기록과 한 글자라도 다른 질문 · 회로 · 조건 · DB면 여기서 멈춘다
            raise ReplayMiss(f'기록에 없는 LLM 호출입니다(노드 {node}, {schema.__name__}). '
                             '데모는 기록한 질문 · 회로 · 조건을 새 대화의 첫 질문으로 보낼 때만 재생합니다.')
        return schema.model_validate(response)
    return replay


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
