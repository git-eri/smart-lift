import network
import socket
import machine
from time import sleep
from picozero import pico_temp_sensor, pico_led

import tools

def webpage(state):
    # Format html file
    with open('index.html', 'r') as f:
        html = f.read()
        html = html.format(state = state)
    return str(html)

def serve(connection):
    # Start web server
    state = 'OFF'
    pico_led.off()
    while True:
        client = connection.accept()[0]
        request = client.recv(1024)
        request = str(request)
        print(request)
        
        # Handle requests
        try:
            request = request.split()[1]
        except IndexError:
            pass
        if request == '/up?':
            pico_led.on()
            state = 'UP'
        elif request == '/down?':
            pico_led.off()
            state = 'DOWN'
        
        html = webpage(state)
        client.send(html)
        client.close()

try:
    # Bootup
    ip = tools.connect()
    connection = tools.open_socket(ip)
    serve(connection)
except KeyboardInterrupt:
    machine.reset()
except:
    tools.blink(20,0.1)
    machine.reset()