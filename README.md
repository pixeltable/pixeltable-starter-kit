# Pixeltable Starter Kit

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/pixeltable/pixeltable-starter-kit)

Two apps. Each is one application file (`app.py`).
Declare, Experiment, Serve: `pxt schema update`, then `pxt service update`, then insert, `/ask`, or `pxt dashboard`.

**Export your API keys before the first `pxt` command** -- the service inherits the daemon's environment. Export a
key afterwards and the next `pxt` command refuses with `STALE_CONFIG` until `pxt daemon restart`.
Why, and how to recover: [chat-agent/README.md](chat-agent/README.md).

## Try it on Pixeltable Cloud, no account

Open a codespace with the button above, then:

```bash
bash .devcontainer/cloud.sh
```

`pxt new` gives you a free Cloud database for 48 hours. The script uploads the chat agent, creates its tables,
starts its service, and calls it once. Open the link it prints to claim the trial and keep it.
`bash .devcontainer/cloud.sh video-search` deploys the other app. From a local clone it runs the same way; it needs `uv`.

## Chat agent

```bash
export ANTHROPIC_API_KEY=sk-...        # before the first pxt command; /ask needs it
uvx pixeltable-new myapp
cd myapp && uv sync
uv run pxt schema update app.py agent
uv run pxt service update app.py agent
uv run pxt service list
```

Already cloned: `cd chat-agent` instead of `uvx pixeltable-new`, then the same `uv sync` and `pxt` commands.

```bash
curl -s -X POST http://127.0.0.1:<port>/api/knowledge \
  -H "Content-Type: application/json" \
  -d '{"body": "Pixeltable is a unified backend: one application file, tables, and insert runs compute.", "title": "intro", "source": "docs"}'
```

`POST /api/knowledge` works without a key -- embeddings run locally. Only `/ask` needs `ANTHROPIC_API_KEY`.

## Video search

```bash
uvx pixeltable-new myapp --video
cd myapp && uv sync
uv run pxt schema update app.py videointel
uv run pxt service update app.py videointel
uv run pxt service list
```

Already cloned: `cd video-search` instead of `uvx pixeltable-new --video`.

```bash
curl -s -X POST http://127.0.0.1:<port>/api/ingest \
  -F "video=@/path/to/clip.mp4" \
  -F "title=demo"

curl -s -X POST http://127.0.0.1:<port>/api/ingest/image \
  -F "image=@/path/to/photo.jpg" \
  -F "label=demo" \
  -F "source_id=api-001"
```

Video ingest is a background job. Poll `job_url` from the insert response.

Already have FastAPI: copy `app.py` under a project root (`pixeltable.toml`, or run `pxt init`), apply it, then
`app.include_router(api)` on the router in `app.py`.

## Same file, hosted

```bash
uv run pxt db update pxt://org:mydb
uv run pxt schema update app.py pxt://org:mydb
uv run pxt service update app.py pxt://org:mydb
```

Chat agent `/ask` also needs `pxt secret set pxt://org ANTHROPIC_API_KEY=sk-...`, then `pxt db restart pxt://org:mydb`
so the pods read it, before schema update.
Experiment on Cloud is dashboard insert plus `pxt schema diff`.
[Cloud](https://docs.pixeltable.com/howto/deployment/cloud).

## Without HTTP

Apply, then insert from Python or open `pxt dashboard`. [Self-hosting](https://docs.pixeltable.com/howto/deployment/overview).

## For agents

Emit `TableModel` classes and a `FastAPIRouter` in `app.py`. Indexes go on `__indexes__`.
Do not emit a sequence of table-create or column-add calls.
Drift check and exit codes: [AGENTS.md](AGENTS.md).

Layout and tests: [AGENTS.md](AGENTS.md).
Skill: `npx skills add pixeltable/pixeltable-skill`.

Python 3.11+. `uv sync` installs `pixeltable[serve]>=0.7.16`.

## Resources

- [Quickstart](https://docs.pixeltable.com/overview/quick-start) · [How it works](https://docs.pixeltable.com/overview/how-it-works)
- [Self-hosting](https://docs.pixeltable.com/howto/deployment/overview) · [Cloud](https://docs.pixeltable.com/howto/deployment/cloud) · [HTTP serving](https://docs.pixeltable.com/howto/deployment/serving)
- [pixeltable-new](https://github.com/pixeltable/pixeltable-new) · [pixeltable-skill](https://github.com/pixeltable/pixeltable-skill)

## License

Apache 2.0
