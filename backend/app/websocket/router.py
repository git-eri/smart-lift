import hmac
import os
import re
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import logger
from app.core.state import cm, lm

router = APIRouter()
PEER_ID = re.compile(r"^(?:con|cli)[A-Za-z0-9_-]{1,61}$")


def origin_allowed(websocket: WebSocket, *, controller: bool = False) -> bool:
    """Browser control must come from this host or an explicit allowlist."""
    origin = websocket.headers.get("origin")
    if origin is None:
        return True  # ESPs and non-browser integration clients have no Origin.
    if controller and origin == "file://":
        # arduinoWebSockets <=2.6.1 supplies this synthetic Origin by default.
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
    token = os.environ.get("SMARTLIFT_CONTROLLER_TOKEN", "")
    if client_id.startswith("con") and token and not hmac.compare_digest(
        websocket.headers.get("x-controller-token", ""), token
    ):
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
        # Cleanup runs for protocol failures and unexpected errors too. A
        # rejected duplicate connection never reaches this block.
        if await cm.disconnect(client_id, websocket):
            if client_id.startswith("con"):
                await lm.controller_disconnected(client_id)
            else:
                await lm.client_disconnected(client_id)
