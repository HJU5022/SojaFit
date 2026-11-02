# judge

## 역할
- 이 폴더: 회로 속 부품의 역할을 정하고, 역할에서 대체 조건을 도출하고, 후보 부품을 판정하는 결정적 코드를 둡니다. 숫자 비교와 단위 비교는 이 폴더에서만 합니다.
- 넣는 것: 넷리스트 읽기(`netlist.py`), 회로 역할(`roles.py`), 대체 조건(`conditions.py`), 판정(`verdict.py`), 규칙 파일(`rules/roles.yaml`, `rules/conditions.yaml`).
- 넣지 않는 것: LLM 호출(`backend/services/llm.py`), 검색(`backend/rag/`), 그래프 조립(`backend/graph/`), 단위 환산 함수(`backend/rag/`에서 만들고 여기서는 읽기만).
- 담당: 에이전트. 규칙 파일은 관련 평가 문항의 정답을 정한 사람이 아닌 다른 조원이 교차 검토합니다.

## 판정 5종
동일품 / 사양 동등 / 역할상 충분 / 불충족 / 문서로 확인 안 됨. 판정마다 근거로 쓴 데이터시트의 쪽·표·행을 붙입니다.

## 파일
- `JUDGE.md` — 이 폴더 설명
