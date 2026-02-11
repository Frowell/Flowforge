"""Seed helpers — create workflows, dashboards, and widgets via API.

Used by benchmark scenarios to set up test fixtures before load generation.
All resources are created in the dev tenant (dev-tenant-001).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

import requests

from .auth import AUTH_HEADERS

logger = logging.getLogger(__name__)

DEFAULT_API_BASE = "http://app:8000"


def _api(base: str, path: str) -> str:
    return f"{base}/api/v1{path}"


def create_workflow(
    api_base: str = DEFAULT_API_BASE,
    name: str | None = None,
) -> dict[str, Any]:
    """Create a minimal workflow with a single data-source node."""
    name = name or f"bench-workflow-{uuid4().hex[:8]}"
    payload = {
        "name": name,
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
                            "columns": ["trade_id", "symbol", "price", "quantity"],
                        },
                    },
                },
                {
                    "id": "filter-1",
                    "type": "filter",
                    "position": {"x": 300, "y": 0},
                    "data": {
                        "label": "Filter AAPL",
                        "config": {
                            "conditions": [
                                {
                                    "column": "symbol",
                                    "operator": "equals",
                                    "value": "AAPL",
                                }
                            ]
                        },
                    },
                },
            ],
            "edges": [
                {"source": "source-1", "target": "filter-1"},
            ],
        },
    }
    resp = requests.post(
        _api(api_base, "/workflows"),
        json=payload,
        headers=AUTH_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    result = resp.json()
    logger.info("Created workflow %s (%s)", result["id"], name)
    return result


def create_dashboard(
    api_base: str = DEFAULT_API_BASE,
    name: str | None = None,
) -> dict[str, Any]:
    """Create an empty dashboard."""
    name = name or f"bench-dashboard-{uuid4().hex[:8]}"
    resp = requests.post(
        _api(api_base, "/dashboards"),
        json={"name": name},
        headers=AUTH_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    result = resp.json()
    logger.info("Created dashboard %s (%s)", result["id"], name)
    return result


def create_widget(
    dashboard_id: str,
    workflow_id: str,
    source_node_id: str = "filter-1",
    api_base: str = DEFAULT_API_BASE,
    title: str | None = None,
) -> dict[str, Any]:
    """Pin a workflow output node as a dashboard widget."""
    title = title or f"bench-widget-{uuid4().hex[:8]}"
    payload = {
        "dashboard_id": dashboard_id,
        "title": title,
        "source_workflow_id": workflow_id,
        "source_node_id": source_node_id,
        "layout": {"x": 0, "y": 0, "w": 6, "h": 4},
        "config_overrides": {},
    }
    resp = requests.post(
        _api(api_base, "/widgets"),
        json=payload,
        headers=AUTH_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    result = resp.json()
    logger.info("Created widget %s on dashboard %s", result["id"], dashboard_id)
    return result


def seed_dashboard_with_widgets(
    widget_count: int,
    api_base: str = DEFAULT_API_BASE,
) -> dict[str, Any]:
    """Create a workflow, a dashboard, and N widgets pointing at the workflow."""
    workflow = create_workflow(api_base=api_base)
    dashboard = create_dashboard(
        api_base=api_base,
        name=f"bench-{widget_count}-widgets",
    )
    widgets = []
    for i in range(widget_count):
        w = create_widget(
            dashboard_id=dashboard["id"],
            workflow_id=workflow["id"],
            api_base=api_base,
            title=f"widget-{i}",
        )
        widgets.append(w)
    return {
        "workflow": workflow,
        "dashboard": dashboard,
        "widgets": widgets,
    }
