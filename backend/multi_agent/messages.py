"""사용자에게 보이는 거절 문구(일상어), 가격 안내 문구, 판정 답 틀. 내부 이유 코드는 따로 로그에 남긴다.

- 역할: 거절 사유(`Reason`)를 사용자가 알아들을 말로 바꾸고, 가능하면 다음에 할 행동을 같이 알려 준다.
  가격 · 재고 질문에는 값 없이 화면이 따로 보여 준다는 안내를 만든다(`price_message`, 단일 · 멀티 가격 안내 노드가 같이 쓴다).
  판정 결과(`judgement`)를 코드 틀의 답 글로 바꾼다(`render_judgement`, 숫자 · 인용은 판정 결과를 그대로 옮긴다).
  Supervisor가 거절한 부분을 답 끝에 한 줄씩 붙인다(`with_declined`, 멀티의 두 에이전트가 답을 낼 때 같이 쓴다).
- 하지 않는 일: 거절 결정(Supervisor · 단일 그래프 라우팅), 코드 이름 노출, 숫자 비교(`backend/judge/`), 가격 · 재고 조회(`backend/services/mouser.py`).
  "코퍼스" 같은 우리끼리 쓰는 말은 쓰지 않는다.
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05, 내부 코드와 사용자 문구 분리), SPEC 2절 가격 안내 · 6절 Mouser(ADR 0009)
"""
from backend.multi_agent.contracts import Reason

CLUES = '부품 윗면의 글자, 주문 코드, 데이터시트 파일'


def refusal_message(reason: Reason, parts: list[str] = (), revisions: list[str] = ()) -> str:
    """거절 사유에 맞는 안내 문구. parts · revisions는 질문에서 확인한 값이고 있으면 문구에 넣는다."""
    named = ', '.join(parts) if parts else '질문하신 부품'
    texts = {
        Reason.OUT_OF_SCOPE: '이 서비스는 회로 속 부품의 역할과 대체 후보를 데이터시트로 확인해 드려요. 회로나 부품에 관한 질문을 해 주세요.',
        Reason.PART_MISSING: f'{named}의 데이터시트를 찾을 수 없어요. 품번이 맞는지 확인해 주시거나 데이터시트 파일을 알려 주세요.',
        Reason.REVISION_MISSING: f'요청하신 판({", ".join(revisions) if revisions else "개정판"})의 데이터시트가 없어요. 가지고 계신 판의 데이터시트를 알려 주세요.',
        Reason.NOT_FOUND: f'요청하신 내용을 데이터시트에서 확인하지 못했어요. 정확한 품번이나 {CLUES}을 알려 주시면 다시 찾아볼게요.',
        Reason.LIMIT_REACHED: '확인하는 데 시간이 너무 오래 걸려 멈췄어요. 질문을 조금 더 구체적으로 다시 해 주세요.',
        Reason.VERIFY_FAILED: '답변의 근거를 확인하지 못해 답을 보여 드릴 수 없어요. 질문을 다시 해 주세요.',
        Reason.SEARCH_ERROR: '검색 도구를 사용할 수 없어 근거를 확인하지 못했어요. 잠시 후 다시 시도해 주세요.',
    }
    return texts[reason]  # 거절 사유가 아닌 이유(재시도 사유)를 넘기면 KeyError: 거절 결정서는 이미 거절 사유만 받는다


def refusal_for(reason: Reason, facts: dict) -> str:
    """사실 확인 결과(`Facts` dict)로 거절 문구를 만든다. 없다고 확인된 품번 · 개정판만 문구에 넣는다(단일 · 멀티 거절 노드가 같이 쓴다).

    [왜] 있는 품번은 넣지 않는다. 판정의 제조사 거절(part_missing)에서 코퍼스에 있는 품번을 "찾을 수 없어요"라고 말하게 된다(SPEC 8.3).
    """
    missing_parts = [p for p, ok in (facts.get('parts') or {}).items() if not ok]
    missing_revs = [r for r, ok in (facts.get('revisions') or {}).items() if not ok]
    return refusal_message(reason, missing_parts, missing_revs)


def with_declined(state: dict, answer: str) -> str:
    """Supervisor가 거절한 부분마다 답 끝에 한 줄: 물은 말 + 거절 문구(사용자 문구는 거절 노드와 같은 refusal_for)."""
    lines = [f"- 답하지 않은 부분 '{d['ask']}': {refusal_for(Reason(d['reason']), state.get('facts') or {})}"
             for d in (state.get('plan') or {}).get('declined') or []]
    return '\n\n'.join([answer, '\n'.join(lines)]) if lines else answer


