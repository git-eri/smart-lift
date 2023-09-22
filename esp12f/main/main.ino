#include "functions.h"

const char* ssid = "FRITZ!Box 7590 AX"; //Enter SSID
const char* password = "4Infu.wk"; //Enter Password
const char* websockets_server_host = "192.168.178.63"; //Enter server adress
const uint16_t websockets_server_port = 8000; // Enter server port

using namespace websockets;

WebsocketsClient client;

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
  bool connected = client.connect(websockets_server_host, websockets_server_port, "/ws/c0001");
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
      for (int i = 0; i <= 31; i++) {
        if (i < 16) {
          hc595Write(i, HIGH);
          delay(30);
        } else {
          hc595Write(i - 16, LOW);
          delay(30);
        }  
      }
  });
} 

void loop() {
  if(client.available()) {
        client.poll();
    }
}