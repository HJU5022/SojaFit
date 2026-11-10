# 사용자별 분석 thread · 승인 기록 · 사용자 사실 기억

**11-09 변경:** 장기 기억을 승인한 판정 사례에서 사용자 사실 3칸으로 바꿨다(아래 "사용자 사실 기억", SPEC 8.5). 승인 사례는 이제 승인 기록이다. 승인 원본과 승인·`/api/memories` 관리 API는 그대로 두지만 새 분석에 넘기지 않고(`approved_memories`는 빈 목록) 승인 때 Store에 쓰지 않는다. 그 아래 절의 "승인 사례 기억" 설계·AC 중 "(11-09 대체)"를 붙인 줄은 그 전 설계다.

**11-10 변경:** React만 남기기로 하고(조장 결정) React 이전 화면 `/workspace`(`backend/web/templates/workspace.html`)와 그 경로(`/api/circuits` · `/api/threads` 목록 · 상세 · `messages` · `resume` · `approve` · `retry` · `/api/memories` · `/api/memories/{thread}/{version}/control` · `/api/analysis/readiness` · `/api/analysis/demo`)를 지웠다. 지금 분석 입구는 React 대화 API(`POST /api/threads/{id}/runs` · `POST /api/runs/{id}/resume`, SPEC 4절)이고, 승인은 React의 `POST /api/messages/{id}/approvals`다. 옛 승인 기록(`sojafit_agent.approvals`)은 새로 쓰는 경로 없이 삭제 · 보관 기간 규칙만 따르며, 정정 · 철회 · 재시도 기능은 없다. 아래 절의 화면 · 경로 설명은 11-09까지의 기록이다.

상태: 로컬·공유 DB·운영 0% 시험 배포 검증 수행. 조장 리뷰·정본 문서 반영·병합은 남는다. 목표 시각: 2026-11-09 17:30 KST. 사용자는 분석 한 건당 thread 하나와 사용자 넷리스트 업로드·화면 연결을 선택했다. 최신 증거·한계는 [운영 검증 결과](../research/thread-memory-operations-review.md)와 [작업 기록](../worklog/sth.md)을 따른다. Why의 미구현 설명은 착수 당시 상태다.

## Why
- 로그인 사용자가 자기 회로의 특정 부품 분석을 이어가고, 승인한 사례를 다음 분석에서 찾아볼 수 있어야 한다.
- 현재 로그인은 사용자 ID를 확인하지만 대화 API, 소유권 검사, DB Checkpointer, Store 연결이 없다.
- 검증 지표: 다른 사용자 접근 허용 0건, 재접속·저장소 재연결 후 상태 유실 0건, 같은 결과 중복 승인 시 기억 1건.

## Goal
- 2026-11-09 마무리 범위: 관련 승인 사례 참조·관리까지 완료한다. 모든 대화 자동 기억/자유로운 과거 기록 질의는 포함하지 않는다. 사용자가 기본 보관 정책으로 자동 삭제 없음·직접 철회/삭제를 선택했다.
- 분석 한 건 = thread 하나. 사용자 한 명은 여러 thread를 소유한다.
- 생성·목록·상세·질문·중단 재개·결과 승인과 자기 승인 사례 조회를 API로 제공한다.
- 기존 비밀번호·Google 로그인과 세션을 그대로 사용한다.
- 17:30까지 구현·검증을 목표로 하되 로컬 검증, 공유 DB 적용, 배포 검증을 구분해 보고한다.
- 로그인 후 넷리스트 업로드, 대상 선택, 내 분석 목록·질문·재개·승인·관련 사례를 같은 출처 화면에서 제공한다.
- Out of Scope: 한 thread 안의 여러 분석, 회원가입, 기존 업무 표 초안 전체 적용, 견적서 발행·가격 저장, 대화에서 기억 자동 학습(사용자 사실은 설정 API로만 쓴다).

## What
- (11-09 대체) 승인 기억 활용: 새 질문 실행 전에 인증 사용자의 같은 품번 승인 사례를 최대 5건 조회해 별도 그래프 상태로 전달한다. Supervisor·판정 읽기·답변 생성 모델이 참고하되 과거 조건을 현재 조건으로 자동 채우거나 승인을 사양 근거로 쓰지 않는다. 숫자 판정과 현재 근거 검증은 유지한다.
- 사용자가 회로·대상 부품을 정해 분석 thread를 만들고 질문한다. 조건 보충·후보 비교는 같은 thread를 쓴다.
- 조건 질문 interrupt는 같은 thread에서 재개한다. 다른 회로·대상 분석은 새 thread를 만든다.
- 서버가 생성한 현재 판정 결과를 사용자가 명시적으로 승인하면 그 결과와 승인 시점을 남기고 자기 namespace에 사례를 저장한다.
- 승인 사례는 다음 분석의 역할·품번으로 최대 5건을 찾아 결과와 함께 별도 참고 자료로 표시하고, 자기 사례 목록으로도 조회한다. 과거 사용자 승인은 사양의 참이나 대체 적합성을 보증하지 않는다.
- 다른 사용자·없는 thread는 동일한 404, 미인증은 401, 처리 중 중복 실행·미승인 과거 결과의 최초 승인은 409로 처리한다. 이미 승인한 과거 결과는 Store 재저장을 허용한다.
- DB·Store 실패를 성공으로 응답하지 않는다. 사용자 입력, 토큰, 접속 문자열을 오류·로그에 노출하지 않는다.

