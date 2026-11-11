"""RAG 에이전트: 지시서의 검색어로 찾고, 근거 채점과 답 쓰기를 LLM 한 번으로 하고, 인용을 코드로 검사해 보고한다.

- 역할: 검색(지시서의 첫 검색어 · 질문의 품번 필터, BM25 + voyage-4-large → rerank-3 상위 5) → 다른 품번 줄 · 다른 판 거르기(코드) →
  근거 채점 + 답 쓰기(Haiku 1번: 질문 · 지시서 · 대상 회로 · 청크를 함께 받는다) → 근거가 없거나 일부만 답했으면 LLM이 준 다른 검색어로 1번만 다시(일부 답은 앞 근거와 함께, #49) →
  인용 검사(코드: 보여 준 청크 번호와 넷리스트만) → 보고(ok · partial · fail + 200자 요약 + 부분 답 + 근거).
  지시서에 품번(parts)이 있으면 그 품번 문서 안에서만 찾는다(재계획이 넣는다, 설계 v2). 품번 없이 정격(specs)만 있으면
  찾기 도구(find, 카드 찾기)로 그 정격과 같은 값의 품번을 먼저 찾고 그 문서 안에서 찾는다(11-07 R1 dev G4).
  근거를 끝내 못 찾으면 거절을 정하지 않고 다시 찾을 사유(no_result · all_rejected)로 보고한다.
  역할 할 일처럼 검색어가 없으면 검색 없이 넷리스트만으로 답한다.
- 하지 않는 일: 할 일 정하기(Supervisor), 숫자 비교 · 대체 판정(대체 부품 에이전트와 `backend/judge/`), 여러 할 일 합치기(종합),
  LLM 직접 호출(`chat`을 받아 쓴다. 실제 연결은 `llm.node_chat`).
- 출처: backend/multi_agent/MULTI_AGENT.md "구조 결정"의 RAG 에이전트(예전 채점 Luna · 생성 Haiku를 한 호출로 합침, 채점은 질문 맥락을
  가진 쪽이 한다), backend/graph/nodes.py(검색 · 다른 품번 줄 거르기 · 인용 함수를 그대로 쓴다)
"""
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.graph.mcp_retriever import RetrievalUnavailableError
from backend.graph.memory import memory_context, memory_sources
from backend.graph.nodes import NOT_FOUND, REVISION, WORD, citations, netlist_block, other_part_row, search
from backend.multi_agent.contracts import MAX_SEARCHES, Reason, Task, TaskReport
from backend.rag.units import to_si

PROMPT = (Path(__file__).resolve().parents[2] / 'prompts' / 'docs_answer.md').read_text(encoding='utf-8')
CITE_GROUP = re.compile(r'\[([^\]]*)\]\]*')  # 중첩 인용의 바깥 래퍼까지 함께 정리한다


class DocsAnswer(BaseModel):
    """근거 채점 + 답 쓰기 LLM의 답안지."""
    grade: Literal['enough', 'partial', 'none'] = Field(description='Does the evidence answer the task: enough, partial or none')
    answer: str = Field(default='', description='Korean answer citing only the exact allowed evidence IDs from the input; never renumber or cite page numbers; empty when grade is none')
    memory_refs: list[str] = Field(default_factory=list, max_length=5, description='Historical source IDs consulted; never cite these in answer')
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
ASSEMBLY = re.compile(r'실장|조립|\b(?:pre[- ]?)?(?:assembl|mount)', re.I)


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
    """LLM에 줄 user 글: 질문 · 지시서 · 문서 근거와 역할 작업의 넷리스트."""
    part = part if task.kind == 'role' else {}  # 사양 조회에 회로 연결을 부가 설명할 근거를 주지 않는다.
    blocks = []
    for d in docs:
        if d.get('source_type') == 'external_web':
            blocks.append(f"[{d['chunk_id']}] Manufacturer PDF: {d['source_url']} · PDF p.{d['page']}\n"
                          f"Table: {d['table']}\nRow: {d.get('row', '')}\nExtracted cells: {d['content']}")
        else:
            blocks.append(f"[{d['chunk_id']}] {d['file']} · {d['page']}쪽\n{d['content']}")
    if part:
        blocks.append(netlist_block({**part,'footprint':''}))  # Keep footprint annotations out of model instructions; preserve the original for code.
    allowed = [str(d['chunk_id']) for d in docs] + (['넷리스트'] if part else [])
    return '\n'.join([f'Question: {question}', 'Supervisor brief:', f'- goal: {task.goal}', f'- return: {task.output}',
                      f'- boundary: {task.boundary}', '', 'Evidence:', '\n\n'.join(blocks) or '(none)',
                      'Allowed citation IDs: '+', '.join(f'[{cid}]' for cid in allowed)+
                      '. Copy these IDs exactly; page numbers and source captions are not citation IDs.'])


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
    items = sorted(citations(m.group(0)))
    if not items:
        return m.group(0)  # [0.60 V]처럼 번호가 아닌 괄호는 그대로
    left = [x for x in items if x in valid]
    return f"[{', '.join(left)}]" if left else ''


