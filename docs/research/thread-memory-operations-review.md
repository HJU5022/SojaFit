# Thread·승인 기억 운영 검증 결과

- 상태: 이력 (2026-11-09~11-12 검증 실행의 스냅샷. 이후 배포·DB 상태를 보증하지 않는다)
- 기준일: 2026-11-12
- 기준 커밋: 검증 실행별 대상 커밋은 1절 표. 현재 기준 커밋 6707002
- 정본 여부: 정본(Thread·승인 기억 운영 검증의 실행 결과). 기능 계약의 정본은 [user-thread-memory.md](../specs/user-thread-memory.md)와 [evaluator-demo-readiness.md](../specs/evaluator-demo-readiness.md), 측정 절차의 정본은 [thread-memory-operations.md](../experiments/thread-memory-operations.md)
- 관련 문서: [SPEC](../../SPEC.md) 8.5, [GATES](../GATES.md)

## 1. 검증 실행 요약

| 날짜 | 대상 | 환경 | 결과 | 확인하지 않은 것 |
|---|---|---|---|---|
| 2026-11-09 | STH `717c93a`·`245be70`·`ccadd3f`, 시험 image digest `cdc9ed1d…056f4` | 로컬 전체 pytest + 시험 Cloud Run revision `sojafit-api-00020-miv`(운영 00008-2h5가 100% 유지, 시험 트래픽 0%), 키 없는 소스 Compose(포트 8773) | 972 passed, 36 skipped, 57.86초. 합성 HTTP 17항목 통과. 실제 HTTP 흐름 통과(1.2절) | 원격 GitHub CI 실행, 전체 동결셋 before/after, 실제 청구 대조, 운영 RTO/RPO |
| 2026-11-09 | 위와 같은 날 원격 CI | head `7ff0d4a` | 일반 test CI 성공. Secret Scan이 검증 요약의 소스 SHA-256 한 건을 generic-api-key로 오탐 → `.gitleaksignore`의 커밋·파일·규칙·줄 fingerprint 한 건으로 처리(파일·규칙 전체 제외 아님). 같은 이미지 로컬 전체 이력 검사 453 commits/35.04MB: 실패 1 → 탐지 0, 다른 입력 위치의 검출 대조군은 여전히 탐지 | 변경 커밋의 원격 완료 결과 |
| 2026-11-12 | OSC `0d6592f`(이 저장소에 없는 커밋) + 당시 미커밋 작업 트리 | Docker + 로컬 `pgvector/pgvector:pg16`, 임시 DB·서버·계정 | 사용자 A·B 분리 확인. A 분석을 `requires_input`으로 중단. B의 A run 조회·재개 각각 404. HTTP 서버 종료·같은 DB로 재기동 후 A의 run이 `requires_input` 유지, 재개는 SSE `completed`. 종료 코드 0 | 실제 모델 답변·검색 품질, 배포 서버 재시작, 모든 API의 계정 분리 |
| 2026-11-12 | 코드 `758cbcc` | 로컬 `pgvector/pgvector:pg16` 임시 PostgreSQL | 별도 OS 프로세스 2개로 체크포인트 저장→종료→같은 DB·thread/run 읽기 확인. `WAITING` 확인 후 재개해 `DONE`과 답변 확인. 다른 계정의 `detail()` 조회는 `HTTPException`으로 차단. `tests/conversations/test_repository.py`, `tests/api/test_full_service_flow.py` 30 passed | 실제 LLM·검색 품질, HTTP 서버 재시작, 배포 환경, 전체 사용자 경계 |

원시: 2026-11-09 행은 `evals/results/graph/memory_operations_2026-11-09.json`(`tests.passed`=972, `skipped`=36, `seconds`=57.86, `synthetic_demo.http_checks` 17개 모두 true, `trial.revision`, `live_workflow.additional_reservation_usd`=0.426852) [실측] 값이 위 표와 일치한다. 2026-11-12 두 행의 원시 로그는 저장소에 없다(한계 1).

