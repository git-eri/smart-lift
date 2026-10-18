"""The version 2 wire protocol. Actuator inputs never use implicit coercion."""

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

from app.core.protocol import CONTROLLER_ID_PATTERN, IDENTIFIER_PATTERN, MAX_LIFT_ID, PROTOCOL_VERSION

Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=IDENTIFIER_PATTERN)]
LiftId = Annotated[StrictInt, Field(ge=0, le=MAX_LIFT_ID)]
Direction = Annotated[StrictInt, Field(ge=0, le=2)]
Toggle = Annotated[StrictInt, Field(ge=0, le=1)]


class Case(str, Enum):
    HELLO = "hello"
    STOP = "stop"
    RESET_STOP = "reset_stop"
    STOP_STATE = "stop_state"
    MOVE_LIFT = "move_lift"
    LIFT_MOVED = "lift_moved"
    POWER_STATE = "power_state"
    GET_POWER_STATES = "get_power_states"
    ERROR = "error"
    ONLINE_LIFTS = "online_lifts"
    POWER_STATES = "power_states"
    CLIENT_DISCONNECT = "client_disconnect"


class BaseMsg(BaseModel):
    model_config = ConfigDict(extra="forbid")
    case: Case


class HelloMsg(BaseMsg):
    """Register a compatible controller before any actuator command is allowed."""

    case: Literal[Case.HELLO]
    protocol_version: Annotated[StrictInt, Field(ge=PROTOCOL_VERSION, le=PROTOCOL_VERSION)]
    lifts: Annotated[list[LiftId], Field(min_length=1, max_length=64)]
    stop_latched: StrictBool
    power_state: Toggle
    version: str = Field(default="", max_length=32)
    ip: str = Field(default="", max_length=64)
    rssi: StrictInt = 0

    @model_validator(mode="after")
    def unique_lifts(self):
        if len(set(self.lifts)) != len(self.lifts):
            raise ValueError("Duplicate lift IDs")
        return self


class StopMsg(BaseMsg):
    case: Literal[Case.STOP]
    client_id: Identifier | None = None


class ResetStopMsg(BaseMsg):
    case: Literal[Case.RESET_STOP]
    client_id: Identifier | None = None


class StopStateMsg(BaseMsg):
    case: Literal[Case.STOP_STATE]
    stopped: StrictBool
    reset_id: Identifier | None = None


class MoveLiftMsg(BaseMsg):
    """One press identity: renewals cannot create or take over a movement."""

    case: Literal[Case.MOVE_LIFT]
    client_id: Identifier = "unassigned"
    con_id: Annotated[str, Field(min_length=4, max_length=64, pattern=CONTROLLER_ID_PATTERN)]
    lift_id: LiftId
    direction: Direction
    toggle: Toggle
    command_id: Identifier
    control_epoch: Identifier
    renew: StrictBool = False


class PowerStateMsg(BaseMsg):
    case: Literal[Case.POWER_STATE]
    state: Toggle


class GetPowerStatesMsg(BaseMsg):
    case: Literal[Case.GET_POWER_STATES]
    client_id: Identifier | None = None


class ErrorMsg(BaseMsg):
    case: Literal[Case.ERROR]
    detail: str = Field(min_length=1, max_length=512)
    command_id: Identifier | None = None


class LiftMovedMsg(BaseMsg):
    case: Literal[Case.LIFT_MOVED]
    con_id: Identifier | None = None
    lift_id: LiftId
    direction: Direction
    toggle: Toggle
    command_id: Identifier
