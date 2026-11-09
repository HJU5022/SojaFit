"""판정 에이전트: 역할 · 회로 값을 읽고(LLM 1번), 빠진 값을 묻고(인터럽트), 사양 표 값으로 판정한다(코드).

- 역할: `judge_read_agent`(읽기 노드)와 `judge_agent`(판정 노드). 읽기를 따로 두는 이유는 인터럽트에서 재개하면
  노드가 처음부터 다시 돌기 때문이다(읽기 결과를 먼저 상태에 남겨 LLM을 다시 부르지 않는다).
  멀티는 두 노드를 하위 그래프(`build.py`)로 묶고 `judge_task_node`가 보고를 할 일 보고서로 바꾼다. 단일 그래프는 두 노드를 그대로 쓴다.
- 하지 않는 일: 숫자 비교(backend/judge/verdict.py), 답 문구(backend/multi_agent/messages.py), LLM 직접 호출(chat을 받아 쓴다).
- 출처: docs/specs/judge-agent.md What · How
"""
import contextvars
import os
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

from langgraph.types import interrupt
from pydantic import BaseModel, Field, field_validator

from backend.graph.mcp_retriever import RetrievalUnavailableError
from backend.judge import conditions as C
from backend.judge import sheet_conditions as S
from backend.judge import verdict as V
from backend.multi_agent.contracts import AgentReport, Reason, TaskReport
from backend.multi_agent.facts import ORDER_CODE
from backend.rag.spec_lookup import CODES as SPEC_CODES
from backend.rag.spec_lookup import THT_PACKAGES
from backend.rag.units import to_si

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
        #      개정 코드 · 판('K2611' · '2027 edition')은 짧다. 40자를 넘는 글은 요구 없음으로 받는다
        # shortcut: 긴 문장 안에 적힌 개정 코드도 함께 버린다(개정판 거절이 안 남). 그런 문항이 나오면 코드 모양('K2611' · 연도)만 골라 남긴다
        # [주의] JSON 조각을 자른 뒤의 길이를 본다(cut_json_leak과 어느 쪽이 먼저 돌아도 'K2611','package_wanted':… 의 K2611이 남는다)
        cut = LEAK.split(v, 1)[0].rstrip(" '\"") if isinstance(v, str) else ''
        return '' if len(cut) > 40 else v


def render_read(state: dict, rules: dict) -> str:
    """읽기 LLM에 줄 user 글: 역할 목록(이름 · 알아보는 법 · 그 역할이 받는 값 이름과 종류), 대상 주변 회로, 사용 조건, 질문."""
    part = state.get('target_part') or {}
    # [왜] 값 이름을 역할마다 roles.yaml에서 만든다. 모든 역할의 이름을 한 줄로 주면 다른 역할의 이름(i_out · v_bus)으로 읽어
    #      to_inputs가 버리고 기준값이 비었다(11-06 동결 평가 4회 실측, 인용 없는 답 40건 중 20건)
    lines = ['Roles (each lists the value names it accepts):']
    lines += [f'- {rid}: {r["name"]} — {r["recognize"]} | inputs: ' + ', '.join(f'{n} ({k})' for n, k in C.inputs(r).items())
              for rid, r in rules.items()]
    lines += [f'Question type: {state.get("question_type", "")}',
              f'Target: {part.get("ref", state.get("target", ""))} value={part.get("value", "")} footprint={part.get("footprint", "")}',
              'Nets around the target:']
    lines += [f'- {n["name"]}: ' + ', '.join(n['nodes']) + (f' (+{n["more"]} more)' if n.get('more') else '') for n in part.get('nets', [])]
    lines += [f'Conditions: {state.get("conditions", "")}', f'Question: {state.get("question", "")}']
    return '\n'.join(lines)


