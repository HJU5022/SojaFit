"""줄기 그래프의 노드들. 노드는 상태(메모장)를 받아 자기가 바꾼 칸만 dict로 돌려준다.

- 역할: SPEC 2절 노드 표의 일을 노드 함수 하나씩으로 한다(입력 읽기, 라우팅, 짧은 답, 가격 안내, 검색, 채점, 재작성, 생성, 거절, 판정, 답 틀 11개).
  가격 안내(`price_answer`)는 멀티 그래프도 그대로 쓴다.
  사실 확인(`multi_agent/facts.py`)과 판정 읽기(`multi_agent/agents/judge.py`)는 멀티 그래프의 노드를 그대로 쓴다(build.py가 붙인다).
  `build.py`가 노드를 그래프에 붙이고, `evals/runners/run_skill_pair.py`는 `generate`를 직접 부르며, `evals/runners/run_graph.py`는 그래프 전체를 돌린다.
  입력은 `AgentState`(`state.py`), 출력은 바뀐 칸만 담은 dict. 프롬프트는 `backend/prompts/*.md`에서 읽는다.
- 하지 않는 일: 노드를 잇는 갈림길과 조립(`build.py`), 숫자 비교 판정(`backend/judge/`, 판정 노드는 멀티 대체 부품 에이전트를 부르기만 한다),
  LLM 직접 호출(`backend/services/llm.py`의 `node_chat`만 쓴다), Mouser 가격 · 재고 조회(그래프 밖 `/api/prices`, ADR 0009).
- 출처: SPEC.md 2절 "그래프"(노드 표), SPEC.md 3절(판정 이름), ADR 0006, 강의 2주 20강(노드는 State를 받아 바뀐 부분만 돌려준다),
  backend/multi_agent/contracts.py(질문 종류 · 거절 사유 코드), backend/multi_agent/messages.py(거절 문구 · 판정 답 틀).
"""
import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from backend.graph.mcp_retriever import RetrievalUnavailableError
from backend.graph.state import AgentState
from backend.graph.memory import memory_context, memory_sources
from backend.multi_agent.contracts import QuestionType, Reason
from backend.multi_agent.messages import price_message, refusal_for, render_judgement
from backend.multi_agent.supervisor import Facts, render_facts
from backend.services import llm

REPO = Path(__file__).resolve().parents[2]  # 저장소 루트. 입력의 넷리스트 경로는 여기서부터의 상대 경로다
PROMPTS = REPO / "backend" / "prompts"     # 프롬프트 파일 폴더(버전 기록은 같은 폴더 PROMPTS.md)
SKILL = REPO / "backend" / "mcp_skill" / "skills" / "SKILL.md"

# 입력 글의 "키: 값" 줄 → 메모장 칸 이름
FIELDS = {"회로": "circuit", "넷리스트": "netlist_path", "대상": "target", "사용 조건": "conditions", "질문": "question"}
MAX_NET_NODES = 8      # [왜] GND·VCC처럼 부품이 많이 붙은 넷은 앞 8개만 보여 준다. 다 넣으면 근거가 길어져 핵심이 묻힌다
MAX_PASS_THROUGH_PINS = 3  # [왜] 핀이 3개 이하인 부품(저항·퓨즈·스위치·다이오드)만 건너가 다음 넷을 본다. IC·커넥터는 넷이 많아 건너가지 않는다
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]*[A-Za-z0-9]|[A-Za-z0-9]")  # 영문·숫자 낱말. 품번 안의 . - 는 살린다(SMBJ5.0A, AMS1117-3.3)
QUANTITY = re.compile(r"\d+(\.\d+)?[A-Za-z]{1,3}")  # 값과 단위(3.6V, 500mA, 100pF). 코퍼스 품번 9,589개 중 이 모양은 0개(11-02 실측)
REVISION = re.compile(r"[A-Za-z]\d{4}")              # 개정 코드(K2611, G1804). 코퍼스 품번 중 이 모양은 0개(11-02 실측)
LABEL = re.compile(r"^\[[^\]]*\] ")                    # 표 한 줄 청크 앞의 [파일 · 쪽 · 표 제목] 이름표. 파일 이름의 품번을 줄의 품번으로 보지 않게 뗀다
CITE = re.compile(r"\[([^\]]*)\]")                     # 답 속 인용 괄호: [12] · [12, 15] · [넷리스트]
NOT_FOUND = "문서로 확인 안 됨"                          # 근거로 답할 수 없을 때의 답(SPEC 3절 판정 이름과 같다)
CLUES = "부품 윗면 글자, 사진, 데이터시트, 주문 코드"        # 근거가 없을 때 사용자에게 묻는 단서(SPEC 2절 "근거가 없을 때" 3번)


