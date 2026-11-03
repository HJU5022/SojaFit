# evals

## 역할
- 이 폴더: 평가셋, 동결 해시, 평가 실행기, 평가 결과를 둡니다. 위치와 파일 이름은 테스트 코드가 가정하므로 옮기지 않습니다.
- 넣는 것: 동결 평가셋(`dataset_v1.jsonl`), 동결 기록(`FROZEN.json`), 평가셋 명세(`dataset-guide.md`), 사전 등록(`preregister.md`), 평가 실행기·동결 스크립트, 임베딩 프록시 표본, 평가 원시 결과(`results/`), 동결 전 초안(`drafts/`). `dataset_v2.jsonl`은 v2 동결 때, `exclusions.json`은 코퍼스가 바뀔 때 생기며 지금은 없습니다([dataset-guide.md](dataset-guide.md)).
- 넣지 않는 것: 지표 해석과 개선 전후 비교(루트 `EVAL_REPORT.md`), 단위 테스트(`tests/`), 평가가 아닌 측정 스크립트와 그 원시 결과(`scripts/`, `scripts/results/`).
- 담당: 평가·문서. 정답은 두 사람이 교차해서 정합니다.

평가셋 필드·정답 기준·동결·채점 방식의 정본은 [dataset-guide.md](dataset-guide.md)입니다.

