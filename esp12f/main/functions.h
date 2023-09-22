const uint8_t buttonPin = 0; // a button 
const uint8_t stcpPin = 12;   // GPIO12 	74x595 RCLK/STCP
const uint8_t shcpPin = 13;   // GPIO13 	74x595 SRCLK/SHCP
const uint8_t serPin = 14;    // GPIO14 	74x595 SER/DS
const uint8_t oePin = 5;      // GPIO05 	74x595 OE/output enable active low

const uint8_t output[] {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}; // the used outputs, can also be used to change the order of the outputs
//const uint8_t output[] {0, 8, 7, 15};
int actual = -1;

#include "functions.cpp"
#include <ArduinoWebsockets.h>
#include <ESP8266WiFi.h>