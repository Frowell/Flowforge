"""Tests for WebSocket endpoint."""

import json
from unittest.mock import AsyncMock, MagicMock

from app.services.websocket_manager import WebSocketManager


class TestWebSocketManager:
    """Unit tests for the WebSocket manager itself (no network)."""

    async def test_publish_execution_status_includes_tenant(self):
        """Execution status messages publish to tenant-scoped channels."""
        from uuid import UUID

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock()
        manager = WebSocketManager(mock_redis)

        tenant_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        exec_id = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

        await manager.publish_execution_status(
            tenant_id=tenant_id,
            execution_id=exec_id,
            node_id="node1",
            status="running",
        )

        mock_redis.publish.assert_awaited_once()
        call_args = mock_redis.publish.call_args
        channel = call_args[0][0]
        assert f"flowforge:{tenant_id}:execution:{exec_id}" == channel
        payload = json.loads(call_args[0][1])
        assert payload["type"] == "execution_status"
        assert payload["node_id"] == "node1"
        assert payload["status"] == "running"

    async def test_publish_live_data_includes_tenant(self):
        """Live data messages publish to tenant-scoped widget channels."""
        from uuid import UUID

        mock_redis = MagicMock()
        mock_redis.publish = AsyncMock()
        manager = WebSocketManager(mock_redis)

        tenant_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        widget_id = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")

        await manager.publish_live_data(
            tenant_id=tenant_id,
            widget_id=widget_id,
            data={"rows": [{"price": 150}]},
        )

        mock_redis.publish.assert_awaited_once()
        channel = mock_redis.publish.call_args[0][0]
        assert f"flowforge:{tenant_id}:widget:{widget_id}" == channel

    async def test_subscribe_and_unsubscribe_channels(self):
        """WebSocket can subscribe/unsubscribe to multiple channels."""
        mock_redis = MagicMock()
        manager = WebSocketManager(mock_redis)

        mock_ws = AsyncMock()
        # Manually register (without calling accept)
        manager._ws_channels[mock_ws] = set()

        await manager.subscribe_to_channel(mock_ws, "flowforge:t1:widget:w1")
        assert "flowforge:t1:widget:w1" in manager._ws_channels[mock_ws]
        assert mock_ws in manager._connections.get("flowforge:t1:widget:w1", set())

        await manager.unsubscribe_from_channel(mock_ws, "flowforge:t1:widget:w1")
        assert "flowforge:t1:widget:w1" not in manager._ws_channels.get(mock_ws, set())

    async def test_disconnect_all_removes_from_all_channels(self):
        """disconnect_all removes WebSocket from every channel."""
        mock_redis = MagicMock()
        manager = WebSocketManager(mock_redis)

        mock_ws = AsyncMock()
        manager._ws_channels[mock_ws] = {"ch1", "ch2"}
        manager._connections["ch1"] = {mock_ws}
        manager._connections["ch2"] = {mock_ws}

        await manager.disconnect_all(mock_ws)
        assert mock_ws not in manager._ws_channels
        assert mock_ws not in manager._connections.get("ch1", set())
        assert mock_ws not in manager._connections.get("ch2", set())

    async def test_broadcast_to_channel_sends_to_all(self):
        """Broadcast sends messages to all connections on a channel."""
        mock_redis = MagicMock()
        manager = WebSocketManager(mock_redis)

        ws1 = AsyncMock()
        ws2 = AsyncMock()
        manager._connections["test_channel"] = {ws1, ws2}

        await manager._broadcast_to_channel("test_channel", '{"test": true}')
        ws1.send_text.assert_awaited_once_with('{"test": true}')
        ws2.send_text.assert_awaited_once_with('{"test": true}')

    async def test_broadcast_removes_dead_connections(self):
        """Dead connections are removed from the channel on send failure."""
        mock_redis = MagicMock()
        manager = WebSocketManager(mock_redis)

        ws_good = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_text.side_effect = Exception("Connection closed")
        manager._connections["test_channel"] = {ws_good, ws_dead}

        await manager._broadcast_to_channel("test_channel", '{"test": true}')
        assert ws_dead not in manager._connections["test_channel"]
        assert ws_good in manager._connections["test_channel"]

    async def test_tenant_isolation_in_channels(self):
        """Messages on tenant A's channel don't reach tenant B."""
        mock_redis = MagicMock()
        manager = WebSocketManager(mock_redis)

        ws_a = AsyncMock()
        ws_b = AsyncMock()

        tenant_a_channel = "flowforge:tenant-a:widget:w1"
        tenant_b_channel = "flowforge:tenant-b:widget:w1"

        manager._connections[tenant_a_channel] = {ws_a}
        manager._connections[tenant_b_channel] = {ws_b}

        # Broadcast to tenant A's channel
        await manager._broadcast_to_channel(tenant_a_channel, '{"data": "for A"}')

        ws_a.send_text.assert_awaited_once()
        ws_b.send_text.assert_not_awaited()
