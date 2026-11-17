"""Spec 에이전트: 역할 · 회로 값을 읽고(LLM 1번), 빠진 값을 묻고(인터럽트), 사양 표 값으로 판정한다(코드).

- 역할: `judge_read_agent`(읽기 노드)와 `judge_agent`(판정 노드). 읽기를 따로 두는 이유는 인터럽트에서 재개하면
  노드가 처음부터 다시 돌기 때문이다(읽기 결과를 먼저 상태에 남겨 LLM을 다시 부르지 않는다).
  멀티는 두 노드를 하위 그래프(`build.py`)로 묶고 `judge_task_node`가 보고를 할 일 보고서로 바꾼다. 단일 그래프는 두 노드를 그대로 쓴다.
- 하지 않는 일: 숫자 비교(backend/judge/verdict.py), 답 문구(backend/multi_agent/messages.py), LLM 직접 호출(chat을 받아 쓴다).
- 출처: docs/specs/judge-agent.md What · How
"""
import contextvars
import logging
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from langgraph.types import interrupt
from pydantic import BaseModel, Field, field_validator

from backend.graph.mcp_retriever import RetrievalUnavailableError
from backend.graph.memory import memory_context
from backend.judge import conditions as C
from backend.judge import sheet_conditions as S
from backend.judge import verdict as V
from backend.multi_agent.contracts import AgentReport, Reason, TaskReport
from backend.multi_agent.agents.part_names import ground_part_names, part_tokens, strip_maker
from backend.multi_agent.facts import ORDER_CODE, refs_of
from backend.multi_agent.revisions import document_revision, requested_revisions, revisions_for_part
from backend.rag.spec_lookup import CODES as SPEC_CODES
from backend.rag.spec_lookup import THT_PACKAGES
from backend.rag.units import to_si
from backend.services.datasheet_rows import grade2_pdf
from backend.services.exa import SearchBudgetExhausted

LOGGER = logging.getLogger(__name__)
PROMPT = (Path(__file__).resolve().parents[2] / 'prompts' / 'judge_read.md').read_text(encoding='utf-8')
LEAK = re.compile(r"[{}]|['\"]\s*:|\]\(|['\"]\s*,\s*['\"]")  # 구조화 출력의 JSON 조각('…','condition':) · 마크다운 조각('…](condition)')이 칸 값으로 새어 든 모양


class Value(BaseModel):
    """질문에서 읽은 회로 값 하나. quote는 질문 글에서 그대로 옮긴 부분이다(숫자 확인에 쓴다)."""
    name: str = Field(max_length=40)
    number: float | None = None
    unit: str = Field(default='', max_length=10)
    flag: bool | None = None
    condition: str = Field(default='', max_length=120)
    quote: str = Field(max_length=200)

    @field_validator('name', 'unit', 'condition', 'quote', mode='before')
    @classmethod
    def cut_json_leak(cls, v):
        # [왜] 읽기 LLM이 quote에 "25°C','condition':'TA=25°C" · "…이다.](condition empty)" 같은 조각을 붙였다(11-06 v3-15 · v3-08).
        #      형식 오류로 다시 부르면 세 번 모두 같은 실수로 문항이 실패했다. 조각 앞까지만 남긴다(숫자 확인은 남은 인용 글로 한다)
        return LEAK.split(v, 1)[0].rstrip(" '\"") if isinstance(v, str) else v


class RequiredSpec(BaseModel):
    """사용자가 꼭 요구한 부품 성질 하나: 사용자 말 그대로와, 그 성질을 재는 사양 표 항목(없으면 none)."""
    words: str = Field(max_length=160)  # [왜] 80자에서 읽기가 영어로 길게 옮긴 말이 넘쳐 형식 오류가 됐다(v3-08)
    code: Literal[SPEC_CODES + ('DIRECTION', 'none')]  # [왜] 목록 밖 글자는 형식 검사에서 걸린다. none이면 판정 노드가 거절한다(SPEC 8.3). DIRECTION은 TVS 방향


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
    # 사용자가 꼭 요구했지만 코퍼스 밖일 수 있는 것(코퍼스 밖 요구 거절, SPEC 8.3)
    required_specs: list[RequiredSpec] = Field(default_factory=list, max_length=6)
    maker_wanted: str = Field(default='', max_length=60)     # 요구한 제조사(영어, Taiwan Semiconductor는 TSC)
    revision_wanted: str = Field(default='', max_length=40)  # 요구한 개정 코드 · 판(쓴 그대로)

    @field_validator('original_part', 'package_wanted', 'category_wanted', 'maker_wanted', 'revision_wanted', mode='before')
    @classmethod
    def cut_json_leak(cls, v):
        # [왜] 읽기 LLM이 revision_wanted에 "','package_wanted':'SMA'}" 같은 JSON 조각을 넣어 개정판 거절로 끝났다(11-06 v3-11).
        #      조각 앞까지만 남긴다(빈 칸이 되면 요구 없음). 짧은 칸에는 JSON 괄호 · '키': 모양이 올 일이 없다
        return LEAK.split(v, 1)[0].rstrip(" '\"") if isinstance(v, str) else v

    @field_validator('revision_wanted', mode='before')
    @classmethod
    def drop_revision_prose(cls, v):
        # [왜] 읽기가 개정 코드 대신 설명 글('Order code difference (A… no revision specified.')을 40자 넘게 적어 형식 오류로 다시 불렸다.
        #      세 회차 v3 판정 읽기의 재시도 4번이 모두 이것이고, 노드마다 2.1~3.6초 늦었다. 재시도 답은 4번 다 빈 칸이었다(사전 등록 #45).
        #      개정 코드 · 판('K2611' · '2027 edition')은 짧다. 40자를 넘는 글은 그 안의 개정 코드 모양(K2611)만 남기고, 없으면 요구 없음으로 받는다
        # [주의] 긴 글을 통째로 버리면 문장 안에 적힌 개정 코드도 사라져 개정판 거절이 빠진다. 그래서 코드 모양만 골라 남긴다
        # [주의] JSON 조각을 자른 뒤의 길이를 본다(cut_json_leak과 어느 쪽이 먼저 돌아도 'K2611','package_wanted':… 의 K2611이 남는다)
        cut = LEAK.split(v, 1)[0].rstrip(" '\"") if isinstance(v, str) else ''
        if len(cut) <= 40:
            return v
        code = re.search(r'(?<![A-Za-z0-9])[A-Za-z]\d{4}(?!\d)', cut)  # 개정 코드는 글자 하나 + 연월 4자리(facts.REVISION과 같은 모양)
        return code.group(0) if code else ''


_RECALL_WORDS = re.compile(r'돌아가|돌아와|이전|앞서|아까|지난|그대로|정정|회상|최신|같은\s*(?:설계|시나리오)', re.I)
_SCENARIO = re.compile(r'(?:설계|시나리오)\s*([^\s,.;:!?]+)', re.I)


def _scenario_labels(text: str) -> list[str]:
    return [re.sub(r'(?:이라고|라고|으로|로|의|를|을|이|가|은|는)$', '', x).upper() for x in _SCENARIO.findall(text or '')]


def _judge_current_text(state: dict) -> str:
    """현재 요청의 조건·질문만 반환한다.

    대화 이력은 별도 상태 필드이며 숫자 grounding의 근거가 아니다. 입력 경계가
    아직 갱신되지 않은 호출도 안전하게 처리하도록 기존 conditions/question만 읽는다.
    """
    return '\n'.join(x for x in (state.get('conditions', ''), state.get('question', '')) if x)


def _history_for_current_question(history: list[str] | None, question: str = '') -> list[str]:
    """명시적인 시나리오 회상 요청에 한해 같은 이름의 이력만 선택한다."""
    rows = [x for x in (history or []) if isinstance(x, str) and x.strip()]
    if not rows or not _RECALL_WORDS.search(question or ''):
        return []
    labels = set(_scenario_labels(question)[:1])
    if not labels:
        # "이전 후보/조건 그대로"처럼 이름을 다시 쓰지 않은 명시적 회상은
        # 최근 사용자 입력만 참조한다. 새 주제 질문에는 위의 회상 신호가 없다.
        # memory_service가 이미 전체 이력을 문자 상한으로 제한한다.
        return rows
    selected = []
    active = False
    for row in rows:
        row_labels = _scenario_labels(row)
        # 한 이력이 "설계 B로 돌아가 A와 섞지 말라"고 말해도, 그 행의
        # 첫 설계명이 기준이다. 다른 설계명이 문장에 언급됐다는 이유로
        # 여러 시나리오를 동시에 주입하지 않는다.
        if row_labels:
            active = row_labels[0] in labels
        if active:
            selected.append(row)
    return selected


def render_read(state: dict, rules: dict) -> str:
    """읽기 LLM에 줄 user 글: 역할 목록(이름 · 알아보는 법 · 그 역할이 받는 값 이름과 종류), 대상 주변 회로, 사용 조건, 질문."""
    part = state.get('target_part') or {}
    # [왜] 값 이름을 역할마다 roles.yaml에서 만든다. 모든 역할의 이름을 한 줄로 주면 다른 역할의 이름(i_out · v_bus)으로 읽어
    #      to_inputs가 버리고 기준값이 비었다(11-06 동결 평가 4회 실측, 인용 없는 답 40건 중 20건)
    lines = ['Roles (each lists the value names it accepts):']
    lines += [f'- {rid}: {r["name"]} — {r["recognize"]} | inputs: ' + ', '.join(f'{n} ({k})' for n, k in C.inputs(r).items())
              for rid, r in rules.items()]
    lines += [f'Question type: {state.get("question_type", "")}',
              f'Target: {part.get("ref", state.get("target", ""))} value={part.get("value", "")}',
              'Nets around the target:']
    lines += [f'- {n["name"]}: ' + ', '.join(n['nodes']) + (f' (+{n["more"]} more)' if n.get('more') else '') for n in part.get('nets', [])]
    lines += [f'Conditions: {state.get("conditions", "")}', f'Question: {state.get("question", "")}']
    return '\n'.join(lines)


def _power_backfeed_evidence(part: dict) -> list[str]:
    """완전한 USB 전원 입력과 정전압 출력 넷 사이의 역류 방지 연결만 확인한다."""
    ref = str(part.get('ref') or '')
    if not ref:
        return []
    def terminal(net, pins):
        return any(re.match(rf'^{re.escape(ref)}\.(?:{pins})(?=\(|$)', node, re.I)
                   for node in net.get('nodes', []))
    nets = part.get('nets') or []
    anodes = [n for n in nets if terminal(n, 'A|ANODE')]
    cathodes = [n for n in nets if terminal(n, 'K|C|CATHODE')]
    if len(anodes) != 1 or len(cathodes) != 1:
        return []
    anode, cathode = anodes[0], cathodes[0]
    components = {c.get('ref'): c for c in part.get('context_components') or []}
    inputs = [node for node in anode.get('nodes', []) if not node.startswith(ref + '.')]
    if anode.get('more', 0) or not inputs:
        return []
    for node in inputs:
        component = components.get(node.split('.', 1)[0], {})
        symbol = str(component.get('symbol') or '').casefold()
        functions = {str(pin.get('function') or '').upper() for pin in component.get('pins') or []}
        connector_pins = {'VBUS', 'GND', 'D+', 'D-', 'ID', 'SHIELD', 'SH'}
        imported_connector = {'VBUS', 'GND', 'D+', 'D-'} <= functions <= connector_pins
        if (not re.search(r'\.VBUS(?=\(|$)', node, re.I) or 'usb' not in symbol
                or not ('connector' in symbol or imported_connector)):
            return []
    outputs = []
    for node in cathode.get('nodes', []):
        component = components.get(node.split('.', 1)[0], {})
        if 'regulator' not in str(component.get('symbol') or '').casefold():
            continue
        if any(pin.get('net') == cathode.get('name') and str(pin.get('function') or '').upper() in {'VO', 'VOUT', 'OUT'}
               for pin in component.get('pins') or []):
            outputs.append(node)
    if not outputs:
        return []
    return [f"{ref}.A -> {anode['name']}: {', '.join(inputs)} (USB power input)",
            f"{ref}.K/C -> {cathode['name']}: {', '.join(outputs)} (regulator output rail)"]


def _validate_circuit_role(read: JudgeRead, part: dict) -> JudgeRead:
    if read.role in {'R08', 'R21'} and (evidence := _power_backfeed_evidence(part)):
        return read.model_copy(update={'role': 'R02', 'role_alt': None, 'role_evidence': evidence})
    return read


