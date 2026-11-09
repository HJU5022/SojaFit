# D5 프론트엔드 서비스 기능 계약

## Why

- **페르소나**: 로그인한 SojaFit 사용자.
- **상황**: 사용자는 공개 데모 회로를 선택하거나 KiCad 넷리스트를 올려 대상 부품을 고르고, D5에 질문해 데이터시트 근거와 후보 판정을 확인한다.
- **문제**: 현재 로그인과 가격 API는 있지만 회로·프로젝트·D5 대화·승인 흐름을 브라우저에서 이어 쓸 서비스 화면이 없다.
- **측정 지표**: AC-01~AC-10의 사용자 흐름·저장 경계·권한 조건을 모두 만족하는 통합 수용 테스트 통과율 100%.

## Goal

- **해결 목표**: React + Vite + TypeScript 화면을 FastAPI와 같은 출처로 제공하고, 기존 D5의 실행·판정 규칙을 변경하지 않은 채 인증부터 프로젝트 생성, 질문·재개, 결과 확인, 승인 견적까지 연결한다.
- **성공 기준**: AC-01~AC-10 모두 통과. 업로드 원본·가격/재고 응답은 영속 저장소에 0건이며, 로그인한 사용자의 프로젝트·대화 복구는 새로고침과 재로그인 후 성공한다.
- **Out of Scope**: D4 실행 UI, D5 판단 규칙 변경, 외부 웹 조회 에이전트, 실제 주문·결제, 원본 회로도/PCB 업로드, 프로젝트 공유, 실시간 공동 편집, 모바일 전용 앱.

## What

**Happy Path**

1. 사용자가 같은 출처에서 로그인하고 새로고침해도 서버 세션으로 인증 상태를 복원한다.
2. 공개 데모 회로 5종 중 하나를 선택하거나 UTF-8 KiCad `.net` 파일(최대 5 MiB)을 올려 프로젝트를 만든다.
3. 업로드는 최상위 구조와 부품·넷 존재를 확인하고 정규화한다. 정규화가 끝나면 성공·실패와 관계없이 원본 참조를 즉시 제거하고, 원본 바이트는 D5 입력·실행 상태·checkpoint로 전달하지 않는다. 정규화 JSON·원본 SHA-256·파서 버전·생성 시각만 저장한다.
4. 사용자가 프로젝트와 대상 부품을 선택해 질문하면 서버가 기존 D5를 같은 thread에서 실행하고 허용된 진행 상태를 SSE로 보낸다.
5. 판정에 회로 값이 더 필요하면 thread/checkpoint에 인터럽트를 보존하고 `requires_input`으로 끝낸다. 사용자의 입력은 같은 run을 재개한다.
6. 브라우저 D5 DTO 허용 필드는 `answer`, `status`, `stage`, `question_type`, `evidence`, `judgement`, `price_parts`, `refusal`, `interrupt`, `request_id`뿐이다. Plan·TaskReport 전문과 일부 내용, 내부 추론·chain-of-thought, 서버 경로, prompt·모델 원문은 반환하거나 노출하지 않는다.
7. 가격·재고가 필요하면 `/api/prices`를 별도 호출하고 화면 메모리에만 보관한다. 판정 승인 후에만 견적과 승인 사례를 저장한다.

**Edge Cases**

| # | 상황 | 처리 |
|---|---|---|
| EC-01 | 비로그인 또는 만료 세션 | 401이면 로그인 화면으로 보내고, 토큰을 브라우저 저장소에 보관하지 않는다. |
| EC-02 | 업로드 파일이 5 MiB 초과 또는 UTF-8/넷리스트 형식 오류 | 413 또는 400으로 거절하고 프로젝트를 만들지 않으며 원본을 보존하지 않는다. |
| EC-03 | 같은 thread에서 실행 중 중복 질문 | 409 `run_in_progress`; 프론트는 중복 실행을 막고 기존 run 상태만 조회한다. |
| EC-04 | SSE 연결이 끊김 | `GET /api/runs/{run_id}`로 저장 상태를 조회하며 질문을 자동 재전송하지 않는다. |
| EC-05 | 다른 사용자의 프로젝트·thread·승인 자료 접근 | 403 또는 리소스 비공개 404로 거절하고 내용을 반환하지 않는다. |
| EC-06 | 승인 전 견적 저장 요청 | 409로 거절하며 견적·승인 사례를 저장하지 않는다. |
| EC-07 | 프로젝트 삭제 | 한 트랜잭션으로 회로, thread, 메시지, run, 견적 및 연결된 승인 사례와 같은 UUID 사용자 분석 thread의 checkpoint·메시지·승인 기록·분석 사건을 삭제한다(11-09 결정). 사용자 사실 기억(Store)은 프로젝트에 딸리지 않아 남는다. |
| EC-08 | 가격 API 미가용 또는 응답 | 가격 없이 판정은 유지하고, 가격 응답은 DB·메시지·checkpoint·견적·승인 사례에 기록하지 않는다. |

