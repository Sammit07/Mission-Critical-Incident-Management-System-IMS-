"""
WebSocket connection manager.
Maintains a set of active connections and broadcasts JSON messages to all of them.
"""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections.add(ws)
        logger.info("WS connected — active: %d", len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(ws)
        logger.info("WS disconnected — active: %d", len(self._connections))

    async def broadcast(self, data: dict) -> None:
        if not self._connections:
            return
        payload = json.dumps(data, default=str)
        dead: set[WebSocket] = set()

        async with self._lock:
            snapshot = set(self._connections)

        for ws in snapshot:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)

        if dead:
            async with self._lock:
                self._connections -= dead

    def connection_count(self) -> int:
        return len(self._connections)


websocket_manager = WebSocketManager()
