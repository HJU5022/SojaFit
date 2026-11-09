# 평가자 시나리오·데모·관측·CI 수정 준비

상태: 2026-11-09 STH 구현·검증 수행. 아래 Why는 착수 당시 진단이다. 실측 결과와 정본 반영 제안은 [별도 기록](../research/thread-memory-operations-review.md)을 따른다. 주요 문서 정본 반영·팀 병합은 조장 검토 대상이다.

## Why
- 평가자는 개발자 DB나 API 키 없이 로그인부터 분석·조건 보충·승인·기억 분리까지 확인해야 한다.
- 스크린샷 첫 지적은 일부 해소됐다. 현재 0% 시험 tag의 OpenAPI에 circuits/threads/messages/resume/approve/retry/memories가 있다. 운영 기본 URL 반영과 평가용 계정의 실제 HTTP·화면 전체 흐름은 별도 검증해야 한다. 서비스 직접 호출 성공을 배포 HTTP 완료로 세지 않는다.
- Compose는 로컬 pgvector DB를 사용하지만 THREADS_ENABLED 기본0이며, 저장 라이브러리 준비·시나리오 적재가 연결되지 않았다. Dockerfile은 db/를 복사하지 않는다. data/demo에는 검토 응답·재생 코드가 없고 DEMO_MODE는 현재 검색 API만 끈다.
- CI는 인증 DB와 pytest를 실행한다. TEST_THREAD_DATABASE_URL이 없어 thread DB 시험이 skip될 수 있다. 기존 평가 실행기의 trace와 일반 앱 요청의 사용자·단계 지연 증거도 구분해야 한다.

## Goal
| 항목 | 성공 기준 |
|---|---|
| 실제 서비스 | 평가용 일반 계정 A/B로 HTTP·화면 핵심 흐름 완료, 교차 접근/타 사용자 기억0건 |
| 한 줄 데모 | 새 clone·빈 로컬 DB·외부 키 없음에서 compose up 후10분 내 시나리오 사용 |
| 과금 차단 | 데모의 LLM/임베딩/리랭크/Mouser 외부 호출0건 |
| CI | thread DB·합성 시나리오가 DB 미설정으로 skip되는 건0건 |
| 관측 | user/thread/version/request/trace 연결, 성공·중단·재개·실패·단계별 지연 증거 |

Out of Scope: 견적 저장, 과거 기억 전용 라우팅, 전체 코퍼스 재배포·사양 전량 적재, 운영 승격, 실제 주문. 데모 성공을 실제 모델 품질이나 운영 성능으로 주장하지 않는다. 풋프린트 이름 비교 문제는 독립 보완 대상으로 유지한다.

## What
순서는 **① 실제 평가자 HTTP 경로 → ② 키 없는 데모 → ③ 서비스 관측 → ④ CI·제출 증거**다. 단계별로 코드/검사/증거를 함께 묶고 완료 후 다음 단계로 간다.

Happy path: A로그인→넷리스트→부품선택→질문→조건질문→동일 thread/version 재개→판정/근거→시험승인→자기기억→재접속 복구. B로그인 후 A의 thread·기억 접근 차단을 확인한다. 실제 모델 경로와 합성 데모 경로를 각각 기록한다.

Edge cases: 미인증401, B의 A접근404, 처리 중 중복409, 준비 안 된 분석DB503, 오래된 결과 최초승인409, 기존승인 재저장 멱등, 미등록 데모 질문, trace 전송 실패, 부분 계정 환경설정, 재시작 후 interrupt/승인 복구.

