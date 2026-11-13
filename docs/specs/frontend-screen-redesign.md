# 프론트엔드 화면 구성

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(정본: [SPEC.md](../../SPEC.md) 2절 목표 사용자 흐름, 4절 계약). 화면 구성·경로·화면별 동작의 상세
- 관련 문서: [d5-frontend-service.md](d5-frontend-service.md)(기능 계약), [project-conversation-navigation.md](project-conversation-navigation.md)(프로젝트·대화 탐색), [circuit-context-diagram.md](circuit-context-diagram.md), [login-auth.md](login-auth.md), [google-user-login.md](google-user-login.md), [frontend/src/SRC.md](../../frontend/src/SRC.md)

## Why

- 대상: 회로에서 교체할 부품을 고르고, 사용 조건에 따른 대체 후보와 데이터시트 근거를 검토하는 사용자.
- 문제: 서비스 소개, 인증, 대화 중심 검토 작업의 역할이 한 화면에 섞이면 처음 방문자가 목적과 한계를 이해하기 어렵고, 분석 중에는 대상 부품·사용 조건·후보·근거의 관계를 놓친다.
- 지표: 화면 3개(랜딩, 로그인, 작업대)의 이동 경로 누락 0건, 1440×900과 390×844에서 가로 넘침 0건.

## Goal

- 랜딩에서 서비스 이해, 로그인에서 인증, 작업대에서 회로와 후보 검토를 수행한다.
- API 요청·응답, 인증·세션·권한, 실행 연결 복구, 판정·근거, 사람 승인·견적의 기능 계약은 화면이 바꾸지 않는다([d5-frontend-service.md](d5-frontend-service.md)).
- 범위 밖: 판정 규칙 변경, 주문·결제, 프로젝트 공유, 모바일 전용 앱.

## What

### 경로

| 경로 | 화면 | 접근 |
|---|---|---|
| `/` | 랜딩 | 공개 |
| `/login` | 로그인. `?google=finish`는 Google 가입·연결 완료 단계 | 공개. 로그인 상태면 `/app`으로 이동 |
| `/signup` | 이메일 인증 메일 요청 | 공개 |
| `/verify-email`, `/reset-password` | 메일 링크로 비밀번호 설정, 재설정 요청 | 공개 |
| `/privacy` | 개인정보처리방침(목차 있음) | 공개. 로그인 상태에서도 이동하지 않는다 |
| `/app` | 작업대 | 로그인 필요, 아니면 `/login`으로 replace |
| `/settings` | 내 설정 | 로그인 필요 |
| `/admin/users` | 사용자 관리 | 관리자 필요 |

근거: `frontend/src/App.tsx`, `frontend/src/auth/RequireAuth.tsx`. 인증 흐름은 [login-auth.md](login-auth.md), [google-user-login.md](google-user-login.md)가 정한다. 로그아웃·탈퇴·세션 만료 때 React Query 캐시와 `sessionStorage`를 비우고 보호 화면은 주소의 `projectId`를 남기지 않고 `/login`으로 바꾼다(`frontend/src/auth/AuthProvider.tsx`).

### 랜딩

| 영역 | 내용 |
|---|---|
| 헤더 | 로고, `서비스 소개`·`사용 방법` 앵커(`#service`, `#how-it-works`), 비로그인이면 `로그인` |
| 첫 영역 | 제목 "회로를 읽고, 대체 부품을 검토하세요.", 한 줄 설명, `회로 검토 시작` 버튼 하나(비로그인 `/login`, 로그인 `/app`), 한계 문구("같은 동작은 보장하지 않습니다", 소형 MCU 회로의 다이오드부터) |
| 서비스 소개 | 검색 실측 3칸(근거 회수율, 필요한 근거 모두 검색, 검색 중앙값)과 측정 조건 문구. 측정 범위 문구: 과거 검색 실험이며 현재 운영 답변 정확도를 뜻하지 않는다 |
| 사용 방법 | 지도형 흐름 9스텝(프로젝트 만들기, 넷리스트 첨부, 분석할 부품 선택, 질문·조건 작성, 조건 보완, 답변 확인, 후보 비교, 문서 근거, 원문 확인). 스텝을 누르면 비모달 설명창 1개가 열리고 세부 과정을 고른다. 캡처 3장(`frontend/public/assets/landing-guide-*.png`)은 예시 데이터이며 크게 보기 버튼으로 `AccessibleDialog`를 연다 |
| 하단 | 안내 문구와 `/privacy` 링크 |