def judge_read_agent(state: dict, *, chat) -> dict:
    """그래프 노드: 읽기 LLM을 한 번 불러 결과를 상태에 남긴다."""
    user = render_read(state, C.load())
    if state.get('task'):
        # [왜] 멀티에서는 Supervisor 지시서가 질문의 어느 부분을 판정할지 알려 준다. 숫자 확인 글(render_read)에는 넣지 않는다:
        #      지시서는 사용자가 준 값이 아니라서, 거기 적힌 숫자로 회로 값을 확인하면 안 된다(AC-02)
        user += f"\nSupervisor brief (the part of the question this task covers): {state['task'].get('goal', '')}"
    votes = max(1, int(os.getenv('LAB_READ_VOTES', '1')))
    if votes == 1:
        read = chat('judge_read', PROMPT, user, JudgeRead)
    else:
        # [왜] lab 실험(11-06): 같은 질문의 읽기가 회차마다 달라(일관성 측정 38문항 중 7~12문항) 3세트 연속 통과가 막혔다.
        #      같은 읽기를 동시에 여러 번 부르고 칸마다 다수결로 하나를 만든다(판정 코드 · 인터럽트는 그대로 한 번). 기본은 1번(설계 그림)
        def one(_):
            try:
                return chat('judge_read', PROMPT, user, JudgeRead)
            except ValueError:
                return None  # 형식을 끝내 어긴 한 번은 표에서 뺀다
        pool = ThreadPoolExecutor(votes)
        # [주의] 스레드마다 문맥(contextvars)을 복사해 넘긴다. 그래야 LangGraph · Langfuse 추적이 이 노드 아래로 이어진다
        futures = [pool.submit(contextvars.copy_context().run, one, i) for i in range(votes)]
        reads = []
        for f in as_completed(futures):
            if (r := f.result()) is not None:
                reads.append(r)
            if len(reads) == 2 and _agree(*reads):
                break  # [왜] 먼저 끝난 두 읽기가 핵심 칸에서 같으면 다수결이 이미 정해졌다. 형식 재시도로 늦은 셋째를 기다리지 않는다(v3-14 17.5초)
        pool.shutdown(wait=False, cancel_futures=True)
        if not reads:
            raise ValueError('판정 읽기가 모두 형식을 어겼다')
        read = merge_reads(reads)
    return {'judge_read': read.model_dump(mode='json'), 'path': ['판정 읽기']}


def _most(items: list, key=lambda x: x):
    """가장 많이 나온 것(같으면 먼저 나온 것)."""
    counts = Counter(key(x) for x in items)
    best = max(counts.values())
    return next(x for x in items if counts[key(x)] == best)


def _agree(a: JudgeRead, b: JudgeRead) -> bool:
    """두 읽기가 판정을 바꾸는 칸(역할 · 값 이름과 숫자 · 요구 항목 · 원래 부품 · 후보 · 패키지)에서 같은가."""
    # [주의] 정렬하지 않고 개수로 비교한다. 같은 이름 값이 둘(숫자 없음 · 있음)이면 정렬이 None과 숫자를 비교해 TypeError가 났다(공식 8회차 v3-09)
    key = lambda r: (r.role, r.role_alt, Counter((v.name, v.number, v.flag) for v in r.values), Counter(x.code for x in r.required_specs),
                     re.sub(r'[^A-Z0-9]', '', r.original_part.upper()), [re.sub(r'[^A-Z0-9]', '', c.upper()) for c in r.candidates],
                     re.sub(r'[^A-Z0-9]', '', r.package_wanted.upper()))
    return key(a) == key(b)


