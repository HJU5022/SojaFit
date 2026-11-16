# prompts

## 역할
- 이 폴더: 노드가 LLM에 보내는 프롬프트 원문(Markdown)과 그 버전 기록 표를 둔다. `Dockerfile`이 `backend/`를 복사하므로 키 없는 데모 모드에서도 같은 프롬프트를 쓴다.
- 넣는 것: 프롬프트 원본 Markdown(노드 하나에 파일 하나, 내용이 곧 시스템 프롬프트)과 아래 버전 기록 표. Langfuse 등록·실행 연결은 [SERVICES.md](../services/SERVICES.md)를 따른다.
- 넣지 않는 것: LLM 호출 코드(`backend/services/llm.py`), 숫자 비교와 단위 환산(`backend/judge/`), 판정 규칙의 임계값(SPEC.md 5절 규칙 파일), 도메인 판단 지침 Skill(`backend/mcp_skill/skills/SKILL.md`).
- 담당: 에이전트

## 프롬프트 해시
`evals/runners/run_graph.py:133`과 `evals/runners/run_skill_pair.py:179`는 이 폴더의 `*.md`를 모두 읽어 프롬프트 해시를 만들되 `PROMPTS.md`만 뺀다. 이 파일을 고쳐도 해시는 바뀌지 않지만, 다른 `.md`를 추가·수정하면 해시가 바뀌어 평가 결과와 묶이는 버전이 달라진다. 프롬프트가 아닌 문서는 이 폴더에 두지 않는다.

## 노드별 모델
`backend/services/langfuse_prompts.py`의 `NODE_MODELS`(`:33`)가 노드별 모델의 정본이다. 선정 이유는 ADR 0014(노드별 분리)와 ADR 0017(Supervisor 모델)이다. 환경변수 `LLM_MODEL`을 정하면 모든 노드가 그 모델 하나를 쓴다. `NODES`에 든 열 개 프롬프트(`supervisor_v0.md` 제외)는 `publish_nodes`가 `backend/prompts/<노드>.md`에서 읽어 Langfuse에 등록하고(`:159`), 실행 전 고정 버전 대조가 같은 파일과 원격 본문을 비교한다(`:181`).

## 파일
읽는 코드는 `backend/`, `evals/`, `scripts/`에서 `prompts` 경로로 파일을 여는 곳을 grep한 결과다. 서비스(요청 처리)가 읽는 파일은 여섯 개이고, 단일 그래프 전용 네 개는 평가 실행기만 돌린다. 어떤 코드도 읽지 않는 프롬프트 파일은 없다.

| 파일 | 내용 | 읽는 코드 | 서비스 사용 |
|---|---|---|---|
| `PROMPTS.md` | 이 문서(프롬프트 해시에서 제외) | 없음 | 해당 없음 |
| `supervisor.md` | 멀티 Supervisor(계획)의 시스템 프롬프트: 질문 종류, 할 일 목록과 지시서, 거절 사유, 검색어 쓰는 법. 영어 | `backend/multi_agent/supervisor.py:31` | 사용 |
| `docs_answer.md` | 멀티 RAG 에이전트의 근거 채점 + 답 쓰기 프롬프트. 영어, 답은 한국어 | `backend/multi_agent/agents/docs.py:34` | 사용 |
| `schematic_dialogue.md` | 검증된 회로도 후보의 차이 설명·선택 질문·전체 소개. 영어, 답은 한국어 | `backend/projects/schematic_dialogue.py` | POST 회로도 대화 |
| `synth.md` | 멀티 종합 노드 프롬프트(보고가 서로 다른 에이전트 2개 이상이고 일부 답·실패가 섞여 `답 정리`가 못 이을 때만, SPEC.md 2절). 영어, 답은 한국어 | `backend/multi_agent/supervisor.py:32` | 사용 |
| `judge_read.md` | Spec 에이전트 읽기 노드 프롬프트: 역할·회로 값 읽기, 숫자 비교 없음. 영어 | `backend/multi_agent/agents/judge.py:35` | 사용 |
| `card_read.md` | 카드 읽기 프롬프트: 카드에서 값·원문 인용 읽기. 영어 | `backend/rag/card_read.py:25` | 사용 |
| `card_pick.md` | 카드 찾기가 분류 문서의 개요 줄을 보고 읽을 문서를 고르는 프롬프트(코드 고르기 `code_pick`이 못 줄 세울 때만). 영어 | `backend/rag/card_find.py:91` | 사용 |
| `route.md` | 단일 그래프 라우팅 프롬프트: 질문 종류 8가지, 확인된 사실로 정하는 검색 전 거절 사유, 일상 대화 답. 영어 | `backend/graph/nodes.py:180` | 평가 전용 |
| `grade.md` | 단일 그래프 채점 프롬프트: 근거가 든 청크 번호 고르기 | `backend/graph/nodes.py:291` | 평가 전용 |
| `rewrite.md` | 단일 그래프 재작성 프롬프트: 원래 질문을 영어 검색어 한 줄로 | `backend/graph/nodes.py:307` | 평가 전용 |
| `generate.md` | 단일 그래프 생성 프롬프트: 근거만으로 인용을 붙여 답하기 | `backend/graph/nodes.py:440` | 평가 전용 |
| `supervisor_v0.md` | Supervisor V0의 질문 분류·근거 선택·다음 경로 계약. `backend/` 코드는 읽지 않음 | `evals/runners/run_supervisor_prompt_v0.py:25` | 사용 안 함 |

