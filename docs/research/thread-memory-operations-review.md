# Thread·승인 기억 운영 검증 결과와 정본 반영 제안

기록일: 2026-11-09. 검증 대상은 STH의 `717c93a`·`245be70`·`ccadd3f`와 시험 image `cdc9ed1d2b5881a2792ed1f46d5ae808d3bac99c406caa055d38155fe79056f4`다. 아래 수치는 해당 실행의 스냅샷이며 이후 배포·DB 상태를 보증하지 않는다. 조장 합의 전 제안은 정본 기능 계약이 아니다.

기능 계약: [사용자별 thread·기억](../specs/user-thread-memory.md), [평가자·데모·관측](../specs/evaluator-demo-readiness.md). 측정 절차: [운영 검증 계약](../experiments/thread-memory-operations.md).

## 2026-11-09 원격 CI 후속 확인
- head 7ff0d4a에서 [일반 test CI](https://github.com/aihuman-7th/proj3-b/actions/runs/42574594948)는 성공했고 [Secret Scan](https://github.com/aihuman-7th/proj3-b/actions/runs/42574594978)은 검증 요약의 소스 SHA-256 한 건을 generic-api-key로 오탐했다. 아래 초기 결과의 원격 CI 미확인은 당시 상태이며 이 실행 결과와 구분한다.
- 해당 값은 실제 backend/auth.py 파일 해시와 대조했다. [.gitleaksignore](../../.gitleaksignore)는 커밋·파일·규칙·줄 fingerprint 한 건에만 적용되며 파일/규칙 전체를 제외하지 않는다. [공식 fingerprint 문서](https://github.com/gitleaks/gitleaks#-gitleaksignore)를 따랐다.
- CI와 같은 이미지의 로컬 전체 이력 검사453 commits/35.04MB를 실패1→탐지0으로 재검증했고, 다른 입력 위치의 검출 대조군은 여전히 탐지됐다. 변경 커밋의 원격 완료 결과는 PR #73의 최신 Checks를 따른다.

## 최종 실행 결과

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

## 이전 검증 스냅샷 — 최종 결과와 구분
다음은 운영 보완 전 기록이다. 실패 수치·미구현 설명을 현재 상태로 해석하지 않는다. 당시 기록의 문구와 수치는 보존한다.


- 후속 운영 검증 준비·명령·합격 기준은 [thread-memory-operations](../experiments/thread-memory-operations.md)를 따른다. 기능 변경 없이 로컬 병렬·백업 복원과 호출 없는 품질 dry-run/보고 비용 기록 도구를 추가한다.
- 구현 범위: 기존 로그인 세션의 사용자 ID를 재사용해 넷리스트 업로드, 분석별 UUID thread, 목록/소유권 검사, DB 체크포인트/조건 재개/제한 재시도, 버전별 승인 원본/사용자 Store, 기본 workspace 화면을 연결했다. 새 질문 뒤 이전 승인 기억 재저장과 새 thread 모델 입력의 같은 품번 사례 조회를 추가했다.
- 최신 로컬 검증: 전체 pytest는 837 passed, 43 skipped, 1 failed(22.34초). 실패는 기존 SOJAFIT.md가 가리키는 db/012_document_category.sql 부재이며 HEAD 트리/파일 조회로 기존 불일치를 확인했다. 신규 기능 관련 API/graph/multi_agent/Langfuse 계약 검사 결과는 297 passed, 22 skipped. 두 결과는 실행 범위가 다르다. 동결 평가셋 답안은 수정하지 않았다.
- 실제 모델 확인 범위: 합성 A 사례 한 건의 generate 답변 회상 성공, Supervisor는 고정 경로였다. A/B 양방향 입력·응답 격리는 실제 DB/가짜 모델 테스트다. 전체 답변 품질 향상이나 운영 준비 완료를 의미하지 않는다.
- 운영 전 우선 보완: (1) 사례 인용만으로 현재 사양 주장이 검증을 통과하는 의미 검증 공백, (2) interrupt 최종 조건의 승인 snapshot 명시적 보존과 문맥 잘림, (3) 일반 서비스 요청의 사용자별 비용/빈도/시간 제한, (4) 이전 승인 version의 화면 복구, (5) 비밀값 없는 오류코드/요청 ID, (6) 실제 모델 전달 사례와 사후 관련 사례 구분, (7) 기억 조회 순서/페이지·철회·보관·백업 복원 절차.
- 확인한 검증 공백: 합성 문장 'SS34의 허용 전압은 999V입니다'에 제공된 승인사례 출처만 붙여 verifier_agent에 넣으면 status=ok가 된다. 실제 모델이 해당 문장을 생성한 결과는 아니며, 현재 검증은 출처 존재/인용 형식 범위다. 이 문제의 수정은 이번 커밋 범위에 포함하지 않았다.
- 적용 경계: 이 커밋은 로컬 기능 코드와 문서·테스트·기존 원시 결과를 보관한다. 실행 중 서버 재시작, 공유 DB 설정 활성화, 원격 프롬프트 등록, 배포, Git push는 하지 않는다. 별도 Supabase 작업의 적용 기록은 이 커밋의 검증 근거와 분리한다.
