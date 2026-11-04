# 동결 v1 검색 베이스라인 방식별 문항 대조와 실패 유형 분석

- 작성일: 2026-11-03
- 기준 데이터셋: `evals/dataset_v1.jsonl` (동결 v1 50건 중 데이터시트 근거가 있는 관련 19문항; 회로 전용 6문항 `e01, e02, m01, m02, h01, h02` 제외)
- 원시 결과: `evals/results/retrieval/retrieval_baseline_2026-11-03.json`(`hybrid`), `evals/results/retrieval/retrieval_dense_2026-11-03.json`(`dense`), `evals/results/retrieval/retrieval_bm25_2026-11-03.json`(`bm25`)
- 목적: `EVAL_REPORT.md` 2장(출제·근거 분리, 판정 방식과 한계), 3-1절(방식별 좋아진·회귀한 문항 분석), 5장(검색 실패 유형 4종)에 들어갈 상세 대조 근거를 기록한다.

---

## 1. 평가셋 출제·근거 분리 및 채점 방식·한계 (`EVAL_REPORT.md` 2장 반영 대상)

- **질문을 쓴 사람과 정답 청크를 찾은 사람이 다른가**:
  - 초기 30건(`e01~h10`)은 김재훈이 정답과 `gold_chunks`를 비운 채(`null`/`[]`) 질문 초안을 먼저 작성했고([evaluation-draft-30.md](../experiments/evaluation-draft-30.md)), 그 뒤 코퍼스 원문 대조로 정답·근거를 채운 뒤 하정운·김재훈이 교차 검수했다.
  - 추가 문항(`n01~n20`, `n21`)과 v2 추가 20건(`draftv2-n01~n20`)은 정답·원문을 보지 않은 AI 초안 작성과 원문 대조를 분리한 뒤 하정운·김재훈이 검수·합의했다(AI 역할 분리는 사람 독립 출제 증거로 쓰지 않음, [ADR 0008](../adr/0008-평가-정보부족-구분과-52건-초안.md)).
- **판정 방식과 한계**:
  - **검색 지표(`evals/runners/run_retrieval.py`)**: 규칙 기반(정확 일치). 관련 문항 중 회로 넷리스트 근거만 있는 6건(`e01, e02, m01, m02, h01, h02`)과 열린 정답인 후보 찾기 문항(`question_type == 'candidate_find'`, v2 10건)을 뺀 데이터시트 근거 19건에서 `gold_chunks`의 PDF 파일명과 페이지 번호가 상위 `k`개 청크에 들어 있는지 잰다.
    - 한계: ① 문서 Recall@k와 MRR은 파일명 일치만 보므로 표지 청크(`page=null`)나 다른 쪽 청크만 올라와도 문서 적중으로 세며(실제 정답 페이지 포함 여부는 `page_hit@k`로 따로 본다), ② 복수 쪽 근거가 모두 필요한 문항(`e05, m04, n01, n02, n04, n05`)에서도 한 쪽만 맞으면 `page_hit@k`가 참이 되고, ③ 검색된 청크가 질문의 조건·수치를 실제로 담고 있는지는 채점하지 않는다.
  - **그래프 실행·인용 검사(`evals/runners/run_graph.py`) 및 답변·거절 5지표 채점(`evals/runners/score_answer.py`)**: 규칙 기반. 실행 경로(`path`), 검색 횟수(`tries`), 거절 여부(`not_found`), 통과 청크 번호 밖의 허위 인용(`fake_citations`), 인용 번호가 빠진 문장(`uncited_sentences`)과 함께, 문항별 `gold_chunks`·`kind`를 대조해 5지표(`cited_gold`, `wrong_citation`, `over_refusal`, `correct_refusal`, `hallucination_risk`)를 코드로 판정한다([answer-refusal-scorer.md](../experiments/answer-refusal-scorer.md)).
    - 한계: 인용한 청크의 `(PDF 파일명, 페이지 번호)` 또는 `[넷리스트]`가 `gold_chunks`와 맞고 허위 인용이 없는지를 결정적으로 검사할 뿐, 자유 서술 문장의 수치·시험 조건·판정 논리가 `expected`와 의미상 완전히 일치하는지는 LLM 없이 자동 판정하지 않는다.

---

## 2. 방식별 문항 대조 (`EVAL_REPORT.md` 3-1절 반영 대상)