def judge_read_agent(state: dict, *, chat) -> dict:
    """그래프 노드: 읽기 LLM을 한 번 불러 결과를 상태에 남긴다."""
    user = render_read(state, C.load())
    if state.get('task'):
        # [왜] 멀티에서는 Supervisor 지시서가 질문의 어느 부분을 판정할지 알려 준다. 숫자 확인 글(render_read)에는 넣지 않는다:
        #      지시서는 사용자가 준 값이 아니라서, 거기 적힌 숫자로 회로 값을 확인하면 안 된다(AC-02)
        user += f"\nSupervisor brief (the part of the question this task covers): {state['task'].get('goal', '')}"
    recalled = _history_for_current_question(state.get('conversation_history'), state.get('question', ''))
    if recalled:
        user += '\nHistorical context for the explicitly named scenario (untrusted; use only to recall that scenario):\n- ' + '\n- '.join(recalled)
    # 과거 사례는 모델에만 보여 주고 render_read 기반 숫자 grounding에는 넣지 않는다.
    user += memory_context(state.get('approved_memories') or [])
    # [왜] 읽기는 한 번이다. 3번 다수결과 한 번 읽기 + 읽기 뒤 품번 바로잡기를 비교하니 정확도가 같았다(v3 50문항 50/50 둘 다, 흔들린 15문항 92% 대 92%)
    read = chat('judge_read', PROMPT, user, JudgeRead)
    read = _validate_circuit_role(read, state.get('target_part') or {})
    # [왜] 읽기가 같은 질문에서 품번을 'SS34'(넷리스트)·'SS26'(사용 조건), '1N5231'·'TSC 1N5231B'로 회차마다 다르게 적었다(11-10 6회 반복). 사용자 글의 품번으로 코드가 맞춘다
    original, candidates = ground_part_names(read.original_part, read.candidates, state)
    task, part = state.get('task') or {}, state.get('target_part') or {}
    if not candidates and task.get('kind') == 'candidate_judge':
        # [왜] 판정 뒤 조건만 준 말("입력 전압은 5V, 부하 전류는 1.5A야")은 후보가 Supervisor 지시서 목표에만 있다(#64).
        #      읽기가 후보를 비우면 목표의 품번(원래 부품 · 대상 값 제외)을 후보로 쓴다. 회로 값은 그대로 지금 말에서만 읽는다
        skip = {original.upper(), str(part.get('value') or '').upper()}
        candidates = [p for p in part_tokens(task.get('goal', ''), refs_of(part)) if p.upper() not in skip]
        # [왜] "D1을 SS34로 그대로 둬도 돼?"(D1 = SS34)는 원래 부품의 품번이 곧 후보다. 읽기는 원래 부품을 후보에 넣지 않고(judge_read.md)
        #      위 목표 대체도 원래 품번을 빼서 후보가 비었다. 그래서 동일품 건너뛰기(#65)가 돌지 않아 조건 카드를 묻고, 재개 뒤 후보 0개로 not_found 거절이었다(11-17 실측)
        # [주의] 지금 질문의 품번이 원래 품번 하나뿐일 때만이다. 주문 코드(SS34 R0G) · 다른 품번이 함께 있으면 그대로 둔다(#65 주문 코드는 묻는다)
        # shortcut: 원래 품번만 적은 판정 할 일을 모두 같은 품번 질문으로 본다("D1 SS34 바꿔도 돼?"도 동일품), 읽기가 '그대로 둠'을 따로 낼 때 그 칸으로 가린다
        if not candidates and original and {p.upper() for p in part_tokens(state.get('question', ''), refs_of(part))} == {original.upper()}:
            candidates = [original]
    read = read.model_copy(update={'original_part': original, 'candidates': candidates})
    return {'judge_read': read.model_dump(mode='json'), 'path': ['판정 읽기']}


NUM = re.compile(r'\d+(?:\.\d+)?')
# 인용 글의 숫자 범위('3.42~3.78V' · '3.42–3.78 V' · '3.42V에서 3.78V' · '3.42 to 3.78V')
NUM_RANGE = re.compile(r'\d(?:\.\d+)?\s*[a-zA-Z]*\s*(?:~|〜|–|—|-|에서|부터|to)\s*\d', re.I)
RANGE_ONLY = {'vz_min', 'vz_max'}  # 사용자가 범위로 정한 값만 받는 이름(judge_read.md: 공칭 ± 공차는 required_specs)
QTY = re.compile(r'(\d+(?:\.\d+)?)\s*([a-zA-Zµμ°%Ω]*)')  # 인용 글의 숫자와 바로 뒤 단위
REPLY = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*([a-zA-Zµμ°%]*)\s*$')
YES, NO = {'예', '네', '응', 'yes', 'true', 'y'}, {'아니오', '아니', 'no', 'false', 'n'}
# [왜] 온도 하나만 받는 조건 값(사용 온도 · 고온 사용 온도)은 '125' · '125°C' · '125도'처럼 기호 없이 적어도 받는다. 화면 예시(TA=25 °C · TJ=125 °C)의
#      기호를 쓴다. 전에는 기호(TJ=)가 없으면 못 읽는 답으로 버렸다(11-17 조장 결정: 사용자는 값을 형식에 맞춰 주지 않는다)
# [주의] 전류 · 펄스까지 받는 조건 값(vf_test · pulse_test · surge_test)은 숫자 하나로 뜻을 정할 수 없어 넣지 않는다
BARE_TEMP = {'temp': 'TA', 'hot_test': 'TJ'}
BARE_TEMP_REPLY = re.compile(r'^\s*(-?\d+(?:\.\d+)?)\s*(?:°\s*C|℃|도|C)?\s*$', re.I)
# 현재 사용자가 전체 조건을 줄 수 없다고 명시한 경우에만 추가 수치 질문을 생략한다.
NO_MORE_CONDITIONS = re.compile(
    r'(?:사용\s*조건|회로\s*조건|추가\s*(?:사용\s*)?조건)\s*(?:[은는을를이가]\s*)?(?:잘\s*)?'
    r'(?:모르겠(?:어(?:요)?|습니다|다|음)|모릅니다|모른다|모름|몰라(?:요)?|'
    r'(?:알|확인할|알려줄|알려드릴|제공할)\s*수\s*없(?:어(?:요)?|습니다|다|음))(?=[\s.!?。]|$)'
    r'|추가\s*(?:사용\s*)?조건으로\s*확인할\s*수\s*있는\s*(?:내용|정보)(?:은|는|이|가)?\s*없(?:어(?:요)?|습니다|다|음)?(?=[\s.!?。]|$)'
)


def _norm(s: str) -> str:
    return ' '.join(s.split())


def grounded(text: str, v: Value) -> bool:
    """값의 quote가 질문 · 회로 글에 그대로 있고, number와 condition의 숫자가 모두 그 quote에 있는지(AC-02)."""
    quote = _norm(v.quote)
    if not quote or quote not in _norm(text):
        return False
    have = {float(n) for n in NUM.findall(quote)}
    # [왜] 읽기가 단위를 바꿔 적을 때가 있다('250mA'를 0.25 A로). SI 값이 인용 글의 숫자 · 단위와 같으면 근거가 있다(11-06 공식 2회차 v3-12)
    have_si = {round(_si(float(n), u), 12) for n, u in QTY.findall(quote) if u}
    if v.number is not None and v.number not in have and round(_si(v.number, v.unit), 12) not in have_si:
        return False
    return all(float(n) in have for n in NUM.findall(v.condition))


def _si(number: float, unit: str) -> float:
    """읽은 숫자 · 단위 → SI 값. %는 100으로 나누고, 단위가 없거나 모르면 숫자 그대로(권선비 등)."""
    if unit == '%':
        return number / 100
    found = to_si(number, unit) if unit else None
    return found[0] if found else number


def to_inputs(read: JudgeRead, text: str, kinds: dict, *, preferred_text: str = '') -> tuple[dict, dict, list[str]]:
    """읽기 결과 → (숫자 · 예/아니오 값, 시험 조건 값, 버린 이름). 규칙에 없는 이름과 근거 없는 값은 버린다."""
    values, conds, dropped = {}, {}, []
    correcting = bool(re.search(r'정정|최신|변경|바꿔|수정', preferred_text or ''))
    current_names = {v.name for v in read.values
                     if correcting and grounded(preferred_text, v)}
    for v in read.values:
        if v.name not in kinds and SAME_QUANTITY.get(v.name) in kinds:
            v = v.model_copy(update={'name': SAME_QUANTITY[v.name]})  # 같은 자리 두 역할의 같은 양을 다른 이름으로 읽은 경우
        kind = kinds.get(v.name)
        # [왜] 읽기가 구매 규격 '공칭 제너 전압 3.3V, 공차 ±2%'를 vz_min · vz_max = 3.3V로도 읽어, 사양 조건에 더해 '최소 VZ ≥ 3.3 · 최대 VZ ≤ 3.3'이
        #      걸려 실제 3.3V 제너가 모두 불충족이 됐다(v3-13, Sonnet 31a3aa3 1세트 · Haiku 4a61fd0 2세트, 사전 등록 #48). 범위가 없는 인용은 버린다
        # 최신 정정은 같은 입력 이름의 오래된 인용만 대체한다. 전압/전류
        # 단위가 같다는 이유로 hot_test, ir_allowed 같은 다른 필드를 지우지 않는다.
        stale = correcting and v.name in current_names and _norm(v.quote) not in _norm(preferred_text)
        if kind is None or not grounded(text, v) or stale or (v.name in RANGE_ONLY and not NUM_RANGE.search(v.quote)):
            dropped.append(v.name)
        elif kind == 'flag' and v.flag is not None:
            values[v.name] = v.flag
        elif kind == 'number' and v.number is not None:
            values[v.name] = _si(v.number, v.unit)
        elif kind == 'condition' and v.condition:
            conds[v.name] = S.parse(v.condition)
        else:
            dropped.append(v.name)
    for a, b in SAME_QUANTITY.items():
        if a in values and b in kinds and b not in values:
            values[b] = values[a]  # [왜] 역할이 둘(R22 · R03)이면 같은 양을 두 이름 모두에 둔다. 한쪽 이름만 채워져 다른 역할이 빠진 값으로 확인 안 됨이 됐다(공식 2회차 v3-12)
    if values.get('v_ac_rms') is not None and 'ac_input' in kinds and values.get('ac_input') is None:
        # [왜] AC 실효값을 줬으면 AC 입력이다. 읽기가 ac_input 플래그를 회차마다 비워 AC 조건(실효값 × √2)이 빠졌다(11-06 v3-08)
        values['ac_input'] = True
    return values, conds, dropped


def merge_reply(answers: dict, values: dict, conds: dict, kinds: dict) -> tuple[dict, dict]:
    """인터럽트 답({이름: "150mA" | "예" | "TJ=25°C"})을 회로 값에 더한다. 못 읽는 답은 버린다(= 모름)."""
    values, conds = dict(values), dict(conds)
    for name, raw in (answers or {}).items():
        kind, text = kinds.get(name), str(raw).strip()
        if kind == 'flag' and text.lower() in YES | NO:
            values[name] = text.lower() in YES
        elif kind == 'number' and (m := REPLY.match(text)):
            values[name] = _si(float(m.group(1)), m.group(2))
        elif kind == 'condition' and (parsed := S.parse(text)):
            conds[name] = parsed
        elif name in BARE_TEMP and (m := BARE_TEMP_REPLY.match(text)):
            conds[name] = {BARE_TEMP[name]: float(m.group(1))}
    return values, conds


def _ask_text(missing: list[str], roles: list[str], rules: dict) -> str:
    """사용자에게 보일 한국어 질문 하나(빠진 값 이름을 그대로 보여 준다)."""
    head = '판정에 필요한 값이 빠져 있어요. 아는 만큼 알려 주세요(모르면 비워 두면 돼요): '
    return head + ', '.join(missing) + (f" / 역할이 {' 또는 '.join(rules[r]['name'] for r in roles)} 중 어느 쪽인지도 알려 주세요." if len(roles) > 1 else '')


def _required_missing(rule: dict, present: set[str]) -> list[str]:
    """역할의 필수 조건만 보고 아직 필요한 회로 값을 돌려준다.

    `when`으로 켜지는 조건은 선택 조건이다. 역할을 고르는 단계에서는 그것을
    필수 입력으로 세지 않아, 회로 값이 충분히 특정한 역할까지 불필요하게
    사용자 입력을 요구하지 않도록 한다. 실제 판정에서는 기존 규칙대로
    조건이 켜지지 않았음을 `uncertain`으로 남긴다.
    """
    missing = []
    for cond in rule.get('conditions') or []:
        if cond.get('tier') != 'required':
            continue
        if 'any' in cond:
            alternatives = [C._asks(member, present) for member in cond['any']]
            if alternatives and all(alternatives):
                missing.extend(alternatives[0])
        else:
            missing.extend(C._asks(cond, present))
    return list(dict.fromkeys(missing))


