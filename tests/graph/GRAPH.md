# graph

## 역할
- 이 폴더: 질문 처리 그래프(`backend/graph/`)의 노드별 회귀 테스트를 둡니다.
- 넣는 것: `test_graph_<노드>.py`. LLM과 검색기는 가짜로 바꿔 API 없이 돌립니다.
- 넣지 않는 것: 평가 실행기와 동결 감시(`tests/evals/`), 검색·적재 시험(`tests/rag/`), LLM 호출 계약(`tests/services/`).
- 담당: 그래프

실행: `uv run pytest -q tests/graph`(저장소 루트).

## 파일
- `GRAPH.md` — 이 문서
- `test_graph_build.py` — 그래프 조립(D4 v2): 정격 검색 고리(통과 → 생성, 재작성 → 재검색 → 생성, 두 번 다 통과 없음 → 거절, 검색 0장 → 거절, 검색 장애 → 거절)와 검색기가 질문 줄만 받는지, 사실 확인 결과가 라우팅 입력에 들어가는지, 첫 단 거절(범위 밖 · 다른 부품 · 없는 품번 · 없는 개정판)이 검색 0번에 사유 코드를 남기는지, 일상 대화 → 짧은 답, 가격 → 가격 안내(검색 · HTTP 호출 없이 물은 품번만 남고 값 없음), 역할 → 생성, 판정 길(판정 읽기 → 판정 → 답 틀, 인터럽트 1번을 빈 답으로 재개, 사양 표 장애 → 거절), 판정 도구 없이 판정 · 찾기 → 검색 고리, 도구 · 체크포인터 없으면 `ValueError` 확인
- `test_graph_mcp_retriever.py` — PR #44 응답 검증, stdio 세션 재사용, timeout과 1회·2회 MCP 검색 경로, 사양 표 목록 응답(`decode_list_result`) 검증 확인
- `test_graph_mcp_stdio.py` — `TEST_DATABASE_URL`의 격리 코퍼스가 있을 때 실제 LangGraph → stdio MCP → DB 검색과 첫 검색 10초 제한 확인
- `test_graph_generate.py` — 생성 노드: 통과 청크·넷리스트 전달, 인용 검사, 근거 없을 때 LLM 미호출, Skill 유무에 따른 지침·적용 해시 확인
- `test_graph_grade.py` — 채점 노드: 같은 문서의 다른 품번 줄 제거, 다른 개정판만 남으면 LLM 미호출, LLM이 낸 없는 번호 버리기 확인
- `test_graph_read_input.py` — 입력 읽기 노드: 입력 글 나누기, 경로 표시, 앞 턴의 검색 · 사실 · 거절 · 판정 칸 비우기, 큰 넷 자르기(대상 자신의 핀은 늘 보임, AC-10), 평가셋 v1 50문항의 대상 부품 읽기 확인
- `test_graph_refuse.py` — 거절 노드: 라우팅 거절(범위 밖 · 없는 품번 · 없는 개정판)의 멀티와 같은 문구, 검색 고리 거절(품번 문서 없음 · 답 없음 · 검색 장애)의 안내문, 이유 코드 `refusal`, Skill 적용 정보 초기화 확인
- `test_graph_rewrite.py` — 재작성 노드와 채점 뒤 갈림길: 원래 질문 고치기, 검색 횟수별 분기 확인
- `test_graph_route.py` — 라우팅 노드: `route.md` 프롬프트 · 확인된 사실 전달, 라우팅 답안지(`route`) 기록, 범위 밖 · 다른 부품의 거절 사유 채우기, 거절 사유 범위, 일상 대화의 `reply` 필수 확인
- `test_graph_search.py` — 검색 노드: 품번 뽑기, 질문 품번 우선, 품번 없으면 전체 검색, 재작성 검색어 사용 확인
- `test_graph_state.py` — 그래프 상태의 `tries`·`path`는 쌓이고 나머지 칸은 덮어써지는지 확인
