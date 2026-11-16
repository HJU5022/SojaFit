# Spec 에이전트와 대체품 찾기

- 상태: 현행
- 기준일: 2026-11-12
- 기준 커밋: 6707002
- 정본 여부: 비정본(정본: [SPEC.md](../../SPEC.md) 3절 판정 5종, 8.3 후보 판정, 8.7 찾기)
- 관련 문서: [ADR 0013](../adr/0013-부품-사양-표는-13종을-규칙으로-만들고-애매한-값은-뺀다.md), [ADR 0016](../adr/0016-사양-표를-버리고-카드-읽기를-기본으로-한다.md), `backend/multi_agent/MULTI_AGENT.md`, `backend/judge/JUDGE.md`

## Why

- 페르소나: 소형 MCU 회로로 시제품·소량 생산을 하는 하드웨어 개발자(SPEC 1절).
- 상황: 단종·재고 부족·원가 절감으로 다이오드 하나를 바꿔야 한다. "D1을 이 부품으로 바꿔도 돼?"(판정) 또는 "D1 대신 쓸 부품 찾아 줘"(대체품 찾기)라고 묻는다. 서비스의 결론은 대체품 찾기이고, 판정은 그 도구다.
- 문제:
  1. 값 하나만 없어도 "문서로 확인 안 됨"으로 끝나면 무엇이 빠졌는지, 무엇을 알려 주면 되는지 알 수 없다.
  2. 역할마다 필요한 조건이 다르다. 역할 규칙이 없으면 조건을 코드가 고를 수 없다.
- 측정 지표: 판정 연습 문제의 역할 정답률과 판정 코드 일치율, 찾기 문항의 후보 적중. 판정·찾기 과잉 거절은 평가 정본 [EVAL_REPORT.md](../../EVAL_REPORT.md)를 따른다.

### 현재 응답의 사용 조건 표시

- Goal: 판정에 쓴 값을 결과 화면에서 확인할 수 있어야 한다. 검증·단위 변환·추가 입력을 거친 값만 표시한다. 조건 추출·수치 판정 규칙 변경은 범위 밖이다.
- How: 응답의 선택 필드 `input_conditions`는 최대 60개 `{code, value}`다(`backend/multi_agent/agents/judge.py` `display_inputs`의 `rows[:60]`). 현재 SSE 결과에만 포함하고 기존 DB 저장 형식과 GET은 유지한다. 원시 읽기·프롬프트는 공개하지 않는다.
- AC: 근거 없는 읽기 값과 수정한 추가 입력이 있으면 최종 검증 값만 표시한다. 저장·GET으로 복원한 과거 기록의 조건은 추측하지 않는다(`tests/multi_agent/test_judge.py::test_displayed_conditions_drop_ungrounded_reads_and_use_resume_values`).

## Goal

- 판정 질문과 대체품 찾기 질문에 판정 5종(SPEC 3절)과 데이터시트 인용(쪽·표·행)으로 답한다. 숫자 비교와 단위 비교는 `backend/judge/`에서만 한다(AGENTS 7번).
- 성공 기준(연습 문제 기준, 기대 수치는 측정 전에 `evals/guides/preregister.md`에 적는다):
  - 역할 정답률 80% 이상
  - 판정 코드 일치율 70% 이상
  - 질문에 없는 숫자로 낸 판정 0건, 인용 없는 판정 0건
  - LLM 호출은 문항당 읽기 1번, 인터럽트는 문항당 최대 1번
- Out of Scope:
  - Mouser 가격·재고 조회(SPEC 4절 `/api/prices`, ADR 0009).
  - 견적서 저장과 승인(SPEC 8.4), 다이오드가 아닌 부품의 판정.
  - 열저항·I²t·IFRM·온도 계수 조건(해당 조건은 "사람 확인"으로 둔다).
  - 동결 평가셋 수정.

## What

### 공통 흐름 (판정·찾기 모두)