def _collapse_float_boundary_conditions(conditions: list[dict]) -> list[dict]:
    """같은 항목의 상·하한이 부동소수점 여유만큼만 벌어진 중복을 제거한다.

    `최대 23.2V`가 읽기 결과에서 `<= 23.2`와 `>= 23.2000000232`로
    동시에 만들어진 경우처럼, 엄격한 하한을 뜻하는 원문이 없는 조건만
    접는다. 사용자가 명시한 `이상/초과/at least/above/>`는 보존한다.
    """
    out = list(conditions)
    lower_words = re.compile(r'이상|최소|초과|at\s+least|above|over|more\s+than|(?<!<)>', re.I)
    for upper in conditions:
        if upper.get('op') != '<=' or upper.get('basis') is None:
            continue
        try:
            hi = float(upper['basis'])
        except (TypeError, ValueError):
            continue
        for lower in conditions:
            if lower.get('code') != upper.get('code') or lower.get('op') != '>=' or lower.get('basis') is None:
                continue
            try:
                lo = float(lower['basis'])
            except (TypeError, ValueError):
                continue
            if lo >= hi and lo - hi <= 1e-8 * max(1.0, abs(hi)) and not lower_words.search(str(lower.get('words') or '')):
                if lower in out:
                    out.remove(lower)
    return out


def _text_flags(values: dict, text: str, kinds: dict[str, str], *, direct_text: str | None = None) -> dict:
    """판정 읽기가 놓친 명시적 플래그를 원문에서 보완한다.

    숫자·역할을 LLM 출력으로 새로 추정하지 않고, 질문에 명시된 PWM 유무처럼
    단순한 불리언 사실만 보완한다. 이 값은 역할 선택과 선택 조건 발동 여부에
    쓰이며, 원문에 근거가 없으면 기존처럼 비워 둔다.
    """
    out = dict(values)
    if kinds.get('pwm') == 'flag' and 'pwm' not in out:
        no_pwm = re.search(r'(?:PWM|펄스\s*폭\s*변조)[^。.\n]{0,20}(?:없|아니|사용하지)', text, re.I)
        has_pwm = re.search(r'(?:PWM|펄스\s*폭\s*변조)[^。.\n]{0,30}(?:\d|사용|구동|제어|있)', text, re.I)
        if no_pwm:
            out['pwm'] = False
        elif has_pwm:
            out['pwm'] = True
    if kinds.get('vf_selects_source') == 'flag':
        flag_text = direct_text if direct_text is not None else text
        clauses = [clause for clause in re.split(r'(?<=[.。!?])\s+|\n+', flag_text)
                   if re.search(r'(?:VF|순방향\s*전압)', clause, re.I)]
        explicit = []
        saw_unknown = False
        for clause in clauses:
            if not re.search(r'전원\s*선택|공급\s*선택', clause, re.I):
                continue
            if re.search(r'\?|여부를?\s*모|하는지\s*모|알\s*수\s*없|모르', clause, re.I):
                saw_unknown = True
                continue
            negative = bool(re.search(r'결정\s*하지\s*않|결정\s*안|영향을?\s*주지\s*않|좌우하지\s*않|아니|않음', clause, re.I))
            positive = bool(re.search(r'결정\s*(?:함|한다|합니다|하여)|영향을?\s*(?:줌|준다|있음)', clause, re.I)) and not negative
            if negative != positive:
                explicit.append(not negative)
        if explicit and all(flag == explicit[0] for flag in explicit):
            # 사용자의 명시 문장이 LLM flag보다 우선한다. 서로 모순인 문장만 확인으로 남긴다.
            out['vf_selects_source'] = explicit[0]
        elif len(explicit) > 1:
            out.pop('vf_selects_source', None)
        elif saw_unknown:
            out.pop('vf_selects_source', None)
    return out


def _direct_condition_text(conditions: str = '', question: str = '') -> str:
    """조건 보완에 사용할 직접 입력만 남긴다.

    회로/netlist 렌더링과 외부 인용문은 숫자 근거가 아니다. 외부 인용 블록은
    제거하여 그 안의 수치를 조건으로 승격하지 않는다.
    """
    text = '\n'.join(x for x in (conditions, question) if x)
    # 외부 자료 경계는 특정 공급자/시험 ID가 아니라 일반 인용·코드·태그 경계로 처리한다.
    text = re.sub(r'```.*?```', '', text, flags=re.S)
    text = re.sub(r'<([A-Za-z][\w:-]*)\b[^>]*>.*?</\1\s*>', '', text, flags=re.I | re.S)
    text = re.sub(r'^\s*>.*$', '', text, flags=re.M)
    return text


def _recover_explicit_conditions(text: str, values: dict, conds: dict, kinds: dict) -> tuple[dict, dict]:
    """직접 적은 hot_test·허용 누설만 복구한다.

    같은 항목에 서로 다른 값을 두 번 적으면 임의로 마지막 값을 고르지 않고
    누락 상태로 남겨 기존 interrupt/확인 경로를 사용한다.
    """
    text = _direct_condition_text(text)
    values, conds = dict(values), dict(conds)
    if kinds.get('temp') == 'condition':
        # 현재 동작 온도는 회상된 조건보다 우선한다. hot_test 안의 TJ는
        # temp(주변 동작 온도)가 아니므로 독립적인 TA/TC만 사용한다.
        matches = re.findall(r'\b(TA|TC)\s*=\s*(\d+(?:\.\d+)?)\s*°?\s*C', text, re.I)
        if matches:
            parsed = [{'TA' if name.upper() == 'TA' else 'TC': float(number)} for name, number in matches]
            if all(item == parsed[0] for item in parsed):
                conds['temp'] = parsed[0]
            else:
                conds.pop('temp', None)
    if kinds.get('hot_test') == 'condition':
        matches = re.findall(r'(?:누설\s*시험|hot_test)\s*[:：]?\s*([^。\n!?]+)', text, re.I)
        parsed = [S.parse(m) for m in matches]
        parsed = [p for p in parsed if p]
        if parsed and all(p == parsed[0] for p in parsed):
            # 현재 본문이 명시한 시험 조건은 모델이 회상한 오래된 조건보다 우선한다.
            conds['hot_test'] = parsed[0]
        elif len(parsed) > 1:
            conds.pop('hot_test', None)
    if kinds.get('ir_allowed') == 'number':
        matches = re.findall(r'(?:허용\s*(?:역)?누설|ir_allowed)\s*(?:전류)?\s*(?:은|=|:)?\s*(\d+(?:\.\d+)?)\s*([munpµμ]?A)', text, re.I)
        parsed = [_si(float(number), unit) for number, unit in matches]
        parsed = [p for p in parsed if p is not None]
        if parsed and all(math.isclose(p, parsed[0], rel_tol=1e-12, abs_tol=0.0) for p in parsed):
            values['ir_allowed'] = parsed[0]
        elif len(parsed) > 1:
            values.pop('ir_allowed', None)
    aliases = {
        'v_reverse_max': r'(?:v_reverse_max|최대\s*역전압|역전압\s*최대)\s*(?:(?:은|는)|=|:)?\s*(\d+(?:\.\d+)?)\s*(V)',
        'i_max': r'(?:i_max|최대\s*(?:부하\s*)?전류|전류\s*최대)\s*(?:(?:은|는)|=|:)?\s*(\d+(?:\.\d+)?)\s*([munpµμ]?A)',
    }
    for name, pattern in aliases.items():
        if kinds.get(name) != 'number':
            continue
        matches = [_si(float(number), unit or 'V') for number, unit in re.findall(pattern, text, re.I)]
        if matches and all(math.isclose(item, matches[0], rel_tol=1e-12, abs_tol=0.0) for item in matches):
            values[name] = matches[0]
        elif len(matches) > 1:
            values.pop(name, None)
    return values, conds


def _recover_history_conditions(rows: list[str], kinds: dict, *, read: JudgeRead | None = None) -> tuple[dict, dict]:
    """선택된 동일 시나리오의 사용자 행을 시간순으로 합친다."""
    values, conds = {}, {}
    for row in rows:
        direct = _direct_condition_text(row)
        if read is not None:
            # 읽기의 인용도 해당 사용자 행에 근거할 때만 시간순으로 반영한다.
            # 앞 행의 명시 별칭이 뒤 행의 유효한 정정을 덮지 않게 한다.
            row_values, row_conds, _ = to_inputs(read, direct, kinds)
            values.update(row_values)
            conds.update(row_conds)
        values, conds = _recover_explicit_conditions(row, values, conds, kinds)
        values = _text_flags(values, direct, kinds, direct_text=direct)
    return values, conds


def _role_present(role: str, rule: dict, values: dict, conds: dict, text: str) -> set[str]:
    """역할 판별용 입력 집합을 만든다.

    여러 역할을 동시에 읽을 때 LLM이 같은 물리량을 `v_in_max/i_max`로
    통일해 적을 수 있다. 질문이 코일을 명시하고 코일 역할만 그 이름을
    받는다면, 역할 선택 단계에서만 `v_coil/i_coil`로 대응시킨다. 실제
    판정 재실행은 선택된 역할의 입력 목록으로 `to_inputs`가 같은 변환을
    수행한다.
    """
    present = set(values) | set(conds)
    names = C.inputs(rule)
    if '코일' in text and 'v_coil' in names and 'v_coil' not in present and 'v_in_max' in values:
        present.add('v_coil')
    if '코일' in text and 'i_coil' in names and 'i_coil' not in present and 'i_max' in values:
        present.add('i_coil')
    return present


def _prefer_role_from_load(roles: list[str], rules: dict, text: str) -> list[str]:
    """질문이 명시한 부하 종류와 충돌하는 역할만 제거한다.

    코일 플라이백과 PWM 모터 프리휠링처럼 회로 모양이 비슷한 역할은
    숫자 입력이 양쪽에 모두 들어와도 역할이 유일해지지 않는다. 사용자가
    `코일 부하`라고 명시했으면 모터 역할을 후보에서 제외하고, 모터라고
    명시했으면 코일 전용 역할을 제외한다. 둘 다 언급되거나 어느 쪽도
    언급되지 않으면 원래의 역할 모호성 처리를 유지한다.
    """
    lowered = text.casefold()
    has_coil = bool(re.search(r'코일|릴레이\s*(?:부하|플라이백)', lowered))
    has_motor = bool(re.search(r'모터|motor', lowered))
    if has_coil and not has_motor:
        preferred = [r for r, rule in rules.items() if '코일' in str(rule.get('recognize', ''))]
        if preferred:
            return [r for r in preferred if r in roles] or preferred[:1]
    if has_motor and not has_coil:
        preferred = [r for r, rule in rules.items() if '모터' in str(rule.get('recognize', ''))]
        if preferred:
            return [r for r in preferred if r in roles] or preferred[:1]
    return roles


# [왜] 읽기가 품번을 'TSC 1N5817'처럼 제조사 이름과 함께 낸다. 사양 표 품번에는 제조사 이름이 없어 0행이 된다(11-06 평가 7건)
EDITION = re.compile(r'[A-Z]\d{4}|(?:19|20)\d{2}|판|EDITION|VERSION|\bREV', re.I)  # 데이터시트 판으로 보이는 글


# [왜] 원래 부품이 '제조사 미상 1N5819'이거나 다른 제조사(onsemi · Vishay …)면 TSC 같은 품번 문서는 그 부품의 문서가 아니다. 정답들은
#      원래 값을 TSC 값으로 대신하지 않는다(v3-01 근거, 11-07 c20-04: TSC 1N5819 값으로 사양 동등을 냈다)
UNKNOWN_MAKER = re.compile(r'제조사\s*(?:가|는|를)?\s*(?:미상|불명|모르|알\s*수\s*없|확인하지\s*못)|maker (?:is )?unknown|unknown maker', re.I)
OTHER_MAKERS = re.compile(r'\b(?:onsemi|on ?semi(?:conductor)?|vishay|nexperia|diodes inc|rohm|stmicro\w*|infineon|littelfuse|bourns|toshiba|'
                          r'fairchild|panjit|micro commercial|comchip|central semi\w*)\b', re.I)


def original_not_tsc(original: str, text: str) -> bool:
    """원래 부품이 TSC 부품이 아니거나 제조사를 모르는가(그러면 TSC 같은 품번 행을 원래 값으로 쓰지 않는다)."""
    return bool(UNKNOWN_MAKER.search(text)) or bool(OTHER_MAKERS.search(original or ''))


def _rule_codes(rules: list[dict]) -> set[str]:
    """역할 규칙들의 조건이 쓰는 사양 코드(any 묶음 안까지). 카드 읽기 specs가 읽을 코드를 줄이는 데 쓴다."""
    out = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k == 'code':
                    out.update(v if isinstance(v, list) else [v])
                else:
                    walk(v)
        elif isinstance(x, list):
            for y in x:
                walk(y)
    for rule in rules:
        walk(rule.get('conditions') or [])
    return out


