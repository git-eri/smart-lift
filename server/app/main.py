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

websocket_conn = None
controllersocket_conn = None

# broadcast lift status to all clients

@app.get("/")
async def read_root(request: Request):
    """Serve the client-side application."""
    return templates.TemplateResponse("dashboard.html", {"request": request, "lifts": lifts})

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Communicates with the client-side application."""
    await manager.connect(websocket)
    global websocket_conn
    websocket_conn = websocket
    try:
        while True:
            data = await websocket.receive_text()
            split_data = data.split(",")
            if split_data[0] == "hello":
                print(f"[WS] 'Client #{client_id} joined'")
                await manager.broadcast(f"msg,'Client #{client_id} joined'")
            elif split_data[0] == "lift":
                print(f"[WS] {client_id},{data}")
                await manager.broadcast(f"incoming,{client_id},{data}")
                if controllersocket_conn:
                    await controllersocket_conn.send_text(f"incoming,{client_id},{data}")
                # await manager.send_personal_message(f"outgoing,{client_id},{data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"[WS] msg,'Client #{client_id} left'")
        await manager.broadcast(f"msg,'Client #{client_id} left'")

@app.websocket("/cs/{controller_id}")
async def websocket_controller(controllersocket: WebSocket, controller_id: int):
    """Communicates with the controller-side application."""
    await manager.connect(controllersocket)
    global controllersocket_conn
    controllersocket_conn = controllersocket
    try:
        while True:
            data = await controllersocket.receive_text()
            split_data = data.split(",")
            if split_data[0] == "hello":
                controllers.append({"id": controller_id, "name": split_data[1], "ip": split_data[2]})
                print("[CS]", controller_id, "connected")
            else:
                print(f"[CS] {data}")
            #await manager.send_personal_message(f"outgoing,{controller_id},{data}", controllersocket)
            #await manager.broadcast(f"incoming,{controller_id},{data}")
    except WebSocketDisconnect:
        manager.disconnect(controllersocket)
        print(f"[CS] msg,'Controller #{controller_id} left'")
        await manager.broadcast(f"msg,'Client #{controller_id} left'")
