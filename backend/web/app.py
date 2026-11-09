"""API 등록 뒤 같은 출처의 React 정적 화면을 연결한다."""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_frontend(app: FastAPI, dist: Path, fallback: Path) -> None:
    """빌드가 없으면 기존 로그인 화면을 제공하고 API 404는 유지한다."""
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

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
        ):
            return response
        index = dist / "index.html"
        headers = {}
        if request_id := response.headers.get("X-Request-ID"):
            headers["X-Request-ID"] = request_id
        return FileResponse(index if index.is_file() else fallback, headers=headers)
