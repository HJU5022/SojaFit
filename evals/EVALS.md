# evals

## 역할

- 이 폴더: 동결 평가셋과 동결 기록을 루트에 두고, 실행 코드·문서·표본·초안·결과를 하위 폴더로 나눈다. 루트 파일의 위치와 이름은 과정 안내와 동결 시험이 가정하므로 옮기지 않는다.
- 넣는 것: 동결 평가셋(`dataset_v1.jsonl`, `dataset_v2.jsonl`, `dataset_v3.jsonl`)과 동결 기록(`FROZEN.json`). 코퍼스가 바뀔 때 만드는 `exclusions.json`도 루트에 둔다(지금은 없음, 규칙은 [dataset-guide.md](guides/dataset-guide.md)).
- 넣지 않는 것: 실행기·동결 스크립트(`evals/runners/`), 명세·사전 등록(`evals/guides/`), 측정 입력(`evals/inputs/`), 프록시 표본(`evals/samples/`), 동결 전 초안·검수 기록(`evals/drafts/`), 지표 해석과 개선 전후 비교(루트 `EVAL_REPORT.md`), 단위 테스트(`tests/`), 평가가 아닌 측정 스크립트와 그 원시 결과(`scripts/`, `scripts/results/`).
- 기준 평가셋: v3([ADR 0015](../docs/adr/0015-평가셋-v3를-새로-만들고-청킹부터-다시-잰다.md)). v1·v2는 이전 측정의 기록으로 둔다.
- 평가셋 필드·정답 기준·동결·채점 방식의 정본: [dataset-guide.md](guides/dataset-guide.md). 평가 수치의 정본: 루트 `EVAL_REPORT.md`. 인젝션 실측 결과의 정본: [injection-results.md](../docs/research/injection-results.md).
- 담당: 평가·문서. 정답은 두 사람이 교차해서 정한다.

## 파일

| 파일·폴더 | 유형 | 설명 |
|---|---|---|
| `EVALS.md` | 폴더 설명 | 이 문서 |
| `dataset_v1.jsonl` | 동결 평가셋 | v1. `drafts/sets/draft_50.jsonl`의 고정 키만 옮김 |
| `dataset_v2.jsonl` | 동결 평가셋 | v2. v1 줄에 `question_type`을 더하고 후보 찾기 20건(`drafts/sets/draft_v2add_20.jsonl`의 고정 키)을 더함 |
| `dataset_v3.jsonl` | 동결 평가셋 | v3(기준 평가셋). 문항에 판정자 필드 `judges`가 있음(역할은 [v3_judging_record.md](drafts/reviews/v3_judging_record.md)). 키 목록은 [dataset-guide.md](guides/dataset-guide.md) |
| `FROZEN.json` | 동결 기록 | 파일별 sha256·건수·관련/비관련 건수·동결일. 동결 여부는 이 파일이 정함 |
| `runners/` | 실행 코드 | 평가 실행기·동결 스크립트. [RUNNERS.md](runners/RUNNERS.md) |
| `docker/` | 컨테이너 정의 | 임베딩 실험용 이미지. [DOCKER.md](docker/DOCKER.md) |
| `inputs/` | 측정 입력 | 페이지 단위 qrels, 고정 재작성 질의, 채점기 입력. [INPUTS.md](inputs/INPUTS.md) |
| `guides/` | 명세·사전 등록 | [GUIDES.md](guides/GUIDES.md) |
| `samples/` | 비동결 표본 | 임베딩 프록시·검색 표본·Supervisor V0 표본. [SAMPLES.md](samples/SAMPLES.md) |
| `drafts/` | 동결 전 초안 | 초안(`sets/`)과 검수 기록(`reviews/`). [DRAFTS.md](drafts/DRAFTS.md) |
| `results/` | 평가 원시 결과 | 폴더 설명 파일 없이 이 문서의 "결과 폴더"가 설명함. 평가가 아닌 측정은 `scripts/results/` |

## 재현 명령

