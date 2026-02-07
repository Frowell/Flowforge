"""Tests for LiveDataService subscribe/poll mode, ref counting, and health-check mode switching."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.live_data_service import LiveDataService


@pytest.fixture
def ws_manager():
    """Mock WebSocketManager with async publish_live_data."""
    mock = MagicMock()
    mock.publish_live_data = AsyncMock()
    return mock


@pytest.fixture
def widget_data_service():
    """Mock WidgetDataService with async fetch_widget_data."""
    mock = MagicMock()
    mock.fetch_widget_data = AsyncMock(return_value={"columns": [], "rows": []})
    return mock


@pytest.fixture
def materialize_client():
    """Mock MaterializeClient with async ping and subscribe."""
    mock = MagicMock()
    mock.ping = AsyncMock(return_value=True)
    mock.subscribe = AsyncMock()
    return mock


def _make_mock_task():
    """Create a mock asyncio.Task."""
    task = MagicMock(spec=asyncio.Task)
    task.done.return_value = False
    task.cancel.return_value = True
    return task


def _make_service(
    ws_manager,
    widget_data_service,
    materialize_client=None,
):
    """Create a LiveDataService without starting background tasks."""
    svc = LiveDataService(
        ws_manager=ws_manager,
        widget_data_service=widget_data_service,
        materialize_client=materialize_client,
    )
    return svc


class TestSubscribeWidgetModeSelection:
    """Tests for the initial mode selection in subscribe_widget."""

    @patch("app.services.live_data_service.settings")
    @patch("app.services.live_data_service.asyncio.create_task")
    def test_subscribe_widget_poll_mode_when_materialize_unavailable(
        self, mock_create_task, mock_settings, ws_manager, widget_data_service, materialize_client
    ):
        """When materialize is not available, subscribe_widget should use poll mode."""
        mock_settings.materialize_subscribe_enabled = True
        mock_create_task.return_value = _make_mock_task()
        svc = _make_service(ws_manager, widget_data_service, materialize_client)
        svc._running = True
        # Materialize is NOT available
        svc._materialize_available = False

        widget_id = uuid4()
        svc.subscribe_widget(
            tenant_id=uuid4(),
            widget_id=widget_id,
            workflow_id=uuid4(),
            view_name="live_positions",
        )

        sub = svc._subscriptions[widget_id]
        assert sub.mode == "poll"
        assert sub.task is not None

    @patch("app.services.live_data_service.settings")
    @patch("app.services.live_data_service.asyncio.create_task")
    def test_subscribe_widget_subscribe_mode_when_materialize_available(
        self, mock_create_task, mock_settings, ws_manager, widget_data_service, materialize_client
    ):
        """When materialize is available and view_name provided, should use subscribe mode."""
        mock_settings.materialize_subscribe_enabled = True
        mock_create_task.return_value = _make_mock_task()
        svc = _make_service(ws_manager, widget_data_service, materialize_client)
        svc._running = True
        svc._materialize_available = True

        widget_id = uuid4()
        svc.subscribe_widget(
            tenant_id=uuid4(),
            widget_id=widget_id,
            workflow_id=uuid4(),
            view_name="live_positions",
        )

        sub = svc._subscriptions[widget_id]
        assert sub.mode == "subscribe"
        # A shared view subscription should exist
        assert "live_positions" in svc._view_subscriptions

    @patch("app.services.live_data_service.settings")
    @patch("app.services.live_data_service.asyncio.create_task")
    def test_subscribe_widget_fallback_to_poll_without_view_name(
        self, mock_create_task, mock_settings, ws_manager, widget_data_service, materialize_client
    ):
        """Even with materialize available, no view_name means poll mode."""
        mock_settings.materialize_subscribe_enabled = True
        mock_create_task.return_value = _make_mock_task()
        svc = _make_service(ws_manager, widget_data_service, materialize_client)
        svc._running = True
        svc._materialize_available = True

        widget_id = uuid4()
        svc.subscribe_widget(
            tenant_id=uuid4(),
            widget_id=widget_id,
            workflow_id=uuid4(),
            view_name=None,
        )

        sub = svc._subscriptions[widget_id]
        assert sub.mode == "poll"


class TestRefCounting:
    """Tests for shared view subscription reference counting."""

    @patch("app.services.live_data_service.settings")
    @patch("app.services.live_data_service.asyncio.create_task")
    def test_ref_counting_shared_view_subscription(
        self, mock_create_task, mock_settings, ws_manager, widget_data_service, materialize_client
    ):
        """Two widgets on same view share one ViewSubscription, ref_count = 2."""
        mock_settings.materialize_subscribe_enabled = True
        mock_create_task.return_value = _make_mock_task()
        svc = _make_service(ws_manager, widget_data_service, materialize_client)
        svc._running = True
        svc._materialize_available = True

        tenant_id = uuid4()
        widget_a = uuid4()
        widget_b = uuid4()
        view_name = "live_positions"

        svc.subscribe_widget(tenant_id, widget_a, uuid4(), view_name=view_name)
        svc.subscribe_widget(tenant_id, widget_b, uuid4(), view_name=view_name)

        view_sub = svc._view_subscriptions[view_name]
        assert view_sub.ref_count == 2
        assert widget_a in view_sub.widget_ids
        assert widget_b in view_sub.widget_ids

    @patch("app.services.live_data_service.settings")
    @patch("app.services.live_data_service.asyncio.create_task")
    def test_unsubscribe_decrements_ref_count(
        self, mock_create_task, mock_settings, ws_manager, widget_data_service, materialize_client
    ):
        """Unsubscribing one widget decrements ref_count."""
        mock_settings.materialize_subscribe_enabled = True
        mock_create_task.return_value = _make_mock_task()
        svc = _make_service(ws_manager, widget_data_service, materialize_client)
        svc._running = True
        svc._materialize_available = True

        tenant_id = uuid4()
        widget_a = uuid4()
        widget_b = uuid4()
        view_name = "live_positions"

        svc.subscribe_widget(tenant_id, widget_a, uuid4(), view_name=view_name)
        svc.subscribe_widget(tenant_id, widget_b, uuid4(), view_name=view_name)

        svc.unsubscribe_widget(widget_a)

        view_sub = svc._view_subscriptions[view_name]
        assert view_sub.ref_count == 1
        assert widget_a not in view_sub.widget_ids
        assert widget_b in view_sub.widget_ids

    @patch("app.services.live_data_service.settings")
    @patch("app.services.live_data_service.asyncio.create_task")
    def test_unsubscribe_last_widget_cancels_view_task(
        self, mock_create_task, mock_settings, ws_manager, widget_data_service, materialize_client
    ):
        """When ref_count reaches 0, the view task is cancelled and view sub is removed."""
        mock_settings.materialize_subscribe_enabled = True
        mock_task = _make_mock_task()
        mock_create_task.return_value = mock_task
        svc = _make_service(ws_manager, widget_data_service, materialize_client)
        svc._running = True
        svc._materialize_available = True

        tenant_id = uuid4()
        widget_a = uuid4()
        view_name = "live_positions"

        svc.subscribe_widget(tenant_id, widget_a, uuid4(), view_name=view_name)

        # The task returned by create_task is already assigned to view_sub.task
        svc.unsubscribe_widget(widget_a)

        mock_task.cancel.assert_called_once()
        assert view_name not in svc._view_subscriptions


class TestHealthCheckModeSwitching:
    """Tests for _upgrade_to_subscribe and _downgrade_to_poll."""

    @patch("app.services.live_data_service.settings")
    @patch("app.services.live_data_service.asyncio.create_task")
    def test_health_check_upgrades_to_subscribe(
        self, mock_create_task, mock_settings, ws_manager, widget_data_service, materialize_client
    ):
        """When materialize becomes available, poll-mode widgets with view_name switch to subscribe."""
        mock_settings.materialize_subscribe_enabled = True
        mock_create_task.return_value = _make_mock_task()
        svc = _make_service(ws_manager, widget_data_service, materialize_client)
        svc._running = True
        svc._materialize_available = False

        tenant_id = uuid4()
        widget_id = uuid4()

        # Subscribe in poll mode (materialize not available yet)
        svc.subscribe_widget(tenant_id, widget_id, uuid4(), view_name="live_pnl")
        assert svc._subscriptions[widget_id].mode == "poll"

        # Simulate materialize becoming available
        svc._materialize_available = True
        svc._upgrade_to_subscribe()

        assert svc._subscriptions[widget_id].mode == "subscribe"
        assert "live_pnl" in svc._view_subscriptions

    @patch("app.services.live_data_service.settings")
    @patch("app.services.live_data_service.asyncio.create_task")
    def test_health_check_downgrades_to_poll(
        self, mock_create_task, mock_settings, ws_manager, widget_data_service, materialize_client
    ):
        """When materialize becomes unavailable, subscribe-mode widgets switch to poll."""
        mock_settings.materialize_subscribe_enabled = True
        mock_create_task.return_value = _make_mock_task()
        svc = _make_service(ws_manager, widget_data_service, materialize_client)
        svc._running = True
        svc._materialize_available = True

        tenant_id = uuid4()
        widget_id = uuid4()

        # Subscribe in subscribe mode
        svc.subscribe_widget(tenant_id, widget_id, uuid4(), view_name="live_pnl")
        assert svc._subscriptions[widget_id].mode == "subscribe"
        assert "live_pnl" in svc._view_subscriptions

        # Simulate materialize becoming unavailable
        svc._materialize_available = False
        svc._downgrade_to_poll()

        assert svc._subscriptions[widget_id].mode == "poll"
        assert svc._subscriptions[widget_id].task is not None
        # View subscriptions should be cleared
        assert len(svc._view_subscriptions) == 0


class TestStop:
    """Tests for the stop() method."""

    @patch("app.services.live_data_service.settings")
    @patch("app.services.live_data_service.asyncio.create_task")
    def test_stop_cancels_all_tasks(
        self, mock_create_task, mock_settings, ws_manager, widget_data_service, materialize_client
    ):
        """stop() cancels all poll tasks, subscribe tasks, and health check task."""
        mock_settings.materialize_subscribe_enabled = True

        # Return distinct mock tasks for each create_task call
        poll_task = _make_mock_task()
        subscribe_task = _make_mock_task()
        mock_create_task.side_effect = [poll_task, subscribe_task]

        svc = _make_service(ws_manager, widget_data_service, materialize_client)
        svc._running = True
        svc._materialize_available = True

        tenant_id = uuid4()

        # Create a poll-mode widget (no view_name)
        poll_widget = uuid4()
        svc.subscribe_widget(tenant_id, poll_widget, uuid4(), view_name=None)

        # Create a subscribe-mode widget
        sub_widget = uuid4()
        svc.subscribe_widget(tenant_id, sub_widget, uuid4(), view_name="live_pnl")

        # Set up a mock health check task
        health_task = _make_mock_task()
        svc._health_check_task = health_task

        svc.stop()

        poll_task.cancel.assert_called_once()
        subscribe_task.cancel.assert_called_once()
        health_task.cancel.assert_called_once()
        assert svc._running is False
        assert len(svc._subscriptions) == 0
        assert len(svc._view_subscriptions) == 0
