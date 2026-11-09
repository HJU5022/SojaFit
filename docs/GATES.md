# 필수 게이트 자기 점검

게이트는 점수가 아니라 **못 지키면 고정으로 깎이는 조건**입니다. 가산점은 7개를 모두 충족한 조만 받습니다. 정의의 정본은 3차 프로젝트 가이드이고, 이 표는 "이 저장소 어디에서 채우는가"를 적은 것입니다.

팀에서 매주 금요일에 아래 표를 갱신하세요. 아래 상태는 2026-11-09 저장소 코드와 문서에 근거하며, 외부 DB·배포·대시보드의 날짜가 적힌 결과는 당시 스냅샷입니다.

| 게이트 | 증명하는 곳 | 평가자가 확인하는 방법 | 지금 상태 |
|---|---|---|---|
| G1 배포 주소 | README 팀 정보의 배포 주소 | 평가용 계정으로 접속해 핵심 시나리오를 끝까지 본다 | 진행 중: 저장소에는 `/health`, `/login`, 비밀번호·Google 관리자 인증과 가격 조회 API가 있다. 11-05 작업 기록에는 0% 시험 리비전의 Google 인증까지 있으나 현재 배포 리비전·트래픽·평가 계정·핵심 시나리오는 이번 점검에서 재검증하지 않았다. 질문·판정·승인·견적 화면과 서비스 API는 아직 없다 |
| G2 한 줄 기동 | `docker-compose.yml`, `.env.example`, 데모 모드 | 새 clone에서 `docker compose up`, 10분 안에 뜨는지 실측 | 증거 보강 필요: 2026-11-09 `jeongun-8`(f6b6d7e)을 `.env` 없이 새 볼륨으로 `docker compose up --build` 하니 13초 만에 db · thread-setup(준비 완료) · api가 떴다(빌드 캐시 있음). 표는 public 20 · sojafit_agent 15개, 데모 사용자 A · B 2개, `/`는 200이었다. 캐시 없는 새 clone 10분 이내 실측은 아직이다 |
| G3 코퍼스 | `data/manifest.jsonl`, `data/corpus/` | 서로 다른 청크(본문 sha256 기준) 1만 개 이상, 문서 50건 이상, 파싱 1종 이상 | 증거 보강 필요: 저장소에는 v1 기준 1,360행 manifest(청크 수 합계 52,244)와 PDF 표본 3건만 있다. v1의 서로 다른 본문 45,898개는 11-01~02 외부 산출물·DB 스냅샷 이력이다. 최신 `main`은 v4h 청킹 코드와 저장소 밖 전체 실행 51,967카드·검색 103질의 기록을 포함하지만, 전체 입력·v4h 청크·요약 해시는 저장소에 없어 새 clone 재현과 에이전트 길 재측정 증거를 더 보강해야 한다 |
| G4 에이전트 | `backend/graph/`, `backend/multi_agent/`, `backend/auth.py`, `backend/graph/memory.py` | 코드와 시연. 평가용 계정 2개로 대화와 기억이 섞이지 않는지 | 진행 중: 로그인·서버 세션은 `main`에 있다(`backend/auth.py`, 11-02). 그래프는 D4 v2 단일 그래프([build.py](../backend/graph/build.py), 11-06: 사실 확인 → 7가지 라우팅 → 질문 종류별 길)와 D5 멀티 그래프([multi_agent/build.py](../backend/multi_agent/build.py), 11-05~06: Supervisor + 검색·판정·작성·검증 서브에이전트) 둘이다. 판정 에이전트([agents/judge.py](../backend/multi_agent/agents/judge.py))는 빠진 회로 값을 인터럽트로 한 번 묻고 같은 thread에서 재개하며, 체크포인터는 평가 실행기가 넘기는 메모리 체크포인터(`InMemorySaver`, [run_graph.py](../evals/runners/run_graph.py))뿐이다. 멀티는 판정 에이전트 없이 #38(11-05, 동결 v2 70문항)에서 쟀고, 판정 길과 D4 v2는 가짜 LLM·도구 시험만 했다([test_graph_build.py](../tests/graph/test_graph_build.py), [test_build.py](../tests/multi_agent/test_build.py)). 영속 체크포인트 DB, 견적서 승인 지점, 사용자별 thread·기억(`backend/graph/memory.py`는 부르는 곳 없음)은 아직 없다. 2026-11-09 갱신: PR #73으로 사용자별 분석 thread(PostgreSQL 체크포인트, 조건 질문 interrupt · 재개, 판정 승인)가 main에 들어갔다. `jeongun-8`에서 React 실행 · 재개를 이 서비스로 연결했고, 장기 기억을 사용자 사실 3칸(Store `(user_id, "profile")`, 의미 검색 색인)으로 바꿨다. 키 없는 로컬 compose에서 시험 14개 통과([local_g4_isolation_2026-11-09.json](../evals/results/threads/local_g4_isolation_2026-11-09.json)). 배포 주소 확인은 아직이다 |
| G5 평가 | `evals/`, `EVAL_REPORT.md` 2장, 3장 | 평가셋 50건 이상(동결 시점 기준, 관련과 비관련 각각 절반), 개선 전후 두 번 이상, 차이는 문항 목록과 함께 | 진행 중: 평가셋 v1 50건(11-02)과 v2 70건(11-03)을 동결했다(`evals/FROZEN.json`). 검색 베이스라인 3가지(`dense`·`bm25`·`hybrid`, `evals/results/retrieval/retrieval_{dense,bm25,baseline}_2026-11-03.json`)의 문항별 차이·실패 유형을 [retrieval-baseline-analysis.md](research/retrieval-baseline-analysis.md)에 정리했다(11-03). 그래프 답 5지표는 동결 v2 70문항으로 #31(D4 기준) → #35(프롬프트 영어) → #37(채점 Luna) → #38(멀티)을 한 번에 하나씩 바꿔 쟀다([preregister.md](../evals/guides/preregister.md), `evals/results/graph/`). D4 v2와 판정 길을 켠 측정은 #39 · #40 · #41 · #42에서 했다. 11-06: 기준 평가셋을 v3로 새로 만들고 청킹 결함을 고친 코퍼스부터 다시 재기로 했다([ADR 0015](adr/0015-평가셋-v3를-새로-만들고-청킹부터-다시-잰다.md)) |
| G6 트레이스 | Langfuse 프로젝트, `EVAL_REPORT.md` 7장 | 대시보드에서 트레이스와 평가 점수가 연결되어 있는지 | 진행 중: 그래프 평가 실행(`evals/runners/run_graph.py`)은 단계·토큰·비용과 실행 점수, 답 5지표(`answer_metric`)를 트레이스 점수로 기록한다. #31(11-04) 동결 v2 70문항에서 트레이스 70개와 `answer_metric` 70건이 결과 파일과 맞는 것을 확인했다([preregister.md](../evals/guides/preregister.md) #31 결과). #20 Skill 대표4건·직접 생성13건의 generation23개를 API 확인했고 상황별 기준12/13 충족(충돌1건 실패). 현재 Skill 실행 UI는 미확인. 기존 사용자 UI6장은 이전 등록 본문에만 해당 |
| G7 제출물 | README, `.env.example`, `docs/deliverables/` | 비밀값 커밋 없음, 3분 이내 시연 영상(정상 경로와 실패 경로) | 진행 중: 제출 문서 자리와 환경변수 예시는 있으나 현재 코드 기준 3분 시연 영상과 최종 비밀값 검사는 확인되지 않았다 |

