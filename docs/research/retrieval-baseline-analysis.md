# 동결 v1 검색 베이스라인의 방식별 문항 대조와 실패 유형

- 상태: 현행
- 기준일: 2026-11-03
- 기준 커밋: 6707002 (원시 결과 3개 파일 재계산 기준)
- 정본 여부: 정본(방식별 문항 대조와 실패 유형 4종). 최종 수치의 정본은 [EVAL_REPORT.md](../../EVAL_REPORT.md) 2·3-1·5장
- 관련 문서: [EVAL_REPORT.md](../../EVAL_REPORT.md), [검색 층별 재측정](retrieval-layered-rerun-2026-11-03.md), [ADR 0008](../adr/0008-평가-정보부족-구분과-52건-초안.md), [답변·거절 채점기](../experiments/answer-refusal-scorer.md), [30건 검수 초안](../experiments/evaluation-draft-30.md)

## 1. 질문과 결론

질문: 동결 v1의 데이터시트 근거 관련 문항 19건에서 dense, BM25, hybrid 검색이 정답 문서와 쪽을 얼마나 찾고, 어디서 실패하는가.

| 항목 | dense | bm25 | hybrid | 근거 |
|---|---:|---:|---:|---|
| 문서 Recall@5 | 0.684 (13/19) | 0.263 (5/19) | 0.737 (14/19) | 원시 `summary.doc_recall@5` |
| 문서 MRR | 0.589 | 0.195 | 0.649 | 원시 `summary.doc_mrr` |
| Page Hit@5 | 0.263 (5/19) | 0.211 (4/19) | 0.368 (7/19) | 원시 `summary.page_hit@5` |
| 응답 시간 p50 | 1.386초 | 0.197초 | 1.485초 | 원시 `summary.sec_p50` |

원시 결과: `evals/results/retrieval/retrieval_dense_2026-11-03.json`, `retrieval_bm25_2026-11-03.json`, `retrieval_baseline_2026-11-03.json`(hybrid). 건수는 행에서 다시 센 값이다.

dense 대비 hybrid: 문서 적중 개선 1건(`draft30-e08`), 악화 0건. Page Hit 개선 5건(`draft30-m05`, `draft30-h05`, `draft50-n01`, `draft50-n06`, `draft50-n07`), 악화 3건(`draft30-h04`, `draft50-n03`, `draft52-n21`). 1~4문항 차이라 부호 검정으로 유의성을 단정하지 않는다.

## 2. 방법과 환경

| 항목 | 값 |
|---|---|
| 데이터셋 | `evals/dataset_v1.jsonl`. 동결 50건 중 데이터시트 근거가 있는 관련 19문항. 제외: 회로 넷리스트 근거만 있는 6건(`e01`, `e02`, `m01`, `m02`, `h01`, `h02`) |
| 실행기 | `evals/runners/run_retrieval.py` |
| 조건 | 무필터, `input` 전체를 질의로 사용, `k=5` |
| 지표 | `gold_chunks`의 PDF 파일명이 상위 `k`개에 있으면 문서 적중, 파일명과 쪽 번호가 모두 있으면 Page Hit. 규칙 기반(정확 일치) |
| 그래프 실행·인용 검사 | `evals/runners/run_graph.py`와 5지표 채점 `evals/runners/score_answer.py`(`cited_gold`, `wrong_citation`, `over_refusal`, `correct_refusal`, `hallucination_risk`)는 규칙 기반. 인용한 `(PDF 파일명, 쪽)` 또는 `[넷리스트]`가 `gold_chunks`와 맞고 허위 인용이 없는지만 결정적으로 검사한다. 자유 서술의 수치·시험 조건·판정 논리가 `expected`와 의미상 일치하는지는 자동 판정하지 않는다([채점기](../experiments/answer-refusal-scorer.md)) |

판정 출처 (평가셋 정답 작성·검수):
- 초기 30건(`e01`~`h10`): 질문 초안은 김재훈이 정답과 `gold_chunks`를 비운 채 작성([evaluation-draft-30.md](../experiments/evaluation-draft-30.md)), 이후 코퍼스 원문 대조로 정답·근거를 채우고 하정운·김재훈이 교차 검수. 이 줄은 작성 당시 문서의 서술이며 저장소의 다른 파일로 다시 확인하지 못했다.
- 추가 문항(`n01`~`n21`)과 v2 추가 20건(`draftv2-n01`~`n20`): 정답·원문을 보지 않은 AI 초안 작성과 원문 대조를 분리한 뒤 하정운·김재훈이 검수·합의했다. AI 역할 분리는 사람 독립 출제의 증거로 쓰지 않는다([ADR 0008](../adr/0008-평가-정보부족-구분과-52건-초안.md)). 본편 합의 43건·기계 대조 7건의 구성은 ADR 0008 23행.

