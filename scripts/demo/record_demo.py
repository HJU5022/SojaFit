"""키 없는 데모용 LLM 응답 기록(record)과 재생 확인(replay).

- 역할: 서비스와 같은 멀티 에이전트 그래프(`memory_service._graph()`의 실제 분석 조립, 체크포인터는 메모리 안, Store 없음)를
  데모 질문 목록(`QUESTIONS`)으로 돌린다. `record`는 실제 LLM 응답을 `backend/services/demo.py`의 recorder로
  `data/demo/recordings/calls.jsonl`에 남기고, 질문마다 결과(경로 · 답 · 판정 · 거절 · 인터럽트와 재개 값)와
  DB 지문을 `outcomes.json`에 남긴다. `replay`는 키 없이 같은 질문을 replayer로 다시 돌려 결과가 기록과 같은지 본다.
- 하지 않는 일: 서비스에 재생 연결(`memory_service._graph()`가 할 일), 동결 평가셋 고치기(데모 전용 변형은 `demo-` id로 따로 둔다),
  채점(`evals/runners/`), 키 · 헤더 · 가격 기록.
- 출처: data/demo/DEMO.md, data/demo/snapshot/SNAPSHOT.md, backend/conversations/memory_service.py `_graph()` · `message()` · `resume()`,
  evals/runners/run_graph.py(조립), AGENTS.md 지킬 것 2 · 4 · 6
- 필요한 것: 키 없는 compose의 DB(빈 볼륨에 corpus-load가 스냅샷 42문서를 넣은 그대로), `DEMO_MODE=1`.
  `record`만 `OPENROUTER_API_KEY`가 필요하고 `--confirm-live`가 있어야 LLM을 부른다(없으면 예상 호출 수만 찍고 멈춘다).
- 실행(저장소 루트, compose 네트워크 안에서. db 포트는 밖으로 열려 있지 않고, 이미지에는 scripts/ · evals/가 없어 붙여 넣는다).
  기록과 재생 확인은 서로 다른 새 compose 프로젝트(-p)에서 돌려, 평가자의 새 볼륨에서도 청크 id가 같은지까지 본다. 명령은 scripts/demo/DEMO.md
"""
import json
import os
import sys
import time
from contextlib import ExitStack
from functools import update_wrapper
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))  # [왜] 경로로 실행해도 backend 패키지를 저장소 루트에서 찾게 한다(scripts/auth와 같은 방식)

OUT = ROOT / 'data/demo/recordings'
CALLS, OUTCOMES = OUT / 'calls.jsonl', OUT / 'outcomes.json'
SNAPSHOT = ROOT / 'data/demo/snapshot'
KEY_VARS = ('OPENROUTER_API_KEY', 'OPENAI_API_KEY', 'VOYAGE_API_KEY', 'ANTHROPIC_API_KEY')
FRANZ = 'data/circuits/collected/received-20261030/c09/received/c09-franzininho-diy.net'
BREAD = 'data/circuits/collected/samples/breadboard_supply/converted/circuit.net'