## How

- **프론트엔드**: React + Vite + TypeScript, React Router, TanStack Query, 소규모 앱 상태용 React Context, same-origin cookie를 사용하는 기본 `fetch` 래퍼, `fetch` 응답 스트림 기반 SSE 훅. Redux·Zustand는 사용하지 않는다.
- **배포**: 개발 Vite 서버는 `/api`를 FastAPI로 프록시한다. 운영 Docker 다단계 빌드는 프론트를 빌드해 정적 산출물만 FastAPI 이미지에 복사한다. FastAPI는 `/api/*`, `/health`, Google callback을 먼저 처리하고 나머지 화면 경로는 React 진입 파일로 보낸다.
- **인증**: 기존 HttpOnly 서버 세션 쿠키와 같은 출처 정책을 사용한다. 로그인·Google 관리자 로그인(설정된 경우)·로그아웃·관리자 계정 관리 경로를 제공한다.
- **프로젝트 API**: `GET/POST /api/projects`, `POST /api/projects/upload`, `GET/PATCH/DELETE /api/projects/{project_id}`, `GET /api/demo-circuits`. 업로드는 multipart `.net`, UTF-8, 최대 5 MiB이며 사용자 파일명/경로를 서버 경로로 사용하지 않는다.
- **대화 API**: 프로젝트별 thread 생성·목록, thread 조회, `POST /api/threads/{thread_id}/runs`, `GET /api/runs/{run_id}`, `POST /api/runs/{run_id}/resume`. 한 thread에 동시 run 하나만 허용한다. run·재개는 `THREADS_ENABLED=1`의 사용자 분석 서비스(`backend/conversations/memory_service.py`)를 같은 UUID thread로 거치며(대상 부품 고정, 없으면 503). SSE 이벤트는 `run_started`, `status`, `requires_input`, `completed`, `refused`, `failed`이며 토큰 단위 출력은 보내지 않는다. 연결 복구는 상태 조회만 하며 자동 재전송하지 않는다.
- **승인·견적·사례 API**: `POST /api/messages/{message_id}/approvals`, 프로젝트 견적 목록 및 승인 메시지 견적 저장, 사용자 승인 사례 목록·삭제. 승인/견적은 판정 메시지 immutable snapshot을 참조한다.
- **가격 경계**: 화면을 열 때 `/api/prices`로 조회한다. Mouser 응답 전체를 화면 메모리에만 둔다. 가격·재고, `product_url`, `fetched_at`을 포함한 응답 필드는 브라우저 영속 캐시·DB·대화·checkpoint·견적·승인 사례·로그 등 어떤 영속 저장소에도 기록하지 않는다.
- **권한·저장**: 모든 사용자 소유 행은 `user_id` 또는 프로젝트 관계로 검증한다. 관리자 계정 관리 권한은 프로젝트·대화 열람 권한을 부여하지 않는다. 프로젝트 삭제는 소유 자료 전체를 원자적으로 삭제한다.
- **표시 계약**: 허용 단계는 `입력 확인`, `사실 확인`, `계획`, `문서 검색`, `판정`, `결과 정리`, `답 검사`, `추가 정보 필요`, `완료`, `오류`이다. 지금 서버가 보내는 단계는 `입력 확인`(시작) · `판정`(추가 정보 대기) · `완료`(완료와 거절, 거절은 상태 `refused`로 가른다) · `오류`(시스템 실패, 상태 `failed`)다(`backend/api/conversations.py`의 `STAGES`). 판정 이름은 `동일품`, `사양 동등`, `역할상 충분`, `불충족`, `문서로 확인 안 됨`을 그대로 쓴다. 모든 판정에 “같은 동작은 보장하지 않는다”를 표시한다.
- **오류**: 기존 JSON 오류 `{error:{code,message,request_id}}`와 `X-Request-ID` 계약을 따른다. 브라우저 D5 DTO 허용 필드는 `answer`, `status`, `stage`, `question_type`, `evidence`, `judgement`, `price_parts`, `refusal`, `interrupt`, `request_id`뿐이다. Plan·TaskReport의 전문이나 일부 내용, 내부 추론·chain-of-thought, 서버 경로, 내부 예외·prompt·업로드 본문·모델 원문은 반환·노출하지 않는다. 오류 화면에는 `error.message`와 `request_id`만 표시하며 내부 예외·prompt·업로드 본문·Mouser 응답을 로그에 남기지 않는다.
- **검증**: 프론트 로그인·업로드·run/SSE·결과·가격 캐시·승인 화면 테스트와 API 권한·영속 checkpoint·가격 비저장·cascade 삭제 통합 테스트를 작성한다. 각 세부 구현은 승인 설계 §12의 검증 항목을 따른다.