### 2-1. 19문항 전체 순위·Page Hit 대조표 (`input` 전체 질의, 무필터, `k=5`)

| 문항 ID | 정답 문서 (쪽) | `dense` 순위 (`page_hit`) | `bm25` 순위 (`page_hit`) | `hybrid` 순위 (`page_hit`) | 변화 요약 (`dense → hybrid` / `bm25 → hybrid`) |
|---|---|---:|---:|---:|---|
| `draft30-e03` | `1N5817 SERIES_H2104.pdf` (1) | 1 (`False`) | `None` (`False`) | 1 (`False`) | 유지 (표지·2쪽 청크만 상위 5, 1쪽 `VRRM` 행은 `dense` 22위·`bm25` 46위) |
| `draft30-e04` | `1N4148 SERIES_K2301.pdf` (2) | 1 (`True`) | 1 (`True`) | 1 (`True`) | 유지 |
| `draft30-e05` | `BZT52C2V4 SERIES_G1804.pdf` (1, 5) | 1 (`False`) | `None` (`False`) | 1 (`False`) | 유지 (표지·2쪽 청크만 상위 5) |
| `draft30-e08` | `SS32 SERIES_Q2412.pdf` (1, 2) | `None` (`False`) | `None` (`False`) | **1** (`False`) | **문서 적중 개선**: `dense` 8·14·15위와 `bm25` 11·33·34위였던 `SS32` 청크가 RRF 합산으로 1~4위 진입 |
| `draft30-m03` | `BZT52C2V4 SERIES_G1804.pdf` (2) | `None` (`False`) | `None` (`False`) | `None` (`False`) | 미적중 유지 (`BZT52C3V6` 질의에 `BZT52B2V4`·`BZX84C2V4`·`BZT52C2V4S` 자매 문서가 상위 점유) |
| `draft30-m04` | `BZT52C2V4 SERIES_G1804.pdf` (1, 2, 6) | 2 (`False`) | `None` (`False`) | 3 (`False`) | 문서 순위 소폭 하락(2→3위, 상위 5 유지), 쪽 미적중 유지 |
| `draft30-m05` | `1N4148 SERIES_K2301.pdf` (1) | 1 (`False`) | `None` (`False`) | 1 (**`True`**) | **Page Hit 개선**: `dense` 16위·`bm25` 15위였던 1쪽 `VRRM 100V` 청크가 RRF로 2위 진입 |
| `draft30-m06` | `1N5817 SERIES_H2104.pdf` (2) | 1 (`True`) | 1 (`True`) | 1 (`True`) | 유지 |
| `draft30-m07` | `BZX84C2V4 SERIES_I2002.pdf` (1, 2) | 1 (`False`) | `None` (`False`) | 1 (`False`) | 유지 (표지 청크만 1위) |
| `draft30-h04` | `1N5817 SERIES_H2104.pdf` (1) | 1 (**`True`**) | `None` (`False`) | 1 (**`False`**) | **Page Hit 회귀 (`dense → hybrid`)**: `dense` 5위였던 1쪽 `KEY PARAMETERS` 청크가 `bm25` 오답 청크(`ESH1DMH`, `ESH1DM`)에 밀려 탈락 |
| `draft30-h05` | `1N5817 SERIES_H2104.pdf` (1) | 1 (`False`) | 2 (`True`) | 1 (**`True`**) | **Page Hit 개선 (`dense → hybrid`)**: `bm25` 2위·`dense` 15위였던 1쪽 정격 청크가 2위 진입 |
| `draft50-n01` | `1N5817 SERIES_H2104.pdf` (1, 2) | 5 (`False`) | 1 (`True`) | **1** (**`True`**) | **문서 순위(5→1위) 및 Page Hit 개선 (`dense → hybrid`)** |
| `draft50-n02` | `BAS70 SERIES_G2606.pdf` (1, 3) | `None` (`False`) | **5** (`False`) | `None` (`False`) | **문서 적중 회귀 (`bm25 → hybrid`)**: `bm25` 5위였던 표지 청크가 `dense` 상위 50 밖이라 `1N4148WSH`·`1N4148WH`에 밀려 탈락 |
| `draft50-n03` | `1N4148 SERIES_K2301.pdf` (2) | 2 (**`True`**) | `None` (`False`) | 1 (**`False`**) | **Page Hit 회귀 (`dense → hybrid`)**: 문서 순위는 2→1위(표지)로 올랐으나 `dense` 2위였던 2쪽 `trr` 청크가 `bm25` 미등장으로 상위 5 밖으로 밀림 |
| `draft50-n04` | `BZT52C2V4 SERIES_G1804.pdf` (1, 2, 3) | `None` (`False`) | `None` (`False`) | `None` (`False`) | 미적중 유지 (`BZT52C5V1` 질의에 `BZX585B2V4`·`BZT52B2V4`·`BZT52C2V7K`가 상위 점유) |
| `draft50-n05` | `BZT52C2V4 SERIES_G1804.pdf` (1, 4) | `None` (`False`) | `None` (`False`) | `None` (`False`) | 미적중 유지 |
| `draft50-n06` | `1N4148 SERIES_K2301.pdf` (2) | 1 (`False`) | 1 (`True`) | 1 (**`True`**) | **Page Hit 개선 (`dense → hybrid`)**: `bm25` 1위였던 2쪽 `ORDERING INFORMATION` `1N4148 R0G` 청크가 2위 진입 |
| `draft50-n07` | `1N5817 SERIES_H2104.pdf` (1) | 1 (`False`) | `None` (`False`) | 2 (**`True`**) | **Page Hit 개선 (`dense → hybrid`)**: `dense` 28위·`bm25` 21위였던 1쪽 청크가 RRF 합산으로 2위 진입 |
| `draft50-n08` | `1N4148 SERIES_K2301.pdf` (1) | `None` (`False`) | `None` (`False`) | `None` (`False`) | 미적중 유지 (`1N4148W SERIES_K1804.pdf` 등 자매 문서가 상위 5 점유) |
| `draft52-n21` | `1N5817 SERIES_H2104.pdf` (2) | 1 (**`True`**) | `None` (`False`) | 2 (**`False`**) | **Page Hit 회귀 (`dense → hybrid`)**: `dense` 3·5위였던 2쪽 `Reverse current` 청크가 `bm25` 상위 오답 청크(`BAT201M3`, `TESDS5V0A`, `1N4148W`)에 밀려 탈락 |

