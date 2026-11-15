# 프로젝트·이전 대화 탐색 API 계약

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(정본: [SPEC.md](../../SPEC.md) 4절 표). 목록·상세 응답의 필드 의미와 화면 동작의 상세
- 관련 문서: [d5-frontend-service.md](d5-frontend-service.md), [frontend-screen-redesign.md](frontend-screen-redesign.md), [api-error-contract.md](api-error-contract.md)
- 화면 열 주의: 2026-11-16 새 화면 교체로 이 문서가 가리키던 옛 화면 파일(`pages/` · `components/` · `hooks/` · `api/`)과 그 시험은 없다. 새 화면의 대응 파일은 [frontend/src/SRC.md](../../frontend/src/SRC.md), 새 화면 시험은 [frontend/tests/TESTS.md](../../frontend/tests/TESTS.md). 서버 쪽 계약의 정본은 [SPEC.md](../../SPEC.md)다

## Why

로그인한 회로 검토자가 프로젝트를 고르고 저장된 대화·분석 결과를 다시 열어야 한다. 화면 복원을 위해 분석을 다시 실행하면 안 된다.

## Goal

- 기존 DB 구조 변경 0개, 열람 중 분석·모델 호출 0회, 타 사용자 기록 노출 0건.
- 범위 밖: 목록 페이지네이션, 저장 기록에서 추가 입력 재개, 대화별 초안 저장.

## What

- 소유 프로젝트 목록을 API 순서대로 보인다. 최초 2개를 보이고 더보기/접기로 나머지를 연다.
- 대화 제목을 누르면 저장 메시지와 최신 run을 읽는다. 다른 메시지의 결과는 해당 run을 명시적으로 선택해 읽는다. 기록은 읽기 전용이며 새 대화의 첫 전송에서만 새 run을 만든다.
- 빈 기록·결과 없음·대상 없음·삭제된 자원·조회 오류를 구분해 보인다.
- 한 대화의 이전 질문·응답은 위로 스크롤해 이어서 읽는다(`이전 메시지 더 보기`). 읽던 위치와 입력 초안을 보존하고, 조회에 실패해도 이미 읽은 본문을 남기며 분석을 자동으로 호출하지 않는다.
- 대화 고정·해제는 이 브라우저(`localStorage`)에만 저장하며 계정·프로젝트별로 분리한다. 저장소가 막혀 있어도 고정 UI는 안내와 함께 동작한다.
- 삭제는 연관 기록의 삭제 범위를 확인한 뒤 요청한다. 실패 시 목록과 선택을 유지하고, 성공 시 현재 대화면 새 빈 대화로 전환하며 다른 대화면 현재 초안을 유지한다.
- 삭제 처리 중에는 중복 요청을 즉시 막고 대화 삭제 버튼을 비활성화하며 `삭제 중`을 표시한다. 실패 시 잠금을 해제해 재시도할 수 있고, 성공 응답 전 다른 대화·화면으로 이동하면 그 선택을 유지한다.
- 프로젝트 ID가 바뀌면 검색어를 초기화한다. 프로젝트 목록(ID 없음)과 프로젝트 사이 또는 서로 다른 프로젝트 사이의 브라우저 뒤로/앞으로 이동에서도 이전 화면의 검색어를 가져오지 않는다.

## How

