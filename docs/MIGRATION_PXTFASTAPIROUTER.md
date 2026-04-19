# Pixeltable `PxtFastAPIRouter` ([PR #1268](https://github.com/pixeltable/pixeltable/pull/1268))

PR adds `pixeltable.serve.PxtFastAPIRouter`: **`add_insert_route`**, **`add_query_route`**, **`GET /media/{path:path}`**, **`GET /jobs/{job_id}`**. Not in **`pixeltable>=0.5.19`** until a release ships it; branch API may still change.

**What the PR does *not* give you as HTTP:** update/delete generators, one handler that merges four searches, or agent + `chat_history` orchestration. Those stay in **your** FastAPI code.

---

## Suggested architecture

| Layer | Path | Role |
|-------|------|------|
| **Product API (keep)** | `/api/data/*`, `POST /api/search`, `/api/agent/*` | One round-trip, Pydantic DTOs, merged search, chat -- **`frontend/src/lib/api.ts` unchanged.** |
| **Pixeltable router (optional)** | e.g. `/api/pxt/*` | OpenAPI, scripts, admin; same tables/queries as facades, different URLs/shapes. |

Handlers under `/api/...` should call **`insert`**, **`@pxt.query`** (or shared helpers), i.e. the same work **`PxtFastAPIRouter` would run**. Mount both; do not replace the product API with `/api/pxt` for the SPA.

```text
SPA  ->  /api/search, /api/data/..., /api/agent/...   (stable)
         |
       Facade routers  ->  Pixeltable
         |
Optional:  /api/pxt/...  ->  same Pixeltable ops (declarative HTTP)
```

---

## Suggested backend

**1. Keep existing routers** -- `backend/routers/data.py`, `search.py`, `agent.py`; register as today.

**2. After Pixeltable ships `serve`, add an optional router** -- new file e.g. `backend/pxt_serve.py`, or inline in `main.py`.

```python
# backend/pxt_serve.py -- illustrative; uncomment imports/routes when PR is in your dependency
import pixeltable as pxt
from pixeltable.serve import PxtFastAPIRouter

import config
# Import @pxt.query functions from your schema module once setup_pixeltable has run:
# from setup_pixeltable import search_documents, search_images, search_video_frames, search_video_transcripts


def build_pxt_router() -> PxtFastAPIRouter:
    r = PxtFastAPIRouter(prefix="/api/pxt")

    # Example: expose queries (paths are yours to choose)
    # r.add_query_route(path="/queries/documents", query=search_documents, method="post")
    # r.add_query_route(path="/queries/images", query=search_images, method="post")
    # ...

    # Example: optional raw insert for a table (adjust paths/columns to your schema)
    # imgs = pxt.get_table(f"{config.APP_NAMESPACE}.images")
    # r.add_insert_route(imgs, path="/tables/images/insert", uploadfile_inputs=["image"], inputs=["timestamp"])

    return r
```

**3. Wire in `main.py`** -- keep existing order; add the optional router last:

```python
app.include_router(data.router)
app.include_router(search.router)
app.include_router(agent.router)

# from pxt_serve import build_pxt_router
# app.include_router(build_pxt_router())
```

Uncomment when `pixeltable.serve` exists and routes are registered.

**4. Refactor facades (optional, for "one logic path"):** extract shared functions, e.g. `run_merged_search(query, types, limit, threshold) -> SearchResponse`, and call them from **`search.py`**; from **`build_pxt_router()`** you only add routes if you still want HTTP mirrors -- often facades stay the single implementation and `/api/pxt` stays thin or omitted.

---

## Suggested frontend

**No change required** for good UX: keep **`frontend/src/lib/api.ts`** calling `/api/data`, `/api/search`, `/api/agent`.

```typescript
// Unchanged idea -- see frontend/src/lib/api.ts
const BASE = '/api'

export async function search(params: { query: string; types?: string[]; limit?: number }) {
  return request(`${BASE}/search`, {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

// Optional: separate tiny module for /api/pxt (admin/tools only), e.g. lib/api-pxt.ts
const PXT = '/api/pxt'
export async function pxtQueryDocuments(queryText: string) {
  return request(`${PXT}/queries/documents`, {
    method: 'POST',
    body: JSON.stringify({ query_text: queryText }),
  })
}
```

Use **`api-pxt.ts`** only for internal tooling; the app shell should keep **`api.ts`**.

---

## PR behavior notes

