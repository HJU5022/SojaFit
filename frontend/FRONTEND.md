# frontend

## 역할
- 넣는 것: React + Vite + TypeScript 도구 설정과 같은 출처 화면 소스. 운영에서는 빌드 산출물(`dist/`)만 FastAPI 이미지로 전달합니다.
- 넣지 않는 것: API·인증·판정 로직(`backend/`), 비밀값. 화면은 서버의 안전 DTO만 표시하고 판정을 새로 계산하지 않습니다.
- 담당: 서비스·운영.
- `frontend/` 도구 루트는 표준 Vite가 package.json·index.html·vite.config.ts를 함께 요구하므로 사용자 승인으로 한 종류 규칙의 좁은 예외입니다. `src/` 등은 예외가 아닙니다.

## 2026-11-16 새 화면으로 교체
- 조장 결정으로 화면 전체를 Codex가 저장소 밖에서 만든 새 프론트엔드(React 19 · Vite 8 · TypeScript 7)로 바꿨습니다. 이전 화면(2026-11-13 재작성본)은 git 기록에 있습니다.
- 새 화면은 `react-router` · React Query · 더미 모드 없이 `src/api.ts`의 fetch 경계와 `ui.tsx`의 경로 처리를 씁니다.

## 실행과 확인
- 개발: `npm ci`, `npm run dev`(주소 `http://localhost:5173`). `/api` · `/health`는 `http://localhost:8000`으로 프록시합니다. 백엔드는 상태를 바꾸는 요청의 Origin이 `AUTH_ORIGIN`(기본 `http://localhost:8000`)과 같아야 해서, 프록시가 Origin을 그 값으로 바꿔 보냅니다. 다른 주소의 백엔드면 `SOJAFIT_API_TARGET`(프록시 대상)과 `SOJAFIT_AUTH_ORIGIN`(Origin 값)을 정합니다.
- 확인: `npm test`(단위 시험, Node 22.18 이상), `npm run build`(타입 검사 포함), `npm run format:check`(Prettier, printWidth 100). 브라우저 시험 `npm run test:e2e`는 키 없는 데모 서버가 필요해 CI에 두지 않았습니다([TESTS.md](tests/TESTS.md)).

## 화면 원칙
- 대체 판정 5종은 SPEC 3절의 화면 표기를 그대로 씁니다. 판정 색은 판정에만 씁니다.
- 판정마다 근거(데이터시트의 쪽·표·행)를 판정 바로 옆에 보입니다.
- 결과 화면마다 "같은 동작은 보장하지 않습니다"를 보입니다.
- 데모 로그인 버튼은 서버가 데모 모드라고 답할 때(`GET /api/auth/demo` 200)만 보입니다.

## 파일
- `FRONTEND.md` — 이 폴더 설명.
- `Dockerfile.recovery` — 운영 이미지를 상속해 화면만 빌드·교체하는 복구용 이미지.
- `package.json` — npm 의존성과 실행 명령.
- `package-lock.json` — npm 의존성 고정.
- `index.html` — React 진입 HTML.
- `vite.config.ts` — React 플러그인·API 프록시.
- `playwright.config.ts` — Playwright 설정.
- `tsconfig.json` — TypeScript 설정.
- `public/` — 정적 이미지·샘플 넷리스트. [PUBLIC.md](public/PUBLIC.md)
- `src/` — 화면 소스. [SRC.md](src/SRC.md)
- `tests/` — 화면 순수 함수 단위 시험. [TESTS.md](tests/TESTS.md)