def _rows(specs, name: str) -> list[dict]:
    """품번의 사양 표 행. 제조사 이름을 떼고 찾고, 없으면 첫 낱말(주문 코드를 뗀 기본 품번, 1N4148 R0G → 1N4148)로 다시 찾는다."""
    name = strip_maker(name)
    return (specs(name) or specs(name.split()[0])) if name else []


_EXTERNAL_NUMBER = re.compile(r'^[+−-]?(?:\d+(?:\.\d+)?|\.\d+)$')
_SHA256 = re.compile(r'^[0-9a-f]{64}$', re.I)
_VRRM_ROW = re.compile(r'^(?:v\s*rrm|repetitive\s+)?peak\s+reverse\s+voltage$|^v\s*rrm$', re.I)
def _row_revision(row: dict) -> str:
    """Extract the revision suffix from a persisted datasheet citation filename."""
    document = str((row.get('citation') or {}).get('document') or '')
    return document_revision(document)


def _grade2_rows(web_search, part: str, codes: set[str], maker: str = '') -> list[dict]:
    """공식 PDF 표 행을 판정기의 기존 사양 행 모양으로 변환한다.

    외부 검색 결과는 검증된 grade-2 행만 받는다. 품번 열이 정확히 요청 품번과
    일치하고, 코드·단위·숫자 셀이 모두 명확한 행만 통과시킨다. 일반 웹 자료와
    typical 값은 이 경로에서 절대 행으로 만들지 않는다.
    """
    if web_search is None or not part or not codes or 'VRRM' not in {str(code).upper() for code in codes}:
        return []
    hosts = {'tsc': 'services.taiwansemi.com', 'taiwansemiconductor': 'services.taiwansemi.com',
             'infineon': 'www.infineon.com', 'vishay': 'www.vishay.com',
             'vishaysemiconductors': 'www.vishay.com',
             'ti': 'www.ti.com', 'texasinstruments': 'www.ti.com',
             'onsemi': 'www.onsemi.com',
             'st': 'www.st.com', 'stmicroelectronics': 'www.st.com',
             'adi': 'www.analog.com', 'analogdevices': 'www.analog.com'}
    maker_key = re.sub(r'[^a-z]', '', maker.casefold())
    if maker and maker_key not in hosts:
        return []
    try:
        terms = f'{maker} repetitive peak reverse voltage VRRM'.strip()
        documents = web_search([part], terms) or []
    except SearchBudgetExhausted:
        # Contention is a request-level budget boundary, not an empty result.
        # Let the caller suppress grade-3 fallback while preserving local rows.
        raise
    except Exception as error:  # 외부 검색 장애는 내부 판정을 중단시키지 않는다
        LOGGER.warning('grade2_rows_failed error=%s', type(error).__name__)
        return []
    rows = []
    for document in documents:
        if document.get('evidence_grade') != 2 or not _SHA256.fullmatch(str(document.get('source_sha256') or '')):
            continue
        source_url = str(document.get('source_url') or '')
        page = document.get('page')
        if (not source_url or grade2_pdf(source_url) != source_url or not document.get('file')
                or type(page) is not int or page <= 0
                or not document.get('table') or len(document.get('doc_parts') or []) != 1):
            continue
        host = source_url.split('/')[2].casefold()
        if maker and hosts[maker_key] != host:
            continue
        if document['doc_parts'][0].casefold() != part.casefold():
            continue
        raw_row = str(document.get('row') or '').strip()
        vishay_vrrm = (host == 'www.vishay.com'
                       and re.sub(r'\s+', '', str(document.get('symbol') or '')).upper()
                       in {'VRRM', 'VRRM=VRWM=VR', 'V=V=VRRMRWMR'}
                       and re.sub(r'\s+', ' ', raw_row).casefold() in {
                           'vrrm', 'repetitive peak reverse voltage',
                           'repetitive peak reverse voltage = working peak reverse voltage = dc blocking voltage'})
        if host == 'www.vishay.com' and not vishay_vrrm:
            continue  # Only an explicit original VRRM symbol/equality is authoritative.
        code = 'VRRM' if vishay_vrrm or raw_row.upper() == 'VRRM' or _VRRM_ROW.fullmatch(raw_row) else ''
        if not code or str(document.get('unit') or '').strip().upper() != 'V':
            continue
        content = str(document.get('content') or '')
        caption = str(document.get('table') or '')
        if ((not re.search(r'\bV\s*RRM\b', content, re.I) and not vishay_vrrm)
                or not re.search(r'\bMAX(?:IMUM)?\s+RATINGS?\b', caption, re.I)):
            continue
        if document.get('conditions'):
            continue
        cells = document.get('cells') or []
        if len(cells) != 1:
            continue
        column, raw = cells[0]
        if str(column).upper() not in {'MAX', part.upper()} and not (vishay_vrrm and str(column).upper() == 'VALUE'):
            continue
        value = str(raw).strip()
        if not _EXTERNAL_NUMBER.fullmatch(value):
            continue
        maximum = float(value)
        if not math.isfinite(maximum) or maximum <= 0:
            continue
        normalized = to_si(maximum, 'V')
        if normalized is None:
            continue
        citation = {
            'document': document.get('file', ''), 'page': document.get('page'),
            'table': document.get('table', ''), 'row': document.get('row', ''),
            'source_url': source_url, 'source_sha256': document['source_sha256'],
            'evidence_grade': 2,
        }
        if re.fullmatch(r'W[1-9][0-9]*', str(document.get('chunk_id', ''))):
            citation['chunk_id'] = document['chunk_id']
        rows.append({'part': part, 'category': '', 'code': code,
                     'min': None, 'typ': None, 'max': normalized[0],
                     'text': None, 'unit': normalized[1],
                     'source_value_text': content,
                     'test_condition': document.get('conditions') or None, 'citation': citation})
    # 같은 품번·행에 서로 다른 공식 PDF 값이 섞이면 어느 쪽도 판정 근거로 선택하지 않는다.
    if len({(row['max'], row['unit']) for row in rows}) > 1 or len({row['citation']['source_url'].split('/')[2] for row in rows}) > 1:
        return []
    return rows[:1]


def _ordering_row(retriever, code: str, base: str) -> dict | None:
    """주문 코드(예: '1N4148 R0G')가 적힌 주문 정보 표 청크를 찾아 인용으로 돌려준다. 없으면 None(인용을 지어내지 않는다)."""
    # [왜] 'R0'이 'R0G' 앞부분이라 낱말 경계로 맞춘다
    exact = re.compile(rf'(?<![A-Z0-9]){re.escape(code)}(?![A-Z0-9])')
    for d in retriever(f'{code} ordering information', parts=[base]):
        if 'ORDER' in (d.get('table') or '').upper() and exact.search(d.get('content', '').upper()):
            return {'document': d.get('file'), 'page': d.get('page'), 'table': d.get('table'), 'row': code, 'chunk_id': d.get('chunk_id')}
    return None


def _identical(retriever, original: str, candidate: str) -> tuple[bool, dict | None]:
    """같은 기본 품번인지 → (동일품인가, 근거 인용). 주문 코드만 다르면 주문 정보 표의 그 행이 근거다(SPEC 8.3 주문 코드 동일품).

    주문 코드 규칙을 먼저 보고, 그 행을 못 찾으면 제조사가 같은 제품이라고 밝힌 청크를 찾아 그 청크를 인용한다(EC-10).
    """
    o, c = strip_maker(original).upper().split(), strip_maker(candidate).upper().split()
    if not o or not c or o[0] != c[0]:
        return False, None
    if o == c:
        return True, None
    if retriever is None:
        return False, None
    tails = [x[1:] for x in (c, o)]
    if all(not t or (len(t) == 1 and ORDER_CODE.fullmatch(t[0])) for t in tails):
        # 후보의 주문 코드 행을 먼저, 후보가 기본 품번뿐이면 원래 품번의 행을 인용한다
        for code in [' '.join(x) for x in (c, o) if len(x) == 2]:
            if cite := _ordering_row(retriever, code, c[0]):
                return True, cite
    docs = retriever(f'{c[0]} ordering information physically identical', parts=[c[0]])
    hit = next((d for d in docs if 'identical' in d.get('content', '').lower()), None)
    if hit is None:
        return False, None
    # [왜] 주문 표가 품번 자리를 'BZV55Cx L0G'처럼 x로 적으면 주문 코드 행을 못 찾는다. 같은 부품이라고 밝힌 그 청크
    #      (청킹 v3: 주문 행 끝 주석 · 표 주석 청크)를 근거로 인용한다. 인용이 없으면 동일품 답이 정답 쪽을 못 가리켰다(11-06 dev 08 · 15)
    cite = {'document': hit.get('file'), 'page': hit.get('page'), 'table': hit.get('table'), 'row': c[0], 'chunk_id': hit.get('chunk_id')}
    return True, (cite if hit.get('file') and hit.get('page') else None)


UNI, BI = re.compile(r'단방향|unidirection|uni-direction', re.I), re.compile(r'양방향|bidirection|bi-direction', re.I)


def _direction(part: str) -> str:
    """TSC TVS 품번의 방향: AEC 'H'를 뗀 끝이 C · CA면 양방향, 아니면 단방향(문서 'For bidirectional use C or CA suffix')."""
    base = re.sub(r'H$', '', (strip_maker(part).upper().split() or [''])[0])
    return 'bi' if re.search(r'CA?$', base) else 'uni'


SAME_DIRECTION = re.compile(r'방향[^.。\n]{0,20}?(기존|지금|원래|현재)[^.。\n]{0,6}?같아야|same (protection )?direction as', re.I)  # '보호 방향도 기존과 같아야'


def _extra_checks(j: V.Judgement, read: 'JudgeRead', category: str, rows: list[dict], roles: list[str], text: str = '') -> V.Judgement:
    """숫자 규칙 밖의 두 성질을 조건 줄로 더한다: 사용자가 요구한 AEC-Q101(사양 표 AEC_Q101 행), TVS 방향(원래 부품 또는 사용자가 말한 방향).

    하나라도 맞지 않으면 불충족이다(동일품은 그대로). [왜] 둘 다 문서 · 품번으로 정해지는데 사양 표 밖 요구로 보고 거절했다(11-06 v3-10 · 14 · 15)
    """
    add = []
    if any(x.code == 'AEC_Q101' for x in read.required_specs):
        row = next((r for r in rows if r['code'] == 'AEC_Q101'), None)
        add.append(V.Check(code='AEC_Q101', tier='required', op='=', basis='AEC-Q101 적합(사용자 요구)', condition=row and row.get('text'),
                           citation=row and row.get('citation'), result='pass' if row else 'fail',
                           why='' if row else '데이터시트에 AEC-Q101 적합 문장이 없음'))
    if category.startswith('tvs') and ('R06' in roles or any(x.code == 'DIRECTION' for x in read.required_specs)):
        words = ' '.join(x.words for x in read.required_specs if x.code == 'DIRECTION')
        if read.original_part and SAME_DIRECTION.search(text):
            # [왜] 사용자가 '보호 방향도 기존과 같아야 한다'고 적었으면 그것이 요구다. 읽기가 질문 속 혼잣말('방향 구분도 덜 신경 써도 될 것 같아서')을
            #      양방향 요구로 적어 단방향 원래 부품의 양방향 후보가 통과했다(11-06 공식 6회차 v3-10)
            words = ''
        want = 'uni' if UNI.search(words) else 'bi' if BI.search(words) else (_direction(read.original_part) if read.original_part else None)
        if want:
            have = _direction(j.part)
            name = {'uni': '단방향', 'bi': '양방향'}
            add.append(V.Check(code='DIRECTION', tier='required', op='=', basis=f'{name[want]}(' + ('사용자 요구' if words else '원래 부품과 같음') + ')',
                               condition=name[have], result='pass' if have == want else 'fail',
                               why='' if have == want else f'후보는 {name[have]}(품번 끝 글자)'))
    if not add:
        return j
    verdict = 'NOT_SUFFICIENT' if j.verdict != 'IDENTICAL' and any(c.result == 'fail' for c in add) else j.verdict
    return j.model_copy(update={'checks': j.checks + add, 'verdict': verdict})


