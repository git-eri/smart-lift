import json
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from . import logger, app, cm, lifts, client, controller

@app.get("/", response_class=FileResponse)
async def read_root():
    """Serve the client-side mobile application."""
    return FileResponse("app/templates/index.html")
@app.get("/admin", response_class=FileResponse)
async def read_admin():
    """Serve the client-side admin application."""
    return FileResponse("app/templates/admin.html")

"""
Main websocket endpoint
"""
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Communicates with the client-side application."""
    await cm.connect(client_id, websocket)
    try:
        if client_id.startswith("con"):
            await controller.handler(websocket, client_id)

        elif client_id.startswith("cli"):
            await client.handler(websocket, client_id)
        else:
            """
            Handle other events
            """
            logger.error("Something else connected: %s", client_id)
            while True:
                data = await websocket.receive_text()
                logger.error("Something else sent something: %s, %s", client_id, data)

    except WebSocketDisconnect:
        await cm.disconnect(client_id, websocket)
        if client_id.startswith("con") and client_id not in lifts:
            message = {}
            message['message'] = 'lift_status'
            message['lifts'] = lifts
            await cm.broadcast_clients(json.dumps(message))
            logger.info("Controller %s left", client_id)
        elif client_id.startswith("cli"):
            logger.info("Client %s left", client_id)

    except Exception as e:
        await cm.disconnect(client_id, websocket)
        logger.exception(e)
