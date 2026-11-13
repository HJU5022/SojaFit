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
- 작업대의 삭제·생성·이름 변경 오류는 닫기 버튼, 재시도 시작, 화면 이동과 창 닫기에서 해제한다. 이전 화면·닫힌 창의 요청이 늦게 끝나도 이전 오류나 화면 이동을 다시 적용하지 않는다.
- 새 프로젝트 창은 어느 생성 버튼으로 열어도 이름·첨부 파일을 기본값으로 초기화한다. 생성 실패 시에는 창과 입력값을 유지해 같은 내용으로 재시도할 수 있다.
- 조건 대조 표의 항목 코드는 한 줄을 유지하고, 기준·근거 열은 너비를 나눠 가지며 긴 내용을 줄바꿈한다. 모바일 카드에서는 열 비율을 해제한다.
- 후보 판정은 채팅에 요약과 상세 보기 버튼을 표시하고, 선택한 run·품번의 판정·조건·근거를 속성 칸에서 보인다. 속성 칸의 조건은 폭에 관계없이 카드로 쌓으며, 조건별 근거와 겹치는 하단 문서 목록만 제외한다. 함께 요청한 문서 설명·추가 출처는 유지한다.
- 질문 입력창·첨부 목록·전송 안내는 검토 영역 하단에 유지한다. 대화 끝이 화면 아래에 있을 때 이동 버튼을 표시하고, 클릭하면 초안·첨부·선택을 유지한 채 끝으로 이동한다. 답변 도착이나 화면 크기 변화만으로 읽던 위치를 바꾸지 않는다.
- 채팅 답변의 숫자 코퍼스 인용은 그 답변의 evidence에 등록된 번호만 숨긴다. 코드·수치·미등록 괄호와 원본 응답은 유지한다. 문서 근거 보기로 해당 질문의 문서·쪽·표·행/절을 속성 칸에서 열고 같은 문서의 서로 다른 위치도 유지한다.
- 저장/실시간 대화에서 사용자 말풍선은 오른쪽, AI 답변과 진행 상태는 왼쪽에 둔다. 대화 본문의 아바타·이름·이메일·질문 머리말은 렌더링하지 않고 스크린리더용 발신자 설명과 기존 질문 선택은 유지한다.
- 개발 검토 화면에서 파일 드롭/선택은 같은 첨부 검증(.net·.txt/파일당5MiB 이하/비어 있지 않음/이름·크기·수정시각 중복 제외)을 거쳐 초안 목록에만 추가한다. API 확인 전에는 첨부가 있는 질문의 전송·Enter·기록 질문 자동 전송을 차단한다. 창 위 파일 드롭은 브라우저 이동을 막되 다른 활성 파일 입력의 기본 드롭은 유지한다. 창을 닫거나 문맥이 바뀌면 드래그 관찰을 정리한다.
- 820px 이하에서는 표가 카드로 쌓이고 레일이 접힙니다. 1180px 이하에서는 검토 문서의 속성 칸이 본문 아래로 내려갑니다.

