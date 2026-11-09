"""RAG 에이전트: 검색 → 근거 채점 · 답 쓰기를 고리로 돌고(근거가 없으면 다른 검색어로 한 번 더), 인용을 코드로 검사해 답을 낸다.

- 역할: 하위 그래프(`build.rag_subgraph`)의 두 노드와 고리 갈림길.
  - `search_step`(검색): 지시서의 첫 검색어 · 질문의 품번 필터로 찾는다(BM25 + voyage-4-large → rerank-3 상위 5) → 다른 품번 줄 · 다른 판 거르기(코드)
    → 변형 품번(양방향 · H)이면 품번 규칙 주석을 더 찾는다. 지시서에 품번 없이 정격(specs)만 있으면 첫 바퀴에 사양 표 도구(find_parts_by_specs)로
    그 정격과 같은 값의 품번을 먼저 찾고 그 문서 안에서 찾는다(11-07 R1 dev G4). 역할 질문처럼 검색어가 없으면 찾지 않고 넷리스트만 쓴다.
  - `answer_step`(근거 채점 · 답 쓰기): Haiku 1번에 질문 · 지시서 · 대상 회로 · 청크를 주고 채점과 답을 함께 받는다. 인용 검사(코드: 보여 준 청크
    번호와 넷리스트만) 뒤 답을 내거나, 근거가 없으면 거절 사유(not_found)와 다음 검색어를 낸다.
  - `after_answer`: 다음 검색어가 있고 상한(MAX_SEARCHES) 전이면 검색으로 되돌아가고, 아니면 하위 그래프를 나간다.
- 하지 않는 일: 질문 종류 정하기(Supervisor), 숫자 비교 · 대체 판정(대체 부품 에이전트와 `backend/judge/`),
  LLM 직접 호출(`chat`을 받아 쓴다. 실제 연결은 `llm.node_chat`).
- 출처: 강의 IV-2 18강 · 20강(채점 → 재작성 → 검색 고리를 조건부 간선으로), 예전 채점 Luna · 생성 Haiku를 한 호출로 합침(11-06 강사 지적
  "채점은 질문 맥락을 가진 쪽이"), backend/graph/nodes.py(검색 · 다른 품번 줄 거르기 · 인용 함수를 그대로 쓴다)
"""
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.graph.mcp_retriever import RetrievalUnavailableError
from backend.graph.nodes import NOT_FOUND, REVISION, WORD, citations, netlist_block, other_part_row, search
from backend.multi_agent.contracts import MAX_SEARCHES, Reason, Task
from backend.multi_agent.messages import with_declined
from backend.rag.units import to_si

PROMPT = (Path(__file__).resolve().parents[2] / 'prompts' / 'docs_answer.md').read_text(encoding='utf-8')
CITE_GROUP = re.compile(r'\[([^\]]*)\]')  # 답 속 인용 괄호(nodes.CITE와 같은 모양)


class DocsAnswer(BaseModel):
    """근거 채점 + 답 쓰기 LLM의 답안지."""
    grade: Literal['enough', 'partial', 'none'] = Field(description='Does the evidence answer the task: enough, partial or none')
    answer: str = Field(default='', description='Korean answer, every sentence ending with its evidence number like [12]; empty when grade is none')
    missing: list[str] = Field(default_factory=list, description='Values or facts the task needs that the evidence does not give')
    next_query: str = Field(default='', max_length=200, description='When grade is none: a different English search query to try once')


def keep_docs(docs: list[dict], parts: list[str], question: str) -> list[dict]:
    """LLM에 보여 주기 전에 코드로 거른다: 물은 품번이 아닌 다른 품번만 적힌 표 줄, 질문이 요청한 개정판이 아닌 문서."""
    # [왜] 단일 그래프 채점 노드의 결정적 검사와 같다. 인용한 청크에 대상 품번이 있게 하는 첫 관문이다(설계 그림 인용 검사)
    revisions = {w.upper() for w in WORD.findall(question) if REVISION.fullmatch(w)}
    return [d for d in docs if not other_part_row(d, parts)
            and not (revisions and d['file'].rsplit('_', 1)[-1].removesuffix('.pdf').upper() not in revisions)]


VARIANT = re.compile(r'C(A?H?)$|(?<=\d)H$', re.I)  # 양방향(…C · …CA · …CAH) · AEC-Q101(…H) 품번: 값 표에는 기본 품번으로만 적힌다
VARIANT_QUERY = ('bidirectional bi-directional C CA suffix electrical characteristics apply in both directions IR limit double'
                 ' "H" means AEC-Q101 qualified ordering information')
NOTE_WORDS = re.compile(r'bi-?directional|both directions|AEC-?Q101', re.I)