def parse_input(text: str) -> dict:
    """입력 글을 회로·넷리스트·대상·사용 조건·질문 칸으로 나눈다(question은 항상 있다)."""
    found = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")  # 첫 ":" 앞이 키, 뒤가 값이다
        if sep and key.strip() in FIELDS:
            found[FIELDS[key.strip()]] = value.strip()
    if "question" not in found:
        found["question"] = text.strip()  # 자유 입력: 넷리스트 없이 질문만 온 경우
    return found


def _connections_file(netlist_path: str) -> Path | None:
    """넷리스트 옆(또는 한 단계 위)의 connections.json 경로를 돌려준다. 없거나 경로가 저장소 밖이면 None."""
    # [주의] 사용자 입력이 파일 읽기로 가는 경계다. 절대 경로나 ../로 저장소 밖을 읽지 못하게 resolve 뒤 REPO 안인지 검사한다
    root = REPO.resolve()
    netlist = (REPO / netlist_path).resolve()
    if not netlist.is_relative_to(root):
        return None
    # [왜] samples는 넷리스트와 같은 폴더에, 받은 회로(c09)는 한 단계 위 폴더에 connections.json이 있다
    for folder in (netlist.parent, netlist.parent.parent):
        if folder.is_relative_to(root) and (folder / "connections.json").exists():
            return folder / "connections.json"
    return None


def circuit_around(connections: dict, target: str) -> dict:
    """대상 부품과, 그 부품에 붙은 작은 부품 너머의 넷까지(2단계) 모아 {ref, value, footprint, nets} dict로 돌려준다."""
    # 예: D1 → 이웃 S1·F1 → S1 너머 J1.PWR, F1 너머 RAW. 그래서 J1 → S1 → D1 → F1 → RAW 전원 경로가 보인다
    # [주의] 대상이 넷리스트에 없으면 빈 dict를 돌려준다. 받는 쪽은 비었는지 먼저 본다
    parts = {c["ref"]: c for c in connections["components"]}
    if target not in parts:
        return {}
    nets_of = {}  # 부품 기호 → 그 부품이 붙은 넷 이름 목록
    for net in connections["nets"]:
        for node in net["nodes"]:
            nets_of.setdefault(node["ref"], []).append(net["name"])
    net_by_name = {net["name"]: net for net in connections["nets"]}

    # 1단계: 대상이 붙은 넷. 2단계: 그 넷의 이웃 부품 중 핀이 적은 부품이 붙은 다른 넷
    names = list(dict.fromkeys(nets_of.get(target, [])))
    neighbors = {n["ref"] for name in names for n in net_by_name[name]["nodes"]} - {target}
    for ref in sorted(neighbors):
        if len(nets_of.get(ref, [])) <= MAX_PASS_THROUGH_PINS:
            names += [name for name in nets_of[ref] if name not in names]

    def show(node):
        """넷 속 핀 하나를 "기호.핀(값)" 글자로 만든다."""
        value = parts.get(node["ref"], {}).get("value", "")
        return f"{node['ref']}.{node.get('pinfunction') or node['pin']}({value})"

    nets = []
    for name in names:
        nodes = net_by_name[name]["nodes"]
        # [왜] 큰 넷(GND · VCC)은 앞 MAX_NET_NODES개만 보이는데, 대상 자신의 핀이 잘리면 역할을 못 읽는다(AC-10). 대상 핀을 앞에 둔다
        mine = [n for n in nodes if n["ref"] == target]
        shown = (mine + [n for n in nodes if n["ref"] != target])[:MAX_NET_NODES]
        nets.append({"name": name, "nodes": [show(n) for n in shown], "more": max(0, len(nodes) - MAX_NET_NODES)})
    target_part = parts[target]
    return {"ref": target, "value": target_part.get("value", ""), "footprint": target_part.get("footprint", ""), "nets": nets}


