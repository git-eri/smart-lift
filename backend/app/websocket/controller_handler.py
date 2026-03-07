from fastapi import WebSocket

from app.core.logging import logger
from app.models.messages import ErrorMsg
from app.utils.message_parser import parse_msg
from app.websocket.controller_routes import router


async def handler(websocket: WebSocket, con_id: str) -> None:
    """Handle 'con*' connections."""

    while True:

        raw = await websocket.receive_text()
        msg = parse_msg(raw)

        logger.debug("Controller %s sent: %s", con_id, raw)

        if isinstance(msg, ErrorMsg):
            logger.error("Controller %s sent invalid data: %s", con_id, msg.detail)
            continue

        h = router.get(msg)

        if h:
            await h(msg, con_id, raw)
        else:
            logger.error(
                "Controller %s sent unsupported case: %s",
                con_id,
                msg.case,
            )