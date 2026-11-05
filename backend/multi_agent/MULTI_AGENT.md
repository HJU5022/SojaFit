# multi_agent

## 역할
- 이 폴더: D5 멀티 에이전트(Supervisor 1개 + 서브에이전트 검색 · 판정 · 작성 · 검증)를 둡니다. 서브에이전트가 끝날 때마다 Supervisor로 돌아와 다음 단계를 정하는 허브 구조입니다.
- 넣는 것: Supervisor가 내리는 결정서와 서브에이전트가 올리는 보고서의 형식 · 이유 코드 · 한도(`contracts.py`), 멀티용 상태, Supervisor, 서브에이전트(`agents/`), 조립.
- 넣지 않는 것: D4 단일 에이전트 그래프(`backend/graph/`, D5 비교의 기준선이라 바꾸지 않습니다), 숫자 · 단위 비교(`backend/judge/`), 검색 구현(`backend/rag/`), LLM 직접 호출([services](../services/SERVICES.md)의 `llm.py`만 씁니다), 프롬프트 원문(`backend/prompts/`), 도구 정의(`backend/mcp_skill/`).
- 담당: 에이전트

## 왜 `graph/`와 따로 두었나 [결정 11-05 정운]
- **비교 기준선 보호:** 가이드는 D4 단일 그래프로 기준 점수를 재고 D5에 멀티로 나눠 같은 평가셋으로 비교하라고 합니다. 단일 코드가 같은 폴더에서 바뀌면 기준선이 흔들립니다. 폴더가 다르면 단일은 그대로 남습니다.
- **갈아엎을 코드와 고정 코드의 분리:** 멀티는 설계를 하면서 자주 바뀝니다. 기준선은 바뀌면 안 됩니다. 둘이 섞이면 어느 쪽이 바뀌었는지 가려내기 어렵습니다.
- **정리가 쉬움:** 멀티가 자리 잡으면 단일 폴더만 "기준선 보관"으로 표시하거나 치우면 됩니다.
- `SOJAFIT.md` 트리는 원래 `graph/`를 Supervisor 자리로 적었으나, 위 이유로 새 폴더를 만들고 이 문서와 트리 · 담당 표에 함께 적었습니다(AGENTS.md 규칙 9, `SOJAFIT.md` "파일을 만들거나 옮길 때" 1번).

## 의존 방향
- `multi_agent`는 `graph`를 불러 쓸 수 있습니다. 처음에는 단일의 검색 · 채점 · 재작성 함수를 그대로 감싸고, 하나씩 새 로직으로 바꿉니다. `graph`는 `multi_agent`를 모릅니다(한 방향).
- `multi_agent`는 `judge` · `rag` · `services`를 불러 씁니다. 판정의 숫자 비교는 `judge`에서만 합니다(AGENTS.md 규칙 7).

## 구조 결정 (11-05, 정운과 설계 대화)
- Supervisor는 서브에이전트가 끝날 때마다 보고를 읽고 다음을 판단합니다(LLM이 판단, 코드 규칙으로 라우팅하지 않음).
- Supervisor는 청크 원문이 아니라 서브에이전트의 요약 보고만 읽습니다. 서브에이전트는 자기 일에 필요한 정보만 받습니다(역할과 컨텍스트 분리).
- 도구는 MCP 서버(stdio) 한 곳에 모으고, 에이전트마다 볼 수 있는 도구를 허용 목록으로 제한합니다.
- 검색은 실패 사유를 붙여 다르게 다시 시도하고, 한도를 둡니다. 거절 이유는 내부 코드로 Langfuse에 남기고 사용자에게는 일상어로 보여 줍니다.

## 구현 상태
- 있음: 약속(`contracts.py`), Supervisor(`supervisor.py`, 가짜 LLM으로 시험, 실제 LLM 연결 · Langfuse 프롬프트 등록은 아직).
- 다음 순서: 서브에이전트 → 조립 → 실제 질문으로 Supervisor 결정 측정. 조각마다 사전 등록 · 시험 · 측정을 거칩니다.

## 파일
- `MULTI_AGENT.md` — 이 문서
- `__init__.py` — 패키지 표시
- `supervisor.py` — Supervisor. 질문 · 사실(`Facts`: 품번 · 개정판이 코퍼스에 있나) · 보고 · 한도 현황 · 고를 수 있는 노드를 글(`render`)로 만들어 LLM에 주고 결정서를 받는다(`decide`). 한도를 넘거나 꺼진 웹이면 거절로 바꾸고, 끝내는 길은 막지 않는다. 판단 횟수 세기(`count_decision` · `count_report`). LLM은 `chat` 함수로 받아 시험에서 가짜로 바꾼다
- `contracts.py` — Supervisor의 결정서 `Decision`(다음 노드 7종, 거절이면 거절 사유 필수)과 서브에이전트의 보고서 `AgentReport`(상태 ok · partial · fail, 200자 요약, 근거 번호 · 부족한 값 · 사유), 이유 코드 `Reason`(거절 7종 · 재시도 3종), 한도(`MAX_HOPS` 8 · `MAX_SEARCHES` 2 · `MAX_WRITES` 2)와 한도 검사 `check_limit`. 같은 사유로 검색이 두 번 실패하면 `NOT_FOUND`(추정), 작성 한도는 `VERIFY_FAILED`
