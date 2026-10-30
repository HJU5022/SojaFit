"""LLM 호출은 이 파일 하나로 모읍니다.

그래프 노드나 라우터가 openai를 직접 import하지 않게 하세요.
여기서 책임지는 것:
  - 데모 모드: DEMO_MODE=1이면 키 없이 기록해 둔 응답을 재생합니다 (G2).
    평가자에게는 API 키가 없습니다. 같은 입력에 같은 응답이 나오도록 입력 해시를 키로 기록하세요.
    기록에 없는 질문이 와도 키 없이 죽지 않게 2단으로 만드세요: 1) 입력 해시 재생, 2) 기록이 없으면 검색된 근거 문장을 그대로 인용하는 추출형 답변.
    작은 로컬 모델(1.5B~3B급)은 "[청크 id]" 같은 인용 형식을 지키지 못하므로 데모 모드의 주력으로 권하지 않습니다.
  - Langfuse 연결: Cloud 자격증명을 확인합니다. 트레이스 데이터 수집은 별도 결정 전까지 하지 않습니다.
  - 출력 계약 검증(Pydantic), 실패 시 재시도와 폴백. 재시도에는 반드시 상한을 둡니다.
    키는 조당 하나이고 한도가 있습니다(조당 30달러).
"""
import os

from dotenv import load_dotenv

load_dotenv()
if not os.getenv("LANGFUSE_BASE_URL") and os.getenv("LANGFUSE_HOST"):
    os.environ["LANGFUSE_BASE_URL"] = os.environ["LANGFUSE_HOST"]

DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1"


def check_langfuse_connection() -> bool:
    """Check configured Langfuse credentials without creating a trace."""
    from langfuse import get_client

    return get_client().auth_check()
