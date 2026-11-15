# 0018 React 작업대 하나로 화면을 통일하고 옛 `/workspace` 화면과 그 엔드포인트를 지운다

- 날짜: 2026-11-10
- 상태: 채택
- 근거: 조장 결정(11-10), 커밋 `00a036a`의 엔드포인트 정적 목록(`backend/main.py` · `backend/api/*.py`의 `@app` · `@router` 데코레이터 50개)과 `frontend/src` 사용처 대조
- 바꾸는 것: React 이전 화면 `/workspace`와 그 화면만 쓰던 엔드포인트 14개, React를 빌드하지 않았을 때 쓰던 로그인 화면을 지운다. 같은 분석 기능의 입구는 React 쪽 하나만 남긴다. 앞선 ADR의 결정은 바꾸지 않고, SPEC 4절 · README 5절에서 옛 화면을 설명하던 글을 지운다.

## 결정
- 화면은 React 작업대(`frontend/`) 하나다. `backend/web/app.py`의 `mount_frontend`가 빌드한 React를 API와 같은 출처로 내보내는 구조는 남긴다. 같은 출처라 세션 쿠키가 CORS 설정 없이 그대로 간다.
- 지우는 엔드포인트 14개(커밋 `00a036a` 기준 모두 `backend/main.py`): `GET /workspace`, `GET /api/analysis/readiness`, `GET /api/analysis/demo`, `GET` · `POST /api/circuits`, `GET` · `POST /api/threads`, `GET /api/threads/{thread_id}`, `POST /api/threads/{thread_id}/messages` · `/resume` · `/approve` · `/retry`, `GET /api/memories`, `POST /api/memories/{thread_id}/{version}/control`.
- 함께 지우는 것: 이 엔드포인트만 쓰던 코드, `backend/web/templates/workspace.html` · `login.html`, 빈 자리만 있던 `backend/web/static/`, `backend/web/design.md`, 이것들을 설명하던 문서 글.
- 남는 엔드포인트는 36개다: 인증 13, 프로젝트 · 회로 7, 분석 6, 승인 · 견적 5, `/api/me/memory` 3, 가격 1, `/health` 1.

## 이유
- 같은 분석 기능에 입구가 둘이었다. React는 `POST /api/projects/{id}/threads` → `POST /api/threads/{id}/runs` → `POST /api/runs/{id}/resume` → `POST /api/messages/{id}/approvals`, 옛 화면은 `POST /api/threads` → `/messages` → `/resume` → `/approve`를 쓰고, 둘 다 `backend/conversations/memory_service.py`의 `Conversations.message` · `resume`을 부른다(커밋 `00a036a` 기준 `backend/api/conversations.py:191`, `backend/main.py:614`). 입구가 둘이면 소유권 확인 · 출처 검사 · 본문 크기 한도 · 오류 응답 · 시험을 두 벌로 맞춰야 한다.
- 엔드포인트 50개 중 14개가 `/workspace` 한 화면만 썼고, `frontend/src`는 이 14개를 부르지 않는다.
- 로그인 뒤 열리는 화면은 React(`/app`)이고 `/workspace`는 주소창에 직접 열어야 했다. 키 없는 데모 흐름(조건 질문 → 재개 → 승인)은 `/workspace`에서만 보였고, React는 `DEMO_MODE=1`에서 합성 데모 회로가 아니면 분석을 422로 끝냈다(README 5절). 처음 여는 화면과 데모 흐름이 다른 화면에 나뉘어 있었다.
- Docker 이미지는 늘 React를 빌드한다(`Dockerfile` 2~8줄 빌드 단계, 31줄 `frontend/dist` 복사). React 빌드가 없을 때 쓰던 `login.html`은 이미지 안에서 쓰일 일이 없다.

## 결과
- 같은 변경 묶음(브랜치 `jeongun-1`)에서 위 엔드포인트 14개 · 파일 5개 · 문서 글을 지웠다. `backend/main.py`의 경로는 29개에서 15개가 됐고, React(`frontend/src` · `frontend/e2e`)가 쓰던 경로는 지운 목록에 없었다. 오프라인 시험 1065 passed · 118 skipped → 1059 passed · 110 skipped(옛 경로 시험을 지우고 React 경로 시험 5개를 더함), 레이아웃 시험 5 passed.
- 지운 뒤 키 없는 데모(`DEMO_MODE=1`)에서 React로 질문하면 늘 422다. 합성 데모 회로가 React 데모 회로 목록(`/api/demo-circuits`)에 없고, 그 넷리스트를 올려도 회로 비교가 맞지 않는다. 기록 재생 데모를 React 데모 회로에 붙이는 일로 고친다.
- 옛 화면과 함께 없어진 기능(분석 재시도, 승인 기록 정정 · 철회 · 복구 · 삭제)은 React에 같은 것이 없다.
- 남은 일: 키 없는 데모 흐름(조건 질문 → 재개 → 승인)을 React 작업대에서 보는 길이 아직 없다. 게이트 G2의 남은 일로 둔다. `docs/GATES.md` G2에 적힌 키 없는 흐름 측정(`93d29c7`)은 지우기 전 코드에서 잰 것이라, React 길이 생기면 다시 잰다.
- 2026-11-16 갱신: 이 남은 일의 React 길은 생겼다. `DEMO_REPLAY=1`일 때 React 작업대의 분석이 같은 멀티 그래프를 돌리고 LLM 응답만 기록에서 재생한다(SPEC 7절, 브라우저 시험 `frontend/tests/demo.spec.ts`). [GATES.md](../GATES.md) G2의 키 없는 흐름 측정(`93d29c7`, 11-13 `ad8612e`)은 새 화면으로 바꾸기 전 코드의 값이고, 현재 코드로는 G2를 다시 재지 않았다.
