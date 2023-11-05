import json
import socket
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from . import ConnectionManager

logger = logging.getLogger(__name__)
logger.info("Starting smart-lift server...")

app = FastAPI()
app.mount('/static', StaticFiles(directory='app/static'), name='static')

cm = ConnectionManager()

@app.get("/", response_class=FileResponse)
async def read_root():
    """Serve the client-side mobile application."""
    return FileResponse("app/templates/index.html")
@app.get("/admin", response_class=FileResponse)
async def read_admin():
    """Serve the client-side admin application."""
    return FileResponse("app/templates/admin.html")


active_lifts = json.loads('{}')

"""
Main websocket endpoint
"""
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Communicates with the client-side application."""
    await cm.connect(client_id, websocket)
    try:
        if client_id.startswith("con"):
            """
            Handle Controller event
            """
            while True:
                data = await websocket.receive_text()
                data = json.loads(data)
                logger.debug("Controller %s sent: %s", client_id, data)
                if data['message'] == 'hello':
                    # Hello message
                    if client_id not in active_lifts:
                        active_lifts[client_id] = []
                        for lift in data['lifts']:
                            active_lifts[client_id].append(lift)
                            logger.debug("Controller %s added lift %s", client_id, lift)
                        logger.info("Controller %s connected", client_id)
                    else:
                        cm.disconnect(client_id, websocket)
                        logger.error("Controller %s already connected", client_id)
                    print(active_lifts)
                elif data['message'] == 'moved_lift':
                    # Lift moved
                    """
                    {
                        "message": "moved_lift",
                        "lift": {
                            "id": 0,
                            "action": 0,
                            "on_off": 0,
                            "status": 0
                        }
                    }
                    """
                    if data[4] == "0":
                        await cm.broadcast_clients(json.dumps(data))
                    else:
                        await cm.broadcast(
                            f"error;Controller {client_id} sent invalid data: {data}"
                        )
                elif data['message'] == 'stop':
                    # Emergency stop
                    pass
                elif data['message'] == 'error':
                    # Error
                    logger.error("Controller %s sent error: %s", client_id, data)
                else:
                    logger.error("Controller %s sent invalid data: %s", client_id, data)


        elif client_id.startswith("cli"):
            """
            Handle Client event
            """
            logger.info("Client %s connected", client_id)
            while True:
                data = await websocket.receive_text()
                logger.debug("Client %s sent: %s", client_id, data)
        else:
            """
            Handle other events
            """
            logger.error("Something else connected: %s", client_id)
            while True:
                data = await websocket.receive_text()
                logger.error("Something else sent something: %s, %s", client_id, data)

    except WebSocketDisconnect:
        cm.disconnect(client_id, websocket)
        if client_id.startswith("con"):
            active_lifts.pop(client_id, None)
            print(active_lifts)
            logger.info("Controller %s left", client_id)
        elif client_id.startswith("cli"):
            logger.info("Client %s left", client_id)
        logger.info("ID %s left", client_id)

