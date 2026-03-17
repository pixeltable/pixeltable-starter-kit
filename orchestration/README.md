# Pixeltable Ephemeral Orchestration

Use Pixeltable as an **ephemeral processing engine**: spin up a container, ingest text and media, let computed columns do the work, export structured results to a serving database via [`export_sql`](https://docs.pixeltable.com/howto/cookbooks/data/data-export-sql), and route generated media (thumbnails, audio, etc.) directly to a cloud bucket via the [`destination`](https://docs.pixeltable.com/sdk/v0.5.9/table) parameter. No persistent infrastructure — the container shuts down when done.

This is the complement to the [starter kit](../README.md) (long-running server). Here Pixeltable is an ephemeral processing engine — it processes data and hands off to your existing serving layer.

```
SQS / Cron / Webhook
        │
        ▼
  Ephemeral Container
  ┌──────────────────────────────────────────────────────┐
  │  1. Create schema (idempotent)                       │
  │  2. Insert text + media from queue/RDBMS/S3          │
  │  3. Computed columns process everything              │
  │  4. export_sql → structured data to serving DB       │
  │  5. destination → generated media to cloud bucket    │
  │  6. Container exits                                  │
  └──────────────────────────────────────────────────────┘
```

## Quick Start

```bash
cd orchestration
uv sync
PIXELTABLE_HOME=/tmp/pxt uv run python pipeline.py
```

Output:

```
Inserting documents...
Inserted 5 rows with 0 errors in 0.01 s
Inserting images (downloading + generating thumbnails)...
  Thumbnails stored locally (set MEDIA_DEST for cloud bucket)
Inserted 2 rows with 0 errors in 0.26 s

Serving DB — processed_documents (5 rows):
  doc-001  Introduction to Pixeltable           words=43
  doc-002  Computed Columns                     words=41
  ...
Serving DB — processed_images (2 rows):
  img-001  cat              481x640
  img-002  scene            640x429

Pipeline completed in 1.0s
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

**Text processing:**

```python
t.add_computed_column(word_count=word_count(t.body), if_exists="ignore")
t.add_computed_column(char_count=char_count(t.body), if_exists="ignore")
t.add_computed_column(preview=preview(t.body), if_exists="ignore")
```

**Image processing — metadata + media generation:**

```python
t.add_computed_column(width=t.image.width, if_exists="ignore")
t.add_computed_column(height=t.image.height, if_exists="ignore")
t.add_computed_column(
    thumb=thumbnail(t.image),
    destination="s3://your-bucket/thumbs/",  # generated media → bucket
    if_exists="ignore",
)
```

Insert triggers all computations automatically — no orchestrator needed. Structured data (word counts, dimensions) stays in Pixeltable for `export_sql`. Generated media (thumbnails) goes directly to your bucket via `destination`.

### 3. Export structured data via `export_sql`

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

### 4. Two output paths

| Output type | Method | Where it goes |
|---|---|---|
| **Structured data** (text, numbers, JSON) | `export_sql` | Serving RDBMS (Postgres, MySQL, Snowflake, etc.) |
| **Generated media** (thumbnails, audio, etc.) | `destination` parameter | Cloud bucket (S3, GCS, Azure Blob) |

The `destination` parameter on `add_computed_column` is the key for media. When set, Pixeltable writes generated files directly to the bucket — the ephemeral container doesn't need any persistent storage. Set it globally via `MEDIA_DEST` or per-column:

```python
# Global: all generated media goes here
PIXELTABLE_OUTPUT_MEDIA_DEST=s3://your-bucket/output

# Per-column: override for specific outputs
t.add_computed_column(
    audio=extract_audio(t.video, format="mp3"),
    destination="s3://your-bucket/audio/",
)
```

Without `destination` or `PIXELTABLE_OUTPUT_MEDIA_DEST`, media is stored locally (fine for local testing).

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PIXELTABLE_HOME` | `~/.pixeltable` | Set to `/tmp/pixeltable` for ephemeral |
| `SERVING_DB_URL` | `sqlite:///serving.db` | SQLAlchemy connection string for export target |
| `OPENAI_API_KEY` | — | Enables LLM summary column |
| `MEDIA_DEST` | — | Cloud URI for generated media (e.g. `s3://bucket/out`). Passed as `destination` on media-generating computed columns. Also settable globally via `PIXELTABLE_OUTPUT_MEDIA_DEST`. |

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
orchestration/
├── pipeline.py          Batch processing script
├── udfs.py              Pixeltable UDFs (word_count, char_count, preview, thumbnail)
├── sample_batch.json    Example JSON input
├── pyproject.toml       Dependencies
├── uv.lock              Locked dependencies
├── Dockerfile           Ephemeral container (PIXELTABLE_HOME=/tmp)
└── docker-compose.yml   Local testing
```