## How
### ① 실제 서비스·평가 계정
- 새 질문 엔드포인트를 만들지 않고 기존 circuits/threads/messages/resume/approve/memories를 사용한다. OpenAPI 존재 확인과 실제 인증 요청 성공은 다른 증거다.
- 시험 tag에서 전용 A/B 일반 계정과 세션·Origin을 사용한다. 기존 비활성 합성 계정을 평가용 활성 계정으로 안내하지 않는다. 비밀번호는 채팅·문서·로그·trace에 적지 않고 별도 안전한 전달/회수 절차를 정한다.
- THREADS_ENABLED와 checkpoint/Store 표·권한·시나리오 사양/출처를 먼저 확인한다. /health만 정상인 상태와 분석 준비 완료를 구분할 readiness 계약을 추가한다. 비밀값·DSN을 노출하지 않는다.
- HTTP 응답·화면·소유권·DB 승인원본/Store를 대조한다. 실제 모델 시연은 사전 등록하고 시나리오 전체 예약$0.50를 공유한다. 운영 기본 URL의 트래픽을 올리는 작업은 별개다.

### ② 키 없는 데모
- 기존 그래프·판정·소유권·저장 경로를 재사용하고 모델/검색의 데모 입력을 제한된 fixture로 제공한다. 가짜 판정 엔드포인트를 따로 만들지 않는다. Conversations 조립에서 DEMO_SCENARIOS=1과 DEMO_MODE=1을 모두 확인한 뒤 합성 응답·도구를 주입하며 LLM/MCP client를 생성하지 않는다. DEMO_MODE 단독의 기존 BM25 실제 모델 평가는 유지한다. 실제 키가 환경에 있어도 데모는 외부 호출하지 않는다.
- 사람이 검토한 합성 회로·사양·노드별 응답으로 역할/조건보충→판정/근거부족 거절의3시나리오를 만든다. 실제 API 응답 원본·원본 PDF·Mouser 응답을 데모에 복사하지 않는다. 각 fixture에 모드·버전·시나리오 ID와 합성 출처를 명시한다.
- 질문·품번·revision·노드/schema를 정확히 매칭한다. 모르는 질문을 비슷한 다른 고정 답변으로 처리하거나 유료 모델로 넘기지 않고 지원 범위를 안내한다. 데모 화면·결과에는 합성/재생임을 표시한다. 가격 API의 available=false는 유지한다.
- Docker 이미지에 db/ 준비 파일을 포함하고 Compose의 명시적 demo bootstrap·THREADS_ENABLED 연결을 수정한다. bootstrap은 격리된 로컬 데모 DB에서만 실행하며 운영 기동에 자동DDL·시드를 넣지 않는다. 기존 계정·승인·볼륨을 삭제하지 않고 멱등으로 준비한다.
- 합성 회로·사양·응답은 같은 scenarios.json 버전에서 읽는다. 실제 코퍼스를 DB에 적재하지 않고 합성 사양 도구의 문서/쪽/표/행 출처를 표시한다. 데모 최소 자료로 G3 전체 코퍼스 재현을 충족했다고 하지 않는다.

### ③ 서비스 관측
- 기존 graph config/callback·Langfuse를 재사용한다. user_id는 인증 결과, thread/version은 소유권 확인된 서버 값만 쓴다. 클라이언트의 임의 user_id를 trace 소유자로 채택하지 않는다.
- request_id↔trace_id↔thread/version과 성공/중단/재개/실패를 연결한다. 재개는 새 요청 기록으로 남기되 같은 thread/version으로 묶는다. checkpoint 저장과 원격 trace 전송 결과는 독립 기록한다.
- 실행한 그래프 노드·검색/사양 도구, 결과 저장(save_result), 승인과 Store 저장의 묶음(approval_and_store)을 계측한다. 주요 미실행 단계는 skipped로 구분한다. checkpoint 라이브러리 I/O만의 개별 지연을 분리 측정하지 않으며 중첩·병렬 단계의 시간을 합산하지 않는다. 지연에는 인간의 조건 입력 대기를 포함하지 않는다.
- trace 장애가 판정/승인 저장을 실패시키지 않게 최소 로컬 메타데이터와 전송 실패만 남긴다. 비밀번호/쿠키/토큰/이메일/DSN/Mouser값은 제외한다. 데모·실제모델·테스트 모드를 분리한다.
- 단계 지연 표는 동일 실행의 실제 기록에서 생성한다. 합성 trace는 계약 확인용으로 표시한다. 실제 앱 user_id/thread/trace가 연결된 화면·Langfuse 스크린샷/링크를 권한·내용 확인 후 확보한다. 준비만 한 증거를 완료로 표시하지 않는다.

