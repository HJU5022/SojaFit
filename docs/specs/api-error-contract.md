# API 오류 응답 규약

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(정본: [SPEC.md](../../SPEC.md) 4절 공통 오류. 코드 표와 개수는 SPEC이 가진다)
- 관련 문서: [ADR 0019](../adr/0019-오류-코드는-화면이-다르게-반응해야-할-때만-나눈-15개로-한다.md), `backend/errors.py`, `backend/main.py`

## Why

- 페르소나: SojaFit API를 호출하는 웹 클라이언트 개발자와 운영자
- 문제: FastAPI 기본 `detail` 형식과 validation 형식이 섞이면 클라이언트가 오류별 구조를 따로 해석해야 하고, 오류를 로그와 잇는 공통 요청 식별자가 없다.
- 측정 지표: JSON 오류 응답 구조 일치율 100%, 모든 HTTP 응답의 `X-Request-ID` 포함률 100%, 요청 본문·내부 예외 문자열 노출 0건

## Goal

- FastAPI JSON 오류를 `error.code`, `error.message`, `error.request_id`로 통일한다.
- 성공·실패 응답 모두 서버가 생성한 요청 식별자를 `X-Request-ID` 헤더로 제공한다.
- OpenAPI의 오류 응답 스키마도 실제 공통 구조를 가리키게 한다.
- 기존 인증·관리자·가격 API의 성공 본문과 HTTP 상태 코드는 바꾸지 않는다.
- `error.code` 값 표와 개수는 [SPEC.md](../../SPEC.md) 4절 공통 오류가 정본이다. 아래 How 표는 HTTP 상태별 매핑과 상황 코드의 발생 지점을 적는다.
- Out of Scope: 질문 API, 사용자별 thread, LangGraph checkpointer·Store, 승인·견적, DB migration, 청킹·검색·모델 평가, 로그 저장소, 분산 trace 연동(요청 ID는 stdout JSON 로그 줄에만 적는다)

## What

- 프로젝트 생성 중복409의 선택적 `details.duplicates`는 소유 프로젝트의 id/name/matches를 최대5개 제공한다([생성 계약](netlist-conversation-versions.md)). 기존 error/code/message/request_id와 로그 형식은 유지하고 다른 오류에는 details를 추가하지 않는다. 클라이언트는409 CONFLICT의 검증된 후보만 선택 UI에 쓰고 잘못된 메타데이터는 무시한다.

1. 요청마다 서버가 UUID 기반 요청 식별자를 만들고 `request.state.request_id`에 저장한다.
2. 정상 응답은 기존 본문을 유지하고 `X-Request-ID` 헤더만 추가한다.
3. HTTP 오류, 검증 오류, 처리되지 않은 예외는 동일한 최상위 `error` 구조를 사용한다.
4. 검증 입력과 내부 예외 문자열은 응답에 노출하지 않는다.
5. 클라이언트가 보낸 `X-Request-ID`는 신뢰하지 않는다.

