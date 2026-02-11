"""Scenario 3: WebSocket Viewers — delivery latency vs viewer count.

Custom Locust User class with a gevent-compatible WebSocket client.
Connects to ws://backend:8000/ws, subscribes to a broadcast channel,
and measures delivery latency (receive_ts - publish_ts).

Ramp: 10 -> 50 -> 100 -> 250 -> 500 concurrent connections.

SLO pass criteria:
  - 100 viewers P95 < 50ms
  - 250 viewers P95 < 100ms
  - 500 viewers P95 < 200ms
"""

from __future__ import annotations

import os
import time

from locust import User, between, events, task

from common.auth import DEV_TENANT_ID, get_auth_headers
from common.ws_client import BenchWebSocket
from shapes.step_shape import StepShape

WS_BASE = os.environ.get("BENCH_WS_BASE", "ws://localhost:8000")


class WebSocketViewerShape(StepShape):
    """Step ramp: 10 -> 50 -> 100 -> 250 -> 500 connections, 60s each."""

    stages = [
        (10, 60),
        (50, 60),
        (100, 60),
        (250, 60),
        (500, 60),
    ]


class WebSocketViewer(User):
    """Simulates a dashboard viewer connected via WebSocket."""

    wait_time = between(1.0, 5.0)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ws: BenchWebSocket | None = None
        self._message_count = 0

    def on_start(self) -> None:
        """Connect to WebSocket on user start."""
        url = f"{WS_BASE}/ws"
        headers = get_auth_headers()

        self._ws = BenchWebSocket(
            url=url,
            on_message=self._handle_message,
            headers=headers,
        )
        try:
            start = time.time()
            self._ws.connect()
            elapsed_ms = (time.time() - start) * 1000
            events.request.fire(
                request_type="ws",
                name="ws_connect",
                response_time=elapsed_ms,
                response_length=0,
                exception=None,
                context={},
            )
        except Exception as exc:
            events.request.fire(
                request_type="ws",
                name="ws_connect",
                response_time=0,
                response_length=0,
                exception=exc,
                context={},
            )

    def on_stop(self) -> None:
        """Disconnect on user stop."""
        if self._ws:
            self._ws.close()

    def _handle_message(self, data: dict, receive_ts: float) -> None:
        """Handle incoming WebSocket messages and measure delivery latency."""
        self._message_count += 1

        # If the message contains a publish timestamp, measure delivery latency
        publish_ts = data.get("publish_ts")
        if publish_ts is not None:
            delivery_ms = (receive_ts - float(publish_ts)) * 1000
            events.request.fire(
                request_type="ws",
                name="ws_delivery",
                response_time=delivery_ms,
                response_length=len(str(data)),
                exception=None,
                context={"message_type": data.get("type", "unknown")},
            )

    @task
    def subscribe_and_wait(self) -> None:
        """Subscribe to widget channels and wait for messages."""
        if not self._ws:
            return

        # Send a subscribe message
        self._ws.send(
            {
                "type": "subscribe",
                "channel": f"flowforge:{DEV_TENANT_ID}:broadcast:table_rows",
            }
        )