- 실측 3칸의 값은 `frontend/src/pages/LandingPage.tsx`의 `metrics` 상수이고, 원시는 `evals/results/retrieval/service_r1_bits_2026-11-04.json`(`r1.test.page_recall@5`, `r1.test.all_evidence@5`, `latency.retrieve.p50`)이다. 값은 이 문서에 다시 적지 않는다. 평가 수치의 정본은 [EVAL_REPORT.md](../../EVAL_REPORT.md)다.
- 설명창은 지도 안쪽 12px 경계, 최대 460×380px에 맞춰 아래/위/옆으로 배치한다. 닫기·Escape·바깥 클릭을 지원하고 닫으면 호출한 스텝 버튼으로 초점이 돌아온다.
- 랜딩 글꼴은 로컬 번들 `@fontsource-variable/noto-sans-kr`이며 외부 글꼴 서버를 부르지 않는다.

### 로그인과 회원가입 화면

로그인은 `Google 로그인`(설정이 켜진 경우) 버튼, 이메일·비밀번호 폼, `비밀번호를 잊으셨나요?`, `회원가입` 링크, `개인정보처리방침` 링크로 이루어진다. 회원가입 링크는 운영 빌드에서도 보인다(`frontend/src/pages/LoginPage.tsx`). 동의 체크 상자는 없다. 오류 문구·Google 가입/연결 단계는 [login-auth.md](login-auth.md), [google-user-login.md](google-user-login.md)를 따른다.

### 작업대(`/app`)

| 영역 | 내용 | 근거 |
|---|---|---|
| 상단 바 | 로고, 프로젝트·부품 검색(불러온 프로젝트와 현재 회로 부품만), 계정 메뉴 | `WorkbenchPage.tsx` |
| 계정 메뉴 | 이메일 표시, `내 설정 관리`, 관리자에게만 `사용자 관리`, `로그아웃`. `개인 설정` 항목은 없다 | `frontend/src/components/AccountMenu.tsx` |
| 왼쪽 작업 메뉴 | `현재 프로젝트` 제목 버튼(프로젝트·부품 관리 창), 프로젝트 목록(최초 2개, 더보기/접기), `이전 대화` 목록, `도움말`. 프로젝트 추가(+)·새 대화(+) 아이콘은 해당 목록 영역에 마우스를 올리거나 키보드 초점이 있을 때만 보인다. 행에서 삭제 아이콘(프로젝트), 고정·삭제(대화)가 나온다. 대화 고정은 이 브라우저(`localStorage`)에만 저장한다. 폭 160~320px, 접으면 58px | `WorkbenchPage.tsx`, `styles.css` |
| 가운데 분석 대화 | 5단계 진행 표시(프로젝트, 대상 선택, 질문, 결과 검토, 승인·견적), `자료 열기` 선택창, 질문 한 칸(Enter 전송, Shift+Enter 줄바꿈, 최대 4000자), 누적 대화, 결과 링크 | `WorkbenchPage.tsx`, `frontend/src/components/ConversationPanel.tsx` |
| 오른쪽 정보 콘솔 | 사용자가 연 자료만 탭으로 쌓는다. 자료는 5종(회로, 문서 근거, 후보 비교, 진행 기록, 승인·견적)이고 종류당 최대 1탭이다. 열린 탭이 없으면 영역이 없다. 기본 폭 360px, 최소 320px, 최대는 (창 폭 - 왼쪽 메뉴 폭)의 절반이다. 경계 드래그와 좌우 방향키로 조절한다 | `WorkbenchPage.tsx` |

