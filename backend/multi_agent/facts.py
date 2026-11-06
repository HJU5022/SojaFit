"""코드가 목록에서 확인하는 사실: 질문에 나온 품번 · 개정판이 코퍼스에 있는가.

- 역할: 질문에서 품번과 개정 코드를 뽑아 코퍼스 목록과 대조해 `Facts`를 만든다. Supervisor는 이 사실을 믿고 판단한다.
- 하지 않는 일: 목록 읽기(목록은 호출하는 쪽이 넘기거나 MCP 도구 `check_corpus`가 알려 준다), 거절 결정(판단은 Supervisor).
- 출처: backend/multi_agent/MULTI_AGENT.md 구조 결정(11-05), backend/graph/nodes.py(`find_parts` · `REVISION` 재사용)
"""
from backend.graph.nodes import REVISION, WORD, find_parts
from backend.multi_agent.supervisor import Facts


def refs_of(target_part: dict) -> set[str]:
    """대상 부품과 주변 넷의 회로 기호. 품번으로 잘못 뽑히지 않게 뺀다(검색 노드와 같은 규칙)."""
    part = target_part or {}
    return {part.get('ref', '')} | {node.split('.')[0] for net in part.get('nets', []) for node in net['nodes']}


def make_facts(question: str, refs: set[str], known_parts: set[str], known_revisions: set[str]) -> Facts:
    """known_parts는 소문자 품번 집합, known_revisions는 대문자 개정 코드 집합이다."""
    revisions = [w.upper() for w in WORD.findall(question) if REVISION.fullmatch(w)]
    return Facts(parts={p: p.lower() in known_parts for p in find_parts(question, refs)},
                 revisions={r: r in known_revisions for r in dict.fromkeys(revisions)})


def make_lookup(check):
    """질문에서 품번 · 개정 코드를 뽑아 `check(parts, revisions)`(MCP 도구 `check_corpus` 호출)로 확인하는 lookup을 만든다."""
    def lookup(state: dict) -> Facts:
        question = state['question']
        parts = find_parts(question, refs_of(state.get('target_part') or {}))
        revisions = list(dict.fromkeys(w.upper() for w in WORD.findall(question) if REVISION.fullmatch(w)))
        if not parts and not revisions:
            return Facts()  # [왜] 확인할 것이 없으면 도구를 부르지 않는다
        answer = check(parts, revisions)
        return Facts(parts=answer['parts'], revisions=answer['revisions'])
    return lookup


def facts_node(state: dict, *, lookup=None) -> dict:
    """사실 확인 노드. lookup(state) → Facts를 넘기지 않으면 확인 없이 비워 둔다(Supervisor가 질문만 보고 판단)."""
    return {'facts': (lookup(state) if lookup else Facts()).model_dump(mode='json'), 'path': ['사실 확인']}
