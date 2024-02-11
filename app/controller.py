"""This module contains the controller class."""
import json
from fastapi import WebSocket

from . import logger, online_lifts, cm, get_lift_info

async def handler(websocket: WebSocket, con_id: str):
    """Handle Controller events"""
    while True:
        data = await websocket.receive_text()
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            logger.error("Controller %s sent invalid data: %s", con_id, data)
            continue
        # logger.debug("Controller %s sent: %s", con_id, data)

        if data['case'] == 'hello':
            # Hello message
            online_lifts[con_id] = {}
            lift_info = get_lift_info()
            for lift in data['lifts']:
                online_lifts[con_id][lift] = {}
                online_lifts[con_id][lift]['id'] = lift
                if lift in lift_info:
                    online_lifts[con_id][lift]['name'] = lift_info[lift]['name']
                else:
                    logger.error("Lift %s not found in lift_info.json. Using default name.", lift)
                    online_lifts[con_id][lift]['name'] = f"Lift {int(lift) + 1}"
                logger.debug("Controller %s added lift %s", con_id, lift)

            message = {}
            message['case'] = 'online_lifts'
            message['lifts'] = online_lifts
            await cm.broadcast_clients(json.dumps(message))
            logger.info("Controller %s connected", con_id)

        elif data['case'] == 'lift_moved':
            # Lift moved
            await cm.broadcast_clients(json.dumps(data))

        elif data['case'] == 'stop':
            # Emergency stop
            pass

        elif data['case'] == 'error':
            # Error
            logger.error("Controller %s sent error: %s", con_id, data)

        else:
            logger.error("Controller %s sent invalid data: %s", con_id, data)