## How

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "로그인이 필요합니다.",
    "request_id": "서버가 생성한 UUID"
  }
}
```

| HTTP 상태 | 오류 코드(기본) | 상황 코드(`backend/errors.py`의 `ApiError`) |
|---:|---|---|
| 400 · 422 | `VALIDATION_ERROR` | |
| 401 | `UNAUTHORIZED` | |
| 403 | `FORBIDDEN` | `ORIGIN_MISMATCH`(요청 출처 불일치, `auth.check_origin`) |
| 404 | `NOT_FOUND` | `SCHEMATIC_NOT_FOUND` (검증된 완성 회로도 없음) |
| 409 | `CONFLICT` | `CONDITION_PENDING`(조건 질문 대기), `ALREADY_APPROVED`(이미 승인 · 승인할 수 없는 판정) |
| 413 | `PAYLOAD_TOO_LARGE` | |
| 429 | `RATE_LIMITED`(가입 횟수 · 호출 간격) | `LIMIT_EXCEEDED`(하루 토큰 · USD 상한, 분석 한 번의 호출 · 예약 상한) |
| 502 | `UPSTREAM_ERROR`(LLM · 임베딩 공급자 장애) | |
| 503 | `UNAVAILABLE` | |
| 504 | `TIMEOUT` | |
| 표에 없는 4xx · 5xx(예: 405) | `VALIDATION_ERROR` · `INTERNAL_ERROR` | |
| 처리되지 않은 예외 | `INTERNAL_ERROR` | |

- DB를 쓸 수 없는 경우는 모두 503 `UNAVAILABLE`이다: 연결 실패 · 연결 풀 대기(`backend/main.py`의 `database_unavailable`)와 DB 설정 누락(`DATABASE_URL`이 비면 `backend/auth.py`의 `connection`이 같은 문구 `저장소에 연결할 수 없습니다. 잠시 후 다시 시도하세요.`로 낸다). 설정 누락이 500이 되지 않게 `KeyError` 전체 처리기는 두지 않는다.
- 분석 SSE의 `failed` 이벤트도 같은 표로 `error.code`를 고른다(`backend/api/conversations.py`의 `public_error`). 분석 전 DB 장애는 `UNAVAILABLE`이다.
- 화면은 자기 오류 코드를 만들지 않는다. 2026-11-16 새 화면(`frontend/src/api.ts`의 `ApiError`)은 서버가 준 `error.code`를 그대로 담고, 본문 없는 오류 응답은 빈 `code`다. 옛 화면이 만들던 `HTTP_ERROR` · `STREAM_ERROR` · `STREAM_CLOSED` · `RUN_FAILED` · `APPROVAL_NOT_READY`는 화면과 함께 없어졌다.
- 로그: 오류 응답 · `failed` 이벤트마다 `backend/errors.py`의 `log_error`가 한 줄(`message: request_failed`, `code`, `status`, `request_id`)을 남긴다. 4xx는 INFO(문구 · 본문 없이), 5xx는 ERROR에 traceback(프레임과 예외 이름만)이다. 줄 모양은 `backend/logs.py`의 JSON 한 줄(`severity` · `time` · `logger` · `message`)이다.

- 문자열 `HTTPException.detail`은 기존 공개 메시지로 사용한다.
- 문자열이 아닌 detail은 상태별 일반 메시지로 바꾸고 객체를 노출하지 않는다.
- validation 메시지는 `요청 형식이 올바르지 않습니다.`로 고정한다.
- 처리되지 않은 예외 메시지는 `요청을 처리하지 못했습니다.`로 고정한다.
- 현재 API 계약을 즉시 전환하므로 기존 `detail` 필드는 함께 반환하지 않는다.
- 새 외부 패키지나 DB 테이블을 추가하지 않는다.

## AC

| AC | Given-When-Then | 시험 |
|---|---|---|
| AC-01 | `/health` 요청이면 기존 본문과 UUID 형식 `X-Request-ID`를 돌려준다 | `tests/api/test_health.py::test_health_has_server_generated_request_id` |
| AC-02 | 401·403·404 오류이면 공통 오류 본문이고 헤더 요청 ID와 일치한다 | `tests/api/test_health.py::test_not_found_uses_error_contract`, `test_auth_required_uses_error_contract`, `test_forbidden_uses_error_contract` |
| AC-03 | 잘못된 로그인 본문이면 422 공통 오류이고 입력값과 Pydantic 내부 정보가 없다 | `tests/api/test_health.py::test_validation_error_uses_safe_error_contract` |
| AC-04 | 처리되지 않은 예외이면 500 공통 오류이고 내부 문자열과 traceback이 없다 | `tests/api/test_health.py::test_unhandled_error_does_not_expose_internal_message` |
| AC-05 | 임의의 `X-Request-ID`를 보내면 서버가 만든 다른 값을 돌려준다 | 미확인(헤더 형식은 `test_health_has_server_generated_request_id`) |
| AC-06 | 기존 인증·관리자·가격 API의 성공 본문과 상태 코드가 유지된다 | `tests/api/test_auth.py`, `tests/api/test_prices.py` |
| AC-07 | `/openapi.json`의 오류 응답 스키마가 `ErrorEnvelope`를 가리킨다 | `tests/api/test_health.py::test_openapi_documents_common_validation_error_contract` |
| AC-08 | `DATABASE_URL`이 없는 서버에서 로그인이 필요한 경로(`GET /api/auth/me`)는 500이 아니라 503 `UNAVAILABLE`이다 | `tests/api/test_errors.py::test_missing_database_url_is_unavailable_not_internal_error` |
| AC-09 | 소유한 오래된 `running` run이면 `POST /api/runs/{run_id}/recover`가 failed로 정리하고, 다른 사용자의 run은 404이며 분석·모델을 호출하지 않는다 | `tests/api/test_conversations.py::test_recover_is_owned_origin_checked_and_never_calls_analysis`, `test_recover_does_not_expose_another_users_run` |
| AC-10 | 잘못된 재개 답이면 422로 거절하고 같은 run의 interrupt를 유지한다 | `tests/api/test_conversations.py::test_resume_unrequested_answers_leave_interrupt_unchanged` |

## 실행 복구와 클라이언트 오류 처리

- 서버: `POST /api/runs/{run_id}/recover`(`backend/api/conversations.py:205`)는 로그인·Origin·소유권을 확인하고 `Run` DTO를 돌려준다. `running`의 갱신 시각이 max(300초, `ANALYSIS_MAX_SECONDS`+60초)보다 오래되고 thread의 분석 advisory 잠금이 없을 때만 failed로 바꾼다(`backend/conversations/repository.py:23-36`). 경로 계약은 [SPEC.md](../../SPEC.md) 4절.
- 서버: 재개 답에 요청하지 않은 키가 있으면 상태 전이 전에 422다(`backend/conversations/memory_service.py:462-463`).
- 클라이언트(읽기 확인): 스트림 수신 120초 제한, 연결 종료 뒤 `GET` 복구 최대 30회(1초 간격, 요청당 10초), 끝나지 않으면 `recover` 한 번 호출(`frontend/src/hooks/useRunStream.ts:30-45,64`, 11-16 교체 전 옛 화면. 새 화면은 `frontend/src/Workbench.tsx`의 `recover`가 `POST /api/runs/{id}/recover`를 한 번 부르며, 120초 · 30회 복구 상한은 새 화면 코드에서 찾지 못했다(2026-11-17 대조)). 질문·재개 POST는 자동 재전송하지 않는다.

## 구현 상태

| 항목 | 상태 | 근거 |
|---|---|---|
| 공통 오류 본문, `X-Request-ID`, OpenAPI 스키마 | 구현 | `backend/main.py`, `tests/api/test_health.py`, `tests/api/test_errors.py` |
| 상황 코드 `ApiError`, 오류 한 줄 로그 | 구현 | `backend/errors.py`, `tests/api/test_errors.py` |
| `POST /api/runs/{run_id}/recover` | 구현, SPEC 4절 표에 있음 | `SPEC.md:155` |

## 한계

- `tests/api/test_errors.py`의 `test_table_has_fifteen_codes_and_defaults` 이름은 15개를 말하지만 단언은 16이다. `backend/errors.py` 머리 주석(`ADR 0019의 15개`, `상황 코드 4개`)도 코드 표(기본 11 + 상황 5)와 다르다. 코드는 이 구역 밖이다.
- 화면 쪽 오류 정규화(HTML·빈 본문·잘못된 JSON 처리)와 failed 안내 단일화는 `frontend/**`를 읽어 대조하지 않았다.
