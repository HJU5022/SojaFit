# Thread·승인 기억 운영 검증

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 정본(검증 계약과 합격 기준). 실행 결과의 정본은 [thread-memory-operations-review.md](../research/thread-memory-operations-review.md)와 `evals/results/graph/thread_validation_2026-11-09.json`
- 관련 문서: [EXPERIMENTS.md](EXPERIMENTS.md), [user-thread-memory.md](../specs/user-thread-memory.md), [evaluator-demo-readiness.md](../specs/evaluator-demo-readiness.md), [sth.md](../worklog/sth.md)

## 1. 요약

| 항목 | 값 | 근거 |
|---|---|---|
| 질문 | 격리·저장 확인 뒤 남은 증거(전체 답변 품질, 운영 부하, 운영 백업 복구, 청구액)를 어떻게 모을 것인가 | |
| 실행한 것 | 유료 품질 평가 1문항(`draft30-e01`), 로컬 병렬·복원 시험 | 3절 |
| 실행하지 않은 것 | 원격 부하, 공유 DB 복원, 전체 동결셋 품질 비교 | |
| 통과 기준 | 예약액·참조 ID·HTTP 200만으로 통과 처리하지 않는다 | 2절 |

## 2. 합격 기준

| 항목 | 첫 검증 합격 기준 | 확대 전 조건 |
|---|---|---|
| 품질 | 동결 v2 선택 1~4건, 오류·가짜 인용·근거 없는 숫자 0건. PDF 쪽·표·시험 조건 대조 | 70건 전체는 같은 코드·코퍼스·기준과 별도 예산 |
| 기억 | A/B 같은 품번·다른 승인 조건. 타 사용자 정보·과거 조건의 현재 자동 대입 0건 | 순수 기억 질문의 범위 밖 거절은 현재 제한으로 집계 |
| 병렬 | 로컬 8개 요청, 예약 초과·다른 thread 변경·예상된 429 외 오류 0건 | 원격은 시험 tag에서 동시성 1→2→4, 단계당 총 4회 이하 |
| 복원 | 별도 DB에서 승인 원본·Store·소유권·중단 재개·새 승인 통과 | 운영은 계정·세션·HMAC 키·CA·코퍼스·앱 버전 검토 |
| 청구액 | 공급자 응답 ID별 비용을 Activity·청구 내역과 대조, 누락은 미확인 | 공용 키 다른 호출·Voyage·Cloud Build/Run 비용 분리 |

범위 밖: 기능 확장, 기억 전용 라우팅, 운영 승격, 공유 DB 덮어쓰기, 동결 정답 수정. 표본 결과는 전체 정확도나 운영 RTO/RPO가 아니다.

순서: 무료 사전 확인 → 로컬 병렬·복원 → 유료 평가 조건 사전 등록 → dry-run → 명시적 execute → PDF·청구 내역 대조. 원격 부하·운영 복원은 대상·예산·백업 권한을 확인한 뒤 별도로 실행한다.

## 3. 결과

| 항목 | 값 | 근거 |
|---|---|---|
| 유료 품질 평가 | 1문항(`draft30-e01`) 완료, `cited_gold` 1, 실패 0, p50 5.9초, LLM 호출 2회 | `evals/results/graph/thread_validation_2026-11-09.json` `summary` |
| 예약·비용 | 예약 $0.244257, 공급자 보고 비용 합계 $0.020088325, 응답 ID 누락 0. 청구 대조 안 함(`billing_reconciled` false) | `thread_validation_2026-11-09.usage.json` |
| 상한 | $0.50, 16회, 90초, 출력 4096토큰 | 같은 파일 `limits`, `evals/runners/run_thread_validation.py:49` |
| 평가셋 | v2, SHA-256 `81582c59…6bb09a9`(`evals/FROZEN.json`의 v2 해시와 같음) | usage 파일 `dataset_sha256` |
| 로컬 병렬·복원, 이후 재검증 | [thread-memory-operations-review.md](../research/thread-memory-operations-review.md) | |

판정 출처: 품질 항목의 규칙 채점(`score_answer`)은 자동이다. 문장별 PDF 대조 검토자는 위 결과 문서가 정본이다.

## 4. 절차

### 4.1 로컬 (저장소 루트)

사전 조건: uv, Docker, 격리 로컬 DB를 가리키는 `TEST_THREAD_DATABASE_URL`. 팀 `DATABASE_URL`을 복사하지 않는다. 복원은 loopback의 `thread_test*` DB만 허용하고 컨테이너 포트도 대조한다. 만든 무작위 `thread_restore_*` DB만 지운다. dump는 메모리에서 처리하고 파일·채팅·Git에 저장하지 않는다. 전체 DB dump/restore이므로 합성 데이터만 있는 DB에서 실행한다.

```bash
uv run --no-sync --offline python -m evals.runners.freeze --check
uv run --no-sync --offline pytest -q tests/repo tests/services/test_llm.py
export TEST_THREAD_BACKUP_CONTAINER=sojafit-thread-test-1109
uv run --no-sync --offline pytest -q -s tests/api/test_threads.py::test_eight_parallel_threads_share_daily_budget_without_mixing tests/api/test_threads.py::test_dump_restore_preserves_owned_threads_and_pending_resume
```

