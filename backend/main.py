"""FastAPI 진입점.

그래프(backend/graph), 검색(backend/rag), 로그인(backend/auth.py)은 각자 자리에서 만들고
여기서는 엔드포인트로 연결만 합니다. LLM 호출은 services/llm.py 한 곳에서만 합니다.
"""
from fastapi import FastAPI

app = FastAPI(title="3차 프로젝트 API")


@app.get("/health")
def health() -> dict:
    """평가자와 배포 환경이 서비스 상태를 확인하는 곳. 지우지 마세요."""
    return {"status": "ok"}


# TODO: 도메인 엔드포인트를 여기에 추가하세요.
#   - 질의 엔드포인트: 로그인한 사용자 id로 thread를 정하고 그래프를 호출합니다
#   - 오류 응답 규약을 정합니다 (검색 결과 없음, 승인 대기 중, 한도 초과 등을 구분)
#   - 요청 ID, 사용 모델, 토큰 수, 지연 시간을 로그에 남깁니다
