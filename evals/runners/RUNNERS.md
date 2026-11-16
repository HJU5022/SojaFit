# runners

## 역할

- 이 폴더: 평가셋 동결, 검색·그래프·Skill·Supervisor·인젝션 평가의 실행 코드를 둔다.
- 실행 위치: 저장소 루트. 모듈 실행은 `uv run python -m evals.runners.<이름>`. 컨테이너 전용 실행기(`embed_cards`, `run_embedding_grid`)는 [DOCKER.md](../docker/DOCKER.md)의 구성을 쓴다.
- 비용 열 표기: 무료 = 공급자 API 호출과 유료 모델 호출이 없는 경로. 유료 = OpenRouter·Voyage 등 공급자 API를 호출하는 경로. 한 실행기가 둘 다 가지면 경로별로 적는다.
- 넣는 것: 실행기(`run_*.py`), 채점기(`score_*.py`), 동결 스크립트(`freeze.py`), 집계·보고(`gate_report.py`, `report_*.py`), 준비·점검 도우미.
- 넣지 않는 것: 평가셋·동결 기록(`evals/`의 `dataset_v*.jsonl`, `FROZEN.json`), 평가 원시 결과(`evals/results/`), 명세·사전 등록(`evals/guides/`), 평가가 아닌 측정 스크립트(`scripts/`).
- 인젝션 실행기의 범위·승인·예산: 입력과 상한은 `data/corpus/injection_tests/baseline_cases.json`(`budget_assumptions`, 범위별 `execution_enabled`)이 정한다. 실측 결과와 사람 검토 수치는 [injection-results.md](../../docs/research/injection-results.md)에 있다.
- 담당: 평가

## 파일

`RUNNERS.md`는 이 문서다. 실행기마다 표의 한 행이다.

### 동결·집계

| 파일 | 측정·역할 | 실행 | 비용 | 쓰는 곳 |
|---|---|---|---|---|
| `freeze.py` | 평가셋 sha256·건수를 동결 기록에 적고, 동결 뒤 바뀐 파일을 검사 | `uv run python evals/runners/freeze.py dataset_v1.jsonl` / `... freeze.py --check` | 무료 | `evals/FROZEN.json` (이미 동결한 파일은 덮어쓰지 않음) |
| `gate_report.py` | `run_gate` 결과 세트(`set*.json`)를 기준표로 집계: 관련 정답률, 무관 올바른 거절률, 지어낸 답·틀린 답·과잉 거절 비율, 문서·쪽 Recall@5·MRR, 응답 시간 p50·p95 | `uv run python -m evals.runners.gate_report <평가셋 jsonl> <결과 폴더> [--min 0.95] [--max-error 0.05] [--p95 10]` | 무료 | `<결과 폴더>/report.json`. 기준 미달이면 종료 코드 1 |
| `score_answer.py` | 평가셋 문항과 그래프 실행 상태를 대조해 답변·거절 5지표(`cited_gold`, `wrong_citation`, `over_refusal`, `correct_refusal`, `hallucination_risk`)를 규칙으로 채점. [작업서](../../docs/experiments/answer-refusal-scorer.md) | `uv run python -m evals.runners.score_answer <평가셋 jsonl> <실행 결과 json> [채점 결과 json]` | 무료 | 세 번째 인자 경로(생략하면 화면 출력) |
| `score_compound.py` | 문항의 `parts`별 채점(답할 수 있는 부분은 정답 인용·판정 코드·찾기 후보, 답하면 안 되는 부분은 거절 여부). `run_gate`가 부름 | 단독 실행 없음 | 무료 | 호출한 실행기의 행 |
| `score_ragas.py` | reference 없이 Faithfulness·LLMContextPrecisionWithoutReference 값을 만듦. `run_gate`가 같은 trace에 점수로 붙임 | 단독 실행 없음 | 유료(판정 LLM 호출) | Langfuse trace 점수 |
| `stage_timing.py` | `run_gate`가 문항 행에 `stages`·`llm_call_log`·`voyage`를 쓰게 하는 기록기. 질문·답 본문은 담지 않음 | 단독 실행 없음 | 무료 | 호출한 실행기의 행 |

### 검색·그래프·판정