## How
### 2026-11-09 기억 관리 완료 계약
- 정정은 승인 원본을 바꾸지 않는 사용자 정정 메모(최대 1000자)다. 원래 조건·판정과 구분하고 모델에 비신뢰 과거 데이터로 전달한다. 새 사양값·현재 조건으로 자동 채우지 않는다.
- 철회는 모델 참조/기억 목록에서 즉시 제외하며 복구할 수 있다. 삭제는 Store 사본을 제거하고 삭제 표식을 남겨 같은 승인 재요청으로 되살아나지 않게 한다. 기존 대화·불변 승인 원본은 보존한다. 화면에서 '기억에서 삭제(대화·승인 원본 유지)'를 명시하며 전체 대화/계정 삭제로 오인시키지 않는다. 자동 삭제는 아래 "보관 · 삭제"(11-09, 마지막 활동 뒤 60일)만 따른다.
- lifecycle의 권한은 thread 소유자다. 상태가 철회/삭제면 Store 삭제 실패·과거 checkpoint의 기억 사본이 있어도 이후 모델 입력/참조로 사용하지 않는다. 과거 완료 답변 문장은 소급 재작성하지 않는다.
- 판정 사례 승인과 견적 승인·저장은 별개임을 승인 UI/API 설명에 표시한다. NOT_VERIFIED 과거 사례를 현재 적합성 근거로 삼지 않는다.

### 실행 계획: 장기기억 마무리
Goal: 기존 분석 서비스의 사례 기억을 평가자 시연·데모·CI·관측·관리까지 연결하고 검토 가능한 로컬 커밋으로 남긴다.
Architecture: 기존 Conversations/DB/그래프를 유지한다. 고정 응답 데모는 별도 DEMO_SCENARIOS=1과 DEMO_MODE=1을 모두 요구해 기존 BM25 실제 모델 평가를 보존한다. lifecycle은 승인 원본 옆 상태/정정 메모로 관리하고 실제 모델 입력 직전에 권한·상태를 재확인한다.
Tech stack: 기존 FastAPI/LangGraph/PostgreSQL/uv/Docker/Langfuse, 새 패키지 없음.
Spec: 이 문서와 evaluator-demo-readiness.md. 현재 사용자 요청은 준비안의 실행 승인으로 해석한다. 자동 삭제 없음은 사용자 선택, 삭제 범위를 기억 참조/Store로 한정하고 원본을 보존하는 것은 명시적 UI 표시를 전제로 한 구현 결정이다.
Constraints: STH 유지, 동결셋/주요 문서 수정 금지, 새 파일만 SOJAFIT 등록, 기존 데이터 자동 삭제 없음, 운영 트래픽 0% 유지, 조장만 병합, 자격증명 로그 금지.
Review focus: 철회/삭제 후 pending/retry 기억 재사용, 삭제의 재승인 부활, A/B 교차 관리, demo의 유료 fallback, 관측 실패의 저장 실패 전파.
- [x] 1. 범위/승인 용어/보관 정책 안내: workspace·작업서, 기존 API markup 검사.
- [x] 2a. services/demo.py+data/demo/scenarios.json: 합성 시나리오 입력의 명시 모드와 허용 질문·회로 검증, 기존 그래프/판정 재사용. tests/api/test_threads.py·tests/services/test_llm.py에서 키 있어도 외부호출 0/미등록 거부 RED→GREEN.
- [x] 2b. Dockerfile·Compose·명시 bootstrap·CI: 빈 격리 DB에서 checkpoint 준비/데모 시나리오/THREADS_ENABLED, TEST_THREAD_DATABASE_URL 설정. 실제 API·화면 재개/승인/A·B, 새 Compose project cold-start 검증.
- [x] 2c. services/langfuse_prompts.py·Conversations: 인증 user/thread/version/request/trace/단계별 실행 시간을 내용 없이 저장·반환하고 선택적 Langfuse 전달. DB/trace 전송 장애가 판정·승인을 잃게 하지 않는 검사와 실제 trace 증거.
- [x] 3. db/016_memory_controls.sql·017_analysis_events.sql와 Conversations/main/workspace: 정정/철회/복구/기억 삭제/보관안내. UI·소유권·Store 실패·pending/retry 참조 차단·멱등/재승인 부활 거부 RED→GREEN. 공유 DB는 가산 적용 전 현행 구조 확인.
- [x] 4. 판정 사례 승인/견적 기능 경계 문구와 API 설명 대조. lifecycle·기억 모델 입력 통합 시험.
- [x] 5. 관련/전체 검사·동결해시·비밀값검사·독립 리뷰 후 목적별 로컬 커밋. 조장 반영용 SPEC/GATES 변경 지점·검증/배포/남은 한계를 정리한다. 병합은 실행하지 않는다.
각 작업의 실제 명령/결과/설계 조정은 docs/worklog/sth.md에 남기며 새 우려가 없으면 통과한 검사를 반복 확대하지 않는다.

### 운영 보완 단계 (2026-11-09 사용자 요청)
1. 기억 인용: 모델의 현재 분석 본문에서는 승인사례 출처를 근거로 허용하지 않는다(다른 현재 출처와 섞어도 거부). 모델이 참고한 사례는 별도 memory_refs 필드로 받고, 서버가 전달한 최대 5건의 소유권 확인 사례 ID와 대조한다. 화면/API의 과거 기록은 승인 원본으로 구성하고 현재 사양 근거와 분리한다. 이는 기억을 현재 근거로 사용하는 경로 차단이며 데이터시트 모든 문장의 의미 정확도 보증은 아니다.
2. 최종 조건: 질문·명시 조건·재개 답변·사용자가 고른 역할·판정에 실제 사용한 값/단위·조건을 버전별 불변 승인 원본에 남긴다. 예전 원본의 미보관 값은 추측해 채우지 않는다. 모델용 문맥은 필드별로 제한해 긴 질문이 최종 조건을 밀어내지 않게 한다.
3. 운영 제한: 일반 분석 실행에도 시간/호출/출력/예약 비용 상한과 사용자별 호출 빈도·일일 예약 예산을 DB에서 적용한다. 실패 재시도와 조건 재개도 포함하며 다중 서버에서 한도를 우회하지 못하게 한다. 상한값은 환경설정으로 검증하며 예약액은 청구액이 아니다. 요청 식별자로 비밀값 없는 실패 종류를 기록한다.
4. 화면 복구: 승인 원본과 Store 저장 상태를 버전별로 표시하고 이전 승인 재저장 버튼을 제공한다. 실제 모델 참조 목록과 사후 관련 사례를 구분한다. 이전 버전 최초 승인은 계속 금지한다.
5. 시험 배포: 사용자가 기존 Cloud Run 운영 트래픽 0% 시험 배포를 선택했다. 먼저 로컬 AC/전체 테스트, 대상 서비스/DB/비밀 참조/롤백 경로 확인 후 별도 시험 revision으로 검증한다. 운영 트래픽 이동은 하지 않는다.

