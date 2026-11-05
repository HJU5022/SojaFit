# judge

## 역할
- 이 폴더: 회로 속 부품의 역할을 정하고, 역할에서 대체 조건을 도출하고, 후보 부품을 판정하는 결정적 코드를 둡니다. 숫자 비교와 단위 비교는 이 폴더에서만 합니다.
- 넣는 것: 회로 역할 규칙, 대체 조건 도출, 판정 5종을 내는 코드와 그 규칙 파일.
- 넣지 않는 것: LLM 호출(`backend/services/llm.py`), 검색(`backend/rag/`), 그래프 조립(`backend/graph/`), 단위 환산 함수(`backend/rag/`에서 만들고 여기서는 읽기만), 도메인 판단 지침 문서(`backend/mcp_skill/skills/SKILL.md`).
- 담당: 에이전트. 규칙 파일은 관련 평가 문항의 정답을 정한 사람이 아닌 다른 조원이 교차 검토합니다.

## 판정 5종
동일품 / 사양 동등 / 역할상 충분 / 불충족 / 문서로 확인 안 됨. 판정마다 근거로 쓴 데이터시트의 쪽·표·행을 붙입니다. 상세는 SPEC 3절입니다.

## 아직 정하지 않은 것
규칙 파일 형식은 SPEC 5절 · `docs/specs/judge-agent.md`를 따릅니다. 넷리스트 주변은 `backend/graph/nodes.py` `circuit_around`, 역할은 판정 읽기 LLM이 정하므로 `netlist.py` · `roles.py` · `rules/conditions.yaml`은 두지 않습니다.

## 파일
- `JUDGE.md` — 이 폴더 설명
- `__init__.py` — 패키지 표시(빈 파일)
- `conditions.py` — 역할 규칙(`rules/roles.yaml`) 읽기 · 모양 검사, 정해진 문법의 기준식으로 대체 조건 기준값 계산, 물어볼 회로 값 목록
- `sheet_conditions.py` — 데이터시트 시험 조건 글(기호 = 값, 펄스 폭 · 파형, 표 제목 기본 조건)을 읽고 같은 조건인지 비교
- `rules/` — 판정 규칙 파일 자리. 형식은 SPEC 5절에서 정하며 지금은 `.gitkeep`뿐입니다
- 예정: `verdict.py`(판정 5종), `rules/roles.yaml`. 만들면 `SOJAFIT.md` 트리의 `(예정)`을 지웁니다
