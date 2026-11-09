# prompts

## 역할
- 이 폴더: 노드가 LLM에 보내는 프롬프트 원문(Markdown)과 그 버전 기록을 둡니다. Dockerfile이 `backend/`를 복사하므로 키 없는 데모 모드에서도 같은 프롬프트를 씁니다.
- 넣는 것: 프롬프트 원본 Markdown(노드 하나에 파일 하나, 내용이 곧 시스템 프롬프트)과 아래 버전 기록 표. Langfuse 등록·실행 연결은 [services](../services/SERVICES.md)를 따릅니다.
- 넣지 않는 것: LLM 호출 코드(`backend/services/llm.py`), 숫자 비교와 단위 환산(`backend/judge/`), 판정 규칙의 임계값(SPEC 5절 규칙 파일), 도메인 판단 지침 Skill(`backend/mcp_skill/skills/SKILL.md`).
- 담당: 에이전트

## 주의: 이 폴더의 .md는 프롬프트 해시에 들어갑니다
`evals/runners/run_graph.py`와 `evals/runners/run_skill_pair.py`는 이 폴더의 `*.md`를 모두 읽어 프롬프트 해시를 만들되 `PROMPTS.md`(이 설명 파일)만 뺍니다. 그래서 이 파일을 고쳐도 해시는 바뀌지 않지만, 다른 `.md`를 추가·수정하면 해시가 바뀌어 평가 결과와 묶이는 버전이 달라집니다. 프롬프트가 아닌 문서는 이 폴더에 두지 않습니다.

## 노드별 모델(시작값)
`backend/services/langfuse_prompts.py`의 `NODE_MODELS`가 노드마다 쓸 모델을 정합니다. `synth`는 `anthropic/claude-sonnet-5.5`, `supervisor`는 11-09부터 `anthropic/claude-haiku-5.5`(ADR 0017), `grade`가 `openai/gpt-6-luna`, `route` · `rewrite` · `generate` · `judge_read` · `docs_answer`가 `anthropic/claude-haiku-5.5`이며 **최종 결정이 아닙니다**(11-05 정운 결정: Supervisor는 Sonnet, 서브에이전트는 Haiku, 채점은 Luna. 측정 뒤 ADR로 정합니다). Luna에만 `temperature`를 보내지 않고 Haiku · Sonnet은 0입니다. 환경변수 `LLM_MODEL`을 정하면 모든 노드가 그 모델 하나를 씁니다(11-04 기준선 재현용). Langfuse 등록 설정의 `model`도 노드별로 이 표를 따릅니다.

## 버전 기록

프롬프트를 바꾸면 같은 PR에서 한 줄을 더합니다. 평가를 다시 쟀으면 결과 위치도 적습니다. 최근 줄을 위에 둡니다.

