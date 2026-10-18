"""Notifications accepted after a controller's one-time hello handshake."""

from app.core.state import lm
from app.models.messages import ErrorMsg, LiftMovedMsg, PowerStateMsg, StopStateMsg
from app.websocket.message_router import MessageRouter

router = MessageRouter()


async def handle_power(msg: PowerStateMsg, con_id: str) -> None:
    await lm.update_power_state(con_id, msg.state)


async def handle_lift_moved(msg: LiftMovedMsg, con_id: str) -> None:
    await lm.recv_lift_moved(con_id, msg)


async def handle_stop_state(msg: StopStateMsg, con_id: str) -> None:
    await lm.recv_stop_state(con_id, msg)


async def handle_error(msg: ErrorMsg, con_id: str) -> None:
    await lm.controller_error(con_id, msg)


router.register(PowerStateMsg, handle_power)
router.register(LiftMovedMsg, handle_lift_moved)
router.register(StopStateMsg, handle_stop_state)
router.register(ErrorMsg, handle_error)
