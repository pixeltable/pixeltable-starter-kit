# AGENTS.md

Instructions for AI coding agents working in the Pixeltable Starter Kit.

## Apps

Apps are one Python file (`app.py`): `TableModel` classes and a `FastAPIRouter`.
The loop is Declare, Experiment, Serve: apply with `pxt schema update`, serve with `pxt service update`, then insert / `/ask` / `pxt dashboard`.
Every example here uses `uv run pxt`, which works whether or not `.venv` is on PATH.
Export API keys before the first `pxt` command: it starts the daemon, and the service inherits the daemon's environment.
A key exported later makes the next `pxt` command refuse with `STALE_CONFIG`; run `pxt daemon restart`, then `pxt service update`.
Indexes belong on the model (`__indexes__`). Routes live on `FastAPIRouter`. No TOML route tables.
Already have FastAPI? Copy `app.py` under a project root (`pixeltable.toml`, or `pxt init`), then
`app.include_router(...)` on the router in `app.py`.
From plain Python, `import app` then `app.TableModel.bind_all(TARGET)` before inserting or calling `ask()`.

Same file on Cloud: `pxt db update pxt://org:mydb`, then
`pxt secret set pxt://org KEY=...`, then `pxt db restart pxt://org:mydb` (pods read secrets at start),
then `pxt schema update app.py pxt://org:mydb`, then `pxt service update app.py pxt://org:mydb`.
Then `t = pxt.get_table('pxt://org:mydb/knowledge')` (or `.../videos`).
`pxt db update` packs the hosted image and workers; it is not Experiment.
`pxt schema update` applies tables. It does not start HTTP.
`pxt service update` starts HTTP (local or `pxt://`) and prints where with `pxt service list`.
Experiment on Cloud is dashboard insert plus `pxt schema diff`.

Drift check: `uv run pxt schema diff app.py agent` (or `videointel`). Exit 0 in sync, 2 pending
(`--json` is the plan), 1 an error naming the file, declaration, or key, 3 refused (a destructive
change without `--allow-destructive`, or a non-interactive run without `-f`). Then `pxt schema update`.
Destructive ops need `--allow-destructive`; CI and Dockerfiles pass `-f`.

```bash
export ANTHROPIC_API_KEY=sk-...        # before the first pxt command
uvx pixeltable-new myapp
cd myapp && uv sync
uv run pxt schema update app.py agent
uv run pxt service update app.py agent
```

`agent` and `videointel` are catalog directories, not folders on disk.
Video: `uvx pixeltable-new myapp --video`, then TARGET `videointel`.

## Layout

```
video-search/   Frames, CLIP, images. TARGET videointel. uvx --video
chat-agent/     Knowledge, memory, LLM. TARGET agent. uvx default
tests/          Structure and config. Schema smoke: --run-slow.
```

Do not add `templates/`, `backend/`, `serving/`, `batch/`, or a PaaS `deploy/` zoo.
New verticals: edit `app.py` or add a folder next to these two with the same apply path.

## Extend an app

1. Add a `TableModel` in that app's `app.py`.
2. Put indexes on the class (`__indexes__`).
3. Register routes on the existing `FastAPIRouter`.
4. Run `uv run pxt schema update app.py agent` (or `videointel`).

Annotation is a stored column. Assignment is a computed column.
Primary key is `pxt.Column(..., primary_key=True)`, not a bare typed field.
Optional is `T | None`. Do not use `pxt.Required`.
Similarity uses `string=`: `col.similarity(string=query)`. In `@pxt.query`, alias as `score=sim`.

## Testing

```bash
uv sync
uv run ruff check video-search/ chat-agent/ tests/
uv run ruff format video-search/ chat-agent/ tests/ --check
uv run python -m pytest tests/ -v
```

Schema import smoke (needs Pixeltable in each app venv):

```bash
cd chat-agent && uv sync && cd ../video-search && uv sync && cd ..
uv run python -m pytest tests/test_schema.py -v --run-slow
```

## Files to read first

1. `chat-agent/app.py`
2. `chat-agent/README.md`
3. `video-search/app.py`
4. `video-search/README.md`
5. [pixeltable/pixeltable AGENTS.md](https://github.com/pixeltable/pixeltable/blob/main/AGENTS.md)
6. [pixeltable-skill](https://github.com/pixeltable/pixeltable-skill)