# 데모 질문. v3-* 는 동결 평가셋 v3 문항의 입력 그대로(tests/services/test_demo_replay.py가 대조), demo-* 는 데모 전용 변형(동결 문항 아님).
# answers: 인터럽트가 물으면 줄 값(물은 이름만 골라 보낸다. 비면 '모름'). calls: 그래프 구조로 어림한 LLM 호출 수(최소, 최대) [추정]
QUESTIONS = [
    {'id': 'v3-01', 'kind': '판정 + 조건 인터럽트', 'circuit': 'ATtiny85 Time Switch',
     'netlist': 'data/circuits/collected/received-20261030/c01/received/c01-attiny85-time-switch.net', 'target': 'D1',
     'conditions': 'VIN은 최대 15V, D1의 연속 전류는 최대 120mA이며 주변 온도는 25°C이다. PWM 없이 직류로 쓴다. '
                   '현재 부품은 넷리스트의 onsemi 1N4007RLG이고 제조사를 바꿔도 된다. 기판의 리드 간격은 수정할 수 있다. '
                   '이번 부품 승인에서 순방향 전압강하는 제한 항목으로 삼지 않는다. 투입 시 D1 전류는 초기 접합온도 25°C에서 피크 2A·폭 8.3ms의 단발 반정현파이다.',
     'question': '전원 입력의 D1을 TSC 1N4007G로 바꿔도 될까? 전기 조건과 실장 변경 여부를 같이 봐 줘.',
     # [왜] 역극성 보호(R01)는 허용 전압강하(v_drop_allowed)를 조건부로 묻는다. 질문이 '제한 항목으로 삼지 않는다'고 했으니 모름으로 답한다
     'answers': {}, 'interrupt': True, 'calls': (2, 5)},
    {'id': 'demo-find', 'kind': '후보 찾기(v3-11 모양, 데모 회로 · 스위칭 다이오드로 바꿈)', 'circuit': 'Franzininho DIY', 'netlist': FRANZ, 'target': 'D3',
     'conditions': 'USB 전원은 최대 5.25V, D3 경로 전류는 최대 40mA, 주변 온도는 25°C이며 PWM은 없다. 현재 1N4148이고 표면실장으로 기판을 바꿀 수 있다. '
                   '구매 규격은 TSC 스위칭 다이오드, 반복 피크 역전압 정격 75V 이상, 평균 순방향 전류 정격 150mA 이상이다. 정격은 데이터시트 표에 적힌 시험 조건 그대로 비교한다.',
     'question': 'D3의 대체 후보를 위 구매 규격으로만 추려 줘. 각 후보의 전압·전류 정격과 패키지를 근거와 함께 알려 줘.',
     'answers': {}, 'interrupt': False, 'calls': (2, 12)},
    {'id': 'demo-rating', 'kind': '정격 확인(v3-21의 1N5408G를 스냅샷에 있는 1N4001G로 바꿈)', 'circuit': 'SparkFun Breadboard Supply', 'netlist': BREAD,
     'target': 'D1', 'conditions': '',
     'question': 'TSC 1N4001G는 전원을 처음 넣을 때처럼 잠깐 몰리는 큰 전류를 어디까지 견딘다고 돼 있어? 한 번만 흘리는 건지, 전류 파형과 지속 시간·온도 조건도 같이 알려 줘.',
     'answers': {}, 'interrupt': False, 'calls': (2, 5)},
    {'id': 'v3-36', 'kind': '거절(코퍼스에 없는 품번)', 'circuit': 'Franzininho DIY', 'netlist': FRANZ, 'target': 'D3',
     'conditions': 'USB 전원은 최대 5.25V, D3 경로 전류는 최대 40mA, 주변 온도는 25°C이며 PWM은 없다. 현재 1N4148이고 MiniMELF용 기판 수정은 가능하다.',
     'question': 'D3용 TSC LL4149의 전압강하 최댓값과 시험 전류가 어떻게 돼? LL4148 말고 발주서에 적힌 LL4149를 확인해 줘.',
     'answers': {}, 'interrupt': False, 'calls': (1, 3)},
    {'id': 'v3-30', 'kind': '거절(범위 밖)', 'circuit': 'Franzininho DIY', 'netlist': FRANZ, 'target': 'D3',
     'conditions': 'USB 전원 5V로 동작하고 D3는 유지한다. IC1은 넷리스트의 ATtiny85이며 펌웨어는 수정할 수 있다.',
     'question': 'D3 교체 대신 펌웨어 쪽을 먼저 보려고 해. 이 ATtiny85가 USB 소프트웨어 통신에 맞는 클록으로 뜨도록 퓨즈 바이트 설정 후보를 골라 줘.',
     'answers': {}, 'interrupt': False, 'calls': (1, 2)},
]
COMPARED = ('interrupt', 'resume', 'path', 'question_type', 'answer', 'verdicts', 'refusal')  # 재생 확인이 기록과 대조하는 칸


