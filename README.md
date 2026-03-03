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

### Docker Compose (local / single server)

**Requires [Docker](https://docs.docker.com/get-docker/)** (Docker Desktop on macOS/Windows, or Docker Engine on Linux).

```bash
cp .env.example .env          # add API keys
docker compose up --build     # http://localhost:8000
```

Pixeltable data persists across restarts via named Docker volumes. To reset everything: `docker compose down -v`.

### Helm (any existing Kubernetes cluster)

**Requires [Helm 3](https://helm.sh/docs/intro/install/)** and a running K8s cluster (EKS, GKE, AKS, k3s, etc.).

```bash
# Build and push image to your registry
docker build -t <your-registry>/pixeltable-app:latest .
docker push <your-registry>/pixeltable-app:latest

# Deploy
helm install pixeltable-app ./deploy/helm/pixeltable-app \
  --set image.repository=<your-registry>/pixeltable-app \
  --set secrets.OPENAI_API_KEY=sk-... \
  --set secrets.ANTHROPIC_API_KEY=sk-ant-...
```

**Local testing with [minikube](https://minikube.sigs.k8s.io/docs/start/):**

```bash
minikube start --cpus=4 --memory=6144
docker build -t pixeltable-app:latest .
minikube image load pixeltable-app:latest
helm install pixeltable-app ./deploy/helm/pixeltable-app \
  --set image.pullPolicy=Never --set service.type=NodePort \
  --set secrets.OPENAI_API_KEY=$OPENAI_API_KEY \
  --set secrets.ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
kubectl port-forward svc/pixeltable-app 9000:8000   # http://localhost:9000
```

See [`deploy/helm/README.md`](deploy/helm/README.md) for full configuration.

### Terraform (provision cluster from scratch)

**Requires [Terraform](https://developer.hashicorp.com/terraform/install)** and cloud credentials. These configs provision everything — VPC, managed K8s cluster, container registry, and all K8s resources:

```bash
# AWS EKS
cd deploy/terraform-k8s && terraform init && terraform apply

# GCP GKE
cd deploy/terraform-gke && terraform init && terraform apply

# Azure AKS
cd deploy/terraform-aks && terraform init && terraform apply
```

Each creates a managed K8s cluster with a 50Gi persistent volume for Pixeltable data. See each `deploy/terraform-*/README.md` for required variables.

### AWS CDK (ECS Fargate)

**Requires [AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting-started.html)** and configured AWS credentials. Serverless containers with EFS for persistent storage and an ALB for load balancing:

```bash
cd deploy/aws-cdk && pip install -r requirements.txt && cdk deploy
```

### Storage notes

All deployment options configure `PIXELTABLE_HOME=/data/pixeltable` pointing to persistent storage (Docker volumes, K8s PVCs, or EFS). For large media workloads, configure external blob storage:

```bash
PIXELTABLE_INPUT_MEDIA_DEST=s3://your-bucket/input    # or gs:// or az://
PIXELTABLE_OUTPUT_MEDIA_DEST=s3://your-bucket/output
```

See [Pixeltable Configuration](https://docs.pixeltable.com/platform/configuration.md) and each `deploy/` README for details.

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
├── helm/                   Helm chart (any existing K8s cluster)
├── terraform-k8s/          Terraform + AWS EKS
├── terraform-gke/          Terraform + GCP GKE
├── terraform-aks/          Terraform + Azure AKS
└── aws-cdk/                AWS CDK + ECS Fargate
```

## Learn More

[Pixeltable Docs](https://docs.pixeltable.com/) · [GitHub](https://github.com/pixeltable/pixeltable) · [Cookbooks](https://docs.pixeltable.com/howto/cookbooks) · [AGENTS.md](AGENTS.md)

## License

Apache 2.0
