# web

## 역할
- 이 폴더: FastAPI가 같은 출처로 빌드한 React 화면(`frontend/dist`)을 연결하는 어댑터(`app.py`), React 이전 화면인 `/workspace` 분석·기억 템플릿, React를 빌드하지 않았을 때 쓰는 로그인 템플릿을 둡니다. React 소스는 `frontend/`에 있습니다.
- 넣는 것: API 등록 뒤 SPA를 연결하는 `app.py`, 화면 설계 문서(`design.md`), 템플릿(`templates/`), 정적 파일(`static/`). 기존 앱 범위 확장과 프론트 분리 결정은 조장 승인 후 `docs/adr/`에 기록합니다.
- 넣지 않는 것: API 로직과 라우트(`backend/main.py`, `backend/auth.py`), 판정 로직(`backend/judge/`), 그래프(`backend/graph/`).
- 담당: 서비스·운영
- 사용자 승인 예외: 이 폴더만 기존 화면 설계 `design.md`와 정적 제공 어댑터 `app.py`를 함께 둡니다. `app.py`는 API 등록 후 비API GET/HEAD의 404만 화면으로 바꾸며, API 응답·메서드 오류·리다이렉트를 유지합니다. API 업무 로직·인증·판정 로직을 넣지 않습니다.

## 구현 상태
- 합성 데모 버튼은 명시 모드에서만 표시한다. 기억 관리의 정정은 사용자 메모이며 원본 판정을 바꾸지 않는다. 철회는 복구 가능, 기억 삭제는 Store 사본만 제거하고 대화·승인 원본을 유지한다. 처리 기록은 내용 없는 단계 지연이며 queued는 원격 수신 확인이 아니다.

## 파일
- `WEB.md` — 이 폴더 설명
- `app.py` — API 등록 뒤 assets를 연결하고 화면용 GET/HEAD 404에 빌드된 React index 또는 미빌드 로그인 HTML 제공. `/api`, `/health`, assets의 기존 응답은 유지
- `design.md` — 화면 목록과 로그인·로그아웃 흐름 및 디자인 원칙
- `templates/login.html` — 같은 출처 비밀번호 로그인·세션 확인·로그아웃 화면. Google 관리자 로그인은 서버 설정이 켜진 경우 표시
- `templates/workspace.html` — 로그인 후 업로드·대상·대화·조건 재개·승인 화면. 이전 버전의 승인 당시 입력·Store 상태·재저장 버튼을 제공하고 모델에 제공한/모델이 선택한/사후 관련 사례를 구분
- `static/` — 화면 정적 파일(CSS·JS·이미지) 자리. 지금은 `.gitkeep`뿐입니다
