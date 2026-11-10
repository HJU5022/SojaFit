"""키 없는 데모의 LLM 응답 기록(recorder) · 재생(replayer)과, 서비스가 재생할 데모 질문 목록 · 확인.

- 역할: 그래프의 `chat(node, system, user, schema)` 모양 함수 두 개와 서비스용 도구.
  `recorder`는 실제 chat을 감싸 호출마다 한 줄(sha256 키 · 노드 · schema 이름 · 파싱한 응답)을 기록 파일에 붙이고,
  `replayer`는 같은 키의 기록 응답을 돌려준다. 기록에 없으면 노드 이름을 담아 `ReplayMiss`로 멈춘다.
  `enabled`는 재생 모드(`DEMO_REPLAY=1`, `DEMO_MODE=1`이 함께 있어야 함)를, `questions` · `match`는 기록한 데모 질문(outcomes.json)을,
  `service_chat`은 서비스 그래프에 넣을 재생 chat(기록이 없으면 부를 때 503)을 돌려준다.
- 하지 않는 일: 실제 LLM 호출(`llm.py`만 한다, AGENTS 지킬 것 2), 기록 실행 · 재생 확인(`scripts/demo/record_demo.py`),
  키 · 헤더 · 가격 기록(응답 칸만 쓴다), 그래프 조립 · 요청 거절 자리(`memory_service.Conversations`).
- 출처: SPEC 7절(데모 모드), data/demo/DEMO.md, 과제 게이트 G2(키 없는 `docker compose up`), 조장 결정 11-10(기록 응답 재생)
"""
import hashlib
import json
import os
import threading
from pathlib import Path

from fastapi import HTTPException

RECORDING = Path(__file__).resolve().parents[2] / 'data/demo/recordings/calls.jsonl'  # 기록 응답 파일(record_demo.py가 만든다)
OUTCOMES = RECORDING.with_name('outcomes.json')  # 질문별 입력 · 결과 · 재개 값(record_demo.py가 기록 끝에 쓴다)
MISSING = ('키 없는 데모의 LLM 응답 기록(data/demo/recordings/)이 없습니다. '
           'scripts/demo/DEMO.md대로 기록을 만든 뒤 서버를 다시 띄우세요.')


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
    """서비스가 기록 응답을 재생하는 모드인가. DEMO_MODE=1 없이 DEMO_REPLAY=1만 있으면 설정 오류(ValueError)."""
    # [왜] DEMO_MODE=1만 켠 실행(평가 · 실제 LLM + BM25 확인)은 실제 LLM을 그대로 쓴다. 재생은 따로 켠다
    if os.getenv('DEMO_REPLAY') != '1':
        return False
    if os.getenv('DEMO_MODE') != '1':
        raise ValueError('기록 응답 재생(DEMO_REPLAY=1)은 DEMO_MODE=1에서만 사용할 수 있습니다.')
    return True


def service_chat():
    """서비스 그래프에 넣을 재생 chat. 기록 파일이 없어도 서버는 뜨고, 부르면 503(분석 요청은 questions()가 먼저 막는다)."""
    if RECORDING.exists():
        return replayer(RECORDING)

    def missing(node, system, user, schema):
        raise HTTPException(503, MISSING)
    return missing


def connections(netlist):
    """기록 질문의 회로 연결 정보: 넷리스트 옆 connections.json을 ensure_thread와 같은 모양({components, nets})으로."""
    from backend.graph.nodes import _connections_file
    data = json.loads(_connections_file(netlist).read_text(encoding='utf-8'))
    return {'components': data.get('components', data.get('parts', [])), 'nets': data.get('nets', [])}


def questions():
    """기록한 데모 질문(outcomes.json의 questions)에 React 데모 회로 id(`demo_id`, 카탈로그에 없으면 None)를 붙여 돌려준다.

    Raises:
        HTTPException: 503. 기록 파일(calls.jsonl · outcomes.json)이 없을 때.
    """
    if not (RECORDING.exists() and OUTCOMES.exists()):
        raise HTTPException(503, MISSING)
    from backend.graph.nodes import _connections_file
    from backend.projects.repository import DEMOS, demo_path
    # [왜] 화면은 프로젝트의 demo_id로 버튼을 고른다. 데모 프로젝트가 읽은 파일과 기록이 읽은 파일이 같은지로 잇는다
    ids = {demo_path(d).resolve(): d for d in DEMOS}
    return [{**q, 'demo_id': ids.get(_connections_file(q['netlist']).resolve())}
            for q in json.loads(OUTCOMES.read_text(encoding='utf-8'))['questions']]


def match(circuit, target, question=None, conditions=None):
    """회로 연결 정보 · 대상 부품(question을 주면 질문 · 조건까지)이 기록과 같은 데모 질문 목록. 기록이 없으면 503."""
    # [주의] 글자 하나라도 다르면 프롬프트가 달라 재생이 멈춘다(ReplayMiss). 그래서 비슷한 질문을 고르지 않고 같은 것만 받는다
    return [q for q in questions() if q['target'] == target and connections(q['netlist']) == circuit
            and (question is None or (q['question'], q['conditions']) == (question, conditions))]


def refusal(reason):
    """기록한 데모 질문 목록을 붙인 422. 화면 문구로 그대로 보인다."""
    listed = ' / '.join(f"[{q['id']}] {q['circuit']} · {q['target']}: {q['question']}" for q in questions())
    return HTTPException(422, f'{reason} 키 없는 데모는 기록한 질문만 새 대화의 첫 질문으로 재생합니다. 데모 질문: {listed}')
