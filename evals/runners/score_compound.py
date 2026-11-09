"""여러 개를 묻는 질문(c20)의 부분별 채점: 답할 수 있는 부분은 기존 기준, 답하면 안 되는 부분은 그 부분을 거절했는지 본다.

- 역할: 평가셋 문항의 `parts`(부분마다 answerable · type · gold_chunks · verdict · candidate_part · qualifying_parts · ask)와
  그래프 실행 상태를 대조해 부분마다 통과를 낸다. 감시 실행기(run_gate)가 문항에 `parts`가 있으면 부른다.
  - 답할 수 있는 부분: 답 전체가 거절이 아니고, 그 부분의 정답 (PDF, 쪽) 중 하나를 인용했다(넷리스트만 근거면 [넷리스트] 인용).
    후보 판정은 그 후보의 판정 코드가 같아야 하고, 찾기는 보여 준 후보가 하나 이상이며 모두 정답 집합 안이어야 한다.
  - 답하면 안 되는 부분: 답 전체가 거절이거나, 그 부분의 열쇠 낱말(품번 · 판 코드 · 영문 낱말)이 든 문장에 '확인 못 함' 말이 있다.
- 하지 않는 일: 그래프 실행, 문항별 점수 합산(run_gate · gate_report).
- 출처: 회의록 D4-D5 B-지시서 4-5.3("채점은 부분마다 기존 기준으로, score_item은 import"), evals/runners/score_answer.py
"""
import re

from evals.runners.gate_report import TABLE_LOC
from evals.runners.run_retrieval import gold_locations
from evals.runners.score_answer import judgement_parts, score_item

# [왜] 종합 답은 못 한 부분을 '이유와 함께' 말한다. 그 말을 찾는 낱말(SPEC 8.3 거절 문구와 종합 프롬프트가 쓰는 표현)
DECLINE = re.compile(r'확인(하지|할 수|이 안|되지)\s*(못|없|않)|찾(지 못|을 수 없)|없어(요|서)|없습니다|없다|제공하지 않|담고 있지 않|'
                     r'범위 밖|다루지 않|답(할 수 없|하지 않|드릴 수 없)|코퍼스에 없|데이터시트에 없|알 수 없|실측|측정값', re.I)
PART_LIKE = re.compile(r'[A-Za-z0-9][A-Za-z0-9.\-]*\d[A-Za-z0-9.\-]*|[A-Za-z0-9.\-]*\d[A-Za-z][A-Za-z0-9.\-]*')
STOP = {'TSC', 'PDF', 'USB', 'GND', 'VCC'}


def _base(name: str) -> str:
    return re.sub(r'^TSC\s+', '', (name or '').strip(), flags=re.I).split(' ')[0].upper()


def ask_tokens(ask: str) -> list[str]:
    """답하면 안 되는 부분의 열쇠 낱말: 품번 · 판 코드 모양 낱말, 없으면 3자 이상 영문 낱말."""
    toks = [t for t in PART_LIKE.findall(ask) if re.search(r'[A-Za-z]', t) and t.upper() not in STOP]
    return toks or [w for w in re.findall(r'[A-Za-z]{3,}', ask) if w.upper() not in STOP]


def all_judgements(state: dict) -> list[dict]:
    """답에 쓴 판정 결과들(멀티는 할 일마다 하나, 단일은 하나)."""
    reports = state.get('final_reports') or state.get('reports') or []
    found = [r['judgement'] for r in reports if r.get('agent') == 'judge' and r.get('judgement')]
    return found or ([state['judgement']] if state.get('judgement') else [])


def score_parts(item: dict, state: dict) -> list[dict]:
    """부분마다 {'type', 'answerable', 'pass'}."""
    from backend.graph.nodes import citations
    answer = state.get('answer') or ''
    base = score_item({**item, 'kind': 'relevant', 'gold_chunks': []}, state)
    cited = {tuple(x) for x in base['cited_locations']} | {(f.strip(), int(p)) for f, p in TABLE_LOC.findall(answer)}
    judgements = all_judgements(state)
    verdicts = {_base(p.get('part')): p.get('verdict') for j in judgements if j.get('kind') != 'find' for p in judgement_parts(j)}
    shown = [_base(p.get('part')) for j in judgements if j.get('kind') == 'find' for p in judgement_parts(j)]
    sentences = [s for s in re.split(r'(?<=[.。!?])\s+|\n', answer) if s.strip()]
    out = []
    for part in item['parts']:
        if part.get('answerable'):
            gold = gold_locations(part.get('gold_chunks') or [])
            pdf = {(f, p) for f, p in gold if f.endswith('.pdf')}
            if pdf:
                ok = bool(pdf & cited)
            elif any('.net' in g for g in part.get('gold_chunks') or []):
                ok = '넷리스트' in citations(answer)
            else:
                ok = bool(answer)
            ok = ok and not base['is_refusal']
            if part.get('type') == 'candidate_judge' and part.get('verdict'):
                ok = ok and verdicts.get(_base(part.get('candidate_part'))) == part['verdict']
            if part.get('type') == 'candidate_find' and part.get('qualifying_parts') is not None:
                qual = {_base(p) for p in part['qualifying_parts']}
                ok = ok and bool(shown) and all(p in qual for p in shown)
        else:
            toks = [t.lower() for t in ask_tokens(part.get('ask', ''))]
            ok = base['is_refusal'] or any(DECLINE.search(s) and (not toks or any(t in s.lower() for t in toks)) for s in sentences)
        out.append({'type': part.get('type'), 'answerable': bool(part.get('answerable')), 'pass': bool(ok)})
    return out
