# src

## 역할
- 넣는 것: React 진입점, 화면 경로 셸, 공통 스타일, 실제 화면 동작 단위 테스트와 테스트 설정.
- 넣지 않는 것: 서버 API·권한 판정(`backend/`), 외부 모델 호출, 사용자 토큰의 브라우저 저장, 생성된 빌드 산출물.
- `/login`은 비밀번호·설정된 Google 로그인, `/signup`은 가입(이메일·8자 이상 비밀번호·처리방침 고지 동의 필수), `/app`은 인증된 작업대, `/settings`는 내 설정(소속·직무·선호 실장 방식, SPEC 8.5)과 일반 계정의 계정 삭제(확인 뒤 `DELETE /api/me`), `/admin/users`는 관리자 전용 계정 활성 상태 관리입니다. 작업대는 프로젝트·회로 선택, D5 질문·진행·추가 입력·연결 복구, 근거와 5종 판정을 제공합니다. `projectId`·`targetRef`만 URL query에 두며 화면 이탈 시 프로젝트·run 요청을 폐기합니다. 로그아웃·탈퇴·세션 만료 때 `AuthProvider`가 React Query 캐시와 sessionStorage를 비우고, 보호 화면이 `/login`으로 replace해 주소의 프로젝트 id를 지웁니다. 900px 이하에서는 프로젝트 drawer와 결과 tab을 사용합니다.

## 파일
- `SRC.md` — 이 문서
- `main.tsx` — React·Router·QueryClient 진입점
- `App.tsx` — AuthProvider·보호 경로·역할별 탐색·로그아웃 셸
- `styles.css` — 작업대 색·글꼴·반응형·키보드 초점 스타일
- `App.test.tsx` — 비로그인 경로 차단·세션 복원·복원 오류 테스트
- `api/` — 기존 typed fetch 경계. `conversations.ts`는 thread/run DTO와 SSE frame, `quotes.ts`는 승인·가격 없는 견적·사례 API, `profile.ts`는 내 설정 `/api/me/memory`, `dummy.ts`는 명시적 개발 mode의 비영속 전체 흐름을 담당
- `auth/` — `AuthProvider.tsx`: 메모리 세션 상태 복원·로그인·가입·로그아웃·탈퇴·401 처리와 세션을 잃을 때 화면 캐시·탭 저장소 비우기, `RequireAuth.tsx`: 로그인·관리자 렌더링 경계, `AuthProvider.test.tsx`: 실제 세션 상태 변화 테스트
- `pages/` — `LoginPage.tsx`·`SignupPage.tsx`(가입·처리방침 고지 `PrivacyNotice`)·`AdminUsersPage.tsx`·`WorkbenchPage.tsx`·`SettingsPage.tsx`: 기존 API 연결 화면과 각 `*.test.tsx` 동작 테스트
- `hooks/` — `useRunStream.ts`와 테스트: SSE 순서, interrupt 재개, 연결 종료 뒤 GET 복구, 자동 재전송 금지
- `components/` — 프로젝트·회로·가격 화면, 대상 부품의 1·2단계 SVG 연결 개념도와 adapter, D5 대화·진행·추가 입력·근거·판정, 결과 옆 참고(내 설정)(`ProfileHints.tsx`), 명시적 승인·소속을 머리에 보이는 가격 없는 견적·승인 사례 확인 삭제 및 동작 테스트
- `test/` — `setup.ts`: jsdom의 jest-dom matcher와 테스트별 화면 정리, `network.ts`: 완전한 손작성 API 응답과 fetch 경계 대역, `projects.tsx`: 현재 프로젝트/데모 전체 DTO와 QueryClient·Router 테스트 렌더러
