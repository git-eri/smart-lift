from app.websocket.client_routes import router
from app.models.messages import ErrorMsg
from app.utils.message_parser import parse_msg
from app.core.logging import logger
from app.core.state import lm


async def handler(websocket, client_id):

    logger.info("Client %s connected", client_id)

    await lm.send_online_lifts(client_id=client_id)
    await lm.send_power_states(client_id=client_id)

    while True:

        raw = await websocket.receive_text()
        msg = parse_msg(raw)

        logger.debug("Client %s sent: %s", client_id, raw)

        if isinstance(msg, ErrorMsg):
            logger.error("Client %s sent invalid data: %s", client_id, msg.detail)
            continue

        h = router.get(msg)

        if h:
            await h(msg, client_id)