저장소 루트에서 실행한다. 실행기별 인자와 비용은 [RUNNERS.md](runners/RUNNERS.md).

| 대상 | 명령 | 비용 | 필요한 것 | 쓰는 곳 |
|---|---|---|---|---|
| 동결 해시 검사 | `uv run python evals/runners/freeze.py --check` | 무료 | 없음 | 화면 |
| 인젝션 저장 결과 기준 검사 | `uv run python -m evals.runners.check_injection_result` | 무료 | 없음 | 화면. 위반이면 종료 코드 1 |
| v1 검색 지표 | `uv run python -m evals.runners.run_retrieval evals/dataset_v1.jsonl evals/results/retrieval/retrieval.json 5 <hybrid\|dense\|bm25>` | `bm25`는 DB 읽기만. `hybrid`·`dense`는 임베딩 API 호출(유료) | `DATABASE_URL`, 임베딩 키, `DEMO_MODE=0` | 두 번째 인자 경로. 컨테이너 실행형: `evals/results/d10/README.md` |
| v3 게이트 실행 | `uv run python -m evals.runners.run_gate evals/dataset_v3.jsonl --out eval-out --sets 1 --keep-going` | 유료(OpenRouter·Voyage·Langfuse). 세트당 약 $0.05는 `eval-live.yml` 머리 주석의 값 | `LLM_PROVIDER=openrouter`, `OPENROUTER_API_KEY`, `VOYAGE_API_KEY`, `DATABASE_URL`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` | `eval-out/set<n>.json` |
| v3 게이트 집계 | `uv run python -m evals.runners.gate_report evals/dataset_v3.jsonl eval-out` | 무료 | 위 실행의 `eval-out/` | `eval-out/report.json`. 기준 미달이면 종료 코드 1 |

- v3 게이트 두 명령은 `.github/workflows/eval-live.yml`(수동 실행 `workflow_dispatch`, 입력 `sets` 기본 1)이 그대로 실행한다.
- `gate_report`의 기본 기준은 `--min 0.95 --max-error 0.05 --p95 10`이다([gate_report.py](runners/gate_report.py)의 `main` 기본값).
- 동결 해시 검사(`freeze.py --check`)는 2026-11-16에 실행해 확인했다(바뀐 파일 없음, 종료 코드 0). 나머지 명령은 실행해 확인하지 않았다(유료이거나 DB가 필요하다). 인자와 환경변수는 코드와 워크플로 파일에서 대조했다.

## v3 재동결 이력

`dataset_v3.jsonl`은 한 번 다시 동결했다. `FROZEN.json`에는 현재 해시와 최초 동결일(`frozen_at` 2026-11-10)만 있고 이력 필드는 없다(이 파일을 고치지 않는다). 이력의 정본은 아래 표이고 같은 사실이 [dataset-guide.md](guides/dataset-guide.md)와 [EVAL_REPORT.md](../EVAL_REPORT.md) 2절 표에 있다.

| 시점 | 파일 sha256 | 커밋 | 바뀐 것 |
|---|---|---|---|
| 2026-11-10 11:48 최초 동결 | `2b99b2125d98db6f127d4364e2940acaf4a27aeb9ee60ef1667d5e0e3e6e5e91` | `30d0469` | 50건(관련 25 · 비관련 25) |
| 2026-11-12 21:23 | `05202314ed1d009593ab14bc5d44e3d7ab7dd4a9f7e726f98282198c7999b4fd`(현재, `FROZEN.json`의 값) | `a16afe5` | 50건 모두에 `judges: ["심태현", "하정운"]` 칸을 더했다. 건수 · 관련/비관련 건수는 그대로 |

- 두 시점의 파일을 문항별로 대조하면 50건 모두에서 다른 칸은 `judges` 하나뿐이다(질문 · 정답 · 판정 기준은 같다). `git show`로 읽은 두 시점 파일의 sha256을 다시 계산해 위 표의 두 값과 같음을 확인했다(2026-11-16 `[실측]`).
- 측정 결과 파일의 `summary`에는 데이터셋 해시가 없다. 그래서 어느 결과가 어느 해시의 파일로 났는지는 결과의 측정 시각 · 커밋으로만 가를 수 있다(11-12 21:23 이전이면 최초 파일, 이후면 현재 파일 `[추정]`). 질문과 정답은 같아 점수 해석은 바뀌지 않는다.
- `freeze.py --check`는 현재 해시와 대조한다. 2026-11-16 실행 결과는 "동결 이후 바뀐 파일: 없음"이다.

## 결과 폴더

`results/` 하위 폴더별 내용이다. 수치와 해석은 루트 `EVAL_REPORT.md`, 각 실험 문서, 사전 등록 번호는 [preregister.md](guides/preregister.md)에 있다. 원시 파일은 수정하지 않는다.

| 폴더 | 내용 | 만든 실행기 | 해석 |
|---|---|---|---|
| `results/d10/` | Checkpoint D10 제출물 점검 증거: 인젝션 기준 검사 통과·실패 출력, 코드 변이 결과와 재현 스크립트(`mutation/`), 비밀값 검사 결과와 원시 증거(`secrets/`), v4h 지문, 재현 명령(`README.md`) | `check_injection_result.py`, `d10/mutation/reproduce.sh` 외 | `results/d10/README.md` |
| `results/retrieval/` | 검색 지표: `retrieval_{baseline,dense,bm25}_*`(v1), `d3_*`(#24), `r1_*`(#25·#28), `retrieval_layer*`·`retrieval_layers_*`(층별 재측정), `service_r1_*`·`service_stages_*`(서비스 경로) | `run_retrieval*.py`, `report_retrieval_layers.py` | [retrieval-layered-rerun-2026-11-03.md](../docs/research/retrieval-layered-rerun-2026-11-03.md), 사전 등록 #24~#28 |
| `results/retrieval/2026-11-16-cand-pool/` | 리랭크 전 후보 수 50 → 200 검색 전후(R1 84문항, S4 설정에서 이것만 바꿈): 두 팔 문항별 지표 · 실패 유형 · 후보 회수 · 리랭크 토큰(`cands_2026-11-16.json`), 새 rerank-3 응답 25건(`rerank_new_2026-11-16.jsonl`), `SHA256.txt`. Page Recall@5 0.8810 → 0.8929(2승 1패, 차이 입증 못 함) | `run_retrieval_r1.py cands` | `results/retrieval/2026-11-16-cand-pool/README.md`, 사전 등록 2026-11-16 jeongun · 리랭크 전 후보 수 |
| `results/embedding/` | 임베딩 격자 본평가(`grid_*`, 모델별 카드 임베딩 기록, 리랭크 캐시)와 프록시 측정(`embedding_<모델>_proxy_*`) | `run_embedding_grid.py`, `benchmark_embeddings.py` | [embedding-grid-eval-2026-11-02.md](../docs/research/embedding-grid-eval-2026-11-02.md) |
| `results/search_compare/` | 청킹 개선 전후, dense·BM25·하이브리드 비교(11-01) | — | 사전 등록 #4~#8 |
| `results/drafts/` | 초안 50건·52건의 보조 검증 원시 기록 | — | `drafts/reviews/second_pass_50_review.md` |
| `results/graph/` | 그래프 실행 문항별 지표(`graph_*`, `multi_*`)와 실험별 하위 폴더 `<날짜>-<이름>/`(판정 단계, v3 Haiku 세트, D8 단계 시간, 속도 A/B, D9, Langfuse 점검 등). 답변 문장·청크 원문은 넣지 않음. 일부 하위 폴더는 `sources_*.json`에 원본 경로·sha256을 기록. `2026-11-14-no-replan/`에는 상한에 닿은 질문 한 건의 경로 기록 [v3-15_cap_path_2026-11-14.md](results/graph/2026-11-14-no-replan/v3-15_cap_path_2026-11-14.md)가 있음 | `run_graph.py`, `run_gate.py`, `scripts/eval/stage_report.py` | `EVAL_REPORT.md`, [d8-stage-remeasure-plan.md](../docs/experiments/d8-stage-remeasure-plan.md), [speed-p95-levers-2026-11-11.md](../docs/experiments/speed-p95-levers-2026-11-11.md) |
| `results/chunking/v4h-2026-11-08/` | v4h 청킹의 `summary.json`·`manifest.jsonl`·`table_suspects.jsonl`·`SHA256.txt`. 청크 본문은 없음 | 저장소 밖 청킹 | `results/chunking/v4h-2026-11-08/README.md`, 문서·청크 수는 [DATA.md](../data/DATA.md) |
| `results/chunking/v1-vs-v4h-2026-11-13/` | 청킹 v1 대 v4h 검색 비교: 같은 동결 v3(쪽 정답 21건)·고정 질의·같은 임베딩과 검색 코드로 잰 `retrieval_v1_*`·`retrieval_v4h_*` json, 설정·지표·한계(`README.md`), `SHA256.txt` | `run_retrieval_v3.py` | `results/chunking/v1-vs-v4h-2026-11-13/README.md` |
| `results/grader/` | 채점기 기준선(`grader_baseline_*`) | `eval_grader.py` | 사전 등록 #34·#36 |
| `results/skill/` | Skill·도구 판단 검증 요약 | `run_skill_pair.py` | 사전 등록 #17 |
| `results/supervisor/` | Supervisor 후보 비교 단계별 `<날짜>-<이름>/`(manifest, 문항별 행, summary, 호출 증거). V0 프롬프트 비교와 Langfuse 가져오기 영수증 포함 | `run_supervisor_*.py`, `report_supervisor_stage3.py`, `import_supervisor_prompt_v0_langfuse.py` | 각 하위 폴더 `*summary*.json`, [supervisor-prompt-v0.md](guides/supervisor-prompt-v0.md) |
| `results/threads/` | thread 기억·입력 경로·신뢰 경계·판정 묶음 확인과 인젝션 실측 원시(`injection_*`) | `run_thread_validation.py`, `run_trust_boundary.py`, `run_claim_consistency.py`, `run_input_surfaces.py`, `run_judgement_bundle.py`, `run_injection_baseline.py`, `run_supervisor_guard_injection.py` | 아래 "인젝션 파일" |

### 그래프 하위 폴더 (`results/graph/`)

`results/graph/` 아래 실험별 폴더와 바로 아래 파일이다. 모두 `run_gate.py` 결과(`set*.json`, 일부 `report.json`)이고 다르면 "내용"에 적는다. 수치는 각 폴더의 README·SUMMARY와 해석 문서에 있고 이 표에 옮기지 않는다. "해석 문서 없음"은 `docs/worklog/` 밖에서 이 폴더를 인용한 문서가 없다는 뜻이다(2026-11-17 `git grep` 기준).

| 폴더·파일 | 내용 | 해석 |
|---|---|---|
| `graph_dataset_v2_*.json`, `multi_dataset_v2_*.json` | 동결 v2 단일·멀티 그래프 문항별 지표(`run_graph.py`) | `EVAL_REPORT.md` 4장, [preregister.md](guides/preregister.md)의 `run_graph` 결과 줄 |
| `memory_operations_2026-11-09.json`, `thread_validation_2026-11-09.json`, 동명 `.usage.json` | 앱 사례 기억 운영 재검증, thread 검증과 사용량(`run_thread_validation.py`) | [thread-memory-operations.md](../docs/experiments/thread-memory-operations.md), 사전 등록 2026-11-09 |
| `2026-11-06-judge-steps/` | 사전 등록 #39~#42(동결 v2 70문항) 판정 단계 원시. 출처 · sha256은 `sources_2026-11-10.json` | `EVAL_REPORT.md` 3 · 4 · 5장 |
| `2026-11-06-judge-diagnosis/` | 판정 길 실패 진단(#39 · #40): 문항별 표, draft50-n04 · n08 재실행 | 폴더 `README.md`, `EVAL_REPORT.md` 5장 |
| `2026-11-10-v3-outside/` | v3 #47 구성(B) · #48+#49(C) 원시 | 폴더 `README.md`, [d9-outside-evidence-2026-11-11.md](../docs/research/d9-outside-evidence-2026-11-11.md) |
| `2026-11-10-v3-haiku-sets/` | v3 50문항 Haiku 구성(#50) 원시. 출처 · sha256은 `sources_2026-11-11.json` | `EVAL_REPORT.md` 3 · 8장 |
| `2026-11-11-d8-stages/`, `2026-11-11-d8-stages-rerun/` | D8 v3 50문항 단계 시간 · 호출별 비용과 집계 `stage_summary.json`, 공급자 429로 실패한 문항 재실행 | `EVAL_REPORT.md` 8장, [d8-stage-remeasure-plan.md](../docs/experiments/d8-stage-remeasure-plan.md) |
| `2026-11-11-langfuse-probe/`, `2026-11-11-langfuse-probe-v2/` | 동결 v3-01 한 문항의 Langfuse 수신 점검(입력 `v3-01-only.jsonl`) | 사전 등록 "2026-11-11 D8 추적 보완 뒤 한 문항 수신 점검". 해석 문서 없음 |
| `2026-11-11-langfuse-ragas-probe/`, `2026-11-11-langfuse-ragas-probe-v2/`, `2026-11-11-langfuse-ragas-probe-v3/` | 같은 한 문항으로 RAGAS 점수 전송 점검 | 해석 문서 없음 |
| `2026-11-11-ndocs-acc/` | `FIND_N_DOCS` 값별 v3 50문항 정확도 | 폴더 `SUMMARY.md`, `EVAL_REPORT.md` 8장, [speed-p95-levers-2026-11-11.md](../docs/experiments/speed-p95-levers-2026-11-11.md) |
| `2026-11-11-speed-e-warm/`, `2026-11-11-speed-f-find-ndocs/`, `2026-11-11-speed-g-all/` | 응답 시간 레버 비교(데우기 공통 · 찾기 문서 수 · A~D 레버). `speed-g-all/E-v3-50-warm-n5/set1.json`은 `ndocs-acc/N5/set1.json`과 바이트가 같은 파일 | 각 폴더 `SUMMARY.md`, [speed-p95-levers-2026-11-11.md](../docs/experiments/speed-p95-levers-2026-11-11.md) |
| `2026-11-11-speed-s1-docs-retry/`, `2026-11-11-speed-s2-warmup/`, `2026-11-11-speed-s3-cite-repair/` | 문서 재시도 · 데우기 · 인용 보정 켬/끔 | [speed-p95-levers-2026-11-11.md](../docs/experiments/speed-p95-levers-2026-11-11.md) |
| `2026-11-11-synth-01-repeat10/`, `2026-11-11-synth-both-agents/` | 합성 문항 반복 · 두 에이전트 실행(입력 jsonl 포함) | 해석 문서 없음 |
| `2026-11-12-codex-v3-50/` | Codex v3 50문항 답과 규칙 · 사람 판정 집계(`TALLY.md`, `scripts/eval/tally_codex_v3.py`) | `EVAL_REPORT.md` 10장 |
| `2026-11-12-d9-improve2/` | D9 v3 50문항 멀티 게이트와 `report.json` | `EVAL_REPORT.md` 3 · 4장, [GATES.md](../docs/GATES.md) |
| `2026-11-12-d9-judge-dev-multi/`, `2026-11-12-d9-judge-dev-single/` | 판정 연습 44문항 멀티 · 단일(입력 `judge_dev_44.jsonl`은 두 폴더가 같은 파일) | `EVAL_REPORT.md` 4장 |
| `2026-11-12-d9-langfuse-capture/` | Langfuse 수집 확인 실행 | `EVAL_REPORT.md` 7장 |
| `2026-11-12-d9-v3-single/` | v3 단일 그래프 | `EVAL_REPORT.md` 4장 |
| `2026-11-12-v3-16-warm-recheck/` | v3-16 한 문항 데운 뒤 재확인 | 해석 문서 없음 |
| `2026-11-13-citecheck-v3/` | 인용 숫자 검사 브랜치의 v3 50문항 재측정과 `report.json` | `EVAL_REPORT.md` 5 · 6 · 8장, [GATES.md](../docs/GATES.md) |
| `2026-11-14-web-prefetch/`, `2026-11-14-docs-parallel/`, `2026-11-14-grade3-early/`, `2026-11-14-no-replan/`, `2026-11-15-web-parallel/` | 웹 근거 미리 출발(B0 · B1 · A1), 검색 병렬화(P1), 참고 웹 검색 미리 출발(G1 무효 · G2 · P1b), 코퍼스 밖 재계획 생략(R1), 웹 공식 검색 병렬 출발(B1) | 각 폴더 `README.md`(사전 등록 · 코드 커밋), `EVAL_REPORT.md` 8장 |
| `2026-11-16-speed-baseline/`, `2026-11-16-speed-L3/`, `2026-11-16-speed-L4/` | speed-exp 웹 켬 기준 A1~A4와 레버 L3 · L4 | 사전 등록 "2026-11-15 speed-exp" 항목들(판정 기록). 해석 문서 없음 |
| `2026-11-16-speedoff-baseline/`, `2026-11-16-speedoff-P2/` | speed-exp 웹 끔 기준 B1~B3와 레버 P2(Voyage 연결 재사용) | 같은 사전 등록 항목들, `d10/langfuse_scores_2026-11-16.md`(B3 trace) |
| `2026-11-16-fixes-before/`, `2026-11-16-fixes-after/` | 동결 전 백엔드 수정 묶음의 웹 끔 v3 전후 | 각 폴더 `README.md` |
| `2026-11-16-codex-v3-50-isolated/` | Codex 격리 재비교 원본 로그(`raw/`) · `runs.json` · 규칙 채점 `tally.jsonl`(`scripts/eval/run_codex_v3_isolated.py`, `tally_codex_v3.py`) | `EVAL_REPORT.md` 10장 |
| `2026-11-16-terra-v3-50-isolated-web/` | Terra 웹 검색 격리 기준선 원본 로그 · 규칙 · 사람 판정. `scripts/run_isolated_baseline.py`는 실행 당시 스크립트 사본이고 실행기가 아니다 | 폴더 `README.md` · `TALLY.md`, `EVAL_REPORT.md` 10장 |

- `results/d10/mutation/`의 `.py`·`.sh`는 변이 시험 증거 묶음의 재현 스크립트라 결과와 함께 둔다. 위 Terra 폴더의 `scripts/`와 함께, 원시 결과 폴더 안의 코드는 실행기 목록([RUNNERS.md](runners/RUNNERS.md))에 넣지 않는다.

### 인젝션 파일 (`results/threads/`)

| 파일 | 내용 |
|---|---|
| `injection_baseline_live_2026-11-11_03.jsonl`, 동명 `.meta.json`·`.budget.json`, `injection_baseline_approval_2026-11-11_03.json` | 110작업 실측03의 원시·메타·예산·승인 |
| `injection_baseline_live_2026-11-11_03_human_jeongun.jsonl` | 실측03의 별도 사본(행 수·검토자 표기는 `injection-results.md`) |
| `injection_baseline_live_2026-11-11_03.reviewer_correction.json` | 실측03 · 스모크08 원시의 `reviewer`=`team_lead` 정정 기록(실제 판정자 심태현 110건, 원시 해시 · 확인 출처). 원시 파일은 바꾸지 않음 |
| `injection_t3_live_2026-11-11_08.jsonl`, 동명 `.meta.json`·`.budget.json`, `injection_t3_approval_2026-11-11_08.json` | T3 스모크08(`t3_smoke_v1`)의 원시·메타·예산·승인 |
| `injection_t3_smoke_live_2026-11-11_07.jsonl`, 동명 `.meta.json`·`.budget.json`, `injection_t3_smoke_approval_2026-11-11_07.json` | T3 스모크07의 원시·메타·예산·승인 |
| `injection_remaining_review_queue_2026-11-11.json` | 실측03·스모크08의 원시 SHA·행·정상 짝·검토 대기 목록 |
| `injection_baseline_review_2026-11-10.json`, `injection_baseline_checks_2026-11-10.json`, `injection_exposure_simulated_v3_2026-11-10.jsonl`, `injection_baseline_artifact_index_2026-11-10.json` | 준비 산출물 통합본: 계획·모의 실행 메타, 무료 검사 기록, 모의 실행 원시, 경로·해시 인덱스 |
| `injection_exposure_code_freeze_2026-11-10.json` | T1 · T3 노출 실행의 승인 범위 · 상한과 옛 코드 동결 커밋 · 보관 참조 기록. 실행 승인 문서가 아님(파일의 `note`). 해석 문서 없음 |
| `supervisor_guard_injection_2026-11-16.json` | Supervisor 답 가드 켬/끔 짝 실측 22작업 원시(호출별 카나리 노출, 계획 · reply, 보고, 켬/끔 답, 공급자 사용량). 해석은 [supervisor-guard-injection-recheck.md](../docs/experiments/supervisor-guard-injection-recheck.md) |

- 실행별 파일은 서로 덮어쓰지 않고 합산하지 않는다.
- 실측01·02와 스모크01~06의 원시는 저장소 밖 백업에 있다. 크기·SHA256·복원 방법은 `injection_baseline_artifact_index_2026-11-10.json`의 `measured_runs_archive`.
- 통합 전 준비 산출물 33개의 원본은 로컬 복구 참조 `refs/archive/injection-pre-consolidation-20261110`(커밋 107aaa3)에 있다. 이 참조는 저장소를 공유해도 함께 공유되지 않는다. 경로·해시는 `injection_baseline_artifact_index_2026-11-10.json`.
- 사람 검토 건수와 판정 결과: [injection-results.md](../docs/research/injection-results.md).

### 그 밖의 thread 파일 (`results/threads/`)

| 파일 | 만든 것 | 해석 |
|---|---|---|
| `claim_consistency_*.json` 6개 | `run_claim_consistency.py` | [injection-results.md](../docs/research/injection-results.md), [c2-defense-recheck.md](../docs/experiments/c2-defense-recheck.md) |
| `input_surface_*.json` 6개 | `run_input_surfaces.py` | [injection-results.md](../docs/research/injection-results.md) |
| `judgement_bundle_*.json` 6개 | `run_judgement_bundle.py` | [preregister.md](guides/preregister.md), [c2-defense-recheck.md](../docs/experiments/c2-defense-recheck.md) |
| `trust_boundary_plan_2026-11-09.json`, `trust_boundary_live_2026-11-09.json` | `run_trust_boundary.py` | [injection-results.md](../docs/research/injection-results.md) |
| `live_smoke_2026-11-09.json` | 저장소 밖 `thread_live_eval.py`(동결 v2 4문항 실제 모델) | 사전 등록 "2026-11-09 사용자 업로드·영속 thread 실제 모델 연결 smoke" |
| `input_regression_2026-11-09.json` | 저장소 밖 `thread_input_eval.py`(v1 · v2 문항의 연결 경로와 업로드 파서 결과 대조) | 해석 문서 없음 |
| `local_g4_isolation_2026-11-09.json` | 키 없는 로컬 compose에서 HTTP로 한 G4 · D7 점검 기록 | `EVAL_REPORT.md`, [GATES.md](../docs/GATES.md), `d10/startup_restart_isolation_2026-11-13.md` |
| `saved_defense_replay_after_2026-11-10.json` | 저장한 응답 두 건의 오프라인 재생(실제 모델 호출 0, 파일의 `mode`) | 해석 문서 없음 |
