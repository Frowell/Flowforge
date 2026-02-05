"""WebSocket Manager — execution status + live data pushes.

Tracks active connections and uses Redis pub/sub for multi-instance fan-out.
Any backend instance can publish a message, and all instances with connected
clients will receive and forward it.

All channels are tenant-scoped: flowforge:{tenant_id}:{channel_type}:{id}
"""

import json
import logging
from uuid import UUID

from fastapi import WebSocket
from redis.asyncio import Redis

from app.core.metrics import websocket_connections_active, websocket_messages_sent_total

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "flowforge"


class WebSocketManager:
    """Manages WebSocket connections and message distribution."""

    def __init__(self, redis: Redis):
        self._redis = redis
        self._connections: dict[str, set[WebSocket]] = {}
        self._ws_channels: dict[WebSocket, set[str]] = {}

    async def connect(self, websocket: WebSocket, channel: str) -> None:
        """Register a WebSocket connection for a channel."""
        await websocket.accept()
        if channel not in self._connections:
            self._connections[channel] = set()
        self._connections[channel].add(websocket)
        if websocket not in self._ws_channels:
            self._ws_channels[websocket] = set()
        self._ws_channels[websocket].add(channel)
        websocket_connections_active.inc()
        logger.info("WebSocket connected to channel: %s", channel)

    async def subscribe_to_channel(self, websocket: WebSocket, channel: str) -> None:
        """Subscribe an already-connected WebSocket to an additional channel."""
        if channel not in self._connections:
            self._connections[channel] = set()
        self._connections[channel].add(websocket)
        if websocket not in self._ws_channels:
            self._ws_channels[websocket] = set()
        self._ws_channels[websocket].add(channel)
        logger.info("WebSocket subscribed to channel: %s", channel)

    async def unsubscribe_from_channel(
        self, websocket: WebSocket, channel: str
    ) -> None:
        """Unsubscribe a WebSocket from a specific channel."""
        if channel in self._connections:
            self._connections[channel].discard(websocket)
            if not self._connections[channel]:
                del self._connections[channel]
        if websocket in self._ws_channels:
            self._ws_channels[websocket].discard(channel)
        logger.info("WebSocket unsubscribed from channel: %s", channel)

    async def disconnect(self, websocket: WebSocket, channel: str) -> None:
        """Remove a WebSocket connection from a single channel."""
        if channel in self._connections:
            self._connections[channel].discard(websocket)
            if not self._connections[channel]:
                del self._connections[channel]
        if websocket in self._ws_channels:
            self._ws_channels[websocket].discard(channel)
        websocket_connections_active.dec()
        logger.info("WebSocket disconnected from channel: %s", channel)

    async def disconnect_all(self, websocket: WebSocket) -> None:
        """Remove a WebSocket from all channels it's subscribed to."""
        channels = self._ws_channels.pop(websocket, set())
        for channel in channels:
            if channel in self._connections:
                self._connections[channel].discard(websocket)
                if not self._connections[channel]:
                    del self._connections[channel]
        websocket_connections_active.dec()
        logger.info("WebSocket disconnected from all channels (%d)", len(channels))

    async def publish_execution_status(
        self,
        tenant_id: UUID,
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
        channel = f"{CHANNEL_PREFIX}:{tenant_id}:execution:{execution_id}"
        await self._redis.publish(channel, json.dumps(message))
        websocket_messages_sent_total.labels(message_type="execution_status").inc()

    async def publish_live_data(
        self,
        tenant_id: UUID,
        widget_id: UUID,
        data: dict,
    ) -> None:
        """Publish live data update for a widget."""
        message = {
            "type": "live_data",
            "widget_id": str(widget_id),
            "data": data,
        }
        channel = f"{CHANNEL_PREFIX}:{tenant_id}:widget:{widget_id}"
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
