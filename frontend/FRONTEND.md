# frontend

## 역할
- 넣는 것: React + Vite + TypeScript 도구 설정과 같은 출처 화면 소스. 운영에서는 빌드 산출물만 FastAPI 이미지로 전달합니다.
- 넣지 않는 것: API·인증·판정 로직(`backend/`), 비밀값. 화면은 서버의 안전 DTO만 표시하고 판정을 새로 계산하지 않습니다.
- 담당: 서비스·운영.
- `frontend/` 도구 루트는 표준 Vite가 package.json·index.html·vite.config.ts를 함께 요구하므로 사용자 승인으로 한 종류 규칙의 좁은 예외입니다. `src/` 등은 예외가 아닙니다.

## 2026-11-13 화면 전면 재작성
- 화면(`src/pages`, `src/components`, `src/styles`)을 처음부터 다시 만들었습니다. 이전 화면의 컴포넌트·스타일·e2e 스펙·랜딩 이미지는 모두 지웠고, 이 문서와 [SRC.md](src/SRC.md)의 이전 설명도 함께 지웠습니다.
- 서버 통신과 인증(`src/api`, `src/auth`, `src/hooks/useRunStream.ts`)은 그대로입니다. 더미 응답(`src/api/dummy.ts`)에 프로젝트 이름 변경·삭제만 더했습니다.
- 업로드 프로젝트의 원본 회로도 창은 `GET /api/external-circuits/schematics`에 프로젝트·회로 버전·대화 문맥을 보내며, 서버에서 부품 정보와 전체 핀 연결이 일치한 EDA 원본 이미지만 표시합니다. 새 버전은 이전 도면을 지우고 과거 대화는 해당 버전으로 대조합니다. 정적 예제 도면은 데모 프로젝트에만 사용합니다. 일반 참고 검색은 `reference_only=true`로 구분합니다. 더미는 프로젝트 동일성을 주장하지 않고 못 찾음을 반환하며 일반 참고 검색의 `attiny85` 2시트 예시는 유지합니다.
- 참조 번호의 끝 숫자가 달라도 서버에서 부품·전체 핀 연결의 일대일 대응을 증명한 도면은 표시하며, 도면과 업로드 파일의 참조 번호가 다를 수 있음을 안내합니다. 국소 연결이나 부품 목록만 같은 도면은 승인하지 않습니다.
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
- 질문 파일 첨부(.net·.txt, UTF-8 KiCad export, 파일당5MiB 이하)는 실제 파싱 API에 연결한다. 파일 없는 프로젝트 생성 후 채팅에서 접수하며, 첨부 전송은 같은 프로젝트의 새 회로 버전·새 대화로 이어진다. 파일만 보내면 부품 선택까지 진행하고, 질문에 특정된 다이오드가 있으면 기존 분석 경로를 한 번 실행한다. 실패하면 초안·파일을 보존한다. 이전 대화는 당시 버전 회로를 복원한다. 자세한 계약은 [작업서](../docs/specs/netlist-conversation-versions.md)를 따른다. 개발용 더미는 파일 파싱을 지원하지 않는다.

- 선택 부품·회로와 대화는 ChatPane의 하나의 스크롤에서 함께 표시하고 입력창은 하단에 유지한다. 답변은 채팅에 한 번만 표시한다. 오른쪽 ReviewDetails는 질문/품번별 탭을 열고 승인 상태·근거를 보존한다. 모바일에서는 상세 패널 접기/Escape로 채팅으로 돌아온다.
- 상세 조건은 요구값·후보값을 나란히 표시하고 기준·시험 조건·문서 근거를 펼쳐 확인한다. 불충족·확인 불가 이유와 주의 사항은 기본 화면에 남긴다. 승인 상태는 탭의 임시 상태가 아니라 서버의 메시지별 기록에서 복원하므로 탭을 닫거나 새로고침해도 유지한다.

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
