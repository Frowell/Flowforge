"""Tests for WebSocketManager — gauge consistency, stale cleanup, heartbeat."""

import asyncio
import contextlib
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

# Add backend to path to allow direct imports
backend_path = Path(__file__).parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from fastapi import WebSocket  # noqa: E402

# Import metrics and manager directly (without app dependencies)
from app.core.metrics import websocket_connections_active  # noqa: E402
from app.services.websocket_manager import WebSocketManager  # noqa: E402


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis = AsyncMock()
    redis.publish = AsyncMock()
    return redis


@pytest.fixture
def ws_manager(mock_redis):
    """WebSocketManager instance with mocked Redis."""
    return WebSocketManager(redis=mock_redis)


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = AsyncMock(spec=WebSocket)
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


class TestGaugeConsistency:
    """Tests for H7 — gauge increment/decrement symmetry."""

    async def test_connect_increments_gauge_once(self, ws_manager, mock_websocket):
        """Connect should increment gauge exactly once."""
        initial = websocket_connections_active._value.get()
        await ws_manager.connect(mock_websocket, "channel:1")
        assert websocket_connections_active._value.get() == initial + 1

    async def test_disconnect_decrements_gauge_once(self, ws_manager, mock_websocket):
        """Disconnect should decrement gauge exactly once."""
        await ws_manager.connect(mock_websocket, "channel:1")
        initial = websocket_connections_active._value.get()
        await ws_manager.disconnect(mock_websocket, "channel:1")
        assert websocket_connections_active._value.get() == initial - 1

    async def test_disconnect_all_decrements_gauge_once(
        self, ws_manager, mock_websocket
    ):
        """disconnect_all should decrement gauge once, not per channel."""
        await ws_manager.connect(mock_websocket, "channel:1")
        await ws_manager.subscribe_to_channel(mock_websocket, "channel:2")
        await ws_manager.subscribe_to_channel(mock_websocket, "channel:3")

        initial = websocket_connections_active._value.get()
        await ws_manager.disconnect_all(mock_websocket)
        # Should decrement once, not 3 times
        assert websocket_connections_active._value.get() == initial - 1

    async def test_subscribe_to_channel_does_not_increment_gauge(
        self, ws_manager, mock_websocket
    ):
        """subscribe_to_channel should NOT increment gauge."""
        await ws_manager.connect(mock_websocket, "channel:1")
        initial = websocket_connections_active._value.get()
        await ws_manager.subscribe_to_channel(mock_websocket, "channel:2")
        # Gauge should remain the same
        assert websocket_connections_active._value.get() == initial

    async def test_multiple_connections_independent_gauge(self, ws_manager):
        """Multiple connections should increment gauge independently."""
        ws1 = AsyncMock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws2 = AsyncMock(spec=WebSocket)
        ws2.accept = AsyncMock()

        initial = websocket_connections_active._value.get()
        await ws_manager.connect(ws1, "channel:1")
        await ws_manager.connect(ws2, "channel:1")
        assert websocket_connections_active._value.get() == initial + 2

        await ws_manager.disconnect(ws1, "channel:1")
        assert websocket_connections_active._value.get() == initial + 1

        await ws_manager.disconnect(ws2, "channel:1")
        assert websocket_connections_active._value.get() == initial


class TestStaleEntryCleanup:
    """Tests for H8 — _ws_channels cleanup when WebSocket dies."""

    async def test_broadcast_removes_dead_websocket_from_ws_channels(
        self, ws_manager, mock_websocket
    ):
        """_broadcast_to_channel should remove dead WS from _ws_channels."""
        # Connect to a channel
        await ws_manager.connect(mock_websocket, "channel:1")
        assert mock_websocket in ws_manager._ws_channels
        assert "channel:1" in ws_manager._ws_channels[mock_websocket]

        # Simulate send failure
        mock_websocket.send_text.side_effect = Exception("Connection closed")

        # Broadcast should detect dead connection and clean up
        await ws_manager._broadcast_to_channel("channel:1", "test message")

        # Should be removed from both _connections and _ws_channels
        assert mock_websocket not in ws_manager._connections.get("channel:1", set())
        assert mock_websocket not in ws_manager._ws_channels

    async def test_broadcast_cleans_multiple_dead_websockets(self, ws_manager):
        """_broadcast_to_channel should clean all dead WebSockets."""
        ws1 = AsyncMock(spec=WebSocket)
        ws1.accept = AsyncMock()
        ws1.send_text = AsyncMock(side_effect=Exception("Dead"))

        ws2 = AsyncMock(spec=WebSocket)
        ws2.accept = AsyncMock()
        ws2.send_text = AsyncMock(side_effect=Exception("Dead"))

        ws3 = AsyncMock(spec=WebSocket)
        ws3.accept = AsyncMock()
        ws3.send_text = AsyncMock()  # Alive

        await ws_manager.connect(ws1, "channel:1")
        await ws_manager.connect(ws2, "channel:1")
        await ws_manager.connect(ws3, "channel:1")

        await ws_manager._broadcast_to_channel("channel:1", "test")

        # Dead ones removed
        assert ws1 not in ws_manager._ws_channels
        assert ws2 not in ws_manager._ws_channels
        # Alive one remains
        assert ws3 in ws_manager._ws_channels

    async def test_disconnect_removes_from_all_channel_sets(
        self, ws_manager, mock_websocket
    ):
        """disconnect should remove WebSocket from all channel sets it's in."""
        await ws_manager.connect(mock_websocket, "channel:1")
        await ws_manager.subscribe_to_channel(mock_websocket, "channel:2")
        await ws_manager.subscribe_to_channel(mock_websocket, "channel:3")

        # Disconnect from channel:2
        await ws_manager.disconnect(mock_websocket, "channel:2")

        # Should still be in channel:1 and channel:3
        assert "channel:1" in ws_manager._ws_channels[mock_websocket]
        assert "channel:2" not in ws_manager._ws_channels[mock_websocket]
        assert "channel:3" in ws_manager._ws_channels[mock_websocket]