### 접근 방식과 결정
- 선택됨: 분석 하나와 thread 하나를 1:1로 연결. 여러 분석을 한 대화에서 관리하는 대안은 문맥·승인 대상 관리가 추가되어 이번 범위에서 제외한다.
- 구현 제안: 기존 업무 표 초안은 현재 코퍼스와 충돌하므로 적용하지 않는다. 독립된 분석 thread 메타데이터 표에 소유자·고정 회로/대상·현재 결과 버전을 보관하고, 별도 승인 표에 버전별 불변 스냅샷을 보관한다. 업무 표와 연결은 후속 통합으로 명시한다.
- 구현 제안: PostgreSQL의 비공개 전용 스키마에서 thread 메타데이터, PostgresSaver, PostgresStore를 관리한다. public 코퍼스·인증 표는 유지하고 users를 참조한다. 라이브러리 내부 표는 라이브러리 setup으로만 생성한다.
- 구현 제안: 기존 서버가 DB 없이도 health/login 화면을 제공하는 동작을 보존하도록 명시적으로 켠 환경에서만 thread 런타임을 초기화한다. 스키마 생성은 서버 시작과 분리한 준비 명령으로 수행한다.

### 신뢰 경계
- FastAPI Depends(auth.current_user_id)로 검증한 정수 users.id만 소유자로 쓴다. 그래프에는 문자열로 전달한다.
- thread_id는 서버가 UUID로 발급한다. users.id나 세션 토큰을 thread_id로 쓰지 않는다.
- 모든 읽기·쓰기·재개·승인 전에 thread_id AND user_id로 소유권을 확인한다. 관리자도 다른 사용자의 분석을 자동으로 읽지 못한다.
- namespace는 서버가 namespace(str(user_id))로 만든다. 브라우저에는 사용자 ID·namespace·그래프 config 지정 권한이 없다.
- 브라우저 입력은 제한된 요청 스키마로 받는다. 서버 내부 파일 경로·state·판정 결과를 임의 주입할 수 없게 한다. KiCad .net(S-expression 또는 XML) UTF-8 파일을 최대 1 MiB까지 읽고 검증한다. 파일 선택 UI가 내용을 JSON으로 전송하므로 multipart 의존성은 추가하지 않는다. 원문·파싱한 연결은 소유자와 함께 DB에 저장하고 서버 파일로 쓰지 않는다. XML DTD·ENTITY, 과도한 깊이·요소 수, 깨진 형식, 중복 부품, 없는 부품을 참조하는 넷은 거부한다.
- 쿠키 기반 상태 변경 API는 기존 auth.check_origin을 사용한다. 응답에는 Cache-Control: no-store를 붙인다.

### API 계약 제안
(11-10에 아래 경로를 React 이전 화면과 함께 지웠다. 지금 계약은 SPEC 4절.)
- 모든 thread/업로드/기억 API 오류는 main의 error.code/message/request_id 계약을 사용한다. DB 연결 실패(503)와 본문 초과(413)도 동일하며 입력·DB 예외 원문은 숨긴다. workspace는 error.message를 읽는다.
- POST /api/circuits: 파일명과 UTF-8 넷리스트 본문을 받아 검증·저장하고 대상 선택용 부품 목록을 반환한다.
- GET /api/circuits: 내 회로와 부품 목록만 반환한다.
- POST /api/threads: 자기 circuit_id·대상을 지정해 thread 생성. 소유자는 세션에서 결정한다.
- GET /api/threads: 내 thread 목록만 반환한다. 결과 개수에 상한을 둔다.
- GET /api/threads/{id}: 내 thread의 표시용 상태·현재 결과·중단 질문을 반환한다. 내부 state 전체를 노출하지 않는다.
- POST /api/threads/{id}/messages: 질문을 받아 기존 그래프를 실행한다. thread의 회로·대상은 서버에서 유지한다.
- POST /api/threads/{id}/resume: 현재 중단 질문의 응답으로 기존 interrupt를 재개한다.
- POST /api/threads/{id}/retry: 현재 결과 버전을 확인한 뒤 일시 실패한 체크포인트 실행을 최대 2회 재시도한다. 완료된 체크포인트와 메타데이터 기록 사이 장애는 조회 때 잠금을 얻은 경우 멱등 복구한다.
- POST /api/threads/{id}/approve: 최초 승인은 현재 서버 판정의 결과 버전을 확인한다. 기존 승인 원본이 있으면 현재 버전·판정 상태와 관계없이 해당 원본으로 Store만 재저장한다. 사용자가 보낸 판정 본문은 저장하지 않는다.
- GET /api/memories: 인증 사용자 namespace의 승인 사례만 개수 상한 내에서 조회한다.
- 요청의 최대 길이, 페이지 크기, 동시 실행 제한과 오류 모양은 구현 계획에 확정하고 테스트한다.

