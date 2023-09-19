import uasyncio
import machine
import tools
from websockets.client import connect
from picozero import pico_led
import utime

pico_id = tools.read_id()

lifts = [
    {"id": "0", "name": "Lift 1", "controller": "c00001"},
    {"id": "1", "name": "Lift 2", "controller": "c00001"},
    {"id": "2", "name": "Lift 3", "controller": "c00001"},
    {"id": "3", "name": "Lift 4", "controller": "c00001"},
    {"id": "4", "name": "Lift 5", "controller": "c00001"}
]


async def connect_ws(ip, server):
    last_msg_time = None
    led_on = False
    led_off_task = None
    connection = None

    try:
        ws = await connect("ws://" + server + ":8000/ws/c0000" + str(pico_id))
        connection = True
    except:
        print("Connection to server failed")
        return

    await ws.send("hello;Pico_" + str(pico_id) + ";" + ip + ";" + str(lifts))

    def turn_off_led():
        nonlocal led_on
        pico_led.off()  # LED ausschalten
        led_on = False
        #print("LED Turned OFF!!!")
    
    async def handle_active_lifts():
        while connection:
            await ws.send('active_lifts;{"id": "0", "name": "Lift 1", "controller": "c00001"},{"id": "1", "name": "Lift 2", "controller": "c00001"}')
            #print("Sent Lift status")
            await uasyncio.sleep(5)
    uasyncio.create_task(handle_active_lifts())

    async def handle_message(msg):
        nonlocal led_on, led_off_task
        data = msg.split(";")

        if data[0] == "msg":
            print("Message:", msg)
        elif len(data) < 5:
            print("msg too short!:", msg)
        elif data[0] == "clients":
            pass
        elif data[2] == "lift":
            #print("Lift", data[3], "Aktion", data[4])

            if not led_on:
                pico_led.on()  # LED einschalten
                led_on = True
                
            if led_off_task:
                led_off_task.cancel()  # Task zum Ausschalten der LED abbrechen
            led_off_task = uasyncio.create_task(turn_off_led_after_delay())
        elif data[2] == "stop":
            print("EMERGENCY STOP")
        else:
            print("Unhandled Event:", msg)

    async def turn_off_led_after_delay():
        await uasyncio.sleep(0.5)  # Warte 500 ms
        turn_off_led()  # LED ausschalten

    try:
        async for msg in ws:
            last_msg_time = utime.ticks_ms()
            await handle_message(msg)
    except Exception as e:
        print("Error:", e)
    finally:
        while utime.ticks_diff(utime.ticks_ms(), last_msg_time) < 200:
            await uasyncio.sleep(0.1)  # Warte, bis 500 ms abgelaufen sind
        turn_off_led()  # LED ausschalten

    await ws.wait_closed()
    connection = False
    print("Connection was closed from server")

try:
    # Bootup
    pico_led.off()
    ip, server = tools.connect()
    print("Connecting to server", server)
    loop = uasyncio.get_event_loop()
    loop.run_until_complete(connect_ws(ip, server))
    loop.run_forever()

except KeyboardInterrupt:
    print("Keyboard Interrupt!")
    #machine.reset()

except OSError as err:
    print("OSError:", err)
    #tools.blink(20,0.1)
    #machine.reset()

#loop.run_forever()
