"""브라우저에 내보낼 결과의 고정 허용 목록. 그래프 상태에서 공개 값만 고르는 `public_state`도 둔다."""
import re
from urllib.parse import unquote
from pydantic import BaseModel, Field, ValidationError
from backend.conversations.models import SafeEvidence, SafeJudgement, SafeInputCondition, SafeRunError, SafeTargetChoice
from backend.rag.source_metadata import source_metadata
from backend.services.datasheet_rows import grade2_pdf, official_pdf
from backend.services.exa import reference_url


class BrowserResult(BaseModel):
    answer: str = ''
    status: str = ''
    stage: str = ''
    question_type: str = ''
    evidence: list = []
    judgement: dict = {}
    price_parts: list = []
    refusal: str = ''
    interrupt: dict = Field(default={}, description='requires_input일 때만 채운다. 회로 값 · 역할을 물으면 {missing, role_choices, question}, '
                                                    '대상 부품을 물으면 {target_choices: [{ref, value}], question}(SPEC 4절 · 8.9)')
    request_id: str = ''
    profile_hints: list = []  # 참고(내 설정): 이번 질문으로 찾은 사용자 사실. 판정 근거가 아니며 저장하지 않는다
    web_search_unavailable: bool = False  # 이 실행에서 Exa 웹 검색이 실패해 등록된 자료로만 답했다(#28). 화면이 안내 한 줄을 붙인다
    error: SafeRunError | None = None


def _document_basename(document: str) -> str:
    # URL을 basename으로 줄이면 호출자 URL이라는 정보가 사라져 공식 출처로 오인한다.
    if any(ord(char) < 32 or ord(char) == 127 for char in document):
        return ''
    normalized = document.lstrip().replace('\\', '/')
    if '://' in normalized or normalized.startswith('//') or (re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', normalized)
            and not re.match(r'^[A-Za-z]:[\\/]', document)):
        return ''
    return document.replace('\\', '/').rsplit('/', 1)[-1]


def _pick(value, keys):
    result = {key: value[key] for key in keys if key in value} if isinstance(value, dict) else {}
    if 'document' in result and isinstance(result['document'], str):
        result['document'] = _document_basename(result['document'])
    for key in ('document', 'table', 'row', 'section'):
        if key in result and not isinstance(result[key], str):
            result[key] = ''
    return result


def _grade2_source(item):
    """서버가 검사한 행만 등급으로 표시한다. 저장된 URL fragment는 원본 바이트의 해시다."""
    if type(item.get('page')) is not int or item['page'] < 1 or not item.get('table') or not item.get('row'):
        return None
    if item.get('evidence_grade') == 2:
        url = item.get('source_url')
        url = grade2_pdf(url.removesuffix(f"#page={item['page']}")) if isinstance(url, str) else ''
        digest = item.get('source_sha256')
    else:
        document = item.get('document')
        if not isinstance(document, str) or '#sha256=' not in document:
            return None
        address, digest = document.rsplit('#sha256=', 1)
        url = grade2_pdf(address)
    if url and isinstance(digest, str) and re.fullmatch(r'[a-f0-9]{64}', digest):
        return url, digest
    return None


def _stored_citation(item):
    fields = _pick(item, ('document', 'page', 'table', 'row', 'chunk_index', 'chunk_id'))
    if source := _grade2_source(item):
        fields['document'] = f'{source[0]}#sha256={source[1]}'
    return fields


def _show_grade2(entry, source):
    url, digest = source
    entry.update(document=unquote(url.rsplit('/', 1)[-1]), evidence_grade=2,
                 source_sha256=digest, source_type='external_web',
                 source_url=f"{url}#page={entry['page']}", outline_page=None)


def _safe_citation(value) -> dict:
    clean = _pick(value, ('document', 'page', 'table', 'row', 'chunk_index', 'chunk_id'))
    if source := _grade2_source(value):
        _show_grade2(clean, source)
        return clean
    metadata = source_metadata(clean.get('document', ''))
    clean.update(metadata or {'source_url': '', 'outline_page': None})
    return clean


def _safe_judgement(value):
    if not isinstance(value, dict) or not value:
        return None
    result = _pick(value, ('kind', 'roles', 'role_evidence', 'capped', 'preferred_mount'))
    for key in ('results', 'shown', 'unverified'):
        candidates = []
        for item in value.get(key, []):
            candidate = _pick(item, ('part', 'role', 'verdict', 'missing', 'uncertain', 'cautions', 'board_change'))
            for cite_key in ('package_citation',):
                if item.get(cite_key):
                    candidate[cite_key] = _stored_citation(item[cite_key])
            candidate['checks'] = []
            for check in item.get('checks', []):
                clean = _pick(check, ('code', 'tier', 'op', 'basis', 'threshold', 'value', 'unit', 'condition', 'result', 'why'))
                if check.get('citation'):
                    clean['citation'] = _stored_citation(check['citation'])
                candidate['checks'].append(clean)
            candidates.append(candidate)
        result[key] = candidates
    result['terms'] = [_pick(term, ('code', 'gte', 'lte')) for term in value.get('terms', [])]
    try:
        return SafeJudgement.model_validate(result).model_dump(mode='json')
    except (ValidationError, TypeError, AttributeError):
        return None


