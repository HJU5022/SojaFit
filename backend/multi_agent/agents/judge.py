"""판정 에이전트: 역할 · 회로 값을 읽고(LLM 1번), 빠진 값을 묻고(인터럽트), 사양 표 값으로 판정한다(코드).

- 역할: `judge_read_agent`(읽기 노드)와 `judge_agent`(판정 노드). 읽기를 따로 두는 이유는 인터럽트에서 재개하면
  노드가 처음부터 다시 돌기 때문이다(읽기 결과를 먼저 상태에 남겨 LLM을 다시 부르지 않는다).
- 하지 않는 일: 숫자 비교(backend/judge/verdict.py), 답 문구(backend/multi_agent/messages.py), LLM 직접 호출(chat을 받아 쓴다).
- 출처: docs/specs/judge-agent.md What · How
"""
from pathlib import Path

from pydantic import BaseModel, Field

from backend.judge import conditions as C

PROMPT = (Path(__file__).resolve().parents[2] / 'prompts' / 'judge_read.md').read_text(encoding='utf-8')


class Value(BaseModel):
    """질문에서 읽은 회로 값 하나. quote는 질문 글에서 그대로 옮긴 부분이다(숫자 확인에 쓴다)."""
    name: str = Field(max_length=40)
    number: float | None = None
    unit: str = Field(default='', max_length=10)
    flag: bool | None = None
    condition: str = Field(default='', max_length=120)
    quote: str = Field(max_length=200)


class JudgeRead(BaseModel):
    """읽기 노드의 구조화 출력."""
    role: str = Field(pattern='^(R0[1-9]|R1[0-9]|R2[0-3]|other)$')
    role_alt: str | None = Field(default=None, pattern='^(R0[1-9]|R1[0-9]|R2[0-3])$')
    role_evidence: list[str] = Field(default_factory=list, max_length=6)
    values: list[Value] = Field(default_factory=list, max_length=20)
    original_part: str = Field(default='', max_length=100)
    candidates: list[str] = Field(default_factory=list, max_length=5)
    package_wanted: str = Field(default='', max_length=30)
    category_wanted: str = Field(default='', max_length=100)


def render_read(state: dict, rules: dict) -> str:
    """읽기 LLM에 줄 user 글: 역할 목록(이름 · 알아보는 법), 값 이름, 대상 주변 회로, 사용 조건, 질문."""
    names = sorted({n for rule in rules.values() for n in C.inputs(rule)})
    part = state.get('target_part') or {}
    lines = ['Roles:'] + [f'- {rid}: {r["name"]} — {r["recognize"]}' for rid, r in rules.items()]
    lines += ['Value names: ' + ', '.join(names), f'Question type: {state.get("question_type", "")}',
              f'Target: {part.get("ref", state.get("target", ""))} value={part.get("value", "")} footprint={part.get("footprint", "")}',
              'Nets around the target:']
    lines += [f'- {n["name"]}: ' + ', '.join(n['nodes']) + (f' (+{n["more"]} more)' if n.get('more') else '') for n in part.get('nets', [])]
    lines += [f'Conditions: {state.get("conditions", "")}', f'Question: {state.get("question", "")}']
    return '\n'.join(lines)


def judge_read_agent(state: dict, *, chat) -> dict:
    """그래프 노드: 읽기 LLM을 한 번 불러 결과를 상태에 남긴다."""
    read = chat('judge_read', PROMPT, render_read(state, C.load()), JudgeRead)
    return {'judge_read': read.model_dump(mode='json'), 'path': ['판정 읽기']}
