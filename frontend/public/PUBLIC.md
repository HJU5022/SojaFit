# public

## 역할
- 넣는 것: Vite가 파일 이름을 유지한 채 웹 루트에서 제공해야 하는 화면 전용 정적 이미지.
- 넣지 않는 것: React·TypeScript 소스(`frontend/src/`), 빌드 산출물(`frontend/dist/`), 사용자 업로드, 비밀값, 서버 데이터와 판정 근거.
- 담당: 서비스·운영.

## 파일
- `PUBLIC.md` — 이 폴더 설명.
- `assets/` — Vite 개발 화면과 FastAPI 배포 화면이 `/assets`로 제공하는 브랜드 이미지. [ASSETS.md](assets/ASSETS.md)

현재 랜딩·로그인의 연결 예시는 LandingPage.tsx의 SVG로 렌더링한다. 구버전 랜딩 회로 배경 이미지는 제거했다.