def merge_reads(reads: list[JudgeRead]) -> JudgeRead:
    """읽기 여러 번을 칸마다 다수결로 하나로 만든다. 값 · 요구 성질은 절반 넘는 읽기에 나온 이름 · 항목만 남긴다."""
    need = len(reads) // 2 + 1
    role = _most([r.role for r in reads])
    pick = next(r for r in reads if r.role == role)  # 역할 근거는 그 역할을 고른 첫 읽기에서
    role_alt = _most([r.role_alt for r in reads])
    norm = lambda x: re.sub(r'[^A-Z0-9]', '', (x or '').upper())
    rules = C.load()
    names = {n for rid in (role, role_alt) if rid in rules for n in C.inputs(rules[rid])}
    # [왜] 같은 사실을 읽기마다 다른 모양으로 적으면 모양별 표가 모두 절반 아래라 사실이 통째로 빠졌다
    #      (공식 3회차 v3-04: 전압강하 한계를 요구 성질 VF · 회로 값 v_drop_allowed · 없음으로 나눠 적음). 세기 전에 모양을 맞춘다
    def name_of(v):
        return SAME_QUANTITY[v.name] if v.name not in names and SAME_QUANTITY.get(v.name) in names else v.name
    def has_code(r, code):
        return any(x.code == code for x in r.required_specs) or any(LIMITS.get(v.name) == code for v in r.values)
    values = []
    for name in dict.fromkeys(name_of(v) for r in reads for v in r.values):
        got = [v.model_copy(update={'name': name}) for r in reads for v in r.values if name_of(v) == name]
        held = sum(any(name_of(v) == name for v in r.values) for r in reads)
        if held >= need or (name in LIMITS and sum(has_code(r, LIMITS[name]) for r in reads) >= need):
            values.append(_most(got, key=lambda v: (v.number, norm(v.unit), v.flag)))
    specs = []
    for code in dict.fromkeys(x.code for r in reads for x in r.required_specs):
        if sum(has_code(r, code) for r in reads) < need:
            continue
        # [왜] 한 읽기가 같은 항목을 둘로 나눠 적기도('공칭 3.3V' · '±2% B 등급') 하고 읽기마다 담은 말이 다르다. 읽기마다 그 항목 말을 잇고
        #      가장 긴 것을 쓴다. 첫 말만 쓰니 공차가 빠져 ±5% 부품이 나왔다(공식 4회차 v3-13)
        joined = [', '.join(x.words for x in r.required_specs if x.code == code) for r in reads]
        specs.append(RequiredSpec(words=max(joined, key=len)[:160], code=code))
    return JudgeRead(role=role, role_alt=role_alt, role_evidence=pick.role_evidence, values=values,
                     original_part=_most([r.original_part for r in reads], key=norm),
                     candidates=list(_most([tuple(r.candidates) for r in reads], key=lambda c: tuple(norm(x) for x in c))),
                     package_wanted=_most([r.package_wanted for r in reads], key=norm),
                     category_wanted=_most([r.category_wanted for r in reads]), required_specs=specs,
                     maker_wanted=_most([r.maker_wanted for r in reads], key=norm),
                     revision_wanted=_most([r.revision_wanted for r in reads], key=norm))


NUM = re.compile(r'\d+(?:\.\d+)?')
QTY = re.compile(r'(\d+(?:\.\d+)?)\s*([a-zA-Zµμ°%Ω]*)')  # 인용 글의 숫자와 바로 뒤 단위
REPLY = re.compile(r'^\s*(\d+(?:\.\d+)?)\s*([a-zA-Zµμ°%]*)\s*$')
YES, NO = {'예', '네', '응', 'yes', 'true', 'y'}, {'아니오', '아니', 'no', 'false', 'n'}


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


def to_inputs(read: JudgeRead, text: str, kinds: dict) -> tuple[dict, dict, list[str]]:
    """읽기 결과 → (숫자 · 예/아니오 값, 시험 조건 값, 버린 이름). 규칙에 없는 이름과 근거 없는 값은 버린다."""
    values, conds, dropped = {}, {}, []
    for v in read.values:
        if v.name not in kinds and SAME_QUANTITY.get(v.name) in kinds:
            v = v.model_copy(update={'name': SAME_QUANTITY[v.name]})  # 같은 자리 두 역할의 같은 양을 다른 이름으로 읽은 경우
        kind = kinds.get(v.name)
        if kind is None or not grounded(text, v):
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
    return values, conds