| 경로 | 동작 | 근거 |
|---|---|---|
| `GET /api/projects` 외 프로젝트 API | 기존 목록·상세·생성·이름 변경·삭제 재사용 | [d5-frontend-service.md](d5-frontend-service.md) |
| `GET /api/projects/{project_id}/threads` | 소유권 확인 뒤 요약 배열 `id, project_id, title, created_at, last_activity_at, latest_run_id, status`. 마지막 활동(대화 생성·메시지·최신 run 갱신 중 최댓값) 내림차순. 제목은 첫 사용자 질문을 공백 정리해 60자로 줄이고 빈 값이면 `새 대화`. cursor·limit 없음. 조회로 마지막 활동 시각을 갱신하지 않는다 | `backend/api/conversations.py` `list_threads`, `backend/conversations/repository.py` `list_threads` |
| `GET /api/threads/{thread_id}` | `id, project_id, title, target_ref, target_locked, latest_run, messages, next_before_message_id`. 쿼리 `limit`(1~100, 기본 50), `before_message_id`. 최근 쪽부터 한 쪽을 돌려주고 쪽 안에서는 id 오름차순. 메시지는 `id, run_id, role, content, created_at`만 공개한다. 과거 조건 원문·checkpoint·원시 그래프는 반환하지 않는다. `target_locked`는 run이 하나라도 있으면 true | `backend/api/conversations.py` `thread_detail`, `backend/conversations/repository.py` `thread_detail` |
| `GET /api/runs/{run_id}` | 기존 안전 DTO로 결과 복원. 화면은 project·thread·run·message 소속을 확인한 뒤 승인에 실제 assistant `message_id`를 쓴다. 저장되지 않는 `profile_hints`·표시 조건·실시간 가격은 추측하지 않는다 | `backend/api/conversations.py` `get_run` |
| `DELETE /api/threads/{thread_id}` | 로그인·Origin·소유권 확인, 성공 204, 없는 대화·타 사용자 404, 실행 중이거나 분석 잠금 중이면 409. 분석 저장소의 thread·checkpoint·연관 기록을 함께 삭제 | `backend/conversations/repository.py` `delete_thread` |
| `POST /api/runs/{run_id}/recover` | [api-error-contract.md](api-error-contract.md)를 따른다. 조회 GET은 읽기 전용이며 질문·재개·모델을 재전송하지 않는다 | `backend/api/conversations.py` `recover_run` |

- 프로젝트·대화를 바꾸면 선택 결과를 초기화하고 늦은 응답은 폐기한다. 실행 중 전환 잠금, 로그아웃 시 캐시 제거, 저장 대화의 대상 고정을 유지한다(`frontend/src/Workbench.tsx`).
- 새 마이그레이션은 없다. 기존 `projects`, `threads`, `messages`, `runs`와 분석 대상 정보를 쓴다.

## AC

| # | Given - When - Then | 테스트 |
|---|---|---|
| 1 | 두 계정이 남의 프로젝트·대화·run 조회·삭제 - 없는 자원과 같은 404 | `tests/api/test_conversations.py`, `tests/api/test_threads.py::test_other_user_cannot_access_thread_or_resume` |
| 2 | 저장 질문·답변·판정 목록과 상세 열기 - 메시지·run 소속 일치, 분석 호출 0회 | (화면 시험은 11-16 교체로 지워짐) |
| 3 | A 조회 지연 중 B 선택 뒤 A 응답 도착 - B 대화·결과 유지 | (화면 시험은 11-16 교체로 지워짐) |
| 4 | 대상 고정 기록에서 URL 대상 변경 - 저장된 대상을 표시하고 재분석하지 않음 | (화면 시험은 11-16 교체로 지워짐) |
| 5 | 실행 중 대화 삭제 - 409, 기록 보존 | `tests/api/test_conversations.py`, `tests/api/test_deletion.py` |
| 6 | 삭제 확인 연속 클릭 - DELETE 1회와 처리 중 버튼 잠금. 현재 대화 삭제 성공 - 새 빈 대화로 전환. 다른 대화 삭제·응답 전 이동 - 현재 선택 유지. 실패 후 재시도 허용 | (화면 시험은 11-16 교체로 지워짐) |
| 7 | 브라우저에 고정한 대화 - 같은 계정·프로젝트에서만 위에 표시, 저장소가 막혀도 안내 | (화면 시험은 11-16 교체로 지워짐) |
| 8 | 같은 thread의 여러 질문 후 기록 복원·이전 쪽 읽기 - 본문이 순서대로 남고 읽던 위치·입력 초안 유지, 실패해도 기존 본문 유지, 자동 분석 호출 0 | (화면 시험은 11-16 교체로 지워짐) |
| 9 | 부품 검색 후 뒤로 가기로 프로젝트 목록 복귀 - 검색어 빈 값·프로젝트 목록 표시. 목록 검색 후 앞으로 가기 및 다른 프로젝트 사이 뒤로/앞으로 이동 - 검색어 초기화 | (화면 시험은 11-16 교체로 지워짐) |

## 구현 상태

| AC | 상태 |
|---|---|
| 1~8 | 테스트 파일이 있다. 파일 지정은 주제별 대응이며 AC 문장과 시험 함수의 일치는 대조하지 않았다 |
| 9 | 프로젝트/목록 및 서로 다른 프로젝트 사이 뒤로/앞으로 이동의 검색어 초기화 회귀로 확인 |

## 한계

- 대화 목록 페이지네이션은 없다. 대화가 많은 프로젝트의 목록은 한 번에 모두 내려온다.
- 저장 대화는 읽기 전용이고 기록에서 추가 입력 재개는 지원하지 않는다.