### 1.1 2026-11-12 HTTP 서버 재시작 재현

- 명령: Docker와 로컬 `pgvector/pgvector:pg16` 이미지가 준비된 환경에서 저장소 루트에서 `uv run --no-sync python tests/api/test_http_restart.py`. 임시 DB·서버와 임시 계정만 쓰고 종료 후 정리한다. 기본 pytest에서는 자동 실행하지 않는다.
- 범위: 실제 FastAPI 라우터·인증·대화 서비스·PostgresSaver/PostgresStore를 쓴다. LLM 그래프는 입력 대기 후 완료하는 합성 그래프로 대체한다. 외부 LLM·임베딩·Langfuse 호출은 없다.
- 이 저장소에 `tests/api/test_http_restart.py`가 있다. 파일 SHA-256은 현재 `2e66c690…a71a`이고 기록 당시 `4554767c…1e5`와 다르다(그 뒤 수정됨). 이 변환에서 실행하지 않았다.

### 1.2 2026-11-09 실제 HTTP 흐름과 UI

| 항목 | 결과 | 근거 |
|---|---|---|
| 실제 HTTP | 시험용 사용자 2명. 조건 보충 → `SPEC_EQUIVALENT` → 승인·Store → 같은 사용자의 새 thread 전달, B는 404와 빈 기억 | 원시 JSON `live_workflow.checks` |
| 추가 예약 | $0.426852(상한 $0.5). 사전 예약 $2.5는 시험 예산 장벽이며 실제 사용·청구가 아니다. 공급자 실제 청구 대조는 하지 않았다 | `live_workflow.additional_reservation_usd`, `reservation_cap_usd`, `test_prefill_not_actual_usage_usd`, `billing_reconciled`=false |
| 모델의 사례 선택 | 실제 모델은 새 thread의 자기 승인 사례를 입력받았지만 이번 답의 `memory_refs`는 비어 있었다. 전달 성공과 명시 선택 성공은 다르다. 이 사례만으로 회상률·답변 품질 향상을 주장하지 않는다 | `live_workflow.model_selected_case`=false |
| 실제 UI | 시험 URL에서 비밀번호 로그인, 승인 당시 최종 입력, 정정 메모 저장, 철회 후 기억 목록 제외, 복구 후 재표시를 관찰. API 삭제·재승인 차단과 중단 checkpoint 재개 차단은 격리 DB·합성 HTTP에서 검증 | 스크린샷은 저장소에 없음(한계 1) |
| Langfuse | `received`, `same_user`, `same_thread`, `trace_ids_match` 모두 true. 요약 span은 전송 시각, 처리 시간은 실측 metadata이며 중첩·병렬 시간을 합산하지 않는다. generation 원문, 비밀번호, 쿠키, DSN은 내보내지 않는다 | 원시 JSON `trace_checks` |
| 정리 | 시험 계정 비활성화, 세션 제거, 공유 DB의 시험 사용자 원본·승인은 보존 | 원시 JSON `live_workflow.cleanup` |
| 시험 설정 | 시험 revision만 출력 상한 2048. 기본 코드 4096·일일 $3·실행 $0.50 유지. Secret Manager 참조, TLS verify-full, CA, 동시성 4, timeout 120, max 인스턴스 1 유지 | 원시 JSON `trial.test_max_tokens`, 나머지는 기록 당시 문서 |

## 2. 기능·정본 문서에 반영할 사항 (제안)

