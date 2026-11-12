# 필수 게이트 자기 점검

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: `6707002`
- 정본 여부: 정본(게이트 증거). 배포 리비전은 비정본(정본: [README.md](../README.md) 맨 위 표). 게이트 정의의 정본은 3차 프로젝트 가이드
- 관련 문서: [README.md](../README.md), [SPEC.md](../SPEC.md), [EVAL_REPORT.md](../EVAL_REPORT.md), [evals/results/d10/README.md](../evals/results/d10/README.md)

게이트는 점수가 아니라 못 지키면 고정으로 깎이는 조건이다. 가산점은 7개를 모두 충족한 조만 받는다. 이 문서는 게이트마다 상태, 증거 경로, 확인 못 한 것을 적는다. 외부 DB · 배포 · 대시보드의 날짜가 적힌 결과는 그 시점의 스냅샷이다.

## 상태 표기

`미착수` / `진행 중` / `충족` / `증거 보강 필요` 중 하나로 적고, 충족이면 증거 링크(파일, PR, 대시보드)를 같이 적는다. 링크 없는 충족은 인정되지 않는다.

## 게이트 표

| 게이트 | 증명하는 곳 | 평가자가 확인하는 방법 | 상태 |
|---|---|---|---|
| G1 배포 주소 | README 맨 위 표의 배포 주소 | 평가용 계정으로 접속해 핵심 시나리오를 끝까지 본다 | 진행 중 |
| G2 한 줄 기동 | `docker-compose.yml`, `.env.example`, 데모 모드 | 새 clone에서 `docker compose up`, 10분 안에 뜨는지 실측 | 진행 중 |
| G3 코퍼스 | `data/manifest.jsonl`, `data/corpus/` | 서로 다른 청크(본문 sha256 기준) 1만 개 이상, 문서 50건 이상, 파싱 1종 이상 | 증거 보강 필요 |
| G4 에이전트 | `backend/graph/`, `backend/multi_agent/`, `backend/auth.py`, `backend/graph/memory.py` | 코드와 시연. 평가용 계정 2개로 대화와 기억이 섞이지 않는지 | 진행 중 |
| G5 평가 | `evals/`, `EVAL_REPORT.md` 2장, 3장 | 평가셋 50건 이상(동결 시점 기준, 관련과 비관련 각각 절반), 개선 전후 두 번 이상, 차이는 문항 목록과 함께 | 진행 중 |
| G6 트레이스 | Langfuse 프로젝트, `EVAL_REPORT.md` 7장 | 대시보드에서 트레이스와 평가 점수가 연결되어 있는지 | 진행 중 |
| G7 제출물 | README, `.env.example`, `docs/deliverables/` | 비밀값 커밋 없음, 3분 이내 시연 영상(정상 경로와 실패 경로) | 진행 중 |

## 게이트별 증거

### G1 배포 주소

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 배포 리비전 | [README.md](../README.md) 표 | `docs/worklog/jeongun.md` 11-12 항목 |
| 리비전 `sojafit-api-e0a5e30`(2026-11-12)에서 측정 | `/health` 200, 가입 · 데모 로그인 404(`DEMO_MODE=0`). 인증 통합 PR #109(커밋 `3152ffc`)는 이 리비전보다 뒤라, 이후 코드는 `POST /api/auth/signup`을 `DEMO_MODE`로 막지 않는다([SPEC.md](../SPEC.md) 4절) | `docs/worklog/jeongun.md` 11-12 항목 |
| 새 DB 전환 후 스모크(2026-11-11, 리비전 `sojafit-api-27a410d-live`) | 0% 점검 주소 28/0/0(통과/실패/건너뜀), 100% 전환 뒤 기본 주소 28/0/0. 구글 로그인 실제 왕복 확인. DB는 새 Supabase 프로젝트(서울, Postgres 17.11), 기준선 SQL과 코퍼스 4표(청크 51,967행)만 이전 | [smoke_newdb---sojafit-api-q5lzmlc4wq-du.a.run.app_2026-11-11_041537.json](../scripts/results/smoke/smoke_newdb---sojafit-api-q5lzmlc4wq-du.a.run.app_2026-11-11_041537.json), [smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_042439.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_042439.json) |
| 같은 날 앞선 두 실행 | 2/4/22, 19/1/8. B 계정 비밀번호 입력 문제로 실패(서비스 문제 아님) | [_042105.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_042105.json), [_042119.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-11_042119.json) |
| 옛 DB 기준(2026-11-10) 배포 주소 점검 | 리비전 `sojafit-api-b884849` 23단계 통과 · 실패 0 · 건너뜀 0(31.0초, 실제 LLM): 로그인 → 데모 회로 프로젝트(v3-01) → 조건 질문 정지 → 재개 → 승인 201 · 같은 승인 409 → 견적 → 계정 B의 A 자료 404 → 범위 밖 질문 거절 | [..._2026-11-10_225316.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-10_225316.json) |
| 같은 날 28단계 재점검 | 리비전 `sojafit-api-716c6d6`, 28/0/0. 승인 · 견적 · 승인 사례까지 계정 격리 확인 | [..._232639.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-10_232639.json), [..._232814.json](../scripts/results/smoke/smoke_sojafit-api-559369539072.asia-northeast3.run.app_2026-11-10_232814.json) |
| 되돌리기 리비전 | `sojafit-api-716c6d6`(옛 DB 비밀 사용) | `docs/worklog/jeongun.md` 11-11 항목 |
| 배포 Mouser 키 | 없음. 가격 조회는 `available:false` | 11-10 점검 기록 |