| 날짜 | 파일 | 버전 | 바꾼 것 | 이유 | 평가 결과 |
|---|---|---|---|---|---|
| 2026-11-10 | `docs_answer.md` | 다음 버전 | `partial`일 때도 빠진 부분을 겨눈 다른 검색어를 `next_query`에 쓴다 | 일부만 답하고 끝내 정답 근거 없이 답했다(v3-20, 사전 등록 #49) | 측정 예정 |
| 2026-11-09 | `supervisor.md` | 다음 버전 | 판단 순서 3단계(범위 → 확인된 사실 → 질문 종류별 에이전트), 후보 판정 · 찾기는 다이오드만 | Supervisor를 Haiku로 바꾸면서 범위 밖 · 없는 품번 · 찾기 연결을 틀렸다(#46, 사전 등록 #47) | 사전 등록 #47 측정 결과 |
| 2026-11-06 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | 허브 구조의 "다음 노드 고르기 · 보고 뒤 규칙"을 빼고 계획서(질문 종류 · 다음 길 tasks · finish · price · refuse · 할 일 최대 3개와 지시서: 에이전트 · 종류 · 목표 · 출력 · 경계 · 첫 검색어)를 내게 다시 씀. 제약(숫자 비교 금지 · 거절 사유 · 판정은 후보 판정 · 찾기만 · 사실 믿기)과 질문 종류 정의, 검색어 쓰는 법(예전 `rewrite.md`)은 남김 | 멀티 재설계(11-06 정운 결정, 참조/아티팩트 "SojaFit 멀티 에이전트 구조"): 규칙표를 따라가 질문당 판단 4번 · 비용 20배(D5) | v3 측정 전 |
| 2026-11-06 | `docs_answer.md` | v1(Langfuse 등록 전) | 처음 작성. 문서 에이전트의 근거 채점(enough · partial · none, 없으면 다른 검색어)과 답 쓰기(문장마다 [번호] · [넷리스트], 값은 그대로, 대체 판단 없음)를 한 호출로 | 예전 채점(Luna) · 생성(Haiku) 두 호출을 하나로. 11-06 강사 지적 "채점은 질문 맥락을 가진 쪽이" | v3 측정 전 |
| 2026-11-06 | `synth.md` | v1(Langfuse 등록 전) | 처음 작성. Supervisor ② 종합: 할 일 2개 이상의 부분 답을 한 답으로, 인용 유지, 판정 표 · 숫자는 다시 쓰지 않음(코드가 붙임), 실패한 부분은 이유와 함께 | 위와 같음 | v3 측정 전 |
| 2026-11-06 | `judge_read.md` | 다음 버전(Langfuse 등록 전) | 출력 칸 `required_specs`(꼭 요구한 성질: 사용자 말 + 사양 표 항목 18개 중 하나 또는 `none`) · `maker_wanted`(요구한 제조사, TSC는 `TSC`) · `revision_wanted`(요구한 개정 코드 · 판)와 사양 표 항목 뜻 목록 "Spec-table items"를 더함. 바꾸는 이유(원가 · 재고 · 단종)와 회로 값은 요구 성질로 쓰지 않게 함 | 코퍼스 밖 요구 거절(SPEC 8.3). 고장률 · 잡음 · 다른 제조사 · 없는 판을 요구한 비관련 질문이 판정 답을 받았다(동결 평가 비관련 35건 중 8~10건) | 아직 없음(가짜 LLM 시험만) |
| 2026-11-06 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | 규칙 3: 판정 보고가 fail이면 보고의 사유로 거절(search_error 외에 코퍼스 밖 요구의 part_missing · revision_missing · not_found) | 위와 같음. 코드도 같은 경우를 거절로 바꾼다(`supervisor.decide`) | 아직 없음(가짜 LLM 시험만) |
| 2026-11-06 | `judge_read.md` | 다음 버전(Langfuse 등록 전) | `values`의 `name`을 고른 역할(`role_alt` 포함)이 받는 이름으로만 쓰게 하고(입력 글의 역할 줄에 `inputs: 이름 (종류)`를 코드가 붙임), 사용자가 다른 말로 준 값은 그 역할에서 같은 양을 뜻하는 이름으로 옮기게 함. 모든 값 이름의 뜻 · 단위 목록 "Value names"를 더함 | 모든 역할의 이름을 한 줄로 주던 때 다른 역할의 이름(`i_out` · `v_in_max` · `v_bus` · `v_clamp`)으로 읽어 코드가 버리고 기준값이 비었다(동결 평가 4회 실측, 인용 없는 답 40건 중 20건) | 아직 없음(가짜 LLM 시험만) |
| 2026-11-06 | `route.md` | 다음 버전(Langfuse 등록 전) | 질문 종류에 `price`(다이오드 품번의 현재 가격 · 재고)를 4번째로 더해 8가지로 하고, 범위 밖에서 가격 · 재고를 빼고 주문 · 결제 · 판매처 찾기 · 비교만 남김 | 실시간 가격 · 재고 표시(SPEC 1절, 11-06 결정). 값은 그래프 밖 화면이 Mouser로 조회한다(ADR 0009) | 아직 없음(가짜 LLM 시험만). 동결 n18(SS34 판매처 · 재고 · 가격)은 정답이 범위 밖 거절이라 가격 길로 가면 채점이 달라진다 |
| 2026-11-06 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | 다음 노드 `price`와 질문 종류 `price`를 더하고, 첫 판단에서 가격 질문은 검색 없이 `price`로. 범위 밖에 주문 · 결제 · 판매처 찾기 · 비교를 적어 `route.md`와 맞춤 | 위와 같음. D4 · D5가 같은 질문을 같은 길로 보내게 한다 | 아직 없음(가짜 LLM 시험만) |
| 2026-11-06 | `route.md` | 다음 버전(Langfuse 등록 전) | 질문 종류를 멀티 Supervisor와 같은 7가지(chat · out_of_scope · other_part · role · candidate_find · candidate_judge · rating)로 넓히고, 입력의 확인된 사실(Verified facts)로 검색 전 거절 사유 `reason`(out_of_scope · not_found · part_missing · revision_missing)과 일상 대화 답 `reply`(300자)를 낸다 | D4 v2: 범위 판정을 첫 단에서 하고 질문 종류마다 다른 길로 보낸다(11-06 강사 검토) | 아직 없음(가짜 LLM 시험만) |
| 2026-11-06 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | 판정 · 찾기 질문을 `judge`가 보일 때 바로 `judge`로 보냄(검색을 먼저 거치지 않음). 검색 보고 뒤에는 `writer`로. 판정 보고가 ok · partial이면 `writer`, search_error 실패면 거절. `judge` 설명에 candidate_find를 더함 | 판정 에이전트 연결(docs/specs/judge-agent.md What 1번) | 아직 없음(가짜 LLM 시험만) |
| 2026-11-06 | `judge_read.md` | v1 | 처음 작성. 대상 다이오드의 역할(R01~R23 · other)과 근거 핀, 질문에 적힌 회로 값(quote 그대로), 원래 부품 · 후보 품번 · 원하는 패키지 · 분류를 정해진 칸으로 낸다. 숫자를 비교하거나 적합 여부를 정하지 않는다. 영어. Langfuse에는 아직 등록하지 않음 | 판정 에이전트 읽기 노드(docs/specs/judge-agent.md) | 아직 없음(가짜 LLM 시험만) |
| 2026-11-05 | `route.md`, `grade.md`, `rewrite.md`, `generate.md` | Langfuse 이름 변경 | 등록 이름에서 `sojafit/` 폴더를 뺌: `route`, `grade`, `rewrite`, `generate`, Skill은 `skill-diode-evidence`. 본문은 그대로 | 프로젝트가 SojaFit 하나라 접두사가 필요 없고 목록이 한 줄로 보이게 함(정운 요청). 이전 `sojafit/` 폴더 프롬프트는 과거 트레이스가 가리켜 지우지 않음 | 동작 변화 없음(이름만) |
| 2026-11-05 | `supervisor.md` | v1 | 처음 작성(11-05 영어로 다시 씀, Langfuse `supervisor` v1 등록). 다음 노드 7종(search · judge · writer · verifier · web · finish · refuse)과 거절 사유 7종, 보고 뒤 판단 규칙 | 멀티 에이전트 Supervisor(D5). 코드 규칙 if 문이 아니라 LLM이 판단한다는 강사 기준 | 아직 없음(가짜 LLM 시험만) |
| 2026-11-05 | `supervisor.md` | v3 | 질문 종류에 `chat`(일상 대화, Supervisor가 한국어 `reply`로 직접 답하고 끝냄)와 `other_part`(다이오드가 아닌 전자 부품, 웹 조회 또는 못 찾음 거절)를 더하고, `out_of_scope`는 서비스와 전혀 무관한 질문만 뜻하게 바꿈. 전자 일반 개념 질문은 짧은 설명 + "데이터시트 근거 아님" 표시. 영어로 작성해 등록 | 근거 3등급과 일상 대화 허용 결정(11-05, SPEC 2절) | 실제 Luna 4문장 확인(인사 · 날씨 거절 · MOSFET 못 찾음 거절 · 일반 개념). 70문항 측정 전 |
| 2026-11-05 | `supervisor.md` | v4 | 본문은 v3과 같다. Langfuse 등록 설정의 모델만 `anthropic/claude-sonnet-5.5`(temperature 0)로 바꿨다(노드별 모델 변경, 11-05 정운 결정) |
| 2026-11-05 | `route.md` | v2 | 한국어에서 영어로 번역(규칙 내용 같음, 답변은 한국어) | 모델이 영어를 더 잘 읽고 토큰이 적음, 멀티 에이전트가 영어 위에 쌓임 | v2 70문항 #35: cited_gold 12 · over_refusal 23 · correct_refusal 35(한국어와 같음), 비용 -11% |
| 2026-11-05 | `grade.md` | v2 | 한국어에서 영어로 번역(규칙 내용 같음, 답변은 한국어) | 모델이 영어를 더 잘 읽고 토큰이 적음, 멀티 에이전트가 영어 위에 쌓임 | v2 70문항 #35: cited_gold 12 · over_refusal 23 · correct_refusal 35(한국어와 같음), 비용 -11% |
| 2026-11-05 | `rewrite.md` | v2 | 한국어에서 영어로 번역(규칙 내용 같음, 답변은 한국어) | 모델이 영어를 더 잘 읽고 토큰이 적음, 멀티 에이전트가 영어 위에 쌓임 | v2 70문항 #35: cited_gold 12 · over_refusal 23 · correct_refusal 35(한국어와 같음), 비용 -11% |
| 2026-11-05 | `generate.md` | v2 | 한국어에서 영어로 번역(규칙 내용 같음, 답변은 한국어) | 모델이 영어를 더 잘 읽고 토큰이 적음, 멀티 에이전트가 영어 위에 쌓임 | v2 70문항 #35: cited_gold 12 · over_refusal 23 · correct_refusal 35(한국어와 같음), 비용 -11% |
| 2026-11-03 | `tool_use.md` | `sojafit/tool-use` 등록 번호 1 | PR #36 도구5종의 선택·인자·결과 해석을 별도 프롬프트로 작성 | manifest ID·웹 후보·PDF 무결성·공개 회로의 계약을 구분 | #21~#23 모의12건 확인. 도구/인자5/5·고정 action11/12 일치, 실제 도구0회. `skill_tool_summary_2026-11-03.json` |
| 2026-11-03 | `../mcp_skill/skills/SKILL.md` | Langfuse 등록 번호 2 | S1 7상황·S2 6상황의 현재 본문 등록, 노드 chat prompt는 버전4 유지 | 상황별 판단까지 작성한 본문과 검증 대상 일치 | #20 대표 흐름4건·직접 생성13건의 추적 연결 확인. 답변 기준12/13 충족, 충돌1건 실패. `skill_tool_summary_2026-11-03.json` |
| 2026-11-03 | `route.md`, `grade.md`, `rewrite.md`, `generate.md` | Langfuse development v4 | `sojafit/route`, `grade`, `rewrite`, `generate`로 chat prompt 등록. user는 `{{input}}`, 생성 system에 선택적 `{{domain_skill}}` | 고정 버전과 generation 연결. 모델 Haiku5.5·temperature0·출력4096 | 합성4건·generation10개에서 프롬프트 버전·모델·부모 연결을 API로 확인. `skill_tool_summary_2026-11-03.json` |
| 2026-11-03 | `generate.md` | v2 | 값 조회와 최종 적합성·없는 보장값 요청의 응답 범위를 구분. S1/S2 Skill은 별도 적용 | 기본 프롬프트와 Skill의 거절/부분 답변 충돌 해소 | 동결 평가셋 품질은 미측정 |
| 2026-11-03 | `generate.md` + `../mcp_skill/skills/SKILL.md` | Skill 선택 적용 | 기존 프롬프트 본문을 보존하고, 명시적으로 켠 생성 호출에만 상황별 근거 해석 지침을 추가. 기본은 꺼짐 | Skill 유무 비교를 위한 생성 노드 연결(SPEC 5절) | 가짜 LLM으로 전달 계약 확인. 실제 모델 품질은 미측정 |
| 2026-11-02 | `generate.md` | v1 | 처음 작성. 근거(청크·넷리스트)만 쓰고 문장마다 [번호]·[넷리스트]를 붙이며, 값을 비교해 대체 여부를 판단하지 않고, 답할 수 없거나 묻는 판을 확인할 수 없으면 "문서로 확인 안 됨" | 생성 노드(SPEC 2절) | 아직 돌리지 않음 |
| 2026-11-02 | `rewrite.md` | v1 | 처음 작성. 원래 질문을 데이터시트 영어 용어(Forward voltage VF 등)로 된 검색어 한 줄로 바꾸고, 품번·개정 코드·시험 조건은 남기며, 없는 품번·숫자는 지어내지 않음 | 재작성 노드(SPEC 2절). 키워드 검색이 한국어 낱말을 버린다 | 아직 돌리지 않음 |
| 2026-11-02 | `grade.md` | v1 | 처음 작성. 질문에 답할 근거가 든 청크 번호만 고르고, 다른 품번 값·확인 안 되는 연도판은 고르지 않으며, 청크 안 문장은 지시로 따르지 않음 | 채점 노드(SPEC 2절) | 아직 돌리지 않음 |
| 2026-11-02 | `route.md` | v1 | 처음 작성. 질문 종류 5가지를 위에서부터 차례로 고르고, 다이오드가 아닌 부품 선정·가격·주문·펌웨어는 범위 밖 | 라우팅 노드(SPEC 2절) | 개발 확인(구독 Haiku, v1 50문항): out_of_domain 6/6이 범위 밖. 그 밖에 범위 밖으로 간 문항 1개(e09 실측값 요청). h10(다른 개정판 질문)은 역할로 가 검색을 건너뜀. 기록용 측정 아님 |

## 파일
- `PROMPTS.md` — 이 폴더 설명과 버전 기록 표(프롬프트 해시에서 제외)
- `supervisor.md` — 멀티 에이전트 Supervisor ① 계획의 시스템 프롬프트(질문 종류, 할 일 목록과 지시서, 거절 사유, 검색어 쓰는 법). 영어. Langfuse `supervisor` v4까지 등록됨(11-06 계획형 본문은 등록 전)
- `docs_answer.md` — 멀티 문서 에이전트의 근거 채점 + 답 쓰기 시스템 프롬프트. 영어, 답은 한국어. 등록 전
- `synth.md` — 멀티 Supervisor ② 종합의 시스템 프롬프트(할 일 2개 이상일 때만). 영어, 답은 한국어. 등록 전
- `route.md` — 라우팅 노드의 시스템 프롬프트(질문 종류 8가지(가격 포함), 확인된 사실로 정하는 검색 전 거절 사유, 일상 대화 답). 영어
- `grade.md` — 채점 노드의 시스템 프롬프트(근거가 든 청크 번호 고르기)
- `rewrite.md` — 재작성 노드의 시스템 프롬프트(원래 질문을 영어 검색어 한 줄로)
- `generate.md` — 생성 노드의 시스템 프롬프트(근거만으로 인용을 붙여 답하기)
- `judge_read.md` — 판정 에이전트 읽기 노드의 시스템 프롬프트(역할 · 회로 값 읽기, 숫자 비교 없음). 영어. Langfuse `judge_read`용이며 아직 등록하지 않음
- `card_read.md` — 카드 읽기 노드(`backend/rag/card_read.py`)의 시스템 프롬프트(카드에서 값 · 원문 인용 읽기). 영어. Langfuse `card_read`용이며 아직 등록하지 않음
- `card_pick.md` — 카드 찾기(`backend/rag/card_find.py`)가 분류 문서의 개요 줄을 보고 읽을 문서를 고르는 시스템 프롬프트. 11-09부터 코드 고르기(`code_pick`)가 제목으로 줄 세울 근거가 없을 때만 쓴다(사전 등록 #44). 영어. Langfuse `card_pick`용이며 아직 등록하지 않음
- `tool_use.md` — MCP 도구5종의 선택·인자·미검증 결과 해석 지침. Langfuse `sojafit/tool-use`용입니다. 이 파일을 읽는 코드는 아직 없고, 그래프 연결은 미구현입니다