## 파일
- `EVALS.md` — 이 문서
- `dataset-guide.md` — 평가셋 필드·관련/비관련 분류·동결·판정 방식의 정본
- `dataset_v1.jsonl` — 동결 평가셋 v1. 50건(관련 25·비관련 25), 2026-11-02 동결. `drafts/draft_50.jsonl`의 고정 키만 옮김
- `FROZEN.json` — 동결한 파일별 sha256·건수·관련/비관련 건수·동결일. 현재 `dataset_v1.jsonl` 하나. 동결 여부는 이 파일이 정함
- `preregister.md` — 바꾸기 전에 무엇을 바꾸고 어떤 지표를 기대하는지 먼저 적는 곳
- `embedding_sample_v0.jsonl` — 임베딩 후보를 거르는 비동결 프록시 표본(30청크·18질의). 실제 코퍼스 평가와 구분
- `freeze.py` — 평가셋 sha256·건수를 `FROZEN.json`에 기록. `uv run python evals/freeze.py dataset_v1.jsonl`(동결), `--check`(동결 뒤 바뀐 파일 검사)
- `benchmark_embeddings.py` — 프록시 표본의 dense Recall@5·MRR·지연 측정. `uv run python -m evals.benchmark_embeddings --model bge-m3 --output evals/results/embedding_bge_m3_proxy_<날짜>.json`
- `run_retrieval.py` — 평가셋 관련 문항으로 `retrieve()`의 문서 Recall@k·MRR·쪽 적중@k를 재고 결과 json을 남김. `uv run python -m evals.run_retrieval <평가셋 jsonl> <결과 json> [k] [method]`. 검색 방식(`hybrid` 기본·`dense`·`bm25`)은 summary의 `method`에 적음. 회로 근거만 있는 문항은 세지 않음. 문항에 `question` 키가 있으면 그것으로, 없으면 `input` 전체로 검색함. `dataset_v1.jsonl`에는 `question`이 없어 v1 베이스라인은 회로명·넷리스트 경로·조건이 붙은 `input` 전체로 검색하고, 11-01 실험(preregister #4~#8, `drafts/draft_50.jsonl`)은 `question`만으로 검색했으므로 두 점수는 바로 비교할 수 없음. 질의 필드를 바꾸려면 먼저 `preregister.md`에 등록
- `run_graph.py` — 평가셋 문항(전부 또는 고른 id)을 줄기 그래프로 끝까지 돌려 문항마다 Langfuse 트레이스(단계별 입력·출력, LLM 토큰·비용)와 실행 점수(경로·질문 종류·검색 횟수·LLM 호출 수·카드 수·인용 검사·시간)를 남김. `uv run python -m evals.run_graph <평가셋 jsonl> [문항 id ...]`. 한 번 실행한 문항은 session 하나로 묶고 환경 이름은 `eval`. 문항별 결과 파일은 카드 내용이 들어가 저장소에 남기지 않음. 답이 맞았는지는 채점하지 않음. 비용은 Langfuse 프로젝트에 등록한 OpenRouter 가격표(`anthropic/claude-haiku-5.5`, ADR 0010 가격)로 계산됨
- `run_skill_pair.py` — preregister #17 순차 평가 실행기. `DEMO_MODE=0 uv run python -m evals.run_skill_pair <새 결과 폴더>`. 그림의 노드 순서로 준비 상태를 저장한 뒤 동일 상태에서 Skill 유무 답변을 비교. 생성 거절 경로·부분 결과·해시·예약비용을 기록하며 expected 충족률은 검토 전 null. 서비스 그래프·MCP 통합 검증은 아님. 결과는 새 결과 폴더에 쓰며 요약만 `results/skill_tool_summary_*.json`으로 둠
- `drafts/` — 동결 전 평가셋 초안과 검수 기록(실행·동결 금지, 이력 보존). 목록은 [drafts/DRAFTS.md](drafts/DRAFTS.md)
- `results/` — 평가 원시 결과. 파일은 `<무엇>_<YYYY-MM-DD>.json`이고 폴더 설명 파일은 두지 않음. 평가가 아닌 측정은 `scripts/results/`
  - `chunking_proxy_2026-11-01.json`·`chunking_search_2026-11-01.json` — 청킹 개선 전후 비교(프록시 카드 수·해석 가능 값 / 11문항 검색 지표)
  - `hybrid_search_2026-11-01.json` — dense·BM25·하이브리드 검색 비교(11문항, RRF k=60)
  - `embedding_<모델>_proxy_2026-10-30.json`·`embedding_<모델>_proxy_offline_2026-10-30.json` — 임베딩 프록시 측정(`benchmark_embeddings.py`). 모델은 `bge_m3`·`kure_v1`·`qwen3_0_6b`, `text_embedding_3_small`은 온라인 한 파일만 있음(7개)
  - `retrieval_baseline_2026-11-03.json`·`retrieval_dense_2026-11-03.json`·`retrieval_bm25_2026-11-03.json` — v1 데이터시트 근거 19문항의 검색 지표(`run_retrieval.py`, k=5). 각각 하이브리드·dense만·BM25만. 하이브리드 파일은 `method` 인자가 생기기 전에 만들어 summary에 `method`가 없음
  - `draft50_second_pass_2026-11-02.json` — 50건 초안의 문항 구조·NET 해시·PDF 해시 및 문항별 보조 검증 원시 기록(`drafts/second_pass_50_review.md`의 원본)
  - `draft52_validation_2026-11-02.json` — 추가 두 건의 2차 O 기록 전 스냅샷. 당시 52건 구성·기존 질문 보존·변경 이력·NET/PDF 해시 확인. 사람 검수·평가 실행·동결 결과가 아님
  - `skill_tool_summary_2026-11-03.json` — Skill·도구 판단 개발 검증 요약, 미충족 사례·트레이스와 원본 6개 해시. 상세 실행 JSON은 저장소 밖에 보관하며 동결 평가 점수와 구분
  - `.gitkeep` — 빈 폴더 유지용

임베딩 결과의 수치와 공통 해석은 루트 [EVAL_REPORT.md](../EVAL_REPORT.md), 후보 13종을 선정한 이유·개별 실행 과정·중단 사유·다음 조건은 [embedding-candidate-investigation.md](../docs/research/embedding-candidate-investigation.md)를 봅니다. 2026-11-02 확장 평가기·실제 PDF 표본·원시 결과는 저장소에 없어 재현할 수 없습니다. 차단 결과는 Recall@5·MRR 0점이나 품질 탈락으로 환산하지 않습니다.

`embedding_sample_v0.jsonl`은 후보를 거르는 비동결 프록시이며 v1·v2나 G5 건수에 포함하지 않습니다. 실제 모델 결정은 TSC 1,360건 실제 청크 평가를 별도 사전 등록한 뒤 수행합니다.

평가셋 필드·정답 기준·동결·채점 방식은 [dataset-guide.md](dataset-guide.md)가 정본입니다.
