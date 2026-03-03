terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ── VPC ──────────────────────────────────────────────────────────────────────

resource "google_compute_network" "vpc" {
  name                    = "${var.cluster_name}-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "subnet" {
  name          = "${var.cluster_name}-subnet"
  region        = var.region
  network       = google_compute_network.vpc.id
  ip_cidr_range = "10.0.0.0/20"

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.1.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.2.0.0/20"
  }
}

# ── GKE Cluster ──────────────────────────────────────────────────────────────

resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.region

  network    = google_compute_network.vpc.id
  subnetwork = google_compute_subnetwork.subnet.id

  # Use separately managed node pool
  remove_default_node_pool = true
  initial_node_count       = 1

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  deletion_protection = false
}

resource "google_container_node_pool" "primary" {
  name     = "${var.cluster_name}-pool"
  location = var.region
  cluster  = google_container_cluster.primary.name

  initial_node_count = var.node_count

  autoscaling {
    min_node_count = 1
    max_node_count = var.node_count * 2
  }

  node_config {
    machine_type = var.machine_type
    disk_size_gb = 100

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]
  }
}

# ── Artifact Registry ────────────────────────────────────────────────────────

resource "google_artifact_registry_repository" "app" {
  location      = var.region
  repository_id = var.cluster_name
  format        = "DOCKER"
}

# ── Kubernetes provider ──────────────────────────────────────────────────────

data "google_client_config" "default" {}

provider "kubernetes" {
  host  = "https://${google_container_cluster.primary.endpoint}"
  token = data.google_client_config.default.access_token

  cluster_ca_certificate = base64decode(
    google_container_cluster.primary.master_auth[0].cluster_ca_certificate
  )
}

# ── K8s Namespace ────────────────────────────────────────────────────────────

resource "kubernetes_namespace" "app" {
  metadata {
    name = "pixeltable"
  }

  depends_on = [google_container_node_pool.primary]
}

# ── K8s Secret ───────────────────────────────────────────────────────────────

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

# ── Persistent Volume Claim ──────────────────────────────────────────────────

resource "kubernetes_persistent_volume_claim" "pixeltable_data" {
  metadata {
    name      = "pixeltable-data"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    access_modes       = ["ReadWriteOnce"]
    storage_class_name = "standard-rwo"

    resources {
      requests = {
        storage = "50Gi"
      }
    }
  }
}

# ── Schema init Job ──────────────────────────────────────────────────────────

locals {
  image_url = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}/pixeltable-app:latest"
}

resource "kubernetes_job" "schema_init" {
  metadata {
    name      = "pixeltable-schema-init"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    template {
      metadata {
        labels = { app = "pixeltable-init" }
      }

      spec {
        restart_policy = "OnFailure"

        container {
          name    = "init"
          image   = local.image_url
          command = ["uv", "run", "python", "setup_pixeltable.py"]

          env_from {
            secret_ref {
              name = kubernetes_secret.api_keys.metadata[0].name
            }
          }

          env {
            name  = "PIXELTABLE_HOME"
            value = "/data/pixeltable"
          }

          volume_mount {
            name       = "pixeltable-data"
            mount_path = "/data/pixeltable"
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

    backoff_limit = 3
  }

  wait_for_completion = true
  timeouts { create = "10m" }
}

# ── Deployment ───────────────────────────────────────────────────────────────

resource "kubernetes_deployment" "app" {
  depends_on = [kubernetes_job.schema_init]

  metadata {
    name      = "pixeltable-app"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    replicas = 1

    selector {
      match_labels = { app = "pixeltable-app" }
    }

    template {
      metadata {
        labels = { app = "pixeltable-app" }
      }

      spec {
        container {
          name  = "app"
          image = local.image_url

          command = ["uv", "run", "uvicorn", "main:app",
            "--host", "0.0.0.0", "--port", "8000", "--workers", "4"
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
            initial_delay_seconds = 30
            period_seconds        = 10
          }

          readiness_probe {
            http_get {
              path = "/api/health"
              port = 8000
            }
            initial_delay_seconds = 10
            period_seconds        = 5
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
    name      = "pixeltable-app"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  spec {
    selector = { app = "pixeltable-app" }

    port {
      port        = 80
      target_port = 8000
    }

    type = "LoadBalancer"
  }
}
