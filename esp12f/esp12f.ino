#define VERSION "0.01.01"
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <WebSocketsClient.h>
#include <Hash.h>
#include <ArduinoJson.h>
#include <ESP8266httpUpdate.h>
#include <LittleFS.h>

BearSSL::WiFiClientSecure client;
BearSSL::X509List *serverCert = nullptr;
WebSocketsClient webSocket;

// Pins
const uint8_t buttonPin = 0;
const uint8_t stcpPin = 12;
const uint8_t shcpPin = 13;
const uint8_t serPin = 14;
const uint8_t oePin = 5;

// Lift Relais Mapping
const uint8_t relais_count = 16;
const uint8_t lift_count = 5;
const uint8_t lifts[lift_count][3] = {
  {15,14,13}, {12,11,10}, {9,8,0}, {1,2,3}, {4,5,6}
};

String con_id = "";
String SSID = "";
String PASSWORD = "";
String SERVER = "";
int lift_begin = 0;
int PORT = 0;

// Hilfsfunktion: JSON senden
void sendMessage(const JsonDocument& doc) {
  String jsonStr;
  serializeJson(doc, jsonStr);
  webSocket.sendTXT(jsonStr);
}

// Konfigurationsdatei lesen
bool loadConfig() {
  File configFile = LittleFS.open("/config.json", "r");
  if (!configFile) {
    Serial.println("Failed to open config file");
    return false;
  }

  JsonDocument doc;
  if (deserializeJson(doc, configFile)) {
    Serial.println("Failed to parse config file");
    return false;
  }

  con_id = String(doc["con_id"] | "");
  lift_begin = doc["lift_begin"] | 0;
  SSID = String(doc["ssid"] | "");
  PASSWORD = String(doc["password"] | "");
  SERVER = String(doc["server"] | "");
  PORT = doc["port"] | 443;

  File certFile = LittleFS.open("/server.crt", "r");
  if (!certFile) {
    Serial.println("Failed to open cert file");
    return false;
  }

  String certStr;
  certStr.reserve(2048);
  certStr = certFile.readString();
  serverCert = new BearSSL::X509List(certStr.c_str());
  return true;
}

// Zeit synchronisieren
time_t setClock() {
  configTime(2 * 3600, 0, "pool.ntp.org", "time.nist.gov");
  time_t now = time(nullptr);
  while (now < 8 * 3600 * 2) {
    delay(500);
    Serial.print(".");
    now = time(nullptr);
  }
  Serial.println();
  Serial.print("Current time: ");
  Serial.println(ctime(&now));
  return now;
}

// Firmware-Update
bool updateFirmware(String updateUrl, BearSSL::WiFiClientSecure& client) {
  bool mfln = client.probeMaxFragmentLength(SERVER, PORT, 1024);
  if (mfln) {
    client.setBufferSizes(1024, 1024);
  }

  client.allowSelfSignedCerts();
  client.setTrustAnchors(serverCert);
  setClock();

  Serial.println("Update URL: " + updateUrl);
  ESPhttpUpdate.rebootOnUpdate(false);
  t_httpUpdate_return ret = ESPhttpUpdate.update(client, updateUrl, VERSION);

  if (ret == HTTP_UPDATE_OK) {
    Serial.println("Update succeeded!");
    return true;
  } else if (ret == HTTP_UPDATE_FAILED) {
    Serial.println("Update failed");
  } else {
    Serial.println("Already up-to-date");
  }

  return false;
}

// 74HC595 Relais ansteuern
void hc595Write(uint8_t pin, uint8_t val) {
  if (pin > 15) return;
  static uint16_t state = 0;
  if (val == HIGH) state |= (1 << pin);
  else state &= ~(1 << pin);

  digitalWrite(stcpPin, LOW);
  shiftOut(serPin, shcpPin, MSBFIRST, state >> 8);
  shiftOut(serPin, shcpPin, MSBFIRST, state & 0xFF);
  digitalWrite(stcpPin, HIGH);
}

