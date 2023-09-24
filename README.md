# smart-lift

## Getting Started

This project is a web application for a smart lift system. 

It is written in Python and uses FastAPI as a web framework. The frontend is written in HTML and Javascript and uses websockets to communicate with the server.

The server communicates to one or more controllers with websockets too. The controllers are programmed with MicroPython and run on a Raspberry Pi Pico.


## Local Development

### What you need

- Docker
- Python 3.10
- Raspberry Pi Pico

Lint before commit!
```bash
$ pylint app
```


## Server
The server handles the communication between the controllers and the clients.

### Development

For local testing

```bash
$ cd server
$ uvicorn app.main:app --port 8000 --reload --host 0.0.0.0
```

### Deployment

Run the ```deploy.sh``` script.

```bash
$ git clone https://gitlab.erikj.de/git-eri/smart-lift.git
$ cd smart-lift
$ ???
```

## Controller (ESP8266)

### settings.h
```c
// Controller ID: must be unique
const String con_id = "con00001";
// Lifts start from 0, if Controller handles Lift 6-10 it must be 5
const uint8_t lift_begin = 5;
// Lift count: How many lifts the controller handles
const uint8_t lift_count = 5;
// which Relais for which lift
const uint8_t lifts[lift_count][3] = { {0,1,2},
                                       {3,4,5},
                                       {6,7,8},
                                       {9,10,11},
                                       {12,13,14}
                                      };

// Wifi stuff
const char* ssid = ""; //Enter SSID
const char* password = ""; //Enter Password
const char* websockets_server_host = ""; //Enter server adress
const uint16_t websockets_server_port = 8000; // Enter server port
```



## Controller (Pico)

The controller is connected via wifi and should have its own ip address. The server communicates to the controller via http requests. The controller talks back to the server to give information which lifts are active and if the system is healthy.

### auth.json

This file holds informations about possible wifi networks to connect with and the ip address of the server for that network. It should look like this and should be placed in the root directory of the controller:

```json
{
    "ssid": "wifi-name",
    "password": "wifi-password",
    "server": "ip address of server"
}
```


## What needs to get tested?
- [ ] Checks for invalid calls
- [ ] Checks for leaks
