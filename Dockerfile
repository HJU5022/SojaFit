# G2: 평가자가 `docker compose up` 한 줄로 띄울 수 있어야 합니다.
FROM python:3.12-slim

# 의존성은 uv.lock에 고정된 버전 그대로 설치합니다.
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-cache

ENV PATH="/app/.venv/bin:$PATH"

COPY backend/ ./backend/
COPY data/ ./data/

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
