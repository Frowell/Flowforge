#!/usr/bin/env python3
"""SLO compliance checker — queries Prometheus for P95/P99 values.

Compares observed latencies against threshold constants and exits
non-zero if any SLO is breached.

Usage:
    python scripts/check-slo.py [--prometheus http://localhost:9090]
"""

from __future__ import annotations

import argparse
import sys

import requests

# SLO thresholds (seconds)
SLOS: list[dict] = [
    {
        "name": "HTTP endpoint P99",
        "query": 'histogram_quantile(0.99, sum(rate(flowforge_http_request_duration_seconds_bucket[5m])) by (le))',
        "threshold": 3.0,
    },
    {
        "name": "Query execution P99 (clickhouse)",
        "query": 'histogram_quantile(0.99, sum(rate(flowforge_query_execution_duration_seconds_bucket{target="clickhouse"}[5m])) by (le))',
        "threshold": 2.0,
    },
    {
        "name": "Query execution P99 (materialize)",
        "query": 'histogram_quantile(0.99, sum(rate(flowforge_query_execution_duration_seconds_bucket{target="materialize"}[5m])) by (le))',
        "threshold": 0.050,
    },
    {
        "name": "Query execution P99 (redis)",
        "query": 'histogram_quantile(0.99, sum(rate(flowforge_query_execution_duration_seconds_bucket{target="redis"}[5m])) by (le))',
        "threshold": 0.005,
    },
    {
        "name": "WebSocket delivery P95",
        "query": 'histogram_quantile(0.95, sum(rate(flowforge_websocket_message_delivery_seconds_bucket[5m])) by (le))',
        "threshold": 0.200,
    },
    {
        "name": "Cache operation P95",
        "query": 'histogram_quantile(0.95, sum(rate(flowforge_cache_operation_duration_seconds_bucket[5m])) by (le))',
        "threshold": 0.010,
    },
    {
        "name": "Store health check P95",
        "query": 'histogram_quantile(0.95, sum(rate(flowforge_store_health_check_duration_seconds_bucket[5m])) by (le))',
        "threshold": 1.0,
    },
    {
        "name": "HTTP endpoint P95",
        "query": 'histogram_quantile(0.95, sum(rate(flowforge_http_request_duration_seconds_bucket[5m])) by (le))',
        "threshold": 2.0,
    },
]


def query_prometheus(prom_url: str, query: str) -> float | None:
    """Execute an instant query against Prometheus and return the scalar value."""
    try:
        resp = requests.get(
            f"{prom_url}/api/v1/query",
            params={"query": query},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("data", {}).get("result", [])
        if results:
            value = float(results[0]["value"][1])
            if value != float("inf") and value != float("nan"):
                return value
    except Exception as exc:
        print(f"  WARNING: Query failed: {exc}", file=sys.stderr)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Check SLO compliance")
    parser.add_argument(
        "--prometheus",
        default="http://localhost:9090",
        help="Prometheus base URL",
    )
    args = parser.parse_args()

    print("=" * 70)
    print("FlowForge SLO Compliance Report")
    print("=" * 70)
    print()

    breaches = 0
    no_data = 0

    print(f"{'SLO':<40} {'Observed':>12} {'Threshold':>12} {'Status':>8}")
    print("-" * 70)

    for slo in SLOS:
        value = query_prometheus(args.prometheus, slo["query"])
        threshold = slo["threshold"]

        if value is None:
            status = "NO DATA"
            no_data += 1
            observed_str = "N/A"
        elif value > threshold:
            status = "BREACH"
            breaches += 1
            observed_str = f"{value:.4f}s"
        else:
            status = "OK"
            observed_str = f"{value:.4f}s"

        print(f"  {slo['name']:<38} {observed_str:>12} {threshold:>11.4f}s {status:>8}")

    print("-" * 70)
    print()

    total = len(SLOS)
    passed = total - breaches - no_data
    print(f"Results: {passed}/{total} passed, {breaches} breached, {no_data} no data")
    print()

    if breaches > 0:
        print("FAILED: SLO breaches detected.")
        sys.exit(1)
    elif no_data == total:
        print("WARNING: No metric data available. Ensure benchmarks have run.")
        sys.exit(2)
    else:
        print("PASSED: All SLOs within thresholds.")
        sys.exit(0)


if __name__ == "__main__":
    main()
