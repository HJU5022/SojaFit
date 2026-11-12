# runners

## 역할

- `--t3-smoke`는 t3_smoke_v1의 T3 정상·공격/current 2작업만 선택한다. 독립 승인·INJECTION_T3_SMOKE_DATABASES의 새 injection_test_t3_* DB 2개·공유 $2/200시도/1200초를 사용한다. 전체110회는 계속 잠겨 있고 기존 스모크 승인은 재사용하지 않는다.

- 110건 실행기는 live 모드에서 Langfuse 키가 있고 추적이 활성화되면 기존 그래프 콜백을 연결한다. 항목별 trace_id/trace_url/trace_session/trace_status와 사례·반복·방어 조건을 남기며 T6 준비 턴도 같은 항목 트레이스에 묶는다. plan/simulate는 전송하지 않는다. 초기화/콜백/flush 오류는 평가 결과를 바꾸지 않으며 queued는 서버 수신 확인이 아니다. URL 조회만 실패하면 trace_url=null로 두고 추적은 유지한다. 승인·예산·입력·재시도 조건은 그대로이며 코드 해시 변경 후 기존 유료 승인 파일은 재사용할 수 없다.

- 수정본110회02는baseline_t2_controlled_v2/fixed_database_evidence_v1에서T2만새전용DB의공개6+보호1청크를본문해시대조후고정제공한다. 기존코퍼스/실측01은보존하고다른사례는실제검색을유지한다. 새독립승인/fixture해시/코드커밋과전체공유$15·2500·1800상한이필요하며자동재실행하지않는다.

- T2무료노출준비(2026-11-11): `run_injection_baseline.t2_context_preflight(data)`는원본fixture복사본에서정상/공격×current/ablated4작업만가짜공급자로검사한다. 기존synthetic_docs고정근거(자연검색아님)를실제문서입력렌더러에전달하고보호본문SHA·필터후Evidence영역·사실별ID·공격문·입력바이트를관찰한다. 원본110계획/유료게이트는불변,실모델방어점수는null이다. 이도우미에는live옵션이없고실제유료scope/승인은별도준비가필요하다.

- `--t7-smoke`는등록된t7_smoke_v1의T7정상·공격2작업/current만을선택한다. 독립승인과INJECTION_T7_SMOKE_DATABASES전용2DB/$2·200·1200상한을사용하고전체110회나기존스모크승인을재사용하지않는다. 계획기·실행기의같은옵션을지원한다.

- 2026-11-11 남은경로 스모크: `run_injection_baseline --remaining-smoke`와 계획기의 같은 옵션은 등록된T2/T4/T5/T6/T7 current정상·공격10작업/T6준비2턴만 선택한다. 별도remaining_smoke_v1승인과INJECTION_REMAINING_SMOKE_DATABASES의전용10DB를사용하며전체110·기존T1/T3승인을재사용하지않는다. 순차실행/공유예산/원시보존동작은동일하다.
- 이 폴더: 평가셋을 동결하고 검색·그래프·Skill 평가를 돌리는 실행 코드를 둡니다. 저장소 루트에서 `uv run python -m evals.runners.<이름>`으로 실행합니다.
- 넣는 것: 평가 실행기(`run_*.py`), 동결 스크립트(`freeze.py`), 임베딩 프록시 측정(`benchmark_embeddings.py`), 실행기의 준비·점검·보고 도우미(`embed_cards.py`, `check_retrieval_db.py`, `report_retrieval_layers.py`).
- 넣지 않는 것: 평가셋·동결 기록(`evals/`의 `dataset_v1.jsonl`, `FROZEN.json`), 평가 원시 결과(`evals/results/`), 평가셋 명세·사전 등록(`evals/guides/`), 평가가 아닌 측정 스크립트(`scripts/`).
- 담당: 평가

