# Pixeltable `FastAPIRouter` Integration (v0.6.0)

Pixeltable 0.6.0 ships `pixeltable.serving.FastAPIRouter` with:
- **`add_insert_route`** — POST to insert a row (supports `UploadFile` for media)
- **`add_query_route`** — GET/POST to run a `@pxt.query` function
- **`add_delete_route`** — POST to delete rows by column match
- **`add_update_route`** — POST to update rows by primary key
- **`@insert_route`** decorator — POST insert with post-processing (returns custom Pydantic model)
- **`@update_route`** decorator — POST update with post-processing
- **`GET /media/{path}`** — serves Pixeltable-managed media files
- **`GET /jobs/{job_id}`** — polls background job status (when `background=True`)

---

## Architecture: Dual Router

This starter kit mounts both layers side-by-side:

| Layer | Prefix | Role |
|-------|--------|------|
| **Facade routers** | `/api/data`, `/api/search`, `/api/agent` | SPA-facing; Pydantic DTOs, merged search, chat management. **Frontend calls these.** |
| **Pixeltable FastAPIRouter** | `/api/pxt` | Declarative; auto-generated from tables and `@pxt.query`. Scripts, admin, direct API. |

```text
SPA  →  /api/data, /api/search, /api/agent   (facade — stable contract)
         │
       Facade routers  →  Pixeltable tables/queries
         │
Also:  /api/pxt/...  →  same Pixeltable ops (declarative HTTP)
```

### What lives on `/api/pxt`

| Route | Method | Source |
|-------|--------|--------|
| `/api/pxt/tables/documents/insert` | POST | `add_insert_route(docs_table, uploadfile_inputs=["document"])` |
| `/api/pxt/tables/images/insert` | POST | `add_insert_route(images_table, uploadfile_inputs=["image"])` |
| `/api/pxt/tables/videos/insert` | POST | `add_insert_route(videos_table, uploadfile_inputs=["video"])` |
| `/api/pxt/tables/documents/delete` | POST | `add_delete_route(docs_table)` |
| `/api/pxt/tables/images/delete` | POST | `add_delete_route(images_table)` |
| `/api/pxt/tables/videos/delete` | POST | `add_delete_route(videos_table)` |
| `/api/pxt/tables/chat-history/delete` | POST | `add_delete_route(chat_table, match_columns=["conversation_id"])` |
| `/api/pxt/queries/documents` | POST | `add_query_route(query=search_documents)` |
| `/api/pxt/queries/images` | POST | `add_query_route(query=search_images)` |
| `/api/pxt/queries/video-frames` | POST | `add_query_route(query=search_video_frames)` |
| `/api/pxt/queries/video-transcripts` | POST | `add_query_route(query=search_video_transcripts)` |
| `/api/pxt/queries/chat-history` | POST | `add_query_route(query=search_chat_history)` |
| `/api/pxt/agent/query` | POST | `@insert_route(agent_table, ...)` with post-processing → `QueryResponse` |
| `/api/pxt/media/{path}` | GET | Built-in; serves Pixeltable-managed media |
| `/api/pxt/jobs/{job_id}` | GET | Built-in; polls background jobs |

### What stays as facades (can't express via `FastAPIRouter`)

| Facade route | Why |
|-------------|-----|
| `POST /api/search` | 4-way fan-in: runs document, image, video-frame, and transcript queries, merges + sorts results |
| `GET /api/data/files` | Aggregates 3 tables (documents, images, videos) into one response |
| `GET /api/agent/conversations` | Groups chat_history by conversation_id with message counts |
| `GET /api/agent/conversations/{id}` | Filters + orders messages within a conversation |

---

## Key implementation details

### `setup_pixeltable.py` wraps schema in `setup()`

`@pxt.query` in Pixeltable 0.6+ **eagerly evaluates** the function body at decoration time. This means the tables referenced in the query must already exist. The `setup()` function creates tables first, then defines `@pxt.query` functions inside the same scope, and exports them as module-level attributes.

### Explicit `idx_name` for embedding indexes

Pixeltable 0.6.0 has a bug where `add_embedding_index(if_exists="ignore")` creates duplicate indexes when no explicit `idx_name` is provided. All calls use explicit names (e.g., `idx_name="chunks_text_embed"`) as a workaround.

### `@insert_route` decorator for the agent

The agent query endpoint uses the `@insert_route` decorator, which:
1. Accepts the row data as the request body
2. Inserts into the `agent` table (triggering the 8-step computed column pipeline)
3. Reads back the specified output columns
4. Passes them to the decorated function for reshaping into `QueryResponse`

```python
@router.insert_route(
    agent_table,
    path="/agent/query",
    inputs=["prompt", "timestamp", ...],
    outputs=["answer", "doc_context", "image_context", "tool_output"],
)
def agent_query(*, answer, doc_context, image_context, tool_output) -> QueryResponse:
    return QueryResponse(answer=str(answer) if answer else "Error", ...)
```

### Column types: `Json` not `str`

Computed columns that derive from LLM responses or `@pxt.query` results have type `Json | None`, not `String`. The `@insert_route` decorator validates parameter annotations against Pixeltable column types, so output parameters must use `dict | None` (which maps to `Json | None`).

---

## Interacting with `/api/pxt`

### Insert a document

```bash
curl -X POST http://localhost:8000/api/pxt/tables/documents/insert \
  -F "document=@my_file.pdf" \
  -F "timestamp=2026-05-05T12:00:00"
# {"uuid": "019d..."}
```

### Search documents

```bash
curl -X POST http://localhost:8000/api/pxt/queries/documents \
  -H "Content-Type: application/json" \
  -d '{"query_text": "machine learning"}'
# {"rows": [{"text": "...", "sim": 0.85, ...}, ...]}
```

### Delete by primary key

```bash
curl -X POST http://localhost:8000/api/pxt/tables/documents/delete \
  -H "Content-Type: application/json" \
  -d '{"uuid": "019d..."}'
# {"num_rows": 1}
```

### Agent query

```bash
curl -X POST http://localhost:8000/api/pxt/agent/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is Pixeltable?", "timestamp": "2026-05-05T12:00:00", ...}'
# {"answer": "...", "metadata": {...}}
```
