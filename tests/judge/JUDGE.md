# judge

## 역할
- 이 폴더: 판정 코드(`backend/judge/`)의 회귀 테스트를 둡니다. 판정 5종의 순서 규칙, 단위 비교, 규칙 파일 읽기를 지킵니다(SPEC 3절, 8.2·8.3 AC).
- 넣는 것: `test_judge_<모듈>.py`. LLM·DB·네트워크 없이 도는 결정적 시험.
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 검색 시험(`tests/rag/`), 단위 테스트용 가공 회로(`tests/fixtures/`).
- 담당: 에이전트

## 파일
- `test_judge_conditions.py` — 기준식 문법(사칙 연산 · kV · kI · orig.<코드>), 빠진 값, 규칙 모양 검사, 물어볼 값 목록
- `test_judge_sheet_conditions.py` — 사양 표의 실제 조건 글로 읽기 · 비교