## 3. 결과: 19문항 방식별 순위와 Page Hit

표기: `순위 (Page Hit)`. 순위는 정답 문서의 최고 순위(상위 5 밖이면 `-`), O/X는 정답 Page Hit. 원시 행에서 생성했다. 정답 쪽 번호는 `gold`의 기록 순서다.

| 문항 ID | 정답 문서 (쪽) | dense | bm25 | hybrid | dense 대비 hybrid 변화 |
|---|---|---:|---:|---:|---|
| `draft30-e03` | 1N5817 SERIES_H2104.pdf (1) | 1 (O) | - (X) | 1 (O) | - |
| `draft30-e04` | 1N4148 SERIES_K2301.pdf (2,1) | 1 (O) | 2 (O) | 1 (O) | - |
| `draft30-e05` | 1N5817 SERIES_H2104.pdf (1,5) | 1 (X) | - (X) | 1 (X) | - |
| `draft30-e08` | SS32 SERIES_Q2412.pdf (1,2) | - (X) | - (X) | 1 (X) | 문서 적중 개선(dense→hybrid) |
| `draft30-m03` | BZT52C2V4 SERIES_G1804.pdf (2,3) | - (X) | - (X) | - (X) | - |
| `draft30-m04` | BZT52C2V4 SERIES_G1804.pdf (1,6,2) | 2 (X) | - (X) | 3 (X) | - |
| `draft30-m05` | 1N4148 SERIES_K2301.pdf (1) | 1 (X) | - (X) | 1 (O) | Page Hit 개선(dense→hybrid) |
| `draft30-m07` | BZX84C2V4 SERIES_F2001.pdf (2,1) | 1 (X) | - (X) | 1 (X) | - |
| `draft30-h04` | 1N5817 SERIES_H2104.pdf (1) | 1 (O) | - (X) | 1 (X) | Page Hit 회귀(dense→hybrid) |
| `draft30-h05` | 1N5817 SERIES_H2104.pdf (1,2) | 1 (X) | 1 (O) | 1 (O) | Page Hit 개선(dense→hybrid) |
| `draft50-n01` | 1N5817 SERIES_H2104.pdf (1,2) | 5 (X) | 1 (O) | 1 (O) | Page Hit 개선(dense→hybrid) |
| `draft50-n02` | BAS70 SERIES_G2606.pdf (1,3) | - (X) | 5 (X) | - (X) | 문서 적중 회귀(bm25→hybrid) |
| `draft50-n03` | 1N4148 SERIES_K2301.pdf (2) | 2 (O) | - (X) | 1 (X) | Page Hit 회귀(dense→hybrid) |
| `draft50-n04` | BZT52C2V4 SERIES_G1804.pdf (2,3,1) | - (X) | - (X) | - (X) | - |
| `draft50-n05` | BZT52C2V4 SERIES_G1804.pdf (1,4) | - (X) | - (X) | - (X) | - |
| `draft50-n06` | 1N4148 SERIES_K2301.pdf (2) | 1 (X) | 1 (O) | 1 (O) | Page Hit 개선(dense→hybrid) |
| `draft50-n07` | 1N5817 SERIES_H2104.pdf (1) | 1 (X) | - (X) | 2 (O) | Page Hit 개선(dense→hybrid) |
| `draft50-n08` | 1N4148 SERIES_K2301.pdf (1) | - (X) | - (X) | - (X) | - |
| `draft52-n21` | 1N5817 SERIES_H2104.pdf (2) | 1 (O) | - (X) | 2 (X) | Page Hit 회귀(dense→hybrid) |

## 4. 검색 실패 유형 4종