## 상태 표기

`미착수` / `진행 중` / `충족` / `증거 보강 필요` 중 하나로 적고, 충족이면 **증거 링크**(파일, PR, 대시보드)를 같이 적으세요. 링크 없는 "충족"은 평가에서 인정되지 않습니다.

## 자주 놓치는 것

- G2: 평가자에게는 API 키가 없습니다. 키가 없으면 죽는 서비스는 G2를 못 넘습니다.
- G2: 로컬 모델(임베딩, 리랭커)을 쓰면 평가자 컴퓨터에서 내려받기가 막히거나 오래 걸립니다. `HF_HUB_OFFLINE=1`과 `local_files_only=True`를 쓰고, 모델 캐시 크기(예: KURE-v1 약 2.1GB, bge-reranker-v2-m3 약 2.1GB)를 README에 적으세요. 서버 기동 시 모델을 미리 올려(`warmup()`) 첫 질문이 느려지지 않게 합니다.
- G3: "청크 1만 개"는 서로 다른 청크입니다. 같은 문서를 복제하거나 약간 바꾼 것은 세지 않습니다. 본문이 같은 청크가 여러 문서에 있으면 한 개로 칩니다. v1 수치(52,244개 중 서로 다른 본문 45,898개)와 v4h 카드 51,967개는 서로 다른 버전이므로 섞지 않습니다. v4h의 서로 다른 본문 수와 재현 해시는 해당 전체 산출물의 `summary.json`·본문 sha256으로 다시 확인합니다.
- G4: 단일 에이전트로 되돌리는 것은 허용되지 않습니다. 11/6 중간 점검에서 분리를 확인합니다.
- G5: 한 번 재고 끝내면 미충족입니다. 어느 문항이 회귀했는지가 보여야 합니다. 차이가 1~4문항이면 "개선"이라 쓰지 말고 달라진 문항 목록을 적으세요.
- G5: 검색 결과를 후처리로 걸러 0~2개로 줄이면 "우연한 거절"이 생겨 점수가 실제보다 좋게 나올 수 있습니다. 검색 단계에서 필터를 걸거나, 후처리를 쓴다면 이 효과를 따로 보고하세요.
- G7: 시연 영상에는 잘 되는 경로만이 아니라 실패하는 경로도 들어가야 합니다.

## G4와 G5의 "통과"는 증거가 아닙니다: 변이 확인

