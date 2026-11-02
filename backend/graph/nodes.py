"""줄기 그래프의 노드들. 노드는 상태(메모장)를 받아 자기가 바꾼 칸만 dict로 돌려준다.

- 하는 일: SPEC 2절 노드 표의 일을 노드 함수 하나씩으로 한다. 지금은 입력 읽기, 라우팅, 검색, 채점이 있다.
- 하지 않는 일: 노드를 잇는 갈림길과 조립(`build.py`), 숫자 비교 판정(`backend/judge/`), LLM 직접 호출(`backend/services/llm.py`만 쓴다).
- 출처: SPEC.md 2절 "그래프", 강의 2주 20강(노드는 State를 받아 바뀐 부분만 돌려준다).
"""
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.graph.state import AgentState
from backend.services import llm

REPO = Path(__file__).resolve().parents[2]  # 저장소 루트. 입력의 넷리스트 경로는 여기서부터의 상대 경로다
PROMPTS = REPO / "backend" / "prompts"     # 프롬프트 파일 폴더(버전 기록은 같은 폴더 README.md)

# 입력 글의 "키: 값" 줄 → 메모장 칸 이름
FIELDS = {"회로": "circuit", "넷리스트": "netlist_path", "대상": "target", "사용 조건": "conditions", "질문": "question"}
MAX_NET_NODES = 8      # [왜] GND·VCC처럼 부품이 많이 붙은 넷은 앞 8개만 보여 준다. 다 넣으면 근거가 길어져 핵심이 묻힌다
MAX_PASS_THROUGH_PINS = 3  # [왜] 핀이 3개 이하인 부품(저항·퓨즈·스위치·다이오드)만 건너가 다음 넷을 본다. IC·커넥터는 넷이 많아 건너가지 않는다
WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]*[A-Za-z0-9]|[A-Za-z0-9]")  # 영문·숫자 낱말. 품번 안의 . - 는 살린다(SMBJ5.0A, AMS1117-3.3)
QUANTITY = re.compile(r"\d+(\.\d+)?[A-Za-z]{1,3}")  # 값과 단위(3.6V, 500mA, 100pF). 코퍼스 품번 9,589개 중 이 모양은 0개(11-02 실측)
REVISION = re.compile(r"[A-Za-z]\d{4}")              # 개정 코드(K2611, G1804). 코퍼스 품번 중 이 모양은 0개(11-02 실측)
LABEL = re.compile(r"^\[[^\]]*\] ")                    # 표 한 줄 카드 앞의 [파일 · 쪽 · 표 제목] 이름표. 파일 이름의 품번을 줄의 품번으로 보지 않게 뗀다


def parse_input(text: str) -> dict:
    """입력 글을 회로·넷리스트·대상·사용 조건·질문 칸으로 나눈다. 칸 형식이 아니면 글 전체를 질문으로 본다."""
    found = {}
    for line in text.splitlines():
        key, sep, value = line.partition(":")  # 첫 ":" 앞이 키, 뒤가 값이다
        if sep and key.strip() in FIELDS:
            found[FIELDS[key.strip()]] = value.strip()
    if "question" not in found:
        found["question"] = text.strip()  # 자유 입력: 넷리스트 없이 질문만 온 경우
    return found


def _connections_file(netlist_path: str) -> Path | None:
    """넷리스트 옆(또는 한 단계 위)의 connections.json을 찾는다."""
    netlist = REPO / netlist_path
    # [왜] samples는 넷리스트와 같은 폴더에, 받은 회로(c09)는 한 단계 위 폴더에 connections.json이 있다
    for folder in (netlist.parent, netlist.parent.parent):
        if (folder / "connections.json").exists():
            return folder / "connections.json"
    return None


def circuit_around(connections: dict, target: str) -> dict:
    """대상 부품과, 그 부품에 붙은 작은 부품 너머의 넷까지(2단계) 모아 돌려준다.

    예: D1 → 이웃 S1·F1 → S1 너머 J1.PWR, F1 너머 RAW. 그래서 J1 → S1 → D1 → F1 → RAW 전원 경로가 보인다.
    대상이 넷리스트에 없으면 빈 dict를 돌려준다.
    """
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
        value = parts.get(node["ref"], {}).get("value", "")
        return f"{node['ref']}.{node.get('pinfunction') or node['pin']}({value})"

    nets = []
    for name in names:
        nodes = net_by_name[name]["nodes"]
        nets.append({"name": name, "nodes": [show(n) for n in nodes[:MAX_NET_NODES]],
                     "more": max(0, len(nodes) - MAX_NET_NODES)})
    target_part = parts[target]
    return {"ref": target, "value": target_part.get("value", ""), "footprint": target_part.get("footprint", ""), "nets": nets}


def read_input(state: AgentState) -> dict:
    """입력 읽기 노드: 입력 글을 칸으로 나누고 넷리스트에서 대상 부품 주변을 읽는다. LLM을 쓰지 않는다(SPEC 2절)."""
    fields = parse_input(state["input"])
    target_part = {}
    if fields.get("netlist_path") and fields.get("target"):
        found = _connections_file(fields["netlist_path"])
        if found:
            target_part = circuit_around(json.loads(found.read_text(encoding="utf-8")), fields["target"])
    return {**fields, "target_part": target_part, "path": ["입력 읽기"]}


class Route(BaseModel):
    """라우팅 노드가 LLM에게 받는 답안지(강의 2주 20강의 Route와 같은 역할)."""
    question_type: Literal["out_of_scope", "role", "candidate_find", "candidate_judge", "rating"] = Field(
        description="질문 종류. backend/prompts/route.md의 순서대로 처음 맞는 것")


