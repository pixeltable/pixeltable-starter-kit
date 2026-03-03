# Pixeltable Orchestration Pipeline

Use Pixeltable as an **ephemeral processing engine**: spin up a container, ingest data, let computed columns do the work, export results to a serving database, and shut down. No persistent infrastructure to maintain.

This is the complement to the [starter kit](../README.md) (long-running server). Here Pixeltable is a batch pipeline — it processes data and hands off to your existing serving layer.

```
SQS / Cron / Webhook
        │
        ▼
  Ephemeral Container
  ┌─────────────────────────────────────┐
  │  1. Create schema (idempotent)      │
  │  2. Insert batch from queue/RDBMS   │
  │  3. Computed columns process data   │
  │  4. export_sql → serving database   │
  │  5. Container exits                 │
  └─────────────────────────────────────┘
```

## Quick Start

```bash
cd pipeline
uv sync
PIXELTABLE_HOME=/tmp/pxt uv run python pipeline.py
```

Output:

```
Inserted 5 rows with 0 errors in 0.01 s (425 rows/s)
Exported to sqlite:///serving.db -> table 'processed_documents'

Serving DB has 5 rows:
  doc-001  Introduction to Pixeltable           words=43
  doc-002  Computed Columns                     words=41
  ...
Pipeline completed in 0.6s
```

### Docker

```bash
docker compose up --build    # runs pipeline, exports to volume, exits
```

### Custom input

```bash
# From a JSON file
uv run python pipeline.py --input batch.json

# From a source database
uv run python pipeline.py --input-db 'postgresql://user:pass@host/db'
```

## How It Works

### 1. Schema setup (idempotent)

Every run calls `create_table` / `add_computed_column` with `if_exists='ignore'`. On an ephemeral container (`PIXELTABLE_HOME=/tmp/...`), this creates everything fresh. On a persistent volume, it reuses existing schema.

### 2. Computed columns as pipeline stages

```python
t.add_computed_column(word_count=word_count(t.body), if_exists="ignore")
t.add_computed_column(char_count=char_count(t.body), if_exists="ignore")
t.add_computed_column(preview=preview(t.body), if_exists="ignore")
```

Insert triggers all computations automatically — no orchestrator needed.

### 3. Export via `export_sql`

```python
from pixeltable.io.sql import export_sql

export_sql(
    table.select(table.source_id, table.title, table.word_count),
    "processed_documents",
    db_connect_str="postgresql://user:pass@serving-host/db",
    if_exists="replace",  # or "insert" to append
)
```

Supports PostgreSQL, MySQL, SQLite, Snowflake, and TigerData. See [Export to SQL databases](https://docs.pixeltable.com/howto/cookbooks/data/data-export-sql).

### 4. Media output via `destination`

For pipelines that generate media (thumbnails, audio, etc.), the `destination` parameter on `add_computed_column` routes outputs directly to a cloud bucket:

```python
t.add_computed_column(
    audio=extract_audio(t.video, format="mp3"),
    destination="s3://your-bucket/audio/",
    if_exists="ignore",
)
```

The container doesn't need to persist anything — generated files land in your bucket automatically.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PIXELTABLE_HOME` | `~/.pixeltable` | Set to `/tmp/pixeltable` for ephemeral |
| `SERVING_DB_URL` | `sqlite:///serving.db` | SQLAlchemy connection string for export target |
| `OPENAI_API_KEY` | — | Enables LLM summary column |
| `MEDIA_DEST` | — | Cloud URI for generated media (e.g. `s3://bucket/out`) |

## Production Deployment

### ECS Fargate Spot + SQS (cheapest)

```
SQS Queue → EventBridge Rule → ECS Fargate Spot Task
```

- Pay only when processing (~70% cheaper with Spot)
- Scale to zero when idle
- Pass batch payload via environment variable or S3 pointer

### Kubernetes Job + KEDA

```
Queue (SQS/Redis) → KEDA ScaledJob → K8s Job (Spot nodes)
```

- Auto-scales Job count based on queue depth
- Node auto-scaler provisions/deprovisions spot instances
- Scale to zero when queue is empty

### AWS Batch

- Submit jobs to a managed queue
- Auto-provisions optimal instance types
- Native Spot support with automatic retries

## Files

```
pipeline/
├── pipeline.py          Main processing script
├── udfs.py              Pixeltable UDFs (word_count, char_count, preview)
├── sample_batch.json    Example JSON input
├── pyproject.toml       Dependencies
├── uv.lock              Locked dependencies
├── Dockerfile           Ephemeral container (PIXELTABLE_HOME=/tmp)
└── docker-compose.yml   Local testing
```
