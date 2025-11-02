// Gets checked by server to determine if update is needed
#define VERSION "0.02.06"

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <WebSocketsClient.h>
#include <Hash.h>
#include <ArduinoJson.h>
#include <ESP8266httpUpdate.h>
#include <LittleFS.h>
#include <time.h>

// --- TLS/HTTP clients for OTA (BearSSL used only for ESPhttpUpdate) ---
BearSSL::WiFiClientSecure clientSecure;
WiFiClient clientPlain;

// --- Optional trust anchors for OTA only ---
BearSSL::X509List *serverCert = nullptr;   // from /server.crt (self-signed)
BearSSL::X509List *isrgRoot   = nullptr;   // from /isrg_root_x1.pem

WebSocketsClient webSocket;

// =================== Hardware pins ===================
const uint8_t powerSensePin = 4;  // D2
const uint8_t buttonPin     = 2;  // D4 (avoid GPIO0)
const uint8_t stcpPin       = 12; // D6 latch
const uint8_t shcpPin       = 13; // D7 clock
const uint8_t serPin        = 14; // D5 data
const uint8_t oePin         = 5;  // D1 output enable (LOW active)

// =================== Relay / Lift config ===================
const uint8_t relais_count = 16;
const uint8_t lift_count   = 5;
const uint8_t lifts[lift_count][3] = {
  {15,14,13}, {12,11,10}, {9,8,0}, {1,2,3}, {4,5,6}
};

// =================== Runtime configuration ===================
String con_id = "";
String SSID = "";
String PASSWORD = "";
String SERVER = "";
int    lift_begin = 0;
int    PORT = 0;
// Optional SHA1 fingerprint
String FINGERPRINT = "";
String WS_PATH = "/api/ws/";
String UPDATE_PATH = "/api/update/";

// =================== Power sensing ===================
const bool POWER_ACTIVE_LOW = true;
bool powerState = false;
unsigned long lastPowerCheck = 0;
const unsigned long powerPollInterval = 500;

// =================== Button debounce ===================
bool btnLastStable = HIGH;
bool btnReading    = HIGH;
unsigned long btnLastChangeMs = 0;
const unsigned long btnDebounceMs = 30;

// =================== TLS mode ===================
enum class TLSMode : uint8_t { PLAINTEXT = 0, PUBLIC_CA = 1, SELF_SIGNED = 2, INSECURE = 3 };
TLSMode TLS_MODE = TLSMode::PUBLIC_CA;

// =================== Shift register state ===================
static uint16_t hc595_state = 0;

// ---------- JSON send helper ----------
bool sendMessage(const JsonDocument& doc) {
  String json;
  serializeJson(doc, json);
  return webSocket.sendTXT(json);
}

// ---------- Hex helpers ----------
int hexNibble(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return 10 + (c - 'a');
  if (c >= 'A' && c <= 'F') return 10 + (c - 'A');
  return -1;
}

