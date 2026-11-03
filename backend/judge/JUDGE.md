# judge

## 역할
- 이 폴더: 회로 속 부품의 역할을 정하고, 역할에서 대체 조건을 도출하고, 후보 부품을 판정하는 결정적 코드를 둡니다. 숫자 비교와 단위 비교는 이 폴더에서만 합니다. 지금은 비어 있습니다(이 설명 파일뿐, 코드 없음).
- 넣는 것: 회로 역할 규칙, 대체 조건 도출, 판정 5종을 내는 코드와 그 규칙 파일.
- 넣지 않는 것: LLM 호출(`backend/services/llm.py`), 검색(`backend/rag/`), 그래프 조립(`backend/graph/`), 단위 환산 함수(`backend/rag/`에서 만들고 여기서는 읽기만), 도메인 판단 지침 문서(`backend/mcp_skill/skills/SKILL.md`).
- 담당: 에이전트. 규칙 파일은 관련 평가 문항의 정답을 정한 사람이 아닌 다른 조원이 교차 검토합니다.

## 판정 5종
동일품 / 사양 동등 / 역할상 충분 / 불충족 / 문서로 확인 안 됨. 판정마다 근거로 쓴 데이터시트의 쪽·표·행을 붙입니다. 상세는 SPEC 3절입니다.

## 아직 정하지 않은 것
SPEC은 이 폴더의 파일 이름을 정하지 않았습니다. 규칙 파일 형식도 SPEC 5절에서 "(정할 것)"입니다. 이전 설명에 있던 `netlist.py`, `roles.py`, `conditions.py`, `verdict.py`, `rules/*.yaml`은 계획 후보일 뿐 어디에서도 요구하지 않고 없습니다. 파일을 만들 때 SPEC과 SOJAFIT.md 트리를 먼저 정합니다.

## 파일
- `JUDGE.md` — 이 폴더 설명
- `rules/` — 판정 규칙 파일 자리. 형식은 SPEC 5절에서 정하며 지금은 `.gitkeep`뿐입니다
- 예정(후보 이름, SPEC이 정하면 바꿈): `netlist.py`(넷리스트 주변 읽기), `roles.py`(회로 역할), `conditions.py`(대체 조건), `verdict.py`(판정 5종), `rules/roles.yaml`·`rules/conditions.yaml`. 만들면 `SOJAFIT.md` 트리의 `(예정)`을 지웁니다