def env_problems(mode: str, env) -> list[str]:
    """실행을 막을 이유 목록(비면 진행). env는 .env를 읽은 뒤의 환경변수다."""
    out = []
    if env.get('DEMO_MODE') != '1':
        out.append('DEMO_MODE=1이 아닙니다. 키 없는 데모와 같은 BM25 검색이어야 기록이 맞습니다')
    if [k for k, v in env.items() if k.startswith('LAB_') and v]:
        # [왜] LAB_READ_VOTES 같은 실험 설정은 같은 호출을 여러 번 부르거나 프롬프트를 바꿔 서비스와 다른 길이 된다
        out.append('LAB_* 실험 환경변수를 지우세요. 서비스와 같은 설정이어야 합니다')
    if mode == 'record':
        if not env.get('OPENROUTER_API_KEY'):
            out.append('OPENROUTER_API_KEY가 없습니다(기록은 실제 LLM을 부릅니다)')
        if env.get('LLM_PROVIDER') not in (None, '', 'openrouter') or env.get('LLM_MODEL'):
            out.append('서비스와 같은 공급자 · 노드별 모델이어야 합니다(LLM_PROVIDER=openrouter, LLM_MODEL 비움)')
    return out


def db_fingerprint(conn) -> dict:
    """문서 · 청크 수와 (청크 id, 본문 sha256) 목록의 sha256. 프롬프트에 청크 id가 들어가 같은 적재여야 재생이 맞는다."""
    docs = conn.execute('SELECT count(*) FROM source_documents').fetchone()[0]
    chunks, digest = conn.execute(
        "SELECT count(*), encode(sha256(convert_to(coalesce(string_agg(id::text || ':' || chunk_sha256, ',' ORDER BY id), ''), 'UTF8')), 'hex')"
        ' FROM document_chunks').fetchone()
    return {'documents': docs, 'chunks': chunks, 'ids_sha256': digest}


def connections(netlist: str) -> dict:
    """React 데모 회로와 같은 연결 정보: 넷리스트 옆 connections.json을 ensure_thread와 같은 모양({components, nets})으로."""
    from backend.graph.nodes import _connections_file
    data = json.loads(_connections_file(netlist).read_text(encoding='utf-8'))
    return {'components': data.get('components', data.get('parts', [])), 'nets': data.get('nets', [])}


def service_inputs(q: dict) -> dict:
    """memory_service.message()가 새 대화의 첫 질문에 만드는 그래프 입력과 같은 모양."""
    # [주의] 같은 대화의 두 번째 질문부터는 '이전 사용자 입력'이 붙어 프롬프트가 달라진다. 기록은 새 대화의 첫 질문만 맞는다
    content = (f"사용 조건: {q['conditions']}\n" if q['conditions'] else '') + q['question']
    return {'input': content, 'connections': connections(q['netlist']), 'circuit': q['circuit'], 'target': q['target'],
            'conditions': q['conditions'], 'user_id': 'demo', 'run_version': 1, 'approved_memories': []}


def build_app(chat, stack: ExitStack):
    """memory_service._graph()의 실제 분석 조립과 같게 만든다. 다른 점: chat · 카드 도구 chat을 주입, 체크포인터는 메모리 안, Store 없음."""
    from langgraph.checkpoint.memory import InMemorySaver
    from backend.graph.mcp_retriever import StdioMcpRetriever
    from backend.multi_agent.build import build_graph
    from backend.multi_agent.facts import make_lookup
    from backend.rag.card_find import default_find
    from backend.rag.card_specs import default_specs
    from backend.rag.retrieve import retrieve
    from backend.services.langfuse_prompts import timed_tool
    mcp = stack.enter_context(StdioMcpRetriever())  # 사실 확인(check_corpus)만 MCP로 부른다(서비스와 같음)
    specs, find = default_specs(chat=chat), default_find(chat=chat)
    return build_graph(chat=chat, retriever=timed_tool('search', retrieve), judge_enabled=True,
                       lookup=make_lookup(mcp.check, specs.doc_rows), specs=update_wrapper(timed_tool('specs', specs), specs),
                       find=update_wrapper(timed_tool('find', find), find), checkpointer=InMemorySaver())


