# STH 작업 기록

## 2026-11-09 문서 규칙 보완·PR 본문 준비
- 한 일: 기능 작업서의 실측/이전 스냅샷/정본 반영 제안을 research/thread-memory-operations-review.md로 분리했다. 최신 마무리 기록을 파일 위로 옮기고 원문 기록을 보존했다. DB 013~017·thread-setup 순서, 웹 화면 범위, 합성 데모 출처와 관측 계약을 현재 구현에 맞췄다.
- 바꾼 파일: docs/specs/evaluator-demo-readiness.md·user-thread-memory.md, docs/research/thread-memory-operations-review.md·RESEARCH.md, docs/experiments/thread-memory-operations.md, docs/worklog/sth.md, db/DB.md, backend/web/WEB.md, data/demo/DEMO.md, SOJAFIT.md(신규 파일 한 줄만).
- 실행한 명령과 결과: uv run --no-sync --offline pytest tests/repo -q → 5 passed(0.32초). 수정 문서10개의 로컬 Markdown 링크 오류0, 실제 SQL 파일 순서 일치, 최신 작업 기록 위치·기능 작업서 다섯 섹션 보존 확인. git diff --check 통과. 애플리케이션 코드 변경0.
- 확인 못 한 것: 문서만 수정해 전체 코드/유료 평가/배포를 다시 실행하지 않는다. 원격 CI·전체 품질 회귀·실제 청구 대조는 이전 기록대로 미검증이다.
- 다음 할 일: 보완 커밋과 main 기준 PR 본문 초안을 준비하고, 확인된 조장 허락 범위에서 STH 일반 푸시를 수행한다. 새 PR 생성·병합은 수행하지 않는다. STH head의 기존 열린 PR #73에 변경을 쌓고 본문을 갱신한다. GitHub 연결 도구는 저장소 조회 권한이 없어 기존 Git 인증을 메모리에서 사용한 API 읽기로 head=STH/base=main/open을 확인했다.

## 2026-11-09 장기기억 마무리 — 실행·검증 기록
- 사용자 선택: 자동 삭제 없음. 직접 철회/삭제, 정정은 승인 원본을 덮어쓰지 않는 사용자 메모. 기억 삭제는 Store 사본/향후 참조 차단이고 대화·승인 원본을 유지한다.
- Ruling: 새 analysis_trace.py를 만들지 않고 기존 langfuse_prompts.py에 내용 없는 단계 콜백/요약 전송을 추가했다. 기존 추적 경계와 의존성을 재사용한다. 원격 요약 span 시간은 전송 시각이고 실제 처리 시간은 metadata.stages/elapsed_ms다. queued는 수신 확인이 아니다.
- 변경: DEMO_SCENARIOS=1 및 DEMO_MODE=1을 요구하는 앱 합성 시나리오. 기존 DEMO_MODE 단독 BM25+실제 모델 평가는 유지. 실제 그래프/판정/PG 저장소를 사용하고 LLM/MCP 대신 합성 응답·사양만 주입한다. Compose는 별도 setup 서비스로 checkpointer/store를 준비하며 CI에 TEST_THREAD_DATABASE_URL/JUnit artifact를 연결했다.
- 로컬 검증: 합성 데모 2 passed (격리 DB 사용), 단계 기록 2 passed, lifecycle/과거 checkpoint 차단 3 passed. 전체 최신 검사 TEST_AUTH_DATABASE_URL·TEST_THREAD_DATABASE_URL 설정, uv run --no-sync --offline pytest -q --junitxml=.pytest_cache/final-test-results.xml: 970 passed,37 skipped,Docling warning1,53.04초. GitHub 원격 CI 실행은 아직 하지 않음.
- 빈 DB Compose: 키·실제 .env를 제외한 132개 파일(3.53MB) 컨텍스트, 별도 sojafit-memory-final 프로젝트/pgdata, 8772 포트. build/up 성공. 실제 HTTP 로그인 A/B·조건 보충·승인·새 thread 기억 참조·정정·철회·복구·삭제·재승인 부활 차단 17항목 통과. 첫 시험의 즉시 resume는 일반 2초 빈도 제한에 걸려429, 시험도 호출 간격을 지키도록 수정 후 같은 경로 통과. 모델 호출0(통합시험은 실제키 존재+외부 transport 호출 시 실패하도록 검사).
- 독립 리뷰: final_memory_review가 시간 초과 뒤 최종 checkpoint 재조회가 DONE으로 복구되는 P2 발견. 실제 PG 테스트에 read_input/run_version/승인 가능 판정을 넣어 RED 재현. input_record.execution_limit_reached 표식을 보관하고 재조회 자동 완료·승인을 차단했다. 새 질문/허용된 재개·재시도에서 새 예산 적용 시 표식을 초기화한다. 시간초과/기존 메타데이터 장애 복구 같은 검사 2 passed. readiness는 새 correction 열까지 확인한다.
- 공유 DB: 기존 approvals의 열을 확인한 뒤 가산 migration manage_approved_memories_and_analysis_events 적용. 기존 행/코퍼스/승인 snapshot 수정 없음. 새 analysis_events 및 private schema의 anon/authenticated 접근 false 확인. 016/017 SQL과 기능은 같고 공유 적용은 기존 역할이 존재하므로 REVOKE를 직접 사용했다.
- 시험 배포: Cloud Build 64cae673-6fc1-4cfd-8372-e0ca2532247b 성공. image digest cdc9ed1d2b5881a2792ed1f46d5ae808d3bac99c406caa055d38155fe79056f4, revision 00019-wav 운영0%. 후속 실제 모델 검증은 같은 이미지의 출력 상한만 시험용2048로 낮춘0% revision을 사용한다. 기본 코드4096/일일$3/실행$0.50은 유지한다.
- 실제 모델 검증 사전 계획: 목적=시험 URL의 로그인→실제 후보 판정→조건 보충→승인→새 thread 기억 참조/격리/관측을 확인. 기존 후보와 같은 G-K 회로 변형 및 12V/0.1A/전압강하모름. 새 disposable A/B 계정만 사용하고 완료 후 비활성화. 임의 원본/운영 사용자는 삭제하지 않는다. 시험 A의 analysis_usage에 시작 잔액2.50을 명시적으로 잡아 일일$3 중 이번 검증 합계 예약$0.50만 허용한다(2.50은 실제 호출/청구 아님). 유료 단계 최대2회, 전체예약잔액초과/90초/16회/HTTP실패 시 중단, 자동 재실행 없음. 명령: uv run --env-file .env python <작업 산출물>/memory_release_http.py. G-K 회로·승인 문맥이 달라 동결 e01 정식 회귀 점수로 비교하지 않는다. 전체 frozen 품질 재측정과 실제 청구 대조는 별도 한계로 남긴다.
- 최종 검증/인계: 전체972 passed,36 skipped,57.86초(인증·thread DB 및 격리 dump/restore 포함), 동결 해시 변경 없음. 최종 소스의 별도 Compose8773 HTTP17항목 통과. 실제 시험 revision00020-miv 운영0%, 운영00008은100% 유지. 실제 두 흐름 합산 추가 예약$0.426852/상한$0.50, 모델은 자기 사례를 입력받았으나 memory_refs 선택은 이번에 없음. 후보 판정/승인/Store 성공과 명시적 기억 선택을 구분한다. Langfuse3건 실제 수신과 user16/thread/request 일치 확인. 화면 로그인/정정/철회/복구 확인 후 시험 계정16/17 비활성화·auth session 제거. 검토한 JPG3개와 원시 보고는 로컬 작업 산출물에 보관한다.
- 정본 문서 반영안/증거·한계/큰 변경의 이유는 docs/specs/evaluator-demo-readiness.md 마지막 절에 작성했다. 전체 동결 품질 비교/실제 청구·운영 복원·원격 CI 실행은 미검증. 패키지 footprint 문자열 비교/None 경고는 기존 judge 후속 과제다. 운영 승격/원격 push/PR/merge는 하지 않는다.
- 로컬 커밋: 717c93a(인용/모델 호출 예산 경계), 245be70(API·최종 입력·기억 관리·데모·관측·통합 시험). 이 기록과 평가 실행기/원시 결과/정본 반영안은 마지막 검증 자료 커밋으로 보관한다. 두 번째 커밋은 구현 경로와 보안·복구 통합 시험을 함께 포함해971추가/40삭제이며, 규모/분리 이유와 조장 검토 범위를 readiness 작업서에 적었다.
- Ruling: 데모 bootstrap은 별도 demo CLI를 추가하지 않고 Compose의 thread-setup 서비스가 기존 명시 --setup을 호출하게 했다. Compose가 DATABASE_URL을 로컬 db로 강제하므로 기존 .env의 공유 DB를 건드리지 않는다. 일반 --setup CLI는 공유 DB의 명시적 가산 준비라는 원래 용도를 유지한다.
- 최종 비밀 검사: 변경 diff+신규 텍스트에 .env의 실제 민감 필드 값 및 대표 토큰 패턴을 대조해0건. 동결셋 해시2개 일치. Cloud Build의 Python/HTML48개와 작업 소스 바이트 일치 확인. gitleaks 전체 저장소 스캔/원격 CI 실행은 아님.

## 2026-11-09 평가자 경로·데모·CI·관측 보완 준비
- 사용자 요청: 스크린샷의 부족한 점3개(배포 시나리오 엔드포인트, 키 없는 Compose 데모, CI 평가 회귀/user_id·지연·Langfuse 증거)를 보완할 수정 작업을 준비.
- 현행 대조: 현재0% thread-memory-test tag의 /openapi.json을 실제 GET해 auth/login·circuits·threads/messages/resume/approve/retry·memories 존재를 확인했다. API 부재는 일부 해소됐지만 평가용 계정의 HTTP/화면 전체 완료나 운영 기본 URL 반영은 이번 읽기로 증명하지 않았다. Compose는 THREADS_ENABLED 기본0·라이브러리 setup/시드 미연결, Dockerfile은 db 미포함, data/demo는 응답/재생 없음. CI는 인증 DB만 설정하고 TEST_THREAD_DATABASE_URL이 없다. 기존 평가 trace와 일반 앱 요청의 사용자/단계 지연 증거는 별도다.
- 준비물: docs/specs/evaluator-demo-readiness.md(Why/Goal/What/How/AC)에 ①평가자 HTTP/readiness→②합성 키 없는 데모→③서비스 trace/지연→④CI/품질 회귀·artifact 순서, 수정 경로와 합격 기준을 작성했다. 기본 API를 재사용하고 재생 결과를 실제 품질로 세지 않으며 유료 평가는 명시적 사전 등록 경로로 분리한다. 무료 CI의 thread 시험 skip 제거가 첫 CI 변경이다. 새 문서를 SPECS 목록과 SOJAFIT 한 줄에 등록했다.
- 경계: 이번 변경은 준비 문서뿐이다. 제품 코드/Compose/CI/DB/계정/모델/프롬프트/배포/트래픽/원격 Git을 변경하지 않았다. SPEC/GATES 정본 갱신은 조장 반영 요청으로 남겼다. 검증은 아래 문서 구조·저장소 배치와 diff 검사이며 새로운 실제 시연·품질 실험·스크린샷은 만들지 않는다.
- 실제 확인: 새 작업서의5절 존재 검사 통과, uv run --no-sync --offline pytest -q tests/repo →5 passed/0.31초, git diff --check 통과. 스크린샷의 user_id 지적은 앱 DB 소유자 기록 자체의 부재가 아니라 일반 서비스 trace/지연 증거 연결 공백으로 정리했다.

## 2026-11-09 운영 사양 표 출처 검증·문서1건 적재·동일 후보 재시험 (실행 전)
- 사용자 승인: 사양 표 적재와 문서·청크 출처 연결을 확인한 뒤 같은 사례를 재검증. 범위는 현재 비어 있는 public.part_specifications 중 tsc-1n4001g-k-series_b2104(document8) 한 문서의 기존 파서 파생행이다. 기존 원문/임베딩/사용자 승인 원본/스키마/배포는 변경하지 않는다. 전체1360문서 적재로 확대하지 않는다. 유료 재시험은 이번 회차 예약$0.50/16회/90초이며 앞선 회차와 별도다.
- 읽기/원문 확인: 사양0행 재확인→현재 DB의 대상30청크를 해시·page/table/row/순번 그대로 내보내 기존 specs.build 실행. 숫자56행/패키지14행 생성, range_unsplittable1건은 검토목록에만 두고 적재하지 않음. 제조사 공식 B2104 PDF383406바이트의 SHA256 687ce10afa3b20413f841e8b9fbc6f31fcba27727166f1258496bf50b5e4627f가 DB와 일치했다. PDF1~2쪽을 렌더해 VRRM 품번열·IF1A·IFSM30A·온도·VF/IR/CJ의 단위/시험조건·DO41패키지를 대조했다. VF/IR 등 조건이 보존됐고 원문 없는 숫자/비현실 값 자동 검사0건이다.
- 적재 전 검사: uv run --no-sync --offline pytest -q tests/rag/test_rag_specs.py tests/rag/test_rag_spec_lookup.py tests/rag/test_rag_units.py →66 passed/11 skipped/0.27초. 11건은 TEST_DATABASE_URL 미지정 DB시험이다. 대상 원문·해시를 재대조하고 기존 specs.load의 docs 필터/단일 트랜잭션으로70행만 적재한다. 실패 시 트랜잭션 롤백, 성공 뒤 출처JOIN·page/table/row·원문값·대상외행수와 MCP조회 확인. 예상 못한 불일치면 모델 재시험 전에 중단한다.
- 복구/안전: 적재 직전 대상 사양0행을 요구한다. 데이터 교체는 document8에만 제한되며 원본/청크는 변경하지 않는다. 출처 검증 실패 시 이번 실행이 넣은 사양ID만 제거하는 복구를 검토하며 다른 문서·사용자 데이터는 삭제하지 않는다. 비어 있던 정확한 시점·원인은 감사 로그 없이 확정하지 않는다.
- 적재 실제 결과: 기존 specs.load를 docs=['1N4001G-K SERIES_B2104.pdf']로 호출해 1문서/70행/0.24초 성공. 대상 원문/청크를 SHARE 잠금으로 재대조하고 시작 사양0행을 확인했다. 적재 뒤70행 모두 현재 document8+chunk_index JOIN 및 page/table/row 일치, 패키지 원문 포함을 assert로 확인했다. 다른 문서 사양행0 유지·대상청크30개 불변. Supabase 독립 SELECT에서도70행/7품번/깨진출처0/쪽불일치0 확인. PDF·청크·생성사양·검토목록·load결과는 세션 candidate-specs 산출물에 보존했다.
- 실제 모델 결과: candidate_ops_loaded.py, 새 합성 사용자14/15/thread4ae74d05-0b0d-423b-b7c2-5f03dd2e8c8d/version1. 검사19개 통과, WAITING→12V/0.1A/전압강하모름→close/reopen→DONE→시험승인/Store1건. supervisor/judge_read 각1회, 재개 후 읽기 재호출0. 기존 judge의 SPEC_EQUIVALENT 판정과 두 필수 조건pass를 확인했다. VRRM15V/후보1000V(원문page1/idx15), IF_AV0.142857A/후보1A(page1/idx17)이며 실제 표·행과 인용이 일치한다. 이전 사용자10의 NOT_VERIFIED 승인 원본은 변하지 않았다. 새로운 깨끗한 namespace에서 재시험해 과거 불확실 기억이 입력되지 않게 했다.
- 저장/비용: 메시지4/승인1/checkpoints14/blobs45/writes80, namespace memories.14/key4ae74d05-0b0d-423b-b7c2-5f03dd2e8c8d:1. 중복승인1건/사용자15의 빈 기억·조회404·승인404, 보충원문/실제SI입력/승인Store 일치 확인. 17.484초/예약$0.290793(이번회차$0.50 미만)/공급자보고$0.02185325/LLM2회. 시험계정 비활성화·기록보존. 계정·thread 식별자와 원시 결과는 세션 candidate_ops_loaded.json에 보존하고 자격증명은 저장하지 않았다. 이번에는 제품 코드·프롬프트·배포를 변경하지 않았다.
- 의미 검토/남은 제한: 새 결과의 '패키지가 달라 기판 수정 필요'는 verdict.py:347의 shortcut(문자열 포함 비교)에서 import_input:DIODE-0.4에 DO-41이 없어서 나온다. 실제 패드/치수 불일치 확인이 아니며 'None' 표제 출력도 남는다. 해당 문구까지 검증통과로 보고하지 않는다. 허용전압강하/사용온도/발열은 여전히 확인되지 않았다. 전체1360문서 사양 적재·실제 부품 채택/견적 승인·HTTP/화면·최종청구대조는 이번 결과에 포함하지 않는다. 양호한 판정을 만들려고 원문값/판정규칙/과거 승인 원본을 수정하지 않았다.

## 2026-11-09 Supabase HTTP 로그인→분석→승인→기억 E2E 실행 전
- 실제 결과: 2026-11-09 14:16 KST 실행, http_supabase_e2e.py exit0/25.891초/47개 검사 전부 통과. 합성 A12/B13, 회로7d4c87ef-a859-4bad-ae93-0c2fb888cc57, thread45706b05-6a68-4ee2-a525-bb5c783f2272/version1. 실제 TCP 로그인·세션/me·업로드·Thread NEW→WAITING→서버 재시작→같은 중단값 복원→12V/0.1A/전압강하 모름 보충→DONE→시험 승인·중복 승인·자기 기억1건→B조회/승인404·빈 목록→재시작 후 결과/기억 유지→로그아웃/me·분석401 확인. 쿠키 HttpOnly/SameSite와 승인 전409도 확인했다.
- DB 증거: checkpoint14개, 승인 원본1개와 Store memories.12/45706b05-6a68-4ee2-a525-bb5c783f2272:1 한 건, 질문/재개 입력과 snapshot 일치. 종료 후 독립 읽기 전용 조회로 DONE/version1·승인/Store 각1개·시험계정2개 비활성·세션0건을 다시 assert했다. 시험 기록은 유지했고 로컬 서버는 종료했다.
- 비용/판정: A의 UTC 일일 예약액 $0.289812/입장2회로 $0.50 아래. 실제 공급자 청구액은 미수집. 1N4007G-K 최종 NOT_VERIFIED: VRRM/IF_AV 후보 사양값과 인용을 확보하지 못했다. 기능 저장 성공이 실제 대체 가능 판정 성공을 뜻하지 않는다. 유료 재시도·증액·코퍼스/사양 적재·배포 변경 없음.
- 산출물: 현재 세션 visualizations/http_supabase_e2e_20261109T051627Z.json에 합성 응답·판정·47개 검사·예약액·정리 결과를 보관했다. 비밀값은 포함하지 않았다. 사후 결과 출력에서 cp949가 UnicodeEncodeError를 내 ASCII escape로 같은 조회를 재실행해 통과했다. 이는 HTTP 실행 실패가 아니다. 실행기 AST 검사와 동결 해시 검사도 통과. Cloud Run/실제 브라우저 UI/Google 로그인/실제 청구·전체 답변 품질은 미검증이다.
- 사용자 승인: Supabase 연결로 실제 로그인부터 Thread 생성·분석·승인·장기기억 저장까지 검증 요청. 로컬 loopback FastAPI 서버 + 팀 Supabase + 실제 OpenRouter/MCP 경로를 사용하고 Cloud Run은 변경하지 않는다. 합성 일반계정 A/B 두 개와 공개 회로의 메모리상 변형만 생성하며 비밀번호·쿠키·키는 메모리에서만 사용한다.
- 비교/기대: 기존 코드·모델·코퍼스 유지. breadboard_supply D1 업로드 품번만 보유 변형 1N4001G-K로 명시해 1N4007G-K 후보 판정. 실제 HTTP 로그인/쿠키/me→업로드→Thread 생성→질문→조건 대기 시 서버 재시작→질문된 조건에12V/0.1A/모름 답변→완료→시험 승인→중복 승인→Store·원본 DB 일치→재시작 후 기억 유지→B404·빈 기억→로그아웃401을 확인한다. 문서 부족 결과를 긍정 판정으로 바꾸지 않는다.
- 예산/명령/중단: 세션 산출물 http_supabase_e2e.py를 uv run --env-file .env --no-sync --offline python으로 실행. 새 A의 ANALYSIS_DAILY_USD=0.50으로 최초 질문·재개 합계 예약 $0.50, 요청별16회·90초·4096토큰, 유료 HTTP 요청은 최초1회·재개최대1회. 오류·상한 뒤 유료 재시도/증액 없음. DB 예약액과 최종 청구는 구분한다.
- 보존/정리: 기존 사용자·코퍼스·스키마 수정 없이 합성 실행 기록은 검토용으로 남기고 시험계정만 비활성화·해당 세션 폐기한다. 실패 시에도 정리한다. 결과는 현재 세션 visualizations에 비밀값 없이 기록한다. 실제 사용자 세션·운영 배포 UI·부하·백업복원은 범위 밖이다.

## 2026-11-09 input_record·analysis_usage Supabase 재확인과 검증
- 사용자 요청: 로컬 코드에 맞는 입력 기록 컬럼·사용량 테이블 추가 및 검증. 조회 결과 이미 migration 20261109040141(preserve_thread_inputs_and_analysis_reservations)로 두 항목이 반영돼 있어 중복 DDL은 실행하지 않는다.
- 검증 계획: 카탈로그로 로컬 SQL 014·015와 타입·기본값·NULL·PK/FK/CHECK·인덱스를 대조하고 anon/authenticated 접근 차단을 확인한다. 임의의 음수 ID를 사용하는 합성 사용자·회로·thread로 input_record JSON 왕복과 현재 Conversations._budget의 입장 간격·예약액 상한·사용자 분리를 한 트랜잭션에서 시험한 뒤 롤백한다. 실제 사용자 행·코퍼스·세션·모델·운영 배포는 건드리지 않고 시퀀스도 사용하지 않는다. 실패하면 같은 검증을 수정 원인에 맞춰 재실행하고 결과를 기록한다.
- 실제 결과: 중복 마이그레이션 없이 검증 완료. Docker psql과 팀 Supabase psycopg 카탈로그를 같은 search_path로 대조해 컬럼 6개(input_record 포함)·analysis_usage 제약 3개(PK/FK/CHECK)·인덱스 1개 일치. input_record는 nullable JSONB/기본값 없음, reserved_usd는 NUMERIC(16,10)/기본값 0, attempts는 기본값 1이다. anon/authenticated의 schema USAGE 및 threads/analysis_usage SELECT·INSERT·UPDATE·DELETE 권한 없음 확인.
- 동작 검증: 단일 Supabase 트랜잭션에서 합성 음수 사용자 ID 두 개와 회로·thread를 생성해 input_record NULL 초기값·재개 답변 포함 JSON 저장/조회 일치를 확인했다. 실제 Conversations._budget을 같은 연결에 바인딩해 즉시 재입장 429, 예약액 0.4→1.0 누적, 1.1 초과 예약 429, 상한 도달 후 입장 429, 허용 입장 attempts 증가 및 다른 사용자 예약액 독립을 검증했다. 음수 reserved_usd는 CHECK 위반으로 거부됐다. 시험 사용자·회로·thread·사용량 전부 롤백 후 미잔존 확인. 시퀀스는 사용하지 않았다.
- 최신 Conversations 생성자는 실제 Supabase에서 초기화·종료 성공(factory는 모델/MCP 없는 객체로 대체). 모델 호출·실제 사용자 세션·운영 트래픽·코퍼스 변경 없이 현재 스키마 준비 검사를 통과했다. 운영 HTTP/API·실제 모델 분석·배포는 이번 검증 범위가 아니며 기존 변경을 덮어쓰지 않았다.

## 2026-11-09 운영 DB 실제 후보 판정·조건 재개·승인 기억 실행 전
- 사용자 승인: 후보 판정에서 조건 보충·승인·기억 저장까지 실제$0.50 한도 검증, 이어 운영 DB 사용 선호를 반영. Supabase SojaFit의 threads/approvals/analysis_usage 존재를 읽기 조회했다. 새 합성 일반계정2개·회로1개·thread1개만 생성하고 시험 뒤 계정만 비활성화해 검증 기록은 남긴다. 기존 사용자·코퍼스·스키마·배포·트래픽은 변경하지 않는다.
- 사례/명령/기대: preregister의 해당 실행 전 계약을 따른다. 공개 breadboard_supply D1 1N4001→1N4007, 초기 전압/전류 생략→요청된 조건에12V/0.1A→재연결 재개→코드 판정→시험 승인→자기 namespace 저장·중복 방지·B격리 확인. Conversations 서비스 직접 호출이며 이번 시험에 별도 HTTP 로그인/화면/운영 부하는 포함하지 않는다.
- 비용/중단: message/resume 전체가 같은 EvaluationBudget($0.50/16회/90초)을 공유하고 각 요청의 원래 일일 예약·입장 검사는 유지한다. 가짜 그래프·가짜 도구·가짜 응답을 사용하지 않는다. 오류/상한 뒤 추가 유료 요청 없이 중단·기록한다. 공급자 보고 비용과 실제 청구 대조를 구분한다. 외부 모델·공유 DB 쓰기 범위는 합성 시험 workflow에 한정한다.
- 최초 실패/진단: 계정10/11/thread07cdcea4-3b31-4f21-a228-c0cc8089fbfd에서 Supervisor가1N4001/1N4007 코퍼스 없음을 거절했다. WAITING 검사 실패로 승인/Store 저장 없이 종료, 계정비활성화 성공. 예약$0.13896/공급자 보고$0.0190525. 읽기 전용 SQL 확인: source_documents1360/document_chunks51967/part_specifications0. 표지의 실제 품번은1N4001G-K~1N4007G-K였다.
- 진단 후 계획 수정: 임의 사양값 적재 없이 합성 업로드 품번을 실제 보유 변형으로 명시하고 같은 비활성 시험계정 기록에서 후속1회만 실행. 남은 예약$0.36104/15회/추가90초, 누적$0.50 이하. 시간 제한은 진단 뒤 별도 실행에만 재시작하며 예산은 누적한다. 근거 부족을 예상하므로 NOT_VERIFIED를 긍정 대체 판정으로 보고하지 않는다. 가능한 조건 질문/재연결/재개/시험 승인/Store/격리를 확인하고 추가 오류면 중단한다. 시험계정 재활성화·사양표·배포 변경은 하지 않는다.
- 최종 검증: 후속 사례 검사 18개 통과. WAITING에서 v_in_max/i_max/v_drop_allowed 요청→합성 12V/0.1A/모름→런타임 close/reopen 뒤 동일 interrupt/version1→DONE/can_approve→시험 승인→원본·Store 일치. node_calls supervisor/judge_read 각 1번, 재개 후 읽기 모델 추가 호출 0. 실제 judge 계산 기준 VRRM 15V/IF_AV 약 0.1429A, 후보 사양 행 없음으로 NOT_VERIFIED. 현재 부품 대체 가능을 증명한 결과가 아니다.
- 실제 저장: user10/circuit8b3a81ea-9e9f-4590-8ea0-1ff46ad138f6/thread c86eb3a9-708c-460c-b952-fd7c054d3531/version1。 메시지4/승인1/checkpoints14/blobs45/writes80, namespace memories.10/key c86eb3a9-708c-460c-b952-fd7c054d3531:1의Store1건. 승인snapshot의input_record.resumes와resolved_inputs에입력12V/0.1A가보존됨. 재승인기억1건·B(namespace11)빈기억·thread조회/승인404를확인했다. 합성계정10/11은비활성상태로유지하고기록은사용자확인용으로남겼다. 다른사용자기록을읽거나수정하지않았다.
- 비용/산출물: 최초예약$0.13896+후속$0.290787=총$0.429747, DB일일예약도같은값/입장attempts3。 공급자보고$0.0190525+$0.02188555=총$0.04093805, LLM총3호출。 후속실행17.094초。 세션산출물candidate_ops_e2e.json/candidate_ops_covered.json에응답·DB카운트·공급자ID·검사원문보관。 비밀번호/토큰/DSN은저장하지않음。 최종청구대조·HTTP로그인/화면·실제사양충족검증은하지않았다. 후속과제는운영part_specifications 적재및chunk출처정합성검증후같은실제판정재시험이며이번범위에서임의행을채우지않았다.

## 2026-11-09 답변 품질 평가 실제 실행 전
- 사용자 승인: 준비 순서 중 우선 답변 품질을 $0.50 한도에서 실제 실행하고 설명하도록 요청했다. 대상은 사전 등록한 동결 v2 draft30-e01 1건(회로 D1 역할), 기존 멀티·노드별 모델·하이브리드 설정이다. 계정·운영 트래픽·공유 DB 스키마는 변경하지 않는다.
- 명령: `LLM_PROVIDER=openrouter DEMO_MODE=0 uv run --env-file .env --no-sync --offline python <세션 산출물>/quality_e01_exec.py`가 run_thread_validation --ids draft30-e01 --out evals/results/graph/thread_validation_2026-11-09.json --execute를 호출한다. 결과 파일은 없음을 확인했다. 호출 전 예약 한도 $0.50/16회/90초/4096토큰. 예산 초과/오류 뒤 유료 재실행·증액은 하지 않는다. 예약액과 공급자 보고 비용·실제 청구액을 구분한다.
- 증거: 기존 result_row 반환값은 바꾸지 않고 같은 실행의 최종 답변·현재 근거·상태를 로컬 세션 산출물에만 보관해 의미 대조에 사용한다. 동결 expected는 실행 후 채점에만 쓰고 모델에 전달하지 않는다. 기존 Langfuse callback을 유지하고 잠금 의존성을 올리지 않는다. 순수 역할 질문이라 데이터시트 숫자 판정·기억·전체70건 품질의 성공으로 확대하지 않는다.
- 실제 결과: 2026-11-09 13:35 KST, session multi-dataset_v2-1109-1335-openrouter. 선택1건 완료/오류0/5.9초/LLM2회/검색0회/runner exit0. role 일치·cited_gold·가짜 인용0·미인용 문장0. 원시 결과 evals/results/graph/thread_validation_2026-11-09.json 및 .usage.json, 실제 답변·근거 로컬 캡처는 세션 visualizations/quality_e01_review_input.json. trace https://cloud.langfuse.com/project/cmvucheif009rad0k6qfg5h55/traces/9154e7f5af3a92900ee36ff734014fc7 . Langfuse의 긴 metadata.node_models/prompts 속성 생략 경고가 있었고 전체 모델/해시는 로컬 meta에 남았다.
- 의미 검토: D1.A–S1.S 및 D1.C–F1.1, 퓨즈 뒤 RAW/U1.IN 연결이 원본 circuit.net과 일치했다. 답변은 직렬·한 방향 통과 역할을 말하지만 역극성 보호 목적/역접속 시 동작과 J1 단독 공급 한계를 명시하지 않았다. 자동 인용 통과와 별개로 설명 완결성은 부분 충족이다. 답변이나 동결 정답을 수정하지 않았고 개선·재평가는 이번 한도에서 추가 실행하지 않았다.
- 비용/제한: 예약$0.244257, 공급자 보고 LLM비용$0.020088325(2개 응답ID 모두 확보), 최종 청구 대조 미실행. $0.50 한도 아래에서 종료했고 추가 유료 호출 없음. 실제 검색·사양 숫자·기억·다른 문항·전체 품질·부하/복원은 이번 평가 범위가 아니다. 공유 DB는 코퍼스/MCP 읽기만 사용했으며 구조·계정·배포·트래픽을 변경하지 않았다. 동결 해시/원시 결과 예산 대조와 git diff --check를 마지막에 확인한다.

## 2026-11-09 미검증 항목의 실행 준비
- 요청: 이전 보고의 미검증 품질·부하·백업 복원·실제 비용을 검증할 수 있게 준비. 제품 동작·프롬프트·공유 DB·배포는 변경하지 않는다. 동결 v1/v2와 팀 주요 문서는 유지하며 SOJAFIT은 신규 파일 2줄만 추가했다.
- 변경: docs/experiments/thread-memory-operations.md에 품질/기억/병렬/복원/청구 대조의 기준·실행 명령·중단 조건을 작성했다. evals/runners/run_thread_validation.py는 기본 dry-run과 명시적 execute를 구분하고 기존 run_graph/EvaluationBudget으로 선택1~4건 전체 예약 $0.50/16회/90초를 적용한다. 공급자 응답 ID·모델·토큰·보고 비용만 usage.json에 기록하며 누락 합계는 null이다. 실제 청구액 검증은 Activity ID별 대조로 남기며 Voyage/Cloud 비용과 분리한다. 새 의존성은 없다.
- 로컬 시험 범위: 합성 loopback thread_test DB의 8개 병렬 요청 및 pg_dump를 같은 컨테이너의 새 thread_restore_<무작위> DB로 복원하는 시험. 포트 매핑·DB 이름을 확인하고 생성한 DB만 제거한다. 공유 DB/운영 백업은 사용하지 않았다. 원격 부하는 명령·중단 기준만 준비했다.
- 실제 결과: 첫 병렬 시험은 invoke 내부에 둔 시험용 Barrier에서 BrokenBarrierError(10초)로 실패했다. 시작 시점 동기화로 바꾸고 같은 두 검사를 재실행해 2 passed/4.16초. 8건 중3건DONE/5건429, 예약 $0.08 이하·질문 격리 확인. dump726728바이트/0.344초, restore0.625초. 복원 DB에서 기억 원본 일치·B404·승인 Store 상태·interrupt 재개·추가 승인과 원본 interrupt 유지 확인, 대상 DB 정리 성공. 작은 합성 DB 결과이며 운영 RTO/RPO가 아니다.
- 실행기 RED→GREEN: 신규2검사가 미구현 import로 실패한 뒤 구현해 tests/evals/test_run_graph.py+tests/repo →24 passed/7.30초. 보고 비용 누락/본문 제외·dry-run/ID·덮어쓰기 거부를 API 없이 확인했다. 후속 실제 callback 수집 경로도 가짜 모델로 검증한다. 이번 턴의 실제 유료 모델 호출·원격 부하·운영 복원·청구 내역 대조는 하지 않는다.
- 전체 회귀 첫 결과: 937 passed/57 skipped/1 failed(38.09초). 병렬 시험이 입장429에서도 질문이 저장됐다고 가정해 IndexError가 났다. 입장 전에 거부되면 version0/메시지 없음인 정상 계약에 맞춰 검사하고, 성공은 최대3건·나머지429·일일상한/격리를 확인하도록 수정했다. 제품 코드는 바꾸지 않았다. 백업 옵션 때는 fixture 초기화 전에 loopback thread_test DB인지도 거부하도록 보완했다.
- 최종 검증: 같은 전체 `TEST_THREAD_DATABASE_URL=<합성 로컬 DB> TEST_THREAD_BACKUP_CONTAINER=sojafit-thread-test-1109 uv run --no-sync --offline pytest -q` 재실행 →938 passed/57 skipped/Docling 경고1,27.30초. 실제 LangChain 가짜 모델 callback을 통한 usage 파일 생성·누락 비용 null·원문 미포함·llm.chat 복원도 포함한다. 새 실행기의 문서상 CLI를 execute 없이 직접 실행해 execute=false/동결v2해시/상한 표시 및 결과 파일 미생성을 확인했다. freeze --check와 git diff --check 통과. 새 유료 평가·원격 부하·공유 DB 복원·청구 내역 대조는 미실행이다. 현재 시험 배포 revision과 운영 트래픽은 이 준비 작업에서 변경하지 않았다. 변경은 STH 미커밋 상태다.

