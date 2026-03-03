# ── Stage 1: Build frontend ──────────────────────────────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ── Stage 2: Python runtime ─────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Pin the venv to the absolute Python path so symlinks survive at runtime
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --python /usr/local/bin/python3

# Install spacy model directly into the venv
RUN uv pip install --python .venv/bin/python \
    en-core-web-sm@https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

# Copy app code + built frontend
COPY backend/ ./
COPY --from=frontend-build /app/backend/static ./static

# Tell uv where the venv lives so `uv run` never recreates it
ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV PIXELTABLE_HOME=/data/pixeltable

RUN addgroup --system --gid 1000 appgroup && \
    adduser --system --uid 1000 --ingroup appgroup appuser && \
    mkdir -p /data/pixeltable && chown -R appuser:appgroup /data/pixeltable

USER appuser
EXPOSE 8000

CMD ["sh", "-c", "uv run python setup_pixeltable.py && uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4"]