확인 못 한 것:

| 항목 | 이유 |
|---|---|
| 리비전 `e0a5e30`에서의 스모크 재실행 | 최신 일반 스모크가 2026-11-11 042439이다. `aa14abc`(11-12 12:44, `DEMO_MODE=0`에서 데모 회로 생성 API 차단) 이전 코드의 값이다. 스모크 시나리오가 데모 회로 프로젝트(v3-01)로 시작해 `DEMO_MODE=0` 배포에서 그대로 재현되는지는 스크립트로 확인하지 않았다 |
| #109 이후 코드의 배포 동작 | 가입 · Google 연결 변경이 배포되지 않았다 |
| 서버 로그의 Langfuse `Failed to export spans 403 Forbidden` | 옛 리비전에서도 11-10부터 났고 원인을 찾지 못했다 |

### G2 한 줄 기동

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 측정 조건 | 이미지 0개 · 볼륨 0개인 빈 Docker 엔진(`docker:dind` 29.9.3)에 커밋 `5631309`(`jeongun`)를 번들에서 clone, `.env` 없이 `docker compose up -d` 한 줄(2026-11-10) | `scripts/results/smoke/smoke_localhost-18000_2026-11-10_055128.json`(맥), `_055423.json`(WSL) |
| 맥(Apple M2, arm64) | `/health` 200 55.6초, 데모 A 로그인 200 55.7초, `scripts/smoke/http_smoke.py --demo --refusal` 23단계 통과 62.9초 | 위와 같음 |
| WSL2(i9-12900KF, x86_64, WSL 안 Docker 29.1.3 위의 dind) | `/health` 59.8초, 로그인 59.9초, 스모크 23단계 통과 67.5초 | 위와 같음 |
| 기동되는 서비스 | db · thread-setup · corpus-load(42문서 · 청크 1,556개) · api가 두 컴퓨터 모두 정상 | 위와 같음 |
| 임베딩 · 리랭커 | API 호출(Voyage)이라 로컬 모델 내려받기가 없다. 데모 모드의 검색은 BM25만 쓴다 | [SPEC.md](../SPEC.md) 6 · 7절 |

확인 못 한 것:

| 항목 | 이유 |
|---|---|
| 커밋 `e928d59`(11-11) 이후의 기동 시간 | 이 커밋이 `Dockerfile`에 `kicad libcairo2` 설치를 추가했다. 기동 시간 재측정이 없다 |
| Windows Docker Desktop | 확인하지 않았다 |
| 최종 main의 새 clone 기동 | 제출 직전에 다시 잰다 |
| WSL의 GitHub clone 시간 | 자격 증명이 없어 재지 않았다. 맥은 main clone 3.6초(저장소가 비공개라 저장된 자격 증명으로 받음) |

### G3 코퍼스

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 문서 수 | 1,360건 | `data/manifest.jsonl` 1,360행, `evals/results/chunking/v4h-2026-11-08/manifest.jsonl` 1,360행 |
| v4h 청크 | `cards` 51,967, `distinct_text` 51,967(청커 `tsc-v4h-2026-11-08`). 게이트 1만 개 기준 초과 | [summary.json](../evals/results/chunking/v4h-2026-11-08/summary.json), [corpus_v4h_fingerprint_2026-11-12.md](../evals/results/d10/corpus_v4h_fingerprint_2026-11-12.md) |
| 결과 파일 sha256 | `manifest.jsonl` · `summary.json` · `table_suspects.jsonl` | `evals/results/chunking/v4h-2026-11-08/SHA256.txt` |
| 새 Supabase 프로젝트 | 문서 1,360 · 청크 51,967 · 임베딩 51,967(옛 운영 DB에서 복사할 때 센 값, 2026-11-11) | `docs/worklog/jeongun.md` 11-11 항목 |
| v1 manifest | 문서 1,360행, 청크 합 52,244, 서로 다른 본문 45,898(외부 스냅샷). v4h와 서로 다른 버전이라 섞어 세지 않는다 | `data/manifest.jsonl` |
| 파싱 | Docling 2.145.0 + pdfplumber 대조 | [EVAL_REPORT.md](../EVAL_REPORT.md) 1-1절 |

