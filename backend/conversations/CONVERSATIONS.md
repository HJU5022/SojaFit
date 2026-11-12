# conversations

## 실행 상태 정리

- `repository.recover_stale_run`은 인증된 recover POST에서만 호출한다. project/run 행 잠금과 기존 thread advisory transaction 잠금으로 실행·삭제와 충돌하지 않게 한다. 최근 실행, 활성 분석 잠금, requires_input·완료 결과는 유지한다.
- 중단 기준은 갱신 후 max(300초, ANALYSIS_MAX_SECONDS+60초)이며, 오래된 running만 failed로 바꾼다. checkpoint·메시지·조건·견적은 삭제하지 않고 모델도 재실행하지 않는다. 저장되지 않은 완료 답을 추측해 복원하지 않는다. GET 조회는 읽기 전용이다.

## 역할
- 판정의 input_conditions는 검증된 값·시험 조건·적용 한계만 현재 브라우저 응답에 표시한다. runs 저장에서는 제외하므로 DB 변경이 필요 없고 저장 기록 GET은 해당 목록을 복원하지 않는다. raw read_values/원문 보고는 내보내지 않는다.
- 이 폴더: 프로젝트 소유 대화·메시지·실행의 저장 경계와 내부 결과 형식을 둡니다.
- 넣는 것: 소유권 조건 SQL, 실행 상태 전이, 안전 결과 형식.
- 넣지 않는 것: HTTP 라우터, 그래프 실행, 가격·재고 응답.
- 담당: 서비스·운영

## 파일
- `CONVERSATIONS.md` — 이 문서
- `__init__.py` — 패키지 표시
- `memory_service.py` — React run·재개가 거치는 사용자 분석 서비스: thread 소유권·DB 체크포인트·조건 재개, 질문·재개 때 사용자 사실 찾기(`profile_hints`). `THREADS_ENABLED=1`에서 사용하며 `--setup` CLI를 제공. HTTP 입구는 React 대화 API · 내 설정 · 탈퇴뿐이다(React 이전 화면 `/workspace` 경로는 11-10에 지움). `upload` · `create` · `approve` · `memories`는 11-11 재설계(P2)로 지웠다. `ensure_thread`가 React 대화(public.threads)와 같은 UUID의 분석 thread를 처음 한 번 만들고(FK, 회로 사본 없음; 회로 이름 · 연결 정보는 `public.threads → projects → circuits`에서 읽는다. public 행이 없으면 404) 대상 부품을 고정한다(바꾸면 409). `initialize`(`--setup`)는 SQL 파일을 적용하지 않고 LangGraph 표만 만든다. 새 질문마다 보관 기간 청소 함수(db/023)를 작은 묶음으로 부른다(실패해도 분석 계속). 탈퇴는 계정 단위 advisory lock(분석 · 기록 쓰기는 공유, 탈퇴는 배타)으로 진행 중인 분석과 서로 409. 분석 예산은 USD 예약과 같은 위쪽 경계 토큰을 사용자 · 서비스 전체 UTC 하루 상한(5,000,000 · 10,000,000)에 원자적으로 더하고 넘으면 호출 전 429(`_budget`, `admission`, db/022). 키 없는 데모(`DEMO_REPLAY=1`)는 같은 그래프에 재생 chat(`backend/services/demo.py`)을 넣고 Store를 넘기지 않으며, 기록한 회로 · 대상 · 질문 · 사용 조건을 새 대화의 첫 질문으로만(`ensure_thread` · `message`), 재개는 기록한 답 · 역할만 받는다(아니면 422, 기록이 없으면 503, 기록에 없는 호출은 노드 이름을 담은 503)
- `profile.py` — 사용자 사실 3칸 장기 기억(SPEC 8.5): 칸 검사, 틀 문장, Store 덮어쓰기(version)·지우기, Voyage 의미 검색(키 없으면 순위 없이)
- `dto.py` — 브라우저 결과 허용 목록(참고(내 설정) `profile_hints` 포함), 그래프 상태에서 공개 값만 고르는 `public_state`
- `models.py` — 실행 상태와 저장 허용 결과 형식
- `repository.py` — 소유자 조건, 실행 생성·재개 및 결과 저장. 목록의 첫 질문 제목·최근 활동·최신 run 요약과 페이지 단위 저장 메시지·run 참조 조회는 SELECT만 사용하며 분석·보관 정리를 호출하지 않는다. 분석 thread가 없는 저장소는 target_ref=null로 읽기만 허용한다.
- `delete_thread`는 프로젝트 행 잠금과 thread advisory transaction 잠금 아래 소유권·실행 중 여부를 확인하고, 기존 `delete_analysis_threads`와 public thread FK cascade를 한 트랜잭션에서 처리한다. 추가 입력 대기는 실행 잠금이 없으면 삭제 가능하다. 프로젝트·다른 대화·사용자 사실 Store는 유지한다. 고정은 DB 기능이 아니라 사용자가 선택한 브라우저 설정이다.

`str(threads.id)`가 불변 LangGraph `thread_id` 정본이고, 같은 UUID가 사용자 분석 서비스(`sojafit_agent`)의 thread id다. 체크포인트·승인 기록·사용자 사실 기억(Store, namespace `(user_id, "profile")`)은 분석 서비스에만 있다. 승인 사례는 장기 기억이 아니라 승인 기록이다(11-09): 새 분석에 넘기지 않고 Store에 쓰지 않는다. 프로젝트 삭제는 project 행 잠금으로 새 실행·재개와 직렬화하고 활성 실행이 있으면 거절하며, public 행과 같은 UUID의 분석 thread·checkpoint를 한 트랜잭션에서 지운다(`memory_service.delete_analysis_threads`). 탈퇴(`DELETE /api/me`)는 계정 잠금(`account_deletion`)을 잡고 분석 기록 → Store namespace → 계정 순서로 지운다. 저장 결과는 answer, question_type, 품번, interrupt, 공개 판정·인용 메타데이터만 허용하며 request_id는 저장하지 않는다. 문서 질문의 raw chunk는 반환하지 않는다.
