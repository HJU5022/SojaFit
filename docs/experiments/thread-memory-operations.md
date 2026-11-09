# Thread·승인 기억 운영 검증

상태: STH의 검증 계약. 선택 문항·실제 HTTP·로컬 복원 결과는 [운영 검증 결과](../research/thread-memory-operations-review.md)와 [작업 기록](../worklog/sth.md)를 따른다. 원격 부하·공유 DB 복원·전체 동결셋 품질 비교는 실행하지 않았다.

## Why
격리·저장은 확인했지만 전체 답변 품질, 운영 부하, 운영 백업 복구와 청구액은 별도 증거가 필요하다. 예약액·참조 ID·HTTP200만으로 통과 처리하지 않는다.

## Goal
| 항목 | 첫 검증·합격 기준 | 확대 전 조건 |
|---|---|---|
| 품질 | 동결 v2 선택 1~4건, 오류/가짜 인용/근거 없는 숫자 0건. PDF 쪽·표·시험 조건 대조 | 70건 전체는 같은 코드·코퍼스·기준과 별도 예산으로 측정 |
| 기억 | A/B 같은 품번·다른 승인 조건. 타 사용자 정보/과거 조건의 현재 자동 대입 0건 | 순수 기억 질문의 범위 밖 거절은 현재 제한으로 집계 |
| 병렬 | 로컬 8개 요청, 예약 초과/다른 thread 변경/예상된429 이외 오류 0건 | 원격은 시험 tag에 동시성1→2→4, 단계당 총4회 이하 |
| 복원 | 별도 DB에서 승인 원본/Store/소유권/중단 재개/새 승인 전부 통과 | 운영은 계정·세션·HMAC키·CA·코퍼스·앱 버전 검토 |
| 청구액 | 공급자 응답 ID별 비용을 Activity/청구 내역과 대조, 누락은 미확인 | 공용 키 다른 호출·Voyage·Cloud Build/Run 비용 분리 |

Out of Scope: 기능 확장, 기억 전용 라우팅, 운영 승격, 공유 DB 덮어쓰기, 동결 정답 수정. 표본 결과는 전체 정확도/운영 RTO/RPO가 아니다.

## What
무료 사전 확인→로컬 병렬·복원→유료 평가 조건 사전 등록→dry-run→명시적 execute→PDF/청구 내역 대조 순서다. 원격 부하·운영 복원은 대상·예산·백업 권한을 확인한 뒤 별도로 실행한다.

## How
### 로컬 (PowerShell, 저장소 루트)
uv/Docker 및 환경변수 TEST_THREAD_DATABASE_URL에 격리 로컬 DB가 필요하다. 팀 DATABASE_URL을 복사하지 않는다. 복원은 loopback의 thread_test* DB만 허용하고 컨테이너 포트도 대조한다. 생성한 무작위 thread_restore_* DB만 제거한다. dump는 메모리에서 처리하고 파일/채팅/Git에 저장하지 않는다.

```powershell
uv run --no-sync --offline python -m evals.runners.freeze --check
uv run --no-sync --offline pytest -q tests/repo tests/services/test_llm.py
$env:TEST_THREAD_BACKUP_CONTAINER = 'sojafit-thread-test-1109'
uv run --no-sync --offline pytest -q -s tests/api/test_threads.py::test_eight_parallel_threads_share_daily_budget_without_mixing tests/api/test_threads.py::test_dump_restore_preserves_owned_memory_and_pending_resume
```

전체 DB dump/restore이므로 합성 데이터만 있는 DB에서 실행한다. BACKUP_CONTAINER가 없으면 skip이며 성공으로 세지 않는다. CI에 Docker 소켓이 없으면 로컬 결과를 첨부한다.

### 유료 품질·보고 비용 준비
기존 run_graph/EvaluationBudget을 재사용한다. 기본은 API 없는 dry-run. execute는 선택 문항 전체 합계 예약 $0.50/16회/90초/4096토큰이다. Voyage도 같은 예약·시간 경계를 사용한다. 못 끝내면 부분 실행/실패로 남기고 자동 증액하지 않는다. 서비스 사용자 일일 DB 예산과 독립된 평가 프로세스이므로 공용 키 잔액도 확인한다.