## AC (Given-When-Then)

**AC-01 same-origin login and session restore**
- GIVEN 활성 사용자가 브라우저에서 로그인 화면을 연 상태, WHEN 올바른 계정으로 로그인한 뒤 새로고침하거나 다시 방문하면, THEN same-origin HttpOnly 세션으로 사용자 상태가 복원되고 토큰은 브라우저 저장소에 없다. 설정된 경우 Google 관리자 로그인과 로그아웃도 기존 세션 계약을 따른다.

**AC-02 demo project creation**
- GIVEN 로그인한 사용자, WHEN 공개 데모 회로 목록의 5종 중 하나를 골라 프로젝트를 만들면, THEN 소유 사용자와 회로 출처가 연결된 프로젝트가 생성되고 작업대에서 부품 후보를 확인할 수 있다.

**AC-03 upload normalization and original disposal**
- GIVEN 로그인한 사용자가 UTF-8 KiCad `.net` 파일(5 MiB 이하)을 업로드, WHEN 검증과 정규화가 성공하거나 실패하면, THEN 성공 시 정규화 JSON·원본 SHA-256·파서 버전·시각만 프로젝트에 저장된다. 정규화 직후 원본 참조를 제거하고 D5 입력·실행 상태·checkpoint로 전달하지 않으며, 저장소 어디에도 원본 바이트·본문·로컬 경로가 없다. 5 MiB 초과는 413, 형식 오류는 400이며 실패 시 프로젝트를 만들지 않고 처리 종료 뒤 원본 참조를 제거한다.

**AC-04 D5 run completion**
- GIVEN 프로젝트와 대상 부품을 선택한 사용자, WHEN 질문을 보내면, THEN 기존 `backend/multi_agent/build.py`의 D5가 같은 thread에서 실행되고 허용된 SSE 진행 단계와 최종 `completed` 또는 `refused` 결과를 저장 후 전송한다. 한 thread의 중복 run은 409이며 내부 D5 상태 전문과 토큰 스트림은 노출되지 않는다.

**AC-05 interrupt and resume**
- GIVEN D5 판정이 추가 회로 값을 요구해 영속 checkpoint에 interrupt 상태가 저장됨, WHEN 사용자가 요구된 값을 제출하면, THEN 동일 thread/checkpoint에서 `Command(resume=...)`로 재개되고 최종 상태를 조회할 수 있다.

**AC-06 evidence and five verdicts**
- GIVEN D5가 판정 결과를 완료함, WHEN 작업대가 결과를 표시하면, THEN 각 후보는 `동일품`, `사양 동등`, `역할상 충분`, `불충족`, `문서로 확인 안 됨` 중 해당 판정을 보이고 문서명·쪽·표/행 또는 절 근거와 “같은 동작은 보장하지 않는다”를 함께 표시한다.

