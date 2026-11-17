"""사용자에게 보이는 거절 문구(일상어), 가격 안내 문구, 판정 답 틀. 내부 이유 코드는 따로 로그에 남긴다.

- 역할: 거절 사유(`Reason`)를 사용자가 알아들을 말로 바꾸고, 가능하면 다음에 할 행동을 같이 알려 준다.
  가격 · 재고 질문에는 값 없이 화면이 따로 보여 준다는 안내를 만든다(`price_message`, 단일 · 멀티 가격 안내 노드가 같이 쓴다).
  견적 요청에는 견적을 만드는 화면 길을 고정 안내로 알려 준다(`QUOTE_GUIDE`, 멀티 견적 안내 노드, #60).
  앞 답 · 근거를 다시 보여 달라는 말에는 화면에 남은 근거 자리를 고정 안내로 알려 준다(`EARLIER_ANSWER`, 멀티 끝내기, #64).
  일반 개념 설명 끝 문장(`GENERAL_NOTE`, #66)도 LLM이 아니라 멀티 끝내기가 붙인다.
  판정 결과(`judgement`)를 코드 틀의 답 글로 바꾼다(`render_judgement`, 숫자 · 인용은 판정 결과를 그대로 옮긴다).
  후보 찾기가 0개로 끝난 거절에는 읽은 역할 · 건 조건을 보여 준다(`empty_find_message`, 11-17).
- 하지 않는 일: 거절 결정(Supervisor · 단일 그래프 라우팅), 코드 이름 노출, 숫자 비교(`backend/judge/`), 가격 · 재고 조회(`backend/services/mouser.py`).
  "코퍼스" 같은 우리끼리 쓰는 말은 쓰지 않는다.
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05, 내부 코드와 사용자 문구 분리), SPEC 2절 가격 안내 · 6절 Mouser(ADR 0009)
"""
import re

from backend.multi_agent.contracts import Reason

# 회로 없이 시작한 대화에서 회로가 필요한 질문의 거절(SPEC 8.9). [왜] Reason에 넣지 않는다: Reason은 계획서 구조화 출력 형식에 들어가
# 데모 기록의 LLM 호출 키가 바뀐다. 코드만 정하는 이유 코드다. [주의] 화면이 이 문구로 회로 고르기 카드를 붙인다(frontend/src/circuit.ts NEEDS_CIRCUIT)
CIRCUIT_MISSING = 'circuit_missing'
NEED_NETLIST = '이 질문은 회로가 있어야 검토할 수 있어요. 넷리스트를 첨부해 주세요.'
# 견적 요청의 답(#60). [왜] 견적은 대화가 아니라 승인 · 수량 화면이 만든다(SPEC 8.4). 그래프는 승인 기록을 읽지 않아 한 문구로 길만 알려 준다.
# [주의] 따옴표 안 이름은 화면 글자와 같아야 한다(frontend/src/Reply.tsx 후보 카드 · Candidate.tsx 승인 칸 · Workbench.tsx 머리 단추)
QUOTE_GUIDE = ("견적은 판정받은 후보를 승인한 뒤 수량을 넣어 만들어요. 판정 답의 '조건과 근거 보기'에서 '이 후보 승인하기'를 누르고 "
               "'견적 수량'을 넣어 '견적서 저장'을 누르세요. 저장한 견적은 프로젝트 화면 위쪽 '견적 목록'에서 볼 수 있어요. "
               "승인 단추는 판정이 동일품 · 사양 동등 · 역할상 충분인 후보에만 있어요. 후보가 모두 문서로 확인 안 됨이면 "
               "회로 전압 · 전류를 알려 주시면 판정을 확정할 수 있어요. "
               "아직 판정받은 후보가 없다면 'D1을 SS14로 바꿔도 될까?'처럼 바꿀 후보를 먼저 물어보세요.")