작업대 동작:

- 프로젝트 생성: 파일 업로드(`.net`, 5 MiB 이하는 [d5-frontend-service.md](d5-frontend-service.md))가 기본이다. 데모 회로 생성은 서버 `GET /api/demo-circuits`가 목록을 줄 때(`DEMO_MODE=1`)만 보인다. 운영(`DEMO_MODE=0`)에서는 404이고 화면은 알림 없이 업로드 칸만 둔다. 생성 성공 시 새 프로젝트를 선택하고 생성 창을 닫으며 관리 창을 자동으로 열지 않는다.
- 부품 선택: `현재 프로젝트` 관리 창의 `분석할 부품` 선택창. 선택 값은 주소 `targetRef`, 프로젝트는 `projectId`, 저장 대화는 `threadId`로 유지한다. 저장 대화를 열면 대상은 고정되고 분석을 다시 실행하지 않는다([project-conversation-navigation.md](project-conversation-navigation.md)).
- 자료 열기: 가운데 `자료 열기` 선택창이나 답변 아래 결과 링크, 답변의 `[숫자]` 인용(현재 응답 근거의 `citation_number`와 일치하는 것만)으로 연다. 같은 자료를 다시 열면 기존 탭을 활성화하고, 탭을 닫으면 가까운 탭으로 이동하며 마지막 탭을 닫으면 영역이 사라진다. 탭은 좌우·Home·End·Delete 키로 조작한다. 프로젝트·대화를 바꾸면 탭을 모두 닫는다. 프로젝트 생성 직후 넷리스트 연결 개념도는 자동으로 연다.
- 연결 개념도: 배율 50~300%, 휠·`+`/`-` 키 25% 단위, 포인터 기준 확대, 왼쪽 드래그 이동(4px 미만 이동은 노드 클릭), 우상단 맞춤 아이콘(100%·스크롤 원점). 표시 영역·격자 크기는 고정이고 그래프만 확대된다. 대상·회로·페이지가 바뀌면 100%로 돌아간다([circuit-context-diagram.md](circuit-context-diagram.md)).
- 질문 접수: 새 실행 상태가 도착하고 현재 입력 초안이 전송 당시 초안과 같을 때만 입력을 비운다. 실행 ID 없이 실패한 접수는 원문을 남긴다. 자동 재전송은 없다.
- 반응형: 1200px 미만에서 오른쪽 정보 콘솔은 대화상자로 열리고, 768px 미만에서 왼쪽 메뉴는 메뉴 버튼의 대화상자로 열린다(`window.matchMedia`, `WorkbenchPage.tsx`).
- 도움말: `기본 사용방법` 대화상자(읽기 전용, 쓰기 요청 없음). 질문창 파일 첨부 버튼은 개발 빌드(`import.meta.env.DEV`)에만 있다.

### 내 설정(`/settings`)

프로필 정보 3칸(소속, 직무, 선호 실장 방식)의 저장·칸별 삭제·모두 삭제와, 일반 계정에 한해 계정 삭제(확인 단계 있음)를 제공한다. 기억 API는 SPEC 8.5절이 정한다. 관리자에게는 계정 삭제 영역과 설정 목차가 없다(`frontend/src/pages/SettingsPage.tsx`).

### 접근성과 모션

- `AccessibleDialog`(`frontend/src/components/AccessibleDialog.tsx`): `role="dialog"`, `aria-modal`, `aria-labelledby`, 초점 가두기, Escape 닫기, 닫은 뒤 호출 요소로 초점 복귀. 가장 위 대화상자만 키 입력에 반응한다. 판정 승인 확인과 삭제 확인은 배경 클릭으로 닫히지 않는다.
- 모션 감소: `prefers-reduced-motion: reduce`에서 전환·애니메이션을 제거한다. 저장 값 `localStorage['sojafit-reduce-motion']='true'`도 작업대의 애니메이션을 끈다(변경 UI는 없다).
- 판정 의미는 색만으로 전달하지 않는다. 단계 표시는 서버가 보낸 상태만 쓰고 완료율·예상 시간을 만들지 않는다.