확인 못 한 것:

| 항목 | 이유 |
|---|---|
| 청크별 sha256 목록 또는 DB 행 수 조회 결과와 열람 방법 | 저장소에 없다. `chunks.jsonl` 본문은 lab에만 있다 |
| 운영 DB에서 `sha256(본문)`을 다시 센 값 | `distinct_text`는 청킹 산출물의 서로 다른 본문 수다 |
| 옛 운영 DB가 52,244에서 51,967로 바뀐 날짜와 이유 | 작업 기록에서 찾지 못했다 |
| 새 clone에서 청킹 전체 재실행 | `chunks.jsonl`이 저장소에 없어 불가 |

### G4 에이전트

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 서비스 그래프 | D5 멀티 그래프(Supervisor + RAG 에이전트 · Spec 에이전트). D4 v2 단일 그래프는 비교 기준선 | `backend/multi_agent/build.py`, `backend/graph/build.py` |
| 영속 체크포인트 · 승인 · 견적 | 사용자별 분석 thread(PostgreSQL 체크포인트, 조건 질문 interrupt · 재개, 판정 승인)가 서비스에 있다(PR #73 이후) | `backend/conversations/memory_service.py` |
| 배포 주소 스모크(2026-11-10~11) | 조건 질문 정지 `requires_input` → 재개 `completed` → 승인 201 · 같은 승인 409 → 견적 저장. 계정 B가 A의 프로젝트 · thread · run · 견적 · 승인을 읽거나 쓰면 404 | G1 증거의 28단계 JSON |
| 로컬 compose 재시작 복원(2026-11-09, `jeongun-8` `f6b6d7e`) | 조건 질문에서 멈춘 대화가 `docker compose restart api` 뒤에도 WAITING, 답하고 재개하면 DONE. 같은 승인 요청 두 번은 둘 다 200이고 DB 승인 원본은 1건. 데모 사용자 B는 A의 대화 조회 · 승인이 404. 시험 14개 통과 | [local_g4_isolation_2026-11-09.json](../evals/results/threads/local_g4_isolation_2026-11-09.json), `tests/api/test_http_restart.py` |
| 사용자 사실 기억 | 사용자 사실 3칸을 Store `(user_id, "profile")`에 두고 문장 임베딩 색인으로 찾는다(`backend/conversations/profile.py`). 순위 · 사용자 격리 · 수정 뒤 재임베딩 · 삭제는 결정적 가짜 임베딩으로 DB 시험 통과. 키 없는 로컬 compose에서 저장 · 사용자 격리 · 남의 id 거절(422) 확인 | [test_profile.py](../tests/conversations/test_profile.py), [test_threads.py](../tests/api/test_threads.py) |
| 변이 확인 | 아래 표 9건 | [mutation_2026-11-12.md](../evals/results/d10/mutation_2026-11-12.md) |

확인 못 한 것:

| 항목 | 이유 |
|---|---|
| 배포 서버 재시작 뒤 복원 | 로컬 compose에서만 확인했다 |
| 현재 코드에서 재시작 뒤 재개와 계정 분리 재기록 | 위 로컬 기록(11-09) 뒤 `backend/conversations/memory_service.py`가 바뀌었다(최근 변경 `e0a5e30`, `280df84`, `c42273f`) |
| 배포 DB에서 실제 Voyage 임베딩으로 한 사용자 기억 의미 검색 | 확인하지 않았다. 키 없는 로컬 compose의 검색은 순위 없는 목록이다 |

### G5 평가

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 기준 평가셋 | v3 50건(관련 25 · 비관련 25, 2026-11-10 동결). v1 50건(11-02), v2 70건(11-03)도 동결 | `evals/FROZEN.json`, [ADR 0015](adr/0015-평가셋-v3를-새로-만들고-청킹부터-다시-잰다.md) |
| 개선 전후 비교 | 3-A 검색 5단계, 3-B 판정 길 8단계, 3-C v3 검색 길 2단계, 3-D 현재 스택 확인. 달라진 문항 목록과 회귀 문항 포함 | [EVAL_REPORT.md](../EVAL_REPORT.md) 3절 |
| v3 현재 값 | 50/50 | `evals/results/graph/2026-11-12-d9-improve2/set1.json` |
| 검색 기준선(v1) | 하이브리드 Recall@5 0.737 · MRR 0.649 | `evals/results/retrieval/retrieval_baseline_2026-11-03.json` |
| 사전 등록 | 바꾸기 전 기대를 기록 | `evals/guides/preregister.md` |

확인 못 한 것:

| 항목 | 이유 |
|---|---|
| v3 문항의 검색 Recall@5 · MRR | 측정하지 않았다(EVAL_REPORT 12절) |
| 3-C 14행의 원시 결과 | 원시 미보관(EVAL_REPORT 12절) |
| 3-A 5행(비트 후보)에서 기대 중 두 항목 | 합계 ±0.02와 시간 3배 이상은 기대와 달랐다. 유지를 정한 기록이 없다(EVAL_REPORT 3절 5행) |

### G6 트레이스

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 평가 실행의 점수 연결 | 그래프 평가 실행기(`evals/runners/run_graph.py`)가 단계 · 토큰 · 비용 · 실행 점수 · 답 5지표(`answer_metric`)를 트레이스 점수로 기록. 동결 v2 70문항 실행(#31, 11-04)에서 트레이스 70개와 `answer_metric` 70건이 결과 파일과 맞음 | `evals/guides/preregister.md` #31 결과, `evals/results/graph/` |
| 반복 평가 | v3 50문항 4세트(#50)가 세트마다 Langfuse 세션 하나에 트레이스 50개와 문항 점수를 남김 | [EVAL_REPORT.md](../EVAL_REPORT.md) 7장 |
| 서비스 분석 트레이스 | `user_id`(사용자) · `session_id`(대화)를 붙이고 질문 · 답 글은 보내지 않음(시험으로 확인) | `tests/services/test_langfuse_prompts.py` |
| Skill 대표 흐름 | 대표 4건 · 직접 생성 13건의 generation 23개를 API로 확인, 상황별 기준 12/13 충족 | `evals/results/skill/skill_tool_summary_2026-11-03.json` |
| 느림 원인 사례 | 2건과 LLM 단계별 시간 · 비용 | [EVAL_REPORT.md](../EVAL_REPORT.md) 7 · 8장 |

확인 못 한 것:

| 항목 | 이유 |
|---|---|
| 대시보드 스크린샷 3장(트레이스 상세 1장 포함) | `docs/deliverables/langfuse/`에 `.gitkeep`만 있다. 작업 원시는 `evals/results/graph/2026-11-12-d9-langfuse-capture/` |
| 배포본 서비스 분석 트레이스의 Langfuse 수신 | 확인하지 못했다(G1의 403 오류) |
| 현재 Skill 실행 UI | 확인하지 않았다 |

### G7 제출물

| 항목 | 값 | 증거 경로 |
|---|---|---|
| 시연 스크립트 | 초안(정상 · 실패 컷) | [demo_script.md](deliverables/demo_script.md) |
| 실패 분석 | 있음 | [failure_analysis.md](deliverables/failure_analysis.md) |
| AI 도구 사용 기록 | 있음 | [ai_tools_log.md](deliverables/ai_tools_log.md) |
| 포트폴리오 | 하정운 1건 | [portfolio-jeongun.md](deliverables/portfolio-jeongun.md) |

확인 못 한 것(없는 것):

| 항목 | 상태 |
|---|---|
| 시연 영상 파일 | 없음 |
| Langfuse PNG | 없음 |
| 최종 비밀값 검사 | 없음 |
| 다른 조원 포트폴리오(오세창 · 심태현) | 없음 |

## 변이 확인

핵심 코드를 한 줄 깨뜨렸을 때 테스트가 실제로 실패하는지 확인한 기록이다(G4 · G5). 재작성 횟수 상한 테스트가 상수끼리 비교하면(`assert n == MAX_REWRITES`) 상한을 99로 올려도 통과하므로 리터럴과 비교한다(`assert n == 2`).

| # | 깨뜨린 곳 (파일, 한 줄) | 실패해야 하는 테스트 | 실제로 실패했는가 | 확인한 날 |
|---|---|---|---|---|
| 1 | `backend/graph/build.py` 24행 `MAX_TRIES = 2` → `MAX_TRIES = 99` (재검색 횟수 상한 무력화) | `tests/graph/test_graph_rewrite.py::test_after_grade_rewrites_once_then_refuses`, `tests/graph/test_graph_build.py::test_still_no_pass_refuses_after_two_searches` | 실패 (`AssertionError: assert '재작성' == '거절'`, `StopIteration`, 원복 후 통과) | 2026-11-03 |
| 2 | `backend/graph/nodes.py` 270행 `other_part_row` 반환식을 `return False`로 변경 (같은 문서 내 다른 품번 행 결정적 필터 제거) | `tests/graph/test_graph_grade.py::test_other_part_row_dropped_before_llm` | 실패 (`AssertionError: {'passed': [1, 2, 3, 4]} != {'passed': [2, 3, 4]}`, 1N5817 행 `1`번 통과로 실패, 원복 후 통과) | 2026-11-03 |
| 3 | `backend/graph/nodes.py` 460행 `generate`의 `"fake_citations": sorted(cited - valid)` → `[]` (없는 근거 번호 인용 검출 무력화) | `tests/graph/test_graph_generate.py::test_generate_counts_fake_and_uncited` | 실패 (`AssertionError: {'fake_citations': []} != {'fake_citations': ['999']}`, 원복 후 통과) | 2026-11-03 |
| 4 | `backend/graph/build.py`: 검색 상한을 2회에서 3회로 변경 | `tests/graph/test_graph_build.py::test_still_no_pass_refuses_after_two_searches` | 실패(세 번째 채점에서 `StopIteration`), 원복 후 통과 | 2026-11-03 |
| 5 | `backend/graph/nodes.py`: MCP 장애의 `retrieval_error`를 `None`으로 변경 | `tests/graph/test_graph_build.py::test_retrieval_failure_is_not_reported_as_empty_corpus` | 실패(`None != {"kind": "timeout"}`), 원복 후 통과 | 2026-11-03 |
| 6 | `backend/graph/build.py`: MCP 장애도 채점으로 분기 | `tests/graph/test_graph_build.py::test_retrieval_failure_is_not_reported_as_empty_corpus` | 실패(path에 불필요한 `채점` 추가), 원복 후 통과 | 2026-11-03 |
| 7 | `backend/multi_agent/supervisor.py` `check_node`: 종합 숫자 검사 `problem = bool(…)` → `problem = False` | `tests/multi_agent/test_build.py::test_synth_that_invents_a_number_is_refused_by_the_check` | 실패(`KeyError: 'refusal_reason'`), 원복 후 깨끗 | 2026-11-12 |
| 8 | `backend/multi_agent/supervisor.py` `_judgement_reply` 첫 줄 `return None` | `tests/multi_agent/test_supervisor.py::test_partial_judgement_does_not_fall_back_to_unsafe_prose` (single · synth) | 실패(문서 사용 권고가 최종 답에 남음 / synth fallback), 원복 후 깨끗 | 2026-11-12 |
| 9 | `backend/multi_agent/contracts.py` `MAX_AGENT_RUNS = 6` → `99` | `tests/multi_agent/test_contracts.py::test_limits_match_agreed_numbers` | 실패(`99 != 6`), 원복 후 깨끗. (같은 변경으로 `test_collect_refuses_over_the_agent_limit`는 상수를 쓰므로 통과) | 2026-11-12 |

원시 로그: [mutation_2026-11-12.md](../evals/results/d10/mutation_2026-11-12.md). D10 재현 · 기준 미달 출력 · 코퍼스 지문: [evals/results/d10/README.md](../evals/results/d10/README.md).

## G4 추가 확인

| 항목 | 상태 | 증거 |
|---|---|---|
| 승인 대기 상태를 영속 체크포인트에 저장하고 서버 재시작 뒤 복원 · 재개. 승인 전 부작용 없음, 같은 승인 요청 반복 시 실행 중복 없음 | 로컬 compose에서 확인(2026-11-09, `jeongun-8` `f6b6d7e`). 배포 주소에서는 확인하지 않음 | [local_g4_isolation_2026-11-09.json](../evals/results/threads/local_g4_isolation_2026-11-09.json) |
| 사용자별 DB Store에 기억 저장, 의미 검색 · 활용 · 잘못된 기억 수정. thread 체크포인트나 코퍼스 벡터만으로 사용자 장기 기억을 대신하지 않음 | 일부 확인. 저장 · 격리 · 수정 · 삭제는 가짜 임베딩 DB 시험과 로컬 compose에서 확인. 실제 Voyage 임베딩과 배포 DB에서의 의미 검색은 확인하지 않음 | [test_profile.py](../tests/conversations/test_profile.py), [test_threads.py](../tests/api/test_threads.py) |
