# multi_agent

## 역할
- 이 폴더: 멀티 에이전트(`backend/multi_agent/`)의 회귀 테스트. 소스 폴더와 같은 이름으로 짝을 맞춘다(`tests/graph/` ↔ `backend/graph/`와 같은 규칙).
- 넣는 것: `test_<대상>.py`. LLM과 검색기는 가짜로 바꿔 API 없이 돌린다. 실제 모델·외부 서비스·DB·소켓은 호출하지 않는다.
- 넣지 않는 것: 단일 그래프 시험(`tests/graph/`), 평가 실행기와 동결 감시(`tests/evals/`), 판정 코드 시험(`tests/judge/`).
- 담당: 에이전트

실행: `uv run pytest -q tests/multi_agent`(저장소 루트).

저장된 실측 응답을 재생하는 시험(`test_docs_agent.py`)은 가짜 공급자로 그 응답을 다시 흘려 코드의 처리(인용 교정, 문장 제거, 보존)를 확인한다. 새 모델 성적이 아니고 원시 파일은 바꾸지 않는다. 재생에 쓰는 원시 파일은 `evals/results/threads/injection_baseline_live_2026-11-11_03.jsonl`, `evals/results/threads/injection_t3_smoke_live_2026-11-11_07.jsonl`, `data/demo/snapshot/chunks.jsonl`이다.

## 파일
| 파일 | 확인하는 것 |
|---|---|
| `MULTI_AGENT.md` | 이 문서 |
| `test_build.py` | 조립: 바로 끝내는 길(부품 목록의 종류 거르기 · 종류별 개수 · 없는 종류 한 줄과 부품 종류 가르기 `part_kind` 포함, #59. 견적 안내의 고정 문구와 그 문구 속 화면 이름이 프런트 글자와 같음, #60), 할 일 1개/2개의 답 정리·종합, 지어낸 숫자 거절, 재계획 뒤 거절, 판정 인터럽트 재개, 대상이 빈 대화의 `대상 확인`(대상이 필요한 할 일만 묻고 재개 때 Supervisor를 다시 부르지 않음, #62), 그림의 노드 이름·조건 라벨, 기억 읽기와 찾기 후보 순서 |
| `test_contracts.py` | 계획서 형식 검사(거절 사유 없음, 일상 대화 reply 없음, 할 일 수 범위, 번호 순서, 판정에 맞지 않는 종류, 검색어 없는 문서 할 일), 부품 목록 밖의 `part_kinds`는 비움, 보고 요약 한도, 이유 코드 분류, 상한 상수 |
| `test_facts_lookup.py` | 사실 확인이 MCP 도구(`check_corpus`) 응답(가짜 함수)으로 `Facts`를 만들고 확인할 것이 없으면 도구를 안 부름 |
| `test_supervisor.py` | Supervisor: LLM 입력 글(재계획에도 회로가 붙었는지 `Circuit attached` 줄), 결정 처리와 상한, 재계획 규칙, 승인 사례 입력, 판정 답의 출력 경계, 부분·실패 문서 혼합 보존, 문서 보고의 넷리스트 인용 권한, footprint 비전달 |
| `test_agents.py` | RAG 에이전트: 지시서 검색어, 근거 채점 + 답 쓰기 LLM 1번, 다른 검색어 재검색 1번, 없는 인용 차단, 다른 품번 줄 거르기, 검색 장애·0건, 외부 검색 1회. 사실 확인·거절 문구·판정 답 틀 |
| `test_docs_agent.py` | RAG 에이전트의 인용 처리: 허용 번호, 교정 1회 상한, 미인용 문장 제거와 보존, 과거 사례 인용 거부, enough + missing의 partial, 주문 코드 접미사 허용, 저장된 실측 응답 재생 |
| `test_judge.py` | Spec 에이전트: 읽기 LLM 1번, 인터럽트 한 번과 재개, 판정·찾기·정렬, 비교는 `verdict`에서만, 품번 제조사 이름 떼기, 주문 코드만 다른 동일품, 선호 실장 방식은 순서만 바꿈 |
| `test_judge_read.py` | 판정 읽기: 역할별 값 이름·종류, 역할에 없는 이름은 `dropped`, 코퍼스 밖 요구가 묻지 않고 판정 보고로 나옴, footprint만 다른 입력의 계획·읽기·문서 입력이 같음 |
| `test_readme_graph.py` | README 3절 mermaid 블록이 조립한 그래프(`get_graph(xray=True).draw_mermaid()` + 고정 정규화)와 글자까지 같음. 다시 만드는 명령은 파일 머리말 |
| `test_part_names.py` | 읽기 뒤 품번 바로잡기(`part_names.py`): 사용자 글의 품번으로 맞추고 글에 품번이 없거나 둘 이상이거나 앞부분이 겹치면 그대로 둠, 후보가 원래 부품이 되지 않음, 주문 코드는 한 칸 띄어 씀 |
