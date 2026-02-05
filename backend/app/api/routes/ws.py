"""WebSocket endpoint for live execution status and data streaming.

WebSocket channels are tenant-scoped — the tenant_id is extracted from the
bearer token on connection and used to scope all pub/sub channels.
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.auth import _decode_token
from app.core.config import settings
from app.services.websocket_manager import CHANNEL_PREFIX, WebSocketManager

logger = logging.getLogger(__name__)

router = APIRouter()


async def _extract_tenant_id(token: str) -> str | None:
    """Extract tenant_id from a JWT token. Returns None if invalid."""
    try:
        payload = await _decode_token(token)
        return payload.get("tenant_id")
    except Exception:
        return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection for:
    - Execution status updates (pending -> running -> complete/error per node)
    - Live data pushes from Materialize-backed sources

    The WebSocket manager tracks connections and uses Redis pub/sub
    for multi-instance fan-out. All channels are prefixed with tenant_id.

    Query params:
        token: JWT access token for authentication
    """
    token = websocket.query_params.get("token")

    # Dev-mode bypass
    if settings.app_env == "development" and not token:
        tenant_id = settings.dev_tenant_id
    elif not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    else:
        tenant_id = await _extract_tenant_id(token)
        if not tenant_id:
            await websocket.close(code=4001, reason="Invalid token")
            return

    # Get WebSocket manager from app state (Depends doesn't work with WS)
    ws_manager: WebSocketManager = websocket.app.state.ws_manager

    # Connect to the general tenant channel
    general_channel = f"{CHANNEL_PREFIX}:{tenant_id}:general"
    await ws_manager.connect(websocket, general_channel)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            action = msg.get("action")
            channel_suffix = msg.get("channel", "")

            if action == "subscribe" and channel_suffix:
                # Always prepend tenant prefix to prevent cross-tenant leakage
                full_channel = f"{CHANNEL_PREFIX}:{tenant_id}:{channel_suffix}"
                await ws_manager.subscribe_to_channel(websocket, full_channel)
                await websocket.send_json(
                    {"type": "subscribed", "channel": channel_suffix}
                )

            elif action == "unsubscribe" and channel_suffix:
                full_channel = f"{CHANNEL_PREFIX}:{tenant_id}:{channel_suffix}"
                await ws_manager.unsubscribe_from_channel(websocket, full_channel)
                await websocket.send_json(
                    {"type": "unsubscribed", "channel": channel_suffix}
                )

            else:
                await websocket.send_json({"type": "error", "detail": "Unknown action"})

    except WebSocketDisconnect:
        await ws_manager.disconnect_all(websocket)
    except Exception:
        logger.exception("WebSocket error")
        await ws_manager.disconnect_all(websocket)
