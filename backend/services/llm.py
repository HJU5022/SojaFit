"""LLM 호출은 이 파일 하나로 모읍니다.

그래프 노드나 라우터가 openai를 직접 import하지 않게 하세요.
여기서 책임지는 것:
  - 데모 모드: DEMO_MODE=1이면 키 없이 기록해 둔 응답을 재생합니다 (G2).
    평가자에게는 API 키가 없습니다. 같은 입력에 같은 응답이 나오도록 입력 해시를 키로 기록하세요.
  - Langfuse 트레이스: 입출력, 모델, 토큰, 지연, 비용을 남기고 평가 점수를 연결합니다 (G6).
  - 출력 계약 검증(Pydantic), 실패 시 재시도와 폴백. 재시도에는 반드시 상한을 둡니다.
    키는 조당 하나이고 한도가 있습니다(조당 30달러).
"""
import os

DEMO_MODE = os.getenv("DEMO_MODE", "1") == "1"

# TODO: 구현
#   def complete(messages, *, model, response_model=None) -> ...
