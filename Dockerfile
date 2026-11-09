# G2: 평가자가 `docker compose up` 한 줄로 띄울 수 있어야 합니다.
FROM python:3.12-slim

# 의존성은 uv.lock에 고정된 버전 그대로 설치합니다.
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /uvx /bin/

WORKDIR /app

# UV_COMPILE_BYTECODE: 시작 시간을 줄이려 설치할 때 .pyc를 미리 만든다.
# UV_PYTHON_DOWNLOADS=never: 베이스 이미지의 파이썬 3.12만 쓰고 uv가 파이썬을 내려받지 못하게 한다.
ENV UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

# 코드보다 먼저 의존성 파일만 복사해야 코드만 바뀔 때 이 설치 층을 캐시에서 재사용한다.
# --locked: uv.lock과 pyproject.toml이 어긋나면 실패. --no-dev: 테스트 도구는 이미지에 넣지 않는다.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-cache

# uv가 만든 가상환경의 uvicorn을 바로 실행하려고 PATH 앞에 둔다.
ENV PATH="/app/.venv/bin:$PATH"

COPY backend/ ./backend/
# data/는 서비스가 읽는 데이터(코퍼스·회로·데모)다. evals/·tests/·scripts/는 서비스에 필요 없어 넣지 않는다.
COPY data/ ./data/
COPY db/ ./db/

EXPOSE 8000
# 0.0.0.0: 컨테이너 밖(compose의 포트 연결)에서 접속하려면 모든 인터페이스에 열어야 한다.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
