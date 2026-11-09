# 평가자 시나리오·데모·관측·CI 수정 준비

상태: 2026-11-09 STH 구현·검증 수행. 아래 Why와 초기 작업 범위는 준비 시점의 진단이며 최신 상태는 마지막 실행 결과 절을 따른다. 주요 문서 정본 반영·팀 병합은 조장 검토 대상이다.

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
- 기존 그래프·판정·소유권·저장 경로를 재사용하고 모델/검색의 데모 입력을 제한된 fixture로 제공한다. 가짜 판정 엔드포인트를 따로 만들지 않는다. LLM 입구에서 DEMO_MODE를 외부 client 생성보다 먼저 분기한다. 실제 키가 환경에 있어도 데모는 외부 호출하지 않는다.
- 사람이 검토한 합성 회로·사양·노드별 응답으로 역할/조건보충→판정/근거부족 거절의3시나리오를 만든다. 실제 API 응답 원본·원본 PDF·Mouser 응답을 데모에 복사하지 않는다. 각 fixture에 모드·버전·시나리오 ID와 합성 출처를 명시한다.
- 질문·품번·revision·노드/schema를 정확히 매칭한다. 모르는 질문을 비슷한 다른 고정 답변으로 처리하거나 유료 모델로 넘기지 않고 지원 범위를 안내한다. 데모 화면·결과에는 합성/재생임을 표시한다. 가격 API의 available=false는 유지한다.
- Docker 이미지에 db/ 준비 파일을 포함하고 Compose의 명시적 demo bootstrap·THREADS_ENABLED 연결을 수정한다. bootstrap은 격리된 로컬 데모 DB에서만 실행하며 운영 기동에 자동DDL·시드를 넣지 않는다. 기존 계정·승인·볼륨을 삭제하지 않고 멱등으로 준비한다.
- 코퍼스/사양 시드는 같은 fixture 버전으로 만든다. doc/chunk/page/row 출처를 검증한다. 데모 최소 자료로 G3 전체 코퍼스 재현을 충족했다고 하지 않는다.

### ③ 서비스 관측
- 기존 graph config/callback·Langfuse를 재사용한다. user_id는 인증 결과, thread/version은 소유권 확인된 서버 값만 쓴다. 클라이언트의 임의 user_id를 trace 소유자로 채택하지 않는다.
- request_id↔trace_id↔thread/version과 성공/중단/재개/실패를 연결한다. 재개는 새 요청 기록으로 남기되 같은 thread/version으로 묶는다. checkpoint 저장과 원격 trace 전송 결과는 독립 기록한다.
- plan/검색/judge_read/judge/synth·check/checkpoint/승인·Store의 시간·결과를 기록하고 실행하지 않은 단계는 skipped로 구분한다. 지연에는 인간의 조건 입력 대기를 포함하지 않는다.
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