bool parseSha1Fingerprint(const String& in, uint8_t out[20]) {
  // Collect only hex digits
  String h; h.reserve(40);
  for (size_t i = 0; i < in.length(); i++) {
    char c = in[i];
    if ((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')) {
      h += c;
    }
  }
  if (h.length() != 40) return false;
  for (uint8_t i = 0; i < 20; i++) {
    int hi = hexNibble(h[i*2]);
    int lo = hexNibble(h[i*2+1]);
    if (hi < 0 || lo < 0) return false;
    out[i] = (uint8_t)((hi << 4) | lo);
  }
  return true;
}

// ---------- Load ISRG Root CA for OTA (optional) ----------
bool loadISRGFromFS() {
  if (isrgRoot) return true;
  File f = LittleFS.open("/isrg_root_x1.pem", "r");
  if (!f) return false;
  String pem = f.readString();
  f.close();
  isrgRoot = new BearSSL::X509List(pem.c_str());
  return true;
}

// ---------- Load config from LittleFS ----------
bool loadConfig() {
  if (!LittleFS.exists("/config.json")) return false;

  File f = LittleFS.open("/config.json", "r");
  DynamicJsonDocument doc(f.size() + 512);
  if (deserializeJson(doc, f)) { f.close(); return false; }
  f.close();

  con_id      = String(doc["con_id"]     | "");
  lift_begin  = doc["lift_begin"]        | 0;
  SSID        = String(doc["ssid"]       | "");
  PASSWORD    = String(doc["password"]   | "");
  SERVER      = String(doc["server"]     | "");
  PORT        = doc["port"]              | 0;
  WS_PATH     = String(doc["ws_path"]    | "/api/ws/");
  UPDATE_PATH = String(doc["update_path"]| "/api/update/");
  FINGERPRINT = String(doc["fingerprint"]| "");

  String tls = String(doc["tls_mode"] | "public_ca"); tls.toLowerCase();
  if      (tls == "plaintext")    TLS_MODE = TLSMode::PLAINTEXT;
  else if (tls == "self_signed")  TLS_MODE = TLSMode::SELF_SIGNED;
  else if (tls == "insecure")     TLS_MODE = TLSMode::INSECURE;
  else                            TLS_MODE = TLSMode::PUBLIC_CA;

  if (TLS_MODE == TLSMode::SELF_SIGNED) {
    File c = LittleFS.open("/server.crt", "r");
    if (!c) return false;
    String pem = c.readString(); c.close();
    serverCert = new BearSSL::X509List(pem.c_str());
  }
  if (TLS_MODE == TLSMode::PUBLIC_CA) loadISRGFromFS();

  return true;
}

// ---------- Set timezone + sync NTP ----------
time_t setClock() {
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  setenv("TZ", "CET-1CEST,M3.5.0/2,M10.5.0/3", 1); tzset();

  time_t now = time(nullptr);
  uint32_t ms = millis();
  while (now < 8 * 3600 * 2 && millis() - ms < 10000) { delay(250); now = time(nullptr); }
  return now;
}

// ---------- Read power input ----------
bool readPowerSense() {
  int raw = digitalRead(powerSensePin);
  return POWER_ACTIVE_LOW ? (raw == LOW) : (raw == HIGH);
}

// ---------- 74HC595 write ----------
void hc595Write(uint8_t pin, uint8_t val) {
  if (pin > 15) return;
  noInterrupts();
  if (val) hc595_state |=  (1 << pin);
  else     hc595_state &= ~(1 << pin);
  digitalWrite(stcpPin, LOW);
  shiftOut(serPin, shcpPin, MSBFIRST, hc595_state >> 8);
  shiftOut(serPin, shcpPin, MSBFIRST, hc595_state & 0xFF);
  digitalWrite(stcpPin, HIGH);
  interrupts();
}

// ---------- Relays to safe state ----------
void safeRelays() {
  for (uint8_t i = 0; i < relais_count; i++) hc595Write(i, LOW);
}

// ---------- OTA Firmware Update ----------
bool updateFirmware(String url) {
  Serial.println(String("[OTA] ") + url);

  // Safe outputs while updating
  digitalWrite(oePin, HIGH);
  safeRelays();

  t_httpUpdate_return ret;
  if (TLS_MODE == TLSMode::PLAINTEXT) {
    ret = ESPhttpUpdate.update(clientPlain, url, VERSION);
  } else {
    setClock();

    if      (TLS_MODE == TLSMode::INSECURE)    clientSecure.setInsecure();
    else if (TLS_MODE == TLSMode::SELF_SIGNED) clientSecure.setTrustAnchors(serverCert);
    else if (TLS_MODE == TLSMode::PUBLIC_CA)   clientSecure.setTrustAnchors(isrgRoot);

    if (FINGERPRINT.length()) clientSecure.setFingerprint(FINGERPRINT.c_str());

    ret = ESPhttpUpdate.update(clientSecure, url, VERSION);
  }

  if (ret == HTTP_UPDATE_OK) return true; // device will reboot
  digitalWrite(oePin, LOW);
  return false;
}

// ---------- WebSocket events ----------
void webSocketEvent(WStype_t type, uint8_t *payload, size_t len) {
  if (type == WStype_DISCONNECTED) {
    Serial.println("[WS] Lost connection. Outputs safe.");
    safeRelays();
    digitalWrite(oePin, HIGH);
  }

  if (type == WStype_CONNECTED) {
    Serial.println("[WS] Connected");
    digitalWrite(oePin, LOW);
    StaticJsonDocument<256> hello;
    hello["case"] = "hello";
    auto arr = hello.createNestedArray("lifts");
    for (int i=0;i<lift_count;i++) arr.add(lift_begin+i);
    hello["power_state"] = powerState ? 1 : 0;
    sendMessage(hello);
  }

  if (type == WStype_TEXT) {
    StaticJsonDocument<512> d;
    if (deserializeJson(d, payload, len)) return;
    String c = d["case"] | "";

    if (c == "move_lift") {
      int id = d["lift_id"], dir = d["direction"], t = d["toggle"];
      if (id<lift_begin || id>=lift_begin+lift_count || dir<0||dir>2 || (t!=0 && t!=1)) return;
      uint8_t r = lifts[id-lift_begin][dir];
      hc595Write(r, t==1);
      StaticJsonDocument<128> rj; rj["case"]="lift_moved"; rj["lift_id"]=id; rj["direction"]=dir; rj["toggle"]=t; sendMessage(rj);
    }

    if (c == "stop") {
      safeRelays(); digitalWrite(oePin, HIGH);
      StaticJsonDocument<64> rj; rj["case"]="stop"; rj["status"]="0"; sendMessage(rj);
    }
  }
}

// ---------- WiFi connect with scan + BSSID lock ----------
bool connectWiFiRobust(const char* ssid, const char* pass,
                       uint32_t totalTimeoutMs = 300000,
                       uint32_t attemptTimeoutMs = 30000)
{
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  WiFi.hostname(con_id.c_str());

  uint32_t start = millis();
  uint8_t attempt = 0;

  while (millis() - start < totalTimeoutMs) {
    attempt++;

    // Scan for target SSID and pick best BSSID/channel
    int n = WiFi.scanNetworks(false, true);
    int best = -1, bestRSSI = -127; uint8_t chan = 0;
    uint8_t bssid[6] = {0};

    for (int i=0; i<n; i++) {
      if (WiFi.SSID(i) == ssid) {
        int rssi = WiFi.RSSI(i);
        if (rssi > bestRSSI) { bestRSSI = rssi; best = i; }
      }
    }

    if (best >= 0) {
      const uint8_t* apBSSID = WiFi.BSSID(best); // pointer on ESP8266
      if (apBSSID) memcpy(bssid, apBSSID, 6);
      chan = WiFi.channel(best);

      Serial.printf("[WIFI] Try #%u -> '%s' RSSI %d dBm ch %u BSSID %02X:%02X:%02X:%02X:%02X:%02X\n",
                    attempt, ssid, bestRSSI, chan,
                    bssid[0],bssid[1],bssid[2],bssid[3],bssid[4],bssid[5]);

      WiFi.begin(ssid, pass, chan, bssid, true);
    } else {
      Serial.printf("[WIFI] Try #%u -> SSID '%s' not found. Generic connect.\n", attempt, ssid);
      WiFi.begin(ssid, pass);
    }

    // Wait for association + DHCP for attemptTimeoutMs
    uint32_t a = millis();
    while (millis() - a < attemptTimeoutMs) {
      if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("[WIFI] Connected. IP: %s RSSI: %d dBm\n",
                      WiFi.localIP().toString().c_str(), WiFi.RSSI());
        return true;
      }
      delay(250);
    }

    // Cycle WiFi stack before next try
    Serial.println("[WIFI] Attempt failed, cycling WiFi stack...");
    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    delay(300);
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    WiFi.setAutoReconnect(true);
  }
  return false;
}

