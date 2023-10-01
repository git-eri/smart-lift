"""Main FastAPI application and routing logic."""
import ast
import json
import asyncio
import logging
from logging.config import dictConfig
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from . import LogConfig, ConnectionManager

# Configure logging
dictConfig(LogConfig().dict())
logger = logging.getLogger("smart-lift")

logger.info("Starting smart-lift server...")

app = FastAPI()

app.mount('/static', StaticFiles(directory='static'), name='static')

cm = ConnectionManager()

templates = Jinja2Templates(directory="app/templates")
lifts = []
controllers = []
clients = []
active_lifts = []

# Send active lifts to clients every 10 seconds
async def send_message_to_clients():
    """Sends a message to all active clients every 10 seconds."""
    while True:
        await cm.broadcast_clients("lift_status;" + str(json.dumps(lifts)))
        await asyncio.sleep(2)

# asyncio.create_task(send_message_to_clients())


@app.get("/")
async def read_root(request: Request):
    """Serve the client-side application."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/admin")
async def read_admin(request: Request):
    """Serve the client-side application."""
    return templates.TemplateResponse("admin.html", {"request": request})


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Communicates with the client-side application."""
    await cm.connect(client_id, websocket)
    try:
        if client_id.startswith("con"):
            # Handle Controller event
            logger.info("Controller %s connected", client_id)
            first_touch = await websocket.receive_text()
            first_touch = first_touch.split(";")
            if first_touch[0] == "hello":
                msg_lifts = ast.literal_eval(first_touch[1])
                for lift in msg_lifts:
                    if lift not in lifts:
                        lifts.append(lift)
                await cm.broadcast_clients("lift_status;" + str(json.dumps(lifts)))
            while True:
                data = await websocket.receive_text()
                data = data.split(";")
                logger.debug("Controller %s sent: %s", client_id, data)
                if data[0] == "hello":
                    # Controller joining
                    pass
                elif data[0] == "moved_lift":
                    # Lift moved
                    if data[4] == "0":
                        await cm.broadcast_clients(f"moved_lift;{data[1]};{data[2]};{data[3]}")
                    else:
                        await cm.broadcast(
                            f"error;Controller {client_id} sent invalid data: {data}"
                        )
                elif data[0] == "stop":
                    # Emergency stop
                    pass
                elif data[0] == "error":
                    # Error
                    logger.error("Controller %s sent error: %s", client_id, data)
                else:
                    logger.error("Controller %s sent something unhandled: %s", client_id, data)

        elif client_id.startswith("cli"):
            # Handle Client event
            logger.info("Client %s connected", client_id)
            await cm.send_personal_message(client_id, "lift_status;" + str(json.dumps(lifts)))
            while True:
                data = await websocket.receive_text()
                data = data.split(";")
                logger.debug("Client %s sent: %s", client_id, data)
                if data[0] == "hello":
                    # Client joining
                    pass
                elif data[0] == "lift":
                    # Lift moved
                    con_id = data[1]
                    lift_id = data[2]
                    action = data[3]
                    on_off = data[4]
                    if on_off == "on":
                        await cm.send_personal_message(con_id, f"lift;{lift_id};{action};on")
                        active_lifts.append(lift_id, client_id)
                    elif on_off == "off":
                        await cm.send_personal_message(con_id, f"lift;{lift_id};{action};off")
                    else:
                        logger.error("Client %s sent something unhandled: %s", client_id, data)
                elif data[0] == "stop":
                    # Emergency stop
                    await cm.broadcast("stop")
                else:
                    logger.error("Client %s sent something unhandled: %s", client_id, data)
        else:
            # Handle other event
            logger.error("Something else connected: %s", client_id)
            while True:
                data = await websocket.receive_text()
                logger.error("Something else sent something: %s, %s", client_id, data)
    except WebSocketDisconnect:
        cm.disconnect(client_id, websocket)
        if client_id.startswith("con"):
            # Handle controller disconnecting
            for lift in lifts.copy():
                if lift["controller"] == client_id:
                    lifts.remove(lift)
            await cm.broadcast_clients("lift_status;" + str(json.dumps(lifts)))
            await cm.broadcast(f"msg;Controller {client_id} left")
            logger.info("Controller %s left", client_id)
        elif client_id.startswith("cli"):
            # Handle client disconnecting
            # TODO: Client disconnecting while lift is moving
            if client_id in active_lifts:
                active_lifts.remove(client_id)
            await cm.broadcast(f"msg;Client {client_id} left")
            logger.info("Client %s left", client_id)
        else:
            logger.error("Something else left: %s", client_id)
