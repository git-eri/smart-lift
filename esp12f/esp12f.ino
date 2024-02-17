#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <WebSocketsClient.h>
#include <Hash.h>
#include <ArduinoJson.h>
#include <ESP8266httpUpdate.h>
#include "settings.h"
#define VERSION "0.01.01"
#define USE_SERIAL Serial

WiFiClient client;
WebSocketsClient webSocket;

const uint8_t buttonPin = 0; // a button 
const uint8_t stcpPin = 12;   // GPIO12 	74x595 RCLK/STCP
const uint8_t shcpPin = 13;   // GPIO13 	74x595 SRCLK/SHCP
const uint8_t serPin = 14;    // GPIO14 	74x595 SER/DS
const uint8_t oePin = 5;      // GPIO05 	74x595 OE/output enable active low

void(* resetFunc) (void) = 0;

// A function that accepts arrays of any type T and any length N, and returns the length N. 
template <class T, size_t N> constexpr size_t len(const T(&)[N]) { return N; }

bool update(String updateUrl, WiFiClient client){
	USE_SERIAL.println(updateUrl);
	t_httpUpdate_return ret;
	ESPhttpUpdate.rebootOnUpdate(false);
	ret=ESPhttpUpdate.update(client,updateUrl,VERSION);
	USE_SERIAL.println(ret);
	if(ret!=HTTP_UPDATE_NO_UPDATES){
		if(ret==HTTP_UPDATE_OK){
			USE_SERIAL.println("UPDATE SUCCEEDED");
			return true;
		} else {
			if(ret==HTTP_UPDATE_FAILED){
				USE_SERIAL.println("Update Failed");
			}
		}
	} else {
		USE_SERIAL.println("Already on latest version. Continuing...");
	}
	return false;
}

// 74HC595 shift register pins
void hc595Write(uint8_t pin, uint8_t val) {
	if (pin > 15) return;       // sanitize input
	static uint16_t state = 0;  // remember the state of all outputs in a bitmask
	if (val == HIGH) {
		state |= (1 << pin);      // activate the pin in the bitmask
	}
	else {
		state &= ~(1 << pin);     // deactivate the pin in the bitmask
	}
	digitalWrite(stcpPin, LOW);
	shiftOut(serPin, shcpPin, MSBFIRST, state >> 8);   // send the higher nibble to second 74HC595
	shiftOut(serPin, shcpPin, MSBFIRST, state & 0xFF); // send the lower nibble to first 74HC595
	digitalWrite(stcpPin, HIGH);
}

