"""RAG 에이전트: 지시서의 검색어로 찾고, 근거 채점과 답 쓰기를 LLM 한 번으로 하고, 인용을 코드로 검사해 보고한다.

- 역할: 검색(지시서의 첫 검색어 · 질문의 품번 필터, BM25 + voyage-4-large → rerank-3 상위 5) → 다른 품번 줄 · 다른 판 거르기(코드) →
  근거 채점 + 답 쓰기(Haiku 1번: 질문 · 지시서 · 대상 회로 · 청크를 함께 받는다) → 근거가 없거나 일부만 답했으면 LLM이 준 다른 검색어로 1번만 다시(일부 답은 앞 근거와 함께, #49) →
  인용 검사(코드: 보여 준 청크 번호와 넷리스트만) → 보고(ok · partial · fail + 200자 요약 + 부분 답 + 근거).
  지시서에 품번(parts)이 있으면 그 품번 문서 안에서만 찾는다(재계획이 넣는다, 설계 v2). 품번 없이 정격(specs)만 있으면
  찾기 도구(find, 카드 찾기)로 그 정격과 같은 값의 품번을 먼저 찾고 그 문서 안에서 찾는다(11-07 R1 dev G4).
  근거를 끝내 못 찾으면 거절을 정하지 않고 다시 찾을 사유(no_result · all_rejected)로 보고한다.
  역할 할 일처럼 검색어가 없으면 검색 없이 넷리스트만으로 답한다.
- 하지 않는 일: 할 일 정하기(Supervisor), 숫자 비교 · 대체 판정(Spec 에이전트와 `backend/judge/`), 여러 할 일 합치기(종합),
  LLM 직접 호출(`chat`을 받아 쓴다. 실제 연결은 `llm.node_chat`).
- 출처: backend/multi_agent/MULTI_AGENT.md "구조 결정"의 RAG 에이전트(예전 채점 Luna · 생성 Haiku를 한 호출로 합침, 채점은 질문 맥락을
  가진 쪽이 한다), backend/graph/nodes.py(검색 · 다른 품번 줄 거르기 · 인용 함수를 그대로 쓴다)
"""
import base64
import contextvars
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.graph.mcp_retriever import RetrievalUnavailableError
from backend.graph.memory import memory_context, memory_sources
from backend.judge.pdf_claims import check_pdf_lines, row_sentence, sentence_digest
from backend.services.exa import OTHER_MANUFACTURER, SearchBudgetExhausted, slot_in_use
from backend.graph.nodes import NOT_FOUND, WORD, citations, circuit_mechanism, find_parts, netlist_block, other_part_row, search, unsupported_numbers
from backend.multi_agent.contracts import MAX_SEARCHES, Reason, Task, TaskReport
from backend.multi_agent.revisions import requested_revisions, revision_matches, revisions_for_part
from backend.rag.units import to_si
from backend.rag.card_read import read_code_values
from backend.rag.card_find import doc_packages, load_cards

PROMPT = (Path(__file__).resolve().parents[2] / 'prompts' / 'docs_answer.md').read_text(encoding='utf-8')
CITE_GROUP = re.compile(r'\[([^\]]*)\]\]*')  # 중첩 인용의 바깥 래퍼까지 함께 정리한다


class DocsAnswer(BaseModel):
    """근거 채점 + 답 쓰기 LLM의 답안지."""
    grade: Literal['enough', 'partial', 'none'] = Field(description='Does the evidence answer the task: enough, partial or none')
    answer: str = Field(default='', description='Korean answer citing only the exact allowed evidence IDs from the input; never renumber or cite page numbers; empty when grade is none')
    memory_refs: list[str] = Field(default_factory=list, max_length=5, description='Historical source IDs consulted; never cite these in answer')
    missing: list[str] = Field(default_factory=list, description='Values or facts the task needs that the evidence does not give')
    next_query: str = Field(default='', max_length=200, description='When grade is none or partial: a different English search query to try once (for partial, aimed at what is missing)')


class PdfAnswer(DocsAnswer):
    pdf_rows: list[Literal['W1', 'W2', 'W3']] = Field(
        description='Select only the PDF rows answering this task. The server renders their exact part, values and units.')
    answer: str = Field(default='', description='Only sentences supported by internal numeric citations. Leave empty for PDF facts.')


class PdfOnlyAnswer(PdfAnswer):
    answer: Literal[''] = ''


class RecoveryFigure(BaseModel):
    """Figure 6에서 읽은 전류 표식만 보관하는 임시 검증 결과."""
    labels: list[str] = Field(default_factory=list, max_length=12)
    forward_current: float
    reverse_peak: float
    recovery_end: float
    arrow_start: float
    arrow_end: float
    unit: Literal['A']
    start_on_zero_crossing: bool
    end_on_recovery: bool
    readable: bool


FIGURE_PROMPT = (
    '\nFigure evidence instructions: read only the current labels from the supplied official PDF figure. '
    'Report current levels rather than numeric time coordinates. Follow the vertical markers down to the waveform. '
    'Report the forward-current label, reverse peak, '
    'and the recovery-end marker; do not confuse the final zero level with the recovery-end marker. '
    'Do not infer an unlabelled value or a replacement/operating guarantee.'
)


def requested_parts(question: str) -> set[str]:
    """명시적으로 요청한 품번을 확인한다. 회로 기호와 계열 요청은 제외한다."""
    refs = {word for word in WORD.findall(question)
            if re.fullmatch(r'(?:TP|SW|IC|LS|D|U|C|R|J|F|Q|L|Y|X|K|T)\d+', word, re.I)}
    parts = {part.upper() for part in find_parts(question, refs)}
    return {part for part in parts
            if not part.endswith('.PDF') and not re.search(
                re.escape(part) + r'\s*(?:시리즈|계열|family|series)', question, re.I)}


def _mentions_exact_part(doc: dict, exact_parts: set[str]) -> bool:
    """Whether a card explicitly names one of the requested exact parts."""
    if not exact_parts:
        return True
    names = {str(p).upper() for p in doc.get('doc_parts') or ()}
    names.update(str(p).upper() for p in doc.get('parts') or ())
    if names & exact_parts:
        return True
    # External cards may expose the part only in the row/title metadata.
    haystack = ' '.join(str(doc.get(key) or '') for key in ('file', 'title', 'row', 'content'))
    return any(re.search(r'(?<![A-Z0-9])' + re.escape(part) + r'(?![A-Z0-9])', haystack.upper())
               for part in exact_parts)


