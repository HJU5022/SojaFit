# 프로젝트·이전 대화 탐색 API 계약

## Why
- 로그인한 회로 검토자가 프로젝트를 선택하고 저장된 대화·분석 결과를 다시 열어야 한다. 화면 복원을 위해 분석을 다시 실행해서는 안 된다.

## Goal
- 기존 DB 구조 변경 0개, 열람 중 분석·모델 호출 0회, 타 사용자 기록 노출 0건을 유지한다.
- 목록/기록 페이지네이션·기록에서 추가 입력 재개·대화별 초안 저장·모바일 최적화는 후속 범위다.

## What
- 소유 프로젝트 목록을 기존 API 순서대로 표시한다. 최초 2개를 보이고 더보기/접기로 나머지를 연다.
- 대화 제목을 누르면 저장 메시지와 최신 run을 읽는다. 다른 메시지의 결과는 해당 run을 명시적으로 선택해서 읽는다.
- 빈 기록·결과 없음·대상 없음·삭제된 자원·조회 오류를 구분한다. 기록은 읽기 전용이며 새 대화의 첫 전송에서만 기존 POST로 생성한다.
- 고정/해제는 현재 브라우저에 저장한다. 삭제는 연관 기록 삭제 범위를 확인한 후 요청하며 실패 시 목록과 선택을 유지한다.

## How
- `GET /api/projects`와 기존 프로젝트 상세/생성/이름 변경/삭제 API를 재사용한다.
- `GET /api/projects/{project_id}/threads`: 소유권 확인 후 id·project_id·title·created_at·last_activity_at·latest_run_id·status 요약 배열. 마지막 활동 내림차순이다. 첫 사용자 질문을 공백 정리하고 60자로 줄여 제목을 만든다. 빈 제목은 새 대화다. 현재 cursor/limit은 제공하지 않는다.
- `GET /api/threads/{thread_id}`: id·project_id·title·target_ref·target_locked·latest_run·messages. 메시지는 id·run_id·role·content·created_at만 공개하며 id 오름차순이다. 과거 조건 원문·checkpoint·원시 그래프는 반환하지 않는다.
- `GET /api/runs/{run_id}`: 기존 안전 DTO로 결과를 복원한다. 화면은 project/thread/run/message 소속을 확인한 후 승인에 실제 assistant message_id를 사용한다. 저장되지 않는 profile_hints·표시 조건·실시간 가격은 추측하지 않는다.
- `DELETE /api/threads/{thread_id}`: 로그인·Origin·소유권 확인, 성공 204, 없는/타 사용자 404, 실행/분석 잠금 중 409. 분석 저장소의 thread·checkpoint·연관 기록을 기존 삭제 함수로 함께 처리한다.
- `POST /api/runs/{run_id}/recover`는 [오류 계약](api-error-contract.md)을 따른다. 조회 GET은 읽기 전용이며 질문·재개·모델을 재전송하지 않는다.
- 프로젝트/대화 전환 시 선택 결과를 초기화하고 늦은 응답을 폐기한다. 실행 중 전환 잠금, 로그아웃 캐시 제거, 기존 target 고정을 유지한다.
- DB migration은 추가하지 않는다. 기존 projects·threads·messages·runs와 분석 대상 정보를 사용한다. 조회로 마지막 활동 시각을 갱신하지 않는다.
- 정본 SPEC 4절 검토 요청: 대화 요약·상세·삭제·recover와 `/api/auth/me`의 본인 email을 반영한다. Google 일반 가입을 제외한 경로 수는 40개다.

## AC
- Given 두 계정 When 남의 프로젝트·대화·run 조회/삭제 Then 없는 자원과 같은 404다.
- Given 저장 질문·답변·판정 When 목록과 상세 열기 Then 메시지/run 소속이 일치하고 분석 호출은 0회다.
- Given A 조회 지연 When B 선택 뒤 A 응답 Then B 대화·결과를 유지한다.
- Given 대상 고정 기록 When URL 대상 변경 Then 저장된 대상을 표시하고 재분석하지 않는다.
- Given 실행 중 대화 When 삭제 Then 409이며 기록을 보존한다.
- Given 현재 대화 When 삭제 성공 Then 새 빈 대화로 전환한다. Given 다른 대화 삭제 Then 현재 초안을 유지한다.
- Given 브라우저에 고정한 대화 When 동일 계정·프로젝트로 다시 접근 Then 위에 표시한다. 다른 계정의 고정 상태는 적용하지 않는다.