def _ask_text(missing: list[str], roles: list[str], rules: dict) -> str:
    """사용자에게 보일 한국어 질문 하나(빠진 값 이름을 그대로 보여 준다)."""
    head = '판정에 필요한 값이 빠져 있어요. 아는 만큼 알려 주세요(모르면 비워 두면 돼요): '
    return head + ', '.join(missing) + (f" / 역할이 {' 또는 '.join(rules[r]['name'] for r in roles)} 중 어느 쪽인지도 알려 주세요." if len(roles) > 1 else '')


# [왜] 읽기가 품번을 'TSC 1N5817'처럼 제조사 이름과 함께 낸다. 사양 표 품번에는 제조사 이름이 없어 0행이 된다(11-06 평가 7건)
EDITION = re.compile(r'[A-Z]\d{4}|(?:19|20)\d{2}|판|EDITION|VERSION|\bREV', re.I)  # 데이터시트 판으로 보이는 글
MAKER = re.compile(r'^\s*(?:TSC|Taiwan\s+Semiconductor)\s+', re.I)


def _part(name: str) -> str:
    """품번 앞의 제조사 이름(TSC · Taiwan Semiconductor)을 뗀다."""
    return MAKER.sub('', name or '').strip()


# [왜] 원래 부품이 '제조사 미상 1N5819'이거나 다른 제조사(onsemi · Vishay …)면 TSC 같은 품번 문서는 그 부품의 문서가 아니다. 정답들은
#      원래 값을 TSC 값으로 대신하지 않는다(v3-01 근거, 11-07 c20-04: TSC 1N5819 값으로 사양 동등을 냈다)
UNKNOWN_MAKER = re.compile(r'제조사\s*(?:가|는|를)?\s*(?:미상|모르|알\s*수\s*없)|maker (?:is )?unknown|unknown maker', re.I)
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
    name = _part(name)
    return (specs(name) or specs(name.split()[0])) if name else []


def _ordering_row(retriever, code: str, base: str) -> dict | None:
    """주문 코드(예: '1N4148 R0G')가 적힌 주문 정보 표 청크를 찾아 인용으로 돌려준다. 없으면 None(인용을 지어내지 않는다)."""
    # [왜] 'R0'이 'R0G' 앞부분이라 낱말 경계로 맞춘다
    exact = re.compile(rf'(?<![A-Z0-9]){re.escape(code)}(?![A-Z0-9])')
    for d in retriever(f'{code} ordering information', parts=[base]):
        if 'ORDER' in (d.get('table') or '').upper() and exact.search(d.get('content', '').upper()):
            return {'document': d.get('file'), 'page': d.get('page'), 'table': d.get('table'), 'row': code, 'chunk_id': d.get('chunk_id')}
    return None


def _identical(retriever, original: str, candidate: str) -> tuple[bool, dict | None]:
    """같은 기본 품번인지 → (동일품인가, 근거 인용). 주문 코드만 다르면 주문 정보 표의 그 행이 근거다(B2, 정운 11-06).

    주문 코드 규칙을 먼저 보고, 그 행을 못 찾으면 제조사가 같은 제품이라고 밝힌 청크를 찾아 그 청크를 인용한다(EC-10).
    """
    o, c = _part(original).upper().split(), _part(candidate).upper().split()
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
    base = re.sub(r'H$', '', (_part(part).upper().split() or [''])[0])
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
    else:
        verdict = j.verdict if j.verdict in ('IDENTICAL', 'SPEC_EQUIVALENT', 'ROLE_SUFFICIENT') else 'ROLE_SUFFICIENT'
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
#      사양 표 패키지 56종 중 스루홀(리드 · 나사 고정)은 아래 17종이고 나머지는 표면실장이다(11-07 DB 실측)
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


