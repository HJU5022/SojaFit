"""줄기 그래프의 노드들. 노드는 상태(메모장)를 받아 자기가 바꾼 칸만 dict로 돌려준다.

- 역할: SPEC 2절 노드 표의 일을 노드 함수 하나씩으로 한다(입력 읽기, 라우팅, 검색, 채점, 재작성, 생성, 거절 7개).
  `build.py`가 노드를 그래프에 붙이고, `evals/runners/run_skill_pair.py`는 `generate`를 직접 부르며, `evals/runners/run_graph.py`는 그래프 전체를 돌린다.
  입력은 `AgentState`(`state.py`), 출력은 바뀐 칸만 담은 dict. 프롬프트는 `backend/prompts/*.md`에서 읽는다.
- 하지 않는 일: 노드를 잇는 갈림길과 조립(`build.py`), 숫자 비교 판정(`backend/judge/`), LLM 직접 호출(`backend/services/llm.py`의 `node_chat`만 쓴다).
- 출처: SPEC.md 2절 "그래프"(노드 표), SPEC.md 3절(판정 이름), ADR 0006, 강의 2주 20강(노드는 State를 받아 바뀐 부분만 돌려준다).
"""
import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from backend.graph.mcp_retriever import RetrievalUnavailableError
from backend.graph.state import AgentState
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
LABEL = re.compile(r"^\[[^\]]*\] ")                    # 표 한 줄 카드 앞의 [파일 · 쪽 · 표 제목] 이름표. 파일 이름의 품번을 줄의 품번으로 보지 않게 뗀다
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
        nets.append({"name": name, "nodes": [show(n) for n in nodes[:MAX_NET_NODES]],
                     "more": max(0, len(nodes) - MAX_NET_NODES)})
    target_part = parts[target]
    return {"ref": target, "value": target_part.get("value", ""), "footprint": target_part.get("footprint", ""), "nets": nets}


def read_input(state: AgentState) -> dict:
    """입력 읽기 노드: 입력 글을 칸으로 나누고 넷리스트에서 대상 부품 주변을 읽는다. LLM을 쓰지 않는다(SPEC 2절).

    입력: `input` 칸. 출력: 나눈 칸, `target_part`, 앞 턴 검색 칸을 비우는 값, `path`. 턴마다 비우는 이유는 아래 [왜] 참고.
    """
    fields = parse_input(state["input"])
    target_part = {}
    if fields.get("netlist_path") and fields.get("target"):
        found = _connections_file(fields["netlist_path"])
        if found:
            target_part = circuit_around(json.loads(found.read_text(encoding="utf-8")), fields["target"])
    # [왜] 같은 thread의 다음 메시지(체크포인터)에서 앞 질문의 검색 결과가 새 질문에 섞이지 않게 턴마다 비운다.
    # 안 비우면 낡은 query로 검색하고, 낡은 passed·docs로 역할 질문에 답하고, 낡은 tries 때문에 재작성 없이 거절한다.
    # [주의] tries는 더하기 칸(operator.add)이라 0을 덮어쓸 수 없다. 지금 값의 음수를 돌려줘야 합쳐서 0이 된다.
    reset = {"query": "", "parts": [], "docs": [], "passed": [], "retrieval_error": None,
             "tries": -state.get("tries", 0)}
    # [주의] 뒤에 오는 dict가 앞을 덮는다. 입력에서 나눈 칸이 reset 값보다 앞서야 해서 reset을 먼저 펼친다
    return {**reset, **fields, "target_part": target_part, "path": ["입력 읽기"]}  # path는 쌓는 칸이라 이름만 돌려주면 이어 붙는다


class Route(BaseModel):
    """라우팅 노드가 LLM에게 받는 답안지(강의 2주 20강의 Route와 같은 역할)."""
    # Literal로 다섯 값만 허용한다. LLM이 다른 글자를 내면 pydantic 검사에서 걸러진다(structured output)
    question_type: Literal["out_of_scope", "role", "candidate_find", "candidate_judge", "rating"] = Field(
        description="질문 종류. backend/prompts/route.md의 순서대로 처음 맞는 것")