### 후보별 상세 보기 — 2026-11-13 사용자 요청(사진 8~9)

- 판정 답변은 구조화된 판정을 바탕으로 판정 요약·주의할 점·다음 행동을 간결하게 설명하고, 모든 후보에 `품번 상세 보기` 버튼을 제공한다. 수치 비교·새 모델 호출·서버 응답 변경은 하지 않는다. 후보가 없는 일반 문서 답변은 기존 본문을 유지한다.
- 상세 보기는 run ID와 품번을 함께 선택한다. 첫 후보를 자동 선택하지 않으며, 이전 질문의 링크도 그 질문의 판정·조건·근거·승인 대상 메시지를 연다.
- 조건 대조와 후보 주의사항은 사이드바로 옮긴다. 문서명·쪽·표·행·원본 링크는 조건별 근거 한 곳에서 확인한다. 조건의 시험 조건·판정 이유와 회로 역할 근거도 표시한다. 별도 하단 문서 목록에서 후보 근거와 중복되는 문서만 제외하며, 함께 요청한 문서 설명과 추가 출처·패키지 근거는 유지한다.
- 링크를 누르면 선택 부품 제목으로 초점을 옮겨 좁은 화면에서도 상세를 찾을 수 있게 한다. 링크 자체는 승인이나 추가 분석을 실행하지 않는다. 숫자·API·판정 규칙, 4·5번과 나머지 UI 항목은 범위 밖이다.

## How