## 2026-11-09 기억 근거·최종 조건·운영 한도·화면 복구·0% 시험 배포
- 사용자 선택: 기존 STH에서 ①기억 인용 검증→②승인 최종 조건→③비용/시간→④화면 복구→⑤기존 Cloud Run 0% 시험 배포. 하루 사용자 예약 $3/실행 예약 $0.50를 선택했다. 운영 기본 URL로의 승격은 요청 범위가 아니다.
- 변경: memory_refs와 본문 근거를 분리하고 제공되지 않은 기억 ID/본문 기억 인용을 거부. input_record/analysis_inputs를 승인 원본에 저장. 기존 EvaluationBudget+DB analysis_usage로 사용자 일일·실행 예약과 호출/시간 상한을 적용. 이전 승인 버전의 Store 상태·재저장 UI, 제공/선택/관련 사례 표시를 추가했다. 신규 SQL 014/015와 기존 폴더 설명·환경 예시·작업서를 갱신했다.
- 로컬 검증: 단계별 RED→GREEN(①관련 검사199 passed, ②71 passed, ③88 passed/1 skipped, ④복구2 passed). 전체 `TEST_THREAD_DATABASE_URL=<격리 로컬 DB> uv run --no-sync --offline pytest -q` → 932 passed/57 skipped/Docling 경고1, 41.35초. 테스트는 가짜 모델이며 실제 모델 평가로 해석하지 않는다.
- 브라우저: localhost:8770, 합성 계정/실제 로컬 PG/가짜 모델에서 결과2 상태로 결과1 승인 저장 대기 펼치기→기억 저장 다시 시도→기억 저장됨/관련 사례 재표시를 확인했다. 개인 로그인 자격증명은 사용하지 않았다.
- 시험 배포 실행 전 계획: project sojafit/asia-northeast3/sojafit-api, 운영 00008-2h5 100%와 기존 tag 3개 보존. 새 thread-memory-test tag에만 THREADS_ENABLED=1, 사용자 선택 예산, revision max1/min0/concurrency4/timeout120 적용. 비밀값 참조·CA/TLS 검증 유지. 014/015를 기존 sojafit_agent에 가산 적용하고 공개 역할 차단을 재검증한다. 실패 시 새 revision으로 운영 트래픽을 보내지 않고 중단한다.
- 빌드 계획/비용: 현재 pyproject/uv.lock/.python-version이 기존 main-3bc2ff3 이미지 소스와 동일함을 git diff로 확인했다. 해당 digest를 기반으로 현재 추적 backend와 검토 SQL만 복사하는 최소 시험 이미지를 Cloud Build 1회/최대900초로 만든다. .env/.git/사용자 업로드/캐시는 업로드하지 않는다. Cloud Build/저장소/시험 URL 호출 비용은 LLM 예약 한도와 별개다. 추가 빌드는 실패 원인과 변경을 기록한 후에만 진행한다.
- 미검증/제한(배포 전): 실제 모델 전체 품질, 공급자 실제 청구액, 강제 프로세스 취소, 부하/백업 복원, 원격 프롬프트 등록은 확인하지 않았다. 주요 문서 SPEC 수정은 조장 반영 제안으로 남긴다.
- DB 적용: 팀 SojaFit에 migration 20261109040141(preserve_thread_inputs_and_analysis_reservations) 성공. input_record JSONB와 analysis_usage 존재 및 anon/authenticated CRUD 차단을 재조회했다. 신규 schema 관련 advisor finding은 없고 기존 public RLS 정책 없음 INFO11건, rls_auto_enable 공개 실행 WARN2종, Supabase Auth 유출 비밀번호 보호 WARN은 유지된다. 기존 경고를 이번 범위에서 바꾸지 않았다. 보완 문서: https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable 및 https://supabase.com/docs/guides/database/database-linter?lint=0029_authenticated_security_definer_function_executable 및 https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection .
- 빌드/배포 결과: 데이터 차이는 DATA/CORPUS 설명 2개뿐이라 의존성·실행 데이터는 동일함을 확인하고 설명도 overlay에 포함했다. 소스 77파일/825126바이트(별도 Dockerfile/ignore 포함 archive79파일). Cloud Build 2bd8ddc3-1e6d-41e6-884b-68d187f7cdeb 성공, 이미지 digest 361bea3fdbbc94790f2d544b7be8c2225246f8a487e03b5988fcb53e4446f8e4. revision sojafit-api-00018-tus 배포 성공. URL https://thread-memory-test---sojafit-api-q5lzmlc4wq-du.a.run.app . 배포 후 운영 00008-2h5 100%, 새 tag 0%, 기존 tag3개 보존을 확인했다. 실제 build/운영 청구액은 미수집이다.
- 실제 시험 URL: 합성 A/B 로그인·회로 업로드·thread 생성·승인 원본 재저장·자기 기억 조회 성공. 교차 thread 조회/승인 404. 실제 모델 2건의 과거 기록만 묻는 질문은 범위 밖으로 거절(본문 회상0/2)했지만 자기 사례만 모델 입력에 제공했다. 질문만 현재 역할+과거 사례로 바꾼 추가1회는 넷리스트 현재 설명과 별도 referenced_memories1건을 반환했다. 본문에 과거 설계명은 없고 현재 적합성도 단정하지 않았다. 이 경로의 별도 사례 참조는 확인했으나 자유로운 과거 기록 질의는 지원을 확인하지 못했다. 예약 $0.139050+$0.139056+$0.247407=$0.525513, 실제 청구액 미수집. 각 시도 뒤 생성한 계정·업무 행·Store·checkpoint·세션 정리 성공. 합성 결과/소스 manifest는 해당 세션 visualizations에 보관했다.
- 추가 회귀: Voyage 429 재시도가 다음 외부 호출 전에도 예산 상한을 지키는 테스트를 추가해 `1 passed` 확인했다. 후속 변경은 문서/테스트뿐이며 배포 기능 코드는 동일하다. 현재 STH 작업 내용은 아직 커밋·push하지 않았다. SPEC·주요 문서 수정은 조장 반영 요청으로 남긴다. 핵심 변경이 약400줄을 넘어 향후 PR에는 통합 승인·격리·복구·한도 검증을 함께 검토하는 이유와 논리별 커밋 범위를 적어야 한다.
- 마지막 확인: `git diff --check` 통과, `uv run --no-sync --offline pytest -q tests/repo` → 5 passed/0.87초. Cloud Run 설정 재조회에서 운영100%/시험0%/기존tag/일일3·실행0.50/인스턴스최대1/concurrency4/timeout120/verify-full/CA마운트/비밀값 참조 보존을 assert로 확인했다. 실제 .env 비밀값의 diff 미포함 및 동결 v1/v2 미변경도 확인했다. 하루 예산 기준은 UTC(한국 시간 오전9시 경계)다. 실제 모델 전체 의미 정확도·자유로운 기억 회상 질의·부하·백업 복원·공급자 실제 청구액은 미검증이다.

## 2026-11-09 팀 Supabase Thread·기억 구조 추가
- 사용자 승인: 로컬에서 검증한 Thread·장기기억 테이블을 팀 Supabase에도 생성하도록 요청했다. 대상은 SojaFit 프로젝트이며 기존 계정·코퍼스·세션 데이터 이관, 환경설정 활성화, 배포는 범위 밖이다.
- 실행 전 계획: 기존 sojafit_agent 충돌 여부와 public.users.id bigint identity를 확인하고, 013 메타데이터 SQL을 이력 있는 마이그레이션으로 적용한다. 이어 검증된 설치 버전(langgraph-checkpoint-postgres 3.2.0)의 Saver/Store.setup을 session 연결·verify-full에서 실행한다. 새 표·인덱스·제약·공개 역할 차단을 확인한다. 기존 표 변경 없이 새 비공개 구조만 추가하며 실패 시 서비스 활성화 없이 중단하고 생성 상태를 기록한다. 라이브러리 setup은 autocommit이므로 부분 적용될 수 있다. 복구 시에는 새 schema가 비어 있고 사용되지 않음을 확인한 뒤 제거를 별도 검토하며 기존 DB 볼륨·public 표는 삭제하지 않는다.
- 적용 결과: Supabase 마이그레이션 `20261109025926` (`create_private_agent_thread_memory`) 성공. 메타데이터 4개 표를 생성하고 session 연결에서 설치된 PostgresSaver/PostgresStore.setup으로 내부 표 6개를 생성했다. 라이브러리 migration 최대 버전은 checkpoint 9, store 3이다. PUBLIC·anon·authenticated의 schema/table/sequence 권한을 명시적으로 회수했다. 기존 public 표와 계정·코퍼스 행은 수정하지 않았다.
- 실제 검증: 로컬 Docker psql 카탈로그와 Supabase psycopg 카탈로그를 대조해 컬럼 55개·제약 17개·인덱스 19개 모두 일치했다. 최초 제약 비교는 search_path 차이로 실패했으며 동일한 public search_path에서 같은 비교를 재실행해 통과했다. anon/authenticated의 schema USAGE 없음 및 10개 표의 SELECT/INSERT/UPDATE/DELETE 없음 확인. 합성 checkpoint 저장→조회, Store 저장→조회 및 다른 namespace의 미조회, 전체 시험 트랜잭션 롤백 후 데이터 미잔존을 확인했다. 실제 사용자·계정 행은 시험에 사용하지 않았다.
- 보안 advisor 재조회: 신규 sojafit_agent 관련 finding은 없고 기존 public 표 11개 정책 없음 INFO와 rls_auto_enable 실행 권한 및 Supabase Auth 유출 비밀번호 보호 WARN은 유지된다. 별도 범위로 수정하지 않았다. 관련 문서: https://supabase.com/docs/guides/database/database-linter?lint=0028_anon_security_definer_function_executable 및 https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection .
- 미실행: 로컬 시험 기록·계정 이관, THREADS_ENABLED 활성화, Cloud Run 배포, 실제 운영 사용자 A/B API 시험, 모델 평가. 서버 활성화 전에 실제 앱 DB 역할로 연결·사용자 격리·재개·승인 AC를 시험해야 한다. 현재 확인은 테이블 생성·구조 동등성과 저장 라이브러리 동작 범위다.

## 2026-11-09 로컬 시험 DB와 팀 Supabase 구조 비교
- 범위: 사용자 요청에 따라 읽기 전용 구조 비교와 동기화 방법 검토. 코드·환경변수·DB·배포는 변경하지 않았고 이 기록만 추가했다.
- 확인: Docker 컨테이너 목록과 sojafit-thread-test-1109의 psql 카탈로그 SELECT, Supabase SojaFit 프로젝트의 information_schema/pg_constraint SELECT 및 보안 advisor를 실행했다. 공통 public.users/auth_sessions/auth_login_attempts의 컬럼 16개는 타입·길이·NULL·기본값·identity가 모두 일치했고 PK/UNIQUE/FK/CHECK도 대조했다. 로컬에는 Google 인증·RAG 표가 없고 sojafit_agent의 메타데이터 4개·checkpoint 4개·Store 2개 표가 있다. Supabase public에는 인증 6개·RAG 5개 표가 있으며 sojafit_agent 표는 조회되지 않았다. 로컬 표 RLS는 꺼져 있고 Supabase public 표 11개는 켜져 있다.
- 설정·구현: 현재 .env의 DATABASE_URL은 팀 Supabase session pooler 5432와 verify-full을 사용한다. Compose는 별도로 로컬 db를 지정한다. 인증과 Conversations는 같은 DATABASE_URL을 읽으며 Store namespace는 memories + public.users.id다. 같은 login_id라도 DB별 숫자 ID가 같다는 보장은 없다. 현재 기억은 승인 사례 조회이며 자동 학습·기억 임베딩이 아니다.
- 제안: 운영 계정·코퍼스를 유지하고 검토된 013 메타데이터 SQL 및 동일 uv.lock의 Saver/Store.setup으로 분석 구조만 추가한다. 백업·복구 및 실제 앱 DB 역할의 비공개 schema 권한을 먼저 확인하고 setup 뒤 라이브러리 표까지 권한을 점검한다. 현재 세션 잠금 구현에는 direct/session 연결을 사용한다. setup은 autocommit이며 라이브러리 DDL에 CREATE INDEX CONCURRENTLY가 있어 단일 트랜잭션 원자 적용으로 간주하지 않는다. Dockerfile은 db/를 복사하지 않아 현 setup CLI를 현재 이미지 안에서 그대로 실행할 수 없다. THREADS_ENABLED=1은 구조 준비와 시험 배포 후 활성화한다.
- 기존 데이터 이관이 필요할 때: 검증된 login_id 기준 사용자 매핑을 만들고 circuits/threads 소유자, Store prefix와 checkpoint 내부 user_id를 함께 변환·검증한다. checkpoint bytea는 SQL 문자열 치환으로 바꾸지 않는다. 세션·로그인 시도·OAuth 임시 상태와 합성 시험 계정은 기본 이관 대상에서 제외한다. 소유자 A/B 격리·재접속·interrupt 재개·중복 승인 시험 후 반영한다.
- 제한: 사용자·세션 집계 SELECT는 자동 승인 검토에서 요청 범위 초과로 거절되어 실행하지 않았고 구조만으로 계속했다. 계정별 동일인 여부·실제 운영 Cloud Run 연결 대상·배포 버전·로그인·데이터 이관·모델 평가는 확인하지 않았다. 테스트나 setup은 실행하지 않았다. Supabase 문서로 direct/session/transaction 연결 차이를 확인했다. 다음 작업은 조장과 적용 대상·복구 경로·로컬 기록 이관 필요 여부를 정한 뒤 시험 환경에서 구조 추가와 AC 검증이다.

## 2026-11-09 사용자별 업로드·분석 thread·Store 구현과 로컬 검증
- 사용자 직접 시연: Swagger `/docs`에서 합성 A(234) 로그인→넷리스트 JSON 업로드→thread 두 개 생성→첫 thread 조건 interrupt·서버 재시작 뒤 재개→승인→둘째 thread의 독립 대화와 관련 기억→B(235)의 빈 목록·A thread 404→A 재로그인을 확인했다. 실제 로컬 PG 행은 A 기준 회로 1/thread 2/메시지 6/checkpoint 8/승인 1/Store 1, Store prefix `memories.234`, key `첫 thread UUID:1`이었다. 제품에 포함하지 않는 임시 실행기의 `/demo/db-snapshot`은 인증 사용자 행만 읽고 비밀 해시는 제외한다. 시연용 조회의 이전 GET 응답 재사용은 no-store와 조회 번호로 방지했다. 팀 DB를 변경하지 않았으며 판정 모델은 가짜였다. Swagger 탭과 localhost:8769 시연 서버는 사용자가 직접 살펴볼 수 있게 열어두었다.
- 실제 모델 smoke 실행 전: 목적은 업로드→영속 thread→기존 D5 모델 연결 검증이다. 동결 v2 4문항(`draft30-e01/e03/m04/e06`), BM25, 노드별 기존 모델, 출력 1024, 최대 40회·480초·예약 $1.00로 사전 등록했다. 공유 코퍼스 읽기만 사용하고 합성 사용자의 저장은 로컬 격리 DB에 한정한다. 전체 70문항 평가나 개선 주장으로 해석하지 않는다. 실행기와 결과 위치는 preregister의 해당 절을 따른다.
- 목표: 금일 17:30 KST까지 로그인 사용자 기반 thread 소유권, DB 체크포인트, 승인 사례 Store 저장·조회를 구현·검증한다. 사용자 선택은 분석 한 건당 thread 하나다.
- 현재 상태: 사용자의 넷리스트 업로드·화면 연결 범위 승인을 반영해 구현했다. 세션 사용자 소유권, PostgreSQL Checkpointer/Store, 버전별 승인 원본, 관련 사례, 실패 실행 재시도와 메타데이터 복구를 포함한다. 공유 DB 적용·배포는 하지 않았다.
- 바꾼 파일: `backend/conversations.py`, `backend/graph/netlist.py`, main·단일/멀티 build/state·입력 읽기, 로그인 및 신규 workspace 화면, `db/013_agent_memory.sql`, API/graph 테스트, .env.example, 해당 폴더 설명·DB 설계·작업서·preregister·원시 측정. SOJAFIT은 신규 파일 7줄만 추가했다. SPEC 등 주요 문서는 직접 수정하지 않았다.
- 실행한 명령과 실제 결과: `.venv/Scripts/uv.exe run --no-sync pytest -q tests/api/test_auth.py::test_login_page_has_no_question_controls tests/api/test_auth.py::test_question_endpoint_is_not_exposed tests/api/test_auth.py::test_https_login_cookie_and_cross_origin_logout tests/graph/test_graph_build.py::test_second_message_in_same_thread_starts_fresh` → `4 passed in 1.21s`(샌드박스 uv 캐시/인터프리터 권한 문제 뒤 승인된 재실행). `docker ps` → Docker daemon 연결 불가.
- 착수 시 미확인: Docker·격리 PostgreSQL·신규 기능·실제 모델 연결은 아래 후속 검증으로 확인했다. 현재도 공유 DB의 신규 스키마 적용·실제 배포·전체 답변 품질 평가는 미검증이다. 원격 Git은 변경하지 않았다.
- 설계 검토: 독립 검토에서 첫 버전의 샘플 회로 한정 범위, 다음 분석의 관련 사례 표시, 과거 승인 원본 보존을 확인했다. 관련 사례는 역할·품번 기준 최대 5건 표시, 원본은 버전별 불변 승인 표로 보존하도록 보완했다. 샘플/API 한정 범위는 사용자 검토 대상이다.
- 문서 검사: 구조 테스트 `1 failed, 4 passed` — 기존 HEAD 트리의 `db/012_document_category.sql`가 실제 Git에 없어 실패했다(`git show HEAD:SOJAFIT.md`, `git ls-tree HEAD db/012_document_category.sql`로 대조). 새 작업서의 트리·목록은 반영했다. `git diff --check` 통과. 기존 주요 문서 불일치는 권한 범위 밖이므로 수정하지 않았다.
- 실행 환경 준비: Docker Desktop을 숨김 실행했다. 기존 restart 정책에 따라 Langfuse 실습 컨테이너들이 기동된 것을 확인했다. 기존 서비스·볼륨을 수정/삭제하지 않았다. 별도 `sojafit-thread-test-1109` PostgreSQL 16 컨테이너를 loopback 포트 55439에 생성하고 기존 인증 SQL 003·005·006만 적용했다. 외부 공유 DB가 아닌 일회용 로컬 시험 DB다.
- 추가 검증: `uv run --no-sync --offline pytest -q tests/api tests/graph tests/multi_agent -p no:cacheprovider` → `239 passed, 22 skipped in 11.32s`(DB 미설정). 이어 로컬 격리 DB만 `TEST_AUTH_DATABASE_URL`로 지정해 `uv run --no-sync --offline pytest -q tests/api/test_auth.py -p no:cacheprovider` → `51 passed in 24.30s`. 신규 thread·Store 격리를 검증한 결과는 아니다.
- 런타임 대조: 설치 버전 langgraph 1.2.18, langgraph-checkpoint-postgres 3.2.0, psycopg 3.3.6, psycopg-pool 3.3.3의 실제 생성자 signature를 확인했다. 추가 의존성 설치는 하지 않았다.
- 구현 검증: 새 파서 테스트는 미구현 import 실패→12건 통과(이후 NUL 입력을 더해 13건), 새 저장/API 테스트는 미구현 실패→기능별 통과로 확인했다. 공개 회로의 U$1 참조명을 발견해 허용한 뒤 같은 실패 검사를 재실행했다. HTTP Origin 테스트는 .env의 기존 값에 의존해 한 번 실패했고 테스트에서 Origin을 명시한 뒤 통과했다.
- 독립 코드 리뷰: 일시 노드 실패 뒤 thread가 막히는 문제와 checkpoint 완료 뒤 상태/이력 기록 실패 문제를 실제 PG에서 재현했다. 저장 실행 최대 2회 재시도, checkpoint_id별 답변 멱등 저장, 잠금 하의 상태 복구로 수정했다. 리뷰 재확인에서 두 finding 해소 및 추가 중요 오류 없음. 과거 결과 버전의 조건 재개가 허용되는 실패도 확인한 뒤 버전 검사를 넣고 재실행했다.
- 최종 전체 검사: 두 TEST_*_DATABASE_URL을 로컬 일회용 DB로 지정하고 `.venv/Scripts/uv.exe run --no-sync --offline pytest -q -p no:cacheprovider` → `1 failed, 851 passed, 22 skipped in 32.99s`. 실패는 위에 기록한 기존 `test_tree_matches_files`의 012 파일 누락 한 건뿐이다. 신규 입력/저장/API 검증은 25건(파서 13, API/저장 12)을 포함한다. 실제 기본 D5·MCP·Postgres 저장소의 앱 lifespan 시작/종료도 모델 호출 없이 통과했다.
- 브라우저 검사: 합성 계정·가짜 판정 그래프·실제 로컬 PG 서버에서 파일 선택 업로드→D1 선택→새 분석→조건 interrupt→12 입력 재개→사례 승인→새로고침/서버 재기동 후 이력·기억 확인, B 계정의 빈 목록을 확인했다. 최종 버전 재개와 승인 성공 안내도 재확인했다. 화면 캡처는 visualizations의 `thread-ui-approved-final.png`; 임시 UI 서버는 검증 뒤 종료했다. 이것을 실제 모델 답변 정확도 검증으로 해석하지 않는다.
- 동결 입력 재측정: `thread_input_eval.py` → v1/v2 120문항의 기존 connections 경로와 업로드 파서 결과 모두 일치, 오류 0, 두 동결 SHA-256 일치. `evals/results/threads/input_regression_2026-11-09.json`에 비민감 결과를 기록했다.
- 실제 모델 재측정: 사전 등록한 4문항 전부 완료, 사용자 ID 일치 4/4, LLM 23회, 82.7초, 보수적 예약액 $0.89312, 실제 청구액 미확인. `live_smoke_2026-11-09.json`에 기록했다. 채점은 정답 근거 인용 1·올바른 거절 1·과잉 거절 1·오답 근거 1이다. 성능 향상이나 70문항 전체 점수로 주장하지 않는다. 코드는 4e0963b+미커밋 변경이며 이 실행은 이후 추가한 재개 버전 guard 전이다(모델/프롬프트/판정 경로는 동일). 공유 코퍼스는 실행 시점 읽기이며 DB 스냅샷을 동결하지 않았다.
- 남은 팀 작업: 조장이 SPEC 4·8.5·8.6과 SOJAFIT의 기존 상태 설명/012 불일치를 검토·반영해야 한다. DB 정의서 A-02는 이번 기능에 맞게 사용자 ID와 thread UUID를 구분했다. 실제 서비스 DB 적용은 대상·백업·권한 검토 후 명시적인 setup 명령으로, 배포·운영 UI 확인은 별도로 진행한다. 새 의존성·원격 push·PR 생성은 없다.
- 준비 명령 검증: 로컬 DATABASE_URL만 프로세스 환경에 지정해 `uv run --no-sync --offline python -m backend.conversations --setup` 재실행 exit 0. 이후 sojafit_agent의 circuits/threads/messages/approvals 및 checkpoints/checkpoint_blobs/checkpoint_writes/checkpoint_migrations/store/store_migrations 10개 표를 조회했다. 실제 서비스 DB에서 setup을 실행한 증거는 아니다. 최종 `git diff --check` 통과.

## 2026-11-05 Google 로그인 작업서 파일 배치 정리
- 한 일: 사용자 요청에 따라 별도 구현 계획의 내용을 `docs/specs/google-admin-login.md`의 구현 계획 절에 합쳤다. 기존 `google-admin-login-plan.md`는 내용 대조 후 제거하고 `SOJAFIT.md` 트리와 `docs/specs/SPECS.md`의 파일 목록을 한 파일 기준으로 정리했다. 아래 과거 기록의 계획 파일 이름은 당시 작업 이력이다.
- 확인 방법: 계획 본문을 통합 파일에 기록한 뒤 내용이 일치함을 확인하고 기존 파일을 제거했다. `.\.venv\Scripts\uv.exe run --no-sync --offline pytest -q tests/repo/test_repo_layout.py -p no:cacheprovider` 결과 `5 passed`. 필수 다섯 절과 구현 계획 여섯 단계를 확인했고 `git diff --check`도 통과했다. 코드·DB·클라우드는 변경하지 않았다.
- 재발 방지: 파일을 만들기 전에 트리와 해당 폴더 설명의 '넣는 것·넣지 않는 것'을 확인하고, 추가 후 트리·목록·문서 내용 적합성을 함께 대조한다. 구조 테스트 통과와 사람의 내용 검토 결과를 구분한다.
- 미확인: 팀장의 SPEC·관리자 운영 절차 검토, Google 로그인 구현과 실제 인증 검증.

## 2026-11-05 Google 관리자 로그인 구현 계획
- 한 일: 사용자의 요청에 따라 Google 계정과 기존 비밀번호를 함께 쓰는 관리자 로그인 구현 계획을 작성했다. 격리 DB, 인증 검증, 연결·회수, 기존 API 회귀와 운영 검토를 단계별로 분리했다.
- 바꾼 파일: `docs/specs/google-admin-login-plan.md`, `docs/specs/google-admin-login.md`, `docs/specs/SPECS.md`, `SOJAFIT.md` 신규 파일 한 줄 및 이 작업 기록. 설계의 임시 쿠키는 로컬 HTTP와 배포 HTTPS의 Secure 차이를 명시했다.
- 확인 방법: 현재 인증 코드·DB 폴더 규칙·설계와 계획을 대조하고 문서 변경을 확인했다. 구현·DB 변경·외부 연결·테스트는 수행하지 않았다.
- 미확인: 팀장 SPEC 검토, 관리자 승인·회수 책임자, 운영 DB 백업·복구, Google 계약과 로그 보관 경로, 실제 Google 로그인.

## 2026-11-05 Google OAuth 기본 설정
- 한 일: 사용자의 Google API 사용자 데이터 정책 동의와 웹 OAuth 클라이언트 생성 요청을 확인하고, SojaFit 프로젝트에 OAuth 앱과 웹 클라이언트를 생성했다. 앱 대상은 외부, 게시 상태는 테스트 중이다.
- 리디렉션: Cloud Run과 localhost:8000의 `/api/auth/google/callback`을 등록했다. 이는 미구현 경로이며 실제 로그인에 성공했다는 뜻이 아니다. 클라이언트 비밀과 ID는 기록하지 않았다.
- 확인: 콘솔에서 OAuth 구성 및 클라이언트 생성 결과, 테스트 상태와 테스트 사용자 0명을 확인했다. 사용자 추가·비밀 관리·코드·DB·배포는 수행하지 않았다.
- 다음 할 일: 설계 승인과 구현 계획, 관리자 승인·회수 절차, 실제 콜백 구현, 비밀의 안전한 전달·저장, 테스트 사용자 적용 여부와 전체 인증 흐름을 확인한다.
- 설계 반영: 사용자의 요청으로 `docs/specs/google-admin-login.md`에 생성된 OAuth 앱·웹 클라이언트, 테스트 상태, 등록한 두 콜백 주소와 기존 `/me`·`/logout` 재사용 계획을 반영했다. GCP 설정과 미구현 기능, 비밀 주입 미확인을 구분했다. 문서 대조와 diff 검사를 수행하며 코드·DB·클라우드는 추가 변경하지 않는다.
- 추가 결정: 사용자는 Google에 연결된 관리자에게 기존 SojaFit 비밀번호 로그인도 허용하는 A안을 선택했다. 설계안에 두 로그인 방법과 전체 관리자 권한 회수 시 두 방법·기존 세션을 함께 차단해야 함을 반영했다. 문서 확인만 했으며 구현이나 테스트는 하지 않았다.

## 2026-11-05 Google 관리자 로그인 설계
- 한 일: 사용자가 선택한 기존 인증 유지 방식과 팀원별 개인 Gmail 사용을 기준으로 Google 관리자 로그인 검토안을 작성했다. 신원 검증, 사전 승인, 권한 회수, 기존 세션 호환 및 수용 기준을 정리했다.
- 바꾼 파일: `docs/specs/google-admin-login.md`, `docs/specs/SPECS.md`, `SOJAFIT.md` 신규 파일 트리 한 줄, 이 기록.
- 확인 방법: 기존 인증 코드·SQL·작업서 및 Google 공개 문서를 대조했다. 코드·DB·클라우드 설정 변경과 인증 테스트는 하지 않았다.
- 미확인 및 다음 할 일: 설계 승인, 팀장 SPEC 검토, 승인·권한 회수 운영 절차, Google Cloud 계약·로그 경로와 운영 DB 백업·복구 경로 확인 후 구현 계획을 작성한다.

## 2026-11-05 로그인 개인정보 및 Cloud Logging 검토
- 한 일: 로그인 코드와 개인정보 처리방침·보관·삭제·관리 권한을 대조하고, 로그인 라이브러리와 Google Cloud·Supabase의 공개 데이터 처리 조건을 검토했다. 개인정보 처리방침, 보관·삭제 기준과 외부 사업자 계약의 팀별 적용 내용은 추가 확인이 필요하다.
- 사용자 확인: 팀 GCP 로그 버킷은 `_Default` 30일, `_Required` 400일이며 둘 다 `global`이다. 사용자가 제공한 로그 라우터 화면에서 두 싱크가 활성이고 각각 같은 이름의 버킷을 대상으로 함을 확인했다.
- 싱크 필터: `_Default`의 포함 필터는 지정된 감사·시스템 이벤트 로그 6종을 제외하며 별도 제외 필터는 없었다. Cloud Run 요청 로그는 해당 포함 조건을 충족하나 상위 조직·폴더 라우팅 및 실제 저장 버킷은 별도 확인이 필요하다.
- 사용자 확인: 로그인 요청 조회 화면에는 정보 11건·경고 7건이 표시됐다. 공유된 요청 로그 한 건은 POST 로그인 API의 403이며, 표시된 `httpRequest` 필드에는 접속 IP가 있고 이메일·비밀번호·쿠키 값은 보이지 않았다. IP 등 실제 값은 기록하지 않는다. 다른 로그와 컨테이너 출력에 대한 검증은 아니다.
- 확인 방법: 사용자 제공 콘솔 화면·필터·로그 필드와 코드, Google Cloud·Supabase 공식 문서를 읽기 전용으로 대조했다. 코드·클라우드 설정 변경이나 신규 테스트는 하지 않았다.
- 확인 못 한 것 및 다음 할 일: 성공 200 요청과 컨테이너 로그의 민감정보 포함 여부, 로그의 실제 저장 경로·다른 내보내기 경로, 외부 사업자 계약과 개인정보 정책을 확인한다. 백업·복구 결정은 팀의 후속 과제로 남는다.

## 2026-11-05 배포 평가 계정 로그인 확인
- 한 일: 사용자가 만든 평가 계정 두 개로 Cloud Run `POST /api/auth/login`을 각각 실행해 둘 다 HTTP 200을 확인했다고 보고했다. Swagger에서 현재 로그인 세션의 `GET /api/auth/me`도 200과 일반 사용자 역할을 반환했다. `POST /api/auth/logout`은 200, 로그아웃 직후 `GET /api/auth/me`는 401을 반환했다.
- 확인 방법과 결과: 실제 배포 주소의 Swagger UI로 로그인→세션 조회→로그아웃→세션 없는 접근 흐름을 확인했다. 비밀번호, 이메일, 사용자 ID, 쿠키·토큰은 작업기록에 남기지 않았다. 테스트 후 Swagger가 새로고침 뒤에도 요청 입력을 복원하는 것을 확인해 브라우저를 `/health`로 이동했다. `/health`는 `{"status":"ok"}`을 반환했다.
- 사용자 추가 확인: 잘못된 비밀번호 1회는 `401`, 이어 올바른 비밀번호는 로그인 성공. 서로 다른 브라우저에서 각 계정의 세션을 확인했고 한쪽 로그아웃 뒤 다른 쪽 세션은 유지됐다. 일반 사용자로 관리자 API를 호출했을 때 `403`이었다. 이 결과는 사용자가 Swagger에서 직접 확인했다고 보고했다.
- 사용자 추가 확인: 관리자 API로 테스트 계정을 비활성화했고, 해당 계정의 로그인 시도가 `401`로 거부됐다.
- 사용자 추가 확인: 접속 중인 계정을 비활성화한 뒤 기존 세션의 `GET /api/auth/me`가 `401`, 다시 활성화한 뒤에도 기존 세션은 `401`이었다. 이후 로그아웃은 `200`, 새 로그인은 `200`이었다. 비활성화로 기존 세션이 폐기되고 재활성화만으로 복구되지 않으며 새 로그인이 가능한 흐름을 사용자가 확인했다고 보고했다.
- 배포 확인: Cloud Run에서 `GET /login`을 다시 열었으나 `404 Not Found`였다. 현재 배포본은 실제 로그인 화면 검증을 진행할 수 없고, 로그인 API는 Swagger에서 확인하는 상태다.
- 배포 쿠키 확인: 사용자가 안전한 PowerShell 확인을 실행해 Cloud Run 로그인 `200`, 세션 조회 `200`, 로그아웃 `200`을 확인했다. 응답의 쿠키 속성은 `HttpOnly`, `Max-Age=28800`(8시간), `Path=/`, `SameSite=lax`, `Secure`였다. 토큰과 비밀번호는 작업 기록에 넣지 않았다.
- 확인 못 한 것: 실제 로그인 화면(`/login`)은 배포본에서 `404`이므로 UI 검증은 미완료다. 질문 API는 로그인 범위에서 제외한다.
- 다음 할 일: 실제 `/login` 화면이 배포본에 반영된 뒤 화면 로그인 흐름을 검증한다. 평가 종료 후 계정 제거 절차와 DB 백업·복구 결정도 팀과 정한다.

## 2026-11-04 테스트 Supabase 인증정보 저장 확인
- 사용자에게 설명한 뒤 개인 `sojafit-auth-test` 인증 표가 비어 있는지 확인하고, 실제 `auth.provision()` 경로로 합성 사용자 1명을 생성했다. DB에 이메일은 원문, 비밀번호는 scrypt 해시로 저장됨을 확인하고 입력 비밀번호의 해시 검증이 통과했다. 값과 해시는 출력하지 않았다.
- 실제 FastAPI TestClient 로그인 성공과 DB 세션 토큰 값이 원문이 아닌 HMAC 검증값임을 확인했다. 이 시험에서 만든 계정·세션·실패기록만 정리하고 계정과 실패기록 부재를 확인했다. DB 시퀀스는 증가할 수 있다.
- 운영 DB·Cloud Run·검색 데이터는 건드리지 않았다. 로그·백업 저장 여부, 이메일 암호화 정책, 배포 환경 전체는 확인하지 않았다.

## 2026-11-04 로컬 격리 DB에서 제한 역할 로그인·검색 시험
- 사용자 요청에 따라 기존 DB와 분리된 일회성 `pgvector/pgvector:pg16` Docker 컨테이너를 loopback 임의 포트에 만들고, 인증·검색 스키마 및 합성 문서 3건만 적재했다. 외부 API는 호출하지 않았다.
- 제한 역할로 실제 FastAPI 로그인·me 성공 후, 검색 테이블 권한이 없으면 `warmup()`이 InsufficientPrivilege로 거부되는 것을 확인했다. 검색 표 4개 SELECT 권한을 추가한 뒤 BM25 방식의 실제 `retrieve()`가 합성 문서·페이지를 반환했고, 로그인 유지·로그아웃 및 검색 표 DELETE 거부를 확인했다.
- 생성한 정확한 임시 컨테이너 ID를 지정해 컨테이너와 익명 볼륨을 제거했고 이름 접두어로 남은 컨테이너가 없음을 확인했다. 기존 Supabase, 로컬 인증 DB, 운영 DB, `.env`, 코퍼스는 변경하지 않았다.
- 범위: 단일 사용자·합성 데이터·BM25만 검증했다. Voyage dense/리랭크, 실제 검색 DB의 RLS·권한, 동시성·운영 배포 및 검색 품질 평가는 검증하지 않았다. SELECT를 부여한 4개 중 BM25 경로에서 직접 읽은 표는 문서·청크다.