**AC-07 price response is not persisted**
- GIVEN 완료 결과에 `price_parts`가 있음, WHEN 사용자가 가격·재고 패널을 열면, THEN `/api/prices`를 별도 호출하고 응답을 현재 화면 메모리에만 둔다. Mouser 응답 전체와 가격·재고·`product_url`·`fetched_at`은 DB·브라우저 영속 캐시·대화·checkpoint·견적·승인 사례·로그 등 어떤 영속 저장소에도 기록되지 않는다.

**AC-08 approval before quote**
- GIVEN 판정 메시지에 대한 사용자 승인이 아직 없음, WHEN 견적 저장을 요청하면, THEN 409로 거절되고 견적 및 승인 사례가 생성되지 않는다. 승인 뒤에는 승인 snapshot을 참조하는 견적과 승인 사례를 저장할 수 있다.

**AC-09 per-user authorization**
- GIVEN 사용자 A가 소유한 프로젝트·thread·메시지·승인 자료가 존재하고 사용자 B 또는 관리자 계정이 이를 요청, WHEN 각 리소스 API를 호출하면, THEN 소유자만 접근하고 타 사용자 및 관리자 계정 관리 권한만 가진 사용자는 자료 본문을 조회할 수 없다.

**AC-10 project cascade deletion**
- GIVEN 프로젝트 소유자가 프로젝트를 삭제, WHEN 삭제가 완료되면, THEN 정규화 회로·thread·메시지·run·견적 및 프로젝트에 연결된 승인 사례가 같은 UUID 분석 thread의 checkpoint·승인 기록과 함께 한 트랜잭션에서 삭제되고 이후 목록·상세 API에서 조회되지 않는다.

## 조장 반영 요청

아래 문단은 조장 소유 `SPEC.md`에 반영할 제안이다. 이 작업에서는 `SPEC.md`와 `docs/adr/`를 수정하지 않는다.

### `SPEC.md` §2. 흐름과 그래프 제안 문단

> 같은 출처 React + Vite 화면은 로그인한 사용자가 공개 데모 회로 또는 정규화한 KiCad 넷리스트 프로젝트를 만들고 대상 부품을 선택해 질문하도록 한다. 질문은 기존 D5를 같은 thread에서 실행하며 진행·추가 정보 요구·완료·거절을 표시한다. 판정에 값이 부족하면 영속 checkpoint의 interrupt를 같은 thread에서 재개한다. 화면은 사용자용 답, 데이터시트 근거와 후보별 판정만 보여 주고 D5 판단 순서와 규칙은 변경하지 않는다.

### `SPEC.md` §4. 계약 제안 문단

> 화면은 FastAPI와 같은 출처로 제공하고 개발 중 Vite `/api` 요청은 FastAPI에 프록시한다. 프로젝트·회로·thread·run·재개·승인·견적·승인 사례 API는 [D5 프론트엔드 기능 계약](d5-frontend-service.md)을 따른다. 질문·재개는 SSE 상태 이벤트를 사용하고 연결이 끊기면 저장 run 상태를 조회하며 질문을 자동 재전송하지 않는다. 기존 HttpOnly 서버 세션과 공통 오류 응답 계약을 유지한다.

### `SPEC.md` §8.4 견적서 승인과 저장 제안 문단

> 완료된 판정 메시지를 사람이 승인한 뒤에만 승인 snapshot을 만들고 그 snapshot을 참조하는 견적서를 저장한다. 승인 전 견적 요청은 거절한다. 가격·재고와 판매처 응답 필드는 승인·견적 스키마에 두지 않으며, 견적 화면은 품번으로 가격 API를 다시 조회한다. 프로젝트 삭제는 연결된 견적과 업무 자료를 함께 삭제한다.

### `SPEC.md` §8.5 사용자별 사례 기억 제안 문단

> 승인 사례는 승인된 판정 snapshot과 사용자 소유 프로젝트에서 만든 회로 조건·판정 요약만 저장한다. 사용자별 권한을 적용하고 관리자의 계정 관리 권한은 다른 사용자의 프로젝트·대화·사례 열람을 허용하지 않는다. 사용자는 자신의 승인 사례를 조회·삭제할 수 있으며, 연결된 프로젝트 삭제 시 해당 프로젝트에 귀속된 승인 사례도 같은 트랜잭션에서 삭제한다.

### 제안 ADR 제목

`React·Vite 화면은 FastAPI와 같은 출처로 배포한다`
