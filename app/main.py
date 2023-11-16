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

lifts = json.loads('{}')
#active_lifts = json.loads('{}')

def get_lift_info():
    with open('app/lift_info.json') as f:
        data = json.load(f)
    return data

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
            """
            Handle Controller event
            """
            while True:
                data = await websocket.receive_text()
                try:
                    data = json.loads(data)
                except:
                    logger.error("Controller %s sent invalid data: %s", client_id, data)
                    continue
                # logger.debug("Controller %s sent: %s", client_id, data)
                if data['message'] == 'hello':
                    # Hello message
                    if client_id not in lifts:
                        lifts[client_id] = {}
                        lift_info = get_lift_info()
                        for lift in data['lifts']:
                            lifts[client_id][lift] = {}
                            lifts[client_id][lift]['id'] = lift
                            lifts[client_id][lift]['name'] = lift_info[lift]['name']
                            logger.debug("Controller %s added lift %s", client_id, lift)
                        message = {}
                        message['message'] = 'lift_status'
                        message['lifts'] = lifts
                        await cm.broadcast_clients(json.dumps(message))
                        logger.info("Controller %s connected", client_id)
                    else:
                        cm.disconnect(client_id, websocket)
                        logger.error("Controller %s already connected", client_id)
                elif data['message'] == 'moved_lift':
                    print(data)
                    # Lift moved
                    if data['lift']['status'] == 0:
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
            message = {}
            message['message'] = 'lift_status'
            message['lifts'] = lifts
            await cm.send_personal_message(client_id, json.dumps(message))
            while True:
                data = await websocket.receive_text()
                try:
                    data = json.loads(data)
                except:
                    logger.error("Client %s sent invalid data: %s", client_id, data)
                    continue
                logger.debug("Client %s sent: %s", client_id, data)
                if data['message'] == 'hello':
                    # Client joining
                    pass
                elif data['message'] == 'lift':
                    # Lift moved
                    con_id = data['lift']['con_id']
                    lift_id = data['lift']['id']
                    action = data['lift']['action']
                    on_off = data['lift']['on_off']
                    if on_off == 1:
                        message = {}
                        message['message'] = 'lift'
                        message['lift'] = {}
                        message['lift']['id'] = lift_id
                        message['lift']['action'] = action
                        message['lift']['on_off'] = '1'
                        await cm.send_personal_message(con_id, json.dumps(message))
                        #active_lifts.append(lift_id, client_id)
                    elif on_off == 0:
                        message = {}
                        message['message'] = 'lift'
                        message['lift'] = {}
                        message['lift']['id'] = lift_id
                        message['lift']['action'] = action
                        message['lift']['on_off'] = '0'
                        await cm.send_personal_message(con_id, json.dumps(message))
                    else:
                        logger.error("Client %s sent something unhandled: %s", client_id, data)
                elif data['message'] == 'error':
                    # Error
                    logger.error("Client %s sent error: %s", client_id, data)
                else:
                    logger.error("Client %s sent invalid data: %s", client_id, data)
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
            lifts.pop(client_id, None)
            logger.info("Controller %s left", client_id)
        elif client_id.startswith("cli"):
            logger.info("Client %s left", client_id)

