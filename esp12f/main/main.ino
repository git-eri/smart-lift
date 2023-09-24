#include "settings.h"
#include <ArduinoWebsockets.h>
#include <ESP8266WiFi.h>

const uint8_t buttonPin = 0; // a button 
const uint8_t stcpPin = 12;   // GPIO12 	74x595 RCLK/STCP
const uint8_t shcpPin = 13;   // GPIO13 	74x595 SRCLK/SHCP
const uint8_t serPin = 14;    // GPIO14 	74x595 SER/DS
const uint8_t oePin = 5;      // GPIO05 	74x595 OE/output enable active low
//int actual = -1;

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
  String about_me = "[";
  for (uint8_t i = lift_begin; i < lift_begin + lift_count; i++) {
    for (uint8_t j = 0; j < 3; j++) {
      //Serial.println("Lift " + lifts[i][j]);
      uint8_t number = i + 1;
      about_me.concat("{'id': '"+ String(i) +"', 'name': 'Lift " + number +"', 'controller': '"+ con_id +"'},");
    }
  }
  about_me.concat("]");  

  // Connect to wifi
  WiFi.begin(ssid, password);
  // Wait some time to connect to wifi
  for(uint8_t i = 0; i < 10 && WiFi.status() != WL_CONNECTED; i++) {
      Serial.print(".");
      delay(1000);
  }
  // Check if connected to wifi
  if(WiFi.status() != WL_CONNECTED) {
      Serial.println("No Wifi!");
      return;
  }
  Serial.println("Connected to Wifi, Connecting to server...");
  // Try to connect to Websockets server
  bool connected = client.connect(websockets_server_host, websockets_server_port, "/ws/" + con_id);
  if(connected) {
      Serial.println("Connecetd to Server!");
  } else {
      Serial.println("Not Connected!");
  }
  // Run callback when messages are received
  client.onMessage([&](WebsocketsMessage message) {
    Serial.println(message.data());
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
      } else if (on_off == "off") {
        uint8_t value = lifts[lift_id.toInt() - lift_begin][action.toInt()];
        hc595Write(value, LOW);
        client.send("moved_lift;" + lift_id +";"+ action +";"+ on_off + ";0");
      }
      else {
        client.send("moved_lift;" + lift_id +";"+ action +";"+ on_off + ";1");
        return;
      }
    }
    else if (msg_type == "stop") {
      // Handle Emergency Stop
      for (uint8_t i = 0; i < 16; i++) {
        hc595Write(i, LOW);
      }
      Serial.println("EMERGENCY STOP");
      client.send("stop;ok");
    }
    else if (msg_type == "msg") {
      // Handle messages from server
      return;
    }
    else {
      // Handle other bullshit that happens
      Serial.println("Unhandled Event: " + message.data());
      client.send("error;Unhandled Event;" + message.data());
    }
  });

  client.send("hello;" + about_me);
}

void loop() {
  if(client.available()) {
    client.poll();
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