```powershell
uv run --no-sync --offline python -m evals.runners.run_thread_validation --ids draft30-e01 --out evals/results/graph/thread_validation_2026-11-09.json
# 아래는 사전 등록·잔액·비교 조건 확인 뒤 실행할 유료 명령이다.
uv run --env-file .env --no-sync python -m evals.runners.run_thread_validation --ids draft30-e01 --out evals/results/graph/thread_validation_2026-11-09.json --execute
```

기존 결과는 덮어쓰지 않는다. 옆 usage.json에는 본문 없이 공급자 응답 ID/모델/토큰/보고 비용/예약액/누락 여부를 남긴다. 비용 누락 시 합계는 null이며 0달러가 아니다. 오류·타임아웃은 응답이 없어 비용 증거가 빠질 수 있다. Voyage는 별도 청구 내역으로 대조한다. 기존 원격 API는 공급자 ID를 반환하지 않아 과거 원격 비용을 이 파일로 소급 증명하지 못한다.

### 실행 시 남길 증거
- 품질: 결과 trace_url에서 문장별 PDF 이름/개정판/쪽/표/행/시험 조건을 적고 일치·불일치·확인 불가로 표시한다. 숫자/단위/판정을 코드 결과와 대조한다. 규칙 채점과 의미 검증을 구분한다.
- 기억: provided/selected와 의미 정확성을 구분한다. 순수 기억, 현재 역할+기억, 현재/과거 조건 충돌, 기억 없음, B의 A 접근, 악성 지시를 각각 확인한다. 참조 ID만으로 의미 검증을 통과시키지 않는다.
- 청구액: Activity에서 usage의 응답 ID로 비용/모델/시각을 대조한다. 공용 키 잔액 차이를 실험 비용으로 귀속하지 않는다. ID 누락/취소/지연 반영은 미확인이다. CSV 원본·자격증명을 Git에 넣지 않는다.
- 원격 부하: 성공 수·429/409/503/504·p50/p95·예약 증가·Cloud Run 오류·DB 연결 수를 기록한다. 총12요청 이하/예약 최대$6(실제 청구 상한 아님). 503/504·격리 실패·예약 초과·운영 영향 시 중단한다. 별도 실행 승인·사전 등록 대상이며 운영 기본 URL에는 보내지 않는다. 4건의 p95를 운영 성능으로 해석하지 않는다.
- 운영 복원: 승인된 백업 시각/보관 위치/복호화 권한/보존기간/RPO/RTO/앱·마이그레이션·코퍼스 버전/세션 HMAC·DB CA 복구 경로를 기록한다(비밀값 제외). 사용자 ID와 sojafit_agent/checkpoint/Store를 일관된 snapshot으로 복원한다. 별도 비공개 DB에서 읽기/재개/승인/A·B를 검증한 뒤 전환을 검토한다. 실제 전환·기존 DB 삭제는 이번 준비에 포함하지 않는다.

## AC
- GIVEN execute 없음 WHEN dry-run THEN API/DB 호출 없이 문항·동결 해시·상한만 표시한다.
- GIVEN 기존 결과 또는 모르는/중복/5개 이상 ID WHEN 준비 THEN 호출 전에 거부한다.
- GIVEN 응답 비용/ID 누락 WHEN 집계 THEN 미확인이며 청구액 대조를 통과시키지 않는다.
- GIVEN 로컬8개 thread WHEN 일일$0.08에서 예약 THEN 최대3건성공/나머지429, 질문이 섞이지 않는다. 입장429는 version0/메시지 없음도 허용한다.
- GIVEN 승인/interrupt dump WHEN 새 DB restore THEN 자기 기억/B의404/조건 재개/새 승인 통과, 원본 interrupt 유지.
- GIVEN 공유 DB/다른 컨테이너 포트 WHEN 복원 시험 THEN DB 생성·복원·삭제 전에 거부한다.
- GIVEN 순수 과거 기억 질문 WHEN 범위 밖 거절 THEN 기억 활용 성공에 포함하지 않는다.
