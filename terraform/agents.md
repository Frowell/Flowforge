# Terraform Infrastructure — Agent Rules

> Parent rules: [`/workspace/agents.md`](../agents.md)

## Overview

FlowForge production infrastructure runs on **Google Cloud Platform (GCP)**, managed by **Terraform**. Each environment (dev, staging, prod) lives in its own GCP project for billing isolation and IAM boundary separation.

This document defines the infrastructure requirements. It does NOT contain Terraform code — it is the specification that guides Terraform module implementation.

---

## GCP Services

| Service | GCP Resource | Purpose |
|---------|-------------|---------|
| Kubernetes | GKE Standard | Application workloads + self-hosted ClickHouse/Materialize |
| PostgreSQL | Cloud SQL for PostgreSQL 16 | App metadata (workflows, dashboards, widgets, users) |
| Redis | Memorystore for Redis | Cache (schema registry, preview) + pub/sub (WebSocket fan-out) |
| Container Registry | Artifact Registry | Docker images for backend + frontend |
| Networking | VPC + subnets + Cloud NAT | Private cluster networking |
| DNS | Cloud DNS | Service DNS records |
| Secrets | Secret Manager | DB passwords, Keycloak secrets, API keys, JWT signing keys |
| IAM | Workload Identity | Pod-level GCP access without JSON key files |
| State | GCS bucket | Terraform remote state with locking |
| Load Balancing | GKE Ingress (Gateway API or NGINX Ingress Controller) | External HTTPS traffic routing |
| Monitoring | Cloud Monitoring + Cloud Logging | Infrastructure-level observability |

---

## Module Structure

```
terraform/
├── modules/
│   ├── networking/     # VPC, subnets, Cloud NAT, firewall rules
│   ├── gke/            # GKE cluster + node pools
│   ├── cloudsql/       # Cloud SQL PostgreSQL instance
│   ├── memorystore/    # Memorystore Redis instance
│   ├── registry/       # Artifact Registry repository
│   ├── dns/            # Cloud DNS zone + records
│   ├── secrets/        # Secret Manager secrets
│   └── iam/            # Service accounts, Workload Identity bindings
├── environments/
│   ├── dev/            # Smallest footprint, cost-optimized
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── terraform.tfvars
│   ├── staging/        # Mirrors prod topology, smaller instances
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── outputs.tf
│   │   └── terraform.tfvars
│   └── prod/           # Full production configuration
│       ├── main.tf
│       ├── variables.tf
│       ├── outputs.tf
│       └── terraform.tfvars
├── backend.tf          # GCS remote state configuration
└── agents.md           # This file — infrastructure requirements
```

Each environment directory calls the same shared modules with different variable values. No environment-specific logic in modules.

---

## Environment Sizing

| Resource | Dev | Staging | Prod |
|----------|-----|---------|------|
| GKE node pool | 2x `e2-standard-4` | 3x `e2-standard-4` | 3x `e2-standard-8` (+ autoscale to 6) |
| Cloud SQL | `db-f1-micro`, no HA, 10GB SSD | `db-custom-2-4096`, no HA, 20GB SSD | `db-custom-4-8192`, HA (regional), 50GB SSD |
| Memorystore | 1GB Basic tier | 2GB Basic tier | 5GB Standard tier (HA, automatic failover) |
| ClickHouse (self-hosted) | 1 replica, 50GB SSD PD | 1 replica, 100GB SSD PD | 3 replicas, 500GB SSD PD each |
| Materialize (self-hosted) | 1 replica, 10GB SSD PD | 1 replica, 20GB SSD PD | 2 replicas, 50GB SSD PD each |

### Cost Optimization (Dev)

- Use preemptible/spot nodes for GKE in dev
- Cloud SQL `db-f1-micro` is shared-core (acceptable for dev)
- No HA for any service in dev
- Consider scheduled shutdown (scale node pool to 0 outside business hours)

---

## GKE Cluster

### Cluster Configuration

- **Type**: GKE Standard (not Autopilot — need StatefulSet control for ClickHouse/Materialize)
- **Kubernetes version**: Latest stable release channel
- **Private cluster**: Enabled — no public IPs on nodes
- **Master authorized networks**: Restricted to VPN/bastion CIDR + GitHub Actions runner IPs
- **Binary Authorization**: Enabled in prod (images must come from Artifact Registry)
- **Workload Identity**: Enabled cluster-wide

### Node Pools