## 파일
- `run_injection_baseline.py` — 기본은110개 not_run JSONL, `--simulate`는 실제 그래프+가짜 모델/검색/SQL. `--execute`는 입력 플래그·사용자/조장 승인·정확한 측정 커밋/해시·사전 등록 커밋·깨끗한 작업 파일이 모두 필요하며 현재 입력에서는 거부. 사람 판정은null, 출력 덮어쓰기 거부·중단 후 not_run 보존 `--exposure-only`는 독립 scope·승인·DB·$2 상한의 T1/T3 current4작업만 선택한다.
- `injection_baseline_runtime.py` — 승인 경로의14개 빈 loopback DB·42문서 복사본/합성 문서 적재·본문 해시 벡터 캐시·실제 hybrid/카드 도구·서비스 message와 PostgreSQL 임시 이력 표·전체 공유 예약/바이트 한도. 실제 공급자 연결은 미실행, 가짜 공급자+실DB 4건만 확인 탐색은별도 INJECTION_EXPOSURE_DATABASES4DB만사용한다.
- `plan_injection_baseline.py` — `baseline_cases.json`에서 110개 고정 job(정상55·공격55)과 준비10턴을 만들고 공식 단가 스냅샷·토큰/경로 가정으로 예상 청구와 예약 상한을 계산. 기본 `--out <새 JSON>`, 네트워크·DB·유료 실행 옵션 없음 `--exposure-only`로4작업과별도예산을무료계산한다.
- `run_injection_preflight.py` — 유료 실행 옵션 없는 인젝션 준비 검사. 기본 `--out <새 JSON>`은 네 관문의 오프라인 테스트를 실행한다. `--local-db`만 명시한 두 빈 loopback 전용 DB에 소형 합성 코퍼스를 적재하고 실제 BM25 검색을 확인한다. 구조화 응답과 공급자 시도를 분리하고 실행별 카드 캐시를 만든다. [작업서](../../docs/experiments/injection-baseline-preflight.md)
- `check_injection_result.py` — 저장한 인젝션 실측03 결과 jsonl(110작업)이 사전 등록 기준(정상55·공격55·completed/live·빈 답 0·판정형 5기준 true·노출 전제)을 지키는지 키·네트워크 없이 확인, 미달이면 종료 코드 1. ci.yml `eval-injection-replay`가 실행. 모델 호출·사람 채점 없음
- `run_thread_validation.py` — v2 1~4건 dry-run과 명시적 유료 실행. 합계 예약 $0.50/16회/90초. 공급자 ID·보고 비용을 기록. [운영 검증](../../docs/experiments/thread-memory-operations.md)
- `run_trust_boundary.py` — D7 합성 공격 3건+정상 대조군의 호출 없는 계획. `uv run python -m evals.runners.run_trust_boundary --out <새 json>`. 별도 승인·사전 등록 뒤 `--execute`만 문서 에이전트를 실제 모델로 실행(예약 $0.50/16회/90초/출력 1024토큰). DB·임베딩·배포 HTTP·전체 Supervisor는 검사하지 않는다. 모델 원문과 최종 반환의 알려진 canary/외부 도메인 유출을 구분한다. 남은 절차는 [요약](../../docs/research/thread-memory-work-summary.md)
- `run_judgement_bundle.py` — `judgement_bundle_v1`의 plan/load/preflight/simulate. 숫자 loopback+`injection_test_*` DB만 허용하고 기존 서비스 DB를 거부한다. 실제 모델 실행 옵션 없음. 가짜 모델에 실제 BM25/MCP/판정 그래프를 연결하며 전체 4건에 단일 예산을 적용한다. HTTP/화면/모델 보안성 시험이 아니다. [주의] load/preflight/simulate는 `db/011_part_specifications.sql`·MCP `part_specs`·`find_parts`를 쓰는데 사양 표 제거(ADR 0016)로 지금 코드에 없어 돌지 않는다. 지금 확인되는 것은 plan과 예산 단위 시험뿐이다. 절차는 preregister의 'D7 검색 청크→판정 첫 묶음 v1' 후속 절
- `run_claim_consistency.py` — 고정 대조군+C1+C2 실제 모델 기준선. 기본 계획은 외부 호출 0, `--execute`는 합산 예약 $0.50/16회/90초/출력 1024. 기존 문서 에이전트/코드 판정/답 정리·종합/최종 검사를 연결하며 DB/Supervisor 계획/HTTP는 실행하지 않는다. 의미 평가는 원문 대조 후 별도 기록한다. 결과 파일의 코드 해시는 실행 시점 스냅샷이며 방어 개선율을 뜻하지 않는다
- `run_input_surfaces.py` — 다섯 입력 위치 호환성, 청크/값/질문 컴포넌트 실측. `--out <새 JSON>`은 무료, `--execute`만 합산 $0.50/16회/90초/1024토큰. `--question-only`는 사전 등록한 별도 예산으로 P4-N/P4-A만 고른다. 이름/소속은 보류하며 DB/검색/HTTP/전체 Supervisor/계정 격리는 검사하지 않는다
- `freeze.py` — 평가셋 sha256·건수를 `../FROZEN.json`에 기록. `uv run python evals/runners/freeze.py dataset_v1.jsonl`(동결), `--check`(동결 뒤 바뀐 파일 검사)
- `benchmark_embeddings.py` — 프록시 표본([embedding_sample_v0.jsonl](../samples/embedding_sample_v0.jsonl))의 dense Recall@5·MRR·지연 측정. `uv run python -m evals.runners.benchmark_embeddings --model bge-m3 --output evals/results/embedding/embedding_bge_m3_proxy_<날짜>.json`
- `run_retrieval.py` — 평가셋 관련 문항으로 `retrieve()`의 문서 Recall@k·MRR·Page Hit@k를 재고 결과 json을 남김. `uv run python -m evals.runners.run_retrieval <평가셋 jsonl> <결과 json> [k] [method]`. 검색 방식은 `hybrid`(기본)·`dense`·`bm25`. 결과는 `../results/retrieval/`에 둠
- `run_retrieval_d3.py` — 사전 등록 #24 D3 공식 검색 측정. 동결 v2 채점 19문항을 [qrels](../inputs/qrels_v2_pages.json)로 재고, 기준(서비스 경로)에서 한 조건씩 바꾼 E1~E8 칸과 필터 끔 재측정·no_result 임계값·탐색 격자를 `../results/retrieval/`에 남김. 청크·벡터는 저장소 밖 파일을 인자로 읽음. `uv run --with docling-core python -m evals.runners.run_retrieval_d3 qrels|official|noresult|chunks|embed <변형>|explore`
- `run_retrieval_r1.py` — 사전 등록 #25 R1 검색 측정. [검색 표본](../samples/retrieval_r1.jsonl) 84문항으로 임베딩 11 × 필터 3 × 질의 2 × 리랭커 4 = 264칸을 dev 세트 46문항에서 줄 세워 상위 3칸을 고르고, test 세트 38문항에서 지금 서비스와 한 번 비교. 검색 · 지표 · 비교는 `run_retrieval_d3.py`를 그대로 씀. `uv run python -m evals.runners.run_retrieval_r1 rewrite|qvec-api|requests|run|steps`(GPU: `gpu-qvec|gpu-rerank`). `steps`는 사전 등록 #28의 한 번에 하나씩 단계별 재측정(S0 지금 서비스 → S4 1위)
- `run_retrieval_service.py` — 사전 등록 #26 서비스 경로 재측정. 실제 `retrieve()`(DEMO_MODE=0)로 R1 84문항 · v2 19문항의 쪽 지표, R1 1위 칸과의 상위 5개 대조, `retrieve()` · `rewrite()` 시간을 재서 `../results/retrieval/service_r1_<날짜>.json`에 남김. db/008 적용과 voyage 적재 뒤 `uv run python -m evals.runners.run_retrieval_service`. `--out <경로>` · `--prereg '#27'`로 비트 후보 검색(사전 등록 #27) 결과를 다른 파일에 남기고, `--compare <정확 json> <비트 json>`은 DB 없이 두 결과 파일의 상위 5개 같음 · Page Recall · 시간을 견줌. `--stages N`은 사전 등록 #28의 단계별 시간(질문 임베딩 · rerank-3 · 나머지)과 rerank 토큰만 잰다.
- `run_retrieval_v3.py` — v3 평가셋(또는 같은 형식의 dev 파일)의 검색 지표를 에이전트 검색 길 그대로 잰다: 입력 읽기 → 재작성(LLM 1번) → 검색 노드와 같은 품번 필터로 `retrieve(k=10)`, 문서 · 쪽 Recall@5 · MRR(정의는 `run_retrieval.py`와 같음). `uv run python -m evals.runners.run_retrieval_v3 <평가셋 jsonl> <결과 json>`
- `run_graph.py` — 평가셋 문항(전부 또는 고른 id)을 D4 v2 단일 그래프로 끝까지 돌려(MCP 서버를 열어 사실 확인에 쓰고, 찾기 · 판정 값은 서비스와 같은 카드 도구(`backend/rag/card_*.py`, `DATABASE_URL` · 카드 읽기 LLM)로 판정 길을 켜고, 판정 인터럽트는 빈 값으로 한 번 재개, 거절 사유 `refusal_code` 점수 추가) 문항마다 Langfuse 트레이스와 실행 점수(경로·검색 횟수·LLM 호출 수·인용 검사·5지표 `answer_metric`·시간)를 남기고, 같은 지표와 실행 조건·5지표 요약을 `../results/graph/graph_<평가셋>_<날짜>.json`에 저장(답변 문장·청크 원문은 넣지 않음). `--multi`를 붙이면 멀티 에이전트(Supervisor + 서브에이전트)를 같은 평가셋 · 같은 채점으로 재고(검색 횟수 · Supervisor 판단 횟수 `hops` 점수 추가, 결과 `multi_<평가셋>_<날짜>.json`, 같은 사실 확인 · 카드 도구로 Spec 에이전트를 켬), 실행 조건에 노드별 모델 `node_models`를 남긴다. `uv run python -m evals.runners.run_graph <평가셋 jsonl> [문항 id ...] [--out <결과 json>] [--multi]`
- `run_gate.py` — 감시 실행기(v3 반복 측정): 평가셋을 멀티 에이전트로 여러 세트 연달아 하나씩 돌리며(동시 실행 없음) 문항마다 통과를 바로 판정하고, 처음 실패한 문항이나 세트의 응답 시간 p95 초과에서 멈춰 경로 · 지표 · 판정 · 트레이스 주소를 남김. 문항에 `parts`가 있으면 `score_compound`로 채점. `GATE_WARMUP=1`이면 세트 앞에 BM25·Voyage·MCP lookup을 데워 콜드를 문항 latency에서 빼고(정상 상태 측정용 · 서비스 기본 아님), Spec `find` 앞 문서 수는 `FIND_N_DOCS`(기본 5). p95 레버 A/B: [speed-p95-levers-2026-11-11.md](../../docs/experiments/speed-p95-levers-2026-11-11.md). `uv run python -m evals.runners.run_gate <평가셋 jsonl> --out <결과 폴더> [--sets 3] [--p95 10] [--keep-going]`
- `stage_timing.py` — `run_gate`가 문항 행에 새 칸 `stages`(서비스와 같은 노드 단위 시간) · `llm_call_log`(LLM 호출마다 노드 · 모델 · 초 · 입력 · 출력 · 캐시 토큰 · 공급자 보고 비용) · `voyage`(임베딩 · 리랭크 호출 초 · 토큰)를 쓰게 하는 기록기. 질문 · 답 본문은 담지 않는다. 집계는 `scripts/eval/stage_report.py`

