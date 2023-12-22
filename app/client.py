"""This module contains the client class."""
import json
from fastapi import WebSocket

from . import logger, lifts, cm

async def handler(websocket: WebSocket, client_id: str):
    """Handle Client events"""
    logger.info("Client %s connected", client_id)
    message = {}
    message['message'] = 'lift_status'
    message['lifts'] = lifts
    await cm.send_personal_message(client_id, json.dumps(message))
    while True:
        data = await websocket.receive_text()
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            logger.error("Client %s sent invalid data: %s", client_id, data)
            continue
        logger.debug("Client %s sent: %s", client_id, data)
        if data['message'] == 'hello':
            # Client joining
            pass
        elif data['message'] == 'lift':
            # Lift moved
            con_id = data['lift']['con_id']
            lift_id = data['lift']['id']
            action = data['lift']['action']
            on_off = data['lift']['on_off']
            if on_off == 1:
                message = {}
                message['message'] = 'lift'
                message['lift'] = {}
                message['lift']['id'] = lift_id
                message['lift']['action'] = action
                message['lift']['on_off'] = '1'
                await cm.send_personal_message(con_id, json.dumps(message))
                #active_lifts.append(lift_id, client_id)
            elif on_off == 0:
                message = {}
                message['message'] = 'lift'
                message['lift'] = {}
                message['lift']['id'] = lift_id
                message['lift']['action'] = action
                message['lift']['on_off'] = '0'
                await cm.send_personal_message(con_id, json.dumps(message))
            else:
                logger.error("Client %s sent something unhandled: %s", client_id, data)
        elif data['message'] == 'error':
            # Error
            logger.error("Client %s sent error: %s", client_id, data)
        else:
            logger.error("Client %s sent invalid data: %s", client_id, data)
