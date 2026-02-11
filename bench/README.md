# FlowForge Benchmarks

Automated benchmarking module for measuring and enforcing latency SLOs across the FlowForge serving layer.

## Quick Start

```bash
# Start benchmark infrastructure (Toxiproxy, Prometheus, Grafana)
make bench-up

# Start the backend (in another terminal)
make backend

# Run all 4 scenarios
make bench-run

# Check SLO compliance
make bench-slo

# Stop infrastructure
make bench-down
```

## SLO Targets

| Store | Metric | SLO |
|-------|--------|-----|
| Redis | Point lookup P99 | < 5ms |
| Materialize | Live query P99 | < 50ms |
| ClickHouse | Analytical query P99 | < 2s |
| HTTP endpoint | Overall P99 | < 3s |
| WebSocket | Delivery P95 | < 200ms |

## Scenarios

### 1. Event Rate Sweep (`make bench-event-rate`)

Measures P95/P99 query latency at varying concurrency levels. Step ramp from 5 to 100 concurrent users, 60 seconds per stage.

### 2. Widget Count (`make bench-widgets`)

Dashboard load time vs. widget count. Seeds dashboards with 1, 5, 10, 25, and 50 widgets and measures total load time.

### 3. WebSocket Viewers (`make bench-ws`)

WebSocket delivery latency vs. concurrent viewer count. Ramp from 10 to 500 concurrent connections.

### 4. Store Failure / Chaos (`make bench-chaos`)

Injects TCP-level failures via Toxiproxy on a timed schedule:
- t=30s: ClickHouse timeout (15s)
- t=60s: Redis 500ms latency (15s)
- t=90s: Materialize timeout (15s)
- t=120s: Redis + ClickHouse simultaneous failure (10s)

## Infrastructure

| Service | Port | Purpose |
|---------|------|---------|
| Toxiproxy | 8474 (API) | TCP fault injection |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3001 | Benchmark dashboards |
| Locust | 8089 | Load test web UI (when using compose) |

## Architecture

```
bench/
├── docker-compose.bench.yml     # Bench-specific services
├── locustfiles/
│   ├── common/                  # Shared auth, seed, WebSocket, toxics helpers
│   ├── shapes/                  # Configurable load shapes
│   ├── scenario_event_rate.py   # Scenario 1
│   ├── scenario_widget_count.py # Scenario 2
│   ├── scenario_ws_viewers.py   # Scenario 3
│   └── scenario_store_failure.py# Scenario 4
├── toxiproxy/config.json        # Proxy definitions
├── prometheus/prometheus.yml     # Scrape config
├── grafana/provisioning/        # Datasources + dashboards
└── scripts/
    ├── run-bench.sh             # Orchestrator
    ├── check-slo.py             # SLO gate
    └── seed-bench-data.py       # Test data setup
```

## Grafana Dashboard

Open `http://localhost:3001` after `make bench-up`. The pre-provisioned dashboard has 6 rows:

1. **Query Latency** — Execution duration heatmap + P95/P99 time series
2. **WebSocket** — Active connections, delivery latency, message rate
3. **Cache** — Hit/miss ratio, operation duration
4. **HTTP** — Endpoint latency heatmap, error rate
5. **SLO Compliance** — Current P95 vs. threshold (green/red)
6. **Chaos** — Store health status, error rate during failures

## CI

The benchmark workflow (`.github/workflows/bench.yml`) runs nightly at 03:00 UTC and can be triggered manually via `workflow_dispatch`. It:

1. Starts all backing stores as GitHub Actions services
2. Seeds benchmark data
3. Runs all 4 scenarios
4. Checks SLO compliance against Prometheus
5. Uploads results as artifacts

## Design Decisions

- [RFC 0003: Data Pipeline Benchmarking](../docs/rfcs/0003-data-pipeline-benchmarking.md)
- [ADR 0011: Locust for Load Testing](../docs/decisions/0011-locust-load-testing.md)
- [ADR 0012: Toxiproxy for Chaos Testing](../docs/decisions/0012-toxiproxy-chaos-testing.md)