### ④ CI·실제 품질 회귀
- 첫 변경은 기존 인증 DB를 유지한 TEST_THREAD_DATABASE_URL 및 thread setup 연결이다. 사용자 FK와 초기화 순서를 보존한다. JUnit에 pass/fail/skip 이유를 남긴다.
- 키·운영 DSN 없는 CI에서 합성 HTTP 전체 흐름을 실행하고 외부 transport를 차단해 호출0을 검증한다. 새 환경은 별도 Compose project/일회용 DB를 사용한다. 사용자의 기존 pgdata에 down -v를 실행하지 않는다.
- 매 PR은 동결 해시·단위/DB/합성 시나리오·관측 계약을 검사한다. 실제 모델 품질 회귀는 별도 명시적 job/수동 실행으로 기존 evals 실행기를 사용한다. 비교 코드/모델/코퍼스/동결셋/예산/지표를 사전 등록하고 같은 문항의 before/after를 대조한다.
- 실제 기준선 확정 전에는 품질 결과를 warning 보고로 두고 임의 점수 gate를 만들지 않는다. 유료 평가 미실행은 미실행으로 표시한다. 고정 데모 성공률을 실제 모델 정확도로 집계하지 않는다.
- artifact에는 모드·버전·환경·표본 수·p50/p95 정의·단계 지연·시나리오 결과·trace 링크를 남긴다. 스크린샷은 실제 시연 결과만 보관하고 비밀값을 제외한다. G2/G4/G5/G6 증거를 각각 연결한다.

### 수정 경로·커밋 단위
1. backend/main.py·conversations.py·tests/api/test_threads.py: readiness/평가자 HTTP 경로.
2. Dockerfile·docker-compose.yml·services/llm.py·명시적 bootstrap·data/demo와 합성 fixture: 키 없는 데모. 파일 추가 전 트리/폴더 설명을 갱신한다.
3. conversations.py·multi_agent/build.py·services/langfuse_prompts.py 및 테스트: trace·단계 지연. 인증/예산/판정은 유지한다.
4. .github/workflows/ci.yml·기존 evals/runners·tests 및 문서: CI/유료 품질 보고/artifact 연결.
5. 조장에게 SPEC 구현 경계/7절·GATES의 최신 상태와 증거 반영을 요청한다. STH에서는 주요 문서를 직접 수정하지 않는다. 공개 데모 자료 범위는 SPEC6절의 기존 검토 절차를 따른다. 이번 준비에서 원격 push/PR/배포·운영 계정 활성화는 하지 않는다.

## AC
- GIVEN 시험 tag WHEN OpenAPI와 A/B HTTP 확인 THEN API 존재/실제 완료/미검증을 구분한다.
- GIVEN 빈 로컬DB·외부키 없음 WHEN compose up THEN10분 내 핵심 흐름 완료·demo표시·외부호출0이다.
- GIVEN 데모에 실제키 또는 미등록질문 WHEN 요청 THEN 유료호출0이며 다른 고정답으로 오매칭하지 않는다.
- GIVEN B WHEN A의 조회/질문/재개/승인 THEN404이며 A 상태·기억은 불변이다.
- GIVEN CI WHEN thread DB 시험 THEN DB 미설정 skip0이며 결과가 artifact에 남는다.
- GIVEN 사람의 조건 입력 대기 WHEN 재개 THEN 동일thread/version이고 대기시간은 처리 지연에서 제외된다.
- GIVEN trace 장애 WHEN 판정/승인 성공 THEN 저장을 유지하고 전송 실패를 별도 기록한다.
- GIVEN 실제 품질 job 미실행 WHEN CI 보고 THEN 미실행으로 표시하며 데모 점수로 대체하지 않는다.
- GIVEN 제출 증거 WHEN 화면·trace·지연 표 대조 THEN 같은 user/thread/version/시나리오를 가리킨다.

## 관련 문서
- [실측 결과·정본 반영 제안](../research/thread-memory-operations-review.md)
- [작업 기록](../worklog/sth.md)
