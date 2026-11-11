# web

## 역할
- 이 폴더: FastAPI가 같은 출처로 빌드한 React 화면(`frontend/dist`)을 연결하는 어댑터(`app.py`)를 둡니다. 화면 소스와 화면 원칙은 `frontend/`([FRONTEND.md](../../frontend/FRONTEND.md))에 있습니다.
- 넣는 것: API 등록 뒤 SPA를 연결하는 `app.py`. 기존 앱 범위 확장과 프론트 분리 결정은 조장 승인 후 `docs/adr/`에 기록합니다.
- 넣지 않는 것: API 로직과 라우트(`backend/main.py`, `backend/auth.py`, `backend/api/`), 판정 로직(`backend/judge/`), 그래프(`backend/graph/`), 화면 HTML·템플릿(React 이전 화면 `/workspace`와 미빌드 로그인 템플릿은 11-10에 지웠습니다).
- 담당: 서비스·운영
- `app.py`는 API 등록 후 비API GET/HEAD의 404만 React `index.html`로 바꾸며, API 응답·메서드 오류·리다이렉트를 유지합니다. 빌드가 없으면(백엔드만 띄움) 화면 주소도 공통 404 JSON입니다. Docker 이미지는 늘 React를 빌드해 넣습니다(`Dockerfile`).

## 파일
- `WEB.md` — 이 폴더 설명
- `app.py` — API 등록 뒤 assets와 `circuit-schematics` PNG를 연결하고 화면용 GET/HEAD 404에 빌드된 React index 제공. `/api`, `/health`, assets·회로도 자산의 기존 응답과 미빌드 때의 404는 유지. 회로도 누락은 index로 대체하지 않는다.
