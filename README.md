# smart-lift

This project is a web application to smartify multiple car lifts. 

It is written in Python and uses FastAPI as a web framework. The frontend is written in HTML and Javascript and uses websockets to communicate with the server.

The server communicates to one or more controllers with websockets too. The controllers are relais boards using ESP8266's and are programmed using Arduino.

This system is made for double parking lifts that have 3 actions each: up, down and lock. Each relais on the board simulates a button press for the lift.

| Mobile  | Desktop |
| ------------- | ------------- |
| <img src="media/mobile.gif" height="200">  | <img src="media/desktop.png" height="200">  |

My lifts came with an annoying keyswitch with bad placement. I removed them all, made a custom Box with 3 buttons for every lift. That way every lift can be controlled from one place or with your smartphone. Each button is in parallel to every relais, so both are functional.

| Inside  | Front |
| ------------- | ------------- |
| <img src="media/controlbox_inside.png" height="400">  | <img src="media/controlbox_outside.png" height="200">  |

This setup is just tested for that specific [relais board](#relaisboard--layout) but the settings are easily adaptable to interface with boards with more or less relais.

## Getting Started

### arduino-cli
Install the arduino-cli from the [official website](https://arduino.github.io/arduino-cli/installation/).

Initialize the arduino-cli using ```arduino-cli config init```

Modify the ~/.arduino15/arduino-cli.yaml according to this example:
```yaml
library:
    enable_unsafe_install: true
board_manager:
  additional_urls:
    - https://arduino.esp8266.com/stable/package_esp8266com_index.json
```

Install the ESP8266 board and the necessary libraries:
```bash
arduino-cli core install esp8266:esp8266
arduino-cli lib install ArduinoJson
arduino-cli lib install --git-url https://github.com/Links2004/arduinoWebSockets
```

### Clone the repository:
```bash
git clone https://github.com/git-eri/smart-lift.git
```

Build the binaries and create certificates with:
```bash
./init.sh
```

### Programm the Boards
- Copy the [defaults.json](esp12f/data/default.json) and rename the file to [config.json](#configjson). Edit the file to fit your needs.

#### Dependencies

- [Arduino IDE](https://www.arduino.cc/en/software)
- ESP8266 board manager
- [ArduinoJson](https://arduinojson.org/)
- [WebSockets](https://github.com/Links2004/arduinoWebSockets)
- [LittleFS](https://github.com/earlephilhower/arduino-littlefs-upload)

#### Build & Upload

Using the [ESP8266 board manager](https://arduino-esp8266.readthedocs.io/en/latest/installing.html), install the ESP8266 board. Then install the ArduinoJson and WebSockets librarys. Using the NodeMCU 1.0 (ESP-12E) board, upload the sketch [esp12f.ino](esp12f/esp12f.ino) to your controller.

With the sketch uploaded, you can upload the data folder to the LittleFS of the controller. This can be done using the [LittleFS uploader](https://github.com/earlephilhower/arduino-littlefs-upload). With the plugin installed in the Arduino IDE, you can upload the data folder to the controller using `[Ctrl]` + `[Shift]` + `[P]`, then "`Upload LittleFS to Pico/ESP8266/ESP32`"


### Finally, build and run the docker container:
```bash
docker compose up --build
```
- The docker container should be up and running. Now you can turn on your programmed controllers and access the interface in your browser on port ```8000```. You should see the lifts being addded to the interface as the controllers connect to the server.
- If you reached this step, you may now figure out how to interface with your lift. My lift was controlled using a key switch which i just replaced with the box shown above and connected everything up. You could also use one controller with at least 3 relais for every lift.


## Modifications

### config.json

```json
{
    "con_id": "con1",
    "lift_begin": 0,
    "ssid": "<ssid>",
    "password": "<wifi password>",
    "server": "<server adress>",
    "port": 8000
}
```

### lift_info.json

This file is used by the frontend so you can name your lifts. Change this file accordingly to your setup.

```json
{
    "lifts": [
        {
            "id": 0,
            "name": "Lift 1"
        },
        {
            "id": 1,
            "name": "Lift 2"
        }
    ]
}
```


## Development

### Controller (ESP8266)

#### Relaisboard & Layout

<img src="media/relais_board.png" height="200">


### Controller Simulator

For testing and debugging purposes there is a controller simulator. It can be accessed at ```/sim#0-4```. You can change the number of lifts by changing the numbers after the URI fragment (```#```). The Page will then simulate a controller with the given range of lifts. It responds like a controller and the indicator lights will light up when a lift is moving.

### Known Issues
- [ ] The mobile frontend has to act in a safe way when a controller get's disconnected. Currently if a controller gets disconnected, the disconnected lifts disappear and the ui will move to the other controller. If a button was held down at this time, the lift which is now shown will then move. This needs to be fixed. 
  - Maybe leave the disconnected lifts but grey them out, and show a message so the button press is aborted. Then the lifts can be removed after a timeout.

### What needs to get tested?
- [ ] Checks for invalid calls
- [ ] Checks for leaks
- [ ] Checks for invalid input
- [ ] Checks for race conditions

### What needs to get done?
- [ ] Add monitoring (Prometheus, Grafana)
- [ ] Add unit testing
