import json
from pydantic import ValidationError

from app.models.messages import (
    Case,
    BaseMsg,
    HelloMsg,
    StopMsg,
    MoveLiftMsg,
    PowerStateMsg,
    GetPowerStatesMsg,
    ErrorMsg,
    LiftMovedMsg,
)


def parse_msg(raw: str) -> BaseMsg:
    """Parse inbound JSON into a typed model; be liberal for lift_moved."""

    try:
        obj = json.loads(raw)

        if not isinstance(obj, dict) or "case" not in obj:
            raise ValueError("Missing 'case'")

        c = Case(obj["case"])

    except Exception as exc:
        return ErrorMsg(case=Case.ERROR, detail=f"Malformed message: {exc} :: {raw}")

    try:
        if c is Case.HELLO:
            return HelloMsg(**obj)

        if c is Case.STOP:
            return StopMsg(**obj)

        if c is Case.MOVE_LIFT:
            return MoveLiftMsg(**obj)

        if c is Case.POWER_STATE:
            return PowerStateMsg(**obj)

        if c is Case.GET_POWER_STATES:
            return GetPowerStatesMsg(**obj)

        if c is Case.ERROR:
            return ErrorMsg(**obj)

        if c is Case.LIFT_MOVED:
            return LiftMovedMsg(**obj)

    except ValidationError as ve:
        return ErrorMsg(case=Case.ERROR, detail=f"Validation error: {ve.errors()} :: {obj}")

    return ErrorMsg(case=Case.ERROR, detail=f"Unsupported case: {obj}")