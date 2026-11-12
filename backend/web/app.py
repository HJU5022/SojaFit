"""API 등록 뒤 같은 출처의 React 정적 화면을 연결한다.

역할: 빌드한 React(`frontend/dist`)의 assets를 연결하고, 화면 주소의 GET/HEAD 404를 `index.html`로 바꾼다.
하지 않는 일: API·인증·판정 로직. 빌드가 없을 때 대신 보일 화면(예전 로그인 템플릿은 11-10에 지움).
  빌드가 없으면 화면 주소도 원래 404(공통 오류)를 그대로 돌려준다. Docker 이미지는 늘 React를 빌드해 넣는다(Dockerfile).
출처: backend/web/WEB.md, frontend/FRONTEND.md.
"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """빌드가 있으면 화면 주소에 React index를 주고, API·health·assets의 응답은 그대로 둔다."""
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")
    schematics = dist / "circuit-schematics"
    if schematics.is_dir():
        app.mount("/circuit-schematics", StaticFiles(directory=schematics), name="circuit-schematics")

    @app.middleware("http")
    async def frontend(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if (
            request.method not in {"GET", "HEAD"}
            or response.status_code != 404
            or path == "/api"
            or path.startswith("/api/")
            or path.rstrip("/") == "/health"
            or path == "/assets"
            or path.startswith("/assets/")
            or path == "/circuit-schematics"
            or path.startswith("/circuit-schematics/")
        ):
            return response
        index = dist / "index.html"
        if not index.is_file():
            return response  # [왜] 빌드가 없으면(로컬 백엔드만 띄움) 대신 보일 화면이 없다. 공통 404 JSON 그대로
        headers = {}
        if request_id := response.headers.get("X-Request-ID"):
            headers["X-Request-ID"] = request_id
        return FileResponse(index, headers=headers)
