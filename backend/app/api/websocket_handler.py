import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.metrics_service import metrics_service
from ..services.websocket_manager import websocket_manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/dashboard")
async def dashboard_ws(websocket: WebSocket):
    """
    Real-time push channel for the dashboard.
    Broadcasts incident_created, incident_updated, signal_received, rca_submitted events.
    """
    await websocket_manager.connect(websocket)
    try:
        # Send current metrics on connect so the UI boots with data immediately
        await websocket.send_text(json.dumps({
            "type": "connected",
            "metrics": metrics_service.get_stats(),
        }))

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except (json.JSONDecodeError, KeyError):
                pass
    except WebSocketDisconnect:
        await websocket_manager.disconnect(websocket)
