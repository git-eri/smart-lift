"""Init file for the app module."""
from pydantic import BaseModel # pylint: disable=no-name-in-module
from fastapi import WebSocket

class LogConfig(BaseModel):
    """Logging configuration to be set for the server"""
    version = 1
    disable_existing_loggers = False
    formatters = {
        "default": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s | %(asctime)s | %(message)s",
            "datefmt": "%d-%m-%Y %H:%M:%S",
        },
        "file": {
            "()": "logging.Formatter",
            "fmt": "%(levelname)s | %(asctime)s | %(message)s",
            "datefmt": "%d-%m-%Y %H:%M:%S",
        }
    }
    handlers = {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "level": "INFO",
        },
        "debug": {
            "formatter": "file",
            "class": "logging.FileHandler",
            "filename": "debug.log",
            "level": "DEBUG",
        },
        "error": {
            "formatter": "file",
            "class": "logging.FileHandler",
            "filename": "error.log",
            "level": "ERROR",
        },
    }
    loggers = {
        "smart-lift": {"handlers": ["default", "debug", "error"], "level": "DEBUG"},
    }

class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, client_id: int, websocket: WebSocket):
        """Adds a new connection to the list of active connections."""
        await websocket.accept()
        self.active_connections.append((client_id, websocket))

    def disconnect(self, client_id: int, websocket: WebSocket):
        """Removes a connection from the list of active connections."""
        self.active_connections.remove((client_id, websocket))

    async def send_personal_message(self, client_id: int, message: str):
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
