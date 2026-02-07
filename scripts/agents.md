# Scripts — Agent Rules

> Parent rules: [`/workspace/agents.md`](../agents.md)

## Purpose

Developer utilities and operational scripts for the FlowForge development environment.

## Script Catalog

| Script | Language | Purpose |
|--------|----------|---------|
| `start-pipeline.sh` | Bash | Orchestrate full pipeline: generator, Bytewax flows, backend, frontend |
| `check-connectivity.sh` | Bash | Verify connectivity to all backing services (PG, Redis, CH, MZ, Redpanda) |
| `validate-schema-parity.sh` | Bash | Run Python + TypeScript schema engines against shared fixtures, verify identical output |
| `seed_historical.py` | Python | Seed ClickHouse with 6 months of historical trade data |
| `setup-cluster.sh` | Bash | K8s cluster setup for local development |
| `scaffold.sh` | Bash | Generate initial project structure |
| `install-tools.sh` | Bash | Install development tools and CLI utilities |

## Conventions

### Bash Scripts

- Start with `#!/usr/bin/env bash` and `set -e` (fail on first error)
- Use colored log functions (`log_info`, `log_success`, `log_warn`, `log_error`) for consistent output
- Detect environment (devcontainer vs native) and adjust hostnames accordingly
- Store PIDs in `.pipeline-pids/` for clean shutdown
- Support `--stop` and `--status` flags for lifecycle management

### Python Scripts

- Use the same Python version as the backend (3.12+)
- Import connection settings from environment variables, not hardcoded values
- Scripts are standalone — they do not import from `backend/app/`

## Rules

- **Idempotent.** Scripts should be safe to run multiple times without side effects.
- **No secrets in scripts.** Connection strings come from environment variables.
- **Fail loudly.** Use `set -e` in bash. Print clear error messages before exiting.
- **Document usage.** Each script should print help text when called with `--help` or no arguments (where applicable).
