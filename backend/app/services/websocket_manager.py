"""WebSocket Manager — execution status + live data pushes.

Tracks active connections and uses Redis pub/sub for multi-instance fan-out.
Any backend instance can publish a message, and all instances with connected
clients will receive and forward it.

All channels are tenant-scoped: flowforge:{tenant_id}:{channel_type}:{id}
"""

import asyncio
import contextlib
import json
import logging
import time
from uuid import UUID

from fastapi import WebSocket
from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from app.core.metrics import (
    websocket_connections_active,
    websocket_message_delivery_seconds,
    websocket_messages_sent_total,
)

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "flowforge"
HEARTBEAT_INTERVAL_SECONDS = 30


class WebSocketManager:
    """Manages WebSocket connections and message distribution."""

    def __init__(self, redis: Redis):
        self._redis = redis
        self._connections: dict[str, set[WebSocket]] = {}
        self._ws_channels: dict[WebSocket, set[str]] = {}
        self._heartbeat_task: asyncio.Task | None = None
        self._tenant_connections: dict[str, int] = {}
        self._pubsub: PubSub | None = None

    @staticmethod
    def _extract_tenant_id(channel: str) -> str | None:
        """Extract tenant_id from a channel name.

        Channel format: flowforge:{tenant_id}:{channel_type}:{id}
        Returns None for malformed channels.
        """
        parts = channel.split(":")
        if len(parts) >= 2 and parts[0] == CHANNEL_PREFIX:
            return parts[1]
        return None

    async def _subscribe_tenant(self, tenant_id: str) -> None:
        """Subscribe to a tenant's Redis pub/sub channels if not already subscribed."""
        count = self._tenant_connections.get(tenant_id, 0)
        if count == 0 and self._pubsub is not None:
            pattern = f"{CHANNEL_PREFIX}:{tenant_id}:*"
            await self._pubsub.psubscribe(pattern)
            logger.info("Subscribed to tenant pattern: %s", pattern)
        self._tenant_connections[tenant_id] = count + 1

    async def _unsubscribe_tenant(self, tenant_id: str) -> None:
        """Unsubscribe from a tenant's channels when last connection disconnects."""
        count = self._tenant_connections.get(tenant_id, 0)
        if count <= 1:
            if self._pubsub is not None:
                pattern = f"{CHANNEL_PREFIX}:{tenant_id}:*"
                await self._pubsub.punsubscribe(pattern)
                logger.info("Unsubscribed from tenant pattern: %s", pattern)
            self._tenant_connections.pop(tenant_id, None)
        else:
            self._tenant_connections[tenant_id] = count - 1

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

        # H2: Subscribe to tenant's Redis channels on first connection
        tenant_id = self._extract_tenant_id(channel)
        if tenant_id is not None:
            await self._subscribe_tenant(tenant_id)

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
        """Remove a WebSocket connection from a single channel.

        H7 fix: Only decrement gauge if this is the last channel for this WebSocket.
        H8 fix: Clean up _ws_channels when all channels are removed.
        """
        if channel in self._connections:
            self._connections[channel].discard(websocket)
            if not self._connections[channel]:
                del self._connections[channel]

        # H2: Unsubscribe tenant when last connection for that tenant disconnects
        tenant_id = self._extract_tenant_id(channel)
        if tenant_id is not None:
            await self._unsubscribe_tenant(tenant_id)

        if websocket in self._ws_channels:
            self._ws_channels[websocket].discard(channel)
            # H8: Clean up _ws_channels if no channels remain
            if not self._ws_channels[websocket]:
                del self._ws_channels[websocket]
                # H7: Only decrement gauge when WebSocket is fully removed
                websocket_connections_active.dec()

        logger.info("WebSocket disconnected from channel: %s", channel)

    async def disconnect_all(self, websocket: WebSocket) -> None:
        """Remove a WebSocket from all channels it's subscribed to.

        H7 fix: Only decrement gauge once per connection, not per channel.
        H8 fix: Already removes from _ws_channels (via pop).
        """
        channels = self._ws_channels.pop(websocket, set())
        for channel in channels:
            if channel in self._connections:
                self._connections[channel].discard(websocket)
                if not self._connections[channel]:
                    del self._connections[channel]

            # H2: Unsubscribe tenant when last connection disconnects
            tenant_id = self._extract_tenant_id(channel)
            if tenant_id is not None:
                await self._unsubscribe_tenant(tenant_id)

        # H7: Only decrement if the WebSocket was actually tracked
        if channels:
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
        """Send a message to all local WebSocket connections on a channel.

        H8 fix: Clean up dead WebSockets from both _connections AND _ws_channels.
        """
        connections = self._connections.get(channel, set())
        dead: set[WebSocket] = set()

        channel_type = self._extract_channel_type(channel)
        for ws in connections:
            try:
                start = time.monotonic()
                await ws.send_text(message)
                elapsed = time.monotonic() - start
                websocket_message_delivery_seconds.labels(
                    channel_type=channel_type,
                ).observe(elapsed)
            except Exception:
                dead.add(ws)

        # H8: Clean up dead WebSockets from both sides
        for ws in dead:
            connections.discard(ws)
            # Also remove from _ws_channels to prevent memory leak
            await self.disconnect_all(ws)

    async def _broadcast_to_all(self, message: str) -> None:
        """Send a message to every connected WebSocket client."""
        dead: set[WebSocket] = set()

        for ws in self._ws_channels:
            try:
                start = time.monotonic()
                await ws.send_text(message)
                elapsed = time.monotonic() - start
                websocket_message_delivery_seconds.labels(
                    channel_type="broadcast",
                ).observe(elapsed)
            except Exception:
                dead.add(ws)

        for ws in dead:
            await self.disconnect_all(ws)

    @staticmethod
    def _extract_channel_type(channel: str) -> str:
        """Extract the channel type from a channel name.

        Channel format: flowforge:{tenant_id}:{channel_type}:{id}
        """
        parts = channel.split(":")
        if len(parts) >= 3:
            return parts[2]
        return "unknown"

    async def _heartbeat_loop(
        self, interval: float = HEARTBEAT_INTERVAL_SECONDS
    ) -> None:
        """H9: Periodic heartbeat to detect stale connections.

        Sends ping messages to all connected WebSockets. Connections that fail
        to receive the ping are automatically cleaned up.
        """
        logger.info("Starting WebSocket heartbeat loop (interval: %ds)", interval)
        while True:
            try:
                await asyncio.sleep(interval)

                # Get snapshot of current connections
                websockets = list(self._ws_channels.keys())
                dead: set[WebSocket] = set()

                for ws in websockets:
                    try:
                        await ws.send_json({"type": "ping", "timestamp": time.time()})
                    except Exception as e:
                        logger.debug("Heartbeat failed for WebSocket: %s", e)
                        dead.add(ws)

                # Clean up dead connections
                for ws in dead:
                    await self.disconnect_all(ws)

                if dead:
                    logger.info("Heartbeat removed %d dead connections", len(dead))

            except asyncio.CancelledError:
                logger.info("WebSocket heartbeat loop cancelled")
                break
            except Exception as e:
                logger.error("Error in WebSocket heartbeat loop: %s", e)

    def start_heartbeat(self) -> None:
        """H9: Start the background heartbeat task.

        Call this on application startup after the WebSocketManager is initialized.
        """
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("WebSocket heartbeat task started")

    async def stop_heartbeat(self) -> None:
        """H9: Stop the background heartbeat task.

        Call this on application shutdown.
        """
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
            logger.info("WebSocket heartbeat task stopped")

    async def start_subscriber(self) -> None:
        """Start the Redis pub/sub subscriber loop.

        Call this on application startup. It listens for messages published
        by any backend instance and forwards them to local WebSocket connections.

        H2 fix: No longer subscribes to all tenants upfront. The pubsub object
        is created empty; per-tenant subscriptions are added/removed dynamically
        as WebSocket clients connect and disconnect.
        """
        self._pubsub = self._redis.pubsub()

        async for message in self._pubsub.listen():
            if message["type"] == "pmessage":
                channel = message["channel"]
                if isinstance(channel, bytes):
                    channel = channel.decode()
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()

                # Broadcast channels go to ALL connected clients
                if ":broadcast:" in channel:
                    await self._broadcast_to_all(data)
                else:
                    await self._broadcast_to_channel(channel, data)