`run_gate`는 `run_graph`와 같은 실행 조건을 기록하고 `run_scores`의 점수와 `pass` · `cost_usd` · RAGAS(Faithfulness·Context Precision, G6)를 각 trace에 붙인다. `RAGAS_ENABLED=0`이면 RAGAS만 건너뛴다. 호출 수는 `StageRecorder` 실기록이며 미보고 비용은 0으로 대체하지 않는다. 오류 문항은 품질 점수 없이 `pass=0` · 지연 · 호출 수 · 확인 가능한 비용만 남긴다. 점수 전송은 응답 시간 측정 뒤에 하며 전송 장애가 원래 결과를 바꾸지 않는다. 행의 `score_delivery=queued`는 원격 수신 확인이 아니다.
- `score_ragas.py` — 강의 03강처럼 reference 없이 Faithfulness·LLMContextPrecisionWithoutReference를 재 Langfuse Score 칸에 올릴 값을 만든다. `run_gate`가 같은 trace에 `create_score`로 붙인다.
- `gate_report.py` — `run_gate` 결과 세트(`set*.json`)를 11-07 기준표로 집계: 관련 정답률, 무관 올바른 거절률, 지어낸 답 · 근거 틀린 답 · 답할 수 있는데 거절 비율, 에이전트 길 검색 문서 · 쪽 Recall@5 · MRR, 응답 시간 p50 · p95. `python -m evals.runners.gate_report <평가셋 jsonl> <결과 폴더> [--min 0.95] [--max-error 0.05] [--p95 10]`
- `run_judge_dev.py` — 판정 연습 문제(jsonl)를 멀티 그래프로 돌려(인터럽트는 빈 값으로 한 번 재개) 문항마다 역할 · 판정이 기대와 같은지 매기고, 역할 정답률 · 판정 일치율을 `../results/judge/judge_dev_<날짜-시각>.json`에 저장. 판정 질문은 첫 후보의 판정, 찾기 질문은 보여 준 후보 · 판정 집합을 본다. 연습 문제 파일은 아직 저장소에 없다. `uv run python -m evals.runners.run_judge_dev <연습 문제 jsonl>`
- `run_supervisor_models.py` — 동결 v2 70문항의 후보 5종 평가 계획, ZDR provider 확인, 문항별 실행·중단·집계. `plan|import-evidence|smoke|run` 명령을 지원하며 live 명령은 `--confirm-live`와 비용 상한이 필요함. 1차 결과는 `../results/supervisor/2026-11-04-stage1-v1/`
- `run_supervisor_jev.py` — Jev Decisions API typed answer를 평가 계약으로 변환하고 70문항 plan·smoke·run·집계를 수행. OpenRouter 호출은 `backend/services/llm.py`를 경유하며 live 명령에는 `--confirm-live`와 `--max-usd` 비용 관리값이 필요함. 입력 비용 추정으로 다음 job을 차단하므로 실제 지출의 절대 상한은 아님
- `report_supervisor_stage3.py` — API 없이 1~3차 원시 행의 hash·분모·라우팅 일관성·3회 일치/flip을 재계산하고 3차 집계 JSON·상세/간단 보고서를 생성
- `supervisor_prompt_v0_common.py` — V0 13건의 전용 hash·건수를 확인하고 정답·id를 제외한 입력을 만들며, 실패 행도 전체 분모에 남겨 네 필드·의미 일치를 결정적으로 채점
- `run_supervisor_prompt_v0.py` — Luna·Haiku에 같은 V0 prompt·13건을 주는 독립 Chat 실행기. `plan`은 API 없이 26-job manifest를 만들고 `smoke|run`은 명시적 live 확인과 비용·시간·단가 상한이 필요함. 본 실행은 성공한 smoke의 exact model·provider만 허용
- `run_supervisor_prompt_v0_jev.py` — Jev Decisions의 5개 typed answer를 같은 V0 네 필드로 변환하는 독립 실행기. `plan`은 API 없이 13-job manifest를 만들며 live 실행은 호출·시간 상한을 집행하고 승인 USD와 비용 미보고를 구분함. 본 실행은 성공한 smoke의 exact model·provider만 허용
- `compare_supervisor_prompt_v0.py` — 정확한 세 후보의 dataset·의미 계약 hash와 case 집합이 같을 때만 네 필드 정확도·형식·의미·지연·usage를 집계. Jev typed answer confidence는 별도 보존
- `import_supervisor_prompt_v0_langfuse.py` — 완료된 V0 13문항·세 후보 결과를 모델 재호출 없이 Langfuse Dataset 1개와 Experiment 3개로 가져오고 결정적 점수 7개를 기록. `plan`은 외부 쓰기 없이 확인하고 `import --confirm-langfuse-write`만 실제로 기록
- `eval_grader.py` — 사전 등록 #36 채점기 기준선. [grader_cases_v2.json](../inputs/grader_cases_v2.json)으로 정답 쪽 유지율 · 검색 판정 × 통과 판정 표 · 비관련 통과 0개 비율 · 쪽 재현율을 계산(LLM · API 호출 없음). `uv run python -m evals.runners.eval_grader run [--snapshot ...]` → [grader_baseline](../results/grader/). `collect-r1`은 R1 dev 46문항에 서비스 검색과 지금 채점 노드를 1번씩 돌려 스냅샷을 새로 만든다(운영 DB 읽기 · Voyage · OpenRouter 호출, 사전 등록 #34)
- `score_answer.py` — 평가셋 문항과 그래프 실행 상태를 대조해 답변·거절 5지표(`cited_gold`, `wrong_citation`, `over_refusal`, `correct_refusal`, `hallucination_risk`)를 규칙 기반으로 채점([작업서](../../docs/experiments/answer-refusal-scorer.md)). `uv run python -m evals.runners.score_answer <평가셋 jsonl> <실행 결과 json> [채점 결과 json]`
- `score_compound.py` — 여러 개를 묻는 질문의 부분별 채점: 문항의 `parts`마다 답할 수 있는 부분은 정답 (PDF, 쪽) 인용 · 판정 코드 · 찾기 후보로, 답하면 안 되는 부분은 그 부분을 거절했는지(열쇠 낱말이 든 문장의 '확인 못 함' 말)로 통과를 냄. `run_gate`가 부름
- `run_skill_pair.py` — preregister #17 순차 평가 실행기. `DEMO_MODE=0 uv run python -m evals.runners.run_skill_pair <새 결과 폴더>`. 동일 상태에서 Skill 유무 답변을 비교하고 요약만 `../results/skill/`에 둠

