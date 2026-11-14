# G2: 평가자가 `docker compose up` 한 줄로 띄울 수 있어야 합니다.
FROM node:24-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/index.html frontend/vite.config.ts frontend/tsconfig*.json ./
COPY frontend/src/ ./src/
COPY frontend/public/ ./public/
COPY data/circuits/ /data/circuits/
ARG VITE_LOCAL_ATTACHMENT_UI=0
RUN VITE_LOCAL_ATTACHMENT_UI=$VITE_LOCAL_ATTACHMENT_UI npm run build

FROM ubuntu:24.04 AS renderer
# KiCad 10 originals also occur in the verified public corpus. Use the official
# stable 10.0 PPA; keep Python 3.12 and the API image's dependencies separate.
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates software-properties-common python3.12 python3.12-venv libcairo2 util-linux \
    && add-apt-repository --yes ppa:kicad/kicad-10.0-releases \
    && apt-get update \
    && apt-get install -y --no-install-recommends 'kicad=10.0.*' \
    && kicad-cli --version \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --only-group renderer --no-cache
ENV PATH="/app/.venv/bin:$PATH"
COPY backend/ ./backend/
RUN useradd --create-home --shell /usr/sbin/nologin sojafit
USER sojafit
EXPOSE 8000
CMD ["uvicorn", "backend.projects.schematic:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python:3.12-slim

# API 이미지에는 KiCad를 넣지 않는다. 렌더러 이미지는 --build-arg INCLUDE_KICAD=1로 만든다.
ARG INCLUDE_KICAD=0
RUN apt-get update \
    && if [ "$INCLUDE_KICAD" = "1" ]; then apt-get install -y --no-install-recommends kicad libcairo2; else apt-get install -y --no-install-recommends libcairo2; fi \
    && rm -rf /var/lib/apt/lists/*

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
COPY --from=frontend-build /frontend/dist/ ./frontend/dist/
# data/는 서비스가 읽는 데이터(코퍼스·회로·데모)다. evals/·tests/·scripts/는 서비스에 필요 없어 넣지 않는다.
COPY data/ ./data/
COPY db/ ./db/

# [왜] 서버는 파일을 쓰지 않는다. root 대신 전용 계정으로 돌려 컨테이너가 뚫려도 이미지 안을 못 바꾸게 한다(D7 2-3절)
RUN useradd --create-home --shell /usr/sbin/nologin sojafit
USER sojafit

EXPOSE 8000
# 0.0.0.0: 컨테이너 밖(compose의 포트 연결)에서 접속하려면 모든 인터페이스에 열어야 한다.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
