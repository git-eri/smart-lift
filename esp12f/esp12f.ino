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
  for(int i =0; i < numberOfNetworks; i++){
    for (size_t j = 0; j < len(networks); ++j) {
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
  for(uint8_t i = 0; i < 10 && WiFi.status() != WL_CONNECTED; i++) {
      Serial.print(".");
      delay(500);
  }
  Serial.println("");
  // Check if connected to wifi
  if(WiFi.status() != WL_CONNECTED) {
      Serial.println("No Network found!");
      delay(500);
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
    //Serial.println(message.data());
    String msg_type = getValue(message.data(), ';', 0);
    if (msg_type == "lift") {
      // Handle lift actions
      String lift_id = getValue(message.data(), ';', 1);
      String action = getValue(message.data(), ';', 2);
      String on_off = getValue(message.data(), ';', 3);
      if (on_off == "on") {
        uint8_t value = lifts[lift_id.toInt() - lift_begin][action.toInt()];
        hc595Write(value, HIGH);
        client.send("moved_lift;" + lift_id +";"+ action +";"+ on_off + ";0");
        return;
      } else if (on_off == "off") {
        uint8_t value = lifts[lift_id.toInt() - lift_begin][action.toInt()];
        hc595Write(value, LOW);
        client.send("moved_lift;" + lift_id +";"+ action +";"+ on_off + ";0");
        return;
      }
      else {
        client.send("moved_lift;" + lift_id +";"+ action +";"+ on_off + ";1");
        return;
      }
    }
    else if (msg_type == "stop") {
      // Handle Emergency Stop
      Serial.println("EMERGENCY STOP");
      for (uint8_t i = 0; i < 16; i++) {
        hc595Write(i, LOW);
      }
      client.send("stop;ok");
      return;
    }
    else if (msg_type == "msg") {
      // Handle messages from server
      Serial.println("Message: " + message.data());
      return;
    }
    else {
      // Handle other bullshit that happens
      Serial.println("Unhandled Event: " + message.data());
      client.send("error;Unhandled Event;" + message.data());
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
        client.send("error;Test Error");
        Serial.println("Test Error");
      }
      delay(50);
    }
    lastButtonState = buttonState;
  }
  else {
    for (uint8_t i = 0; i < 16; i++) {
      hc595Write(i, LOW);
    }
    Serial.println("Server not available! Retrying now...");
    delay(500);
    resetFunc();
  }
}