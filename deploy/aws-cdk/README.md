# AWS CDK Deployment (ECS Fargate)

Deploys the Pixeltable Starter Kit on ECS Fargate with persistent storage via EFS.

## What gets created

- **VPC** — 2 AZs, public/private subnets, NAT gateway
- **ECS Fargate cluster** — 4 vCPU / 8 GB task, auto-scales 1–4
- **EFS file system** — Persistent storage for Pixeltable data
- **Application Load Balancer** — Public HTTP endpoint
- **Secrets Manager** — Stores API keys
- **CloudWatch** — Container insights + log group

## Prerequisites

- [AWS CLI](https://aws.amazon.com/cli/) configured with credentials
- [AWS CDK v2](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html)
- [Docker](https://docs.docker.com/get-docker/)
- Python 3.10+

## Deploy

```bash
cd deploy/aws-cdk

# Install CDK dependencies
pip install -r requirements.txt

# Set API keys
export ANTHROPIC_API_KEY=your-key
export OPENAI_API_KEY=your-key

# Bootstrap (first time only) and deploy
cdk bootstrap
cdk deploy
```

The app URL will be printed as a stack output.

## Architecture

```
Internet → ALB → ECS Fargate (4 vCPU / 8 GB)
                      ↓
                 EFS volume (/data/pixeltable)
                      ↓
                 Pixeltable data
                 (embedded PostgreSQL + file cache)
```

## Pixeltable storage

Uses EFS for persistent Pixeltable data across container restarts and scaling events.
For large media files, configure external blob storage via environment variables:

```
PIXELTABLE_INPUT_MEDIA_DEST=s3://your-bucket/input
PIXELTABLE_OUTPUT_MEDIA_DEST=s3://your-bucket/output
```

See [Pixeltable Configuration](https://docs.pixeltable.com/platform/configuration.md) for all options.

## Cleanup

```bash
cdk destroy
```

Note: EFS file system is retained by default to prevent data loss. Delete it manually via the AWS console if no longer needed.
