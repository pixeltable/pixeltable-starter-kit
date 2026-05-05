# AGENTS.md

Instructions for AI coding agents working with the Pixeltable Starter Kit.

## Pixeltable Resources

Before modifying this codebase, familiarize yourself with Pixeltable:

- **Core AGENTS.md** — [pixeltable/pixeltable/AGENTS.md](https://github.com/pixeltable/pixeltable/blob/main/AGENTS.md) covers the full SDK: tables, computed columns, views, iterators, UDFs, embedding indexes, and all AI provider integrations.
- **Claude Code Skill** — [pixeltable/pixeltable-skill](https://github.com/pixeltable/pixeltable-skill) gives Claude deep Pixeltable expertise via progressive disclosure (`SKILL.md` → `API_REFERENCE.md`).
- **MCP Server** — [pixeltable/mcp-server-pixeltable-developer](https://github.com/pixeltable/mcp-server-pixeltable-developer) exposes Pixeltable as an MCP server for interactive exploration (tables, queries, Python REPL).
- **Docs** — [docs.pixeltable.com](https://docs.pixeltable.com/) · [SDK Reference](https://docs.pixeltable.com/sdk/latest/pixeltable)

## What This Template Is

A production-ready starter kit demonstrating how to put Pixeltable in production with FastAPI + Pydantic + TypeScript. Three tabs show three interaction patterns:

| Tab | Pattern | Key Pixeltable Features |
|-----|---------|------------------------|
| **Data** | Upload → automatic processing | `create_table`, `create_view` with iterators, `add_computed_column` |
| **Search** | Cross-modal similarity queries | `add_embedding_index`, `.similarity()`, CLIP + sentence-transformers |
| **Agent** | Insert-triggers-pipeline | `pxt.tools`, `invoke_tools`, chained computed columns, `@pxt.query` |

## Project Structure

```
backend/
├── main.py                 FastAPI app (lifespan, CORS, routers, SPA fallback)
├── config.py               Environment-driven settings (models, prompts, CORS)
├── models.py               Pydantic models: row schemas + all API responses
├── functions.py             @pxt.udf definitions (web search, context assembly)
├── setup_pixeltable.py      Declarative schema: tables, views, indexes, @pxt.query, agent pipeline
├── pxt_serve.py             Pixeltable FastAPIRouter (v0.6+): declarative /api/pxt routes
├── pyproject.toml           Dependencies managed via uv
└── routers/
    ├── data.py              Upload, list, delete, chunks, frames, transcription
    ├── search.py            Cross-modal similarity search
    └── agent.py             Tool-calling agent + conversation CRUD

frontend/src/
├── App.tsx                  Tab navigation (Data / Search / Agent)
├── components/              Page components + shared UI (Button, Badge)
├── lib/api.ts               Typed fetch wrapper mirroring backend response models
└── types/index.ts           TypeScript interfaces matching Pydantic models

orchestration/                   Ephemeral orchestration deployment pattern
├── pipeline.py                  Batch processing (ingest → compute → export_sql)
├── udfs.py                      Pixeltable UDFs
├── Dockerfile                   Ephemeral container
└── docker-compose.yml           Local testing

deploy/
├── helm/                    Helm chart (any existing K8s cluster)
├── terraform-k8s/           Terraform + AWS EKS
├── terraform-gke/           Terraform + GCP GKE
├── terraform-aks/           Terraform + Azure AKS
└── aws-cdk/                 CDK + ECS Fargate
```

## Setup

```bash
git clone https://github.com/pixeltable/pixeltable-starter-kit.git
cd pixeltable-starter-kit
cp .env.example .env          # add ANTHROPIC_API_KEY and OPENAI_API_KEY

cd backend
uv sync                       # creates .venv, installs deps including en_core_web_sm
source .venv/bin/activate
python setup_pixeltable.py    # initialize schema (idempotent; set RESET_SCHEMA=true to wipe)
python main.py                # http://localhost:8000

# Frontend (separate terminal)
cd frontend
npm install && npm run dev    # http://localhost:5173
```

Production: `cd frontend && npm run build` then `python main.py` — serves everything at `:8000`.

## Architectural Decisions

Each decision below is intentional. Don't change it without understanding why.

### Pixeltable IS the data layer

There is no ORM, no SQLAlchemy, no direct PostgreSQL client. Pixeltable handles storage, indexing, transformation, and retrieval. The `setup_pixeltable.py` file defines the entire data model declaratively — tables, views, computed columns, embedding indexes, `@pxt.query` functions, and the agent pipeline — in a single `setup()` function.

### Sync endpoints (`def`, not `async def`)

All FastAPI endpoints use `def`, not `async def`. Pixeltable operations are synchronous and thread-safe. Uvicorn runs sync endpoints in a thread pool automatically, which is the correct pattern. Using `async def` would block the event loop.

### No explicit event loop configuration

`uvicorn.run()` is called without `loop="asyncio"`. This lets Uvicorn auto-detect `uvloop` when available, which is faster.

### Schema-as-code

`setup_pixeltable.py` exposes a `setup()` function that creates (or reconnects to) the full schema. It is called automatically on server startup via `main.py`'s lifespan hook, and is also safe to run standalone (`python setup_pixeltable.py`). Every `create_dir`, `create_table`, `create_view`, `add_computed_column`, and `add_embedding_index` call uses `if_exists="ignore"` (with explicit `idx_name` to avoid a Pixeltable 0.6.0 idempotency issue), so repeated calls never destroy data. To wipe and recreate the namespace from scratch, set `RESET_SCHEMA=true`, which calls `drop_dir` first. The `@pxt.query` functions are defined inside `setup()` after their tables exist (required because `@pxt.query` eagerly evaluates the function body in 0.6+) and exported as module-level attributes for use by `pxt_serve.py` and the agent pipeline. The schema defines:

1. **Document pipeline** — table → `DocumentSplitter` view → sentence-transformer embedding index
2. **Image pipeline** — table → thumbnail computed column → CLIP embedding index
3. **Video pipeline** — table → `FrameIterator` view (keyframes + CLIP) → audio extraction → Whisper transcription → `StringSplitter` view → embedding index
4. **Chat history** — table with embedding index for memory retrieval
5. **Agent pipeline** — 8-step chain (11 computed columns): initial LLM call with tools → tool execution → context retrieval (RAG across all media) → history injection → context assembly → final LLM call → answer extraction

### Dual-router architecture (v0.6+)

The app mounts two router layers side-by-side:

| Layer | Prefix | Role |
|-------|--------|------|
| **Facade routers** | `/api/data`, `/api/search`, `/api/agent` | SPA-facing endpoints with Pydantic DTOs, merged search, chat history management. These are what `frontend/src/lib/api.ts` calls. |
| **Pixeltable FastAPIRouter** | `/api/pxt` | Declarative routes auto-generated from tables and `@pxt.query` functions. Useful for scripts, admin, direct API access, and showing what Pixeltable's serving layer can do. |

Both hit the same Pixeltable tables and indexes. The SPA frontend only uses the facade routes — the `/api/pxt` routes are an optional companion for direct Pixeltable access. See `pxt_serve.py` for the implementation and `docs/MIGRATION_PXTFASTAPIROUTER.md` for the architecture rationale.

Routes that **must** stay as facades (app-level orchestration the router can't express): `POST /api/search` (4-way fan-in), `GET /api/data/files` (3-table aggregation), `GET/POST /api/agent/conversations` (group-by conversation_id).

### Pydantic everywhere

`models.py` contains both **row schemas** (for `table.insert()`) and **API response models** (for `response_model=`). Every endpoint declares its response model so `/docs` is self-documenting. Where Pixeltable query results match model fields directly, `ResultSet.to_pydantic()` converts them.

### `@pxt.udf` and `@pxt.query` for logic

Business logic lives in Pixeltable functions, not endpoint handlers. `@pxt.udf` (in `functions.py`) for custom transforms like web search and context assembly. `@pxt.query` (defined inside `setup_pixeltable.setup()`, exported as module attributes) for reusable similarity searches. Facade routers are thin — they insert rows, collect results, and return responses. The Pixeltable FastAPIRouter in `pxt_serve.py` exposes the same `@pxt.query` functions as declarative HTTP endpoints.

### Agent pipeline as computed columns

The entire tool-calling agent is a chain of `add_computed_column()` calls on the `agent` table. Inserting a row triggers the full pipeline: tool planning → execution → multimodal RAG → context assembly → final answer. The router just inserts and reads back.

### Typed frontend

TypeScript interfaces in `types/index.ts` mirror the backend Pydantic models. `lib/api.ts` is a generic typed fetch wrapper — no code generation, no heavy HTTP client. Intentionally simple for a template.

### Containerized deployment

A multi-stage `Dockerfile` builds the frontend and Python runtime into a single image. `docker-compose.yml` runs it locally with named volumes for Pixeltable data. Deployment options live in `deploy/`:

- **`deploy/helm/`** — Helm chart for deploying on **any existing K8s cluster**. Creates Secret, PVC, schema init Job (Helm hook), Deployment with health checks, and LoadBalancer Service. No infra provisioning — just `helm install`.
- **`deploy/terraform-k8s/`** — Provisions full AWS stack from scratch: VPC, EKS cluster, ECR, plus K8s resources. Pixeltable data on 50Gi EBS.
- **`deploy/terraform-gke/`** — Same pattern for GCP: VPC, GKE cluster, Artifact Registry. 50Gi Persistent Disk.
- **`deploy/terraform-aks/`** — Same pattern for Azure: Resource Group, AKS cluster, ACR. 50Gi Managed Disk.
- **`deploy/aws-cdk/`** — ECS Fargate behind ALB with EFS for persistent storage. Auto-scales 1–4 tasks.

All configure `PIXELTABLE_HOME=/data/pixeltable` pointing to persistent storage. For large media workloads, set `PIXELTABLE_INPUT_MEDIA_DEST` and `PIXELTABLE_OUTPUT_MEDIA_DEST` to S3/GCS/Azure Blob URIs (see [Pixeltable Configuration](https://docs.pixeltable.com/platform/configuration.md)).

### SPA fallback

`npm run build` outputs to `backend/static/`. FastAPI's catch-all `/{full_path:path}` serves the built frontend. One process, one port in production. In development, Vite's proxy forwards `/api` to the backend.

### `pyproject.toml` + `uv`

Modern Python packaging. `uv sync` creates the venv and installs deps in one command. No `requirements.txt`.

## Key Patterns to Follow

When extending this template:

**Adding a new data type:**
1. Add a table in `setup_pixeltable.py` with `pxt.create_table()`
2. Add views/iterators for processing (`create_view` + iterator)
3. Add embedding indexes for search (`add_embedding_index`)
4. Add a `@pxt.query` function for similarity search
5. Add Pydantic response models in `models.py`
6. Add router endpoints with `response_model=`

**Adding a computed column:**
```python
table.add_computed_column(
    new_col=some_function(table.existing_col),
    if_exists="ignore",
)
```

**Querying with `to_pydantic()`:**
```python
result = table.select(col_a=table.a, col_b=table.b).collect()
items = list(result.to_pydantic(MyPydanticModel))
```

**Adding a tool to the agent:**
1. Define the function with `@pxt.udf` or `@pxt.query`
2. Add it to the `pxt.tools()` call in `setup_pixeltable.py`
3. Re-run `python setup_pixeltable.py`

## Files to Read First

If you're new to this codebase, read in this order:

1. `setup_pixeltable.py` — the core. Defines the entire data model, `@pxt.query` functions, and agent pipeline.
2. `pxt_serve.py` — Pixeltable's `FastAPIRouter` integration (v0.6+). Shows how to expose tables and queries as declarative HTTP endpoints.
3. `models.py` — all Pydantic models (row schemas + API responses).
4. `routers/agent.py` — shows the insert-triggers-pipeline pattern (facade).
5. `routers/data.py` — shows CRUD + `to_pydantic()` conversion (facade).
6. `functions.py` — `@pxt.udf` definitions used by the agent.
7. `frontend/src/lib/api.ts` + `types/index.ts` — how the frontend talks to the backend.
