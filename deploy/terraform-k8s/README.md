# Terraform + Kubernetes (EKS) Deployment

One-command deployment of the Pixeltable App Template to AWS EKS.

## What gets created

- **VPC** — 2 AZs, public/private subnets, NAT gateway
- **EKS cluster** — Managed node group (m6i.xlarge × 2 by default)
- **ECR repository** — For the app Docker image
- **K8s resources** — Namespace, secret (API keys), PVC (50Gi for Pixeltable data), schema init job, deployment, LoadBalancer service

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- [AWS CLI](https://aws.amazon.com/cli/) configured with credentials
- [Docker](https://docs.docker.com/get-docker/)

## Deploy

```bash
# 1. Build and push the Docker image
cd ../..  # repo root
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-west-2.amazonaws.com
docker build -t pixeltable-app .
docker tag pixeltable-app:latest <ACCOUNT_ID>.dkr.ecr.us-west-2.amazonaws.com/pixeltable-app:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-west-2.amazonaws.com/pixeltable-app:latest

# 2. Deploy infrastructure + app
cd deploy/terraform-k8s
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings

terraform init
terraform apply \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="openai_api_key=$OPENAI_API_KEY"

# 3. Get the app URL
terraform output load_balancer_hostname
```

## Architecture

```
Internet → AWS ALB → K8s Service → Pod (uvicorn × 4 workers)
                                        ↓
                                   PVC (50Gi EBS gp3)
                                        ↓
                                   Pixeltable data
                                   (embedded PostgreSQL + file cache)
```

## Pixeltable storage

Pixeltable runs an embedded PostgreSQL instance and file cache. In this deployment:

- `PIXELTABLE_HOME=/data/pixeltable` points to the PVC
- The PVC uses `gp3` storage class (EBS) for persistence across pod restarts
- Schema init runs as a K8s Job before the app deployment starts

For production with large media files, configure external blob storage:

```bash
# In terraform.tfvars or as env vars on the deployment
PIXELTABLE_INPUT_MEDIA_DEST=s3://your-bucket/input
PIXELTABLE_OUTPUT_MEDIA_DEST=s3://your-bucket/output
```

See [Pixeltable Configuration](https://docs.pixeltable.com/platform/configuration.md) for all options.

## Customize

| Variable | Default | Description |
|----------|---------|-------------|
| `region` | `us-west-2` | AWS region |
| `cluster_name` | `pixeltable-app` | EKS cluster name |
| `node_instance_type` | `m6i.xlarge` | Worker node size |
| `node_count` | `2` | Number of worker nodes |

## Cleanup

```bash
terraform destroy \
  -var="anthropic_api_key=$ANTHROPIC_API_KEY" \
  -var="openai_api_key=$OPENAI_API_KEY"
```