def safe_judgement(value):
    try:
        return _safe_judgement(value)
    except (TypeError, AttributeError, ValueError):
        return None


def public_state(state: dict) -> dict:
    """그래프 상태에서 공개 계약에 구조화된 값만 선택한다. 원문 문서와 보고서는 복사하지 않는다."""
    answer = state.get('answer', '')
    question_type = state.get('question_type', '')
    parts = state.get('price_parts', [])
    result = {'answer': answer if isinstance(answer, str) else '',
              'question_type': question_type if isinstance(question_type, str) and question_type in {'out_of_scope', 'chat', 'other_part', 'price', 'role', 'rating', 'candidate_judge', 'candidate_find'} else '',
              'price_parts': [p for p in parts if isinstance(p, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}', p)] if isinstance(parts, list) else []}
    reports = state.get('final_reports') or state.get('reports') or []
    cited = {str(item) for report in reports if isinstance(report, dict)
             for item in report.get('evidence_ids', [])}
    evidence = []
    for doc in state.get('docs') or []:
        if not isinstance(doc, dict) or str(doc.get('chunk_id')) not in cited:
            continue
        document, page, table = doc.get('file'), doc.get('page'), doc.get('table')
        if not isinstance(document, str) or not isinstance(page, (int, str)) or not isinstance(table, (str, type(None))):
            continue
        entry = {'document': _document_basename(document), 'page': page,
                 'table': table or '', 'row': '', 'section': '', 'citation_number': str(doc['chunk_id'])}
        if doc.get('source_type') == 'external_web':
            source = _grade2_source(doc)
            if doc.get('evidence_grade') == 2 and not source:
                continue
            url = source[0] if source else official_pdf(doc.get('source_url'))
            if not (url and re.fullmatch(r'W[1-9][0-9]*', entry['citation_number']) and
                    type(page) is int and page > 0 and table and isinstance(doc.get('row'), str) and doc['row']):
                continue
            entry.update(document=url, row=doc['row'])
            if source:
                entry['document'] = f'{source[0]}#sha256={source[1]}'
        if entry not in evidence:
            evidence.append(entry)
    # 참고 링크는 검증된 수치의 [W번호]와 겹치지 않는 [R번호]를 사용한다.
    reference_links = list(dict.fromkeys(url for report in reports if isinstance(report, dict)
                                for ref in report.get('references', []) if isinstance(ref, dict)
                                if (url := reference_url(ref.get('source_url')))))[:3]
    if reference_links:
        lines = []
        for idx, url in enumerate(reference_links, 1):
            label = f'R{idx}'
            evidence.append({'citation_number': label, 'document': url, 'section': '미검증 참고 정보'})
            lines.append(f'[{label}] {url}')
        result['answer'] += '\n\n미검증 참고 정보\n' + '\n'.join(lines)
    if evidence:
        result['evidence'] = evidence
    if judgement := safe_judgement(state.get('judgement')):
        result['judgement'] = judgement
    return result


def stored_evidence(entries):
    """Keep the existing runs JSON schema; the canonical PDF URL identifies a W document."""
    result = []
    for entry in entries:
        fields = {k: entry[k] for k in SafeEvidence.model_fields if k in entry}
        if entry.get('evidence_grade') == 3:
            url = reference_url(entry.get('source_url'))
            if url and re.fullmatch(r'R[1-9][0-9]*', fields.get('citation_number', '')):
                result.append({'document': url, 'citation_number': fields['citation_number'],
                               'section': '미검증 참고 정보'})
            continue
        if entry.get('source_type') == 'external_web':
            source = _grade2_source(entry)
            if entry.get('evidence_grade') == 2 and not source:
                continue
            fields['document'] = f'{source[0]}#sha256={source[1]}' if source else official_pdf(entry['source_url'].split('#', 1)[0])
            if not fields['document']:
                continue
        result.append(fields)
    return result


def result_dto(state: dict, *, request_id: str, status: str = '', stage: str = '', interrupt: dict | None = None,
               profile_hints=(), input_conditions=()) -> BrowserResult:
    # 명시적으로 구조화한 공개 칸만 선택한다.
    answer = state.get('answer', '')
    try:
        error = SafeRunError.model_validate(state['error']) if state.get('error') else None
    except (ValidationError, TypeError):
        error = None
    safe_interrupt = {}
    if interrupt is None:
        interrupt = state.get('interrupt', {})
    if interrupt and status == 'requires_input':
        patterns = {'missing': r'[A-Za-z][A-Za-z0-9_]{0,63}', 'role_choices': r'R(?:0[1-9]|1[0-9]|2[0-3])'}
        for key, pattern in patterns.items():
            value = interrupt.get(key)
            if isinstance(value, list):
                safe_interrupt[key] = [v for v in value if isinstance(v, str) and re.fullmatch(pattern, v)][:30]
        safe_interrupt['question'] = '판정에 필요한 값을 알려 주세요.'
        choices = []
        for item in interrupt.get('target_choices') or []:
            try:
                choices.append(SafeTargetChoice.model_validate({'ref': item.get('ref'), 'value': str(item.get('value') or '')[:100]}).model_dump())
            except (ValidationError, AttributeError):
                continue
        if choices:
            # [왜] 저장된 문장을 믿지 않고 검사한 후보로 다시 만든다(SPEC 8.9)
            safe_interrupt['target_choices'] = choices[:30]
            found = ', '.join(c['ref'] + (f"({c['value']})" if c['value'] else '') for c in choices[:30])
            safe_interrupt['question'] = f'넷리스트에서 다이오드 {found}를 찾았어요. 어떤 부품을 바꿀까요?'
    question_types = {'out_of_scope', 'chat', 'other_part', 'price', 'role', 'rating', 'candidate_judge', 'candidate_find'}
    question_type = state.get('question_type')
    judgement = safe_judgement(state.get('judgement')) or {}
    # 공식 출처는 브라우저 응답에만 붙인다. runs.safe_result의 고정 저장 형식에는 넣지 않는다.
    for group in ('results', 'shown', 'unverified'):
        for candidate in judgement.get(group, []):
            if candidate.get('package_citation'):
                candidate['package_citation'] = _safe_citation(candidate['package_citation'])
            for check in candidate.get('checks', []):
                if check.get('citation'):
                    check['citation'] = _safe_citation(check['citation'])
    # shortcut: 표시 조건은 현재 응답에만 포함한다. 기록 복원이 필요할 때 저장 계약을 확장한다.
    if judgement:
        judgement['input_conditions'] = []
        rows = input_conditions
        for item in rows[:60] if isinstance(rows, list) else []:
            try:
                judgement['input_conditions'].append(SafeInputCondition.model_validate(_pick(item, ('code', 'value'))).model_dump())
            except (ValidationError, TypeError):
                continue
    evidence = []
    for item in state.get('evidence', []):
        try:
            clean = _pick(item, ('document', 'page', 'table', 'row', 'section', 'citation_number'))
            entry = SafeEvidence.model_validate(clean).model_dump(mode='json')
            if re.fullmatch(r'R[1-9][0-9]*', entry['citation_number']):
                url = reference_url(item.get('document'))
                if not url or item.get('section') != '미검증 참고 정보':
                    continue
                entry.update(document=url, evidence_grade=3, source_type='web_reference',
                             source_url=url, outline_page=None)
            elif source := _grade2_source(item):
                _show_grade2(entry, source)
            elif re.fullmatch(r'W[1-9][0-9]*', entry['citation_number']):
                url = official_pdf(item.get('document'))
                if not url or type(entry['page']) is not int or entry['page'] < 1 or not entry['table'] or not entry['row']:
                    continue
                entry.update(document=url.rsplit('/', 1)[-1], source_type='external_web',
                             source_url=f"{url}#page={entry['page']}", outline_page=None)
            else:
                entry.update(source_metadata(entry['document']) or {'source_url': '', 'outline_page': None})
            if entry not in evidence:
                evidence.append(entry)
        except (ValidationError, TypeError):
            continue
    for group in ('results', 'shown', 'unverified'):
        for candidate in judgement.get(group, []):
            for check in candidate.get('checks', []):
                citation = check.get('citation')
                if citation:
                    entry = SafeEvidence(document=citation.get('document', ''), page=citation.get('page'),
                                         table=citation.get('table', ''), row=citation.get('row', ''),
                                         citation_number=str(citation.get('chunk_id') or citation.get('chunk_index') or '')).model_dump(mode='json')
                    if source := _grade2_source(citation):
                        _show_grade2(entry, source)
                    else:
                        entry.update(source_metadata(entry['document']) or {'source_url': '', 'outline_page': None})
                    if entry not in evidence:
                        evidence.append(entry)
    return BrowserResult(answer=answer if isinstance(answer, str) else '', status=status, stage=stage,
                         evidence=evidence, refusal=answer if status == 'refused' and isinstance(answer, str) else '',
                         question_type=question_type if isinstance(question_type, str) and question_type in question_types else '',
                         price_parts=[p for p in state.get('price_parts', []) if isinstance(p, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}', p)] if isinstance(state.get('price_parts', []), list) else [],
                         interrupt=safe_interrupt, error=error, judgement=judgement, request_id=request_id,
                         web_search_unavailable=state.get('web_search_unavailable') is True,
                         profile_hints=[{key: str(hint.get(key, '')) for key in ('kind', 'value', 'text')} for hint in profile_hints][:3])