## 2026-11-04 로그인·검색 통합 시험 환경 확인
- Docker 컨테이너·이미지 목록을 읽기 전용으로 확인했다. 현재 실행 중인 SojaFit 인증 DB는 일반 postgres:16이며, pgvector 이미지와 이전에 멈춘 SojaFit 컨테이너는 존재한다. 멈춘 컨테이너의 데이터나 용도는 이번에 검증하지 않아 재사용하지 않았다.
- 인증·검색을 함께 검증한 격리 환경은 아직 확인하지 못했다. 기존 Supabase 인증 DB·검색 데이터·pgvector 및 컨테이너 상태를 변경하지 않았다.

## 2026-11-04 로그인 제한 역할의 검색 DB 영향 점검
- `backend/rag/retrieve.py`와 MCP 검색 호출을 읽어 같은 DATABASE_URL을 사용하고 검색이 `document_chunks`, `source_documents`, `chunk_embeddings`, `chunk_embedding_bits` 조회 및 pgvector 형식 등록을 사용함을 확인했다. 실제 권한은 대상 DB의 역할·RLS·확장 설정에 따라 검증해야 한다.
- 개인 Supabase 인증 테스트 프로젝트를 읽기 전용 조회한 결과 위 검색 표 4개와 vector 확장이 없었다. 인증 전용 DB를 검색용으로 변경하거나 확장·데이터를 적재하지 않았다.
- 따라서 앞선 제한 역할의 검색 성공은 검증할 수 없다. 팀 검색 담당과 검색 DB·권한 구조가 정해지면 격리된 검색 DB에서 인증·검색을 함께 시험해야 한다. 기존 연결 설정과 역할은 변경하지 않았다.

## 2026-11-04 제한 DB 역할로 실제 인증 API 시험
- 사용자 요청으로 개인 `sojafit-auth-test`의 인증 표 3개가 비어 있음을 확인하고, 별도의 임시 LOGIN 역할과 이 역할에만 적용되는 시험 RLS 정책을 만들었다. 역할에는 superuser·BYPASSRLS·CREATEROLE을 주지 않았고, 이메일·비밀번호는 합성값을 사용했다. 기존 `.env`는 변경하지 않았다.
- 임시 역할로 TLS `verify-full` 연결과 DB 양쪽 구간 암호화를 확인한 뒤 실제 FastAPI TestClient에서 오답 401, 사용자 A/B·관리자 로그인 및 me, 일반 사용자 관리자 접근 거부, 이메일 마스킹, A 로그아웃 후 B 유지, B 비활성화 후 세션 거부가 통과했다.
- finally에서 이번 합성 사용자·세션·시도 기록, 시험 정책과 DB 역할만 삭제했다. 이후 역할·계정·정책·실패기록이 남지 않았음을 확인했다. 테스트 과정에서 DB 시퀀스 값은 증가할 수 있다. 비밀번호·토큰·접속 문자열은 출력하지 않았다.
- 시험은 인증 API 범위에 한정하며 검색·별도 계정 생성 CLI·부하·배포 환경은 검증하지 않았다. 시험 RLS는 해당 백엔드 역할의 인증 표 전체 행을 허용하므로 사용자별 데이터 격리를 의미하지 않는다. 운영 DB와 기존 연결 설정은 변경하지 않았다.

## 2026-11-04 인증 DB 임시 제한 권한 시험
- 개인 `sojafit-auth-test`의 인증 표가 비어 있는지 확인하고 단일 트랜잭션에서 NOLOGIN·NOSUPERUSER·NOBYPASSRLS 시험 역할, 표 권한과 역할 전용 임시 RLS 정책, 합성 계정 한 건을 만들었다. 종료 시 전부 롤백했고 역할 잔존 false·시험 정책 0건을 확인했다.
- 첫 시험은 역할 전환 단계에서 InsufficientPrivilege(42501)로 실패했다. 원인은 생성한 역할로의 SET 권한 부재였다. 같은 시험에서 postgres에 SET 권한을 트랜잭션 내 임시 부여해 재실행했고, 계정 잠금 조회·변경, 로그인 시도 CRUD, 세션 생성·갱신·삭제, advisory lock의 대표 SQL이 통과했다.
- 이 시험은 실제 로그인 API 전체·독립 DB 로그인·검색을 검증하지 않는다. 시험 RLS는 신뢰된 백엔드 역할의 해당 표 전체 행을 허용하므로 사용자별 소유권 격리를 뜻하지 않는다. 지속 역할·비밀번호·RLS·기존 DATABASE_URL과 운영 DB는 변경하지 않았다.

## 2026-11-04 인증 DB 최소 권한 사전 점검
- `backend/auth.py`의 SQL 호출을 읽어 계정 조회·관리, 세션 생성·조회 갱신·삭제, 로그인 실패 기록 CRUD와 계정 생성 CLI·advisory lock 사용을 확인했다. 검색도 같은 DATABASE_URL을 쓰므로 인증용 권한만으로 전환하면 검색에 영향이 있을 수 있다.
- 테스트 Supabase의 인증 표 3개는 postgres 소유, RLS 활성, 정책 없음이며 advisor는 정책 없음 INFO 3건을 보고했다. 전용 역할에는 GRANT뿐 아니라 자체 세션 방식에 맞는 RLS 접근 경계가 필요하다.
- 읽기 전용 조사만 했으며 역할·정책·설정·데이터를 변경하지 않았다. 새 역할로 실제 로그인·검색 검증은 미실행이다.

## 2026-11-04 로컬 Supabase DB 연결 인증서 검증 설정
- 사용자 요청에 따라 로컬 `.env`에서 `sojafit-auth-test` 대상임을 확인한 뒤 DATABASE_URL에 `sslmode=verify-full`과 저장소 밖 테스트용 공개 CA 경로만 추가했다. 다른 설정·비밀값은 출력하거나 변경하지 않았다. Compose가 자체 DATABASE_URL을 우선한다는 경계는 유지한다.
- 변경 전 실제 `backend.auth.connection()`으로 올바른 CA 연결 성공과 없는 CA 연결 실패를 확인했다. 변경 후 `.env`를 읽은 같은 연결로 인증서·서버명 검증 및 읽기 전용 SELECT 1이 성공했고 클라이언트→풀러 및 풀러→DB TLS는 모두 true였다.
- 인증 테스트는 샌드박스 안에서 멈춰 중단한 뒤, `TEST_AUTH_DATABASE_URL`을 비우고 같은 명령을 재실행해 19 passed, 15 skipped. DB 통합 시험은 수행하지 않았다.
- 공개 CA 경로는 현재 PC의 Codex 작업 폴더 전용이다. 다른 PC·배포·팀 DB에서는 해당 DB의 CA를 준비하고 연결 설정을 따로 바꿔야 한다. 실제 실행 프로세스가 새 환경변수를 읽게 재시작해야 하며, 서비스 DB·Cloud Run·Compose·pgvector·인증 데이터는 변경하지 않았다.

## 2026-11-04 테스트 Supabase SSL 강제 적용
- 사용자에게 재시작·일시 연결 중단과 테스트 프로젝트 범위를 설명한 뒤 `sojafit-auth-test`의 Enforce SSL을 활성화했다. 대시보드에서 활성화 상태와 성공 알림을 확인했다. 운영 DB는 변경하지 않았다.
- 공식 CA를 지정한 `sslmode=verify-full` 연결로 읽기 전용 `SELECT 1`이 성공했다. 클라이언트→풀러 TLS와 DB가 관측한 풀러→PostgreSQL SSL 모두 true였다. 비밀번호를 비운 비암호화 연결 시도는 SSL 관련 오류로 거부됐다.
- `.env`와 애플리케이션의 기본 SSL 검증 설정은 변경하지 않았다. 따라서 verify-full 성공은 이번 시험에 한정된다. 배포 환경과 다른 DB 적용은 확인하지 않았다.

## 2026-11-04 테스트 DB 서버 인증서 검증 시험
- `sojafit-auth-test` Supabase 대시보드의 Database Settings에서 제공하는 공개 CA 인증서를 저장소 밖 Codex 작업 폴더에 받아 형식을 확인했다. 비밀키는 포함되지 않았다.
- 로컬 `.env`의 테스트 DB 연결에 인증서 경로와 `sslmode=verify-full`을 일회성으로 지정하여 읽기 전용 `SELECT 1`을 수행했다. 연결과 서버 인증서·호스트명 검증이 성공했고 클라이언트→풀러 TLS 사용을 확인했다.
- 대시보드에서 SSL 강제 설정은 꺼져 있었다. 이번 단계는 일회성 연결 시험이며 `.env`·애플리케이션 설정, SSL 강제 설정, DB 데이터는 바꾸지 않았다. 풀러→DB 연결 암호화와 배포 환경은 별도 검토가 필요하다.

## 2026-11-04 인증 통신·저장 보호 재점검
- Supabase 테스트 프로젝트가 ACTIVE_HEALTHY임을 재확인했다. 현재 로컬 `.env`는 비데모 모드, HTTPS 형식 AUTH_ORIGIN, 32바이트 이상 AUTH_SECRET이 설정돼 있다. 값은 출력하지 않았다. Compose는 자체 DB 주소를 우선하므로 이 결과를 Compose 설정으로 일반화하지 않는다.
- 테스트 DB 풀러 접속에서 클라이언트 구간 TLS 사용을 확인했으나 DB `pg_stat_ssl`은 false였다. 명시적 sslmode가 없고 `verify-full` 읽기 전용 연결은 로컬 루트 CA 파일이 없어 실패했다. 서버 인증서 신뢰·호스트명 검증 성공 및 SSL 강제 상태는 미확인이다.
- Supabase 공식 FAQ는 DB·백업 저장 암호화를 설명하나 프로젝트 백업 보유·복원은 확인하지 않았다. DB 저장 암호화는 이메일 필드 암호화를 뜻하지 않는다.
- 보안 advisor는 인증 표의 정책 없음 INFO 3건을 보고했다. 운영 Cloud Run의 HTTPS·쿠키·DB 설정, 실제 로그와 백업 복원은 확인하지 않았다. DB·설정·데이터 변경 없이 읽기 전용으로 점검했다.

## 2026-11-04 Supabase 인증 DB 연결 및 교체 전 읽기 전용 점검
- 현재 `.env`의 DB 접속 대상 식별자가 `sojafit-auth-test`와 일치했고 PostgreSQL 연결과 인증 표 3개 존재를 확인했다. 비밀값과 연결 문자열은 출력하지 않았다.
- Supabase에서 두 인증 마이그레이션 이력, 인증 표 3개의 RLS 활성화와 `anon`/`authenticated`의 SELECT·INSERT·UPDATE·DELETE 실효 권한이 없음을 확인했다. security advisor는 정책 없음 INFO 3건을 보고했다. 자체 세션과 백엔드 역할에 맞춘 정책 검토가 필요하다.
- 연결은 풀러를 사용한다. 클라이언트→풀러 구간은 현재 설정과 `sslmode=require` 시험 모두 TLS 사용으로 확인됐다. DB의 `pg_stat_ssl`에서 관측한 풀러→PostgreSQL 구간은 SSL false였다. 전체 전송 구간 보호를 확정하지 않고 공급자 설정·구조 확인이 필요하다. 명시적 sslmode와 서버 인증서 검증은 확인되지 않았다.
- 현재 접속 역할은 postgres 계열로 최소 권한이 아니다. 실제 Cloud Run 연결 대상, 배포 로그인, HTTP 쓰기 차단, 저장·백업 암호화는 확인하지 않았다. DB·계정·설정·pgvector는 변경하지 않았다.

## 2026-11-04 Supabase 테스트 DB 실제 로그인 흐름 검증
- 합성 사용자 A/B와 관리자를 임시 생성하고 `FastAPI TestClient`로 실제 `.env` DB를 사용하는 인증 API를 검증했다. 오답 비밀번호 401, 3계정 로그인·내 정보, HttpOnly/SameSite 쿠키, A 로그아웃 후 A 401·B 유지, 교차 Origin 403, 일반 사용자 관리자 목록 403, 관리자 목록 이메일 마스킹, 계정 비활성화 후 기존 세션 401이 통과했다.
- 첫 실행은 테스트 스크립트의 관리자 이메일 마스킹 기대값 오류로 검증이 중단됐으나, finally 정리가 실행됐다. 기대값을 `auth.mask_email()`과 비교하도록 바로잡아 동일한 검증을 재실행했고 모든 항목이 통과했다.
- 테스트 후 정확한 합성 계정 ID와 그 사용자 세션, 이메일 SHA-256 로그인 실패 행만 정리했다. 읽기 전용 재조회 결과 users/sessions/login_attempts 각각 0건이다. 비밀번호·세션 토큰은 출력·기록하지 않았다.
- 범위: Supabase 테스트 프로젝트의 FastAPI API 흐름만 검증했다. Cloud Run, UI 브라우저 흐름, HTTP API의 쓰기, 평가계정, 운영 최소 권한 역할은 미검증. pgvector와 다른 테이블은 변경하지 않았다.

## 2026-11-04 Supabase HTTP Data API 공개 접근 확인
- `.env`의 프로젝트 URL과 publishable 키 형식만 검증해 값은 출력하지 않고, publishable 키를 사용해 `users`, `auth_sessions`, `auth_login_attempts`에 각각 읽기 전용 HTTP GET을 보냈다.
- 결과: 세 요청 모두 HTTP 401로 거부됐다. 이 결과는 현재 공개 키로 Data API 인증 테이블을 읽지 못함을 확인한다. DB 권한 단계에서 `anon`/`authenticated` SELECT 거부도 별도 확인했다.
- 주의: 키 값은 publishable 형식이지만 `.env` 변수 이름이 `SUPABASE_SERVICE_ROLE_KEY`다. 기능 영향은 시험에 없었으나 이름과 값 유형이 달라 혼동될 수 있다. 키 값은 기록하지 않았다.
- 범위: GET만 수행했으며 계정·DB·Cloud Run·pgvector는 변경하지 않았다. 로그인 API의 합성 계정 E2E는 아직 실행하지 않았다.

## 2026-11-04 테스트 DB 인증 표 접근 제한 적용
- 사용자 승인으로 Supabase 테스트 프로젝트에 `restrict_auth_tables_public_access` 마이그레이션을 적용했다. 인증 표 3개와 `users_id_seq`의 PUBLIC·anon·authenticated 권한을 회수하고 세 표에 RLS를 활성화했다. 별도 정책은 생성하지 않았다.
- 확인: 세 표의 RLS 활성, anon/authenticated의 표 실효 권한과 시퀀스 권한 없음. 실제 DB 역할 전환으로 각 역할의 세 표 SELECT가 모두 거부됐다(6건). `.env` 백엔드 역할로 세 표 읽기 및 합성 데이터 INSERT·UPDATE·DELETE가 성공했으며 트랜잭션은 롤백했다.
- Supabase security advisor에서 기존 RLS 비활성 ERROR는 사라지고 정책 없음 INFO 3건으로 바뀌었다. 테이블 세 개의 행 수는 변경 전 0건이었다. HTTP Data API, 로그인 흐름과 Cloud Run은 이번에 시험하지 않았다.
- 남은 일: HTTP API 접근 및 로그인 시험, 백엔드 전용 최소 권한 역할과 개인정보 정책을 검토한다. pgvector·다른 테이블은 변경하지 않았다.

## 2026-11-04 인증 테이블 보호안 준비
- 확인: 테스트 프로젝트의 인증 표 3개는 `postgres` 소유, RLS 비활성 및 정책 없음. `anon`/`authenticated`의 표 SELECT와 `users_id_seq` USAGE 실효 권한이 있다. `.env`의 접속 역할은 `postgres`이고 해당 역할은 RLS 우회 속성이 있다.
- 한 일: 인증 표 3개와 ID 시퀀스에 국한한 공개 역할 권한 회수·RLS 적용 SQL 및 적용 후 검증·실패 처리 방침을 `docs/specs/login-completion-plan.md`에 준비했다. Supabase 보안 advisor가 RLS 변경을 사용자 검토 대상으로 안내해 아직 DB 변경은 실행하지 않았다.
- 확인 못 한 것: 공개 API 차단과 백엔드 인증 CRUD의 변경 후 동작, 최소 권한 전용 역할, Cloud Run DB 연결. 인증 계정 적재와 pgvector 변경은 하지 않았다.

## 2026-11-04 Supabase 인증 보안 작업 준비
- 한 일: `sojafit-auth-test` 보안 advisor, public 인증 표 목록·RLS·행 수 및 `information_schema.role_table_grants`를 읽기 전용으로 확인하고 로그인 완료 계획에 현재 상태와 작업 순서를 추가했다.
- 결과: 인증 표 3개는 각 0행, RLS 비활성. `anon`/`authenticated`는 세 표 각각 SELECT·INSERT·UPDATE·DELETE 등을 직접 부여받았다. advisor는 세 표 모두 RLS 미적용 ERROR를 보고한다.
- 다음 할 일: Data API 노출과 상속·시퀀스 권한 및 백엔드 역할을 확인하고 인증 표만의 권한 회수·RLS 적용과 접근 검증을 진행한다. 사용자의 지시에 따라 별도 `TEST_AUTH_DATABASE_URL` 설정은 현재 범위에서 제외한다.
- 확인 못 한 것: 변경 후 실제 API 차단 및 백엔드 접근, 이메일 정책 팀 합의, Cloud Run 대상과 로그인. DB 설정·계정·pgvector는 변경하지 않았다.

## 2026-11-04 Supabase 테스트 DB 연결 확인
- 사용자 요청으로 `.env`의 DB 대상이 `sojafit-auth-test` 프로젝트인지 확인한 뒤 읽기 전용 PostgreSQL `SELECT 1`을 실행해 성공했다. 인증 계정이나 테이블 데이터는 조회·변경하지 않았다.
- 앞선 비밀번호 재설정 화면 확인 과정에서 새 비밀번호가 도구 출력에 표시되어 사용자에게 재설정을 안내했고, 사용자가 다시 변경한 뒤 연결 확인을 진행했다. 비밀번호 및 연결 문자열은 작업기록에 적지 않는다.
- 확인하지 못한 것: 로그인 API의 DB 연동, Cloud Run의 DB 대상 및 배포 로그인. 이전에 확인된 인증 테이블 RLS·권한 문제는 재검증과 조치가 필요하며, 그 전에는 계정·개인정보를 적재하지 않는다. pgvector는 변경하지 않았다.

## 2026-11-04 로그인 재검증 및 남은 작업 재확인
- 실행: `TEST_AUTH_DATABASE_URL`을 지정하지 않고 `.venv/Scripts/python.exe -m pytest tests/api/test_auth.py -q -rs -p no:cacheprovider`를 실행했다. 샌드박스 내부에서는 첫 테스트 이후 대기해 중단했고, 샌드박스 밖 재실행은 `19 passed, 15 skipped`였다. 15건은 격리 인증 테스트 DB가 필요한 사례다.
- 확인: DB 없는 비밀번호 해시·Origin 거부·입력값 노출 방지·관리자 이메일 마스킹 등은 통과했다. 오전의 격리 DB `34 passed` 및 합성 계정 흐름은 과거 실행 기록이며 이번 재검증 결과가 아니다.
- 차단 및 재개: 현재 `TEST_AUTH_DATABASE_URL`이 없어 DB 통합 테스트를 다시 실행하지 않았다. 격리 테스트 DB의 현재 상태와 접속을 확인하고 전용 주소를 안전하게 지정한 뒤 15건을 재실행한다. Cloud Run의 실제 DB 대상·인증 스키마와 배포 로그인 흐름은 별도 확인이 필요하다.
- 범위: 개인 Supabase 프로젝트는 이번 작업 대상에서 제외한다. 인증 코드·DB·pgvector·배포 설정은 변경하지 않았다. 사용자 소유권, 개인정보 보관 정책 및 평가 계정은 기존 계획에 따라 후속 검토한다.

## 2026-11-04 Supabase 인증 테스트 프로젝트 준비 — RLS 점검 대기
- 한 일: 사용자 선택에 따라 `SimonTH-0912's Org` Free 조직에 월 `$0` 생성 견적을 확인하고 서울 리전의 `sojafit-auth-test` 프로젝트를 만들었다. 생성 직후 `ACTIVE_HEALTHY` 상태였다.
- 스키마: 새 프로젝트의 빈 public 스키마에 `003_auth.sql` → `005_auth_attempt_window.sql` → `006_user_roles.sql`만 migration `sojafit_auth_test_schema`로 적용했다. 실제 설치 확장은 `pg_stat_statements`, `pgcrypto`, `plpgsql`, `supabase_vault`, `uuid-ossp`; vector는 설치되지 않았다. 코퍼스/업무 데이터와 pgvector는 변경하지 않았다.
- 보안 차단: `users`, `auth_sessions`, `auth_login_attempts`에 RLS가 꺼져 있고 `anon`/`authenticated`에 CRUD 등 표 권한이 확인됐다. Supabase advisor도 `rls_disabled_in_public` ERROR를 보고했다. Supabase 지침에 따라 RLS를 임의 적용하지 않았고 계정/개인정보는 적재하지 않았다.
- 검증 범위: project status·초기 public tables·migrations·extensions·테이블 구조·role grants·security advisors를 MCP로 읽었다. Supabase 프로젝트에서 FastAPI 테스트를 실행하지 않았고 Cloud Run 및 `DATABASE_URL`도 연결하지 않았다.
- 문서: `docs/research/supabase-auth-test-runbook.md`에 생성 과정, 확인 결과, RLS 점검 SQL, 중단 사유와 재개 절차를 기록했다. `RESEARCH.md`와 `SOJAFIT.md`에는 새 파일 경로를 등록했다.
- 다음 할 일: anon/authenticated 접근 차단과 trusted backend DB role을 확정한 뒤 RLS/권한을 적용하고, 비밀값을 공유하지 않는 방식으로 `TEST_AUTH_DATABASE_URL`을 연결해 인증 테스트를 수행한다.
## 2026-11-04 테스트 DB 합성 계정 로그인 흐름
- 한 일: 연결 유지 중인 `sojafit-auth-test-local`에 합성 사용자 A/B와 관리자 계정 3개를 추가했다. 고정 별칭이 이미 있으면 쓰지 않도록 먼저 검사하고, 기존 계정을 덮어쓰지 않았다. 비밀번호는 테스트 실행 중 무작위 생성해 scrypt 해시만 저장했으며 평문은 출력·보관하지 않았다.
- 확인: 세 계정 로그인과 `/api/auth/me`의 ID/역할 확인, 일반 사용자 관리자 목록 거부(403), A 로그아웃 후 A 세션 거부(401)와 B 세션 유지, 관리자가 B를 비활성화한 뒤 B 세션 거부(401)를 확인했다. API 응답과 DB 조회에서 비밀번호 해시·세션 토큰은 출력하지 않았다.
- 범위: 이 검증은 loopback 전용 일반 PostgreSQL 테스트 DB만 사용했다. `.env`의 Supabase 주소, Cloud Run, Compose pgvector DB 및 업무 데이터 테이블은 사용·변경하지 않았다. 테스트 계정은 합성 데이터이며 실제 사용자 로그인용이 아니다.
- 바꾼 파일: `docs/specs/login-completion-plan.md`, 이 작업기록. 애플리케이션 코드와 서비스 DB는 변경하지 않았다.
- 다음 할 일: 테스트 DB를 이용해 후속 인증 검증을 진행한다. 실제 서비스 DB 연결 대상은 여전히 특정되지 않았으므로 서비스 DB 적용·Cloud Run 로그인 확인은 해당 대상 식별 후 진행한다.

## 2026-11-04 로컬 인증 테스트 DB 연결 유지
- 한 일: 사용자의 요청에 따라 앞서 일회성으로 검증한 방식으로 후속 작업용 테스트 DB를 다시 연결했다. 일반 `postgres:16` 컨테이너 `sojafit-auth-test-local`을 `127.0.0.1:55434`에만 바인딩하고 실행 상태로 유지한다. 테스트 전용 계정 설정 외에 비밀값이나 `.env`는 변경하지 않았다.
- 적재·확인: 빈 DB에 `003_auth.sql` → `005_auth_attempt_window.sql` → `006_user_roles.sql`만 적용했다. 읽기 전용 카탈로그 확인 결과 public 인증 표는 `users`, `auth_sessions`, `auth_login_attempts`뿐이고 설치 확장은 `plpgsql`뿐이다. 테스트가 만든 합성 행은 users 10, sessions 4, login attempts 3건이다. 이메일과 해시 값은 열람·기록하지 않았다.
- 검증: `.venv/Scripts/uv.exe run --no-sync --offline pytest -q -rs tests/api/test_auth.py -p no:cacheprovider` — `34 passed`, DB 테스트 skip 없음.
- 안전 경계: `.env`의 Supabase 주소와 Docker Compose의 `pgvector/pgvector` DB는 사용하지 않았다. DB 포트는 loopback에만 열려 있고 실제 서비스 DB·Cloud Run·pgvector는 변경하지 않았다. 테스트 컨테이너는 후속 작업을 위해 유지 중이다.
- 다음 할 일: 이 격리 DB를 합성 인증 데이터 검증에 사용한다. 실제 서비스 DB 대상은 여전히 미확인(부재를 확인한 것은 아님)이며, 식별된 뒤에만 별도로 읽기 전용 점검과 담당자 검토를 진행한다.

## 2026-11-04 격리 인증 테스트 DB 연결
- 한 일: 서비스 DB 대상이 확인되지 않아 L04부터 진행했다. `pgvector/pgvector` Compose DB는 사용하지 않고, `postgres:16` 일회용 PostgreSQL을 `127.0.0.1:55434`에만 바인딩했다. 임의 생성한 테스트 비밀번호는 프로세스 메모리에서만 사용했고 출력·파일·저장소에는 남기지 않았다.
- 적용 범위: 빈 테스트 DB에 `003_auth.sql` → `005_auth_attempt_window.sql` → `006_user_roles.sql`만 적용했다. `TEST_AUTH_DATABASE_URL`만 해당 격리 DB를 가리키게 했으며 인증 테스트 종료 후 컨테이너와 프로세스 환경변수를 정리했다.
- 검증: `.venv/Scripts/uv.exe run --no-sync --offline pytest -q -rs tests/api/test_auth.py -p no:cacheprovider` — `34 passed`, DB 관련 skip 없음. 인증 API의 DB 연동·세션 분리·잠금/만료·권한·마스킹 테스트를 확인했다.
- 결과와 경계: 로컬 격리 DB의 인증 흐름은 검증됐지만 Cloud Run 서비스 DB의 존재·제공자·접속 대상은 여전히 미확인이다. 운영 `DATABASE_URL`, Cloud Run, 기존 공유 DB 및 pgvector는 사용하거나 변경하지 않았다. 테스트는 기존 `TEST_AUTH_DATABASE_URL` → 테스트 프로세스의 `DATABASE_URL` override 패턴을 사용한다. 추후 공식 DB로 전환할 때는 대상 인증 스키마를 별도 검토·적용하고 Cloud Run의 `DATABASE_URL` 참조를 전환해야 하며, 현재 코드는 그대로 유지할 수 있다.
- 다음 할 일: L03의 서비스 DB 프로젝트/환경 식별 및 읽기 전용 스키마 확인. DB 담당자 또는 Cloud Run Secret의 비밀값을 노출하지 않는 대상 식별 정보가 필요하다. 그전까지 L05 서비스 DB 적용은 보류한다.

## 2026-11-04 A안 L03 서비스 DB 대상 재확인 — 접근 차단
- 한 일: 사용자의 A안 선택 방향에 맞춰 연결된 Supabase 프로젝트 목록을 새로 조회하고, 저장소의 배포/DB 이력에서 대상 단서를 확인했다.
- 실행 결과: 연결 목록은 `SimonTH-0912's Project`와 `minwon-bot` 두 개이며 모두 `INACTIVE`다. 첫 항목에 PostgreSQL 인스턴스 메타데이터는 있으나 기존 public 테이블 조회는 접근 오류였다. 저장소 기록은 Cloud Run의 `DATABASE_URL`이 Secret 참조라고만 확인하며 실제 Secret 문자열은 읽지 않는다. GCP 명령줄은 이전 확인에서 권한 부족이었고 현재 사용할 수 있는 GCP 읽기 전용 도구도 없다.
- 판정: SojaFit 서비스 DB 대상은 여전히 특정되지 않았다. A안의 실제 저장/백업 암호화, 연결 TLS, 앱·운영 DB 권한은 해당 대상 설정을 보지 못해 검증할 수 없다. Supabase의 일반 보안 문서는 프로젝트별 확인을 대신하지 않는다.
- 바꾼 파일: `docs/specs/login-completion-plan.md` L03 재조회 결과, 이 작업기록. DB·Cloud Run·pgvector·비밀값은 변경하지 않았다.
- 확인 방법: Supabase `list_projects` 읽기 전용 조회, 저장소 배포/DB 기록 검색, 작업계획과 결과 대조. 애플리케이션 테스트는 실행하지 않았다.
- 재개 조건: 서비스 DB 제공자/프로젝트 ref를 알려 주거나 해당 Supabase 프로젝트를 Codex 연결에서 활성화한다. 접속 비밀번호·`DATABASE_URL` 원문은 보내지 않는다. 대상 확인 후 인증 테이블 및 A안 저장/백업·TLS·권한만 읽기 전용으로 점검한다.

## 2026-11-04 이메일 암호화 A안 선택 방향 기록
- 한 일: 사용자가 DB 저장 암호화·접근 통제인 A안을 선택 방향으로 제시해 이메일 옵션 문서와 L02 검증 계획에 반영했다.
- 판정: 앱 계층 이메일 암호화/복호화와 DB 스키마 변경은 선택하지 않은 방향이다. A안에서는 DB 조회 권한을 가진 앱/운영 역할이 이메일 평문을 볼 수 있다. 팀 합의 및 실제 서비스 DB 제공자 상태는 미확인이다.
- 참고 자료: Supabase 공식 FAQ의 일반 저장·백업 암호화 설명, PostgreSQL SSL 강제 및 모드 안내를 반영했다. Cloud Run이 연결한 특정 DB와 프로젝트 설정을 확인한 것은 아니다.
- 바꾼 파일: `docs/research/email-encryption-options.md`, `docs/specs/login-completion-plan.md`, 이 작업기록. DB·Cloud Run·pgvector·비밀값은 변경하지 않았다.
- 확인 방법: 옵션 문서·`login_id` 직접 조회 구조·DB 접근 차단 기록 대조 및 `git diff --check`.
- 다음 할 일: 서비스 DB 제공자/프로젝트를 식별하고 저장·백업 암호화, 연결 TLS/SSL, 최소 권한을 읽기 전용으로 확인한다. 팀이 DB 조회 권한자에게 이메일 평문이 보이는 점을 수용하는지도 정한 뒤 L03/L04를 잇는다.

## 2026-11-04 로그인 이메일 암호화 정책 팀 논의자료
- 한 일: 사용자 요청에 따라 현재 `login_id` 평문 조회/UNIQUE, 로그인·관리자 마스킹 코드와 DB 경계를 확인하고 팀 결정자료를 작성했다. DB 저장 계층 보호, 앱 계층 AEAD+분리 HMAC 검색값, 이메일 대신 별칭/IdP, 단순 결정적 암호화의 프로젝트 범위·난이도·위험을 비교했다.
- 바꾼 파일: `docs/research/email-encryption-options.md`, `docs/research/RESEARCH.md`, `SOJAFIT.md` 트리 한 줄, 이 작업기록. 제안 문서는 합의 전으로 표시했다.
- 참고 근거: Google Cloud KMS envelope encryption/Tink, NIST key management guidance, Python Cryptographic Authority AEAD 문서. 실제 Cloud KMS 비용·권한과 서비스 DB 설정은 확인하지 않았다.
- 확인 방법: 현재 API 조회·DB 열·관리자 이메일 마스킹·문서 위계와 옵션별 영향 대조 및 `git diff --check`.
- 확인 못 한 것: 팀의 보호 목표·채택안·키 운영 담당, 서비스 DB 제공자/저장 암호화·백업·TLS 설정. 정책 선택이나 DB/코드 변경은 하지 않았다.
- 다음 할 일: 팀이 보호 목표와 A/B/C 중 채택안을 결정한다. B를 택하면 조장 SPEC 반영과 기존 이메일의 안전한 이관·키 회전 작업서를 먼저 확정한다. 서비스 DB와 pgvector는 변경하지 않았다.

## 2026-11-04 첨부 체크리스트의 로그인 항목 대조
- 한 일: 외부 제공 `E:/teamproject3/자료/작업-체크리스트.md`의 로그인 관련 5-4, 6-1~6-3 항목을 현재 인증 코드·테스트·DB 작업서 및 최근 확인 결과와 대조했다. 체크리스트는 기준 `main cdbe4a2`, 현재 STH `fdbe30a`는 그 main보다 9커밋 뒤다. 인증 코드·SQL·테스트·로그인 작업서 차이는 없고 `SPEC.md`는 다르다. 통합은 하지 않았다.
- 대조: 6-1 API는 코드상 있음, 로컬 DB 비의존 테스트는 19 passed. 6-2 AUTH_ORIGIN은 같은 출처 로그아웃 200으로 출처 검사만 확인했으며 전체 로그인 미검증. 인증 SQL 적용 및 평가계정 2개는 미확인/미생성. 5-4 사용자별 thread/Store는 namespace 규칙만 있어 미완료. 6-3 Compose DB는 Docker 엔진 접근 거부로 실행 미확인.
- 주의: 첨부의 서비스 DB 항목에 `007`이 있으나 저장소 `db/DB.md`는 해당 SQL을 새 로컬 Compose DB 시드로 규정한다. 이를 서비스 DB에 적용하지 않도록 실행 계획에 경계를 기록했다. 인증 스키마 후보는 `003`, `005`, `006`이다.
- 바꾼 파일: `docs/specs/login-completion-plan.md`, `docs/worklog/sth.md`. 제공된 체크리스트 원본, 브랜치, DB, pgvector와 배포는 변경하지 않았다.
- 확인 방법: 체크리스트 원문 항목, Git 기준 커밋/부모 관계와 인증 관련 파일 비교, `git diff --check`. 코드 테스트는 실행하지 않았다(직전 L01 기록 참조).
- 다음 할 일: 개인정보/이메일 암호화 정책을 담당자가 결정하고 실제 서비스 DB 접근을 확보한 뒤 L03부터 이어간다. `SPEC.md` 인증 변경은 조장 반영 대상이다.