## 파일
- `SRC.md` — 이 폴더 설명.
- `main.tsx` — Router · QueryClient · 글꼴 · 스타일 진입점.
- `App.tsx` — 경로 표: `/` 랜딩, `/login`, `/signup`, `/verify-email`, `/reset-password`, `/privacy`, `/app`, `/settings`, `/admin/users`.
- `dummy-circuits.d.ts` — 실제 데모 JSON을 묶는 빌드 시점 가상 모듈 타입.
- `api/` — 서버 API의 타입 있는 fetch 경계(`client` · `auth` · `admin` · `projects` · `conversations` · `quotes` · `prices` · `profile` · `externalCircuits`)와 개발 전용 `dummy.ts`, 테스트.
- `auth/` — `AuthProvider`(세션 복원·로그인·로그아웃·탈퇴) · `RequireAuth`(인증·관리자 경계)와 테스트.
- `hooks/useRunStream.ts` — 분석 실행의 시작·재개·연결 복구 상태 머신과 테스트.
- `hooks/useConversation.ts` — 검토 한 건의 화면 상태: 저장된 질문, 실행 중인 질문, 단계 이름, 첨부. 작업대와 대화 상세 조회 캐시를 공유하며 대화 전환 후 늦게 도착한 응답은 무시하고, 기록 복원 중에는 질문을 보내지 않는다.
- `lib/judgement.ts` — 판정 표기·색 이름·값과 인용 위치 표시, 등록된 숫자 인용의 화면 숨김과 후보 근거를 제외한 추가 문서 위치 목록.
- `lib/circuit.ts` — 프로젝트 연결에서 부품 목록과 대상 부품의 넷·이웃을 뽑는 순수 함수. 테스트 `circuit.test.ts`.
- `lib/inputLabels.ts` — 판정 입력 코드의 화면 이름과 항목별 단위·형식 placeholder. 알 수 없는 코드는 단위를 추정하지 않는다.
- `pages/LandingPage.tsx` — 공개 랜딩: 첫 화면 예시, 쓰는 법, 판정 5종, 신뢰 수치, 하지 않는 것.
- `pages/LoginPage.tsx` — 이메일 로그인, 서버가 켠 Google 로그인과 계정 연결, 데모 모드의 데모 사용자 버튼.
- `pages/SignupPage.tsx` · `pages/EmailActionPage.tsx` — 가입 메일 요청, 메일 링크의 비밀번호 설정과 재설정.
- `pages/PrivacyPage.tsx` — 개인정보처리방침(글은 이전과 같음).
- `pages/WorkbenchPage.tsx` — 작업대 셸: 레일, 프로젝트 목록(이름 변경·삭제), 부품 목록(맨 위 질문 칸이 질문 속 부품 번호의 검토를 열고 질문을 한 번 보낸다. 테스트 `WorkbenchPage.ask.test.tsx`), 새 프로젝트·원본 회로도·승인 사례 창. 대화 상세의 대상 부품을 주소의 선택값보다 우선해 복원하고, 프로젝트 불일치·조회 대기·오류·재시도를 구분한다. 원본 회로도 창은 예제 프로젝트에 저장된 그림을, 저장된 그림이 없는 프로젝트(올린 넷리스트, 예제 회로 목록이 404인 운영의 모든 프로젝트)에는 웹 검색을 보인다. 예제 회로 목록 응답 전에는 버튼을 숨기고, 목록이 404이면 오류 안내 없이 업로드 칸만 둔다. 테스트 `WorkbenchPage.test.tsx`.
- `pages/SettingsPage.tsx` — 내 설정 3칸 저장·삭제, 계정 삭제.
- `pages/AdminUsersPage.tsx` — 관리자 전용 계정 목록과 정지·정지 해제.
- `components/Review.tsx` — 검토 대화: 후보 요약·상세 보기, 회로, 활동과 하단 고정 입력창·대화 끝 이동. 대화/검토 내용의 스크롤과 ResizeObserver로 이동 버튼을 갱신한다. 선택한 질문·품번의 판정·조건 대조·근거·승인·견적과 공통 가격 정보를 속성 칸에 표시한다. 속성 칸 너비 조절과 상세 제목 초점 이동. 회귀 `WorkbenchPage.ask.test.tsx`.
- `components/Schematic.tsx` — 원본 회로도 이미지(`SchematicImage`)와, 누를 때만 `GET /api/external-circuits/schematics`로 찾는 웹 검색(`ExternalSchematic`). 테스트 `Schematic.test.tsx`.
- `components/ContextDiagram.tsx` — 대상 부품의 넷과 이웃을 그리는 SVG 개념도.
- `components/PriceLookup.tsx` — 누를 때만 조회하는 가격·재고.
- `components/SafeMarkdown.tsx` — 최소 마크다운 렌더러(표·굵게·목록·인용, HTML·이미지·링크는 글자로만). 표시 콜백은 본문·굵은 글씨에 적용하고 코드 구간은 보존한다. 테스트 `SafeMarkdown.test.tsx`.
- `components/ApprovedCases.tsx` — 승인 사례 목록과 확인 삭제.
- `components/AuthCard.tsx` · `components/PageShell.tsx` — 로그인 계열 화면과 설정·관리 화면의 공통 틀.
- `styles/app.css` — 전체 스타일.
- `test/` — 테스트 설정(`setup.ts`)과 도구(`projects.tsx` · `network.ts`).
