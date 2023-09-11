import uasyncio
import machine
import tools
from websockets.client import connect

async def connect_ws():
    ws = await connect("ws://192.168.178.63:8000/ws/1234")
    if not ws:
        print("connection failed")
        return
    print("sending")
    await ws.send("This is a story")
    print("sent")
    async for msg in ws:
        print(msg)
    await ws.wait_closed()

try:
    # Bootup
    ip = tools.connect()
    
except KeyboardInterrupt:
    machine.reset()
except:
    tools.blink(20,0.1)
    machine.reset()
    
loop = uasyncio.get_event_loop()
loop.run_until_complete(connect_ws())