def _schottky_exempt(j: V.Judgement, category: str) -> V.Judgement:
    """쇼트키 계열 후보의 TRR 조건은 면제(정답 판정 기준표 3.5). 면제한 뒤 판정을 다시 정한다.

    조건의 exempt가 면제 범위다: schottky(쇼트키 계열 모두, 기본) · sic(SiC 쇼트키만, R14 100 kHz 초과) · none(면제 없음).
    """
    sic = category.startswith('sic-schottky')
    if not sic and not category.startswith('schottky'):
        return j
    free = ('schottky', 'sic') if sic else ('schottky',)
    checks = [c.model_copy(update={'result': 'pass', 'why': '쇼트키 면제'}) if c.code == 'TRR' and c.exempt in free else c
              for c in j.checks]
    if j.verdict == 'IDENTICAL':
        verdict = 'IDENTICAL'  # [왜] 동일품은 조건 결과보다 먼저다(judge_part와 같은 순서, SPEC 3절)
    elif any(c.result == 'fail' for c in checks):
        verdict = 'NOT_SUFFICIENT'
    elif any(c.result == 'unverified' for c in checks):
        verdict = 'NOT_VERIFIED'
    elif j.verdict in ('IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT'):
        verdict = j.verdict
    elif j.assumed:
        # [왜] 회로 값 없이 원래 부품 기준으로 통과한 후보는 '역할상 충분'을 내지 않는다(judge_part와 같은 규칙, 11-17).
        #      면제로 남은 조건이 풀렸으면 주요 정격이 원래보다 못하지 않을 때만 사양 동등이다
        verdict = 'SPEC_EQUIVALENT' if j.not_worse else 'NOT_VERIFIED'
    else:
        verdict = 'ROLE_SUFFICIENT'
    return j.model_copy(update={'checks': checks, 'verdict': verdict})


# [왜] R22(PWM 모터 프리휠링)는 R03(릴레이 플라이백)과 같은 자리라 같은 양을 다른 이름으로 받는다(roles.yaml R22 recognize).
#      읽기가 R22를 고르고 R03 이름(i_coil)으로 적으면 값이 버려져 확인 안 됨이 됐다(11-06 공식 1회차 v3-12)
SAME_QUANTITY = {'v_coil': 'v_in_max', 'i_coil': 'i_max', 'v_in_max': 'v_coil', 'i_max': 'i_coil'}
LIMITS = {'v_drop_allowed': 'VF', 'ir_allowed': 'IR'}
# 원문 한계 문장(숫자 · 단위 · 요구 말이 모두 있을 때만): 전압강하 → VF, 역류 · 누설 → IR
TEXT_LIMITS = (('VF', 'v_drop_allowed', re.compile(r'전압\s?강하[^.。\n]{0,25}?(\d+(?:\.\d+)?)\s*(m?V)(?=[^.。\n]{0,8}?(?:까지|이하|이내|허용|이어야|여야))')),
               ('IR', 'ir_allowed', re.compile(r'(?:역류|누설\s?전류)[^.。\n]{0,25}?(\d+(?:\.\d+)?)\s*([µu]A|mA|nA)(?=[^.。\n]{0,8}?(?:까지|이하|이내|허용|이어야|여야))')))  # 이 역할에 없어 버려진 한계 값 이름 → 같은 뜻의 사양 표 항목
# [주의] 단위는 실제 단위만 본다. 'R0G'의 '0G'를 숫자+단위로 봐 포장 코드 질문을 거절했다(11-06 h3-10)
NUMBER_UNIT = re.compile(r'\d+(?:\.\d+)?\s*(?:[munpµμkM]?(?:V|A|W|s|Hz|F|Ω)\b|°C|%|ppm|FIT\b|dB)')
ORDERING = re.compile(r'포장|packing|packag|ordering|주문|suffix|접미|reel|릴|ammo|앰모', re.I)  # 주문 코드 · 포장 이야기(질문 자체이지 성질이 아님)
# [주의] FIT은 대문자 낱말만 본다. 'fitted'(달려 있는)의 fit을 고장률로 봐 거절했다(공식 10회차 3세트 v3-08)
OUTSIDE_WORDS = re.compile(r'(?-i:\bFIT\b)|MTBF|고장|수명|lifetime|reliab|신뢰|noise|잡음|radiation|방사|이온화|선량|krad|rad\(si\)|(?-i:\bTID\b)|drift|드리프트|실측|measured|성적서|test report|로트|lot\b|'
                           r'반품|guarant|보장|aec-?q200', re.I)  # 사양 표가 담지 않는 성질 낱말
SAME_AS = re.compile(r'same|같은|동등|equivalent|as good as|현재|지금|기존|current|existing|fitted', re.I)  # 지금 부품과 같기를 바라는 말
# [왜] '표면실장 · 삽입형'은 패키지 이름이 아니라 실장 방식이다. 패키지 이름으로 도구에 넘기면 그 이름의 패키지가 없어 0개였다(11-07 v2 n01 · n09).
#      스루홀(리드 · 나사 고정) 패키지 이름은 `spec_lookup.THT_PACKAGES`(17종, 11-07 사양 표 패키지 56종 DB 실측)이고 나머지는 표면실장으로 본다
SMD_WORDS = re.compile(r'표면\s*실장|surface[- ]?mount|(?-i:\bSMD\b|\bSMT\b)', re.I)
THT_WORDS = re.compile(r'삽입\s*형|스루\s*홀|through[- ]?hole|(?-i:\bTHT\b)|리드\s*형|axial', re.I)


def mount_wanted(read) -> str:
    """사용자가 요구한 실장 방식: 'smd' · 'tht' · ''(요구 없음). 패키지 칸 · 요구 성질 말에서 본다(대체 이유인 '삽입형 대신'은 앞말이 아니라 바라는 쪽)."""
    words = ' '.join([read.package_wanted] + [r.words for r in read.required_specs])
    if SMD_WORDS.search(words):
        return 'smd'
    return 'tht' if THT_WORDS.search(words) else ''


def mount_of(packages: list[str]) -> set[str]:
    """패키지 이름들 → 실장 방식 집합."""
    return {'tht' if re.sub(r'[^A-Z0-9]', '', p.upper()) in THT_PACKAGES else 'smd' for p in packages or []}


# [왜] 읽기가 고른 분류로 0개일 때 넓힐 같은 계열(쇼트키끼리, 회복 시간 계열끼리). 분류를 통째로 빼면 '쇼트키' 요구에 초고속 정류형이 나왔다(11-07 h4-14)
_RECOVERY = ['fast-recovery-trr-100-500ns', 'high-efficiency-trr-50-99ns', 'super-fast-recovery', 'ultra-fast-recovery']
SIBLINGS = {'schottky-rectifier': ['schottky-diode', 'sic-schottky-diode'], 'schottky-diode': ['schottky-rectifier'],
            'sic-schottky-diode': ['schottky-rectifier'], **{c: [x for x in _RECOVERY if x != c] for c in _RECOVERY}}
# [왜] 사용자가 계열을 콕 집어 말했는지(그러면 분류를 빼지 않는다). '정류 · 고속'은 일반 말이라 넣지 않는다('단일 정류 다이오드'에 분류를 못 빼 0개, 11-07 h4-12)
NAMED_FAMILY = re.compile(r'쇼트키|schottky|제너|zener|(?-i:\bTVS\b)|(?-i:\bESD\b)|브리지|bridge|스위칭|switching|(?-i:\bSiC\b)', re.I)
FAMILY = re.compile(r'쇼트키|schottky|정류|rectifier|제너|zener|tvs|esd|고속|fast|ultra|super|switching|스위칭|브리지|bridge', re.I)  # 다이오드 계열 이름


GRADE = {'A': 1, 'B': 2, 'C': 5}  # TSC 제너 VZ 공차 등급(%): BZT52B · BZV55B는 ±2%, …C는 ±5%


def _restates_circuit_value(spec: 'RequiredSpec', values: dict, rules: list[dict]) -> bool:
    """요구 말의 숫자가 역할 규칙이 같은 항목에 쓰는 회로 값과 같으면(정상 최대 13.0V를 'VWM 13.0V에 맞게'로 다시 적음) 되풀이다."""
    # [왜] 되풀이를 요구로 읽으면 'maximum' 같은 말로 방향이 뒤집혔다(VRWM ≤ 13, 11-06 v3-09 안정성 측정). 역할 조건이 그 값으로 이미 본다
    nums = [_si(float(n), u) for n, u in QTY.findall(spec.words) if u]
    if len(nums) != 1:
        return False
    used = {n for rule in rules for c in rule['conditions'] if c.get('code') == spec.code for b in C._bases(c) for n in C.names(b)}
    return any(values.get(n) is not None and abs(values[n] - nums[0]) <= 1e-9 * max(1.0, abs(nums[0])) for n in used)


def _tolerance_words(words: str, code: str, text: str) -> str:
    """제너 VZ 요구 말에 공차가 없는데 사용자 원문에 '공차 ±x%'나 'B 등급'이 있으면 붙인다."""
    # [왜] 읽기가 공차를 빼고 '공칭 3.3V'만 적는 회차가 있어 C 등급(±5%) 부품이 나왔다(공식 4회차 v3-13)
    if code != 'VZ' or '±' in words:
        return words
    m = re.search(r'공차[^.。\n]{0,10}?±\s*(\d+(?:\.\d+)?)\s*%|tolerance[^.\n]{0,10}?±\s*(\d+(?:\.\d+)?)\s*%', text, re.I)
    if m:
        return f'{words} ±{m.group(1) or m.group(2)}%'
    g = re.search(r'\b([ABC])\s*등급|grade\s*([ABC])\b', text)
    return f'{words} ±{GRADE[g.group(1) or g.group(2)]}%' if g else words


def _ground_ops(words: str, text: str, code: str = '') -> str:
    """요구 말의 숫자가 사용자 원문에 그대로 있으면, 원문의 그 구절(연산 말 포함)로 바꾼다. 연산 말은 원문을 믿는다."""
    # [왜] 원문 '허용하는 전압은 최대 23.2V'를 읽기가 'below 23.2 V'로 옮긴 회차만 미만(<)이 되어 23.2V 후보가 불충족이었다(11-07 m2 v3-09).
    #      숫자 · 단위가 하나뿐인 말만, 원문 구절에 연산 말(최대 · 이하 · 미만 · 이상 …)이 있을 때만 바꾼다. 범위 · 단위를 바꿔 쓴 말은 그대로 둔다
    # [왜] 'at 10A 10/1000µs at or below 23.2V'처럼 시험 조건 숫자가 섞이면 숫자가 셋이라 건너뛰어 같은 일이 났다(11-10 v3-09, 사전 등록 #50).
    #      그 항목 단위(VC면 V)의 숫자만 센다. 다른 단위 숫자는 조건을 만들 때도 버려진다(conditions.user_conditions)
    nums = [(n, u) for n, u in re.findall(r'(\d+(?:\.\d+)?)\s*([a-zA-Zµμ]+)', words) if code not in C.CODE_UNIT or C._si(n, u, code) is not None]
    if len(nums) != 1 or C._RANGE.search(words):
        return words
    num, unit = nums[0]
    for m in re.finditer(r'(?<![\d.])' + re.escape(num) + r'\s*' + re.escape(unit), text):
        start = max(text.rfind(ch, 0, m.start()) for ch in '.,;。\n') + 1
        ends = [i for i in (text.find(ch, m.end()) for ch in '.,;。\n') if i != -1]
        clause = text[start:min(ends) if ends else len(text)].strip()
        if any(p.search(clause) for p in (C._LE, C._LT, C._GE, C._GT)):
            return clause
    return words


def _rated_words(words: str, text: str) -> str:
    """사용자 원문에서 그 숫자 바로 앞에 '정격'이 있으면 요구 말에 rated를 붙인다(정격 값과 같음으로 읽게)."""
    # [왜] '평균 순방향 전류 정격 1A'를 읽기가 'average forward current 1A'로 옮기면 1A 이상으로 읽혀 2A 부품(SK24AH)이 나왔다(11-06 v3-14)
    if C.RATED.search(words):
        return words
    for m in re.finditer(r'(\d+(?:\.\d+)?)\s*([a-zA-Zµμ]+)', words):
        if re.search(r'정격[^.,。\n]{0,15}?(?<![\d.])' + re.escape(m.group(1)) + r'\s*' + re.escape(m.group(2)), text):
            return words + ' (rated)'
    return words


def _original_from_text(read: JudgeRead, text: str) -> str:
    """후보와 기본 품번이 같고 주문 코드만 다른 품번을 사용자가 적었으면 그것이 원래 부품이다(주문 코드 질문)."""
    # [왜] 'D1에 쓸 BZV55B3V3 L0 대신 TSC BZV55B3V3 L0G로'에서 읽기 셋 중 둘이 넷리스트 옛 표기(BZX84C3V3)를 원래 부품으로 적어
    #      동일품을 사양 동등으로 냈다(11-06 공식 7회차 v3-06)
    upper = text.upper()
    for cand in read.candidates:
        c = strip_maker(cand).upper().split()
        if not c or strip_maker(read.original_part).upper().split()[:1] == c[:1]:
            continue
        for m in re.finditer(r'(?<![A-Z0-9])' + re.escape(c[0]) + r'(?:\s+([RALM][A-Z0-9]G?))?(?![A-Z0-9])', upper):
            if m.group(0).split() != c:
                return m.group(0)
    return read.original_part


