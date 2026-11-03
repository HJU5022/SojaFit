# evals

## 역할
- 이 폴더: 평가셋 v1·v2, 동결 해시, 제외 목록, 평가 실행 스크립트, 원시 결과를 둡니다. 위치와 파일 이름은 테스트 코드가 가정하므로 옮기지 않습니다.
- 넣는 것: `dataset_v1.jsonl`, `dataset_v2.jsonl`, `FROZEN.json`, `exclusions.json`, `freeze.py`, `PREREGISTER.md`, 평가 실행 스크립트, `results/`.
- 넣지 않는 것: 지표 해석과 개선 전후 비교(루트 `EVAL_REPORT.md`), 단위 테스트(`tests/`).
- 담당: 평가·문서. 정답은 두 사람이 교차해서 정합니다.
- 이 문서는 평가셋 필드·정답 기준·채점 방식의 정본입니다.

## 파일
- `dataset_v1.jsonl` — 평가셋 v1. 50건(관련 25·비관련 25), 2026-11-02 동결. `draft_50.jsonl`의 고정 키만 옮김
- `FROZEN.json` — 동결한 파일별 sha256·건수·관련/비관련 건수·동결일. 현재 `dataset_v1.jsonl` 하나. 동결 여부는 이 파일이 정함
- `embedding_sample_v0.jsonl` — 임베딩 후보를 거르는 비동결 프록시 표본(실제 코퍼스 평가와 구분)
- `benchmark_embeddings.py` — 프록시 표본의 dense Recall@5·MRR·지연 측정
- `freeze.py` — 동결 파일의 sha256을 `FROZEN.json`에 기록
- `run_retrieval.py` — 평가셋 관련 문항으로 `retrieve()`의 문서 Recall@k·MRR·쪽 적중@k를 재고 결과 json을 남김. 네 번째 인자로 검색 방식(`hybrid` 기본·`dense`·`bm25`)을 고르고 summary의 `method`에 적음. 회로 근거만 있는 문항은 세지 않음. 문항에 `question` 키가 있으면 그것으로, 없으면 `input` 전체로 검색함. `dataset_v1.jsonl`에는 `question`이 없어 v1 베이스라인은 회로명·넷리스트 경로·조건이 붙은 `input` 전체로 검색하고, 11-01 실험(PREREGISTER #4~#8, `draft_50.jsonl`)은 `question`만으로 검색했으므로 두 점수는 바로 비교할 수 없음. 질의 필드를 바꾸려면 먼저 `PREREGISTER.md`에 등록
- `PREREGISTER.md` — 바꾸기 전에 무엇을 바꾸고 어떤 지표를 기대하는지 먼저 적는 곳
- `run_skill_pair.py` — #17 순차 평가 실행기. `DEMO_MODE=0 uv run python -m evals.run_skill_pair <새 결과 폴더>`. 그림의 노드 순서로 준비 상태를 저장한 뒤 동일 상태에서 Skill 유무 답변을 비교. 생성 거절 경로·부분 결과·해시·예약비용을 기록하며 expected 충족률은 검토 전 null. 서비스 그래프·MCP 통합 검증은 아님
- `results/` — 평가 원시 결과
- `results/tool_prompt_check_2026-11-03.json` — #21 도구 선택 프롬프트의 자유 인자 스키마 실패·중단 결과. 도구 선택5종의 필수 인자가 빈 객체여서 실패
- `results/tool_prompt_check_2026-11-03_typed.json` — #22 명시적 인자 스키마로 같은 프롬프트·입력12건을 확인한 개발 결과. 실제 도구 호출은0회
- `results/tool_prompt_check_2026-11-03_last.json` — #23 미실행 지시문 주입1건 확인과 #22 합산 검토. 서로 다른12건 확인, 도구/인자5/5·고정 행동11/12 일치
- `results/langfuse_skill_check_2026-11-03_final.json` — 이전 등록 본문에 대한 사전 등록 #19의 합성4건·generation10개 타임라인 API 확인과 응답. 사용자 제공 UI6장으로 등록 목록·정격 조회·보장값 부재 흐름 확인 완료(범위는 JSON의 `ui_confirmation`). 동결셋 평가·전체 사례 UI 확인·실제 청구액 측정은 아님
- `results/langfuse_skill_check_2026-11-03_current.json` — #20 현재 Skill 본문의 대표 흐름4건 재검증. 모델·프롬프트·Skill 버전·해시와 원격 타임라인을 기록
- `results/skill_scenarios_2026-11-03_current.json` — #20 S1 7상황·S2 6상황의 생성 노드 직접 검증. 입력 근거·검토 기준·답변·원격 타임라인을 기록. Codex 답변 검토12/13 충족, 충돌1건 실패이며 전체 그래프/검색/동결 평가 결과와 구분
- `draft_30.jsonl` — 난이도별 10건씩 30행의 검수 초안. 관련성은 11-01에 관련 17·비관련 13으로 정함(e08·m07은 코퍼스에 데이터시트가 있어 관련, e07·m08은 비관련). 파일의 `kind`와 정답은 비어 있고 정답은 `draft_50.jsonl`에 채웠음, 실행·동결 금지
- `DRAFT_30_REVIEW.md` — 초안 30건의 질문·가정·예상 답변 방향과 검수 목록
- `draft_50.jsonl` — 현재 50건(관련 25·비관련 25) 검수 초안. 52건에서 n22(관련)·n13(비관련)을 예비 이관. 사람 합의 43건·숫자형 기계 대조 7건. 고정 키를 `dataset_v1.jsonl`로 옮겨 동결했고 이 파일은 검수 이력으로 남김
- `DRAFT_50_REVIEW.md` — 현재 50건 검토표. 세 문항 변경 의견·n21 검수란과 예비 이관 안내
- `SECOND_PASS_50_REVIEW.md` — 11-02 Codex 보조 검증 50건과 동결 전 미확인 사항(h03 relevant·n13 포함·n21 없던 당시 구성). 사람 2차 판정은 별도
- `results/draft50_second_pass_2026-11-02.json` — 문항 구조·NET 해시·PDF 해시 및 문항별 보조 검증 원시 기록
- `results/draft52_validation_2026-11-02.json` — 추가 두 건의 2차 O 기록 전 스냅샷. 당시 52건 구성·기존 질문 보존·변경 이력·NET/PDF 해시 확인. 사람 검수·평가 실행·동결 결과가 아님
- `results/storage_contract_2026-11-02.json` — 합성 벡터를 넣은 전용 로컬 PostgreSQL의 형식·용량·검색 계약 확인. 실제 코퍼스 250MB·품질 달성 결과가 아님
- `results/auth_boundary_2026-11-02.json` — 로그인 잠금·세션 만료 경계 실측 원시 결과(`scripts/auth_boundary_after_merge.py`)
- `results/scrypt_concurrent_2026-11-02.json` — 동시 scrypt·프로세스 메모리 실측 원시 결과(`scripts/measure_scrypt_concurrent.py`)
- `results/retrieval_baseline_2026-11-03.json`·`retrieval_dense_2026-11-03.json`·`retrieval_bm25_2026-11-03.json` — v1 데이터시트 근거 19문항의 검색 지표 원시 결과(`run_retrieval.py`, k=5). 각각 하이브리드·dense만·BM25만. 하이브리드 파일은 `method` 인자가 생기기 전에 만들어 summary에 `method`가 없음

임베딩 결과의 수치와 공통 해석은 루트 [EVAL_REPORT.md](../EVAL_REPORT.md), 후보 13종을 선정한 이유·개별 실행 과정·중단 사유·다음 조건은 [embedding-candidate-investigation.md](../docs/embedding-candidate-investigation.md)를 봅니다. 2026-11-02 확장 평가기·실제 PDF 표본·원시 결과는 저장소에 없어 재현할 수 없습니다. 차단 결과는 Recall@5·MRR 0점이나 품질 탈락으로 환산하지 않습니다.

`embedding_sample_v0.jsonl`은 후보를 거르는 비동결 프록시이며 v1·v2나 G5 건수에 포함하지 않습니다. 실제 모델 결정은 TSC 1,360건 실제 청크 평가를 별도 사전 등록한 뒤 수행합니다.

## 평가셋

G5: 최종 평가셋은 **50건 이상**(동결 시점 기준)이고 **관련 질문과 비관련 질문이 각각 절반**입니다. 개선 전후를 같은 셋으로 두 번 이상 재서 회귀를 숫자로 보입니다.

**평가셋이 쉬우면 어떤 개선도 보이지 않습니다.** 같은 문항 구성이라도 코퍼스가 작으면 임베딩 모델을 바꿔도 거의 같은 점수를 냅니다(30청크 프록시에서는 임베딩 후보 세 종의 Recall@5가 모두 1.000이었습니다. `PREREGISTER.md` #1·#2). v2에 문항을 더할 때도 일부러 어려운 문항을 넣습니다.

## 동결 계획

| 버전 | 시점 | 건수 | 하는 일 |
|---|---|---|---|
| v1 | 11/2(월) 동결 | 50건 (관련 25, 비관련 25. n22·n13 예비 이관) | 변경 3건 재검수·합의와 n21 검수를 마치고 동결(sha256 `2fef02c2…`). 검색 베이스라인 점수는 11/3 |
| v2 | 11/6(금) 중간 점검 전 | 동결한 v1 50건 + 후보 찾기 문항 20건 예정([ADR 0003](../docs/adr/0003-평가셋-v1을-50건으로-동결.md)) | v1은 그대로 두고 문항을 더하면 다시 동결 |

v2를 동결한 뒤에는 **단일 에이전트 기준 점수도 v2로 다시 재고**, 멀티에이전트와 이후 모든 개선 전후 비교를 v2로 잽니다.

## 파일과 형식

`dataset_v1.jsonl`은 2026-11-02에 `draft_50.jsonl`의 고정 키(`id`, `input`, `kind`, `irrelevant_type`, `expected`, `gold_chunks`, `why`, `as_of`, `corpus_version`)만 옮겨 동결했습니다. v2는 v1을 복사해 `dataset_v2.jsonl`로 만들어 건을 더합니다.

| 필드 | 뜻 |
|---|---|
| `kind` | `relevant`(핵심 요청에 답할 근거가 있거나, 아래의 사용자 조건 부족에 해당) 또는 `irrelevant`(범위 밖·대상/요청 속성/판본 근거 부재). 아래 분류 기준을 따름 |
| `irrelevant_type` | 비관련만. 아래 4종 중 하나: `out_of_domain`, `unknown_entity`, `missing_attribute`, `wrong_period` |
| `as_of` | 정답 기준일. 코퍼스가 바뀌면 정답이 바뀌는 문항(데이터시트 개정판 교체 등)을 가려내는 근거 |
| `corpus_version` | 이 문항을 쓸 때의 코퍼스 버전(`data/manifest.jsonl`의 해시 또는 날짜) |
| `expected` | 정답 또는 판정 기준 |
| `gold_chunks` | 정답 근거가 있는 청크나 문서 위치. 비관련은 빈 목록 |
| `why` | 정답을 정한 기준. 팀원끼리 판단이 갈릴 때 돌아보는 근거 |

**잘 되는 것만 모으면 평가가 아니라 자랑입니다.** 비관련 질문, 애매한 질문, 말을 바꿔 묻는 질문을 반드시 넣으세요.

## 관련·비관련과 NOT_VERIFIED의 구분

2026-11-02 김재훈과의 검토에서 정했고 v1 동결에 적용한 기준이다. 관련 문서가 있다는 사실만으로 relevant가 되는 것은 아니며, 질문이 요청한 핵심 값·판정과 부족한 정보의 출처를 확인한다.

| 상황 | 분류·정답 기준 | 예 |
|---|---|---|
| 정격·특성 조회의 핵심 요청에 문서로 답할 수 있음 | relevant. 값의 MAX/TYP와 시험 조건을 밝혀 답하고 실제 회로 보장으로 확대하지 않음 | e04·e08·n21 |
| 적합성 판단에 쓸 후보 정격·판정 근거는 있으나 사용자의 동작 조건이 부족함 | relevant + NOT_VERIFIED. 부족한 사용자 조건을 구체적으로 밝히고 추가 정보를 요청. 조건을 임의로 채우거나 불충족으로 단정하지 않음 | n01의 TA, n02의 차단 펄스 폭·파형 |
| 핵심 요청인 수치·보장값·실측·제조사/품번을 확인할 문서 속성이 없음 | irrelevant / missing_attribute. 주변 설명이나 다른 값으로 요청 답변을 대신하지 않음 | h03·n14·e09·m08·m09·h08·h09 |

- 사용자 조건을 추가해도 필요한 문서 속성이 없으면 사용자 조건 부족만으로 relevant에 넣지 않는다. 후보 자료 부재는 unknown_entity, 요청 판본 부재는 wrong_period로 구분한다.
- 부품 정격을 답한 뒤 부가적인 대체 적합성을 미확정으로 남기는 경우(e08 등), NOT_VERIFIED라는 단어만으로 문항 전체를 irrelevant로 바꾸지 않는다.
- `kind`와 대체 판정 5종은 별도 축이다. SPEC의 NOT_VERIFIED는 대체 판정상 거절이지만 relevant 여부와 일대일 대응하지 않는다. n01·n02처럼 NOT_VERIFIED를 정답으로 명시한 문항을 정답대로 응답했을 때 단순히 그 코드가 있다는 이유로 오거절로 채점하지 않는다. 실제 채점기와 지표별 분모는 이 기준에 맞춰 별도 확인해야 하며, 현재 검색 평가기는 답변·거절을 채점하지 않는다.
- 데이터셋 수량을 맞추기 위해 분류를 바꾸지 않는다. h03 재분류 후 24/26에서 관련 두 건을 추가해 52건(26/26)이 됐던 이력을 보존한다. 현재는 n22(관련)·n13(비관련)을 예비로 이관한 50건(25/25)이다.

## 비관련 질문은 4종을 섞습니다

한 종류만 쓰면 쉬운 거절만 늘어 점수가 부풀려집니다. 비관련 절반 안에서 4종이 모두 들어가야 합니다.

| `irrelevant_type` | 뜻 | 예 (v1 문항) |
|---|---|---|
| `out_of_domain` | 도메인 밖 | "Q1 AO3406 대신 쓸 MOSFET 좀 골라 줘."(e06) |
| `unknown_entity` | 코퍼스에 없는 부품이나 대상 | 코퍼스에 없는 BAT85의 정격(n09) |
| `missing_attribute` | 있는 대상이지만 코퍼스에 없는 항목 | BZT52C3V6 G1804판에 없는 1V 정전용량 보장 최댓값(n14) |
| `wrong_period` | 같은 문서인데 요청한 판본이 다름 | SS34 Q2611판을 물었는데 코퍼스에는 Q2412판만 있음(n15) |

현재 판본 지정 문항의 정답은 사람이 고정 코퍼스와 대조해 정한다. 요청 판본의 자동 확인은 미구현이며, 필요한 후속 작업은 [RAG 파이프라인 작업서](../docs/specs/rag-pipeline.md#후속-필요사항-요청-판본-확인-미구현)에 기록했다. 코퍼스에 없다는 사실만으로 해당 판본이 실제로 존재하지 않는다고 판정하지 않는다.

## 질문은 정답을 보지 않고 씁니다

질문을 쓰는 사람은 정답 청크를 열어 보지 않고 질문을 씁니다. 정답을 보고 쓴 질문은 정답 문장의 낱말을 그대로 따라 쓰게 되어 검색이 쉬워집니다. 정답 청크는 다른 팀원이 나중에 찾아 `gold_chunks`에 적습니다.

## 동결

하정운 1차 판정과 김재훈 2차 검토·수정 의견을 반영해 합의한 v1 50건을 2026-11-02에 동결했다. 최종 평가셋은 `dataset_v1.jsonl`이며 SHA256은 `FROZEN.json`에 기록했다.

동결본과 검수 이력을 읽을 때 알아 둘 점:
- `draft_30.jsonl`·`draft_50.jsonl`의 `status`·`review_flags`·`review_hold`·`author_review`는 동결 직전까지의 검수 이력이다. "not_frozen", "do_not_freeze", "검토 전" 같은 값이 남아 있어도 동결 여부는 `FROZEN.json`이 정한다.
- id 접두사(`draft30-`·`draft50-`·`draft52-`)는 그 문항이 처음 들어간 초안을 나타낸다. 문서에서는 접두사를 빼고 e01·n21처럼 부른다.
- `corpus_version` 표기가 둘이다. 49건은 "TSC 다이오드 데이터시트 1,360건(2026-11-01 수집)"이고, n21은 `sha256:2d452ab3…`로 커밋 b9a98ae(11-01)의 `data/manifest.jsonl` 해시다. 현재 manifest는 11-02에 줄여 해시가 다르다.
- `why`가 인용하는 `TASK.md`(정답 초안 작업 지시서)·`정답판정-기준표.md`·`tsc_datasheet_list.csv`(CSV)는 저장소 밖 자료다.
- 동결본의 넷리스트 인용에는 가운뎃점이 두 종류(`・` U+30FB, `·` U+00B7) 섞여 있다. 동결 파일이라 고치지 않는다.

```bash
uv run python evals/freeze.py dataset_v1.jsonl     # sha256과 건수를 FROZEN.json에 기록
uv run python evals/freeze.py --check              # 동결 이후 바뀐 파일이 없는지 확인
```

동결 뒤에는 정답을 고치지 않습니다. `tests/test_frozen_evals.py`가 PR마다 해시를 확인하고, 바뀌면 CI가 실패합니다. 정답이 정말 틀렸다면 파일을 고치지 말고 `docs/`에 이유를 적고 강사와 상의하세요.

### 동결 뒤에 코퍼스를 바꿨다면

코퍼스가 바뀌면 정답이 달라지는 문항이 생깁니다. 평가셋 파일은 고치지 않고 `evals/exclusions.json`에 문항 id와 사유를 적어 **지표에서만 뺍니다**. 사유를 공개하는 것이 조건이며, 제외 때문에 50건 밑으로 줄어도 감점하지 않습니다. `EVAL_REPORT.md` 2장에 제외 건수를 적으세요.

```json
{"as_of": "2026-11-08", "excluded": [{"id": "draft50-n15", "reason": "SS34 새 개정판을 수집해 정답 문서가 바뀜"}]}
```

## 판정 방식

정확 일치, 스키마 통과, 규칙 기반, LLM-as-judge 모두 가능합니다. 다만 **어떤 방식이고 한계가 무엇인지** `EVAL_REPORT.md`에 적어야 합니다. 생성 모델과 판정 모델은 같은 것으로 두지 마세요. 후한 점수가 나옵니다.

청크 id가 일치하는지만 보면 "답이 질문에 맞는가"는 알 수 없습니다. 한계로 적으세요. 하나의 정확도로 합치지 말고 `EVAL_REPORT.md` 2장의 **지표 5개**로 나눠 보고합니다.

## 결과 보관

재측정 결과의 원시 파일은 `evals/results/`에 둡니다. 평가자가 샘플 몇 문항을 다시 돌려 숫자가 맞는지 보므로, **한 줄 재현 명령**을 `EVAL_REPORT.md` 9장에 적으세요.