# 화면 사용법을 묻는 일상 대화의 고정 안내(11-17). [왜] 이 길의 답은 LLM이 쓰는데, 있는 기능을 없다고 답했다
# ("회로도 원본은 보여드리지 않습니다" · "회로에서 버튼의 위치를 찾으시나요?", 운영 대화 실측). 프롬프트는 재생 기록의 키라 바꾸지 않고
# 코드가 낱말로 갈라 고정 글을 낸다. [주의] 따옴표 안 이름은 화면 글자와 같아야 한다(Workbench.tsx 머리 단추 · Reply.tsx · Candidate.tsx)
SCREEN_GUIDES = (
    (re.compile(r'회로도|개념도|schematic', re.I),
     "회로도는 화면 오른쪽 위 '회로 보기'를 누르면 볼 수 있어요. 회로도 파일(.kicad_sch)을 올린 회로는 그 그림을, 넷리스트만 올린 회로는 "
     "고른 부품의 핀과 네트 연결 개념도를 보여 드려요. 넷리스트에는 부품 위치와 배선이 없어 회로도 그림은 그리지 못해요."),
    (re.compile(r'버튼|단추'),
     "승인 단추('이 후보 승인하기')는 판정 답의 후보 카드에서 '조건과 근거 보기'를 누르면 아래쪽에 있어요. "
     "판정이 동일품 · 사양 동등 · 역할상 충분인 후보에만 보이고, 문서로 확인 안 됨 · 불충족 후보에는 없어요."),
)


# 직전 판정을 되묻는 말(11-17). [왜] 그래프는 앞 답을 다음 질문에 넘기지 않아 "그래서 어떤 부품 써야 돼?" · "조건이 뭐야?"가
# 일상 대화로 끝났다(운영 대화 실측). 대화 서비스가 직전 판정의 요약만 상태에 싣고(`last_judgement`), 여기서 코드가 글로 옮긴다.
# LLM에는 주지 않는다(이전 답을 근거로 쓰지 않는다는 규칙은 그대로다). 일상 대화로 끝나는 길에서만 쓴다
ASKS_PICK = re.compile(r'추천|그래서|결론|(?:어떤|어느|무슨|뭘|뭐|머)[^.?!]{0,12}(?:써|쓰|사야|골라|고르|바꾸|바꿔|좋|나아|낫)')
ASKS_CONDITIONS = re.compile(r'조건')
APPROVABLE = ('IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT')


def followup_reply(question: str, last: dict) -> str:
    """직전 판정 요약(`last_judgement`)으로 답할 수 있는 되물음이면 그 답, 아니면 빈 글자."""
    cands = (last or {}).get('candidates') or []
    if not cands:
        return ''
    question = question or ''
    named = lambda rows: ', '.join(f"{c['part']}({VERDICT_KO.get(c['verdict'], c['verdict'])})" for c in rows)
    missing = ', '.join(last.get('missing') or [])
    if ASKS_CONDITIONS.search(question):
        from backend.judge import conditions as C
        rules = C.load()
        roles = ', '.join(rules[r]['name'] for r in last.get('roles') or [] if r in rules) or '규칙 없는 역할'
        terms = _terms_line({'terms': last.get('terms') or [], 'terms_from_original': last.get('terms_from_original')})
        tail = (f'아직 모르는 값: {missing}. 알려 주시면 그 값으로 다시 판정해요.' if missing
                else '회로 전압 · 전류를 알려 주시면 원래 부품 기준 대신 그 값으로 다시 판정해요.' if last.get('terms_from_original')
                else '더 알려 주실 값은 없어요.')
        return f'앞 검토에서 본 조건이에요. 역할: {roles}. {terms}. {tail}'
    if ASKS_PICK.search(question):
        ready = [c for c in cands if c['verdict'] in APPROVABLE]
        if ready:
            easy = [c['part'] for c in ready if c.get('board_change') is False]
            return (f'앞 검토 기준으로 승인할 수 있는 후보는 {named(ready[:3])}예요. '
                    + (f"이 가운데 기판 수정이 필요 없는 후보는 {', '.join(easy[:3])}예요. " if easy else '')
                    + "후보 카드의 '조건과 근거 보기'에서 근거를 확인하고 '이 후보 승인하기'를 누르면 견적을 만들 수 있어요. " + NO_GUARANTEE)
        return (f"앞 검토에서는 확정된 후보가 없었어요. 가장 가까운 후보는 {', '.join(c['part'] for c in cands[:3])}예요. "
                + (f'빠진 값({missing})을 알려 주시면 판정을 확정할 수 있어요.' if missing else '조건과 근거는 후보 카드에서 볼 수 있어요.'))
    return ''


