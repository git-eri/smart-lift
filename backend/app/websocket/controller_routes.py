from app.core.state import lm
from app.models.messages import ErrorMsg, HelloMsg, LiftMovedMsg, PowerStateMsg, StopStateMsg
from app.websocket.message_router import MessageRouter

router = MessageRouter()


async def handle_hello(msg, con_id, raw):
    await lm.recv_hello(con_id, msg)


async def handle_power(msg, con_id, raw):
    await lm.update_power_state(con_id, msg.state)


async def handle_lift_moved(msg, con_id, raw):
    await lm.recv_lift_moved(con_id, msg)


async def handle_stop_state(msg, con_id, raw):
    await lm.recv_stop_state(con_id, msg)


async def handle_error(msg, con_id, raw):
    await lm.controller_error(con_id, msg)


router.register(HelloMsg, handle_hello)
router.register(PowerStateMsg, handle_power)
router.register(LiftMovedMsg, handle_lift_moved)
router.register(StopStateMsg, handle_stop_state)
router.register(ErrorMsg, handle_error)