### 저장·승인 일관성
- PR #72 main 통합: 현재 그래프는 Plan → 문서/판정 Send → 모으기 → 답 정리/종합 → 답 검사다. store 인자를 compile까지 전달하고 approved_memories를 계획·문서·판정 하위 그래프·종합 모델에 전달한다. 구 verifier는 복원하지 않고 docs의 인용 정리와 최종 check_node에 사례 출처 검사를 연결한다. 판정 읽기의 지시서·다수결 등 main 개선을 유지하며 기억을 숫자 grounding 본문에 넣지 않는다.
- 신규 승인 snapshot에는 당시 사용자 조건·질문·판정 입력 해석·대상 회로 정보를 보관한다. 기존 snapshot의 없는 정보는 확인 불가로 표시한다. 기억의 품번·요약·조건은 소유권을 확인한 승인 원본에서 구성하며 Store 값 자체를 신뢰하지 않는다.
- 모델 입력은 서버가 선별한 approved_memories 별도 필드로 전달한다. 매 새 질문에서 목록을 갱신(없으면 빈 목록)하며 interrupt 재개는 기존 목록을 유지한다. 사례별 텍스트·전체 건수를 제한한다. 기억은 지시가 아닌 데이터이며 현재 회로 조건·데이터시트보다 우선하지 않는다. 승인 사례 인용은 데이터시트 번호와 구분한다.
- saver/store를 앱 수명 동안 관리하고 재사용한다. RAM 저장소는 단위 테스트에만 쓴다.
- thread 하나에 동시에 두 실행이 들어가 state가 섞이지 않도록 DB 기반 배타 처리를 둔다. 잠금·호출에는 시간·횟수 상한을 둔다.
- 최초 승인은 현재 완료된 판정만 가능하다. 이미 승인한 버전은 새 질문 뒤에도 소유권 확인 후 Store 재저장을 허용하며, 승인 원본·시각은 바꾸지 않는다.
- 승인한 판정의 원본 스냅샷을 승인 표에 thread_id와 결과 버전별로 보관하고 Store에는 요약·thread_id·결과 버전·승인 시각을 둔다. 새 질문·새 승인으로 과거 승인 원본을 덮어쓰지 않는다. 견적 ID를 만들어 내지 않는다.
- 기억 key는 thread와 결과 버전으로 결정해 중복 요청 시 한 건만 남긴다. Store 실패 뒤 새 질문을 보내도 같은 승인 재시도로 복구한다. 신규 승인 원본에는 품번도 보관한다. 품번이 없는 기존 원본은 변경 불가인 업로드 회로의 고정 대상 품번을 사용하며 현재 그래프 상태를 참조하지 않는다.
- 사용자가 승인했다는 사실을 데이터시트 근거 대신 사용하지 않는다. 초기 조회는 임베딩 없이 수행한다.

### 적용·검증 경계
- 먼저 가짜 LLM/검색과 격리 PostgreSQL로 검증한다. 공유·운영 DB에 자동 적용하지 않는다.
- 실제 모델 호출·전체 평가 전 worklog에 목적·예산·명령·중단 조건을 기록하고 preregister에 기대를 적는다. 동결 평가셋을 바꾸지 않는다.
- STH에서는 SPEC.md를 직접 수정하지 않는다. 조장 반영 요청에 SPEC 4·8.5·8.6과 테이블 정의 A-02의 thread_id 불일치 정정안을 남긴다.
- 원격 push·PR 생성·배포는 이번 로컬 구현 승인에 포함하지 않는다.

## AC
- GIVEN 새 계획형 판정 하위 그래프의 interrupt WHEN PostgreSQL 연결을 닫고 다시 열어 소유자가 재개 THEN 같은 조건 질문·기억을 유지하고 판정 읽기 모델을 다시 호출하지 않으며 완료 결과를 승인할 수 있다.
- GIVEN thread API의 DB 장애 또는 본문 크기 초과 WHEN 오류 응답 THEN 공통 error 본문과 X-Request-ID가 일치하고 no-store이며 DB 예외 원문은 노출하지 않는다.
- (11-09 대체: 이제 어느 사례도 모델 입력에 넣지 않는다) GIVEN A/B가 같은 품번의 서로 다른 사례를 승인 WHEN 각각 새 thread 질문 THEN 실제 그래프의 모델 입력에는 자기 사례만 포함되고 다른 사용자의 사례는 포함되지 않는다. 기억을 읽는 가짜 모델의 응답으로 연결을 검증한다.
- (11-09 대체) GIVEN 과거 승인 조건에만 숫자가 존재 WHEN 새 분석에서 모델이 그 숫자를 현재 조건으로 제안 THEN 기존 grounded 검증이 거부하고 필요한 조건을 묻는다.
- GIVEN 관련 기억 없음 또는 다음 질문에서 관련 기억이 사라짐 WHEN 그래프 실행 THEN 빈 목록을 전달해 이전 턴 기억이 재사용되지 않는다.
- (11-09 대체) GIVEN 승인 기억의 지시문 WHEN 모델 입력 구성 THEN 데이터 경계와 현재 근거 우선 규칙을 전달하며 기억만으로 사양 근거가 생기지 않는다.
- GIVEN 미인증 요청 WHEN thread/기억 API 호출 THEN 401이며 그래프·Store를 호출하지 않는다.
- GIVEN 사용자 A와 B WHEN B가 A의 thread를 조회·질문·재개·승인 THEN 모두 404이며 A의 상태·기억은 바뀌지 않는다.
- GIVEN 같은 사용자 WHEN 분석 두 건 생성 THEN 서로 다른 thread와 독립된 체크포인트를 사용한다.
- GIVEN 저장된 thread WHEN 런타임 연결을 닫고 다시 열어 조회·재개 THEN 기존 상태를 유지한다.
- GIVEN 중단된 분석 WHEN 소유자가 답변 THEN 같은 thread에서 재개하고 판정 결과를 반환한다.
- GIVEN 질문·거절·중단 상태 WHEN 승인 THEN 거부하고 기억을 만들지 않는다.
- GIVEN 완료된 판정 WHEN 소유자가 현재 결과 버전을 승인 THEN 승인 스냅샷이 남는다(11-09부터 Store에는 쓰지 않는다).
- GIVEN 같은 결과 WHEN 승인 재요청 THEN 승인 원본을 중복 생성하지 않고 성공을 반환한다.
- GIVEN 다음 질문으로 결과 변경 WHEN 승인 원본이 없는 과거 결과 버전 승인 THEN 409로 거부한다.
- (11-09 대체: Store에 쓰지 않으므로 이전 승인 버전 재요청은 원본을 그대로 두고 성공) GIVEN 승인 원본 저장 후 Store 실패 WHEN 같은 thread에 새 질문 후 이전 승인 버전 재요청 THEN 원본·승인 시각·품번을 유지한 기억 한 건을 복구한다. 현재 결과가 거절이어도 복구하며 다른 사용자는 404로 거부한다. 품번 필드가 없는 기존 승인 원본도 복구한다.
- GIVEN 사용자 A의 승인 사례 WHEN A와 B가 기억 조회 THEN A에게만 표시된다.
- GIVEN 역할·품번이 같은 자기 승인 사례 WHEN 새 분석 결과 조회 THEN 최대 5건의 관련 사례를 함께 표시하고 다른 사용자 사례와 일치하지 않는 사례는 제외한다.
- GIVEN 한 thread의 서로 다른 결과를 각각 승인 WHEN 과거 사례 조회 THEN 각 버전의 승인 원본을 유지한다.
- GIVEN 동시 실행 요청 WHEN 같은 thread 실행 THEN 상태가 섞이지 않고 경쟁 요청을 제한한다.
- GIVEN 악성 본문·경로·namespace·사용자 ID 주입 WHEN 요청 THEN 검증 실패하며 서버 파일·다른 사용자 데이터에 접근하지 않는다.
- GIVEN 실패한 그래프 노드 WHEN 소유자가 현재 버전을 재시도 THEN 저장 지점에서 이어가고 재시도는 최대 2회다.
- GIVEN 완료 checkpoint 뒤 메타데이터 실패 WHEN 다시 조회 THEN 상태·답변 기록을 복구하고 같은 checkpoint의 답변은 중복되지 않는다.

