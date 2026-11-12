# frontend

## 역할
- 넣는 것: React + Vite + TypeScript 도구 설정과 같은 출처 화면 소스. 운영에서는 빌드 산출물만 FastAPI 이미지로 전달합니다.
- 넣지 않는 것: API·인증·판정 로직(`backend/`), 비밀값. 화면은 서버의 안전 DTO만 표시하고 판정을 새로 계산하지 않습니다.
- 담당: 서비스·운영.
- `frontend/` 도구 루트는 표준 Vite가 package.json·index.html·vite.config.ts를 함께 요구하므로 사용자 승인으로 한 종류 규칙의 좁은 예외입니다. `src/` 등은 예외가 아닙니다.

## 2026-11-13 화면 전면 재작성
- 화면(`src/pages`, `src/components`, `src/styles`)을 처음부터 다시 만들었습니다. 이전 화면의 컴포넌트·스타일·e2e 스펙·랜딩 이미지는 모두 지웠고, 이 문서와 [SRC.md](src/SRC.md)의 이전 설명도 함께 지웠습니다.
- 서버 통신과 인증(`src/api`, `src/auth`, `src/hooks/useRunStream.ts`)은 그대로입니다. 더미 응답(`src/api/dummy.ts`)에 프로젝트 이름 변경·삭제만 더했습니다.
- 저장된 원본 회로도가 없는 프로젝트(올린 넷리스트)는 작업대의 원본 회로도 창에서 `GET /api/external-circuits/schematics`로 웹에서 찾아 보여줍니다. 더미 응답에는 이 검색과 올린 넷리스트 프로젝트 하나를 더했습니다. 더미에서는 검색어에 `attiny85`가 있으면 2시트가 나오고 없으면 못 찾음입니다.
- 모양의 기준은 [design.md](design.md) 하나입니다. 색·글자·간격·상태·금지 목록이 거기 있고, 벗어나려면 그 문서를 먼저 고칩니다.

## 실행과 확인
- 개발: `npm ci`, `npm run dev`. `/api`는 `http://localhost:8000`으로 프록시합니다.
- 서버 없이 화면만: `npm run dev:dummy`. 로그인 없이 가짜 응답으로 뜹니다(개발 빌드에서만).
- 확인: `npm run test:run`, `npm run build`. 브라우저 e2e는 지금 없습니다.
- `docker build -f frontend/Dockerfile.recovery ...`은 고정 운영 이미지를 상속해 화면만 교체하는 복구용입니다. 루트 Dockerfile의 전체 서버 빌드와 구분합니다.

## 화면 원칙
- 대체 판정 5종은 SPEC 3절의 화면 표기를 그대로 씁니다. 판정 색은 판정에만 씁니다.
- 판정마다 근거(데이터시트의 쪽·표·행)를 판정 바로 옆에 보입니다.
- 결과 화면마다 "같은 동작은 보장하지 않습니다"를 보입니다.
- 데모 로그인 버튼은 서버가 데모 모드라고 답할 때(`GET /api/auth/demo` 200)만 보입니다. 서비스(`DEMO_MODE=0`)에서는 404라 보이지 않습니다(조장 결정 11-13).
- 질문 파일 첨부(.net · .txt) 버튼은 개발 빌드에서만 보입니다. 운영에서는 `useRunStream`이 첨부를 막습니다.

## 서버가 생긴 뒤에 붙일 것
- 관리자의 이메일 가림 해제(사유 기록)와 강제 탈퇴. 서버 API가 없어 화면에 두지 않았습니다(`docs/worklog/jeongun.md` 11-12 · 11-13).
- 랜딩 신뢰 구역의 판정 일치 수치. 재측정 뒤에 넣습니다.

## 파일
- `FRONTEND.md` — 이 폴더 설명.
- `design.md` — 화면 모양의 기준(색·글자·간격·상태·움직임·금지 목록).
- `Dockerfile.recovery` — 운영 이미지를 상속해 화면만 빌드·교체하는 복구용 이미지.
- `package.json` — npm 의존성과 실행 명령.
- `package-lock.json` — npm 의존성 고정.
- `index.html` — React 진입 HTML.
- `vite.config.ts` — React·API 프록시·Vitest와 더미 회로 가상 모듈 설정.
- `tsconfig.json` — TypeScript 프로젝트 참조.
- `tsconfig.app.json` — 화면 TypeScript 설정.
- `tsconfig.node.json` — Vite TypeScript 설정.
- `public/` — 정적 이미지. [PUBLIC.md](public/PUBLIC.md)
- `src/` — 화면 소스와 단위 테스트. [SRC.md](src/SRC.md)
