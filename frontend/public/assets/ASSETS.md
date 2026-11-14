# assets

## 역할
- 넣는 것: `/assets`에서 제공하는 승인된 브랜드 이미지. Vite는 빌드 때 `dist/assets`로 복사하고 FastAPI는 기존 StaticFiles 경로로 제공한다.
- 넣지 않는 것: React 소스, 사용자 업로드, API 데이터, 서버 설정, 비밀값.

## 파일
- `ASSETS.md` — 이 폴더 설명.
- `sojafit-icon.svg` — 사용자 제공 `new_logo.png`의 격자형 S 심볼을 옮긴 투명 SVG. 원본의 밝은색·중간 회색·회색 셀을 유지하며 파비콘과 랜딩·작업대·로그인·설정/관리 화면의 공통 로고로 쓴다. `SojaFit` 글자는 기존 접근 가능한 링크 텍스트를 유지한다.

2026-11-13 화면 재작성 때 이전 랜딩의 캡처 3장(`landing-guide-*.png`), 기판 배경(`landing-circuit-background.png`), 가로 로고(`sojafit-logo.svg`)는 쓰는 곳이 없어 지웠다.
