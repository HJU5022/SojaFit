# web

## 역할
- 이 폴더: 로그인 화면과 앞으로의 입력·승인·견적 화면을 둡니다. 현재 브라우저 화면은 FastAPI가 같은 출처로 제공하는 로그인 화면입니다.
- 넣는 것: 화면 설계 문서(`design.md`), 템플릿(`templates/`), 정적 파일(`static/`). 기존 앱 범위 확장과 프론트 분리 결정은 조장 승인 후 `docs/adr/`에 기록합니다.
- 넣지 않는 것: API 로직과 라우트(`backend/main.py`, `backend/auth.py`), 판정 로직(`backend/judge/`), 그래프(`backend/graph/`).
- 담당: 서비스·운영

## 파일
- `WEB.md` — 이 폴더 설명
- `design.md` — 화면 목록과 로그인·로그아웃 흐름 및 디자인 원칙
- `templates/login.html` — 같은 출처 비밀번호 로그인·세션 확인·로그아웃 화면. Google 관리자 로그인은 서버 설정이 켜진 경우 표시
- `templates/workspace.html` — 로그인 후 사용자 넷리스트 업로드·대상 선택·내 분석 대화·조건 재개·승인 사례 화면
- `static/` — 화면 정적 파일(CSS·JS·이미지) 자리. 지금은 `.gitkeep`뿐입니다
