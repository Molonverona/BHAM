"""
BHAM – WebSocket Connection Manager
Manages all active WebSocket connections and provides broadcast utilities.
Log records and scan events are pushed in real-time to every connected client.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from core.logger import logger, register_ws_hook

log = logging.getLogger("bham.ws")


class ConnectionManager:
    """
    Keeps track of all live WebSocket connections and exposes
    broadcast / unicast helpers.

    Usage (in route handler):
        await manager.connect(websocket)
        try:
            while True:
                data = await websocket.receive_json()
                await manager.handle_client_message(websocket, data)
        except WebSocketDisconnect:
            manager.disconnect(websocket)
    """

    def __init__(self) -> None:
        self._active: list[WebSocket] = []
        # Queue for cross-thread event injection (scanners run in thread-pool)
        self._queue: asyncio.Queue[dict] = asyncio.Queue()
        self._pump_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def startup(self) -> None:
        """Start the background queue-pump coroutine. Call once at app startup."""
        self._loop = asyncio.get_running_loop()
        self._pump_task = asyncio.create_task(self._pump_queue(), name="ws-pump")
        # Register log hook so every log line also reaches WebSocket clients
        register_ws_hook(self._enqueue_log)
        log.info("WebSocket ConnectionManager started.")

    async def shutdown(self) -> None:
        """Gracefully cancel the pump task."""
        if self._pump_task and not self._pump_task.done():
            self._pump_task.cancel()
            try:
                await self._pump_task
            except asyncio.CancelledError:
                pass
        log.info("WebSocket ConnectionManager stopped.")

    # ── Connection helpers ────────────────────────────────────────────────────

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active.append(websocket)
        log.info("WS client connected – total: %d", len(self._active))
        # Send a full state snapshot immediately on connection
        from data.state import state
        await self._send_json(websocket, {"event": "snapshot", "data": state.snapshot()})

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._active:
            self._active.remove(websocket)
        log.info("WS client disconnected – remaining: %d", len(self._active))

    # ── Broadcast ────────────────────────────────────────────────────────────

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """Send *payload* (serialised as JSON) to every connected client."""
        dead: list[WebSocket] = []
        for ws in list(self._active):
            try:
                await ws.send_text(json.dumps(payload, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    def broadcast_sync(self, payload: dict[str, Any]) -> None:
        """
        Thread-safe variant: enqueues *payload* for delivery by the pump task.
        Call from synchronous scanner code or logging hooks.
        """
        if self._loop:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, payload)

    # ── Log streaming ────────────────────────────────────────────────────────

    def _enqueue_log(self, message: str) -> None:
        """Called by the logger WebSocketHandler on every record."""
        if self._loop:
            self._loop.call_soon_threadsafe(
                self._queue.put_nowait,
                {"event": "log", "message": message}
            )

    # ── State hook (registered with AppState) ────────────────────────────────

    def enqueue_state_event(self, payload: dict) -> None:
        """Registered with AppState.register_broadcast_hook; thread-safe."""
        if self._loop:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, payload)

    # ── Pump coroutine ────────────────────────────────────────────────────────

    async def _pump_queue(self) -> None:
        """Drain the internal queue and broadcast each item."""
        while True:
            payload = await self._queue.get()
            await self.broadcast(payload)

    # ── Client message dispatcher ─────────────────────────────────────────────

    async def handle_client_message(
        self, websocket: WebSocket, data: dict[str, Any]
    ) -> None:
        """
        Dispatch inbound WS messages from the browser.
        Currently supported commands:
          { "cmd": "ping" }            → {"event": "pong"}
          { "cmd": "get_snapshot" }    → full state snapshot
        """
        cmd = data.get("cmd", "")
        match cmd:
            case "ping":
                await self._send_json(websocket, {"event": "pong"})
            case "get_snapshot":
                from data.state import state
                await self._send_json(
                    websocket, {"event": "snapshot", "data": state.snapshot()}
                )
            case _:
                await self._send_json(
                    websocket, {"event": "error", "detail": f"Unknown command: {cmd}"}
                )

    # ── Internal helper ───────────────────────────────────────────────────────

    @staticmethod
    async def _send_json(ws: WebSocket, payload: dict) -> None:
        try:
            await ws.send_text(json.dumps(payload, default=str))
        except Exception as exc:
            log.debug("Failed to send JSON to WS client: %s", exc)


# ── Module-level singleton ────────────────────────────────────────────────────
manager = ConnectionManager()
