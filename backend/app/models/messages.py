from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict


class Case(str, Enum):
    HELLO = "hello"
    STOP = "stop"
    MOVE_LIFT = "move_lift"
    LIFT_MOVED = "lift_moved"
    POWER_STATE = "power_state"
    GET_POWER_STATES = "get_power_states"
    ERROR = "error"
    ONLINE_LIFTS = "online_lifts"
    POWER_STATES = "power_states"
    CLIENT_DISCONNECT = "client_disconnect"


class BaseMsg(BaseModel):
    case: Case


class HelloMsg(BaseMsg):
    case: Literal[Case.HELLO]
    lifts: Optional[list[int]] = None
    power_state: Optional[int] = Field(default=None, ge=0, le=1)


class StopMsg(BaseMsg):
    case: Literal[Case.STOP]


class MoveLiftMsg(BaseMsg):
    case: Literal[Case.MOVE_LIFT]
    client_id: str
    con_id: str
    lift_id: int = Field(ge=0)
    toggle: int = Field(ge=0, le=1)
    direction: Optional[int] = Field(default=None, ge=0, le=2)

    model_config = ConfigDict(extra="allow")


class PowerStateMsg(BaseMsg):
    case: Literal[Case.POWER_STATE]
    state: int = Field(ge=0, le=1)


class GetPowerStatesMsg(BaseMsg):
    case: Literal[Case.GET_POWER_STATES]


class ErrorMsg(BaseMsg):
    case: Literal[Case.ERROR]
    detail: Any


class LiftMovedMsg(BaseMsg):
    case: Literal[Case.LIFT_MOVED]
    con_id: Optional[str] = None
    lift_id: Optional[int] = None

    model_config = ConfigDict(extra="allow")