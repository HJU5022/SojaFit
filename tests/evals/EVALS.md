# evals

## 역할
- 이 폴더: 평가 체계(동결 감시, 그래프 평가 실행, Skill 쌍 비교, 검색 측정, 채점기, 수퍼바이저 비교, 인젝션 기준선)의 회귀 테스트.
- 넣는 것: 평가셋 동결·평가 실행기·채점기·보고 집계를 API 없이 확인하는 `test_*.py`. 외부 모델·임베딩 공급자와 공유 DB는 호출하지 않고(소켓 차단), 유료 실행기는 계획·한도·덮어쓰기 거부·승인 없는 실행 차단을 가짜 모델로 확인한다. 가짜 모델 검사이며 실제 방어율·모델 성적을 주장하지 않는다.
- 넣지 않는 것: 평가셋과 평가 실행기 자체(`evals/`), 평가 결과 파일(`evals/results/`), 그래프 노드 시험(`tests/graph/`).
- 담당: 평가

실행: `uv run pytest -q tests/evals`(저장소 루트).

## 파일
### 동결·그래프 평가·검색 측정
| 파일 | 확인하는 것 |
|---|---|
| `EVALS.md` | 이 문서 |
| `test_frozen_evals.py` | `evals/FROZEN.json`에 기록된 파일의 해시가 바뀌지 않았는지. `FROZEN.json`이 없으면 검사하지 않고 통과 |
| `test_run_graph.py` | 그래프 평가 실행: 최종 메모장에서 점수 뽑기, 거절 시 점수 제외, 단일·멀티 거절 사유 코드, MCP 사실 확인 + 카드 도구 연결, 판정 인터럽트 한 번 재개, 스레드 검증의 dry-run·덮어쓰기 거부 |
| `test_run_judge_dev.py` | 판정 연습 문제 채점: 판정 문항의 역할·판정 일치, 찾기 문항의 보여 준 후보·판정 집합, 판정 결과가 없을 때 틀림 처리, 비율 모으기 |
| `test_skill_pair.py` | Skill 쌍 순차 실행의 경로·검색 상한, 사본 격리·실행 순서 교차, 예외 시 부분 결과·덮어쓰기 금지, 평가 호출·예약비용 상한 |
| `test_retrieval_d3.py` | D3 검색 측정 실행기: gold 줄의 쪽 풀기, Page Hit·회수율·Full Recall·nDCG, 실패 유형, 정확 부호 검정, no_result 임계값(가짜 청크) |
| `test_retrieval_service.py` | 서비스 경로 재측정 실행기: 지표 정의, 1위 칸과 상위 5개 대조, 백분위·상한, 파일 이름 대응, 오류 문항 건너뛰기(가짜 retrieve) |
| `test_retrieval_layers.py` | 층별 재측정의 토큰화·nDCG·판정 규칙, 층 결과 파일 요약의 재계산 일치, 나머지 측정 스크립트 문법 |
| `test_bit_search.py` | 비트 검색의 recall·상위 5 일치 계산, 결과 파일에서 다시 계산한 recall이 문서 값과 같음 |
| `test_embedding_grid.py` | 격자 평가 실행기의 문항 읽기·순위·요약·카드 묶기, 격자 결과 파일 요약을 문항별 값으로 다시 계산해 대조, 모델 표와 임베딩 기록의 일치 |
| `test_stage_timing.py` | 단계 시간 기록기: LLM 호출마다 노드 이름·토큰·보고 비용·캐시 토큰, Voyage 호출 종류별 기록, 집계의 p50·p95 정의, 오류 행 대체, `run_gate.main`의 trace별 점수·실행 조건·점수 전송 장애 시 결과 보존(가짜 클라이언트) |
| `test_approval_wait_report.py` | 승인 대기 보고: 합성 이벤트로 재개·승인 대기를 서버 시간과 떼어 계산하고 짧은 자동 호출을 사람 대기에서 뺌, 대화 id 미출력, 일회용 DB(`TEST_THREAD_DATABASE_URL`)에서 읽기 전용 연결 |

### 채점기·기준표
| 파일 | 확인하는 것 |
|---|---|
| `test_score_answer.py` | 답변·거절 5지표 채점기: 데이터시트·회로 근거 인용, 다른 쪽·허위 인용 오답 처리, 조건 부족 설명 대 단순 거절 구분, 비관련 거절 대 환각 위험, v1·v2 분모·제외 처리 |
| `test_score_compound.py` | 여러 개를 묻는 질문의 부분별 채점: 부분마다 자기 규칙(답할 부분의 근거·판정, 답하면 안 되는 부분의 거절 말)으로 채점, 열쇠 낱말로 품번·영문 낱말 고르기 |
| `test_score_ragas.py` | RAGAS 채점 실행기: 근거 모으기, 질문 줄 고르기, 비활성/재료 부족 시 빈 결과 |
| `test_eval_grader.py` | 채점기 기준선 계산: 충분·부분·부족 판정 규칙, 정답 쪽 유지율·판정 표, 스냅샷 만들기(본문을 버림), 스냅샷 문항 만들기와 수집(가짜 검색·채점, 연속 오류 3번 중단), 스냅샷이 사전 등록 숫자를 재현하는지 |
| `test_gate_report.py` | 기준표 집계: verdict 칸 없는 옛 평가셋은 expected의 첫 판정 코드를 씀, 근거 위치 고르기, 비율·오탐·p95 기준 미달 찾기 |
| `test_import_human_review.py` | 사람 채점 시트 변환: O/X/보류 파싱, 미채점 건너뜀, `human_review` 채움, 일치율, 원본 덮어쓰기 거부. 합성 시트만 사용 |