## 2026-11-04 로그인 작업 L02 암호·개인정보 코드 대조
- 한 일: L02에 따라 기존 인증 구현, DB 정의, API, 추적 코드와 회귀 사례를 검토했다.
- 확인: 비밀번호는 salt를 둔 scrypt, 세션은 난수 쿠키와 서버 저장 HMAC-SHA256이며 원문을 DB에 저장하지 않는다. 둘 다 복호화 방식이 아니다. 운영 외 모드는 `AUTH_SECRET` 32바이트 이상을 검사한다. `login_id` 이메일은 DB에 평문 저장·직접 비교하고 `display_name`은 선택 열, 로그인 실패 키는 이메일 SHA-256이다. 실패 행 정리는 만료된 잠금 창을 다음 로그인에서 처리한다. 인증 라우트 코드에는 요청 본문 로깅이 없지만 Cloud Logging/외부 추적 수집은 확인되지 않았다.
- 판정 및 정책 제안(미승인): 합성 테스트에서는 이메일만 쓰고 표시명은 비워 둔다. 비밀번호·쿠키·토큰 원문을 로그/추적에 포함하지 않는다. 이메일 필드 암호화 필요 여부, 계정·실패 행·백업 보관 종료 기준, 운영자 접근, 실제 개인정보 사용 시작 시점은 조장/서비스 담당 결정이 필요하다. 이메일 암호화는 현재 조회·UNIQUE 구조 변경 설계가 선행돼야 한다.
- 바꾼 파일: `docs/specs/login-completion-plan.md`, `docs/worklog/sth.md`. 보안 구현·개인정보 정책·DB는 변경하지 않았다.
- 확인 방법: `tests/api/test_auth.py` 전체 `19 passed, 15 skipped`; skip은 모두 격리 DB 필요 사례. 애플리케이션 테스트는 이번 코드 대조 전에 L01에서 실행한 결과이며, 로그 수집 설정이나 DB 저장 암호화 확인 결과로 해석하지 않는다.
- 다음 할 일: L02 정책 미결 항목을 결정한 뒤 L03에서 서비스 DB 프로젝트와 읽기 전용 스키마 접근을 확보한다. 현재 Supabase 후보가 비활성·접근 불가이고 로컬 Docker 엔진도 접근이 차단되어 L04 이후 DB 단계는 대기 중이다.

## 2026-11-04 로그인 작업 L01 인증 테스트 실행 환경 복구
- 한 일: 로그인 마무리 계획 L01을 실행하고 테스트 대기 원인을 확인했다. Windows Proactor가 Starlette TestClient/AnyIO의 로컬 socketpair를 만드는 `accept()`에서 대기했다. 앱 인증 함수에는 진입하지 않아 이전 지연을 인증 코드 오류나 scrypt 원인으로 보지 않는다.
- 실행한 명령과 결과: 격리 내 단일 테스트는 대기를 재현했다. 동일 `test_login_rejects_cross_origin`을 샌드박스 밖에서 실행해 `1 passed in 0.37s`. 이어 `UV_CACHE_DIR=<저장소 .venv 아래 임시 캐시> uv run --no-sync --offline pytest -q -rs tests/api/test_auth.py -p no:cacheprovider`: `19 passed, 15 skipped in 2.85s`. skip은 모두 `TEST_AUTH_DATABASE_URL` 필요 사례이며 서비스/격리 DB 접속을 하지 않았다.
- 바꾼 파일: `docs/specs/login-completion-plan.md`의 L01 상태, `docs/worklog/sth.md`. 인증 코드·의존성·DB·pgvector·Cloud Run은 변경하지 않았다.
- 확인 못 한 것: DB 통합 사례, 현재 서비스 DB 로그인·세션 흐름. `.venv/Scripts/uv.exe`가 기본 캐시 경로에 접근할 수 없어 캐시를 저장소의 `.venv` 아래로 지정했다.
- 다음 할 일: L02에서 개인정보 최소 수집, 로그/세션/계정 보관·삭제, 평문 이메일 저장 허용, 운영 키·DB TLS·백업 접근에 대한 미결 결정을 정리한다. DB 확인은 L03의 프로젝트 접근 선행 조건 뒤에 한다.

## 2026-11-04 로그인 암호·개인정보·인증 DB 작업 준비
- 한 일: 사용자 요청 3개 범위를 현재 인증 코드·SQL·SPEC 4/8.6·로그인 작업서·과거 실측·현재 차단 기록과 대조했다. `docs/specs/login-completion-plan.md`에 상태 비교, L01~L07 실행 체크리스트, 파일/API, 완료 기준을 정리했다.
- 정리한 경계: 비밀번호는 복호화 없이 scrypt로 비교하고 세션 HMAC도 암호화와 구분한다. 이메일 평문 저장·보관/삭제·로그·접근 정책은 결정 대상으로 남긴다. 별도 테스트 DB 검증 후 서비스 DB에 인증 스키마와 합성 계정만 적용하며 pgvector는 변경하지 않는다. 자동 DB 테스트는 서비스 DB에서 실행하지 않는다.
- 바꾼 파일: 위 계획서, `docs/specs/SPECS.md`, `SOJAFIT.md`의 새 파일 트리 한 줄, 이 작업기록. 코드·DB·배포·비밀값은 변경하지 않았다.
- 확인 방법: 소스/SQL/테스트 이름과 계획의 경로·링크·요구사항 대조 및 diff 점검. 이번 문서 작업에서 애플리케이션 테스트·평가셋·클라우드 검증은 실행하지 않았다.
- 확인 못 한 것: 서비스 DB 대상·접근·인증 적용 상태, 현재 테스트 대기 원인, 현 배포 로그인·세션 성공과 개인정보 정책. 기존 접근 차단을 해소한 것으로 표시하지 않았다.
- 다음 할 일: L01 검증 환경 조사와 L02 개인정보 결정 준비부터 진행하고, DB 접근이 확보되면 L03 읽기 전용 점검 → L04 격리 검증 → L05 인증만 적재 → L06 배포 검증 → L07 정리 순서로 진행한다.

## 2026-11-04 현재 DB 존재 여부 재확인
- 한 일: 연결된 Supabase 프로젝트 목록, 사용자 명명 후보의 public 테이블 목록, 로컬 Compose DB 상태를 읽기 전용으로 확인했다.
- 결과: Supabase 프로젝트 2개가 보였고 모두 `INACTIVE`였다. `SimonTH-0912's Project` 항목에는 PostgreSQL 17 인스턴스 메타데이터가 있지만, public 테이블 조회는 `Database is possibly not accessible at the moment`로 실패했다. 다른 프로젝트는 `minwon-bot`이며 SojaFit DB라는 근거가 없다.
- 로컬 확인: `docker compose ps --format json`은 Docker Desktop 엔진 파이프 접근 거부로 실패했다. 로컬 DB 컨테이너 실행 여부는 확인하지 못했다.
- 판정: Supabase에 등록된 기존 PostgreSQL 프로젝트/DB 자원은 있으나 비활성이고 접근할 수 없어, 현재 서비스 DB인지 또는 인증 테이블이 있는지는 확인되지 않았다. Cloud Run의 `DATABASE_URL`은 Secret 참조만 확인했고 실제 대상은 열람하지 않았다.
- 바꾼 파일: `docs/worklog/sth.md`. 데이터베이스·인증 테이블·계정·pgvector는 변경하지 않았다.
- 다음 할 일: SojaFit 서비스가 실제 사용하는 활성 DB 프로젝트를 담당자에게 확인하고 접근 권한을 연결한다. 이후 pgvector를 제외한 스키마 목록과 인증 마이그레이션 이력을 읽기 전용으로 확인한다.

## 2026-11-04 로그인 마무리 전 확인
- 사용자 전달 맥락: 개인정보·인증 관련 데이터는 서비스 DB에 둘 수 있으나 pgvector는 건드리지 않는다. 이 작업에서는 DB 쓰기나 스키마 변경을 수행하지 않았다.
- Cloud Run 읽기 전용 확인: GCP 콘솔의 `sojafit-api` 서비스 URL은 `https://sojafit-api-559369539072.asia-northeast3.run.app`이고 `AUTH_ORIGIN`은 같은 출처(끝 `/` 포함)로 설정돼 있었다. 애플리케이션이 끝 `/`를 제거해 비교하므로 출처 형식은 일치한다. `DATABASE_URL`은 Secret 참조로만 보였고 값은 열지 않았다. Cloud SQL 연결은 콘솔에서 연결되지 않은 상태였다.
- 판정: 앞서 해당 HTTPS Origin으로 보낸 쿠키 없는 `/api/auth/logout`의 200은 출처 검사를 통과한 증거다. 로그인 API의 DB 인증·세션 생성 성공 증거는 아니다. 실제 DB 대상과 인증 스키마를 확인하지 못했고, 연결된 Supabase 후보 프로젝트는 비활성/접근 불가 상태였다. pgvector에는 접근하거나 변경하지 않았다.
- 로컬 테스트: `TEST_AUTH_DATABASE_URL` 미설정. 셸에서 `uv`를 찾지 못했다. `.venv/Scripts/uv.exe run --no-sync ...`는 샌드박스가 사용자 uv 캐시 쓰기를 거부해 실패했다. `.venv/Scripts/python.exe -m pytest -q -rs tests/api/test_auth.py` 및 Origin/쿠키 테스트만 분리한 재시도는 첫 Origin 테스트에서 응답 없이 오래 대기해 중단했다. 테스트 통과로 간주하지 않는다.
- 바꾼 파일: `docs/worklog/sth.md`만 기록 보완. 인증 코드, Cloud Run, 서비스 DB, 평가 데이터와 pgvector는 변경하지 않았다.
- 다음 할 일: 서비스 DB 소유자와 실제 DB 프로젝트/접근 권한 및 인증 마이그레이션 상태를 확인한다. 쓰기 전 읽기 전용 스키마 검사와 격리 DB 복구 경로를 마련하고, pgvector 영역을 제외해 인증 스키마·평가 계정 흐름을 검증한다. 사용자가 말한 로그인 화면은 현재 체크아웃에 없어 별도 프론트엔드 위치·배포 주소도 연결해야 한다.

## 2026-11-04 인증 DB 스키마 확인 접근 차단
- 한 일: 연결된 Supabase 프로젝트를 읽기 전용으로 조회하고 인증 테이블 목록을 확인하려 했다.
- 실행한 명령과 결과: 프로젝트 목록에 SojaFit으로 식별되는 항목은 없었다. `SimonTH-0912's Project` 후보는 `INACTIVE`였고 `public` 테이블 조회는 `Database is possibly not accessible at the moment`로 실패했다. 다른 프로젝트는 이번 작업 대상인지 확인되지 않아 조회하지 않았다.
- 바꾼 파일: `docs/worklog/sth.md`. DB·Cloud Run에는 변경을 가하지 않았고 SQL을 실행하지 않았다.
- 확인 못 한 것: SojaFit이 사용하는 Supabase 프로젝트 식별자, 공유 DB의 현재 테이블·마이그레이션·백업 상태.
- 다음 할 일: DB 담당자가 SojaFit 프로젝트를 활성화하거나 해당 프로젝트 접근을 연결하고, 대상·복구 경로를 확인한 뒤 읽기 전용 스키마 검사 및 격리 DB 적용 검증을 진행한다.

## 2026-11-04 Cloud Run AUTH_ORIGIN 설정 후 출처 검사
- 한 일: 사용자가 Cloud Run 환경변수 등록을 완료했다고 알려, 공개 API에서 출처 검사만 합성 요청으로 확인했다.
- 실행한 명령과 결과: `/health` GET은 HTTP 200. `Origin: https://sojafit-api-559369539072.asia-northeast3.run.app`을 넣어 쿠키 없이 `/api/auth/logout`에 빈 POST를 보내 HTTP 200 `{"ok":true}`를 확인했다. 첫 요청은 빈 POST의 Content-Length가 없어 Google 프런트엔드에서 411을 받았고, 길이 0을 명시해 재확인했다. 쿠키가 없어 `auth.logout`의 DB 삭제문은 실행되지 않았다.
- 결과: 현재 Cloud Run 요청은 해당 HTTPS 출처의 Origin 검사를 통과한다. 공통 `check_origin`을 쓰므로 로그인 403 차단이 해소된 것으로 판단한다.
- 바꾼 파일: `docs/worklog/sth.md`. Cloud Run 설정·DB·계정은 변경하지 않았다.
- 확인 못 한 것: 실제 `/api/auth/login` 이후 DB·계정 인증·세션 쿠키 흐름. 인증 테이블과 평가 계정은 확인되지 않아 실제 로그인 성공은 검증하지 않았다.
- 다음 할 일: DB 대상과 인증 스키마 적용 이력을 확인하고, 격리 검증 및 담당자 검토 후 평가 계정으로 로그인·세션을 확인한다.

## 2026-11-04 Cloud Run AUTH_ORIGIN 설정 접근 차단
- 한 일: 사용자가 요청한 `AUTH_ORIGIN` 설정 전 `sojafit` 프로젝트의 `sojafit-api` 서비스 URL·리비전·현재 변수만 비밀값을 조회하지 않는 형식으로 확인하려 했다.
- 실행한 명령과 결과: `gcloud run services describe sojafit-api --project=sojafit --region=asia-northeast3 --format=...`가 현재 인증 계정에 `run.services.get` 권한이 없어 `PERMISSION_DENIED`로 실패했다. 변경 명령과 로그인 시험은 실행하지 않았다.
- 바꾼 파일: `docs/worklog/sth.md`. Cloud Run 환경변수·리비전·DB는 변경하지 않았다.
- 확인 못 한 것: 현재 Cloud Run 주소·리비전·`AUTH_ORIGIN` 값. 기록된 API HTTPS 주소는 README의 2026-11-03 확인값이다.
- 다음 할 일: 배포 담당자가 서비스 조회·수정 권한을 부여하거나 직접 설정한 뒤, `/docs`에서 합성 계정으로 Origin 차단이 해소되는지 확인한다. DB 테이블 미적용 시 이후 인증 단계는 별도 실패할 수 있다.

## 2026-11-04 Cloud Run 로그인 화면 주소 확인
- 한 일: `backend/web/WEB.md`, `backend/main.py`, `README.md`, 디렉토리 목록을 대조해 로컬 화면과 Cloud Run API 공개 범위를 확인했다. 현재 체크아웃에는 실행 가능한 로그인 화면·정적 파일·화면 라우트가 없고, README는 화면을 아직 없음으로 표시한다. 문서에 기록된 API 주소는 `https://sojafit-api-559369539072.asia-northeast3.run.app`이다.
- 결과: 이 API의 `/docs`에서만 로그인 API를 시험한다면 `AUTH_ORIGIN` 후보는 위 API 출처다. 실제 로그인 화면이 별도 프론트엔드로 배포되면 그 화면의 출처를 써야 한다. 로컬에서 봤다는 화면이 현재 체크아웃 밖의 앱인지 여부는 찾지 못했다.
- 바꾼 파일: `docs/worklog/sth.md`. Cloud Run·DB·코드는 변경하지 않았다.
- 확인 못 한 것: 현재 GCP 리비전의 주소·설정, 사용자가 말한 로컬 화면의 실제 실행 위치. GCP UI 읽기는 브라우저 주소 판별 정책으로 중단됐고 `gcloud`는 로컬 자격 증명 경로 권한 오류로 실행되지 않았다.
- 다음 할 일: 로컬 로그인 화면의 실행 주소와 배포 방식을 확인하고, 프론트엔드를 배포한 뒤 실제 화면 Origin에 맞춰 `AUTH_ORIGIN`을 설정해 로그인·세션을 검증한다.

## 2026-11-04 Chrome에서 Cloud Run 로그인 403 확인
- 한 일: 사용자가 연 Chrome의 GCP 콘솔에서 SojaFit `sojafit-api`를 조회하고 Swagger UI에서 합성 계정값으로 로그인 요청 1건을 보냈다. 실제 계정 비밀번호·토큰·비밀값은 열람하거나 기록하지 않았다.
- 확인: 콘솔은 서비스 정상, 컨테이너 포트 8000, 1GiB, `DEMO_MODE=0`으로 표시했다. 환경 변수와 Secret 참조 목록에 `AUTH_ORIGIN`은 없었다. 동일 서비스의 `/docs`에서 합성 요청은 403과 `요청 출처를 확인할 수 없습니다.`를 반환했다. 이는 현재 코드의 Origin 검사와 일치하지만 실제 제보 요청의 출처는 별도 미확인이다.
- 바꾼 파일: `docs/worklog/sth.md`. Cloud Run 설정·DB·계정·배포는 변경하지 않았다.
- 확인 못 한 것: 실제 인증 DB 스키마와 테스트 계정, 올바른 Origin 설정 후 로그인·세션 동작 및 제보 요청 상세. 이전 조장 기록은 인증 테이블 부재를 보고했으나 현재 DB 상태를 직접 조회하지 않았다.
- 다음 할 일: 서비스 담당자와 실제 브라우저 출처와 DB 마이그레이션 이력·테스트 계정을 확인하고, 변경은 팀 절차에 따라 격리 환경에서 먼저 검증한다.

## 2026-11-04 로그인 403·MCP 후속 확인 진행
- 로그인·배포: `sojafit` 프로젝트의 Cloud Run 서비스를 읽기 전용으로 조회했으나 현재 계정의 권한 부족으로 리비전·`AUTH_ORIGIN` 설정을 확인하지 못했다. 제보의 요청 URL·Origin·본문도 없어 실제 403 원인을 확정하지 못했다. 공유 DB 인증 스키마는 접근하지 않았다. 403 해결과 평가 계정 검증은 배포 담당자 협조 후 재개한다.
- MCP 테스트: 임시 pgvector 컨테이너와 합성 문서 4건·청크 8개만 사용했다. 최초 데이터 준비는 합성 SHA 길이 오류로 롤백했고 같은 준비를 바로잡아 재실행했다. 변경 전 `tests/graph/test_graph_mcp_stdio.py`는 새 `Rewrite` 호출에서 1건 실패했다. 가짜 LLM에 재작성 응답을 더하고 기대 경로에 재작성 단계를 추가한 뒤 같은 테스트는 1 passed, `tests/graph`는 60 passed였다. 실제 stdio·격리 DB 검색이며 데모 BM25와 가짜 LLM을 사용했다. 임시 컨테이너는 종료·자동 제거했다.
- 장애 계약: `docs/specs/mcp-graph-integration.md`는 MCP의 `RetrievalUnavailableError`만 안전 응답으로 바꾸도록 명시한다. 기본 Voyage 검색에서 발생하는 일반 예외의 사용자 응답은 별도 계약이 없어 변경하지 않았다. 담당자와 오류 종류·API 응답·재시도 기준을 정한 뒤 별도 작업한다.
- 기타 선행 조건: 403 재현 당시 실제 요청·Origin과 현재 DB 상태는 미확인이다. 업무 데이터 소유권 연동은 업무 API·DB Store·승인 흐름과 팀 합의가 필요하고, 로그인·관리자 화면은 현재 없다. `SPEC.md`의 임베딩·저장 설명은 조장 반영 요청 대상이다.
- 브랜치: 읽기 전용 `git ls-remote --heads origin main STH`에서 STH `fdbe30a`, main `cdbe4a2`를 확인했다. main은 STH 이후 커밋을 포함하며 이 작업에서 pull·merge하지 않았다.
- 바꾼 파일: `tests/graph/test_graph_mcp_stdio.py`, `docs/worklog/sth.md`. 운영 DB·배포·원격 저장소는 변경하지 않았다.
- 확인 못 한 것: 실제 Cloud Run 로그인, Voyage 외부 장애 및 운영 DB, 실제 코퍼스 성능·평가셋 재측정. 격리 테스트 통과를 서비스 전체 완료로 보지 않는다.

## 2026-11-04 로그인 403 포함 후속 확인 목록
- 한 일: 전달받은 로그인 403 제보를 기존 PR #46 통합 후 확인 목록에 추가하고 인증 코드·배포 기록을 대조했다. 제보 이미지에는 403 외에 요청 URL·Origin·응답 본문·시각이 없어 특정 원인으로 확정하지 않았다.
- 로컬 확인: `auth.check_origin`은 요청 Origin과 `AUTH_ORIGIN`이 다르거나 Origin이 없으면 인증·DB 조회 전에 403을 반환한다. 합성 이메일·가짜 인증 함수로 Origin 누락·불일치는 각각 403 및 인증 미호출, 일치는 200 및 인증 호출을 확인했다. `.venv/Scripts/python.exe -m pytest -q tests/api/test_auth.py -k 'cross_origin or cookie' -p no:cacheprovider`: 2 passed, 32 deselected.
- 배포 기록: 저장된 `origin/main` `cdbe4a2`의 `docs/worklog/jeongun.md`는 당시 Cloud Run에서 `AUTH_ORIGIN` 미설정으로 로그인 403, 운영 DB 인증 표 003·005·006·007 미적용이라고 보고한다. 실제 배포의 현재 리비전·설정·스키마와 이번 제보가 같은 상황인지는 직접 확인하지 않았다.
- 후속 확인 목록:
  1. 배포 담당자와 실패 요청의 URL·시각·HTTP 메서드·응답 상태 및 본문, 브라우저 Origin과 실제 서비스의 `AUTH_ORIGIN` 설정 여부를 대조한다. 계정·비밀번호·쿠키·토큰은 기록하지 않는다. 서로 다른 출처를 허용해야 한다면 우회하지 말고 팀과 인증·CSRF 정책을 먼저 정한다.
  2. 공유 DB의 인증 스키마 및 마이그레이션 적용 이력을 읽기 전용으로 확인한다. Origin을 맞춘 뒤 DB 테이블 부재 등 별도 오류가 드러날 수 있으므로, 격리 DB에서 먼저 인증·로그아웃·HTTPS 쿠키·세션을 확인한다. 운영 DB 변경·배포는 대상 및 팀 절차 확인 후 별도 진행한다.
  3. `tests/graph/test_graph_mcp_stdio.py`의 재작성 단계 누락을 점검하고 격리 코퍼스 DB에서 실제 그래프→MCP→검색 경로를 다시 검증한다.
  4. Voyage 기본 검색의 일반 예외와 MCP 검색 장애 응답 차이를 확인하고 기대 동작을 정한다. `SPEC.md`의 임베딩·저장 설명 불일치는 조장에게 수정 요청한다.
  5. 최신 main과 STH의 차이·충돌 및 이전에 기록한 소유권 연결, 로그인 화면·관리자 메뉴, 배포 키·평가 계정, 로그인 동시성의 미검증 항목을 대조한다.
- 바꾼 파일: `docs/worklog/sth.md`. 코드·배포 설정·공유 DB는 변경하지 않았다.
- 확인 못 한 것: 실제 403 응답 본문·요청 출처·현재 Cloud Run 설정·인증 스키마·평가 계정과 엔드투엔드 로그인. 평가셋은 재측정하지 않았다.

## 2026-11-04 조장 관리 SPEC 변경 분리
- 한 일: 미커밋 주요 문서 중 `SPEC.md`만 변경된 것을 확인하고, 인증·마스킹 반영 요청 초안을 저장소 밖에 보관한 뒤 `origin/main` 기준으로 되돌렸다. 당시 `origin/main`과 STH의 해당 파일 원본은 동일했다.
- 바꾼 파일: `SPEC.md`, `docs/worklog/sth.md`. 요청 초안은 저장소 밖 Codex 작업 폴더의 `sojafit-spec-auth-request.md`에 보관했다. 인증 코드와 다른 미커밋 변경은 유지했다.
- 확인: 저장 전 diff와 조장 관리 문서 규칙을 대조했다. 코드 테스트나 조장에게 요청 전달은 하지 않았다.
- 다음 할 일: 기존 계정 이메일 형식의 호환성을 확인하고, 정책이 확정되면 저장한 초안을 조장에게 전달해 `SPEC.md` 반영을 요청한다.

## 2026-11-04 원격 STH fast-forward 및 변경 확인
- 한 일: 기존 미커밋·미추적 변경을 `codex-sth-pull-safety-20261104` stash에 보관하고 `git pull --ff-only origin STH`로 `95ca940`에서 `013e5a1`로 갱신했다. `git stash apply --index`는 `SPEC.md`와 이 작업 기록을 자동 병합했고 미해결 충돌은 없었다. 안전 사본 stash는 유지했다.
- 받은 내용: MCP `search_corpus` 응답 검증·stdio 세션 재사용 검색기와 그래프 주입 경로, 검색 장애를 빈 결과와 구분하는 분기·턴 초기화, NumPy 선행 import, 관련 테스트·문서 및 main의 변경이다. MCP 검색기는 인자로 주입할 때 사용하며 기본 검색 경로를 자동 전환하지 않는다.
- 보존 확인: 인증 코드·테스트·시드·작업서와 미추적 측정 JSON을 stash와 줄바꿈 정규화 후 해시 비교해 일치했다. `SPEC.md`와 작업 기록의 양쪽 변경은 자동 병합 상태로 보존했다. 주요 문서 `SPEC.md`의 기존 미커밋 인증 변경은 조장 검토 대상이다.
- 검사: 샌드박스 집중 테스트는 진행 중 실패 표시 후 완료 전 중단했다. 같은 범위를 로컬 권한에서 `.venv/Scripts/python.exe -m pytest -q tests/graph tests/mcp_skill tests/repo tests/api -p no:cacheprovider --maxfail=1`로 재실행해 130 passed, 16 skipped (10.38초). 첫 실행은 최종 실패 상세를 수집하지 못해 원인을 확정하지 않는다. `git diff --check` 통과, 미해결 충돌 파일 없음.
- 미검증: 건너뛴 DB 의존 경로, 실제 Cloud Run, 전체 평가셋 재측정. 풀은 푸시·배포·공유 DB 변경을 포함하지 않았다.
- 다음 할 일: 인증 변경에 대한 조장 문서 반영을 요청하고, 실제 격리 DB 기반 MCP 경로와 배포 검증은 선행 환경이 준비되면 별도 실행한다.

## 2026-11-04 STH 충돌 상태 점검
- 한 일: 현재 STH와 원격 STH·main의 충돌 가능성 및 미커밋 변경 겹침을 확인했다. Git 병합·브랜치 이동·커밋·푸시는 하지 않았다.
- 확인 결과: 로컬 STH `95ca940`은 원격 STH `013e5a1`보다 21커밋 뒤이며 fast-forward 가능 상태다. `git ls-remote --heads origin main STH`에서 원격 main `4dc4685`, STH `013e5a1`이 로컬 원격 추적 참조와 일치했다. `git status`, `git diff --name-only --diff-filter=U`상 진행 중인 병합이나 미해결 파일은 없다.
- 병합 예행 확인: 별도 임시 Git object 디렉터리를 사용해 `git merge-tree --write-tree origin/STH origin/main`을 실행한 결과 충돌 없이 종료 코드 0이었다. 이는 해당 시점 커밋 간 확인이며 이후 원격 변경은 포함하지 않는다.
- 미커밋 변경: 원격 STH 변경과 겹치는 `SPEC.md`, `docs/worklog/sth.md`를 임시 파일에서 3방향 비교했다. 원본 줄바꿈 그대로는 각 1곳 충돌이었으나 CRLF/LF를 LF로 통일한 비교에서는 두 파일 모두 충돌 0이었다. 실제 Git 병합 결과를 보장하는 검증은 아니며 기존 변경을 보존한 채 통합 시 재확인해야 한다. `SPEC.md`의 인증 문구는 조장 소유 주요 문서에 해당하므로 팀 규칙에 따라 조장에게 반영을 요청한다.
- 바꾼 파일: `docs/worklog/sth.md`. 기존 미커밋 변경과 미추적 측정 결과는 유지했다. 코드 테스트는 실행하지 않았다.
- 다음 할 일: 미커밋 변경을 안전하게 보존하고 원격 참조를 다시 확인한 뒤 STH를 통합한다. 작업 기록은 양쪽 내용을 모두 보존하고, 줄바꿈과 주요 문서 수정 권한을 확인한다.

## 2026-11-04 로그인 화면·배포 계정 검토
- 한 일: 현재 작업 트리의 화면 설계, 인증·관리자 API, 데모 계정 시드와 배포 검증 기록을 대조했다.
- 화면: `backend/web/`에는 설계 문서만 있고 로그인·관리자 UI는 없다. 과거 수동 화면은 제거됐으며 `tests/api/test_health.py`는 루트 404를 기대한다. 로그인·사용자 확인·로그아웃과 관리자 목록·일반 계정 활성 상태 변경 API는 있으나 실제 브라우저 연결은 미검증이다. FastAPI 직접 제공 여부와 상호작용은 미결이므로 서비스 담당과 정하고 작업 범위·수용 기준을 확정한 뒤 화면과 기존 테스트를 함께 고친다. 사용자 화면 표시만으로 관리자 권한을 보장하지 말고 서버 측 검사를 유지한다.
- 배포 비밀값·평가 계정: 비데모 서버는 32바이트 이상 `AUTH_SECRET`을 요구하며 `AUTH_ORIGIN`은 출처 검사와 Secure 쿠키에 영향을 준다. CLI 계정 생성과 로컬 Compose 데모 시드는 있으나 실제 Cloud Run 비밀값·DB·평가 계정 설정 여부는 확인되지 않았다. 공개 데모 계정은 실제 평가 계정으로 쓰지 않는다. 배포 담당자와 접근 권한·대상 DB 및 스키마 이력·비밀값 주입 방식·별도 평가 계정 전달 방법을 확인하고 격리 환경부터 검증한다. 키 변경 시 기존 세션은 재로그인이 필요하다.
- 확인: `backend/web/WEB.md`, `backend/web/design.md`, `SPEC.md`, `docs/specs/login-auth.md`, `backend/main.py`, `backend/auth.py`, `tests/api/test_health.py`, `docker-compose.yml`, `.env.example`, `docs/GATES.md`와 기존 로컬 실측 기록을 대조했다. `git status --short --branch`상 STH는 저장된 `origin/STH`보다 21커밋 뒤에 있어 구현 전 최신 상태를 확인해야 한다. 원격을 새로 조회하지는 않았다.
- 바꾼 파일: `docs/worklog/sth.md`. 코드 테스트·실제 배포 접근·비밀값 확인 또는 계정 생성은 하지 않았다.
- 다음 할 일: 화면 담당과 제공 방식·관리자 메뉴 범위 및 수용 기준을 합의하고, 배포 담당과 앞 절의 Cloud Run 재개 조건을 확인한다. 기존 미커밋 변경을 보존한 채 최신 브랜치 차이를 검토한다.

## 2026-11-04 인증 후속 검증
- 목적·조건: 격리 PostgreSQL과 Windows 단일 프로세스에서 로그인 1건과 실제 scrypt 2건 동시 실행을 비교하고, 두 슬롯이 찬 동안 세 번째 요청의 503과 메모리를 확인한다. 외부 모델 호출과 비용은 없다.
- 명령: `TEST_AUTH_DATABASE_URL`을 로컬 테스트 전용 DB로 지정하고 `.venv/Scripts/python.exe scripts/auth/measure_scrypt_concurrent.py` 실행. `uv` 실행 파일을 찾지 못해 기존 가상환경을 직접 사용한다.
- 중단 조건: 테스트 DB 연결 불가, 동일 날짜 결과 파일 존재, 검증 실패 또는 과도한 자원 사용 시 중단한다. 기존 결과는 덮어쓰지 않는다.
- 결과: 로컬 PostgreSQL 16.15 임시 컨테이너에 인증 SQL 003·005·006을 적용하고 `.venv/Scripts/python.exe -m pytest -q tests/api -p no:cacheprovider` 실행: 36 passed (20.44초). 임시 컨테이너는 종료·자동 제거했다.
- 실제 scrypt 측정: 두 로그인 200, 겹침 456.91ms, 두 검증 중 세 번째 503, 단일·두 건 최대 working set 184.30·312.73MiB. 결과 `scripts/results/auth/scrypt_concurrent_2026-11-04.json`. Windows 단일 Python 프로세스에서 각 조건 한 번 측정한 값이며 DB·Cloud Run 메모리와 일반 요청 지연을 뜻하지 않는다.
- 배포 확인: 공개 health 주소는 이 실행 환경의 DNS 조회에 실패했고, 서비스 URL의 프로젝트 번호에 대한 `gcloud projects describe`는 현재 계정 권한 부족으로 실패했다. 배포·공유 DB는 변경하지 않았다.
- 업무 데이터: 실제 업무 API·DB Store·승인 흐름이 없어 소유권 검사를 연결할 대상이 없음을 `backend/main.py`, `backend/graph/GRAPH.md`, `db/manual/MANUAL.md`에서 확인했다. 팀의 연동 경계 합의와 업무 기능 구현 후 교차 접근을 시험해야 한다.
- 바꾼 파일: 이 작업 기록과 위 측정 결과 JSON. 평가셋 재측정, Cloud Run 인증·설정 및 실제 업무 데이터 소유권은 확인하지 못했다.
- 다음 할 일: 배포 담당자에게 해당 프로젝트의 읽기 권한 또는 리비전·메모리·포트·DB 설정 확인을 요청하고, 업무 API 담당과 소유권 연동 경계를 확정한다.

### 접근 문제로 보류 — Cloud Run 검증 재개 방법
- 중단 지점: 2026-11-04 서비스 주소에 표시된 프로젝트 번호 `559369539072`의 프로젝트 조회가 현재 인증 계정의 권한 부족으로 실패했다. 공개 `/health` 요청은 이 실행 환경의 DNS 조회 실패로 응답을 받지 못했다. DNS 실패만으로 서비스 장애라고 판단하지 않는다.
- 재개 조건: 배포 담당자에게 실제 프로젝트 ID·서비스명·리전 확인과 Cloud Run 설정 및 필요 로그의 읽기 권한을 요청한다. 권한을 받을 수 없으면 담당자가 리비전, 포트, 메모리, 인스턴스·동시 요청 설정과 DB 스키마 적용 여부를 확인해 전달한다. 별도로 테스트용 계정과 격리 검증 환경을 준비한다. 비밀번호, 토큰, DB 주소 등 비밀값은 작업 기록이나 채팅에 적지 않는다.
- 재개 순서: ① 접근 가능한 환경에서 `/health`와 실제 배포 리비전을 확인한다. ② 포트 8000과 서비스 설정, 대상 DB 및 인증 스키마 적용 이력을 읽기 전용으로 대조한다. ③ 테스트 계정으로 HTTPS 쿠키·Origin, 로그인·`/api/auth/me`·로그아웃 및 세션 거부를 검증한다. ④ 격리 환경에서 DB 장애 및 두 슬롯 점유 시 503을 확인하고, 여러 인스턴스의 메모리·오류·지연은 시험 조건과 예산을 정한 뒤 측정한다. 실제 관측과 미검증 항목을 이 기록에 추가한다.
- 안전 경계: 공유·운영 DB 변경, 배포, 부하 시험 및 실제 계정 사용은 대상과 팀 절차를 확인한 후 진행한다. 로컬 36건 통과와 scrypt 측정 결과는 Cloud Run 검증을 대신하지 않는다.
- 별도 선행 조건: 업무 데이터 소유권 검사는 권한 문제와 별개로 업무 API·DB Store·승인 흐름과 소유권 경계 합의가 필요하다. 구현이 준비되면 위 업무 데이터 항목의 A/B 교차 접근 시험부터 진행한다.

