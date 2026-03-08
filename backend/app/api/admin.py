from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.state import lm

router = APIRouter(prefix="/admin", tags=["admin"])


class RenameRequest(BaseModel):
    lift_id: int = Field(ge=0)
    new_name: str = Field(min_length=1, max_length=80)


@router.post("/lift-rename")
async def rename_lift_endpoint(payload: RenameRequest):
    await lm.change_name(payload.lift_id, payload.new_name)
    return {
        "status": "ok",
        "lift_id": payload.lift_id,
        "new_name": payload.new_name,
    }