NO_REVISION_ASKED = re.compile(r'없음|없다|없습|없어|아님|무관|NONE|NOT\s+SPECIFIED|NO\s+(?:SPECIFIC\s+)?(?:REVISION|EDITION)', re.I)  # 개정판 요구가 없다는 말


def outside_corpus(read: JudgeRead, facts: dict, text: str = '') -> tuple[Reason, str] | None:
    """사용자가 꼭 요구한 것이 코퍼스 밖이면 (거절 사유, 요약). 이름 · 항목만 대조한다(숫자 판단 없음, SPEC 8.3)."""
    maker = re.sub(r'[^A-Z]', '', read.maker_wanted.upper())  # 'Taiwan Semiconductor Co.' → 'TAIWANSEMICONDUCTORCO'
    # [왜] #146이 Vishay · TI · ST · ADI · onsemi를 통과시켰지만 아래 판정은 TSC 내부 카드 행을 그대로 써
    #      "비셰이 1N5817"에 TSC 1N5817.pdf로 판정 답이 나갔다. 9c87ba36처럼 TSC · Infineon만 통과시키고 나머지는 maker_missing으로 거절한다
    if maker and maker != 'TSC' and not maker.startswith('TAIWANSEMI') and not maker.startswith('INFINEON'):
        return Reason.MAKER_MISSING, f'required maker {read.maker_wanted} is not a supported Grade 2 manufacturer'  # 품번 문구가 아닌 제조사 문구(#63)
    # [왜] 사실 확인이 코퍼스 목록에 없다고 확인한 품번을 후보로 판정하면, 비슷한 다른 품번 문서로 판정 답이 나갔다(#46 Haiku Supervisor v3-32 · 34:
    #      1N5408X · UF4007X). 원래 부품은 다른 제조사 품번일 수 있어 후보만 본다. 이름이 그대로 같을 때만 거절한다(접두어로 넓히지 않는다)
    missing = {name.upper() for name, ok in (facts.get('parts') or {}).items() if not ok}
    if gone := [c for c in read.candidates if strip_maker(c).upper() in missing]:
        return Reason.PART_MISSING, 'candidate not in the corpus: ' + ', '.join(gone)
    wanted = read.revision_wanted.strip().upper()
    # [왜] 판정 길에는 코퍼스 개정판 전체 목록이 없다. 사실 확인이 코퍼스에 있다고 확인한 개정 코드(K2611)를 담을 때만 통과한다
    # [주의] 판으로 보이는 글(개정 코드 · 연도 · '판' · edition · rev)만 요구로 본다. 읽기가 포장 코드 'L0'을 넣어 개정판 거절로 끝났다(11-06 v3-03)
    # [주의] 사용자 글에 그 판이 실제로 있어야 한다. 읽기가 프롬프트 예시의 'K2611'을 지어내 개정판 거절로 끝났다(11-06 h3-15)
    grounded = not text or any(tok in text.upper() for tok in re.findall(r'[A-Z]\d{4}|(?:19|20)\d{2}', wanted)) or not re.search(r'\d', wanted)
    # [주의] 읽기가 요구가 없다는 말을 이 칸에 적으면('특정 개정판 요구는 없음') 판 낱말이 들어 있어 개정판 거절로 끝났다(11-17 v3-09 과잉 거절).
    #      요구 없음을 뜻하는 말이면 요구로 보지 않는다
    if (wanted and grounded and EDITION.search(wanted) and not NO_REVISION_ASKED.search(wanted)
            and not any(ok and code in wanted for code, ok in (facts.get('revisions') or {}).items())):
        return Reason.REVISION_MISSING, f'required revision {read.revision_wanted} is not confirmed in the corpus'
    # [왜] '쇼트키 정류형'처럼 다이오드 계열을 말한 것은 분류 조건이지 사양 표에 없는 성질이 아니다. 거절했다(11-06 h3-14)
    # [주의] '지금 SS14와 같은 수준'처럼 막연한 바람도 none으로 왔다(v3-08). 숫자 · 단위나 코퍼스 밖 성질 낱말(고장률 · 수명 · 잡음 · 실측 …)이 있을 때만 거절한다
    # [주의] '지금 달린 SS14와 같은 수준'은 판정(사양 동등 · 역할상 충분)이 답하는 바람이다. 코퍼스 밖 성질 낱말이 없으면 거절하지 않는다(공식 10회차 3세트 v3-08)
    unheld = [r.words for r in read.required_specs if r.code == 'none' and not FAMILY.search(r.words) and not ORDERING.search(r.words)
              and (OUTSIDE_WORDS.search(r.words) or (NUMBER_UNIT.search(r.words) and not SAME_AS.search(r.words)))]
    if unheld:
        return Reason.NOT_FOUND, 'required property not in the spec table: ' + ', '.join(unheld)
    return None


def _report(status: str, summary: str, missing=(), reason=None) -> dict:
    return AgentReport(agent='judge', status=status, summary=summary[:200], missing=list(missing), reason=reason).model_dump(mode='json')


def display_inputs(values: dict, conds: dict) -> list[dict]:
    """판정에 채택한 값만 표시한다. 원문·LLM 읽기 결과는 공개하지 않는다."""
    rows = []
    for name, value in values.items():
        unit = ('V' if name.startswith(('v_', 'vz_')) else 'A' if name.startswith(('i_', 'ir_')) else
                {'c_hold': 'F', 'droop_allowed': 'V/s', 'err_allowed': '(비율)'}.get(name, ''))
        shown = ('예' if value else '아니오') if isinstance(value, bool) else f'{value:g} {unit}'.strip()
        rows.append({'code': name, 'value': shown})
    units = {'TA': '°C', 'TJ': '°C', 'TC': '°C', 'IF': 'A', 'IZ': 'A', 'IPP': 'A', 'VR': 'V', 'pulse': 's'}
    for name, condition in conds.items():
        shown = ', '.join(f'{key}={value:g} {units.get(key, "")}'.strip() if isinstance(value, (int, float))
                          else f'{key}={value}' for key, value in condition.items())
        if shown:
            rows.append({'code': name, 'value': shown})
    return rows[:60]