| Pool | Purpose | Machine type | Scaling |
|------|---------|-------------|---------|
| `default` | Application workloads (backend, frontend, Keycloak) | Per environment sizing | Autoscaler in prod |
| `stateful` | ClickHouse + Materialize + Redpanda StatefulSets | `e2-standard-8` (prod) | Fixed count |

The `stateful` pool uses node labels (`flowforge.io/pool=stateful`) and taints to ensure only StatefulSet workloads land on these nodes.

### Namespaces

| Namespace | Contents |
|-----------|----------|
| `flowforge` | Backend, frontend, Keycloak deployments |
| `flowforge-data` | ClickHouse, Materialize, Redpanda StatefulSets |
| `monitoring` | Prometheus, Grafana (if self-hosted) |

---

## Networking

### VPC Design

- **One VPC per environment** (no shared VPC for simplicity)
- Primary subnet for GKE nodes: `/20` (4,096 IPs)
- Secondary range for pods: `/14` (262,144 IPs)
- Secondary range for services: `/20` (4,096 IPs)

### Private Connectivity

- **Cloud NAT**: All outbound traffic from GKE nodes routes through Cloud NAT (no public IPs on nodes)
- **Private Service Access**: Enabled for Cloud SQL and Memorystore private IP connectivity
- **Cloud SQL**: Private IP only — no public IP, no Cloud SQL Auth Proxy needed when using private networking + Workload Identity
- **Memorystore**: Private IP only — accessible from within VPC

### Firewall Rules

- Allow internal traffic within VPC (GKE nodes ↔ Cloud SQL ↔ Memorystore)
- Allow GKE master to node communication (required for private clusters)
- Deny all ingress from internet to nodes (traffic enters via load balancer only)
- Allow health check probes from GCP load balancer ranges

### Load Balancing

- **External HTTPS LB**: Frontend + embed endpoints (terminates TLS with managed certificate)
- **Internal LB**: Backend API (cluster-internal, accessed via Ingress from frontend pods or via external LB path routing)
- TLS certificates managed via Google-managed SSL certificates or cert-manager with Let's Encrypt

---

## Cloud SQL (PostgreSQL)

- **Version**: PostgreSQL 16
- **Purpose**: App metadata only (workflows, dashboards, widgets, users, API keys)
- **Private IP**: Enabled via Private Service Access — no public IP
- **Connection**: Backend pods connect directly via private IP (no Cloud SQL Auth Proxy sidecar needed)
- **Auth**: Workload Identity for IAM database authentication, or username/password from Secret Manager
- **Backups**: Automated daily backups, 7-day retention (prod: 30 days)
- **Flags**: `max_connections=200`, `shared_buffers` sized to instance memory
- **Maintenance window**: Sunday 03:00 UTC (prod)
- **HA**: Regional (prod only) — automatic failover to standby in different zone

### Database Setup

- Single database: `flowforge`
- Application user: `flowforge_app` (limited to DML on app schema)
- Migration user: `flowforge_migrate` (DDL permissions for Alembic)
- Passwords stored in Secret Manager

---

## Memorystore (Redis)

- **Version**: Redis 7.x
- **Purpose**: Schema registry cache, preview result cache, WebSocket pub/sub fan-out
- **Tier**: Basic (dev/staging), Standard with HA (prod)
- **Private IP**: Accessible only within VPC
- **Auth**: AUTH string stored in Secret Manager (enabled in prod)
- **Memory policy**: `allkeys-lru`
- **Maxmemory**: Per environment sizing table

---

## Self-Hosted ClickHouse on GKE

ClickHouse is self-hosted on GKE as a StatefulSet because the application requires direct SQL access to specific table schemas populated by the data pipeline.

### StatefulSet Configuration

- **Image**: `clickhouse/clickhouse-server:24.x` (pin to specific minor version)
- **Replicas**: Per environment sizing table
- **Storage**: `pd-ssd` PersistentVolumes via StorageClass
- **Resources** (prod per replica):
  - Requests: 4 CPU, 16Gi memory
  - Limits: 8 CPU, 32Gi memory
- **Resources** (dev per replica):
  - Requests: 1 CPU, 4Gi memory
  - Limits: 2 CPU, 8Gi memory

### Access Pattern

- **Read-only from FlowForge app** — the app NEVER writes to ClickHouse
- The data pipeline (separate workstream) populates tables via Kafka/Redpanda ingestion
- Backend pods connect via HTTP protocol (port 8123) using `clickhouse-connect`
- ClickHouse credentials stored in Secret Manager, injected as environment variables via Workload Identity