def judgement_summary(judgement: dict) -> dict:
    """판정 결과 → 다음 질문에 싣는 작은 요약(후보는 판정이 좋은 순 · 기판 수정이 필요 없는 순으로 8개까지). 판정이 없으면 빈 dict."""
    results = (judgement or {}).get('results') or []
    if not results:
        return {}
    order = {v: i for i, v in enumerate(('IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT', 'NOT_VERIFIED', 'NOT_SUFFICIENT'))}
    ranked = sorted(results, key=lambda c: (order.get(c.get('verdict'), 9), c.get('board_change') is not False))
    return {'roles': list(judgement.get('roles') or []), 'terms': list(judgement.get('terms') or []),
            'terms_from_original': bool(judgement.get('terms_from_original')),
            'candidates': [{'part': c.get('part'), 'verdict': c.get('verdict'), 'board_change': c.get('board_change')} for c in ranked[:8]],
            'missing': sorted({m for c in results for m in c.get('missing') or []})}


def screen_guide(question: str) -> str:
    """화면 사용법(회로도 보기 · 승인 단추 위치)을 묻는 말이면 그 고정 안내, 아니면 빈 글자. 일상 대화로 끝나는 길에서만 쓴다."""
    return next((text for pattern, text in SCREEN_GUIDES if pattern.search(question or '')), '')

# 앞 답 · 근거를 다시 보여 달라는 말의 답(#64). [왜] 그래프는 앞 답을 갖고 있지 않다(이력은 사용자 입력만). 화면에 남은 답의 근거 자리를 알려 준다.
# [주의] 따옴표 안 이름은 화면 글자와 같아야 한다(frontend/src/Reply.tsx 후보 카드 · 문서 근거, Candidate.tsx 조건별 검토)
EARLIER_ANSWER = ("앞서 드린 답은 이 대화 위쪽에 그대로 있어요. 판정 답은 후보 카드의 '조건과 근거 보기'를 누르면 '조건별 검토'와 데이터시트 근거를 "
                  "다시 볼 수 있고, 문서 답은 답 아래 '문서 근거'를 펼치면 인용한 데이터시트를 볼 수 있어요.")

# 일반 개념 설명(일상 대화) 끝에 코드가 붙이는 문장(#66). [왜] LLM이 쓰게 했더니 '데이tásheet'처럼 글자가 깨졌다
GENERAL_NOTE = '데이터시트 근거가 아닌 일반 설명입니다.'


def refusal_message(reason: Reason, parts: list[str] = (), revisions: list[str] = ()) -> str:
    """거절 사유에 맞는 안내 문구. parts · revisions는 질문에서 확인한 값이고 있으면 문구에 넣는다."""
    named = ', '.join(parts) if parts else '질문하신 부품'
    texts = {
        Reason.OUT_OF_SCOPE: '이 서비스는 회로 속 부품의 역할과 대체 후보를 데이터시트로 확인해 드려요. 회로나 부품에 관한 질문을 해 주세요.',
        Reason.PART_MISSING: f'{named}의 데이터시트를 찾을 수 없어요. 품번이 맞는지 확인해 주시거나 데이터시트 파일을 알려 주세요.',
        Reason.REVISION_MISSING: f'요청하신 판({", ".join(revisions) if revisions else "개정판"})의 데이터시트가 없어요. 가지고 계신 판의 데이터시트를 알려 주세요.',
        Reason.NOT_FOUND: '이 부품 자료를 찾지 못했어요. 정확한 품번이나 부품에 적힌 글자를 알려 주시면 다시 찾아볼게요.',
        # [왜] 아래 셋은 '찾지 못함'이 아니라 서비스가 하지 않는 일이다. 대신 물을 말을 하나씩 알려 준다(#63)
        Reason.MEASUREMENT: "직접 측정한 값은 데이터시트에 없어 알려 드릴 수 없어요. 대신 'D1 최대 접합 온도 알려줘'처럼 데이터시트에 적힌 정격 · 특성값을 물어봐 주세요.",
        Reason.CIRCUIT_VALUE: ("효율 · 소비 전력 · 바꾼 뒤 출력 전압 같은 회로 전체의 값은 계산하지 않아요. 부품 정격을 데이터시트로 비교해 "
                               "바꿔도 되는지만 판정하니 'D1을 SS14로 바꿔도 될까?'처럼 물어봐 주세요."),
        Reason.MAKER_MISSING: ("지금은 TSC(Taiwan Semiconductor) 데이터시트로 후보를 찾고 판정해요. 다른 제조사 부품을 원하시면 바꿀 품번을 알려 주시고, "
                               "TSC 후보를 원하시면 'D1 대체품 찾아줘'처럼 물어봐 주세요."),
        Reason.LIMIT_REACHED: '확인하는 데 시간이 너무 오래 걸려 멈췄어요. 질문을 조금 더 구체적으로 다시 해 주세요.',
        Reason.VERIFY_FAILED: '답변의 근거를 확인하지 못해 답을 보여 드릴 수 없어요. 질문을 다시 해 주세요.',
        Reason.SEARCH_ERROR: '지금은 자료를 확인할 수 없어요. 잠시 후 다시 시도해 주세요.',  # 공급자 장애 · 품번 확인 시간 초과(#29 문구 11-16)
    }
    return texts[reason]  # 거절 사유가 아닌 이유(재시도 사유)를 넘기면 KeyError: 거절 결정서는 이미 거절 사유만 받는다


