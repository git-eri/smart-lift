"""Main application entrypoints (websocket + REST API)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import Header, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from packaging import version
from pydantic import BaseModel, Field
from prometheus_fastapi_instrumentator import Instrumentator

from . import app, cm, lm, logger

# Expose default Prometheus metrics under /metrics (namespace included)
Instrumentator().instrument(app, metric_namespace="smartlift").expose(app)


# ---------- WebSocket endpoint ----------

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str) -> None:
    """Multiplex clients ('cli*') and controllers ('con*') on one endpoint."""
    from . import client, controller  # local import to avoid circulars during app import

    await cm.connect(client_id, websocket)
    try:
        if client_id.startswith("con"):
            await controller.handler(websocket, client_id)

        elif client_id.startswith("cli"):
            await client.handler(websocket, client_id)

        else:
            # Unknown actor: keep socket open but log; optionally close
            logger.error("Unknown peer connected: %s", client_id)
            while True:
                data = await websocket.receive_text()
                logger.error("Unknown peer %s sent: %s", client_id, data)

    except WebSocketDisconnect:
        await cm.disconnect(client_id, websocket)
        if client_id.startswith("con"):
            # Remove lifts and power state are handled in cm.disconnect via lm access;
            # ensure clients see the latest roster.
            await lm.send_online_lifts(broadcast=True)
            logger.info("Controller %s left", client_id)

        elif client_id.startswith("cli"):
            message = {"case": "client_disconnect", "client_id": client_id}
            # If the client was controlling a lift, enforce stop and inform others.
            if client_id in lm.active_lifts:
                await lm.e_stop()
                logger.error("Client %s left while controlling lifts", client_id)
            await cm.broadcast_clients(json.dumps(message))
            logger.info("Client %s left", client_id)


# ---------- Firmware update endpoint ----------

@app.get("/update/{con_id}")
async def update(con_id: str, x_esp8266_version: Optional[str] = Header(default=None)):
    """Serve the latest .bin for a controller if its reported version is older.

    Expects files like:
      app/binaries/<version>.bin           (version discovery)
      app/binaries/<con_id>-<version>.bin  (controller-specific binary to serve)
    """
    bin_dir = Path("app/binaries")
    versions = [p.stem for p in bin_dir.glob("*.bin")]
    if not versions:
        return {"error": "No binaries found on server"}

    # Pick the highest semantic version (by packaging.version)
    latest = max(versions, key=version.parse)

    if x_esp8266_version is None or version.parse(x_esp8266_version) < version.parse(latest):
        candidate = bin_dir / f"{con_id}-{latest}.bin"
        if not candidate.exists():
            # Fallback: try generic image "<latest>.bin"
            generic = bin_dir / f"{latest}.bin"
            if generic.exists():
                logger.info("Serving GENERIC firmware to %s: %s", con_id, latest)
                return FileResponse(generic)
            return {"error": f"Binary not found for controller {con_id} and version {latest}"}

        logger.info("Serving firmware to %s: %s", con_id, latest)
        return FileResponse(candidate)

    # Not modified
    return Response(status_code=304)


# ---------- Admin: rename lift ----------

class RenameRequest(BaseModel):
    lift_id: int = Field(ge=0)
    new_name: str = Field(min_length=1, max_length=80)


@app.post("/admin/lift-rename")
async def rename_lift_endpoint(payload: RenameRequest):
    """Change the display name of a lift (persist + live update)."""
    await lm.change_name(payload.lift_id, payload.new_name)
    return {"status": "ok", "lift_id": payload.lift_id, "new_name": payload.new_name}


# ---------- Read-only REST APIs ----------

@app.get("/lifts/online")
async def get_online_lifts() -> Dict[str, Dict[int, Dict[str, object]]]:
    """Full map of online lifts per controller.

    Returns:
    {
      "con1": { 0: {"id":0,"name":"Lift 1"}, 1: {"id":1,"name":"Lift 2"} },
      "con2": { ... }
    }
    """
    # Return shallow copies to avoid leaking internal references
    return {con_id: dict(lifts) for con_id, lifts in lm.online_lifts.items()}


@app.get("/lifts/online/{con_id}")
async def get_online_lifts_by_controller(con_id: str):
    """Lifts of a specific controller (or 404 if unknown)."""
    lifts = lm.online_lifts.get(con_id)
    if lifts is None:
        return Response(status_code=404)
    return {"con_id": con_id, "lifts": dict(lifts)}


@app.get("/lifts/online/flat")
async def get_online_lifts_flat() -> List[Dict[str, object]]:
    """Flattened list for easy frontend consumption."""
    result: List[Dict[str, object]] = []
    for con_id, lifts in lm.online_lifts.items():
        for lift_id, meta in lifts.items():
            result.append(
                {
                    "con_id": con_id,
                    "lift_id": int(lift_id),
                    "name": meta.get("name", f"Lift {int(lift_id) + 1}"),
                }
            )
    return result


@app.get("/lifts/active")
async def get_active_lifts() -> Dict[str, int]:
    """Map client_id -> lift_id currently controlled."""
    return dict(lm.active_lifts)


@app.get("/power")
async def get_power_states() -> Dict[str, int]:
    """All known power states by controller (0/1)."""
    return dict(lm.lift_power)


@app.get("/power/{con_id}")
async def get_power_state(con_id: str):
    """Power state of a single controller, or null if unknown."""
    return {"con_id": con_id, "state": lm.lift_power.get(con_id)}