def route(state: AgentState) -> dict:
    """라우팅 노드: 질문 종류를 다섯 가지 중 하나로 정한다(SPEC 2절). 어디로 갈지는 build.py의 갈림길이 정한다."""
    # [왜] 질문만 주면 "D1은 무슨 역할이야"처럼 대상이 빠진 질문을 놓칠 수 있어 대상 기호와 값을 같이 준다
    part = state.get("target_part") or {}
    user = f"대상: {state.get('target', '')} {part.get('value', '')}\n질문: {state['question']}"
    answer = llm.chat((PROMPTS / "route.md").read_text(encoding="utf-8"), user, Route)
    return {"question_type": answer.question_type, "path": ["라우팅"]}


def find_parts(text: str, refs: set[str]) -> list[str]:
    """글에서 품번으로 보이는 낱말(영문과 숫자가 섞인 것)을 나온 순서대로 뽑는다. 회로 기호·값·개정 코드는 뺀다."""
    found = []
    for word in WORD.findall(text):  # [왜] 영문·숫자만 이어 붙여 "1N5819는"의 조사 "는"이 떨어진다
        if not (re.search(r"[A-Za-z]", word) and re.search(r"\d", word)):
            continue  # TSC, USB(숫자 없음)와 2026(영문 없음)은 품번이 아니다
        if word in refs or QUANTITY.fullmatch(word) or REVISION.fullmatch(word):
            continue
        found.append(word)
    # [주의] 코퍼스에 없는 품번(1N4001, BAT85)도 남긴다. 그래야 retrieve가 []를 돌려 "문서로 확인 안 됨"으로 간다
    return list(dict.fromkeys(found))  # 같은 품번이 두 번 나와도 한 번만


def search(state: AgentState, retriever) -> dict:
    """검색 노드: 검색어로 카드를 찾되, 질문에 품번이 있으면 그 품번 문서 안에서만, 없으면 대상 값의 품번 문서 안에서만 찾는다(SPEC 2절).

    retriever는 backend.rag.retrieve.retrieve와 같은 모양(question, *, parts)이다. build.py가 넣어 주고, 시험에서는 가짜를 넣는다.
    """
    part = state.get("target_part") or {}
    # shortcut: 회로 기호는 대상과 그 주변 넷의 부품만 안다. 멀리 있는 기호(U3, SJ1)는 품번으로 잘못 뽑힌다. 실측에서 틀리면 넷리스트 전체 기호로 넓힌다
    refs = {part.get("ref", "")} | {node.split(".")[0] for net in part.get("nets", []) for node in net["nodes"]}
    # [왜] 질문 품번과 대상 값 품번을 합치면 "D3 후보 1N60P 정격"(코퍼스에 없음)에 D3 값 1N4148 문서가 나와 엉뚱한 수치로 답한다(11-02 결정)
    parts = find_parts(state["question"], refs) or find_parts(part.get("value", ""), refs)
    query = state.get("query") or state["question"]  # 재작성 노드가 검색어를 바꿨으면 그것으로, 아니면 질문으로 찾는다
    docs = retriever(query, parts=parts or None)  # 품번이 하나도 없으면 None: 코퍼스 전체에서 찾는다
    return {"query": query, "parts": parts, "docs": docs, "tries": 1, "path": ["검색"]}  # tries 1이 더해져 상한 판단에 쓰인다


class Grade(BaseModel):
    """채점 노드가 LLM에게 받는 답안지(강의 2주 20강의 채점기와 같은 역할)."""
    passed_ids: list[int] = Field(description="질문에 답할 근거가 든 카드 번호. 없으면 빈 목록")


def other_part_row(doc: dict, parts: list[str]) -> bool:
    """표 한 줄 카드가 같은 문서의 다른 품번만 적힌 줄이면 True. 예: 1N5819를 물었는데 1N5817 순방향 전압 줄."""
    if not doc.get("table") or not parts:
        return False  # 글 카드("FEATURES" 등)는 문서 전체 이야기라 거르지 않는다. 물은 품번이 없으면 비교할 것이 없다
    # [왜] 문서 표지 품번 목록과 겹치는 낱말만 품번으로 본다. 그래야 패키지 이름(DO-41, SOD-123F)이 든 줄을 버리지 않는다
    named = {w.lower() for w in find_parts(LABEL.sub("", doc["content"]), set())} & set(doc.get("doc_parts", []))
    return bool(named) and not named & {p.lower() for p in parts}


def grade(state: AgentState) -> dict:
    """채점 노드: 결정적 검사(다른 품번 줄, 요청한 개정판)로 먼저 거르고, 남은 카드를 LLM 호출 한 번으로 채점한다(SPEC 2절)."""
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
        return {"passed": [], "path": ["채점"]}  # 남은 카드가 없으면 LLM을 부르지 않는다
    cards = "\n\n".join(f"[{d['chunk_id']}] {d['file']} · {d['page']}쪽\n{d['content']}" for d in kept)
    # [왜] 강의 20강처럼 하위 검색어가 아니라 원래 질문 기준으로 채점한다
    answer = llm.chat((PROMPTS / "grade.md").read_text(encoding="utf-8"), f"질문: {state['question']}\n\n카드:\n{cards}", Grade)
    shown = {d["chunk_id"] for d in kept}
    return {"passed": [i for i in answer.passed_ids if i in shown], "path": ["채점"]}  # LLM이 없는 번호를 내면 버린다
