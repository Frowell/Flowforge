# RFC 0003: Data Pipeline Benchmarking

**Status:** Accepted
**Author:** Architecture team
**Date:** 2026-02-11

## Summary

Add an automated benchmarking module (`bench/`) that measures and enforces latency SLOs across the serving layer — Redis (< 1ms), Materialize (< 10ms), ClickHouse (< 500ms), and WebSocket end-to-end (< 200ms) — using Locust for load generation, Toxiproxy for chaos injection, and Prometheus + Grafana for observability.

## Motivation

FlowForge defines latency SLOs across the serving layer but has no automated way to measure or enforce them. The backend already emits Prometheus metrics (`backend/app/core/metrics.py`) and the query router instruments execution latency, but there are no load tests, no SLO regression gates, no chaos testing, and no P95/P99 reporting.

Without benchmarks:

1. **SLO drift goes undetected.** A seemingly innocuous change to the query compiler or cache TTL can regress P99 latency by 10x, and no test catches it until users complain.
2. **Capacity planning is guesswork.** We don't know how many concurrent WebSocket viewers the system supports, or how dashboard load time scales with widget count.
3. **Failure modes are untested.** When ClickHouse goes down for 15 seconds, does the backend degrade gracefully or cascade-fail? We have no data.
4. **CI has no performance gate.** A PR that passes unit tests but doubles query latency merges without friction.

## Detailed Design

### 1. Benchmark Scenarios

Four scenarios cover the key performance dimensions:

#### Scenario 1: Event Rate Sweep

Locust `HttpUser` hitting `GET /api/v1/widgets/{id}/data` and `POST /api/v1/preview` with a step ramp from 5 to 100 concurrent users (60s per stage). Measures P95/P99 query latency at each concurrency level.

**SLO pass criteria:**
- Redis P99 < 5ms
- Materialize P99 < 50ms
- ClickHouse P99 < 2s
- HTTP endpoint P99 < 3s

#### Scenario 2: Widget Count

Seed dashboards with 1, 5, 10, 25, and 50 widgets. Each simulated user loads all widgets sequentially (simulates the `Promise.all()` on dashboard mount). Measures total dashboard load time.

**SLO pass criteria:**
- 10-widget dashboard P95 < 2s
- 25-widget dashboard P95 < 5s
- 50-widget dashboard P95 < 10s

#### Scenario 3: WebSocket Viewers

Custom Locust `User` class with a gevent-compatible WebSocket client. Connects to `ws://backend:8000/ws`, subscribes to a broadcast channel, and measures delivery latency (`receive_ts - publish_ts`).

**SLO pass criteria:**
- 100 viewers P95 < 50ms
- 250 viewers P95 < 100ms
- 500 viewers P95 < 200ms

#### Scenario 4: Store Failure (Chaos)

Same request pattern as event rate, with Toxiproxy chaos injections on a timed schedule:
- t=30s: ClickHouse timeout for 15s
- t=60s: Redis 500ms latency for 15s
- t=90s: Materialize timeout for 15s
- t=120s: Redis latency + ClickHouse down simultaneously for 10s

**SLO pass criteria:**
- Error rate < 10% during any single failure
- Recovery time < 30s after toxic removal
- No cascade failures (one store failing must not crash another)

### 2. Tooling

**Locust** for load generation — Python-based, supports custom User classes for WebSocket, has built-in web UI and CSV/JSON export, integrates with Prometheus via `locust-plugins`.

**Toxiproxy** for chaos injection — TCP-level proxy that can inject latency, timeouts, bandwidth limits, and connection resets. Controlled via REST API, perfect for scripted chaos schedules.

**Prometheus** for metrics collection — scrapes the backend's `/metrics` endpoint plus Toxiproxy's metrics. Provides the query backend for SLO checks.

**Grafana** for visualization — pre-provisioned dashboards with 6 rows covering query latency, WebSocket, cache, HTTP, SLO compliance, and chaos events.

### 3. Infrastructure

A dedicated `bench/docker-compose.bench.yml` adds Toxiproxy, Prometheus, Grafana, and Locust (master + 2 workers) to the existing dev container network. When the bench profile is active, backend environment variables are overridden to route through Toxiproxy proxies.

### 4. Backend Metrics Additions

Five new Prometheus metrics fill observability gaps:

| Metric | Type | Purpose |
|--------|------|---------|
| `flowforge_websocket_message_delivery_seconds` | Histogram | Time from Redis message receipt to `send_text()` completion |
| `flowforge_cache_operation_duration_seconds` | Histogram | Duration of Redis cache get/set operations |
| `flowforge_live_data_mode` | Gauge | Current mode per widget (1=poll, 2=subscribe) |
| `flowforge_store_health_check_duration_seconds` | Histogram | Health check latency per store |
| `flowforge_store_health_status` | Gauge | Store health (1=healthy, 0=unhealthy) |

### 5. CI Integration

A nightly GitHub Actions workflow (`bench.yml`) runs all four scenarios against a full infrastructure stack, checks SLOs via Prometheus queries, and uploads a Prometheus snapshot as an artifact. Manual `workflow_dispatch` is also supported for on-demand benchmarking.

### 6. SLO Gate

`bench/scripts/check-slo.py` queries Prometheus for P95/P99 values across all metric families, compares them against threshold constants, prints a summary table, and exits non-zero on any breach. This script runs as the final step in both local `make bench-slo` and the CI workflow.

## Alternatives Considered

See [ADR 0011: Locust for Load Testing](../decisions/0011-locust-load-testing.md) for the load testing tool comparison (Locust vs k6 vs custom asyncio vs JMeter).

See [ADR 0012: Toxiproxy for Chaos Testing](../decisions/0012-toxiproxy-chaos-testing.md) for the chaos injection tool comparison (Toxiproxy vs Docker controls vs Pumba vs Chaos Mesh).

## Open Questions

*All resolved during design:*

- ~~Should benchmarks run in CI or only locally?~~ Both — nightly CI plus local `make bench-*` targets.
- ~~Should we use k6 for its lower overhead?~~ No — Locust's Python ecosystem and custom User class support are more valuable for WebSocket scenarios. See ADR 0011.
- ~~Should chaos testing use Kubernetes-native tools?~~ No — Toxiproxy works in both Docker Compose and K8s, keeping dev/CI parity. See ADR 0012.
