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


class TestTenantScopedSubscription:
    """Tests for H2 — tenant-scoped Redis pub/sub subscriptions."""

    @pytest.fixture
    def mock_pubsub(self):
        """Mock Redis PubSub object."""
        pubsub = AsyncMock()
        pubsub.psubscribe = AsyncMock()
        pubsub.punsubscribe = AsyncMock()
        return pubsub

    @pytest.fixture
    def ws_manager_with_pubsub(self, mock_redis, mock_pubsub):
        """WebSocketManager with pubsub pre-initialized (simulates post-startup)."""
        manager = WebSocketManager(redis=mock_redis)
        manager._pubsub = mock_pubsub
        return manager

    def _make_ws(self):
        ws = AsyncMock(spec=WebSocket)
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    async def test_first_connect_subscribes_to_tenant(
        self, ws_manager_with_pubsub, mock_pubsub
    ):
        """Connecting first client for a tenant subscribes to that tenant's pattern."""
        ws = self._make_ws()
        tenant_id = str(uuid4())
        channel = f"flowforge:{tenant_id}:execution:abc"

        await ws_manager_with_pubsub.connect(ws, channel)

        mock_pubsub.psubscribe.assert_called_once_with(f"flowforge:{tenant_id}:*")

    async def test_second_connect_same_tenant_no_duplicate_subscribe(
        self, ws_manager_with_pubsub, mock_pubsub
    ):
        """Multiple connections for same tenant should only subscribe once."""
        ws1 = self._make_ws()
        ws2 = self._make_ws()
        tenant_id = str(uuid4())

        await ws_manager_with_pubsub.connect(
            ws1, f"flowforge:{tenant_id}:execution:abc"
        )
        await ws_manager_with_pubsub.connect(
            ws2, f"flowforge:{tenant_id}:execution:def"
        )

        # psubscribe should only be called once for this tenant
        assert mock_pubsub.psubscribe.call_count == 1

    async def test_last_disconnect_unsubscribes_tenant(
        self, ws_manager_with_pubsub, mock_pubsub
    ):
        """Disconnecting last client for a tenant unsubscribes that tenant's pattern."""
        ws = self._make_ws()
        tenant_id = str(uuid4())
        channel = f"flowforge:{tenant_id}:execution:abc"

        await ws_manager_with_pubsub.connect(ws, channel)
        mock_pubsub.psubscribe.assert_called_once()

        await ws_manager_with_pubsub.disconnect(ws, channel)

        mock_pubsub.punsubscribe.assert_called_once_with(f"flowforge:{tenant_id}:*")

    async def test_disconnect_one_of_two_no_unsubscribe(
        self, ws_manager_with_pubsub, mock_pubsub
    ):
        """Disconnecting one of two clients for same tenant should NOT unsubscribe."""
        ws1 = self._make_ws()
        ws2 = self._make_ws()
        tenant_id = str(uuid4())

        await ws_manager_with_pubsub.connect(
            ws1, f"flowforge:{tenant_id}:execution:abc"
        )
        await ws_manager_with_pubsub.connect(
            ws2, f"flowforge:{tenant_id}:execution:def"
        )

        await ws_manager_with_pubsub.disconnect(
            ws1, f"flowforge:{tenant_id}:execution:abc"
        )

        # Should NOT have unsubscribed — ws2 still connected
        mock_pubsub.punsubscribe.assert_not_called()

    async def test_disconnect_all_unsubscribes_tenant(
        self, ws_manager_with_pubsub, mock_pubsub
    ):
        """disconnect_all should unsubscribe tenant when last WS disconnects."""
        ws = self._make_ws()
        tenant_id = str(uuid4())
        channel = f"flowforge:{tenant_id}:execution:abc"

        await ws_manager_with_pubsub.connect(ws, channel)
        await ws_manager_with_pubsub.disconnect_all(ws)

        mock_pubsub.punsubscribe.assert_called_once_with(f"flowforge:{tenant_id}:*")

    async def test_multiple_tenants_independent_subscriptions(
        self, ws_manager_with_pubsub, mock_pubsub
    ):
        """Different tenants get independent subscribe/unsubscribe cycles."""
        ws_a = self._make_ws()
        ws_b = self._make_ws()
        tenant_a = str(uuid4())
        tenant_b = str(uuid4())

        await ws_manager_with_pubsub.connect(
            ws_a, f"flowforge:{tenant_a}:execution:abc"
        )
        await ws_manager_with_pubsub.connect(ws_b, f"flowforge:{tenant_b}:widget:xyz")

        assert mock_pubsub.psubscribe.call_count == 2

        # Disconnect tenant A only
        await ws_manager_with_pubsub.disconnect(
            ws_a, f"flowforge:{tenant_a}:execution:abc"
        )

        # Only tenant A should be unsubscribed
        mock_pubsub.punsubscribe.assert_called_once_with(f"flowforge:{tenant_a}:*")

        # Tenant B still subscribed
        assert ws_manager_with_pubsub._tenant_connections[tenant_b] == 1

    async def test_non_tenant_channel_no_subscription(
        self, ws_manager_with_pubsub, mock_pubsub
    ):
        """Channels without flowforge: prefix should not trigger tenant tracking."""
        ws = self._make_ws()

        await ws_manager_with_pubsub.connect(ws, "other:channel:format")

        mock_pubsub.psubscribe.assert_not_called()

    async def test_extract_tenant_id_valid(self):
        """_extract_tenant_id returns tenant_id for valid channel names."""
        assert (
            WebSocketManager._extract_tenant_id("flowforge:tenant-123:execution:abc")
            == "tenant-123"
        )

    async def test_extract_tenant_id_malformed(self):
        """_extract_tenant_id returns None for malformed channel names."""
        assert WebSocketManager._extract_tenant_id("other:tenant:type:id") is None
        assert WebSocketManager._extract_tenant_id("flowforge") is None
        assert WebSocketManager._extract_tenant_id("") is None
