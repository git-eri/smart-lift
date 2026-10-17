import asyncio
from dataclasses import dataclass, field

from fastapi import WebSocket

from app.core.logging import logger

SEND_TIMEOUT_SECONDS = 0.25


@dataclass
class Connection:
    socket: WebSocket
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    usable: bool = True


class ConnectionManager:
    """Serialize writes per socket; a slow peer cannot stall every controller."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._connections: dict[str, Connection] = {}

    async def connect(self, client_id: str, ws: WebSocket) -> bool:
        async with self._lock:
            if client_id in self._connections or len(self._connections) >= 128:
                await ws.close(code=1008, reason="Peer ID already connected or connection limit reached")
                return False
            await ws.accept()
            self._connections[client_id] = Connection(ws)
        logger.info("Connected %s", client_id)
        return True

    async def is_current(self, client_id: str, ws: WebSocket) -> bool:
        async with self._lock:
            connection = self._connections.get(client_id)
            return connection is not None and connection.socket is ws and connection.usable

    async def disconnect(self, client_id: str, ws: WebSocket) -> bool:
        async with self._lock:
            current = self._connections.get(client_id)
            if current is None or current.socket is not ws:
                return False
            del self._connections[client_id]
        logger.info("Disconnected %s", client_id)
        return True

    async def send(self, client_id: str, message: str) -> bool:
        async with self._lock:
            connection = self._connections.get(client_id)
        if connection is None or not connection.usable:
            return False

        async def write():
            async with connection.send_lock:
                if not connection.usable:
                    return False
                await connection.socket.send_text(message)
                return True

        try:
            return await asyncio.wait_for(write(), timeout=SEND_TIMEOUT_SECONDS)
        except (TimeoutError, RuntimeError, OSError):
            logger.warning("Send failed for %s; closing connection", client_id)
        except Exception:
            logger.exception("Unexpected WebSocket send failure for %s", client_id)
        # The endpoint's finally block owns cleanup; a failed send must not
        # silently orphan domain state or remove a different session.
        if connection.usable:
            # Leave the identity registered for endpoint cleanup, but stop
            # retrying this peer in every subsequent control-state broadcast.
            connection.usable = False
            try:
                await asyncio.wait_for(connection.socket.close(code=1011), SEND_TIMEOUT_SECONDS)
            except Exception:
                pass
        return False

    async def _broadcast(self, message: str, prefix: str = "") -> None:
        async with self._lock:
            ids = [peer for peer, connection in self._connections.items()
                   if peer.startswith(prefix) and connection.usable]
        await asyncio.gather(*(self.send(peer, message) for peer in ids))

    async def broadcast(self, message: str) -> None:
        await self._broadcast(message)

    async def broadcast_clients(self, message: str) -> None:
        await self._broadcast(message, "cli")

    async def close_all(self) -> None:
        async with self._lock:
            sockets = [connection.socket for connection in self._connections.values()]
        async def close(ws):
            try:
                await asyncio.wait_for(ws.close(code=1001), SEND_TIMEOUT_SECONDS)
            except Exception:
                pass
        await asyncio.gather(*(close(ws) for ws in sockets))
