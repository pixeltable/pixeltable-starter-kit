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

# Install Python deps (cached layer)
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# Install spacy model (uv doesn't provide pip, so use uv pip directly)
RUN uv pip install --python .venv/bin/python \
    en-core-web-sm@https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl

# Copy app code + built frontend
COPY backend/ ./
COPY --from=frontend-build /app/backend/static ./static

# Pixeltable data lives here — mount a volume in production
ENV PIXELTABLE_HOME=/data/pixeltable

EXPOSE 8000

# Schema init + server start.
# In production, run setup_pixeltable.py once (or as an init container),
# then start the server.
CMD ["sh", "-c", "uv run python setup_pixeltable.py && uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4"]