`TEST_THREAD_BACKUP_CONTAINER`가 없으면 복원 시험은 skip되며 성공으로 세지 않는다. CI에 Docker 소켓이 없으면 로컬 결과를 첨부한다.

### 4.2 유료 품질·보고 비용

기존 `run_graph`/`EvaluationBudget`을 쓴다. 기본은 API 없는 dry-run. execute는 선택 문항 합계 예약 $0.50, 16회, 90초, 4096토큰이며 Voyage도 같은 예약·시간 경계를 쓴다. 못 끝내면 부분 실행·실패로 남기고 자동 증액하지 않는다. 서비스 사용자 일일 DB 예산과 독립된 평가 프로세스이므로 공용 키 잔액도 확인한다.

```bash
uv run --no-sync --offline python -m evals.runners.run_thread_validation --ids draft30-e01 --out evals/results/graph/<새 결과 파일>.json
# 사전 등록·잔액·비교 조건 확인 뒤에만 (유료)
uv run --env-file .env --no-sync python -m evals.runners.run_thread_validation --ids draft30-e01 --out evals/results/graph/<새 결과 파일>.json --execute
```

기존 결과 파일은 덮어쓰지 않는다(`--out`이 이미 있으면 `FileExistsError`; 2026-11-09 결과 파일은 이미 존재하므로 새 경로를 쓴다). 옆 `usage.json`에는 본문 없이 응답 ID, 모델, 토큰, 보고 비용, 예약액, 누락 여부를 남긴다. 비용이 누락되면 합계는 null이고 0달러가 아니다. 오류·타임아웃은 응답이 없어 비용 증거가 빠질 수 있다. Voyage는 별도 청구 내역으로 대조한다. 과거 원격 API는 공급자 ID를 반환하지 않아 과거 원격 비용을 이 파일로 소급 증명하지 못한다.

### 4.3 실행 때 남길 증거

| 영역 | 남길 것 |
|---|---|
| 품질 | trace_url에서 문장별 PDF 이름·개정판·쪽·표·행·시험 조건을 일치/불일치/확인 불가로 표시. 숫자·단위·판정을 코드 결과와 대조. 규칙 채점과 의미 검증을 구분 |
| 기억 | provided/selected와 의미 정확성을 구분. 순수 기억, 현재 역할+기억, 현재·과거 조건 충돌, 기억 없음, B의 A 접근, 악성 지시를 각각 확인. 참조 ID만으로 의미 검증을 통과시키지 않는다 |
| 청구액 | Activity에서 usage의 응답 ID로 비용·모델·시각을 대조. 공용 키 잔액 차이를 실험 비용으로 귀속하지 않는다. ID 누락·취소·지연 반영은 미확인. CSV 원본·자격증명은 Git에 넣지 않는다 |
| 원격 부하 | 성공 수, 429/409/503/504, p50/p95, 예약 증가, Cloud Run 오류, DB 연결 수. 총 12요청 이하, 예약 최대 $6(실제 청구 상한 아님). 503/504·격리 실패·예약 초과·운영 영향 시 중단. 별도 승인·사전 등록 대상이며 운영 기본 URL에는 보내지 않는다. 4건의 p95를 운영 성능으로 해석하지 않는다 |
| 운영 복원 | 승인된 백업 시각·보관 위치·복호화 권한·보존기간·RPO·RTO·앱·마이그레이션·코퍼스 버전·세션 HMAC·DB CA 복구 경로(비밀값 제외). 사용자 ID와 `sojafit_agent`·checkpoint·Store를 일관된 snapshot으로 복원. 별도 비공개 DB에서 읽기·재개·승인·A/B를 검증한 뒤 전환을 검토. 실제 전환·기존 DB 삭제는 포함하지 않는다 |

## 5. 수용 기준

| 조건 | 기대 | 시험 |
|---|---|---|
| execute 없이 dry-run | API·DB 호출 없이 문항·동결 해시·상한만 표시 | `evals/runners/run_thread_validation.py:51` |
| 기존 결과가 있거나 모르는·중복·5개 이상 ID | 호출 전에 거부 | `run_thread_validation.py:44-48` |
| 응답 비용·ID 누락 | 미확인이며 청구액 대조를 통과시키지 않음 | |
| 로컬 8개 thread, 일일 $0.08 | 최대 3건 성공, 나머지 429, 질문이 섞이지 않음. 입장 429는 version 0·메시지 없음도 허용 | `tests/api/test_threads.py::test_eight_parallel_threads_share_daily_budget_without_mixing` |
| 승인·interrupt dump를 새 DB에 restore | 자기 기억 유지, B는 404, 조건 재개·새 승인 통과, 원본 interrupt 유지 | `tests/api/test_threads.py::test_dump_restore_preserves_owned_threads_and_pending_resume` |
| 공유 DB·다른 컨테이너 포트로 복원 시험 | DB 생성·복원·삭제 전에 거부 | |
| 순수 과거 기억 질문의 범위 밖 거절 | 기억 활용 성공에 포함하지 않음 | |

## 6. 한계

- 유료 품질 평가는 1문항뿐이다. 전체 정확도가 아니다.
- 원격 부하, 공유 DB 복원, 전체 동결셋 품질 비교는 실행하지 않았다.
- 공급자 보고 비용은 실제 청구와 대조하지 않았다.
- 수용 기준 표에서 시험 이름이 비어 있는 행은 대응 시험을 확인하지 못했다.
