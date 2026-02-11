"""Scenario 1: Event Rate Sweep.

Measures P95/P99 query latency at varying concurrency levels.
Hits GET /api/v1/widgets/{id}/data and POST /api/v1/executions/preview
with a step ramp from 5 to 100 concurrent users (60s per stage).

SLO pass criteria:
  - Redis P99 < 5ms
  - Materialize P99 < 50ms
  - ClickHouse P99 < 2s
  - HTTP endpoint P99 < 3s
"""

from __future__ import annotations

import os

from locust import HttpUser, between, task

from common.auth import get_auth_headers
from shapes.step_shape import StepShape

# Widget and workflow IDs are set by the seed script via env vars
WIDGET_ID = os.environ.get("BENCH_WIDGET_ID", "")
WORKFLOW_ID = os.environ.get("BENCH_WORKFLOW_ID", "")


class EventRateShape(StepShape):
    """Step ramp: 5 -> 10 -> 25 -> 50 -> 100 users, 60s each."""

    stages = [
        (5, 60),
        (10, 60),
        (25, 60),
        (50, 60),
        (100, 60),
    ]


class EventRateUser(HttpUser):
    """Simulates a user fetching widget data and previewing workflows."""

    wait_time = between(0.5, 2.0)
    headers = get_auth_headers()

    @task(3)
    def get_widget_data(self) -> None:
        """Fetch data for a seeded widget."""
        if not WIDGET_ID:
            return
        self.client.get(
            f"/api/v1/widgets/{WIDGET_ID}/data",
            headers=self.headers,
            name="/api/v1/widgets/:id/data",
        )

    @task(1)
    def preview_workflow(self) -> None:
        """Execute a preview query against the seeded workflow."""
        if not WORKFLOW_ID:
            return
        payload = {
            "workflow_id": WORKFLOW_ID,
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
            name="/api/v1/executions/preview",
        )

    @task(1)
    def health_check(self) -> None:
        """Hit the readiness endpoint to measure store health check latency."""
        self.client.get(
            "/health/ready",
            name="/health/ready",
        )
