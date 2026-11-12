# 평가자 데모: 기록 응답 재생과 확인 경로

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(정본: [SPEC.md](../../SPEC.md) 7절 데모 모드·오프라인 규칙, 운영 절차는 [data/demo/DEMO.md](../../data/demo/DEMO.md))
- 관련 문서: [scripts/demo/DEMO.md](../../scripts/demo/DEMO.md), [user-thread-memory.md](user-thread-memory.md), [thread-memory-operations-review.md](../research/thread-memory-operations-review.md)

## Why

- 평가자는 개발자 DB와 API 키 없이 로그인부터 분석·조건 보충·승인·사용자 간 분리까지 확인해야 한다.
- 키 없는 환경에서 LLM·임베딩·리랭크·Mouser를 부르면 과금되거나 실패한다. 기록에 없는 질문을 비슷한 답으로 처리하면 데모가 실제 품질처럼 보인다.

## Goal

| 항목 | 성공 기준 | 근거 |
|---|---|---|
| 키 없는 기동 | `.env` 없이 `docker compose up --build`만으로 데모 사용자 로그인과 기록 질문 재생 | `docker-compose.yml`, [data/demo/DEMO.md](../../data/demo/DEMO.md) |
| 외부 호출 | 재생 모드에서 LLM·임베딩·리랭크·Mouser 호출 0건 | `backend/services/demo.py`, SPEC 7절 |
| 오매칭 | 기록과 한 글자라도 다른 질문·회로·대상·조건은 다른 고정 답으로 처리하지 않고 거절 | `backend/services/demo.py` `match` |
| CI | 대화 DB 시험이 DB 미설정으로 건너뛰지 않음 | `.github/workflows/ci.yml:30` `TEST_THREAD_DATABASE_URL` |

Out of Scope: 기록하지 않은 질문의 답, 데모 성공률을 실제 모델 품질로 집계하는 일, 전체 코퍼스 재배포, 실제 주문.

## What

### Happy Path

1. 데모 사용자 A 또는 B로 로그인한다(`DEMO_MODE=1`, 비밀번호 없음).
2. 데모 회로로 프로젝트를 만들고 기록 질문이 있는 부품을 고른다. 화면이 `GET /api/demo-questions`로 질문 버튼을 보인다.
3. 버튼이 기록한 질문·사용 조건을 새 대화의 첫 질문으로 보낸다. 조건 질문(`v3-01` · `demo-ask` · `demo-find` · `demo-notsuff`)에는 기록한 답으로 재개한다.
4. 서비스가 실제와 같은 멀티 에이전트 그래프를 돌리고, LLM 호출만 기록에서 꺼낸다.
5. 완료된 판정의 후보를 승인하고(201, 같은 승인은 409) 견적을 저장한다. 승인 · 견적은 재생이 아니라 서비스의 승인 API가 처리한다([scripts/demo/DEMO.md](../../scripts/demo/DEMO.md)).

### Edge Case

| 입력 | 결과 | 근거 |
|---|---|---|
| 기록에 없는 회로·대상·질문·조건 | 422, 데모 질문 목록을 문구에 담음 | `demo.refusal`, `memory_service.py:354-357` |
| 같은 대화의 두 번째 질문 | 스트림 뒤 `failed`(첫 질문으로만 재생) | `memory_service.py:422` |
| 기록과 다른 재개 답 | 거절 | `memory_service.py:469` |
| 기록 파일 없음 | 서버는 기동, 분석 요청과 `GET /api/demo-questions`는 503 | `demo.questions`, `demo.service_chat` |
| 확인을 통과했으나 기록에 없는 호출 | 실제 LLM으로 넘기지 않고 노드 이름을 담은 503(`ReplayMiss`) | `demo.replayer` |
| `DEMO_REPLAY=1`이고 `DEMO_MODE`가 1이 아님 | 설정 오류 | `demo.enabled` |
| `DEMO_MODE=1`만 켬 | 재생 없이 실제 LLM 사용(평가·실제 모델 확인용) | `demo.enabled` |
| 재생 모드가 아닐 때 `GET /api/demo-questions` | 404 | `backend/api/conversations.py:165-171` |

## How

### 기록과 재생

- 기록 파일: `data/demo/recordings/calls.jsonl`(호출 한 줄: `sha256`, `node`, `schema`, `response`)와 `outcomes.json`(질문별 입력·경로·답·판정·거절 코드·재개 값, DB 지문).
- 찾기 키: (노드, system, user, schema 이름)을 JSON 목록으로 묶은 sha256(`demo.call_key`).
- 기록 실행·재생 대조: `scripts/demo/record_demo.py`(`record`, `replay`). 방법은 [scripts/demo/DEMO.md](../../scripts/demo/DEMO.md).
- 서비스 조립: `memory_service.py:125,296` — 재생 모드는 `demo.service_chat()`을 LLM 호출 함수로 쓰고, Store를 그래프에 넘기지 않으며(`:310`) 웹 검색(Exa)을 켜지 않는다(`:303`). 검색은 BM25만 쓴다(SPEC 7절).
- 가격 API는 Mouser를 부르지 않고 `available: false`를 돌려준다(SPEC 7절, ADR 0009).
- 데모 코퍼스: compose `corpus-load`가 `data/demo/snapshot/`을 로컬 DB에 넣는다(`docker-compose.yml:42-52`). 규모와 출처는 [SNAPSHOT.md](../../data/demo/snapshot/SNAPSHOT.md).