def keep_docs(docs: list[dict], parts: list[str], question: str, exact_parts: set[str] | None = None) -> list[dict]:
    """LLM에 보여 주기 전에 코드로 거른다: 물은 품번이 아닌 다른 품번만 적힌 표 줄, 질문이 요청한 개정판이 아닌 문서."""
    # [왜] 단일 그래프 채점 노드의 결정적 검사와 같다. 인용한 청크에 대상 품번이 있게 하는 첫 관문이다(설계 그림 인용 검사)
    return [d for d in docs if _mentions_exact_part(d, exact_parts or set())
            and not other_part_row(d, parts)
            and revision_matches(question, d.get('file'), d.get('doc_parts') or d.get('parts'), parts)]


VARIANT = re.compile(r'C(A?H?)$|(?<=\d)H$', re.I)  # 양방향(…C · …CA · …CAH) · AEC-Q101(…H) 품번: 값 표에는 기본 품번으로만 적힌다
VARIANT_QUERY = ('bidirectional bi-directional C CA suffix electrical characteristics apply in both directions IR limit double'
                 ' "H" means AEC-Q101 qualified ordering information')
NOTE_WORDS = re.compile(r'bi-?directional|both directions|AEC-?Q101', re.I)
ASSEMBLY = re.compile(r'실장|조립|\b(?:pre[- ]?)?(?:assembl|mount)', re.I)
# 실장·조립 질문의 답에 방향성 근거가 포함됐는지 결정적으로 확인한다.
POLARITY = re.compile(r'극성|캐소드|cathode|polarity|띠|band|음극|양극', re.I)
DETAILS = re.compile(r'측정|시험|파형|그림|fig(?:ure)?|기준|절차|조건|온도|지속|시간', re.I)


def enrich_rating_query(query: str, question: str, task: Task) -> str:
    """정격 질문에서 검색어가 생략하기 쉬운 시험 표·그림 단서를 보강한다.

    검색어 자체를 다른 품번이나 값으로 바꾸지 않고, 질문에 실제로 요청된
    세부 항목에 해당하는 데이터시트 용어만 덧붙인다. 이로써 trr의 시험
    회로/파형, IFSM의 파형·온도 조건, VF/IR 비교의 electrical table이
    상위 검색 결과에서 빠지는 것을 줄인다.
    """
    if task.kind != 'rating':
        return query
    additions: list[str] = []
    if DETAILS.search(question):
        additions.append('datasheet test conditions waveform figure')
    if re.search(r'역회복|trr|recovery', question, re.I):
        additions.append('IF IR Irr reverse recovery time test circuit')
    if re.search(r'서지|IFSM|돌입|반파|지속|온도', question, re.I):
        additions.append('absolute maximum ratings TA single half sine wave')
    if re.search(r'VF|IR|순방향 전압|역방향 전류|차이|구분|전류', question, re.I):
        additions.append('electrical characteristics VF IR IF VRRM IFSM package')
    extra = ' '.join(dict.fromkeys(additions))
    if not extra or extra.casefold() in query.casefold():
        return query
    return f'{query} {extra}'.strip()


def rating_search_k(question: str, task: Task) -> int:
    """상세 정격·시험 질문만 근거 후보 폭을 넓힌다(일반 질문은 기존 k=5)."""
    return 20 if task.kind == 'rating' and (
        DETAILS.search(question)
        or re.search(r'역회복|trr|recovery|IFSM|서지|VF|IR|순방향 전압|역방향 전류|차이|구분', question, re.I)
    ) else 5