## 2026-11-03 인증 후속 작업 준비
- 한 일: 업무 데이터 소유권, Cloud Run 인증 검증, scrypt 동시 처리 제한의 현재 구현과 선행 조건을 문서·코드에서 대조했다. 아래는 작업 제안이며 팀 합의나 실행 결과가 아니다.
- 업무 데이터 소유권: `docs/specs/login-auth.md`의 후속 연동 계약을 기준으로 서비스·에이전트 담당이 thread 소유권 확인 위치, Store namespace와 사용자 ID 변환 경계, 견적 승인 권한을 합의한다. 업무 API·승인 흐름·DB Store와 업무 표 적용이 준비되면 세션의 사용자 ID로 각 리소스 조회·변경을 제한하고 A/B 교차 접근 및 재접속·재시작 후 격리를 시험한다. `backend/graph/memory.py`는 namespace 규칙만 제공한다.
- Cloud Run: 배포 담당과 서비스·리비전, 대상 DB와 스키마 적용 이력, 접근 권한, 테스트 계정, 비용·시험 시간을 확인한다. 격리 환경에서 먼저 `/health`, HTTPS 쿠키·Origin, 로그인·세션·로그아웃, DB 장애와 2개 슬롯 점유 시 503, 로그의 민감값 노출 여부를 확인한다. 운영 DB 변경이나 배포는 팀 절차에 따라 별도 진행한다. `Dockerfile`은 8000번 포트로 고정되어 있어 실제 서비스의 포트 설정을 대조한다.
- 동시 처리: 현재 동일 PostgreSQL DB의 트랜잭션 advisory lock 두 칸이 로그인 경로를 제한하며 초과 요청은 503이다. 기존 격리 DB 테스트와 Windows 로컬 실측을 기준으로 재현하고 Cloud Run의 인스턴스·메모리·여러 프로세스 조건에서 별도 확인한다. 연결이 검증 도중 끊어지면 잠금이 먼저 해제될 수 있고 계정 생성 CLI는 제한 범위 밖이다. 2건을 변경할지, 초과 요청 재시도 방식과 목표 처리량은 측정 후 결정한다.
- 바꾼 파일: `docs/worklog/sth.md`.
- 확인 방법: `git status --short --branch`, 관련 폴더 설명·`docs/specs/login-auth.md`·인증 코드·테스트·배포 설정·기존 로컬 실측 기록을 대조했다. 새 테스트나 외부 환경 접근은 수행하지 않았다.
- 확인 못 한 것: 현 Cloud Run 리비전·설정과 인증 동작, 공유 DB 스키마·권한, 실제 업무 리소스의 교차 사용자 접근, 배포 환경 부하·메모리.
- 다음 할 일: 담당자와 연동 경계 및 격리 검증 환경을 확정하고, 인증 DB 테스트를 실행한 뒤 배포 검증과 업무 기능 연동을 각각 진행한다.

## 2026-11-03 로그인 이메일 입력·응답 보완
- 한 일: 로그인 API·계정 생성 CLI에 같은 이메일 형식 및 100자 제한을 적용했다. 데모 시드에도 동일 길이 제한을 더하고, 잘못된 기존 주소는 관리자 응답에서 전부 가려 목록 조회가 실패하지 않게 했다.
- 바꾼 파일: backend/auth.py, backend/main.py, db/007_demo_accounts.sql, tests/api/test_auth.py, docs/specs/login-auth.md, SPEC.md, docs/worklog/sth.md.
- 실행한 명령과 결과: `uv run --no-sync python -m pytest tests/api/test_auth.py -q -p no:cacheprovider` — 18 passed, 14 skipped (격리 인증 DB 미설정). `git diff --check` 통과.
- 확인 못 한 것: DB 통합 테스트는 건너뛰었고 Cloud Run·프록시 로그 및 운영 DB 설정은 접근할 수 없어 확인하지 않았다.
- 다음 할 일: TEST_AUTH_DATABASE_URL이 있는 환경에서 데모 시드 및 인증 DB 테스트를 실행한다.

## 2026-11-03 새 main 구조 병합과 MCP 자료 보관
- 한 일: `f271553`을 STH에 병합하고 MCP 테스트·측정 스크립트 및 원시 자료 15개는 요청에 따라 저장소 밖에 보관했다. stash의 수정된 MCP 테스트 사본도 별도로 보관했다.
- 정리: MCP 조사 문서의 외부 보관 자료와 사전등록 경로를 반영했다. 로그인 마스킹 변경은 이 MCP 커밋에서 제외했다.
- 확인: 충돌 없음, 외부 보관 사본 해시 대조, stage 변경의 `git diff --cached --check`, MCP 조사 문서 상대 링크 0건 누락. 테스트는 `uv` 실행 파일을 찾지 못해 실행하지 못했다.
- 다음 할 일: 팀과 MCP 테스트·측정 자료 위치를 정하고 복원한 뒤 구조 검사와 MCP 회귀 테스트를 실행한다. 원시 자료가 저장소 밖에 있어 현재 클론만으로 실측을 재현할 수 없다.

## 2026-11-03 최신 main 통합 및 MCP 문서 재분류
- 한 일: 최신 main `5760105`를 STH에 병합하고 자동 충돌을 수동 해결했다. 이전 `docs/mcp/`의 MCP 조사·실측·미합의 제안 문서 10개를 기존 `docs/research/`로 옮기고 폴더를 제거했다. 검색 도구 작업서는 `docs/specs/mcp-search-tools.md`에 유지했다.
- 코드 병합: STH 관리자 계정 API의 이메일 사용자명 마스킹과 해당 테스트를 보존했다. 구 `docs/README.md`·`docs/specs/README.md`·`backend/mcp_skill/README.md`·`scripts/README.md`는 main의 새 설명 파일로 대체했다.
- 문서 정합: `docs/research/RESEARCH.md`, `docs/specs/SPECS.md`와 `SOJAFIT.md` 신규 파일 항목을 맞췄다. 이동 문서의 현재 링크는 새 이름·경로로 바꿨다. `SPEC.md`의 stash 변경은 조장 소유 문서 규칙에 따라 작업 트리에서 제외하고 원본 stash에 남겼다.
- 확인: 충돌 미해결 파일 0, `git diff --check` 통과, 오래된 현재 경로 참조 0. 앱·회귀 테스트는 실행하지 않았다. 기존 stash는 안전을 위해 유지했다.
- 상태: STH가 로컬 merge commit을 포함해 `origin/STH`보다 23커밋 앞서며 push하지 않았다.
- 다음 할 일: 팀 리드가 소유한 `SOJAFIT.md`의 기존 MCP 서버 설명이 main 기준 자리표시자로 남아 있다. STH MCP 변경 PR에서 해당 설명 갱신을 리드에게 요청한다.

## 2026-11-03 나머지 MCP 도구 연결 위치 점검
- 한 일: 문서 조회·TSC 웹 후보·PDF 무결성·회로 정보 도구의 현재 코드 호출처와 그래프에서의 후보 사용 상황을 대조했다.
- 결론 제안: 질문 응답 그래프는 우선 `search_corpus`만 연결한다. 문서 메타데이터는 근거가 있을 때 선택 호출, 웹 검색·PDF 검증·회로 정보는 별도 정책과 사용 근거가 정해질 때까지 그래프 기본 경로에 넣지 않는다.
- 바꾼 파일: `docs/mcp/mcp-tool-contract-review.md`, `docs/worklog/STH.md`.
- 확인 못 한 것: 팀의 도구 노출 결정, 코퍼스 밖 공개 품번 정책, 사용자 회로 접근 요구. 코드·테스트는 수정하거나 실행하지 않았다.

## 2026-11-03 search_corpus 연결 계약 확인
- 한 일: 현재 STH MCP 도구와 원격 main `e25558a` 그래프의 입력·청크 필드·빈 결과 분기를 대조했다.
- 검증: 가짜 검색기를 넣은 별도 MCP stdio 프로세스에서 정상 청크 1건·빈 목록·합성 예외를 각 1회 호출했다. 성공은 `structuredContent.result`, 빈 결과는 빈 텍스트 블록 목록, 오류는 `isError=true`와 예외 문구를 포함하는 텍스트로 관찰됐다. DB·외부 API·실제 키는 사용하지 않았다.
- 바꾼 파일: `docs/mcp/mcp-tool-contract-review.md`, `docs/worklog/STH.md`.
- 확인 못 한 것: 실제 DB 오류의 응답·민감정보 노출 여부, 여러 청크·다른 SDK 버전, LangGraph와 MCP의 실제 통합. 다음 할 일: 오류 비노출 및 실패 구분 계약을 담당자와 협의한다.

## 2026-11-03 MCP 도구 계약 점검 문서 분리
- 한 일: 기존 구현 계획에 적은 도구별 계약·사용처 점검을 별도 문서로 분리하고 문서 목록과 구현 계획에 연결했다.
- 바꾼 파일: `docs/mcp/mcp-tool-contract-review.md`, `docs/mcp/mcp-tool-implementation-plan.md`, `docs/mcp/README.md`, `docs/worklog/STH.md`.
- 확인: 관련 문서의 로컬 링크 21개 중 누락 0개, `git diff --check` 통과. 애플리케이션 테스트와 외부 호출은 새로 수행하지 않았다.

## 2026-11-03 MCP 도구 계약 1차 점검
- 한 일: 다섯 도구의 입력·출력·실행 조건·한계와 사용처 제안을 정리하고 `search_corpus`의 품번 목록 및 빈 결과·장애 처리 협의안을 작성했다.
- 바꾼 파일: `docs/mcp/mcp-tool-implementation-plan.md`, `docs/worklog/STH.md`. 기존 로그인·MCP 코드 변경은 보존했다.
- 실행한 명령과 결과: `uv run --no-sync pytest -q -rs tests/test_mcp_search.py tests/test_mcp_manifest.py -p no:cacheprovider` — 36 passed.
- 확인 못 한 것: 실제 코퍼스 DB·Exa·LangGraph 전체 연동, 팀의 도구 노출·입력 상한 결정. 다음 할 일: 그래프·검색 담당자와 계약 대조 및 팀 디렉터리 정리 후 경로 재확인.

## 2026-11-03 MCP 두 사람 작업 분담 문서 분리
- 한 일: 두 사람의 작업 순서·의존 관계·완료 기준을 별도 문서로 옮기고 인수인계 문서와 문서 목록에서 연결했다.
- 바꾼 파일: `docs/mcp/mcp-two-person-work-plan.md`, `docs/mcp/mcp-collaboration-handoff.md`, `docs/mcp/README.md`, `docs/worklog/STH.md`.
- 확인: 관련 문서의 로컬 링크 17개 중 누락 0개, `git diff --check` 통과. 애플리케이션 테스트·외부 호출은 하지 않았다.

## 2026-11-03 MCP 공동작업 인수인계
- 한 일: MCP 도구의 구현·사용처·정보 경계·LangGraph 연결 검토·검증 한계와 팀 결정 사항을 인수인계 문서로 정리하고 두 사람의 작업 분담·의존 관계·완료 기준을 제안했다.
- 바꾼 파일: `docs/mcp/mcp-collaboration-handoff.md`, `docs/mcp/README.md`, `docs/worklog/STH.md`.
- 확인: 인수인계 문서와 목록의 로컬 링크 14개 중 누락 0개, `git diff --check` 통과. 애플리케이션 실행이나 외부 API 호출은 하지 않았다.

## 2026-11-03 MCP 도구 사용처와 문서 디렉터리 정리
- 한 일: 다섯 도구의 실제 호출처와 제안 사용처, 미결 사항을 구현 계획에 기록하고 관련 문서 7개를 `docs/mcp/`로 모았다. 기존 그래프 연결과 도구 삭제는 수행하지 않았다.
- 바꾼 파일: `docs/mcp/`, `docs/README.md`, `SOJAFIT.md`, `evals/PREREGISTER.md`, `docs/worklog/STH.md`.
- 확인: 이동 문서·목록의 상대 링크 91개를 확인해 누락 0개. `git diff --check` 통과. 이전 작업 기록의 옛 경로는 당시 기록으로 보존하며 현재 문서는 `docs/mcp/`에 있다. 실제 DB·외부 API·LangGraph 연결은 실행하지 않았다.

### 2026-11-03 MCP 입력 경계 및 구현 계획 정합성

- `search_tsc_web`의 문서 ID 길이를 `get_corpus_document`와 동일한 1~200자로 검증해 내부 예외 대신 경계에서 입력 오류를 반환하도록 맞췄다. 빈 값·200자·201자 조건의 회귀 테스트를 추가했다.
- 구현 계획의 MCP 도구 수를 5개로 고치고, 로컬 PDF 무결성 및 공개 회로 조회는 구현됐으며 PDF 다운로드·내용 검증과 사용자 회로 권한은 미구현임을 구분했다.
- 검증: 프로젝트 루트에서 `uv run --no-sync pytest -q -rs tests/test_mcp_search.py tests/test_mcp_manifest.py tests/test_graph_read_input.py tests/test_rag_retrieve.py tests/test_graph_search.py` — 57 passed, 1 skipped (`TEST_DATABASE_URL` 미설정). `git diff --check` 통과.

## 2026-11-03 로그인 정보 응답 마스킹
- 한 일: 로그인 입력 검증 오류에서 입력값을 응답하지 않도록 하고 관리자 계정 목록 이메일을 `a***@domain` 형식으로 마스킹했다. 로그인 작업서와 SPEC에 기준을 추가했다.
- 바꾼 파일: backend/main.py, tests/test_auth.py, docs/specs/login-auth.md, SPEC.md, docs/worklog/STH.md.
- 실행한 명령과 결과: `uv run --no-sync python -m pytest tests/test_auth.py -q -p no:cacheprovider` — 11 passed, 14 skipped (격리 인증 DB 미설정). `git diff --check` 통과.
- 확인 못 한 것: 격리 DB 통합 시험과 배포 환경의 실제 프록시·서버 로그.
- 다음 할 일: 격리 DB가 준비되면 건너뛴 인증 통합 테스트를 실행한다.

### 2026-11-03 우선순위 2 MCP 도구 기본 기능

- `verify_tsc_pdf`를 저장소 TSC 표본 3건의 서명·바이트 크기·SHA-256 무결성 대조로 구현했다. 내용 파싱 검증과 신규 PDF 다운로드는 하지 않고 미검증 상태를 반환한다.
- `get_circuit_info`를 고정 공개 회로 카탈로그와 기존 `circuit_around` 함수에 연결했다. 임의 파일 경로를 받지 않는다.
- MCP/spec/폴더 안내/구현 계획을 갱신하고 PDF 표본·회로 조회·잘못된 입력 및 stdio 호출 시험을 추가했다. 첫 실행은 manifest 문서 정보에 bytes가 없어 4건 실패했고, bytes 필드를 포함한 뒤 재실행해 `tests/test_mcp_search.py tests/test_mcp_manifest.py tests/test_graph_read_input.py tests/test_rag_collect.py tests/test_rag_parse.py` 44 passed.

## 2026-11-03 MCP·웹 검색 후보 논의 초안
- 사용자 확인: W02~W08 7질의, 공급자당 최대 7회·재시도/본문 추출 없음·15초 제한·총 지출 $0, 공식 도메인 적중 4~7/7과 중앙값 0.5~5초의 사전 기대를 초안에 기록했다. 최신 원격 main SPEC과 11-03 공식 가격을 읽기 전용으로 대조했다. 비교 API 호출과 실험 사전등록은 하지 않았다.
- 무료 기능 탐색: Exa 익명 MCP 초기화·도구 목록 HTTP 200, 공개 W01 검색 1회 HTTP 200·1,172.74ms. 응답에 manifest와 경로가 일치하는 공식 도메인 PDF 링크가 있었으나 원본 PDF·개정·해시는 확인하지 않았다. 공급자 비교 및 운영 성능 결과가 아니다. 초기 도구 형식 출력의 Windows cp949 오류는 ASCII 출력으로 재조회해 해결했다.
- 추가 준비: manifest의 8개 문서 제목·개정·ID를 대조해 웹 검색 질문, 품번·출처·개정 구분, 24회 상한 비용 추정과 무료 Exa 연결 탐색 조건을 초안에 추가했다. 공식 정답·품질 결과는 아니다.
- 한 일: 2026-11-02 조사 내용을 바탕으로 프로젝트 도구별 외부 MCP 후보와 웹 검색 비용·적합성, 미결 사항 및 다음 논의·검증 절차를 초안으로 정리했다.
- 바꾼 파일: docs/mcp-tool-candidates-draft.md, docs/DOCS.md, docs/worklog/STH.md.
- 확인: 프로젝트 MCP 안내·SPEC·문서 목록과 초안의 경로를 대조한다. 외부 가격은 2026-11-02 공식 안내 기준이며 도입 전 재확인한다.
- 확인 못 한 것: Tavily·Brave 실제 호출, 공급자 간 품질·지연·비용 비교, Exa 링크의 PDF 원문과 키 없는 데모의 실시간 웹 검색 평가 인정 여부.

## 2026-11-02 최신 main 반영 및 인증 변경 검증
- 한 일: 원격 main 404f2e1을 로컬 main과 STH에 fast-forward로 반영하고 보관한 로그인·데모 시드·인증 키 변경을 복원했다. .env.example, README, backend/main.py, db/DB.md, tests/TESTS.md의 충돌에서 양쪽 유효 내용을 보존했다.
- 확인: 격리 PostgreSQL에서 PYTHONUTF8=1로 전체 pytest를 실행해 75건 통과·10건 건너뜀. 최초 실행은 동결 데이터의 Windows CRLF 체크아웃 때문에 해시 검사 1건이 실패했다. 정규화한 값과 Git 원본이 기록된 해시와 일치함을 확인한 뒤 작업 사본을 동일한 Git 원본 바이트로 복원하고 재실행했다. 동결 데이터는 커밋에 포함하지 않는다.
- 확인 못 한 것: 클라우드 비밀값과 배포, 운영자 메뉴 UI, RAG DB가 필요한 검사 10건.

## 2026-11-02 로그인 피드백과 인증 키 실측
- 한 일: 격리된 Compose PostgreSQL에서 데모 시드와 비데모 기본 계정 차단을 확인하고 로컬 AUTH_SECRET으로 역할별 로그인·관리 API·세션 HMAC·키 교체·로그아웃을 각 3회씩 확인했다. 키와 토큰은 기록하지 않았다.
- 바꾼 파일: docs/auth-feedback-key-verification.md, docs/DOCS.md, docs/worklog/STH.md.
- 확인: TestClient 실측 6회 성공, 전체 pytest 75건 통과·RAG 관련 10건 건너뜀. 실행 환경과 개별 시간은 실측 문서에 기록했다.
- 확인 못 한 것: 운영자 메뉴 UI, 실제 API 컨테이너의 .env 전달 및 클라우드 배포, 동시 부하.

## 2026-11-02 인증 키와 세션 저장값 연결
- 한 일: 세션 토큰은 난수로 유지하고 AUTH_SECRET이 있으면 HMAC-SHA256으로 DB 저장값을 계산하도록 변경했다. 키 없는 데모는 기존 SHA-256을 유지하며 데모 외 환경은 32바이트 이상 키를 요구한다. 로컬 .env에 비어 있던 키를 생성하고 값은 기록하지 않았다.
- 바꾼 파일: backend/auth.py, backend/main.py, tests/test_auth.py, tests/TESTS.md, docs/auth_boundary_after_merge.py, .env.example, README.md, SPEC.md, docs/specs/login-auth.md.
- 확인: 키 설정·미설정, 앱 시작, 키 변경과 세션 거부, 로그인·로그아웃을 격리 PostgreSQL에서 검사했다. 전체 pytest 75건 통과, RAG DB 관련 10건 건너뜀. 후속 키 관련 재검사 4건 통과.
- 확인 못 한 것: 클라우드 비밀값 설정과 배포 반영. 키 전환 전 세션은 재로그인이 필요하다.

## 2026-11-02 데모 시드 검증과 모드 제한
- 한 일: DB 문서의 시드 설명을 갱신하고 실제 시드 SQL의 기본값·사용자 지정·일부 설정·데모 모드별 동작을 격리 DB 회귀 테스트에 추가했다. 공개 기본 계정은 DEMO_MODE=1에서만 생성하도록 제한하고 명시적으로 지정한 네 값은 계속 허용한다.
- 바꾼 파일: db/DB.md, db/007_demo_accounts.sql, docker-compose.yml, tests/test_auth.py, tests/TESTS.md, .env.example, README.md, SPEC.md, docs/specs/login-auth.md.
- 확인: 모드 제한 전 새 테스트 1건이 실패했고 제한 후 5건 모두 통과했다. 격리 Compose 새 볼륨에서 DEMO_MODE=1은 계정 2개, 0은 0개를 확인했다. UTF-8 모드의 전체 pytest는 71개 통과, RAG DB 관련 10개 건너뜀이다.
- 확인 못 한 것: 기존 DB 볼륨 및 배포 DB 적용. 기본 계정 정보는 공개 데모 전용이다.

## 2026-11-02 로그인 역할 응답과 Compose 데모 계정
- 한 일: `/api/auth/me`가 DB에서 확인한 역할을 사용자 ID와 함께 반환하도록 변경했다. Compose 새 DB에서 DEMO 변수 네 개가 모두 비면 공개 데모 계정을 생성하고 네 값이 모두 있으면 해당 값을 사용한다. 일부 설정은 오류로 처리한다.
- 바꾼 파일: 인증 API와 테스트, 데모 시드, `.env.example`, README, SPEC, 로그인 작업서.
- 확인: 격리 Compose PostgreSQL에서 데모 관리자·사용자 로그인과 역할 응답을 확인하고 인증 통합 테스트를 실행했다.
- 확인 못 한 것: 기존 볼륨과 배포 DB의 시드 적용. 공개 데모 자격 증명은 실제 서비스나 제출용 계정으로 사용하지 않는다.

## 2026-10-30 Migration 1 SQL 초안
- 한 일: 최신 `db/table-definition.md`의 5.1~5.14를 기준으로 업무 테이블 14개, 기본키·CHECK·외래키·UNIQUE 및 정의서의 해시 인덱스를 담은 초안을 작성했다. 벡터 임베딩 Migration 2는 차원과 확장 스키마가 결정되지 않아 제외했다.
- 바꾼 파일: `db/001_create_business_tables.sql.draft`, `db/DB.md`, `docs/worklog/STH.md`
- 실행한 명령과 결과: 로컬 `STH`를 `main`까지 fast-forward했다(원격 변경 없음). 이력 결과 `STH`는 `origin/STH`보다 9개 커밋 앞섰다. SQL은 아직 DB에 적용하지 않았다.
- 확인 못 한 것: `db/ERD.md` 승인, migration runner 및 이력 테이블 선택, Supabase/Compose 양쪽 실행, IDENTITY 방식, `updated_at` 갱신 주체, 일부 가정 제약조건.
- 다음 할 일: 초안과 위 결정 항목을 검토·확정한 뒤 선택한 runner에 맞는 migration 경로로 옮겨 빈 로컬 DB 및 개발 DB에서 검증한다.

## 2026-10-30 Langfuse Cloud 연결 확인
- 한 일: `STH` 브랜치에서 Langfuse SDK v5 환경변수 호환과 자격증명 확인 함수를 추가했다. 자동 프롬프트·응답 계측은 보류했다.
- 바꾼 파일: `backend/services/llm.py`, `.env.example`, `backend/services/SERVICES.md`, `SPEC.md`, `docs/worklog/STH.md`
- 실행한 명령과 결과: `.env` 자격증명 값을 출력하지 않고 Cloud `GET /api/public/projects`를 호출해 인증 성공과 프로젝트 1개를 확인했다.
- 확인 못 한 것: Python SDK 함수 실행과 모델 trace는 검증하지 않았다. 현재 `.env`에 `OPENROUTER_API_KEY`가 없고, 이 셸에서 `uv`와 프로젝트 `.venv`를 찾지 못했다.
- 다음 할 일: 프롬프트·응답을 Cloud에 저장할지 결정되면 실제 LLM 계측을 추가한다.

## 2026-10-30 Migration 초기화 SQL 순서 정렬
- 한 일: Docker Compose 초기화 SQL에서 pgvector 확장이 업무 스키마보다 먼저 실행되도록 세 자리 파일명 규칙을 적용했다.
- 바꾼 파일: `db/01_init.sql`을 `db/000_init.sql`로 이동하고 `db/DB.md`, `docs/worklog/STH.md`를 갱신했다.
- 실행한 명령과 결과: 파일명 정렬과 Git diff를 확인했다. 실제 DB 초기화는 실행하지 않았다.
- 확인 못 한 것: 빈 DB에서 Compose 초기화, Supabase 적용, Migration 1/2 실행 이력은 검증하지 않았다.
- 다음 할 일: 피드백 2번의 `thread_id` 생성 규칙을 확정한 뒤 초안에 반영한다.

## 2026-11-02 Migration 1 코퍼스 정의 중복 정리
- 한 일: Migration 1 초안에서 PR #17 코퍼스 SQL과 중복된 문서·청크 표 및 청크 해시 인덱스 생성 정의를 제거하고 선행 조건을 기록했다. 기존 외래 키는 유지했다.
- 바꾼 파일: `db/001_create_business_tables.sql.draft`, `db/DB.md`, `db/table-definition.md`, 이 파일.
- 실행과 결과: 격리된 Compose PostgreSQL에서 pgvector 확장, PR #17 코퍼스 SQL, 수정된 초안을 순서대로 적용했다. 전체 15개 표와 문서·청크 참조 외래 키 6개를 확인했다. 원본 초안은 같은 조건에서 `source_documents` 중복으로 실패했고 트랜잭션이 롤백됐다. 검증 중 중지된 테스트 컨테이너를 재시작하고 동일 검증을 다시 수행했다.
- 확인 못 한 것: 실제 코퍼스 데이터가 있는 DB, Supabase, 마이그레이션 이력 도구와 자동 초기화 순서. PR #17은 현재 STH에 아직 반영되지 않았다.
- 다음 할 일: 팀의 최신 변경을 반영하고 ERD 및 SQL 실행 순서·이력 방식을 확정한 뒤 데이터가 있는 환경을 검증한다.

## 2026-11-02 로그인 및 사용자 식별 1차 구현
- 한 일: 기존 로그인 시안을 FastAPI에 연결하고 PostgreSQL 사용자·서버 세션, scrypt 비밀번호 해시, 동일 출처 확인, 계정별 로그인 실패 제한을 추가했다. 사전 생성 계정은 대화형 명령으로 준비한다. Migration 1 초안의 users 중복 정의를 인증 SQL로 이동했다.
- 바꾼 파일: `backend/auth.py`, `backend/main.py`, `backend/web/login.html`, `backend/web/WEB.md`, `db/03_auth.sql`, `db/001_create_business_tables.sql.draft`, `db/DB.md`, `db/ERD.md`, `db/table-definition.md`, `docs/specs/login-auth.md`, `docs/specs/SPECS.md`, `tests/test_auth.py`, `tests/TESTS.md`, `SPEC.md`, `.env.example`, `README.md`, 이 파일.
- 검증: 테스트 전용 PostgreSQL 컨테이너에 인증 SQL을 적용하고 `TEST_AUTH_DATABASE_URL`을 지정해 `.venv/Scripts/python.exe -m pytest -q`를 실행했다: 30 passed, 2 skipped. 두 계정의 로그인·세션·로그아웃·만료와 5회 실패 제한을 확인했다. 브라우저에서 테스트 계정 로그인과 로그아웃을 확인했다. `uv` 실행 파일은 현재 셸에서 찾지 못해 기존 프로젝트 가상환경의 Python을 사용했다.
- 미구현·미검증: 기존 DB·Supabase·Cloud Run에 스키마 적용 및 배포, 사용자별 회로·대화·기억·견적 접근 제어, 계정 생성 자동화·비밀번호 재설정, 대규모 악용 방어와 운영 보안 검토, 실제 평가 계정 준비, 평가셋 재측정. CI에서는 인증 통합 DB가 제공되지 않으면 해당 테스트를 건너뛴다.
- 다음 할 일: 팀과 기존 DB 마이그레이션 이력·실행 순서를 확정하고, AUTH_ORIGIN과 쿠키·자원 한도를 배포 환경에서 검증하며, 각 기능 구현 시 사용자 소유권 검사를 연결한다.

## 2026-11-02 최신 main 반영 및 로그인 작업 복원
- 한 일: 미커밋 로그인 변경을 untracked 파일까지 stash에 보관하고 `main`을 `git pull --ff-only`로 갱신했다. `STH`에 최신 main을 fast-forward한 뒤 보관한 변경을 다시 적용했다. `SPEC.md`와 `tests/TESTS.md`는 자동 병합됐으며 미해결 충돌은 없다. 보관본은 유지했다.
- 확인: 새 로그인 파일 4개의 Git 해시가 보관본과 일치하고 `git diff --check`에 오류가 없다. 격리 인증 DB를 사용해 `.venv/Scripts/python.exe -m pytest -q`를 다시 실행한 결과 31 passed, 2 skipped. 테스트 DB 컨테이너는 정지했다.
- 남은 일: 기존 DB 마이그레이션, 실제 사용자별 업무 데이터 접근 제어, 배포 보안 확인 및 평가셋 재측정은 수행하지 않았다.

## 2026-11-02 DB 폴더 안내 중복 정리
- 한 일: `db/DB.md`에서 중복된 Migration 1 목록과 존재하지 않는 `01_init.sql` 항목을 제거하고 현재 SQL 파일 및 실행 순서와 대조했다. 기존 볼륨에 초기화 SQL이 자동 재실행되지 않는 점과 볼륨 삭제 시 데이터가 사라지는 점을 명시했다.
- 확인: `db/` 파일 목록 및 SQL 초안의 선행 조건과 문서를 대조했다. DB 실행이나 볼륨 삭제는 하지 않았다.

## 2026-11-02 DB SQL 파일 번호 정리
- 한 일: 실행 순서에 맞춰 `02_rag_corpus.sql` → `002_rag_corpus.sql`, `03_auth.sql` → `003_auth.sql`, 업무 초안 `001_create_business_tables.sql.draft` → `004_create_business_tables.sql.draft`로 이름을 정리했다. 관련 코드·테스트·문서 경로를 갱신하고 `001`은 비워 뒀다. 코퍼스·임베딩 SQL은 삭제하지 않았다.
- 확인: Git 이력에서 별도의 `db/002*` SQL 삭제 기록은 찾지 못했다. 기존 두 자리 `02_rag_corpus.sql`이 코퍼스 및 임베딩을 생성한다. 각 SQL의 실행문은 변경 전과 같고 주석·파일명만 바뀌었다.
- 검증: 테스트 컨테이너의 별도 빈 DB에서 `000` → `002` → `003` → `004` 초안을 순서대로 수동 적용해 테이블 17개를 확인했다. 별도 DB에 `TEST_DATABASE_URL`, `TEST_AUTH_DATABASE_URL`을 지정하고 `.venv/Scripts/python.exe -m pytest -q` 실행: 32 passed, 1 skipped. 적재 테스트는 테스트 전용 DB에서 임시 스키마를 만들고 삭제했다.
- 확인 못 한 것: 실제 Compose 신규 볼륨 자동 초기화, 기존 팀원 DB·Supabase의 파일명 기반 이력과 데이터, 평가셋 재측정. 파일명 변경이 기존 마이그레이션 도구의 이력에 미치는 영향은 도구와 환경 확정 후 확인한다.

## 2026-11-02 인증·DB 적용·CI 1차 보강
- 한 일: 인증된 사용자 ID와 thread·Store·업무 데이터 소유권의 연결 계약 및 교차 접근 테스트 초안을 기록했다(팀 검토 필요). 실제 그래프·업무 API는 아직 없어 소유권 기능은 구현하지 않았다. 기존 DB의 인증 스키마를 읽기 전용으로 대조하는 절차를 추가했다.
- 한 일: PR CI에 격리 PostgreSQL과 인증 SQL 초기화를 추가했다. 로그인 실패 집계를 15분으로 한정하고 5회 실패 후 15분 잠금 정책을 유지했다. 기존 잠금 의미를 보존하기 위해 새 `005_auth_attempt_window.sql`로 집계 시작 컬럼을 추가했다.
- 검증: 실패 집계 시간이 없는 기존 코드에서 테스트 실패를 확인한 뒤 수정 후 통과했다. 격리 PostgreSQL 16에서 CI와 같은 인증 SQL 초기화 후 전체 테스트 33 passed, 2 skipped(코퍼스 DB 미설정). 기존 사용자·세션·활성 잠금이 있는 별도 모의 DB의 데이터 보존을 확인했다. DB 점검 SQL과 CI YAML 구조를 확인했다. GitHub Actions 실행은 아직 확인하지 않았다.
- 로컬 개발 DB: 대상 스키마와 제약을 격리 기준 DB와 읽기 전용 비교한 뒤 `005`만 트랜잭션으로 적용했다. 적용 전후 users 4건·sessions 1건·login attempts 0건이 유지됐고, 기존 로컬 테스트 계정 두 개로 변경된 코드의 로그인·식별·로그아웃을 확인했다. 공유 DB와 Cloud에는 적용하지 않았다.
- 남은 일: 실제 업무 데이터의 소유권 적용·교차 접근 테스트, 팀의 thread/Store ID 계약, 계정 잠금 악용·분산 요청·실패 기록 보존 대책, 실제 GitHub Actions 및 Cloud 배포 검증, 기존 DB 마이그레이션 이력 방식 확정, 평가셋 재측정. 과거 실패 기록 중 집계 시작 시간이 없는 비잠금 기록은 다음 실패부터 새 구간을 시작하며 활성 잠금은 유지된다.

## 2026-11-02 인증 리뷰 경계·동시 제한 검증 보강
- 한 일: 비활성 계정 및 비활성 사용자의 기존 세션 거부, 30분 유휴·8시간 절대 만료 경계 전후, 15분 잠금 중 차단과 잠금 종료 후 허용, 두 PostgreSQL advisory 슬롯 점유 시 503 테스트를 추가했다. HTTPS Secure 쿠키·교차 Origin 로그아웃·DB 오류 상세 미노출 테스트도 포함했다.
- 검증: 별도 CI 전용 PostgreSQL 16 (`sojafit-ci-auth-check`, 127.0.0.1:55434)에서 `TEST_AUTH_DATABASE_URL` 지정 후 `.venv/Scripts/python.exe -m pytest -q tests/test_auth.py`: 12 passed. 기존 로컬 개발 DB와 계정은 사용하지 않았다.
- 제한: 만료 경계는 DB 시각을 기준보다 5초 안팎 앞/뒤로 설정해 시험했으며 8시간을 실제 기다린 시험은 아니다. 두 advisory 잠금 점유 테스트는 초과 요청의 503 제한을 검증하지만, Cloud Run 프로세스의 실제 RSS나 scrypt 병렬 메모리는 측정하지 않았다.

## 2026-11-02 관리자·사용자 계정 권한
- 한 일: `006_user_roles.sql`로 기존 계정 기본 역할 `user`를 추가하고 신뢰된 명령줄에서 `admin` 생성 옵션을 제공했다. 관리자 전용 계정 조회·일반 계정 활성화 API와 로그인 화면을 추가했다. 일반 사용자의 관리자 API 접근과 관리자 계정의 상태 변경은 거부한다. 사용자 비활성화와 세션 삭제를 한 트랜잭션에서 처리하고 로그인과 비활성화가 사용자 행 잠금으로 경합하도록 했다.
- 변경: `backend/auth.py`, `backend/main.py`, `backend/web/login.html`, `db/006_user_roles.sql`, CI 초기화, 인증 테스트, `SPEC.md`, 인증 작업서·DB 안내·ERD·README·테스트 안내.
- 검증: 새 역할 컬럼이 없는 상태에서 새 관리자 테스트가 실패하는 것을 확인한 후 구현했다. 격리 PostgreSQL에서 전체 테스트 39 passed, 2 skipped. 새로 만든 임시 테스트 DB에 003→005→006 적용 후 인증 테스트 13 passed, 임시 DB만 삭제했다. 기존 `.venv` Python을 사용했으며 `uv` 명령은 PATH에서 찾지 못했다.
- 로컬 개발 DB: 사전 상태 사용자 4명·세션 2건을 확인하고 006을 적용했으며 기존 계정은 `user`로 유지했다. 별도 로컬 관리자·사용자 테스트 계정 2개를 생성하고 HTTP로 관리자 조회 200·일반 사용자 거부 403·비활성 세션 거부 401·재활성화 후 이전 세션 거부 401을 확인했다. 기존 세션 두 건은 유지했다. 테스트 비밀번호는 저장소 밖 이 PC의 로컬 `.env`에만 보관했다.
- 미검증: 관리자 화면의 직접 브라우저 조작, 공유 DB·Cloud Run 마이그레이션과 배포, GitHub Actions, 업무 데이터 소유권과 전체 평가셋. 기존 DB에서는 앱 업데이트 전 006을 한 번만 적용해야 한다.

