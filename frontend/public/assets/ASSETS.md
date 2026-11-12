# assets

## 역할
- 넣는 것: `/assets`에서 제공하는 승인된 브랜드 이미지. Vite는 빌드 때 `dist/assets`로 복사하고 FastAPI는 기존 StaticFiles 경로로 제공한다.
- 넣지 않는 것: React 소스, 사용자 업로드, API 데이터, 서버 설정, 비밀값.

## 파일
- `ASSETS.md` — 이 폴더 설명.
- `sojafit-logo.svg` — 기존 A안 Circuit S 심볼·SOJAFIT 가로 로고. 심볼 #8A94A6, 단자와 FIT #FF5722, SOJA #EDF0F4. Segoe UI Bold의 대문자 워드마크를 path로 변환해 설치 폰트에 의존하지 않는다.
- `sojafit-icon.svg` — 같은 Circuit S 심볼과 주황 단자를 어두운 정사각 바탕에 배치한 파비콘.