def read_input(state: AgentState) -> dict:
    """입력 읽기 노드: 입력 글을 칸으로 나누고 넷리스트에서 대상 부품 주변을 읽는다. LLM을 쓰지 않는다(SPEC 2절).

    입력: `input` 칸. 출력: 나눈 칸, `target_part`, 앞 턴 검색 칸을 비우는 값, `path`. 턴마다 비우는 이유는 아래 [왜] 참고.
    """
    uploaded = state.get('connections')
    fields = ({'circuit': state['circuit'], 'target': state['target'], 'conditions': state.get('conditions', ''),
               'question': state['input']} if uploaded else parse_input(state["input"]))
    target_part = {}
    if uploaded:
        target_part = circuit_around(uploaded, fields['target'])
    elif fields.get("netlist_path") and fields.get("target"):
        found = _connections_file(fields["netlist_path"])
        if found:
            target_part = circuit_around(json.loads(found.read_text(encoding="utf-8")), fields["target"])
    # [왜] 같은 thread의 다음 메시지(체크포인터)에서 앞 질문의 검색 결과가 새 질문에 섞이지 않게 턴마다 비운다.
    # 안 비우면 낡은 query로 검색하고, 낡은 passed·docs로 역할 질문에 답하고, 낡은 tries 때문에 재작성 없이 거절한다.
    # [주의] tries는 더하기 칸(operator.add)이라 0을 덮어쓸 수 없다. 지금 값의 음수를 돌려줘야 합쳐서 0이 된다.
    reset = {"query": "", "parts": [], "docs": [], "passed": [], "retrieval_error": None,
             "tries": -state.get("tries", 0),
             # 사실 · 거절 코드 · 판정 칸: 앞 질문의 것으로 새 질문을 거절하거나 답하지 않게 한다(멀티 parse_node와 같은 이유)
             "facts": {}, "refusal": {}, "judge_read": {}, "judgement": {},
             "price_parts": []}  # 앞 질문의 가격 안내 품번이 새 답에 붙지 않게 한다
    # [주의] 뒤에 오는 dict가 앞을 덮는다. 입력에서 나눈 칸이 reset 값보다 앞서야 해서 reset을 먼저 펼친다
    return {**reset, **fields, "target_part": target_part, "path": ["입력 읽기"]}  # path는 쌓는 칸이라 이름만 돌려주면 이어 붙는다


# 라우팅이 검색 전에 정할 수 있는 거절 사유. 한도 · 검증 · 검색 장애는 그 뒤 단계에서만 생긴다
FirstStageReason = Literal[Reason.OUT_OF_SCOPE, Reason.PART_MISSING, Reason.REVISION_MISSING, Reason.NOT_FOUND]
REFUSED_TYPES = {"out_of_scope": Reason.OUT_OF_SCOPE, "other_part": Reason.NOT_FOUND}  # 종류만으로 거절이 정해지는 질문(멀티 Supervisor 규칙과 같음)


class Route(BaseModel):
    """라우팅 노드가 LLM에게 받는 답안지(강의 2주 20강의 Route와 같은 역할). 질문 종류는 멀티 Supervisor와 같은 8가지다."""
    # Literal로 정한 값만 허용한다. LLM이 다른 글자를 내면 pydantic 검사에서 걸러진다(structured output)
    question_type: QuestionType = Field(description="질문 종류. backend/prompts/route.md의 순서대로 처음 맞는 것")
    reason: FirstStageReason | None = Field(default=None, description="검색 전에 거절할 때만 거절 사유. 거절하지 않으면 비운다")
    reply: str = Field(default="", max_length=300, description="일상 대화(chat)일 때 사용자에게 보여 줄 한국어 답")

    @model_validator(mode="after")
    def refusal_reason_and_reply(self):
        if self.reason is None and self.question_type in REFUSED_TYPES:
            # [왜] 범위 밖 · 다른 부품은 종류만으로 사유가 정해진다. 비워 왔다고 형식 재시도(유료)로 다시 부르지 않고 채운다
            self.reason = REFUSED_TYPES[self.question_type]
        if self.question_type == "chat" and not self.reply.strip():
            raise ValueError("일상 대화에는 reply가 필요하다")  # [왜] 짧은 답 노드는 LLM을 다시 부르지 않고 이 reply를 답으로 쓴다
        return self


