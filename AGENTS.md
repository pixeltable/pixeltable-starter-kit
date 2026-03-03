# AGENTS.md

Instructions for AI coding agents working with this app template.

## Pixeltable Resources

Before modifying this codebase, familiarize yourself with Pixeltable:

- **Core AGENTS.md** — [pixeltable/pixeltable/AGENTS.md](https://github.com/pixeltable/pixeltable/blob/main/AGENTS.md) covers the full SDK: tables, computed columns, views, iterators, UDFs, embedding indexes, and all AI provider integrations.
- **Claude Code Skill** — [pixeltable/pixeltable-skill](https://github.com/pixeltable/pixeltable-skill) gives Claude deep Pixeltable expertise via progressive disclosure (`SKILL.md` → `API_REFERENCE.md`).
- **MCP Server** — [pixeltable/mcp-server-pixeltable-developer](https://github.com/pixeltable/mcp-server-pixeltable-developer) exposes Pixeltable as an MCP server for interactive exploration (tables, queries, Python REPL).
- **Docs** — [docs.pixeltable.com](https://docs.pixeltable.com/) · [SDK Reference](https://docs.pixeltable.com/sdk/latest/pixeltable)

## What This Template Is

A skeleton full-stack app demonstrating how to put Pixeltable in production with FastAPI + Pydantic + TypeScript. Three tabs show three interaction patterns:

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
├── setup_pixeltable.py      Declarative schema: tables, views, indexes, agent pipeline
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

deploy/
├── helm/                    Helm chart (any existing K8s cluster)
├── terraform-k8s/           Terraform + AWS EKS
├── terraform-gke/           Terraform + GCP GKE
├── terraform-aks/           Terraform + Azure AKS
└── aws-cdk/                 CDK + ECS Fargate
```

## Setup

```bash
git clone https://github.com/pixeltable/pixeltable-app-template.git
cd pixeltable-app-template
cp .env.example .env          # add ANTHROPIC_API_KEY and OPENAI_API_KEY

cd backend
uv sync                       # creates .venv, resolves and installs deps
source .venv/bin/activate
python -m spacy download en_core_web_sm
python setup_pixeltable.py    # initialize schema (one-time, drops and recreates)
python main.py                # http://localhost:8000

# Frontend (separate terminal)
cd frontend
npm install && npm run dev    # http://localhost:5173
```

Production: `cd frontend && npm run build` then `python main.py` — serves everything at `:8000`.

## Architectural Decisions

Each decision below is intentional. Don't change it without understanding why.

### Pixeltable IS the data layer

There is no ORM, no SQLAlchemy, no direct PostgreSQL client. Pixeltable handles storage, indexing, transformation, and retrieval. The `setup_pixeltable.py` file defines the entire data model declaratively — tables, views, computed columns, embedding indexes, and the agent pipeline — in ~380 lines.

### Sync endpoints (`def`, not `async def`)

All FastAPI endpoints use `def`, not `async def`. Pixeltable operations are synchronous and thread-safe. Uvicorn runs sync endpoints in a thread pool automatically, which is the correct pattern. Using `async def` would block the event loop.

### No explicit event loop configuration

`uvicorn.run()` is called without `loop="asyncio"`. This lets Uvicorn auto-detect `uvloop` when available, which is faster.

### Schema-as-code

`setup_pixeltable.py` is run once to initialize (or reset) the schema. It uses `drop_dir` + `create_dir` for a clean slate, and `if_exists="ignore"` for idempotent operations. The schema defines:

1. **Document pipeline** — table → `DocumentSplitter` view → sentence-transformer embedding index
2. **Image pipeline** — table → thumbnail computed column → CLIP embedding index
3. **Video pipeline** — table → `FrameIterator` view (keyframes + CLIP) → audio extraction → Whisper transcription → `StringSplitter` view → embedding index
4. **Chat history** — table with embedding index for memory retrieval
5. **Agent pipeline** — 8 chained computed columns: initial LLM call with tools → tool execution → context retrieval (RAG across all media) → history injection → context assembly → final LLM call → answer extraction

### Pydantic everywhere

`models.py` contains both **row schemas** (for `table.insert()`) and **API response models** (for `response_model=`). Every endpoint declares its response model so `/docs` is self-documenting. Where Pixeltable query results match model fields directly, `ResultSet.to_pydantic()` converts them.

### `@pxt.udf` and `@pxt.query` for logic

Business logic lives in Pixeltable functions, not endpoint handlers. `@pxt.udf` (in `functions.py`) for custom transforms like web search and context assembly. `@pxt.query` (in `setup_pixeltable.py`) for reusable similarity searches. Routers are thin — they insert rows, collect results, and return responses.

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

1. `setup_pixeltable.py` — the core. Defines the entire data model and agent pipeline.
2. `models.py` — all Pydantic models (row schemas + API responses).
3. `routers/agent.py` — shows the insert-triggers-pipeline pattern.
4. `routers/data.py` — shows CRUD + `to_pydantic()` conversion.
5. `functions.py` — `@pxt.udf` definitions used by the agent.
6. `frontend/src/lib/api.ts` + `types/index.ts` — how the frontend talks to the backend.
