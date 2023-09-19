import json
import network
import machine
import socket
from time import sleep
from picozero import pico_led

def read_auth():
    # Read auth.json and return ssid and password
    with open('auth.json', 'r') as f:
        data = json.load(f)
    return data

def read_id():
    # Read pico_id and return id
    with open('pico_id', 'r') as f:
        id = f.readline().strip('\n')
    return int(id)

def connect():
    # Connect to WLAN and return own IP
    server = None
    pico_id = read_id()
    wlan = network.WLAN(network.STA_IF)
    wlan.config(hostname=f"pico{pico_id}")
    wlan.config(pm = 0xa11140) # type: ignore # disable power saving
    wlan.active(True)
    # Search for known networks
    while wlan.isconnected() == False or server == None:
        ip = None
        ssid = None
        server = None
        tries = 0
        while not ssid:
            print("Search for networks")
            networks = wlan.scan()
            known_net = read_auth()    
            for net in known_net:
                for w in networks:
                    if known_net[net]["ssid"] == w[0].decode():
                        ssid = known_net[net]["ssid"]
                        password = known_net[net]["password"]
                        server = known_net[net]["server"]
                        print(f"Connecting to {ssid}...")
                        wlan.connect(ssid, password)
                        break
            if not ssid:
                print("No known network found...")
                #blink(10,0.1)
                #machine.reset()
        while wlan.isconnected() == False:
            print('Waiting for connection...')
            sleep(1)
            tries = tries + 1
            if tries >= 10:
                print("Retry Wifi connect")
                break
    
    ip = wlan.ifconfig()
    print('IPv4-Address:', ip[0], '/', ip[1])
    print('Standard-Gateway:', ip[2])
    print('DNS-Server:', ip[3])
    blink(5, 0.05)
    return ip[0], server

def open_socket(ip):
    address = (ip, 80)
    connection = socket.socket()
    connection.bind(address)
    connection.listen(1)
    return connection

def connect_to_server(ip):
    address = (ip, 80)
    connection = socket.socket()
    connection.connect(address)
    return connection

def blink(amount, speed):
    pico_led.off()
    for i in range(amount):
        pico_led.on()
        sleep(speed)
        pico_led.off()
        sleep(speed)