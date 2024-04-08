"""Init file for the app module."""
import json
import logging
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

class LiftManager:
    """Manages lifts and protocol messages"""

    def __init__(self):
        self.online_lifts = {}
        self.active_lifts = {}
        with open('app/lift_info.json', encoding="utf8") as file:
            self.lift_info = json.load(file)

    async def send_online_lifts(self, client_id="", broadcast=False):
        """Send the set of active lifts to the specified client."""
        message = {}
        message['case'] = 'online_lifts'
        message['lifts'] = dict(sorted(self.online_lifts.items()))
        if broadcast and client_id == "":
            await cm.broadcast_clients(json.dumps(message))
        else:
            await cm.send_personal_message(client_id, json.dumps(message))

    async def send_move_lift(self, data: dict):
        """Sends the command to the dedicated controller to move the lift"""
        if data['toggle'] == 0:
            self.active_lifts.pop(data['client_id'], None)
        elif data['toggle'] == 1:
            self.active_lifts[data['client_id']] = data['lift_id']
        logger.debug("Active lifts: %s", self.active_lifts)
        await cm.send_personal_message(data['con_id'], json.dumps(data))

    async def send_lift_moved(self, data: dict):
        """Sends the status of the moved lift to all clients"""
        await cm.broadcast_clients(json.dumps(data))

    async def recv_hello(self, con_id: str, data: dict):
        """Save the incoming lift list and broadcast new lifts to clients"""
        self.online_lifts[con_id] = {}
        for lift in data['lifts']:
            self.online_lifts[con_id][lift] = {}
            self.online_lifts[con_id][lift]['id'] = lift
            if str(lift) in self.lift_info:
                self.online_lifts[con_id][lift]['name'] = self.lift_info[str(lift)]['name']
            else:
                logger.error("lift%s not found in lift_info.json. Using default name.", lift)
                self.online_lifts[con_id][lift]['name'] = f"Lift {int(lift) + 1}"
            logger.debug("Controller %s added lift %s", con_id, lift)
        await self.send_online_lifts(broadcast=True)

    async def e_stop(self):
        """Emergency Stop all lifts"""
        message = {}
        message['case'] = 'stop'
        await cm.broadcast(json.dumps(message))
        logger.info("Emergency stop sent")
        self.active_lifts = {}

    async def change_name(self, lift_id, new_name):
        """Changing the Name of the Lift"""
        self.lift_info[str(lift_id)]['name'] = new_name
        await self.send_online_lifts(broadcast=True)

class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: list[tuple[str, WebSocket]] = []

    async def connect(self, client_id: str, websocket: WebSocket):
        """Adds a new connection to the list of active connections."""
        await websocket.accept()
        if client_id.startswith("con"):
            for connection_id, connection in self.active_connections:
                if connection_id == client_id:
                    self.active_connections.remove((client_id, connection))
                    logger.debug(
                        "Controller %s already connected, removing old connection",
                        client_id
                    )
        self.active_connections.append((client_id, websocket))

    async def disconnect(self, client_id: str, websocket: WebSocket):
        """Removes a connection from the list of active connections."""
        if (client_id, websocket) in self.active_connections:
            self.active_connections.remove((client_id, websocket))
            if client_id.startswith("con") and client_id in lm.online_lifts:
                lm.online_lifts.pop(client_id, None)
                logger.debug("Lifts were removed from lifts dict for controller %s", client_id)
                # await websocket.close()
        else:
            logger.debug(
                "Connection %s was already removed from active connections and lifts dict",
                client_id
            )

    async def send_personal_message(self, client_id: str, message: str):
        """Sends a message to a specific connection."""
        for connection_id, connection in self.active_connections:
            if connection_id == client_id:
                await connection.send_text(message)

    async def broadcast(self, message: str):
        """Broadcasts a message to all active connections."""
        for _, connection in self.active_connections:
            await connection.send_text(message)

    async def broadcast_clients(self, message: str):
        """Broadcasts a message to all active clients."""
        for connection_id, connection in self.active_connections:
            if connection_id.startswith("cli"):
                await connection.send_text(message)

logger = logging.getLogger(__name__)
logger.info("Starting smart-lift server...")

app = FastAPI()
app.mount('/static', StaticFiles(directory='app/static'), name='static')

cm = ConnectionManager()
lm = LiftManager()
