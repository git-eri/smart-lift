from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

from app.core.logging import logger
from app.core.state import cm, lm


router = APIRouter()

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):

    from app.websocket import client_handler, controller_handler

    await cm.connect(client_id, websocket)

    try:

        if client_id.startswith("con"):
            await controller_handler.handler(websocket, client_id)

        elif client_id.startswith("cli"):
            await client_handler.handler(websocket, client_id)

        else:
            logger.error("Unknown peer connected: %s", client_id)

            while True:
                data = await websocket.receive_text()
                logger.error("Unknown peer %s sent: %s", client_id, data)

    except WebSocketDisconnect:

        await cm.disconnect(client_id, websocket)

        if client_id.startswith("con"):
            await lm.controller_disconnected(client_id)
            logger.info("Controller %s left", client_id)

        elif client_id.startswith("cli"):

            message = {
                "case": "client_disconnect",
                "client_id": client_id,
            }

            if client_id in lm.active_lifts:
                await lm.e_stop()
                logger.error(
                    "Client %s left while controlling lifts",
                    client_id,
                )

            await cm.broadcast_clients(json.dumps(message))

            logger.info("Client %s left", client_id)