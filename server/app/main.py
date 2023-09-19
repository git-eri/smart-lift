"""Main FastAPI application and routing logic."""
import ast
import asyncio
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, BackgroundTasks
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

async def send_lift_status(websocket):
    while True:
        await websocket.send_text("This is a periodic message.")
        print("Sent lift status")
        await asyncio.sleep(10)

templates = Jinja2Templates(directory="app/templates")

lifts = []
active_lifts = []

@app.get("/")
async def read_root(request: Request):
    """Serve the client-side application."""
    return templates.TemplateResponse("dashboard.html", {"request": request, "lifts": lifts})

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str, background_tasks: BackgroundTasks):
    """Communicates with the client-side application."""
    await manager.connect(websocket)
    if not client_id.startswith("c"):
        print(f"Client {client_id} connected")
        background_tasks.add_task(send_lift_status, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            split_data = data.split(";")

            if client_id.startswith("c"):
                # Handle Controller messages
                if split_data[0] == "hello":
                    # Handle Controller joining
                    print(f"Controller {client_id} connected")
                    msg_lifts = ast.literal_eval(split_data[3])
                    for lift in msg_lifts:
                        if lift not in lifts:
                            lifts.append(lift)
                    await manager.broadcast(f"msg;controller {client_id} joined")
                elif split_data[0] == "active_lifts":
                    # Handle Controller sending active lifts
                    msg_active = ast.literal_eval(split_data[1])
                    for lift in msg_active:
                        if lift not in active_lifts:
                            active_lifts.append(lift)
                    await manager.broadcast(f"clients;active_lifts;{active_lifts}")
                    # await manager.send_personal_message(f"outgoing;{client_id};{data}",websocket)
            else:
                # Handle client messages
                if split_data[0] == "lift":
                    # Handle Lift moving
                    await manager.broadcast(f"incoming;{client_id};{data}")
                elif split_data[0] == "stop":
                    # Handle Emergency Stop
                    print("EMERGENCY STOP")
                    await manager.broadcast(f"incoming;{client_id};{data}")
                else:
                    print(f"Something Else: {client_id},{data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        if client_id.startswith("c"):
            # Handle controller disconnecting
            for lift in lifts:
                print(lift)
                if lift["controller"] == client_id:
                    lifts.remove(lift)
            for lift in active_lifts:
                if lift["controller"] == client_id:
                    active_lifts.remove(lift)
            # TODO: Somehow not all lifts are removed from the list
            await manager.broadcast(f"msg;Controller {client_id} left")
        else:
            # Handle client disconnecting
            print(f"Client {client_id} left")
            await manager.broadcast(f"msg;Client {client_id} left")
