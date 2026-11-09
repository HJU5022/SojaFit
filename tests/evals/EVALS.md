# evals

## 역할
- 이 폴더: 평가 체계(동결 감시, 그래프 평가 실행, Skill 쌍 비교)의 회귀 테스트를 둡니다.
- 넣는 것: 평가셋 동결·평가 실행기·Skill 쌍 실행을 API 없이 확인하는 `test_*.py`.
- 넣지 않는 것: 평가셋과 평가 실행기 자체(`evals/`), 평가 결과 파일(`evals/results/`), 그래프 노드 시험(`tests/graph/`).
- 담당: 평가

실행: `uv run pytest -q tests/evals`(저장소 루트).

## 파일
- `test_run_graph.py`의 운영 준비 검사 — run_thread_validation의 dry-run/ID·덮어쓰기 거부, 공급자 보고 비용 누락/null·본문 제외 확인
- `EVALS.md` — 이 문서
- `test_frozen_evals.py` — `evals/FROZEN.json`에 기록된 파일의 해시가 바뀌지 않았는지 확인. `FROZEN.json`이 없으면 검사하지 않고 통과합니다
- `test_retrieval_d3.py` — D3 검색 측정 실행기: gold 줄의 모든 쪽 풀기(이어 적은 쪽·범위), Page Hit·회수율·Full Recall·회수 가능만·중복 제거 nDCG, 실패 유형 4종, 정확 부호 검정, no_result 임계값을 가짜 청크로 확인(데이터·API 없이)
- `test_retrieval_service.py` — 서비스 경로 재측정 실행기: 지표 정의, R1 1위 칸과 상위 5개 대조, 백분위·상한, 파일 이름 대응, 오류 문항 건너뛰기를 가짜 retrieve로 확인(DB·API 없이)
- `test_run_graph.py` — 그래프 평가 실행: 최종 메모장에서 경로·검색 횟수·청크 수·인용 검사 점수를 뽑는지, 거절이면 점수를 빼는지, 단일 · 멀티 거절 사유 코드를 같은 이름으로 세는지, 단일 · 멀티 모두 MCP 서버를 열어 사실 확인에 쓰고 찾기 · 판정 값은 카드 도구로 잇는지(가짜 MCP · 가짜 카드 도구), 판정 인터럽트를 빈 답으로 한 번만 재개하는지 확인(Langfuse·LLM 없이)
- `test_run_judge_dev.py` — 판정 연습 문제 채점: 판정 문항의 역할 · 판정 일치, 찾기 문항의 보여 준 후보 · 판정 집합, 판정 결과가 없을 때 틀림 처리, 비율 모으기. 실제 그래프는 돌리지 않음
- `test_supervisor_models.py` — 동결 입력·schema 재시도·provider 중단·예산·집계·증거 hash를 API 호출 없이 검증
- `test_supervisor_jev.py` — Jev typed answer·gold 격리·provider 정책·예산·70-job manifest를 API 없이 검증
- `test_supervisor_stage3_report.py` — 3차 집계의 gold·형식·라우팅 분모와 완전한 3회 비교·과거 Jev 수치 재계산 검증
- `test_supervisor_prompt_v0_common.py` — V0 13건의 hash·건수 동결, 정답·id 입력 격리, 오류 행을 포함한 공통 분모와 상태 전이 표본을 API 없이 검증
- `test_supervisor_prompt_v0.py` — Luna·Haiku V0 실행기의 모델 고정, 입력 격리, 형식 재시도 상한, 오프라인 26-job plan과 live gate를 API 없이 검증
- `test_supervisor_prompt_v0_jev.py` — Jev V0의 공통 질문 계약·입력 경계·typed answer 확률 검증·의미 오류 분리·오프라인 13-job plan·live gate를 API 없이 검증
- `test_compare_supervisor_prompt_v0.py` — 세 후보 고정, dataset·의미 계약 hash, case 집합·실행 수 일치, API별 형식 지표와 Jev metadata 분리를 API 없이 검증
- `test_import_supervisor_prompt_v0_langfuse.py` — V0 Dataset payload·고정 ID·7개 결정적 점수·hash 차단·중복 영수증 차단·세 Experiment 쓰기 계약을 네트워크 없이 검증
- `test_score_answer.py` — 답변·거절 5지표 채점기: 데이터시트·회로 근거 인용, 다른 쪽·허위 인용 오답 처리, `n01` `relevant + NOT_VERIFIED` 조건 부족 설명 대 단순 거절 구분, 비관련 4종 거절 대 환각 위험, v1 50건·v2 70건 분모·제외 처리 확인(API·DB 없이)
- `test_score_compound.py` — 여러 개를 묻는 질문 부분별 채점: 부분마다 자기 규칙(답할 부분의 근거 · 판정, 답하면 안 되는 부분의 거절 말)으로 채점하는지, 열쇠 낱말로 품번 · 영문 낱말을 고르는지
- `test_gate_report.py` — 기준표 집계: verdict 칸 없는 옛 평가셋(v2)은 expected의 첫 판정 코드를 쓰는지, 문서 할 일 검색이 있으면 그것을 · 없으면 판정 표 근거 칸을 근거 위치로 쓰는지, 비율 · 오탐 · p95 기준 미달을 빠짐없이 고르는지(그래프 · LLM 없음)
- `test_embedding_grid.py` — 격자 평가 실행기의 문항 읽기(v1에서 19건)·순위·요약·카드 묶기, 격자 결과 파일 78칸의 요약을 문항별 값으로 다시 계산해 대조, 모델 표와 임베딩 기록의 일치
- `test_retrieval_layers.py` — 층별 재측정의 토큰화·nDCG·판정 규칙(순 차이 +5와 부트스트랩 구간), 층 결과 파일 요약의 재계산 일치, 나머지 측정 스크립트 문법(환경변수는 시험 뒤 되돌림)
- `test_bit_search.py` — 비트 검색의 recall·상위 5 일치 계산, 결과 파일에서 다시 계산한 recall이 문서 값(N=1,600 0.949, N=3,200 0.980)과 같음
- `test_eval_grader.py` — 충분 · 부분 · 부족 판정 규칙, 정답 쪽 유지율 · 판정 표 계산, 스냅샷 만들기(본문을 버리는지), 스냅샷 문항 만들기와 R1 수집(가짜 검색 · 채점, 연속 오류 3번 중단), v2 스냅샷이 사전 등록 #36의 숫자(15 · 12/15 · 34/35)를, R1 dev 스냅샷이 #34 결과(39 · 36/39)를 재현하는지
- `test_skill_pair.py` — Skill 쌍 순차 실행의 경로·검색 상한, 사본 격리·실행 순서 교차, 예외 시 부분 결과·덮어쓰기 금지, 평가 호출·예약비용 상한을 API 없이 확인
