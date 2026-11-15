# src

## 역할
- 넣는 것: 화면 소스(React·TypeScript·CSS).
- 넣지 않는 것: 판정·검색·인증 로직(`backend/`), 빌드 산출물, 비밀값, 단위 시험(`../tests/`).
- 담당: 서비스·운영.

2026-11-16에 화면 전체를 새 프론트엔드로 교체했습니다. 이전 `pages/` · `components/` · `hooks/` · `lib/` · `auth/` · `api/` 구조와 더미 모드는 없습니다. 경위는 [FRONTEND.md](../FRONTEND.md).

## 경계
- 화면은 서버가 보낸 DTO만 그립니다. 숫자 비교와 판정은 `backend/judge/`에서만 합니다.
- 서버와의 통신은 `api.ts`의 `api()`와 `streamRun()` 둘뿐입니다. 쿠키 세션을 쓰고 자동 재전송을 하지 않습니다. 401은 `session-expired` 이벤트로 알리고 `App.tsx`가 화면 상태와 `sessionStorage`를 비웁니다.
- 경로는 `react-router` 없이 `ui.tsx`의 `navigate()` · `useLocation()`으로 다룹니다. 경로 표는 `App.tsx` 한 곳입니다.
- 스타일은 `styles.css` 한 파일의 일반 CSS입니다.

## 파일
- `SRC.md` — 이 폴더 설명.
- `main.tsx` — React 진입점·글꼴·스타일.
- `App.tsx` — 경로 표와 세션 경계. 공개 경로(`/` · `/login` · `/signup` · `/password-reset` · `/privacy`)와 로그인 뒤 경로(`/app` · `/settings` · `/approved` · `/admin`).
- `api.ts` — 쿠키 API fetch 경계·오류·SSE 연결.
- `types.ts` — 공개 API 자료형.
- `stream.ts` — SSE 프레임 복원(UTF-8 청크 경계·종료 이벤트).
- `circuit.ts` — 프로젝트 연결에서 부품 목록과 핀·넷 뽑기.
- `display.ts` — 서버 숫자·기준식·링크를 화면 표기로 바꾸는 순수 함수: 긴 소수는 유효숫자 3자리로(받은 값은 마우스를 올리면 보임), 판정 기준식(`v_in_max * kV`)은 한국어로, 링크는 http(s)만. 시험 `../tests/display.test.ts`.
- `inputLabels.ts` — 판정 입력 코드(회로 값 이름)의 화면 이름. 이름과 뜻은 `backend/judge/rules/roles.yaml` 머리말과 짝이다.
- `ui.tsx` — 공통 상태 조각·경로 이동·자원 훅·판정 표기·회로 도식. `Markdown`은 서버 답을 그리되 그림과 http(s) 아닌 링크는 글자로만 보인다.
- `Landing.tsx` — 공개 랜딩.
- `Auth.tsx` — 로그인·가입·비밀번호 재설정·Google 계정 연결.
- `Account.tsx` — 내 설정·승인 사례·관리자 계정·개인정보 안내.
- `Projects.tsx` — 프로젝트 목록과 새 프로젝트 창(데모 회로·넷리스트 업로드·샘플 넷리스트 받기 링크).
- `Workbench.tsx` — 회로 선택·검토 대화·실시간 진행·조건 재개·첨부 버전.
- `Reply.tsx` — 검토 결과 답과 조건 입력 카드.
- `Schematic.tsx` — 원본 회로도 구역(작업대 왼쪽 열). 예제 프로젝트는 `/api/demo-circuits`의 저장된 도면(`/circuit-schematics/*.png`)과 출처·라이선스를, 모든 프로젝트는 버튼을 누를 때만 `GET /api/external-circuits/schematics`(프로젝트·회로 버전·대화 문맥을 보내 서버가 부품·핀 연결이 같다고 확인한 도면만 받음)로 웹 검색한다. 이미지는 같은 출처 경로만, 링크는 http(s)만 쓴다.
- `Candidate.tsx` — 후보 상세: 조건·인용·회로 정보·승인·견적·요청 시 가격 조회.
- `styles.css` — 전체 스타일.
- `vite-env.d.ts` — Vite 환경 타입.
