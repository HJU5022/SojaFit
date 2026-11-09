# api

## 역할
- 넣는 것: 기존 세션을 사용하는 서비스 HTTP 라우터. 공통 오류 DTO·요청 ID 처리는 `backend/main.py`에 맡긴다.
- 넣지 않는 것: DB SQL(`backend/projects/`), 인증 구현(`backend/auth.py`), 업로드 파싱, D5 실행.
- 담당: 서비스·운영

## 파일
- `API.md` — 이 문서
- `__init__.py` — 패키지 표시
- `conversations.py` — 대화·실행·SSE API
- `projects.py` — `GET/POST /api/projects`, `POST /api/projects/upload`, `GET/PATCH/DELETE /api/projects/{project_id}`, `GET /api/demo-circuits`

모든 경로에 로그인 세션이 필요하다. 데모 POST는 `{demo_id, name}`, PATCH는 `{name}`만 받고, 다른 필드·공백 이름·200자 초과 이름·알 수 없는 데모는 공통 422로 거절한다. POST/PATCH/DELETE는 `auth.check_origin`을 적용한다. POST는 201 상세, GET 목록은 메타데이터 배열, GET/PATCH 상세는 `connections` 포함, DELETE는 204를 반환한다. 없는 프로젝트·다른 사용자 프로젝트는 같은 메시지의 공통 404다. DB 오류·DB 설정 누락은 안전한 503이다.

업로드 POST는 multipart `file` 하나와 `name` 하나만 받는다. 인증·Origin 확인 후 파일 5 MiB+1, 이름 800 bytes, 전체 multipart 5 MiB+16 KiB를 상한으로 메모리 수신하며 disk spool을 막는다. `UploadFile.read`는 최대 5 MiB+1로 한 번만 호출한다. 정규화 성공 직후 원본 버퍼를 닫고 finally에서도 모든 업로드를 닫는다. 파일명은 경로로 사용하지 않으며 저장소에는 connections/source_sha256/parser_version만 전달한다. 크기 초과는 공통 413, UTF-8·넷리스트·multipart 형식 오류는 공통 400이다. 기존 공통 handler의 413 code는 `HTTP_ERROR`이며 두 오류 모두 request_id/X-Request-ID를 포함한다.

UploadFile의 filename은 비어 있지 않아야 하며 양끝 공백을 제외해 대소문자 구분 없이 `.net`으로 끝나야 한다. 잘못된 확장자/빈 filename은 읽기 전에 공통 400으로 거절하고 파일을 닫는다. filename 자체가 없으면 multipart text field로 처리되어 허용된 text field 수를 초과하므로 공통 400으로 거절한다.

`GET/POST /projects/{project_id}/threads`, `GET /threads/{thread_id}`, `POST /threads/{thread_id}/runs`, `GET /runs/{run_id}`, `POST /runs/{run_id}/resume`는 소유권을 확인한다. 변경 요청은 Origin을 확인한다. run과 resume은 SSE로 `run_started`, `status`, 마지막 상태를 보내며 마지막 상태는 DB 저장 후 전송한다. 연결이 끊어져도 실행은 계속되고 GET은 재실행하지 않는다. 실행 중 또는 추가 정보 대기 중인 thread가 있는 프로젝트 삭제는 409다. checkpoint 삭제와 프로젝트 삭제는 별도 연결이라 완전한 원자성을 보장하지 않으며 Task 13에서 실패 복구를 검증해야 한다.