- `embed_cards.py` — 사전 등록 #16 카드 52,244장을 실험 DB에 넣고 모델 6종으로 카드를 임베딩. 컨테이너에서 실행([DOCKER.md](../docker/DOCKER.md))
- `run_embedding_grid.py` — 사전 등록 #16 임베딩 6종 × 검색 방식(BM25·dense·하이브리드) × 리랭커 × 질의 글 78칸의 문서 Recall@5·MRR·쪽 적중·다중 근거와 단계별 시간. 결과 [grid_2026-11-02.json](../results/embedding/grid_2026-11-02.json)
- `check_retrieval_db.py` — 층별 재측정 0층. Supabase의 카드·벡터·정확 검색 상위 50·서비스 경로 상위 5를 로컬과 대조(읽기만, `DATABASE_URL`)
- `run_retrieval_layers.py` — 검색 조합 층별 재측정 1~4층(`queries`·`layer1`~`layer4`·`price`·`embed <모델>`). 입출력은 `LAYERS_WORK`. 해석 [retrieval-layered-rerun-2026-11-03.md](../../docs/research/retrieval-layered-rerun-2026-11-03.md)
- `report_retrieval_layers.py` — 층별 결과 파일에서 사전 등록 비교(C1~C11)의 값을 뽑아 `report.json`으로 남김(새 검색·API 없음)

실행기별 세부 동작(질의 필드, 검색 방식 기록, 비용 계산 등)은 [EVALS.md](../EVALS.md)를 봅니다.
