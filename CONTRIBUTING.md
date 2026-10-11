# Contributing

## Development setup

```bash
git clone https://github.com/pixeltable/pixeltable-starter-kit.git
cd pixeltable-starter-kit
uv sync
```

Apps require `pixeltable[serve]>=0.7.16` and Python 3.11+. HuggingFace
sentence-transformer embeddings require sentence-transformers 5.6.0+.
The chat agent requires `anthropic>=1.3`: pixeltable 0.7.8+ imports `httpx2`, which
older SDKs do not ship, and SDK 1.x rejects `temperature`/`top_p`/`top_k`.

## Testing

```bash
uv sync
uv run ruff check video-search/ chat-agent/ tests/
uv run ruff format video-search/ chat-agent/ tests/ --check
uv run python -m pytest tests/ -v
```

Slow checks in `.github/workflows/test.yml`:

- **schema-smoke** (every push/PR, and also on the weekly cron and manual dispatch, since it is
  ungated): `pytest tests/test_schema.py --run-slow`, then `pxt schema update` + `pxt schema diff`
  for each app against a temporary catalog. Needs no API key.
- **app-smoke** (weekly cron + manual dispatch only): serves each app and drives real HTTP.
  `/ask` runs only when the `ANTHROPIC_API_KEY` repository secret is set; it is also the canary
  for the model id pinned in `chat-agent/app.py`. Video search generates a 2s clip with ffmpeg.

## Apps

`chat-agent/` is the default `uvx pixeltable-new` extract. `video-search/` is `--video`.

Each app needs: `app.py`, `pixeltable.toml` (`[[pixeltable.database]]`),
`pyproject.toml` (`[build-system]` and `[tool.setuptools] py-modules` listing `app`),
`README.md`, `Dockerfile`, `docker-compose.yml`.

Do not add TOML service route tables. Do not add `templates/` or a second
apply path. Tables are declared in `app.py` and applied with `pxt schema update`.

Same application file on Cloud.

`pixeltable-new` fetches `chat-agent/` or `video-search/` from this repo's `main` tarball.
Printed next-steps live in pixeltable-new and need a PyPI release to change.
This kit's contract is `pxt db update`, then schema update, then `pxt service update`
on `pxt://`; if a published scaffold prints anything else, release pixeltable-new.

## Linting

Ruff in root `pyproject.toml`: line-length 120; rules `E, W, F, I, B, C4, UP`;
ignored `E501`, `B008`, `B904`.

## Releasing pixeltable-new

See [`pixeltable-new/CONTRIBUTING.md`](https://github.com/pixeltable/pixeltable-new/blob/main/CONTRIBUTING.md).
