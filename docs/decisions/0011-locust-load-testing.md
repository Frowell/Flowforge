# 0011: Locust for Load Testing

**Status:** Accepted
**Date:** 2026-02-11
**Deciders:** Architecture team

## Context

FlowForge needs automated load testing to validate latency SLOs (Redis < 1ms, Materialize < 10ms, ClickHouse < 500ms, WebSocket < 200ms). The load testing tool must support:

1. HTTP endpoint testing (widget data, preview)
2. WebSocket connection testing (concurrent viewers, delivery latency)
3. Configurable step-ramp load shapes (5 → 10 → 25 → 50 → 100 users)
4. Prometheus metrics export for SLO validation
5. Headless CI execution with CSV/JSON result export
6. Docker-based deployment for reproducible runs

## Decision

Use **Locust** as the load testing framework, with `locust-plugins` for Prometheus export and `websocket-client` for WebSocket scenarios.

## Alternatives Considered

### k6 (Grafana Labs)

Pros: Lower resource overhead per virtual user, built-in Prometheus remote write, JavaScript-based scripting.

Cons: WebSocket support exists but is less flexible than Locust's custom User classes. The JavaScript runtime cannot reuse our existing Python helpers (auth token generation, seed scripts). The step-ramp load shape requires a custom executor configuration that is less intuitive than Locust's `LoadTestShape`.

### Custom asyncio script

Pros: Maximum flexibility, no framework overhead, reuses backend's async patterns directly.

Cons: Reinvents reporting, distribution, web UI, and metrics export. Significant engineering effort for features Locust provides out of the box. No standard result format for CI integration.

### Apache JMeter

Pros: Mature, widely adopted, GUI-based test design.

Cons: JVM-based with high resource overhead per virtual user. XML test plans are hard to version control. No native Python integration for seed scripts. WebSocket support requires third-party plugins with inconsistent quality.

## Consequences

**Positive:**
- Python-native: seed scripts, auth helpers, and toxics controllers share the same language as the backend
- Custom `User` classes enable precise WebSocket latency measurement (timestamp comparison)
- `LoadTestShape` provides clean step-ramp profiles without external orchestration
- Distributed mode (master + workers) scales to 500+ concurrent connections
- Built-in web UI at port 8089 for interactive debugging
- `locust-plugins` provides Prometheus exporter for seamless Grafana integration

**Negative:**
- Higher memory per virtual user than k6 (~2-5x), but acceptable for our scale (500 users max)
- gevent-based concurrency requires WebSocket libraries compatible with gevent's monkey patching
- Team must learn Locust's API, though it's small and well-documented
