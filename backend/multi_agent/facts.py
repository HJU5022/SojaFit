"""코드가 목록에서 확인하는 사실: 질문에 나온 품번 · 개정판이 코퍼스에 있는가.

- 역할: 질문에서 품번과 개정 코드를 뽑아 코퍼스 목록과 대조해 `Facts`를 만든다. Supervisor는 이 사실을 믿고 판단한다.
- 하지 않는 일: 목록 읽기(목록은 호출하는 쪽이 넘기거나 MCP 도구 `check_corpus`가 알려 준다), 거절 결정(판단은 Supervisor).
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05), backend/graph/nodes.py(`find_parts` · `REVISION` 재사용)
"""
import re

from backend.graph.nodes import REVISION, WORD, circuit_parts, find_parts
from backend.multi_agent.supervisor import Facts
from backend.multi_agent.revisions import requested_revisions


def refs_of(target_part: dict) -> set[str]:
    """대상 부품과 주변 넷의 회로 기호. 품번으로 잘못 뽑히지 않게 뺀다(검색 노드와 같은 규칙)."""
    part = target_part or {}
    nets = part.get('nets', [])
    # [왜] 넷 이름('/PB3')과 핀 이름도 품번이 아니다. 'PB3 쪽 D1'의 PB3을 코퍼스에 없는 품번으로 보고 거절했다(11-06 v3-13)
    # [주의] 핀은 'U1.XTAL1/PB3_2(ATtiny85-20SU)' 모양이다: 괄호 속 부품 값을 떼고, 끝의 '_핀 번호'를 떼고, '/'로 나눈 이름마다 뺀다.
    #        괄호 속 값(ATtiny85-20SU · BZX84C3V3)은 품번일 수 있어 빼지 않는다
    pins = {name for net in nets for node in net['nodes'] if '.' in node
            for name in re.sub(r'_\d+$', '', re.sub(r'\(.*\)$', '', node.split('.', 1)[1])).split('/')}
    return ({part.get('ref', '')} | {node.split('.')[0] for net in nets for node in net['nodes']} | pins
            | {net.get('name', '').lstrip('/') for net in nets}) - {''}


# [왜] 주문 코드 모양만 기본 품번에 붙인다. 코퍼스 주문 정보 표의 꼬리표 31종(RFG · RRG · A0G · R0 · L0G · M6G 등)은 모두
# R · A · L · M 한 글자 + 글자나 숫자 하나 + 선택 G다(11-06 실측). 그래야 '1N4148 BAT85'의 없는 BAT85를 가리지 않는다
ORDER_CODE = re.compile(r'[RALM][A-Z0-9]G?')
# [왜] 개정 코드(K2611) 대신 연도로 판을 요구하는 말('2026년판' · '2026년 개정판' · '2026년 USB-C판'). 코퍼스 개정 코드는 글자 + 연월(YYMM)이다
#      (v2 동결 draft30-e10 · m10 · h10: 없는 판인데 확인하지 않아 답했다, 11-07 기준선)
# [왜] 파일 이름으로 판을 요구하면('US1A SERIES_N2602.pdf') 낱말 규칙이 'N2602.pdf'로 읽어 개정 코드를 못 뽑았다(11-07 h4-47)
FILE_REVISION = re.compile(r'_([A-Za-z]\d{4})\.pdf', re.I)


def revisions_in(question: str) -> list[str]:
    """질문의 개정 코드: 낱말(K2611)과 파일 이름 끝(…_N2602.pdf)."""
    # Keep the historical source order for TSC codes (the MCP contract and
    # tests expose a list), then append normalized generic forms deterministically.
    found = [w.upper() for w in WORD.findall(question) if REVISION.fullmatch(w)]
    found.extend(m.upper() for m in FILE_REVISION.findall(question))
    for revision in sorted(requested_revisions(question)):
        if revision not in found:
            found.append(revision)
    return list(dict.fromkeys(found))


YEAR_EDITION = re.compile(r'((?:19|20)\d{2})\s*년\s*(?:[A-Za-z0-9\-]+\s*)?(?:개정판|판|버전)')


def year_editions(question: str, parts: list[str], found: dict, specs) -> dict[str, bool]:
    """연도로 요구한 판 → 그 품번의 코퍼스 문서 개정 코드 중 같은 연도가 있나. 품번이 없거나(회로 판 등) 확인할 수 없으면 없음."""
    out = {}
    for m in YEAR_EDITION.finditer(question):
        yy, revs = m.group(1)[2:], set()
        for p in parts:
            if found.get(p) and specs is not None:
                # 사양 표 행의 인용 문서 이름 끝이 개정 코드다('1N5817 SERIES_H2104.pdf' → H2104)
                revs |= {r['citation']['document'].rsplit('_', 1)[-1].removesuffix('.pdf') for r in specs(p, ['VRRM', 'PACKAGE'])}
        out[m.group(0).replace(' ', '')] = any(len(r) == 5 and r[1:3] == yy for r in revs)
    return out