def route(state: AgentState) -> dict:
    """라우팅 노드: 질문 종류를 다섯 가지 중 하나로 정한다(SPEC 2절). 어디로 갈지는 build.py의 갈림길이 정한다."""
    # [왜] 질문만 주면 "D1은 무슨 역할이야"처럼 대상이 빠진 질문을 놓칠 수 있어 대상 기호와 값을 같이 준다
    part = state.get("target_part") or {}
    user = f"대상: {state.get('target', '')} {part.get('value', '')}\n질문: {state['question']}"
    answer = llm.node_chat("route", (PROMPTS / "route.md").read_text(encoding="utf-8"), user, Route)
    return {"question_type": answer.question_type, "path": ["라우팅"]}  # 바뀐 칸만 돌려준다: 나머지 칸은 그대로 남는다


def find_parts(text: str, refs: set[str]) -> list[str]:
    """글에서 품번으로 보이는 낱말(영문+숫자)을 나온 순서대로 중복 없이 뽑는다. refs(회로 기호)·값·개정 코드는 뺀다."""
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
    """검색 노드: 질문에 품번이 있으면 그 품번 문서 안에서만, 없으면 대상 값의 품번 문서 안에서만 카드를 찾는다(SPEC 2절)."""
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
    """표 한 줄 카드가 같은 문서의 다른 품번만 적힌 줄이면 True(예: 1N5819를 물었는데 1N5817 순방향 전압 줄)."""
    if not doc.get("table") or not parts:
        return False  # 글 카드("FEATURES" 등)는 문서 전체 이야기라 거르지 않는다. 물은 품번이 없으면 비교할 것이 없다
    # [왜] 문서 표지 품번 목록과 겹치는 낱말만 품번으로 본다. 그래야 패키지 이름(DO-41, SOD-123F)이 든 줄을 버리지 않는다
    named = {w.lower() for w in find_parts(LABEL.sub("", doc["content"]), set())} & set(doc.get("doc_parts", []))
    return bool(named) and not named & {p.lower() for p in parts}


