# smart-lift

## Getting Started

This project is a web application for a smart lift system. 

It is written in Python and uses FastAPI as a web framework. The frontend is written in HTML and Javascript and uses websockets to communicate with the server.

The server communicates to one or more controllers with websockets too. The controllers are programmed with MicroPython and run on a Raspberry Pi Pico.


## Local Development

### What you need

- Docker
- Python 3.10
- Any Relais Board based on ESP8266

Lint before commit!
```bash
$ pylint app
```


## Server
The server handles the communication between the controllers and the clients.

### Development

For local testing

```bash
$ cd app
$ uvicorn app.main:app --host=0.0.0.0 --port=8000 --log-config=app/log_conf.yml
```

### Deployment

Run the ```deploy.sh``` script.

```bash
$ git clone https://gitlab.erikj.de/git-eri/smart-lift.git
$ cd smart-lift
$ ???
```

## Controller (ESP8266)

### Dependencies

- [Arduino IDE](https://www.arduino.cc/en/software)
- ESP8266 (https://dl.espressif.com/dl/package_esp32_index.json)
- [ArduinoJson](https://arduinojson.org/)
- [WebSockets](https://github.com/gilmaimon/ArduinoWebsockets)


### settings.h
```c
// Controller ID: must be unique
const String con_id = "con0";
// Lifts start from 0, if Controller handles Lift 6-10 it must be 5
const uint8_t lift_begin = 0;
// Lift count: How many lifts the controller handles
const uint8_t lift_count = 5;
// which Relais for which lift
const uint8_t lifts[lift_count][3] = { {15,14,13},
                                       {12,11,10},
                                       {9,8,6},
                                       {5,4,3},
                                       {2,1,0}
                                      };

// Wifi connections
const String networks[3][4] = { {"SSID","Password","Server IP","Server Port"},
                               };
```


## What needs to get tested?
- [ ] Checks for invalid calls
- [ ] Checks for leaks
