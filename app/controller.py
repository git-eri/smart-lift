"""This module contains the controller class."""
import json
from fastapi import WebSocket

from . import logger, lm

async def handler(websocket: WebSocket, con_id: str):
    """Handle Controller events"""
    while True:
        data = await websocket.receive_text()
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            logger.error("Controller %s sent invalid data: %s", con_id, data)
            continue
        logger.debug("Controller %s sent: %s", con_id, data)

        if data['case'] == 'hello':
            # Hello message
            await lm.recv_hello(con_id, data)
            logger.info("Controller %s connected", con_id)

        elif data['case'] == 'lift_moved':
            # Lift moved
            await lm.send_lift_moved(data)

        elif data['case'] == 'stop':
            # Emergency stop
            pass

        elif data['case'] == 'error':
            # Error
            logger.error("Controller %s sent error: %s", con_id, data)

        else:
            logger.error("Controller %s sent invalid data: %s", con_id, data)
