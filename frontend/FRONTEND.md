# frontend

## 역할
- 넣는 것: React + Vite + TypeScript 도구 설정과 같은 출처 화면 소스. 운영에서는 빌드 산출물만 FastAPI 이미지로 전달합니다.
- 넣지 않는 것: API·인증·판정 로직(`backend/`), D5 내부 상태와 비밀값. 화면은 서버의 안전 DTO만 표시하고 판정을 새로 계산하지 않습니다.
- 개발: `npm ci`, `npm run dev`. `/api`는 `http://localhost:8000`으로 프록시합니다. 인증 DB 없이 UI만 확인할 때는 명시적으로 `VITE_DUMMY_AUTH=1`을 설정할 수 있으며 production build에서는 이 값이 무시됩니다. 로그인부터 승인·견적까지 비영속 전체 흐름은 `npm run dev:dummy`에서만 사용할 수 있습니다.
- 확인: `npm run test:run`, `npm run build`, `npm run e2e`. e2e는 로컬 Vite와 가짜 API만 사용합니다.
- `frontend/` 도구 루트는 표준 Vite가 package.json·index.html·vite.config.ts를 함께 요구하므로 사용자 승인으로 한 종류 규칙의 좁은 예외입니다. `src/` 등은 예외가 아닙니다.

## 화면 원칙
옛 `backend/web/design.md`(11-10에 지움)에서 지금도 맞는 것만 옮겼습니다. 900px 이하 배치 · 401 처리 · 자동 재전송 금지는 [SRC.md](src/SRC.md)에 있습니다.
- 대체 판정 5종은 SPEC 3절의 화면 표기를 그대로 씁니다.
- 판정마다 근거(데이터시트의 쪽·표·행이나 공개 문서의 절)를 판정 바로 옆에 보입니다.
- 결과 화면마다 "같은 동작은 보장하지 않습니다"를 보입니다.
- 패키지가 달라 기판 수정이 필요한 후보는 판정과 따로(기판 수정 칸) 표시합니다.
- 데스크톱은 프로젝트·대화·결과의 3열입니다. 모든 입력에 label을 두고, 진행 상태는 `aria-live`, 키보드 초점은 3px 윤곽선으로 보입니다.

## 파일
- `FRONTEND.md` — 이 문서
- `package.json` — npm 의존성과 개발·빌드·테스트 명령. `elkjs`는 연결 개념도의 직교 배선과 겹침 없는 자동 배치를 브라우저 Web Worker에서 계산합니다.
- `package-lock.json` — npm 의존성 고정
- `index.html` — 한국어 React 진입 HTML
- `vite.config.ts` — React 플러그인, API 개발 프록시, jsdom 테스트와 단일 catalog의 실제 15종 연결 JSON·visual metadata를 dummy mode에 묶는 virtual module 설정
- `tsconfig.json` — TypeScript 프로젝트 참조
- `tsconfig.app.json` — 화면 TypeScript 검사 설정
- `tsconfig.node.json` — Vite 설정 TypeScript 검사 설정
- `playwright.config.ts` — 로컬 Vite Playwright 설정
- `public/` — Vite가 루트 경로로 제공하는 화면 전용 정적 이미지. [PUBLIC.md](public/PUBLIC.md)
- `e2e/` — 외부 호출 없는 브라우저 smoke. [E2E.md](e2e/E2E.md)
- `src/` — 화면 소스와 단위 테스트. [SRC.md](src/SRC.md)
