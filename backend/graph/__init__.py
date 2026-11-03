"""줄기 그래프 패키지: 상태(state), 노드(nodes), 조립(build)을 모은다.

- 역할: `build.build_graph()`가 compile한 앱을 `evals/run_graph.py`·시험이 가져다 쓴다(서버 import 대상).
- 하지 않는 일: 검색(`backend/rag/`), 숫자 비교 판정(`backend/judge/`), LLM 호출 자체(`backend/services/llm.py`).
- 출처: SPEC.md 2절 "그래프", backend/graph/GRAPH.md.
"""
