import json

from app.websocket.message_router import MessageRouter
from app.models.messages import (
    HelloMsg,
    PowerStateMsg,
    LiftMovedMsg,
    StopMsg,
    Case,
)
from app.core.state import lm

router = MessageRouter()


async def handle_hello(msg, con_id, raw):
    await lm.recv_hello(con_id, msg)


async def handle_power(msg, con_id, raw):
    await lm.update_power_state(con_id, int(msg.state))


async def handle_lift_moved(msg, con_id, raw):
    try:
        obj = json.loads(raw)
    except Exception:
        obj = {"case": Case.LIFT_MOVED.value, "con_id": con_id}

    await lm.send_lift_moved_raw(obj)


async def handle_stop(msg, con_id, raw):
    pass


router.register(HelloMsg, handle_hello)
router.register(PowerStateMsg, handle_power)
router.register(LiftMovedMsg, handle_lift_moved)
router.register(StopMsg, handle_stop)