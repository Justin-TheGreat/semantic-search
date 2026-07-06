terraform {
  required_version = ">= 1.7"
  required_providers {
    kind = {
      source  = "tehcyx/kind"
      version = "~> 0.6"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
  }
}

provider "kind" {}

# ---------------------------------------------------------------------------
# Local Kubernetes cluster (kind). NodePort 30080 is mapped to host port 8080
# so the API is reachable at http://localhost:8080 without an ingress.
# ---------------------------------------------------------------------------
resource "kind_cluster" "ragship" {
  name           = var.cluster_name
  wait_for_ready = true

  kind_config {
    kind        = "Cluster"
    api_version = "kind.x-k8s.io/v1alpha4"

    node {
      role = "control-plane"

      extra_port_mappings {
        container_port = 30080
        host_port      = 8080
      }
    }
  }
}

provider "kubernetes" {
  host                   = kind_cluster.ragship.endpoint
  cluster_ca_certificate = kind_cluster.ragship.cluster_ca_certificate
  client_certificate     = kind_cluster.ragship.client_certificate
  client_key             = kind_cluster.ragship.client_key
}

provider "helm" {
  kubernetes {
    host                   = kind_cluster.ragship.endpoint
    cluster_ca_certificate = kind_cluster.ragship.cluster_ca_certificate
    client_certificate     = kind_cluster.ragship.client_certificate
    client_key             = kind_cluster.ragship.client_key
  }
}

resource "kubernetes_namespace_v1" "ragship" {
  metadata {
    name = "ragship"
  }
}

# ---------------------------------------------------------------------------
# Secrets (never committed — value comes from var.db_password / TF_VAR_db_password)
# ---------------------------------------------------------------------------
resource "kubernetes_secret_v1" "db" {
  metadata {
    name      = "ragship-db"
    namespace = kubernetes_namespace_v1.ragship.metadata[0].name
  }
  data = {
    password = var.db_password
  }
}

# ---------------------------------------------------------------------------
# Qdrant via the official Helm chart
# ---------------------------------------------------------------------------
resource "helm_release" "qdrant" {
  name       = "qdrant"
  repository = "https://qdrant.github.io/qdrant-helm"
  chart      = "qdrant"
  namespace  = kubernetes_namespace_v1.ragship.metadata[0].name

  set {
    name  = "replicaCount"
    value = "1"
  }
}

# ---------------------------------------------------------------------------
# PostgreSQL + Redis as plain Deployments with upstream images.
# (Deliberate deviation from Bitnami charts: after Broadcom's 2025 registry
# changes Bitnami chart image references became unreliable — see ADR 0004.)
# ---------------------------------------------------------------------------
resource "kubernetes_deployment_v1" "postgres" {
  metadata {
    name      = "postgresql"
    namespace = kubernetes_namespace_v1.ragship.metadata[0].name
    labels    = { app = "postgresql" }
  }
  spec {
    replicas = 1
    selector {
      match_labels = { app = "postgresql" }
    }
    template {
      metadata {
        labels = { app = "postgresql" }
      }
      spec {
        container {
          name  = "postgres"
          image = "postgres:15-alpine"
          env {
            name  = "POSTGRES_USER"
            value = "searchuser"
          }
          env {
            name  = "POSTGRES_DB"
            value = "searchdb"
          }
          env {
            name = "POSTGRES_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret_v1.db.metadata[0].name
                key  = "password"
              }
            }
          }
          port {
            container_port = 5432
          }
          readiness_probe {
            exec {
              command = ["pg_isready", "-U", "searchuser", "-d", "searchdb"]
            }
            period_seconds = 5
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "postgres" {
  metadata {
    name      = "postgresql"
    namespace = kubernetes_namespace_v1.ragship.metadata[0].name
  }
  spec {
    selector = { app = "postgresql" }
    port {
      port        = 5432
      target_port = 5432
    }
  }
}

resource "kubernetes_deployment_v1" "redis" {
  metadata {
    name      = "redis"
    namespace = kubernetes_namespace_v1.ragship.metadata[0].name
    labels    = { app = "redis" }
  }
  spec {
    replicas = 1
    selector {
      match_labels = { app = "redis" }
    }
    template {
      metadata {
        labels = { app = "redis" }
      }
      spec {
        container {
          name  = "redis"
          image = "redis:7-alpine"
          args  = ["redis-server", "--maxmemory", "256mb", "--maxmemory-policy", "allkeys-lru"]
          port {
            container_port = 6379
          }
          readiness_probe {
            exec {
              command = ["redis-cli", "ping"]
            }
            period_seconds = 5
          }
        }
      }
    }
  }
}

resource "kubernetes_service_v1" "redis" {
  metadata {
    name      = "redis"
    namespace = kubernetes_namespace_v1.ragship.metadata[0].name
  }
  spec {
    selector = { app = "redis" }
    port {
      port        = 6379
      target_port = 6379
    }
  }
}

# ---------------------------------------------------------------------------
# The RAGShip app from the local Helm chart.
# wait = false because the ragship:local image is side-loaded with
# `kind load docker-image` after the cluster exists; pods recover on their own.
# ---------------------------------------------------------------------------
resource "helm_release" "ragship" {
  name      = "ragship"
  chart     = "${path.module}/../../deploy/helm/ragship"
  namespace = kubernetes_namespace_v1.ragship.metadata[0].name
  wait      = false

  depends_on = [
    helm_release.qdrant,
    kubernetes_deployment_v1.postgres,
    kubernetes_deployment_v1.redis,
    kubernetes_secret_v1.db,
  ]
}
