"""Main application file"""
import os
import json
from fastapi import WebSocket, WebSocketDisconnect, Header, Response
from fastapi.responses import FileResponse
from packaging import version
from prometheus_fastapi_instrumentator import Instrumentator

from . import client, controller, logger, app, cm, lm

Instrumentator().instrument(app, metric_namespace='smartlift').expose(app)

@app.get("/", response_class=FileResponse)
async def read_root():
    """Serve the client-side mobile application."""
    return FileResponse("app/templates/index.html")
@app.get("/admin", response_class=FileResponse)
async def read_admin():
    """Serve the client-side admin application."""
    return FileResponse("app/templates/admin.html")
@app.get("/sim", response_class=FileResponse)
async def read_sim():
    """Serve the client-side sim application."""
    return FileResponse("app/templates/sim.html")


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
            await cm.broadcast_clients(json.dumps(message))
            logger.info("Client %s left", client_id)

@app.get("/update/{con_id}")
async def update(con_id: str, x_esp8266_version: str | None = Header(default=None)):
    """Updates the controller with the latest data."""
    # Get latest version on server
    latest_version = None
    device = None
    for file in os.listdir('app/binaries'):
        if file.endswith('.bin'):
            device = file.split('-')[0]
            if device == con_id:
                latest_version = file.strip('.bin').strip(device).strip('-')
                print(device, latest_version)
    if latest_version is None:
        return {"error": "No binaries found on server"}
    if device is None:
        return {"error": "No binaries found on server"}

    # Check if the controller has the latest version
    if version.parse(x_esp8266_version) < version.parse(latest_version):
        # Send the latest version to the controller
        logger.info("Sending updates to controller: %s, %s", con_id, latest_version)
        return FileResponse("app/binaries/" + con_id + "-" + latest_version + ".bin")

    return Response(status_code=304)