- 사진 13번 보완: 파일 드롭을 다른 대화상자 위에 놓아도 브라우저 파일 탐색을 막으며 실제 활성 input[type=file]의 기본 드롭만 예외로 둔다. 전송 API 확인 전에는 첨부 목록이 있을 때 전송 버튼·Enter·폼 제출·기록 질문 자동 전송을 차단하고 준비 중 안내를 표시한다. 첨부 해제 시 일반 질문 전송을 복원하며 초안은 유지한다.
- 사진 13번(2026-11-13): 사용자가 UI 우선/API 연동 대기를 선택했다. 기존 개발 빌드의 질문 첨부를 재사용해 대상 부품의 검토가 열린 화면 어디에 파일을 놓아도 입력창 첨부 목록에 추가한다. 기존 `.net`·`.txt`를 대소문자 구분 없이 받으며 파일당5MiB 이하/빈 파일 제외, 이름·크기·수정시각이 같은 파일은 중복 추가하지 않는다. 파일 선택 버튼과 드롭이 같은 검증을 쓴다. 드래그 중 안내를 표시하고 놓거나 화면을 떠나면 해제한다. 기본 파일 열기를 막되 텍스트 드래그는 방해하지 않고 열린 대화상자·분석 중·기록 복원 중에는 첨부하지 않는다. 오류 안내는 닫기/정상 재시도/대화 전환에서 해제한다. 드롭만으로 업로드·전송하지 않는다. 운영의 기존 첨부 전송 차단은 유지한다. AC: GIVEN 개발 검토 화면 WHEN 파일 드롭 THEN 초안 유지·첨부 표시·요청0. GIVEN 다중/중복/잘못된 파일 WHEN 드롭 THEN 유효한 파일만 한 번씩 유지·오류 안내. GIVEN 텍스트 드래그 WHEN 드롭 THEN 기본 동작 유지. GIVEN 운영 빌드 WHEN 파일 드롭 THEN 미첨부·미지원 안내·요청0.
- 사진 12번(2026-11-13): 사용자 질문은 오른쪽에 붙는 중립색 말풍선, AI 답변은 왼쪽 말풍선으로 배치한다. 본문은 긴 문장을 읽기 쉽도록 왼쪽 정렬하고 줄바꿈한다. 대화 본문의 사용자/AI 아바타·이름·이메일·질문 번호/선택됨 머리말은 제거하며 스크린리더용 발신자 구분(`내 메시지 N`/`AI 답변`)은 유지한다. 저장/실시간 메시지에 같이 적용한다. 기존 질문 선택·후보 상세/근거 버튼·진행 표시·고정 입력창·승인 기능은 유지한다. AC: GIVEN 저장/실시간 대화 WHEN 표시 THEN 사용자 우측/AI 좌측, 프로필 이미지와 이름 미표시. GIVEN 과거 질문 WHEN 선택/상세 보기 THEN 같은 run의 값·근거 유지. 1280px·390px에서 긴 메시지 줄바꿈과 가로 넘침을 시각 확인한다.
- 사진 11번(2026-11-13): 채팅 답변의 evidence.citation_number와 일치하는 숫자 인용 표식(`[2171]`, `[2171, 2172]`)은 표시 단계에서 숨긴다. 원본 답변/API·근거 데이터·수치·미등록 숫자 괄호·코드 구간은 유지한다. 굵은 글씨·표·목록에도 적용한다. 보조 문서 근거가 있는 답변에 `문서 근거 보기` 버튼을 두고 run ID에 맞는 문서·쪽·표·행/절·원본 링크를 사이드바에서 표시한다. 같은 문서의 서로 다른 쪽은 보존하고 후보 조건 근거와의 중복 제거는 유지한다. AC: GIVEN 숫자 인용을 포함한 저장/실시간 답변 WHEN 표시 THEN 인용 번호가 보이지 않는다. GIVEN 과거 답변 WHEN 문서 근거 보기 THEN 그 run의 근거와 쪽 링크에 접근한다. GIVEN 코드/사양 값 WHEN 표시 THEN 내용 유지. 외부 링크/HTML을 답변에서 실행하지 않는 경계도 유지한다.
- 추가 조건 입력의 placeholder는 항목 코드에 맞춘다(2026-11-13). 전압 V·전류 A/µA·온도 TA/TJ=°C·커패시터 µF와 복합 시험 조건 예시를 구분하고, flag는 예/아니오·개수/권선비는 숫자로 안내한다. 허용 처짐은 서버가 V/s 문자열을 받지 않으므로 V/s 기준 숫자만 입력하도록 안내한다. 알 수 없는 코드는 임의 단위 없이 안내한다. 표시 예시만 바꾸며 자동 입력·단위 변환·판정/API는 바꾸지 않는다. AC: GIVEN i_limit/hot_test 등 추가 질문 WHEN 입력란 표시 THEN 해당 단위/형식 예시. GIVEN 입력값 작성 WHEN 계속 검토 THEN 작성한 원문을 기존 answers 계약으로 전달.
- 사진 10번(2026-11-13): 검토 내용(대화·좁은 화면의 부품 상세)은 스크롤하고 질문 입력창·첨부 목록·전송 안내는 검토 영역 하단의 별도 행에 둔다. 대화 끝이 보이는 영역 아래에 있으면 입력창 위에 `대화 맨 아래로 이동` 아이콘 버튼을 표시한다. 누르면 현재 대화 끝으로 이동하고 입력창에 초점을 둔다. 초안·첨부·선택한 후보는 유지하고 API 요청은 추가하지 않는다. 답변 도착 시 읽던 위치를 강제로 바꾸지 않으며 화면 크기·답변 높이 변경 뒤 버튼 표시를 갱신한다.
- 사진 10번 AC: GIVEN 긴 대화의 중간 WHEN 스크롤 THEN 입력창이 화면 하단에 유지된다. GIVEN 대화 끝이 아래에 있음 WHEN 이동 버튼 클릭/Enter THEN 끝으로 이동하고 초안·첨부가 유지된다. GIVEN 끝이 보임 WHEN 위치 갱신 THEN 이동 버튼을 숨긴다. 데스크톱·390px에서 배치와 마지막 답변 가림 여부를 브라우저로 확인한다.
- `Review.tsx`는 기존 CandidateDto·Checks·run 조회 캐시를 재사용한다. 선택 상태는 run ID와 품번으로 묶고, 후보가 없는 일반 문서 질문은 SafeMarkdown과 문서 목록을 유지한다. 승인 메시지 ID도 선택한 run에서 얻는다.
- 후보 답변에서 서버 `render_judgement`의 고정 역할 헤더~동작 보장 제외 문장만 요약/상세로 대체한다. 그 앞뒤 설명·미완료 안내는 유지하며, 인식하지 못한 형식은 원문을 보존한다. 서버 답변 형식 변경 시 별도 설명 필드 계약을 검토한다.
- `app.css`는 후보 링크와 좁은 사이드바의 Checks 카드 배치만 추가한다. 기존 너비 조절과 모바일 아래쪽 정보 영역은 유지한다.
- 구현 순서: 후보 선택·질문 경계·중복 제거·문서 보존·승인 회귀 추가 → 답변·선택 상태·사이드바 변경 → 카드 스타일 → 단위 테스트·빌드·모의 API 브라우저(데스크톱/390px) 확인.
- 추가 AC: GIVEN 후보 둘 WHEN 둘째 상세 보기 THEN 둘째 판정·조건·문서만 표시. GIVEN 두 질문에 같은 품번 WHEN 이전 링크/승인 THEN 이전 run의 값과 message_id 사용. GIVEN 새 대화 WHEN 전환 THEN 이전 후보 자동 선택 없음. GIVEN 후보 판정 WHEN 채팅/상세 조회 THEN 본문 표·중복 하단 목록 없음, 조건별 근거 유지. GIVEN 일반 문서 질문 WHEN 조회 THEN 원문 마크다운·출처 유지. GIVEN 미확인·불충족 후보 WHEN 상세 보기 THEN 승인 불가.

