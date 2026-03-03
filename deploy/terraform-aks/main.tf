terraform {
  required_version = ">= 1.5"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
  }
}

provider "azurerm" {
  features {}
}

# ── Resource Group ───────────────────────────────────────────────────────────

resource "azurerm_resource_group" "rg" {
  name     = var.resource_group_name
  location = var.location
}

# ── Container Registry ───────────────────────────────────────────────────────

resource "azurerm_container_registry" "acr" {
  name                = replace(var.cluster_name, "-", "")
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  sku                 = "Basic"
  admin_enabled       = true
}

# ── AKS Cluster ──────────────────────────────────────────────────────────────

resource "azurerm_kubernetes_cluster" "aks" {
  name                = var.cluster_name
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  dns_prefix          = var.cluster_name

  default_node_pool {
    name       = "default"
    node_count = var.node_count
    vm_size    = var.vm_size

    enable_auto_scaling = true
    min_count           = 1
    max_count           = var.node_count * 2
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin = "azure"
  }
}

# Grant AKS access to ACR
resource "azurerm_role_assignment" "aks_acr" {
  principal_id                     = azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
  role_definition_name             = "AcrPull"
  scope                            = azurerm_container_registry.acr.id
  skip_service_principal_aad_check = true
}

# ── Kubernetes provider ──────────────────────────────────────────────────────

provider "kubernetes" {
  host                   = azurerm_kubernetes_cluster.aks.kube_config[0].host
  client_certificate     = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].client_certificate)
  client_key             = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].client_key)
  cluster_ca_certificate = base64decode(azurerm_kubernetes_cluster.aks.kube_config[0].cluster_ca_certificate)
}

# ── K8s Namespace ────────────────────────────────────────────────────────────

resource "kubernetes_namespace" "app" {
  metadata {
    name = "pixeltable"
  }
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
    storage_class_name = "managed-csi"

    resources {
      requests = {
        storage = "50Gi"
      }
    }
  }
}

# ── Deployment ───────────────────────────────────────────────────────────────

locals {
  image_url = "${azurerm_container_registry.acr.login_server}/pixeltable-starter:latest"
}

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
      match_labels = { app = "pixeltable-starter" }
    }

    template {
      metadata {
        labels = { app = "pixeltable-starter" }
      }

      spec {
        container {
          name  = "app"
          image = local.image_url

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
    selector = { app = "pixeltable-starter" }

    port {
      port        = 80
      target_port = 8000
    }

    type = "LoadBalancer"
  }
}