## 2026-11-02 최신 main 병합과 로그인 작업 복원
- 한 일: PR #22의 head가 기존 STH 커밋 `d981455`와 같음을 Git 참조로 확인했다. 미커밋 관리자 작업을 untracked 파일 포함 stash로 보관한 뒤 `origin/main`을 STH에 병합했다. `db/DB.md`와 `db/ERD.md`의 코퍼스 halfvec 안내와 인증 SQL 명명·역할 안내를 함께 보존했다.
- 후속 수정: main에서 들어온 RAG 저장소 테스트가 옛 `db/02_rag_corpus.sql` 경로를 사용하는 부분을 `db/002_rag_corpus.sql`로 맞추고, Windows SQL 파일 UTF-8 읽기 및 비밀번호가 생략되는 `db.info.dsn` 재연결을 수정했다.
- 검증: 테스트 전용 PostgreSQL 16과 별도 임시 pgvector DB를 사용했다. 첫 실행은 임시 DB의 확장 미설치 및 Windows 기본 인코딩, 두 번째 실행은 잠금 테스트의 비밀번호 없는 DSN으로 실패해 각각 원인을 수정했다. pgvector 확장 및 UTF-8 환경에서 동일 전체 검사 재실행: 73 passed, 1 skipped. 임시 DB는 삭제했다.
- 제한: GitHub 연결 도구는 PR #22에 404를 반환하고 gh CLI는 사용할 수 없어 PR 메타데이터는 확인하지 못했다. 원격 PR 상태·GitHub Actions·배포는 확인하지 않았으며 push하지 않았다. 기존 stash와 이번 보관 stash는 유지했다.

## 2026-11-02 인증 리뷰 실측 기록
- 한 일: STH `8dc9630` 기준으로 격리 PostgreSQL 16.15에서 두 계정의 로그인·세션 분리·로그아웃, 잠금·세션 만료 경계, 실제 scrypt 동시 실행과 프로세스 메모리를 측정하고 `docs/auth-login-verification.md`에 기록했다. `docs/DOCS.md`에 파일을 등록했다.
- 환경과 결과: Windows Python 3.12.10, FastAPI TestClient, 로컬 테스트 DB. 고정된 트랜잭션 시각에서 잠금 900초와 절대 만료 28,800초 및 경계 전·동일·후 상태가 기대와 같았다. 2개 scrypt 호출이 343.11ms 겹친 동안 세 번째 요청은 503이었다. Windows 프로세스 working set은 단일 요청 54.11→183.43MiB, 동시 2개 55.39→312.13MiB였다. 각 결과는 단일 실행이다.
- 실행: 프로젝트 `.venv/Scripts/python.exe`로 로컬 실측 스크립트 `auth_boundary_after_merge.py`, `measure_scrypt_concurrent.py`를 각각 격리 DB에 대해 실행했다. 실측 스크립트와 원시 JSON은 로컬 작업 폴더에만 보관했고 테스트 데이터는 롤백 또는 삭제했다.
- 제한: 메모리는 Windows Python 프로세스 표본이며 PostgreSQL·OS 메모리는 제외, Cloud Run·실제 경과 시간 대기·분산 인스턴스는 미검증. 반복 부하 및 GitHub Actions 결과도 별도 확인이 필요하다.

## 2026-11-02 로그인 테스트 화면 제거 및 Compose 데모 계정 시드
- 한 일: 수동 로그인·관리자 화면 HTML과 해당 루트 라우트를 제거하고, 로컬 `.env`의 이메일·scrypt 해시를 사용하는 Compose 초기화 SQL 시드를 추가했다. 자격 증명은 읽거나 저장소에 기록하지 않는다.
- 문서 보완: README의 상세 `.env` 설정 절차는 제거하고, 필요한 변수·해시 생성·따옴표 규칙을 `007_demo_accounts.sql` 주석으로 옮겼다. `.env.example`에는 변수 목록과 간단한 안내를 유지했다.
- 제한: 자동 시드는 새 Compose 볼륨의 최초 초기화에서만 실행된다. 네 환경변수가 모두 비어 있으면 건너뛰며, 기존 볼륨에는 자동 재실행되지 않는다.
- 검증: `uv run pytest tests/test_auth.py tests/test_health.py -q` 결과 8 passed, 8 skipped(로컬 테스트 인증 DB 미설정). 루트 회귀 테스트는 수정 전 HTML 응답 200으로 실패했다. 해시 전용 CLI 시험을 포함했다. `docker compose config --quiet` 통과. 이름이 분리된 새 Compose DB에서 임시 scrypt 해시로 관리자·일반 계정 생성과 해시 형식을 확인하고 DB 초기화 로그에 해시가 없는 것을 검사했다. 환경변수를 비운 별도 새 DB도 정상 기동하고 users 0건임을 확인했다. 두 격리 테스트 프로젝트의 볼륨만 삭제했으며 기존 개발 DB는 사용·변경하지 않았다. 별도 임시 `.env`로 작은따옴표로 감싼 scrypt 해시가 Compose 컨테이너 환경에 그대로 전달되는 것도 값 비공개 상태로 확인했다. `git diff --check`에서 공백 오류는 없고 줄바꿈 변환 경고만 표시됐다.

## 2026-11-02 인증 실측 재현 자료 추가
- 한 일: 인증 경계값·scrypt 측정 스크립트와 해당 실행의 원시 JSON을 `docs/`에 복사하고 실측 기록 및 문서 색인에 링크했다. 저장소 루트에서 실행할 수 있도록 스크립트에 repo 경로 준비를 추가했다.
- 안전 범위: 스크립트는 `TEST_AUTH_DATABASE_URL`에 `127.0.0.1:55434/ci_auth`가 있을 때만 실행한다. 실측 산출물에서 계정 비밀번호·세션 토큰·DB 접속 문자열은 확인되지 않았다. 재실행은 원시 JSON을 덮어쓴다.
- 확인: JSON 값과 문서 수치를 대조하고, 스크립트 문법을 검증한다. DB 실측은 새로 수행하지 않는다.

### 2026-11-03 웹 검색 후보 비교 준비
- 목적·조건: Tavily keyless, Exa 익명 MCP, Brave를 W02~W08 각 최대 1회 비교. 15초 제한, 재시도·본문 추출 없음, 실제 지출 $0. 불확실한 유료 계정은 호출하지 않음.
- 기대와 실패 처리: evals/PREREGISTER.md의 웹 검색 후보 탐색 항목 참조. 동결 평가셋은 사용하지 않음.
- 시작 전 상태: STH에서 git pull --ff-only 결과 최신; origin/main은 22커밋 앞섬. 기존 미커밋 문서는 보존.

- 실측 결과: Tavily 키 없는 SDK 7회 정상, Exa 익명 MCP 7회 중 정상 4·무료 제한 2·원본 기록 오류 1. Brave 결제 통제 미확인으로 미호출. 비용 . 상세와 축약 원자료는 후보 문서 9절 및 evals/results/web-search-exploration-2026-11-03.json. Tavily 실행기 추가. 프로젝트 MCP/서비스 연동과 Brave 측정은 미완료.

- 2026-11-03 Brave 추가 실측: 사용자가 무료 크레딧 $5와 자동 충전 비활성화를 확인. W02~W08 각 1회, 정상 7/7, 공식 도메인 출현 7/7, 응답 p50 669.14ms. URL·본문 미보관, 파생 통계 보관 허용 여부 및 실제 계정 크레딧 차감은 미확인.

- 2026-11-03 웹 검색 재측정 준비: 기존 결과를 알고 같은 W02~W08을 세 후보에 최대 한 번씩 재실행. 무료 경로·지출 , 15초, 재시도 없음. 기대·조건은 사전등록 참조.

- 2026-11-03 웹 검색 재측정: 21회 전부 정상. Tavily 공식 도메인 4/7·p50 790.22ms, Exa 6/7·p50 1,193.75ms, Brave 7/7·p50 240.48ms. Brave 응답 URL·본문 미보관, 파생 통계 보관 허용 범위와 실제 크레딧 차감은 미확인. 코드 경로의 차이와 이전 결과를 본 반복 실험 한계는 후보 문서 10절.

- 웹 검색 30문항 탐색: 기존 W01~W08을 제외한 manifest에서 seed 42로 30개를 무작위 추출해 입력과 사전 기대를 검색 전 고정. 각 도구 최대 30회, 실제 지출 $0, 재시도 없음.

- 30문항 실측: Tavily 정상 25 후 한도 1·미실행 4, Exa·Brave 각 정상 30. 과거 manifest 주소 일치는 각 2/25·22/30·9/30. URL·본문 없이 질의별 집계와 실행기를 evals에 기록, Brave 파생값의 보관 범위와 실제 크레딧 차감 미확인. 상세 후보 문서 11절.

- Tavily 인증 30문항 준비: 무료 크레딧 30 이상·초과 자동 과금 꺼짐을 사용자가 확인. 같은 30문항 Basic 각 1회, , 재시도 없음. 이전 결과를 이미 본 재측정임을 사전등록.

- Tavily 인증 30문항 실측: 정상 30/30, 도메인 28/30, 과거 주소 일치 3/30, 응답 p50 822.73ms. 키·URL·본문 없는 질의별 집계와 실행기 추가. 무료 크레딧 차감 내역은 대시보드에서 미확인.

- 웹 검색 실측 결과를 팀 공유용 web-search-results-interpretation.md로 정리. 30문항 결과표, 지표별 의미, 후보별 해석과 PDF·비용·호출 조건의 미확인 사항을 기록.


### 2026-11-03 MCP 검색 도구 1차
- main을 1cf18a9까지 fast-forward한 뒤 STH에 반영. 기존 웹 검색 문서·사전등록 복원 중 docs/README.md와 evals/PREREGISTER.md 충돌을 양쪽 내용 보존으로 해결했다. 보관 stash는 안전을 위해 남겼다.
- 작업서 docs/specs/mcp-search-tools.md, SPEC 8.7, FastMCP stdio 서버 두 도구, 환경변수 예시, 의존성·테스트를 추가했다. EXA_WEB_SEARCH_ENABLED 기본 0, 데모에서도 외부 호출을 차단하고 결과를 미검증 후보로 표시한다.
- uv run --no-sync pytest -q tests/test_mcp_search.py tests/test_rag_retrieve.py tests/test_graph_search.py: 31 passed, 1 skipped. stdio 응답 형식 차이로 첫 실행은 1 failed였고 응답 텍스트를 JSON으로 읽도록 고친 뒤 재실행해 통과했다.
- 실제 Exa API 호출·과금·PDF 검증·실제 DB 연동·LangGraph 연결·Compose/클라우드 배포 및 가산점은 미검증이다.

### 2026-11-03 웹 검색 도메인 필터 비교 준비
- 기존 30문항으로 도구별 무필터/필터 1회씩 짝 비교. 총 최대 180회, 결과 5개, 15초, 재시도 없음, 지출 $0.
- Exa Auto·Tavily Basic·Brave Search 각 인증 경로로 고정. Brave는 site 연산자를 쓰며 세 공급자의 필터 방식은 동일 구현이 아님. 무료 잔액과 자동 과금·충전 확인을 기다린다.

- 2026-11-03 TSC 필터 비교: 사용자 무료 잔액 및 자동 과금 차단 확인 후 Exa·Tavily·Brave 각 필터 없음/적용 30회씩, 총 180/180 정상. 기존 manifest 주소 일치는 Exa 23→24, Tavily 5→5, Brave 9→9. 실제 차감·청구 내역 미확인.
- 별도 사전등록한 S23·S13·S29 공개 PDF 각 1회 확인: 모두 PDF·기존 manifest 해시 일치, 문서명 문자열은 S29 미확인. PDF 원문 및 검색 응답 URL·본문은 저장하지 않음. 세부 결과 docs/web-search-filter-comparison.md.

- MCP 도구 목록과 후속 선행 조건을 docs/mcp-tool-implementation-plan.md에 정리했다. get_corpus_document를 추가해 기존 manifest의 문서 메타데이터를 읽기만 하고 PDF 미검증 상태를 표시한다. MCP·RAG 테스트 36 passed, 1 skipped; 실제 DB 및 외부 PDF 연동은 미검증.

- MCP 우선순위 1~2 실행 준비: 기존 계획에 5개 도구·기능의 현재 상태, 단계별 준비·검증·완료 기준, 팀 결정 항목 추가. MCP·RAG 테스트 36 passed, 코퍼스 DB 검사 1 skipped. Docker 엔진 접근 불가를 확인. 외부 API·DB 데이터 변경 없음.

### 2026-11-03 저장소 표본의 DB 없는 테스트 준비
- Git에 있는 PDF 3건·manifest·공개 회로 5종으로 MCP와 입력 읽기, PDF 파일·텍스트를 시험한다. 외부 요청·DB 연결·지출 0. 조건과 기대는 evals/PREREGISTER.md에 먼저 기록했다.

- 저장소 표본 DB 없는 점검: MCP·회로 읽기·수집·파싱 기초 31 passed; PDF 서명·manifest 해시·쪽 수 3/3 일치, 개정 코드·품번 토큰 3/3 발견, 전체 문서명 0/3. pypdf 오프라인 점검 스크립트·결과 문서 추가. Docling·pdfplumber, DB, 실제 Exa는 미실행.

### 2026-11-03 Docling·pdfplumber 표본 대조 준비
- 사용자 요청: 저장소 PDF 3건에 기존 파서를 DB 없이 실행하고 표 숫자를 양방향 대조한다. 금전 $0, 출력은 저장소 밖 사용자 작업공간. Windows 프로세스 외부에서 파일당 600초 제한.
- uv sync --locked --group ingest --offline: torch 캐시 부재로 실패. 이어서 uv sync --locked --group ingest 성공해 잠금된 74개 패키지를 프로젝트 가상환경에 설치했다. Docling 2.145.0, pdfplumber 0.11.10, torch 2.15.0.
- 예상·실행 조건은 evals/PREREGISTER.md에 사전등록. DB·LLM·유료 API를 사용하지 않는다.

- Docling·pdfplumber 실측: uv ingest 의존성을 설치한 후 저장소 TSC PDF 3건을 별도 사용자 작업공간에서 처리. 총 18쪽·표 18개, 표 셀 숫자의 같은 쪽 대조 515/515, 찾은 표 영역 역방향 숫자 누락 0. 대표 정격 3행의 좌표 영역을 별도 대조. 세 원본 해시는 사후에도 manifest와 일치. 파서·MCP 회귀 23 passed. 전체 표 누락·품번/조건 의미·실제 DB 연동은 미검증. 상세 docs/mcp-docling-verification-2026-11-03.md.

### 2026-11-03 MCP 외부 검색 개인정보 경계

- 사용자 결정: 공개 확인된 품번만 외부 검색하고 확인 불가 시 중단한다. 자유 문장 대신 TSC 공개 출처 manifest의 문서 ID를 받아 출처·문서명·개정이 일치할 때만 목록 값으로 검색어를 만든다. 목록 밖은 unverified, 목록 오류는 unavailable로 차단한다.
- 수정: MCP 서버, 검색 도구 작업서·SPEC·MCP 안내·구현 계획, 모의 테스트. 기존 질의 인자 query는 doc_id로 변경했다.
- 모의 테스트에서 변경 전 개인 정보가 포함된 문장이 외부 요청에 전달되려는 실패를 확인했다. 수정 후 `uv run --no-sync pytest -q -rs tests/test_mcp_search.py tests/test_mcp_manifest.py tests/test_rag_retrieve.py tests/test_graph_search.py` 결과 44 passed, 1 skipped (테스트 DB 미설정). 실제 Exa 호출 및 비용 발생은 없다.
- 제한: manifest는 과거 공개 출처 기록이며 실시간 공개 상태를 보증하지 않는다. 목록 밖 신규 품번 검색, 다른 외부 서비스의 정보 전송, 공급자의 로그·보관 정책은 검증하지 않았다.

### 2026-11-03 TSC 공개 품번 확인 방안 정리

- 코퍼스 밖 TSC 품번 조회와 외부 전송의 경계를 논의할 수 있도록 네 가지 방안, 장단점, 결정 항목을 docs/tsc-public-part-verification-options.md에 정리하고 docs/README.md에 연결했다. 팀 결정 전 초안이다.
- 코드·DB·API 변경이나 외부 API 호출은 없다. 출처 자료의 전체 품번 포함 여부, 자동 수집 조건과 제조사 API는 미확인이다.

### 2026-11-03 MCP 현황과 다음 작업 준비

- 현재 코드·문서·Skill 양식과 브랜치 상태를 대조하고 기존 MCP 구현 계획에 완료 범위, 검증 경계, 후속 순서를 정리했다.
- `uv run --no-sync pytest -q -rs tests/test_mcp_search.py tests/test_mcp_manifest.py tests/test_rag_retrieve.py tests/test_graph_search.py`: 44 passed, 1 skipped (테스트 DB 미설정). `docker compose ps`: Docker 엔진 소켓 부재로 연결 실패. 외부 API·DB 변경 없음.

### 2026-11-03 격리 DB MCP 검색 점검

- 임시 pgvector PostgreSQL 16.15에 합성 문서 4건·청크 8건을 넣고 데모 BM25 및 stdio MCP 경로를 확인했다. 일반 실행의 첫 검색이 지연됐으며 추적상 NumPy import에 머물렀다. 진단용 사전 import 조건에서만 알려진 품번 2건, 미존재 품번 0건, 다른 품번 필터 0건, manifest found, 웹 disabled를 확인했다. 실제 코퍼스 및 원인 검증은 미완료. 상세와 단발 측정치는 docs/mcp-tool-implementation-plan.md 참조. 기존 DB·외부 API는 사용하지 않았다.
### 2026-11-03 우선순위 2 MCP 도구 골격

- `verify_tsc_pdf(doc_id)`와 `get_circuit_info(circuit_id, target)`를 MCP 도구 목록에 추가했다. 두 도구는 입력 형식만 확인하고 `not_implemented`를 돌려주며 네트워크·파일·DB에 접근하지 않는다.
- MCP 작업서와 폴더 안내, 구현 계획에 미구현 상태와 선행 결정 사항을 명시했다. 검색 지연 조사는 미해결이라 그 로직은 수정하지 않았다.
- 이번 요청에서는 테스트 실행을 하지 않았다. 변경 검토는 diff 확인으로 제한한다.

### 2026-11-03 최신 main 통합

- `origin/main`의 17개 커밋을 로컬 `STH`에 병합했다. `docs/specs/README.md`와 `evals/PREREGISTER.md` 충돌은 MCP 검색·웹/PDF 기록과 main의 Skill·도구 프롬프트 기록을 모두 보존해 해결했다.
- 저장소의 동결 평가셋 blob은 CRLF이고 `FROZEN.json`은 LF 바이트 해시를 기록해 Windows에서 검사가 실패하는 문제를 확인했다. 평가셋 내용이나 기대 해시는 바꾸지 않고 `.gitattributes`에서 `evals/dataset_v*.jsonl`을 항상 LF로 체크아웃하게 했다.
- UTF-8 임시 JSON을 Windows 기본 cp949로 읽던 테스트 2곳에 인코딩을 명시했다. `uv run --no-sync pytest -q` 재실행 결과 184 passed, 24 skipped.
- 원격 push, 외부 API 호출, DB 변경은 수행하지 않았다.

### 2026-11-03 MCP `search_corpus` LangGraph 통합 설계

- 두 사람 분담안의 B 역할에 맞춰 범위를 MCP 서버 구현이 아닌 LangGraph 검색 통합으로 확정했다. 나머지 도구 4개의 사용자 흐름 연결, 서버 계약 변경, 외부 실호출은 제외했다.
- `docs/specs/mcp-graph-integration.md`에 동기 그래프와 비동기 stdio 세션의 경계, 정상 빈 결과와 MCP 장애 구분, 세션 재사용·종료, 가짜 클라이언트와 격리 DB 검증 AC를 작성했다.
- 서버 코드·공통 SPEC·테스트·동결 평가셋은 변경하지 않았다. 구현 전 사용자 문서 검토를 기다린다.

- 작업서 승인 후 `docs/specs/mcp-graph-integration-plan.md`에 6개 구현 작업을 TDD 순서로 작성했다. 그래프 장애 분기, 응답 검증, 지속 stdio 세션, 그래프 재검색, 격리 DB, 문서·변이 검증을 각각 독립 커밋으로 나눈다. 구현 코드는 아직 변경하지 않았다.

### 2026-11-03 MCP `search_corpus` LangGraph 통합 구현

- B 담당 범위에서 `backend/graph/mcp_retriever.py`를 추가하고 기존 `build_graph(retriever=...)`에 주입했다. stdio MCP 세션은 전용 asyncio 루프에서 한 번 열어 재사용하며, 응답 청크 필드·타입을 검사한다. A 담당 `backend/mcp_skill/` 서버 코드는 수정하지 않았다.
- 정상 빈 목록은 기존 문서 없음으로, MCP timeout·도구 오류·응답 형식 오류는 `retrieval_error`로 구분해 채점·재검색 없이 안전한 장애 응답으로 끝낸다. 직접 RAG 기본 경로와 검색 최대 2회는 유지했다.
- TDD 커밋: `3eb7d40` 검색 장애 분기, `bba9c4f` 응답 검증, `5d28e6f` 지속 stdio 세션, `a989b57` 그래프 재검색 통합, `e7b8c70` 조건부 실제 stdio 검사.
- 변이 확인 3건은 검색 상한 2→3, 장애를 빈 결과로 변경, 장애를 채점으로 분기했을 때 각각 지정 테스트가 실패했고 원복 후 통과했다. 상세는 `docs/GATES.md`.
- `uv lock --check` 통과. `uv run --no-sync pytest -q -rs` 결과 196 passed, 25 skipped. 신규 `tests/test_graph_mcp_stdio.py`는 `TEST_DATABASE_URL` 미설정으로 skip되어 실제 그래프→stdio MCP→격리 DB 경로와 단발 지연은 이번 환경에서 확인하지 못했다.
- 외부 API·LLM 실호출, 운영 DB, Docker 볼륨 변경, 나머지 MCP 도구 4개의 그래프 연결은 수행하지 않았다. 원격 push·PR 생성도 수행하지 않았다.

### 2026-11-03 최신 main 재통합

- `origin/main` `5760105`를 로컬 `STH`에 병합했다. 기존 MCP·LangGraph 커밋은 유지하고, `backend/mcp_skill/mcp_server/server.py`의 도구 5종 구현과 `search_corpus` 그래프 연결을 보존했다.
- main의 ADR 0012 폴더 규칙에 맞춰 충돌한 설명 파일을 `GRAPH.md`, `MCP_SKILL.md`, `DOCS.md`, `SPECS.md`, `SCRIPTS.md`에 통합했다. MCP 조사·실측 문서 7개는 `docs/research/`로 옮기고 링크·`SOJAFIT.md` 트리·폴더 파일 목록을 갱신했다.
- main의 턴 초기화와 합쳐질 때 이전 MCP 장애가 남지 않도록 `read_input`이 `retrieval_error`도 초기화하게 하고 회귀 테스트를 추가했다. Windows에서 저장소 구조 테스트가 Git UTF-8 파일 목록을 cp949로 읽던 문제는 subprocess에 `encoding="utf-8"`을 명시했다.
- `uv lock --check` 통과. MCP·그래프 집중 테스트는 `64 passed, 1 skipped`, 전체 `uv run --no-sync pytest -q -rs`는 `209 passed, 25 skipped`였다.
- `TEST_DATABASE_URL`과 인증 전용 테스트 DB가 없어 실제 stdio MCP→격리 DB 및 DB 의존 테스트는 실행하지 못했다. 원격 push·외부 API·운영 DB 변경은 수행하지 않았다.

### 2026-11-03 PR #44 계약 수용과 B 연결 조정

- A 확인에 따라 원격 PR #44 head `0185d55`를 로컬 B 커밋과 병합하고, 이어 최신 `origin/main` `72b7723`의 폴더·평가 변경을 통합했다. PR #44가 저장소 밖 보관으로 정한 MCP 독립 테스트·웹 측정 파일 삭제를 유지했고, B 그래프 테스트는 새 구조인 `tests/graph/`로 옮겼다.
- PR #44의 stdio 관찰 계약인 `structuredContent={"result": [...]}`를 먼저 실패 테스트로 고정했다. 기존 디코더에서 청크 목록과 빈 목록이 모두 `invalid_response`로 실패하는 것을 확인한 뒤, `structuredContent.result`를 우선 검증하고 이전 단일 JSON 텍스트는 호환 경로로 남겼다. 해당 테스트 파일은 `13 passed`였다.
- PR #44·B 문서와 최신 main의 검색 베이스라인·시장 조사 문서를 모두 보존하고 `SOJAFIT.md`, 폴더 설명, B 작업서의 새 경로를 맞췄다. 구조 검사는 `5 passed`, 그래프 묶음은 `58 passed, 1 skipped`, 전체 회귀는 `190 passed, 25 skipped`, `uv lock --check`는 통과했다.
- 일회용 pgvector DB에 합성 문서 4건·청크 5건을 넣어 실제 stdio를 재검증했다. 기본 서버 경로는 10초 제한에서 `timeout`, PR #44에 기록된 `numpy` 선행 import 진단 경로는 4.51초에 청크 2건과 `SS32 SERIES_Q2412.pdf` 출처를 정상 수신했다. 일회용 컨테이너는 제거했다.
- 결론: B의 실제 FastMCP 응답 해석은 조정됐지만, 기본 MCP 서버의 첫 검색 지연은 A 서버 초기화 범위로 남는다. 원격 push·외부 API·운영 DB 변경은 수행하지 않았다.

### 2026-11-03 MCP 첫 검색 지연 개선

- 사용자 결정에 따라 검색 지연을 B 통합 범위에서 직접 개선했다. 격리 DB의 실제 LangGraph → stdio MCP 테스트에 첫 검색 10초 제한을 먼저 추가했고, 변경 전에는 `1 failed in 13.60s`로 재현됐다.
- 원인은 FastMCP 요청 worker에서 처음 실행되던 NumPy 지연 import였다. 공용 검색 모듈 시작 시 NumPy를 읽도록 옮겼으며 MCP 서버 계약과 도구 구현은 변경하지 않았다.
- 같은 합성 DB에서 수정 후 통합 테스트는 `1 passed in 3.58s`, 별도 측정은 프로세스 시작부터 첫 청크 2건까지 2.426초, 같은 세션의 두 번째 검색은 0.045초였다. 이는 합성 문서 4건·청크 5건의 로컬 단발 측정이며 실제 전체 코퍼스의 운영 성능을 뜻하지 않는다.
- MCP·검색 집중 테스트는 `26 passed in 3.80s`, `uv lock --check`와 전체 회귀는 `201 passed, 14 skipped`였다. 외부 API·LLM·운영 DB·원격 저장소는 사용하거나 변경하지 않았다.