### 수퍼바이저 후보 비교 (Supervisor Prompt V0 포함)
| 파일 | 확인하는 것 |
|---|---|
| `test_supervisor_models.py` | 후보 비교 실행기: 동결 입력, schema 재시도, provider 중단, 예산, 집계, 증거 hash |
| `test_supervisor_jev.py` | Jev 평가기: typed answer, gold 격리, provider 정책, 예산, 작업 manifest |
| `test_supervisor_stage3_report.py` | 3차 집계의 gold·형식·라우팅 분모와 3회 비교, 과거 Jev 수치 재계산 |
| `test_supervisor_prompt_v0_common.py` | V0 평가셋의 hash·건수 동결, 정답·id 입력 격리, 오류 행을 포함한 공통 분모와 상태 전이 표본 |
| `test_supervisor_prompt_v0.py` | Luna·Haiku V0 실행기의 모델 고정, 입력 격리, 형식 재시도 상한, 오프라인 plan과 live gate |
| `test_supervisor_prompt_v0_jev.py` | Jev V0의 공통 질문 계약·입력 경계·typed answer 확률 검증·오프라인 plan·live gate |
| `test_compare_supervisor_prompt_v0.py` | 세 후보 고정, dataset·의미 계약 hash, case 집합·실행 수 일치, API별 형식 지표와 Jev metadata 분리 |
| `test_import_supervisor_prompt_v0_langfuse.py` | V0 Dataset payload·고정 ID·결정적 점수·hash 차단·중복 영수증 차단·Experiment 쓰기 계약(네트워크 없음) |

### 인젝션·신뢰 경계·방어 재생
| 파일 | 확인하는 것 |
|---|---|
| `test_injection_baseline_plan.py` | 짝 구성(정상/공격 짝, 변경 위치 하나), 정답 필드 제외, 보호 사실 비노출 전제, T5 양쪽 fallback, T7 정규화·연결 보존, 예산식, 오프라인 명령·덮어쓰기 거부, 독립 잠금과 예산 |
| `test_injection_baseline.py` | 기본 계획(110행)·덮어쓰기/미실행 보존·승인 없는 실행 차단, T1~T7 실제 그래프 + 가짜 공급자, 사양 오염 자동채점, 스모크 계획의 원본 잠금·독립 scope, Langfuse 기록. 공급자·DB·소켓 차단 |
| `test_injection_preflight.py` | 공급자·DB·socket 연결을 기본 차단하고 원격/기존 DB 거부, 본문 해시, 여섯 노드·형식 재시도 관찰, 공유 예산, 스레드 전달, 캐시 격리, 사양 오염/누락/미도달/사람 미검토 채점 |
| `test_check_injection_result.py` | 저장한 실측 결과가 기준을 통과하고, 작업 수·상태·판정 기준·노출 전제를 깬 변이는 실패로 바뀜 |
| `test_input_surfaces.py` | 무료 계획, 덮어쓰기 거부, 이름 필드 무시/ref 거부, 청크·값·질문의 모델 입력 노출, 위험 응답 기록과 최종 차단(가짜 모델) |
| `test_claim_consistency.py` | 유료 기준선 실행기의 호출 없는 계획, 결과 덮어쓰기 거부, 상한 뒤 후속 미실행/부분 raw 보존, 거짓 가짜 응답의 원시 보존/최종 차단 |
| `test_trust_boundary.py` | D7 실행기의 dry-run 외부 호출 0, 기존 결과 보존, 정상 대조군, 공격 노출·canary 유출 탐지, 타 사용자 참조의 코드 차단, 오류 후 not_run 보존 |
| `test_judgement_bundle.py` | 원격/서비스 DB·덮어쓰기 거부, 단일 예산 차단, 위험 문서 답이 판정 답에서 차단됨. loopback DB 왕복 시험은 `TEST_INJECTION_DATABASE_URL`이 없으면 건너뛰며 사양 표 제거(ADR 0016) 뒤 현재 코드와의 일치는 확인되지 않음 |
| `test_saved_defense_replay.py` | 저장된 실제 C2/P4-N 응답과 원시 SHA256을 기존 에이전트·판정·최종 조립에 재생(모델·네트워크·DB 차단). 기준선 보존과 수정 후 차단 확인, `roles.yaml` 내용은 측정 커밋 `190cf89` 값에 고정 |
