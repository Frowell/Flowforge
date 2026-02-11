# GitHub Actions CI/CD — Agent Rules

> Parent rules: [`/workspace/agents.md`](../../agents.md) | Infrastructure: [`/workspace/terraform/agents.md`](../../terraform/agents.md)

## Overview

FlowForge uses **GitHub Actions** for CI/CD. Workflows cover linting, testing, building Docker images, deploying to GKE, and managing Terraform infrastructure changes.

This document defines the CI/CD pipeline requirements. It does NOT contain workflow YAML — it is the specification that guides workflow implementation.

---

## Workflows

| Workflow | File | Trigger | Purpose |
|----------|------|---------|---------|
| CI | `ci.yml` | PR to `main` | Lint, typecheck, test (backend + frontend) |
| Build | `build.yml` | Push to `main` | Build Docker images, push to Artifact Registry |
| Deploy Dev | `deploy-dev.yml` | Push to `main` (after build) | Auto-deploy to dev GKE cluster |
| Deploy Staging | `deploy-staging.yml` | Manual dispatch / git tag | Deploy to staging GKE cluster |
| Deploy Prod | `deploy-prod.yml` | Manual dispatch (approval required) | Deploy to prod GKE cluster |
| Terraform Plan | `terraform-plan.yml` | PR modifying `terraform/**` | Run `terraform plan` on all environments |
| Terraform Apply | `terraform-apply.yml` | Push to `main` modifying `terraform/**` | `terraform apply` on dev; manual for staging/prod |
| Benchmarks | `bench.yml` | Nightly 03:00 UTC + manual dispatch | Run load tests, check SLO compliance, upload results |

---

## CI Workflow (`ci.yml`)

**Trigger**: Pull request to `main`

### Backend Steps

1. **Setup**: Python 3.12, install dependencies from `pyproject.toml`
2. **Lint**: `ruff check backend/`
3. **Format check**: `ruff format --check backend/`
4. **Type check**: `mypy backend/app/` (if configured)
5. **Test**: `pytest backend/tests/ -v --tb=short`
   - Tests must NOT require running databases — all external stores mocked
   - Coverage report uploaded as artifact

### Frontend Steps

1. **Setup**: Node 22, `npm ci` in `frontend/`
2. **Lint**: `npx eslint src/`
3. **Type check**: `npx tsc --noEmit`
4. **Format check**: `npx prettier --check src/`
5. **Test**: `npx vitest run`

### Rules

- Backend and frontend jobs run **in parallel**
- PR cannot merge if any check fails
- No secrets required for CI — all tests use mocks

---

## Build Workflow (`build.yml`)

**Trigger**: Push to `main` branch

### Steps

1. **Checkout** code
2. **Authenticate** to GCP via Workload Identity Federation (no JSON key files)
3. **Configure** Docker for Artifact Registry (`gcloud auth configure-docker <region>-docker.pkg.dev`)
4. **Build backend image**: Multi-stage Dockerfile
   - Builder stage: install Python dependencies
   - Runtime stage: slim Python image + app code
5. **Build frontend image**: Multi-stage Dockerfile
   - Build stage: `npm ci && npm run build`
   - Runtime stage: nginx serving static files
6. **Tag** images with git SHA and `latest`
7. **Push** to Artifact Registry: `<region>-docker.pkg.dev/<project>/flowforge/<service>:<tag>`

### Image Tags

| Tag | Mutability | Purpose |
|-----|-----------|---------|
| `<git-sha>` | Immutable | Exact version tracking, rollback target |
| `latest` | Mutable | Points to most recent main build |

### Rules

- Build must complete successfully before deploy workflows trigger
- Both images (backend + frontend) build **in parallel**
- Build cache: Use Docker layer caching via `actions/cache` or GHA cache mounts
- GCP authentication via **Workload Identity Federation** — no service account JSON keys in GitHub Secrets

---

## Deploy Workflows

### Deploy Dev (`deploy-dev.yml`)

**Trigger**: Successful completion of `build.yml` on `main`

