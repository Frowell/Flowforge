#!/usr/bin/env python3
"""Seed benchmark-specific workflows, dashboards, and widgets.

Creates test fixtures for all benchmark scenarios and exports the
resource IDs as environment variables for Locust to consume.

Usage:
    python scripts/seed-bench-data.py [--api-base http://app:8000]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

# Add parent directory so we can import locustfiles modules
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "locustfiles"))

from common.seed import (  # noqa: E402
    create_dashboard,
    create_widget,
    create_workflow,
    seed_dashboard_with_widgets,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed benchmark data")
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="Backend API base URL",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="Output file for env vars (- for stdout)",
    )
    args = parser.parse_args()

    env_vars: dict[str, str] = {}

    # Scenario 1 & 4: Single workflow + widget for event rate & chaos
    logger.info("Creating workflow and widget for event rate scenario...")
    workflow = create_workflow(api_base=args.api_base, name="bench-event-rate")
    dashboard = create_dashboard(api_base=args.api_base, name="bench-event-rate")
    widget = create_widget(
        dashboard_id=dashboard["id"],
        workflow_id=workflow["id"],
        api_base=args.api_base,
        title="bench-event-rate-widget",
    )
    env_vars["BENCH_WIDGET_ID"] = widget["id"]
    env_vars["BENCH_WORKFLOW_ID"] = workflow["id"]
    env_vars["BENCH_DASHBOARD_ID"] = dashboard["id"]

    # Scenario 2: Dashboards with varying widget counts
    logger.info("Creating dashboards with varying widget counts...")
    dashboard_configs = []
    for count in [1, 5, 10, 25, 50]:
        logger.info("  Seeding %d-widget dashboard...", count)
        result = seed_dashboard_with_widgets(
            widget_count=count,
            api_base=args.api_base,
        )
        dashboard_configs.append(
            {
                "dashboard_id": result["dashboard"]["id"],
                "widget_ids": [w["id"] for w in result["widgets"]],
            }
        )
    env_vars["BENCH_DASHBOARDS"] = json.dumps(dashboard_configs)

    # Write env vars
    output_lines = []
    for key, value in env_vars.items():
        output_lines.append(f"export {key}='{value}'")

    output_text = "\n".join(output_lines) + "\n"

    if args.output == "-":
        sys.stdout.write(output_text)
    else:
        with open(args.output, "w") as f:
            f.write(output_text)
        logger.info("Wrote env vars to %s", args.output)

    logger.info("Seed complete.")


if __name__ == "__main__":
    main()