def route(state: AgentState) -> dict:
    """라우팅 노드: 질문 종류(8가지)와 검색 전 거절 사유 · 일상 대화 답을 정한다(SPEC 2절). 어디로 갈지는 build.py의 갈림길이 정한다."""
    # [왜] 질문만 주면 "D1은 무슨 역할이야"처럼 대상이 빠진 질문을 놓칠 수 있어 대상 기호와 값을 같이 준다
    part = state.get("target_part") or {}
    # [왜] 사실 확인 결과를 멀티 Supervisor와 같은 글(render_facts)로 붙여, 코퍼스에 없는 품번 · 개정판을 검색 전에 거절하게 한다
    facts = render_facts(Facts(**(state.get("facts") or {})))
    user = "\n".join([f"대상: {state.get('target', '')} {part.get('value', '')}", f"질문: {state['question']}", *facts])
    answer = llm.node_chat("route", (PROMPTS / "route.md").read_text(encoding="utf-8"), user, Route)
    # 바뀐 칸만 돌려준다: 나머지 칸은 그대로 남는다. route 칸은 갈림길 · 거절 · 짧은 답 노드가 읽는다
    return {"question_type": answer.question_type, "route": answer.model_dump(mode="json"), "path": ["라우팅"]}


def short_reply(state: AgentState) -> dict:
    """짧은 답 노드: 일상 대화는 라우팅이 낸 reply를 그대로 답으로 쓴다. LLM을 더 부르지 않는다(멀티 Supervisor의 끝내기와 같음)."""
    # [왜] check · skill도 덮어쓴다. 같은 thread 앞 턴의 인용 검사 · Skill 적용 정보가 이 답의 것으로 보이면 안 된다
    return {"answer": state["route"]["reply"], "check": {}, "skill": {"enabled": False, "applied": False, "sha256": None},
            "path": ["짧은 답"]}


# 품번이 아닌 규격 · 인증 이름(AEC-Q101, IEC61000, J-STD-020, ISO7637, UL94, JESD201). [왜] 'AEC-Q101'을 코퍼스에 없는 품번으로 셌다(11-06 v3-14)
STANDARD = re.compile(r'(AEC-?Q\d+|IEC-?\d+(-\d+)*|J-?STD-?\d+|ISO-?\d+|UL-?\d+|JESD-?\d+)', re.I)


def find_parts(text: str, refs: set[str]) -> list[str]:
    """글에서 품번으로 보이는 낱말(영문+숫자)을 나온 순서대로 중복 없이 뽑는다. refs(회로 기호)·값·개정 코드는 뺀다."""
    found = []
    for word in WORD.findall(text):  # [왜] 영문·숫자만 이어 붙여 "1N5819는"의 조사 "는"이 떨어진다
        if not (re.search(r"[A-Za-z]", word) and re.search(r"\d", word)):
            continue  # TSC, USB(숫자 없음)와 2026(영문 없음)은 품번이 아니다
        if word in refs or QUANTITY.fullmatch(word) or REVISION.fullmatch(word) or STANDARD.fullmatch(word):
            continue
        found.append(word)
    # [주의] 코퍼스에 없는 품번(1N4001, BAT85)도 남긴다. 그래야 retrieve가 []를 돌려 "문서로 확인 안 됨"으로 간다
    return list(dict.fromkeys(found))  # 같은 품번이 두 번 나와도 한 번만


def price_answer(state: AgentState) -> dict:
    """가격 안내 노드: 가격 · 재고를 물은 품번만 `price_parts`에 남기고 정해진 안내로 끝낸다. LLM · Mouser를 부르지 않는다(SPEC 2절).

    [왜] Mouser 값은 그래프 상태 · 체크포인트 · Langfuse 트레이스에 남으면 안 된다(ADR 0009). 값은 화면이 그래프 밖 `/api/prices`로
    볼 때마다 조회한다. 멀티 그래프도 이 노드를 그대로 붙인다(D4 · D5가 같은 답을 내게).
    """
    part = state.get("target_part") or {}
    refs = {part.get("ref", "")} | {node.split(".")[0] for net in part.get("nets", []) for node in net["nodes"]}  # 검색 노드와 같은 회로 기호
    # 검색 노드와 같은 규칙: 질문 속 품번, 없으면 대상 값의 품번("D1 가격 얼마야" → D1 값의 품번)
    parts = find_parts(state["question"], refs) or find_parts(part.get("value", ""), refs)
    # [왜] check · skill도 비운다(짧은 답과 같은 이유). 멀티 메모장에는 skill 칸이 없어 LangGraph가 그 칸을 버린다
    return {"price_parts": parts, "answer": price_message(parts), "check": {},
            "skill": {"enabled": False, "applied": False, "sha256": None}, "path": ["가격 안내"]}


