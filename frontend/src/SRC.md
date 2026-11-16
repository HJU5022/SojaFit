# src

## 역할
- 넣는 것: 화면 소스(React·TypeScript·CSS).
- 넣지 않는 것: 판정·검색·인증 로직(`backend/`), 빌드 산출물, 비밀값, 단위 시험(`../tests/`).
- 담당: 서비스·운영.

## 경계
- 화면은 서버가 보낸 DTO만 그립니다. 숫자 비교와 판정은 `backend/judge/`에서만 합니다.
- 서버와의 통신은 `api.ts`의 `api()`와 `streamRun()` 둘뿐입니다. 쿠키 세션을 쓰고 자동 재전송을 하지 않습니다. 401은 `session-expired` 이벤트로 알리고 `App.tsx`가 화면 상태와 `sessionStorage`를 비웁니다.
- 경로는 라우터 라이브러리 없이 `ui.tsx`의 `navigate()` · `useLocation()`으로 다룹니다. 경로 표는 `App.tsx` 한 곳입니다.
- 스타일은 `styles.css` 한 파일의 일반 CSS입니다.

## 파일
- `SRC.md` — 이 폴더 설명.
- `main.tsx` — React 진입점·글꼴·스타일.
- `App.tsx` — 경로 표와 세션 경계. 공개 경로(`/` · `/login` · `/signup` · `/password-reset` · `/privacy`, 메일 링크용 `/verify-email` · `/reset-password`)와 로그인 뒤 경로(`/app`: 인자 없으면 새 대화 화면, `?project=&thread=`는 작업대 · `/projects` · `/settings` · `/approved` · `/admin` · `/admin/users`). 사이드바 맨 위는 "새 대화"이고 대화 목록·프로젝트 폴더는 `Conversations.tsx`가 그린다.
- `api.ts` — 쿠키 API fetch 경계·오류(`ApiError`)·SSE 연결, 판정 5종·실행 상태의 화면 표기(`verdicts` · `statuses`).
- `types.ts` — 공개 API 자료형.
- `stream.ts` — SSE 프레임 복원(UTF-8 청크 경계·종료 이벤트).
- `circuit.ts` — 프로젝트 연결에서 부품 목록과 핀·넷 뽑기. `unsupportedPartReason`은 LED·표시기·다이오드가 아닌 부품을 판정 대상에서 빼고 서버(`_require_supported_target`)와 같은 문구로 이유를 보인다(서버가 최종 판단). 시험 `../tests/circuit.test.ts`.
- `approval.ts` — 한 검토 결과의 승인 목록에서 후보 하나의 승인 상태(이 후보 승인, 다른 후보 승인)를 가르는 순수 함수. 서버는 사례가 남은 활성 승인만 돌려주므로 사례를 지우면 다시 승인할 수 있다. 시험 `../tests/approval.test.ts`.
- `display.ts` — 서버 숫자·기준식·링크를 화면 표기로 바꾸는 순수 함수: 긴 소수는 유효숫자 3자리로(받은 값은 마우스를 올리면 보임), 판정 기준식(`v_in_max * kV`)은 한국어로, 답변 속 등록된 말뭉치 인용 번호(`[79]`)는 숨기고, 링크는 http(s)만, 수량별 가격 조회 경로(`/prices?parts=…&quantity=…`)와 예상 금액 줄(적용 구간·단가·금액, 계산을 보류한 경우 안내). 시험 `../tests/display.test.ts`.
- `inputLabels.ts` — 판정 입력 코드(회로 값 이름)의 화면 이름과 입력칸 안내(`inputPlaceholder`). 이름과 뜻은 `backend/judge/rules/roles.yaml` 머리말과 짝이다.
- `ui.tsx` — 경로 이동(`navigate` · `useLocation`)·자원 훅(`useResource`)·공통 조각(로고·불러오는 중·오류·빈 상태·판정 배지·면책 문구·창·근거 출처)·회로 도식(`Circuit`). `Markdown`은 서버 답을 그리되 그림과 http(s) 아닌 링크는 글자로만 보인다.
- `Landing.tsx` — 공개 랜딩.
- `Auth.tsx` — 로그인·가입·비밀번호 재설정·Google 계정 연결.
- `Account.tsx` — 내 설정·승인 사례·관리자 계정·개인정보 안내.
- `Conversations.tsx` — 대화가 먼저인 입구. 사이드바 "대화"(모든 프로젝트의 대화, `GET /api/threads` 한 번, ⋯ 메뉴로 그 자리 이름 변경 `PATCH /api/threads/{id}` · 확인 뒤 삭제)와 "프로젝트"(같은 목록을 프로젝트별로 나눈 폴더), 새 대화 화면(넷리스트 첨부 → 파일 이름으로 `POST /api/projects/upload`, 기존 프로젝트 · 데모 회로 고르기, 409 중복이면 기존 열기 · 새로 만들기). 대화(thread)는 작업대의 첫 질문 때 생긴다.
- `Projects.tsx` — 프로젝트 목록(`/projects`: 줄마다 이름 변경 · 삭제 아이콘 버튼, 선택 칸과 일괄 삭제는 `DELETE /api/projects/{id}`를 하나씩 불러 실패만 모아 보임)과 새 프로젝트 창(데모 회로·넷리스트 업로드·샘플 넷리스트 받기 링크). `/api/demo-circuits`가 404(운영, `DEMO_MODE=0`)면 데모 회로 탭을 숨기고 넷리스트 업로드로 시작한다.
- `Workbench.tsx` — 회로 선택·검토 대화·실시간 진행·조건 재개·첨부 버전.
- `Reply.tsx` — 검토 결과 답과 조건 입력 카드.
- `Schematic.tsx` — 원본 회로도 구역(작업대 왼쪽 열). 예제 프로젝트는 `/api/demo-circuits`의 저장된 도면(`/circuit-schematics/*.png`)과 출처·라이선스를, 모든 프로젝트는 버튼을 누를 때만 `GET /api/external-circuits/schematics`(프로젝트·회로 버전·대화 문맥을 보내 서버가 부품·핀 연결이 같다고 확인한 도면만 받음)로 웹 검색한다. 이미지는 같은 출처 경로만, 링크는 http(s)만 쓴다.
- `Candidate.tsx` — 후보 상세: 조건·인용·회로 정보·승인·견적·요청 시 가격 조회.
- `styles.css` — 전체 스타일.
- `vite-env.d.ts` — Vite 환경 타입.
