"""A cancelled endpoint must not release an ID ahead of domain teardown."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.managers.connection_manager import ConnectionManager
from app.websocket import router as sessions


def socket():
    return SimpleNamespace(accept=AsyncMock(), close=AsyncMock())


class SessionCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_endpoint_keeps_identity_reserved_until_domain_cleanup(self):
        manager = ConnectionManager()
        old_socket, new_socket = socket(), socket()
        entered, released = asyncio.Event(), asyncio.Event()

        async def clear_domain(peer):
            entered.set()
            await released.wait()

        domain = SimpleNamespace(controller_disconnected=AsyncMock(side_effect=clear_domain))
        await manager.connect("con1", old_socket)
        with patch.object(sessions, "cm", manager), patch.object(sessions, "lm", domain):
            endpoint = asyncio.create_task(sessions._finish_session("con1", old_socket))
            await asyncio.wait_for(entered.wait(), 1)
            endpoint.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await endpoint
            self.assertFalse(await manager.is_current("con1", old_socket))
            self.assertFalse(await manager.begin_disconnect("con1", old_socket))
            self.assertFalse(await manager.connect("con1", new_socket))
            released.set()
            await asyncio.wait_for(asyncio.gather(*tuple(sessions._cleanup_tasks)), 1)
        domain.controller_disconnected.assert_awaited_once_with("con1")
        self.assertTrue(await manager.connect("con1", new_socket))

    async def test_failed_domain_cleanup_still_releases_reservation(self):
        manager, old_socket = ConnectionManager(), socket()
        await manager.connect("cli1", old_socket)
        domain = SimpleNamespace(client_disconnected=AsyncMock(side_effect=RuntimeError("cleanup failed")))
        with patch.object(sessions, "cm", manager), patch.object(sessions, "lm", domain):
            with self.assertLogs("smartlift", level="ERROR"), self.assertRaises(RuntimeError):
                await sessions._finish_session("cli1", old_socket)
        self.assertTrue(await manager.connect("cli1", socket()))
