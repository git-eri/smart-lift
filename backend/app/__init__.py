"""Init file for the app module.

Contains:
- LiftManager: runtime state & domain logic
- ConnectionManager: resilient websocket registry
- Shared message models (Pydantic)
- FastAPI app initialization
"""

from __future__ import annotations

import asyncio
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from fastapi import FastAPI, WebSocket
from pydantic import BaseModel, Field, ValidationError
from pydantic import ConfigDict  # pydantic v2

# ---------- Logging ----------
logger = logging.getLogger(__name__)
logger.info("Starting smart-lift server...")

# ---------- Message models (shared for client/controller parsing) ----------

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
    toggle: int = Field(ge=0, le=1)  # 0 -> release, 1 -> acquire
    # IMPORTANT: this was missing and caused direction to be dropped
    direction: Optional[int] = Field(default=None, ge=0, le=2)

    # Allow future extra fields (e.g., speed, accel) and keep them when dumping
    model_config = ConfigDict(extra="allow")


class PowerStateMsg(BaseMsg):
    case: Literal[Case.POWER_STATE]
    state: int = Field(ge=0, le=1)


class GetPowerStatesMsg(BaseMsg):
    case: Literal[Case.GET_POWER_STATES]


class ErrorMsg(BaseMsg):
    case: Literal[Case.ERROR]
    detail: Any


# Liberal model for lift_moved: allow unknown/extra fields and make known ones optional
class LiftMovedMsg(BaseMsg):
    case: Literal[Case.LIFT_MOVED]
    con_id: Optional[str] = None
    lift_id: Optional[int] = None
    model_config = ConfigDict(extra="allow")  # keep all extra top-level fields


# ---------- Connection manager ----------

