# graph

## 역할
- 이 폴더: `backend/graph/`의 노드별 회귀 테스트. 단일 그래프 기준선(`build.py`)과 서비스가 import하는 공용 도구(`nodes.py` 도우미, `mcp_retriever.py`)를 함께 확인한다. 분담은 [GRAPH.md](../../backend/graph/GRAPH.md).
- 넣는 것: `test_graph_<노드>.py`. LLM과 검색기는 가짜로 바꿔 API 없이 돌린다.
- 넣지 않는 것: 평가 실행기와 동결 감시(`tests/evals/`), 검색·적재 시험(`tests/rag/`), LLM 호출 계약(`tests/services/`), 멀티 그래프 시험(`tests/multi_agent/`).
- 담당: 그래프

실행: `uv run pytest -q tests/graph`(저장소 루트).

## 파일
| 파일 | 확인하는 것 |
|---|---|
| `GRAPH.md` | 이 문서 |
| `test_agent_netlist.py` | 에이전트용 KiCad 업로드(`backend/graph/netlist.py`)의 두 형식, 참조 무결성, 크기·깊이 제한 |
| `test_graph_build.py` | 단일 그래프 조립: 정격 검색 고리, 첫 단 거절, 일상 대화·가격 안내·역할·판정 길, 인터럽트 재개, 코퍼스 밖 요구 거절, 판정 도구·체크포인터 없을 때의 동작 |
| `test_graph_read_input.py` | 입력 읽기 노드: 입력 글 나누기, 경로 표시, 앞 턴의 검색·사실·거절·판정 칸 비우기, 큰 넷 자르기(대상 자신의 핀은 늘 보임), 저장소 밖 넷리스트 경로 무시, 주변 핀의 선언 기능 · 숨은 커패시터, 부스트 · 플라이백 기구 판독(선언 극성 · 실제 출력 커패시터, 숫자 핀만으로 추론 안 함), 평가셋 v1 문항의 대상 부품 읽기 |
| `test_graph_route.py` | 라우팅 노드: `route.md` 프롬프트와 확인된 사실 전달, 라우팅 답안지 기록, 거절 사유 채우기·범위, 일상 대화 `reply` 필수 |
| `test_graph_search.py` | 검색 노드: 품번 뽑기, 질문 품번 우선, 품번 없으면 전체 검색, 재작성 검색어 사용 |
| `test_graph_grade.py` | 채점 노드: 같은 문서의 다른 품번 줄 제거, 다른 개정판만 남으면 LLM 미호출, LLM이 낸 없는 번호 버리기 |
| `test_graph_rewrite.py` | 재작성 노드와 채점 뒤 갈림길: 원래 질문 고치기, 검색 횟수별 분기 |
| `test_graph_generate.py` | 생성 노드: 통과 청크·넷리스트 전달, 인용 검사(중첩 명시 번호 인식, 비인용 숫자·쪽수 제외, 바깥 과거 사례 검출), 근거 없을 때 LLM 미호출, Skill 유무에 따른 지침·적용 해시 |
| `test_graph_refuse.py` | 거절 노드: 라우팅 거절의 멀티와 같은 문구, 검색 고리 거절의 안내문, 이유 코드 `refusal`, Skill 적용 정보 초기화 |
| `test_graph_state.py` | 그래프 상태의 `tries`·`path`는 쌓이고 나머지 칸은 덮어써짐 |
| `test_graph_supervisor.py` | Supervisor V0(`backend/graph/supervisor.py`)의 네 필드 스키마, 입력 경계, 의미 일관성, Jev 공통 계약 |
| `test_graph_mcp_retriever.py` | MCP 검색 응답 검증, stdio 세션 재사용, timeout, 1회·2회 MCP 검색 경로, 코퍼스 확인(`check_corpus`) 응답 검증 |
| `test_graph_mcp_stdio.py` | `TEST_DATABASE_URL`의 격리 코퍼스가 있을 때 실제 LangGraph → stdio MCP → DB 검색과 첫 검색 시간 제한 |
