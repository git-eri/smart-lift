"""Validate untrusted JSON before role-specific WebSocket dispatch."""

import json

from app.core.protocol import MAX_MESSAGE_BYTES
from app.models.messages import (
    BaseMsg, Case, ErrorMsg, GetPowerStatesMsg, HelloMsg, LiftMovedMsg,
    MoveLiftMsg, PowerStateMsg, ResetStopMsg, StopMsg, StopStateMsg,
)

MESSAGE_TYPES = {
    Case.HELLO: HelloMsg,
    Case.STOP: StopMsg,
    Case.RESET_STOP: ResetStopMsg,
    Case.STOP_STATE: StopStateMsg,
    Case.MOVE_LIFT: MoveLiftMsg,
    Case.LIFT_MOVED: LiftMovedMsg,
    Case.POWER_STATE: PowerStateMsg,
    Case.GET_POWER_STATES: GetPowerStatesMsg,
    Case.ERROR: ErrorMsg,
}


def parse_msg(raw: str) -> BaseMsg:
    """Reject malformed inputs without echoing arbitrary payloads into logs."""
    if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValueError("Message exceeds 4096 bytes")
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("Expected a JSON object")
        model = MESSAGE_TYPES[Case(obj.get("case"))]
        return model.model_validate(obj)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Invalid message or unsupported protocol fields") from exc