def judge_agent(state: dict, *, specs, find, retriever, web_search=None, web_search_fallback=None, reread=None) -> dict:
    """그래프 노드: 코퍼스 밖 요구면 거절 사유로 보고하고, 아니면 빠진 값을 한 번 묻고 사양 표 값으로 후보를 판정한다(찾기면 거르고 판정하고 줄 세운다)."""
    rules = C.load()
    # 재개 시 읽기 LLM은 다시 부르지 않지만 고정 회로의 연결 검증은 유지한다.
    read = _validate_circuit_role(JudgeRead.model_validate(state['judge_read']), state.get('target_part') or {})
    revision_text = ' '.join([state.get('conditions', ''), state.get('question', '')])
    editions = requested_revisions(revision_text)
    references = []
    grade2_budget_exhausted = False
    grade3_budget_exhausted = False
    # [왜] 코퍼스 밖 요구(사양 표에 없는 성질 · TSC 아닌 제조사 · 확인 안 된 개정판)는 규칙 · 조건을 만들기 전에 거절한다.
    #      묻거나 판정하면 그 요구와 상관없는 판정 답이 나간다(11-06 동결 평가: 비관련 35건 중 8~10건)
    if refused := outside_corpus(read, state.get('facts') or {}, ' '.join([state.get('conditions', ''), state.get('question', '')])):
        reason, why = refused
        return {'path': ['판정'], 'reports': (state.get('reports') or []) + [_report('fail', f'cannot judge from the corpus: {why}', reason=reason)]}
    part = state.get('target_part') or {}
    # [왜] 숫자 확인은 질문 · 사용 조건 · 대상 주변 회로 글로만 한다. 역할 목록(rules)의 알아보는 법 글에 있는 숫자는 사용자가 준 값이 아니다(AC-02)
    current_text = _judge_current_text(state)
    recalled = _history_for_current_question(state.get('conversation_history'), state.get('question', ''))
    # 회상 요청일 때만 같은 이름의 이력을 grounding에 보탠다. 주제 전환이나
    # 일반 질문에서는 과거 역할·숫자가 현재 값으로 승격되지 않는다.
    history_text = '\n'.join(recalled)
    text = '\n'.join(x for x in (current_text, history_text, render_read(state, {})) if x)
    direct_text = _direct_condition_text(current_text)
    roles = list(dict.fromkeys(r for r in (read.role, read.role_alt) if r and r != 'other'))  # 같은 역할을 두 번 적으면 하나로
    # [왜] 같은 대상을 이어 묻는 턴: 읽기 LLM이 턴마다 역할을 다르게 읽어 앞 답과 판정이 뒤집혔다(11-17 실측: 찾기 R02 · 사양 동등 → 바로 뒤 판정 R01 · 확인 안 됨).
    #      이 대화에서 이미 정한 역할(사용자가 되묻기에서 보거나 고른 역할)을 이어 쓴다. Supervisor가 같은 대상일 때만 `prior`를 넘긴다
    prior = state.get('prior') or {}
    prior_roles = [r for r in prior.get('roles') or [] if r in rules]
    if prior_roles:
        roles = prior_roles
    base = {'roles': roles, 'role_evidence': read.role_evidence, 'results': [], 'shown': [], 'unverified': [], 'terms': [],
            'capped': False, 'dropped': [], 'asked': []}
    if not roles:
        return {'judgement': {**base, 'kind': 'no_rule'}, 'path': ['판정'],
                'reports': (state.get('reports') or []) + [_report('partial', 'role outside the 23 roles: no judging rule')]}
    if not prior_roles:
        roles = _prefer_role_from_load(roles, rules, text)
    kinds = {k: v for r in roles for k, v in C.inputs(rules[r]).items()}

    def resolve_inputs(input_kinds: dict) -> tuple[dict, dict, list[str]]:
        if recalled:
            # 모델이 초기 행만 회상하거나 일부 필드를 생략해도, 선택된 동일
            # 시나리오의 사용자 행을 시간순으로 합친다. 현재 직접 인용은 마지막에 우선한다.
            history_values, history_conds = _recover_history_conditions(recalled, input_kinds, read=read)
            _, _, old_dropped = to_inputs(read, history_text, input_kinds)
            current_values, current_conds, current_dropped = to_inputs(
                read, current_text, input_kinds, preferred_text=current_text)
            merged_values = {**history_values, **current_values}
            merged_conds = {**history_conds, **current_conds}
            dropped_values = old_dropped + current_dropped
        else:
            merged_values, merged_conds, dropped_values = to_inputs(
                read, text, input_kinds, preferred_text=current_text)
        merged_values = _text_flags(merged_values, text, input_kinds, direct_text=direct_text)
        merged_values, merged_conds = _recover_explicit_conditions(
            direct_text, merged_values, merged_conds, input_kinds)
        return merged_values, merged_conds, dropped_values

    values, conds, dropped = resolve_inputs(kinds)
    if prior_roles:
        # 앞 턴에 사용자가 알려 준 회로 값도 이어 쓴다(그 턴에 사용자 글 인용 확인을 거친 값, AC-02). 이번 글에서 읽은 값이 먼저다
        given = prior.get('inputs') or {}
        values = {**{k: v for k, v in (given.get('values_si') or {}).items() if k in kinds}, **values}
        conds = {**{k: v for k, v in (given.get('test_conditions') or {}).items() if k in kinds}, **conds}
    auto_selected = False
    if len(roles) > 1 and read.role_evidence:
        complete = [r for r in roles if not _required_missing(rules[r], _role_present(r, rules[r], values, conds, text))]
        # 읽기가 회로 연결 근거를 함께 냈고 한 역할만 필수 입력을 모두 갖추면
        # 그 역할을 선택한다. 두 역할 모두/어느 쪽도 충분하지 않으면 기존처럼
        # 사용자에게 한 번만 확인해 모호성을 보존한다(특정 문항 분기 없음).
        if len(complete) == 1:
            roles = complete
            auto_selected = True
            kinds = {k: v for k, v in C.inputs(rules[roles[0]]).items()}
            values, conds, dropped = resolve_inputs(kinds)
    if auto_selected:
        asked = list(dict.fromkeys(_required_missing(rules[roles[0]], set(values) | set(conds))))
    else:
        asked = list(dict.fromkeys(n for r in roles for n in C.needed(rules[r], set(values) | set(conds))))
    if (NO_MORE_CONDITIONS.search(current_text)
            or state.get('conditions', '').strip().rstrip('.!') in {'모름', '몰라', '몰라요', '모르겠어', '모르겠어요', '모르겠습니다'}):
        asked = []
    read = read.model_copy(update={'original_part': _original_from_text(read, text)})
    # [왜] 후보가 모두 원래 부품과 같은 품번이면 회로 값 · 역할과 상관없이 동일품이다(SPEC 3절). 6개 값을 물은 뒤 동일품을 냈다(#65).
    #      주문 코드만 다른 품번은 문서 행을 찾아야 동일품이라 묻고, 원래 부품의 제조사가 다르거나 모르면 근거가 없어 묻는다(EC-05)
    same_part = (state.get('question_type') != 'candidate_find' and bool(read.candidates) and not original_not_tsc(read.original_part, text)
                 and all(_identical(None, read.original_part, c)[0] for c in read.candidates))
    if same_part:
        asked = []
    elif state.get('reply_text'):
        # 글로 답한 뒤 다시 읽은 회차: 묻지 않고, 같이 온 폼 답 · 역할만 더한다(위 [왜])
        values, conds = merge_reply(state.get('reply_answers') or {}, values, conds, kinds)
        if state.get('reply_role') in roles:
            roles = [state['reply_role']]
        asked = []
    elif prior_roles:
        asked = []  # 이 대상은 이 대화에서 이미 한 번 물었다. 이어 묻는 턴마다 같은 폼을 다시 띄우지 않는다(모르는 값은 원래 부품 기준으로 본다)
    elif asked or len(roles) > 1:
        # [주의] 인터럽트는 문항당 한 번이다(AC-08). 재개하면 이 노드가 처음부터 다시 돌지만, 읽기는 앞 노드에 남아 있어 LLM을 다시 부르지 않는다
        # [주의] 재개 값은 {'answers': {...}, 'role': ...} 모양이다. 빈 dict({})로 재개하면 LangGraph가 재개로 보지 않고 다시 멈춘다(11-06 실측)
        # [왜] 되묻기 전에 에이전트가 회로에서 읽은 것(역할 · 근거)을 같이 보낸다. 화면이 값만 묻는 폼으로 보여 사용자는 아무것도
        #      조사하지 않고 묻는다고 느꼈다(11-17 조장 결정: 되묻기는 단서를 더 얻는 수단). `roles`는 읽은 순서라 첫 값이 가장 유력하다
        reply = interrupt({'missing': asked, 'role_choices': roles if len(roles) > 1 else [], 'question': _ask_text(asked, roles, rules),
                           'roles': roles, 'role_evidence': read.role_evidence,
                           # 역할 후보가 둘이면 역할마다 묻는 값이 다르다. 화면이 고른 역할의 값만 보이게 나눠 보낸다
                           'role_missing': {r: [n for n in asked if n in C.inputs(rules[r])] for r in roles}}) or {}
        note = str(reply.get('text') or '').strip()
        if note and reread and not state.get('reply_text'):
            # [왜] 사용자가 폼 대신 글로 답했다("전원은 5V, 전류는 잘 몰라"). 그 글을 사용 조건에 더해 읽기 LLM을 한 번 더 부르고(숫자는 같은
            #      글 인용 확인을 거친다, AC-02), 더 묻지 않고 판정한다. 폼 답 · 고른 역할이 같이 왔으면 그 값이 먼저다
            # [주의] 다시 읽은 뒤에는 인터럽트를 부르지 않는다(문항당 한 번, AC-08). `reply_text`가 그 표시다
            again = {**state, 'conditions': f"{state.get('conditions', '')}\n{note}".strip(), 'reply_text': note,
                     'reply_answers': reply.get('answers') or {}, 'reply_role': reply.get('role')}
            again['judge_read'] = reread(again)['judge_read']
            return judge_agent(again, specs=specs, find=find, retriever=retriever, web_search=web_search,
                               web_search_fallback=web_search_fallback, reread=reread)
        values, conds = merge_reply(reply.get('answers') or {}, values, conds, kinds)
        if reply.get('role') in roles:
            roles = [reply['role']]
    base['analysis_inputs'] = {'roles': roles, 'values_si': dict(values), 'test_conditions': dict(conds),
                               'read_values': [v.model_dump(mode='json') for v in read.values]}
    used_names = {name for role in roles for name in C.inputs(rules[role])}
    base['input_conditions'] = display_inputs({n: v for n, v in values.items() if n in used_names},
                                               {n: v for n, v in conds.items() if n in used_names})
    # [왜] 사용자가 숫자로 적은 규격('VRRM 400~600V', 'trr 최댓값 100ns 이하')을 역할 규칙 조건 뒤에 필수 조건으로 붙인다.
    #      판정과 찾기가 같은 규칙을 쓴다. 붙이지 않으면 규격 밖 후보를 보여 주거나 원래 부품 값과만 비교했다(11-06 v3-05 · 11 · 12)
    # [왜] 한계 값('전압강하 1.8V까지')을 읽기가 회차마다 요구 성질(VF)로도, 이 역할에 없는 회로 값 이름(v_drop_allowed)으로도 적었다.
    #      버려진 한계 값은 같은 뜻의 요구 조건으로 바꿔, 어느 쪽으로 적어도 같은 판정이 나게 한다(11-06 v3-04 일관성 측정)
    given_codes = {x.code for x in read.required_specs}
    limits = [(f'{v.number}{v.unit} 이하', LIMITS[v.name]) for v in read.values
              if v.name in dropped and v.name in LIMITS and v.number is not None and LIMITS[v.name] not in given_codes]
    for code, name, pattern in TEXT_LIMITS:
        # [왜] 읽기 셋이 모두 한계 문장('다이오드 전압강하는 1.8V까지 허용한다')을 빠뜨린 회차가 있다(공식 9회차 3세트 v3-04, 1 · 2세트는 읽음).
        #      읽기가 그 항목을 요구로도 값으로도 적지 않았을 때만, 숫자 · 단위 · 요구 말이 있는 원문 문장을 코드가 읽어 같은 요구 조건으로 넣는다
        if code not in given_codes and not any(v.name == name for v in read.values) and (m := pattern.search(state.get('conditions', ''))):
            limits.append((f'{m.group(1)}{m.group(2)} 이하', code))
    spec_words = {}
    for x in read.required_specs:  # 같은 항목을 둘로 나눠 적었으면 한 말로 잇는다('공칭 3.3V' + '±2% B 등급')
        if _restates_circuit_value(x, values, [rules[r] for r in roles]):
            continue
        spec_words[x.code] = f'{spec_words[x.code]}, {x.words}' if x.code in spec_words else x.words
    extra = C.user_conditions([(_tolerance_words(_rated_words(_ground_ops(w, text, code), text), code, text), code) for code, w in spec_words.items()] + limits)
    extra = _collapse_float_boundary_conditions(extra)
    given = {c['code'] for c in extra}

    def keep(cond: dict) -> bool:
        # [왜] 사용자가 그 항목을 숫자로 정했으면, 원래 부품 값과 비교하는 역할 조건(orig.TRR 등)은 뺀다. 원래 부품을 몰라 '확인 안 됨'만 났다(v3-12)
        #      같은 이유로, 빠진 회로 값이 있어 계산할 수 없는 역할 조건(IF_AV ≥ i_max × kI인데 i_max를 다른 역할 이름으로 읽음)도 뺀다.
        #      사용자의 구매 규격('평균 순방향 전류 정격 1A')이 그 항목의 기준이다(11-06 공식 1회차 v3-12)
        codes = set(cond['code'] if isinstance(cond.get('code'), list) else [cond.get('code')])
        if not codes & given:
            return True
        bases = C._bases(cond)
        return not (any(C.orig_codes(b) for b in bases) or any(values.get(n) is None for b in bases for n in C.names(b)))
    rules = {r: ({**rules[r], 'conditions': [c for c in rules[r]['conditions'] if 'any' in c or keep(c)] + extra} if extra else rules[r])
             for r in roles}
    # [왜] 카드에서 판정 값을 읽는 specs(backend/rag/card_specs.py)는 읽을 코드를 알면 덜 읽는다. prefetch가 없는 specs(데모 · 시험 가짜)는 건너뛴다
    prefetch = getattr(specs, 'prefetch', None)
    need = sorted(_rule_codes([rules[r] for r in roles]) | {x.code for x in read.required_specs})
    # [왜] 사용자가 패키지를 여럿 허용하면('MiniMELF 또는 SOD-123F') 패키지마다 찾아 합친다. 도구는 패키지 하나만 거른다(11-06 v3-13)
    # [왜] 실장 방식 말('표면실장')은 패키지 이름으로 넘기지 않고 찾은 뒤 패키지 종류로 거른다
    # [주의] 도구는 영문 · 숫자 · 빈칸 · 점 · 하이픈 이름만 받는다. 'DO-214AC (SMA)'처럼 괄호가 섞이면 도구 오류였다(11-07 c20-12)
    packages = [x.strip() for x in re.split(r'[,/()]|\bor\b|또는', read.package_wanted or '')
                if x.strip() and not SMD_WORDS.search(x) and not THT_WORDS.search(x) and re.fullmatch(r'[A-Za-z0-9. \-]{1,30}', x.strip())] or [None]
    warm = []
    if state.get('question_type') == 'candidate_find' and getattr(find, 'also_read', None):
        # [왜] 카드 찾기(lab)는 판정이 쓸 코드까지 한 번에 읽어 두고(판정 값 읽기가 같은 문서를 다시 읽지 않음), 원래 부품 문서를 읽는 동안
        #      같은 조건의 찾기를 미리 시작한다. 찾기 질문에서 카드 읽기가 차례로 세 번이던 것을 한 번으로 줄인다(11-09 Langfuse)
        # [주의] 원래 부품 문서가 없어 조건이 바뀌면(아래 h3-13 규칙) 미리 한 찾기는 쓰이지 않을 뿐이다(찾기 memo 키가 다름)
        find.also_read(need)
        early = V.search_conditions(rules[roles[0]], values)
        if early:
            ahead = ThreadPoolExecutor(max_workers=len(packages))
            warm = [ahead.submit(contextvars.copy_context().run, find, early, read.category_wanted or None, pkg, 50) for pkg in packages]
            ahead.shutdown(wait=False)
    try:
        if prefetch and read.original_part and not original_not_tsc(read.original_part, text):
            prefetch([strip_maker(read.original_part), strip_maker(read.original_part).split(' ')[0]], need)
        original_rows = [] if original_not_tsc(read.original_part, text) else _rows(specs, read.original_part)  # 후보 조회와 같은 규칙(제조사 이름 · 주문 코드)
        original_editions = revisions_for_part(revision_text, strip_maker(read.original_part)) if editions else set()
        if editions:
            original_rows = [row for row in original_rows if _row_revision(row) in (original_editions or set())]
        if state.get('question_type') == 'candidate_find' and not original_rows and extra:
            # [왜] 원래 부품 문서가 아예 없는데(제조사 미상 1N5231) 사용자가 구매 규격을 숫자로 줬으면, 원래 값과 비교하는 역할 조건은
            #      모든 후보를 '확인 안 됨'으로 만들 뿐이다. 그 조건은 빼고 구매 규격과 회로 값 조건으로 찾는다(11-06 h3-13)
            rules = {r: {**rule, 'conditions': [c for c in rule['conditions'] if 'any' in c or not any(C.orig_codes(b) for b in C._bases(c))]}
                     for r, rule in rules.items()}
        footprint = part.get('footprint')
        if state.get('question_type') == 'candidate_find':
            terms = V.search_conditions(rules[roles[0]], values)
            # [왜] 회로 값이 없는 필수 조건은 원래 부품의 같은 정격을 기준으로 후보를 모은다. 전에는 조건이 다 비면 후보 0개 → 거절이었고,
            #      일부만 비면 그 조건 없이 찾아 원래보다 약한 부품(SS34 자리에 1N5817)이 섞였다(11-17 조장 결정, 운영 대화 실측).
            #      판정도 같은 기준이다(`verdict._stand_in`): 원래 부품 값 이상이면 그 조건은 통과로 본다
            have = {t['code'] for t in terms}
            stand_ins = [t for t in V.original_search_conditions(rules[roles[0]], values, original_rows) if t['code'] not in have]
            from_original, terms = bool(stand_ins), (terms + stand_ins)[:10]
            # [왜] 원래 부품의 패키지 · 분류를 주면 도구가 그 순서로 모두 줄 세운 뒤 50개에서 자른다(SPEC 8.3 찾기 순위)
            near = {'original_packages': [x['text'] for x in original_rows if x['code'] == 'PACKAGE' and x.get('text')] or None,
                    'original_category': next((x['category'] for x in original_rows if x.get('category')), None)}
            mount = mount_wanted(read)
            for w in warm:  # 미리 시작한 찾기가 끝나기를 기다린다(결과는 찾기 memo에 남아 아래 search가 쓴다)
                try:
                    w.result()
                except Exception:  # noqa: BLE001  [왜] 미리 한 찾기의 오류는 아래 같은 호출이 다시 내므로 여기서는 삼킨다
                    pass

            def search(category):
                merged = {}
                for pkg in packages:
                    # [왜] 원래 부품의 패키지 · 분류 순 50개만 보면, 조건이 느슨할 때(VRRM ≥ 15만) 같은 패키지 계열로 50개가 다 차서
                    #      같은 시험 조건으로 비교할 수 있는 다른 패키지 후보(SS14 SMA 등)를 보지 못하고 0개를 보였다(11-07 v2 n02 · n04 · n07).
                    #      기준에 가까운 순 50개를 더해 판정한다(값 비교는 판정 코드, 이 줄은 후보 모으기)
                    # [왜] near 순 + 기준 가까운 순 두 번 find가 기본. JUDGE_NEAR_FIND=0이면 near 한 번만(속도 A/B용)
                    hits = list(find(terms, category, pkg, 50, **near))
                    if os.getenv('JUDGE_NEAR_FIND', '1') != '0' and any(near.values()):
                        hits += list(find(terms, category, pkg, 50))
                    for f in hits:
                        merged.setdefault(f['part'].upper(), f)
                return list(merged.values())[:100]
            found = search(read.category_wanted or None) if terms else []
            if not found and terms and read.category_wanted:
                # [왜] 분류는 읽기가 고른 우리 분류 이름이다. '고속 정류형'을 fast-recovery-trr-100-500ns로 골라 trr 75 ns 이하와 겹치는 부품이
                #      0개였다(11-06 v3-12). 먼저 같은 계열 분류로 넓히고, 사용자가 계열(쇼트키 · 제너 …)을 직접 말하지 않았을 때만 분류를 뺀다
                #      (분류를 통째로 빼 '쇼트키' 요구에 초고속 정류형이 나왔다, 11-07 h4-14). 패키지는 사용자 조건이라 그대로
                # [왜] 형제 분류마다 문서 고르기 · 카드 읽기를 차례로 하면 분류를 넓힐 때 최대 26초가 더 걸렸다(11-09). 동시에 하고 순서대로 합친다
                sibs = SIBLINGS.get(read.category_wanted, [])
                with ThreadPoolExecutor(max_workers=max(1, len(sibs))) as pool:
                    futures = [pool.submit(contextvars.copy_context().run, search, sib) for sib in sibs]
                    found = [f for fu in futures for f in fu.result()]
                if not found and not NAMED_FAMILY.search(text):
                    found = search(None)
            # 구매 규격 전체 목록을 요청한 찾기에서는 현재 부품도 조건을 만족하면
            # 결과에 포함한다. 원래 부품이 요구 제조사·패키지·정격을 만족하지
            # 않으면 아래의 일반 조건 판정에서 자연스럽게 제외된다.
            candidates = [(f['part'], f.get('category', ''), f.get('packages', [])) for f in found]
            if mount:
                candidates = [c for c in candidates if mount in mount_of(c[2])]  # 요구한 실장 방식의 패키지가 있는 후보만
            # [왜] 내 설정의 선호 실장 방식(기억 읽기, SPEC 8.5)은 질문이 실장 방식을 말하지 않았을 때만 쓴다. 질문의 요구가 이긴다.
            #      거르지 않고 같은 판정 · 같은 기판 수정 여부 안에서 그 방식의 패키지가 있는 후보를 앞에 둔다(V.rank)
            prefer = '' if mount else state.get('mount_preference') or ''
            preferred = {c[0] for c in candidates if prefer and prefer in mount_of(c[2])}
        else:
            terms, found, prefer, preferred, from_original = [], [], '', set(), False
            candidates = [(p, '', None) for p in read.candidates]
        results = []
        if prefetch and candidates:
            # 후보들을 문서별로 묶어 한 번에 읽어 둔다(후보마다 차례로 읽으면 LLM 호출이 후보 수만큼 이어진다)
            prefetch([n for c in candidates for n in (strip_maker(c[0]), strip_maker(c[0]).split(' ')[0])], need)
        # [왜] _identical은 후보마다 검색 1~2번(각 1.2~1.5초)을 차례로 불러 v3-06에서 4~6초였다. 읽기만 하고 서로 영향이 없어(후보 이름 · 원래 품번만 입력)
        #      후보마다 동시에 시작해 두고 아래 루프가 원래 순서대로 결과를 꺼낸다. 오류는 꺼내는 자리에서 그대로 올라간다(원래 호출 자리와 같음)
        ident_pool = ThreadPoolExecutor(max_workers=4)
        idents = [ident_pool.submit(contextvars.copy_context().run, _identical, retriever, read.original_part, c[0]) for c in candidates]
        ident_pool.shutdown(wait=False)
        for (name, category, packages), ident in zip(candidates, idents):
            part_editions = revisions_for_part(revision_text, strip_maker(name)) if editions else set()
            if editions and not part_editions:
                continue  # An ambiguous part/edition association must not borrow another part's edition.
            rows = _rows(specs, name)
            if editions:
                rows = [row for row in rows if _row_revision(row) in part_editions]
                packages = None  # 패키지도 지정 판본에서 다시 읽는다.
            existing = {row.get('code') for row in rows}
            missing_codes = set(need) - existing
            grade2_rows = []
            if web_search and missing_codes:
                # 기존 품번 표와 find 결과는 TSC 코퍼스에서 왔다. 다른 제조사의 동명 부품과 합치지 않는다.
                tsc_candidate = bool(rows) or state.get('question_type') == 'candidate_find'
                maker = read.maker_wanted or ('TSC' if tsc_candidate else '')
                if not tsc_candidate or maker.upper() in ('TSC', 'TAIWAN SEMICONDUCTOR'):
                    try:
                        grade2_rows = _grade2_rows(web_search, strip_maker(name), missing_codes, maker)
                    except SearchBudgetExhausted as error:
                        grade2_budget_exhausted = error.grade == 2
                        grade2_rows = []
                    if editions:
                        grade2_rows = [row for row in grade2_rows
                                       if _row_revision(row) in part_editions]
                    rows = [*rows, *grade2_rows]
            if (web_search_fallback and web_search and not grade2_budget_exhausted
                    and 'VRRM' in {str(code).upper() for code in missing_codes}
                    and not grade2_rows):
                reference_terms = f"{read.maker_wanted or 'TSC'} {strip_maker(name)} repetitive peak reverse voltage VRRM"
                reference_terms += ' ' + ' '.join(sorted(part_editions))
                try:
                    fallback_rows = web_search_fallback([strip_maker(name)], reference_terms) or []
                except SearchBudgetExhausted as error:
                    grade3_budget_exhausted = error.grade == 3
                    fallback_rows = []
                for ref in fallback_rows:
                    filename = str(ref.get('file') or '')
                    if ref.get('source_type') != 'external_web_reference' or not ref.get('source_url'):
                        continue
                    if editions and not any(re.search(r'(?<![A-Z0-9])' + code + r'(?![A-Z0-9])',
                                                      (filename + ' ' + ref['source_url']).upper()) for code in part_editions):
                        continue
                    references.append({k: ref[k] for k in
                                       ('source_url', 'file', 'doc_parts', 'retrieved_at') if k in ref})
            if editions and not rows:
                continue
            packages = packages if packages is not None else [x['text'] for x in rows if x['code'] == 'PACKAGE' and x.get('text')]
            category = category or next((x['category'] for x in rows if x.get('category')), '')  # 판정 질문은 행의 분류로
            same, same_cite = ident.result()
            if editions and same_cite and (document_revision(same_cite.get('document')) not in part_editions
                                           or document_revision(same_cite.get('document')) not in (original_editions or set())):
                same, same_cite = False, None
            judged = [_schottky_exempt(V.judge_part(rules[r], r, name, values, conds, rows,
                                                    original_rows=original_rows or None, identical=same, identical_citation=same_cite,
                                                    footprint=footprint, packages=packages), category) for r in roles]
            worst = max(judged, key=lambda j: V.ORDER.index(j.verdict))  # 역할이 둘이면 더 나쁜 판정(EC-02)
            results.append(_extra_checks(worst, read, category, rows, roles, text))
    except RetrievalUnavailableError as error:
        return {'judgement': {**base, 'kind': 'judge'}, 'path': ['판정'],
                'reports': (state.get('reports') or []) + [_report('fail', f'spec table tool failed: {error.kind}', reason=Reason.SEARCH_ERROR)]}
    if same_part:
        # [왜] 묻지 않은 값을 빠진 값으로 남기면 동일품 답 아래에 '알려 주시면 판정할 수 있어요'가 붙고 재계획에도 missing으로 간다(#65)
        results = [j.model_copy(update={'missing': []}) for j in results]
    if state.get('question_type') == 'candidate_find':
        # 후보 찾기 질문은 상위 몇 개를 고르는 판정 질문과 달리, 사용자가
        # 명시한 구매 규격을 만족하는 전체 목록을 요구한다. 불충족 후보는
        # 여전히 제외하고, 통과 후보만 모두 보이도록 순위 함수의 표시 상한을
        # 현재 결과 수로 넓힌다(도구의 50개 검색 상한은 그대로 유지).
        shown, unverified = V.rank(results, per_verdict=max(1, len(results)), total=len(results), preferred=preferred)
    else:
        shown, unverified = results, []
    judgement = {**base, 'kind': 'find' if state.get('question_type') == 'candidate_find' else 'judge', 'roles': roles,
                 'results': [j.model_dump(mode='json') for j in results], 'shown': [j.model_dump(mode='json') for j in shown],
                 'unverified': [j.model_dump(mode='json') for j in unverified], 'terms': terms, 'terms_from_original': from_original,
                 'capped': len(found) >= 50,
                 'dropped': dropped, 'asked': asked, 'preferred_mount': prefer}  # 순서에 쓴 선호 실장 방식(트레이스 · API에서 보이게)
    missing = sorted({m for j in results for m in j.missing})
    status = 'ok' if results else 'partial'
    summary = f'{len(results)} candidates judged' + (f', {len(shown)} shown' if judgement['kind'] == 'find' else '')
    report_reason = Reason.LIMIT_REACHED if grade2_budget_exhausted or grade3_budget_exhausted else None
    return {'judgement': judgement, 'references': references, 'path': ['판정'],
            'reports': (state.get('reports') or []) + [_report(status, summary, missing, reason=report_reason)]}