1. Supervisor가 질문 종류를 `candidate_judge` 또는 `candidate_find`로 정하고 Spec 에이전트(`judge`)로 보낸다(`backend/multi_agent/supervisor.py`).
2. 읽기(LLM 1번, `judge_read` 노드): 대상 주변 회로(`circuit_around`)와 질문으로 역할(23개 또는 `other`), 근거 핀, 회로 값, 원래 부품, 후보 품번(판정만), 원하는 패키지·분류를 정해진 칸으로 낸다(`judge_read_agent`).
3. 숫자 확인(코드): 회로 값마다 그 숫자와 단위가 질문 글(사용 조건 포함)에 있는지 본다(`grounded`). 없으면 버리고 "빠진 값"으로 친다.
4. 규칙(코드): 그 역할의 조건을 `roles.yaml`에서 읽는다. 조건은 세 층이다.
   - 필수: 사양 값과 회로 값으로 코드가 계산할 수 있는 조건
   - 조건부 필수: 발동 조건(PWM, 데이터선, 고온, OP앰프 없음 등)이 있을 때만 필수
   - 주의(사람 확인): 문서로 계산할 수 없는 것. 판정을 바꾸지 않고 답에 목록으로 붙인다
5. 묻기(그래프 인터럽트): 필수 조건이나 발동 여부에 필요한 회로 값이 빠졌으면 한 번에 모아 묻는다. 사용자가 답하면 같은 thread에서 이어 간다.
6. 값 읽기(코드): 원래 부품과 후보의 사양 행(값·시험 조건·인용)을 카드 읽기 도구로 읽는다(`backend/rag/card_specs.py`, ADR 0016). 코드가 먼저 읽고 못 읽은 카드만 LLM(`card_read.md`)이 읽는다(`backend/rag/card_read.py`).
7. 비교와 판정(코드, `backend/judge/verdict.py`): 조건마다 통과·실패·확인 안 됨을 정하고 SPEC 3절 순서로 판정 5종을 낸다. 패키지가 다르면 판정과 별도로 "기판 수정 필요"를 붙인다.

### 판정 질문 (후보가 질문에 있음)

8. 후보 하나하나를 7단계로 판정해 답으로 만든다.

### 대체품 찾기 질문 (후보를 찾음)

8. 필수 조건 중 숫자 하한·상한인 것을 찾기 조건(`verdict.search_conditions`, 최대 10개)으로 바꿔 `card_find.find`(후보 상한 50, `backend/rag/card_find.py`)로 거른다. 원래 부품의 패키지·분류를 넘겨 같은 패키지 → 같은 분류 → 기준에 가까운 순으로 줄 세운다. 시험 조건이 중요한 값(VF 등)은 거르기에 쓰지 않고 7단계에서 본다.
9. 거른 후보마다 7단계로 판정한다.
10. 정렬(`verdict.rank`): 판정 순서(동일품 → 사양 동등 → 역할상 충분) → 기판 수정이 필요 없는 부품 먼저 → 선호 실장 방식 → 품번 순. 불충족은 뺀다. 판정별 상위 3개, 모두 합쳐 최대 5개를 보여 준다. "확인 안 됨" 후보는 견적 대상이 아니므로 따로 표시한다(SPEC 2절).

### 답

- 판정 경로의 답은 코드가 만든 틀로 쓴다(`backend/multi_agent/messages.py` `render_judgement`). 숫자와 인용을 LLM이 다시 쓰지 않게 하려는 것이다. 틀에는 판정, 조건 표(조건·기준과 계산식·후보 값과 시험 조건·통과 여부·인용), 빠진 값과 "알려 주면 판정할 수 있는 것", 불확실한 조건, 사람이 확인할 것, 기판 수정 필요가 든다.
- "문서로 확인 안 됨"이어도 찾은 값·조건·빠진 것은 모두 보여 준다(ADR 0006).

### 역할 23개

