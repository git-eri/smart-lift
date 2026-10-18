"""Operator actions; the connection identity always overrides claimed ownership."""

from app.websocket.message_router import MessageRouter
from app.models.messages import (
    StopMsg,
    MoveLiftMsg,
    GetPowerStatesMsg,
    ResetStopMsg,
)
from app.core.state import lm

router = MessageRouter()


async def handle_stop(msg: StopMsg, client_id: str) -> None:
    await lm.e_stop()


async def handle_move_lift(msg: MoveLiftMsg, client_id: str) -> None:
    # Never allow an operator to release or renew another socket's hold by
    # supplying that socket's client_id in otherwise valid JSON.
    msg.client_id = client_id
    await lm.send_move_lift(msg)


async def handle_get_power(msg: GetPowerStatesMsg, client_id: str) -> None:
    await lm.send_power_states(client_id=client_id)


async def handle_reset(msg: ResetStopMsg, client_id: str) -> None:
    await lm.reset_stop(client_id)


router.register(StopMsg, handle_stop)
router.register(MoveLiftMsg, handle_move_lift)
router.register(GetPowerStatesMsg, handle_get_power)
router.register(ResetStopMsg, handle_reset)
