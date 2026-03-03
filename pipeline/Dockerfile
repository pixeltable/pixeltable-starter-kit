FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --python /usr/local/bin/python3
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

COPY pipeline.py udfs.py ./

RUN addgroup --system --gid 1000 appgroup && \
    adduser --system --uid 1000 --ingroup appgroup appuser && \
    mkdir -p /tmp/pixeltable && chown -R appuser:appgroup /tmp/pixeltable

USER appuser
ENV PIXELTABLE_HOME=/tmp/pixeltable

ENTRYPOINT ["uv", "run", "python", "pipeline.py"]