// WebSocket Event-Handler
void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch (type) {
    case WStype_DISCONNECTED:
      Serial.println("WebSocket disconnected. Resetting...");
      for (uint8_t i = 0; i < relais_count; i++) hc595Write(i, LOW);
      delay(200);
      ESP.restart();
      break;

    case WStype_CONNECTED: {
      Serial.printf("Connected to: %s\n", payload);
      StaticJsonDocument<512> about_me;
      about_me["case"] = "hello";
      JsonArray jlifts = about_me.createNestedArray("lifts");
      for (uint8_t i = lift_begin; i < lift_begin + lift_count; i++) {
        jlifts.add(i);
      }
      sendMessage(about_me);
      break;
    }

    case WStype_TEXT: {
      StaticJsonDocument<1024> doc_in;
      if (deserializeJson(doc_in, payload)) {
        Serial.println("JSON parse error");
        return;
      }

      String caseType = doc_in["case"] | "";

      if (caseType == "move_lift") {
        uint8_t lift_id = doc_in["lift_id"];
        uint8_t direction = doc_in["direction"];
        uint8_t value = lifts[lift_id - lift_begin][direction];
        hc595Write(value, doc_in["toggle"] == 1 ? HIGH : LOW);

        StaticJsonDocument<128> response;
        response["case"] = "lift_moved";
        response["lift_id"] = lift_id;
        response["direction"] = direction;
        response["toggle"] = doc_in["toggle"];
        sendMessage(response);
      }

      else if (caseType == "stop") {
        Serial.println("EMERGENCY STOP triggered");
        for (uint8_t i = 0; i < relais_count; i++) hc595Write(i, HIGH);
        StaticJsonDocument<128> response;
        response["case"] = "stop";
        response["status"] = "0";
        sendMessage(response);
      }

      else if (caseType == "info") {
        Serial.printf("Info: %s\n", payload);
      }

      else {
        Serial.printf("Unhandled case: %s\n", payload);
        StaticJsonDocument<128> errorDoc;
        errorDoc["case"] = "error";
        errorDoc["type"] = "Unhandled Event";
        errorDoc["error"] = (const char*)payload;
        sendMessage(errorDoc);
      }
      break;
    }

    case WStype_BIN:
      Serial.printf("Received binary data: %u bytes\n", length);
      break;

    default:
      break;
  }
}

// Setup
void setup() {
  pinMode(buttonPin, INPUT);
  pinMode(stcpPin, OUTPUT);
  pinMode(shcpPin, OUTPUT);
  pinMode(serPin, OUTPUT);
  pinMode(oePin, OUTPUT);
  digitalWrite(oePin, LOW);

  for (uint8_t i = 0; i < relais_count; i++) hc595Write(i, LOW);

  Serial.begin(115200);
  Serial.println("\nBooting...\n");

  if (!LittleFS.begin()) {
    Serial.println("LittleFS mount failed");
    return;
  }

  if (!loadConfig()) {
    Serial.println("Config load failed");
    return;
  }

  WiFi.hostname(con_id.c_str());
  WiFi.mode(WIFI_STA);
  WiFi.begin(SSID, PASSWORD);

  Serial.print("Connecting to WiFi");
  for (uint8_t i = 0; i < 100 && WiFi.status() != WL_CONNECTED; i++) {
    Serial.print(".");
    delay(200);
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi failed. Restarting...");
    delay(200);
    ESP.restart();
  }

  if (updateFirmware("https://" + SERVER + ":" + String(PORT) + "/update/" + con_id, client)) {
    Serial.println("Updated. Restarting...");
    delay(200);
    ESP.restart();
  }

  String uri = "/ws/" + con_id;
  webSocket.beginSslWithCA(SERVER.c_str(), PORT, uri.c_str(), serverCert);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
}

// Loop
void loop() {
  webSocket.loop();

  static uint8_t lastButtonState = HIGH;
  uint8_t buttonState = digitalRead(buttonPin);

  if (buttonState != lastButtonState) {
    if (buttonState == HIGH) {
      Serial.println("Test Error Triggered");
      StaticJsonDocument<128> errDoc;
      errDoc["case"] = "error";
      errDoc["type"] = "Test Error";
      errDoc["error"] = "Manual Trigger";
      sendMessage(errDoc);
    }
    delay(50);
  }

  lastButtonState = buttonState;
}