// Function to get values from string
String getValue(String data, char separator, int index) {
	uint8_t found = 0;
	uint8_t strIndex[] = {0, -1};
	uint8_t maxIndex = data.length()-1;
	for(size_t i = 0; i <= maxIndex && found <= index; i++) {
		if(data.charAt(i) == separator || i == maxIndex) {
			found++;
			strIndex[0] = strIndex[1]+1;
			strIndex[1] = (i == maxIndex) ? i+1 : i;
		}
	}
	return found>index ? data.substring(strIndex[0], strIndex[1]) : "";
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {

	switch(type) {
		case WStype_DISCONNECTED: {
			USE_SERIAL.printf("Disconnected!\n");
			for (uint8_t i = 0; i < 16; i++) {
				hc595Write(i, LOW);
			}
			USE_SERIAL.printf("Cause:");
			if(WiFi.status() != WL_CONNECTED) {
				USE_SERIAL.println("Wifi got disconnected! Resetting now...");
			} else {
				USE_SERIAL.println("Server not available! Resetting now...");
			}
			delay(200);
			resetFunc();
		}
			break;

		case WStype_CONNECTED: {
			USE_SERIAL.printf("Connected to url: %s\n", payload);
			// Build dictionary for server
			StaticJsonDocument<700> about_me;
			about_me["case"] = "hello";
      		JsonArray jlifts = about_me.createNestedArray("lifts");
			for (uint8_t i = lift_begin; i < lift_begin + lift_count; i++) {
				jlifts.add(i);;
			}
			String about_me_str;
			serializeJson(about_me, about_me_str);
			USE_SERIAL.printf("Sending: %s\n", about_me_str);
			webSocket.sendTXT(about_me_str);
		}
			break;

		case WStype_TEXT: {
			//USE_SERIAL.printf("[WSc] get text: %s\n", payload);
			StaticJsonDocument<1024> doc_in;
			DeserializationError error = deserializeJson(doc_in, payload);
			if (error) {
				USE_SERIAL.print(F("deserialize incoming message failed: "));
				USE_SERIAL.println(error.f_str());
				return;
			}

			if (doc_in["case"] == "move_lift") {
				// Handle lift actions
        		uint8_t lift_id = doc_in["lift_id"];
        		uint8_t direction = doc_in["direction"];
				uint8_t value = lifts[lift_id - lift_begin][direction];
				if (doc_in["toggle"] == 1) {
					hc595Write(value, HIGH);
				} else {
					hc595Write(value, LOW);
				}
				StaticJsonDocument<128> doc_out;
				doc_out["case"] = "lift_moved";
				doc_out["lift_id"] = doc_in["lift_id"];
				doc_out["direction"] = doc_in["direction"];
				doc_out["toggle"] = doc_in["toggle"];
				String doc_out_str;
				serializeJson(doc_out, doc_out_str);
				webSocket.sendTXT(doc_out_str);
				return;
			} else if (doc_in["case"] == "stop") {
				// Handle Emergency Stop
				USE_SERIAL.println("EMERGENCY STOP");
				for (uint8_t i = 0; i < 16; i++) {
					hc595Write(i, LOW);
				}
				StaticJsonDocument<128> doc_out;
				doc_out["case"] = "stop";
				doc_out["status"] = "0";
				String doc_out_str;
				serializeJson(doc_out, doc_out_str);
				webSocket.sendTXT(doc_out_str);
				return;
			} else if (doc_in["case"] == "info") {
				// Handle messages from server
				USE_SERIAL.printf("Message: %s\n", payload);
				return;
			} else {
				// Handle other bullshit that happens
				USE_SERIAL.printf("Unhandled Event: %s\n", payload);
				StaticJsonDocument<128> doc_out;
				doc_out["case"] = "error";
				doc_out["type"] = "Unhandled Event";
				doc_out["error"] = payload;
				String doc_out_str;
				serializeJson(doc_out, doc_out_str);
				webSocket.sendTXT(doc_out_str);
				return;
			}
		}
			break;

		case WStype_BIN:
			USE_SERIAL.printf("get binary length: %u\n", length);
			hexdump(payload, length);
			break;

        case WStype_PING:
            //USE_SERIAL.printf("[WSc] get ping\n");
            break;

        case WStype_PONG:
            //USE_SERIAL.printf("[WSc] get pong\n");
            break;
    }
}

void setup() {
	pinMode(buttonPin, INPUT);
	pinMode(stcpPin, OUTPUT);
	pinMode(shcpPin, OUTPUT);
	pinMode(serPin, OUTPUT);
	pinMode(oePin, OUTPUT);
	digitalWrite(oePin, LOW);

	// Disable all relais on start
	for (uint8_t i = 0; i < 16; i++) {
		hc595Write(i, LOW);
	}

	USE_SERIAL.begin(115200);
	USE_SERIAL.setDebugOutput(false);
	USE_SERIAL.println();
	USE_SERIAL.println("active");
	USE_SERIAL.println();

	// Search for known networks
	uint8_t numberOfNetworks = 0;
	for(uint8_t i = 0; i < 3 || numberOfNetworks < 1; i++) {
		numberOfNetworks = WiFi.scanNetworks();
	}
	int active_net = NULL;
	for (uint8_t j = 0; j < len(networks); j++) {
		for(uint8_t i = 0; i < numberOfNetworks; ++i){
      USE_SERIAL.println(WiFi.SSID(i));
			if (networks[j][0] == WiFi.SSID(i)) {
				USE_SERIAL.println("Connecting to Network: " + networks[j][0]);
				active_net = j;
				break;
			}
		}
	}
  if (numberOfNetworks < 1 && active_net == NULL) {
    USE_SERIAL.println("No Networks found. Resetting now ...");
    delay(200);
    resetFunc();
  }

	// Connect to wifi
	WiFi.hostname(con_id.c_str());
	WiFi.mode(WIFI_STA);
	WiFi.begin(networks[active_net][0], networks[active_net][1]);
	// Wait some time to connect to wifi
	for(uint8_t i = 0; i < 50 && WiFi.status() != WL_CONNECTED; i++) {
		USE_SERIAL.print(".");
		delay(200);
	}
	USE_SERIAL.println("");

	// Check if connected to wifi
	if(WiFi.status() != WL_CONNECTED) {
		USE_SERIAL.println("Could not connect to " + networks[active_net][0] +". Resetting now...");
		delay(200);
		resetFunc();
	}
  // Check for updates
	if (update("http://" + networks[active_net][2] + ":" + networks[active_net][3].toInt() + "/update/" + con_id, client)) {
		USE_SERIAL.println("Update successful. Resetting now...");
		delay(200);
		resetFunc();
	}

	USE_SERIAL.println("Connected to Wifi, Connecting to server " + networks[active_net][2] + ":" + networks[active_net][3].toInt() + "/ws/" + con_id);

	// Try to connect to Websockets server
	webSocket.begin(networks[active_net][2], networks[active_net][3].toInt(), "/ws/" + con_id);

	// event handler
	webSocket.onEvent(webSocketEvent);

	webSocket.setReconnectInterval(5000);
}

void loop() {
  webSocket.loop();

  static uint8_t lastButtonState = HIGH;
  uint8_t buttonState = digitalRead(buttonPin);
  if (digitalRead(buttonPin) != lastButtonState) {
    if (buttonState == HIGH) {
      USE_SERIAL.println("Test Error");
      StaticJsonDocument<128> doc_out;
      doc_out["case"] = "error";
      doc_out["type"] = "Test Error";
      doc_out["error"] = "Joke";
      String doc_out_str;
      serializeJson(doc_out, doc_out_str);
      webSocket.sendTXT(doc_out_str);
    }
    delay(50);
  }
  lastButtonState = buttonState;
}
