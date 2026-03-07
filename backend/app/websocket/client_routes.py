from app.websocket.message_router import MessageRouter
from app.models.messages import (
    StopMsg,
    MoveLiftMsg,
    GetPowerStatesMsg,
)
from app.core.state import lm

router = MessageRouter()


async def handle_stop(msg, client_id):
    await lm.e_stop()


async def handle_move_lift(msg, client_id):
    msg.client_id = client_id
    await lm.send_move_lift(msg)


async def handle_get_power(msg, client_id):
    await lm.send_power_states(client_id=client_id)


router.register(StopMsg, handle_stop)
router.register(MoveLiftMsg, handle_move_lift)
router.register(GetPowerStatesMsg, handle_get_power)