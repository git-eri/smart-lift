"""Controller (hardware) websocket handler.

Accepts updates from controllers (con*), maintains lift discovery,
forwards movement status, and power state changes.
"""

import json
from fastapi import WebSocket

from . import HelloMsg, LiftMovedMsg, PowerStateMsg, StopMsg, ErrorMsg, Case, logger, lm, parse_msg


async def handler(websocket: WebSocket, con_id: str) -> None:
    """Handle 'con*' connections."""
    while True:
        raw = await websocket.receive_text()
        msg = parse_msg(raw)
        logger.debug("Controller %s sent: %s", con_id, raw)

        if isinstance(msg, ErrorMsg):
            logger.error("Controller %s sent invalid data: %s", con_id, msg.detail)
            continue

        if isinstance(msg, HelloMsg):
            await lm.recv_hello(con_id, msg)
            logger.info("Controller %s connected", con_id)

        elif isinstance(msg, PowerStateMsg):
            await lm.update_power_state(con_id, int(msg.state))

        elif isinstance(msg, LiftMovedMsg):
            # Broadcast the raw payload exactly as sent by the controller.
            try:
                obj = json.loads(raw)
            except Exception:
                obj = {"case": Case.LIFT_MOVED.value, "con_id": con_id}
            await lm.send_lift_moved_raw(obj)

        elif isinstance(msg, StopMsg):
            pass

        else:
            logger.error("Controller %s sent unsupported case: %s", con_id, msg.case)