def run_question(app, q: dict) -> dict:
    """질문 하나를 서비스처럼 돌린다(인터럽트면 정한 답으로 한 번 재개). 실행마다 서비스와 같은 호출 · 시간 · 예약 상한을 건다."""
    from langgraph.types import Command
    from backend.conversations.memory_service import Conversations
    from backend.rag.card_find import SHARED_READS
    from backend.services.llm import evaluation_limits
    from evals.runners.score_answer import judgement_parts
    # [왜] 카드 읽기 결과는 프로세스 전체가 나눠 쓴다. 앞 질문이 읽어 둔 카드 때문에 이 질문의 카드 읽기 호출이 기록에서 빠지지 않게 비운다
    SHARED_READS.clear()
    config = {'configurable': {'thread_id': q['id']}}
    with evaluation_limits(Conversations._budget_settings()[0]):  # AGENTS 지킬 것 6: 실행당 16회 · 예약 $0.50 · 90초(서비스 값)
        state = app.invoke(service_inputs(q), config)
    interrupt = resume = None
    if pending := state.get('__interrupt__'):
        if len(pending) != 1:  # [왜] 서비스 resume()은 첫 인터럽트 하나에만 답한다. 둘이면 화면에서 재생할 수 없다
            raise SystemExit(f"{q['id']}: 인터럽트가 {len(pending)}개라 서비스처럼 재개할 수 없습니다")
        interrupt = pending[0].value
        # 서비스는 물은 이름(missing) 밖의 답을 422로 막는다. 역할 후보가 있으면 API가 그중 하나를 꼭 받으므로
        # 질문 목록의 role, 없으면 첫 후보를 고른다(고른 값은 outcomes에 남아 화면이 같은 값을 보낸다). 후보가 없으면 ''(서비스와 같음)
        choices = interrupt.get('role_choices') or []
        resume = {'answers': {k: v for k, v in q['answers'].items() if k in (interrupt.get('missing') or [])},
                  'role': q.get('role') if q.get('role') in choices else (choices[0] if choices else '')}
        with evaluation_limits(Conversations._budget_settings()[0]):
            state = app.invoke(Command(resume=resume), config)
        if state.get('__interrupt__'):
            raise SystemExit(f"{q['id']}: 재개 뒤 다시 멈췄습니다")
    if q['interrupt'] and interrupt is None:
        raise SystemExit(f"{q['id']}: 조건 인터럽트를 보여 줄 질문인데 멈추지 않았습니다. 질문을 바꾸고 다시 기록하세요")
    return {'id': q['id'], 'kind': q['kind'], 'circuit': q['circuit'], 'netlist': q['netlist'], 'target': q['target'],
            'conditions': q['conditions'], 'question': q['question'], 'interrupt': interrupt, 'resume': resume,
            'path': state.get('path', []), 'question_type': state.get('question_type', ''), 'answer': state.get('answer', ''),
            'verdicts': [[p.get('part'), p.get('verdict')] for p in judgement_parts(state.get('judgement') or {})],
            'refusal': (state.get('refusal') or {}).get('code', '')}


def differences(recorded: list[dict], replayed: list[dict]) -> list[str]:
    """기록 결과와 재생 결과가 다른 (질문 id, 칸) 목록."""
    before = {r['id']: r for r in recorded}
    return [f"{r['id']}: {k}" for r in replayed for k in COMPARED if before.get(r['id'], {}).get(k) != r.get(k)] + \
           [f'{i}: 재생 안 됨' for i in sorted(set(before) - {r['id'] for r in replayed})]


def _no_llm(*args, **kwargs):
    raise RuntimeError('재생 확인 중 실제 LLM 입구가 불렸습니다(주입한 chat을 거치지 않은 길)')


