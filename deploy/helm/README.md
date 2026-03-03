# Helm Chart — Pixeltable Starter Kit

Deploy the Pixeltable app on **any existing Kubernetes cluster** using Helm.

Unlike the Terraform configs (which provision the cluster from scratch), this chart assumes you already have a K8s cluster and just want to deploy the app.

## Prerequisites

- Kubernetes cluster (any provider: EKS, GKE, AKS, k3s, minikube, etc.)
- [Helm 3](https://helm.sh/docs/intro/install/)
- Docker image pushed to an accessible registry (or loaded locally for minikube)

## Quick Start

```bash
# Build and push image to your registry
docker build -t <your-registry>/pixeltable-starter:latest .
docker push <your-registry>/pixeltable-starter:latest

# Install the chart
helm install pixeltable-starter ./deploy/helm/pixeltable-starter \
  --set image.repository=<your-registry>/pixeltable-starter \
  --set secrets.OPENAI_API_KEY=sk-... \
  --set secrets.ANTHROPIC_API_KEY=sk-ant-...
```

## Test Locally with minikube

```bash
# Start a local cluster
minikube start --cpus=4 --memory=6144

# Build and load image (no registry needed)
docker build -t pixeltable-starter:latest .
minikube image load pixeltable-starter:latest

# Deploy
helm install pixeltable-starter ./deploy/helm/pixeltable-starter \
  --set image.repository=pixeltable-starter \
  --set image.pullPolicy=Never \
  --set service.type=NodePort \
  --set secrets.OPENAI_API_KEY=$OPENAI_API_KEY \
  --set secrets.ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  --set persistence.size=10Gi

# Wait ~2 min for schema init, then port-forward
kubectl port-forward svc/pixeltable-starter 9000:8000
# App is at http://localhost:9000

# Clean up
helm uninstall pixeltable-starter
minikube stop
```

## Configuration

All values are in `pixeltable-starter/values.yaml`. Key options:

| Parameter | Default | Description |
|---|---|---|
| `image.repository` | `pixeltable-starter` | Container image |
| `image.tag` | `latest` | Image tag |
| `image.pullPolicy` | `IfNotPresent` | Set to `Never` for minikube with local images |
| `service.type` | `LoadBalancer` | K8s service type (`ClusterIP`, `NodePort`, `LoadBalancer`) |
| `persistence.enabled` | `true` | Create a PVC for Pixeltable data |
| `persistence.size` | `50Gi` | PVC size |
| `schemaInit.enabled` | `true` | Run `setup_pixeltable.py` before starting the server |
| `secrets.*` | `""` | API keys (stored as K8s Secret) |
| `resources.requests.memory` | `4Gi` | Memory request |

## How It Works

1. **Secret** — API keys are stored in a K8s Secret.
2. **PVC** — A PersistentVolumeClaim holds Pixeltable's embedded PostgreSQL and file cache.
3. **Deployment** — When `schemaInit.enabled=true`, the container runs `setup_pixeltable.py` before starting uvicorn. Pixeltable manages its own embedded Postgres, so schema init and the server run in the same container to share the database process.
4. **Service** — Exposes port 8000 via LoadBalancer (configurable).
5. **Health checks** — Readiness probe at `/api/health` with longer initial delays to allow for schema init and model downloads.

## Upgrade

```bash
helm upgrade pixeltable-starter ./deploy/helm/pixeltable-starter --set image.tag=v2
```

Set `schemaInit.enabled=false` after the first deployment to skip re-running schema setup on restarts.
