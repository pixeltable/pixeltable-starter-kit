# Pixeltable App Template

A skeleton app showing how [Pixeltable](https://github.com/pixeltable/pixeltable) unifies **storage, orchestration, and retrieval** for multimodal workloads. Pixeltable is data infrastructure — you can build whatever you want on top of it. This template just demonstrates the core pattern with a simple three-tab UI:

- **Data** — Upload documents, images, and videos. Pixeltable automatically chunks, extracts keyframes, transcribes audio, and generates thumbnails via computed columns and iterators.
- **Search** — Cross-modal similarity search across all media types using embedding indexes.
- **Agent** — Chat with a tool-calling agent (Claude) wired up entirely as Pixeltable computed columns.

> For a more complete example, see **[Pixelbot](https://github.com/pixeltable/pixelbot)**.

## Quick Start

**Prerequisites:** Python 3.10+, Node.js 18+, [uv](https://docs.astral.sh/uv/)

```bash
git clone https://github.com/pixeltable/pixeltable-app-template.git
cd pixeltable-app-template
cp .env.example .env   # add your ANTHROPIC_API_KEY and OPENAI_API_KEY

# Backend
cd backend
uv sync
source .venv/bin/activate
python -m spacy download en_core_web_sm
python setup_pixeltable.py   # initialize schema (one-time)
python main.py               # http://localhost:8000

# Frontend (new terminal)
cd frontend
npm install && npm run dev   # http://localhost:5173
```

**Production:** `cd frontend && npm run build` then `cd ../backend && python main.py` — serves everything at `:8000`.

## Deploy

```bash
# Docker (simplest)
docker compose up --build          # http://localhost:8000

# AWS EKS via Terraform
cd deploy/terraform-k8s && terraform init && terraform apply

# AWS ECS Fargate via CDK
cd deploy/aws-cdk && cdk deploy
```

Each option handles Pixeltable's persistent storage (embedded PostgreSQL + file cache) via volumes. For large media files, configure external blob storage:

```bash
PIXELTABLE_INPUT_MEDIA_DEST=s3://your-bucket/input
PIXELTABLE_OUTPUT_MEDIA_DEST=s3://your-bucket/output
```

See [Pixeltable Configuration](https://docs.pixeltable.com/platform/configuration.md) and `deploy/` READMEs for details.

## Project Structure

```
backend/
├── main.py                 FastAPI app, CORS, routers, SPA fallback
├── config.py               Model IDs, system prompts, env overrides
├── models.py               Pydantic models (row schemas + API responses)
├── functions.py            @pxt.udf definitions (web search, context assembly)
├── setup_pixeltable.py     Full multimodal schema (tables, views, indexes, agent)
├── pyproject.toml          Dependencies (uv sync)
└── routers/
    ├── data.py             Upload, list, delete, chunks, frames, transcription
    ├── search.py           Cross-modal similarity search
    └── agent.py            Tool-calling agent + conversations

frontend/src/
├── App.tsx                 Tab navigation (Data / Search / Agent)
├── components/             Page components + shared UI (Button, Badge)
├── lib/api.ts              Typed fetch wrapper
└── types/index.ts          Shared interfaces

deploy/
├── terraform-k8s/          Terraform + EKS (1-click K8s deployment)
└── aws-cdk/                AWS CDK + ECS Fargate
```

## Learn More

[Pixeltable Docs](https://docs.pixeltable.com/) · [GitHub](https://github.com/pixeltable/pixeltable) · [Cookbooks](https://docs.pixeltable.com/howto/cookbooks) · [AGENTS.md](AGENTS.md)

## License

Apache 2.0
