#include "settings.h"
#include <ArduinoWebsockets.h>
#include <ESP8266WiFi.h>
#include <ArduinoJson.h>

// A function that accepts arrays of any type T and any length N, 
// and returns the length N. 
template <class T, size_t N> constexpr size_t len(const T(&)[N]) { return N; }

const uint8_t buttonPin = 0; // a button 
const uint8_t stcpPin = 12;   // GPIO12 	74x595 RCLK/STCP
const uint8_t shcpPin = 13;   // GPIO13 	74x595 SRCLK/SHCP
const uint8_t serPin = 14;    // GPIO14 	74x595 SER/DS
const uint8_t oePin = 5;      // GPIO05 	74x595 OE/output enable active low
uint8_t active_net = 0;

using namespace websockets;
WebsocketsClient client;

void(* resetFunc) (void) = 0;

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

String getValue(String data, char separator, int index){
  int found = 0;
  int strIndex[] = {0, -1};
  int maxIndex = data.length()-1;
  for(int i=0; i<=maxIndex && found<=index; i++){
    if(data.charAt(i)==separator || i==maxIndex){
        found++;
        strIndex[0] = strIndex[1]+1;
        strIndex[1] = (i == maxIndex) ? i+1 : i;
    }
  }
  return found>index ? data.substring(strIndex[0], strIndex[1]) : "";
}

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println("I am active!");
  pinMode(buttonPin, INPUT);
  pinMode(stcpPin, OUTPUT);
  pinMode(shcpPin, OUTPUT);
  pinMode(serPin, OUTPUT);
  pinMode(oePin, OUTPUT);
  digitalWrite(oePin, LOW); // enable the output

  // Disable all relais on start
  for (uint8_t i = 0; i < 16; i++) {
    hc595Write(i, LOW);
  }

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

  // Search for known networks
  int numberOfNetworks = WiFi.scanNetworks();
  for (size_t j = 0; j < len(networks); ++j) {
    for(int i =0; i < numberOfNetworks; i++){
      if (networks[j][0] == WiFi.SSID(i)) {
        Serial.println("Connecting to Network: " + networks[j][0]);
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
      Serial.print(".");
      delay(200);
  }
  Serial.println("");
  // Check if connected to wifi
  if(WiFi.status() != WL_CONNECTED) {
      Serial.println("No Network found!");
      delay(200);
      void(* resetFunc) (void) = 0;
      //return;
  }
  Serial.println("Connected to Wifi, Connecting to server...");
  // Try to connect to Websockets server
  bool connected = client.connect(networks[active_net][2], networks[active_net][3].toInt(), "/ws/" + con_id);
  if(connected) {
    Serial.println("Connecetd to Server: " + networks[active_net][2] + ":" + networks[active_net][3]);
  } else {
    Serial.println("Could not connect to " + networks[active_net][2]);
  }
  // Run callback when messages are received
  client.onMessage([&](WebsocketsMessage message) {
    StaticJsonDocument<1024> doc_in;
    DeserializationError error = deserializeJson(doc_in, message.data());
    if (error) {
      Serial.print(F("deserialize incoming message failed: "));
      Serial.println(error.f_str());
      return;
    }
    String message_in = doc_in["message"];
    //Serial.println(message.data());
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
        client.send(doc_out_str);
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
        client.send(doc_out_str);
        return;
      }
      else {
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
        client.send(doc_out_str);
        return;
      }
    }
    else if (message_in == "stop") {
      // Handle Emergency Stop
      Serial.println("EMERGENCY STOP");
      for (uint8_t i = 0; i < 16; i++) {
        hc595Write(i, LOW);
      }
      StaticJsonDocument<128> doc_out;
      doc_out["message"] = "stop";
      doc_out["status"] = "0";
      String doc_out_str;
      serializeJson(doc_out, doc_out_str);
      client.send(doc_out_str);
      return;
    }
    else if (message_in == "info") {
      // Handle messages from server
      Serial.println("Message: " + message.data());
      return;
    }
    else {
      // Handle other bullshit that happens
      Serial.println("Unhandled Event: " + message.data());
      StaticJsonDocument<128> doc_out;
      doc_out["message"] = "error";
      doc_out["type"] = "Unhandled Event";
      doc_out["error"] = message.data();
      String doc_out_str;
      serializeJson(doc_out, doc_out_str);
      client.send(doc_out_str);
      return;
    }
  });

  client.send(about_me_str);
}

void loop() {
  if(client.available()) {
    client.poll();
    static int lastButtonState = HIGH;
    int buttonState = digitalRead(buttonPin);
    if (digitalRead(buttonPin) != lastButtonState) {
      if (buttonState == HIGH) {
        Serial.println("Test Error");
        StaticJsonDocument<128> doc_out;
        doc_out["message"] = "error";
        doc_out["type"] = "Test Error";
        doc_out["error"] = "Joke";
        String doc_out_str;
        serializeJson(doc_out, doc_out_str);
        client.send(doc_out_str);
      }
      delay(50);
    }
    lastButtonState = buttonState;
  }
  else {
    for (uint8_t i = 0; i < 16; i++) {
      hc595Write(i, LOW);
    }
    if(WiFi.status() != WL_CONNECTED) {
      Serial.println("Wifi got disconnected!");
    } else {
      Serial.println("Server not available! Retrying now...");
    }
    delay(200);
    resetFunc();
  }
}