"""This module contains the client class."""
import json
from fastapi import WebSocket

from . import logger, online_lifts, cm

async def handler(websocket: WebSocket, client_id: str):
    """Handle Client events"""
    logger.info("Client %s connected", client_id)
    message = {}
    message['case'] = 'online_lifts'
    message['lifts'] = online_lifts
    await cm.send_personal_message(client_id, json.dumps(message))
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

        elif data['case'] == 'move_lift':
            # Lift moved
            await cm.send_personal_message(data['con_id'], json.dumps(data))

        elif data['case'] == 'error':
            # Error
            logger.error("Client %s sent error: %s", client_id, data)

        else:
            logger.error("Client %s sent invalid data: %s", client_id, data)