class ConnectionManager:
    """Tracks active WebSocket connections in a threadsafe (async) way."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._connections: Dict[str, WebSocket] = {}

    async def connect(self, client_id: str, ws: WebSocket) -> None:
        """Accept the socket and ensure at most one connection per id."""
        await ws.accept()
        async with self._lock:
            old = self._connections.pop(client_id, None)
            if old is not None:
                try:
                    await old.close()
                except Exception:
                    pass
            self._connections[client_id] = ws
            logger.debug("Connected %s (total=%d)", client_id, len(self._connections))

    async def disconnect(self, client_id: str, ws: Optional[WebSocket] = None) -> None:
        """Forget the connection. Does not close `ws` (caller does that)."""
        async with self._lock:
            current = self._connections.get(client_id)
            if current is ws or (ws is None and current is not None):
                self._connections.pop(client_id, None)
                logger.debug("Disconnected %s (total=%d)", client_id, len(self._connections))

    async def send(self, client_id: str, message: str) -> None:
        """Send a text message to a specific connection id."""
        async with self._lock:
            ws = self._connections.get(client_id)
        if not ws:
            return
        try:
            await ws.send_text(message)
        except Exception:
            await self.disconnect(client_id)

    async def broadcast(self, message: str) -> None:
        """Send a text message to all active connections."""
        async with self._lock:
            items = list(self._connections.items())
        for cid, ws in items:
            try:
                await ws.send_text(message)
            except Exception:
                await self.disconnect(cid)

    async def broadcast_clients(self, message: str) -> None:
        """Send a text message to all 'cli*' connections."""
        async with self._lock:
            items = [(cid, ws) for cid, ws in self._connections.items() if cid.startswith("cli")]
        for cid, ws in items:
            try:
                await ws.send_text(message)
            except Exception:
                await self.disconnect(cid)


# ---------- Lift manager ----------

class LiftManager:
    """Keeps runtime state and implements domain actions."""

    def __init__(self) -> None:
        # online_lifts maps con_id -> { lift_id -> { "id": int, "name": str } }
        self.online_lifts: Dict[str, Dict[int, Dict[str, Any]]] = {}
        # active_lifts maps client_id -> lift_id
        self.active_lifts: Dict[str, int] = {}
        # lift_power maps con_id -> 0/1
        self.lift_power: Dict[str, int] = {}
        self._lock = asyncio.Lock()

        self._lift_info_path = Path("app/lift_info.json")
        self.lift_info: Dict[str, Dict[str, Any]] = self._load_lift_info()

    # ----- JSON persistence helpers -----

    def _load_lift_info(self) -> Dict[str, Dict[str, Any]]:
        """Load persistent lift metadata from disk; return empty if missing/corrupt."""
        try:
            data = json.loads(self._lift_info_path.read_text(encoding="utf8"))
            if not isinstance(data, dict):
                raise ValueError("lift_info.json is not a dict")
            return data
        except FileNotFoundError:
            logger.warning("lift_info.json not found; using empty map.")
            return {}
        except Exception as exc:
            logger.error("Failed to read lift_info.json: %s; using empty map.", exc)
            return {}

    def _atomic_write_json(self, path: Path, data: Any) -> None:
        """Atomically write JSON (prevents partial files on crash)."""
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf8")
        tmp.replace(path)

    # ----- Outbound messages -----

    async def send_online_lifts(self, *, client_id: str = "", broadcast: bool = False) -> None:
        """Send all currently online lifts to a client, or broadcast to clients."""
        async with self._lock:
            payload = {
                "case": Case.ONLINE_LIFTS,
                "lifts": {
                    con_id: {int(lid): dict(meta) for lid, meta in lifts.items()}
                    for con_id, lifts in self.online_lifts.items()
                },
            }
        message = json.dumps(payload, default=str)
        if broadcast and client_id == "":
            await cm.broadcast_clients(message)
        else:
            await cm.send(client_id, message)

    async def send_power_states(self, *, client_id: str = "", broadcast: bool = False) -> None:
        """Send all known controller power states to clients (not to controllers)."""
        async with self._lock:
            payload = {"case": Case.POWER_STATES, "states": dict(self.lift_power)}
        message = json.dumps(payload)
        if broadcast and client_id == "":
            await cm.broadcast_clients(message)
        else:
            await cm.send(client_id, message)

    # ----- State updates -----

    async def update_power_state(self, con_id: str, state: int) -> None:
        """Update a controller power state and broadcast delta if changed."""
        state = 1 if int(state) == 1 else 0
        async with self._lock:
            prev = self.lift_power.get(con_id)
            self.lift_power[con_id] = state
        if prev != state:
            await cm.broadcast_clients(json.dumps({"case": Case.POWER_STATE, "con_id": con_id, "state": state}))
            logger.info("Power state %s -> %s", con_id, state)

    async def send_move_lift(self, data: MoveLiftMsg) -> None:
        """Forward a move command to the appropriate controller; track active set."""
        async with self._lock:
            if data.toggle == 0:
                self.active_lifts.pop(data.client_id, None)
            else:
                # ensure only one client controls a given lift_id
                for cid, lid in list(self.active_lifts.items()):
                    if lid == data.lift_id and cid != data.client_id:
                        self.active_lifts.pop(cid, None)
                self.active_lifts[data.client_id] = data.lift_id
            logger.debug("Active lifts: %s", self.active_lifts)

        # Forward EXACTLY what we have (including direction and future extras)
        await cm.send(data.con_id, data.model_dump_json())

    # Raw passthrough to keep old clients working for lift_moved
    async def send_lift_moved_raw(self, obj: Dict[str, Any]) -> None:
        """Broadcast a raw lift_moved dict exactly as received (backward compatible)."""
        obj = dict(obj)
        obj["case"] = Case.LIFT_MOVED.value
        await cm.broadcast_clients(json.dumps(obj))

    async def send_lift_moved_model(self, data: LiftMovedMsg) -> None:
        """If you ever emit lift_moved programmatically."""
        await cm.broadcast_clients(data.model_dump_json())

    async def recv_hello(self, con_id: str, data: HelloMsg) -> None:
        """Register a controller's lifts and optionally its power state, then notify clients."""
        async with self._lock:
            self.online_lifts[con_id] = {}
            for lift in data.lifts or []:
                self.online_lifts[con_id][lift] = {"id": lift}
                info_key = str(lift)
                if info_key in self.lift_info and "name" in self.lift_info[info_key]:
                    self.online_lifts[con_id][lift]["name"] = self.lift_info[info_key]["name"]
                else:
                    logger.error("lift %s not found in lift_info.json. Using default name.", lift)
                    self.online_lifts[con_id][lift]["name"] = f"Lift {lift + 1}"

            changed = False
            if data.power_state is not None:
                prev = self.lift_power.get(con_id)
                self.lift_power[con_id] = 1 if int(data.power_state) == 1 else 0
                changed = prev != self.lift_power[con_id]

        if changed:
            await cm.broadcast_clients(json.dumps({"case": Case.POWER_STATE, "con_id": con_id, "state": self.lift_power[con_id]}))

        await self.send_online_lifts(broadcast=True)

    async def e_stop(self) -> None:
        """Emergency stop: broadcast to all connections and clear active set."""
        await cm.broadcast(json.dumps({"case": Case.STOP}))
        logger.info("Emergency stop sent")
        async with self._lock:
            self.active_lifts.clear()

    async def change_name(self, lift_id: int, new_name: str) -> None:
        """Change the persistent and live name of a lift and notify clients."""
        str_id = str(lift_id)
        self.lift_info[str_id] = {"name": new_name}
        try:
            self._atomic_write_json(self._lift_info_path, self.lift_info)
        except Exception as exc:
            logger.error("Failed to persist lift name: %s", exc)

        updated = False
        async with self._lock:
            for _, lifts in self.online_lifts.items():
                if lift_id in lifts:
                    lifts[lift_id]["name"] = new_name
                    updated = True

        if updated:
            logger.info("Lift %s name changed to '%s' (live).", lift_id, new_name)
            await self.send_online_lifts(broadcast=True)
        else:
            logger.warning("Lift %s not found live; name will apply on next reconnect.", lift_id)


# ---------- FastAPI app & singletons ----------

app = FastAPI(root_path="/api")

cm = ConnectionManager()
lm = LiftManager()


# ---------- Utilities ----------

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
            # Liberal parse (keeps extras). We don't *use* the model for broadcasting,
            # but parsing helps to verify 'case' and basic shape during debugging.
            return LiftMovedMsg(**obj)
    except ValidationError as ve:
        return ErrorMsg(case=Case.ERROR, detail=f"Validation error: {ve.errors()} :: {obj}")

    return ErrorMsg(case=Case.ERROR, detail=f"Unsupported case: {obj}")
