"""README 3절의 mermaid 그림이 코드가 조립한 그래프와 같은지 본다.

- 역할: `build_graph`로 만든 그래프의 `get_graph(xray=True).draw_mermaid()` 글(하위 그래프 펼침)을 아래 `normalize`로 고친 것이
  README.md의 첫 ```mermaid 블록과 글자 하나까지 같아야 한다. 노드나 간선을 바꾸고 README를 안 고치면 실패한다.
- 하지 않는 일: GitHub에서 그려지는지는 보지 않는다. 실제 LLM · 검색 · DB 호출 없음.
- 출처: backend/multi_agent/build.py, README.md 3절
- 다시 만들기: `PYTHONPATH=. python tests/multi_agent/test_readme_graph.py` (저장소 루트)가 블록을 출력한다.
"""
import re
from pathlib import Path

from tests.multi_agent.test_build import judge_app, scripted

README = Path(__file__).resolve().parents[2] / 'README.md'


def normalize(raw: str) -> str:
    """LangGraph 원문에서 GitHub가 못 읽는 두 곳과 노드 글자색만 고친다. 노드 이름 · 라벨 · 간선 방향은 그대로다.
    1) 한국어 노드 id가 `\\c785\\b825\\20`처럼 CSS 이스케이프로 나온다. 풀어서 글자가 아닌 문자(공백 · `·` · `:`)를 `_`로 바꾼 id를 쓴다. 화면에 보이는 라벨은 그대로다.
    2) 조건 간선 라벨 ` -. &nbsp;글&nbsp; .-> `(괄호 · `·`가 있다)를 ` -.->|"&nbsp;글&nbsp;"| `로 바꿔 따옴표로 감싼다.
    3) `classDef default` · `last`에 `color:#1f2328`을 붙인다(다크 모드에서 글자가 보이게)."""
    # shortcut: 이스케이프 바로 뒤에 16진수 글자(a-f 0-9)가 붙는 id는 잘못 읽는다. 지금 노드 이름에는 없고, 생기면 아래 비교가 실패해 드러난다
    ident = re.compile(r'(?:\\[0-9a-f]{1,6}|[A-Za-z0-9_])+')
    decode = lambda m: re.sub(r'\W', '_', re.sub(r'\\([0-9a-f]{1,6})', lambda e: chr(int(e[1], 16)), m[0])) if '\\' in m[0] else m[0]
    text = re.sub(r' -\. (&nbsp;.*?&nbsp;) \.-> ', r' -.->|"\1"| ', ident.sub(decode, raw))
    # [왜] GitHub 다크 모드는 글자를 밝게 그려 밝은 노드 바탕에서 안 보인다. 바탕을 칠한 노드(default · last)의 글자색을 고정한다
    return re.sub(r'(classDef (?:default|last) fill:\S+)', r'\1,color:#1f2328', text)


def graph_mermaid() -> str:
    return normalize(judge_app(scripted()).get_graph(xray=True).draw_mermaid()).strip()


def test_readme_mermaid_is_the_graph_the_code_builds():
    blocks = re.findall(r'```mermaid\n(.*?)```', README.read_text(encoding='utf-8'), re.S)
    assert blocks, 'README.md에 ```mermaid 블록이 없다'
    assert blocks[0].strip() == graph_mermaid(), 'README의 mermaid 블록이 코드의 그래프와 다르다. `PYTHONPATH=. python tests/multi_agent/test_readme_graph.py`로 다시 만들어 README 3절 블록을 바꾼다'


if __name__ == '__main__':
    print(graph_mermaid())
