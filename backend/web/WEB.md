# web

## 역할
- 이 폴더: 로그인, 입력(회로와 바꿀 부품), 판정 결과와 근거, 승인, 견적서 화면을 둡니다.
- 넣는 것: 화면 HTML. 지금은 `login.html` 한 장을 `backend/main.py`가 `/`에서 그대로 내줍니다. 템플릿(`templates/`)·정적 파일(`static/`) 구조는 [DESIGN.md](DESIGN.md)에서 정합니다.
- 넣지 않는 것: API 로직(`backend/main.py`), 판정 로직(`backend/judge/`).
- 담당: 서비스·운영

## 파일
- `WEB.md` — 이 폴더 설명
- `DESIGN.md` — 화면 목록과 디자인 규칙
- `login.html` — 이메일·비밀번호 로그인 화면과 관리자용 계정 활성·비활성 패널
