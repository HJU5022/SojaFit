# judge

## 역할
- 이 폴더: 판정 코드(`backend/judge/`)의 회귀 테스트. 판정 5종의 순서 규칙, 단위 비교, 규칙 파일 읽기를 지킨다(SPEC.md 3절, 8.2·8.3).
- 넣는 것: `test_judge_<모듈>.py`. LLM·DB·네트워크 없이 도는 결정적 시험.
- 넣지 않는 것: 그래프 노드 시험(`tests/graph/`), 검색 시험(`tests/rag/`), 단위 테스트용 가공 회로(`tests/fixtures/`).
- 담당: 에이전트

## 파일
| 파일 | 확인하는 것 |
|---|---|
| `JUDGE.md` | 이 문서 |
| `test_judge_conditions.py` | 기준식 문법(사칙 연산, kV, kI, `orig.<코드>`), 빠진 값, 규칙 모양 검사(slot 포함), 물어볼 값 목록 |
| `test_judge_rules_file.py` | 실제 규칙 파일 `backend/judge/rules/roles.yaml`의 모든 역할이 읽히고 문법에 맞는지, R04 제너의 VZ 범위(`vz_min`·`vz_max`) 판정과 범위가 없을 때 최대 VZ 비교 |
| `test_judge_sheet_conditions.py` | 사양 표의 실제 조건 글과 카드 읽기가 쓴 조건 글('IZT = 20 mA', '@ rated VR; TJ = 25°C', 'IPP = 27.0 A')을 읽고 시험 조건으로 행 고르기 |
| `test_judge_verdict.py` | 작은 규칙·가짜 사양 표 행으로 판정 5종 순서, 찾기 검색 조건, 후보 정렬(선호 후보는 같은 판정·기판 수정 여부 안에서만 앞으로), slot 칸 읽기, `orig.VZ` 최대, 표 제목에 조건 없는 VZ 행의 TA=25°C, 숫자 unless |
