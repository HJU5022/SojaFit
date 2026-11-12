# 용어집

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 정본(문서·주석에서 쓰는 용어). 각 용어의 구현 정의는 코드와 [SPEC.md](../../SPEC.md)가 우선한다
- 관련 문서: [REFERENCE.md](REFERENCE.md), [EVAL_REPORT.md](../../EVAL_REPORT.md), [MULTI_AGENT.md](../../backend/multi_agent/MULTI_AGENT.md)

문서와 주석은 "쓰는 말"을 쓴다. "같은 뜻의 다른 표기"는 지난 기록을 읽을 때 찾아보기 위한 열이다.

## 1. 검색·평가

| 쓰는 말 | 영어 | 뜻 | 같은 뜻의 다른 표기 |
|---|---|---|---|
| 청크 | chunk | DB(`document_chunks`)에 저장하는 검색 단위. 데이터시트 표 한 행이 청크 하나이고 문서마다 표지 청크 1개와 표 밖 글 청크가 더 있다(`backend/rag/pipeline/chunk.py`) | |
| 카드 | card | 표 한 행으로 된 청크. 판정 값과 후보 찾기는 카드 도구(`backend/rag/card_specs.py`, `card_find.py`)가 카드를 그때그때 읽는다([ADR 0016](../adr/0016-사양-표를-버리고-카드-읽기를-기본으로-한다.md)). 청크 전체를 카드라고 부른 문서도 있다 | |
| 표지 청크 | cover chunk | 문서의 품번 목록만 적은 청크(`page_number` 없음). 서비스 검색은 늘 뺀다([SPEC.md](../../SPEC.md) 6절) | 표지 카드 |
| top-k | top-k | 검색이 돌려주는 상위 청크 k개. 서비스 기본 5(`backend/rag/retrieve.py:163` `retrieve(..., k=5)`) | 상위 k장 |
| 정답 페이지 | gold page | 질문의 답이 적힌 데이터시트 페이지 | 정답 쪽 |
| 기준선 | baseline | 비교의 기준이 되는 설정 | 베이스라인, 기준 |
| 평가셋 v1·v2·v3 | eval set | 동결한 공식 평가셋(`evals/dataset_v*.jsonl`, 해시는 `evals/FROZEN.json`). v1 2026-11-02 50건, v2 2026-11-03 70건, v3 2026-11-10 50건. 기준은 v3 | |
| R1 검색 평가셋 | retrieval set | 검색만 재려고 사양 표로 정답 페이지를 정한 84문항(`evals/samples/retrieval_r1.jsonl`). 사람 판정은 없다 | R1 표본 |
| dev 세트, test 세트 | dev / test (hold-out) | R1을 PDF 단위로 나눈 두 묶음. dev 46문항으로 조합을 고르고, 고를 때 쓰지 않은 test 38문항으로 확인한다(`retrieval_r1.jsonl`의 `split`) | 고르기용, 확인용 |
| 사전 등록 | pre-registration | 측정 전에 조건·지표·기대 범위를 `evals/guides/preregister.md`에 커밋하고 측정 뒤 고치지 않는 것 | 사전등록 |
| 쿼리 재작성 | query rewriting | 검색 전에 LLM이 질문을 영어 검색어로 바꾸는 단계(`rewrite()`) | 질의 재작성, 질문 재작성 |
| 표지 청크 제외 | | 표지 청크를 검색 후보에서 빼는 필터(품번 필터와 함께 쓰면 "품번 + 카드 종류" 칸) | 표지 빼기 |

## 2. 지표

