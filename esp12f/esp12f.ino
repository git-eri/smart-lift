#define VERSION "0.01.01"
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <WebSocketsClient.h>
#include <Hash.h>
#include <ArduinoJson.h>
#include <ESP8266httpUpdate.h>
#include <LittleFS.h>

BearSSL::WiFiClientSecure client;
BearSSL::X509List *serverCert;
WebSocketsClient webSocket;

// Reset function
void(* resetFunc) (void) = 0;

// Set pins for registers/relais
const uint8_t buttonPin = 0;
const uint8_t stcpPin = 12;
const uint8_t shcpPin = 13;
const uint8_t serPin = 14;
const uint8_t oePin = 5;

// Assign lift numbers to relais
const uint8_t lift_count = 5;
const uint8_t lifts[lift_count][3] = { {15,14,13},
                                       {12,11,10},
                                       {9,8,0},
                                       {1,2,3},
                                       {4,5,6}
                                      };
String con_id;
String SSID;
String PASSWORD;
String SERVER;
int lift_begin;
int PORT;

// Get config file data
bool loadConfig() {
	File configFile = LittleFS.open("/config.json", "r");
	if (!configFile) {
		Serial.println("Failed to open config file");
		return false;
	}

	JsonDocument doc;
	auto error = deserializeJson(doc, configFile);
	if (error) {
		Serial.println("Failed to parse config file");
		return false;
	}

	con_id = String(doc["con_id"]);
	lift_begin = doc["lift_begin"];
	SSID = String(doc["ssid"]);
	PASSWORD = String(doc["password"]);
	SERVER = String(doc["server"]);
	PORT = doc["port"];

	char *buffer = new char[4096];
	File certFile = LittleFS.open("/server.crt", "r");
	if (!certFile) {
		Serial.println("Failed to open cert file");
		return false;
	}
	certFile.readBytes(buffer, certFile.size());
  Serial.println(buffer);
	certFile.close();
	serverCert = new BearSSL::X509List(buffer);
	delete buffer;
	return true;
}

time_t setClock() {
	configTime(2*3600, 0, "pool.ntp.org", "time.nist.gov");
	Serial.print("Waiting for NTP time sync: ");
	time_t now = time(nullptr);
	while (now < 8 * 3600 * 2) {
		delay(500);
		Serial.print(".");
		now = time(nullptr);
	}
	Serial.println("");
	struct tm timeinfo;
	gmtime_r(&now, &timeinfo);
	Serial.print("Current time: ");
	Serial.print(asctime(&timeinfo));
	return now;
}

// Update function
bool update(String updateUrl, BearSSL::WiFiClientSecure client){
	bool mfln = client.probeMaxFragmentLength(SERVER, PORT, 1024);
	Serial.printf("MFLN supported: %s\n", mfln ? "yes" : "no");
	if (mfln) {
		client.setBufferSizes(1024, 1024);
	}
	client.allowSelfSignedCerts();
	client.setTrustAnchors(serverCert);
	setClock();
		Serial.println(updateUrl);
		t_httpUpdate_return ret;
		ESPhttpUpdate.rebootOnUpdate(false);
		ret=ESPhttpUpdate.update(client,updateUrl,VERSION);
		Serial.println(ret);
		if(ret!=HTTP_UPDATE_NO_UPDATES){
			if(ret==HTTP_UPDATE_OK){
				Serial.println("Update succeeded!");
				return true;
			} else {
				if(ret==HTTP_UPDATE_FAILED){
					Serial.println("UPDATE FAILED");
				}
			}
		} else {
			Serial.println("Already on latest version. Continuing...");
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

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
	switch(type) {
		case WStype_DISCONNECTED: {
			Serial.printf("Disconnected!\n");
			for (uint8_t i = 0; i < 16; i++) {
				hc595Write(i, LOW);
			}
			Serial.printf("Cause:");
			if(WiFi.status() != WL_CONNECTED) {
				Serial.println("Wifi got disconnected! Resetting now...");
			} else {
				Serial.println("Server not available! Resetting now...");
			}
			delay(200);
			resetFunc();
		}
			break;

		case WStype_CONNECTED: {
			Serial.printf("Connected to url: %s\n", payload);
			// Build dictionary for server
			StaticJsonDocument<700> about_me;
			about_me["case"] = "hello";
      		JsonArray jlifts = about_me.createNestedArray("lifts");
			for (uint8_t i = lift_begin; i < lift_begin + lift_count; i++) {
				jlifts.add(i);;
			}
			String about_me_str;
			serializeJson(about_me, about_me_str);
			Serial.printf("Sending: %s\n", about_me_str);
			webSocket.sendTXT(about_me_str);
		}
			break;

		case WStype_TEXT: {
			//Serial.printf("[WSc] get text: %s\n", payload);
			StaticJsonDocument<1024> doc_in;
			DeserializationError error = deserializeJson(doc_in, payload);
			if (error) {
				Serial.print(F("deserialize incoming message failed: "));
				Serial.println(error.f_str());
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
				Serial.println("EMERGENCY STOP");
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
				Serial.printf("Message: %s\n", payload);
				return;
			} else {
				// Handle other bullshit that happens
				Serial.printf("Unhandled Event: %s\n", payload);
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
			Serial.printf("get binary length: %u\n", length);
			hexdump(payload, length);
			break;

        case WStype_PING:
            //Serial.printf("[WSc] get ping\n");
            break;

        case WStype_PONG:
            //Serial.printf("[WSc] get pong\n");
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

	Serial.begin(115200);
	Serial.setDebugOutput(true);
	Serial.println();
	Serial.println("active");
	Serial.println();

  	// Get data from filesystem
  	Serial.println("Mounting FS...");

  	if (!LittleFS.begin()) {
    	Serial.println("Failed to mount file system");
    	return;
  	}

  	if (!loadConfig()) {
    	Serial.println("Failed to load config");
  	} else {
    	Serial.println("Config loaded");
  	}

	// Connect to wifi
	WiFi.hostname(con_id.c_str());
	WiFi.mode(WIFI_STA);
	WiFi.begin(SSID, PASSWORD);
	// Wait some time to connect to wifi
	for(uint8_t i = 0; i < 50 && WiFi.status() != WL_CONNECTED; i++) {
		Serial.print(".");
		delay(200);
	}
	Serial.println("");

	// Check if connected to wifi
	if(WiFi.status() != WL_CONNECTED) {
		Serial.println("Could not connect to " + String(SSID) +". Resetting now...");
		delay(200);
		resetFunc();
	}
  // Check for updates
	if (update("https://"+ String(SERVER) + ":" + String(PORT) + "/update/" + con_id, client)) {
		Serial.println("Resetting now...");
		delay(200);
		resetFunc();
	}

	Serial.println("Connected to Wifi, Connecting to server " + SERVER + ":" + PORT + "/ws/" + con_id);

	// Try to connect to Websockets server
	//webSocket.begin(networks[active_net][2], networks[active_net][3].toInt(), "/ws/" + con_id);
  	String uri = "/ws/" + con_id;
	webSocket.beginSslWithCA(SERVER.c_str(), PORT, uri.c_str() , serverCert);

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
      Serial.println("Test Error");
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