| 유형 | 해당 문항 | 원인 | 적용된 조치와 근거 | 남은 한계 |
|---|---|---|---|---|
| 1. 입력의 회로명·넷리스트 경로 토큰 오염 | `e03`, `e05`, `h04`, `n02`, `n03`, `n07`, `n08`, `n21`. BM25 문서 미적중 14/19(위 표), hybrid Page Hit 회귀 `h04`, `n03`, `n21` | `dataset_v1.jsonl`에 `question` 키가 없어 `input` 전체(회로 이름, 넷리스트 경로, 대상 기호)로 검색한다. 토크나이저가 `supply`, `power`, `driver`, `circuit`, `d1`~`d3` 같은 비질문 토큰을 뽑아 일부 문서(`BAT201M3_B2609.pdf`, `1N4148W SERIES_K1804.pdf`, `TESDS5V0A_D15.pdf`)를 BM25 상위권에 올린다 | 그래프 `parse_input`이 입력을 칸으로 나누고(`backend/graph/nodes.py:46`) 검색에는 `question` 칸을 쓴다. 사전 등록 #16 비교: `질문:` 줄만 쓰면 BM25 MRR 0.195 → 0.939(0.939는 [embedding-grid-eval](embedding-grid-eval-2026-11-02.md) 표) | 질문 줄 안의 조건 숫자(`25°C`, `5mA`)나 대상 기호가 일반 정격표·마킹 행과 토큰이 겹친다 |
| 2. 시리즈 대표 문서명과 개별 품번 차이, 자매 문서 혼동 | `m03`, `n04`, `n05`, `n08`, `n02`. hybrid 문서 미적중 5건 전부(원시: `rank`=null 5건) | 한 PDF가 여러 품번을 묶어 파일명에는 시작 품번만 있고, 접미사 자매 문서(`1N4148W`, `BZT52B2V4`, `BZT52C2V7K`, `BZX585B2V4`)가 코퍼스에 함께 있다. 필터 없이 검색하면 시험 조건이 같은 다른 시리즈·자매 문서 청크가 상위를 차지한다 | `retrieve(parts=...)`의 표지 청크 기반 정확 품번 필터, 그래프 `search` 노드의 품번 추출, `grade` 노드의 형제 품번 행 제거 규칙(`SPEC.md` 2·4절) | 품번이 없는 후보 탐색 질문이나 표지 표기와 다른 접미사·하이픈 변형은 정확 일치 필터에 걸리지 않는다 |
| 3. 표지 청크(`page=null`)·주문 코드 표의 상위 점유와 한영 용어 간극 | `e05`, `e08`, `m04`, `m07`, `n03`, `n21`. 문서는 1~3위로 찾았으나 쪽 미적중(위 표 hybrid 열) | 품번을 나열한 표지 청크와 `ORDERING INFORMATION` 행이 품번 토큰 일치로 최상위를 차지한다. 한국어 속성어("역회복 시간", "역방향 누설전류")가 영문 표 항목명(`Reverse recovery time`, `Reverse current`)과 달라 세부 표 행이 5위 밖으로 밀린다 | 그래프 `grade`에서 통과 청크가 없으면 `rewrite` 노드가 영문 파라미터명으로 재작성해 재검색. 리랭커 `rerank-3`은 기준 칸에서 MRR 0.649 → 0.860으로 채택 후보([preregister](../../evals/guides/preregister.md) 145행). 적용은 별도 사전 등록 | 첫 검색에서 같은 문서의 다른 쪽이 `grade`를 통과하면 재작성 없이 멈출 수 있다 |
| 4. 다중 쪽 근거·도면/곡선 쪽 동시 회수 한계 | `e05`(1쪽+5쪽 도면), `m04`(1·2쪽+6쪽 권장 패드), `n02`(1쪽+3쪽 곡선 조건), `n04`(1·2쪽+3쪽 주석), `n05`(1쪽+4쪽 곡선) | 정격표(1~2쪽), 표 밖 주석(3쪽), 곡선·외형 치수(3~6쪽)가 함께 필요한 문항은 `k=5` 안에 모든 쪽이 들어오기 어렵다. 도면·곡선 쪽은 텍스트가 짧아 순위가 낮다 | 청킹 개선으로 표 제목·품번을 행 청크마다 붙였다. 표 밖 주석과 도면·곡선 쪽 회수는 부족하며 청킹 개선·`k` 확대·리랭킹은 사전 등록 실험 후보 | 곡선 내부 수치(예: `n02` Fig.2)는 텍스트 파싱만으로 보장값 여부를 확정할 수 없어 "문서로 확인 안 됨"(`NOT_VERIFIED`) 경계로 다룬다 |

## 5. 한계

1. 문서 Recall@k와 MRR은 파일명 일치만 본다. 표지 청크(`page=null`)나 다른 쪽 청크만 올라와도 문서 적중으로 센다. 정답 쪽 포함 여부는 Page Hit@k가 따로 본다.
2. 복수 쪽 근거가 필요한 문항(`e05`, `m04`, `n01`, `n02`, `n04`, `n05`)도 한 쪽만 맞으면 Page Hit@5가 참이다.
3. 검색된 청크가 질문의 조건·수치를 실제로 담았는지는 채점하지 않는다.
4. 19문항이라 방식 간 차이는 1~4문항이다.
5. 유형 1의 하이브리드 MRR 0.649 → 0.869(`질문:` 줄만 사용)와 필터 단독 효과(동결 v1)는 이 문서가 원시로 확인하지 못했다. 사전 등록 후 측정이 필요하다.
6. 이전 판본의 문항별 서술(각 행의 청크 순위 변화 원인)은 원시 행의 상위 5개만으로 다시 확인할 수 없어 싣지 않았다.
