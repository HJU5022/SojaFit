# src

## 역할
- 넣는 것: React 진입점, 화면 경로 셸, 공통 스타일, 실제 화면 동작 단위 테스트와 테스트 설정.
- 넣지 않는 것: 서버 API·권한 판정(`backend/`), 외부 모델 호출, 사용자 토큰의 브라우저 저장, 생성된 빌드 산출물.
- `/login`은 데모 모드면 비밀번호 없는 "데모 사용자 A · B로 들어가기" 버튼(로컬 데모 전용 계정, 평가 계정 아님)을 위에, 그 아래 비밀번호·설정된 Google 로그인, `/signup`은 가입(이메일·8자 이상 비밀번호·처리방침 고지 동의 필수), `/app`은 인증된 작업대, `/settings`는 내 설정(소속·직무·선호 실장 방식, SPEC 8.5)과 일반 계정의 계정 삭제(확인 뒤 `DELETE /api/me`), `/admin/users`는 관리자 전용 계정 활성 상태 관리입니다. 작업대는 프로젝트·회로 선택, 질문·진행·추가 입력·연결 복구, 근거와 5종 판정을 제공합니다. `projectId`·`targetRef`만 URL query에 두며 화면 이탈 시 프로젝트·run 요청을 폐기합니다. 로그아웃·탈퇴·세션 만료 때 `AuthProvider`가 React Query 캐시와 sessionStorage를 비우고, 보호 화면이 `/login`으로 replace해 주소의 프로젝트 id를 지웁니다. 900px 이하에서는 프로젝트 drawer와 결과 tab을 사용합니다.

## 파일
- `SRC.md` — 이 문서
- `main.tsx` — React·Router·QueryClient 진입점
- `App.tsx` — AuthProvider·보호 경로·역할별 탐색·로그아웃 셸
- `styles.css` — 작업대 색·글꼴·반응형·키보드 초점 스타일
- `App.test.tsx` — 비로그인 경로 차단·세션 복원·복원 오류 테스트
- `dummy-circuits.d.ts` — 저장소의 실제 데모 연결 JSON과 visual catalog를 읽는 build-time virtual module 타입
- `api/` — 기존 typed fetch 경계. `conversations.ts`는 thread/run DTO와 SSE frame, 키 없는 데모의 기록 질문 목록(`listDemoQuestions`, 재생 모드가 아니면 404), `quotes.ts`는 승인·가격 없는 견적·사례 API, `profile.ts`는 내 설정 `/api/me/memory`, `dummy.ts`는 명시적 개발 mode의 비영속 전체 흐름을 담당합니다. 더미 프로젝트 15종은 `vite.config.ts`가 단일 catalog의 실제 `connections.json`과 `visuals.json`을 묶어 제공하므로 손으로 축약한 회로를 사용하지 않습니다.
- `auth/` — `AuthProvider.tsx`: 메모리 세션 상태 복원·로그인·가입·로그아웃·탈퇴·401 처리와 세션을 잃을 때 화면 캐시·탭 저장소 비우기, `RequireAuth.tsx`: 로그인·관리자 렌더링 경계, `AuthProvider.test.tsx`: 실제 세션 상태 변화 테스트
- `pages/` — `LoginPage.tsx`·`SignupPage.tsx`(가입·처리방침 고지 `PrivacyNotice`)·`AdminUsersPage.tsx`·`WorkbenchPage.tsx`·`SettingsPage.tsx`: 기존 API 연결 화면과 각 `*.test.tsx` 동작 테스트
- `hooks/` — `useRunStream.ts`와 테스트: SSE 순서, interrupt 재개, 연결 종료 뒤 GET 복구, 자동 재전송 금지, `failed` frame의 서버 오류 문구 표시
- `components/` — `AccessibleDialog.tsx` 공통 키보드 dialog, `LandingServiceIntroduction.tsx` 랜딩 서비스 소개, 프로젝트·회로·가격 화면, 대상 부품의 1·2단계 SVG 연결 개념도와 adapter, 대화·진행·추가 입력(역할 이름·값 한글 이름, 키 없는 데모면 기록 질문 버튼과 기록한 답으로 재개)·근거·판정(판정 표·근거·승인이 같은 후보 목록 `candidatesOf`), 결과 옆 참고(내 설정)(`ProfileHints.tsx`), 명시적 승인·소속을 머리에 보이는 가격 없는 견적·승인 사례 확인 삭제 및 동작 테스트. `circuitLayout.ts`는 네트 접점·부품·배선 그래프와 페이지 규칙(6 nets/page, 5 neighbors/net)을 만들고, `circuitLayoutClient.ts`는 Worker 결과와 안전 배치를 교체합니다.
- `workers/` — `circuitLayout.worker.ts`: `elkjs` layered/orthogonal layout을 화면 스레드 밖에서 실행해 부품 블록과 네트 접점 좌표, 직교 배선 경로를 반환합니다. 회로 데이터는 외부 API로 보내지 않습니다.
- `test/` — `setup.ts`: jsdom의 jest-dom matcher와 테스트별 화면 정리, `network.ts`: 완전한 손작성 API 응답과 fetch 경계 대역, `projects.tsx`: 현재 프로젝트/데모 전체 DTO와 QueryClient·Router 테스트 렌더러

## 회로 이미지와 공식 문서 근거
- `CircuitSchematic.tsx`는 검증된 데모 원본 회로도를 읽기 전용으로 표시하며 출처·라이선스·원본 자료·원본 저장소를 함께 보여줍니다. 데모 15종의 provenance와 자산 해시는 `data/circuits/visuals.json`에서 관리합니다. 이미지 로딩 실패 때 생성 이미지로 대체하지 않습니다.
- `CircuitSummary.tsx`의 `원본 회로도`와 `연결 개념도`는 별도 보기입니다. `WorkbenchPage.tsx`는 프로젝트 선택 전에도 `/api/demo-circuits`의 검증된 원본 15종을 우측 패널에서 고르고 미리 볼 수 있게 하고, 프로젝트 선택 후에는 demo id로 해당 원본을 연결합니다. 업로드 넷리스트에는 원본 회로도나 부품 좌표를 만들지 않으며 연결 개념도만 제공합니다.
- 연결 개념도는 고정 원형 좌표를 사용하지 않습니다. target/component와 net junction을 분리한 그래프를 ELK가 왼쪽에서 오른쪽으로 배치하고 배선을 직각으로 꺾습니다. 한 화면에 네트 6개, 네트당 이웃 부품 5개를 표시하고 나머지는 `+N`과 페이지로 탐색해 큰 회로에서도 노드가 한곳에 겹치지 않게 합니다.
- 개발 dummy에서도 15종 프로젝트를 모두 선택할 수 있고, 모든 데모는 작업대 안에서 원본 회로도와 같은 회로의 연결 개념도를 전환합니다.
- `EvidencePanel.tsx`는 선택 후보의 서버 DTO에 포함된 canonical 공식 데이터시트와 패키지 외형 페이지를 HTTPS 새 탭 링크로 표시합니다. 패키지 페이지 provenance는 오프라인으로 생성한 `data/package-outline-pages.json`에 있습니다. 링크가 없으면 문서명·인용 좌표만 표시하며 외부 PDF를 화면에 가져오지 않습니다.
- 패키지 일치 가능성은 직접 교체 보증이 아닙니다. 물리적 장착, 재배선, 어댑터 제작, 납땜 절차를 제공하지 않습니다. 개발 dummy의 후보는 실제 manifest 문서와 일치하는 `SS34L`입니다.