| # | 대상 | 내용 | 반영 여부 |
|---|---|---|---|
| 1 | SPEC 8.5 | 장기 기억 = 사용자별 관련 승인 사례 참조. 정정은 별도 메모, 철회는 복구 가능, 기억 삭제는 Store 사본·향후 참조 제거·원본 유지, 자동 만료 없음. 전체 대화 자동 기억·자유 과거 질의는 범위 밖 | 미확인 |
| 2 | SPEC 7절 / README 데모 | `DEMO_MODE` 단독의 기존 BM25 실제 모델 평가와 `DEMO_SCENARIOS`+`DEMO_MODE` 앱 합성 시연을 구분 | 미확인 (`SPEC.md`에서 `DEMO_SCENARIOS`를 찾지 못했다) |
| 3 | SOJAFIT.md `data/demo` | "현재 설명 파일만 있고 재생 코드는 없음"을 "명시적 앱 합성 시나리오 데이터"로 갱신 | 미확인 |
| 4 | GATES G2·G4·G5·G6 | 위 실행의 범위·모드·샘플 수·증거를 적고, 원격 CI 실행·전체 동결셋 before/after·실제 청구 대조·운영 RTO/RPO는 미검증으로 유지. app 추적은 내용 없는 메타데이터 | 미확인 |
| 5 | 판정 사례 승인 | 판정 사례 승인은 견적서 승인·저장이 아니다. 판정 답변의 패키지·기판수정 문구는 footprint 문자열 비교 수준이며 치수 검증을 하지 못한다. `None` 표기와 오판 가능성은 judge 보완 과제 | 미확인 |

## 3. 2026-11-09 이전 스냅샷에서 해소된 것

| 이전 기록 | 현재 |
|---|---|
| 전체 pytest 837 passed, 43 skipped, 1 failed: `SOJAFIT.md`가 가리키는 `db/012_document_category.sql` 부재 | `db/012_document_category.sql` 존재 [실측] 2026-11-12 |
| 운영 전 보완 7건: ① 사례 인용만으로 현재 사양 주장이 검증을 통과하는 의미 검증 공백 ② interrupt 최종 조건의 승인 snapshot 보존·문맥 잘림 ③ 사용자별 비용·빈도·시간 제한 ④ 이전 승인 version 화면 복구 ⑤ 비밀값 없는 오류코드·요청 ID ⑥ 실제 모델 전달 사례와 사후 관련 사례 구분 ⑦ 기억 조회 순서·페이지·철회·보관·백업 복원 절차 | 2026-11-09 최종 실행에서 일부(④ 정정·철회·복구, ⑦ 철회·복구)를 관찰했다. 나머지는 이 변환에서 확인하지 않았다 |
| 합성 문장 "SS34의 허용 전압은 999V입니다"에 승인 사례 출처만 붙여 `verifier_agent`에 넣으면 `status=ok`. 검증은 출처 존재·인용 형식 범위 | 재확인하지 않았다 |

## 4. 한계

1. 2026-11-12 두 실행(1절 표 3·4행)의 원시 로그·스크립트는 저장소에 없다. 두 번째 실행은 inline 스크립트라 그대로 재현할 수 없고 G4 증거로 충분한지 별도 검토가 필요하다. 첫 번째 실행의 대상 커밋 `0d6592f`는 이 저장소에 없다. 스크린샷 3장(`memory-trial-restored.jpg`, `memory-trial-revoked.jpg`, `memory-demo-new-thread.jpg`)은 로컬 작업 산출물이며 저장소에 없다.
2. 두 번째 11-12 실행에서 Langfuse 키는 비워 외부 호출을 끊었다. 같은 프로세스 인스턴스 재생성 검사에서는 Langfuse 401 경고가 관찰됐다.
3. 11-09 실행의 실제 Langfuse trace는 프로젝트 권한이 있어야 열린다. 링크는 싣지 않았다.
4. 2절의 반영 여부는 SPEC·GATES·SOJAFIT를 모두 대조하지 않았다. 재현 가능한 HTTP 서버 재시작 증거는 `tests/api/test_http_restart.py`가 있으나 이 변환에서 실행하지 않았다.
5. 1절 표 1행의 시험 revision과 URL은 기록 시점의 배포 상태이며 현재 존재하는지 확인하지 않았다.
