# web

## 역할
- 이 폴더: FastAPI가 빌드한 React 화면(`frontend/dist`)을 같은 출처로 연결하는 어댑터(`app.py`). 화면 소스와 화면 원칙은 `frontend/`([FRONTEND.md](../../frontend/FRONTEND.md))에 있다.
- 넣는 것: API 등록 뒤 SPA를 연결하는 `app.py`.
- 넣지 않는 것: API 로직과 라우트(`backend/main.py`, `backend/auth.py`, `backend/api/`), 판정 로직(`backend/judge/`), 그래프(`backend/multi_agent/`), 화면 HTML·템플릿.
- 담당: 서비스·운영

`app.py`는 API 등록 후 화면 주소의 GET/HEAD 404만 React `index.html`로 바꾸고 HTML은 `Cache-Control: no-store`로 제공한다. `/assets/`의 GET/HEAD는 `no-cache`로 매번 재검증하되 ETag/304를 유지해 고정 경로 로고의 오래된 캐시를 방지한다. API·`/health`·회로도 자산의 응답과 메서드 오류·리다이렉트는 그대로 둔다. 빌드(`frontend/dist/index.html`)가 없으면(백엔드만 띄움) 화면 주소도 공통 404 JSON이다. Docker 이미지는 React를 빌드해 넣는다(`Dockerfile`).

## 파일
| 파일 | 하는 일 |
|---|---|
| `WEB.md` | 이 문서 |
| `app.py` | `mount_frontend(app, dist)`: `/assets`와 `/circuit-schematics` PNG를 정적으로 연결하고, 화면용 GET/HEAD 404에 빌드된 React index를 돌려줌. 회로도 자산 누락은 index로 대체하지 않음 |
