"""MCP 서버(가산 선택) 자리표시자.

역할: 3차 RAG 검색 등 서비스 기능을 FastMCP tool로 노출할 자리. 지금은 예시 tool(example_tool) 하나뿐이다.
호출자: MCP 클라이언트(Claude Desktop·Cursor 등, 또는 langchain-mcp-adapters). 읽는 환경변수는 없다.
실행: `python -m backend.mcp_skill.mcp_server.server`(stdio).
하지 않는 일: 도구 5종 구현과 LangGraph 클라이언트 연결(PR #36 통합 대상, 아직 없음), 판정 코드(backend/judge/).
출처: backend/mcp_skill/MCP_SKILL.md, SPEC.md 5절 "MCP 도구 선택 프롬프트", docs/specs/mcp-tool-prompt.md.
[왜] 도구를 무엇으로 가를지가 설계다. 모델이 tool 설명만 읽고 언제 쓰는 도구인지 알아야 한다(2주차 6·7강).
"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("project-mcp")


@mcp.tool()
def example_tool(query: str) -> str:
    """이 도구가 언제 쓰이는지 한 문장으로 적습니다. 모델이 이 설명만 보고 고릅니다.

    Args:
        query: 무엇을 넣어야 하는지

    Raises:
        NotImplementedError: 아직 구현 전인 자리표시자다.
    """
    # [주의] MCP tool의 docstring은 모델에게 보이는 도구 설명이다. 구현할 때 언제 쓰고 언제 쓰지 않는지까지 적는다
    raise NotImplementedError


if __name__ == "__main__":
    mcp.run()