def refusal_for(reason: Reason, facts: dict) -> str:
    """사실 확인 결과(`Facts` dict)로 거절 문구를 만든다. 없다고 확인된 품번 · 개정판만 문구에 넣는다(단일 · 멀티 거절 노드가 같이 쓴다).

    [왜] 있는 품번은 넣지 않는다. 판정의 제조사 거절(part_missing)에서 코퍼스에 있는 품번을 "찾을 수 없어요"라고 말하게 된다(SPEC 8.3).
    """
    missing_parts = [p for p, ok in (facts.get('parts') or {}).items() if not ok]
    missing_revs = [r for r, ok in (facts.get('revisions') or {}).items() if not ok]
    return refusal_message(reason, missing_parts, missing_revs)


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


def _role_line(judgement: dict) -> str:
    """답 맨 위의 역할 줄(읽은 역할과 그 근거)."""
    return f"역할: {', '.join(judgement['roles']) or '규칙 없는 역할'} (근거: {'; '.join(judgement['role_evidence']) or '—'})"


def _terms_line(judgement: dict) -> str:
    """찾기에 건 조건 줄. 회로 값이 없어 원래 부품 정격으로 대신 찾았으면 그 사실을 붙인다(`terms_from_original`)."""
    terms = ', '.join(f"{t['code']} {'≥' if 'gte' in t else '≤'} {_num(t.get('gte', t.get('lte')))}" for t in judgement['terms'])
    note = ' (회로 값을 모르는 조건은 원래 부품의 정격을 기준으로 찾았어요)' if terms and judgement.get('terms_from_original') else ''
    return f'사양 표에서 건 조건: {terms or "없음(빠진 값이 있어 거르지 못함)"}{note}'


def empty_find_message(judgement: dict) -> str:
    """후보 찾기가 0개로 끝났을 때의 안내: 읽은 역할 · 건 조건을 보여 주고 다음에 줄 것을 알려 준다(멀티 거절 노드가 쓴다).

    [왜] 전에는 공통 문구('이 부품 자료를 찾지 못했어요')만 보여 이미 읽은 역할과 계산한 조건이 버려졌다. 사용자는 무엇을 고쳐 다시
         물어야 하는지 알 수 없었다(11-17 조장 결정). 실행 상태는 그대로 거절이고 문구만 바뀐다.
    """
    lines = [_role_line(judgement), _terms_line(judgement)]
    if judgement['terms']:
        lines.append('이 조건을 모두 만족하는 부품을 찾지 못했어요. 값이 맞는지 다시 확인하시거나, 패키지 · 분류 같은 조건을 줄여 다시 물어봐 주세요.')
    else:
        lines.append('후보를 고를 기준이 되는 값이 없어 찾지 못했어요. 회로 전압 · 전류처럼 아는 값만 알려 주시면 다시 찾아볼게요. '
                     '단위 없이 숫자만 적어도 돼요.')
    return '\n'.join(lines)


def render_judgement(judgement: dict) -> str:
    """판정 결과 → 답 글(코드 틀). 숫자와 인용은 판정 결과를 그대로 옮긴다(LLM이 다시 쓰지 않는다)."""
    lines = [_role_line(judgement), '']
    if judgement['kind'] == 'no_rule':
        lines.append('이 다이오드의 역할은 판정 규칙이 있는 23개 역할 밖이라 판정하지 않았어요.')
    elif judgement['kind'] == 'find':
        lines.append(_terms_line(judgement))
        if judgement['capped']:
            lines.append('후보가 50개 상한에 걸렸어요. 패키지나 분류를 좁혀 주세요.')
        if not judgement['shown']:
            lines.append('조건을 모두 만족하는 부품을 찾지 못했어요.')
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
