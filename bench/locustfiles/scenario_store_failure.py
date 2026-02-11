"""Scenario 4: Store Failure — chaos injection via Toxiproxy.

Same request pattern as event rate, with Toxiproxy chaos injections:
  - t=30s:  ClickHouse timeout for 15s
  - t=60s:  Redis 500ms latency for 15s
  - t=90s:  Materialize timeout for 15s
  - t=120s: Redis latency + ClickHouse down simultaneously for 10s

SLO pass criteria:
  - Error rate < 10% during any single failure
  - Recovery time < 30s after toxic removal
  - No cascade failures
"""

from __future__ import annotations

import os

import gevent
from locust import HttpUser, between, events, task

from common.auth import get_auth_headers
from common.toxics import (
    apply_latency,
    apply_timeout,
    remove_toxic,
    reset_all_proxies,
)

WIDGET_ID = os.environ.get("BENCH_WIDGET_ID", "")

# Chaos schedule: (start_seconds, action_fn)
CHAOS_SCHEDULE = [
    # t=30s: ClickHouse timeout for 15s
    (30, "ch_timeout_on"),
    (45, "ch_timeout_off"),
    # t=60s: Redis 500ms latency for 15s
    (60, "redis_latency_on"),
    (75, "redis_latency_off"),
    # t=90s: Materialize timeout for 15s
    (90, "mz_timeout_on"),
    (105, "mz_timeout_off"),
    # t=120s: Redis latency + ClickHouse down for 10s
    (120, "multi_failure_on"),
    (130, "multi_failure_off"),
]


def _ch_timeout_on():
    apply_timeout("clickhouse", timeout_ms=0, toxic_name="ch_timeout")


def _ch_timeout_off():
    try:
        remove_toxic("clickhouse", "ch_timeout")
    except Exception:
        pass


def _redis_latency_on():
    apply_latency("redis", latency_ms=500, toxic_name="redis_latency")


def _redis_latency_off():
    try:
        remove_toxic("redis", "redis_latency")
    except Exception:
        pass


def _mz_timeout_on():
    apply_timeout("materialize", timeout_ms=0, toxic_name="mz_timeout")


def _mz_timeout_off():
    try:
        remove_toxic("materialize", "mz_timeout")
    except Exception:
        pass


def _multi_failure_on():
    apply_latency("redis", latency_ms=500, toxic_name="redis_latency_multi")
    apply_timeout("clickhouse", timeout_ms=0, toxic_name="ch_timeout_multi")


def _multi_failure_off():
    try:
        remove_toxic("redis", "redis_latency_multi")
    except Exception:
        pass
    try:
        remove_toxic("clickhouse", "ch_timeout_multi")
    except Exception:
        pass


ACTIONS = {
    "ch_timeout_on": _ch_timeout_on,
    "ch_timeout_off": _ch_timeout_off,
    "redis_latency_on": _redis_latency_on,
    "redis_latency_off": _redis_latency_off,
    "mz_timeout_on": _mz_timeout_on,
    "mz_timeout_off": _mz_timeout_off,
    "multi_failure_on": _multi_failure_on,
    "multi_failure_off": _multi_failure_off,
}

_chaos_started = False


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Start the chaos schedule when the test begins."""
    global _chaos_started
    if _chaos_started:
        return
    _chaos_started = True

    # Reset all proxies before starting
    try:
        reset_all_proxies()
    except Exception:
        pass

    # Schedule chaos events using gevent
    for delay_seconds, action_name in CHAOS_SCHEDULE:
        action_fn = ACTIONS.get(action_name)
        if action_fn:
            gevent.spawn_later(delay_seconds, action_fn)


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Clean up all toxics when the test ends."""
    try:
        reset_all_proxies()
    except Exception:
        pass


class StoreFailureUser(HttpUser):
    """Simulates a user making requests during chaos injection."""

    wait_time = between(0.5, 2.0)
    headers = get_auth_headers()

    @task(3)
    def get_widget_data(self) -> None:
        """Fetch widget data — affected by store failures."""
        if not WIDGET_ID:
            return
        self.client.get(
            f"/api/v1/widgets/{WIDGET_ID}/data",
            headers=self.headers,
            name="/api/v1/widgets/:id/data [chaos]",
        )

    @task(1)
    def preview_workflow(self) -> None:
        """Preview query — affected by store failures."""
        if not WIDGET_ID:
            return
        payload = {
            "workflow_id": WIDGET_ID,  # Reuse seeded workflow
            "target_node_id": "source-1",
            "graph": {
                "nodes": [
                    {
                        "id": "source-1",
                        "type": "data_source",
                        "position": {"x": 0, "y": 0},
                        "data": {
                            "label": "Raw Trades",
                            "config": {
                                "table": "flowforge.raw_trades",
                                "columns": [
                                    "trade_id",
                                    "symbol",
                                    "price",
                                    "quantity",
                                ],
                            },
                        },
                    }
                ],
                "edges": [],
            },
        }
        self.client.post(
            "/api/v1/executions/preview",
            json=payload,
            headers=self.headers,
            name="/api/v1/executions/preview [chaos]",
        )

    @task(2)
    def health_check(self) -> None:
        """Health check — monitors store status during chaos."""
        self.client.get(
            "/health/ready",
            name="/health/ready [chaos]",
        )
