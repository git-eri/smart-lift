"""Validate peer admission and keep socket teardown coupled to domain cleanup."""

import asyncio
import os
import re
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import logger
from app.core.protocol import PEER_ID_PATTERN
from app.core.security import controller_token_valid
from app.core.state import cm, lm

router = APIRouter()
PEER_ID = re.compile(PEER_ID_PATTERN)
_cleanup_tasks: set[asyncio.Task] = set()


async def _cleanup_peer(client_id: str, websocket: WebSocket) -> None:
    """Keep the ID reserved until no old movement/controller state can survive."""
    if not await cm.begin_disconnect(client_id, websocket):
        return
    try:
        if client_id.startswith("con"):
            await lm.controller_disconnected(client_id)
        else:
            await lm.client_disconnected(client_id)
    finally:
        await cm.disconnect(client_id, websocket)


def _cleanup_finished(task: asyncio.Task) -> None:
    _cleanup_tasks.discard(task)
    if not task.cancelled() and task.exception() is not None:
        error = task.exception()
        logger.error("WebSocket session cleanup failed", exc_info=(type(error), error, error.__traceback__))


async def _finish_session(client_id: str, websocket: WebSocket) -> None:
    """Retain a strong reference if caller cancellation outlives the endpoint."""
    cleanup = asyncio.create_task(_cleanup_peer(client_id, websocket))
    _cleanup_tasks.add(cleanup)
    cleanup.add_done_callback(_cleanup_finished)
    await asyncio.shield(cleanup)


def origin_allowed(websocket: WebSocket, *, controller: bool = False) -> bool:
    """Browser control must come from this host or an explicit allowlist."""
    origin = websocket.headers.get("origin")
    if origin is None:
        return True  # ESPs and non-browser integration clients have no Origin.
    if controller and origin == "file://":
        # Some arduinoWebSockets releases supply this synthetic Origin by default.
        # Browser peers keep the normal same-host policy; controller token
        # authentication is still checked separately below.
        return True
    allowed = {entry.strip() for entry in os.environ.get("SMARTLIFT_ALLOWED_ORIGINS", "").split(",") if entry.strip()}
    if origin in allowed:
        return True
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and parsed.netloc.lower() == websocket.headers.get("host", "").lower()


@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    from app.websocket import client_handler, controller_handler

    if not PEER_ID.fullmatch(client_id):
        logger.warning("WebSocket rejected: invalid peer ID")
        await websocket.close(code=1008)
        return
    if not origin_allowed(websocket, controller=client_id.startswith("con")):
        logger.warning("WebSocket %s rejected: Origin is not permitted", client_id)
        await websocket.close(code=1008)
        return
    if client_id.startswith("con") and not controller_token_valid(websocket.headers.get("x-controller-token")):
        logger.warning("WebSocket %s rejected: controller token missing or invalid", client_id)
        await websocket.close(code=1008)
        return
    if not await cm.connect(client_id, websocket):
        return
    try:
        if client_id.startswith("con"):
            await controller_handler.handler(websocket, client_id)
        else:
            await client_handler.handler(websocket, client_id)
    except WebSocketDisconnect:
        pass
    except (RuntimeError, KeyError, ValueError):
        logger.warning("Invalid or closed WebSocket session %s", client_id)
    except Exception:
        logger.exception("WebSocket session failed for %s", client_id)
    finally:
        # Shield the complete teardown, not just registry removal. Cancellation
        # must not free an ID while its previous domain state still exists.
        await _finish_session(client_id, websocket)