## 실행·팀 검토
- 준비: 대상 DB와 복구 경로를 확인한 뒤 `uv run --env-file .env python -m backend.conversations.memory_service --setup`. 기존 SQL 003·005·006 인증 스키마가 선행되어야 한다. 새 Compose DB는 013 메타데이터 SQL을 실행하지만 라이브러리 표 준비 명령은 별도로 필요하다. 기존 볼륨 삭제로 초기화하지 않는다.
- 시작: `.env`의 `THREADS_ENABLED=1`과 적절한 DATABASE_URL/AUTH_ORIGIN/AUTH_SECRET을 설정한 뒤 `uv run --env-file .env uvicorn backend.main:app --host 127.0.0.1 --port 8000`. 기존 코퍼스와 모델 키가 있어야 실제 RAG 판정이 가능하다. `/login`의 분석 링크로 `/workspace`에 들어간다.
- 조장 반영 요청: SPEC 4절에 circuits/threads/messages/resume/retry/approve/memories API와 1 MiB 업로드 계약을 반영하고, 8.5절에 이 문서 AC를 반영한다. 8.6절의 업무 데이터 미구현 문구는 소유권 검증 범위를 반영해 갱신한다. 주요 문서는 STH에서 직접 수정하지 않았다.
- 기존 트리 불일치: SOJAFIT의 db/012_document_category.sql은 HEAD에도 있으나 실제 파일이 없다. 이번 기능과 관계없는 해당 줄 변경은 조장 검토 대상이다.
- 변경 규모: 인증→업로드→thread→승인 기억의 전체 흐름과 보안·복구 테스트 때문에 핵심 변경이 400줄을 넘는다. 임의로 일부만 구현하면 격리·재개·승인 일관성을 검증할 수 없어 한 기능으로 유지하고, parser/저장·API/화면·검증을 논리 단위로 검토한다. 원격 push/PR은 하지 않는다.

## 구현 순서
### 2026-11-09 운영 보완 계약
- 승인 사례 ID는 현재 답변의 근거 인용으로 허용하지 않는다. 제공된 자기 사례 ID만 `memory_refs`에 담고 서버가 승인 원본으로 표시한다. `consulted_memories`(제공됨), `referenced_memories`(선택됨), `related_memories`(사후 검색)를 구분한다. 현재 데이터시트 문장의 의미 정확도 전체를 보증하는 검사는 아니다.
- `threads.input_record`에 버전별 질문·명시 조건·재개 답변을 저장하고 승인 snapshot에 불변 보관한다. 판정 보고의 `analysis_inputs`에는 적용한 역할·SI 값·시험 조건·읽은 원문 값을 남긴다. 기존 승인에 없는 값은 역추정하지 않는다.
- 사용자 선택: UTC 하루 예약 $3, 실행당 예약 $0.50. 기본 90초/16회/출력 4096토큰/입장 간격 2초. 상한 설정은 `ANALYSIS_*`; DB `analysis_usage`에서 일일 예약을 원자 갱신한다. 실패 예약도 유지한다. 보수적 단가의 예약 한도이며 공급자 청구액의 절대 상한은 아니다. 시간 제한은 외부 호출·재시도 경계에서 적용한다.
- GIVEN 동일 사용자 동시 thread WHEN 예약 합계가 하루 상한 초과 THEN 한 요청은 외부 호출 전에 429. GIVEN 다른 사용자 THEN 예산은 독립. GIVEN 시간 만료 THEN 504와 비밀값 없는 request_id 기록.
- GIVEN 과거 승인 Store 저장 실패 뒤 새 질문 WHEN 화면의 과거 버전 재저장 버튼 클릭 THEN 원본은 그대로 두고 해당 버전 Store 복구. 버전별 stored/pending/unknown 상태와 승인 당시 입력을 표시한다.
- 시험 배포는 기존 Cloud Run의 새 tag/revision에만 적용하고 기본 URL의 운영 트래픽은 기존 revision 100%를 유지한다. 014/015는 비공개 schema의 가산 변경이며 기존 계정·코퍼스는 이관하지 않는다. SPEC 해당 절 반영은 조장 검토 요청으로 남긴다.

