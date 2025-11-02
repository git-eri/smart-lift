"""Client (frontend app) websocket handler.

Parses incoming messages, requests initial state, and forwards actions to LiftManager.
"""

from fastapi import WebSocket

from . import ErrorMsg, GetPowerStatesMsg, MoveLiftMsg, StopMsg, logger, lm, parse_msg


async def handler(websocket: WebSocket, client_id: str) -> None:
    """Handle 'cli*' connections."""
    logger.info("Client %s connected", client_id)

    # Send initial snapshots (online lifts + power states)
    await lm.send_online_lifts(client_id=client_id)
    await lm.send_power_states(client_id=client_id)

    while True:
        raw = await websocket.receive_text()
        msg = parse_msg(raw)
        logger.debug("Client %s sent: %s", client_id, raw)

        if isinstance(msg, ErrorMsg):
            logger.error("Client %s sent invalid data: %s", client_id, msg.detail)
            continue

        if isinstance(msg, StopMsg):
            await lm.e_stop()

        elif isinstance(msg, MoveLiftMsg):
            # Enforce client_id from connection, not from payload
            msg.client_id = client_id
            await lm.send_move_lift(msg)

        elif isinstance(msg, GetPowerStatesMsg):
            await lm.send_power_states(client_id=client_id)

        else:
            # 'hello' from client is a no-op; keep for protocol symmetry
            pass