def judge_task_node(state: dict, *, specs, find, retriever, web_search=None, web_search_fallback=None, reread=None) -> dict:
    """멀티 하위 그래프 노드: 판정 노드(`judge_agent`)를 그대로 돌리고, 그 보고를 할 일 보고서(`TaskReport`)로 바꾼다."""
    # [왜] 판정 코드는 단일 그래프(D4 v2)와 같이 쓴다. 멀티만의 칸(할 일 번호 · 판정 결과)은 여기서 붙인다
    out = judge_agent(state, specs=specs, find=find, retriever=retriever, web_search=web_search,
                      web_search_fallback=web_search_fallback, reread=reread)
    r, judgement = out['reports'][-1], out.get('judgement') or {}
    summary, reason = r['summary'], r.get('reason')
    if judgement.get('kind') == 'find':
        # [왜] 재계획이 요약만 읽고 찾은 품번을 다음 할 일(그 품번 문서 검색)에 쓸 수 있게 상위 후보 품번을 요약에 넣는다(설계 v2)
        names = [p.get('part') for p in judgement.get('shown') or [] if p.get('part')][:8]
        summary = f"{summary}: {', '.join(names)}" if names else summary
    status = r['status']
    if status == 'partial' and not judgement.get('results'):
        # [왜] 판정한 후보가 없는 보고는 답이 아니라 실패다. 일부 답(partial)으로 두면 재계획이 '있는 답으로'를 고를 때 빈 판정이 답으로 나갔다
        #      (#46 Haiku Supervisor의 v3-31 USB-C 커넥터 질문 · h3-31 인덕터 질문: 판정 읽기 셋이 모두 23역할 밖으로 읽음).
        #      23역할 밖이면 이 서비스에 판정 규칙이 없어 다시 해도 같다(not_found). 후보를 못 찾은 것은 조건을 바꿔 다시 찾을 수 있다(no_result)
        status = 'fail'
        reason = reason or (Reason.NOT_FOUND.value if judgement.get('kind') == 'no_rule' else Reason.NO_RESULT.value)
    report = TaskReport(task=state['task']['id'], agent='judge', status=status, summary=summary[:200], reason=reason,
                        missing=r.get('missing') or [], judgement=judgement,
                        references=out.get('references') or [], llm_calls=1, round=state.get('round') or 1)
    return {'reports': [report.model_dump(mode='json')], 'path': out['path']}