실행 방식: 현재 STH에서 직접 실행하며 TDD와 마지막 독립 리뷰를 수행한다. 새 브랜치/워크트리는 팀 규칙상 만들지 않는다.

1. `backend/graph/netlist.py`와 `tests/graph/test_agent_netlist.py`: 가공 회로와 기존 공개 샘플로 KiCad 두 형식 파싱·1 MiB 제한·비정상 입력 RED→GREEN. 기존 `circuit_around` 연결 형식을 재사용한다.
2. `db/013_agent_memory.sql`, `backend/conversations/memory_service.py`, `tests/api/test_threads.py`: 전용 스키마의 circuits/threads/messages/approvals와 연결 풀·setup CLI를 작성한다. 012 번호는 기존 트리에 예약되어 사용하지 않는다. app.state 런타임은 THREADS_ENABLED=1일 때만 초기화하며 공개 인증 DB를 유지한다.
3. 같은 테스트 파일에서 실제 PostgresSaver/PostgresStore와 가짜 그래프를 이용해 소유권·재연결·interrupt·동시 실행·승인 멱등성 RED→GREEN. 승인 key는 thread:version, 원본은 별도 승인 표에 보존한다.
4. `backend/main.py`, 그래프 두 build/state 및 `nodes.read_input`: 엄격한 API 스키마, Origin/no-store, 고정된 업로드 연결 주입, Store 전달을 연결한다. 요청에 내부 state/사용자/파일 경로를 받지 않는다. 현재 모델 그래프는 기존 평가 실행기와 같은 MCP 도구·D5 조립을 재사용한다.
5. `backend/web/templates/workspace.html`와 기존 로그인 화면: 업로드·대상·대화 목록·이력·조건 질문·승인·관련 사례를 DOM textContent로 표시한다. 비로그인·401 때 민감한 화면을 비우고 /login으로 이동한다. 파일/질문/응답은 브라우저 영구 저장소에 보관하지 않는다.
6. 각 폴더 설명·SOJAFIT 신규 파일 줄·.env.example·DB 스키마 설명·worklog를 갱신한다. SPEC 변경안은 이 작업서에 조장 반영 요청으로 둔다.
7. 테스트 전용 DB 환경변수와 가짜 모델로 전체 pytest 및 브라우저 흐름을 확인한다. 동결 평가셋 해시를 확인하고 실제 유료 평가 전 별도 사전 등록/예산을 준비한다. 공유 DB 적용·배포와 미검증 항목은 분리해 보고한다.

### 검토 초점
- 파일명·질문에 줄바꿈 키/경로/HTML을 넣어도 서버 파일이나 DOM을 조작하지 못하는가.
- 회로·thread·resume·approval·memory 모든 경로에서 사용자 B의 접근이 실패하는가.
- checkpoint 성공 후 메타데이터 실패, 승인 원본 성공 후 Store 실패에서 재시도로 안전하게 복구하는가.
- 중단값은 엄격한 answers/role로 제한하고 한 thread의 동시 실행을 DB 잠금으로 거부하는가.
- 새 결과 뒤 미승인 과거 버전의 최초 승인은 거부하고, 기존 승인 원본의 Store 재저장은 허용하며 원본은 유지하는가.

## 관련 문서
- [검증 결과와 이전 스냅샷](../research/thread-memory-operations-review.md)
- [운영 검증 절차](../experiments/thread-memory-operations.md)

## 사용자 사실 기억 (11-09)

칸 · 저장 · 검색 · 활용 · 고치기 · 지우기 · 한계 · 수용 기준의 정본은 [SPEC 8.5](../../SPEC.md)다. 여기에는 구현 위치와 세부를 둔다.

