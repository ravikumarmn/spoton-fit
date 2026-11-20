# SpotOn API image (Technical PRD section 12). Multi-stage, uv-based, non-root.
#   docker build -t spotonfit .
#   docker run --env-file .env -p 8080:8080 spotonfit
# Migrations are applied by the deploy pipeline (python -m spotonfit.migrations), not at startup.

FROM python:3.15.2-slim AS builder
# A C compiler for dependencies without Python 3.15 wheels yet (e.g. zstandard via langsmith).
# Build stage only; the runtime image below stays slim.
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# Dependencies first (cached layer), then the project itself.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.15.2-slim
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
# The Flutter web build (the deploy pipeline fills webapp/ before docker build); served at "/".
COPY --chown=app:app webapp ./webapp
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=prod \
    AUTO_MIGRATE=false \
    PORT=8080 \
    WEB_CONCURRENCY=1
USER app
EXPOSE 8080
# --proxy-headers: trust X-Forwarded-For from Cloud Run's front end (client IPs for rate limits).
# One process by default: rate limits are counted in memory, so more processes (or instances)
# would each allow the full limit. The async app handles many requests in one process.
CMD ["sh", "-c", "uvicorn spotonfit.api.main:app --host 0.0.0.0 --port ${PORT} --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips='*'"]