R01 역극성 보호(직렬), R02 역류 방지, R03 릴레이 플라이백(켜고 끄기만), R04 제너 클램프 · 전압 기준, R05 AC · 브리지 정류, R06 ESD · TVS, R07 병렬 역극성 보호, R08 입력 핀 보호, R09 전압 낮추기, R10 신호선 다이오드 OR, R11 벅 프리휠링, R12 부스트 출력, R13 플라이백 전원 출력, R14 RCD 스너버, R15 부트스트랩, R16 차지펌프(양전압 2배 · 음전압), R17 피크 검파(피크 홀드 · 포락선), R18 게이트 보호 제너, R19 게이트 빨리 끄기, R20 레귤레이터 보호, R21 리셋 방전, R22 PWM 모터 프리휠링, R23 키 매트릭스 격리. 역할마다 규칙이 있다. 공통 여유는 전압 ×1.25(정격의 80%), 전류 ×1.43(정격의 70%)이고, R13 · R14 · R16의 역할별 여유는 규칙 원본을 따른다.

### Edge Cases

| # | 상황 | 처리 |
|---|---|---|
| EC-01 | 역할이 `other`(23개 밖) | 판정하지 않는다. 찾은 값과 "이 역할은 판정 규칙이 없다"를 답한다 |
| EC-02 | 역할이 둘로 갈림(예: RESET→VCC 다이오드 하나 = R08 또는 R21) | 하나로 단정하지 않고 두 후보를 인터럽트로 확인한다. 답이 없으면 두 역할로 모두 판정하고 더 나쁜 판정을 낸다 |
| EC-03 | 읽기가 질문에 없는 숫자를 냄 | 버리고 빠진 값으로 친다(3단계) |
| EC-04 | 인터럽트에 답이 없음(평가 실행 포함) | 필수 값이 빠지면 그 조건은 확인 안 됨(→ "문서로 확인 안 됨"). 조건부 발동 여부가 빠지면 그 조건 없이 판정하고 "불확실한 조건"에 적는다. 기본값을 쓰는 규칙(R14 · R17)은 기본값으로 판정했다고 밝힌다 |
| EC-05 | 원래 부품이 코퍼스에 없거나 품번이 없음 | 동일품 · 사양 동등은 내지 않는다(SPEC 3절). 역할상 충분까지만 낸다 |
| EC-06 | 후보 값의 시험 조건이 기준과 다름(온도 TA/TJ, 시험 전류 · 전압, 펄스 폭 · 파형) | 그 조건은 확인 안 됨. 더 가혹한 조건의 값으로 한계를 추정하지 않는다. 조건 칸이 비면 표 제목의 기본 조건(예: TA=25°C unless otherwise noted)을 쓴다. 표 제목도 조건을 적지 않은 제너 VZ 행은 TA=25°C로 본다. 다른 코드는 "적혀 있지 않음"이다. 역전압 정격(VRRM · VR · VRWM)은 온도로 줄지 않아 사용 온도를 맞추지 않는다 |
| EC-07 | 후보 품번의 사양 행이 없음(코퍼스에는 있음) | 그 후보는 확인 안 됨. 찾아본 문서를 적는다. 코퍼스에 아예 없는 품번은 사실 확인(`part_missing`)이 먼저 처리한다 |
| EC-08 | 찾기 결과 0개 | 건 검색 조건을 그대로 보여 주고 "조건을 모두 만족하는 부품을 찾지 못했어요."라고 답한다 |
| EC-09 | 찾기 후보가 50개 상한에 걸림 | 상한에 걸렸다고 밝히고 패키지 · 분류를 좁히길 권한다 |
| EC-10 | 같은 기본 품번에 주문 코드만 다름(예: 1N4148 A0G · R0G) | 동일품. 근거는 주문 정보 표의 그 주문 코드 행이다. 그 행을 못 찾으면 제조사가 같은 제품이라고 밝힌 문장이 있는 청크를 찾는다 |

