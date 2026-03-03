terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
  }
}

provider "aws" {
  region = var.region
}

data "aws_availability_zones" "available" {
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

# ── VPC ──────────────────────────────────────────────────────────────────────

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${var.cluster_name}-vpc"
  cidr = "10.0.0.0/16"

  azs             = slice(data.aws_availability_zones.available.names, 0, 2)
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnets = ["10.0.10.0/24", "10.0.11.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = true
  enable_dns_hostnames = true

  public_subnet_tags = {
    "kubernetes.io/role/elb" = 1
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb" = 1
  }
}

# ── EKS ──────────────────────────────────────────────────────────────────────

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.30"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    default = {
      instance_types = [var.node_instance_type]
      min_size       = 1
      max_size       = var.node_count * 2
      desired_size   = var.node_count
    }
  }
}

# ── ECR ──────────────────────────────────────────────────────────────────────

resource "aws_ecr_repository" "app" {
  name                 = var.ecr_repository_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

# ── Kubernetes provider (uses EKS cluster) ───────────────────────────────────

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

# ── K8s Namespace ────────────────────────────────────────────────────────────

resource "kubernetes_namespace" "app" {
  metadata {
    name = "pixeltable"
  }
}

# ── K8s Secret (API keys) ───────────────────────────────────────────────────

resource "kubernetes_secret" "api_keys" {
  metadata {
    name      = "pixeltable-api-keys"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  data = {
    ANTHROPIC_API_KEY = var.anthropic_api_key
    OPENAI_API_KEY    = var.openai_api_key
  }
}

# ── Persistent Volume Claim (Pixeltable data) ───────────────────────────────

resource "kubernetes_persistent_volume_claim" "pixeltable_data" {
  metadata {
    name      = "pixeltable-data"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = "gp3"

    resources {
      requests = {
        storage = "50Gi"
      }
    }
  }
}

# ── Deployment ───────────────────────────────────────────────────────────────

resource "kubernetes_deployment" "app" {
  metadata {
    name      = "pixeltable-starter"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    replicas = 1

    strategy {
      type = "Recreate"
    }

    selector {
      match_labels = {
        app = "pixeltable-starter"
      }
    }

    template {
      metadata {
        labels = {
          app = "pixeltable-starter"
        }
      }

      spec {
        container {
          name  = "app"
          image = "${aws_ecr_repository.app.repository_url}:latest"

          # Schema init + server in same container (Pixeltable's embedded
          # Postgres must stay alive — separate Jobs leave stale PID files)
          command = ["sh", "-c",
            "uv run python setup_pixeltable.py && uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4"
          ]

          port {
            container_port = 8000
          }

          env_from {
            secret_ref {
              name = kubernetes_secret.api_keys.metadata[0].name
            }
          }

          env {
            name  = "PIXELTABLE_HOME"
            value = "/data/pixeltable"
          }

          env {
            name  = "CORS_ORIGINS"
            value = "*"
          }

          volume_mount {
            name       = "pixeltable-data"
            mount_path = "/data/pixeltable"
          }

          resources {
            requests = {
              cpu    = "2"
              memory = "4Gi"
            }
            limits = {
              cpu    = "4"
              memory = "8Gi"
            }
          }

          liveness_probe {
            http_get {
              path = "/api/health"
              port = 8000
            }
            initial_delay_seconds = 60
            period_seconds        = 30
          }

          readiness_probe {
            http_get {
              path = "/api/health"
              port = 8000
            }
            initial_delay_seconds = 30
            period_seconds        = 10
          }
        }

        volume {
          name = "pixeltable-data"

          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.pixeltable_data.metadata[0].name
          }
        }
      }
    }
  }
}

# ── Service ──────────────────────────────────────────────────────────────────

resource "kubernetes_service" "app" {
  metadata {
    name      = "pixeltable-starter"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    selector = {
      app = "pixeltable-starter"
    }

    port {
      port        = 80
      target_port = 8000
    }

    type = "LoadBalancer"
  }
}