### Persistence

- PVCs use `pd-ssd` StorageClass with `reclaimPolicy: Retain`
- Volume size per environment sizing table
- Data survives pod restarts and rescheduling

### Networking

- ClusterIP Service for internal access: `clickhouse.flowforge-data.svc.cluster.local:8123`
- No external exposure — ClickHouse is only accessible from within the GKE cluster

---

## Self-Hosted Materialize on GKE

Materialize provides real-time materialized views for live positions, quotes, and P&L.

### StatefulSet Configuration

- **Image**: `materialize/materialized:latest` (pin to specific version in prod)
- **Replicas**: Per environment sizing table
- **Storage**: `pd-ssd` PersistentVolumes
- **Resources** (prod per replica):
  - Requests: 2 CPU, 8Gi memory
  - Limits: 4 CPU, 16Gi memory
- **Resources** (dev per replica):
  - Requests: 1 CPU, 2Gi memory
  - Limits: 2 CPU, 4Gi memory

### Dependencies

- Materialize sources connect to Redpanda/Kafka (also self-hosted on GKE in `flowforge-data` namespace)
- Redpanda StatefulSet required alongside Materialize

### Access Pattern

- **Read-only from FlowForge app** — the app queries materialized views, never creates them
- Backend pods connect via PG wire protocol (port 6875) using asyncpg
- Connection string: `postgresql://materialize@materialize.flowforge-data.svc.cluster.local:6875/materialize`

### Networking

- ClusterIP Service: `materialize.flowforge-data.svc.cluster.local:6875`
- No external exposure

---

## Self-Hosted Redpanda on GKE

Redpanda provides Kafka-compatible streaming for the data pipeline and as a source for Materialize.

### StatefulSet Configuration

- **Image**: `redpandadata/redpanda:latest` (pin in prod)
- **Replicas**: 1 (dev/staging), 3 (prod)
- **Storage**: `pd-ssd` PersistentVolumes
- **Resources** (prod per broker):
  - Requests: 2 CPU, 4Gi memory
  - Limits: 4 CPU, 8Gi memory

### Networking

- Kafka API: `redpanda.flowforge-data.svc.cluster.local:9092`
- Admin API: port 9644 (cluster-internal only)
- No external exposure

---

## Workload Identity

Workload Identity maps Kubernetes service accounts to GCP IAM service accounts, eliminating JSON key files.

### Service Account Mapping

| K8s Service Account | GCP Service Account | Permissions |
|---------------------|---------------------|-------------|
| `flowforge-backend` (ns: `flowforge`) | `flowforge-backend@<project>.iam` | Cloud SQL Client, Secret Manager Accessor |
| `flowforge-frontend` (ns: `flowforge`) | `flowforge-frontend@<project>.iam` | (none — static assets only) |
| `clickhouse` (ns: `flowforge-data`) | `flowforge-clickhouse@<project>.iam` | (none — no GCP API access needed) |
| `materialize` (ns: `flowforge-data`) | `flowforge-materialize@<project>.iam` | (none — no GCP API access needed) |

### Rules

- **No `GOOGLE_APPLICATION_CREDENTIALS`** in any pod — Workload Identity handles authentication
- Backend pods use the mapped GCP service account to access Cloud SQL and Secret Manager
- All GCP API calls from pods go through Workload Identity — never download or mount service account keys

---

## Secret Manager

All secrets are stored in GCP Secret Manager and accessed via Workload Identity.

### Secrets Inventory

| Secret Name | Purpose | Consumers |
|-------------|---------|-----------|
| `cloudsql-app-password` | PostgreSQL app user password | Backend pods |
| `cloudsql-migrate-password` | PostgreSQL migration user password | Migration jobs |
| `keycloak-admin-password` | Keycloak admin credentials | Keycloak deployment |
| `keycloak-db-password` | Keycloak database password | Keycloak deployment |
| `redis-auth-string` | Memorystore AUTH (prod only) | Backend pods |
| `clickhouse-password` | ClickHouse default user password | Backend pods |
| `jwt-signing-key` | JWT token signing key | Backend pods |
| `api-key-encryption-key` | Encryption key for API key storage | Backend pods |

### Rules

- Secrets are NEVER stored in Kubernetes ConfigMaps or Secrets manifests
- Secrets are NEVER committed to source control
- Pods access secrets via the Secret Manager API using Workload Identity
- Secret rotation: supported via Secret Manager versioning