def grade(state: AgentState) -> dict:
    """채점 노드: 결정적 검사(다른 품번 줄, 요청한 개정판)로 먼저 거르고, 남은 카드를 LLM 호출 한 번으로 채점한다(SPEC 2절).

    입력: question·docs·parts. 출력: 통과한 카드 id(chunk_id) 목록 `passed`. 빈 목록이면 build.py 갈림길이 재작성이나 거절로 보낸다.
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
        return {"passed": [], "path": ["채점"]}  # 남은 카드가 없으면 LLM을 부르지 않는다
    cards = "\n\n".join(f"[{d['chunk_id']}] {d['file']} · {d['page']}쪽\n{d['content']}" for d in kept)
    # [왜] 강의 20강처럼 하위 검색어가 아니라 원래 질문 기준으로 채점한다
    answer = llm.node_chat("grade", (PROMPTS / "grade.md").read_text(encoding="utf-8"), f"질문: {state['question']}\n\n카드:\n{cards}", Grade)
    shown = {d["chunk_id"] for d in kept}
    # [주의] LLM이 보여 준 적 없는 번호를 내면 버린다. 안 버리면 없는 카드가 근거로 통과한다
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


def netlist_block(part: dict) -> str:
    """대상 부품과 주변 넷을 생성 노드의 근거 한 덩어리([넷리스트])로 쓴다."""
    # [주의] part는 read_input이 만든 target_part이고 비어 있으면 안 된다(part["nets"]를 바로 읽는다)
    nets = "\n".join(f"- {n['name']}: {', '.join(n['nodes'])}" + (f" 외 {n['more']}개" if n["more"] else "") for n in part["nets"])
    return f"[넷리스트] {part['ref']} {part['value']} ({part['footprint']})\n{nets}"


def citations(text: str) -> set[str]:
    """글에서 인용한 근거 번호를 모은다. [0.60 V]처럼 번호가 아닌 괄호는 인용으로 보지 않는다."""
    # [왜] 괄호 안을 먼저 꺼내 쉼표로 나눈다. [12]만 찾으면 [12, 15]처럼 한 괄호에 묶은 인용을 놓친다(강의 2주 20강)
    return {c.strip() for br in CITE.findall(text) for c in br.split(",") if c.strip().isdigit() or c.strip() == "넷리스트"}


def generate(state: AgentState, *, use_skill: bool = False) -> dict:
    """생성 노드: 통과 카드와 넷리스트만으로 답하고, 없는 근거 인용과 인용 없는 문장을 센다(SPEC 2절).

    입력: question·docs·passed·target_part. use_skill이 True면 도메인 Skill을 시스템 프롬프트에 붙인다.
    출력: answer, check, skill(적용 여부와 sha256), path.
    주의: use_skill인데 Skill 파일이 없으면 FileNotFoundError, 비었으면 ValueError를 그대로 올린다(실패를 숨기지 않는다).
    """
    passed = set(state.get("passed") or [])
    cards = [d for d in state.get("docs", []) if d["chunk_id"] in passed]  # 채점을 통과한 카드만 근거로 넘긴다
    blocks = [f"[{d['chunk_id']}] {d['file']} · {d['page']}쪽\n{d['content']}" for d in cards]  # 파일 이름에 개정 코드가 있어 출처가 된다
    part = state.get("target_part") or {}
    if part:
        blocks.append(netlist_block(part))  # [왜] 역할 질문은 검색 없이 오므로 넷리스트가 유일한 근거다
    skill_info = {"enabled": use_skill, "applied": False, "sha256": None}
    answer = NOT_FOUND  # 근거가 하나도 없으면(넷리스트 없이 온 역할 질문) LLM을 부르지 않는다
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
        answer = llm.node_chat("generate", system, user, Answer, skill_text=text).answer.strip()
    valid = {str(d["chunk_id"]) for d in cards} | ({"넷리스트"} if part else set())  # 실제로 넘긴 근거. 이 밖의 번호를 인용하면 없는 근거 인용이다
    cited = citations(answer)
    # 마침표 뒤 공백에서 문장을 자른다. "문서로 확인 안 됨"은 인용할 근거가 없는 답이라 세지 않는다
    sentences = [] if answer == NOT_FOUND else [s for s in re.split(r"(?<=[.。])\s+", answer) if s.strip()]
    check = {"fake_citations": sorted(cited - valid),                          # 넘긴 적 없는 근거 번호
             "uncited_sentences": sum(1 for s in sentences if not citations(s)),  # 근거 번호가 하나도 없는 문장 수
             "used": sorted(cited & valid)}                                    # 넘긴 근거 중 실제로 인용한 번호
    # shortcut: 검사에 걸려도 기록만 하고 답은 그대로 낸다(강의 2주 20강, 11-02 조장 결정). 실측으로 걸리는 비율을 본 뒤 다시 쓰기나 거절로 보낼지 정한다
    return {"answer": answer, "check": check, "skill": skill_info, "path": ["생성"]}


def refuse(state: AgentState) -> dict:
    """거절 노드: 이유(범위 밖 / 근거 없음)와 다음 할 일(단서 요청)을 답으로 남기고 끝낸다. LLM을 쓰지 않는다(SPEC 2절)."""
    skill_info = {"enabled": False, "applied": False, "sha256": None}
    if state.get("question_type") == "out_of_scope":
        answer = "이 질문은 SojaFit 범위 밖입니다. SojaFit은 회로 속 다이오드의 역할·정격과 대체 후보를 TSC 데이터시트로 확인합니다."
        return {"answer": answer, "check": {}, "skill": skill_info, "path": ["거절"]}  # 이전 턴의 적용 정보도 비운다
    if state.get("retrieval_error"):
        answer = "검색 도구를 사용할 수 없어 문서 근거를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요."
        return {"answer": answer, "check": {}, "skill": skill_info, "path": ["거절"]}
    docs, parts = state.get("docs") or [], state.get("parts") or []
    # [왜] 근거 없음을 둘로 나눠 보여 준다. 품번 문서가 아예 없는 것과, 문서는 있는데 답이 없는 것은 사용자가 줄 단서가 다르다
    if not docs:
        found = f"{', '.join(parts)} 데이터시트를 찾지 못했습니다" if parts else "질문에 맞는 데이터시트를 찾지 못했습니다"
    else:
        files = ", ".join(sorted({d["file"] for d in docs}))  # SPEC 3절: 찾아본 문서를 보여 준다
        found = f"찾아본 문서({files})에서 질문에 답할 근거를 찾지 못했습니다(검색 {state.get('tries', 0)}번)"
    # 대화는 끊지 않는다. 사용자가 단서를 주면 같은 thread의 다음 메시지로 다시 찾는다(SPEC 2절, ADR 0006)
    return {"answer": f"{NOT_FOUND}: {found}. 단서({CLUES})를 알려 주시면 다시 찾겠습니다.",
            "check": {}, "skill": skill_info, "path": ["거절"]}