def _ground_ops(words: str, text: str) -> str:
    """요구 말의 숫자가 사용자 원문에 그대로 있으면, 원문의 그 구절(연산 말 포함)로 바꾼다. 연산 말은 원문을 믿는다."""
    # [왜] 원문 '허용하는 전압은 최대 23.2V'를 읽기가 'below 23.2 V'로 옮긴 회차만 미만(<)이 되어 23.2V 후보가 불충족이었다(11-07 m2 v3-09).
    #      숫자 · 단위가 하나뿐인 말만, 원문 구절에 연산 말(최대 · 이하 · 미만 · 이상 …)이 있을 때만 바꾼다. 범위 · 단위를 바꿔 쓴 말은 그대로 둔다
    nums = re.findall(r'(\d+(?:\.\d+)?)\s*([a-zA-Zµμ]+)', words)
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
        c = _part(cand).upper().split()
        if not c or _part(read.original_part).upper().split()[:1] == c[:1]:
            continue
        for m in re.finditer(r'(?<![A-Z0-9])' + re.escape(c[0]) + r'(?:\s+([RALM][A-Z0-9]G?))?(?![A-Z0-9])', upper):
            if m.group(0).split() != c:
                return m.group(0)
    return read.original_part


def outside_corpus(read: JudgeRead, facts: dict, text: str = '') -> tuple[Reason, str] | None:
    """사용자가 꼭 요구한 것이 코퍼스 밖이면 (거절 사유, 요약). 이름 · 항목만 대조한다(숫자 판단 없음, SPEC 8.3)."""
    maker = re.sub(r'[^A-Z]', '', read.maker_wanted.upper())  # 'Taiwan Semiconductor Co.' → 'TAIWANSEMICONDUCTORCO'
    if maker and maker != 'TSC' and not maker.startswith('TAIWANSEMI'):
        return Reason.PART_MISSING, f'required maker {read.maker_wanted} is not TSC'
    wanted = read.revision_wanted.strip().upper()
    # [왜] 판정 길에는 코퍼스 개정판 전체 목록이 없다. 사실 확인이 코퍼스에 있다고 확인한 개정 코드(K2611)를 담을 때만 통과한다
    # [주의] 판으로 보이는 글(개정 코드 · 연도 · '판' · edition · rev)만 요구로 본다. 읽기가 포장 코드 'L0'을 넣어 개정판 거절로 끝났다(11-06 v3-03)
    # [주의] 사용자 글에 그 판이 실제로 있어야 한다. 읽기가 프롬프트 예시의 'K2611'을 지어내 개정판 거절로 끝났다(11-06 h3-15)
    grounded = not text or any(tok in text.upper() for tok in re.findall(r'[A-Z]\d{4}|(?:19|20)\d{2}', wanted)) or not re.search(r'\d', wanted)
    if wanted and grounded and EDITION.search(wanted) and not any(ok and code in wanted for code, ok in (facts.get('revisions') or {}).items()):
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