### 2026-11-04 로그인 로그 개인정보 점검
- `backend/auth.py`, `backend/main.py`, Dockerfile과 로그인 관련 출력·로깅 경로를 읽기 전용으로 확인했다. 앱 로그인 경로에는 이메일·비밀번호·쿠키 토큰을 출력하거나 기록하는 코드가 보이지 않았고, 유효성 오류 응답에서도 입력값을 제거한다.
- 계정 생성 CLI의 `--hash-only`는 scrypt 비밀번호 해시를 표준 출력에 표시한다. 의도된 기능이지만 출력 리다이렉션/CI 로그에 남지 않도록 운영 시 주의가 필요하다.
- 실제 Uvicorn/Cloud Run 로그 내용·보존기간·접근권한은 확인하지 않았다. 코드 검색은 저장·배포 환경 로그에 개인정보가 없음을 증명하지 않는다. 코드·테스트·외부 설정 변경 없음.
- Google Cloud Console의 `sojafit` 프로젝트에서 Cloud Run 서비스 정상 상태와 비밀값을 열지 않은 Secret Manager 참조를 확인했다. Cloud Logging은 `_Default` 30일, `_Required` 400일 보존이며 라우터에 기본 버킷 외 별도 내보내기 싱크는 보이지 않았다. 로그 항목/본문과 IAM 권한은 열지 않았다.
- Supabase 대시보드의 개인 `sojafit-auth-test` 프로젝트는 Free 요금제이며, 백업 화면에 Free는 프로젝트 백업을 포함하지 않는다고 표시된다. Cloud Run의 `DATABASE_URL` 비밀값은 읽지 않았으므로 실제 서비스가 이 개인 테스트 프로젝트를 대상으로 하는지와 그 DB의 백업 상태는 미확인이다. 외부 설정 변경 없음.
- Supabase 연결에서 프로젝트 메타데이터를 확인한 결과 목록에 활성 상태인 것은 `sojafit-auth-test`뿐이고, 나머지 두 프로젝트는 비활성이다. Cloud Run에는 Secret Manager의 `DATABASE_URL:latest`만 연결돼 있어 이 목록만으로 실제 DB 대상을 대조할 수 없었다. 비밀값 열람·로그 본문 열람·테스트 로그인·DB 쓰기 없이 확인을 마쳤다.
- 사용자가 공유한 호스트 정보는 Supabase shared pooler의 ap-northeast-2 리전, 5432 세션 모드 형식이다. 호스트는 프로젝트 고유 식별자가 아니므로 대상 프로젝트는 여전히 미확인이다. 다음 확인에는 비밀번호를 제외한 사용자명의 프로젝트 ref만 필요하다.
- 사용자가 제공한 project ref로 Supabase 프로젝트 조회를 시도했으나, 연결된 Supabase 도구와 현재 Chrome 세션 모두 접근 거부를 반환했다. 프로젝트의 활성 상태·요금제·백업 설정은 확인 불가하며 설정 변경·로그인 정보 입력 없이 종료했다.
- 로컬 `.env`의 `DATABASE_URL`은 비밀값을 출력하지 않고 파싱해 `tdtiabsgldkusyfyfysf` 테스트 프로젝트의 shared pooler임을 확인했다. 사용자가 Secret Manager 연결에서 전한 ref `owkklccwglcpfmmezcxj`와 다르다. `.env`와 Cloud Run Secret Manager 설정은 별개이며 이번 확인에서 `.env`는 수정하지 않았다.
- Supabase 초대 URL 오류를 확인했다. URL에는 비밀 토큰이 없어 전체 링크를 저장하지 않았다. 로컬 TCP 3000 listener와 HTTP 응답이 없고, `backend/web/WEB.md` 기준 저장소 웹 화면도 미구현이다. `otp_expired`는 초대 OTP 만료/무효 상태를 가리킨다. 초대가 Supabase 조직 협업 초대인지 Auth 사용자 초대인지, 실제 프로젝트의 Site URL/redirect allowlist 및 이메일 prefetch는 확인하지 않았다.
- Codex Supabase 도구의 조직/프로젝트 목록을 재조회했다. 현재 연결에는 `trjpvdafthdgpwwkiktw` 조직과 그 소속 프로젝트 3개만 보이고, 사용자가 확인한 `dcssmaguthdhdpbpbvoy` 조직과 `owkklccwglcpfmmezcxj` 프로젝트는 목록에 없으며 직접 조회도 permission denied다. Chrome 자동화 탭은 Supabase 로그인 화면이었다. 연결 OAuth 주체의 이메일은 도구에서 확인할 수 없어 실제로 다른 계정인지, 조직 초대 후 토큰 갱신이 안 된 것인지는 구분하지 못했다. 권한·프로젝트 설정은 변경하지 않았다.
- 사용자가 연 Codex 인앱 브라우저에서는 로그인된 상태로 `dcssmaguthdhdpbpbvoy` 조직의 `SojaFit` 프로젝트(`owkklccwglcpfmmezcxj`)를 직접 확인했다. 프로젝트 상태 Healthy, 조직/플랜 HJU5022 FREE, Overview의 Last backup은 No backups이며 Database > Backups는 Free 플랜에 프로젝트 백업이 포함되지 않는다고 표시했다. 배너에는 grace period 종료 및 사용량 한도 소진 시 요청 처리가 중단될 수 있다는 경고가 보였다. 로그·DB 데이터·비밀값은 열지 않았고 설정을 변경하지 않았다. Codex Supabase 도구 연결 범위는 별도 확인이 필요하다.
- Supabase 대상 프로젝트 SQL Editor에서 카탈로그 메타데이터만 조회했다. 실행 역할은 `postgres`였고, `public.users`, `public.auth_sessions`, `public.auth_login_attempts`는 모두 없었다. 따라서 이 세 테이블의 컬럼·제약·인덱스·RLS 정책·테이블 권한은 조회되지 않았다. `anon`, `authenticated`, `service_role`의 `public` 스키마 사용 권한은 true였지만, 이는 개별 테이블 권한을 뜻하지 않는다. 조회 쿼리는 저장하지 않았고 사용자·로그인·세션 행, 비밀값, 설정은 읽거나 변경하지 않았다. 이 결과만으로 Supabase Auth의 `auth.users` 또는 DB 전체에 앱 계정 테이블이 없다고 단정할 수 없다. 다음은 저장소의 실제 로그인 DB 테이블/스키마 이름과 배포 대상을 대조해야 한다.
- 후속 읽기 전용 메타데이터 조회로 `auth`, `public` 등 시스템 카탈로그 외 스키마의 같은 이름 표를 검색했다. 결과는 Supabase 관리 스키마의 `auth.users` 한 개뿐이었고, `public.users`, `public.auth_sessions`, `public.auth_login_attempts`는 여전히 찾지 못했다. 따라서 Supabase Auth 계정 표가 존재하는 것과 애플리케이션의 자체 로그인 저장소가 준비된 것은 별개다. 처음 실행은 SQL 편집기 기존 문장 중간에 새 쿼리가 삽입되어 문법 오류가 났으며, 편집기 전체를 교체한 뒤 같은 조회가 정상 실행됐다. 행 데이터와 설정은 읽거나 변경하지 않았다.
- Supabase Data API 설정을 읽기 전용으로 확인했다. Data API 활성, 노출 스키마 2개 중 1개, `public`의 표 4/4 및 함수 1/1 노출, 새 표 자동 노출 옵션 활성 상태였다. `public`의 코퍼스 표 4개(`source_documents`, `document_chunks`, `chunk_embeddings`, `chunk_embedding_bits`)는 `anon`·`authenticated`·`service_role` 모두에 실효 SELECT/INSERT/UPDATE/DELETE/TRUNCATE 권한이 있었다. 이 표들은 RLS가 켜져 있고 강제 옵션은 꺼져 있으며 정책은 각각 0개다. 역할 속성상 `anon`과 `authenticated`는 RLS 우회 불가, `service_role`과 `postgres`는 `BYPASSRLS`다. 따라서 ACL 권한만으로 anon/authenticated가 행을 읽거나 쓸 수 있다고 단정할 수 없고, 현재 정책 0개에서는 일반 역할 접근이 차단된다. 서비스가 어떤 DB 역할로 연결되는지는 비밀값을 읽지 않아 미확인이다.
- Data API가 노출한 함수는 `public.rls_auto_enable()`로 확인했다. 함수 정의는 읽기만 했고 실행하지 않았다. `SECURITY DEFINER`, 반환형 `event_trigger`, `pg_catalog` 고정 search_path이며, 활성 `ensure_rls` 이벤트 트리거(DDL command end)에 연결돼 있다. 정의상 public 신규 테이블에 RLS를 켜는 동작이고 정책을 추가하지는 않는다. Data API 설정의 새 표 자동 노출은 켜져 있어, 신규 표를 만들면 API 권한 부여와 RLS 활성화가 함께 적용될 수 있으나 접근 정책은 별도 설계가 필요하다. 대시보드 설정 변경은 저장하지 않았다. 조회 중 설정 선택 UI에만 잠시 미저장 0개 상태가 나타났고, 새 페이지에서 저장된 1/2·4/4·1/1 상태를 재확인했다. 실제 DB 행·함수 실행·비밀값은 접근하지 않았다.
- 로컬 `.env` 값 자체는 출력하지 않고 연결 대상과 키 이름만 확인했다. `DATABASE_URL`은 `tdtiabsgldkusyfyfysf` 프로젝트를 가리키며 새로 확인한 `owkklccwglcpfmmezcxj`와 다르다. `DATABASE_URL`은 인증과 RAG 코드 모두가 사용하므로 바꾸면 두 경로가 함께 새 DB로 이동한다. 현재 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`는 `.env`에 있지만 backend/scripts에서 참조가 없고, `SUPABASE_SERVICE_ROLE_KEY`도 현재 코드에서 사용하지 않는다. `AUTH_SECRET`과 `AUTH_ORIGIN`은 DB 접속값이 아니므로 DB 교체만으로 자동 교체 대상이 되지 않는다. `.env`, Cloud Run Secret Manager, DB 스키마/권한은 변경하지 않았다.
- 사용자가 Cloud Run Secret Manager의 `DATABASE_URL`에서 사용자 이름이 `postgres.owkklccwglcpfmmezcxj`임을 확인해 알려줬다. 비밀번호·전체 접속 문자열은 받지 않았다. 공유 풀러 형식상 DB 역할 `postgres`를 가리키며, 앞서 대상 DB의 `pg_roles` 메타데이터에서 `postgres.rolbypassrls=true`를 확인했다. 따라서 Cloud Run 요청은 RLS 정책으로 제한되지 않는 연결 역할을 사용한다는 평가를 추가했다. 이 연결을 별도 제한 역할로 바꾸는 작업은 아직 하지 않았다.
- Cloud Run 콘솔의 현재 서비스 revision을 재확인했다. `sojafit-api-00008-2h5`가 현재 트래픽 100%를 받고 서비스는 정상 상태였다. revision 환경변수에서 `DATABASE_URL`이 Secret Manager의 `DATABASE_URL:latest`를 참조한다. 사용자가 해당 secret에서 사용자 이름 `postgres.owkklccwglcpfmmezcxj`를 확인했다고 알려줬으므로, Cloud Run의 대상 project ref는 `owkklccwglcpfmmezcxj`라는 근거가 충분하다. 비밀값은 열지 않았다. `backend/main.py`의 `/health`는 정적 `{"status":"ok"}`만 반환하므로 서비스 정상 표시가 DB 접속 성공을 증명하지는 않는다.
- 로컬 `.env` 키/사용처를 비밀값 없이 대조했다. `DATABASE_URL`과 `SUPABASE_URL`은 모두 이전 `tdtiabsgldkusyfyfysf` project ref를 가리킨다. 로컬 설정은 `DEMO_MODE=0`, `RAG_VECTOR_TYPE=vector`, `AUTH_ORIGIN`은 Cloud Run 주소이며 `VOYAGE_API_KEY`는 비어 있다. `LLM_PROVIDER`·`LLM_MODEL`은 비어 있어 코드 기본값(openrouter 및 기본 모델)을 쓴다. `LANGFUSE_HOST`는 코드의 호환 처리로 `LANGFUSE_BASE_URL`로 옮겨진다. `SUPABASE_URL`·`SUPABASE_PUBLISHABLE_KEY`는 현재 backend/scripts에서 사용처가 없고 `.env.example`에는 publishable 대신 `SUPABASE_SERVICE_ROLE_KEY` 항목이 있지만 코드 사용처는 확인되지 않았다. 프로젝트의 DB·`.env`·Cloud Run 설정은 변경하지 않았다.
- 대상 Supabase 프로젝트의 Data API Overview에서 API URL `https://owkklccwglcpfmmezcxj.supabase.co/rest/v1/`를 읽기 전용으로 확인했다. 따라서 `.env`의 `SUPABASE_URL`에 넣을 프로젝트 기본 URL은 `https://owkklccwglcpfmmezcxj.supabase.co`이다(`/rest/v1/` 제외). 앞서 로컬 `.env`에서 확인한 값은 이전 `tdtiabsgldkusyfyfysf` 프로젝트였으며 파일은 변경하지 않았다.
- 새 Supabase 프로젝트의 Settings > API Keys를 읽기 전용으로 확인했다. 새 `sb_publishable_...` 기본 키 1개, 새 `sb_secret_...` 키 2개, 기존 JWT 기반 `service_role` 키가 존재했다. publishable 값은 대시보드에서 표시되지만 저장소의 키 관리 규칙에 따라 기록·채팅에 복사하지 않았다. `service_role` 값은 마스킹 상태로 두었고 Reveal/Copy를 누르지 않았다. 현재 backend/scripts 및 Cloud Run revision 설정에서 `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SERVICE_ROLE_KEY` 사용처가 없어 `.env`에 새 값을 입력하거나 Cloud Run Secret을 추가하지 않았다. Supabase는 기존 anon/service_role 키를 publishable/secret 키로 교체하는 중이며, secret 키는 RLS 우회 가능한 서버 전용 비밀값이다. 키 회전·비활성화는 하지 않았다.
- 사용자가 `.env`를 갱신했다고 요청해 비밀값을 출력하지 않고 형식만 확인했다. `SUPABASE_URL`과 `DATABASE_URL`은 모두 새 `owkklccwglcpfmmezcxj` 프로젝트를 가리키며, `DATABASE_URL`의 사용자명은 `postgres.owkklccwglcpfmmezcxj`다. `SUPABASE_PUBLISHABLE_KEY`는 비어 있지 않고 `sb_publishable_` 접두 형식이다. `SUPABASE_SERVICE_ROLE_KEY`는 비어 있지 않지만 값은 legacy JWT `service_role`(`eyJ...`)이 아니라 새 API secret(`sb_secret_...`) 형식이다. 이 차이는 키 자체를 검증한 것은 아니며 값은 읽거나 기록하지 않았다. 두 변수 모두 현재 backend/scripts에 사용처가 없다. 로컬 `.env`가 이제 운영 Supabase DB와 RLS 우회 가능한 `postgres` 역할을 가리키므로, 합성계정 생성·마이그레이션·적재 스크립트는 실행하지 않았다. 파일 수정은 하지 않았다.
- 사용자가 새 `.env` 기준 검증을 요청해 접속 문자열은 출력하지 않고 로컬 설정으로 Supabase에 연결했다. 네트워크 허용 실행에서 `SET TRANSACTION READ ONLY` 후 `current_database=postgres`, `current_user=postgres`, read-only=on, `rolbypassrls=true`, `vector` 확장 존재, `public.users/auth_sessions/auth_login_attempts` 없음이 확인됐다. RAG 메타데이터는 `public.chunk_embeddings.embedding`가 `halfvec`인데 `.env`는 `RAG_VECTOR_TYPE=vector`였다. 저장소의 기존 `ingest.py`는 이 불일치를 거부하므로 `.env`의 해당 한 줄만 `halfvec`으로 바꾸고 `backend.rag.storage.vector_type()` 자기검사에서 halfvec 인식 통과를 확인했다. 인증 통합 테스트, RAG 검색/적재, 마이그레이션은 실행하지 않았고 운영 DB에는 쓰지 않았다. 새 `.env`는 운영 DB의 `postgres` 역할을 가리키므로 테스트 전용 DB를 분리할 필요가 남아 있다.
- 사용자가 새 `.env` 기준 로그인 API·RAG·운영 쓰기 확인을 요청했다. Cloud Run `POST /api/auth/login`에는 가짜 invalid 이메일/빈 비밀번호만 보내 422 유효성 응답을 확인했다. 이 요청은 DB에 접근하지 않았다. 실제 로그인 호출은 자체 인증 표 3개가 없음을 이미 확인했으므로 보내지 않았다.
- 새 `.env`의 운영 DB로 BM25 `SS34 diode` 검색을 1회 실행했다. Voyage/OpenRouter를 호출하지 않았고 DB에는 SELECT만 했다. 결과 3건, 페이지 번호 [3,3,3], 약 6.969초였다. 내용 본문은 출력하지 않았다. `.env`에 `VOYAGE_API_KEY`가 비어 있어 dense/hybrid 임베딩·리랭크 경로는 확인하지 않았다.
- `postgres` 역할의 카탈로그 권한을 읽기 전용으로 확인했고 RAG ingest가 사용하는 `source_documents`, `document_chunks`, `chunk_embeddings`, `chunk_embedding_bits` 모두 INSERT/UPDATE/DELETE 권한이 true였다. `ingest.py`는 dry-run 옵션 없이 실제 INSERT를 수행한다. 운영 백업·복구와 적재 범위 확인 전이라 적재나 임시 쓰기/롤백 시험은 하지 않았다. 비밀값·사용자 데이터는 출력하지 않았다.
- 사용자가 이해 확인 후 로그인 작업을 이어가도록 요청했다. 별도 로컬 인증 DB 상태를 확인했으나 `127.0.0.1:55434`는 닫혀 있고 `TEST_AUTH_DATABASE_URL`은 설정되지 않았다. Docker CLI는 Docker Desktop Linux 엔진 named pipe 접근 거부를 반환했으며, 운영 DB 대신 쓸 로컬 컨테이너를 사용할 수 없었다.
- DB 비사용 로그인 테스트 subset을 `.venv` Python으로 실행: `5 passed, 6 skipped in 2.74s`; 생략은 격리 인증 DB 요구 조건이다. 전체 `tests/api/test_auth.py`는 TestClient 기반 두 번째 사례에서 멈췄고, faulthandler는 Windows asyncio `_fallback_socketpair`의 `accept` 대기를 보여줬다. 60초 뒤 실행을 중단했으므로 전체 테스트 결과는 미확인이다. 코드 변경은 하지 않았고 운영 DB에는 쓰지 않았다. 계속하려면 Docker/로컬 PostgreSQL을 사용할 수 있게 하거나 별도 격리 `TEST_AUTH_DATABASE_URL`을 준비해야 한다. 생산 Supabase URL을 테스트 URL로 사용하지 않는다.
- 이어서 확인: Docker Desktop 앱을 열어 보려 했지만 앱이 확인 가능한 창을 제공하지 않아 Docker 엔진을 시작할 수 없었다. 재확인 결과 `127.0.0.1:55434`는 닫혀 있고 Docker named pipe는 계속 `permission denied`였다. DB 미사용 로그인 테스트를 다시 실행해 `5 passed, 6 skipped`를 확인했다. 6건은 격리 인증 DB가 없어 건너뛰었다. 코드/DB 설정은 변경하지 않았다.
- 다음 단계: Docker Desktop을 직접 실행해 엔진이 준비된 뒤 같은 로그인 DB 테스트를 재개하거나, 별도 격리 테스트 DB 주소를 준비한다. 운영 Supabase URL로는 DB 통합 테스트를 실행하지 않는다.
- 후속 읽기 전용 확인: `sojafit-auth-test`는 정상 상태이며 인증 표 3개는 모두 0행이고 RLS가 켜져 있다. `anon`·`authenticated`의 각 표 SELECT 실효 권한은 없고 권한 제한 마이그레이션 이력이 있다. security advisor는 세 표에 정책이 없다는 INFO를 보고했다. 로컬 `DATABASE_URL`은 테스트 프로젝트가 아니고 `TEST_AUTH_DATABASE_URL`은 비어 있어 로그인 DB 테스트는 실행하지 않았다. 테스트 안내 및 계획 맨 앞에 확인 시점과 이전 기록을 구분했다. HTTP Data API 접근과 실제 로그인은 미검증이다.
- Docker Desktop 실행 후 로컬 `sojafit-auth-test-local` 컨테이너에 새 빈 DB `auth_check_83a26b9e75a9`를 만들고 인증 SQL `003`, `005`, `006`만 적용했다. 테스트 프로세스에만 해당 로컬 DB 연결을 설정하여 `.venv/Scripts/uv.exe run --no-sync --offline pytest -q -rs tests/api/test_auth.py -p no:cacheprovider` 실행 결과 `34 passed in 19.50s`. 합성 계정·세션 등 테스트 데이터와 새 DB는 로컬 컨테이너에 남아 있다. 기존 DB, 운영 Supabase, Cloud Run은 변경하지 않았다. Supabase 환경 및 배포 로그인은 별도 미검증이다.
- 서비스 DB 재확인: Supabase 연결 도구는 팀 프로젝트 조회를 권한 부족으로 거부했다. 로컬 `.env` 연결의 프로젝트 ref를 확인하고 읽기 전용 트랜잭션으로 접속해 `public.users`, `auth_sessions`, `auth_login_attempts`가 없으며 접속 역할은 `BYPASSRLS`임을 확인했다. 클라이언트 연결의 TLS는 켜져 있었으나 URL에 `sslmode`가 없고 현재 libpq 기본값은 `prefer`, 별도 `sslrootcert`는 설정되지 않았다. 서버의 `pg_stat_ssl`은 해당 백엔드 연결에 대해 false를 반환했으며 풀러 경유 구간의 의미는 제공자 설정 확인이 필요하다. 이 결과는 Cloud Run의 실제 연결 설정을 확인한 것이 아니다. DB 쓰기와 설정 변경은 하지 않았다.
- 서비스 DB `verify-full` 준비: 현재 URL에 SSL 모드·CA 경로가 없고 프로세스의 libpq 기본값은 `prefer`다. 설치된 certifi 공개 CA 묶음으로 서비스 풀러에 `verify-full` 연결을 시도했으나 인증서 검증 실패로 연결되지 않았다. 다른 CA 거부 시험은 실행하지 않았다. 개인 테스트 프로젝트의 CA는 서비스 프로젝트용으로 확인되지 않았다. 서비스 프로젝트 CA를 확인하려 브라우저의 기존 Supabase API 키 페이지에 접근하려 했으나 자동 보안 검토가 민감한 키 노출 위험을 이유로 거부했다. `.env`, DB 및 Cloud Run은 변경하지 않았다. 서비스 프로젝트의 신뢰할 수 있는 공식 공개 CA를 확보한 뒤 읽기 전용 검증을 재개한다.
- 사용자가 서비스 프로젝트에서 내려받은 공개 CA를 확인했다. CA 인증서 1개, 만료 2031-04-26이며 개인키는 없었다. 원본의 한글 디렉터리 경로는 libpq가 인식하지 못해 최초 연결이 실패했다. 같은 인증서를 `.venv` 아래 영문 임시 경로에 복사하자 `sslmode=verify-full` 읽기 전용 SELECT가 성공했고, certifi의 CA 묶음으로는 인증서 검증이 거부됐다. 시험용 복사본은 자동 정리했다. `.env`와 Cloud Run 설정은 변경하지 않았으므로 일회성 검증이며, 상시 적용 시 영문 경로와 배포별 CA 제공을 별도로 준비해야 한다.
- 사용자 요청에 따라 공개 CA를 저장소 밖 `E:/teamproject3/certs/sojafit-service-ca.crt`로 이동하고 원본과 복사본의 SHA-256 일치 후 기존 파일을 제거했다. 새 경로의 CA로 `verify-full` 읽기 전용 SELECT 성공을 먼저 확인했다. 로컬 `.env`의 `DATABASE_URL`에 `sslmode=verify-full`과 새 `sslrootcert` 경로만 추가한 뒤 실제 `backend.auth.connection()`으로 TLS·검증 모드·읽기 전용 SELECT를 확인했다. 실패 시 변경 전 `.env`로 복원하도록 처리했으며 검증은 성공했다. Cloud Run, 운영 DB 데이터 및 검색 실행은 변경하거나 검증하지 않았다. 다른 PC와 배포 환경에는 해당 경로가 없으므로 별도로 CA 제공과 설정이 필요하다.
- 사용자가 GCP Secret Manager에 `sojafit-service-db-ca`를 생성한 뒤 콘솔에서 버전 1이 사용 설정된 것을 확인했다. 보안 비밀 값은 열지 않았으므로 로컬 인증서와 등록 내용의 일치는 별도로 확인하지 않았다. Cloud Run 파일 마운트, 서비스 계정 접근 권한, DB TLS 설정과 새 리비전 배포는 수행하지 않았다.
- Cloud Run `sojafit-api` 콘솔에서 기본 컴퓨팅 서비스 계정을 사용하고, 이 계정에 새 CA 보안 비밀의 접근자 권한이 프로젝트에서 상속됨을 확인했다. 콘솔의 미배포 변경안에 CA 버전 1을 `/etc/sojafit-certs/service-ca.crt`로 마운트하고 `PGSSLMODE=verify-full`, `PGSSLROOTCERT`를 해당 파일 경로로 추가했다. 변경사항 검토에서 기존 환경변수·보안 비밀 참조가 유지됨을 확인하고 즉시 트래픽 제공 체크를 해제했다. 배포 버튼은 누르지 않았고 새 리비전은 생성하지 않았다. Cloud Run `DATABASE_URL`의 SSL 파라미터가 환경변수를 덮어쓰는지, 등록된 CA 파일이 일치하는지 및 0% 트래픽 검증 경로는 미확인이다.
- 후속 진행: Cloud Run `DATABASE_URL` 비밀값은 출력하지 않고 대상 프로젝트 일치 및 `sslmode`·`sslrootcert` URL 파라미터 부재만 확인했다. 등록 CA 버전 1과 로컬에서 검증한 CA의 인증서 SHA-256 지문은 일치했다. 변경안을 배포해 `sojafit-api-00009-t6p` 리비전을 만들고 태그 `tls-check-00009`를 연결했다. 콘솔에서 새 리비전 0%, 기존 `sojafit-api-00008-2h5` 100%를 확인했다. 태그 주소의 GET `/health`와 `/openapi.json`은 각각 200이었으나 `/health`는 DB 연결을 검사하지 않는다. 배포 API 목록에 검색 경로가 없고 서비스 DB에 자체 인증 표가 없으므로 새 리비전의 실제 DB TLS·검색·로그인 동작은 미검증이다. 태그 주소는 별도 직접 접근 경로로 남아 있다. 운영 트래픽 전환은 하지 않았다.
- 후속 연결 검증: Cloud Run에 `sojafit-db-tls-check` 작업을 생성하고 1회 실행했다(서울, 동일 이미지 digest·기본 서비스 계정·`DATABASE_URL:latest`·CA 버전 1 마운트 및 동일 PG SSL 환경변수). 제한 1분, 재시도 0회. 실행 `sojafit-db-tls-check-7vmc8`은 종료 코드 0과 `VERIFY_FULL_AND_CORPUS_READ_OK` 로그를 남겼다. psycopg에서 실효 `verify-full`과 TLS, 읽기 전용 SELECT 1, `public.document_chunks` SELECT를 확인했으며 결과 데이터·접속 문자열은 출력하지 않았다. 선택된 서비스 리비전의 VPC는 없음으로 표시됐다. 이 작업은 별도 Cloud Run 작업이므로 서비스 리비전 내부의 실제 요청·검색 전체 또는 배포 로그인 검증을 뜻하지 않는다. 기존 서비스 트래픽은 종전 리비전 100%, 새 리비전 0%로 유지했다. 작업과 시험용 태그는 후속 검토를 위해 남겼으며 실행 비용은 미확인이다.
- 서비스 DB 백업·스키마 읽기 전용 점검: 팀 Supabase 콘솔은 Free 플랜에 프로젝트 백업이 포함되지 않는다고 표시했다. 별도 수동 백업·복구 담당자와 복구 시험은 미확인이다. 화면 상단에는 사용량 유예 기간 종료 후 한도 소진 시 프로젝트 요청을 처리할 수 없다는 경고가 표시됐으며 현재 남은 사용량은 확인하지 않았다. DB 설정의 Enforce SSL은 꺼져 있었다. 설정·복원은 실행하지 않았다.
- 같은 서비스 DB에 `verify-full` 읽기 전용 연결 후 `public`의 `users`, `users_id_seq`, `auth_sessions`, `auth_login_attempts` 이름과 충돌하는 관계 객체가 없음을 확인했다. `ensure_rls` 등 이벤트 트리거가 활성이고, 현재 DB 역할이 `public`에 만드는 새 표·시퀀스에는 `anon`·`authenticated`에 대한 기본 권한이 있다(표에 TRUNCATE 등 포함). 그러므로 인증 표 신설 시 RLS뿐 아니라 공개 역할의 표·시퀀스 권한을 함께 제한하는 설계와 검증이 필요하다. `supabase_migrations.schema_migrations`는 확인되지 않았다. 운영 DB 스키마나 데이터를 변경하지 않았다.

## 2026-11-04 로그인 마무리 계획의 로컬 검증 상태 정리
- `docs/specs/login-completion-plan.md`에서 초기 DB 미사용 테스트 결과(`19 passed, 15 skipped`)와 후속 분리 로컬 PostgreSQL 테스트 결과(`34 passed`)를 서로 다른 시점으로 구분했다.
- 로컬 격리 DB 범위는 검증된 것으로 정리하고, 외부 DB 및 배포 로그인은 미검증 상태로 유지했다. Supabase 사용량·백업·대시보드 상태, 코드, DB, Cloud Run은 이번 정리에서 변경하거나 확인하지 않았다.
- 이후 사용자는 로그인 뒤 질문까지 시연하고, 질문 기록은 저장하지 않는 범위를 선택했다. 같은 출처의 최소 화면, 합성 평가 계정의 평가 종료 후 삭제, 공통 읽기 전용 코퍼스를 포함한 검토용 설계안과 수용 기준 초안을 같은 작업서에 추가했다.
- 이 안은 사용자별로 저장된 대화·기억을 제공하지 않는다. 질문 API·화면은 아직 없고, 로그/추적 제공자의 보관 여부도 확인되지 않아 실사용 개인정보는 시연에 넣지 않는 제안이다. 루트 `SPEC.md`와 아키텍처 ADR은 STH에서 직접 고치지 않고 조장 승인을 받아 반영해야 한다.
- 사용자가 검토안에 동의한 뒤, 팀장 승인/SPEC 반영 → 정확한 합성 계정 삭제 절차 → 세션 보호 질문 API → 같은 출처 화면 → 회귀 확인 순서의 구현 계획을 작성했다.
- 문서 대조만 했으며 테스트·코드·DB·Cloud Run은 변경하거나 확인하지 않았다. 구현은 팀장이 보관 종료일·외부 로그 범위와 주요 SPEC/ADR을 승인할 때까지 보류한다.

## 2026-11-04 로그인 후 질문 시연 로컬 구현
- 사용자 승인 범위(로그인 → 질문 1회 → 답변 → 로그아웃, 질문 기록 미저장)에 따라 `backend/main.py`에 `/login` 화면과 세션 보호 `/api/ask`를 연결했다. 질문은 1~2000자, 알 수 없는 ID 필드는 거부하며, 서버 세션 사용자 ID만 그래프에 전달한다. 답변만 반환하고 Origin도 검증한다.
- `backend/web/templates/login.html`을 추가했다. 같은 출처 기존 인증 API를 사용하며 localStorage/sessionStorage는 쓰지 않고, 답은 `textContent`로 표시한다. 로그아웃 성공 시 입력·답을 지운다.
- `backend/auth.py`에 정확한 사용자 ID 재입력을 요구하는 운영자 삭제 CLI를 추가했다. 비활성 일반 사용자 중 `@example.test` 합성 계정만 허용하며 관리자·활성·실제 도메인 계정은 거부한다. 사용자 삭제에 연결 세션 cascade와 이메일 해시 로그인 실패 행 삭제를 묶었다. 격리 DB 통합 테스트도 추가했지만 이번에는 DB가 준비되지 않아 실행하지 않았다.
- 화면/API 안내 문서와 신규 파일 트리 줄, 검토 계획 체크 상태를 갱신했다. 루트 `SPEC.md`와 ADR은 주요 문서이므로 STH에서 수정하지 않았다. PR/병합 전에 팀장 승인과 SPEC/ADR 반영이 필요하다.
- 검증: `.venv/Scripts/python.exe -m pytest -q tests/api/test_question.py tests/api/test_auth.py::test_account_deletion_cli_requires_exact_id_confirmation -p no:cacheprovider` 결과 `8 passed`; 이후 삭제 CLI 관리자 역할 회귀를 추가했다. 마지막 API 전체 `.venv/Scripts/python.exe -m pytest -q tests/api -p no:cacheprovider` 결과 `30 passed, 16 skipped`; `git diff --check`도 통과했다. 전용 `TEST_AUTH_DATABASE_URL`은 비워 두어 DB 통합 시험을 건너뛰었고 서비스 DB에는 접속하지 않았다.
- 확인하지 못한 범위: 브라우저에서 실제 로그인·질문 흐름, 로컬/서비스 DB에 대한 사용자별 질문 실측, Cloud Run 배포, 프록시·모델·Langfuse 등 외부 로그 보관. Docker named pipe 권한 문제로 격리 컨테이너 상태를 사용할 수 없었다. 실제 개인정보 대신 합성 입력만 사용해야 한다.

## 2026-11-05 팀장 체크리스트 대조 및 공유 준비
- 사용자가 제공한 `E:/teamproject3/자료/작업-체크리스트.md`(2026-11-04 11:32 수정)를 로그인 작업 기록, 로컬 코드·테스트 및 `db/DB.md`와 다시 대조했다. 체크리스트의 질문 API 부재 설명은 로컬 코드에는 오래된 상태지만, Cloud Run 배포본에서 질문을 실행했다는 뜻은 아니다.
- 체크리스트 6-1의 질문 API는 로컬 구현됨(`/api/ask`, `/login`)으로 구분한다. 화면 방식 ADR·루트 SPEC, 오류 응답의 전체 계약은 미완료다. 6-2의 Cloud Run 로그인, 별도 평가 계정, 실제 로그인→질문→로그아웃은 미검증이며 G1 완료로 볼 수 없다.
- 체크리스트의 5-4 로그인 사용자 ID로 thread·Store 분리는 미완료다. 이번 질문 시연은 기록을 저장하지 않으며, 미래의 회로·대화·기억·견적 소유권 검증과 구분한다.
- 안전상 결정이 필요한 불일치: 체크리스트는 운영 DB에 007 적용을 적었으나 `db/DB.md`는 `007_demo_accounts.sql`을 로컬 Compose 데모 계정 시드로 설명한다. 팀장·DB 담당자가 서비스용 스키마/시드 경계를 확인하기 전에는 적용하지 않는다.
- 다음 순서: ① 이메일 보호 수준·보관/삭제·로그 보관 정책 결정, ② 운영 DB 마이그레이션 및 공개 권한/RLS/백엔드 역할 설계 승인, ③ 격리 DB 통합 테스트와 합성 계정 삭제 시험, ④ 팀장이 SPEC/ADR·체크리스트 갱신, ⑤ Cloud Run Origin·인증 스키마·평가 계정을 확인하고 합성 입력으로 전체 시나리오 검증.
- 사용자 내일 설명용 핵심: 인증 API와 로컬 질문 시연은 준비됐지만 배포 로그인은 끝나지 않았다. 이전 API 전체 테스트 기록은 30 passed, 16 skipped이며 격리 DB·브라우저·Cloud Run 흐름은 이 결과에 포함되지 않는다.
- 확인 방법: 체크리스트 메타데이터와 5-4·6-1·6-2·G1 항목, `backend/main.py`, `backend/auth.py`, 테스트, `db/DB.md`, 작업기록을 읽기 전용 대조했다. 새 테스트·DB 접속·Cloud Run 접근·코드 변경은 하지 않았다.

## 2026-11-05 AGENTS.md 재검토 보완
- `backend/main.py`의 `/api/ask`에서 Origin 검증을 FastAPI 인증 의존성 앞에 두었다. 이전에는 `auth.current_user`가 세션의 `last_seen_at`을 갱신한 뒤 Origin을 거부할 수 있었다. 이제 다른 출처 또는 Origin 누락은 인증 세션 조회·갱신과 그래프 실행 전에 거부한다.
- 회귀 테스트에서 외부 Origin 요청 시 인증 의존성 및 그래프가 모두 실행되지 않는지 확인하도록 했고, 비로그인 `401` 검증은 허용 Origin을 포함해 기존 의미를 유지했다. `/api/ask` 데코레이터 앞에 있던 잘못된 문자를 제거해 모듈 import 오류도 바로잡았다.
- `SOJAFIT.md`의 웹/템플릿 설명과 `docs/specs/login-completion-plan.md`의 현재 로컬 화면/API 상태를 구현에 맞게 갱신했다. 배포·브라우저·격리 DB 검증 항목은 미완료로 남겼다.
- 검증: `uv run --no-sync pytest -q tests/api -p no:cacheprovider` (`.venv/Scripts/uv.exe` 사용) 결과 `30 passed, 16 skipped`. 격리 인증 DB가 없어 DB 통합 테스트 16건은 skip이다. 샌드박스는 Windows TestClient socketpair 및 uv 잠금/캐시 쓰기를 막아 해당 표준 명령은 로컬 권한으로 실행했다. `git diff --check` 통과(작업기록의 LF→CRLF 경고만 표시).
- 전체 테스트 추가 확인: `uv run --no-sync pytest -q -p no:cacheprovider`는 `277 passed, 27 skipped, 1 failed`였다. 유일한 실패는 `tests/evals/test_frozen_evals.py::test_frozen_files_unchanged`로, Windows 체크아웃의 CRLF 바이트가 FROZEN의 LF SHA-256과 달랐다. `HEAD:evals/dataset_v2.jsonl`의 해시는 기대값과 일치하고, 작업 파일을 LF 정규화한 해시도 기대값과 일치했다. 평가 파일은 수정하지 않았다. 해당 한 검사를 제외한 나머지는 `277 passed, 27 skipped, 1 deselected`였다.
- 확인하지 않은 것: 브라우저·Cloud Run 요청에서의 검증, 서비스 DB 세션 만료 실측, 로그/추적 보관 정책, DB 통합 테스트.

## 2026-11-05 로그인 범위에서 질문 API 제거
- 사용자 결정에 따라 로그인 기능의 범위를 로그인·세션 확인·로그아웃으로 축소했다. 직전 커밋 `58c6bf6`은 유지하고, 후속 커밋에서 `/api/ask`와 그래프 연결을 제거한다.
- 로그인 화면에서 질문 입력·답 영역과 요청 코드를 제거하고, 로그인된 세션 상태와 로그아웃만 표시한다. `tests/api/test_question.py`를 제거하고, `tests/api/test_auth.py`에 `/api/ask` 미노출(404)과 질문 폼 미표시 회귀 검사를 추가했다.
- `SOJAFIT.md`, backend/web 문서, API 테스트 안내와 로그인 작업계획을 현재 범위에 맞게 갱신했다. 작업계획에는 이전 질문 시연 결정을 과거 검토 이력으로 표시했다.
- TDD 회귀 확인: 구현 전 두 새 검사가 기존 동작에서 실패했다(질문 UI 표시, `/api/ask` 200). 제거 후 두 검사 `2 passed`. 전체 API 테스트 `25 passed, 16 skipped`; 격리 DB 통합 테스트 16건은 실행하지 않았다.
- 저장소 테스트는 동결셋 원시 해시 검사를 제외하고 `272 passed, 27 skipped, 1 deselected`. Windows 체크아웃의 CRLF와 FROZEN LF 해시 불일치는 이전 점검에서 확인했으며 동결 평가 파일은 수정하지 않았다.
- 미확인: 실제 브라우저 로그인·로그아웃, Cloud Run, 서비스 DB. 검색·LLM은 이번 범위에서 호출하지 않는다.

## 2026-11-05 팀 DB 인증 테이블 생성
- 한 일: 팀 DB 테이블 생성에 대한 팀장 허락과 사용자 요청을 확인했다. 사용자는 백업·복구 결정은 추후로 미뤘다. Supabase 마이그레이션 `20261105014613`으로 인증 테이블 세 개와 사용자 ID 시퀀스를 생성하고 세 테이블에 RLS를 켰으며 PUBLIC·anon·authenticated의 테이블 및 시퀀스 권한을 회수했다. RAG 객체는 변경 대상으로 지정하지 않았다.
- 확인: 적용 전 관계 이름 충돌 0건. 적용 후 카탈로그 읽기 전용 조회로 세 테이블의 컬럼, RLS 활성화, anon·authenticated의 SELECT/INSERT/UPDATE/DELETE/TRUNCATE와 시퀀스 USAGE/SELECT 권한 없음, postgres 권한 보유 및 마이그레이션 이력을 확인했다.
- 후속 확인: `users`는 0건이고 기본키·외래키·로그인 ID UNIQUE·역할 CHECK 제약이 조회됐다. 현재 Cloud Run 기본 주소의 GET `/login`은 404였다. `git diff --check -- docs/worklog/sth.md`는 오류 없이 통과했다(LF→CRLF 경고).
- 확인 못 한 것: 팀 DB 백업·복구 경로, HTTP Data API를 통한 접근 검증, 서비스 계정 생성과 Cloud Run 로그인 흐름. 기존 검색 테이블 권한은 이번에 변경하거나 실제 동작을 시험하지 않았다.
- 다음 할 일: 평가 계정의 안전한 입력·전달 방법을 정하고 생성한 뒤 배포 로그인/세션/로그아웃을 확인한다. 기존 사용자 요청에 따라 질문 API는 범위에서 제외한다.
- 추가 확인: 팀 DB의 users는 여전히 0건이다. 로컬 .env의 대상 프로젝트 일치, verify-full·CA 경로 설정과 CA 파일 존재, AUTH_SECRET 길이 및 DEMO_MODE=0을 비밀값 출력 없이 확인했다. Cloud Run 기본 주소의 OpenAPI에는 로그인·me·로그아웃 API가 있으나 /login 화면은 이전 확인에서 404였다. 계정 생성과 API 로그인 요청은 실행하지 않았다.

## 2026-11-05 Google 관리자 로그인 로컬 구현 진행
- `db/010_google_auth.sql`에 OAuth 상태·승인 대기·Google 식별자 연결 표와 RLS·공개 역할 권한 제한을 추가했다. 기존 사용자 표와 비밀번호 로그인은 유지한다. 팀 DB에는 이 SQL을 적용하지 않았다.
- `backend/auth.py`, `backend/main.py`, 로그인 화면에 인증 코드·PKCE·nonce 검증, Google ID 토큰 서명 및 클레임 검증, 관리자 수동 승인·연결 철회와 세션 폐기, 관리자 비활성화 명령을 추가했다. 설정하지 않으면 Google 로그인은 꺼져 있다. `Authlib`, `joserfc`를 uv 직접 의존성으로 추가했다.
- Docker의 별도 임시 PostgreSQL에 기존 인증 SQL을 적용하고 가짜 계정·Google 응답으로 검증했다. 처음 전체 API 검사에서 기존 테스트의 예외 메시지 대소문자 비교 1건이 실패하여 비교를 수정했다. 최종 `uv run --no-sync --offline pytest -q tests/api tests/repo/test_repo_layout.py -p no:cacheprovider`는 56 passed였다. 사용자의 기존 변경 `tests/graph/test_graph_mcp_stdio.py`는 건드리지 않았다.
- Google 토큰 교환은 실제 외부 호출 없이 합성 응답으로 확인했다. 실제 Google 계정 로그인, 여러 인스턴스의 동시 회수 경합, 로컬 브라우저 시각 확인, 팀 DB 이관 및 Cloud Run은 확인하지 않았다. 유휴 중 만료 데이터의 정기 삭제와 Cloud Run 요청 로그의 콜백 쿼리 보호, 비밀키 주입, 팀장 SPEC·계약 검토 및 DB 백업·복구 절차가 운영 적용 전 남아 있다. 만료 행은 관련 요청이 들어올 때 정리한다.
- `uv sync` 기본 그룹 실행으로 기존 적재 그룹 패키지가 빠진 것을 확인해 `uv sync --group ingest`로 복원했다. 테스트 DB는 기존 볼륨을 건드리지 않는 전용 임시 컨테이너를 사용했고, 시험 후 해당 컨테이너와 임시 접속 정보를 삭제했다. 변경 규모가 팀 PR 기준 400줄 안팎을 넘으므로 PR 작성 시 이유와 분리 검토 방식을 명시해야 한다.