def main(mode: str, confirm: bool) -> int:
    """record · replay 한 번. 성공 0, 막히거나 다르면 1."""
    from backend.services import demo, langfuse_prompts, llm  # [주의] llm을 import할 때 .env를 읽으므로 환경 검사는 그 뒤에 한다
    if problems := env_problems(mode, os.environ):
        print('\n'.join(f'멈춤: {p}' for p in problems), file=sys.stderr)
        return 1
    lo, hi = sum(q['calls'][0] for q in QUESTIONS), sum(q['calls'][1] for q in QUESTIONS)
    runs = len(QUESTIONS) + sum(q['interrupt'] for q in QUESTIONS)
    print(f"질문 {len(QUESTIONS)}개 · 그래프 실행 {runs}번. 예상 LLM 호출 약 {lo}~{hi}회 [추정, 형식 재시도 제외], "
          f"상한 실행마다 {os.getenv('ANALYSIS_MAX_CALLS', '16')}회 · 예약 ${os.getenv('ANALYSIS_MAX_USD', '0.50')}. "
          f"v3 실측 문항당 약 $0.001 → 약 ${len(QUESTIONS) * 0.001:.3f}", flush=True)
    if mode == 'record' and not confirm:
        print('유료 호출 전에 멈췄습니다. 부르려면 --confirm-live를 붙이세요.')
        return 0
    import psycopg
    with psycopg.connect(os.environ['DATABASE_URL']) as conn:  # [주의] 접속 문자열은 찍지 않는다
        db = db_fingerprint(conn)
    want = {'documents': sum(1 for _ in open(SNAPSHOT / 'manifest.jsonl', encoding='utf-8')),
            'chunks': sum(1 for _ in open(SNAPSHOT / 'chunks.jsonl', encoding='utf-8'))}
    if {k: db[k] for k in want} != want:
        print(f"멈춤: DB가 데모 스냅샷이 아닙니다(문서 {db['documents']} · 청크 {db['chunks']}, 기대 {want['documents']} · {want['chunks']}). "
              '키 없는 compose의 DB에서 돌리세요', file=sys.stderr)
        return 1
    if mode == 'replay':
        recorded = json.loads(OUTCOMES.read_text(encoding='utf-8'))
        if recorded['db'] != db:
            print('멈춤: DB 청크 id가 기록 때와 다릅니다. 빈 볼륨에 corpus-load로 스냅샷을 넣은 DB여야 합니다', file=sys.stderr)
            return 1
        for key in KEY_VARS:
            os.environ.pop(key, None)  # [왜] 키 없이 도는지 본다. llm이 .env를 이미 읽은 뒤라 지운 값이 다시 들어오지 않는다
        llm.chat = llm.node_chat = _no_llm  # [왜] 주입한 replayer를 거치지 않는 LLM 길이 있으면 여기서 드러난다
        chat = demo.replayer(CALLS)
    else:
        OUT.mkdir(parents=True, exist_ok=True)
        CALLS.write_text('', encoding='utf-8')  # [주의] 기록은 늘 처음부터 다시 쓴다(앞 기록과 섞이지 않게)
        OUTCOMES.unlink(missing_ok=True)  # [왜] 이번 기록이 중간에 멈추면 옛 결과 파일이 새 기록과 짝지어 남지 않게 지운다
        chat = demo.recorder(llm.node_chat, CALLS)
    with ExitStack() as stack:
        app = build_app(chat, stack)
        results = []
        for q in QUESTIONS:
            started = time.monotonic()
            results.append(run_question(app, q))
            print(f"{q['id']}\t{'>'.join(results[-1]['path'])}\t{results[-1]['verdicts'] or results[-1]['refusal']}\t"
                  f'{time.monotonic() - started:.1f}초', flush=True)
    if mode == 'record':
        OUTCOMES.write_text(json.dumps({'recorded_at': time.strftime('%Y-%m-%d'), 'db': db,
                                        'models': {n: llm.node_model(n) for n in langfuse_prompts.NODES},
                                        'questions': results}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(f"기록 {sum(1 for _ in open(CALLS, encoding='utf-8'))}줄 · 결과 {len(results)}개를 {OUT.relative_to(ROOT)}에 남겼습니다")
        return 0
    diff = differences(recorded['questions'], json.loads(json.dumps(results, ensure_ascii=False)))  # [왜] 기록은 JSON을 거친 값이라 같은 모양으로 맞춰 견준다
    print('\n'.join(f'다름: {d}' for d in diff) or '재생 결과가 기록과 같습니다')
    return 1 if diff else 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args or args[0] not in ('record', 'replay'):
        sys.exit(__doc__)
    sys.exit(main(args[0], '--confirm-live' in args))