def search(state: AgentState, retriever) -> dict:
    """검색 노드: 질문에 품번이 있으면 그 품번 문서 안에서만, 없으면 대상 값의 품번 문서 안에서만 청크를 찾는다(SPEC 2절)."""
    # retriever는 backend.rag.retrieve.retrieve와 같은 모양(question, *, parts)이다. build.py가 넣어 주고, 시험에서는 가짜를 넣는다
    part = state.get("target_part") or {}
    # shortcut: 회로 기호는 대상과 그 주변 넷의 부품만 안다. 멀리 있는 기호(U3, SJ1)는 품번으로 잘못 뽑힌다. 실측에서 틀리면 넷리스트 전체 기호로 넓힌다
    refs = {part.get("ref", "")} | {node.split(".")[0] for net in part.get("nets", []) for node in net["nodes"]}
    # [왜] 질문 품번과 대상 값 품번을 합치면 "D3 후보 1N60P 정격"(코퍼스에 없음)에 D3 값 1N4148 문서가 나와 엉뚱한 수치로 답한다(11-02 결정)
    parts = find_parts(state["question"], refs) or find_parts(part.get("value", ""), refs)
    query = state.get("query") or state["question"]  # 재작성 노드가 검색어를 바꿨으면 그것으로, 아니면 질문으로 찾는다
    try:
        docs = retriever(query, parts=parts or None)  # 품번이 하나도 없으면 None: 코퍼스 전체에서 찾는다
    except RetrievalUnavailableError as error:
        return {"query": query, "parts": parts, "docs": [],
                "retrieval_error": {"kind": error.kind}, "tries": 1, "path": ["검색"]}
    return {"query": query, "parts": parts, "docs": docs,
            "retrieval_error": None, "tries": 1, "path": ["검색"]}  # tries 1이 더해져 상한 판단에 쓰인다


class Grade(BaseModel):
    """채점 노드가 LLM에게 받는 답안지(강의 2주 20강의 채점기와 같은 역할)."""
    passed_ids: list[int] = Field(description="질문에 답할 근거가 든 카드 번호. 없으면 빈 목록")


def other_part_row(doc: dict, parts: list[str]) -> bool:
    """표 한 줄 청크가 같은 문서의 다른 품번만 적힌 줄이면 True(예: 1N5819를 물었는데 1N5817 순방향 전압 줄)."""
    if not doc.get("table") or not parts:
        return False  # 글 청크("FEATURES" 등)는 문서 전체 이야기라 거르지 않는다. 물은 품번이 없으면 비교할 것이 없다
    if doc["content"].split("] ", 1)[0].endswith("주석"):
        # [왜] 표 주석 카드(청킹 v4부터 따로 된 카드)는 표 한 줄이 아니다. 'C or CA suffix for types SMAJ5.0 - Types SMAJ188'처럼
        #      계열 범위 품번을 적어 다른 품번 줄로 버려지면 양방향 품번 규칙 근거가 사라졌다(v3-19, 11-09)
        return False
    # [왜] 문서 표지 품번 목록과 겹치는 낱말만 품번으로 본다. 그래야 패키지 이름(DO-41, SOD-123F)이 든 줄을 버리지 않는다
    # [주의] 청킹 v3가 행 끝에 붙인 표 주석('\n주: … 2.4V (BZV55B2V4) to 75V (BZV55B75)')의 예시 품번은 그 행의 품번이 아니라 보지 않는다(11-06 v3-18)
    body = LABEL.sub("", doc["content"]).split("\n주: ", 1)[0]
    named = {w.lower() for w in find_parts(body, set())} & set(doc.get("doc_parts", []))
    # [왜] TSC TVS는 양방향 품번(C · CA)이 단방향 행(… · …A)의 값을 쓴다('Electrical characteristics apply in both directions'). SMAJ6.5CA를 물으면 SMAJ6.5A 행이 근거다(v3-19)
    # [왜] H 품번(AEC-Q101)도 값 표에는 기본 품번으로 적힌다('"H" means AEC-Q101 qualified'). SMAJ6.5CAH → SMAJ6.5CA · SMAJ6.5A
    bases = {p.lower() for p in parts} | {p.lower()[:-1] for p in parts if p.lower().endswith("h")}
    asked = bases | {re.sub(r"c(a?)$", r"\1", p) for p in bases}
    order = re.search(r'\bORDERING CODE(?:\(\d+\))*\s*:\s*([^|\n]+)', body, re.I)
    if order and re.search(r'''["']x["']\s+defines\b''', doc['content'], re.I):
        # Only a documented numeric wildcard expands; retain suffixes so G never matches GH.
        codes = [w.lower() for w in WORD.findall(order.group(1)) if re.search(r'\dx', w, re.I)]
        if codes:
            return not any(re.fullmatch(re.sub(r'(?<=\d)x+', lambda m: r'\d+', re.escape(code)), p)
                           for code in codes for p in asked)
    return bool(named) and not named & asked


