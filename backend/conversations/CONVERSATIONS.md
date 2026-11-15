# conversations

## 역할
- 이 폴더: 프로젝트 소유 대화·메시지·실행(run)의 저장 경계, React run·재개가 거치는 사용자 분석 서비스, 사용자 사실 기억, 브라우저로 내보낼 결과의 허용 목록을 둔다.
- 넣는 것: 소유권 조건 SQL(`repository.py`), 실행 상태 전이와 오래된 running 정리, 분석 thread·체크포인트·예산·사용자 사실 기억(`memory_service.py`, `profile.py`), 안전 결과 형식(`models.py`, `dto.py`).
- 넣지 않는 것: HTTP 라우터(`backend/api/`), 그래프 정의(`backend/multi_agent/`), 가격·재고 응답(`backend/api/prices.py`).
- 담당: 서비스·운영

## 동작 요약
| 항목 | 내용 | 근거 |
|---|---|---|
| thread id | `str(threads.id)`가 LangGraph `thread_id` 정본이다. 분석 서비스(`sojafit_agent`)의 thread는 화면용 `public.threads`와 같은 UUID다 | `memory_service.py` `ensure_thread` |
| 대화 문맥 | 현재 질문은 `input`, 같은 thread의 이전 사용자 입력은 내부 `conversation_history`로 분리한다. 질문 50건 상한 안에서 이력을 최대 20,000자로 제한하며 12개 개수 제한은 두지 않는다. assistant 답변·승인 사례는 포함하지 않는다. 공개 API 요청·응답 형식은 그대로다 | `memory_service.py` `_conversation_history`, `message` |
| 회로 버전 | `public.threads.circuit_version`은 생성 당시 버전으로 고정한다. 상세·새 실행·분석 시작·재개는 `project_circuit_versions`에서 해당 버전을 읽으며 이후 업로드가 과거 대화를 바꾸지 않는다 | `repository.py`, `memory_service.py`, `db/031_circuit_versions.sql` |
| 체크포인트·사용자 사실 | 분석 서비스에만 있다. 사용자 사실은 Store namespace `(user_id, "profile")`에 둔다 | `profile.py` `namespace` |
| 승인 사례 | 비활성이다. 분석 입력의 `approved_memories`는 항상 빈 목록이고 Store에도 쓰지 않는다. 승인 기록은 `public.approvals`(견적 승인)에만 남는다 | `memory_service.py:442`(`'approved_memories': []`), 같은 파일 머리말 |
| 토큰 상한 | 사용자·서비스 하루 상한은 호출 전에 원자적으로 차감한다. 값은 `memory_service.py`의 `USER_DAILY_TOKENS`·`SERVICE_DAILY_TOKENS`이고 계약은 [SPEC.md](../../SPEC.md) | `memory_service.py:55-56` |
| 프로젝트 삭제 | project 행 잠금으로 새 실행과 직렬화하고, public 행과 같은 UUID의 분석 thread·checkpoint를 한 트랜잭션에서 지운다 | `memory_service.delete_analysis_threads` |
| 탈퇴 | 계정 잠금(`account_deletion`)을 잡고 분석 기록, Store namespace 순서로 지우며 계정 행은 호출자(`backend/api/profile.py`)가 마지막에 지운다 | `memory_service.py:15`, `backend/api/profile.py` |
| 오래된 running 정리 | `repository.recover_stale_run`이 인증된 recover POST에서만 호출된다. 오래되고 분석 잠금이 없는 running만 failed로 바꾸고 모델은 다시 부르지 않는다 | `repository.py:23` |
| 저장 결과 | answer, question_type, 품번, interrupt, 공개 판정·인용 메타데이터와 선택적 error(code/message)만 허용한다. 알려진 공개 오류 코드만 저장하며 request_id·내부 예외·문서 원문은 저장하지 않는다. 재개 입구429도 대기 run의 오류로 기록하고 이후 실행 중/완료된 run에는 덮어쓰지 않는다 | `models.py`, `dto.py`, `repository.record_resume_error` |

계약 상세는 [user-thread-memory.md](../../docs/specs/user-thread-memory.md)와 [api-error-contract.md](../../docs/specs/api-error-contract.md)를 따른다.

## 파일
| 파일 | 하는 일 |
|---|---|
| `CONVERSATIONS.md` | 이 문서 |
| `__init__.py` | 패키지 표시 |
| `memory_service.py` | 분석 서비스 `Conversations`: thread 소유권, DB 체크포인트, 조건 재개, 하루 토큰·USD 예산(`admission`), `profile_hints`, 삭제 `delete_analysis_threads`, `--setup` CLI `initialize`, `DEMO_REPLAY=1` 재생 chat 주입 |
| `profile.py` | 사용자 사실 3칸 장기 기억: 칸 검사, 틀 문장, Store 덮어쓰기(version)·지우기, Voyage 의미 검색(키가 없거나 데모 모드면 순위 없이) |
| `dto.py` | 브라우저 결과 허용 목록 `BrowserResult`, 그래프 상태에서 공개 값만 고르는 `public_state`, 저장 결과 변환 `result_dto` |
| `models.py` | 실행 상태와 저장 허용 결과 형식(`SafeResult` 등) |
| `repository.py` | 소유자 조건이 붙은 대화 저장소 `ConversationRepository`: thread 생성·삭제, run 시작·종료·재개·정리, 목록과 페이지 단위 메시지 조회(SELECT만) |