### 평가자 확인 경로

- 새 질문 엔드포인트는 없다. 일반 대화 API(`/api/threads/{id}/runs` 등)를 그대로 쓴다. 경로 목록은 [SPEC.md](../../SPEC.md) 4절.
- 사용자 분리 확인은 데모 사용자 A와 B를 쿠키가 다른 창에서 각각 열어 본다. 다른 사용자의 thread·run은 404다([user-thread-memory.md](user-thread-memory.md)).
- 단계별 지연과 trace 전달 결과는 `analysis_events`(`stages`, `trace_id`, `trace_delivery` 열)에 남는다(`memory_service.py:386`). 상세는 SPEC 7절의 Langfuse 줄.

## AC

| AC | Given-When-Then | 시험 |
|---|---|---|
| AC-01 | 기록 호출을 기록한 뒤 재생하면 같은 그래프 결과가 나온다 | `tests/services/test_demo_replay.py::test_record_then_replay_gives_the_same_graph_result` |
| AC-02 | 기록에 없는 호출은 거절 답이 아니라 노드 이름을 담은 오류로 멈춘다 | `test_miss_fails_closed_with_the_node_name_instead_of_a_refusal` |
| AC-03 | 같은 프롬프트에 단어 하나가 다르면 재생하지 않는다 | `test_same_prompt_with_a_different_word_is_a_miss` |
| AC-04 | 기록 줄에 호출 칸 밖의 값(키 등)이 없다 | `test_recorder_writes_only_the_call_fields_and_calls_once_per_key` |
| AC-05 | 기록 파일이 없어도 서버가 서고 분석은 503이다 | `test_missing_recording_is_503_and_the_server_still_builds_its_chat` |
| AC-06 | 같은 회로·대상·질문·조건만 기록 질문으로 받는다 | `test_recorded_questions_match_only_the_same_circuit_target_question_and_conditions` |
| AC-07 | 기록 질문마다 같은 회로의 React 데모 프로젝트가 있다 | `test_every_demo_question_has_a_react_demo_project_with_the_same_circuit` |
| AC-08 | 서비스가 판정·조건 인터럽트·기록한 답 재개를 재생한다 | `test_service_replays_a_recorded_judgement_with_interrupt_and_recorded_resume` |
| AC-09 | 실행 중 기록 누락은 숨은 대체 없이 노드 이름을 담은 503이다 | `test_replay_miss_during_a_run_is_a_503_naming_the_node_not_a_hidden_fallback` |

## 구현 상태

| 항목 | 상태 | 근거 |
|---|---|---|
| 기록 응답 재생, 질문 대조, `GET /api/demo-questions` | 구현 | `backend/services/demo.py`, `backend/api/conversations.py:165` |
| 기록 10개 질문(회로 6곳, 호출 18줄, 기록일 2026-11-12) | 구현 | `data/demo/recordings/outcomes.json`, [scripts/demo/DEMO.md](../../scripts/demo/DEMO.md) |
| 대화 DB 시험 CI 연결 | 구현 | `.github/workflows/ci.yml:30` |
| 데모·실제 모델 구분을 화면에 표시 | 미구현 | SPEC 7절 |

## 한계

- 기록에 없는 질문은 키 없는 모드에서 재생되지 않는다: 기록 질문과 다른 회로 · 대상 · 질문 · 조건은 422(데모 질문 목록), 확인을 통과했는데 프롬프트나 DB가 기록 때와 달라 기록에 없는 호출이 나오면 503 `UNAVAILABLE`(노드 이름 포함). 2026-11-13 main에서 기록 질문 5개가 모두 이 503으로 멈췄고(코드가 기록 뒤에 바뀜), 11-12 재기록으로 풀었다.
- 재생은 기록한 질문에 같은 답을 내는 것만 보인다. 새 질문의 품질, 실제 모델 정확도, 운영 성능은 측정하지 않는다.
- 배포 환경에서 평가용 계정으로 한 HTTP·화면 전체 흐름의 실행 결과는 이 문서가 근거로 갖고 있지 않다. 단계 지연 표와 Langfuse 화면 증거는 [thread-memory-operations-review.md](../research/thread-memory-operations-review.md)와 [docs/GATES.md](../GATES.md)가 다룬다.
- CI에서 외부 transport를 차단해 호출 0건을 검증하는 시험은 확인하지 못했다.