## How

### 파일

| 파일 | 할 일 |
|---|---|
| `backend/judge/rules/roles.yaml` | 역할 23개의 알아보는 법, 조건(층·코드·비교·기준식·발동 조건), 되물을 값, 주의 목록, 출처 |
| `backend/judge/conditions.py` | 규칙 파일 읽기와 기준식 계산(`kV`·`kI` 여유) |
| `backend/judge/verdict.py` | 시험 조건 맞추기, 조건별 비교, 판정 5종, 찾기 조건 만들기, 후보 정렬. LLM·DB를 부르지 않는다(값은 인자로 받는다) |
| `backend/judge/sheet_conditions.py` | 시험 조건(온도·전류·펄스 파형) 맞춤 |
| `backend/multi_agent/agents/judge.py` | Spec 에이전트: 읽기(`judge_read_agent`) → 숫자 확인 → 인터럽트 → 카드 값 읽기 → `verdict` → 보고서(`judge_agent`, `judge_task_node`) |
| `backend/prompts/judge_read.md` | 읽기 프롬프트(영어, Langfuse `judge_read`) |
| `backend/rag/card_specs.py` · `card_find.py` · `card_read.py` | 사양 행 읽기, 조건으로 부품 찾기, 카드 값 읽기 |
| `backend/multi_agent/messages.py` | 판정 답 틀 |
| `backend/multi_agent/build.py` | 하위 그래프 `회로 읽기` → `대체 부품 판정` 연결 |
| `backend/graph/nodes.py` `circuit_around` | 큰 넷에서 대상 자신의 핀을 먼저 두고 `MAX_NET_NODES`(8)개만 보인다 |

### 규칙 파일 형식(예: R01)

```yaml
R01:
  name: 역극성 보호(직렬)
  recognize: 커넥터·배터리 → 다이오드 → 전원 넷, 캐소드가 부하 쪽   # 읽기 프롬프트에 넣는다
  inputs: [v_in_max, i_max, v_drop_allowed]                              # 되물을 수 있는 회로 값
  conditions:
    - {tier: required, code: [VRRM, VR], op: ">=", basis: "v_in_max * kV"}
    - {tier: required, code: IF_AV, op: ">=", basis: "i_max * kI"}
    - {tier: conditional, code: VF, op: "<=", basis: "v_drop_allowed", when: "v_drop_allowed", at: {IF: i_max}}
  cautions: [발열(열저항 칸이 생기면 필수로)]
  source: "TI SLVA139 [문서]"
```

- `basis`는 회로 값 이름 · 숫자 · `kV`(1.25) · `kI`(1/0.7)와 사칙 연산만 쓴다. `verdict.py`가 정해진 문법만 읽는다(임의 코드 실행 없음).
- `orig.<코드>`(원래 부품 값)는 후보 행과 시험 조건이 같은 원래 부품 행의 값이다. 같은 조건의 원래 행이 없으면 그 조건은 확인 안 됨이고, `orig.*`를 쓰는 조건은 찾기 거르기에 쓰지 않는다.
- 원본의 "알면 A, 모르면 B"는 `basis: A, default: B`로 적는다(A에 쓸 값이 없으면 B로 판정하고 불확실에 밝힌다, B가 쓰는 회로 값은 묻는다). "A 또는 B"는 `{tier, any: [{code, op, basis, at?}, …], when?, unless?}`로 적는다. 멤버 하나라도 통과하면 통과, 모두 계산돼 실패하면 실패, 그 밖은 확인 안 됨이다. 계산할 수 있는 멤버가 없을 때만 첫 멤버의 값을 묻고, 찾기 거르기에는 쓰지 않는다.
- `slot`(min · typ · max)을 적은 조건은 후보 행의 그 칸 값만 본다(다른 칸으로 물러나지 않는다, `within`에는 쓰지 않는다). `unless`는 `when`의 반대로 값이 있고 거짓이 아니면 꺼진다(flag는 참, 숫자는 주어짐). `orig.VZ`는 원래 부품의 최대 VZ다.
- `exempt`는 TRR 조건의 쇼트키 면제 범위다. `schottky`(기본, 쇼트키 계열 모두) · `sic`(SiC 쇼트키만, R14 100 kHz 초과) · `none`(면제 없음). 면제는 판정 노드가 후보 분류로 한다.
- 회로 값 이름은 `roles.yaml`의 `inputs`가 정한다. 읽기 입력 글에는 역할마다 그 역할의 이름 · 종류를 붙이고(코드가 만든다), 뜻 · 단위는 읽기 프롬프트 "Value names"에 둔다. 읽기는 고른 역할(과 `role_alt`)의 이름만 쓰고, 그 밖의 이름은 코드가 버려 `dropped`에 남긴다.

