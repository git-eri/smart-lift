"""Main FastAPI application and routing logic."""
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates

app = FastAPI()

class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Adds a new connection to the list of active connections."""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Removes a connection from the list of active connections."""
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Sends a message to a specific connection."""
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        """Broadcasts a message to all active connections."""
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

templates = Jinja2Templates(directory="app/templates")

controllers = [
    {"id": "0", "name": "Controller 1", "ip": "192.168.178.23"},
    {"id": "1", "name": "Controller 2", "ip": "192.168.178.24"},
]

lifts = [
    {"id": "0", "name": "Lift 1"},
    {"id": "1", "name": "Lift 2"},
    {"id": "2", "name": "Lift 3"},
    {"id": "3", "name": "Lift 4"},
    {"id": "4", "name": "Lift 5"}
]

# broadcast lift status to all clients

@app.get("/")
async def read_root(request: Request):
    """Serve the client-side application."""
    return templates.TemplateResponse("dashboard.html", {"request": request, "lifts": lifts})

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    """Communicates with the client-side application."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"{client_id},{data}")
            # await manager.send_personal_message(f"outgoing,{client_id},{data}", websocket)
            await manager.broadcast(f"incoming,{client_id},{data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"msg,'Client #{client_id} left'")
        await manager.broadcast(f"msg,'Client #{client_id} left'")


@app.websocket("/cs/{controller_id}")
async def websocket_endpoint(websocket: WebSocket, controller_id: int):
    """Communicates with the controller-side application."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            print(f"{controller_id},{data}")
            await manager.send_personal_message(f"outgoing,{controller_id},{data}", websocket)
            await manager.broadcast(f"incoming,{controller_id},{data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"msg,'Controller #{controller_id} left'")
        await manager.broadcast(f"msg,'Client #{controller_id} left'")
