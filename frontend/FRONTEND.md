# frontend

## 역할
- 넣는 것: React + Vite + TypeScript 도구 설정과 같은 출처 화면 소스. 운영에서는 빌드 산출물만 FastAPI 이미지로 전달합니다.
- 넣지 않는 것: API·인증·판정 로직(`backend/`), D5 내부 상태와 비밀값. 화면은 서버의 안전 DTO만 표시하고 판정을 새로 계산하지 않습니다.
- 개발: `npm ci`, `npm run dev`. `/api`는 `http://localhost:8000`으로 프록시합니다.
- 확인: `npm run test:run`, `npm run build`, `npm run e2e`. e2e는 로컬 Vite와 가짜 API만 사용합니다.
- `frontend/` 도구 루트는 표준 Vite가 package.json·index.html·vite.config.ts를 함께 요구하므로 사용자 승인으로 한 종류 규칙의 좁은 예외입니다. `src/` 등은 예외가 아닙니다.

## 파일
- `FRONTEND.md` — 이 문서
- `package.json` — npm 의존성과 개발·빌드·테스트 명령
- `package-lock.json` — npm 의존성 고정
- `index.html` — 한국어 React 진입 HTML
- `vite.config.ts` — React 플러그인, API 개발 프록시, jsdom 테스트 설정
- `tsconfig.json` — TypeScript 프로젝트 참조
- `tsconfig.app.json` — 화면 TypeScript 검사 설정
- `tsconfig.node.json` — Vite 설정 TypeScript 검사 설정
- `playwright.config.ts` — 로컬 Vite Playwright 설정
- `e2e/` — 외부 호출 없는 브라우저 smoke. [E2E.md](e2e/E2E.md)
- `src/` — 화면 소스와 단위 테스트. [SRC.md](src/SRC.md)
