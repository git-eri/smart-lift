import hmac
import os
import re

from fastapi import APIRouter, Response, Header, HTTPException
from fastapi.responses import FileResponse
from packaging import version
from pathlib import Path
from typing import Dict, List, Optional

from app.core.state import lm
from app.core.logging import logger

router = APIRouter(tags=["api"])


# ---------- firmware update ----------

@router.get("/update/{con_id}")
async def update(con_id: str, x_esp8266_version: Optional[str] = Header(default=None),
                 x_controller_token: Optional[str] = Header(default=None)):
    """Serve the latest .bin for a controller if its reported version is older.

    Expects files like:
      app/binaries/<version>.bin           (version discovery)
      app/binaries/<con_id>-<version>.bin  (controller-specific binary to serve)
    """
    if not re.fullmatch(r"con[A-Za-z0-9_-]{1,61}", con_id):
        raise HTTPException(status_code=400, detail="Invalid controller ID")
    token = os.environ.get("SMARTLIFT_CONTROLLER_TOKEN", "")
    if token and not hmac.compare_digest(x_controller_token or "", token):
        raise HTTPException(status_code=403, detail="Controller authentication required")
    bin_dir = Path(os.environ.get("SMARTLIFT_BIN_DIR", "app/binaries"))
    candidates = []
    for binary in bin_dir.glob("*.bin"):
        if binary.is_symlink() or not binary.is_file():
            continue
        specific = binary.stem.startswith(con_id + "-")
        text = binary.stem[len(con_id) + 1:] if specific else binary.stem
        try:
            parsed = version.Version(text)
        except version.InvalidVersion:
            continue  # Other controllers and unrelated files are not versions.
        candidates.append((parsed, specific, binary))
    if not candidates:
        return Response(status_code=304)
    latest, _, candidate = max(candidates, key=lambda item: (item[0], item[1]))
    try:
        current = version.Version(x_esp8266_version) if x_esp8266_version else None
    except version.InvalidVersion as exc:
        raise HTTPException(status_code=400, detail="Invalid firmware version") from exc
    if current is not None and current >= latest:
        return Response(status_code=304)
    logger.info("Serving firmware to %s: %s", con_id, latest)
    return FileResponse(candidate, media_type="application/octet-stream")


# ---------- Read-only REST APIs ----------

@router.get("/lifts/online")
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


@router.get("/lifts/online/controller/{con_id}")
async def get_online_lifts_by_controller(con_id: str):
    """Lifts of a specific controller (or 404 if unknown)."""
    lifts = lm.online_lifts.get(con_id)
    if lifts is None:
        return Response(status_code=404)
    return {"con_id": con_id, "lifts": dict(lifts)}


@router.get("/lifts/online/flat")
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


@router.get("/lifts/active")
async def get_active_lifts() -> List[Dict[str, object]]:
    """Active holds, including their exact controller, owner and direction."""
    return await lm.active_snapshot()


@router.get("/power")
async def get_power_states() -> Dict[str, int]:
    """All known power states by controller (0/1)."""
    return dict(lm.lift_power)


@router.get("/power/{con_id}")
async def get_power_state(con_id: str):
    """Power state of a single controller, or null if unknown."""
    return {"con_id": con_id, "state": lm.lift_power.get(con_id)}


# Keep the original URL after the static /flat route, so "flat" cannot be
# mistaken for a controller ID.
router.add_api_route("/lifts/online/{con_id}", get_online_lifts_by_controller, methods=["GET"], include_in_schema=False)
