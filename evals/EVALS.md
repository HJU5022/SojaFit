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
| `dataset_v3.jsonl` | 동결 평가셋 | v3(기준 평가셋). 문항에 판정자 필드 `judges`가 있음. 키 목록은 [dataset-guide.md](guides/dataset-guide.md) |
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
- 이 문서의 명령은 실행해 확인하지 않았다. 인자와 환경변수는 코드와 워크플로 파일에서 대조했다.

## 결과 폴더

`results/` 하위 폴더별 내용이다. 수치와 해석은 루트 `EVAL_REPORT.md`, 각 실험 문서, 사전 등록 번호는 [preregister.md](guides/preregister.md)에 있다. 원시 파일은 수정하지 않는다.

| 폴더 | 내용 | 만든 실행기 | 해석 |
|---|---|---|---|
| `results/d10/` | Checkpoint D10 제출물 점검 증거: 인젝션 기준 검사 통과·실패 출력, 코드 변이 결과와 재현 스크립트(`mutation/`), 비밀값 검사 결과와 원시 증거(`secrets/`), v4h 지문, 재현 명령(`README.md`) | `check_injection_result.py`, `d10/mutation/reproduce.sh` 외 | `results/d10/README.md` |
| `results/retrieval/` | 검색 지표: `retrieval_{baseline,dense,bm25}_*`(v1), `d3_*`(#24), `r1_*`(#25·#28), `retrieval_layer*`·`retrieval_layers_*`(층별 재측정), `service_r1_*`·`service_stages_*`(서비스 경로) | `run_retrieval*.py`, `report_retrieval_layers.py` | [retrieval-layered-rerun-2026-11-03.md](../docs/research/retrieval-layered-rerun-2026-11-03.md), 사전 등록 #24~#28 |
| `results/embedding/` | 임베딩 격자 본평가(`grid_*`, 모델별 카드 임베딩 기록, 리랭크 캐시)와 프록시 측정(`embedding_<모델>_proxy_*`) | `run_embedding_grid.py`, `benchmark_embeddings.py` | [embedding-grid-eval-2026-11-02.md](../docs/research/embedding-grid-eval-2026-11-02.md) |
| `results/search_compare/` | 청킹 개선 전후, dense·BM25·하이브리드 비교(11-01) | — | 사전 등록 #4~#8 |
| `results/drafts/` | 초안 50건·52건의 보조 검증 원시 기록 | — | `drafts/reviews/second_pass_50_review.md` |
| `results/graph/` | 그래프 실행 문항별 지표(`graph_*`, `multi_*`)와 실험별 하위 폴더 `<날짜>-<이름>/`(판정 단계, v3 Haiku 세트, D8 단계 시간, 속도 A/B, D9, Langfuse 점검 등). 답변 문장·청크 원문은 넣지 않음. 일부 하위 폴더는 `sources_*.json`에 원본 경로·sha256을 기록 | `run_graph.py`, `run_gate.py`, `scripts/eval/stage_report.py` | `EVAL_REPORT.md`, [d8-stage-remeasure-plan.md](../docs/experiments/d8-stage-remeasure-plan.md), [speed-p95-levers-2026-11-11.md](../docs/experiments/speed-p95-levers-2026-11-11.md) |
| `results/chunking/v4h-2026-11-08/` | v4h 청킹의 `summary.json`·`manifest.jsonl`·`table_suspects.jsonl`·`SHA256.txt`. 청크 본문은 없음 | 저장소 밖 청킹 | `results/chunking/v4h-2026-11-08/README.md`, 문서·청크 수는 [DATA.md](../data/DATA.md) |
| `results/grader/` | 채점기 기준선(`grader_baseline_*`) | `eval_grader.py` | 사전 등록 #34·#36 |
| `results/skill/` | Skill·도구 판단 검증 요약 | `run_skill_pair.py` | 사전 등록 #17 |
| `results/supervisor/` | Supervisor 후보 비교 단계별 `<날짜>-<이름>/`(manifest, 문항별 행, summary, 호출 증거). V0 프롬프트 비교와 Langfuse 가져오기 영수증 포함 | `run_supervisor_*.py`, `report_supervisor_stage3.py`, `import_supervisor_prompt_v0_langfuse.py` | 각 하위 폴더 `*summary*.json`, [supervisor-prompt-v0.md](guides/supervisor-prompt-v0.md) |
| `results/threads/` | thread 기억·입력 경로·신뢰 경계·판정 묶음 확인과 인젝션 실측 원시(`injection_*`) | `run_thread_validation.py`, `run_trust_boundary.py`, `run_claim_consistency.py`, `run_input_surfaces.py`, `run_judgement_bundle.py`, `run_injection_baseline.py` | 아래 "인젝션 파일" |

### 인젝션 파일 (`results/threads/`)

| 파일 | 내용 |
|---|---|
| `injection_baseline_live_2026-11-11_03.jsonl`, 동명 `.meta.json`·`.budget.json`, `injection_baseline_approval_2026-11-11_03.json` | 110작업 실측03의 원시·메타·예산·승인 |
| `injection_baseline_live_2026-11-11_03_human_jeongun.jsonl` | 실측03의 별도 사본(행 수·검토자 표기는 `injection-results.md`) |
| `injection_t3_live_2026-11-11_08.jsonl`, 동명 `.meta.json`·`.budget.json`, `injection_t3_approval_2026-11-11_08.json` | T3 스모크08(`t3_smoke_v1`)의 원시·메타·예산·승인 |
| `injection_t3_smoke_live_2026-11-11_07.jsonl`, 동명 `.meta.json`·`.budget.json`, `injection_t3_smoke_approval_2026-11-11_07.json` | T3 스모크07의 원시·메타·예산·승인 |
| `injection_remaining_review_queue_2026-11-11.json` | 실측03·스모크08의 원시 SHA·행·정상 짝·검토 대기 목록 |
| `injection_baseline_review_2026-11-10.json`, `injection_baseline_checks_2026-11-10.json`, `injection_exposure_simulated_v3_2026-11-10.jsonl`, `injection_baseline_artifact_index_2026-11-10.json` | 준비 산출물 통합본: 계획·모의 실행 메타, 무료 검사 기록, 모의 실행 원시, 경로·해시 인덱스 |

- 실행별 파일은 서로 덮어쓰지 않고 합산하지 않는다.
- 실측01·02와 스모크01~06의 원시는 저장소 밖 백업에 있다. 크기·SHA256·복원 방법은 `injection_baseline_artifact_index_2026-11-10.json`의 `measured_runs_archive`.
- 통합 전 준비 산출물 33개의 원본은 로컬 복구 참조 `refs/archive/injection-pre-consolidation-20261110`(커밋 107aaa3)에 있다. 이 참조는 저장소를 공유해도 함께 공유되지 않는다. 경로·해시는 `injection_baseline_artifact_index_2026-11-10.json`.
- 사람 검토 건수와 판정 결과: [injection-results.md](../docs/research/injection-results.md).