def grade(state: AgentState) -> dict:
    """채점 노드: 결정적 검사(다른 품번 줄, 요청한 개정판)로 먼저 거르고, 남은 청크를 LLM 호출 한 번으로 채점한다(SPEC 2절).

    입력: question·docs·parts. 출력: 통과한 청크 id(chunk_id) 목록 `passed`. 빈 목록이면 build.py 갈림길이 재작성이나 거절로 보낸다.
    """
    revisions = {w.upper() for w in WORD.findall(state["question"]) if REVISION.fullmatch(w)}  # 질문이 요청한 개정 코드
    kept = []
    for doc in state.get("docs", []):
        if other_part_row(doc, state.get("parts") or []):
            continue
        # 파일 이름 끝이 개정 코드다: "1N4148 SERIES_K2301.pdf" → K2301
        if revisions and doc["file"].rsplit("_", 1)[-1].removesuffix(".pdf").upper() not in revisions:
            continue
        kept.append(doc)
    if not kept:
        return {"passed": [], "path": ["채점"]}  # 남은 청크가 없으면 LLM을 부르지 않는다
    cards = "\n\n".join(f"[{d['chunk_id']}] {d['file']} · {d['page']}쪽\n{d['content']}" for d in kept)
    # [왜] 강의 20강처럼 하위 검색어가 아니라 원래 질문 기준으로 채점한다
    answer = llm.node_chat("grade", (PROMPTS / "grade.md").read_text(encoding="utf-8"), f"질문: {state['question']}\n\n카드:\n{cards}", Grade)
    shown = {d["chunk_id"] for d in kept}
    # [주의] LLM이 보여 준 적 없는 번호를 내면 버린다. 안 버리면 없는 청크가 근거로 통과한다
    return {"passed": [i for i in answer.passed_ids if i in shown], "path": ["채점"]}


class Rewrite(BaseModel):
    """재작성 노드가 LLM에게 받는 답안지."""
    query: str = Field(description="데이터시트 검색어 한 줄")


def rewrite(state: AgentState) -> dict:
    """재작성 노드: 원래 질문을 데이터시트 검색어 한 줄로 바꾼다(SPEC 2절). 품번 필터는 바꾸지 않는다."""
    # [주의] 품번 필터는 검색 노드가 원래 질문에서 다시 뽑는다. 여기서 바꾸는 것은 query 칸뿐이다
    # [왜] 1차 검색어가 아니라 언제나 원래 질문을 고친다(강의 2주 20강). 고친 것을 또 고치면 뜻이 점점 멀어진다
    # [왜] 키워드 검색(BM25)은 한국어 낱말을 버린다. 영어 용어로 바꿔야 "순방향 전압"이 Forward voltage 줄에 걸린다
    answer = llm.node_chat("rewrite", (PROMPTS / "rewrite.md").read_text(encoding="utf-8"), state["question"], Rewrite)
    return {"query": answer.query.strip(), "path": ["재작성"]}  # query 칸을 새 검색어로 덮어쓴다


class Answer(BaseModel):
    """생성 노드가 LLM에게 받는 답안지."""
    answer: str = Field(description="문장마다 근거 번호를 붙인 답. 근거로 답할 수 없으면 '문서로 확인 안 됨'")
    memory_refs: list[str] = Field(default_factory=list, max_length=5, description='Historical source IDs consulted, separate from answer evidence')


def netlist_block(part: dict) -> str:
    """대상 부품과 주변 넷을 생성 노드의 근거 한 덩어리([넷리스트])로 쓴다."""
    # [주의] part는 read_input이 만든 target_part이고 비어 있으면 안 된다(part["nets"]를 바로 읽는다)
    nets = "\n".join(f"- {n['name']}: {', '.join(n['nodes'])}" + (f" 외 {n['more']}개" if n["more"] else "") for n in part["nets"])
    return f"[넷리스트] {part['ref']} {part['value']} ({part['footprint']})\n{nets}"


