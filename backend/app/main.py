"""Main application file"""
import os
import json
from fastapi import WebSocket, WebSocketDisconnect, Header, Response
from fastapi.responses import FileResponse
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.cors import CORSMiddleware
from packaging import version
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from . import client, controller, logger, app, cm, lm

# check if https is enabled
if os.getenv('USE_SSL', 'false').lower() == 'true':
    logger.info("HTTPS is enabled, redirecting HTTP to HTTPS")
    app.add_middleware(HTTPSRedirectMiddleware)
else:
    logger.info("HTTPS is not enabled, not redirecting HTTP to HTTPS")

hostname = os.getenv('HOSTNAME', 'localhost').lower()
frontend_port = os.getenv('FRONTEND_PORT', '8080')

origins = [
    f"http://{hostname}:{frontend_port}",
    f"https://{hostname}",
    f"https://smart-lift.pbs-it.de"
]

logger.info(f"Hostname: {hostname}")

app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
)

Instrumentator().instrument(app, metric_namespace='smartlift').expose(app)

class RenameRequest(BaseModel):
    lift_id: int
    new_name: str

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Communicates with the clients application."""
    await cm.connect(client_id, websocket)
    try:
        if client_id.startswith("con"):
            await controller.handler(websocket, client_id)

        elif client_id.startswith("cli"):
            await client.handler(websocket, client_id)

        else:
            logger.error("Something else connected: %s", client_id)
            while True:
                data = await websocket.receive_text()
                logger.error("Something sus sent something: %s, %s", client_id, data)

    except WebSocketDisconnect:
        await cm.disconnect(client_id, websocket)
        if client_id.startswith("con") and client_id not in lm.online_lifts:
            await lm.send_online_lifts(broadcast=True)
            logger.info("Controller %s left", client_id)
        elif client_id.startswith("cli"):
            message = {}
            message['case'] = 'client_disconnect'
            message['client_id'] = client_id
            if client_id in lm.active_lifts:
                await lm.e_stop()
                logger.error("Client %s left while controlling lifts", client_id)
            await cm.broadcast_clients(json.dumps(message))
            logger.info("Client %s left", client_id)

@app.get("/update/{con_id}")
async def update(con_id: str, x_esp8266_version: str | None = Header(default=None)):
    """Updates the controller with the latest data."""
    # Get latest version on server
    latest_version = None
    for file in os.listdir('app/binaries'):
        if file.endswith('.bin'):
            latest_version = file.strip('.bin')
            print(latest_version)
    if latest_version is None:
        return {"error": "No binaries found on server"}

    # Check if the controller has the latest version
    if version.parse(x_esp8266_version) < version.parse(latest_version):
        # Send the latest version to the controller
        logger.info("Sending updates to controller: %s, %s", con_id, latest_version)
        return FileResponse("app/binaries/" + con_id + "-" + latest_version + ".bin")

    return Response(status_code=304)

@app.post("/admin/lift-rename")
async def rename_lift_endpoint(payload: RenameRequest):
    """Admin-Endpoint: Name eines Lifts ändern"""
    await lm.change_name(payload.lift_id, payload.new_name)
    return {
        "status": "ok",
        "lift_id": payload.lift_id,
        "new_name": payload.new_name
    }
