# src

## 역할
- 넣는 것: React 진입점, 화면 경로 셸, 공통 스타일, 실제 화면 동작 단위 테스트와 테스트 설정.
- 넣지 않는 것: 서버 API·권한 판정(`backend/`), 외부 모델 호출, 사용자 토큰의 브라우저 저장, 생성된 빌드 산출물.
- `/login`은 비밀번호·설정된 Google 로그인, `/app`은 인증된 작업대, `/admin/users`는 관리자 전용 계정 활성 상태 관리입니다. 작업대는 프로젝트·회로 선택, D5 질문·진행·추가 입력·연결 복구, 근거와 5종 판정을 제공합니다. `projectId`·`targetRef`만 URL query에 두며 화면 이탈 시 프로젝트·run 요청을 폐기합니다. 900px 이하에서는 프로젝트 drawer와 결과 tab을 사용합니다.

## 파일
- `SRC.md` — 이 문서
- `main.tsx` — React·Router·QueryClient 진입점
- `App.tsx` — AuthProvider·보호 경로·역할별 탐색·로그아웃 셸
- `styles.css` — 작업대 색·글꼴·반응형·키보드 초점 스타일
- `App.test.tsx` — 비로그인 경로 차단·세션 복원·복원 오류 테스트
- `api/` — 기존 typed fetch 경계. `conversations.ts`는 thread/run DTO와 SSE frame, `quotes.ts`는 승인·가격 없는 견적·사례 API를 담당
- `auth/` — `AuthProvider.tsx`: 메모리 세션 상태 복원·로그인·로그아웃·401 처리, `RequireAuth.tsx`: 로그인·관리자 렌더링 경계, `AuthProvider.test.tsx`: 실제 세션 상태 변화 테스트
- `pages/` — `LoginPage.tsx`·`AdminUsersPage.tsx`·`WorkbenchPage.tsx`: 기존 API 연결 화면과 각 `*.test.tsx` 동작 테스트
- `hooks/` — `useRunStream.ts`와 테스트: SSE 순서, interrupt 재개, 연결 종료 뒤 GET 복구, 자동 재전송 금지
- `components/` — 프로젝트·회로·가격 화면과 D5 대화·진행·추가 입력·근거·판정, 명시적 승인·가격 없는 견적·승인 사례 확인 삭제 및 동작 테스트
- `test/` — `setup.ts`: jsdom의 jest-dom matcher와 테스트별 화면 정리, `network.ts`: 완전한 손작성 API 응답과 fetch 경계 대역, `projects.tsx`: 현재 프로젝트/데모 전체 DTO와 QueryClient·Router 테스트 렌더러