def price_message(parts: list[str]) -> str:
    """가격 · 재고 질문의 답. [왜] Mouser 값은 답 문장에 넣지 않는다(ADR 0009). 값은 화면이 볼 때마다 따로 조회해 보여 준다."""
    if not parts:
        return '가격·재고를 볼 품번을 알려 주세요. 화면의 가격·재고 칸에 출처와 조회 시각을 붙여 보여 드려요.'
    return (f"{', '.join(parts)}의 가격·재고는 이 답과 따로 화면의 가격·재고 칸에 출처와 조회 시각을 붙여 보여 드려요. "
            '데이터시트 근거와 섞지 않고, 값은 저장하지 않아 볼 때마다 다시 조회해요.')


VERDICT_KO = {'IDENTICAL': '동일품', 'SPEC_EQUIVALENT': '사양 동등', 'ROLE_SUFFICIENT': '역할상 충분',
              'NOT_SUFFICIENT': '불충족', 'NOT_VERIFIED': '문서로 확인 안 됨'}
RESULT_KO = {'pass': '통과', 'fail': '실패', 'unverified': '확인 안 됨'}
NO_GUARANTEE = '같은 동작은 보장하지 않습니다.'


def _num(v) -> str:
    """판정 값 표시(숫자 계산 없이 글자로만 바꾼다). 범위는 '최소 ~ 최대'."""
    if v is None:
        return '—'
    if isinstance(v, list):
        return ' ~ '.join(_num(x) for x in v)
    return f'{v:.4g}'


def _one(j: dict) -> list[str]:
    lines = [f"**{j['part']}: {VERDICT_KO[j['verdict']]}**", '', '| 조건 | 기준 | 후보 값 | 시험 조건 | 결과 | 근거 |', '|---|---|---|---|---|---|']
    for c in j['checks']:
        cite = c.get('citation') or {}
        where = f"{cite.get('document', '')} {cite.get('page', '')}쪽 {cite.get('table', '')} {cite.get('row', '')}".strip() if cite else '—'
        lines.append(f"| {c['code']} {c['op']} | {_num(c.get('threshold'))} ({c['basis']}) | {_num(c.get('value'))} {c.get('unit') or ''} "
                     f"| {c.get('condition') or '표 기본 조건'} | {RESULT_KO[c['result']]}{(' · ' + c['why']) if c.get('why') else ''} | {where} |")
    if j['missing']:
        lines.append(f"- 빠진 값: {', '.join(j['missing'])} → 알려 주시면 판정할 수 있어요.")
    if j['uncertain']:
        lines.append('- 불확실한 조건: ' + ' / '.join(j['uncertain']))
    if j['cautions']:
        lines.append('- 사람이 확인할 것: ' + ' / '.join(j['cautions']))
    if j.get('board_change'):
        cite = j.get('package_citation') or {}
        where = f" (후보 패키지 근거: {cite.get('document', '')} {cite.get('page', '')}쪽 {cite.get('table', '')})" if cite else ''
        lines.append(f'- 패키지가 달라 기판 수정이 필요해요{where}.')
    return lines


def render_judgement(judgement: dict) -> str:
    """판정 결과 → 답 글(코드 틀). 숫자와 인용은 판정 결과를 그대로 옮긴다(LLM이 다시 쓰지 않는다)."""
    lines = [f"역할: {', '.join(judgement['roles']) or '규칙 없는 역할'} (근거: {'; '.join(judgement['role_evidence']) or '—'})", '']
    if judgement['kind'] == 'no_rule':
        lines.append('이 다이오드의 역할은 판정 규칙이 있는 23개 역할 밖이라 판정하지 않았어요.')
    elif judgement['kind'] == 'find':
        terms = ', '.join(f"{t['code']} {'≥' if 'gte' in t else '≤'} {_num(t.get('gte', t.get('lte')))}" for t in judgement['terms'])
        lines.append(f'사양 표에서 건 조건: {terms or "없음(빠진 값이 있어 거르지 못함)"}')
        if judgement['capped']:
            lines.append('후보가 50개 상한에 걸렸어요. 패키지나 분류를 좁혀 주세요.')
        if not judgement['shown']:
            lines.append('이 조건을 모두 채우는 TSC 부품을 사양 표에서 찾지 못했어요.')
        for j in judgement['shown']:
            lines += _one(j) + ['']
        unverified = judgement['unverified']
        if not judgement['shown'] and unverified:
            # [왜] 확인된 후보가 없으면 확인 안 됨 후보 상위 3개를 근거 표와 함께 보인다. 빠진 회로 값을 알려 주면 판정할 수 있는 후보다
            #      (11-07 v2 찾기: 이름만 나열해 근거가 없었다). 판정은 그대로 '확인 안 됨'이다
            lines.append('아래 후보는 표 값은 있지만 빠진 값 · 다른 시험 조건 때문에 문서로 확인 안 됨이에요(견적 대상 아님).')
            for j in unverified[:3]:
                lines += _one(j) + ['']
            unverified = unverified[3:]
        if unverified:
            lines.append('문서로 확인 안 됨(견적 대상 아님): ' + ', '.join(j['part'] for j in unverified))
    else:
        for j in judgement['results']:
            lines += _one(j) + ['']
    lines.append(NO_GUARANTEE)
    return '\n'.join(lines)
