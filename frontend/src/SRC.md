# src

## 역할
- 넣는 것: React 진입점, 화면 경로 셸, 공통 스타일, 실제 화면 동작 단위 테스트와 테스트 설정.
- 넣지 않는 것: 서버 API·권한 판정(`backend/`), 외부 모델 호출, 사용자 토큰의 브라우저 저장, 생성된 빌드 산출물.
- `/login`은 비밀번호·설정된 Google 로그인, `/app`은 인증된 작업대, `/admin/users`는 관리자 전용 계정 활성 상태 관리입니다. `/`는 로그인 경로로 보내고 이미 로그인했다면 작업대를 엽니다. 작업대는 소유 프로젝트 목록·데모 생성·`.net` 업로드·이름 변경·명시적 삭제 확인·서버 회로 요약과 대상 참조 선택을 제공합니다. `projectId`·`targetRef`만 URL query에 두며 화면 이탈 시 프로젝트 메모리 캐시를 폐기합니다. 가격 패널의 후보 공급은 후속 범위입니다.

## 파일
- `SRC.md` — 이 문서
- `main.tsx` — React·Router·QueryClient 진입점
- `App.tsx` — AuthProvider·보호 경로·역할별 탐색·로그아웃 셸
- `styles.css` — 작업대 색·글꼴·반응형·키보드 초점 스타일
- `App.test.tsx` — 비로그인 경로 차단·세션 복원·복원 오류 테스트
- `api/` — `client.ts`: 같은 출처 fetch·공통 오류·401 세션 만료 알림·오류 표시, `auth.ts`: 로그인·me·로그아웃·Google 상태, `admin.ts`: 목록·활성 변경, `prices.ts`: no-store 가격 DTO와 호출, `projects.ts`: 프로젝트 목록/상세·데모·multipart 업로드·이름 변경·204 삭제 DTO와 호출, `client.test.ts`: 오류·자격 증명·가격 요청 경계 테스트
- `auth/` — `AuthProvider.tsx`: 메모리 세션 상태 복원·로그인·로그아웃·401 처리, `RequireAuth.tsx`: 로그인·관리자 렌더링 경계, `AuthProvider.test.tsx`: 실제 세션 상태 변화 테스트
- `pages/` — `LoginPage.tsx`·`AdminUsersPage.tsx`·`WorkbenchPage.tsx`: 기존 API 연결 화면과 각 `*.test.tsx` 동작 테스트
- `components/` — `ProjectSidebar.tsx`·`CircuitSetup.tsx`·`CircuitSummary.tsx`와 각 `*.test.tsx`: 프로젝트 선택/수정/삭제·데모/업로드/입력 폐기·서버 요약/대상 선택과 네트워크 경계 동작 테스트. `PricePanel.tsx`: 열 때 조회·닫기/품번 변경 시 폐기하는 화면 메모리 전용 패널, `PricePanel.test.tsx`: 결과·오류·빈 필드·수명·비저장 테스트
- `test/` — `setup.ts`: jsdom의 jest-dom matcher와 테스트별 화면 정리, `network.ts`: 완전한 손작성 API 응답과 fetch 경계 대역, `projects.tsx`: 현재 프로젝트/데모 전체 DTO와 QueryClient·Router 테스트 렌더러
