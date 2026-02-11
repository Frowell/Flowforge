# 0012: Toxiproxy for Chaos Testing

**Status:** Accepted
**Date:** 2026-02-11
**Deciders:** Architecture team

## Context

FlowForge needs chaos testing to validate graceful degradation when backing stores (ClickHouse, Redis, Materialize) fail or experience latency spikes. The chaos tool must:

1. Inject TCP-level failures (latency, timeout, connection reset) on individual store connections
2. Be scriptable via API for timed chaos schedules during benchmark runs
3. Work in both Docker Compose (local/CI) and Kubernetes (production)
4. Support concurrent toxics on multiple proxies (e.g., Redis latency + ClickHouse down simultaneously)
5. Provide metrics for observing toxic state in Grafana

## Decision

Use **Toxiproxy** (Shopify) as the TCP proxy for chaos injection, controlled via the `toxiproxy-python` client library.

## Alternatives Considered

### Docker network controls (tc/netem)

Pros: No additional service to run, uses Linux kernel traffic shaping natively.

Cons: Requires `CAP_NET_ADMIN` in containers (security concern in CI). Operates at the network interface level — cannot target individual TCP connections or ports. Cannot simulate application-layer failures like slow responses. Not scriptable via a REST API.

### Pumba

Pros: Docker-native chaos tool, supports network delay, packet loss, and container kill.

Cons: Docker-only — does not work in Kubernetes without adaptation. Cannot inject per-connection latency (operates at container level). No REST API for programmatic control during benchmark runs. Less actively maintained than Toxiproxy.

### Chaos Mesh (CNCF)

Pros: Kubernetes-native, rich fault injection (pod kill, network partition, IO chaos), CRD-based configuration.

Cons: Requires Kubernetes — does not work in Docker Compose, breaking dev/CI parity. Heavy installation footprint (multiple operators + CRDs). Overkill for our use case of injecting TCP-level faults on 4 store connections. Would require a separate chaos testing setup for local development.

## Consequences

**Positive:**
- TCP-level proxying: transparent to the application, no code changes needed
- REST API (port 8474): scriptable chaos schedules from Python (`toxiproxy-python`)
- Per-proxy targeting: can inject latency on Redis while ClickHouse remains healthy
- Built-in toxics: `latency`, `timeout`, `slow_close`, `bandwidth`, `slicer`
- Works identically in Docker Compose and Kubernetes (deploy as a sidecar or standalone pod)
- Low overhead: single Go binary, minimal resource usage
- Proxy configuration via JSON file for reproducible setups

**Negative:**
- All traffic must route through Toxiproxy proxies, adding ~0.1ms baseline latency
- Backend environment variables must be overridden to point at proxy ports instead of direct store ports
- Cannot simulate application-layer failures (e.g., ClickHouse returning error responses) — only TCP-level faults
- Proxy configuration must be maintained separately from store connection config
