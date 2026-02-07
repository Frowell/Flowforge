# Kubernetes Manifests — Agent Rules

> Parent rules: [`/workspace/agents.md`](../agents.md) | Terraform: [`/workspace/terraform/agents.md`](../terraform/agents.md)

## Purpose

Kubernetes resource definitions for deploying FlowForge. Uses Kustomize for environment-specific overlays.

## Directory Structure

```
k8s/
├── base/
│   ├── kustomization.yaml    # Base resources (all environments)
│   ├── namespace.yaml        # flowforge namespace
│   ├── infra/                # Backing services (PostgreSQL, Redis, ClickHouse, etc.)
│   └── app/                  # Application (backend, frontend deployments)
└── overlays/
    ├── dev/                  # Dev: default resources, no autoscaling
    │   ├── kustomization.yaml
    │   └── resource-limits.yaml
    └── prod/                 # Prod: HPA, PDB, Ingress, resource limits
        ├── kustomization.yaml
        ├── resource-limits.yaml
        ├── hpa-backend.yaml
        ├── hpa-frontend.yaml
        ├── pdb-backend.yaml
        ├── pdb-frontend.yaml
        ├── ingress.yaml
        └── backend-config-patch.yaml
```

## Overlay Strategy

| Overlay | Autoscaling | Resources | Ingress | Backing Services |
|---------|-------------|-----------|---------|------------------|
| `dev` | None | Minimal | None | In-cluster (StatefulSets) |
| `prod` | HPA (CPU 70%) | Production limits | TLS via cert-manager | GCP managed (Cloud SQL, Memorystore) |

## Production Notes

In production, PostgreSQL and Redis are **GCP managed services** (Cloud SQL, Memorystore) — not in-cluster pods. The prod overlay patches backend config to use external connection strings from Secret Manager.

ClickHouse and Materialize remain self-hosted on GKE (no managed equivalent).

## Resource Limits

| Component | Request (CPU/Mem) | Limit (CPU/Mem) |
|-----------|-------------------|-----------------|
| Backend | 500m / 512Mi | 2000m / 1Gi |
| Frontend | 200m / 128Mi | 500m / 256Mi |

## Rules

- **Kustomize only.** No Helm charts. Overlays patch the base resources.
- **Namespace `flowforge`** for all resources.
- **No secrets in manifests.** Secret values come from K8s Secrets (populated by Secret Manager + Workload Identity in prod, or env vars in dev).
- **Health probes.** All deployments must define liveness and readiness probes.
  - Backend: `/health/live` (liveness), `/health/ready` (readiness)
  - Frontend: HTTP GET on `/` (nginx)
- **Labels.** All resources use `app.kubernetes.io/name`, `app.kubernetes.io/component`, `app.kubernetes.io/part-of: flowforge`.
