"""Serialized lift ownership, expiring holds and an acknowledged STOP latch."""

import asyncio
import json
import os
import secrets
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from app.core.logging import logger
from app.models.messages import ErrorMsg, HelloMsg, LiftMovedMsg, MoveLiftMsg, StopStateMsg

HOLD_TIMEOUT_SECONDS = 0.5
RESET_TIMEOUT_SECONDS = 3.0


@dataclass
class ActiveMovement:
    client_id: str
    con_id: str
    lift_id: int
    direction: int
    command_id: str
    expires_at: float

    def command(self, toggle: int, *, renew: bool = False) -> dict:
        return {
            "case": "move_lift", "lift_id": self.lift_id,
            "direction": self.direction, "toggle": toggle,
            "command_id": self.command_id, "renew": renew,
        }


class LiftManager:
    def __init__(self, connection_manager, *, clock: Callable[[], float] = time.monotonic,
                 lift_info_path: Path | None = None) -> None:
        self.cm = connection_manager
        self.clock = clock
        self.online_lifts: dict[str, dict[int, dict]] = {}
        self.active_lifts: dict[tuple[str, int], ActiveMovement] = {}
        self.lift_power: dict[str, int] = {}
        self.controllers: dict[str, dict] = {}
        self.stopped = True
        self.control_epoch = secrets.token_hex(16)
        self._reset_waiting: dict[str, str] = {}
        self._reset_deadline = 0.0
        self._seen_commands: dict[str, deque] = defaultdict(lambda: deque(maxlen=256))
        self._lock = asyncio.Lock()
        self._config_lock = asyncio.Lock()
        self._lift_info_path = lift_info_path or Path(
            os.environ.get("SMARTLIFT_DATA_DIR", "app/data")
        ) / "lift_info.json"
        self.lift_info = self._load_lift_info()

    def _load_lift_info(self) -> dict:
        try:
            data = json.loads(self._lift_info_path.read_text(encoding="utf8"))
            if not isinstance(data, dict) or any(
                not str(key).isdigit() or not isinstance(value, dict)
                or not isinstance(value.get("name"), str)
                for key, value in data.items()
            ):
                raise ValueError("Expected lift ID -> {name: string}")
            return data
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            logger.error("Failed to read lift names: %s", exc)
            return {}

    @staticmethod
    def _atomic_write_json(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with tmp.open("w", encoding="utf8") as output:
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.flush()
            os.fsync(output.fileno())
        tmp.replace(path)

    async def _error(self, client_id: str, detail: str, command_id: str | None = None):
        payload = {"case": "error", "detail": detail}
        if command_id is not None:
            payload["command_id"] = command_id
        await self.cm.send(client_id, json.dumps(payload))

    def _control_state(self) -> dict:
        return {
            "case": "control_state", "stopped": self.stopped,
            "reset_pending": bool(self._reset_waiting),
            "control_epoch": self.control_epoch,
            "controllers": {peer: dict(state) for peer, state in self.controllers.items()},
        }

    async def _broadcast_control(self):
        await self.cm.broadcast_clients(json.dumps(self._control_state()))

    async def send_control_state(self, client_id: str):
        async with self._lock:
            await self.cm.send(client_id, json.dumps(self._control_state()))

    async def send_online_lifts(self, *, client_id: str = "", broadcast: bool = False):
        async with self._lock:
            payload = json.dumps({"case": "online_lifts", "lifts": self.online_lifts})
        if broadcast:
            await self.cm.broadcast_clients(payload)
        else:
            await self.cm.send(client_id, payload)

    async def send_power_states(self, *, client_id: str = "", broadcast: bool = False):
        async with self._lock:
            payload = json.dumps({"case": "power_states", "states": self.lift_power})
        if broadcast:
            await self.cm.broadcast_clients(payload)
        else:
            await self.cm.send(client_id, payload)

    async def update_power_state(self, con_id: str, state: int):
        async with self._lock:
            if con_id not in self.controllers:
                return
            previous = self.lift_power.get(con_id)
            self.lift_power[con_id] = state
        if previous != state:
            await self.cm.broadcast_clients(json.dumps({
                "case": "power_state", "con_id": con_id, "state": state,
            }))

    async def _publish_stopped(self, movement: ActiveMovement):
        payload = movement.command(0)
        payload.pop("renew")
        payload.update(case="lift_moved", con_id=movement.con_id)
        await self.cm.broadcast_clients(json.dumps(payload))

    async def _end_movement(self, key: tuple[str, int]):
        movement = self.active_lifts.pop(key)
        sent = await self.cm.send(movement.con_id, json.dumps(movement.command(0)))
        if not sent and movement.con_id in self.controllers:
            self.controllers[movement.con_id]["ready"] = False
        await self._publish_stopped(movement)

    async def send_move_lift(self, data: MoveLiftMsg):
        async with self._lock:
            key = (data.con_id, data.lift_id)
            movement = self.active_lifts.get(key)
            matches = movement is not None and (
                movement.client_id == data.client_id
                and movement.command_id == data.command_id
                and movement.direction == data.direction
            )
            # Releases are permitted even with an old epoch, but can never
            # release another operator's or a newer press's movement.
            if data.toggle == 0:
                if matches:
                    await self._end_movement(key)
                return

            now = self.clock()
            if movement is not None and movement.expires_at <= now:
                await self._end_movement(key)
                movement, matches = None, False

            controller = self.controllers.get(data.con_id, {})
            reason = None
            if self.stopped or self._reset_waiting:
                reason = "STOP active; release controls and request reset"
            elif data.control_epoch != self.control_epoch:
                reason = "Control state changed; press the button again"
            elif not controller.get("ready") or controller.get("stopped", True):
                reason = "Controller is not ready"
            elif data.lift_id not in self.online_lifts.get(data.con_id, {}):
                reason = "Lift does not belong to this controller"
            elif data.renew and not matches:
                reason = "Hold expired or was cancelled; press the button again"
            elif not data.renew and movement is not None:
                reason = "Lift is already controlled; release it before changing direction"
            elif not data.renew and data.command_id in self._seen_commands[data.client_id]:
                reason = "Command ID already used; press the button again"

            if reason:
                await self._error(data.client_id, reason, data.command_id)
                return

            if not data.renew:
                movement = ActiveMovement(data.client_id, data.con_id, data.lift_id,
                                          data.direction, data.command_id,
                                          now + HOLD_TIMEOUT_SECONDS)
                self.active_lifts[key] = movement
                self._seen_commands[data.client_id].append(data.command_id)
            else:
                movement.expires_at = now + HOLD_TIMEOUT_SECONDS
            if not await self.cm.send(data.con_id, json.dumps(movement.command(1, renew=data.renew))):
                self.controllers[data.con_id]["ready"] = False
                self.active_lifts.pop(key, None)
                await self._publish_stopped(movement)
                await self._error(data.client_id, "Controller disconnected", data.command_id)
                await self._broadcast_control()

    async def recv_lift_moved(self, con_id: str, msg: LiftMovedMsg):
        async with self._lock:
            key = (con_id, msg.lift_id)
            movement = self.active_lifts.get(key)
            matches = movement is not None and movement.command_id == msg.command_id \
                and movement.direction == msg.direction
            if msg.toggle == 1 and (not matches or self.stopped):
                return
            if msg.toggle == 0 and matches:
                self.active_lifts.pop(key)
            # Socket identity, never a controller-provided con_id, is canonical.
            obj = msg.model_dump(exclude_none=True)
            obj["con_id"] = con_id
            await self.cm.broadcast_clients(json.dumps(obj))

    async def recv_hello(self, con_id: str, data: HelloMsg):
        async with self._lock:
            if con_id in self.controllers:
                raise ValueError("Controller already registered")
            self.online_lifts[con_id] = {
                lift: {"id": lift, "name": self.lift_info.get(str(lift), {}).get("name", f"Lift {lift + 1}")}
                for lift in data.lifts
            }
            self.lift_power[con_id] = data.power_state
            self.controllers[con_id] = {"ready": False, "stopped": data.stop_latched}
            ready = await self.cm.send(con_id, json.dumps({"case": "controller_ready", "protocol_version": 2}))
            self.controllers[con_id]["ready"] = ready
            if data.stop_latched or self.stopped or self._reset_waiting:
                await self._stop_locked()
            await self._broadcast_control()
        await self.send_online_lifts(broadcast=True)
        await self.send_power_states(broadcast=True)

    async def _stop_locked(self):
        self.stopped = True
        self.control_epoch = secrets.token_hex(16)
        self._reset_waiting.clear()
        movements = list(self.active_lifts.values())
        self.active_lifts.clear()
        for controller in self.controllers.values():
            controller["stopped"] = True
        await asyncio.gather(*(self.cm.send(peer, json.dumps({"case": "stop"})) for peer in self.controllers))
        for movement in movements:
            await self._publish_stopped(movement)
        await self.cm.broadcast_clients(json.dumps({"case": "stop"}))
        await self._broadcast_control()

    async def e_stop(self):
        async with self._lock:
            await self._stop_locked()

    async def reset_stop(self, client_id: str):
        async with self._lock:
            if not self.stopped or self._reset_waiting:
                return
            if not self.controllers or not all(state["ready"] for state in self.controllers.values()):
                await self._error(client_id, "All connected controllers must be ready before reset")
                return
            reset_id = secrets.token_hex(16)
            self._reset_waiting = {peer: reset_id for peer in self.controllers}
            self._reset_deadline = self.clock() + RESET_TIMEOUT_SECONDS
            results = await asyncio.gather(*(self.cm.send(peer, json.dumps({
                "case": "reset_stop", "reset_id": reset_id,
            })) for peer in self._reset_waiting))
            if not all(results):
                await self._stop_locked()
                await self._error(client_id, "Reset failed; STOP remains active")
            await self._broadcast_control()

    async def recv_stop_state(self, con_id: str, msg: StopStateMsg):
        async with self._lock:
            if con_id not in self.controllers:
                return
            if self._reset_waiting and self.clock() >= self._reset_deadline:
                await self._stop_locked()
            if msg.stopped:
                if self._reset_waiting or not self.stopped:
                    await self._stop_locked()
                self.controllers[con_id]["stopped"] = True
            elif self._reset_waiting.get(con_id) == msg.reset_id and msg.reset_id is not None:
                self.controllers[con_id]["stopped"] = False
                del self._reset_waiting[con_id]
                if not self._reset_waiting:
                    self.stopped = False
                    self.control_epoch = secrets.token_hex(16)
            elif self.stopped:
                await self.cm.send(con_id, json.dumps({"case": "stop"}))
            await self._broadcast_control()

    async def controller_disconnected(self, con_id: str):
        async with self._lock:
            was_registered = con_id in self.controllers
            self.controllers.pop(con_id, None)
            self.online_lifts.pop(con_id, None)
            self.lift_power.pop(con_id, None)
            # Even an idle session loss invalidates queued starts made before
            # the outage. A new controller session requires a fresh reset epoch.
            if was_registered:
                await self._stop_locked()
            await self._broadcast_control()
        await self.send_online_lifts(broadcast=True)
        await self.send_power_states(broadcast=True)

    async def client_disconnected(self, client_id: str):
        async with self._lock:
            if any(movement.client_id == client_id for movement in self.active_lifts.values()):
                await self._stop_locked()
            self._seen_commands.pop(client_id, None)
        await self.cm.broadcast_clients(json.dumps({"case": "client_disconnect", "client_id": client_id}))

    async def controller_error(self, con_id: str, msg: ErrorMsg):
        logger.warning("Controller %s reported: %s", con_id, msg.detail)
        async with self._lock:
            if msg.command_id:
                for key, movement in list(self.active_lifts.items()):
                    if movement.con_id == con_id and movement.command_id == msg.command_id:
                        await self._end_movement(key)
                        await self._error(movement.client_id, msg.detail, msg.command_id)
            else:
                await self.cm.broadcast_clients(json.dumps({
                    "case": "error", "detail": f"Controller {con_id}: {msg.detail}",
                }))

    async def expire_movements(self):
        async with self._lock:
            now = self.clock()
            if self._reset_waiting and now >= self._reset_deadline:
                logger.warning("Reset acknowledgement timed out; retaining STOP")
                await self._stop_locked()
            for key, movement in list(self.active_lifts.items()):
                if now >= movement.expires_at:
                    await self._end_movement(key)
                    await self._error(movement.client_id, "Hold timed out; press the button again", movement.command_id)

    async def watchdog(self):
        try:
            while True:
                await asyncio.sleep(0.05)
                await self.expire_movements()
        except Exception:
            logger.exception("Movement watchdog failed; latching STOP")
            await self.e_stop()
            raise

    async def active_snapshot(self) -> list[dict]:
        async with self._lock:
            return [asdict(movement) for movement in self.active_lifts.values()]

    async def change_name(self, lift_id: int, new_name: str):
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("Name cannot be blank")
        async with self._config_lock:
            updated = {**self.lift_info, str(lift_id): {"name": new_name}}
            await asyncio.to_thread(self._atomic_write_json, self._lift_info_path, updated)
            async with self._lock:
                self.lift_info = updated
                for lifts in self.online_lifts.values():
                    if lift_id in lifts:
                        lifts[lift_id]["name"] = new_name
        await self.send_online_lifts(broadcast=True)