- 결정(조장 11-09): 체크포인터는 이번 대화의 상태, Store는 다음 대화에서도 유효한 사람에 대한 사실이다. namespace의 첫 칸(사용자 id)이 격리 단위이고, 노드는 LangGraph가 넣어 주는 Store를 받는다(멀티 그래프 `기억 읽기`, 11-10). namespace는 접근 권한 검사가 아니다. 칸은 소속(`affiliation`) · 직무(`job_role`) · 선호 실장 방식(`mounting_preference`) 3개다.
- 코드: `backend/conversations/profile.py`(칸 검사 `clean`, 틀 문장 `sentence`, `VoyageEmbeddings`, `ProfileMemory.facts · update · delete`), `backend/api/profile.py`(`/api/me/memory`), `memory_service.Conversations.profile`과 `_profile_hints`, `dto.result_dto(profile_hints=...)`.
- 저장 모양: Store `(str(user_id), "profile")` / key = 칸 이름 / 값 `{kind, value, text, version, updated_at, source: "user_settings"}`. 여러 칸을 한 번에 고치면 `PutOp`을 한 `batch`로 보내 임베딩도 한 번 부른다.
- 색인: `PostgresStore(index={'dims': 1024, 'embed': VoyageEmbeddings(), 'fields': ['text'], 'ann_index_config': {'kind': 'flat'}})`. LangGraph 동기 `PostgresStore`는 검색 질문도 `embed_documents`로 임베딩하므로, 검색하는 동안만 입력 종류를 `query`로 바꾼다(`contextvars`). 근사 색인(HNSW)은 namespace 조건과 함께 쓰면 다른 사용자 벡터에 밀려 결과가 빌 수 있어 만들지 않는다.
- 켜는 조건: `VOYAGE_API_KEY`가 있고 `DEMO_MODE`가 1이 아니며 `sojafit_agent.store_vectors`가 있을 때. 셋 중 하나라도 아니면 색인 없는 Store로 쓰고 읽는다. 키가 있는데 표가 없으면 시작 때 경고 로그(`profile_index_unavailable`)를 남긴다.
- 스키마 경로: 준비 명령과 색인을 켠 서비스 연결은 `search_path`를 `sojafit_agent, <vector 확장 스키마>`로 둔다. 색인 표의 `vector(1024)` 형과 검색의 `::vector` · `<=>`가 이름으로 찾히기 때문이다. 표는 첫 스키마인 `sojafit_agent`에 생긴다. 확장 스키마는 `pg_extension`에서 읽는다(로컬 Compose `public`, Supabase `extensions`). 준비 명령은 확장을 설치하지 않는다.
- 활용: `Conversations.message`(그 질문 글)와 `resume`(그 버전의 질문 글)이 그래프를 돌리기 전에 사실을 찾고, 응답의 `profile_hints`에 칸 · 값 · 문장만 담는다. 찾기가 실패하면 빈 목록이고 분석은 계속한다. React run은 완료 · 거절 frame에만 싣고 `public.runs`에는 저장하지 않는다. 에이전트 연결(11-10): 멀티 그래프의 `기억 읽기` 노드(`backend/graph/memory.py` `read_profile`)가 선호 실장 방식 한 칸만 읽어 `mount_preference`로 두고, Spec 에이전트가 찾기 후보 순서에만 쓴다(질문이 실장 방식을 말하면 질문이 이김, 판정 · 거르기 · 프롬프트는 그대로, 결과 `preferred_mount`). 소속 · 직무는 그래프 상태 · 프롬프트에 넣지 않는다. 승인 사례 프롬프트 문단("Historical approved cases")과 늘 빈 `approved_memories` · `memory_refs` 길의 제거는 아직 하지 않았다.
- 수용 기준 시험: `tests/conversations/test_profile.py`(칸 검사 · 틀 문장 · version · 지우기 · 의미 순위 · 입력 종류 · 대체 경로 · API 422 · 403 · 401 · 503, DB: 색인 표 위치, `extensions` 스키마), `tests/api/test_threads.py`(승인 사례 미전달, 질문 · 재개의 참고, A/B 격리, 색인 DB에서 다시 임베딩 · 지운 벡터), `tests/api/test_conversations.py`(React frame의 참고, run 기록 미저장), `tests/multi_agent/test_build.py` · `test_judge.py` · `tests/judge/test_judge_verdict.py`(기억 읽기 격리, 찾기 순서, 질문 우선, Store 없으면 예전 순서).

### 보관 · 삭제 (결정 11-09)
- 사용자 사실은 자동 만료가 없다. 사용자가 지우거나 계정을 지울 때 지운다.
- 프로젝트와 거기에 딸린 것(대화, checkpoint, 승인, 견적)은 마지막 활동 뒤 60일에 자동으로 지운다.
- 기록 종류(분석 사건, 로그인 · 가입 시도, 하루 사용량)는 30일 뒤에 지운다.
- 사용자가 직접 지우면 숨기지 않고 바로 지운다.
- 정리는 스케줄러 없이 새 분석을 시작할 때 작은 묶음으로 한다.

#### 자동 정리(구현, `db/023_retention.sql`)
- 규칙 하나 = SQL 함수 하나(`sojafit_agent` 스키마, 공개 역할 EXECUTE 회수). 분석 서비스가 새 질문(`Conversations.message`)마다 그 thread를 잠그기 전에 `SELECT purge_inactive_projects(), purge_log_records()`를 따로 연결로 부른다(`_purge_expired`). 실패하면 `backend.conversations.retention` 경고(`retention_purge_failed`)만 남기고 분석은 계속한다. 시작 때 두 함수가 없으면 서비스가 뜨지 않는다(규칙이 조용히 꺼지지 않게).
- `purge_inactive_projects(keep_days DEFAULT 60, batch_size DEFAULT 20)`: ① React 프로젝트의 마지막 활동 = 프로젝트 `updated_at`(이름 변경) · 대화 생성 · run `updated_at`(시작 · 끝 · 재개) · 승인 · 견적 중 가장 늦은 시각. 지난 것을 최대 batch_size개 `FOR UPDATE SKIP LOCKED`로 골라 사용자가 지울 때와 같은 순서(같은 UUID의 checkpoint → 분석 thread → 빈 분석 회로 → 프로젝트 cascade)로 지운다 ② React 대화에 딸리지 않은 분석 thread(`/api/threads`로 직접 만든 것, 예전 규칙으로 프로젝트만 지워져 남은 것)는 자기 마지막 활동(생성 · 메시지 · 분석 사건 · 승인 · 승인 기록 관리)으로 본다 ③ thread가 없는 분석 회로(업로드 넷리스트 원문)는 올린 뒤 60일. React 표가 없는 DB에서는 아무것도 지우지 않는다.
- `purge_log_records(keep_days DEFAULT 30, batch_size DEFAULT 200)`: 분석 사건(`created_at`), 하루 사용량(사용자 · 서비스 전체, UTC 날짜), 가입 시도(UTC 날짜), 로그인 시도(계정 · IP: 15분 창 시작이 30일 지났고 잠금이 없거나 끝난 행만)를 표마다 최대 batch_size개(ctid 묶음) 지운다.
- 두 함수 모두 트랜잭션 advisory lock(`736128` · `736129`)으로 동시에 한 곳만 청소하고 나머지는 기다리지 않고 0을 돌려준다. Supabase pg_cron으로 하루 한 번 같은 함수를 부를 수 있다(지금은 켜지 않음, SQL 머리 주석에 예).
- 60일 · 30일의 이유: 회로는 몇 주 뒤에 다시 여는 일이 많아 한 달보다 넉넉히 둔다. 기록은 최근 디버깅과 남용 한도 확인에만 쓴다.

