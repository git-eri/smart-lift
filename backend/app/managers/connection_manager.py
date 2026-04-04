import asyncio
from typing import Dict, Optional
from fastapi import WebSocket

from app.core.logging import logger


class ConnectionManager:
    """Tracks active WebSocket connections in a threadsafe (async) way."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, ws: WebSocket) -> None:
        """Accept the socket and ensure at most one connection per id."""
        await ws.accept()

        async with self._lock:
            old = self._connections.pop(client_id, None)

            if old is not None:
                try:
                    await old.close()
                except Exception:
                    pass

            self._connections[client_id] = ws

            logger.debug(
                "Connected %s (total=%d)",
                client_id,
                len(self._connections),
            )

    async def disconnect(self, client_id: str, ws: Optional[WebSocket] = None) -> None:
        """Forget the connection. Does not close `ws`."""
        async with self._lock:
            current = self._connections.get(client_id)

            if current is ws or (ws is None and current is not None):
                self._connections.pop(client_id, None)

                logger.debug(
                    "Disconnected %s (total=%d)",
                    client_id,
                    len(self._connections),
                )

    async def send(self, client_id: str, message: str) -> None:
        """Send a text message to a specific connection."""
        async with self._lock:
            ws = self._connections.get(client_id)

        if not ws:
            return

        try:
            await ws.send_text(message)
        except Exception:
            await self.disconnect(client_id)

    async def broadcast(self, message: str) -> None:
        """Send message to all connections."""
        async with self._lock:
            items = list(self._connections.items())

        for cid, ws in items:
            try:
                await ws.send_text(message)
            except Exception:
                await self.disconnect(cid)

    async def broadcast_clients(self, message: str) -> None:
        """Send message to all 'cli*' connections."""
        async with self._lock:
            items = [
                (cid, ws)
                for cid, ws in self._connections.items()
                if cid.startswith("cli")
            ]

        for cid, ws in items:
            try:
                await ws.send_text(message)
            except Exception:
                await self.disconnect(cid)