## 2026-11-05 실제 Google 계정 로컬 시험
- 사용자 확인 후 Google 인증 플랫폼 테스트 사용자 목록에 사용자 본인 계정을 추가했다. 테스트 사용자 등록은 앱의 관리자 권한 부여와 별개다.
- 임시 PostgreSQL과 `localhost:8000`에서 사용자가 Google 계정으로 로그인했다. 최초 승인 대기 시 요청 1건·연결 0건·세션 0건을 확인했다. 임시 DB의 사전 생성 관리자에게 요청을 승인하고 다시 로그인했을 때 브라우저에 로그인 상태와 로그아웃 버튼이 표시됐다. 로그아웃 뒤 로그인 화면과 DB 세션 0건을 확인했다.
- 요청 액세스 로그를 끄고 테스트했으며, 시험 종료 후 임시 서버·DB와 임시 OAuth 설정 파일을 정리했다. 실제 Google 이메일, 식별자, 인증 코드와 비밀값은 작업 기록에 적지 않았다. Google 테스트 사용자 등록은 유지됐다.
- 이번 결과는 실제 Google 계정 1개의 로컬 시험이다. Cloud Run의 Google 로그인, 운영 DB 마이그레이션, 운영 로그의 콜백 쿼리 보호, 정기 삭제와 계약 검토는 별도 확인이 필요하다.

## 2026-11-05 팀 DB Google 인증 스키마 적용
- 사용자가 세 테이블 추가의 범위와 되돌릴 때 연결 정보가 삭제될 수 있음을 확인한 뒤 진행했다. 팀 Supabase 프로젝트에 `db/010_google_auth.sql`을 마이그레이션 `20261105070655` (`create_google_admin_auth_tables`)로 적용했다. 기존 사용자·검색 데이터의 변경은 요청하지 않았고 새 테이블 세 개의 행 수는 모두 0건이었다.
- 적용 전 `users.id`가 bigint 기본키이고 새 이름에 충돌이 없음을 확인했다. 적용 후 세 표의 RLS, PUBLIC 권한 없음, anon·authenticated의 SELECT/INSERT/UPDATE/DELETE 권한 없음, postgres의 네 권한, Google 식별자 기본키·관리자 ID UNIQUE·외래키를 카탈로그 조회로 확인했다. 실제 Cloud Run 실행 DB 역할과 해당 역할의 동작은 별도 검증이 필요하다.
- Supabase 보안 점검은 새 표를 포함해 RLS 정책이 없는 표를 INFO로 알렸다. 공개 역할을 차단하는 현재 설계와 구분해 검토한다. 별도로 `public.rls_auto_enable()`의 SECURITY DEFINER 실행 권한에 대해 anon·authenticated WARN이 표시됐다. 이 함수는 event_trigger 반환형이며 실제 외부 호출 가능성과 영향은 확인하지 않았고 변경하지 않았다. Supabase Auth 유출 비밀번호 보호 비활성 WARN도 표시됐으나 프로젝트 자체 비밀번호 로그인과의 적용 범위는 별도 검토한다.
- 미확인: 팀 DB 백업·복구 절차, 전체 데이터 변경 없음의 독립적 검증, Cloud Run 요청 로그의 콜백 쿼리 보호, 운영 Google 로그인 및 검색 회귀. 테이블 삭제는 이후 저장된 Google 연결 정보도 삭제하므로 자동 롤백하지 않는다.

## 2026-11-05 Google 콜백 로그 보호 사전 확인
- GCP `sojafit` 프로젝트의 로그 라우터에서 프로젝트 싱크 두 개 `_Default`, `_Required`를 확인했다. `_Default`에는 별도 제외 필터가 없고 감사·시스템 이벤트 등을 제외하는 기본 포함 필터가 설정돼 있었다. 로그 스토리지에서 `_Default` 30일, `_Required` 400일을 확인했다. 상위 조직·폴더의 집계 싱크와 프로젝트 밖 사본은 확인하지 않았다.
- Google Cloud 공식 문서상 Cloud Run 요청 로그는 자동 생성되고, 싱크 제외는 Logging API 수신 이후에 각 싱크별로 적용된다. 싱크 하나의 제외만으로 수집 자체나 다른 싱크의 라우팅이 차단되는 것은 아니다. 필터는 민감한 필드만 지우는 대신 해당 싱크에서 로그 항목 전체를 제외한다.
- 저장소 `Dockerfile`의 uvicorn 실행에는 `--no-access-log`가 없으며, 로컬 설치된 uvicorn의 접속 로그 코드는 경로와 쿼리를 포함한다. 이는 저장소·로컬 라이브러리 관찰이며 현재 배포 리비전의 명령과 실제 콜백 로그를 실측한 것은 아니다. Google Cloud 요청 로그와 컨테이너 접속 로그를 모두 점검해야 한다.
- 실제 인증 코드나 개인정보를 포함한 새 요청은 보내지 않았고 GCP 싱크·서비스 설정은 변경하지 않았다. 향후 합성 값으로 로그 경로별 필터와 비해당 요청 보존을 검증하고, 인증 코드 없이 안전하게 상태를 확인할 운영 방법을 정한다. Cloud Run Google 로그인은 아직 켜지 않았다.
- 후속 로컬 점검: 가짜 쿼리값만 넣은 `uvicorn.protocols.utils.get_path_with_query_string` 호출 결과 경로에 쿼리 문자열이 포함됐다. 따라서 uvicorn 접속 로그 설정과 Cloud Run 자동 요청 로그를 각각 보호해야 한다. `--no-access-log`는 uvicorn 접속 로그 전체에 영향을 주고, Cloud Logging 싱크 제외는 로그 수신 뒤 해당 싱크의 로그 항목 전체를 제외한다. 적용·실제 배포 검증은 하지 않았다.

## 2026-11-05 Google 콜백 요청 로그 제외 설정
- 사용자 승인 후 GCP `sojafit`의 `_Default` 로그 싱크에 `exclude_google_oauth_callback` 제외 필터를 추가했다. `cloud_run_revision`, `sojafit-api`, `run.googleapis.com/requests`와 Google 콜백 URL을 모두 만족하는 요청 로그만 대상으로 한다. 기존 포함 필터는 유지했다.
- 콘솔의 업데이트 성공 메시지와 싱크 세부정보에서 필터 재조회로 저장을 확인했다. 가짜 URL 6개에 대한 로컬 정규식 검사는 통과했으나 Google Cloud에서 실제 로그 항목이 제외되는지는 실측하지 않았다.
- 제한: 필터는 기존 저장 로그를 지우지 않으며 `_Default` 싱크에서 항목 전체를 제외한다. Cloud Logging 수신 이전, 다른 싱크·상위 계층, Uvicorn 등 컨테이너 접속 로그를 보호하지 않는다. 민감 정보 없는 합성 요청으로 제외 동작과 다른 요청 로그 보존을 확인하고 서버 접속 로그 보호를 마치기 전 Google 로그인 배포를 보류한다.

## 2026-11-05 Uvicorn Google 콜백 접속 로그 보호
- `backend/main.py`에서 앱 시작 시 Uvicorn 접속 로그 필터를 등록해 Google 콜백의 쿼리를 제거한다. 요청 경로·상태 코드와 다른 API 접속 로그는 보존하며, 앱 종료 시 필터를 제거한다. 기존 인증 응답과 DB 데이터를 바꾸지 않는다.
- 실제 Uvicorn 서버를 임시 로컬 포트에 띄운 자동 테스트를 먼저 작성했다. 수정 전 h11·httptools 모두 합성 인증 코드가 로그에 남아 실패했고, 수정 후 두 방식 모두 통과했다. 콜백 실패·끝 슬래시·인코딩된 경로와 일반 경로·비슷한 다른 경로의 기록을 확인했다.
- `uv run --no-sync --offline pytest -q tests/api tests/repo/test_repo_layout.py -p no:cacheprovider` 결과 37 passed, 21 skipped. DB 통합 검사는 전용 테스트 DB를 준비하지 않아 skip이며 팀 DB는 사용하지 않았다. 테스트 초기 로컬 서버 준비 중 연결 시간 초과는 대기 처리 후 같은 검사를 재실행해 해결했다.
- Cloud Run에 배포하지 않았다. 이 필터는 Uvicorn 접속 로그와 앱 수명주기가 활성화된 실행 방식에 한정된다. Cloud Run의 요청 로그 제외 실제 동작과 다른 로거·상위 싱크는 별도 검증해야 한다.

## 2026-11-05 Cloud Run 배포 준비 — 로컬 이미지 시험 사전 기록
- 목적: Google 로그인 변경이 포함된 후보 컨테이너를 운영 트래픽 변경 없이 로컬에서 빌드하고 기동·인증 경로를 확인한다. 비교 대상은 현재 배포본이 아니라 로컬 STH의 변경 상태다.
- 범위·예산: `HEAD`의 Dockerfile·의존성·backend·data와 현재 Google 인증 관련 수정 파일만 임시 빌드 컨텍스트로 복사한다. `.env`와 Git 메타데이터를 포함하지 않는다. 로컬 Docker 빌드이며 Cloud Build·운영 API·모델 호출 비용은 발생시키지 않는다. 공식 베이스 이미지와 잠긴 패키지는 네트워크로 내려받을 수 있다.
- 예정 명령: 임시 컨텍스트에서 `docker build -t sojafit-google-local:review <임시경로>`, 이후 로컬 임시 컨테이너로 `/health`·Google 설정 비활성 상태를 확인한다. 빌드가 10분을 넘거나 이미지 다운로드·의존성 오류가 나면 중단하고 기록한다. 기존 이미지·볼륨은 삭제하지 않는다.
- 원격 `main`은 로컬 STH보다 앞서 있고, 운영 `00008` 리비전은 현재 트래픽의 100%다. 실제 배포 전 운영 이미지와 팀 최신 변경의 차이, 비밀 설정, 로그 보호, 배포 대상·롤백 경로를 별도 검토한다.
- 결과: 민감 파일명을 배제한 별도 컨텍스트(추적된 HEAD와 인증 관련 변경만)로 로컬 이미지를 빌드했고 임시 컨테이너에서 `health=ok`, Google 로그인 기본 비활성, 합성 콜백 접속 로그의 합성 쿼리 미노출을 확인했다. 이미지 `sojafit-google-local:review`는 STH 기준이며 최신 main을 포함하지 않는다. Cloud Build나 배포는 실행하지 않았다.
- 로그 실측: 현재 운영 `00008`에 무작위 합성 식별자만 포함한 콜백·health GET을 각각 보냈다. 로그 탐색기에서 같은 식별자로 콜백 Uvicorn 로그와 health Uvicorn·Cloud Run 요청 로그 3건이 보였고 콜백 Cloud Run 요청 로그는 보이지 않았다. 한 표본의 관찰이며 모든 싱크·지연·변형 경로에 대한 보장은 아니다. 실인증 코드는 사용하지 않았다.
- 원격 확인: 2026-11-05 조회에서 `origin/main`은 `f2d2bc5`, STH HEAD는 `71ee74b`이며 양쪽 전용 커밋은 각각 56개·2개다. 팀 main의 `/api/ask`와 질문 화면은 STH에서 제거한 상태이고, `backend/services/llm.py`에는 main에만 있는 평가 전용 기능이 있다. 주요 RAG 검색·그래프 파일의 확인한 차이는 주석·문서 문자열이었다. 운영 OpenAPI에는 당시 `/api/ask`가 없었다. 팀 최신 코드와 로컬 수정은 합치지 않았고, 사용자 선택에 따라 우선 차이만 대조했다.

## 2026-11-05 팀 최신 기준 Google 로그인 후보 사전 기록
- 사용자 선택: 팀 main의 질문 API·화면은 후보에서 제외하고 Google 로그인과 로그 보호를 적용한다. main의 다른 변경(평가용 LLM 코드 포함)은 유지한다. 실제 main이나 STH 작업 파일은 이 후보를 위해 덮어쓰지 않는다.
- 후보 기준: 팀 `origin/main` `f2d2bc5`에서 빌드에 필요한 추적 파일만 임시 디렉터리로 내보내고, 검토한 로그인 관련 소스·템플릿 및 두 의존성 파일을 반영한다. API·화면에 질문 기능이 빠지는 점을 별도 명시한다. `.env`와 비밀키는 포함하지 않는다.
- 목적·비용·명령: 로컬 Docker만 사용해 `docker build -t sojafit-google-main-local:review <임시경로>`를 실행하고 임시 컨테이너에서 정상 기동·인증 경로·가짜 콜백 로그 보호를 확인한다. 외부 모델과 Cloud Build는 호출하지 않는다. 베이스 이미지·잠긴 패키지 다운로드가 실패하거나 빌드가 10분을 넘으면 중단한다. 이전 사용자 파일·이미지·볼륨은 삭제하지 않는다.
- 결과: 로컬 이미지 빌드에 성공했다. 임시 컨테이너에서 health 정상, 로그인 화면 200, 설정 없는 Google 로그인 비활성, 질문 API 404와 질문 폼 부재, main의 평가 함수 존재, 합성 콜백 쿼리의 접속 로그 미노출을 확인했다. 선택한 5개 파일 외 70개 파일은 main 내보내기 결과와 일치했다.
- 별도 임시 PostgreSQL을 사용해 후보 소스의 `tests/api`를 실행한 결과 53 passed였다. 최초 DB 초기화는 준비 전 접속으로 실패했으며 준비 상태를 확인한 뒤 재실행했다. 임시 DB와 시험용 접속 정보는 정리했다.
- 시험용 태그 주소에서 Google 로그인을 시험하려면 해당 주소에 맞는 `AUTH_ORIGIN`과 OAuth 콜백 등록이 필요하다. 이 설정을 운영 기본 주소에 그대로 적용할 수는 없다. Cloud Run 배포, 실제 Google 인증과 팀 DB 연동은 확인하지 않았다.
- Google OAuth 기존 보안 비밀번호가 콘솔 접근성 출력에 노출되어 사용자에게 알렸다. 사용자가 새 OAuth 보안 비밀번호를 추가하고 Secret Manager `GOOGLE_CLIENT_SECRET`에 직접 등록했으며, 버전 1이 사용 설정됨을 비밀값 조회 없이 확인했다. 기존 비밀번호는 유지했으며 새 값으로 실제 인증한 뒤 철회 여부를 검토해야 한다.
- Cloud Run 운영 `00008`과 기존 시험 `00009`가 같은 기본 컴퓨트 서비스 계정을 사용하고, 해당 계정이 새 보안 비밀에 대한 접근 권한을 상속받는 것을 콘솔에서 확인했다. 실제 후보 리비전의 비밀 로딩과 로그인은 아직 검증하지 않았다. `00009`는 `PGSSLMODE=verify-full`, CA 경로 및 비밀 볼륨이 있으나 운영 `00008`에는 해당 별도 설정과 볼륨이 없다. 운영의 URL 자체 TLS 옵션이나 실제 DB 연결 보호 수준은 이 비교만으로 확정할 수 없다.
- Cloud Build·배포 결과: 사용자가 Cloud Shell 인증을 마친 뒤 체크섬이 일치하는 비밀 제외 후보 소스를 풀어 `gcloud run deploy --source . --no-traffic --tag=google-login-test`로 배포했다. `sojafit-api-00013-duv`는 0% 트래픽으로 생성됐고 시험 태그 주소를 반환했다. 이어 시험 `AUTH_ORIGIN`, 기존 OAuth 클라이언트 ID, Secret Manager의 `GOOGLE_CLIENT_SECRET:1` 참조를 추가해 `sojafit-api-00014-wox`를 생성했으며 이 리비전도 0%다. 운영 기본 트래픽은 옮기지 않았다.
- OAuth 설정: 시험 태그 주소의 `/api/auth/google/callback`을 기존 웹 OAuth 클라이언트의 승인된 리디렉션 URI에 추가하고 콘솔의 저장 완료 알림을 확인했다. 로그인 경로와 Google 상태 경로는 각각 HTTP 200, 제외한 `/api/ask`는 404였다. 실제 Google 계정 인증, 팀 DB 로그인 허용 여부, 검색 회귀는 아직 시험하지 않았다.
- 보안 후속: 콘솔의 접근성 출력이 OAuth 비밀값 전체를 반환한 사실을 확인했다. 해당 값은 이 기록에 남기지 않았고 다시 사용하지 않는다. 실제 로그인 전에 사용자가 Google 콘솔에서 새 OAuth 비밀을 발급하고 Secret Manager에 새 버전으로 등록해야 한다. 그 후 Cloud Run 시험 리비전을 새 버전 참조로 갱신해 인증을 검증하고, 이전 비밀 버전은 새 로그인이 확인된 뒤 비활성화한다. 노출된 인증 코드는 일회용이며 이미 인증 절차에 사용됐으므로 재사용하지 않는다.
- 확인하지 못한 것: 시험 리비전의 실제 DB 연결·TLS 설정, 새 OAuth 비밀 교체 후 실계정 로그인·팀 DB 승인·권한 제한·로그 실측, Cloud Run 운영 트래픽 회귀. 새 Secret Manager 버전과 Google 비밀 교체는 사용자 조치 대기 중이다.

## 2026-11-05 Cloud Run Google OAuth 시험 확인
- 새 OAuth 비밀을 Secret Manager `GOOGLE_CLIENT_SECRET`의 버전 2로 등록한 뒤, 시험 태그 `google-login-test`에 연결했다. `GOOGLE_AUTH_ENABLED=1`이 있어야 버튼과 시작 API가 켜지는 코드 조건을 확인해, 이 설정을 반영한 `sojafit-api-00016-yax` 리비전을 `--no-traffic`로 생성했다. 운영 기본 트래픽은 옮기지 않았다.
- 시험 태그에서 `/api/auth/google/status`가 `enabled: true`를 반환하는 것, `/api/auth/google/start`가 Google 계정 선택 화면으로 이동하는 것, 실제 시험 Google 계정 인증 후 콜백이 관리자 연결 승인 대기 화면으로 돌아오는 것을 확인했다. 이는 Google 인증 코드 교환·ID 토큰 검증·팀 DB의 대기 요청 저장까지 통과했다는 뜻이다.
- 대기 상태에서는 관리자 세션이 만들어지지 않는다. 기존 활성 `admin` 계정에 Google 연결 요청을 승인한 뒤 같은 계정으로 다시 로그인하면 세션 발급을 검증할 수 있다. 이번에는 권한을 부여하는 승인 작업과 운영 트래픽 전환을 수행하지 않았다.
- 주의: 콘솔에서 환경 변수를 직접 수정해 기본 트래픽 100% 배포가 될 수 있는 화면을 확인했으나, 변경을 취소하고 0% 시험 리비전만 배포했다. 실제 Google 인증 URL의 상태·nonce·인증 코드는 기록이나 채팅에 남기지 않는다.

## 2026-11-09 새 질문 이후 승인 기억 복구 수정
- 범위: backend/conversations.py, tests/api/test_threads.py, docs/specs/user-thread-memory.md. 기존 승인 API와 DB 구조를 유지한다. 기존 승인 원본이 있으면 현재 version/can_approve 검사보다 먼저 읽고 Store만 재저장한다. 최초 승인에는 현재 완료 결과 검사와 소유권 검사를 유지한다.
- 신규 승인 snapshot에 part를 보관한다. 기존 snapshot은 불변 업로드 회로의 고정 대상 품번으로 복구하며 현재 그래프 상태는 사용하지 않는다. 원본/승인 시각을 수정하지 않는다. SPEC 주요 문서 변경은 조장에게 이 작업서의 API 계약/AC 반영을 요청한다.
- RED: TEST_THREAD_DATABASE_URL을 로컬 격리 PostgreSQL 127.0.0.1:55439/thread_test로 지정하고 uv run --no-sync --offline pytest -q tests/api/test_threads.py -k old_approval_store 실행. 두 경우 모두 이전 version 검사 409로 실패했다.
- GREEN: 같은 전용 DB에서 uv run --no-sync --offline pytest -q tests/api/test_threads.py 실행, 15 passed. HTTP 회귀 추가 후 uv run --no-sync --offline pytest -q tests/api 실행, 57 passed, 21 skipped (15.35초). TEST_AUTH_DATABASE_URL 미설정 인증 DB 테스트는 건너뛰었다. git diff --check 통과.
- 검증: Store.put 합성 장애 503 → 새 질문(version 증가/현재 결과 거절) → 이전 승인 재요청 200 → 실제 PostgresStore 기억 한 건. 신규/기존 snapshot, 현재 state 품번 변경, 중복 재시도, 원본/승인 시각 유지, 다른 사용자 404, 미승인 과거 version 409를 확인했다. HTTP는 TestClient와 실제 로컬 DB를 사용했고 인증 사용자 의존성은 테스트용으로 대체했다.
- 환경 문제: 기본 uv PATH 누락과 샌드박스 캐시 접근 실패 후 기존 portable uv와 별도 캐시 경로/권한 확장으로 실행했다. 패키지 추가나 lock 변경은 하지 않았다.
- 미확인/범위 밖: 실제 모델 호출/평가셋 재측정, 공유 DB/배포, 실행 중 Swagger 서버 재시작, 과거 승인 복구 전용 화면·자동 재처리. 기존 approve API에 해당 version을 재전송하는 수동 복구다. 테스트가 만든 업무 행은 fixture가 정리하며 이전 시연 사용자 데이터는 수정하지 않았다.

## 2026-11-09 승인 기억 모델 입력 연결 — 실제 모델 시험 사전 기록
- 목적: 새 thread의 답변 생성에 승인 기억이 반영되는지와 A/B의 같은 품번 사례가 섞이지 않는지 합성 데이터로 확인한다. 전체 평가/성능 개선 검증은 아니다.
- 조건/예산/명령/중단: evals/guides/preregister.md의 2026-11-09 항목과 동일. 실제 호출은 기존 backend/services/llm.py를 통해 generate 최대 2회, 예약액 0.25달러/100초/512 출력 토큰 상한. 그래프 Supervisor 선택만 고정하고 DB/입력/생성 경로는 실제 구현을 사용한다. 공유 DB/원격 배포 없음. 합성 테스트 사용자 행은 종료 시 정리한다.
- 오류 후 진단: 최초 smoke는 generate 1회에서 서비스 HTTPException으로 중단(예약액 0.07312달러, 응답 0건). 공식 models 읽기 전용 조회에서 설정 모델은 목록에 있었다. 오류를 가리는 서비스의 예외 체인에서 타입/HTTP 상태만 수집하는 진단을 남은 1회/0.17688달러 이내로 수행한다. 최초 계획의 총 2회/0.25달러 상한은 유지하며 진단은 A 한 건만 실행한다. 어떤 오류라도 이후 추가 호출하지 않는다.
- 진단 결과/추가 단계: LengthFinishReasonError(512 출력 상한) 확인. 별도 사전 등록대로 출력 상한만 2048로 바꾼 A 한 건을 최대 1회/예약 0.12달러/60초로 추가 검증한다. 최초 2회 상한은 종료했고 추가 단계의 별도 예산을 적용한다. 전체 실제 청구액은 확인 불가, 예약액만 기록한다.

## 2026-11-09 승인 기억 모델 입력 연결 — 최종 결과
- 변경: conversations.py가 새 질문 실행 전 인증 사용자 namespace의 같은 품번 사례를 조회하고 승인 원본/소유권을 재확인해 최대 5건을 approved_memories로 전달한다. Store에 잘못 들어간 타 사용자 포인터, 무관 품번, 승인 원본 없는 항목은 제외한다. 신규 snapshot은 당시 질문/조건/target_part/judge_read를 보관한다. 기존 원본의 없는 문맥은 unknown이다.
- 그래프/프롬프트: AgentState/MultiState와 supervisor, generate, judge_read에 별도 과거 JSON을 전달한다. 요약 1000자/문맥 2000자/최대 5건 상한. 과거 내용은 지시/현재 조건/사양 근거가 아니라는 지침을 supervisor/generate/judge_read 프롬프트에 추가했다. judge_read 모델만 기억을 읽고 숫자 grounding용 render_read에는 포함하지 않는다. 판정은 기존 judge 코드/답 틀을 유지한다. 생성·검증은 승인사례:thread:version 출처와 실제 제공한 사례 목록을 대조한다.
- RED/GREEN: 새 A/B 통합 테스트는 변경 전 NO_MEMORY 응답으로 실패했다. 실제 PostgresSaver/PostgresStore와 실제 멀티 그래프/가짜 모델로 A/B 양방향 모델 입력·응답 격리, 자기 namespace의 타인 포인터 차단, 무관 품번 제외, 승인 원본 삭제 후 이전 턴 기억 비우기를 확인했다. 과거 987V를 제안하는 가짜 판정 읽기 출력은 grounded 검사에서 탈락하고 조건 질문으로 이어졌다. 기억 건수/길이, 존재하지 않는 사례 인용, 현재 근거가 전혀 없으면 생성하지 않음도 검증했다.
- 최종 명령: TEST_THREAD_DATABASE_URL=로컬격리DB 설정 후 uv run --no-sync --offline pytest -q tests/api tests/graph tests/multi_agent tests/services/test_langfuse_prompts.py → 297 passed, 22 skipped, 19.58초. 전용 인증 DB 등 환경 의존 항목은 skip. git diff --check 통과. 새 의존성/SQL migration은 없다.
- 실제 모델 결과: 기존 generate 모델 anthropic/claude-haiku-5.5. 처음 512토큰 시도/오류 진단 각 1회는 LengthFinishReasonError. 출력만 2048로 바꾼 추가 A 1건은 6.56초에 성공: 자기 설계명 APRICOT_729와 당시 12V를 사례 출처로 회상하고 B의 COBALT_481은 미포함. fake_citations=[], uncited_sentences=0. 실제 smoke에서 Supervisor 선택은 writer→finish로 고정했고 생성은 실제 모델이었다. A/B 양방향은 가짜 모델 통합 테스트 결과다. 전체 3회 예약 합계 0.25776달러이며 실제 청구액은 이 호출 경로에서 수집하지 못했다.
- 산출물: 세션 visualizations의 approved_memory_smoke.py/.json, approved_memory_smoke_attempt1.json, approved_memory_smoke_attempt2.json. 합성 데이터만 사용했고 실제 smoke의 사용자/업무/Store 행을 종료 시 정리했다. 체크포인트 내부 합성 이력은 남을 수 있다.
- 문서: docs/specs/user-thread-memory.md 계약/AC, GRAPH.md, MULTI_AGENT.md, PROMPTS.md 갱신. SPEC 8.5에 별도 화면 표시뿐 아니라 서버 선별 후 모델 입력 전달과 과거 조건 보호 계약 반영을 조장에게 요청한다. STH에서 주요 문서는 수정하지 않았다.
- 미검증/다음: 전체 동결 평가 재측정/실제 Supervisor 포함 유료 전체 그래프, 사용자 실자료, Langfuse 원격 프롬프트 재등록, 배포/공유 DB는 수행하지 않았다. 기억 정정/삭제 UI/벡터 검색은 범위 밖. 이전 실행 중 Swagger 서버는 재시작하지 않아 새 코드 적용에는 재시작이 필요하다.

## 2026-11-09 STH 로컬 커밋 정리
- 사용자 요청: 지금까지 구현한 사용자별 thread/장기기억 기능을 STH에 로컬 커밋하고 변경 내용을 정리한다. 원격 push는 하지 않는다.
- 요약 문서: docs/specs/user-thread-memory.md의 '로컬 커밋용 변경 요약과 운영 보완사항'에 구현/시험/미해결 문제/적용 경계를 정리했다.
- 커밋 전 전체 검사: TEST_THREAD_DATABASE_URL=기존 로컬 격리 DB로 uv run --no-sync --offline pytest -q → 837 passed, 43 skipped, 1 failed (22.34초). 실패는 tests/repo/test_repo_layout.py::test_tree_matches_files의 기존 db/012_document_category.sql 부재다. git ls-tree HEAD에도 해당 파일이 없으며 주요 문서 수정 권한 범위 밖이므로 임의 변경하지 않았다. 기능 테스트 통과와 저장소 전체 통과는 구분한다.
- 규모: 사용자 업로드→분석 상태 보존→승인/기억→모델 전달의 하나의 기능이며 핵심 코드/테스트/계약이 400줄을 넘는다. 분리하면 API/DB/그래프 계약이 실행 불가능한 중간 상태가 되므로 현재 동작 가능한 기능 스냅샷으로 보관한다. 후속 PR에서는 이 사유와 로컬 검사 결과/남은 운영 과제를 기재해야 한다.
- 기존 사용자 변경 보존: 같은 worklog의 별도 Supabase 구조 비교/적용 2개 항목은 이번 대화에서 검증한 변경이 아니므로 작업 파일에 유지하되 이 로컬 커밋에서는 제외한다.
- 스테이징 확인: 이번 기능의 41개 파일을 대상으로 .env의 비밀 필드 9개 실제 값 일치와 private key/OpenAI·OpenRouter/Google/GitHub 토큰 패턴을 값 출력 없이 검사했고 findings=0이었다. gitleaks 실행 결과는 아니며 원격 CI secret scan은 미실행이다. git diff --cached --check 통과. 별도 Supabase 두 절 16줄은 작업 폴더에 남겼다.

## 2026-11-09 PR #72 main 충돌 해결·STH 통합
- 사용자 승인/범위: PR #72의 충돌을 순서대로 해소하고 STH 커밋·푸시까지 수행하도록 직접 요청했다. 이 요청을 이번 STH 일반 푸시의 승인 범위로 적용한다. main 직접 커밋/강제 푸시/PR 머지/리뷰어 지정/배포는 하지 않는다. 새 브랜치/워크트리는 만들지 않는다.
- 기준: 병합 전 STH a09a951, main 2e32a64. git ls-remote에서 PR #72 head가 STH와 같음을 확인했다. GitHub connector PR 조회는 404였으며 Git 원격으로 확인했다. 작업 트리가 깨끗한 상태에서 fetch 후 git merge --no-commit --no-ff origin/main을 수행했다.
- 충돌 11개: SOJAFIT.md, BACKEND.md, main.py, MULTI_AGENT.md, agents/judge.py, agents/verifier.py(modify/delete), multi_agent/build.py, supervisor.py, prompts/PROMPTS.md, prompts/supervisor.md, docs/specs/SPECS.md. 주요 문서는 main의 조장 변경을 유지하고 SOJAFIT에는 기존 STH 신규 파일 7줄만 반영했다. SPEC/README/ADR/EVAL_REPORT는 main의 변경을 그대로 가져오며 STH의 임의 수정은 없다.
- 통합 방식: main의 Plan→Send(문서/판정 하위 그래프)→모으기→종합/답 검사 구조를 유지했다. build_graph에 store 인자/compile 연결을 복원하고 approved_memories를 render_plan, Send payload, JudgeState, docs_answer, render_synth로 전달했다. 구 verifier.py는 main 삭제를 유지하고 사례 출처 검사를 docs의 인용 정리와 supervisor.check_node에 이식했다. judge 읽기의 작업 지시서/다수결/관문과 main LLM 캐싱·추론 설정·재시도 개선은 유지했다.
- API 계약: thread DB 503/본문 크기 413도 error.code/message/request_id 형식과 X-Request-ID/no-store를 사용한다. workspace는 error.message를 읽는다. 기존 내부 오류 테스트는 개인 .env AUTH_ORIGIN 값에 따라 403으로 잘못 끝났으므로 테스트에 의도한 localhost origin을 명시해 500 비밀 보호를 확인했다.
- RED→GREEN: main 기준 기계적 충돌 해소 뒤 새 계약 테스트에서 6 failed, 38 passed(Store 인자, 기억 전달, 사례 인용, 화면/DB 오류 계약). 이식 후 같은 검사 44 passed. 새 판정 하위 그래프를 실제 PostgreSQL에 중단 저장→연결 종료→재연결→재개→승인하고 판정 읽기 재호출 없음/기억 유지까지 확인했다. A/B 새 Plan/docs 모델 입력·응답 격리, 잘못된 타인 포인터 제외, 혼합 사례 인용 정리, 과거 숫자가 종합의 현재 값 검사를 완화하지 않음도 시험했다.
- 최종 검사: TEST_THREAD_DATABASE_URL=기존 로컬 격리DB, uv run --no-sync --offline pytest -q → 923 passed, 57 skipped, 1 warning, 28.77초. warning은 Docling ListItem 부모 보정 deprecation이다. 전용 인증 DB/외부 리소스 등의 환경 의존 항목은 skip했다. 최초 repo 검사에서 unmerged 인덱스의 중복 경로를 대소문자 충돌로 보고했으나 해결 파일 git add 뒤 최종 전체 검사는 통과했다. backend 설명 누락도 복원했다. db/012_document_category.sql은 main의 정식 파일을 가져와 종전 트리 불일치가 해소됐다.
- 문서: user-thread-memory/API 오류 작업서 및 backend/multi_agent/prompts 설명을 새 구조에 맞췄다. 구 구조로 수행한 실제 generate smoke는 과거 기록이며 이 통합의 실제 모델 결과로 재사용하지 않는다.
- 미실행/남은 위험: 유료 모델·동결 평가 재측정·Cloud Run·공유 DB·Langfuse 원격 프롬프트 갱신은 하지 않았다. 승인 사례의 의미적 사양 검증/최종 interrupt 조건 snapshot 보완/운영 예산·관측·복구 UI는 기존 후속 과제다. 이번 작업은 그래프 통합과 충돌 해소 범위다.
- 커밋/원격 결과: 병합 커밋 44042a3(부모 a09a951/2e32a64)을 만들고 사용자 요청대로 git push origin STH 성공. 원격 STH=44042a335c0151e2bdcc86f234fbcbe44f2a0070 확인. git merge-tree origin/main HEAD는 충돌 없이 종료했고 작업 트리는 깨끗했다. 스테이징 텍스트 88개에 실제 비밀 필드 9개 값과 대표 토큰/충돌 표시 검사를 수행해 findings=0, whitespace 검사 통과(gitleaks 자체 실행은 아님).
- PR #72 상태: 푸시 후 PR head ref가 a09a951에 남아 기존 Git 인증으로 GitHub API를 읽기 전용 조회했다(인증값 출력/파일 저장 없음). state=closed, merged=false, head=STH/a09a951, base=main, mergeable_state=dirty였다. 닫힌 PR의 이전 head 상태이며 최신 STH 병합 결과와 구별한다. 재개/새 PR 생성은 수행하지 않았다. PR을 다시 열거나 새 PR을 만들면 최신 STH 기준으로 재검사가 필요하다. 사용자 요청 범위의 STH 충돌 해결·커밋·일반 푸시는 수행했다.