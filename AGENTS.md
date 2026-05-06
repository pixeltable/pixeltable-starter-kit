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
├── main.py                 FastAPI app (CORS, routers, SPA fallback)
├── config.py               Environment-driven settings (models, prompts, CORS)
├── models.py               Pydantic models (agent endpoint only: row schemas + query request/response)
├── functions.py             @pxt.udf definitions (web search, context assembly)
├── setup_pixeltable.py      Declarative schema: tables, views, indexes, @pxt.query, agent pipeline
├── pyproject.toml           Dependencies managed via uv
└── routers/
    ├── data.py              100% declarative FastAPIRouter (upload w/ background jobs, list, delete, detail queries)
    ├── search.py            100% declarative FastAPIRouter (4 similarity search endpoints)
    └── agent.py             FastAPIRouter (3 declarative + 1 hand-written agent query)

frontend/src/
├── App.tsx                  Tab navigation (Data / Search / Agent)
├── components/              Page components + shared UI (Button, Badge)
├── lib/api.ts               Typed fetch wrapper + client-side aggregation/fan-in
└── types/index.ts           TypeScript interfaces (PxtQueryResponse<T> + app-specific types)

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

Production: `cd frontend && npm run build` then `cd ../backend && python main.py` — serves everything at `:8000`.

## Architectural Decisions

Each decision below is intentional. Don't change it without understanding why.

### Pixeltable IS the data layer

There is no ORM, no SQLAlchemy, no direct PostgreSQL client. Pixeltable handles storage, indexing, transformation, and retrieval. The `setup_pixeltable.py` file defines the entire data model declaratively — tables, views, computed columns, embedding indexes, `@pxt.query` functions, and the agent pipeline.

### Sync endpoints (`def`, not `async def`)

All FastAPI endpoints use `def`, not `async def`. Pixeltable operations are synchronous and thread-safe. Uvicorn runs sync endpoints in a thread pool automatically, which is the correct pattern. Using `async def` would block the event loop.

### No explicit event loop configuration

`uvicorn.run()` is called without `loop="asyncio"`. This lets Uvicorn auto-detect `uvloop` when available, which is faster.

### Schema-as-code

`setup_pixeltable.py` has two sections. The `setup()` function creates (or reconnects to) tables, views, indexes, and the agent pipeline — it runs automatically on module import (guarded by `_initialized`), so schema is ready whenever any code imports `setup_pixeltable`. After `setup()`, twelve `@pxt.query` functions are defined at module level (router-facing queries for listing, detail, search, and chat). This two-phase pattern exists because `@pxt.query` eagerly evaluates the function body in 0.6+, so tables must exist first. Agent-internal queries (used only by computed columns) stay inside `setup()`. Every schema call uses `if_exists="ignore"` (with explicit `idx_name`), so repeated imports never destroy data. Set `RESET_SCHEMA=true` to wipe and recreate. The schema defines:

1. **Document pipeline** — table → `DocumentSplitter` view → sentence-transformer embedding index
2. **Image pipeline** — table → thumbnail computed column → CLIP embedding index
3. **Video pipeline** — table → `FrameIterator` view (keyframes + CLIP) → audio extraction → Whisper transcription → `StringSplitter` view → embedding index
4. **Chat history** — table with embedding index for memory retrieval
5. **Agent pipeline** — 8-step chain (11 computed columns): initial LLM call with tools → tool execution → context retrieval (RAG across all media) → history injection → context assembly → final LLM call → answer extraction

### Integrated `FastAPIRouter` (v0.6+)

All three routers use Pixeltable's `FastAPIRouter` (a subclass of FastAPI's `APIRouter`). Routes are registered at module level — `import setup_pixeltable` triggers schema init, then `add_insert_route` / `add_query_route` / `add_delete_route` calls register endpoints directly. Only **1 of 20 endpoints** is hand-written:

**`data.py`** — 100% declarative (12 routes):

| Route | Method | Notes |
|-------|--------|-------|
| `/api/data/upload/{document,video}` | `add_insert_route` | `background=True` — returns job handle, client polls `/jobs/{id}` |
| `/api/data/upload/image` | `add_insert_route` | Synchronous (thumbnail + CLIP is fast) |
| `/api/data/delete/{document,image,video}` | `add_delete_route` | Match by primary key (uuid) |
| `/api/data/chunks`, `/frames`, `/transcription` | `add_query_route` (POST) | Detail queries accepting `file_uuid` |
| `/api/data/list/{documents,images,videos}` | `add_query_route` (GET) | Per-table listing |

