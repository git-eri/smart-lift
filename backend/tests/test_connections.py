import asyncio
import unittest
from unittest.mock import patch

from app.managers.connection_manager import ConnectionManager


class Socket:
    def __init__(self, fail=False):
        self.accepted = False
        self.closed = False
        self.fail = fail
        self.writing = False
        self.messages = []

    async def accept(self):
        self.accepted = True

    async def close(self, **kwargs):
        self.closed = True

    async def send_text(self, message):
        if self.fail:
            raise OSError("closed")
        if self.writing:
            raise AssertionError("Concurrent writes on same WebSocket")
        self.writing = True
        await asyncio.sleep(0)
        self.messages.append(message)
        self.writing = False


class ConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_duplicate_id_cannot_replace_active_controller(self):
        manager = ConnectionManager()
        original, duplicate = Socket(), Socket()
        self.assertTrue(await manager.connect("con1", original))
        self.assertFalse(await manager.connect("con1", duplicate))
        self.assertTrue(duplicate.closed)
        self.assertTrue(await manager.is_current("con1", original))
        self.assertFalse(await manager.disconnect("con1", duplicate))

    async def test_parallel_broadcasts_and_direct_messages_are_serialized(self):
        manager, socket = ConnectionManager(), Socket()
        await manager.connect("cli1", socket)
        results = await asyncio.gather(*(manager.send("cli1", str(i)) for i in range(25)))
        self.assertTrue(all(results))
        self.assertEqual(len(socket.messages), 25)

    async def test_blocked_accept_does_not_hold_registry_lock_or_orphan_id(self):
        entered = asyncio.Event()
        class BlockedAccept(Socket):
            async def accept(self):
                entered.set()
                await asyncio.Event().wait()

        manager, healthy = ConnectionManager(), Socket()
        await manager.connect("cliHealthy", healthy)
        with patch("app.managers.connection_manager.SEND_TIMEOUT_SECONDS", 0.1):
            pending = asyncio.create_task(manager.connect("cliWaiting", BlockedAccept()))
            await asyncio.wait_for(entered.wait(), 1)
            self.assertTrue(await asyncio.wait_for(manager.send("cliHealthy", "still responsive"), 0.05))
            self.assertFalse(await pending)
            self.assertTrue(await manager.connect("cliWaiting", Socket()))

    async def test_blocked_duplicate_close_does_not_hold_registry_lock(self):
        entered = asyncio.Event()
        class BlockedClose(Socket):
            async def close(self, **kwargs):
                entered.set()
                await asyncio.Event().wait()

        manager, original = ConnectionManager(), Socket()
        await manager.connect("con1", original)
        with patch("app.managers.connection_manager.SEND_TIMEOUT_SECONDS", 0.1):
            rejection = asyncio.create_task(manager.connect("con1", BlockedClose()))
            await asyncio.wait_for(entered.wait(), 1)
            self.assertTrue(await asyncio.wait_for(manager.send("con1", "still responsive"), 0.05))
            self.assertFalse(await rejection)
        self.assertTrue(await manager.is_current("con1", original))

    async def test_cancelled_handshake_releases_only_its_own_reservation(self):
        entered = asyncio.Event()
        class BlockedAccept(Socket):
            async def accept(self):
                entered.set()
                await asyncio.Event().wait()

        manager = ConnectionManager()
        pending = asyncio.create_task(manager.connect("con1", BlockedAccept()))
        await asyncio.wait_for(entered.wait(), 1)
        pending.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await pending
        self.assertTrue(await manager.connect("con1", Socket()))

    async def test_send_failure_closes_socket_and_leaves_cleanup_to_endpoint(self):
        manager, socket = ConnectionManager(), Socket(fail=True)
        await manager.connect("con1", socket)
        self.assertFalse(await manager.send("con1", "message"))
        self.assertTrue(socket.closed)
        self.assertFalse(await manager.is_current("con1", socket))
        self.assertTrue(await manager.disconnect("con1", socket))
        self.assertFalse(await manager.send("con1", "message"))

    async def test_backpressured_peer_is_not_retried_by_later_broadcasts(self):
        class BlockedSocket(Socket):
            sends = 0
            closes = 0

            async def send_text(self, message):
                self.sends += 1
                await asyncio.Event().wait()

            async def close(self, **kwargs):
                self.closes += 1
                await asyncio.Event().wait()

        manager, blocked, healthy = ConnectionManager(), BlockedSocket(), Socket()
        await manager.connect("cliBlocked", blocked)
        await manager.connect("cliHealthy", healthy)
        with patch("app.managers.connection_manager.SEND_TIMEOUT_SECONDS", 0.01):
            await manager.broadcast_clients("first")
            await manager.broadcast_clients("second")
            self.assertFalse(await manager.send("cliBlocked", "third"))
        self.assertEqual(blocked.sends, 1)
        self.assertEqual(blocked.closes, 1)
        self.assertEqual(healthy.messages, ["first", "second"])
        self.assertTrue(await manager.disconnect("cliBlocked", blocked))


if __name__ == "__main__":
    unittest.main()