1. Authenticate to GCP via Workload Identity Federation
2. Get GKE credentials: `gcloud container clusters get-credentials`
3. Update image tags in Kustomize overlays or run `kubectl set image`
4. Wait for rollout: `kubectl rollout status deployment/backend -n flowforge`
5. Run health check: `curl https://dev.flowforge.io/health/ready`
6. Post status to commit or Slack

### Deploy Staging (`deploy-staging.yml`)

**Trigger**: Manual workflow dispatch or git tag matching `v*`

- Same steps as dev deploy, targeting staging GKE cluster
- Requires specifying image tag (defaults to `latest`)

### Deploy Prod (`deploy-prod.yml`)

**Trigger**: Manual workflow dispatch only

- **Requires approval** via GitHub Environments protection rule
- Same deployment steps, targeting prod GKE cluster
- Must specify exact image tag (git SHA) — no `latest` in prod
- Post-deploy smoke test: verify `/health/ready` returns 200

### Deployment Strategy

- **Strategy**: Rolling update (`maxUnavailable: 0`, `maxSurge: 1`)
- **Health gates**: Deployment only marked successful after readiness probe passes
- **Rollback**: `kubectl rollout undo deployment/<service> -n flowforge` if health check fails

---

## Terraform Workflows

### Terraform Plan (`terraform-plan.yml`)

**Trigger**: PR modifying any file under `terraform/`

1. Setup Terraform (version from `required_version`)
2. Authenticate to GCP
3. For each environment (`dev`, `staging`, `prod`):
   - `terraform init -backend-config=...`
   - `terraform plan -out=plan.tfplan`
   - Post plan output as PR comment (truncated if too long)
4. PR reviewers can see exactly what will change in each environment

### Terraform Apply (`terraform-apply.yml`)

**Trigger**: Push to `main` modifying `terraform/`

1. **Dev**: Auto-apply (`terraform apply -auto-approve`)
2. **Staging**: Manual approval step, then apply
3. **Prod**: Manual approval step (via GitHub Environments), then apply

### Rules

- Never run `terraform apply` without a prior `terraform plan`
- State locking via GCS backend prevents concurrent applies
- Terraform version pinned in workflow to match `required_version`

---

## GCP Authentication

All GitHub Actions workflows authenticate to GCP via **Workload Identity Federation** — no long-lived service account keys.

### Setup

1. GCP Workload Identity Pool: `github-actions-pool`
2. Provider: `github-actions-provider` configured for the repo
3. Service Account: `github-actions@<project>.iam.gserviceaccount.com`
4. Permissions: Artifact Registry Writer, GKE Developer, Terraform state bucket read/write

### GitHub Actions Configuration

```yaml
# In workflow
- uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: projects/<num>/locations/global/workloadIdentityPools/github-actions-pool/providers/github-actions-provider
    service_account: github-actions@<project>.iam.gserviceaccount.com
```

---

## GitHub Secrets & Variables

### Secrets (per environment)

| Secret | Purpose |
|--------|---------|
| None (Workload Identity Federation) | GCP auth uses OIDC — no stored credentials |

### Variables

| Variable | Purpose |
|----------|---------|
| `GCP_PROJECT_DEV` | Dev GCP project ID |
| `GCP_PROJECT_STAGING` | Staging GCP project ID |
| `GCP_PROJECT_PROD` | Prod GCP project ID |
| `GCP_REGION` | GCP region (e.g., `us-central1`) |
| `GKE_CLUSTER_NAME` | GKE cluster name per environment |
| `ARTIFACT_REGISTRY_REPO` | Artifact Registry repository path |

---

## Environments (GitHub Environments)

| Environment | Protection Rules |
|-------------|-----------------|
| `dev` | None — auto-deploy on main push |
| `staging` | Required reviewers (1 approval) |
| `prod` | Required reviewers (2 approvals) + deployment branches (`main` only) |

---

## Constraints & Rules

1. **No service account JSON keys** — all GCP auth via Workload Identity Federation
2. **No secrets in workflow logs** — use `::add-mask::` for any dynamic secrets
3. **Pin action versions** to SHA, not tags (e.g., `uses: actions/checkout@<sha>`)
4. **Prod deploys require explicit image SHA** — never deploy `latest` to prod
5. **Terraform state is never committed** to the repository
6. **CI must pass before merge** — branch protection rules enforce this