def citations(text: str) -> set[str]:
    """글에서 인용한 근거 번호를 모은다. [0.60 V]처럼 번호가 아닌 괄호는 인용으로 보지 않는다."""
    # [왜] 괄호 안을 먼저 꺼내 쉼표로 나눈다. [12]만 찾으면 [12, 15]처럼 한 괄호에 묶은 인용을 놓친다(강의 2주 20강)
    return {c.strip() for br in CITE.findall(text) for c in br.split(",")
            if c.strip().isdigit() or c.strip() == "넷리스트" or c.strip().startswith('승인사례:')}


def generate(state: AgentState, *, use_skill: bool = False) -> dict:
    """생성 노드: 통과 청크와 넷리스트만으로 답하고, 없는 근거 인용과 인용 없는 문장을 센다(SPEC 2절).

    입력: question·docs·passed·target_part. use_skill이 True면 도메인 Skill을 시스템 프롬프트에 붙인다.
    출력: answer, check, skill(적용 여부와 sha256), path.
    주의: use_skill인데 Skill 파일이 없으면 FileNotFoundError, 비었으면 ValueError를 그대로 올린다(실패를 숨기지 않는다).
    """
    passed = set(state.get("passed") or [])
    cards = [d for d in state.get("docs", []) if d["chunk_id"] in passed]  # 채점을 통과한 청크만 근거로 넘긴다
    blocks = [f"[{d['chunk_id']}] {d['file']} · {d['page']}쪽\n{d['content']}" for d in cards]  # 파일 이름에 개정 코드가 있어 출처가 된다
    part = state.get("target_part") or {}
    if part:
        blocks.append(netlist_block(part))  # [왜] 역할 질문은 검색 없이 오므로 넷리스트가 유일한 근거다
    skill_info = {"enabled": use_skill, "applied": False, "sha256": None}
    answer = NOT_FOUND  # 근거가 하나도 없으면(넷리스트 없이 온 역할 질문) LLM을 부르지 않는다
    memory_refs = []
    if blocks:
        system = (PROMPTS / "generate.md").read_text(encoding="utf-8")
        text = ""
        if use_skill:
            raw = SKILL.read_bytes()
            text = raw.decode("utf-8")
            if not text.strip():
                raise ValueError("도메인 Skill이 비어 있습니다")
            system += f"\n\n<domain_skill>\n{text}\n</domain_skill>"
            skill_info = {"enabled": True, "applied": True, "sha256": hashlib.sha256(raw).hexdigest()}
        user = "근거:\n" + "\n\n".join(blocks) + f"\n\n질문: {state['question']}"  # 강의 20강처럼 근거 다음에 질문
        user += memory_context(state.get('approved_memories') or [])
        response = llm.node_chat("generate", system, user, Answer, skill_text=text)
        answer, memory_refs = response.answer.strip(), response.memory_refs
    valid = {str(d["chunk_id"]) for d in cards} | ({"넷리스트"} if part else set())  # 실제로 넘긴 근거. 이 밖의 번호를 인용하면 없는 근거 인용이다
    if (any(c.startswith('승인사례:') for c in citations(answer)) or
            set(memory_refs) - memory_sources(state.get('approved_memories') or [])):
        answer, memory_refs = NOT_FOUND, []
    cited = citations(answer)
    # 마침표 뒤 공백에서 문장을 자른다. "문서로 확인 안 됨"은 인용할 근거가 없는 답이라 세지 않는다
    sentences = [] if answer == NOT_FOUND else [s for s in re.split(r"(?<=[.。])\s+", answer) if s.strip()]
    check = {"fake_citations": sorted(cited - valid),                          # 넘긴 적 없는 근거 번호
             "uncited_sentences": sum(1 for s in sentences if not citations(s)),  # 근거 번호가 하나도 없는 문장 수
             "used": sorted(cited & valid)}                                    # 넘긴 근거 중 실제로 인용한 번호
    # shortcut: 검사에 걸려도 기록만 하고 답은 그대로 낸다(강의 2주 20강, 11-02 조장 결정). 실측으로 걸리는 비율을 본 뒤 다시 쓰기나 거절로 보낼지 정한다
    return {"answer": answer, "memory_refs": list(dict.fromkeys(memory_refs)), "check": check, "skill": skill_info, "path": ["생성"]}


