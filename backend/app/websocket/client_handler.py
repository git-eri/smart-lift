from app.core.logging import logger
from app.core.state import cm, lm
from app.utils.message_parser import parse_msg
from app.websocket.client_routes import router


async def handler(websocket, client_id):
    await lm.send_online_lifts(client_id=client_id)
    await lm.send_power_states(client_id=client_id)
    await lm.send_control_state(client_id)
    while True:
        raw = await websocket.receive_text()
        if not await cm.is_current(client_id, websocket):
            return
        try:
            msg = parse_msg(raw)
        except ValueError as exc:
            await lm._error(client_id, str(exc))
            continue
        action = router.get(msg)
        if action is None:
            await lm._error(client_id, "Message is not permitted for an operator")
            continue
        logger.debug("Operator %s: %s", client_id, msg.case)
        await action(msg, client_id)