**`search.py`** — 100% declarative (4 routes):

| Route | Method | Notes |
|-------|--------|-------|
| `/api/search/{documents,images,video-frames,transcripts}` | `add_query_route` (POST) | One per embedding index, accepts `query_text` |

**`agent.py`** — 3 declarative + 1 hand-written:

| Route | Method | Notes |
|-------|--------|-------|
| `/api/agent/conversation` | `add_query_route` (POST) | Messages for a `conversation_id` |
| `/api/agent/messages` | `add_query_route` (GET) | All messages (frontend groups client-side) |
| `/api/agent/delete-conversation` | `add_delete_route` | `match_columns=["conversation_id"]` |
| `/api/agent/query` | **Hand-written** `@router.post` | Multi-table side effects (agent + 2× chat_history) |

The frontend (`api.ts`) handles aggregation that was previously done server-side: parallel fetches to granular endpoints, client-side merge/sort/group-by, and deduplication.

### Minimal Pydantic models

`models.py` contains only the models needed by the single hand-written endpoint (`POST /api/agent/query`): `ToolAgentRow` and `ChatHistoryRow` (row schemas for `table.insert()`) and `QueryRequest`/`QueryResponse` (API contract). All other endpoints are declarative — `FastAPIRouter` auto-generates request/response schemas from table columns and `@pxt.query` return types. Query endpoints return `{ "rows": [...] }` automatically.

### `@pxt.udf` and `@pxt.query` for logic

Business logic lives in Pixeltable functions, not endpoint handlers. `@pxt.udf` (in `functions.py`) for custom transforms like web search and context assembly. `@pxt.query` (defined at module level in `setup_pixeltable.py`, after `setup()` creates the tables) for all read endpoints — listing, detail queries, similarity search. Each `@pxt.query` maps 1:1 to an `add_query_route` call in the router file. The only hand-written endpoint (`POST /api/agent/query`) exists because it performs multi-table inserts with conditional logic that can't be expressed declaratively.

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
3. Add embedding indexes for search (`add_embedding_index` with explicit `idx_name`)
4. Add `@pxt.query` functions for listing and similarity search (inside `setup()`, export as module attrs)
5. Register routes at module level in the router file:
   - `add_insert_route` for uploads (`uploadfile_inputs` for media)
   - `add_delete_route` for deletion
   - `add_query_route` for listing and search
6. Update the frontend `api.ts` to call the new endpoints

**Adding a computed column:**
```python
table.add_computed_column(
    new_col=some_function(table.existing_col),
    if_exists="ignore",
)
```

**Adding a new `@pxt.query` + route:**
```python
# In setup_pixeltable.py, at module level (after setup()):
_my_table = pxt.get_table(f"{config.APP_NAMESPACE}.my_table")

@pxt.query
def list_my_items():
    return _my_table.select(name=_my_table.name, score=_my_table.score)

# In routers/my_router.py:
router.add_query_route(path="/items", query=setup_pixeltable.list_my_items, method="get")
```

**Adding a tool to the agent:**
1. Define the function with `@pxt.udf` or `@pxt.query`
2. Add it to the `pxt.tools()` call in `setup_pixeltable.py`
3. Re-run `python setup_pixeltable.py`

## Files to Read First

If you're new to this codebase, read in this order:

1. `setup_pixeltable.py` — the core. Defines the entire data model, `@pxt.query` functions, and agent pipeline.
2. `routers/data.py` — 100% declarative `FastAPIRouter` (shows how `add_insert_route`, `add_delete_route`, `add_query_route` replace hand-written endpoints).
3. `routers/agent.py` — mixed: declarative routes + 1 hand-written endpoint (shows when you *must* keep custom code).
4. `functions.py` — `@pxt.udf` definitions used by the agent pipeline.
5. `frontend/src/lib/api.ts` + `types/index.ts` — how the frontend consumes PXT routes with client-side aggregation.
6. `models.py` — minimal Pydantic models for the agent endpoint only.
