"""Socket identity, bounded I/O and serialized writes for a single backend worker."""

import asyncio
from dataclasses import dataclass, field

from fastapi import WebSocket

from app.core.logging import logger
from app.core.protocol import MAX_PEER_CONNECTIONS

SEND_TIMEOUT_SECONDS = 0.25


@dataclass
class Connection:
    """An ID stays reserved from handshake until domain cleanup has completed."""

    socket: WebSocket
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    usable: bool = False
    closing: bool = False


class ConnectionManager:
    """Serialize writes per socket; a slow peer cannot stall every controller."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._connections: dict[str, Connection] = {}

    async def connect(self, client_id: str, ws: WebSocket) -> bool:
        """Reserve the ID first, then perform bounded I/O outside the registry lock."""
        connection = Connection(ws)
        async with self._lock:
            rejected = client_id in self._connections or len(self._connections) >= MAX_PEER_CONNECTIONS
            if not rejected:
                self._connections[client_id] = connection
        if rejected:
            await self._close_socket(ws, code=1008, reason="Peer ID already connected or connection limit reached")
            return False

        accepted = False
        try:
            await asyncio.wait_for(ws.accept(), timeout=SEND_TIMEOUT_SECONDS)
            async with self._lock:
                if self._connections.get(client_id) is connection and not connection.closing:
                    connection.usable = True
                    accepted = True
            if accepted:
                logger.info("Connected %s", client_id)
            return accepted
        except (TimeoutError, RuntimeError, OSError):
            logger.warning("WebSocket handshake failed for %s", client_id)
            return False
        finally:
            if not accepted:
                await self.disconnect(client_id, ws)
                await self._close_socket(ws, code=1011)

    @staticmethod
    async def _close_socket(ws: WebSocket, **options) -> None:
        """A peer which stopped reading must not block rejection or shutdown."""
        try:
            await asyncio.wait_for(ws.close(**options), timeout=SEND_TIMEOUT_SECONDS)
        except Exception:
            pass

    async def is_current(self, client_id: str, ws: WebSocket) -> bool:
        async with self._lock:
            connection = self._connections.get(client_id)
            return connection is not None and connection.socket is ws and connection.usable

    async def disconnect(self, client_id: str, ws: WebSocket) -> bool:
        """Release this exact socket's reservation after its domain state is gone."""
        async with self._lock:
            current = self._connections.get(client_id)
            if current is None or current.socket is not ws:
                return False
            del self._connections[client_id]
        logger.info("Disconnected %s", client_id)
        return True

    async def begin_disconnect(self, client_id: str, ws: WebSocket) -> bool:
        """Stop all dispatch/writes while one endpoint owns domain teardown."""
        async with self._lock:
            connection = self._connections.get(client_id)
            if connection is None or connection.socket is not ws or connection.closing:
                return False
            connection.closing = True
            connection.usable = False
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
            await self._close_socket(connection.socket, code=1011)
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
        """Close transports; each endpoint still owns its identity-safe cleanup."""
        async with self._lock:
            sockets = [connection.socket for connection in self._connections.values()]
        await asyncio.gather(*(self._close_socket(ws, code=1001) for ws in sockets))