단일 그래프 전용 프롬프트는 [GRAPH.md](../graph/GRAPH.md)의 분담 표대로 `evals/runners/run_graph.py`(단일 대 멀티 비교, EVAL_REPORT.md 4장)와 `run_skill_pair.py`가 쓴다.

## 버전 기록
프롬프트를 바꾸면 같은 PR에서 한 줄을 더한다. 평가를 다시 쟀으면 결과 위치도 적는다. 최근 줄을 위에 둔다.

| 날짜 | 파일 | 버전 | 바꾼 것 | 이유 | 평가 결과 |
|---|---|---|---|---|---|
| 2026-11-17 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | 서로 다른 두세 품번의 차이 · 비교는 `rating`이고 부품마다 `docs` 할 일 하나(`query`에 그 품번, `parts`에 그 품번 하나). 같은 품번의 접미사 · 주문 코드(SS14H와 SS14, L0와 L0G)는 할 일 하나 그대로. 일반 설명 `chat`은 끝 문장을 쓰지 않고 `reply_kind: general`만 표시(코드가 붙임). 데이터시트 그래프 · 특성 곡선 그림은 읽지 않으니 보여 주거나 읽어 준다고 말하지 않기 | #66: "1N4007이랑 1N4148 차이가 뭐야?"가 1N4148만 답하고 trr 문장을 되풀이함, 일반 설명 끝이 "데이tásheet 근거가 아닌 일반 설명입니다."로 깨짐, "그 그래프 보여줄 수 있어?"에 "특성 곡선에 한해 확인해 드릴 수 있습니다"라고 답함 | 아직 없음(가짜 LLM 시험만). 동결 평가셋의 접미사 · 주문 코드 문항(v3-18 L0/L0G, v3-20 SS14H/SS14, draft50-n06 A0G/R0G)은 비교 규칙의 예외로 적어 할 일 하나 그대로. 서로 다른 두 품번을 비교하는 동결 문항은 없음 |
| 2026-11-17 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | 품번 · 물음표 없이 조건 값만 준 말도 이전 사용자 입력을 받게 하고(`render_plan`), 그 말은 바로 앞 후보 요청을 그 조건으로 다시 판정 · 찾기(앞 요청이 없으면 `chat`으로 무엇을 볼지 묻기). 앞 답 · 근거를 다시 보여 달라는 말은 `chat` + `reply_kind: earlier_answer`(빈 reply)이고 답은 코드 고정 문구 | #64: 판정 뒤 "입력 전압은 5V, 부하 전류는 1.5A야"가 후보 없는 candidate_judge로 거절되고, "아까 SS14 판정 근거 다시 보여줘"에 "다시 조회하지 않고 말씀드리지 않겠습니다"라고 답함 | 아직 없음(가짜 LLM 시험만). 평가 실행기는 대화 이력을 넘기지 않아 동결 평가셋의 입력 글은 그대로이고, 동결 문항은 모두 무언가를 묻는 말이라 조건만 준 말 규칙에 닿지 않음 |
| 2026-11-17 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | 거절 사유 `measurement`(사용자 보드 · 로트 실측값) · `circuit_value`(효율 · 소비 전력 · 바꾼 뒤 출력 전압 같은 회로 전체 값, 부품 PD는 `rating`) · `maker_missing`(품번 없이 TSC가 아닌 제조사 · 브랜드로 바꾸거나 찾기, 질문 종류 `candidate_find`이고 `other_part` 아님)을 더하고 `not_found`는 다이오드가 아닌 부품만 남김. 실측 · 회로 전체 값은 `out_of_scope` · `other_part`가 아니라고 적음. 문구는 코드(`messages.refusal_message`)가 고정 | #63: "D1 실제로 측정한 온도" · "D1을 삼성 부품으로 바꿔줘" · "효율이 몇 % 좋아져?"가 모두 not_found의 "이 부품 자료를 찾지 못했어요"를 받음 | 아직 없음(가짜 LLM 시험만). 동결 평가셋의 실측(draft30-e09 · h08, v3-39~44) · 출력 전압(draft30-h03) · 제조사 지정 찾기(draftv2-n13 · n15 · n17 · n19) 문항은 거절 기대 그대로라 사유 코드만 바뀜. 부품 PD 정격(draft50-n05) · 전력 정격 찾기(draftv2-n06, v3-13)는 `rating` · `candidate_find`로 남게 예외를 적음 |
| 2026-11-16 | `schematic_dialogue.md` | 다중 회로도 후보 대화 | 서버가 정한 모드·후보·차이 항목으로 자연어 설명과 질문 생성 | 동명 후보 구분과 복수 요청 전체 소개 | 관련 회귀와 등록 사례의 실제 응답은 worklog/osc.md에 기록 |
| 2026-11-17 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | 질문 종류 · 다음 길 `quote`(견적 · 견적서를 만들어 · 내 · 보여 달라는 요청)를 더함. `out_of_scope`는 실제 주문 · 결제(품번 · 수량이 있어도)와 판매처 · 최저가 찾기만, `price`는 품번의 현재 가격 · 재고만으로 좁히고 예문("견적서 내줘" → quote, "SS34 가격 얼마야" → price, "주문해 줘" · "어디서 제일 싸게 사?" → out_of_scope)을 넣음. `chat` 답에서 견적을 못 만든다고 말하지 않게 함. 답은 코드(`quote_answer`)가 고정 문구로 냄 | #60: 회로 대화의 "견적서 내줄 수 있나"가 `out_of_scope`로 가 "회로나 부품에 관한 질문을 해 주세요"라고 답함 | 아직 없음(가짜 LLM 시험만). 동결 평가셋에 견적 문항은 없고, 범위 밖 기대 문항 draft50-n18(판매처 · 재고 · 가격) · n20(100개 주문 · 결제)이 이 변경과 맞닿음. 계획서 형식과 입력 글이 바뀌어 키 없는 데모 기록(`data/demo/recordings/`)은 다시 만들지 않음 |
| 2026-11-17 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | `parts_list`에 부품 종류 `part_kinds`(diode · led · resistor 등 12가지, 비우면 전체)를 고르게 함. 회로가 붙은 대화의 "X 뭐뭐 있어 · 몇 개야 · 목록 보여줘"와 되묻기는 `parts_list`(종류가 다이오드가 아니어도 `other_part` 아님), 일반 설명 `chat`은 뜻을 묻거나("다이오드가 뭐야") 회로가 없을 때만. 입력에 `Circuit attached: yes (N parts)` · `no` 줄(`render_plan`)을 더함 | #59: 84부품 회로 대화에서 "다이오드는 뭐뭐잇어"가 `chat` 일반 설명으로 가고, 되물은 `parts_list`는 84개 전체를 냄 | 아직 없음(가짜 LLM 시험만). 입력 글이 바뀌어 키 없는 데모 기록(`data/demo/recordings/`)의 Supervisor 호출 키와 맞지 않음, 다시 만들지 않음 |
| 2026-11-17 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | 질문 종류 · 다음 길 `parts_list`(지금 회로의 부품 목록 요청, `chat` · `role` · `other_part`가 아님)를 더하고, `chat` 답에서 회로 부품을 보여 줄 수 없다고 말하지 않게 함. 목록은 코드(`parts_list_answer`)가 넷리스트로 답함 | #55: "부품 리스트 좀 보여줄래"가 `chat`으로 가 Supervisor가 지어낸 거절을 씀 | 아직 없음(가짜 LLM 시험만). 키 없는 데모 기록(`data/demo/recordings/`)은 이 프롬프트로 다시 만들지 않음 |
| 2026-11-16 | `supervisor.md` | 공식 제조사 정격 조회 | 외부 검색이 켜진 션트 기준소자의 정격 조회를 docs에 허용하고 일반 IC 대체 판정 거절은 유지 | 허용 제조사의 공식 원문 정격 질문이 검색 전에 범위 밖으로 분류되는 문제 방지 | 허용 일곱 제조사 범위, 상세 결과 worklog/osc.md |
| 2026-11-11 | `docs_answer.md` | 작업별 근거 범위 | 넷리스트는 대상이 있는 role 작업에만 제공하며 사양 조회에는 허용하지 않음을 명시 | T3 사양 답변에 부품값·넷명 혼용 가능성이 있는 부가 설명이 포함됨 | 저장 T3 응답 무료 재생·교정 실패/성공·정상 연결 보존 검사, 새 유료 측정 없음 |
| 2026-11-10 | `docs_answer.md` | 맡은 항목·근거부재 분리 | 전체 질문은 문맥으로만 사용, 맡은 항목의 미확인 사실은 missing에 기록하고 답의 문장마다 근거 인용 | 스모크02의 다른 하위작업에 대한 근거부재 문장이 최종답에서 모순을 일으킴 | 저장 응답 무료 재생·모의 교정 검사, 이 버전의 유료 재측정 없음 |
| 2026-11-10 | `docs_answer.md` | 인용 번호 명시 · 무료 검증 | 입력의 허용 chunk ID만 그대로 인용하고 페이지·문서 위치·임의 순번을 쓰지 않도록 명시 | 실제 T1/T3 스모크의 1000V 문장이 잘못된 인용으로 제거됨 | 저장 응답 오류 재현·가짜 교정 응답 검사만 수행, 유료 재측정 없음 |
| 2026-11-10 | `tool_use.md` | 지움 | 파일을 지움(Langfuse `sojafit/tool-use` 등록 번호 1은 그대로) | 읽는 코드가 없었고 그래프에 연결하지 않았다 | 해당 없음 |
| 2026-11-10 | `docs_answer.md` | 다음 버전 | `partial`일 때도 빠진 부분을 겨눈 다른 검색어를 `next_query`에 쓴다 | 일부만 답하고 끝내 정답 근거 없이 답했다(v3-20, 사전 등록 #49) | 사전 등록 #49 측정 결과 |
| 2026-11-09 | `supervisor.md` | 다음 버전 | 판단 순서 3단계(범위 → 확인된 사실 → 질문 종류별 에이전트), 후보 판정 · 찾기는 다이오드만 | Supervisor를 Haiku로 바꾸면서 범위 밖 · 없는 품번 · 찾기 연결을 틀렸다(#46, 사전 등록 #47) | 사전 등록 #47 측정 결과 |
| 2026-11-09 | `supervisor.md`, `docs_answer.md`, `synth.md`, `generate.md`, `judge_read.md` | 기억 근거 분리·원격 등록 전 | 과거 승인 ID는 답 본문의 근거로 쓰지 않고 `memory_refs` 별도 필드로 반환 | 기억만으로 현재 사양 주장이 통과하는 경로 차단 | 가짜 모델·로컬 DB 회귀 검사. 전체 실제 모델 품질은 미측정 |
| 2026-11-09 | `supervisor.md`, `docs_answer.md`, `synth.md` | main 계획형 구조 통합·원격 등록 전 | main의 Plan/Send/종합 규칙을 유지하고 과거 승인 JSON의 데이터 경계·현재 근거 우선·사례 출처 구분 지침 추가 | PR #72 충돌 해결과 thread 기억 전달 유지 | 가짜 모델/실제 PostgreSQL 통합 및 전체 회귀 결과는 worklog/sth.md |
| 2026-11-09 | `supervisor.md`, `judge_read.md`, `generate.md` | 로컬 변경·Langfuse 등록 전 | 별도 historical approved cases 데이터 경계, 현재 조건·사양 근거 우선, 과거 값 복사 금지, 사례 출처 구분 | 새 thread에서 자기 승인 사례 참고 | 실제 DB/가짜 모델 격리 시험 및 실제 generate 합성 A 1건 회상 smoke 확인. 전체 평가 재측정 없음 |
| 2026-11-06 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | 허브 구조의 "다음 노드 고르기 · 보고 뒤 규칙"을 빼고 계획서(질문 종류 · 다음 길 tasks · finish · price · refuse · 할 일 최대 3개와 지시서: 에이전트 · 종류 · 목표 · 출력 · 경계 · 첫 검색어)를 내게 다시 씀. 제약(숫자 비교 금지 · 거절 사유 · 판정은 후보 판정 · 찾기만 · 사실 믿기)과 질문 종류 정의, 검색어 쓰는 법(예전 `rewrite.md`)은 남김 | 멀티 재설계(`backend/multi_agent/MULTI_AGENT.md`): 규칙표를 따라가 질문당 판단 4번 · 비용 20배(D5) | v3 측정 전 |
| 2026-11-06 | `docs_answer.md` | v1(Langfuse 등록 전) | 처음 작성. RAG 에이전트의 근거 채점(enough · partial · none, 없으면 다른 검색어)과 답 쓰기(문장마다 [번호] · [넷리스트], 값은 그대로, 대체 판단 없음)를 한 호출로 | 예전 채점(Luna) · 생성(Haiku) 두 호출을 하나로. 채점은 질문 맥락을 가진 쪽이 해야 한다 | v3 측정 전 |
| 2026-11-06 | `synth.md` | v1(Langfuse 등록 전) | 처음 작성. 종합: 할 일 2개 이상의 부분 답을 한 답으로, 인용 유지, 판정 표 · 숫자는 다시 쓰지 않음(코드가 붙임), 실패한 부분은 이유와 함께 | 위와 같음 | v3 측정 전 |
| 2026-11-06 | `judge_read.md` | 다음 버전(Langfuse 등록 전) | 출력 칸 `required_specs`(꼭 요구한 성질: 사용자 말 + 사양 표 항목 18개 중 하나 또는 `none`) · `maker_wanted`(요구한 제조사, TSC는 `TSC`) · `revision_wanted`(요구한 개정 코드 · 판)와 사양 표 항목 뜻 목록 "Spec-table items"를 더함. 바꾸는 이유(원가 · 재고 · 단종)와 회로 값은 요구 성질로 쓰지 않게 함 | 코퍼스 밖 요구 거절(SPEC 8.3). 고장률 · 잡음 · 다른 제조사 · 없는 판을 요구한 비관련 질문이 판정 답을 받았다(동결 평가 비관련 35건 중 8~10건) | 아직 없음(가짜 LLM 시험만) |
| 2026-11-06 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | 규칙 3: 판정 보고가 fail이면 보고의 사유로 거절(search_error 외에 코퍼스 밖 요구의 part_missing · revision_missing · not_found) | 위와 같음. 코드도 같은 경우를 거절로 바꾼다(`supervisor.decide`) | 아직 없음(가짜 LLM 시험만) |
| 2026-11-06 | `judge_read.md` | 다음 버전(Langfuse 등록 전) | `values`의 `name`을 고른 역할(`role_alt` 포함)이 받는 이름으로만 쓰게 하고(입력 글의 역할 줄에 `inputs: 이름 (종류)`를 코드가 붙임), 사용자가 다른 말로 준 값은 그 역할에서 같은 양을 뜻하는 이름으로 옮기게 함. 모든 값 이름의 뜻 · 단위 목록 "Value names"를 더함 | 모든 역할의 이름을 한 줄로 주던 때 다른 역할의 이름(`i_out` · `v_in_max` · `v_bus` · `v_clamp`)으로 읽어 코드가 버리고 기준값이 비었다(동결 평가 4회 실측, 인용 없는 답 40건 중 20건) | 아직 없음(가짜 LLM 시험만) |
| 2026-11-06 | `route.md` | 다음 버전(Langfuse 등록 전) | 질문 종류에 `price`(다이오드 품번의 현재 가격 · 재고)를 4번째로 더해 8가지로 하고, 범위 밖에서 가격 · 재고를 빼고 주문 · 결제 · 판매처 찾기 · 비교만 남김 | 실시간 가격 · 재고 표시(SPEC 1절). 값은 그래프 밖 화면이 Mouser로 조회한다(ADR 0009) | 아직 없음(가짜 LLM 시험만). 동결 n18(SS34 판매처 · 재고 · 가격)은 정답이 범위 밖 거절이라 가격 길로 가면 채점이 달라진다 |
| 2026-11-06 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | 다음 노드 `price`와 질문 종류 `price`를 더하고, 첫 판단에서 가격 질문은 검색 없이 `price`로. 범위 밖에 주문 · 결제 · 판매처 찾기 · 비교를 적어 `route.md`와 맞춤 | 위와 같음. D4 · D5가 같은 질문을 같은 길로 보내게 한다 | 아직 없음(가짜 LLM 시험만) |
| 2026-11-06 | `route.md` | 다음 버전(Langfuse 등록 전) | 질문 종류를 멀티 Supervisor와 같은 7가지(chat · out_of_scope · other_part · role · candidate_find · candidate_judge · rating)로 넓히고, 입력의 확인된 사실(Verified facts)로 검색 전 거절 사유 `reason`(out_of_scope · not_found · part_missing · revision_missing)과 일상 대화 답 `reply`(300자)를 낸다 | D4 v2: 범위 판정을 첫 단에서 하고 질문 종류마다 다른 길로 보낸다(11-06) | 아직 없음(가짜 LLM 시험만) |
| 2026-11-06 | `supervisor.md` | 다음 버전(Langfuse 등록 전) | 판정 · 찾기 질문을 `judge`가 보일 때 바로 `judge`로 보냄(검색을 먼저 거치지 않음). 검색 보고 뒤에는 `writer`로. 판정 보고가 ok · partial이면 `writer`, search_error 실패면 거절. `judge` 설명에 candidate_find를 더함 | Spec 에이전트 연결(docs/specs/judge-agent.md What 1번) | 아직 없음(가짜 LLM 시험만) |
| 2026-11-06 | `judge_read.md` | v1 | 처음 작성. 대상 다이오드의 역할(R01~R23 · other)과 근거 핀, 질문에 적힌 회로 값(quote 그대로), 원래 부품 · 후보 품번 · 원하는 패키지 · 분류를 정해진 칸으로 낸다. 숫자를 비교하거나 적합 여부를 정하지 않는다. 영어. Langfuse에는 아직 등록하지 않음 | Spec 에이전트 읽기 노드(docs/specs/judge-agent.md) | 아직 없음(가짜 LLM 시험만) |
| 2026-11-05 | `supervisor_v0.md` | v0 | 여섯 질문 유형·전체 필요 근거·현재 상태별 다음 경로를 네 필드로 반환 | Luna·Haiku·Jev의 상태 기반 라우팅 비교 기준선 | V0 13건: `exact_decision_match` Luna·Haiku 1.0(13/13), Jev 0.538(7/13). `evals/results/supervisor/2026-11-06-prompt-v0-v1/summary.json` |
| 2026-11-05 | `route.md`, `grade.md`, `rewrite.md`, `generate.md` | Langfuse 이름 변경 | 등록 이름에서 `sojafit/` 폴더를 뺌: `route`, `grade`, `rewrite`, `generate`, Skill은 `skill-diode-evidence`. 본문은 그대로 | 프로젝트가 SojaFit 하나라 접두사가 필요 없고 목록이 한 줄로 보이게 함. 이전 `sojafit/` 폴더 프롬프트는 과거 트레이스가 가리켜 지우지 않음 | 동작 변화 없음(이름만) |
| 2026-11-05 | `supervisor.md` | v1 | 처음 작성(11-05 영어로 다시 씀, Langfuse `supervisor` v1 등록). 다음 노드 7종(search · judge · writer · verifier · web · finish · refuse)과 거절 사유 7종, 보고 뒤 판단 규칙 | 멀티 에이전트 Supervisor(D5). 코드 규칙 if 문이 아니라 LLM이 판단한다는 설계 기준 | 아직 없음(가짜 LLM 시험만) |
| 2026-11-05 | `supervisor.md` | v3 | 질문 종류에 `chat`(일상 대화, Supervisor가 한국어 `reply`로 직접 답하고 끝냄)와 `other_part`(다이오드가 아닌 전자 부품, 웹 조회 또는 못 찾음 거절)를 더하고, `out_of_scope`는 서비스와 전혀 무관한 질문만 뜻하게 바꿈. 전자 일반 개념 질문은 짧은 설명 + "데이터시트 근거 아님" 표시. 영어로 작성해 등록 | 근거 3등급과 일상 대화 허용(SPEC 2절) | 실제 Luna 4문장 확인(인사 · 날씨 거절 · MOSFET 못 찾음 거절 · 일반 개념). 70문항 측정 전 |
| 2026-11-05 | `supervisor.md` | v4 | 본문은 v3과 같다. Langfuse 등록 설정의 모델만 `anthropic/claude-sonnet-5.5`(temperature 0)로 바꿨다(노드별 모델 변경, ADR 0014) | 노드별 모델 변경 | 해당 없음 |
| 2026-11-05 | `route.md` | v2 | 한국어에서 영어로 번역(규칙 내용 같음, 답변은 한국어) | 모델이 영어를 더 잘 읽고 토큰이 적음, 멀티 에이전트가 영어 위에 쌓임 | v2 70문항 사전 등록 #35: cited_gold 12 · over_refusal 23 · correct_refusal 35(한국어와 같음), 비용 -11%. `evals/results/graph/graph_dataset_v2_2026-11-05.json` |
| 2026-11-05 | `grade.md` | v2 | 한국어에서 영어로 번역(규칙 내용 같음, 답변은 한국어) | 모델이 영어를 더 잘 읽고 토큰이 적음, 멀티 에이전트가 영어 위에 쌓임 | v2 70문항 사전 등록 #35: cited_gold 12 · over_refusal 23 · correct_refusal 35(한국어와 같음), 비용 -11%. `evals/results/graph/graph_dataset_v2_2026-11-05.json` |
| 2026-11-05 | `rewrite.md` | v2 | 한국어에서 영어로 번역(규칙 내용 같음, 답변은 한국어) | 모델이 영어를 더 잘 읽고 토큰이 적음, 멀티 에이전트가 영어 위에 쌓임 | v2 70문항 사전 등록 #35: cited_gold 12 · over_refusal 23 · correct_refusal 35(한국어와 같음), 비용 -11%. `evals/results/graph/graph_dataset_v2_2026-11-05.json` |
| 2026-11-05 | `generate.md` | v2 | 한국어에서 영어로 번역(규칙 내용 같음, 답변은 한국어) | 모델이 영어를 더 잘 읽고 토큰이 적음, 멀티 에이전트가 영어 위에 쌓임 | v2 70문항 사전 등록 #35: cited_gold 12 · over_refusal 23 · correct_refusal 35(한국어와 같음), 비용 -11%. `evals/results/graph/graph_dataset_v2_2026-11-05.json` |
| 2026-11-03 | `tool_use.md` | `sojafit/tool-use` 등록 번호 1 | PR #36 당시 도구 5종(현재 6종, `backend/mcp_skill/mcp_server/server.py`)의 선택·인자·결과 해석을 별도 프롬프트로 작성 | manifest ID·웹 후보·PDF 무결성·공개 회로의 계약을 구분 | #21~#23 모의 12건 확인. 도구/인자 5/5·고정 action11/12 일치, 실제 도구 0회. `evals/results/skill/skill_tool_summary_2026-11-03.json` |
| 2026-11-03 | `../mcp_skill/skills/SKILL.md` | Langfuse 등록 번호 2 | S1 7상황·S2 6상황의 현재 본문 등록, 노드 chat prompt는 버전 4 유지 | 상황별 판단까지 작성한 본문과 검증 대상 일치 | #20 대표 흐름 4건·직접 생성 13건의 추적 연결 확인. 답변 기준 12/13 충족, 충돌 1건 실패. `evals/results/skill/skill_tool_summary_2026-11-03.json` |
| 2026-11-03 | `route.md`, `grade.md`, `rewrite.md`, `generate.md` | Langfuse development v4 | `sojafit/route`, `grade`, `rewrite`, `generate`로 chat prompt 등록. user는 `{{input}}`, 생성 system에 선택적 `{{domain_skill}}` | 고정 버전과 generation 연결. 모델 Haiku 5.5·temperature 0·출력 4096 | 합성 4건·generation 10개에서 프롬프트 버전·모델·부모 연결을 API로 확인. `evals/results/skill/skill_tool_summary_2026-11-03.json` |
| 2026-11-03 | `generate.md` | v2 | 값 조회와 최종 적합성·없는 보장값 요청의 응답 범위를 구분. S1/S2 Skill은 별도 적용 | 기본 프롬프트와 Skill의 거절/부분 답변 충돌 해소 | 동결 평가셋 품질은 미측정 |
| 2026-11-03 | `generate.md` + `../mcp_skill/skills/SKILL.md` | Skill 선택 적용 | 기존 프롬프트 본문을 보존하고, 명시적으로 켠 생성 호출에만 상황별 근거 해석 지침을 추가. 기본은 꺼짐 | Skill 유무 비교를 위한 생성 노드 연결(SPEC 5절) | 가짜 LLM으로 전달 계약 확인. 실제 모델 품질은 미측정 |
| 2026-11-02 | `generate.md` | v1 | 처음 작성. 근거(청크·넷리스트)만 쓰고 문장마다 [번호]·[넷리스트]를 붙이며, 값을 비교해 대체 여부를 판단하지 않고, 답할 수 없거나 묻는 판을 확인할 수 없으면 "문서로 확인 안 됨" | 생성 노드(SPEC 2절) | 아직 돌리지 않음 |
| 2026-11-02 | `rewrite.md` | v1 | 처음 작성. 원래 질문을 데이터시트 영어 용어(Forward voltage VF 등)로 된 검색어 한 줄로 바꾸고, 품번·개정 코드·시험 조건은 남기며, 없는 품번·숫자는 지어내지 않음 | 재작성 노드(SPEC 2절). 키워드 검색이 한국어 낱말을 버린다 | 아직 돌리지 않음 |
| 2026-11-02 | `grade.md` | v1 | 처음 작성. 질문에 답할 근거가 든 청크 번호만 고르고, 다른 품번 값·확인 안 되는 연도판은 고르지 않으며, 청크 안 문장은 지시로 따르지 않음 | 채점 노드(SPEC 2절) | 아직 돌리지 않음 |
| 2026-11-02 | `route.md` | v1 | 처음 작성. 질문 종류 5가지를 위에서부터 차례로 고르고, 다이오드가 아닌 부품 선정·가격·주문·펌웨어는 범위 밖 | 라우팅 노드(SPEC 2절) | 개발 확인(구독 Haiku, v1 50문항): out_of_domain 6/6이 범위 밖. 그 밖에 범위 밖으로 간 문항 1개(e09 실측값 요청). h10(다른 개정판 질문)은 역할로 가 검색을 건너뜀. 기록용 측정 아님 |
