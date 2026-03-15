from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import api, admin
from app.websocket.router import router as ws_router

app = FastAPI(root_path="/api")

Instrumentator().instrument(app, metric_namespace="smartlift").expose(app)

app.include_router(ws_router)
app.include_router(api.router)
app.include_router(admin.router)