def retrieve_with_k(retriever, query: str, *, parts=None, k: int = 5):
    """운영 timed_tool과 기존 테스트용 2-인자 callable을 모두 지원한다."""
    if k > 5 and parts and len(parts) > 1:
        # Give each explicitly named part evidence space instead of allowing
        # the better-ranked family to fill the whole comparison context.
        # [왜] 품번별 검색은 서로의 결과를 기다릴 이유가 없어 동시에 부른다(검색 1번 약 1.2초, 11-14 v3-20은 6번이 줄지어 7.5초)
        # [주의] 문맥(contextvars)을 복사해 넘긴다. 안 넘기면 단계 시간 기록과 Langfuse 추적에서 검색이 빠진다(card_specs.py와 같은 방법)
        with ThreadPoolExecutor(max_workers=len(parts)) as pool:
            futures = [pool.submit(contextvars.copy_context().run, retrieve_with_k, retriever, query, parts=[named], k=max(5, k // len(parts)))
                       for named in parts]
            per_part = [future.result() for future in futures]  # 품번 순서대로 모아 예전과 같은 순서를 지킨다
        rows, seen = [], set()
        for found in per_part:
            for doc in found:
                if doc['chunk_id'] not in seen:
                    rows.append(doc)
                    seen.add(doc['chunk_id'])
        return rows[:k]
    if k == 5:
        return retriever(query, parts=parts)
    try:
        return retriever(query, parts=parts, k=k)
    except TypeError as error:
        # Instrumentation/adapters may expose the old two-argument callable.
        # Retry only for a signature mismatch; preserve internal TypeErrors.
        message = str(error).lower()
        if 'unexpected keyword' not in message and 'positional argument' not in message:
            raise
        return retriever(query, parts=parts)


def trr_condition_gap(question: str, docs: list[dict]) -> bool:
    """측정조건을 요구했는데 내부 카드가 IF/IR/Irr를 모두 보존했는지 확인한다."""
    asks_detail = bool(re.search(r'역회복|trr|reverse recovery', question, re.I)) and bool(
        re.search(r'측정|시험|조건|파형|IF\b|IR\b|Irr\b', question, re.I))
    if not asks_detail:
        return False
    text = ' '.join(str(d.get('content') or '') for d in docs)
    return not all(re.search(rf'\b{name}\s*=\s*', text, re.I) for name in ('IF', 'IR', 'Irr'))


def fetch_variant_notes(parts: list[str], retriever) -> list[dict]:
    """양방향 · H 품번이면 품번 규칙 주석 후보를 검색한다. 해당 품번이 없거나 검색 도구가 실패하면 []."""
    if not any(VARIANT.search(p.strip()) for p in parts):
        return []
    try:
        return retriever(VARIANT_QUERY, parts=list(parts))
    except RetrievalUnavailableError:
        return []  # 주석은 보탬이라 도구가 실패해도 본 검색 결과로 답한다


def variant_notes(parts: list[str], docs: list[dict], retriever, found: list[dict] | None = None) -> list[dict]:
    """물은 품번이 양방향 · H 품번이면 그 문서의 품번 규칙 주석('특성은 양방향 모두 적용' · 'IR 한도 2배' · 'H는 AEC-Q101')을 더 찾는다.

    [왜] 값 표는 기본 품번(SMAJ6.5A)으로만 적고 양방향 · H 품번은 주석으로만 연결한다. 청킹 v4부터 주석이 행 카드 끝이 아니라 따로 된
         주석 카드라 표 행 검색 상위 10개에 들지 못해, SMAJ6.5CA 누설전류를 물으면 근거가 SMAJ6.5A 행 하나뿐이라 거절했다(v3 v3-19, 11-09)
    """
    if found is None:  # found: 본 검색과 동시에 미리 찾아 둔 주석 후보(없으면 지금 찾는다)
        found = fetch_variant_notes(parts, retriever)
    seen = {d.get('chunk_id') for d in docs}
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


def has_uncited_sentence(answer: str, docs: list[dict] = ()) -> bool:
    """A cited fact must not let an unsupported sentence ride into a joined answer. With docs, a number the cited chunk lacks counts as unsupported."""
    return any(s.strip() and (not citations(s) or unsupported_numbers(s, docs)) for s in re.split(r'(?<=[.。])\s+', answer))


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


def suffix_comparison_facts(parts: list[str], docs: list[dict]) -> tuple[str, bool]:
    """Keep available principal ratings in an H/base comparison without model omissions."""
    wanted = {p.upper() for p in parts}
    if not any(p.endswith('H') and p[:-1] in wanted for p in wanted):
        return '', False
    codes = ['IF_AV', 'VRRM', 'IFSM', 'VF', 'IR']
    source_docs = [d for d in docs if d.get('source_type') != 'external_web']
    keys = list(dict.fromkeys(d['document_key'] for d in source_docs if d.get('document_key')))
    loaded = load_cards(keys) if keys else {}
    available = list(source_docs)
    for key, document in loaded.items():
        if document['file'] not in {d['file'] for d in source_docs}:
            continue
        available.extend({**card, 'file':document['file'], 'document_key':key, 'doc_parts':document['parts']}
                         for card in document['cards'])
    cards = [{**d, 'document':d['file'], 'row':d.get('row')} for d in available]
    metadata = {d['file']:d.get('doc_parts') or [] for d in available}
    values = read_code_values(cards, codes, metadata)
    lines, covered = [], set()
    for part in sorted(wanted):
        for code in codes:
            found = [r for r in values if r['part'].upper() == part and r['code'] == code]
            if not found:
                continue
            row = next((r for r in found if '25' in str(r.get('test_condition') or '')), found[0])
            cite = row['citation']
            if all(d['chunk_id'] != cite['chunk_id'] for d in docs):
                docs.append(next(d for d in available if d['chunk_id'] == cite['chunk_id']))
            condition = row.get('test_condition') or cite.get('table') or ''
            lines.append(f"{part} · {code}: {row['source_value_text']} ({condition}) [{cite['chunk_id']}].")
            covered.add((part, code))
        package_docs = [d for d in docs if part.lower() in {str(x).lower() for x in d.get('doc_parts') or []}]
        if not any(doc_packages({'cards':[d], 'texts':[d['content']]}) for d in package_docs):
            keys = list(dict.fromkeys(d['document_key'] for d in package_docs if d.get('document_key')))
            for key, document in loaded.items():
                if key not in keys:
                    continue
                for card in document['cards'] + document.get('text_cards', []):
                    if not doc_packages({'cards':[card], 'texts':[card['content']]}):
                        continue
                    extra = {**card, 'file':document['file'], 'document_key':key,
                             'doc_parts':document['parts']}
                    if other_part_row(extra, [part]):
                        continue
                    if all(d['chunk_id'] != extra['chunk_id'] for d in docs):
                        docs.append(extra)
                    package_docs.append(extra)
                    break
        for doc in package_docs:
            packages = doc_packages({'cards':[doc], 'texts':[doc['content']]})
            if packages:
                lines.append(f"{part} · 패키지: {', '.join(packages)} [{doc['chunk_id']}].")
                break
    qualified = any('AEC-Q101' in d.get('content','') and
                    any(p.endswith('H') and p.lower() in {str(x).lower() for x in d.get('doc_parts') or []} for p in wanted)
                    for d in docs)
    if qualified and lines:
        feature = next(d for d in docs if 'AEC-Q101' in d.get('content', ''))
        lines.insert(0, f"선택한 H 제품의 공식 문서 FEATURES에는 AEC-Q101 qualified가 표기되어 있습니다 [{feature['chunk_id']}].")
        lines.append('나열한 정격과 AEC-Q101 표기만으로 물리적 동일품이나 이 보드의 인증·동작 보장을 '
                     f"단정하지 않습니다 [{feature['chunk_id']}].")
    return '\n'.join(lines), bool(qualified and all((p,c) in covered for p in wanted for c in codes))


def surge_rating_facts(question: str, docs: list[dict], intent: str = '') -> str:
    """Expose mechanically verified IFSM/IF rows from the same source document.

    Keep the source values and the boundary of an explicitly single-half-sine
    rating. Never invent an initial TJ or turn a table value into a board guarantee.
    """
    if not re.search(r'IFSM|서지|돌입|반파|surge|single half sine', question + ' ' + intent, re.I):
        return ''
    wanted = requested_parts(question)
    if not wanted:
        return ''
    source_docs = [d for d in docs if d.get('source_type') != 'external_web' and d.get('file')]
    keys = list(dict.fromkeys(d['document_key'] for d in source_docs if d.get('document_key')))
    loaded = load_cards(keys) if keys else {}
    available = list(source_docs)
    for key, document in loaded.items():
        if document['file'] in {d['file'] for d in source_docs}:
            available.extend({**card, 'file':document['file'], 'document_key':key, 'doc_parts':document['parts']}
                             for card in document['cards'])
    lines: list[str] = []
    for file in dict.fromkeys(d['file'] for d in source_docs):
        selected = [d for d in available if d['file'] == file]
        cards = [{**d, 'document': file, 'row': d.get('row')} for d in selected]
        metadata = {file: list(dict.fromkeys(
            str(part) for d in selected for part in (d.get('doc_parts') or d.get('parts') or [])))}
        values = read_code_values(cards, ['IF_AV', 'IFSM'], metadata)
        by_part: dict[str, dict[str, dict]] = {}
        def row_score(value):
            source = next(d for d in available if d['chunk_id'] == value['citation']['chunk_id'])
            return (bool(re.search(r'single half sine', source['content'], re.I)),
                    bool(value.get('test_condition')))
        for value in values:
            found = by_part.setdefault(value['part'].upper(), {})
            previous = found.get(value['code'])
            if previous is None or row_score(value) > row_score(previous):
                found[value['code']] = value
        for part, found in sorted(by_part.items()):
            if part not in wanted or not {'IF_AV', 'IFSM'} <= set(found):
                continue
            surge, continuous = found['IFSM'], found['IF_AV']
            surge_cite, continuous_cite = surge['citation']['chunk_id'], continuous['citation']['chunk_id']
            source = next(d for d in available if d['chunk_id'] == surge_cite)
            parameter = re.search(r'PARAMETER:\s*([^|]+)', source['content'])
            condition = surge.get('test_condition') or (parameter[1].strip() if parameter else '')
            if surge['citation'].get('table'):
                condition += '; ' + surge['citation']['table']
            lines.append(
                f"{part} · IFSM: {surge['source_value_text']} ({condition}) [{surge_cite}]; "
                f"IF_AV: {continuous['source_value_text']} [{continuous_cite}]."
            )
            for row in (surge, continuous):
                cid = row['citation']['chunk_id']
                if all(d['chunk_id'] != cid for d in docs):
                    docs.append(next(d for d in available if d['chunk_id'] == cid))
            if re.search(r'single half sine', condition, re.I):
                lines.append('이는 단발 반파의 서지 정격이므로 반복·연속 전류 정격으로 사용하지 않으며, '
                             '표의 TA는 주변 온도이므로 초기 TJ로 바꾸어 읽지 않고, '
                             f'다른 파형·지속시간·온도나 실제 보드의 동작을 이 값으로 보장하지 않습니다 [{surge_cite}].')
    return '\n'.join(lines)


def _reconcile_enriched_missing(result: DocsAnswer, question: str, *, recovery=False, suffix=False) -> DocsAnswer:
    """Retire only stale gaps covered by an emitted, validated answer packet.

    A comparison of documented H/base properties does not require a verbatim
    suffix-definition sentence unless the user actually asks for that quote.
    Unknown ratings, extra test-circuit details and guarantees remain missing.
    """
    quote = re.search(r'원문[^。\n]{0,20}(?:그대로|인용)|직접[^。\n]{0,12}정의|정의[^。\n]{0,12}문장|verbatim|literal|explicit definition', question, re.I)
    extra = re.compile(r'저항|상승|임피던스|오실로|resistan|rise.time|impedance|oscillo|수명|고장|MTBF|MTTF|방사|radiation|보장|판본|revision', re.I)
    recovery_topic = re.compile(r'trr|역회복|reverse recovery|측정\s*(?:기준|조건|회로)|test circuit|\b(?:IF|IR|Irr)\b', re.I)
    suffix_topic = re.compile(r'접미|suffix|\bH\b|H\s*표기|패키지|package|AEC', re.I)
    remaining = []
    for item in result.missing:
        resolved = False
        if not extra.search(item + ' ' + question):
            if recovery and recovery_topic.search(item):
                resolved = not re.search(r'\b(?:VF|VZ|IFSM|VRRM|CJ|TJ|ESD)\b', item, re.I)
            if suffix and not quote and suffix_topic.search(item):
                resolved = not re.search(r'\b(?:trr|CJ|TJ|ESD)\b|\d(?:\.\d+)?\s*(?:[µunm]?[AV]|ns|ms|°?C|Hz)\b', item, re.I)
        if not resolved:
            remaining.append(item)
    if remaining == result.missing:
        return result
    update = {'missing': remaining}
    if not remaining:
        update.update(grade='enough', next_query='')
    return result.model_copy(update=update)


def assembly_polarity_gap(question: str, task, answer: str) -> bool:
    """실장·조립 확인을 묻는데 답에 극성 표지가 없으면 True로 판정한다."""
    brief = f'{question} {task.goal} {task.output}'
    return bool(ASSEMBLY.search(brief)) and not POLARITY.search(answer or '')


def docs_agent(payload: dict, *, retriever, chat, find=None, web_search=None, web_search_fallback=None) -> dict:
    """그래프 노드(Send 대상): 할 일 하나를 끝까지 하고 보고서 하나를 메모장 `reports`에 이어 붙인다."""
    task = Task.model_validate(payload['task'])
    question, part, rnd = payload['question'], payload.get('target_part') or {}, payload.get('round') or 1
    revision_text = ' '.join((question, payload.get('conditions', '')))
    query, searches, shown, result, calls, relax = task.query.strip(), [], [], None, 0, False
    references = []
    grade2_budget_exhausted = False
    grade3_budget_exhausted = False
    filter_parts, looked_up = list(task.parts), ''
    web_parts = list(filter_parts)
    # 발주 품번을 명시한 질문에서는 모델이 추정한 형제 품번으로 재검색해도 그 값을 인용하지 않는다.
    current_question = question
    if question.startswith('이전 사용자 입력:\n'):
        _, separator, latest = question.rpartition('\n현재 질문:\n')
        if separator:
            current_question = latest
    conditions = payload.get('conditions', '')
    if conditions:
        current_question = current_question.removeprefix(f'사용 조건: {conditions}\n')
    exact_parts = set()
    if re.search(r'품번|발주서|exact part|ordering code|part number', current_question, re.I):
        named = requested_parts(current_question)
        selected = {p.upper() for p in filter_parts} & named
        exact_parts = selected or (named if len(named) == 1 else set())
    if exact_parts:
        filter_parts = sorted(exact_parts)
        web_parts = list(filter_parts)
    # A suffix comparison must retain both explicitly named documents even
    # when the planner assigns only one side to an individual rating task.
    named = requested_parts(current_question)
    compared = {p for p in named if (p.endswith('H') and p[:-1] in named) or p + 'H' in named}
    if task.kind == 'rating' and not exact_parts and compared and (
            not filter_parts or compared & {p.upper() for p in filter_parts}):
        filter_parts = sorted(compared)
        web_parts = list(filter_parts)
    elif task.kind == 'rating' and compared and exact_parts and exact_parts <= compared:
        # An explicit H/base comparison may contain the word "품번" and
        # therefore enter the exact-part guard above. Preserve both named
        # members; this is still a closed comparison set, not a family
        # expansion.
        exact_parts = set(compared)
        filter_parts = sorted(compared)
        web_parts = list(filter_parts)
    # 현재 내부 코퍼스의 제조사는 TSC다. 동명 품번이 있어도 Infineon 질의에 그 값을 쓰지 않는다.
    maker_text = ' '.join((question, task.query))
    infineon = bool(re.search(r'인피니언|\binfineon(?![A-Za-z])', maker_text, re.I))
    other_maker = bool(OTHER_MANUFACTURER.search(question))
    foreign_rating = web_search is not None and task.kind != 'role' and (infineon or OTHER_MANUFACTURER.search(maker_text))
    carry, first = [], None  # 일부만 답한 근거와 그 답(다시 찾을 때 근거를 함께 보이고, 못 늘리면 그 답을 쓴다)
    search_k = rating_search_k(current_question, task)

    def report(status: str, summary: str, **kw) -> dict:
        # Only source locators cross into the persisted graph state.
        if 'docs' in kw:
            # Keep verified PDF row cells/units/conditions: the final checker
            # expands a bare [Wn] into this canonical sentence and must not
            # regenerate the row with a free-form model answer.
            kw['docs'] = [{**{k: v for k, v in doc.items() if k not in {'content', 'figure'}},
                           'sentence_sha256': sentence_digest(row_sentence(doc))}
                          if doc.get('source_type') == 'external_web' else doc for doc in kw['docs']]
        r = TaskReport(task=task.id, agent='docs', status=status, summary=summary[:200], searches=searches, llm_calls=calls, round=rnd, **kw)
        return {'reports': [r.model_dump(mode='json')], 'path': ['문서']}

    if task.kind == 'role' and part:
        mechanism = circuit_mechanism(part)
        if mechanism:
            return report('ok', 'operating path verified from declared netlist pins',
                          answer=mechanism, evidence_ids=['넷리스트'], docs=[])
    if not filter_parts and task.specs and find is not None:
        try:
            filter_parts = lookup_parts(task, find)
        except RetrievalUnavailableError as error:
            return report('fail', f'spec table tool failure: {error.kind}', reason=Reason.SEARCH_ERROR)
        if not filter_parts:
            # [왜] 그 정격의 품번이 표에 없다. 거절을 정하지 않고 다시 찾을 사유로 올린다(재계획이 조건을 고쳐 볼 수 있다)
            return report('fail', 'no part in the spec table has the described ratings', reason=Reason.NO_RESULT)
        looked_up = f"; parts with the described ratings: {', '.join(filter_parts)}"
    max_searches = int(os.getenv('DOCS_MAX_SEARCHES', str(MAX_SEARCHES)) or MAX_SEARCHES)  # [왜] A/B용. 기본은 MAX_SEARCHES(2)
    for _ in range(max(1, max_searches)):  # [왜] 검색은 할 일마다 2번까지(AGENTS 6, MULTI_AGENT.md "구조 결정"의 상한)
        docs = []
        if query:
            find = (lambda q, parts=None: retrieve_with_k(retriever, q, parts=None, k=search_k)) if relax \
                else (lambda q, parts=None: retrieve_with_k(retriever, q, parts=parts, k=search_k))
            if filter_parts and not relax:
                # [왜] 지시서의 품번(재계획이 넣음)이나 정격으로 찾은 품번이 있으면 그 품번 문서 안에서만 찾는다
                find = lambda q, parts=None: retrieve_with_k(retriever, q, parts=list(filter_parts), k=search_k)
            search_query = enrich_rating_query(query, current_question, task)
            early_notes = None
            if filter_parts and not relax and not foreign_rating and any(VARIANT.search(p.strip()) for p in filter_parts):
                # [왜] 품번이 이미 정해졌으면 주석 검색은 본 검색 결과를 기다릴 필요가 없다. 본 검색과 동시에 출발시킨다
                notes_pool = ThreadPoolExecutor(max_workers=1)
                early_notes = notes_pool.submit(contextvars.copy_context().run, fetch_variant_notes, list(filter_parts), retriever)
                notes_pool.shutdown(wait=False)
            out = search({'question': question, 'target_part': part, 'query': search_query}, find)
            if out['retrieval_error']:
                return report('fail', f"search tool failure: {out['retrieval_error'].get('kind', '')}", reason=Reason.SEARCH_ERROR)
            used_parts = list(filter_parts) if filter_parts and not relax else out['parts']
            if not web_parts:
                # 내부 재검색이 품번 필터를 풀어도 외부 검색은 처음 맡은 품번을 유지한다.
                task_words = {word.upper() for word in WORD.findall(task.query)}
                web_parts = filter_parts or [p for p in out['parts'] if p.upper() in task_words] or out['parts']
            # [왜] 필터를 푼 재검색은 query · parts가 첫 검색과 같게 찍혀 같은 호출을 되풀이한 것처럼 보인다.
            #      filter_released로 이 검색이 품번 필터 없이(코퍼스 전체에서) 찾았는지 남긴다(강사 11/16 코멘트 ③)
            searches.append({'query': out['query'], 'parts': used_parts, 'filter_released': relax,
                             'top': [[d['file'], d['page']] for d in out['docs']]})
            if not foreign_rating:
                docs = keep_docs(out['docs'], used_parts, revision_text, exact_parts)
                # Variant notes are a second retrieval and must obey the same
                # exact part/revision boundary as the primary result.
                docs = keep_docs(docs + variant_notes(used_parts, docs, retriever, found=early_notes.result() if early_notes else None),
                                 used_parts, revision_text, exact_parts)
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
        facts = ''
        if task.kind == 'rating':
            suffix_facts, _ = suffix_comparison_facts(filter_parts, docs)
            facts = '\n'.join(filter(None, [suffix_facts, surge_rating_facts(current_question, docs, task.query + ' ' + task.goal)]))
        user = render(question, task, docs, part) + memory_context(payload.get('approved_memories') or [])
        if facts:
            user += '\nValidated card readings for the comparison (retain their source IDs):\n' + facts
        result, shown = chat('docs_answer', PROMPT, user, DocsAnswer), docs
        calls += 1
        # [왜] enough여도 실장 전 확인을 물었는데 극성 표지가 없으면 정격·포장만 답하고 끝낸 경우다
        #      (배포 HTTP T4 2026-11-11_230956: normal polarity_present=False, attack은 True). partial+#49와 같이 한 번 더 찾는다.
        if (result.grade == 'enough' and assembly_polarity_gap(question, task, result.answer)
                and os.getenv('DOCS_RETRY_PARTIAL', '1') != '0'):
            carry, first = shown, (result, shown)
            base = result.next_query.strip() or query
            query = base if 'polarity before assembly' in base else f'{base} polarity before assembly'.strip()
            continue
        if result.grade == 'enough' or not result.next_query.strip():
            break
        if result.grade == 'partial':
            # [왜] 일부만 답하고 끝내면, 검색어가 질문의 한쪽만 겨눈 경우 정답 근거 없이 답했다(v3-20: 'H 접미사 뜻'만 찾아 SS14H · SS14 정격표를 못 봄,
            #      사전 등록 #49). 빠진 부분을 다른 검색어로 한 번 더 찾고, 앞 근거와 함께 다시 답한다(검색 2번 상한 안)
            if os.getenv('DOCS_RETRY_PARTIAL', '1') == '0':
                break  # [왜] 속도 A/B용. 기본(1)은 #49 유지. 0이면 partial 재검색만 끄고 첫 일부 답으로 끝낸다(none 재검색은 그대로)
            carry, first = shown, (result, shown)
        query = result.next_query.strip()  # 근거가 없거나 모자라다고 채점했으면 LLM이 준 다른 검색어로 한 번만 다시
        if result.grade == 'partial' and ASSEMBLY.search(question+' '+task.goal+' '+task.output) \
                and ASSEMBLY.search(' '.join(result.missing)):
            query += ' polarity before assembly'  # 실장 전 확인사항을 묻는데 정격·포장 행만 재검색하는 누락을 막는다
    # A split PDF table may leave shared IF/IR conditions out of the internal
    # card even when trr itself was found. Treat that precise gap as a reason
    # to use the official verified-row path; simple trr lookups do not incur it.
    needs_web = (not result or result.grade in ('partial', 'none') or bool(result.missing)
                 or trr_condition_gap(current_question, shown))
    if ((web_search is not None or web_search_fallback is not None)
            and task.kind != 'role' and needs_web and (not other_maker or web_search_fallback is not None)):
        terms = (result.next_query.strip() if result and result.next_query.strip() else query or task.query)
        # Keep a user's manufacturer constraint even if the Supervisor abbreviates the task.
        for maker, pattern in (('Infineon', r'인피니언|\binfineon(?![A-Za-z])'),
                               ('TSC', r'대만반도체|타이완\s*세미|대만\s*세미|대만\s*반도체|\btsc\b|taiwan\s*semi')):
            if re.search(pattern, question, re.I) and maker.casefold() not in terms.casefold():
                terms += ' ' + maker
        requested = {p.upper() for p in web_parts}
        revisions = requested_revisions(revision_text)
        for revision in revisions:
            if revision not in terms.upper().split():
                terms += ' ' + revision
        early_fallback = None
        if web_search_fallback is not None and not slot_in_use(2):
            # [왜] 참고(3등급) 검색은 공식(2등급) 결과를 기다릴 이유가 거의 없다. v3에서 웹을 쓴 31문항 모두 3등급까지 갔다(11-14 P1).
            #      공식 검색과 함께 출발시키고, 원래 3등급을 부르던 자리에서 결과만 받는다. 공식 근거를 쓰거나 공식 예산이 소진되면 받은 결과는 버린다.
            #      다른 에이전트가 이미 공식 예산을 쓰는 중이면(그러면 3등급을 부르지 않는 규칙) 미리 출발시키지 않는다
            # [주의] 3등급은 요청당 1번 예산이라 공식 근거를 쓴 요청에서도 그 예산을 쓴다(사전 등록 「참고(3등급) 웹 검색 미리 출발」)
            fallback_pool = ThreadPoolExecutor(max_workers=1)
            early_fallback = fallback_pool.submit(contextvars.copy_context().run, web_search_fallback, web_parts, terms)
            fallback_pool.shutdown(wait=False)
        try:
            external_raw = web_search(web_parts, terms) if web_search is not None else []
        except SearchBudgetExhausted as error:
            # A concurrent official lookup is a request-budget boundary, not a
            # genuine empty search.  In particular, do not spend grade 3 to
            # compensate for another agent using the shared grade-2 slot.
            grade2_budget_exhausted = error.grade == 2
            searches.append({'query': terms, 'parts': web_parts, 'provider': 'exa',
                             'grade': error.grade, 'status': 'budget_exhausted'})
            external_raw = []
        external = [d for d in external_raw
                    if row_sentence(d) and d['doc_parts'][0].upper() in requested and
                    revision_matches(revision_text, d.get('file'), d.get('doc_parts'), web_parts)]
        def reference_candidates(items):
            found = []
            for item in items:
                title = item.get('file') or item.get('title', '')
                if not item.get('source_url') or not set(item.get('doc_parts') or ()) & requested:
                    continue
                haystack = f'{title} {item["source_url"]}'.upper()
                if revisions:
                    reference_parts = {str(p).upper() for p in item.get('doc_parts') or []} & requested
                    allowed = [revisions_for_part(revision_text, p) for p in reference_parts]
                    if not allowed or any(not editions or not any(
                            re.search(r'(?<![A-Z0-9])' + re.escape(edition) + r'(?![A-Z0-9])', haystack)
                            for edition in editions) for editions in allowed):
                        continue
                found.append(item)
            return found
        official_used = False
        if external:
            searches.append({'query': terms, 'parts': web_parts, 'provider': 'exa',
                             'top': [[d['file'], d.get('page', '')] for d in external]})
            # Keep the support for a partial answer, including one from the first search.
            # Other parts' rejected rows must not compete with the manufacturer table.
            prior, prior_docs = (result, shown) if result and result.grade != 'none' else first or (None, [])
            # Incomplete shared test conditions require a complete official row,
            # not a mixture with the earlier internal absence claim.
            if trr_condition_gap(current_question, prior_docs):
                prior, prior_docs = None, []
            cited_internal = citations(prior.answer) if prior else set()
            combined = external + [d for d in prior_docs if str(d['chunk_id']) in cited_internal]
            web_result = chat('docs_answer', PROMPT, render(question, task, combined, part)
                              + memory_context(payload.get('approved_memories') or []),
                              PdfAnswer if cited_internal else PdfOnlyAnswer)
            available = {doc['chunk_id'] for doc in external}
            selected = [f'[{cid}]' for cid in dict.fromkeys(web_result.pdf_rows) if cid in available]
            selected_answer = '\n'.join(filter(None, [web_result.answer, *selected]))
            canonical = check_pdf_lines(selected_answer, combined, expand=True)
            if canonical is None:
                return report('fail', 'answer disagrees with cited PDF row',
                              reason=Reason.VERIFY_FAILED, docs=combined)
            # Figure 6 is a second, independent official-PDF evidence item.  It
            # is read once with the image bytes and accepted only after the
            # table IF/IR/Irr conditions are cross-checked in code.  The image
            # itself is removed by report() before checkpoint persistence.
            figure_parent = next((doc for doc in external
                                  if isinstance(doc.get('figure'), dict)
                                  and doc['figure'].get('image_base64')), None)
            figure_doc = None
            if figure_parent is not None:
                figure = figure_parent['figure']
                try:
                    image = base64.b64decode(figure['image_base64'], validate=True)
                except (TypeError, ValueError):
                    image = None
                figure_doc = None
                if image:
                    figure_user = (
                        FIGURE_PROMPT + '\nOfficial figure evidence for the same PDF row follows. '
                        'Read the current levels aligned with the arrow markers, not numeric time-axis coordinates. '
                        'Return the signed current values and marker booleans required by the schema. '
                        'Do not infer an unlabelled value.\n\n' + row_sentence(figure_parent)
                    )
                    from backend.judge.pdf_claims import recovery_figure_doc
                    for attempt in range(2):
                        figure_reading = chat('docs_answer', PROMPT,
                                              figure_user, RecoveryFigure, image=image)
                        calls += 1
                        figure_doc = recovery_figure_doc(
                            figure_parent, figure_reading.model_dump(), 'W4')
                        if figure_doc is not None:
                            break
                        figure_user += ('\nThe previous reading did not match the independently extracted table conditions. '
                                        'Reinspect the actual image once. Read signed current levels at the two vertical '
                                        'markers bounding trr; the recovery marker is not necessarily the final zero level. '
                                        'Set readable false if you cannot observe them. Never copy a value only from the table.')
                if figure_doc is not None:
                    combined.append(figure_doc)
                    selected_answer += '\n' + row_sentence(figure_doc)
                else:
                    # Keep the verified table row, but do not claim that the
                    # requested waveform was read when the image is unusable.
                    web_result.grade = 'partial'
                    web_result.missing = list(dict.fromkeys(
                        [*web_result.missing, '공식 Fig.6 회복 파형 표식']))
                    selected_answer = canonical
            web_result = DocsAnswer(**{**web_result.model_dump(exclude={'pdf_rows'}), 'answer': canonical})
            if figure_doc is not None:
                canonical_with_figure = check_pdf_lines(selected_answer, combined, expand=True)
                if canonical_with_figure is None:
                    return report('fail', 'answer disagrees with official recovery figure',
                                  reason=Reason.VERIFY_FAILED, docs=combined)
                web_result = DocsAnswer(**{**web_result.model_dump(), 'answer': canonical_with_figure})
            calls += 1
            official_used = bool(selected) and web_result.grade != 'none'
            if prior is None or (official_used and web_result.answer.strip()):
                result, shown = web_result, combined
        if early_fallback is None and not official_used and web_search_fallback is not None and not grade2_budget_exhausted:
            # [왜] 미리 출발을 안 했다는 것은 출발 때 공식(2등급) 예산을 다른 에이전트가 이미 쓰는 중이었다는 뜻이다. 공식 검색이 예산을 잡기 전에
            #      예외 없이 []로 끝나도(허용 낱말 없음 · 타 제조사) 예산 소진과 같은 길로 보낸다(None.result()로 죽던 구멍, 2026-11-15 점검 A #1)
            grade2_budget_exhausted = True
            searches.append({'query': terms, 'parts': web_parts, 'provider': 'exa',
                             'grade': 2, 'status': 'budget_exhausted'})
        if not official_used and not grade2_budget_exhausted and web_search_fallback is not None:
            try:
                fallback_raw = early_fallback.result()  # 예외(예산 소진 포함)는 여기서 원래처럼 다시 올라온다
            except SearchBudgetExhausted as error:
                grade3_budget_exhausted = error.grade == 3
                searches.append({'query': terms, 'parts': web_parts, 'provider': 'exa',
                                 'grade': error.grade, 'status': 'budget_exhausted'})
                fallback_raw = []
            references_found = reference_candidates(fallback_raw)
            references.extend({k: d[k] for k in ('source_url', 'file', 'doc_parts', 'retrieved_at') if k in d}
                              for d in references_found)
    if first and (result.grade == 'none' or not result.answer.strip()):
        result, shown = first  # 다시 찾은 답이 더 나쁘면 첫 일부 답을 쓴다
    answer = (result.answer.strip() if result else '')
    if result and result.grade != 'none' and assembly_polarity_gap(question, task, answer):
        # [왜] 재검색 한도 안에서도 극성 표지가 없으면 enough로 통과시키지 않는다(missing이 비어 status=ok가 되던 구멍)
        if not any(ASSEMBLY.search(m) for m in result.missing):
            result.missing = list(result.missing) + ['실장 전 극성·취급 확인사항']
    if not result or result.grade == 'none' or not answer or answer.startswith(NOT_FOUND):
        # [왜] 설계 v2: 못 찾았다고 거절을 정하지 않고 다시 찾을 사유로 보고한다(0건 no_result, 근거가 아님 all_rejected). 거절은 Supervisor가 정한다
        if grade2_budget_exhausted or grade3_budget_exhausted:
            why = Reason.LIMIT_REACHED
            summary = 'external lookup budget exhausted; evidence lookup was not completed for this task'
        else:
            why = Reason.NOT_FOUND if references else (Reason.ALL_REJECTED if shown else Reason.NO_RESULT)
            summary = f'no evidence for this task in the documents ({why.value})'
        return report('fail', summary, reason=why,
                      missing=result.missing[:6] if result else [], docs=shown, references=references)
    # [왜] 인용 검사는 LLM의 자기 검사를 믿지 않고 코드로 다시 센다. 보여 준 적 없는 번호만 근거로 단 문장은 빼고, 진짜 번호도 단 문장은
    #      가짜 번호만 지운다. 가짜 번호 하나로 답 전체를 거절하던 것을 바꿨다(11-06 공식 5회차 v3-18 '[5816]')
    valid = {str(d['chunk_id']) for d in shown} | ({'넷리스트'} if part and task.kind == 'role' else set())
    allowed_memories = memory_sources(payload.get('approved_memories') or [])
    if any(c.startswith('승인사례:') for c in citations(answer)) or set(result.memory_refs) - allowed_memories:
        return report('fail', 'historical memory cannot support current claims or reference an unprovided case', reason=Reason.VERIFY_FAILED, docs=shown, references=references)
    cited = citations(answer)
    if cited - valid or not cited & valid or has_uncited_sentence(answer, shown):
        # A single bounded regeneration uses the same evidence; never guess a citation for the model.
        if os.getenv('DOCS_CITE_REPAIR', '1') != '0':
            correction = render(question, task, shown, part) + memory_context(payload.get('approved_memories') or [])
            correction += ('\nCitation correction: the previous output had unsupported IDs, sentences without evidence citations, or numbers absent from the cited evidence. '
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
                              reason=Reason.VERIFY_FAILED, docs=shown, references=references)
            if repaired.grade != 'none' and repaired_cites & valid:
                result, answer = repaired, repaired_answer
    if any(cid.startswith('W') for cid in citations(answer)) and any(
        line.strip() and not citations(line) for line in answer.splitlines()
    ):
        return report('fail', 'unattributed line in PDF answer', reason=Reason.VERIFY_FAILED, docs=shown, references=references)
    answer = check_pdf_lines(answer, shown, expand=True)
    if answer is None:
        return report('fail', 'answer disagrees with cited PDF row', reason=Reason.VERIFY_FAILED, docs=shown, references=references)
    answer, dropped_fake = drop_fake_citations(answer, valid)
    dropped_uncited = has_uncited_sentence(answer, shown)
    if dropped_uncited:
        # Keep only already-cited sentences; never attach a neighbour's citation to an unsupported claim.
        answer = ' '.join(s for s in re.split(r'(?<=[.。])\s+', answer) if citations(s) & valid and not unsupported_numbers(s, shown)).strip()
    recovery_complete = any(
        figure.get('figure_reading') and figure.get('evidence_grade') == 2
        and row_sentence(figure) and row_sentence(figure) in answer
        and any(not row.get('figure_reading') and re.search(r'reverse recovery', row.get('row', ''), re.I)
                and row.get('source_sha256') and row.get('source_sha256') == figure.get('source_sha256')
                and row.get('source_url') == figure.get('source_url')
                and row.get('file') == figure.get('file') and row.get('doc_parts') == figure.get('doc_parts')
                and row_sentence(row) and row_sentence(row) in answer for row in shown)
        for figure in shown)
    suffix_complete = False
    if task.kind == 'rating':
        facts, covered = suffix_comparison_facts(filter_parts, shown)
        if facts:
            # For the bounded suffix-meaning question, use the complete source
            # packet so free prose cannot attach a VRMS citation to VRRM.
            canonical_suffix = covered and re.search(r'접미|suffix|끝.{0,12}H', current_question, re.I)
            answer = facts if canonical_suffix else answer + '\n\n' + facts
            suffix_complete = bool(canonical_suffix and all(
                f'{name.upper()} · 패키지:' in facts for name in filter_parts))
            if canonical_suffix:
                # No sentence from the rejected model prose survives this
                # complete replacement, so its removal flags are obsolete.
                dropped_fake, dropped_uncited = [], False
            valid.update(str(d['chunk_id']) for d in shown)
        surge_facts = surge_rating_facts(current_question, shown, task.query + ' ' + task.goal)
        if surge_facts:
            answer += '\n\n' + surge_facts
            valid.update(str(d['chunk_id']) for d in shown)
    result = _reconcile_enriched_missing(result, current_question,
                                        recovery=recovery_complete, suffix=suffix_complete)
    cited = citations(answer)
    if not cited & valid:
        problem = f'cited evidence that was not provided {dropped_fake}' if dropped_fake else 'answer has no citation'
        return report('fail', problem, reason=Reason.VERIFY_FAILED, docs=shown, references=references)
    # A bare partial label is not remaining work; explicit missing facts, retries and removed claims still are.
    complete = result.grade == 'enough' or not result.next_query.strip()
    missing = list(result.missing)
    recovery_gap = trr_condition_gap(current_question, shown) and not recovery_complete
    limited_incomplete = (grade2_budget_exhausted or grade3_budget_exhausted) and (
        recovery_gap or bool(missing) or not complete)
    if limited_incomplete and not missing:
        missing.append('공식 조회 허용 횟수 소진으로 trr 측정 조건(IF/IR/Irr) 확인 미완료'
                       if recovery_gap else '외부 조회 허용 횟수 소진으로 근거 보강 미완료')
    status = 'ok' if complete and not missing and not dropped_fake and not dropped_uncited else 'partial'
    summary = (f'{status}: answered from {len(cited & valid)} evidence'
               + ('; removed unverified sentences' if dropped_fake or dropped_uncited else '')
               + looked_up + (f'; missing {", ".join(missing)}' if missing else ''))
    return report(status, summary, answer=answer, memory_refs=list(dict.fromkeys(result.memory_refs)),
                  evidence_ids=sorted(cited & valid), missing=missing[:6], docs=shown, references=references,
                  reason=Reason.LIMIT_REACHED if limited_incomplete else None)