def has_uncited_sentence(answer: str) -> bool:
    """A cited fact must not let an unsupported sentence ride into a joined answer."""
    return any(s.strip() and not citations(s) for s in re.split(r'(?<=[.。])\s+', answer))


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


def docs_agent(payload: dict, *, retriever, chat, find=None, web_search=None) -> dict:
    """그래프 노드(Send 대상): 할 일 하나를 끝까지 하고 보고서 하나를 메모장 `reports`에 이어 붙인다."""
    task = Task.model_validate(payload['task'])
    question, part, rnd = payload['question'], payload.get('target_part') or {}, payload.get('round') or 1
    query, searches, shown, result, calls, relax = task.query.strip(), [], [], None, 0, False
    filter_parts, looked_up = list(task.parts), ''
    web_parts = list(filter_parts)
    carry, first = [], None  # 일부만 답한 근거와 그 답(다시 찾을 때 근거를 함께 보이고, 못 늘리면 그 답을 쓴다)

    def report(status: str, summary: str, **kw) -> dict:
        # Only source locators cross into the persisted graph state.
        if 'docs' in kw:
            kw['docs'] = [{k: v for k, v in doc.items() if k != 'content'}
                          if doc.get('source_type') == 'external_web' else doc for doc in kw['docs']]
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
    for _ in range(MAX_SEARCHES):  # [왜] 검색은 할 일마다 2번까지(AGENTS 6, MULTI_AGENT.md "구조 결정"의 상한)
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
            web_parts = list(used_parts or web_parts)
            searches.append({'query': out['query'], 'parts': used_parts, 'top': [[d['file'], d['page']] for d in out['docs']]})
            docs = keep_docs(out['docs'], used_parts, question)
            docs += variant_notes(used_parts, docs, retriever)
        if carry:
            seen = {d['chunk_id'] for d in carry}
            docs = carry + [d for d in docs if d['chunk_id'] not in seen]
            if len(docs) == len(carry):
                result, shown = first  # 새 근거가 없으면 다시 부르지 않고 첫 일부 답을 쓴다
                break
        if not docs and not (part and task.kind == 'role'):
            if query and not relax:
                relax = True  # [왜] 품번 필터 안에서 0건이면 필터를 풀어 한 번 더 찾는다(예전 검색 에이전트의 no_result 재시도와 같음)
                continue
            break  # 보여 줄 근거가 하나도 없으면 LLM을 부르지 않는다
        user = render(question, task, docs, part) + memory_context(payload.get('approved_memories') or [])
        result, shown = chat('docs_answer', PROMPT, user, DocsAnswer), docs
        calls += 1
        if result.grade == 'enough' or not result.next_query.strip():
            break
        if result.grade == 'partial':
            # [왜] 일부만 답하고 끝내면, 검색어가 질문의 한쪽만 겨눈 경우 정답 근거 없이 답했다(v3-20: 'H 접미사 뜻'만 찾아 SS14H · SS14 정격표를 못 봄,
            #      사전 등록 #49). 빠진 부분을 다른 검색어로 한 번 더 찾고, 앞 근거와 함께 다시 답한다(검색 2번 상한 안)
            carry, first = shown, (result, shown)
        query = result.next_query.strip()  # 근거가 없거나 모자라다고 채점했으면 LLM이 준 다른 검색어로 한 번만 다시
        if result.grade == 'partial' and ASSEMBLY.search(question+' '+task.goal+' '+task.output) \
                and ASSEMBLY.search(' '.join(result.missing)):
            query += ' polarity before assembly'  # 실장 전 확인사항을 묻는데 정격·포장 행만 재검색하는 누락을 막는다
    needs_web = (not result or result.grade in ('partial', 'none') or bool(result.missing))
    if web_search is not None and task.kind != 'role' and needs_web:
        terms = (result.next_query.strip() if result and result.next_query.strip() else query or task.query)
        external = web_search(web_parts, terms)  # 실제 Exa 클라이언트는 공급자 오류를 빈 근거로 닫는다.
        if external:
            searches.append({'query': terms, 'parts': web_parts, 'provider': 'exa',
                             'top': [[d['file'], d.get('page', '')] for d in external]})
            # Keep the support for a partial answer, including one from the first search.
            # Other parts' rejected rows must not compete with the manufacturer table.
            prior, prior_docs = (result, shown) if result and result.grade != 'none' else first or (None, [])
            cited_internal = citations(prior.answer) if prior else set()
            combined = external + [d for d in prior_docs if str(d['chunk_id']) in cited_internal]
            web_result = chat('docs_answer', PROMPT, render(question, task, combined, part)
                              + memory_context(payload.get('approved_memories') or []), DocsAnswer)
            calls += 1
            if (web_result.grade != 'none' and web_result.answer.strip()) or prior is None:
                result, shown = web_result, combined
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
    valid = {str(d['chunk_id']) for d in shown} | ({'넷리스트'} if part and task.kind == 'role' else set())
    allowed_memories = memory_sources(payload.get('approved_memories') or [])
    if any(c.startswith('승인사례:') for c in citations(answer)) or set(result.memory_refs) - allowed_memories:
        return report('fail', 'historical memory cannot support current claims or reference an unprovided case', reason=Reason.VERIFY_FAILED, docs=shown)
    cited = citations(answer)
    if cited - valid or not cited & valid or has_uncited_sentence(answer):
        # A single bounded regeneration uses the same evidence; never guess a citation for the model.
        correction = render(question, task, shown, part) + memory_context(payload.get('approved_memories') or [])
        correction += ('\nCitation correction: the previous output had unsupported IDs or sentences without evidence citations. '
                       'Answer only the assigned task in the Supervisor brief, not the other tasks in the full question. '
                       'Re-answer only from the evidence above, copying its allowed IDs exactly for every sentence. '
                       'Put missing facts for this task in missing, not unsupported absence claims in answer. '
                       'Do not invent support; use grade none if it is absent.')
        repaired = chat('docs_answer', PROMPT, correction, DocsAnswer)
        calls += 1
        repaired_answer = repaired.answer.strip()
        repaired_cites = citations(repaired_answer)
        if any(c.startswith('승인사례:') for c in repaired_cites) or set(repaired.memory_refs) - allowed_memories:
            return report('fail', 'historical memory cannot support current claims or reference an unprovided case',
                          reason=Reason.VERIFY_FAILED, docs=shown)
        if repaired.grade != 'none' and repaired_cites & valid:
            result, answer = repaired, repaired_answer
    answer, dropped_fake = drop_fake_citations(answer, valid)
    dropped_uncited = has_uncited_sentence(answer)
    if dropped_uncited:
        # Keep only already-cited sentences; never attach a neighbour's citation to an unsupported claim.
        answer = ' '.join(s for s in re.split(r'(?<=[.。])\s+', answer) if citations(s) & valid).strip()
    cited = citations(answer)
    if not cited & valid:
        problem = f'cited evidence that was not provided {dropped_fake}' if dropped_fake else 'answer has no citation'
        return report('fail', problem, reason=Reason.VERIFY_FAILED, docs=shown)
    # A bare partial label is not remaining work; explicit missing facts, retries and removed claims still are.
    complete = result.grade == 'enough' or not result.next_query.strip()
    status = 'ok' if complete and not result.missing and not dropped_fake and not dropped_uncited else 'partial'
    summary = (f'{status}: answered from {len(cited & valid)} evidence'
               + ('; removed unverified sentences' if dropped_fake or dropped_uncited else '')
               + looked_up + (f'; missing {", ".join(result.missing)}' if result.missing else ''))
    return report(status, summary, answer=answer, memory_refs=list(dict.fromkeys(result.memory_refs)),
                  evidence_ids=sorted(cited & valid), missing=result.missing[:6], docs=shown)
