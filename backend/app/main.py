"""Application lifecycle: one watchdog and one connection registry per worker."""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import api, admin
from app.websocket.router import router as ws_router
from app.core.state import cm, lm
from app.core.protocol import PROTOCOL_VERSION

@asynccontextmanager
async def lifespan(app):
    """Start lease expiry before serving traffic, then stop outputs on shutdown."""
    watchdog = asyncio.create_task(lm.watchdog(), name="movement-watchdog")
    app.state.movement_watchdog = watchdog
    try:
        yield
    finally:
        await lm.e_stop()
        await cm.close_all()
        watchdog.cancel()
        with suppress(asyncio.CancelledError):
            await watchdog


app = FastAPI(root_path="/api", lifespan=lifespan)

Instrumentator().instrument(app, metric_namespace="smartlift").expose(app)

app.include_router(ws_router)
app.include_router(api.router)
app.include_router(admin.router)


@app.get("/health", include_in_schema=False)
async def health():
    watchdog = getattr(app.state, "movement_watchdog", None)
    if watchdog is None or watchdog.done() or lm.watchdog_failed:
        raise HTTPException(status_code=503, detail="Movement watchdog unavailable")
    return {"status": "ok", "protocol_version": PROTOCOL_VERSION}
