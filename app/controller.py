"""This module contains the controller class."""
import json
from fastapi import WebSocket

from . import logger, lifts, cm, get_lift_info

async def handler(websocket: WebSocket, client_id: str):
    """Handle Controller events"""
    while True:
        data = await websocket.receive_text()
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            logger.error("Controller %s sent invalid data: %s", client_id, data)
            continue
        # logger.debug("Controller %s sent: %s", client_id, data)

        if data['message'] == 'hello':
            # Hello message
            lifts[client_id] = {}
            lift_info = get_lift_info()
            for lift in data['lifts']:
                lifts[client_id][lift] = {}
                lifts[client_id][lift]['id'] = lift

                if lift in lift_info:
                    lifts[client_id][lift]['name'] = lift_info[lift]['name']
                else:
                    logger.error("Lift %s not found in lift_info.json. Using default name.", lift)
                    lifts[client_id][lift]['name'] = f"Lift {int(lift) + 1}"
                logger.debug("Controller %s added lift %s", client_id, lift)

            message = {}
            message['message'] = 'lift_status'
            message['lifts'] = lifts
            await cm.broadcast_clients(json.dumps(message))
            logger.info("Controller %s connected", client_id)

        elif data['message'] == 'moved_lift':
            logger.debug(data)
            # Lift moved
            if data['lift']['status'] == 0:
                await cm.broadcast_clients(json.dumps(data))
            else:
                await cm.broadcast(
                    f"error;Controller {client_id} sent invalid data: {data}"
                )

        elif data['message'] == 'stop':
            # Emergency stop
            pass

        elif data['message'] == 'error':
            # Error
            logger.error("Controller %s sent error: %s", client_id, data)

        else:
            logger.error("Controller %s sent invalid data: %s", client_id, data)
