"""Gevent-compatible WebSocket client for Locust.

Locust uses gevent for concurrency, so we need a WebSocket client that
plays nicely with gevent's cooperative scheduling. This module provides
a thin wrapper around websocket-client with gevent monkey-patching.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Callable

import gevent
import websocket

logger = logging.getLogger(__name__)


class BenchWebSocket:
    """A gevent-compatible WebSocket client for Locust users."""

    def __init__(
        self,
        url: str,
        on_message: Callable[[dict[str, Any], float], None] | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.url = url
        self._on_message = on_message
        self._headers = headers or {}
        self._ws: websocket.WebSocket | None = None
        self._receiver_greenlet: gevent.Greenlet | None = None
        self._running = False

    def connect(self) -> None:
        """Open the WebSocket connection."""
        self._ws = websocket.create_connection(
            self.url,
            header=self._headers,
            timeout=10,
        )
        self._running = True
        self._receiver_greenlet = gevent.spawn(self._receive_loop)
        logger.debug("WebSocket connected to %s", self.url)

    def send(self, data: dict[str, Any]) -> None:
        """Send a JSON message."""
        if self._ws:
            self._ws.send(json.dumps(data))

    def close(self) -> None:
        """Close the connection and stop the receiver."""
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._receiver_greenlet:
            self._receiver_greenlet.kill(block=False)

    def _receive_loop(self) -> None:
        """Background greenlet that reads messages and calls the handler."""
        while self._running and self._ws:
            try:
                raw = self._ws.recv()
                receive_ts = time.time()
                if raw:
                    data = json.loads(raw)
                    if self._on_message:
                        self._on_message(data, receive_ts)
            except websocket.WebSocketConnectionClosedException:
                logger.debug("WebSocket connection closed")
                break
            except Exception:
                if self._running:
                    logger.exception("Error in WebSocket receive loop")
                break
