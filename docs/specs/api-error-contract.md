# API 오류 응답 규약

- 작성일: 2026-11-08
- 범위: FastAPI 공통 JSON 오류 응답과 요청 식별자
- 바뀜(2026-11-10, ADR 0019): `error.code`를 HTTP 상태별 10개에서 화면 행동이 다른 곳만 나눈 15개로 바꾸고(How 표), 오류 응답마다 JSON 한 줄 로그를 남긴다. 아래 Out of Scope의 "로그 저장소 연동"과 How의 마지막 줄은 이 변경으로 바뀌었다(stdout JSON 로그까지, 로그 저장소 · 분산 trace 연동은 여전히 범위 밖)

## Why

- **페르소나**: SojaFit API를 호출하는 웹 클라이언트 개발자와 운영자
- **상황**: 이 작업 전에는 인증·관리자·가격 API가 FastAPI 기본 `detail` 형식과 별도 validation 형식을 반환했다.
- **문제**: 클라이언트가 오류별 응답 구조를 따로 해석해야 했고, 오류를 후속 로그·추적 기능과 연결할 공통 요청 식별자가 없었다.
- **측정 지표**: JSON 오류 응답 구조 일치율 100%, 모든 HTTP 응답의 `X-Request-ID` 포함률 100%, 요청 본문·내부 예외 문자열 노출 0건

## Goal

- FastAPI JSON 오류를 `error.code`, `error.message`, `error.request_id`로 통일한다.
- 성공·실패 응답 모두 서버가 생성한 요청 식별자를 `X-Request-ID` 헤더로 제공한다.
- OpenAPI의 오류 응답 스키마도 실제 공통 구조를 가리키게 한다.
- 기존 인증·관리자·가격 API의 성공 본문과 HTTP 상태 코드는 바꾸지 않는다.
- **Out of Scope**: 질문 API, 사용자별 thread, LangGraph checkpointer·Store, 승인·견적, DB migration, 청킹·검색·모델 평가, 로그 저장소 또는 분산 trace 연동

## What

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
- 화면이 스스로 만드는 코드(`HTTP_ERROR`: 본문 없는 오류 응답, `STREAM_ERROR` · `STREAM_CLOSED` · `RUN_FAILED` · `APPROVAL_NOT_READY`)는 서버 표 밖이다.
- 로그: 오류 응답 · `failed` 이벤트마다 `backend/errors.py`의 `log_error`가 한 줄(`message: request_failed`, `code`, `status`, `request_id`)을 남긴다. 4xx는 INFO(문구 · 본문 없이), 5xx는 ERROR에 traceback(프레임과 예외 이름만)이다. 줄 모양은 `backend/logs.py`의 JSON 한 줄(`severity` · `time` · `logger` · `message`)이다.

- 문자열 `HTTPException.detail`은 기존 공개 메시지로 사용한다.
- 문자열이 아닌 detail은 상태별 일반 메시지로 바꾸고 객체를 노출하지 않는다.
- validation 메시지는 `요청 형식이 올바르지 않습니다.`로 고정한다.
- 처리되지 않은 예외 메시지는 `요청을 처리하지 못했습니다.`로 고정한다.
- 현재 API 계약을 즉시 전환하므로 기존 `detail` 필드는 함께 반환하지 않는다.
- 새 외부 패키지나 DB 테이블을 추가하지 않는다.
- 요청 ID를 로그 저장소나 분산 trace에 기록하는 것은 이 작업 범위가 아니다(11-10부터 stdout JSON 로그 줄에는 적는다, ADR 0019).

## AC

### 2026-11-11 실행 복구·재개·클라이언트 오류 보완 (사용자 요청)

