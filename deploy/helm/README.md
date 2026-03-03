# Helm Chart — Pixeltable App Template

Deploy the Pixeltable app on **any existing Kubernetes cluster** using Helm.

Unlike the Terraform configs (which provision the cluster from scratch), this chart assumes you already have a K8s cluster and just want to deploy the app.

## Prerequisites

- Kubernetes cluster (any provider: EKS, GKE, AKS, k3s, minikube, etc.)
- [Helm 3](https://helm.sh/docs/intro/install/)
- Docker image pushed to an accessible registry

## Quick Start

```bash
# Build and push image to your registry
docker build -t <your-registry>/pixeltable-app:latest .
docker push <your-registry>/pixeltable-app:latest

# Install the chart
helm install pixeltable-app ./deploy/helm/pixeltable-app \
  --set image.repository=<your-registry>/pixeltable-app \
  --set secrets.OPENAI_API_KEY=sk-... \
  --set secrets.ANTHROPIC_API_KEY=sk-ant-...
```

## Configuration

All values are in `pixeltable-app/values.yaml`. Key options:

| Parameter | Default | Description |
|---|---|---|
| `image.repository` | `pixeltable-app` | Container image |
| `image.tag` | `latest` | Image tag |
| `service.type` | `LoadBalancer` | K8s service type (`ClusterIP`, `NodePort`, `LoadBalancer`) |
| `persistence.enabled` | `true` | Create a PVC for Pixeltable data |
| `persistence.size` | `50Gi` | PVC size |
| `schemaInit.enabled` | `true` | Run schema init as a Helm hook |
| `secrets.*` | `""` | API keys (stored as K8s Secret) |
| `resources.requests.memory` | `4Gi` | Memory request |

## How It Works

1. **Secret** — API keys are stored in a K8s Secret.
2. **PVC** — A PersistentVolumeClaim holds Pixeltable's embedded PostgreSQL and file cache.
3. **Schema Init Job** — Runs `setup_pixeltable.py` as a `post-install`/`post-upgrade` Helm hook.
4. **Deployment** — Runs uvicorn with 4 workers, health checks on `/api/health`.
5. **Service** — Exposes port 8000 via LoadBalancer (configurable).

## Upgrade

```bash
helm upgrade pixeltable-app ./deploy/helm/pixeltable-app --set image.tag=v2
```

The schema init job re-runs on upgrade (idempotent).