class TestHeartbeat:
    """Tests for H9 — WebSocket heartbeat/ping implementation."""

    async def test_heartbeat_task_sends_pings(self, ws_manager, mock_websocket):
        """Heartbeat task should periodically ping connections."""
        await ws_manager.connect(mock_websocket, "channel:1")

        # Start heartbeat with short interval
        task = asyncio.create_task(ws_manager._heartbeat_loop(interval=0.05))

        # Wait for at least 2 pings
        await asyncio.sleep(0.15)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

        # Should have sent ping frames
        assert mock_websocket.send_json.call_count >= 2
        # Each call should be a ping message
        for call in mock_websocket.send_json.call_args_list:
            assert call[0][0]["type"] == "ping"

    async def test_heartbeat_removes_unresponsive_connections(self, ws_manager):
        """Heartbeat should remove connections that fail to respond."""
        ws_dead = AsyncMock(spec=WebSocket)
        ws_dead.accept = AsyncMock()
        ws_dead.send_json = AsyncMock(side_effect=Exception("Connection lost"))

        await ws_manager.connect(ws_dead, "channel:1")
        assert ws_dead in ws_manager._ws_channels

        # Start heartbeat
        task = asyncio.create_task(ws_manager._heartbeat_loop(interval=0.05))
        await asyncio.sleep(0.1)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

        # Dead connection should be removed
        assert ws_dead not in ws_manager._ws_channels

    async def test_heartbeat_preserves_alive_connections(self, ws_manager):
        """Heartbeat should keep connections that respond successfully."""
        ws_alive = AsyncMock(spec=WebSocket)
        ws_alive.accept = AsyncMock()
        ws_alive.send_json = AsyncMock()

        await ws_manager.connect(ws_alive, "channel:1")

        task = asyncio.create_task(ws_manager._heartbeat_loop(interval=0.05))
        await asyncio.sleep(0.15)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

        # Alive connection should still exist
        assert ws_alive in ws_manager._ws_channels


class TestPublishMethods:
    """Test Redis pub/sub publishing methods."""

    async def test_publish_execution_status(self, ws_manager, mock_redis):
        """publish_execution_status should format and publish correctly."""
        tenant_id = uuid4()
        execution_id = uuid4()

        await ws_manager.publish_execution_status(
            tenant_id=tenant_id,
            execution_id=execution_id,
            node_id="node_1",
            status="running",
            data={"progress": 50},
        )

        mock_redis.publish.assert_called_once()
        channel, message_str = mock_redis.publish.call_args[0]

        assert channel == f"flowforge:{tenant_id}:execution:{execution_id}"
        message = json.loads(message_str)
        assert message["type"] == "execution_status"
        assert message["execution_id"] == str(execution_id)
        assert message["node_id"] == "node_1"
        assert message["status"] == "running"
        assert message["data"]["progress"] == 50

    async def test_publish_live_data(self, ws_manager, mock_redis):
        """publish_live_data should format and publish correctly."""
        tenant_id = uuid4()
        widget_id = uuid4()

        await ws_manager.publish_live_data(
            tenant_id=tenant_id,
            widget_id=widget_id,
            data={"rows": [{"col1": "val1"}]},
        )

        mock_redis.publish.assert_called_once()
        channel, message_str = mock_redis.publish.call_args[0]

        assert channel == f"flowforge:{tenant_id}:widget:{widget_id}"
        message = json.loads(message_str)
        assert message["type"] == "live_data"
        assert message["widget_id"] == str(widget_id)
        assert message["data"]["rows"][0]["col1"] == "val1"


class TestChannelManagement:
    """Test channel subscription and unsubscription."""

    async def test_unsubscribe_removes_from_channel(self, ws_manager, mock_websocket):
        """Unsubscribe removes WS from channel without decrementing gauge."""
        await ws_manager.connect(mock_websocket, "channel:1")
        await ws_manager.subscribe_to_channel(mock_websocket, "channel:2")

        initial_gauge = websocket_connections_active._value.get()

        await ws_manager.unsubscribe_from_channel(mock_websocket, "channel:2")

        # Should not affect gauge (not a full disconnect)
        assert websocket_connections_active._value.get() == initial_gauge

        # Should be removed from channel:2
        assert "channel:2" not in ws_manager._connections
        assert "channel:2" not in ws_manager._ws_channels[mock_websocket]

        # Should still be in channel:1
        assert mock_websocket in ws_manager._connections["channel:1"]

    async def test_connect_multiple_times_to_same_channel(
        self, ws_manager, mock_websocket
    ):
        """Connecting to the same channel multiple times should be idempotent."""
        initial_gauge = websocket_connections_active._value.get()

        await ws_manager.connect(mock_websocket, "channel:1")
        gauge_after_first = websocket_connections_active._value.get()

        # Connect again to same channel
        await ws_manager.subscribe_to_channel(mock_websocket, "channel:1")

        # Gauge should only increment once (on first connect)
        assert gauge_after_first == initial_gauge + 1
        assert websocket_connections_active._value.get() == gauge_after_first