- Why/Goal: DB 종료 저장 실패·서버 재시작 후 무한 대기와 입력 오류로 인한 재개 단절을 막는다. 모델 재호출은 0회다.
- What: 스트림 수신은 120초, 연결 종료 뒤 GET 복구는 최대 30회(1초 간격, 요청당 10초)로 제한한다. 확인할 수 없으면 실행 ID를 유지하고 수동 상태 확인을 제공한다. 질문·재개 POST는 자동 재전송하지 않는다.
- How: 로그인·Origin·소유권을 확인하는 `POST /api/runs/{run_id}/recover`는 같은 Run DTO와 no-store를 반환한다. `running`의 갱신 시각이 max(300초, ANALYSIS_MAX_SECONDS+60초)보다 오래되고 thread의 분석 advisory 잠금이 없을 때만 failed로 정리한다. GET은 읽기 전용이며 복구는 분석을 실행하지 않는다. DB 구조는 변경하지 않는다.
- How: 재개 답의 요청되지 않은 키는 상태 전이 전에 422로 거절한다. 분석 전 400/409/422/429 오류 후 현재 checkpoint가 여전히 입력을 기다리면 기존 interrupt를 requires_input으로 보존하고 공개 오류를 함께 전달한다. 처리된 입력을 자동 재전송하지 않는다.
- How: 공통 fetch와 SSE 시작 오류는 같은 정규화를 사용한다. HTML·빈 본문·잘못된 JSON/객체는 본문을 화면에 노출하지 않고 상태별 기본 코드·안전한 문구·X-Request-ID를 사용한다. 401은 파싱 성공 여부와 관계없이 세션을 만료시킨다.
- AC: Given 오래된/최근/분석 잠금 중/타 사용자 run, When 복구, Then 오래되고 잠금 없는 소유 run만 failed이며 다른 run·기록·모델은 변경하지 않는다.
- AC: Given 잘못된 재개 답, When 거절 후 올바른 답 제출, Then 같은 run의 입력 폼·interrupt를 유지하고 정상 재개한다.
- AC: Given 끝나지 않는 조회·스트림 오류, When 상한 도달, Then 자동 조회가 멈추고 상태 확인만 다시 할 수 있으며 분석 POST 횟수는 증가하지 않는다.
- AC: Given HTML 401/빈 503/잘못된 JSON 오류, When 일반 API·SSE 시작 호출, Then 공통 오류와 헤더 요청 ID가 유지되고 HTML·서버 내부 문구는 노출하지 않는다.
- 실패 안내 단일화: failed/상태 불명일 때 대화의 분석 상태 카드는 숨기고 기존 role=alert에 오류 안내·요청 ID를 한 번만 표시한다. 실행 ID가 있으면 기존 ‘실행 상태 확인’ 버튼과 recover 호출을 유지한다. 진행 중·추가 입력·완료·거절의 상태 표시는 변경하지 않는다.
- 대화 생성 실패: 첫 thread POST 실패도 대화창의 같은 오류 영역에 요청 ID와 함께 한 번 표시하고 초점을 보낸다. 질문 초안은 유지하고 thread/run을 자동 재전송하지 않는다. 사용자가 다시 전송하면 오류를 지우고 새 thread 생성부터 재시도한다. 아직 run ID가 없으면 실행 상태 확인 버튼을 표시하지 않는다.
- 정본 SPEC 4절의 새 recover 경로·SSE 오류 포함 requires_input 계약 반영은 STH에서 주요 문서를 수정할 수 없으므로 조장 검토 대상으로 남긴다.

- **AC-01** Given `/health`, When 요청, Then 기존 본문과 UUID 형식의 `X-Request-ID`를 반환한다.
- **AC-02** Given 401·403·404 HTTP 오류, When 요청, Then 공통 오류 본문과 헤더의 요청 ID가 일치한다.
- **AC-03** Given 잘못된 로그인 본문, When 검증 실패, Then 422 공통 오류이며 입력값과 Pydantic 내부 정보가 없다.
- **AC-04** Given 처리되지 않은 예외, When 공통 처리기에 도달, Then 500 공통 오류이며 내부 문자열과 traceback이 없다.
- **AC-05** Given 임의의 `X-Request-ID`, When 성공 또는 오류 응답, Then 서버가 생성한 다른 값을 반환한다.
- **AC-06** Given 기존 인증·관리자·가격 API 테스트, When 공통 오류 처리기를 적용, Then 성공 본문과 상태 코드가 유지된다.
- **AC-07** Given `/openapi.json`, When validation 오류 응답 문서를 확인, Then FastAPI 기본 `HTTPValidationError.detail`이 아니라 `ErrorEnvelope`를 가리킨다.
- **AC-08** Given `DATABASE_URL`이 없는 서버와 세션 쿠키, When 로그인이 필요한 경로(`GET /api/auth/me`), Then 500이 아니라 503 `UNAVAILABLE` 공통 오류다(`tests/api/test_errors.py`).
