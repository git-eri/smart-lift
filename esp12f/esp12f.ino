#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <WebSocketsClient.h>
#include <Hash.h>
#include <ArduinoJson.h>
#include "settings.h"
#define USE_SERIAL Serial

WebSocketsClient webSocket;

const uint8_t buttonPin = 0; // a button 
const uint8_t stcpPin = 12;   // GPIO12 	74x595 RCLK/STCP
const uint8_t shcpPin = 13;   // GPIO13 	74x595 SRCLK/SHCP
const uint8_t serPin = 14;    // GPIO14 	74x595 SER/DS
const uint8_t oePin = 5;      // GPIO05 	74x595 OE/output enable active low
uint8_t active_net = 0;

void(* resetFunc) (void) = 0;

// A function that accepts arrays of any type T and any length N, and returns the length N. 
template <class T, size_t N> constexpr size_t len(const T(&)[N]) { return N; }

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
	int found = 0;
	int strIndex[] = {0, -1};
	int maxIndex = data.length()-1;
	for(int i=0; i<=maxIndex && found<=index; i++) {
		if(data.charAt(i)==separator || i==maxIndex) {
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
			USE_SERIAL.printf("Cause:\n");
			if(WiFi.status() != WL_CONNECTED) {
				USE_SERIAL.println("Wifi got disconnected! Retrying now...");
			} else {
				USE_SERIAL.println("Server not available! Retrying now...");
			}
			delay(200);
			resetFunc();
		}
			break;

		case WStype_CONNECTED: {
			USE_SERIAL.printf("Connected to url: %s\n", payload);
			// Build dictionary for server
			StaticJsonDocument<700> about_me;
			about_me["message"] = "hello";
			JsonObject jlifts = about_me.createNestedObject("lifts");
			for (uint8_t i = lift_begin; i < lift_begin + lift_count; i++) {
				JsonObject jlift = jlifts.createNestedObject(String(i));
				jlift["id"] = i;
				jlift["controller"] = con_id;
			}
			String about_me_str;
			serializeJson(about_me, about_me_str);

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
			String message_in = doc_in["message"];
			//USE_SERIAL.println(payload);
			if (message_in == "lift") {
				// Handle lift actions
				uint8_t lift_id = doc_in["lift"]["id"];
				uint8_t action = doc_in["lift"]["action"];
				uint8_t on_off = doc_in["lift"]["on_off"];
				if (on_off == 1) {
					// Handle lift on
					uint8_t value = lifts[lift_id - lift_begin][action];
					hc595Write(value, HIGH);
					StaticJsonDocument<128> doc_out;
					doc_out["message"] = "moved_lift";
					JsonObject lift = doc_out.createNestedObject("lift");
					lift["id"] = lift_id;
					lift["action"] = action;
					lift["on_off"] = on_off;
					lift["status"] = 0;
					String doc_out_str;
					serializeJson(doc_out, doc_out_str);
					webSocket.sendTXT(doc_out_str);
					return;
				} else if (on_off == 0) {
					//Handle lift off
					uint8_t value = lifts[lift_id - lift_begin][action];
					hc595Write(value, LOW);
					StaticJsonDocument<128> doc_out;
					doc_out["message"] = "moved_lift";
					JsonObject lift = doc_out.createNestedObject("lift");
					lift["id"] = lift_id;
					lift["action"] = action;
					lift["on_off"] = on_off;
					lift["status"] = 0;
					String doc_out_str;
					serializeJson(doc_out, doc_out_str);
					webSocket.sendTXT(doc_out_str);
					return;
				} else {
					// Error
					StaticJsonDocument<128> doc_out;
					doc_out["message"] = "moved_lift";
					JsonObject lift = doc_out.createNestedObject("lift");
					lift["id"] = lift_id;
					lift["action"] = action;
					lift["on_off"] = on_off;
					lift["status"] = 1;
					String doc_out_str;
					serializeJson(doc_out, doc_out_str);
					webSocket.sendTXT(doc_out_str);
					return;
				}
			} else if (message_in == "stop") {
				// Handle Emergency Stop
				USE_SERIAL.println("EMERGENCY STOP");
				for (uint8_t i = 0; i < 16; i++) {
					hc595Write(i, LOW);
				}
				StaticJsonDocument<128> doc_out;
				doc_out["message"] = "stop";
				doc_out["status"] = "0";
				String doc_out_str;
				serializeJson(doc_out, doc_out_str);
				webSocket.sendTXT(doc_out_str);
				return;
			} else if (message_in == "info") {
				// Handle messages from server
				USE_SERIAL.printf("Message: %s\n", payload);
				return;
			} else {
				// Handle other bullshit that happens
				USE_SERIAL.printf("Unhandled Event: %s\n", payload);
				StaticJsonDocument<128> doc_out;
				doc_out["message"] = "error";
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
  	USE_SERIAL.println();
  	USE_SERIAL.println("I am active!");
	USE_SERIAL.setDebugOutput(true);
	USE_SERIAL.println();

	// Search for known networks
	int numberOfNetworks = WiFi.scanNetworks();
	for (size_t j = 0; j < len(networks); ++j) {
		for(int i =0; i < numberOfNetworks; i++){
			if (networks[j][0] == WiFi.SSID(i)) {
				USE_SERIAL.println("Connecting to Network: " + networks[j][0]);
				active_net = j;
				break;
			}
		}
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
		USE_SERIAL.println("Could not connect to " + networks[active_net][0]);
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

  static int lastButtonState = HIGH;
  int buttonState = digitalRead(buttonPin);
  if (digitalRead(buttonPin) != lastButtonState) {
    if (buttonState == HIGH) {
      USE_SERIAL.println("Test Error");
      StaticJsonDocument<128> doc_out;
      doc_out["message"] = "error";
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