- Multi-row query: `{ "rows": [...] }` (not a bare array).
- `method='get'` uses query params; `method='post'` uses JSON body (UDF parameter names).
- `add_insert_route`: base tables only (`InsertableTable`).
- `file://` to `/media`: Pixeltable home media/tmp; this repo's `UPLOAD_DIR` differs from router `TempStore` paths.
- v1: `@pxt.query` params with defaults should use `inputs=[]` or be made required.

---

## Gaps -- what the PR doesn't cover yet

### 1. Post-insert hook

Router inserts a row and returns columns. Can't run extra logic after.

**Where it matters:**

`POST /api/agent/query` -- insert agent row, then write 2 rows to `chat_history`, then return `QueryResponse`:

```python
# agent.py does this after insert:
chat_table.insert([{"role": "user", "content": body.query, ...}])
chat_table.insert([{"role": "assistant", "content": answer, ...}])
return QueryResponse(answer=answer, metadata=QueryMetadata(...))
```

`POST /api/data/upload` -- classify file, pick 1 of 3 tables, insert, return custom `UploadResponse`:

```python
# data.py builds a response the frontend expects:
return {"message": "Uploaded image", "filename": file.filename, "uuid": file_uuid, "type": "image"}
```

**Would fix it:** decorator that runs code after insert:

```python
@pxt_api.insert_route(table=agent_tbl, path="/agent/query", outputs=["answer", "doc_context", ...])
def agent_query(request_data, inserted_row):
    # write chat_history, reshape response
    return QueryResponse(...)
```

### 2. No delete route

`table.delete(where=...)` has no HTTP equivalent.

**Where it matters:**

```python
# data.py -- delete file by uuid
table.delete(where=(table.uuid == UUID(file_uuid)))

# agent.py -- delete conversation
table.delete(where=(table.conversation_id == conversation_id))
```

**Would fix it:** `add_delete_route(table, path, where_params=["uuid"])`.

### 3. No update route

PR says `add_update_route()` is planned but not included. Not used in this template today.

### 4. Query response reshaping

Router returns `{ "rows": [...] }` from the `@pxt.query` select list. Can't wrap in a custom model or deduplicate.

**Where it matters:**

```python
# data.py -- wrap chunks in ChunksResponse with uuid + total
return ChunksResponse(uuid=file_uuid, chunks=items, total=len(items))

# data.py -- deduplicate transcription rows
seen = set()
texts = [t for r in rows if (t := r["text"]) not in seen and not seen.add(t)]
return TranscriptionResponse(uuid=file_uuid, sentences=texts, full_text=" ".join(texts))
```

**Would fix it:** query decorator with post-hook:

```python
@pxt_api.query_route(path="/chunks/{uuid}", query=get_chunks_query)
def chunks(request_data, rows):
    items = [ChunkItem(**r) for r in rows]
    return ChunksResponse(uuid=request_data["uuid"], chunks=items, total=len(items))
```

### 5. Multi-query fan-in

One route = one query. No way to run N queries and merge.

**Where it matters:**

```python
# search.py -- 4 similarity searches, merge, sort, one SearchResponse
if "document" in body.types: ...
if "image" in body.types: ...
results.sort(key=lambda x: x["similarity"], reverse=True)
```

**Best fix:** keep as facade. App orchestration, not a table primitive.

### 6. Multi-table aggregation

One route = one table.

**Where it matters:**

```python
# data.py -- list_files: 3 tables into one FilesResponse
result = {"documents": [...], "images": [...], "videos": [...]}

# agent.py -- list_conversations: group chat_history by conversation_id
```

**Best fix:** keep as facade.

---

### Gap summary

| Gap | Endpoints | Fix |
|-----|-----------|-----|
| Post-insert hook | `agent/query`, `data/upload` | `insert_route` decorator |
| Delete | `data/files/{uuid}`, `agent/conversations/{id}` | `add_delete_route` |
| Update | (future) | `add_update_route` |
| Query reshaping | `chunks`, `frames`, `transcription`, `conversations/{id}` | `query_route` decorator |
| Fan-in search | `POST /api/search` | Keep facade |
| Multi-table reads | `GET /api/data/files`, `GET /api/agent/conversations` | Keep facade |

Gaps 1--4: **router features** (decorators + delete/update). Gaps 5--6: **app logic** (facades stay).

---

## Raw `/api/pxt` client (reference only)

[`examples/frontend-pxt-router-client.example.ts`](examples/frontend-pxt-router-client.example.ts) -- not the recommended primary client.

**Current implementations:** `backend/routers/data.py`, `search.py`, `agent.py` -- `frontend/src/lib/api.ts`.