def judge_agent(state: dict, *, specs, find, retriever) -> dict:
    """그래프 노드: 코퍼스 밖 요구면 거절 사유로 보고하고, 아니면 빠진 값을 한 번 묻고 사양 표 값으로 후보를 판정한다(찾기면 거르고 판정하고 줄 세운다)."""
    rules = C.load()
    read = JudgeRead.model_validate(state['judge_read'])
    # [왜] 코퍼스 밖 요구(사양 표에 없는 성질 · TSC 아닌 제조사 · 확인 안 된 개정판)는 규칙 · 조건을 만들기 전에 거절한다.
    #      묻거나 판정하면 그 요구와 상관없는 판정 답이 나간다(11-06 동결 평가: 비관련 35건 중 8~10건)
    if refused := outside_corpus(read, state.get('facts') or {}, ' '.join([state.get('conditions', ''), state.get('question', '')])):
        reason, why = refused
        return {'path': ['판정'], 'reports': (state.get('reports') or []) + [_report('fail', f'cannot judge from the corpus: {why}', reason=reason)]}
    part = state.get('target_part') or {}
    # [왜] 숫자 확인은 질문 · 사용 조건 · 대상 주변 회로 글로만 한다. 역할 목록(rules)의 알아보는 법 글에 있는 숫자는 사용자가 준 값이 아니다(AC-02)
    text = '\n'.join([state.get('conditions', ''), state.get('question', ''), render_read(state, {})])
    roles = [r for r in (read.role, read.role_alt) if r and r != 'other']
    base = {'roles': roles, 'role_evidence': read.role_evidence, 'results': [], 'shown': [], 'unverified': [], 'terms': [],
            'capped': False, 'dropped': [], 'asked': []}
    if not roles:
        return {'judgement': {**base, 'kind': 'no_rule'}, 'path': ['판정'],
                'reports': (state.get('reports') or []) + [_report('partial', 'role outside the 23 roles: no judging rule')]}
    kinds = {k: v for r in roles for k, v in C.inputs(rules[r]).items()}
    values, conds, dropped = to_inputs(read, text, kinds)
    asked = list(dict.fromkeys(n for r in roles for n in C.needed(rules[r], set(values) | set(conds))))
    if asked or len(roles) > 1:
        # [주의] 인터럽트는 문항당 한 번이다(AC-08). 재개하면 이 노드가 처음부터 다시 돌지만, 읽기는 앞 노드에 남아 있어 LLM을 다시 부르지 않는다
        # [주의] 재개 값은 {'answers': {...}, 'role': ...} 모양이다. 빈 dict({})로 재개하면 LangGraph가 재개로 보지 않고 다시 멈춘다(11-06 실측)
        reply = interrupt({'missing': asked, 'role_choices': roles if len(roles) > 1 else [], 'question': _ask_text(asked, roles, rules)}) or {}
        values, conds = merge_reply(reply.get('answers') or {}, values, conds, kinds)
        if reply.get('role') in roles:
            roles = [reply['role']]
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
    extra = C.user_conditions([(_tolerance_words(_rated_words(_ground_ops(w, text), text), code, text), code) for code, w in spec_words.items()] + limits)
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
    read = read.model_copy(update={'original_part': _original_from_text(read, text)})
    # [왜] 카드에서 판정 값을 읽는 specs(lab 3단계, backend/rag/card_specs.py)는 읽을 코드를 알면 덜 읽는다. 사양 표 specs에는 prefetch가 없다
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
            prefetch([_part(read.original_part), _part(read.original_part).split(' ')[0]], need)
        original_rows = [] if original_not_tsc(read.original_part, text) else _rows(specs, read.original_part)  # 후보 조회와 같은 규칙(제조사 이름 · 주문 코드)
        if state.get('question_type') == 'candidate_find' and not original_rows and extra:
            # [왜] 원래 부품 문서가 아예 없는데(제조사 미상 1N5231) 사용자가 구매 규격을 숫자로 줬으면, 원래 값과 비교하는 역할 조건은
            #      모든 후보를 '확인 안 됨'으로 만들 뿐이다. 그 조건은 빼고 구매 규격과 회로 값 조건으로 찾는다(11-06 h3-13)
            rules = {r: {**rule, 'conditions': [c for c in rule['conditions'] if 'any' in c or not any(C.orig_codes(b) for b in C._bases(c))]}
                     for r, rule in rules.items()}
        footprint = part.get('footprint')
        if state.get('question_type') == 'candidate_find':
            terms = V.search_conditions(rules[roles[0]], values)
            # [왜] 원래 부품의 패키지 · 분류를 주면 도구가 그 순서로 모두 줄 세운 뒤 50개에서 자른다(B3, 정운 11-06)
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
                    for f in [*find(terms, category, pkg, 50, **near), *(find(terms, category, pkg, 50) if any(near.values()) else [])]:
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
            # [왜] 찾기는 대체 후보를 찾는 일이다. 원래 부품(같은 기본 품번)이 '동일품'으로 끼면 사용자 요구(양방향 등)를 어겨도 동일품이 나왔다(h3-15)
            orig_base = _part(read.original_part).split(' ')[0].upper()
            candidates = [(f['part'], f.get('category', ''), f.get('packages', [])) for f in found if not orig_base or f['part'].upper() != orig_base]
            if mount:
                candidates = [c for c in candidates if mount in mount_of(c[2])]  # 요구한 실장 방식의 패키지가 있는 후보만
        else:
            terms, found = [], []
            candidates = [(p, '', None) for p in read.candidates]
        results = []
        if prefetch and candidates:
            # 후보들을 문서별로 묶어 한 번에 읽어 둔다(후보마다 차례로 읽으면 LLM 호출이 후보 수만큼 이어진다)
            prefetch([n for c in candidates for n in (_part(c[0]), _part(c[0]).split(' ')[0])], need)
        for name, category, packages in candidates:
            rows = _rows(specs, name)
            packages = packages if packages is not None else [x['text'] for x in rows if x['code'] == 'PACKAGE' and x.get('text')]
            category = category or next((x['category'] for x in rows if x.get('category')), '')  # 판정 질문은 행의 분류로
            same, same_cite = _identical(retriever, read.original_part, name)
            judged = [_schottky_exempt(V.judge_part(rules[r], r, name, values, conds, rows,
                                                    original_rows=original_rows or None, identical=same, identical_citation=same_cite,
                                                    footprint=footprint, packages=packages), category) for r in roles]
            worst = max(judged, key=lambda j: V.ORDER.index(j.verdict))  # 역할이 둘이면 더 나쁜 판정(EC-02)
            results.append(_extra_checks(worst, read, category, rows, roles, text))
    except RetrievalUnavailableError as error:
        return {'judgement': {**base, 'kind': 'judge'}, 'path': ['판정'],
                'reports': (state.get('reports') or []) + [_report('fail', f'spec table tool failed: {error.kind}', reason=Reason.SEARCH_ERROR)]}
    shown, unverified = V.rank(results) if state.get('question_type') == 'candidate_find' else (results, [])
    judgement = {**base, 'kind': 'find' if state.get('question_type') == 'candidate_find' else 'judge', 'roles': roles,
                 'results': [j.model_dump(mode='json') for j in results], 'shown': [j.model_dump(mode='json') for j in shown],
                 'unverified': [j.model_dump(mode='json') for j in unverified], 'terms': terms, 'capped': len(found) >= 50,
                 'dropped': dropped, 'asked': asked}
    missing = sorted({m for j in results for m in j.missing})
    status = 'ok' if results else 'partial'
    summary = f'{len(results)} candidates judged' + (f', {len(shown)} shown' if judgement['kind'] == 'find' else '')
    return {'judgement': judgement, 'path': ['판정'], 'reports': (state.get('reports') or []) + [_report(status, summary, missing)]}