def make_lookup(check, specs=None):
    """질문에서 품번 · 개정 코드를 뽑아 `check(parts, revisions)`(MCP 도구 `check_corpus` 호출)로 확인하는 lookup을 만든다.

    [주의] 없다는 낱말이 띄어 쓴 앞 품번이 있는 경우(1N4148 R0G의 R0G)는 주문 코드로 보고 `'1N4148 R0G': True`로 바꾼다.
    """
    def lookup(state: dict) -> Facts:
        question = state['question']
        # [왜] 대상 주변 넷 밖의 회로 기호도 품번이 아니다. 'D1 D2 둘 다'의 D2 · 대상이 빈 대화의 기호를 코퍼스에 없는 품번으로 보고 거절할 수 있었다(#62)
        parts = find_parts(question, refs_of(state.get('target_part') or {}) | {p.get('ref', '') for p in circuit_parts(state)})
        revisions = revisions_in(question)
        if not parts and not revisions:
            years = year_editions(question, [], {}, None)
            return Facts(revisions=years)  # [왜] 확인할 품번 · 개정 코드가 없으면 도구를 부르지 않는다(연도 판 요구만 '없음'으로 남긴다)
        answer = check(parts, revisions)
        found = dict(answer['parts'])
        # [왜] 주문 코드가 붙은 품번(1N4148 R0G)은 낱말 둘로 뽑힌다. 띄어 쓴 앞 기본 품번이 있으면 있다(판정 코드와 같은 규칙)
        words = list(WORD.finditer(question))
        # 낱말 → 바로 앞 낱말. 사이가 띄어쓰기뿐일 때만 잇는다("1N4148, BAT85"처럼 쉼표 · 조사가 끼면 따로 본다)
        before = {b.group(): a.group() for a, b in zip(words, words[1:]) if question[a.end():b.start()].isspace()}
        for name, ok in answer['parts'].items():
            if not ok and ORDER_CODE.fullmatch(name) and found.get(before.get(name)):  # 주문 코드 모양이고 앞 낱말이 있는 품번이면 주문 코드로 본다
                # 이름은 질문에 쓴 대로 남긴다: "1N4148 R0G: in corpus"
                del found[name]
                found[f'{before[name]} {name}'] = True
        revisions = dict(answer['revisions'])
        files = [m.upper() for m in FILE_REVISION.findall(question)]
        if files and specs is not None:
            # [왜] check_corpus는 개정 코드가 코퍼스 어디에든 있는지만 본다. 파일 이름으로 판을 요구했으면 그 품번 문서의 파일 이름에 있는지 본다
            #      (다른 계열 문서가 같은 N2602를 쓰면 있다고 나왔다, 11-07 h4-47)
            docs = {r['citation']['document'].upper() for p in parts if answer['parts'].get(p)
                    for r in specs(p, ['PACKAGE', 'VRRM', 'VZ', 'VRWM']) if r.get('citation')}
            if docs:
                revisions.update({rev: any(d.endswith(f'_{rev}.PDF') for d in docs) for rev in files})
        return Facts(parts=found, revisions={**revisions, **year_editions(question, parts, answer['parts'], specs)})
    return lookup


def facts_node(state: dict, *, lookup=None) -> dict:
    """사실 확인 노드. lookup(state) → Facts를 넘기지 않으면 확인 없이 비워 둔다(Supervisor가 질문만 보고 판단)."""
    return {'facts': (lookup(state) if lookup else Facts()).model_dump(mode='json'), 'path': ['사실 확인']}


def with_prefetch(lookup, prefetch):
    """사실 확인(lookup)이 품번을 확정하면 그 품번으로 prefetch(품번 목록)를 바로 부른다. 결과는 바꾸지 않는다.

    [왜] 웹 근거는 내부 근거가 모자라다고 판단한 뒤에야 출발해 그 시간이 응답에 더해졌다(사전 등록 2026-11-14).
    품번이 확정되는 이 시점에 공식 PDF 받기를 옆에서 시작하면 Supervisor 계획(LLM)과 시간이 겹친다.
    """
    def run(state: dict) -> Facts:
        facts = lookup(state)
        prefetch(list(facts.parts))
        return facts
    return run

