"""WebSocket Manager — execution status + live data pushes.

Tracks active connections and uses Redis pub/sub for multi-instance fan-out.
Any backend instance can publish a message, and all instances with connected
clients will receive and forward it.
"""

import json
import logging
from uuid import UUID

from fastapi import WebSocket
from redis.asyncio import Redis

from app.core.metrics import websocket_connections_active, websocket_messages_sent_total

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "flowforge:ws"


class WebSocketManager:
    """Manages WebSocket connections and message distribution."""

    def __init__(self, redis: Redis):
        self._redis = redis
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        """Register a WebSocket connection for a channel."""
        await websocket.accept()
        if channel not in self._connections:
            self._connections[channel] = set()
        self._connections[channel].add(websocket)
        websocket_connections_active.inc()
        logger.info("WebSocket connected to channel: %s", channel)

    async def disconnect(self, websocket: WebSocket, channel: str) -> None:
        """Remove a WebSocket connection."""
        if channel in self._connections:
            self._connections[channel].discard(websocket)
            if not self._connections[channel]:
                del self._connections[channel]
        websocket_connections_active.dec()
        logger.info("WebSocket disconnected from channel: %s", channel)

    async def publish_execution_status(
        self,
        execution_id: UUID,
        node_id: str,
        status: str,
        data: dict | None = None,
    ) -> None:
        """Publish an execution status update via Redis pub/sub."""
        message = {
            "type": "execution_status",
            "execution_id": str(execution_id),
            "node_id": node_id,
            "status": status,
            "data": data or {},
        }
        channel = f"{CHANNEL_PREFIX}:execution:{execution_id}"
        await self._redis.publish(channel, json.dumps(message))
        websocket_messages_sent_total.labels(message_type="execution_status").inc()

    async def publish_live_data(
        self,
        widget_id: UUID,
        data: dict,
    ) -> None:
        """Publish live data update for a widget."""
        message = {
            "type": "live_data",
            "widget_id": str(widget_id),
            "data": data,
        }
        channel = f"{CHANNEL_PREFIX}:widget:{widget_id}"
        await self._redis.publish(channel, json.dumps(message))
        websocket_messages_sent_total.labels(message_type="live_data").inc()

    async def _broadcast_to_channel(self, channel: str, message: str) -> None:
        """Send a message to all local WebSocket connections on a channel."""
        connections = self._connections.get(channel, set())
        dead: set[WebSocket] = set()

        for ws in connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)

        for ws in dead:
            connections.discard(ws)

    async def start_subscriber(self) -> None:
        """Start the Redis pub/sub subscriber loop.

        Call this on application startup. It listens for messages published
        by any backend instance and forwards them to local WebSocket connections.
        """
        pubsub = self._redis.pubsub()
        await pubsub.psubscribe(f"{CHANNEL_PREFIX}:*")

        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                channel = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                await self._broadcast_to_channel(channel, data)