## AC

| # | Given - When - Then | 관련 테스트 파일 |
|---|---|---|
| 1 | 비로그인 사용자가 `/` 접근 - 서비스 목적·사용 방법·한계와 `회로 검토 시작`이 보이고 보호 API 요청 0 | `frontend/src/App.test.tsx`, `frontend/src/components/LandingGuide.test.tsx` |
| 2 | 랜딩 시작 선택 - 비로그인은 `/login`, 로그인은 `/app` | `frontend/src/App.test.tsx` |
| 3 | 사용 방법 스텝 클릭 - 설명창이 지도 경계 안에 열리고 Escape·바깥 클릭·닫기로 닫히며 초점이 돌아온다 | `frontend/src/components/LandingGuide.test.tsx` |
| 4 | 로그인 화면 - 성공, 실패, 처리 중 상태 구분. 중복 제출 방지, 비밀번호 비움 | `frontend/src/pages/LoginPage.test.tsx` |
| 5 | `/app` 직접 접근 비로그인 - `/login`으로 이동 | `frontend/src/auth/AuthProvider.test.tsx`, `frontend/src/App.test.tsx` |
| 6 | 프로젝트 없는 작업대 - 진입 모달 없이 프로젝트 선택·생성 가능 | `frontend/src/pages/WorkbenchPage.test.tsx` |
| 7 | 서버 데모 비활성 - 생성 창에 파일 업로드만. 생성 성공 - 새 프로젝트 선택, 관리 창 자동 열림 없음 | `frontend/src/components/CircuitSetup.test.tsx`, `frontend/src/pages/WorkbenchPage.test.tsx` |
| 8 | 자료 탭 - 초기 0개, 중복 열기는 기존 탭 활성화, 닫기·키 조작, 프로젝트 전환 시 모두 닫힘 | `frontend/src/pages/WorkbenchPage.test.tsx` |
| 9 | 오른쪽 경계 최대 드래그 - 폭이 절반 상한을 넘지 않고 접힘·창 크기 변화에 상한을 다시 계산 | `frontend/src/pages/WorkbenchPage.test.tsx` |
| 10 | 연결 개념도 - 배율 50~300%, 드래그 이동 시 노드 선택 안 됨, 맞춤으로 100%·원점 | `frontend/src/components/CircuitContextDiagram.test.tsx` |
| 11 | 완료된 분석에서 후보 선택 - 같은 후보의 판정·근거·미확인 항목을 함께 검토 | `frontend/src/components/D5Panels.test.tsx` |
| 12 | 분석 중·추가 입력·거절·오류·연결 종료 - 상태 구분, 저장 상태 조회로 복구, 질문 자동 재전송 없음 | `frontend/src/hooks/useRunStream.test.tsx` |
| 13 | 판정 승인 - 확인 단계 유지, 가격·재고는 견적에 저장하지 않는다 | `frontend/src/components/QuotePanels.test.tsx`, `frontend/src/components/D5Panels.test.tsx` |
| 14 | 질문 접수 - 동일 초안이면 입력 비움, 접수 실패 시 원문 유지 | `frontend/src/pages/WorkbenchPage.test.tsx` |
| 15 | 도움말 열기 - 현재 선택·초안 보존, 쓰기 요청 0, Escape로 닫으면 도움말 버튼으로 초점 복귀 | `frontend/src/pages/WorkbenchPage.test.tsx` |
| 16 | 내 설정 - 프로필 3칸 저장·삭제, 계정 삭제 확인 | `frontend/src/pages/SettingsPage.test.tsx` |
| 17 | 관리자 사용자 관리 - 관리자만 접근 | `frontend/src/pages/AdminUsersPage.test.tsx` |
| 18 | 키보드 사용자의 대화상자 - Tab·Shift+Tab이 안에서 순환, 닫으면 호출 요소로 복귀, 승인 확인은 배경 클릭으로 닫히지 않음 | `frontend/src/pages/WorkbenchPage.test.tsx`, `frontend/src/components/LandingGuide.test.tsx` |
| 19 | 응답의 등록된 숫자 코퍼스 인용 - 채팅에서 번호 숨김, 문서 근거 보기로 해당 질문의 사이드바 출처 열기. 코드·미등록 괄호·수치는 유지 | `frontend/src/components/SafeMarkdown.test.tsx`, `frontend/src/pages/WorkbenchPage.ask.test.tsx` |

