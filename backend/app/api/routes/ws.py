"""WebSocket endpoint for live execution status and data streaming.

WebSocket channels are tenant-scoped — the tenant_id is extracted from the
bearer token on connection and used to scope all pub/sub channels.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket connection for:
    - Execution status updates (pending -> running -> complete/error per node)
    - Live data pushes from Materialize-backed sources

    The WebSocket manager tracks connections and uses Redis pub/sub
    for multi-instance fan-out. All channels are prefixed with tenant_id.
    """
    await websocket.accept()

    # TODO: Extract tenant_id from bearer token query param or first message
    # TODO: Inject websocket_manager, register this connection with tenant scope
    # TODO: Subscribe to tenant-scoped Redis pub/sub channels
    #       Channel format: flowforge:{tenant_id}:execution:{execution_id}
    # TODO: Forward messages to this client

    try:
        while True:
            data = await websocket.receive_text()
            # Handle subscription requests from the client
            # e.g., subscribe to execution status for a specific workflow
            # e.g., subscribe to live data for a specific widget
            await websocket.send_json({"type": "ack", "data": data})
    except WebSocketDisconnect:
        # TODO: Unregister from websocket_manager
        pass