### 읽기 출력(구조화 출력, pydantic)

- `role`(R01~R23 · `other`), `role_alt`(갈릴 때 두 번째 후보, EC-02), `role_evidence`(근거 핀 목록, 예: `D1.K → +5V`)
- `values`: 회로 값 이름 → {`value`, `unit`, `quote`(질문에서 그대로 옮긴 글)}
- `original_part`, `candidates`(판정만), `package_wanted`, `category_wanted`
- `required_specs`(꼭 요구한 성질: `words` 사용자 말 · `code` 사양 항목 또는 `none`), `maker_wanted`, `revision_wanted`: 코퍼스 밖 요구 거절에 쓴다(SPEC 8.3)

### 인터럽트

- LangGraph `interrupt({"missing": [...], "role_choices": [...], "question": "<한국어 질문 하나>"})`로 묻는다(`backend/multi_agent/agents/judge.py:768`). 재개 값은 `{"answers": {회로 값 이름: 값}, "role": <고른 역할, 있으면>}`이다. 체크포인터가 필요하다(`build_graph(checkpointer=...)`).
- 평가 실행기(`evals/runners/run_graph.py --multi`)는 인터럽트를 만나면 `{"answers": {}}`(= 모름, EC-04)로 한 번 재개한다. 빈 dict(`{}`)로 재개하면 LangGraph가 재개로 보지 않고 다시 멈춘다.

### 한도

- 읽기 LLM 1번, 인터럽트 1번, 찾기 조건 최대 10개, 찾기 후보 상한 50개, 답에 보여 주는 후보 최대 5개.
- 읽기 모델은 `NODE_MODELS["judge_read"]`(`backend/services/langfuse_prompts.py:33`)가 정한다. 선정 이유는 ADR 0014.

### 연습 문제와 측정

- 판정 연습 문제 실행기: `evals/runners/run_judge_dev.py`(입력 `judge_dev.jsonl`). 동결 평가셋은 아니다.
- 입력 파일 `judge_dev.jsonl`과 역할 규칙 원본 3개(`전자_데이터시트/`)는 이 저장소에 없다(한계).

## AC (Given-When-Then)