| 쓰는 말 | 뜻 | 같은 뜻의 다른 표기 |
|---|---|---|
| Page Recall@k | 정답 페이지 중 top-k 안에 든 비율 | 쪽 회수율@k |
| Page Hit@k | 정답 페이지가 하나라도 top-k 안에 든 문항 비율 | 쪽 적중@k |
| Full Recall@k | 정답 페이지를 전부 top-k 안에 찾은 문항 비율 | 모든 근거@k |
| Page MRR | 첫 정답 청크 순위의 역수 평균(10위 밖은 0) | 쪽 MRR |
| Page nDCG@k | 정답 페이지가 위에 있을수록 높은 점수(같은 페이지는 한 번만 셈, 만점 1; `evals/runners/run_retrieval_layers.py`) | 쪽 nDCG@k |

## 3. 판정

| 쓰는 말 | 뜻 | 같은 뜻의 다른 표기 |
|---|---|---|
| N승 M패 | 문항별로 견줘 나아진 문항 N개, 나빠진 문항 M개 | |
| 개선, 악화 | 순 차이(승 − 패) +5문항 이상이고 부트스트랩 95% 신뢰구간 하한 > 0이면 개선, 그 반대면 악화(`evals/guides/preregister.md:327`) | |
| 유의차 없음 | 개선·악화 기준에 못 미침. "같다"는 뜻이 아니다 | 차이 입증 못 함 |

## 4. 멀티 그래프 노드

노드 이름은 `backend/multi_agent/build.py`가 그래프에 붙인 이름과 같다.

| 쓰는 말 | 뜻 | 같은 뜻의 다른 표기 |
|---|---|---|
| Supervisor(계획) | 질문 종류와 할 일(최대 3개)을 정하는 LLM 노드 `Supervisor` | Supervisor ① |
| RAG 에이전트 | 검색 → 근거 채점 + 답 쓰기 → 인용 검사를 하는 서브에이전트(`backend/multi_agent/agents/docs.py`) | 문서 에이전트, 검색 에이전트 |
| Spec 에이전트 | 회로 읽기 → 대체 부품 판정을 하는 서브에이전트(`backend/multi_agent/agents/judge.py`). 숫자 비교는 `backend/judge/` | 판정 에이전트, 판정 서브에이전트 |
| 답 모으기 | 보고를 모아 다음 길을 정하는 코드 노드 | Supervisor ② |
| 종합 | 할 일 2개 이상의 부분 답을 합치는 LLM 노드 | Supervisor ② |

## 5. 바꾸지 않은 표기

- LLM이 읽는 글은 "카드"를 그대로 쓴다: `backend/prompts/`의 프롬프트, `backend/mcp_skill/`의 도구 설명, `backend/graph/nodes.py`의 채점 입력과 출력 스키마 설명. 바꾸면 모델 입력이 달라져 지난 측정과 견줄 수 없다.
- 데이터: 동결 평가셋, `evals/samples/`의 jsonl, `evals/results/`의 측정 결과, `db/`의 SQL.
- 측정 결과 파일 안의 칸 이름(예: `part+kind`, `S2 +표지 빼기`)은 찍힌 그대로다.
- "모델 카드"(Hugging Face model card)는 청크와 다른 말이다.
- 파일 이름과 링크: ADR 0017 파일 이름·제목의 "판정 에이전트", ADR 0008 파일 이름의 "정보부족".
- LLM 출력 스키마로 가는 `contracts.Plan` 설명의 "Supervisor ①"은 모델 입력이라 그대로다.

## 6. 한계

- 위 표 중 코드·파일로 대조한 것: 노드 이름, top-k 기본값, 평가셋 건수·동결일, R1 건수와 dev/test 분할, 개선·악화 기준. 지표(Page Recall, Hit, Full Recall, MRR) 정의는 이전 문서의 정의를 옮겼고 이번에 코드와 대조하지 않았다(nDCG는 `run_retrieval_layers.py:458`에 구현이 있음을 확인).
- 문서 전체에서 같은 개념에 둘 이상의 표기가 함께 쓰인다: "정답 쪽"과 "정답 페이지", "쪽 적중"과 "Page Hit", "사전 등록"과 "사전등록", "문서 에이전트"·"판정 에이전트"와 "RAG 에이전트"·"Spec 에이전트".
