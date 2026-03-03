# Terraform + Kubernetes (GKE) Deployment

One-command deployment of the Pixeltable Starter Kit to Google Kubernetes Engine.

## What gets created

- **VPC** — Custom network with subnet + secondary ranges for pods/services
- **GKE cluster** — Managed node pool (e2-standard-4 × 2 by default, auto-scales)
- **Artifact Registry** — Docker repository for the app image
- **K8s resources** — Namespace, secret (API keys), PVC (50Gi), schema init job, deployment, LoadBalancer service

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- [gcloud CLI](https://cloud.google.com/sdk/docs/install) authenticated
- [Docker](https://docs.docker.com/get-docker/)

## Deploy

```bash
# 1. Build and push the Docker image
cd ../..  # repo root
gcloud auth configure-docker us-central1-docker.pkg.dev
docker build -t pixeltable-starter .
docker tag pixeltable-starter:latest us-central1-docker.pkg.dev/YOUR_PROJECT/pixeltable-starter/pixeltable-starter:latest
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/pixeltable-starter/pixeltable-starter:latest

# 2. Deploy infrastructure + app
cd deploy/terraform-gke
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your project ID and settings

terraform init
terraform apply \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="openai_api_key=$OPENAI_API_KEY"

# 3. Get the app URL
terraform output load_balancer_ip
```

## Pixeltable storage

- `PIXELTABLE_HOME=/data/pixeltable` on a 50Gi PD (standard-rwo)
- For large media files, use GCS:

```bash
PIXELTABLE_INPUT_MEDIA_DEST=gs://your-bucket/input
PIXELTABLE_OUTPUT_MEDIA_DEST=gs://your-bucket/output
```

See [Pixeltable Configuration](https://docs.pixeltable.com/platform/configuration.md) for all options.

## Cleanup

```bash
terraform destroy \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="openai_api_key=$OPENAI_API_KEY"
```
