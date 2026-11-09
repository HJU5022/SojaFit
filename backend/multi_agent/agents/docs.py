"""문서 에이전트: 지시서의 검색어로 찾고, 근거 채점과 답 쓰기를 LLM 한 번으로 하고, 인용을 코드로 검사해 보고한다.

- 역할: 검색(지시서의 첫 검색어 · 질문의 품번 필터, BM25 + voyage-4-large → rerank-3 상위 5) → 다른 품번 줄 · 다른 판 거르기(코드) →
  근거 채점 + 답 쓰기(Haiku 1번: 질문 · 지시서 · 대상 회로 · 청크를 함께 받는다) → 근거가 없거나 일부만 답했으면 LLM이 준 다른 검색어로 1번만 다시(일부 답은 앞 근거와 함께, #49) →
  인용 검사(코드: 보여 준 청크 번호와 넷리스트만) → 보고(ok · partial · fail + 200자 요약 + 부분 답 + 근거).
  지시서에 품번(parts)이 있으면 그 품번 문서 안에서만 찾는다(재계획이 넣는다, 설계 v2). 품번 없이 정격(specs)만 있으면
  사양 표 도구(find_parts_by_specs)로 그 정격과 같은 값의 품번을 먼저 찾고 그 문서 안에서 찾는다(11-07 R1 dev G4).
  근거를 끝내 못 찾으면 거절을 정하지 않고 다시 찾을 사유(no_result · all_rejected)로 보고한다.
  역할 할 일처럼 검색어가 없으면 검색 없이 넷리스트만으로 답한다.
- 하지 않는 일: 할 일 정하기(Supervisor ①), 숫자 비교 · 대체 판정(판정 에이전트와 `backend/judge/`), 여러 할 일 합치기(Supervisor ②),
  LLM 직접 호출(`chat`을 받아 쓴다. 실제 연결은 `llm.node_chat`).
- 출처: 참조/아티팩트 "SojaFit 멀티 에이전트 구조" 문서 에이전트(예전 채점 Luna · 생성 Haiku를 한 호출로 합침, 11-06 강사 지적
  "채점은 질문 맥락을 가진 쪽이"), backend/graph/nodes.py(검색 · 다른 품번 줄 거르기 · 인용 함수를 그대로 쓴다)
"""
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.graph.mcp_retriever import RetrievalUnavailableError
from backend.graph.nodes import NOT_FOUND, REVISION, WORD, citations, netlist_block, other_part_row, search
from backend.multi_agent.contracts import MAX_SEARCHES, Reason, Task, TaskReport
from backend.rag.units import to_si

PROMPT = (Path(__file__).resolve().parents[2] / 'prompts' / 'docs_answer.md').read_text(encoding='utf-8')
CITE_GROUP = re.compile(r'\[([^\]]*)\]')  # 답 속 인용 괄호(nodes.CITE와 같은 모양)


class DocsAnswer(BaseModel):
    """근거 채점 + 답 쓰기 LLM의 답안지."""
    grade: Literal['enough', 'partial', 'none'] = Field(description='Does the evidence answer the task: enough, partial or none')
    answer: str = Field(default='', description='Korean answer, every sentence ending with its evidence number like [12]; empty when grade is none')
    missing: list[str] = Field(default_factory=list, description='Values or facts the task needs that the evidence does not give')
    next_query: str = Field(default='', max_length=200, description='When grade is none or partial: a different English search query to try once (for partial, aimed at what is missing)')


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


