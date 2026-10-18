"""Persistent lift-name administration; failed writes never report success."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.state import lm
from app.core.logging import logger
from app.models.messages import LiftId

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------- rename lift ----------

class RenameRequest(BaseModel):
    lift_id: LiftId
    new_name: str = Field(min_length=1, max_length=80)


@router.post("/lift-rename")
async def rename_lift_endpoint(payload: RenameRequest):
    try:
        saved_name = await lm.change_name(payload.lift_id, payload.new_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        logger.error("Lift name could not be persisted: %s", exc)
        raise HTTPException(status_code=503, detail="Lift name could not be saved") from exc
    logger.info("Renamed lift %d to %s", payload.lift_id, saved_name)
    return {
        "status": "ok",
        "lift_id": payload.lift_id,
        "new_name": saved_name,
    }
