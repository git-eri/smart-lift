"""This module contains the client class."""
import json
from fastapi import WebSocket

from . import logger, lm

async def handler(websocket: WebSocket, client_id: str):
    """Handle Client events"""
    logger.info("Client %s connected", client_id)
    await lm.send_online_lifts(client_id)
    while True:
        data = await websocket.receive_text()
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            logger.error("Client %s sent invalid data: %s", client_id, data)
            continue
        logger.debug("Client %s sent: %s", client_id, data)

        if data['case'] == 'hello':
            pass

        elif data['case'] == 'stop':
            # Lift moved
            await lm.e_stop()

        elif data['case'] == 'move_lift':
            # Lift moved
            await lm.send_move_lift(data)

        elif data['case'] == 'error':
            # Error
            logger.error("Client %s sent error: %s", client_id, data)

        else:
            logger.error("Client %s sent invalid data: %s", client_id, data)