## 2026-11-09 실행 결과와 조장 반영안
- 시험 tag: thread-memory-test → sojafit-api-00020-miv, 운영0%. 운영 00008-2h5는100% 유지. 시험만 출력 상한2048이고 기본 코드4096/일일$3/실행$0.50은 유지한다. Secret Manager 참조/TLS verify-full/CA/동시성4/timeout120/max인스턴스1 유지.
- 최종 전체: 인증·thread 격리 DB와 TEST_THREAD_BACKUP_CONTAINER를 설정한 pytest →972 passed,36 skipped,57.86초. Docling 경고1. 동결 해시 검사 통과. 원격 GitHub CI는 미실행이며 DB 설정+JUnit 업로드를 준비했다.
- 키 없는 최종 소스 Compose: 별도 sojafit-memory-verified DB/앱, 8773, 합성 HTTP17항목 통과. 처음 준비 명령은 작업 경로/포트 충돌로 실패했고 경로·8773을 명시해 동일 검사를 통과했다. 기존 볼륨 삭제 없음. source/lock을 포함한 최초 비캐시 빌드 및 이후 검증 모두10분 이내였으며 CPU/모델 성능 평가가 아니다.
- 실제 HTTP: disposable user16/17, 승인 thread3609152d-6c49-4874-93fb-a5ebf87d4fa0, 새 thread0bb0592d-bd4b-4532-8317-5e1b56ed8c57. 조건 보충→SPEC_EQUIVALENT→승인/Store→같은 사용자의 새 thread 전달과 B404/빈 기억 통과. 합산 추가 예약$0.426852, 사전 예약2.50은 시험 예산 장벽이며 실제 사용/청구가 아니다. 공급자 실제 청구 대조는 미실행.
- 실제 모델은 새 thread의 자기 승인 사례를 입력받았지만 이번 답의 memory_refs는 비어 있었다. 전달 성공과 명시 선택 성공을 혼동하지 않는다. 합성 데모에서는 별도 참조 선택 표시까지 검증했다. 이 사례만으로 회상률/답변 품질 향상을 주장하지 않는다.
- 실제 UI: 시험 URL에서 비밀번호 로그인, 승인 당시 최종 입력, 정정 메모 저장, 철회 후 기억 목록 제외, 복구 후 재표시를 관찰했다. API 삭제/재승인 차단 및 중단 checkpoint 재개 차단은 격리 DB/합성 HTTP에서 검증했다. 실제 공유 DB의 시험 사용자 원본/승인은 보존하고 계정 비활성화·세션 제거를 완료했다.
- Langfuse: CLI observations list의 실제 응답 봉투(body)로 조회, user16/session=승인 thread와 trace3건 일치 확인. 첫 수신 검사는 CLI 봉투를 잘못 파싱해0건으로 보였으며 봉투 처리 수정 후 received/same_user/same_thread/trace_ids_match 모두true. 요약 span은 전송 시각, 처리 시간은 실측 metadata이며 중첩/병렬 시간을 합산하지 않는다. generation 원문/비밀번호/쿠키/DSN은 내보내지 않는다.
- [실제 재개 trace](https://cloud.langfuse.com/project/cmvucheif009rad0k6qfg5h55/traces/1194f9b06476492aaba9256f703280c1): 프로젝트 권한 필요. 로그의 queued와 별개로 API 수신을 확인한 증거다.
- 증거: evals/results/graph/memory_operations_2026-11-09.json(내용 없는 요약), 로컬 작업 산출물의 memory-trial-restored.jpg / memory-trial-revoked.jpg / memory-demo-new-thread.jpg. 스크린샷은 합성 시험 사례만 포함하며 공개 첨부는 SPEC6절 검토 절차를 따른다.

### 정본 문서 수정 요청 (STH에서 직접 수정하지 않음)
1. SPEC8.5: 장기기억=사용자별 관련 승인 사례 참조. 정정은 별도 메모, 철회는 복구 가능, 기억 삭제는 Store 사본/향후 참조 제거·원본 유지, 자동 만료 없음. 전체 대화 자동 기억/자유 과거 질의는 범위 밖이라고 명시한다.
2. SPEC7절/README 데모: DEMO_MODE 단독의 기존 BM25 실제 모델 평가와 DEMO_SCENARIOS+DEMO_MODE 앱 합성 시연을 구분한다. Docker setup과 data/demo/DEMO.md의 시연 순서를 연결한다.
3. SOJAFIT data/demo 부모 설명의 '현재 설명 파일만 있고 재생 코드는 없음'을 '명시적 앱 합성 시나리오 데이터'로 갱신한다. STH에서는 신규 파일 줄 추가/분기 표시만 반영한다.
4. GATES G2/G4/G5/G6: 위 실행 범위/모드/샘플 수/증거를 적고, 원격 CI 실행·전체 동결셋 before/after·실제 청구 대조·운영 RTO/RPO는 미검증으로 유지한다. app 추적은 내용 없는 메타데이터이며 모든 generation 원문/비용 추적을 완성했다고 쓰지 않는다.
5. 판정 사례 승인은 견적서 승인/저장이 아니다. 실제 판정 답변의 패키지/기판수정 문구는 footprint 문자열 비교 수준이며 치수 검증을 하지 못한다. None 표기와 오판 가능성은 별도 judge 보완 과제다.

### 팀 반영·리뷰 범위
- 이번 마무리는 앞서 미커밋으로 누적된 인용 검증/최종 입력/예산 경계와 기억 lifecycle/데모/관측을 함께 정리한다. 400줄을 넘는 핵심 변경은 공유 실행·승인·저장 경로와 실패 복구를 API/DB 통합 시험으로 함께 검증해야 하기 때문이다. 인용/호출 경계, API·기억 관리, 데모·검증 자료를 논리 단위 로컬 커밋으로 구분한다.
- 독립 리뷰의 시간 초과 P2는 RED→GREEN으로 수정했다. 조장 리뷰/정본 문서 반영/PR 병합은 남는다. AGENTS 팀 규칙1·3에 따라 이번 작업에서 원격 push/PR 생성/merge는 실행하지 않는다. 조장에게 보낼 제안 본문이며 실제 PR 코멘트 전송은 하지 않았다.
