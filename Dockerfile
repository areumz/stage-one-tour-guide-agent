# Cloud Run 용 이미지. 인메모리 세션·한도 카운터를 쓰므로 인스턴스는 1대로 둔다 (docs/deploy.md)
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src:/app

WORKDIR /app

# 의존성만 먼저 설치해 레이어 캐시를 쓴다. 프로젝트 자체는 PYTHONPATH 로 읽으므로 설치하지 않는다
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY contracts ./contracts

RUN useradd --system --uid 10001 app
USER app

# Cloud Run 이 PORT 를 넣어 준다 (기본 8080)
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn --factory tour_guide.main:build_app --host 0.0.0.0 --port ${PORT:-8080}"]
