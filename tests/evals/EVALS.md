# evals

## 역할
- 이 폴더: 평가 체계(동결 감시, 그래프 평가 실행, Skill 쌍 비교)의 회귀 테스트를 둡니다.
- 넣는 것: 평가셋 동결·평가 실행기·Skill 쌍 실행을 API 없이 확인하는 `test_*.py`.
- 넣지 않는 것: 평가셋과 평가 실행기 자체(`evals/`), 평가 결과 파일(`evals/results/`), 그래프 노드 시험(`tests/graph/`).
- 담당: 평가

실행: `uv run pytest -q tests/evals`(저장소 루트).

## 파일
- `EVALS.md` — 이 문서
- `test_frozen_evals.py` — `evals/FROZEN.json`에 기록된 파일의 해시가 바뀌지 않았는지 확인. `FROZEN.json`이 없으면 검사하지 않고 통과합니다
- `test_retrieval_d3.py` — D3 검색 측정 실행기: gold 줄의 모든 쪽 풀기(이어 적은 쪽·범위), 쪽 적중·회수율·모든 근거·회수 가능만·중복 제거 nDCG, 실패 유형 4종, 정확 부호 검정, no_result 임계값을 가짜 카드로 확인(데이터·API 없이)
- `test_run_graph.py` — 그래프 평가 실행: 최종 메모장에서 경로·검색 횟수·카드 수·인용 검사 점수를 뽑는지, 거절이면 점수를 빼는지 확인(Langfuse·LLM 없이)
- `test_score_answer.py` — 답변·거절 5지표 채점기: 데이터시트·회로 근거 인용, 다른 쪽·허위 인용 오답 처리, `n01` `relevant + NOT_VERIFIED` 조건 부족 설명 대 단순 거절 구분, 비관련 4종 거절 대 환각 위험, v1 50건·v2 70건 분모·제외 처리 확인(API·DB 없이)
- `test_skill_pair.py` — Skill 쌍 순차 실행의 경로·검색 상한, 사본 격리·실행 순서 교차, 예외 시 부분 결과·덮어쓰기 금지, 평가 호출·예약비용 상한을 API 없이 확인
