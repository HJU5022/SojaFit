"""줄기 그래프의 노드들. 노드는 상태(메모장)를 받아 자기가 바꾼 칸만 dict로 돌려준다.

- 하는 일: SPEC 2절 노드 표의 일을 노드 함수 하나씩으로 한다. 지금은 입력 읽기만 있다.
- 하지 않는 일: 노드를 잇는 갈림길과 조립(`build.py`), 숫자 비교 판정(`backend/judge/`), LLM 직접 호출(`backend/services/llm.py`만 쓴다).
- 출처: SPEC.md 2절 "그래프", 강의 2주 20강(노드는 State를 받아 바뀐 부분만 돌려준다).
"""
import json
from pathlib import Path

from backend.graph.state import AgentState

REPO = Path(__file__).resolve().parents[2]  # 저장소 루트. 입력의 넷리스트 경로는 여기서부터의 상대 경로다

# 입력 글의 "키: 값" 줄 → 메모장 칸 이름
FIELDS = {"회로": "circuit", "넷리스트": "netlist_path", "대상": "target", "사용 조건": "conditions", "질문": "question"}
MAX_NET_NODES = 8      # [왜] GND·VCC처럼 부품이 많이 붙은 넷은 앞 8개만 보여 준다. 다 넣으면 근거가 길어져 핵심이 묻힌다
MAX_PASS_THROUGH_PINS = 3  # [왜] 핀이 3개 이하인 부품(저항·퓨즈·스위치·다이오드)만 건너가 다음 넷을 본다. IC·커넥터는 넷이 많아 건너가지 않는다


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