#### 규칙과 개인정보 보호법 조항

| 규칙 | 구현 | 조항 |
|---|---|---|
| 보관 기간이 지나면 자동으로 지운다(프로젝트 · 분석 대화 60일, 기록 30일) | `db/023_retention.sql` 청소 함수 2개, 새 분석 때 작은 묶음 | 21조(파기): 보유기간이 지나 불필요해진 개인정보는 지체 없이 파기 |
| 사용자가 프로젝트 · 내 설정을 지우면 바로 실제로 지운다 | `DELETE /api/projects/{id}`(같은 UUID 분석 기록 · checkpoint 포함), `DELETE /api/me/memory` | 36조(삭제 요구) |
| 탈퇴하면 계정과 모든 기록을 지운다 | `DELETE /api/me`(기록 먼저, 계정 마지막, 다시 요청하면 이어서) | 37조(처리정지 요구 · 동의 철회) |
| 가입 때 처리방침을 알리고 동의를 받는다 | React `/signup`의 고지(`PrivacyNotice`: 목적 · 저장 항목 · 보관 기간 · 삭제 · Langfuse · 외부 서비스 · 거부 권리)와 동의 체크, 서버 `consent` 필수(없으면 422) | 15조 2항(동의를 받을 때 알릴 사항) |

#### 사용자가 지울 때(구현)
- 프로젝트 삭제 `DELETE /api/projects/{id}`(`backend/api/projects.py` `delete_owned_with_checkpoints`): 프로젝트 행을 잠근 같은 트랜잭션에서 그 프로젝트 대화 UUID의 분석 checkpoint 표 3개(`checkpoint_writes` · `checkpoint_blobs` · `checkpoints`, thread_id 글자) → 분석 thread(메시지 · 승인 기록 · 분석 사건은 FK cascade) → 남은 thread가 없는 같은 UUID 분석 회로 → 프로젝트(회로 · 대화 · run · 메시지 · 승인 · 견적 · 승인 사례는 FK cascade) 순서로 지운다(`memory_service.delete_analysis_threads`, 사용자 조건으로만 고름). 하나라도 실패하면 모두 되돌린다. 사용자 사실(Store)은 프로젝트에 딸리지 않아 남는다.
- 탈퇴 `DELETE /api/me`(`backend/main.py`): Origin 확인, 관리자는 409(운영자 CLI `--delete-user-id`도 관리자는 지우지 않음). 순서는 기록 먼저, 계정 마지막이다. ① 계정 배타 잠금 ② 그 사용자의 분석 thread · 회로 · checkpoint 전부(한 트랜잭션) ③ Store를 namespace 접두사로 찾아 지우는 반복(`(user_id,)` 아래 전부와 옛 `("memories", user_id)`, 한 번에 100개 · 최대 1만 개) ④ 계정 행(세션 · 프로젝트 · 견적 · 승인 사례 · 하루 사용량은 FK cascade, 그 이메일의 로그인 실패 행도 지움). 응답은 `{"deleted": {analysis_threads, analysis_circuits, checkpoints, memory_items, projects, quotes, account}}`이고 세션 쿠키를 지운다.
- 멱등: 계정을 먼저 지우면 기록 삭제가 실패했을 때 다시 요청할 방법이 없다. 그래서 계정을 마지막에 지우고, 중간 실패는 503(`계정 삭제를 끝내지 못했습니다. 다시 요청하면 남은 기록부터 이어서 지웁니다.`)이며 다시 요청하면 남은 것만 지운다(이미 지운 것은 0건).
- 잠금(선택: advisory lock, 표 없음): 키 `hashtextextended('account:<user_id>', 0)`. 분석 실행(`locked`) · 대화 연결(`ensure_thread`) · 업로드 · thread 만들기 · 설정 저장(`account_writer`)은 공유로, 탈퇴는 배타로 잡는다. 공유끼리는 서로 막지 않고 탈퇴와만 막으므로 그 사용자의 분석이 도는 동안 탈퇴는 409(`진행 중인 분석이나 저장이 끝난 뒤 다시 시도하세요.`), 탈퇴가 도는 동안 그 사용자의 새 분석 · 재개 · 설정 저장은 409(`계정 삭제를 처리하는 중입니다.`)다. React run · 재개는 스트림을 열기 전(`admission`)에도 확인한다. 표식 표 대신 잠금을 고른 이유: DB 세션 잠금이라 프로세스가 죽어도 연결과 함께 풀려 남는 표식이 없고, 탈퇴가 실패해도 계정이 남아 있어 다시 요청하면 된다. 공유 public 업무 표의 쓰기(프로젝트 · 대화 · 견적)는 계정 행 삭제의 FK cascade가 지우므로 잠그지 않는다.
- 화면: 내 설정(`/settings`)의 "계정 삭제"(일반 계정만 보임)는 확인 뒤에만 `DELETE /api/me`를 보낸다. 로그아웃 · 탈퇴 · 세션 만료로 로그인 상태를 잃으면 React가 화면 메모리(React Query 캐시)와 sessionStorage를 비우고, 보호 화면은 `/login`으로 바꿔(replace) 주소의 `projectId` · `targetRef`를 남기지 않는다(공용 PC의 다음 사람이 보지 않게).
- 한계: 분석 서비스(`THREADS_ENABLED=1`)가 없으면 탈퇴는 503이다(분석 기록 · Store를 지울 수 없으므로). React run 행이 `running`으로 남은 상태(서버가 실행 도중 죽음)는 잠금이 없어 탈퇴를 막지 않는다.