## 구현 상태

| AC | 상태 |
|---|---|
| 1~19 | 관련 테스트 파일이 있다. 파일 지정은 주제별 대응이며 AC 문장과 시험 함수의 일치는 대조하지 않았다(한계 참조) |
| 가로 넘침 0건, 320~1440px 배치 | 브라우저 e2e 파일은 `frontend/e2e/`에 있다. 이 문서는 폭별 결과를 적지 않는다 |

## 한계

- AC와 테스트의 대응은 파일 단위로만 맞췄다. 줄 단위 일치와 현재 통과 여부(프론트 단위·e2e)는 이 문서 작성 중 실행하지 않았다(미측정).
- 랜딩 실측 3칸 값은 `service_r1_bits_2026-11-04.json`의 `r1.test.page_recall@5`·`all_evidence@5`·`latency.retrieve.p50`과 일치한다. "38문항" 표기는 이 파일에서 직접 세지 않았다(`r1.rows`는 84행, `v2.rows`는 19행이며 합 103은 `latency.retrieve.n`과 같다).
- 개인정보처리방침의 운영자·연락처·법적 근거·국외 이전 상세·시행일은 미확정 항목으로 표시되어 있고 최종 고지가 아니다(`frontend/src/pages/PrivacyPage.tsx`).
- 질문창 파일 선택·드롭 첨부 UI는 개발 빌드에만 있다. 사용자 선택에 따라 전송 API는 확인 대기이며 첨부가 있는 질문 전송은 차단한다.
- 저장 대화는 읽기 전용이며 추가 질문은 새 대화에서 시작한다. 상단 단계 표시의 현재/완료는 같은 색이다.
- 실제 모델 호출·배포 환경에서의 화면 검증 결과는 이 문서에 없다(`docs/worklog/sth.md`에 작업별 기록이 있다).