---

## Artifact Registry

- **Repository type**: Docker
- **Location**: Same region as GKE cluster
- **Repository name**: `flowforge`
- **Image naming**: `<region>-docker.pkg.dev/<project>/flowforge/<service>:<tag>`
- **Tags**: Git SHA (immutable) + `latest` (mutable, points to most recent main build)
- **Cleanup policy**: Delete untagged images older than 30 days

### Images

| Image | Source |
|-------|--------|
| `backend` | `backend/Dockerfile` — multi-stage (builder + runtime) |
| `frontend` | `frontend/Dockerfile` — multi-stage (build + nginx) |

---

## DNS (Cloud DNS)

- **Zone**: Managed zone for `flowforge.io` (or project-specific subdomain)
- **Records**:
  - `app.flowforge.io` → External HTTPS LB (frontend + embed)
  - `api.flowforge.io` → External HTTPS LB (backend API)
  - Environment-specific subdomains: `dev.flowforge.io`, `staging.flowforge.io`

---

## Monitoring & Logging

- **Cloud Logging**: All GKE container logs automatically collected
- **Cloud Monitoring**: GKE cluster metrics, Cloud SQL metrics, Memorystore metrics
- **Uptime checks**: HTTPS checks on `/health/ready` endpoint (backend), frontend root
- **Alerting policies** (prod):
  - Backend error rate > 1% over 5 minutes
  - Cloud SQL CPU > 80% for 10 minutes
  - Memorystore memory usage > 90%
  - GKE node pool at max capacity
  - ClickHouse disk usage > 80%
- **Application-level observability**: Prometheus metrics scraped by Cloud Monitoring (Managed Prometheus) or self-hosted Prometheus in `monitoring` namespace

---

## Terraform State

- **Backend**: GCS bucket with state locking
- **Bucket naming**: `flowforge-terraform-state-<project-id>`
- **Prefix**: `environments/<env>/` — each environment has its own state file
- **Versioning**: Enabled on GCS bucket for state recovery
- **Access**: Only CI/CD service account and infrastructure admins can read/write state

### Backend Configuration

```hcl
# backend.tf
terraform {
  backend "gcs" {
    bucket = "flowforge-terraform-state-<project-id>"
    prefix = "environments/<env>"
  }
}
```

---

## GCP Project Structure

| Project | Environment | Purpose |
|---------|-------------|---------|
| `flowforge-dev` | dev | Development — smallest footprint, spot instances |
| `flowforge-staging` | staging | Pre-production validation — mirrors prod topology |
| `flowforge-prod` | prod | Production — HA, autoscaling, monitoring, alerting |

### Required GCP APIs (enable per project)

- `container.googleapis.com` (GKE)
- `sqladmin.googleapis.com` (Cloud SQL)
- `redis.googleapis.com` (Memorystore)
- `artifactregistry.googleapis.com` (Artifact Registry)
- `dns.googleapis.com` (Cloud DNS)
- `secretmanager.googleapis.com` (Secret Manager)
- `iam.googleapis.com` (IAM)
- `compute.googleapis.com` (Compute Engine — for GKE nodes)
- `monitoring.googleapis.com` (Cloud Monitoring)
- `logging.googleapis.com` (Cloud Logging)
- `servicenetworking.googleapis.com` (Private Service Access)

---

## Deployment Flow

```
Git push to main
  → GitHub Actions builds Docker images
  → Push to Artifact Registry (tagged with git SHA)
  → kubectl set image / Kustomize overlay update on dev GKE cluster
  → Manual promotion to staging → manual promotion to prod
```

Terraform changes follow a separate flow:

```
PR modifying terraform/
  → GitHub Actions runs terraform plan on all environments
  → Merge to main → terraform apply on dev (auto)
  → Manual terraform apply on staging → manual terraform apply on prod
```

---

## Constraints & Rules

1. **No Terraform code in this file** — this is a requirements document only
2. **Modules must be environment-agnostic** — all environment differences expressed via variables
3. **No hardcoded IPs, project IDs, or credentials** in Terraform code — use variables and data sources
4. **All resources must be tagged** with `environment`, `project=flowforge`, `managed-by=terraform`
5. **Destroy protection** enabled on Cloud SQL and GCS state bucket in prod
6. **No public IPs** on GKE nodes, Cloud SQL, or Memorystore — private networking only
7. **Terraform version**: >= 1.5, use `required_version` constraint
8. **Provider version**: Pin Google provider to specific minor version
