# 평가셋 작성·동결·채점 기준

- 상태: 현행
- 기준일: 2026-11-12
- 정본 여부: 정본(평가셋 필드·관련/비관련 분류·동결·판정 방식). 평가 수치의 정본은 루트 `EVAL_REPORT.md`
- 관련 문서: [EVALS.md](../EVALS.md)(폴더 안 파일 목록), [preregister.md](preregister.md), [FROZEN.json](../FROZEN.json)

## 평가셋

G5: 최종 평가셋은 50건 이상(동결 시점 기준)이고 관련 질문과 비관련 질문이 각각 절반이다. 개선 전후를 같은 셋으로 두 번 이상 재서 회귀를 숫자로 보인다.

평가셋이 쉬우면 어떤 개선도 보이지 않는다. 같은 문항 구성이라도 코퍼스가 작으면 임베딩 모델을 바꿔도 거의 같은 점수가 나온다(30청크 프록시에서는 임베딩 후보 세 종의 Recall@5가 모두 1.000이었다. `preregister.md` #1·#2). 문항을 더할 때도 일부러 어려운 문항을 넣는다.

## 버전

기준 평가셋은 v3이다([ADR 0015](../../docs/adr/0015-평가셋-v3를-새로-만들고-청킹부터-다시-잰다.md)). v1·v2 파일과 해시는 그대로 두고, v3 이전의 측정(#31 ~ #42) 기록으로만 읽는다. v3 동결 전에는 검색 지표를 dev 세트로만 쟀고, test 세트는 마지막 확인에 썼다.

| 버전 | 동결일 | 건수 | 구성 | 해시 |
|---|---|---|---|---|
| v1 | 2026-11-02 | 50 (관련 25, 비관련 25) | n22·n13은 예비로 이관한 뒤의 50건. 변경 3건 재검수·합의와 n21 검수 후 동결 | `FROZEN.json`의 `dataset_v1.jsonl` (`2fef02c2…`) |
| v2 | 2026-11-03 | 70 (관련 35, 비관련 35) | 동결한 v1 50건 + 후보 찾기 문항 20건([ADR 0003](../../docs/adr/0003-평가셋-v1을-50건으로-동결.md)) | `FROZEN.json`의 `dataset_v2.jsonl` (`81582c59…`) |
| v3 | 2026-11-10 | 50 (관련 25, 비관련 25) | 판정 분야(후보 판정·후보 찾기) 문항을 늘리고 후보 판정 문항마다 정답 판정을 적음. 청킹 결함을 고친 코퍼스 기준 | `FROZEN.json`의 `dataset_v3.jsonl` (`05202314…`). 최초 동결 해시는 아래 "v3 판정자 정보" |

## 파일과 형식

`dataset_v1.jsonl`은 `drafts/sets/draft_50.jsonl`의 고정 키(`id`, `input`, `kind`, `irrelevant_type`, `expected`, `gold_chunks`, `why`, `as_of`, `corpus_version`)만 옮겨 만들었다. `dataset_v2.jsonl`은 v1을 복사해 건을 더한 파일이다. v1 50건 줄은 `question_type`만 더했고 나머지 칸은 v1과 같다(`tests/evals/test_frozen_evals.py`가 확인). 추가 20건은 `drafts/sets/draft_v2add_20.jsonl`의 고정 키를 옮긴 것이다. `dataset_v3.jsonl`은 아래 공통 필드에 v3 전용 필드가 붙는다.

### 공통 필드 (v1·v2·v3)

| 필드 | 뜻 |
|---|---|
| `id` | 문항 id. v1·v2는 `draft30-`·`draft50-`·`draft52-`·`draftv2-` 접두사, v3는 `v3-01`~`v3-50` |
| `input` | 모델에 주는 입력(회로·넷리스트 경로·대상·사용 조건·질문) |
| `kind` | `relevant`(핵심 요청에 답할 근거가 있거나, 아래의 사용자 조건 부족에 해당) 또는 `irrelevant`(범위 밖·대상/요청 속성/판본 근거 부재). 아래 분류 기준을 따름 |
| `irrelevant_type` | 비관련만. 아래 4종 중 하나: `out_of_domain`, `unknown_entity`, `missing_attribute`, `wrong_period`. 관련은 `null` |
| `as_of` | 정답 기준일. 코퍼스가 바뀌면 정답이 바뀌는 문항(데이터시트 개정판 교체 등)을 가려내는 근거 |
| `corpus_version` | 이 문항을 쓸 때의 코퍼스 버전(`data/manifest.jsonl`의 해시 또는 날짜와 수집 설명). v3는 전 문항이 같은 값 |
| `expected` | 정답 또는 판정 기준 |
| `gold_chunks` | 정답 근거가 있는 청크나 문서 위치. 비관련은 빈 목록 |
| `why` | 정답을 정한 기준. 팀원끼리 판단이 갈릴 때 돌아보는 근거 |
| `question_type` | v2부터. 관련 문항의 질문 종류로, 그래프 라우팅 코드와 같다: `role`(회로로 답함) · `rating`(이름 붙은 부품의 값·사양) · `candidate_judge`(특정 후보로 바꿔도 되는지) · `candidate_find`(후보 품번 없이 대체 후보를 찾음). 비관련은 `null`(`irrelevant_type`이 대신함) |

### v3 전용 필드 (`dataset_v3.jsonl`)

키 집합은 `dataset_v3.jsonl`에서 스크립트로 센 값이다.

| 필드 | 있는 문항 | 형식 | 뜻 |
|---|---|---|---|
| `judges` | 50건 전부 | 문자열 배열 | 판정자. 순서대로 1차, 최종. 전 문항이 `["심태현", "하정운"]`. 아래 "v3 판정자 정보" |
| `original_part` | `candidate_judge` 10건 | 문자열 | 회로 넷리스트에 있는 원래 부품(예: `onsemi 1N4007RLG`) |
| `candidate_part` | `candidate_judge` 10건 | 문자열 | 판정 대상 후보 부품(예: `TSC 1N4007G`) |
| `board_change` | `candidate_judge` 10건 | 불리언 | 후보 실장을 위해 기판 변경이 필요한지(`true` 6건, `false` 4건) |
| `role` | `candidate_judge` 10건 | 문자열 | 회로 역할 번호. `3.1`~`3.6`(판정 기준표의 절 번호) |
| `verdict` | `candidate_judge` 10건 | 문자열 | 정답 판정. `IDENTICAL`, `SPEC_EQUIVALENT`, `ROLE_SUFFICIENT`, `NOT_SUFFICIENT`, `NOT_VERIFIED` 중 하나 |
| `conditions` | `candidate_judge` 10건 | 객체 배열 | 판정 조건별 대조 행. 객체 키: `kind`(`required`·`major_rating`·`conditional`·`identity`), `param`, `op`(`>=`·`<=`·`same`·`comparable`), `threshold`, `threshold_basis`, `candidate_value`, `candidate_condition`, `result`(`pass`·`fail`·`unverified`), `citation` |
| `qualifying_parts` | `candidate_find` 5건 | 문자열 배열 | 조건을 모두 만족하는 코퍼스 품번 집합. 이 집합 안이면 어느 후보든 정답(열린 정답). `run_gate.py`·`run_retrieval_v3.py`가 읽음 |
| `fix_log` | v3-05, v3-09 | 객체 배열 | 정답을 고친 기록. 객체 키는 문항마다 다르다. v3-05: `date`, `by`, `change`, `reason`. v3-09: `date`, `by`, `what`, `basis` |

`judges` 외 v3 전용 필드는 `candidate_judge`·`candidate_find`에만 있고, 나머지 문항(`role` 4건, `rating` 6건, 비관련 25건)에는 없다.

## 관련·비관련과 NOT_VERIFIED의 구분

분류 기준 합의: 하정운·김재훈(2026-11-02), v1 동결에 적용. 관련 문서가 있다는 사실만으로 relevant가 되는 것은 아니며, 질문이 요청한 핵심 값·판정과 부족한 정보의 출처를 확인한다.

| 상황 | 분류·정답 기준 | 예 |
|---|---|---|
| 정격·특성 조회의 핵심 요청에 문서로 답할 수 있음 | relevant. 값의 MAX/TYP와 시험 조건을 밝혀 답하고 실제 회로 보장으로 확대하지 않음 | e04·e08·n21 |
| 적합성 판단에 쓸 후보 정격·판정 근거는 있으나 사용자의 동작 조건이 부족함 | relevant + NOT_VERIFIED. 부족한 사용자 조건을 구체적으로 밝히고 추가 정보를 요청. 조건을 임의로 채우거나 불충족으로 단정하지 않음 | n01의 TA, n02의 차단 펄스 폭·파형 |
| 핵심 요청인 수치·보장값·실측·제조사/품번을 확인할 문서 속성이 없음 | irrelevant / missing_attribute. 주변 설명이나 다른 값으로 요청 답변을 대신하지 않음 | h03·n14·e09·m08·m09·h08·h09 |

- 사용자 조건을 추가해도 필요한 문서 속성이 없으면 사용자 조건 부족만으로 relevant에 넣지 않는다. 후보 자료 부재는 unknown_entity, 요청 판본 부재는 wrong_period로 구분한다.
- 부품 정격을 답한 뒤 부가적인 대체 적합성을 미확정으로 남기는 경우(e08 등), NOT_VERIFIED라는 단어만으로 문항 전체를 irrelevant로 바꾸지 않는다.
- `kind`와 대체 판정 5종은 별도 축이다. SPEC의 NOT_VERIFIED는 대체 판정상 거절이지만 relevant 여부와 일대일 대응하지 않는다. n01·n02처럼 NOT_VERIFIED를 정답으로 명시한 문항을 정답대로 응답했을 때 단순히 그 코드가 있다는 이유로 오거절로 채점하지 않는다. 지표별 분모는 이 기준에 맞춰 확인해야 한다. 검색 평가기(`run_retrieval.py`)는 답변·거절을 채점하지 않고, 답변·거절 5지표는 `evals/runners/score_answer.py`가 채점한다.
- 데이터셋 수량을 맞추기 위해 분류를 바꾸지 않는다. v1 50건(25/25)은 n22(관련)·n13(비관련)을 예비로 이관한 결과다. 경위는 [draft_50_review.md](../drafts/reviews/draft_50_review.md).

## 비관련 질문은 4종을 섞습니다

한 종류만 쓰면 쉬운 거절만 늘어 점수가 부풀려집니다. 비관련 절반 안에서 4종이 모두 들어가야 합니다.

| `irrelevant_type` | 뜻 | 예 (v1 문항) |
|---|---|---|
| `out_of_domain` | 도메인 밖 | "Q1 AO3406 대신 쓸 MOSFET 좀 골라 줘."(e06) |
| `unknown_entity` | 코퍼스에 없는 부품이나 대상 | 코퍼스에 없는 BAT85의 정격(n09) |
| `missing_attribute` | 있는 대상이지만 코퍼스에 없는 항목 | BZT52C3V6 G1804판에 없는 1V 정전용량 보장 최댓값(n14) |
| `wrong_period` | 같은 문서인데 요청한 판본이 다름 | SS34 Q2611판을 물었는데 코퍼스에는 Q2412판만 있음(n15) |

현재 판본 지정 문항의 정답은 사람이 고정 코퍼스와 대조해 정한다. 요청 판본의 자동 확인은 미구현이며, 필요한 후속 작업은 [RAG 파이프라인 작업서](../../docs/specs/rag-pipeline.md#한계)에 기록했다. 코퍼스에 없다는 사실만으로 해당 판본이 실제로 존재하지 않는다고 판정하지 않는다.

## 질문은 정답을 보지 않고 씁니다

질문을 쓰는 사람은 정답 청크를 열어 보지 않고 질문을 씁니다. 정답을 보고 쓴 질문은 정답 문장의 낱말을 그대로 따라 쓰게 되어 검색이 쉬워집니다. 정답 청크는 다른 팀원이 나중에 찾아 `gold_chunks`에 적습니다.

## 동결

판정 출처: v1 50건은 하정운 1차 판정, 김재훈 2차 검토·수정 의견을 반영해 합의한 것이다. 2026-11-02에 동결했고(`dataset_v1.jsonl`) SHA256은 `FROZEN.json`에 있다.

판정 출처: v2 추가 20건(후보 찾기)은 출제와 정답을 나눠 쓴 자동 초안(2026-11-01)이고, 하정운 1차·김재훈 2차 사람 판정에서 모두 O였다(검토표 [draft_v2add_20_review.md](../drafts/reviews/draft_v2add_20_review.md)). v2는 2026-11-03에 동결했다(`dataset_v2.jsonl`, 70건).

후보 찾기 관련 10건은 열린 정답이다. 조건을 모두 만족하는 코퍼스 품번이면 어느 것이든 정답이고, `gold_chunks`의 후보 문서는 예시다. 그래서 `run_retrieval.py`는 이 문항을 검색 순위로 채점하지 않고 `candidate_find_skipped`에 id만 적는다.

### v3 판정자 정보

| 적용 범위 | 1차 판정자 | 최종 판정자 | 근거 |
|---|---|---|---|
| 동결 v3 50문항 | 심태현 | 하정운 | 조장 확인, 2026-11-13 |

v3 정답 초안은 Codex가 작성했고, 하정운이 문항을 검수하고 삭제·추가·수정했다. 정본은 [EVAL_REPORT.md](../../EVAL_REPORT.md) 2절 평가셋 표다.

2026-11-12에 v3 각 문항에 `judges`만 추가했다. 질문·정답·판정 기준은 유지했고 파일 해시는 변경됐다. 최초 동결 SHA-256 `2b99b2125d98db6f127d4364e2940acaf4a27aeb9ee60ef1667d5e0e3e6e5e91`의 원본은 Git 기준 `758cbcc:evals/dataset_v3.jsonl`에서 확인할 수 있다. 수정본 SHA-256은 `05202314ed1d009593ab14bc5d44e3d7ab7dd4a9f7e726f98282198c7999b4fd`이며 `FROZEN.json`의 검사 대상이다. `frozen_at`은 최초 동결일이다.

동결본과 검수 이력을 읽을 때 알아 둘 점:
- `draft_30.jsonl`·`draft_50.jsonl`의 `status`·`review_flags`·`review_hold`·`author_review`는 동결 직전까지의 검수 이력이다. "not_frozen", "do_not_freeze", "검토 전" 같은 값이 남아 있어도 동결 여부는 `FROZEN.json`이 정한다.
- id 접두사(`draft30-`·`draft50-`·`draft52-`)는 그 문항이 처음 들어간 초안을 나타낸다. 문서에서는 접두사를 빼고 e01·n21처럼 부른다.
- v1의 `corpus_version` 표기가 둘이다. 49건은 "TSC 다이오드 데이터시트 1,360건(2026-11-01 수집)"이고, n21은 `sha256:2d452ab3…`로 커밋 b9a98ae(11-01)의 `data/manifest.jsonl` 해시다. 현재 manifest는 11-02에 줄여 해시가 다르다.
- `why`가 인용하는 `TASK.md`(정답 초안 작업 지시서)·`정답판정-기준표.md`·`tsc_datasheet_list.csv`(CSV)는 저장소 밖 자료다.
- 동결본의 넷리스트 인용에는 가운뎃점이 두 종류(`・` U+30FB, `·` U+00B7) 섞여 있다. 동결 파일이라 고치지 않는다.

```bash
uv run python evals/runners/freeze.py dataset_v1.jsonl     # sha256과 건수를 FROZEN.json에 기록
uv run python evals/runners/freeze.py --check              # 동결 이후 바뀐 파일이 없는지 확인
```

동결 뒤에는 정답을 고치지 않습니다. `tests/evals/test_frozen_evals.py`가 PR마다 해시를 확인하고, 바뀌면 CI가 실패합니다. 정답이 정말 틀렸다면 파일을 고치지 말고 `docs/`에 이유를 적고 평가 담당자와 상의하세요.

### 동결 뒤에 코퍼스를 바꿨다면

코퍼스가 바뀌면 정답이 달라지는 문항이 생깁니다. 평가셋 파일은 고치지 않고 `evals/exclusions.json`에 문항 id와 사유를 적어 지표에서만 뺍니다. 사유를 공개하는 것이 조건이며, 제외 때문에 50건 밑으로 줄어도 감점하지 않습니다. `EVAL_REPORT.md` 2장에 제외 건수를 적으세요.

```json
{"as_of": "2026-11-08", "excluded": [{"id": "draft50-n15", "reason": "SS34 새 개정판을 수집해 정답 문서가 바뀜"}]}
```

## 판정 방식

정확 일치, 스키마 통과, 규칙 기반, LLM-as-judge 모두 가능합니다. 다만 어떤 방식이고 한계가 무엇인지 `EVAL_REPORT.md`에 적어야 합니다. 생성 모델과 판정 모델은 같은 것으로 두지 마세요. 후한 점수가 나옵니다.

청크 id가 일치하는지만 보면 "답이 질문에 맞는가"는 알 수 없습니다. 한계로 적으세요. 하나의 정확도로 합치지 말고 `EVAL_REPORT.md` 2장의 지표 5개로 나눠 보고합니다.

## 결과 보관

재측정 결과의 원시 파일은 `evals/results/`에 둡니다. 평가자가 샘플 몇 문항을 다시 돌려 숫자가 맞는지 보므로, 한 줄 재현 명령을 `EVAL_REPORT.md` 9장에 적으세요. 이 폴더의 재현 명령 목록은 [EVALS.md](../EVALS.md)의 "재현 명령"에 있다.
