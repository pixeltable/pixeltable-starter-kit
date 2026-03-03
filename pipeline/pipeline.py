"""Pixeltable as an orchestration layer — ephemeral batch pipeline.

Ingests data from a source (JSON file, RDBMS, or queue), processes it
through Pixeltable computed columns, and exports structured results to a
serving database via ``export_sql``.

Media outputs (thumbnails, audio, etc.) land directly in a cloud bucket
when ``destination`` is set on computed columns.

Usage:
    python pipeline.py                              # process sample data
    python pipeline.py --input batch.json           # process a JSON batch
    python pipeline.py --input-db 'postgresql://…'  # pull from source RDBMS

Environment:
    SERVING_DB_URL   SQLAlchemy connection string for the serving DB
                     (default: sqlite:///serving.db)
    OPENAI_API_KEY   Required for embedding / summarisation columns
    MEDIA_DEST       Cloud URI for generated media (e.g. s3://bucket/out)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pixeltable as pxt
from pixeltable.io.sql import export_sql

from udfs import char_count, preview, word_count

SERVING_DB_URL = os.getenv("SERVING_DB_URL", "sqlite:///serving.db")
MEDIA_DEST = os.getenv("MEDIA_DEST")  # e.g. s3://bucket/output


# ── Schema ──────────────────────────────────────────────────────────────────

def setup_schema() -> pxt.Table:
    """Create (or reuse) the Pixeltable schema. Fully idempotent."""
    pxt.create_dir("pipeline", if_exists="ignore")

    t = pxt.create_table(
        "pipeline.documents",
        {"title": pxt.String, "body": pxt.String, "source_id": pxt.String},
        if_exists="ignore",
    )

    t.add_computed_column(word_count=word_count(t.body), if_exists="ignore")
    t.add_computed_column(char_count=char_count(t.body), if_exists="ignore")
    t.add_computed_column(preview=preview(t.body), if_exists="ignore")

    # Optional: if OPENAI_API_KEY is set, add an LLM summary column
    if os.getenv("OPENAI_API_KEY"):
        try:
            from pixeltable.functions.openai import chat_completions

            messages = [{"role": "user", "content": "Summarize in one sentence: " + t.body}]
            t.add_computed_column(
                summary=chat_completions(
                    messages=messages,
                    model="gpt-4o-mini",
                ).choices[0].message.content,
                if_exists="ignore",
            )
        except Exception as exc:
            print(f"Skipping summary column: {exc}")

    return t


# ── Data loading ────────────────────────────────────────────────────────────

SAMPLE_DATA = [
    {
        "title": "Introduction to Pixeltable",
        "body": (
            "Pixeltable is data infrastructure for AI that replaces the "
            "patchwork of storage, ETL, vector databases, feature stores, "
            "and orchestration frameworks with a single declarative system. "
            "Tables, computed columns, and embedding indexes handle what "
            "typically requires stitching together S3, Postgres, Pinecone, "
            "Airflow, and LangChain."
        ),
        "source_id": "doc-001",
    },
    {
        "title": "Computed Columns",
        "body": (
            "Computed columns in Pixeltable are declarative transformations "
            "that update incrementally. When you insert new rows, only the "
            "new data flows through the computation graph. This eliminates "
            "the need for manual orchestration, retry logic, and dependency "
            "tracking that plague traditional ML pipelines."
        ),
        "source_id": "doc-002",
    },
    {
        "title": "Export to SQL",
        "body": (
            "Pixeltable's export_sql function sends processed data to any "
            "SQL database — PostgreSQL, MySQL, SQLite, Snowflake, or "
            "TigerData. Type mapping is automatic. This lets you use "
            "Pixeltable as a processing engine while keeping your existing "
            "serving infrastructure."
        ),
        "source_id": "doc-003",
    },
    {
        "title": "Media Processing",
        "body": (
            "Pixeltable handles video, audio, images, and documents "
            "natively. Iterators extract frames, split audio, and chunk "
            "documents. Computed columns can run transcription, OCR, object "
            "detection, or any custom UDF. The destination parameter on "
            "add_computed_column routes generated media directly to cloud "
            "storage buckets."
        ),
        "source_id": "doc-004",
    },
    {
        "title": "Ephemeral Deployment",
        "body": (
            "For batch workloads, Pixeltable can run in an ephemeral "
            "container. Schema setup is idempotent and takes seconds. "
            "Data is ingested, processed through computed columns, and "
            "exported to a serving database. The container then exits. "
            "This pattern works with ECS Fargate Spot, Kubernetes Jobs, "
            "or AWS Batch for cost-efficient processing."
        ),
        "source_id": "doc-005",
    },
]


def load_from_json(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def load_from_db(db_url: str) -> list[dict]:
    import sqlalchemy as sa

    engine = sa.create_engine(db_url)
    with engine.connect() as conn:
        rows = conn.execute(sa.text("SELECT title, body, source_id FROM documents"))
        return [dict(r._mapping) for r in rows]


# ── Export ──────────────────────────────────────────────────────────────────

def export_results(t: pxt.Table) -> None:
    """Export processed data to the serving database via export_sql."""
    query = t.select(
        t.source_id,
        t.title,
        t.preview,
        t.word_count,
        t.char_count,
    )

    export_sql(
        query,
        "processed_documents",
        db_connect_str=SERVING_DB_URL,
        if_exists="replace",
    )

    print(f"Exported to {SERVING_DB_URL} -> table 'processed_documents'")


def verify_export() -> None:
    """Quick sanity check: read back from the serving DB."""
    import sqlalchemy as sa

    engine = sa.create_engine(SERVING_DB_URL)
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text("SELECT source_id, title, word_count FROM processed_documents")
        ).fetchall()

    print(f"\nServing DB has {len(rows)} rows:")
    for r in rows:
        print(f"  {r[0]}  {r[1]:<35s}  words={r[2]}")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pixeltable batch pipeline")
    parser.add_argument("--input", help="JSON file with documents to process")
    parser.add_argument("--input-db", help="SQLAlchemy URL to pull documents from")
    args = parser.parse_args()

    t0 = time.time()

    # 1. Schema
    print("Setting up schema...")
    table = setup_schema()

    # 2. Load data
    if args.input:
        data = load_from_json(args.input)
        print(f"Loaded {len(data)} documents from {args.input}")
    elif args.input_db:
        data = load_from_db(args.input_db)
        print(f"Loaded {len(data)} documents from source DB")
    else:
        data = SAMPLE_DATA
        print(f"Using {len(data)} sample documents")

    # 3. Insert (computed columns fire automatically)
    print("Inserting and processing...")
    table.insert(data)

    # 4. Export to serving DB
    print("Exporting results...")
    export_results(table)
    verify_export()

    elapsed = time.time() - t0
    print(f"\nPipeline completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