// =================== SETUP ===================
void setup() {
  pinMode(powerSensePin, INPUT_PULLUP);
  pinMode(buttonPin, INPUT_PULLUP);
  pinMode(stcpPin, OUTPUT);
  pinMode(shcpPin, OUTPUT);
  pinMode(serPin, OUTPUT);
  pinMode(oePin, OUTPUT);

  // Start in safe state
  digitalWrite(oePin, HIGH);
  safeRelays();

  Serial.begin(115200);
  LittleFS.begin();
  if (!loadConfig()) return;

  if (!connectWiFiRobust(SSID.c_str(), PASSWORD.c_str())) return;

  setClock();

  // OTA first (safe outputs during update)
  String url = (TLS_MODE==TLSMode::PLAINTEXT?"http://":"https://") + SERVER + ":" + String(PORT) + UPDATE_PATH + con_id;
  if (updateFirmware(url)) { delay(300); ESP.restart(); }

  // Enable outputs after OTA (if no update)
  digitalWrite(oePin, LOW);

  // ---------- WebSocket setup (Links2004 API) ----------
  String uri = WS_PATH + con_id;

  if (TLS_MODE == TLSMode::PLAINTEXT) {
    // Plain ws://
    webSocket.begin(SERVER.c_str(), PORT, uri.c_str());
  } else {
    // Prepare optional SHA1 fingerprint as 20-byte array
    uint8_t fpBytes[20];
    bool haveFP = parseSha1Fingerprint(FINGERPRINT, fpBytes);

    if (TLS_MODE == TLSMode::INSECURE) {
      // Insecure WSS (no validation)
      webSocket.beginSSL(SERVER.c_str(), PORT, uri.c_str());
      Serial.println("[WS] WSS started (insecure, no fingerprint).");
    } else {
      // PUBLIC_CA or SELF_SIGNED → with this API, use fingerprint pinning if provided
      if (haveFP) {
        webSocket.beginSSL(SERVER.c_str(), PORT, uri.c_str(), fpBytes);
        Serial.println("[WS] WSS with SHA1 fingerprint pinning.");
      } else {
        // No fingerprint supplied → insecure WSS (no CA store supported here)
        webSocket.beginSSL(SERVER.c_str(), PORT, uri.c_str());
        Serial.println("[WS] WSS started WITHOUT fingerprint (no CA store supported by this API).");
      }
    }
  }

  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);

  powerState = readPowerSense();
}

// =================== LOOP ===================
void loop() {
  webSocket.loop();

  // Button debounce & error trigger
  int r = digitalRead(buttonPin);
  if (r != btnReading) { btnReading = r; btnLastChangeMs = millis(); }
  if ((millis() - btnLastChangeMs) > btnDebounceMs && btnReading != btnLastStable) {
    btnLastStable = btnReading;
    if (btnLastStable == LOW) {
      StaticJsonDocument<128> e;
      e["case"]="error"; e["type"]="Test Error"; e["error"]="Manual Trigger";
      sendMessage(e);
    }
  }

  // Power monitor
  if (millis() - lastPowerCheck > powerPollInterval) {
    lastPowerCheck = millis();
    bool np = readPowerSense();
    if (np != powerState) {
      powerState = np;
      StaticJsonDocument<64> d; d["case"] = "power_state"; d["state"] = powerState ? 1 : 0; sendMessage(d);
      Serial.printf("[PWR] Change: %s\n", powerState ? "ON" : "OFF");
    }
  }
}
