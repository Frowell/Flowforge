"""Configurable step-function ramp LoadTestShape.

Defines a sequence of (user_count, duration_seconds) stages.
At each stage boundary the user count jumps to the next level.
"""

from __future__ import annotations

import os

from locust import LoadTestShape


class StepShape(LoadTestShape):
    """Step-function load shape with configurable stages.

    Override ``stages`` in a subclass or set the BENCH_STAGES env var
    as a comma-separated list of ``users:duration`` pairs.

    Example env: BENCH_STAGES=5:60,10:60,25:60,50:60,100:60
    """

    # Default stages: (users, duration_seconds)
    stages: list[tuple[int, int]] = [
        (5, 60),
        (10, 60),
        (25, 60),
        (50, 60),
        (100, 60),
    ]

    # Users added per second when ramping to next stage
    spawn_rate: int = 10

    def __init__(self) -> None:
        super().__init__()
        env_stages = os.environ.get("BENCH_STAGES")
        if env_stages:
            self.stages = []
            for pair in env_stages.split(","):
                users, duration = pair.strip().split(":")
                self.stages.append((int(users), int(duration)))

    def tick(self) -> tuple[int, float] | None:
        """Return (user_count, spawn_rate) for the current time, or None to stop."""
        run_time = self.get_run_time()
        elapsed = 0.0

        for users, duration in self.stages:
            elapsed += duration
            if run_time < elapsed:
                return users, self.spawn_rate

        # All stages complete
        return None
