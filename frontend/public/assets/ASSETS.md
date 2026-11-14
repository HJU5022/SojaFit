# assets

## 역할
- 넣는 것: `/assets`에서 제공하는 승인된 브랜드 이미지. Vite는 빌드 때 `dist/assets`로 복사하고 FastAPI는 기존 StaticFiles 경로로 제공한다.
- 넣지 않는 것: React 소스, 사용자 업로드, API 데이터, 서버 설정, 비밀값.

## 파일
- `ASSETS.md` — 이 폴더 설명.
- `samples/` — 새 프로젝트 창이 내려 주는 샘플 넷리스트. [SAMPLES.md](samples/SAMPLES.md)
- `sojafit-icon.svg` — Circuit S 심볼과 주황 단자를 어두운 정사각 바탕에 배치한 아이콘. 파비콘과 화면 머리의 로고로 쓴다.

2026-11-13 화면 재작성 때 이전 랜딩의 캡처 3장(`landing-guide-*.png`), 기판 배경(`landing-circuit-background.png`), 가로 로고(`sojafit-logo.svg`)는 쓰는 곳이 없어 지웠다.
