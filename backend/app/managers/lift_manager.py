import os
import asyncio
import json
from pathlib import Path
from typing import Any, Dict

from app.core.logging import logger
from app.models.messages import Case, MoveLiftMsg, HelloMsg


class LiftManager:
    """Keeps runtime state and implements domain actions."""

    def __init__(self, connection_manager) -> None:
        self.cm = connection_manager
        self.online_lifts: Dict[str, Dict[int, Dict[str, Any]]] = {}
        self.active_lifts: Dict[str, int] = {}
        self.lift_power: Dict[str, int] = {}

        self._lock = asyncio.Lock()

        self._lift_info_path = Path("app/lift_info.json")
        self.lift_info: Dict[str, Dict[str, Any]] = self._load_lift_info()

    def _load_lift_info(self) -> Dict[str, Dict[str, Any]]:
        try:
            data = json.loads(self._lift_info_path.read_text(encoding="utf8"))
            if not isinstance(data, dict):
                raise ValueError("lift_info.json is not a dict")
            return data

        except FileNotFoundError:
            logger.warning("lift_info.json not found; using empty map.")
            return {}

        except Exception as exc:
            logger.error("Failed to read lift_info.json: %s", exc)
            return {}

    def _atomic_write_json(self, path: Path, data: Any) -> None:
        tmp = path.parent / (path.name + ".tmp")

        with open(tmp, "w", encoding="utf8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            f.flush()
            os.fsync(f.fileno())

        tmp.replace(path)

    async def send_online_lifts(self, *, client_id: str = "", broadcast: bool = False) -> None:
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
            await self.cm.broadcast_clients(message)
        else:
            await self.cm.send(client_id, message)

    async def send_power_states(self, *, client_id: str = "", broadcast: bool = False) -> None:
        async with self._lock:
            payload = {"case": Case.POWER_STATES, "states": dict(self.lift_power)}

        message = json.dumps(payload)

        if broadcast and client_id == "":
            await self.cm.broadcast_clients(message)
        else:
            await self.cm.send(client_id, message)

    async def update_power_state(self, con_id: str, state: int) -> None:
        state = 1 if int(state) == 1 else 0

        async with self._lock:
            prev = self.lift_power.get(con_id)
            self.lift_power[con_id] = state

        if prev != state:
            await self.cm.broadcast_clients(
                json.dumps(
                    {
                        "case": Case.POWER_STATE,
                        "con_id": con_id,
                        "state": state,
                    }
                )
            )

            logger.info("Power state %s -> %s", con_id, state)

    async def send_move_lift(self, data: MoveLiftMsg) -> None:
        async with self._lock:

            if data.toggle == 0:
                self.active_lifts.pop(data.client_id, None)

            else:
                for cid, lid in list(self.active_lifts.items()):
                    if lid == data.lift_id and cid != data.client_id:
                        self.active_lifts.pop(cid, None)

                self.active_lifts[data.client_id] = data.lift_id

        await self.cm.send(data.con_id, data.model_dump_json())

    async def send_lift_moved_raw(self, obj: Dict[str, Any]) -> None:
        obj = dict(obj)
        obj["case"] = Case.LIFT_MOVED.value

        await self.cm.broadcast_clients(json.dumps(obj))

    async def recv_hello(self, con_id: str, data: HelloMsg) -> None:

        changed = False

        async with self._lock:

            self.online_lifts[con_id] = {}

            for lift in data.lifts or []:

                self.online_lifts[con_id][lift] = {"id": lift}

                info_key = str(lift)

                if info_key in self.lift_info and "name" in self.lift_info[info_key]:
                    self.online_lifts[con_id][lift]["name"] = self.lift_info[info_key]["name"]
                else:
                    self.online_lifts[con_id][lift]["name"] = f"Lift {lift + 1}"

            # ---- take power state from controller ----
            if data.power_state is not None:
                prev = self.lift_power.get(con_id)
                self.lift_power[con_id] = 1 if int(data.power_state) == 1 else 0
                changed = prev != self.lift_power[con_id]

        # ---- Broadcast if changed ----
        if changed:
            await self.cm.broadcast_clients(
                json.dumps(
                    {
                        "case": Case.POWER_STATE,
                        "con_id": con_id,
                        "state": self.lift_power[con_id],
                    }
                )
            )

        await self.send_online_lifts(broadcast=True)

    async def controller_disconnected(self, con_id: str) -> None:
        """Remove controller state when it disconnects."""

        async with self._lock:
            removed_lifts = self.online_lifts.pop(con_id, None)
            self.lift_power.pop(con_id, None)

        if removed_lifts:
            logger.info(
                "Controller %s removed (%d lifts)",
                con_id,
                len(removed_lifts),
            )

        await self.send_online_lifts(broadcast=True)
        await self.send_power_states(broadcast=True)

    async def e_stop(self) -> None:
        await self.cm.broadcast(json.dumps({"case": Case.STOP}))

        async with self._lock:
            self.active_lifts.clear()
    
    async def change_name(self, lift_id: int, new_name: str) -> None:
        """Change the persistent and live name of a lift and notify clients."""

        str_id = str(lift_id)

        # update persistent storage
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
            logger.info("Lift %s name changed to '%s'", lift_id, new_name)
            await self.send_online_lifts(broadcast=True)
        else:
            logger.warning("Lift %s not currently online", lift_id)