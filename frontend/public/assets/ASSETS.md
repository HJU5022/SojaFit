# assets

## 역할
- 넣는 것: `/assets`에서 제공하는 승인된 브랜드 이미지. Vite는 빌드 때 `dist/assets`로 복사하고 FastAPI는 기존 StaticFiles 경로로 제공한다.
- 넣지 않는 것: React 소스, 사용자 업로드, API 데이터, 서버 설정, 비밀값.

## 파일
- `ASSETS.md` — 이 폴더 설명.
- `landing-guide-project.png` — 현재 프로젝트 만들기의 넷리스트 첨부 캡처. 개발 환경에서만 표시하는 데모 생성도 포함하며 운영 기능 제공 여부를 뜻하지 않는다.
- `landing-guide-question.png` — 질문 한 칸과 연결 개념도 캡처. 개발 dummy 예시 데이터.
- `landing-guide-evidence.png` — 답변과 문서 근거 패널 캡처. 개발 dummy 예시 데이터. 세 캡처는2026-11-12 로컬1440×1000 Chrome에서 생성했다.
- `sojafit-logo.svg` — 기존 A안 Circuit S 심볼·SOJAFIT 가로 로고. 심볼 #8A94A6, 단자와 FIT #FF5722, SOJA #EDF0F4. Segoe UI Bold의 대문자 워드마크를 path로 변환해 설치 폰트에 의존하지 않는다.
- `sojafit-icon.svg` — 같은 Circuit S 심볼과 주황 단자를 어두운 정사각 바탕에 배치한 파비콘.

- `landing-circuit-background.png` — 사용자가 선택한2번 기판 사진 기반 생성 샘플을 랜딩 브랜드 배경으로 사용. 장식 이미지이며 실제 분석 회로/측정 근거가 아니다. 원본 사진 사용권은 별도 확인 대상이다.
