"""Live data service — polls widget data and publishes changes via WebSocket.

For widgets with auto_refresh_interval == -1 (live mode), this service
periodically fetches data, hashes the result, and publishes to Redis
when data changes. Connected WebSocket clients receive the update.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.services.websocket_manager import WebSocketManager
    from app.services.widget_data_service import WidgetDataService

logger = logging.getLogger(__name__)

# How often to poll for live widget data changes (seconds)
POLL_INTERVAL = 2.0
# Max backoff on error (seconds)
MAX_BACKOFF = 30.0


class _WidgetSubscription:
    """Tracks a single live widget subscription."""

    __slots__ = ("tenant_id", "widget_id", "workflow_id", "last_hash", "task")

    def __init__(self, tenant_id: UUID, widget_id: UUID, workflow_id: UUID):
        self.tenant_id = tenant_id
        self.widget_id = widget_id
        self.workflow_id = workflow_id
        self.last_hash: str | None = None
        self.task: asyncio.Task | None = None  # type: ignore[type-arg]


class LiveDataService:
    """Manages background polling for live-mode widgets."""

    def __init__(
        self,
        ws_manager: WebSocketManager,
        widget_data_service: WidgetDataService,
    ):
        self._ws_manager = ws_manager
        self._widget_data_service = widget_data_service
        self._subscriptions: dict[UUID, _WidgetSubscription] = {}
        self._running = False

    def start(self) -> None:
        """Mark the service as running."""
        self._running = True
        logger.info("LiveDataService started")

    def stop(self) -> None:
        """Stop all polling tasks."""
        self._running = False
        for sub in self._subscriptions.values():
            if sub.task and not sub.task.done():
                sub.task.cancel()
        self._subscriptions.clear()
        logger.info("LiveDataService stopped")

    def subscribe_widget(
        self,
        tenant_id: UUID,
        widget_id: UUID,
        workflow_id: UUID,
    ) -> None:
        """Start polling for a live widget."""
        if widget_id in self._subscriptions:
            return

        sub = _WidgetSubscription(tenant_id, widget_id, workflow_id)
        sub.task = asyncio.create_task(self._poll_loop(sub))
        self._subscriptions[widget_id] = sub
        logger.info("Subscribed to live widget %s", widget_id)

    def unsubscribe_widget(self, widget_id: UUID) -> None:
        """Stop polling for a widget."""
        sub = self._subscriptions.pop(widget_id, None)
        if sub and sub.task and not sub.task.done():
            sub.task.cancel()
            logger.info("Unsubscribed from live widget %s", widget_id)

    async def _poll_loop(self, sub: _WidgetSubscription) -> None:
        """Background task that polls widget data and publishes changes."""
        backoff = POLL_INTERVAL
        while self._running:
            try:
                data = await self._widget_data_service.fetch_widget_data(
                    tenant_id=sub.tenant_id,
                    source_node_id="",  # Will be resolved by the service
                    graph_json={},
                    config_overrides={},
                    filter_params=None,
                    offset=0,
                    limit=100,
                )
                data_hash = hashlib.md5(
                    json.dumps(data, sort_keys=True, default=str).encode()
                ).hexdigest()

                if data_hash != sub.last_hash:
                    sub.last_hash = data_hash
                    await self._ws_manager.publish_live_data(
                        tenant_id=sub.tenant_id,
                        widget_id=sub.widget_id,
                        data=data,
                    )

                backoff = POLL_INTERVAL
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception(
                    "Error polling live widget %s, backing off %.1fs",
                    sub.widget_id,
                    backoff,
                )
                backoff = min(backoff * 2, MAX_BACKOFF)

            await asyncio.sleep(backoff)
