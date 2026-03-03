# Terraform + Kubernetes (AKS) Deployment

One-command deployment of the Pixeltable Starter Kit to Azure Kubernetes Service.

## What gets created

- **Resource Group** — Contains all Azure resources
- **AKS cluster** — Managed node pool (Standard_D4s_v3 × 2 by default, auto-scales)
- **Azure Container Registry** — Docker repository for the app image
- **K8s resources** — Namespace, secret (API keys), PVC (50Gi), schema init job, deployment, LoadBalancer service

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) authenticated (`az login`)
- [Docker](https://docs.docker.com/get-docker/)

## Deploy

```bash
# 1. Build and push the Docker image
cd ../..  # repo root

# First deploy infra to create ACR, then push
cd deploy/terraform-aks
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars

terraform init
terraform apply -target=azurerm_container_registry.acr \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="openai_api_key=$OPENAI_API_KEY"

# Push image
ACR=$(terraform output -raw acr_login_server)
az acr login --name $ACR
cd ../..
docker build -t pixeltable-starter .
docker tag pixeltable-starter:latest $ACR/pixeltable-starter:latest
docker push $ACR/pixeltable-starter:latest

# 2. Deploy everything
cd deploy/terraform-aks
terraform apply \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="openai_api_key=$OPENAI_API_KEY"

# 3. Get the app URL
terraform output load_balancer_ip
```

## Pixeltable storage

- `PIXELTABLE_HOME=/data/pixeltable` on a 50Gi Azure Managed Disk (managed-csi)
- For large media files, use Azure Blob Storage:

```bash
AZURE_STORAGE_ACCOUNT_NAME=youraccount
AZURE_STORAGE_ACCOUNT_KEY=yourkey
PIXELTABLE_INPUT_MEDIA_DEST=az://your-container/input
PIXELTABLE_OUTPUT_MEDIA_DEST=az://your-container/output
```

See [Pixeltable Configuration](https://docs.pixeltable.com/platform/configuration.md) for all options.

## Cleanup

```bash
terraform destroy \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="openai_api_key=$OPENAI_API_KEY"
```