def variant_notes(parts: list[str], docs: list[dict], retriever) -> list[dict]:
    """물은 품번이 양방향 · H 품번이면 그 문서의 품번 규칙 주석('특성은 양방향 모두 적용' · 'IR 한도 2배' · 'H는 AEC-Q101')을 더 찾는다.

    [왜] 값 표는 기본 품번(SMAJ6.5A)으로만 적고 양방향 · H 품번은 주석으로만 연결한다. 청킹 v4부터 주석이 행 카드 끝이 아니라 따로 된
         주석 카드라 표 행 검색 상위 10개에 들지 못해, SMAJ6.5CA 누설전류를 물으면 근거가 SMAJ6.5A 행 하나뿐이라 거절했다(v3 v3-19, 11-09)
    """
    if not any(VARIANT.search(p.strip()) for p in parts):
        return []
    seen = {d.get('chunk_id') for d in docs}
    try:
        found = retriever(VARIANT_QUERY, parts=list(parts))
    except RetrievalUnavailableError:
        return []  # 주석은 보탬이라 도구가 실패해도 본 검색 결과로 답한다
    return [d for d in found if d.get('chunk_id') not in seen and NOTE_WORDS.search(d.get('content', ''))][:3]


def render(question: str, task: Task, docs: list[dict], part: dict) -> str:
    """LLM에 줄 user 글: 질문 · 지시서 · 근거(청크 + 넷리스트)."""
    blocks = [f"[{d['chunk_id']}] {d['file']} · {d['page']}쪽\n{d['content']}" for d in docs]
    if part:
        blocks.append(netlist_block(part))  # [왜] 역할 할 일은 검색 없이 오므로 넷리스트가 유일한 근거다
    return '\n'.join([f'Question: {question}', 'Supervisor brief:', f'- goal: {task.goal}', f'- return: {task.output}',
                      f'- boundary: {task.boundary}', '', 'Evidence:', '\n\n'.join(blocks) or '(none)'])


def drop_fake_citations(answer: str, valid: set[str]) -> tuple[str, list[str]]:
    """보여 주지 않은 근거 번호를 걸러낸다: 그 번호만 단 문장은 빼고, 진짜 번호와 함께 단 괄호에서는 그 번호만 지운다 → (답, 지운 번호)."""
    fake = sorted(citations(answer) - valid)
    if not fake:
        return answer, []
    kept = []
    for sentence in re.split(r'(?<=[.。])\s+', answer):
        got = citations(sentence)
        if got and not got & valid:
            continue  # 가짜 번호만 근거로 단 문장은 근거 없는 문장이다
        kept.append(CITE_GROUP.sub(lambda m: _clean_group(m, valid), sentence))
    return ' '.join(kept).strip(), fake


def _clean_group(m, valid: set[str]) -> str:
    items = [x.strip() for x in m.group(1).split(',')]
    if not any(x.isdigit() or x == '넷리스트' for x in items):
        return m.group(0)  # [0.60 V]처럼 번호가 아닌 괄호는 그대로
    left = [x for x in items if x in valid]
    return f"[{', '.join(left)}]" if left else ''


def lookup_parts(task: Task, find) -> list[str]:
    """품번 없이 정격으로 묘사한 부품: 계획이 옮겨 적은 정격과 같은 값을 가진 품번을 사양 표 도구로 찾는다(값 비교는 도구 안 SQL)."""
    def conditions(vz_range: bool) -> list[dict]:
        out = []
        for s in task.specs:
            si = to_si(s.value, s.unit)
            v = si[0] if si else s.value
            if s.code == 'VZ' and vz_range:
                out += [{'code': 'VZ', 'slot': 'min', 'lte': v}, {'code': 'VZ', 'slot': 'max', 'gte': v}]  # 최소 ≤ 공칭 ≤ 최대
                continue
            # [왜] 묘사한 정격은 '그 값인 부품'이다(교체 요구가 아니라 감쇄율 · 이상이 없다). 표는 반올림돼 있어(0.35 A ↔ 350 mA) 0.5% 폭을 둔다
            cond = {'code': s.code, 'gte': v * 0.995, 'lte': v * 1.005}
            if s.code == 'VZ':
                cond['slot'] = 'typ'  # 제너 전압을 하나로 말하면 공칭(대표 칸)이다
            out.append(cond)
        return out
    package = task.package.strip() or None  # [왜] 묘사에 패키지가 있으면(DO-201AD) 같은 정격의 다른 패키지 부품을 거른다(11-07 h4-20)
    found = find(conditions(False), task.category or None, package, 10)
    if not found and any(s.code == 'VZ' for s in task.specs):
        # [왜] 제너 표에는 공칭 칸 없이 최소 · 최대만 적힌 계열이 있다(BZT52B68 66.64 / 69.36). 공칭이 그 사이에 드는 품번으로 한 번 더 찾는다
        found = find(conditions(True), task.category or None, package, 10)
    return [f['part'] for f in found]