테스트가 초록이라는 것은 아무것도 단언하지 않는 테스트도 초록이라는 뜻입니다. 핵심 코드를 **한 줄 깨뜨렸을 때 그 테스트가 실제로 실패하는지** 확인하고 기록하세요. 사례: 재작성 횟수 상한 테스트가 상수끼리 비교하면(`assert n == MAX_REWRITES`) 상한을 99로 올려도 통과합니다. 리터럴과 비교해야(`assert n == 2`) 상한 변경을 잡습니다. AI 에이전트가 "변이를 잡았다"고 보고해도 직접 확인하세요.

3건 이상을 적습니다.

| # | 깨뜨린 곳 (파일, 한 줄) | 실패해야 하는 테스트 | 실제로 실패했는가 | 확인한 날 |
|---|---|---|---|---|
| 1 | `backend/graph/build.py` 24행 `MAX_TRIES = 2` → `MAX_TRIES = 99` (재검색 횟수 상한 무력화) | `tests/graph/test_graph_rewrite.py::test_after_grade_rewrites_once_then_refuses`, `tests/graph/test_graph_build.py::test_still_no_pass_refuses_after_two_searches` | 실패 (`AssertionError: assert '재작성' == '거절'`, `StopIteration`, 원복 후 통과) | 2026-11-03 |
| 2 | `backend/graph/nodes.py` 157행 `other_part_row` 반환식을 `return False`로 변경 (같은 문서 내 다른 품번 행 결정적 필터 제거) | `tests/graph/test_graph_grade.py::test_other_part_row_dropped_before_llm` | 실패 (`AssertionError: {'passed': [1, 2, 3, 4]} != {'passed': [2, 3, 4]}`, 1N5817 행 `1`번 통과로 실패, 원복 후 통과) | 2026-11-03 |
| 3 | `backend/graph/nodes.py` 236행 `generate`의 `"fake_citations": sorted(cited - valid)` → `[]` (없는 근거 번호 인용 검출 무력화) | `tests/graph/test_graph_generate.py::test_generate_counts_fake_and_uncited` | 실패 (`AssertionError: {'fake_citations': []} != {'fake_citations': ['999']}`, 원복 후 통과) | 2026-11-03 |
| 4 | `backend/graph/build.py`: 검색 상한을 2회에서 3회로 변경 | `tests/graph/test_graph_build.py::test_still_no_pass_refuses_after_two_searches` | 실패(세 번째 채점에서 `StopIteration`), 원복 후 통과 | 2026-11-03 |
| 5 | `backend/graph/nodes.py`: MCP 장애의 `retrieval_error`를 `None`으로 변경 | `tests/graph/test_graph_build.py::test_retrieval_failure_is_not_reported_as_empty_corpus` | 실패(`None != {"kind": "timeout"}`), 원복 후 통과 | 2026-11-03 |
| 6 | `backend/graph/build.py`: MCP 장애도 채점으로 분기 | `tests/graph/test_graph_build.py::test_retrieval_failure_is_not_reported_as_empty_corpus` | 실패(path에 불필요한 `채점` 추가), 원복 후 통과 | 2026-11-03 |

## G4 추가 확인

- [x] 승인 대기 상태를 영속 체크포인트에 저장하고 서버 재시작 뒤 복원·재개한다. 승인 전 부작용이 없고, 같은 승인 요청이 반복돼도 실행이 중복되지 않는지 확인한다.
  - 2026-11-09 키 없는 로컬 compose(`jeongun-8` f6b6d7e): 조건 질문에서 멈춘 대화가 `docker compose restart api` 뒤에도 WAITING이고, 답하고 재개하면 DONE이 됐다. 같은 승인 요청 두 번은 둘 다 200이고 DB 승인 원본은 1건이었다. 데모 사용자 B는 A의 대화 조회 · 승인이 404였다([local_g4_isolation_2026-11-09.json](../evals/results/threads/local_g4_isolation_2026-11-09.json)). 배포 주소에서는 아직 확인하지 않았다.
- [ ] 사용자별 DB Store에 기억을 저장하고 의미 검색·활용·잘못된 기억 수정을 확인한다. thread 체크포인트나 코퍼스 벡터만 저장한 것으로 사용자 장기 기억을 대신하지 않는다.
  - 2026-11-09 진행: 사용자 사실 3칸(소속 · 직무 · 선호 실장 방식)을 Store `(user_id, "profile")`에 두고 문장 임베딩 색인으로 찾는다(`backend/conversations/profile.py`). 분석 결과에 `profile_hints`로 쓰고, `/api/me/memory`로 고치고 지운다. 의미 순위 · 사용자 격리 · 수정 뒤 재임베딩 · 삭제는 결정적 가짜 임베딩으로 DB 시험을 통과했다([test_profile.py](../tests/conversations/test_profile.py), [test_threads.py](../tests/api/test_threads.py)). 키 없는 로컬 compose에서는 저장 · 사용자 격리 · 남의 id 거절(422)을 확인했고, 검색은 순위 없는 목록이었다. 실제 Voyage 임베딩과 배포 DB에서의 의미 검색은 아직 확인하지 않았다.
