"""Init file for the app module."""
import json
import logging
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

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
                    logger.debug("Controller %s already connected, removing old connection", client_id)
        self.active_connections.append((client_id, websocket))

    async def disconnect(self, client_id: str, websocket: WebSocket):
        """Removes a connection from the list of active connections."""
        if (client_id, websocket) in self.active_connections:
            self.active_connections.remove((client_id, websocket))
            if client_id.startswith("con") and client_id in lifts:
                lifts.pop(client_id, None)
                logger.debug("Lifts were removed from lifts dict for controller %s", client_id)
                # await websocket.close()
        else:
            logger.debug("Connection %s was already removed from active connections and lifts dict", client_id)

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

lifts = json.loads('{}')
#active_lifts = json.loads('{}')

app = FastAPI()
app.mount('/static', StaticFiles(directory='app/static'), name='static')

cm = ConnectionManager()
