from fastapi import APIRouter, Response, Header
from fastapi.responses import FileResponse
from packaging import version
from pathlib import Path
from typing import Dict, List, Optional

from app.core.state import lm
from app.core.logging import logger

router = APIRouter(tags=["api"])


# ---------- firmware update ----------

@router.get("/update/{con_id}")
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


@router.get("/lifts/online/{con_id}")
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
async def get_active_lifts() -> Dict[str, int]:
    """Map client_id -> lift_id currently controlled."""
    return dict(lm.active_lifts)


@router.get("/power")
async def get_power_states() -> Dict[str, int]:
    """All known power states by controller (0/1)."""
    return dict(lm.lift_power)


@router.get("/power/{con_id}")
async def get_power_state(con_id: str):
    """Power state of a single controller, or null if unknown."""
    return {"con_id": con_id, "state": lm.lift_power.get(con_id)}