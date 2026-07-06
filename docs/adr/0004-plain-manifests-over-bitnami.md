# ADR 0004 — Postgres/Redis via plain Kubernetes manifests instead of Bitnami charts

**Status:** accepted

## Context

The original plan deployed PostgreSQL and Redis with Bitnami Helm charts.
After Broadcom's August 2025 registry changes, Bitnami chart image references
(docker.io/bitnami/*) became unreliable — most versioned images moved to a
legacy registry and the charts frequently fail to pull.

## Decision

Provision Postgres and Redis as plain `Deployment` + `Service` resources
directly in Terraform (kubernetes provider), using the same upstream images
the compose stack already pins (`postgres:15-alpine`, `redis:7-alpine`).
Qdrant keeps its official first-party Helm chart, so the stack still
demonstrates Terraform-driven Helm releases.

## Consequences

- No dependency on a third-party chart vendor for stateful services; image
  parity between compose and cluster.
- Lost chart conveniences (built-in PVC templates, metrics sidecars). Data in
  the cluster is ephemeral (emptyDir) — acceptable for a throwaway local lab
  where `terraform destroy` is routine; a real deployment would add PVCs.