def docs_agent(payload: dict, *, retriever, chat, find=None) -> dict:
    """그래프 노드(Send 대상): 할 일 하나를 끝까지 하고 보고서 하나를 메모장 `reports`에 이어 붙인다."""
    task = Task.model_validate(payload['task'])
    question, part, rnd = payload['question'], payload.get('target_part') or {}, payload.get('round') or 1
    query, searches, shown, result, calls, relax = task.query.strip(), [], [], None, 0, False
    filter_parts, looked_up = list(task.parts), ''
    carry, first = [], None  # 일부만 답한 근거와 그 답(다시 찾을 때 근거를 함께 보이고, 못 늘리면 그 답을 쓴다)

    def report(status: str, summary: str, **kw) -> dict:
        r = TaskReport(task=task.id, agent='docs', status=status, summary=summary[:200], searches=searches, llm_calls=calls, round=rnd, **kw)
        return {'reports': [r.model_dump(mode='json')], 'path': ['문서']}

    if not filter_parts and task.specs and find is not None:
        try:
            filter_parts = lookup_parts(task, find)
        except RetrievalUnavailableError as error:
            return report('fail', f'spec table tool failure: {error.kind}', reason=Reason.SEARCH_ERROR)
        if not filter_parts:
            # [왜] 그 정격의 품번이 표에 없다. 거절을 정하지 않고 다시 찾을 사유로 올린다(재계획이 조건을 고쳐 볼 수 있다)
            return report('fail', 'no part in the spec table has the described ratings', reason=Reason.NO_RESULT)
        looked_up = f"; parts with the described ratings: {', '.join(filter_parts)}"
    for _ in range(MAX_SEARCHES):  # [왜] 검색은 할 일마다 2번까지(AGENTS 6, B-지시서 4-4)
        docs = []
        if query:
            find = (lambda q, parts=None: retriever(q, parts=None)) if relax else retriever
            if filter_parts and not relax:
                # [왜] 지시서의 품번(재계획이 넣음)이나 정격으로 찾은 품번이 있으면 그 품번 문서 안에서만 찾는다
                find = lambda q, parts=None: retriever(q, parts=list(filter_parts))
            out = search({'question': question, 'target_part': part, 'query': query}, find)
            if out['retrieval_error']:
                return report('fail', f"search tool failure: {out['retrieval_error'].get('kind', '')}", reason=Reason.SEARCH_ERROR)
            used_parts = list(filter_parts) if filter_parts and not relax else out['parts']
            searches.append({'query': out['query'], 'parts': used_parts, 'top': [[d['file'], d['page']] for d in out['docs']]})
            docs = keep_docs(out['docs'], used_parts, question)
            docs += variant_notes(used_parts, docs, retriever)
        if carry:
            seen = {d['chunk_id'] for d in carry}
            docs = carry + [d for d in docs if d['chunk_id'] not in seen]
            if len(docs) == len(carry):
                result, shown = first  # 새 근거가 없으면 다시 부르지 않고 첫 일부 답을 쓴다
                break
        if not docs and not part:
            if query and not relax:
                relax = True  # [왜] 품번 필터 안에서 0건이면 필터를 풀어 한 번 더 찾는다(예전 검색 에이전트의 no_result 재시도와 같음)
                continue
            break  # 보여 줄 근거가 하나도 없으면 LLM을 부르지 않는다
        result, shown = chat('docs_answer', PROMPT, render(question, task, docs, part), DocsAnswer), docs
        calls += 1
        if result.grade == 'enough' or not result.next_query.strip():
            break
        if result.grade == 'partial':
            # [왜] 일부만 답하고 끝내면, 검색어가 질문의 한쪽만 겨눈 경우 정답 근거 없이 답했다(v3-20: 'H 접미사 뜻'만 찾아 SS14H · SS14 정격표를 못 봄,
            #      사전 등록 #49). 빠진 부분을 다른 검색어로 한 번 더 찾고, 앞 근거와 함께 다시 답한다(검색 2번 상한 안)
            carry, first = shown, (result, shown)
        query = result.next_query.strip()  # 근거가 없거나 모자라다고 채점했으면 LLM이 준 다른 검색어로 한 번만 다시
    if first and (result.grade == 'none' or not result.answer.strip()):
        result, shown = first  # 다시 찾은 답이 더 나쁘면 첫 일부 답을 쓴다
    answer = (result.answer.strip() if result else '')
    if not result or result.grade == 'none' or not answer or answer.startswith(NOT_FOUND):
        # [왜] 설계 v2: 못 찾았다고 거절을 정하지 않고 다시 찾을 사유로 보고한다(0건 no_result, 근거가 아님 all_rejected). 거절은 Supervisor가 정한다
        why = Reason.ALL_REJECTED if shown else Reason.NO_RESULT
        return report('fail', f'no evidence for this task in the documents ({why.value})', reason=why,
                      missing=result.missing[:6] if result else [], docs=shown)
    # [왜] 인용 검사는 LLM의 자기 검사를 믿지 않고 코드로 다시 센다. 보여 준 적 없는 번호만 근거로 단 문장은 빼고, 진짜 번호도 단 문장은
    #      가짜 번호만 지운다. 가짜 번호 하나로 답 전체를 거절하던 것을 바꿨다(11-06 공식 5회차 v3-18 '[5816]')
    valid = {str(d['chunk_id']) for d in shown} | ({'넷리스트'} if part else set())
    answer, dropped_fake = drop_fake_citations(answer, valid)
    cited = citations(answer)
    if not cited & valid:
        problem = f'cited evidence that was not provided {dropped_fake}' if dropped_fake else 'answer has no citation'
        return report('fail', problem, reason=Reason.VERIFY_FAILED, docs=shown)
    status = 'ok' if result.grade == 'enough' else 'partial'
    summary = f'{status}: answered from {len(cited & valid)} evidence' + looked_up + (f'; missing {", ".join(result.missing)}' if result.missing else '')
    return report(status, summary, answer=answer, evidence_ids=sorted(cited & valid), missing=result.missing[:6], docs=shown)
