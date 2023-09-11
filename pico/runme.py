import uasyncio
import machine
import tools
from websockets.client import connect
from picozero import pico_led
import utime

async def connect_ws(ip, server):
    ws = await connect("ws://" + server + ":8000/ws/1234")
    if not ws:
        print("Verbindung fehlgeschlagen")
        return

    led_on = False
    led_off_task = None

    def turn_off_led():
        nonlocal led_on
        pico_led.off()  # LED ausschalten
        led_on = False
        #print("LED off")

    async def handle_message(msg):
        nonlocal led_on, led_off_task
        data = msg.split(",")
        if len(data) < 5:
            print("Unhandled Event 1:", msg)
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
            print("Unhandled Event 2:", msg)

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

try:
    # Bootup
    pico_led.off()
    ip, server = tools.connect()
    print("Connecting to server", server)
    loop = uasyncio.get_event_loop()
    loop.run_until_complete(connect_ws(ip, server))

except KeyboardInterrupt:
    machine.reset()
except:
    tools.blink(20,0.1)
    machine.reset()

#loop.run_forever()
