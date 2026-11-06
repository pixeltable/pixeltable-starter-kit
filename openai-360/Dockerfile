FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock pixeltable.toml ./
RUN uv sync --frozen --no-dev --no-install-project --python /usr/local/bin/python3
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

COPY app.py seed.py ./
RUN uv sync --frozen --no-dev --python /usr/local/bin/python3

RUN addgroup --system --gid 1000 appgroup && \
    adduser --system --uid 1000 --ingroup appgroup appuser && \
    mkdir -p /data/pixeltable && chown -R appuser:appgroup /data/pixeltable

USER appuser
ENV PIXELTABLE_HOME=/data/pixeltable

EXPOSE 8000
# `service run` rather than `service update`: a container entrypoint has to stay in the
# foreground. `service update` backgrounds the service and returns, which would exit the
# container. Outside a container, use `pxt service update`.
CMD ["sh", "-c", "uv run pxt schema update app.py claims -f && uv run pxt service run app.py claims --host 0.0.0.0 --port 8000"]
