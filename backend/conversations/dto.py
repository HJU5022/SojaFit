"""브라우저에 내보낼 결과의 고정 허용 목록. 그래프 상태에서 공개 값만 고르는 `public_state`도 둔다."""
import re
from pydantic import BaseModel, ValidationError
from backend.conversations.models import SafeEvidence, SafeJudgement


class BrowserResult(BaseModel):
    answer: str = ''
    status: str = ''
    stage: str = ''
    question_type: str = ''
    evidence: list = []
    judgement: dict = {}
    price_parts: list = []
    refusal: str = ''
    interrupt: dict = {}
    request_id: str = ''
    profile_hints: list = []  # 참고(내 설정): 이번 질문으로 찾은 사용자 사실. 판정 근거가 아니며 저장하지 않는다


def _pick(value, keys):
    result = {key: value[key] for key in keys if key in value} if isinstance(value, dict) else {}
    if 'document' in result and isinstance(result['document'], str):
        result['document'] = result['document'].replace('\\', '/').rsplit('/', 1)[-1]
    for key in ('document', 'table', 'row', 'section'):
        if key in result and not isinstance(result[key], str):
            result[key] = ''
    return result


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
                    candidate[cite_key] = _pick(item[cite_key], ('document', 'page', 'table', 'row', 'chunk_index', 'chunk_id'))
            candidate['checks'] = []
            for check in item.get('checks', []):
                clean = _pick(check, ('code', 'tier', 'op', 'basis', 'threshold', 'value', 'unit', 'condition', 'result', 'why'))
                if check.get('citation'):
                    clean['citation'] = _pick(check['citation'], ('document', 'page', 'table', 'row', 'chunk_index', 'chunk_id'))
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
        entry = {'document': document.replace('\\', '/').rsplit('/', 1)[-1], 'page': page,
                 'table': table or '', 'row': '', 'section': '', 'citation_number': str(doc['chunk_id'])}
        if entry not in evidence:
            evidence.append(entry)
    if evidence:
        result['evidence'] = evidence
    if judgement := safe_judgement(state.get('judgement')):
        result['judgement'] = judgement
    return result


def result_dto(state: dict, *, request_id: str, status: str = '', stage: str = '', interrupt: dict | None = None,
               profile_hints=()) -> BrowserResult:
    # 명시적으로 구조화한 공개 칸만 선택한다.
    answer = state.get('answer', '')
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
    question_types = {'out_of_scope', 'chat', 'other_part', 'price', 'role', 'rating', 'candidate_judge', 'candidate_find'}
    question_type = state.get('question_type')
    judgement = safe_judgement(state.get('judgement')) or {}
    evidence = []
    for item in state.get('evidence', []):
        try:
            clean = _pick(item, ('document', 'page', 'table', 'row', 'section', 'citation_number'))
            entry = SafeEvidence.model_validate(clean).model_dump(mode='json')
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
                    if entry not in evidence:
                        evidence.append(entry)
    return BrowserResult(answer=answer if isinstance(answer, str) else '', status=status, stage=stage,
                         evidence=evidence, refusal=answer if status == 'refused' and isinstance(answer, str) else '',
                         question_type=question_type if isinstance(question_type, str) and question_type in question_types else '',
                         price_parts=[p for p in state.get('price_parts', []) if isinstance(p, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+/-]{0,99}', p)] if isinstance(state.get('price_parts', []), list) else [],
                         interrupt=safe_interrupt, judgement=judgement, request_id=request_id,
                         profile_hints=[{key: str(hint.get(key, '')) for key in ('kind', 'value', 'text')} for hint in profile_hints][:3])