| AC | Given-When-Then | 시험 |
|---|---|---|
| AC-01 판정: 기준 미달이면 불충족 | 역할 R01, 사용 조건 "입력 최대 20V, 최대 순방향 전류 150mA, 주변 25°C", 후보 1N5817(VRRM 20 V)을 판정하면 VRRM 조건(≥ 25 V)이 실패해 `NOT_SUFFICIENT`이고 조건 표에 기준 25 V, 후보 20 V, 인용이 있다 | `tests/judge/test_judge_verdict.py`, `tests/multi_agent/test_judge.py::test_ac01_judge_question_gives_not_sufficient` |
| AC-02 질문에 없는 숫자는 버린다 | 질문에 전압이 없는데 읽기가 `v_in_max = 12 V`를 내면 숫자 확인에서 빠진 값이 되고 인터럽트 질문에 들어간다 | `tests/multi_agent/test_judge.py::test_ac02_number_not_in_question_is_dropped_and_asked` |
| AC-03 필수 값이 끝내 없으면 확인 안 됨 | 역할 R03, 코일 전류가 없고 재개 값이 비어 있으면 `NOT_VERIFIED`이고 답에 후보 값·인용·통과한 조건·"알려 주면 판정할 수 있는 값"이 있다 | `tests/judge/test_judge_verdict.py` |
| AC-04 발동 여부를 모르면 나머지로 판정하고 불확실을 밝힌다 | 역할 R02, 필수 조건은 통과하고 고온 사용 여부가 없으면 고온 IR 조건 없이 판정하고 "불확실한 조건"에 적는다 | `tests/judge/test_judge_verdict.py` |
| AC-05 시험 조건이 다르면 그 조건은 확인 안 됨 | R03 후보의 IFSM이 8.3 ms 반정현파 값이고 질문의 펄스가 1 ms 단발이면 `unverified`이고 더 가혹한 조건 값으로 추정하지 않는다 | `tests/judge/test_judge_sheet_conditions.py` |
| AC-06 찾기: 거르고 판정하고 줄 세운다 | 역할 R01, "입력 최대 12V, 부하 10mA, 표면실장, 기판 수정 가능"이면 VRRM(또는 VR) ≥ 15 V, IF_AV ≥ 0.0143 A 조건으로 찾고 불충족은 빠지며 최대 5개를 판정 순서 → 기판 수정 불필요 순으로 보인다 | `tests/multi_agent/test_judge.py::test_find_question_filters_judges_and_ranks` |
| AC-07 규칙이 없는 역할은 판정하지 않는다 | 읽기가 `role = other`를 내면 판정 코드 없이 찾은 값과 "이 역할은 판정 규칙이 없다"를 답한다 | `tests/multi_agent/test_judge.py::test_ac07_other_role_gives_no_verdict` |
| AC-08 호출 상한 | 인터럽트는 1번을 넘지 않고 재개 값이 회로 값을 채운다 | `tests/multi_agent/test_judge.py::test_ac08_interrupt_once_and_reply_fills_values`, `test_judge_read_calls_llm_once_with_roles_and_circuit` |
| AC-09 숫자 비교는 judge에서만 | 기준 계산과 비교는 `backend/judge/verdict.py` 함수로만 하고 에이전트와 프롬프트는 숫자를 비교하지 않는다 | `tests/multi_agent/test_judge.py::test_ac09_numbers_are_compared_in_verdict_only` |
| AC-10 대상 핀은 잘리지 않는다 | 대상 다이오드가 노드 9개 이상인 GND 넷에 붙어 있어도 `circuit_around`의 보이는 노드에 대상 자신의 핀이 있다 | `tests/graph/test_graph_read_input.py` |

## 구현 상태

| 항목 | 상태 | 근거 |
|---|---|---|
| 역할 규칙 23개 | 구현 | `backend/judge/rules/roles.yaml`(`R\d+:` 23건), `tests/judge/test_judge_rules_file.py` |
| Spec 에이전트(읽기·인터럽트·판정·찾기) | 구현 | `backend/multi_agent/agents/judge.py` |
| 사양 표·MCP `get_part_specs`·`find_parts_by_specs` | 삭제(카드 읽기로 대체) | ADR 0016, `backend/mcp_skill/MCP_SKILL.md` |
| 작성 에이전트 `agents/writer.py` | 없음(답 틀은 `messages.py`) | `backend/multi_agent/messages.py` |

## 한계

- 연습 문제 입력(`judge_dev.jsonl`)과 역할 규칙 원본 3개 파일은 저장소에 없다. 역할 정답률 80%, 판정 일치율 70% 기준의 측정 결과는 이 문서에 근거가 없다.
- 규칙 파일 형식 예(R01)의 `source: "TI SLVA139"` 인용은 규칙 원본에서 온 것이고 원본은 저장소에 없다.