| 파일 | 측정·역할 | 실행 | 비용 | 쓰는 곳 |
|---|---|---|---|---|
| `run_retrieval.py` | 평가셋 관련 문항으로 `retrieve()`의 문서 Recall@k·MRR·Page Hit@k. 방식 `hybrid`(기본)·`dense`·`bm25`는 summary의 `method`에 기록. 질의 글은 문항의 `question` 키, 없으면 `input` 전체(`dataset_v1.jsonl`에는 `question`이 없어 `input` 전체). 질의 필드를 바꾸려면 먼저 [preregister.md](../guides/preregister.md)에 등록. 회로 근거만 있는 문항과 `candidate_find` 문항은 세지 않고 id만 기록 | `uv run python -m evals.runners.run_retrieval <평가셋 jsonl> <결과 json> [k] [method]` | `bm25`는 DB 읽기만. `hybrid`·`dense`는 임베딩 API 호출(유료) | 두 번째 인자 경로(관례 `evals/results/retrieval/`) |
| `run_retrieval_v3.py` | v3 평가셋의 검색 지표를 에이전트 검색 길 그대로 측정: 입력 읽기, 재작성(LLM 1회), 품번 필터 `retrieve(k=10)`. 문항에 `query`가 있으면 재작성을 부르지 않고 그 글로 검색한다(청킹 v1·v4h 비교는 `evals/inputs/rewrite_q3_v3.json`의 Q3를 `query`로 더한 파일을 씀, `evals/results/chunking/v1-vs-v4h-2026-11-13/README.md`) | `uv run python -m evals.runners.run_retrieval_v3 <평가셋 jsonl> <결과 json>` | 유료 | 두 번째 인자 경로 |
| `run_graph.py` | 평가셋 문항을 단일 그래프(`--multi`는 멀티 에이전트)로 끝까지 실행하고 문항별 지표·5지표 요약을 기록. 답변 문장·청크 원문은 저장하지 않음 | `uv run python -m evals.runners.run_graph <평가셋 jsonl> [문항 id ...] [--out <결과 json>] [--multi]` | 유료 | `--out`, 기본 `evals/results/graph/graph_<평가셋>_<날짜>.json`(같은 날 두 번째부터 시각 접미사) |
| `run_gate.py` | 멀티 에이전트로 평가셋을 여러 세트 연달아 하나씩 실행하며 문항 통과를 판정. 처음 실패한 문항이나 세트 p95 초과에서 멈추고 `--keep-going`이면 끝까지 실행. `parts`가 있는 문항은 `score_compound`로 채점. 환경변수 `GATE_WARMUP=1`은 세트 앞에 BM25·Voyage·MCP lookup을 데워 콜드 시간을 뺌, `RAGAS_ENABLED=0`은 RAGAS 점수만 건너뜀. 행의 `score_delivery=queued`는 전송 시도 상태이며 원격 수신 확인이 아님 | `uv run python -m evals.runners.run_gate <평가셋 jsonl> --out <결과 폴더> [--sets 3] [--p95 10] [--keep-going]` | 유료 | `<결과 폴더>/set<n>.json`, Langfuse trace 점수 |
| `run_judge_dev.py` | 판정 연습 문제를 멀티 그래프로 실행해 역할 정답률·판정 일치율을 측정 | `uv run python -m evals.runners.run_judge_dev <연습 문제 jsonl>` | 유료 | `evals/results/judge/judge_dev_<날짜-시각>.json`. 연습 문제 파일(`evals/samples/judge_dev.jsonl`)과 `evals/results/judge/`는 저장소에 없음 |
| `run_skill_pair.py` | 같은 준비 상태에서 Skill 유무 답변을 비교(preregister #17) | `DEMO_MODE=0 uv run python -m evals.runners.run_skill_pair <새 결과 폴더> [--max-usd 1.0] [--max-tokens 1024]` | 유료 | `<새 결과 폴더>`, 요약은 `evals/results/skill/` |
| `eval_grader.py` | 채점 노드의 정답 쪽 유지율·통과 판정 표·비관련 통과 0개 비율·쪽 재현율(preregister #34·#36). 하위 명령 `build`·`run`·`collect-r1` | `uv run python -m evals.runners.eval_grader run [--snapshot <json>] [--out <json>]` | `run`·`build` 무료. `collect-r1`은 운영 DB 읽기·Voyage·OpenRouter 호출(유료) | `run`의 기본 `evals/results/grader/grader_baseline_<날짜>.json`. 입력 스냅샷은 `evals/inputs/` |

### 검색 실험(preregister #16·#24~#28, 층별 재측정)

| 파일 | 측정·역할 | 실행 | 비용 | 쓰는 곳 |
|---|---|---|---|---|
| `run_retrieval_d3.py` | D3 공식 검색 측정(#24): v2 채점 19문항, 조건 E1~E8, 필터 끔, no_result 임계값, 탐색 격자. 하위 명령 `qrels`·`official`·`noresult`·`chunks`·`embed <변형>`·`gpu_embed`·`explore`(`--mode bgem3|bgem3late`, `--exps`, `--out` 등) | `uv run --with docling-core python -m evals.runners.run_retrieval_d3 <명령> [변형]` | 유료(질문 임베딩 `embed_texts`·Voyage rerank 호출 경로가 있음). `qrels`는 API 호출 없음 | `--out`, 기본은 코드가 정함. 청크·벡터는 저장소 밖 경로 인자(`--cards`, `--vectors`, …) |
| `run_retrieval_r1.py` | R1 검색 측정(#25·#28): 84문항, dev에서 264칸 순위, test에서 서비스와 1회 비교, `steps`는 단계별 재측정, `cands`는 S4에서 리랭크 전 후보 수만 50 → `--n-after`로 바꾼 84문항 짝 비교(사전 등록 2026-11-16). 하위 명령 `rewrite`·`qvec-api`·`gpu-qvec`·`requests`·`gpu-rerank`·`run`·`steps`·`cands` | `uv run python -m evals.runners.run_retrieval_r1 <명령>` | 유료(`rewrite`는 OpenRouter, `qvec-api`는 OpenAI·Voyage 임베딩, `cands`는 캐시에 없는 후보 묶음만 Voyage rerank-3, 상한 40회 · 300만 토큰). `gpu-*`는 GPU 연산 | `--out`, 기본 `evals/results/retrieval/r1_<날짜>.json` |
| `run_retrieval_service.py` | 서비스 경로 재측정(#26·#27·#28): 실제 `retrieve()`(`DEMO_MODE=0`)로 쪽 지표, 상위 5 대조, `retrieve()`·`rewrite()` 시간. `--stages N`은 단계별 시간과 rerank 토큰만. `--compare <정확 json> <비트 json>`은 DB 없이 두 결과 파일 비교 | `uv run python -m evals.runners.run_retrieval_service [--out <json>] [--prereg '#27'] [--stages N]` | 유료(운영 DB 읽기·Voyage·OpenRouter). `--compare`는 무료 | `--out`, 기본 `evals/results/retrieval/service_r1_<날짜>.json` |
| `run_retrieval_layers.py` | 검색 조합 층별 재측정 1~4층. 하위 명령 `queries`·`dump_queries`·`layer1`~`layer4`·`price`·`embed <모델>`. 입출력 폴더는 환경변수 `LAYERS_WORK`. OpenRouter 상한은 코드 상수 `CAP_OPENROUTER`. 해석: [retrieval-layered-rerun-2026-11-03.md](../../docs/research/retrieval-layered-rerun-2026-11-03.md) | `uv run python -m evals.runners.run_retrieval_layers <명령>` | 유료(`queries`·`layer*`·`embed`). `price`·`dump_queries`는 확인용 | `$LAYERS_WORK/out/`, `$LAYERS_WORK/inputs/` |
| `check_retrieval_db.py` | 층별 재측정 0층: 카드·벡터·정확 검색 상위 50·서비스 경로 상위 5를 로컬과 대조(읽기만, `DATABASE_URL`) | `uv run python -m evals.runners.check_retrieval_db` | 유료(임베딩 호출 가능) | `$LAYERS_WORK/out/layer0.json`, `$LAYERS_WORK/inputs/parts.json` |
| `report_retrieval_layers.py` | 층별 결과 파일에서 비교 C1~C11의 값을 뽑아 `report.json`으로 저장. import하면 바로 실행 | `uv run python -m evals.runners.report_retrieval_layers` | 무료 | `report.json`(층별 `out/` 폴더) |
| `benchmark_embeddings.py` | 프록시 표본([embedding_sample_v0.jsonl](../samples/embedding_sample_v0.jsonl))의 dense Recall@5·MRR·지연 | `uv run python -m evals.runners.benchmark_embeddings --model <키> [--sample <jsonl>] [--output <json>] [--batch-size 16]` | `text-embedding-3-small`만 API 호출(유료). 나머지는 로컬 모델 | `--output`, 관례 `evals/results/embedding/embedding_<모델>_proxy_<날짜>.json` |
| `embed_cards.py` | 카드를 실험 DB에 적재(`load`)하고 모델별로 임베딩(`<모델 키>`). 컨테이너 실행 | `python -m evals.runners.embed_cards load <chunks.jsonl>` / `python -m evals.runners.embed_cards <모델 키>` | `te3s`(공급자 API)는 유료. `st` 종류 모델은 로컬 연산 | 실험 DB(`EMBED_DB`), `/work/logs/embed_<키>.json` |
| `run_embedding_grid.py` | 임베딩 × 검색 방식 × 리랭커 × 질의 글 격자 본평가(#16). 컨테이너 실행 | `python -m evals.runners.run_embedding_grid <결과 이름> [모델 키 ...]` | 유료(리랭크·질문 임베딩 호출) | `/work/out/<결과 이름>.json`, `/work/out/rerank_cache.jsonl` |

### Supervisor 비교

| 파일 | 측정·역할 | 실행 | 비용 | 쓰는 곳 |
|---|---|---|---|---|
| `run_supervisor_models.py` | 동결 v2 70문항의 후보 5종 비교. 하위 명령 `plan`·`import-evidence`·`smoke`·`run` | `uv run python -m evals.runners.run_supervisor_models plan <출력>` / `run <출력> --model <후보> --max-usd <상한> --confirm-live` | `plan`·`import-evidence` 무료. `smoke`·`run` 유료 | 첫 위치 인자 경로. 1차 결과는 `evals/results/supervisor/2026-11-04-stage1-v1/` |
| `run_supervisor_jev.py` | Jev Decisions API 답을 평가 계약으로 바꿔 70문항 `plan`·`smoke`·`run` | `uv run python -m evals.runners.run_supervisor_jev run <출력> --max-usd <상한> --confirm-live` (`--run-index`는 `plan`) | `plan` 무료. 나머지 유료. 입력 비용 추정으로 다음 job을 막으므로 실제 지출의 절대 상한은 아님 | 첫 위치 인자 경로 |
| `report_supervisor_stage3.py` | 1~3차 원시 행에서 hash·분모·라우팅 일관성·3회 일치/flip을 재계산 | `uv run python -m evals.runners.report_supervisor_stage3 <출력 json>` | 무료 | 출력 json, `docs/research/supervisor-stage3-results.md`, `docs/research/supervisor-stage3-brief-report.md`(스크립트가 쓰지만 이 파일은 저장소에서 삭제했다. 다시 만들면 커밋하지 않는다) |
| `supervisor_prompt_v0_common.py` | V0 13건의 hash·건수 확인, 정답·id를 뺀 입력 생성, 네 필드·의미 일치 채점 | 단독 실행 없음 | 무료 | 호출한 실행기 |
| `run_supervisor_prompt_v0.py` | V0 13건을 Luna·Haiku에 같은 prompt로 실행. `plan`은 26-job manifest | `uv run python -m evals.runners.run_supervisor_prompt_v0 plan <출력>` / `smoke\|run <출력> --model <키> --max-usd --max-seconds --prompt-rate --completion-rate --confirm-live` | `plan` 무료. 나머지 유료 | 첫 위치 인자 경로 |
| `run_supervisor_prompt_v0_jev.py` | Jev Decisions의 typed answer 5개를 V0 네 필드로 바꿔 실행. `plan`은 13-job manifest | `uv run python -m evals.runners.run_supervisor_prompt_v0_jev plan <출력>` / `smoke\|run <출력> --max-calls --max-seconds --max-usd --confirm-live` | `plan` 무료. 나머지 유료 | 첫 위치 인자 경로 |
| `compare_supervisor_prompt_v0.py` | 세 후보의 dataset·의미 계약 hash와 case 집합이 같을 때만 네 필드 정확도·형식·의미·지연·usage 집계 | `uv run python -m evals.runners.compare_supervisor_prompt_v0 <출력 json> <결과1> <결과2> <결과3>` | 무료 | 출력 json |
| `import_supervisor_prompt_v0_langfuse.py` | 완료된 V0 결과를 모델 재호출 없이 Langfuse Dataset·Experiment로 가져옴 | `uv run python -m evals.runners.import_supervisor_prompt_v0_langfuse plan` / `import --confirm-langfuse-write` | `plan` 무료. `import`는 Langfuse에 쓰기(모델 호출 없음) | Langfuse. 영수증 `langfuse_import.json` |

### 인젝션·신뢰 경계

| 파일 | 측정·역할 | 실행 | 비용 | 쓰는 곳 |
|---|---|---|---|---|
| `plan_injection_baseline.py` | `baseline_cases.json`에서 110개 고정 job(정상 55·공격 55)과 준비 10턴, 공식 단가 스냅샷 기반 예상 청구·예약 상한 계산. 범위 옵션 `--exposure-only`·`--remaining-smoke`·`--t7-smoke`·`--t3-smoke` | `uv run python -m evals.runners.plan_injection_baseline --out <새 json> [범위 옵션]` | 무료 | `--out`(이미 있으면 실패) |
| `run_injection_baseline.py` | 인젝션 기준선 실행. 기본은 110개 `not_run` JSONL, `--simulate`는 실제 그래프에 가짜 모델·검색·SQL, `--execute --approval <승인 json>`은 승인 파일 검증을 통과해야 실행. 범위 옵션은 위와 같음 | `uv run python -m evals.runners.run_injection_baseline --out <새 jsonl> [--simulate \| --execute --approval <json>] [범위 옵션]` | 기본·`--simulate` 무료. `--execute`만 유료 | `--out`과 동명 `.meta.json`(이미 있으면 실패). 전용 DB는 환경변수 `INJECTION_BASELINE_DATABASES`·`INJECTION_EXPOSURE_DATABASES`·`INJECTION_T3_SMOKE_DATABASES`·`INJECTION_T7_SMOKE_DATABASES`·`INJECTION_REMAINING_SMOKE_DATABASES` |
| `injection_baseline_runtime.py` | 승인 실행 경로: 빈 loopback 전용 DB 적재, 실제 hybrid 검색·카드 도구·서비스 message 조립, 전체 공유 예약·바이트 한도 | 단독 실행 없음(`run_injection_baseline`이 import) | `--execute` 경로에서 유료 | 호출한 실행기의 출력 |
| `run_injection_preflight.py` | 인젝션 준비 검사: 오프라인 테스트 실행, `--local-db`면 빈 loopback DB 두 개에 소형 합성 코퍼스를 적재해 BM25 검색 확인. [작업서](../../docs/experiments/injection-baseline-preflight.md) | `uv run python -m evals.runners.run_injection_preflight --out <새 json> [--local-db]` | 무료 | `--out`(이미 있으면 실패) |
| `check_injection_result.py` | 저장한 인젝션 결과 JSONL(`evals/results/threads/injection_baseline_live_2026-11-11_03.jsonl`이 기본)이 기준(정상 55·공격 55·completed/live·빈 답 0·판정형 5기준 true·노출 전제)을 지키는지 확인. 위반이면 종료 코드 1. ci.yml이 실행 | `uv run python -m evals.runners.check_injection_result [<jsonl>]` | 무료(모델 호출·사람 채점 없음) | 화면 출력 |
| `run_judgement_bundle.py` | `judgement_bundle_v1`의 `plan`·`load`·`preflight`·`simulate`. 숫자 loopback + `injection_test_*` DB만 허용. `load`·`preflight`·`simulate`는 제거된 `db/011_part_specifications.sql`·`find_parts`를 써서 현재 코드에서 돌지 않고, `plan`과 예산 단위 시험만 유효 | `uv run python -m evals.runners.run_judgement_bundle plan --out <json>` | 무료(실제 모델 실행 옵션 없음) | `--out` |
| `run_thread_validation.py` | v2 1~4건 dry-run과 명시적 유료 실행. [운영 검증](../../docs/experiments/thread-memory-operations.md) | `uv run python -m evals.runners.run_thread_validation --ids <id ...> --out <새 json> [--execute]` | 기본 무료. `--execute` 유료 | `--out` |
| `run_trust_boundary.py` | D7 합성 공격 3건과 정상 대조군. `--execute`만 문서 에이전트를 실제 모델로 실행. 상한은 코드 `LIMITS` | `uv run python -m evals.runners.run_trust_boundary --out <새 json> [--execute]` | 기본 무료. `--execute` 유료 | `--out`(이미 있으면 실패) |
| `run_claim_consistency.py` | 고정 대조군 + C1 + C2 실제 모델 기준선. 상한은 코드 `LIMITS` | `uv run python -m evals.runners.run_claim_consistency --out <새 json> [--execute]` | 기본 무료. `--execute` 유료 | `--out` |
| `run_input_surfaces.py` | 다섯 입력 위치 호환성과 청크·값·질문 컴포넌트 실측. `--question-only`는 P4-N/P4-A만 별도 예산 | `uv run python -m evals.runners.run_input_surfaces --out <새 json> [--execute] [--question-only]` | 기본 무료. `--execute` 유료 | `--out` |
| `run_supervisor_guard_injection.py` | Supervisor 답 가드(`끝내기`) 켬/끔 짝 실측: 사례 11개(코퍼스 청크 · 에이전트 보고 · 질문 공격 · 정상 일상 대화) × 2회를 멀티 그래프(진짜 Supervisor · RAG 에이전트, 고정 카드, 판정 · 웹 · DB 없음)로 돌리고 같은 끝난 상태에 가드 켬/끔을 적용. 상한은 코드 `LIMITS`. [작업서](../../docs/experiments/supervisor-guard-injection-recheck.md) | `uv run --no-sync python -m evals.runners.run_supervisor_guard_injection --out <새 json> [--execute]` | 기본 무료. `--execute` 유료 | `--out`(이미 있으면 실패) |