def search_step(state: dict, *, retriever, find=None) -> dict:
    """그래프 노드 '검색': 이번 바퀴의 검색어로 찾아 LLM에 보여 줄 청크(found)를 정한다. 장애는 error 칸에 남긴다."""
    task, part = Task.model_validate(state['task']), state.get('target_part') or {}
    tries = (state.get('tries') or 0) + 1
    query = task.query.strip() if tries == 1 else state.get('next_query', '')
    filter_parts, relax, searches = list(state.get('filter_parts') or []), bool(state.get('relax')), list(state.get('searches') or [])
    out = {'tries': tries, 'query': query, 'next_query': '', 'found': [], 'error': '', 'path': ['검색']}
    if tries == 1 and task.specs and find is not None:
        # [왜] 품번 없이 정격으로 묘사한 부품: 같은 값의 품번을 사양 표에서 먼저 찾는다(첫 바퀴에만)
        try:
            filter_parts = lookup_parts(task, find)
        except RetrievalUnavailableError:
            return {**out, 'error': Reason.SEARCH_ERROR.value}
        if not filter_parts:
            return {**out, 'error': Reason.NOT_FOUND.value}  # 그 정격의 품번이 표에 없다
        out['filter_parts'] = filter_parts
    if not query:
        return out  # 역할 질문: 검색 없이 넷리스트만 근거로 쓴다
    search_in = (lambda q, parts=None: retriever(q, parts=None)) if relax else retriever
    if filter_parts and not relax:
        # [왜] 정격으로 찾은 품번이 있으면 그 품번 문서 안에서만 찾는다
        search_in = lambda q, parts=None: retriever(q, parts=list(filter_parts))
    found = search({'question': state['question'], 'target_part': part, 'query': query}, search_in)
    if found['retrieval_error']:
        return {**out, 'error': Reason.SEARCH_ERROR.value}
    used_parts = list(filter_parts) if filter_parts and not relax else found['parts']
    searches.append({'query': found['query'], 'parts': used_parts, 'top': [[d['file'], d['page']] for d in found['docs']]})
    docs = keep_docs(found['docs'], used_parts, state['question'])
    docs += variant_notes(used_parts, docs, retriever)
    return {**out, 'found': docs, 'searches': searches, 'counters': {**(state.get('counters') or {}), 'searches': len(searches)}}


def answer_step(state: dict, *, chat) -> dict:
    """그래프 노드 '근거 채점·답 쓰기': LLM 1번으로 채점 + 답을 받고 인용을 검사해 답(또는 거절 사유와 다음 검색어)을 낸다.

    [왜] 바퀴마다 끝낼 때의 결과를 다 채워 둔다. 고리를 나갈지는 `after_answer` 간선이 정하고, 다시 돌면 다음 바퀴가 덮어쓴다.
    """
    task, part, question = Task.model_validate(state['task']), state.get('target_part') or {}, state['question']
    docs, query = state.get('found') or [], state.get('query') or ''
    fail = {'answer': '', 'docs': [], 'passed': [], 'next_query': '', 'path': ['근거 채점·답 쓰기']}
    if state.get('error'):
        return {**fail, 'refusal_reason': state['error']}  # 검색 · 사양 표 도구 장애(search_error)나 정격에 맞는 품번 없음(not_found)
    if not docs and not part:
        # [왜] 품번 필터 안에서 0건이면 필터를 풀어 한 번 더 찾는다. 보여 줄 근거가 하나도 없으면 LLM을 부르지 않는다
        retry = {'relax': True, 'next_query': query} if query and not state.get('relax') else {}
        return {**fail, 'refusal_reason': Reason.NOT_FOUND.value, **retry}
    result = chat('docs_answer', PROMPT, render(question, task, docs, part), DocsAnswer)
    answer = result.answer.strip()
    if result.grade == 'none' or not answer or answer.startswith(NOT_FOUND):
        # [왜] 근거가 아니라고 채점했으면 LLM이 준 다른 검색어로 한 번 더(상한은 간선이 본다). 끝내 없으면 '못 찾음' 거절이다
        return {**fail, 'refusal_reason': Reason.NOT_FOUND.value, 'next_query': result.next_query.strip() if result.grade == 'none' else ''}
    # [왜] 인용 검사는 LLM의 자기 검사를 믿지 않고 코드로 다시 센다. 보여 준 적 없는 번호만 근거로 단 문장은 빼고, 진짜 번호도 단 문장은
    #      가짜 번호만 지운다. 가짜 번호 하나로 답 전체를 거절하던 것을 바꿨다(11-06 공식 5회차 v3-18 '[5816]')
    valid = {str(d['chunk_id']) for d in docs} | ({'넷리스트'} if part else set())
    answer, _ = drop_fake_citations(answer, valid)
    if not citations(answer) & valid:
        return {**fail, 'refusal_reason': Reason.VERIFY_FAILED.value}
    # [왜] '일부만 답함'(partial)도 답으로 낸다. 여러 개를 묻는 질문에서 근거가 있는 부분만 답하고 나머지는 답 글이 '확인 못 함'이라고 쓴다
    return {**fail, 'answer': with_declined(state, answer), 'refusal_reason': '', 'docs': docs, 'passed': [d['chunk_id'] for d in docs]}


def after_answer(state: dict) -> str:
    """고리 갈림길: 다시 찾을 검색어가 있고 상한 전이면 '검색', 아니면 '나가기'(AGENTS 6, B-지시서 4-4)."""
    return '검색' if state.get('next_query') and (state.get('tries') or 0) < MAX_SEARCHES else '나가기'