def judge_task_node(state: dict, *, specs, find, retriever) -> dict:
    """멀티 하위 그래프 노드: 판정 노드(`judge_agent`)를 그대로 돌리고, 그 보고를 할 일 보고서(`TaskReport`)로 바꾼다."""
    # [왜] 판정 코드는 단일 그래프(D4 v2)와 같이 쓴다. 멀티만의 칸(할 일 번호 · 판정 결과)은 여기서 붙인다
    out = judge_agent(state, specs=specs, find=find, retriever=retriever)
    r, judgement = out['reports'][-1], out.get('judgement') or {}
    summary, reason = r['summary'], r.get('reason')
    if judgement.get('kind') == 'find':
        # [왜] 재계획이 요약만 읽고 찾은 품번을 다음 할 일(그 품번 문서 검색)에 쓸 수 있게 상위 후보 품번을 요약에 넣는다(설계 v2)
        names = [p.get('part') for p in judgement.get('shown') or [] if p.get('part')][:8]
        summary = f"{summary}: {', '.join(names)}" if names else summary
    if r['status'] == 'partial' and not judgement.get('results') and not reason:
        reason = Reason.NO_RESULT.value  # 후보를 하나도 못 찾았다: 조건을 바꿔 다시 찾을 수 있는 실패다
    report = TaskReport(task=state['task']['id'], agent='judge', status=r['status'], summary=summary[:200], reason=reason,
                        missing=r.get('missing') or [], judgement=judgement, llm_calls=1, round=state.get('round') or 1)
    return {'reports': [report.model_dump(mode='json')], 'path': out['path']}
