# src

## 역할
- 넣는 것: 화면 소스와 그 단위 테스트.
- 넣지 않는 것: 판정·검색·인증 로직(`backend/`), 빌드 산출물, 비밀값.
- 담당: 서비스·운영.

2026-11-13에 화면을 전면 재작성했습니다. 이전 컴포넌트(ConversationPanel · CircuitContextDiagram · JudgementTable 등)와 `styles.css` · `workers/`는 없습니다. 경위는 [FRONTEND.md](../FRONTEND.md).

## 경계
- 화면은 서버가 보낸 DTO만 그립니다. 숫자 비교와 판정은 `backend/judge/`에서만 합니다.
- `api/` · `auth/` · `hooks/useRunStream.ts`는 서버 계약입니다. 화면을 고칠 때 시그니처를 바꾸지 않습니다.
- 스타일은 `styles/app.css` 한 파일의 일반 CSS입니다. 값은 [design.md](../design.md)의 토큰과 눈금만 씁니다.
- 401을 받으면 `api/client.ts`가 `sojafit:session-expired`를 알리고 `AuthProvider`가 화면 캐시와 탭 저장소를 비웁니다. 실패한 요청을 자동으로 다시 보내지 않습니다.
- 820px 이하에서는 표가 카드로 쌓이고 레일이 접힙니다. 1180px 이하에서는 검토 문서의 속성 칸이 본문 아래로 내려갑니다.

## 파일
- `SRC.md` — 이 폴더 설명.
- `main.tsx` — Router · QueryClient · 글꼴 · 스타일 진입점.
- `App.tsx` — 경로 표: `/` 랜딩, `/login`, `/signup`, `/verify-email`, `/reset-password`, `/privacy`, `/app`, `/settings`, `/admin/users`.
- `dummy-circuits.d.ts` — 실제 데모 JSON을 묶는 빌드 시점 가상 모듈 타입.
- `api/` — 서버 API의 타입 있는 fetch 경계(`client` · `auth` · `admin` · `projects` · `conversations` · `quotes` · `prices` · `profile` · `externalCircuits`)와 개발 전용 `dummy.ts`, 테스트.
- `auth/` — `AuthProvider`(세션 복원·로그인·로그아웃·탈퇴) · `RequireAuth`(인증·관리자 경계)와 테스트.
- `hooks/useRunStream.ts` — 분석 실행의 시작·재개·연결 복구 상태 머신과 테스트.
- `hooks/useConversation.ts` — 검토 한 건의 화면 상태: 저장된 질문, 실행 중인 질문, 단계 이름, 첨부.
- `lib/judgement.ts` — 판정 표기·색 이름·값과 인용 위치 표시.
- `lib/circuit.ts` — 프로젝트 연결에서 부품 목록과 대상 부품의 넷·이웃을 뽑는 순수 함수. 테스트 `circuit.test.ts`.
- `lib/inputLabels.ts` — 판정 입력 코드의 화면 이름.
- `pages/LandingPage.tsx` — 공개 랜딩: 첫 화면 예시, 쓰는 법, 판정 5종, 신뢰 수치, 하지 않는 것.
- `pages/LoginPage.tsx` — 이메일 로그인, 서버가 켠 Google 로그인과 계정 연결, 데모 모드의 데모 사용자 버튼.
- `pages/SignupPage.tsx` · `pages/EmailActionPage.tsx` — 가입 메일 요청, 메일 링크의 비밀번호 설정과 재설정.
- `pages/PrivacyPage.tsx` — 개인정보처리방침(글은 이전과 같음).
- `pages/WorkbenchPage.tsx` — 작업대 셸: 레일, 프로젝트 목록(이름 변경·삭제), 부품 목록(맨 위 질문 칸이 질문 속 부품 번호의 검토를 열고 질문을 한 번 보낸다. 테스트 `WorkbenchPage.ask.test.tsx`), 새 프로젝트·원본 회로도·승인 사례 창. 원본 회로도 창은 예제 프로젝트에 저장된 그림을, 저장된 그림이 없는 프로젝트(올린 넷리스트, 예제 회로 목록이 404인 운영의 모든 프로젝트)에는 웹 검색을 보인다. 예제 회로 목록 응답 전에는 버튼을 숨기고, 목록이 404이면 오류 안내 없이 업로드 칸만 둔다. 테스트 `WorkbenchPage.test.tsx`.
- `pages/SettingsPage.tsx` — 내 설정 3칸 저장·삭제, 계정 삭제.
- `pages/AdminUsersPage.tsx` — 관리자 전용 계정 목록과 정지·정지 해제.
- `components/Review.tsx` — 검토 문서: 판정, 회로, 조건 대조 표, 활동과 입력창, 속성 칸(승인·견적·가격·근거). 속성 칸 너비 조절.
- `components/Schematic.tsx` — 원본 회로도 이미지(`SchematicImage`)와, 누를 때만 `GET /api/external-circuits/schematics`로 찾는 웹 검색(`ExternalSchematic`). 테스트 `Schematic.test.tsx`.
- `components/ContextDiagram.tsx` — 대상 부품의 넷과 이웃을 그리는 SVG 개념도.
- `components/PriceLookup.tsx` — 누를 때만 조회하는 가격·재고.
- `components/SafeMarkdown.tsx` — 서버 답 전체를 보이는 최소 마크다운 렌더러(표·굵게·목록·인용, HTML·이미지·링크는 글자로만). 테스트 `SafeMarkdown.test.tsx`.
- `components/ApprovedCases.tsx` — 승인 사례 목록과 확인 삭제.
- `components/AuthCard.tsx` · `components/PageShell.tsx` — 로그인 계열 화면과 설정·관리 화면의 공통 틀.
- `styles/app.css` — 전체 스타일.
- `test/` — 테스트 설정(`setup.ts`)과 도구(`projects.tsx` · `network.ts`).
