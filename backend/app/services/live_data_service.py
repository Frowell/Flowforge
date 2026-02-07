"""Live data service — polls or subscribes to widget data via WebSocket.

For widgets with auto_refresh_interval == -1 (live mode), this service
periodically fetches data (poll mode) or uses Materialize SUBSCRIBE
(subscribe mode), hashes the result, and publishes to Redis
when data changes. Connected WebSocket clients receive the update.

When Materialize is available and subscribe is enabled, widgets backed
by Materialize views use SUBSCRIBE for lower latency. Otherwise they
fall back to polling. A periodic health check switches modes dynamically.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import TYPE_CHECKING
from uuid import UUID

from app.core.config import settings

if TYPE_CHECKING:
    from app.core.materialize import MaterializeClient
    from app.services.websocket_manager import WebSocketManager
    from app.services.widget_data_service import WidgetDataService

logger = logging.getLogger(__name__)

# How often to poll for live widget data changes (seconds)
POLL_INTERVAL = 2.0
# Max backoff on error (seconds)
MAX_BACKOFF = 30.0
# Health check interval for Materialize availability (seconds)
HEALTH_CHECK_INTERVAL = 30.0


class _ViewSubscription:
    """Tracks a shared SUBSCRIBE connection for a Materialize view.

    Multiple widgets on the same view share one SUBSCRIBE connection.
    """

    __slots__ = ("view_name", "widget_ids", "task", "ref_count")

    def __init__(self, view_name: str):
        self.view_name = view_name
        self.widget_ids: set[UUID] = set()
        self.task: asyncio.Task | None = None  # type: ignore[type-arg]
        self.ref_count = 0


class _WidgetSubscription:
    """Tracks a single live widget subscription."""

    __slots__ = (
        "tenant_id",
        "widget_id",
        "workflow_id",
        "view_name",
        "last_hash",
        "task",
        "mode",
    )

    def __init__(
        self,
        tenant_id: UUID,
        widget_id: UUID,
        workflow_id: UUID,
        view_name: str | None = None,
    ):
        self.tenant_id = tenant_id
        self.widget_id = widget_id
        self.workflow_id = workflow_id
        self.view_name = view_name
        self.last_hash: str | None = None
        self.task: asyncio.Task | None = None  # type: ignore[type-arg]
        self.mode: str = "poll"  # "poll" or "subscribe"


class LiveDataService:
    """Manages background polling/subscribing for live-mode widgets."""

    def __init__(
        self,
        ws_manager: WebSocketManager,
        widget_data_service: WidgetDataService,
        materialize_client: MaterializeClient | None = None,
    ):
        self._ws_manager = ws_manager
        self._widget_data_service = widget_data_service
        self._materialize: MaterializeClient | None = materialize_client
        self._subscriptions: dict[UUID, _WidgetSubscription] = {}
        self._view_subscriptions: dict[str, _ViewSubscription] = {}
        self._running = False
        self._materialize_available = False
        self._health_check_task: asyncio.Task | None = None  # type: ignore[type-arg]

    def start(self) -> None:
        """Mark the service as running and start health checks."""
        self._running = True
        if (
            self._materialize is not None
            and settings.materialize_subscribe_enabled
        ):
            self._health_check_task = asyncio.create_task(
                self._materialize_health_loop()
            )
        logger.info("LiveDataService started")

    def stop(self) -> None:
        """Stop all polling/subscribe tasks."""
        self._running = False
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
        for sub in self._subscriptions.values():
            if sub.task and not sub.task.done():
                sub.task.cancel()
        for view_sub in self._view_subscriptions.values():
            if view_sub.task and not view_sub.task.done():
                view_sub.task.cancel()
        self._subscriptions.clear()
        self._view_subscriptions.clear()
        logger.info("LiveDataService stopped")

    def subscribe_widget(
        self,
        tenant_id: UUID,
        widget_id: UUID,
        workflow_id: UUID,
        view_name: str | None = None,
    ) -> None:
        """Start polling or subscribing for a live widget."""
        if widget_id in self._subscriptions:
            return

        sub = _WidgetSubscription(tenant_id, widget_id, workflow_id, view_name)

        # Decide mode: if Materialize is available and widget has a view, use subscribe
        if (
            self._materialize_available
            and settings.materialize_subscribe_enabled
            and view_name
        ):
            self._start_subscribe_mode(sub)
        else:
            self._start_poll_mode(sub)

        self._subscriptions[widget_id] = sub
        logger.info(
            "Subscribed to live widget %s (mode=%s)", widget_id, sub.mode
        )

    def unsubscribe_widget(self, widget_id: UUID) -> None:
        """Stop polling/subscribing for a widget."""
        sub = self._subscriptions.pop(widget_id, None)
        if sub is None:
            return

        if sub.mode == "subscribe" and sub.view_name:
            self._release_view_subscription(sub.view_name, widget_id)
        elif sub.task and not sub.task.done():
            sub.task.cancel()

        logger.info("Unsubscribed from live widget %s", widget_id)

    def _start_poll_mode(self, sub: _WidgetSubscription) -> None:
        """Start the poll loop for a widget."""
        sub.mode = "poll"
        sub.task = asyncio.create_task(self._poll_loop(sub))

    def _start_subscribe_mode(self, sub: _WidgetSubscription) -> None:
        """Start or join a shared SUBSCRIBE for the widget's view."""
        sub.mode = "subscribe"
        view_name = sub.view_name
        if not view_name:
            self._start_poll_mode(sub)
            return

        if view_name not in self._view_subscriptions:
            view_sub = _ViewSubscription(view_name)
            self._view_subscriptions[view_name] = view_sub
            view_sub.task = asyncio.create_task(
                self._subscribe_loop(view_name, sub.tenant_id)
            )

        view_sub = self._view_subscriptions[view_name]
        view_sub.widget_ids.add(sub.widget_id)
        view_sub.ref_count += 1

    def _release_view_subscription(
        self, view_name: str, widget_id: UUID
    ) -> None:
        """Decrement ref count on a shared view subscription."""
        view_sub = self._view_subscriptions.get(view_name)
        if view_sub is None:
            return

        view_sub.widget_ids.discard(widget_id)
        view_sub.ref_count -= 1

        if view_sub.ref_count <= 0:
            if view_sub.task and not view_sub.task.done():
                view_sub.task.cancel()
            del self._view_subscriptions[view_name]

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

    async def _subscribe_loop(
        self, view_name: str, tenant_id: UUID
    ) -> None:
        """Background task that SUBSCRIBEs to a Materialize view.

        Publishes changes to all widgets watching this view.
        Falls back to poll mode on failure.
        """
        if self._materialize is None:
            return

        backoff = POLL_INTERVAL
        while self._running:
            try:
                async for mz_timestamp, mz_diff, row in self._materialize.subscribe(
                    view_name
                ):
                    if not self._running:
                        return

                    view_sub = self._view_subscriptions.get(view_name)
                    if view_sub is None:
                        return

                    data = {
                        "mz_timestamp": mz_timestamp,
                        "mz_diff": mz_diff,
                        "row": row,
                    }

                    for widget_id in view_sub.widget_ids:
                        sub = self._subscriptions.get(widget_id)
                        if sub:
                            await self._ws_manager.publish_live_data(
                                tenant_id=tenant_id,
                                widget_id=widget_id,
                                data=data,
                            )

                backoff = POLL_INTERVAL
            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception(
                    "SUBSCRIBE to %s failed, backing off %.1fs",
                    view_name,
                    backoff,
                )
                backoff = min(backoff * 2, MAX_BACKOFF)

            await asyncio.sleep(backoff)

    async def _materialize_health_loop(self) -> None:
        """Periodically check Materialize availability and switch modes."""
        while self._running:
            try:
                was_available = self._materialize_available
                if self._materialize:
                    self._materialize_available = await self._materialize.ping()
                else:
                    self._materialize_available = False

                # Mode switching
                if self._materialize_available and not was_available:
                    logger.info(
                        "Materialize became available, "
                        "switching eligible widgets to subscribe mode"
                    )
                    self._upgrade_to_subscribe()
                elif not self._materialize_available and was_available:
                    logger.info(
                        "Materialize became unavailable, "
                        "falling back all widgets to poll mode"
                    )
                    self._downgrade_to_poll()

            except asyncio.CancelledError:
                return
            except Exception:
                logger.exception("Materialize health check failed")

            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

    def _upgrade_to_subscribe(self) -> None:
        """Switch eligible poll-mode widgets to subscribe mode."""
        for sub in list(self._subscriptions.values()):
            if sub.mode == "poll" and sub.view_name:
                if sub.task and not sub.task.done():
                    sub.task.cancel()
                self._start_subscribe_mode(sub)

    def _downgrade_to_poll(self) -> None:
        """Switch all subscribe-mode widgets back to poll mode."""
        # Cancel all view subscriptions
        for view_sub in list(self._view_subscriptions.values()):
            if view_sub.task and not view_sub.task.done():
                view_sub.task.cancel()
        self._view_subscriptions.clear()

        # Restart widgets in poll mode
        for sub in self._subscriptions.values():
            if sub.mode == "subscribe":
                self._start_poll_mode(sub)
