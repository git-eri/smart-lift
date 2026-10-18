"""Require registration once; dispatch only validated controller notifications."""

import asyncio

from fastapi import WebSocket

from app.core.logging import logger
from app.core.state import cm, lm
from app.models.messages import HelloMsg
from app.utils.message_parser import parse_msg
from app.websocket.controller_routes import router


async def handler(websocket: WebSocket, con_id: str) -> None:
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        hello = parse_msg(raw)
        if not isinstance(hello, HelloMsg):
            raise ValueError("Controller must send protocol 2 hello first")
        if not await cm.is_current(con_id, websocket):
            return
        await lm.recv_hello(con_id, hello)
    except (ValueError, TimeoutError) as exc:
        logger.warning("Controller %s handshake rejected: %s", con_id, exc)
        await websocket.close(code=1008, reason="Protocol 2 hello required")
        return
    while True:
        raw = await websocket.receive_text()
        if not await cm.is_current(con_id, websocket):
            return
        try:
            msg = parse_msg(raw)
            action = router.get(msg)
            if action is None:
                raise ValueError("Unsupported controller message")
        except ValueError:
            await websocket.close(code=1008, reason="Invalid controller message")
            return
        await action(msg, con_id)
