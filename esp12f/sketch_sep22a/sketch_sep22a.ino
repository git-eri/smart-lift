const uint8_t buttonPin = 0; // a button 
const uint8_t stcpPin = 12;   // GPIO12 	74x595 RCLK/STCP
const uint8_t shcpPin = 13;   // GPIO13 	74x595 SRCLK/SHCP
const uint8_t serPin = 14;    // GPIO14 	74x595 SER/DS
const uint8_t oePin = 5;      // GPIO05 	74x595 OE/output enable active low

const uint8_t output[] {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}; // the used outputs, can also be used to change the order of the outputs
//const uint8_t output[] {0, 8, 7, 15};
int actual = -1;              // the actual output. -1 = all off

// generic shift out to two 74HC595 shift registers
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

// switch on next output
void next() {
  actual++;
  if (actual >= sizeof(output)) {
    actual = 0;      // wrap around
  }
  hc595Write(output[actual], HIGH);  // switch on new
  Serial.println(output[actual]);
}

void setup() {
  // put your setup code here, to run once:
  Serial.begin(74880);
  Serial.println("Hello, ESP32!");
  pinMode(buttonPin, INPUT);
  pinMode(stcpPin, OUTPUT);
  pinMode(shcpPin, OUTPUT);
  pinMode(serPin, OUTPUT);
  pinMode(oePin, OUTPUT);
  digitalWrite(oePin, LOW); // enable the output

  /*
    // only testing
    hc595Write(0, HIGH);  // single write
    delay(500);
    hc595Write(0, LOW);
    delay(500);
    hc595Write(8, HIGH);
    delay(500);
    hc595Write(0, LOW);
  */
} 

void loop() {
  /*
  //"state change detection" taken from the IDE example and modified for this sketch
  static int lastButtonState = HIGH;         // needs to be static as it must survive the local scope of loop
  // read the pushbutton input pin:
  int buttonState = digitalRead(buttonPin);  // a local variable is ok as we read in each iteration of loop
  // compare the buttonState to its previous state
  if (buttonState != lastButtonState) {
    // if the state has changed, increment the counter
    if (buttonState == HIGH) {
      // if the current state is HIGH then the button went from off to on:
      //Serial.println("on");
      next();
    } else {
      // if the current state is LOW then the button went from on to off:
      // switch off old
      hc595Write(output[actual], LOW);
    }
    // Delay a little bit to avoid bouncing
    delay(50);
  }
  // save the current state as the last state, for next time through the loop
  lastButtonState = buttonState;

  //delay(10);     // only for this simulator!!!
  */

  for (int i = 0; i <= 31; i++) {
    if (i < 16) {
      hc595Write(i, HIGH);
      delay(30);
    } else {
      hc595Write(i - 16, LOW);
      delay(30);
    }
    
  }
}