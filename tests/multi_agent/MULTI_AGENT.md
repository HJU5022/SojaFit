# multi_agent

## 역할
- 이 폴더: 멀티 에이전트(`backend/multi_agent/`)의 회귀 테스트를 둡니다. 소스 폴더와 같은 이름으로 짝을 맞춥니다(`tests/graph/` ↔ `backend/graph/`와 같은 규칙).
- 넣는 것: `test_<대상>.py`. LLM과 검색기는 가짜로 바꿔 API 없이 돌립니다.
- 넣지 않는 것: 단일 그래프 시험(`tests/graph/`), 평가 실행기와 동결 감시(`tests/evals/`), 판정 코드 시험(`tests/judge/`).
- 담당: 에이전트

실행: `uv run pytest -q tests/multi_agent`(저장소 루트).

## 파일
- `MULTI_AGENT.md` — 이 문서
- `test_contracts.py` — 결정서 · 보고서 모양 검사(목록 밖 노드 · 이유 없는 거절 거부), 이유 코드 분류, 한도 규칙(판단 8 · 검색 2 · 작성 2, 같은 사유 반복 → 못 찾음)
