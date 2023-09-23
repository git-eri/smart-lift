#include "functions.h"

const char* ssid = "FRITZ!Box 7590 AX"; //Enter SSID
const char* password = "4Infu.wk"; //Enter Password
const char* websockets_server_host = "192.168.178.63"; //Enter server adress
const uint16_t websockets_server_port = 8000; // Enter server port

using namespace websockets;

WebsocketsClient client;

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
  // put your setup code here, to run once:
  Serial.begin(115200);
  Serial.println("I am active!");
  pinMode(buttonPin, INPUT);
  pinMode(stcpPin, OUTPUT);
  pinMode(shcpPin, OUTPUT);
  pinMode(serPin, OUTPUT);
  pinMode(oePin, OUTPUT);
  digitalWrite(oePin, LOW); // enable the output

  WiFi.begin(ssid, password);
  // Wait some time to connect to wifi
  for(int i = 0; i < 10 && WiFi.status() != WL_CONNECTED; i++) {
      Serial.print(".");
      delay(1000);
  }
  // Check if connected to wifi
  if(WiFi.status() != WL_CONNECTED) {
      Serial.println("No Wifi!");
      return;
  }
  Serial.println("Connected to Wifi, Connecting to server...");
  // try to connect to Websockets server
  bool connected = client.connect(websockets_server_host, websockets_server_port, "/ws/c00001");
  if(connected) {
      Serial.println("Connecetd!");
      client.send("Hello Server");
  } else {
      Serial.println("Not Connected!");
  }
  // run callback when messages are received

  client.onMessage([&](WebsocketsMessage message) {
      Serial.print("Got Message: ");
      Serial.println(message.data());
      String msg_type = getValue(message.data(), ';', 0);
      String client_id = getValue(message.data(), ';', 1);
      String info = getValue(message.data(), ';', 2);
      String lift_id = getValue(message.data(), ';', 3);
      String action = getValue(message.data(), ';', 4);

      if (info == "lift") {
        Serial.println("Lift" + lift_id);
        hc595Write(lift_id.toInt(), HIGH);
      }
  });
  client.send("hello;ESP_c00001;example_ip;[{'id': '0', 'name': 'Lift 1', 'controller': 'c00001'},{'id': '1', 'name': 'Lift 2', 'controller': 'c00001'},{'id': '2', 'name': 'Lift 3', 'controller': 'c00001'},{'id': '3', 'name': 'Lift 4', 'controller': 'c00001'},{'id': '4', 'name': 'Lift 5', 'controller': 'c00001'}]");
}

void loop() {
  if(client.available()) {
        client.poll();
    }
}