"""Main FastAPI application and routing logic."""
import ast
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates

app = FastAPI()

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

cm = ConnectionManager()

templates = Jinja2Templates(directory="app/templates")
lifts = []
controllers = []
clients = []

@app.get("/")
async def read_root(request: Request):
    """Serve the client-side application."""
    return templates.TemplateResponse("dashboard.html", {"request": request, "lifts": lifts})

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """Communicates with the client-side application."""
    await cm.connect(client_id, websocket)
    try:
        if client_id.startswith("con"):
            # Handle Controller event
            print(f"Controller {client_id} connected")
            while True:
                data = await websocket.receive_text()
                data = data.split(";")
                print("Controller sent:", data)
                if data[0] == "hello":
                    # Controller joining
                    msg_lifts = ast.literal_eval(data[1])
                    for lift in msg_lifts:
                        if lift not in lifts:
                            lifts.append(lift)
                    print("Current Lifts:", lifts)
                elif data[0] == "moved_lift":
                    # Lift moved
                    if data[4] == "0":
                        await cm.broadcast_clients(f"moved_lift;{data[1]};{data[2]};{data[3]}")
                    else:
                        await cm.broadcast(f"error;Controller {client_id} sent invalid data: {data}")
                elif data[0] == "stop":
                    # Emergency stop
                    pass
                elif data[0] == "error":
                    # Error
                    pass
                else:
                    print(f"Controller sent something unhandled: {client_id},{data}")
        elif client_id.startswith("cli"):
            # Handle Client event
            print(f"Client {client_id} connected")
            while True:
                data = await websocket.receive_text()
                data = data.split(";")
                print("Client sent:", data)
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
                    elif on_off == "off":
                        await cm.send_personal_message(con_id, f"lift;{lift_id};{action};off")
                    else:
                        print(f"Client sent something unhandled: {client_id},{data}")
                elif data[0] == "stop":
                    # Emergency stop
                    await cm.broadcast(f"stop")
                else:
                    print(f"Client sent something unhandled: {client_id},{data}")
        else:
            # Handle other event
            print(f"Something else connected: {client_id}")
            while True:
                data = await websocket.receive_text()
                print(f"Something else sent something: {client_id},{data}")
    except WebSocketDisconnect:
        cm.disconnect(client_id, websocket)
        if client_id.startswith("con"):
            # Handle controller disconnecting
            # for lift in lifts:
            #     if lift["controller"] == client_id:
            #         lifts.remove(lift)
            print(f"Controller {client_id} left")
            await cm.broadcast(f"msg;Controller {client_id} left")
        elif client_id.startswith("cli"):
            # Handle client disconnecting
            print(f"Client {client_id} left")
            await cm.broadcast(f"msg;Client {client_id} left")
        else:
            print(f"Something else left: {client_id}")