- **통계적 한계**: 데이터시트 근거 관련 문항이 19건이라 `dense` 대비 `hybrid`의 문서 적중 차이(좋아짐 1건 `e08` / 나빠짐 0건)와 Page Hit 차이(좋아짐 5건 `m05, h05, n01, n06, n07` / 나빠짐 3건 `h04, n03, n21`)는 1~4문항 범위 안이어서 부호 검정으로 유의성을 단정하지 않고 문항 목록과 원인을 함께 남긴다.

---

## 3. 검색 실패 유형 4종 분석 (`EVAL_REPORT.md` 5장 반영 대상)

| 유형 | 예시 질문 | 원인 | 조치 | 남은 한계 |
|---|---|---|---|---|
| 1. 입력의 회로명·넷리스트 경로 토큰 오염 | `e03, e05, h04, n02, n03, n07, n08, n21` (BM25 14/19 미적중, 하이브리드 Page Hit 회귀 `h04, n03, n21`) | `dataset_v1.jsonl`에 `question` 키가 없어 `input` 전체(`회로: SparkFun Breadboard Supply\n넷리스트: data/circuits/.../circuit.net\n대상: D1...`)로 검색한다. 영문·숫자 토크나이저(`tokens()`)가 `supply`, `power`, `driver`, `circuit`, `board`, `d1~d3`, `25`, `c` 같은 비질문 토큰을 뽑아 `BAT201M3_B2609.pdf`("For switching power supply / Protection circuits"), `1N4148W SERIES_K1804.pdf`, `TESDS5V0A_D15.pdf` 등을 거의 모든 문항의 BM25 상위권에 올리고 RRF 합산 슬롯을 잠식함 | 그래프 `read_input` 노드는 입력에서 `"질문:"` 줄만 떼어 `search`에 넘긴다. 사전 등록 #16에서 `"질문:"` 줄만 쓰면 BM25 MRR `0.195 → 0.939`, 3-small 하이브리드 MRR `0.649 → 0.869`로 오름을 확인했으며, `run_retrieval.py` 기준 비교는 별도 사전 등록 후 측정 | 질문 줄 안에도 사용 조건 숫자(`25°C`, `5mA`)나 대상 기호(`D1~D3`, 마킹 코드와 동형)가 있으면 일반 정격표·마킹 행과 토큰이 겹침 |
| 2. 시리즈 대표 문서명과 개별 품번 차이·자매 문서 혼동 | `m03`(`BZT52C3V6`), `n04`(`BZT52C5V1`), `n05`(`BZT52C3V6`), `n08`(`1N4148`), `n02`(`BAS70`) — 하이브리드 문서 Recall@5 미적중 5건 전부 | 한 PDF가 수십 개 품번을 묶어 파일명에는 시작 품번만 적히거나(`BZT52C2V4 SERIES_G1804.pdf` 안에 `C3V6`·`C5V1` 포함), 접미사 자매 문서(`1N4148W`, `BZT52B2V4`, `BZT52C2V7K`, `BZX585B2V4`)가 코퍼스에 함께 있다. 필터 없이 전체 청크를 검색하면 시험 조건(`TA=25°C`, `5mA`, `30ms`)이 같은 다른 시리즈·자매 문서 청크가 상위를 차지함 | `retrieve(parts=...)`의 표지 청크 기반 정확 품번 필터와 그래프 `search` 노드의 품번 추출·`grade` 노드의 형제 품번 행 제거 규칙을 적용(`SPEC.md` 2·4절). 동결 v1의 필터 단독 효과는 별도 사전 등록 후 측정 | 품번이 없는 후보 탐색 질문이나 표지 표기와 다른 접미사·하이픈 변형은 정확 일치 필터에 걸리지 않음 |
| 3. 표지 청크(`page=null`)·주문 코드 표 상위 점유와 한영 용어 간극 | `e05`(1,5쪽 누락), `e08`(1,2쪽 누락), `m04`(1,2,6쪽 누락), `m07`(1,2쪽 누락), `n03`(2쪽 누락), `n21`(2쪽 누락) — 문서는 1~3위로 찾았으나 쪽 미적중 | 품번을 나열한 표지 청크(`page=null`)와 `ORDERING INFORMATION` 행이 품번 토큰 일치로 RRF 최상위를 차지하고, 한국어 속성 질문어("역회복 시간", "역방향 누설전류", "납땜/패키지")는 영문 표 항목명(`Reverse recovery time`, `Reverse current`, `PACKAGE OUTLINE DIMENSIONS`)과 어휘가 달라 세부 표 행이 5위 밖으로 밀림 | ① 그래프 `grade`에서 통과 청크가 없으면 `rewrite` 노드가 데이터시트 영문 파라미터명으로 검색어를 재작성해 재검색, ② 후보 풀을 리랭커(`rerank-3`, 사전 등록 #16에서 하이브리드 MRR `0.649 → 0.860`)로 재정렬하는 방안을 사전 등록 후 검토 | 첫 검색에서 같은 문서의 다른 쪽이나 범위 요약 청크가 `grade`를 통과하면 재작성 단계로 가지 않고 멈출 수 있음(`jeongun.md` 11-03 `e03` 사례) |
| 4. 다중 쪽 근거·도면/곡선 쪽 동시 회수 한계 | `e05`(1쪽+5쪽 도면), `m04`(1·2쪽+6쪽 권장 패드), `n02`(1쪽+3쪽 Fig.2 곡선 조건), `n04`(1·2쪽+3쪽 주석), `n05`(1쪽+4쪽 Fig.4 곡선) | 한 판정에 정격표(1~2쪽), 표 밖 주석(Notes, 3쪽), 특성 곡선·외형 치수(3~6쪽)가 함께 필요한 문항은 `k=5` 안에 모든 쪽이 동시에 들어오기 어렵고, 그래프·도면 쪽은 텍스트가 짧아 정격표·주문표 청크보다 순위가 낮음 | 청킹 개선 2로 표 제목·품번을 행 청크마다 붙였으나 표 밖 주석(`Notes`)과 도면·곡선 쪽 회수는 여전히 부족하여, 표 옆 주석 포함 청킹 개선과 `k` 확대·리랭킹을 사전 등록 실험 후보로 둠 | 그래프 곡선 내부 수치(예: `n02` Fig.2, `m04`/`n14` Fig.5)는 텍스트 파싱만으로 보장값 여부를 완결할 수 없어 문서로 확인 안 됨(`NOT_VERIFIED`)·속성 부재 경계 지침과 함께 다뤄야 함 |