def judge(state: AgentState, *, specs, find, retriever) -> dict:
    """판정 노드: 멀티 대체 부품 에이전트의 판정 노드(`judge_agent`)를 그대로 부른다(빠진 값 인터럽트 1번, 숫자 비교는 `backend/judge/`).

    입력: judge_read · question_type · conditions · target_part · facts. 출력: judgement, path(사양 표 도구 장애면 retrieval_error,
    코퍼스 밖 요구면 refusal 코드도).
    주의: 단일 메모장에는 보고서 칸이 없어 `reports`는 버린다. 보고서의 거절 사유는 칸으로 옮겨 거절로 보낸다.
    """
    from backend.multi_agent.agents.judge import judge_agent  # [왜] 판정 길을 이을 때만 판정 규칙 · 프롬프트를 읽는다
    out = judge_agent(state, specs=specs, find=find, retriever=retriever)
    reason = out.pop("reports")[-1].get("reason")
    if reason == Reason.SEARCH_ERROR.value:
        out["retrieval_error"] = {"kind": "spec_table"}
    elif reason:
        out["refusal"] = {"code": reason}  # 코퍼스 밖 요구(SPEC 8.3). 거절 노드가 이 코드로 멀티와 같은 문구를 만든다
    return out


def judgement_answer(state: AgentState) -> dict:
    """답 틀 노드: 판정 결과를 코드 틀(`render_judgement`)로 답 글로 만든다. LLM이 숫자 · 인용을 다시 쓰지 않는다(AGENTS 7번, 멀티 작성과 같음)."""
    return {"answer": render_judgement(state["judgement"]), "check": {"used": [], "judgement": True},
            "skill": {"enabled": False, "applied": False, "sha256": None}, "path": ["답 틀"]}


def refuse(state: AgentState) -> dict:
    """거절 노드: 이유 코드(`refusal`)와 안내문, 다음 할 일(단서 요청)을 답으로 남기고 끝낸다. LLM을 쓰지 않는다(SPEC 2절).

    이유 코드는 멀티 그래프와 같은 `contracts.Reason` 값이다: 라우팅이 정한 사유(out_of_scope · part_missing · revision_missing ·
    not_found), 판정이 코퍼스 밖 요구로 정한 사유(part_missing · revision_missing · not_found), 검색 장애(search_error),
    검색 고리에서 못 찾음(not_found). 평가 실행기가 이 코드로 거절 종류를 센다.
    """
    skill_info = {"enabled": False, "applied": False, "sha256": None}  # 이전 턴의 Skill 적용 정보도 비운다
    # 라우팅이 첫 단에서 정한 사유, 없으면 판정이 코퍼스 밖 요구로 정한 사유(SPEC 8.3)
    reason = (state.get("route") or {}).get("reason") or (state.get("refusal") or {}).get("code")
    if reason:
        # 검색 없이 거절한다. [왜] 문구는 멀티 거절과 같은 함수로 만든다(D4 · D5를 같은 문구로 비교)
        answer = refusal_for(Reason(reason), state.get("facts") or {})
    elif state.get("retrieval_error"):
        reason = Reason.SEARCH_ERROR.value
        answer = "검색 도구를 사용할 수 없어 문서 근거를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요."
    else:
        reason = Reason.NOT_FOUND.value  # [왜] 없는 품번은 사실 확인에서 걸러지므로, 검색 고리의 거절은 '찾지 못함'(추정)이다
        docs, parts = state.get("docs") or [], state.get("parts") or []
        # [왜] 근거 없음을 둘로 나눠 보여 준다. 품번 문서가 아예 없는 것과, 문서는 있는데 답이 없는 것은 사용자가 줄 단서가 다르다
        if not docs:
            found = f"{', '.join(parts)} 데이터시트를 찾지 못했습니다" if parts else "질문에 맞는 데이터시트를 찾지 못했습니다"
        else:
            files = ", ".join(sorted({d["file"] for d in docs}))  # SPEC 3절: 찾아본 문서를 보여 준다
            found = f"찾아본 문서({files})에서 질문에 답할 근거를 찾지 못했습니다(검색 {state.get('tries', 0)}번)"
        # 대화는 끊지 않는다. 사용자가 단서를 주면 같은 thread의 다음 메시지로 다시 찾는다(SPEC 2절, ADR 0006)
        answer = f"{NOT_FOUND}: {found}. 단서({CLUES})를 알려 주시면 다시 찾겠습니다."
    return {"answer": answer, "check": {}, "skill": skill_info, "refusal": {"code": reason, "message": answer}, "path": ["거절"]}
