# mcp_skill

## 역할
- 이 폴더: MCP 서버(`backend/mcp_skill/mcp_server/`)의 회귀 테스트를 둡니다.
- 넣는 것: `test_mcp_server.py`처럼 네트워크·DB·API 키 없이 도는 도구별 테스트. 검색기와 HTTP 호출은 가짜로 바꿉니다.
- 넣지 않는 것: 실제 Exa 호출, LangGraph 연결 시험, Skill 점수 비교(`evals/`).
- 담당: 가산을 시작할 때 정합니다.

실행: `uv run pytest -q tests/mcp_skill`(저장소 루트).

## 파일
- `MCP_SKILL.md` — 이 문서
- `test_mcp_server.py` — MCP 도구 5종: 입력 검사, manifest 조회, TSC 웹 후보의 차단·필터, 표본 PDF 해시 대조, 회로 조회, 도구 목록 확인
