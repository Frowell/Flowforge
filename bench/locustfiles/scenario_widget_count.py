"""Scenario 2: Widget Count — dashboard load time vs widget count.

Seeds dashboards with 1, 5, 10, 25, 50 widgets. Each user loads all
widgets sequentially (simulates Promise.all() on dashboard mount).

SLO pass criteria:
  - 10-widget dashboard P95 < 2s
  - 25-widget dashboard P95 < 5s
  - 50-widget dashboard P95 < 10s
"""

from __future__ import annotations

import json
import os
import time

from locust import HttpUser, between, events, task

from common.auth import get_auth_headers

# Seeded dashboard configs: JSON array of {dashboard_id, widget_ids: [...]}
# Set by seed-bench-data.py before running this scenario.
DASHBOARDS_JSON = os.environ.get("BENCH_DASHBOARDS", "[]")


def _load_dashboards() -> list[dict]:
    try:
        return json.loads(DASHBOARDS_JSON)
    except (json.JSONDecodeError, TypeError):
        return []


class WidgetCountUser(HttpUser):
    """Simulates loading dashboards with varying widget counts."""

    wait_time = between(1.0, 3.0)
    headers = get_auth_headers()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._dashboards = _load_dashboards()
        self._dash_idx = 0

    @task
    def load_dashboard(self) -> None:
        """Load all widgets in a dashboard sequentially."""
        if not self._dashboards:
            return

        dashboard = self._dashboards[self._dash_idx % len(self._dashboards)]
        self._dash_idx += 1

        widget_ids = dashboard.get("widget_ids", [])
        widget_count = len(widget_ids)
        dashboard_id = dashboard.get("dashboard_id", "unknown")

        start = time.time()
        for wid in widget_ids:
            self.client.get(
                f"/api/v1/widgets/{wid}/data",
                headers=self.headers,
                name=f"/api/v1/widgets/:id/data [{widget_count}w]",
            )

        elapsed_ms = (time.time() - start) * 1000
        events.request.fire(
            request_type="dashboard_load",
            name=f"dashboard/{widget_count}-widgets",
            response_time=elapsed_ms,
            response_length=0,
            exception=None,
            context={
                "dashboard_id": dashboard_id,
                "widget_count": widget_count,
            },
        )
