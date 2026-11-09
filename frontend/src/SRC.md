# src

## 역할
- 넣는 것: React 진입점, 화면 경로 셸, 공통 스타일, 실제 화면 동작 단위 테스트와 테스트 설정.
- 넣지 않는 것: 서버 API·권한 판정(`backend/`), 외부 모델 호출, 사용자 토큰의 브라우저 저장, 생성된 빌드 산출물.
- 현재 `/login`, `/app`, `/admin/users`는 화면 셸이며 인증·사용자 관리 기능은 후속 작업입니다. `/`는 로그인 화면으로 보냅니다.

## 파일
- `SRC.md` — 이 문서
- `main.tsx` — React·Router·QueryClient 진입점
- `App.tsx` — 세 화면 경로와 공통 탐색 셸
- `styles.css` — 작업대 색·글꼴·반응형·키보드 초점 스타일
- `App.test.tsx` — 직접 경로 진입과 화면 탐색 동작 테스트
- `test/` — `setup.ts`: jsdom의 jest-dom matcher와 테스트별 화면 정리
