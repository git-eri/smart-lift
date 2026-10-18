// Gets checked by the server to determine if an update is needed.
#define VERSION "0.06.03"
// Compile every translation unit with -DWEBSOCKETS_TCP_TIMEOUT=100 (see init.sh).

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <ESP8266httpUpdate.h>
#include <LittleFS.h>
#include <time.h>
#include "RelayLeases.h"

// ArduinoJson 6 uses fixed message buffers; version 7 manages its own capacity.
// Keep both public APIs supported without relying on deprecated version-7 aliases.
#if ARDUINOJSON_VERSION_MAJOR >= 7
template <size_t Capacity> using MessageDocument = JsonDocument;
#else
template <size_t Capacity> using MessageDocument = StaticJsonDocument<Capacity>;
#endif

constexpr uint8_t protocolVersion = 2;
const uint8_t powerSensePin = 4;  // D2: indication only, not a hardware interlock
const uint8_t buttonPin = 2;     // D4: test/error button, not an emergency switch
const uint8_t stcpPin = 12;      // D6 latch
const uint8_t shcpPin = 13;      // D7 clock
const uint8_t serPin = 14;       // D5 data
const uint8_t oePin = 5;         // D1 output enable (LOW active)
const uint8_t lift_count = RelayLeases::count;
const uint8_t lifts[lift_count][3] = {
  {15,14,13}, {12,11,10}, {9,8,0}, {1,2,3}, {4,5,6}
};

// Use the public API: protected disconnect overloads differ across library versions.
WebSocketsClient webSocket;
bool webSocketConnected = false;
RelayLeases relays;
BearSSL::WiFiClientSecure clientSecure;
WiFiClient clientPlain;
// These objects outlive both the OTA client and every WebSocket reconnection.
BearSSL::X509List* trustAnchors = nullptr;
uint8_t fingerprintBytes[20] = {};
bool haveFingerprint = false;
enum class TLSMode : uint8_t { PLAINTEXT, PUBLIC_CA, SELF_SIGNED };
TLSMode tlsMode = TLSMode::PUBLIC_CA;

String con_id, ssid, password, server, controllerToken, extraHeaders;
String wsPath = "/api/ws/", updatePath = "/api/update/", ntpServer = "pool.ntp.org";
int lift_begin = 0;
uint16_t port = 0;
bool configReady = false, webSocketStarted = false, otaChecked = false;
bool wasWifiConnected = false, clockStarted = false;
uint32_t lastWifiAttempt = 0, lastStatusLog = 0;
const uint32_t wifiRetryMs = 30000;

const bool POWER_ACTIVE_LOW = true;
bool powerState = false;
uint32_t lastPowerCheck = 0;
bool btnLastStable = HIGH, btnReading = HIGH;
uint32_t btnLastChangeMs = 0;

bool sendMessage(const JsonDocument& doc) {
  String json;
  serializeJson(doc, json);
  return webSocket.sendTXT(json);
}

void sendError(const char* detail, const char* commandId = nullptr) {
  Serial.printf("[CONTROL] %s\n", detail);
  MessageDocument<320> doc;
  doc["case"] = "error";
  doc["detail"] = detail;
  if (commandId) doc["command_id"] = commandId;
  sendMessage(doc);
}

void sendMoved(int id, const RelayLeases::Lease& lease, uint8_t toggle) {
  MessageDocument<256> doc;
  doc["case"] = "lift_moved";
  doc["lift_id"] = id;
  doc["direction"] = lease.direction;
  doc["toggle"] = toggle;
  doc["command_id"] = lease.commandId;
  sendMessage(doc);
}

void sendStopState(const char* resetId = nullptr) {
  MessageDocument<192> doc;
  doc["case"] = "stop_state";
  doc["stopped"] = relays.stopped();
  if (resetId) doc["reset_id"] = resetId;
  sendMessage(doc);
}

void sendPowerState() {
  MessageDocument<96> doc;
  doc["case"] = "power_state";
  doc["state"] = powerState ? 1 : 0;
  sendMessage(doc);
}

// Latch an entire 16-bit state once; never expose intermediate relay patterns.
void writeRelays(uint16_t state) {
  noInterrupts();
  digitalWrite(stcpPin, LOW);
  shiftOut(serPin, shcpPin, MSBFIRST, state >> 8);
  shiftOut(serPin, shcpPin, MSBFIRST, state & 0xff);
  digitalWrite(stcpPin, HIGH);
  interrupts();
}

void disableOutputs() {
  digitalWrite(oePin, HIGH);  // Remove output enable before changing any state.
  writeRelays(0);
}

// Transport loss removes session approval, never the operator's STOP latch.
void clearControllerSession() {
  disableOutputs();
  relays.disconnect();
}

void applyRelays() {
  uint16_t bitmap = 0;
  if (relays.ready() && !relays.stopped()) {
    for (uint8_t i = 0; i < lift_count; ++i) {
      const auto& lease = relays.at(i);
      if (lease.active) bitmap |= static_cast<uint16_t>(1U << lifts[i][lease.direction]);
    }
  }
  // A session/reset does not energize outputs: only accepted live leases do.
  if (!bitmap) digitalWrite(oePin, HIGH);
  writeRelays(bitmap);
  if (bitmap) digitalWrite(oePin, LOW);
}

void expireLeases() {
  const uint32_t now = millis();
  uint8_t expiredMask = 0;
  for (uint8_t i = 0; i < lift_count; ++i) {
    if (relays.expired(i, now)) {
      relays.expire(i);
      expiredMask |= (1U << i);
    }
  }
  if (!expiredMask) return;
  applyRelays();  // Switch off before sending potentially blocking acknowledgements.
  for (uint8_t i = 0; i < lift_count; ++i) {
    // A failed send can synchronously disconnect and clear all lease records.
    if (!relays.ready()) break;
    if (expiredMask & (1U << i)) sendMoved(lift_begin + i, relays.at(i), 0);
  }
}

int hexNibble(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

bool parseFingerprint(const String& value) {
  String hex;
  for (size_t i = 0; i < value.length(); ++i) {
    const char c = value[i];
    if (hexNibble(c) >= 0) hex += c;
    else if (c != ':' && c != ' ') return false;
  }
  if (hex.length() != 40) return false;
  for (uint8_t i = 0; i < 20; ++i)
    fingerprintBytes[i] = (hexNibble(hex[2*i]) << 4) | hexNibble(hex[2*i+1]);
  return true;
}

bool configError(const char* message) {
  Serial.printf("[CFG] ERROR: %s. Outputs remain disabled.\n", message);
  return false;
}

bool validId(const String& value) {
  if (value.length() < 4 || value.length() > 64 || !value.startsWith("con")) return false;
  for (size_t i = 0; i < value.length(); ++i) {
    const char c = value[i];
    if (!isalnum(static_cast<unsigned char>(c)) && c != '-' && c != '_') return false;
  }
  return true;
}

bool validHost(const String& value) {
  if (!value.length() || value.length() > 253 || value[0] == '.' || value.endsWith(".")) return false;
  for (size_t i = 0; i < value.length(); ++i) {
    const char c = value[i];
    if (!isalnum(static_cast<unsigned char>(c)) && c != '-' && c != '.') return false;
  }
  return value.indexOf("..") < 0;
}

bool validPrefix(const String& value) {
  if (!value.startsWith("/") || !value.endsWith("/") || value.length() > 128 ||
      value.indexOf("..") >= 0 || value.indexOf("//") >= 0) return false;
  for (size_t i = 0; i < value.length(); ++i) {
    const char c = value[i];
    if (!isalnum(static_cast<unsigned char>(c)) && c != '/' && c != '-' && c != '_') return false;
  }
  return true;
}

bool loadTrustAnchors(const char* path) {
  File cert = LittleFS.open(path, "r");
  if (!cert || !cert.size() || cert.size() > 8192) return configError("CA file missing or oversized");
  const String pem = cert.readString();
  cert.close();
  trustAnchors = new BearSSL::X509List();
  if (!trustAnchors || !trustAnchors->append(pem.c_str()) || !trustAnchors->getCount()) {
    delete trustAnchors;
    trustAnchors = nullptr;
    return configError("CA file is not a valid certificate");
  }
  return true;
}

bool isJsonText(JsonVariantConst field) {
  if (!field.is<const char*>()) return false;
  const JsonString value = field.as<JsonString>();
  return ProtocolText::isText(value.c_str(), value.size());
}

bool loadConfig() {
  File config = LittleFS.open("/config.json", "r");
  if (!config || !config.size() || config.size() > 4096) return configError("config.json missing or oversized");
#if ARDUINOJSON_VERSION_MAJOR >= 7
  JsonDocument doc;
#else
  DynamicJsonDocument doc(6144);
#endif
  const auto error = deserializeJson(doc, config);
  config.close();
  if (error || !doc.is<JsonObject>()) return configError("invalid config.json");
  if (!isJsonText(doc["con_id"]) || !doc["lift_begin"].is<int>() ||
      !isJsonText(doc["ssid"]) || !isJsonText(doc["password"]) ||
      !isJsonText(doc["server"]) || !doc["port"].is<int>())
    return configError("required field missing or wrong type");
  const char* optionalStrings[] = {"ws_path", "update_path", "tls_mode", "fingerprint", "controller_token", "ntp_server"};
  for (const char* key : optionalStrings) {
    if (!doc[key].isUnbound() && !isJsonText(doc[key])) return configError("optional string field is invalid");
  }
  con_id = doc["con_id"].as<String>();
  lift_begin = doc["lift_begin"].as<int>();
  ssid = doc["ssid"].as<String>();
  password = doc["password"].as<String>();
  server = doc["server"].as<String>();
  const int configuredPort = doc["port"].as<int>();
  wsPath = doc["ws_path"] | "/api/ws/";
  updatePath = doc["update_path"] | "/api/update/";
  controllerToken = doc["controller_token"] | "";
  ntpServer = doc["ntp_server"] | "pool.ntp.org";
  if (!validId(con_id)) return configError("invalid controller ID");
  if (lift_begin < 0 || lift_begin > 999996) return configError("lift range must fit IDs 0..1000000");
  if (!ssid.length() || ssid.length() > 32 || password.length() > 64) return configError("invalid WiFi configuration");
  if (!validHost(server) || !validHost(ntpServer)) return configError("server/NTP must be a hostname or IPv4 address");
  if (configuredPort < 1 || configuredPort > 65535) return configError("port must be 1..65535");
  port = static_cast<uint16_t>(configuredPort);
  if (!validPrefix(wsPath) || !validPrefix(updatePath)) return configError("path prefixes must start/end with slash and contain safe path characters");
  if (controllerToken.length() > 256) return configError("controller token is too long");
  for (size_t i = 0; i < controllerToken.length(); ++i) {
    if (controllerToken[i] < 33 || controllerToken[i] > 126) return configError("invalid character in controller token");
  }
  const String mode = doc["tls_mode"] | "public_ca";
  if (mode == "plaintext") tlsMode = TLSMode::PLAINTEXT;
  else if (mode == "public_ca") tlsMode = TLSMode::PUBLIC_CA;
  else if (mode == "self_signed") tlsMode = TLSMode::SELF_SIGNED;
  else return configError("tls_mode must be plaintext, public_ca or self_signed");
  const String fingerprint = doc["fingerprint"] | "";
  if (fingerprint.length()) {
    if (tlsMode == TLSMode::PLAINTEXT || !parseFingerprint(fingerprint)) return configError("invalid TLS fingerprint");
    haveFingerprint = true;
  }
  if (tlsMode != TLSMode::PLAINTEXT &&
      !loadTrustAnchors(tlsMode == TLSMode::SELF_SIGNED ? "/server.crt" : "/isrg_root_x1.pem")) return false;
  if (controllerToken.length()) extraHeaders = "X-Controller-Token: " + controllerToken + "\r\n";
  Serial.printf("[CFG] Validated configuration; TLS mode: %s\n", mode.c_str());
  return true;
}

bool readPowerSense() {
  const int raw = digitalRead(powerSensePin);
  return POWER_ACTIVE_LOW ? raw == LOW : raw == HIGH;
}

// Only called before a WebSocket session can accept movements. Never re-enable OE here.
void checkFirmwareUpdate() {
  disableOutputs();
  const String url = String(tlsMode == TLSMode::PLAINTEXT ? "http://" : "https://") +
                     server + ":" + String(port) + updatePath + con_id;
  HTTPClient http;
  bool began;
  if (tlsMode == TLSMode::PLAINTEXT) {
    began = http.begin(clientPlain, url);
  } else {
    if (haveFingerprint) clientSecure.setFingerprint(fingerprintBytes);
    else clientSecure.setTrustAnchors(trustAnchors);
    began = http.begin(clientSecure, url);
  }
  if (!began) { Serial.println("[OTA] HTTP initialization failed."); return; }
  http.setTimeout(3000);
  if (controllerToken.length()) http.addHeader("X-Controller-Token", controllerToken);
  ESPhttpUpdate.setClientTimeout(3000);
  const t_httpUpdate_return result = ESPhttpUpdate.update(http, VERSION);
  http.end();
  if (result == HTTP_UPDATE_FAILED) Serial.printf("[OTA] Update check failed (code %d).\n", ESPhttpUpdate.getLastError());
  else if (result == HTTP_UPDATE_NO_UPDATES) Serial.println("[OTA] Firmware is current.");
  else { delay(100); ESP.restart(); }
}

bool validCorrelationId(JsonVariantConst field) {
  if (!field.is<const char*>()) return false;
  const JsonString value = field.as<JsonString>();
  return ProtocolText::isIdentifier(value.c_str(), value.size());
}

void handleResetStop(JsonObjectConst doc) {
  if (!validCorrelationId(doc["reset_id"])) { sendError("invalid reset ID"); return; }
  const char* resetId = doc["reset_id"].as<const char*>();
  const auto result = relays.resetStop(resetId);
  if (result == RelayLeases::ResetResult::Accepted) {
    // STOP already had OE disabled; accepting reset clears state but never enables it.
    disableOutputs();
    sendStopState(resetId);
  } else if (result == RelayLeases::ResetResult::Duplicate) {
    // A retransmitted acknowledgement request must not interrupt a later press.
    sendStopState(resetId);
  } else if (result == RelayLeases::ResetResult::NotReady) {
    sendError("controller session is not ready");
  } else if (result == RelayLeases::ResetResult::Stale) {
    sendError("reset ID already used before STOP; request a fresh reset");
  } else {
    sendError("STOP is not latched; reset rejected");
  }
}

void handleMoveLift(JsonObjectConst doc) {
  const char* commandId = validCorrelationId(doc["command_id"]) ? doc["command_id"].as<const char*>() : nullptr;
  if (!doc["lift_id"].is<int>() || !doc["direction"].is<int>() || !doc["toggle"].is<int>() ||
      !commandId) { sendError("invalid move field types", commandId); return; }
  const int id = doc["lift_id"].as<int>(), direction = doc["direction"].as<int>(), toggle = doc["toggle"].as<int>();
  if (id < lift_begin || id >= lift_begin + lift_count || direction < 0 || direction > 2 ||
      (toggle != 0 && toggle != 1) || (toggle == 1 && !doc["renew"].is<bool>()) ||
      (!doc["renew"].isUnbound() && !doc["renew"].is<bool>())) { sendError("invalid move fields", commandId); return; }
  const uint8_t index = id - lift_begin;
  const uint32_t commandTime = millis();
  const bool expiredDuringParsing = relays.expired(index, commandTime);
  const RelayLeases::Lease previous = relays.at(index);
  const auto result = relays.execute(index, direction, toggle, commandId, doc["renew"] | false, commandTime);
  applyRelays();
  // execute() also checks the deadline, including a deadline crossed while parsing.
  if (expiredDuringParsing) sendMoved(id, previous, 0);
  switch (result) {
    case RelayLeases::Result::Accepted: sendMoved(id, relays.at(index), toggle); break;
    case RelayLeases::Result::NotReady: sendError("controller session is not ready", commandId); break;
    case RelayLeases::Result::Stopped: sendError("stop is latched; explicit reset required", commandId); break;
    case RelayLeases::Result::Conflict: sendError("lift already has an active command", commandId); break;
    case RelayLeases::Result::Stale: sendError("stale or expired command", commandId); break;
    default: sendError("invalid command", commandId); break;
  }
}

void webSocketEvent(WStype_t type, uint8_t* payload, size_t len) {
  if (type == WStype_DISCONNECTED) {
    clearControllerSession();
    Serial.println(webSocketConnected
      ? "[WS] Connection lost; outputs disabled, stop latch preserved."
      : "[WS] Connection attempt failed; check server address, port and backend logs. Outputs disabled.");
    webSocketConnected = false;
    return;
  }
  if (type == WStype_ERROR) {
    clearControllerSession();
    // Do not log untrusted payloads or HTTP headers, which can contain credentials.
    Serial.printf("[WS] Protocol error event (%u bytes); disconnecting with outputs disabled.\n", static_cast<unsigned>(len));
    webSocket.disconnect();
    return;
  }
  if (type == WStype_CONNECTED) {
    webSocketConnected = true;
    clearControllerSession();
    MessageDocument<384> hello;
    hello["case"] = "hello";
    hello["protocol_version"] = protocolVersion;
    hello["stop_latched"] = relays.stopped();
    auto ids = hello["lifts"].to<JsonArray>();
    for (uint8_t i = 0; i < lift_count; ++i) ids.add(lift_begin + i);
    hello["power_state"] = powerState ? 1 : 0;
    hello["version"] = VERSION;
    hello["ip"] = WiFi.localIP().toString();
    hello["rssi"] = WiFi.RSSI();
    sendMessage(hello);
    Serial.println("[WS] Connected; awaiting protocol/session approval.");
    return;
  }
  if (type != WStype_TEXT) return;
  expireLeases();
  if (len > 768) { sendError("message too large"); return; }
  MessageDocument<768> doc;
  if (deserializeJson(doc, payload, len) || !doc.is<JsonObject>() || !isJsonText(doc["case"])) {
    sendError("invalid JSON message"); return;
  }
  // The document owns this text until the callback returns; no String allocation needed.
  const char* command = doc["case"].as<const char*>();
  if (strcmp(command, "stop") == 0) {
    disableOutputs();
    relays.stop();
    sendStopState();
    return;
  }
  if (strcmp(command, "controller_ready") == 0) {
    if (!doc["protocol_version"].is<int>() || doc["protocol_version"].as<int>() != protocolVersion) {
      clearControllerSession(); sendError("incompatible protocol version"); return;
    }
    if (!relays.ready()) {
      disableOutputs();
      relays.acceptSession();
      // Resynchronize indication changes between hello and session acceptance.
      powerState = readPowerSense();
      sendPowerState();
    }
    return;
  }
  if (strcmp(command, "reset_stop") == 0) {
    handleResetStop(doc.as<JsonObjectConst>());
    return;
  }
  if (strcmp(command, "move_lift") == 0) handleMoveLift(doc.as<JsonObjectConst>());
  else sendError("unknown command");
}

void startWebSocket() {
  const String uri = wsPath + con_id;
  if (tlsMode == TLSMode::PLAINTEXT) webSocket.begin(server.c_str(), port, uri.c_str(), "");
  else if (haveFingerprint) webSocket.beginSSL(server.c_str(), port, uri.c_str(), fingerprintBytes, "");
  else webSocket.beginSslWithCA(server.c_str(), port, uri.c_str(), trustAnchors, "");
  // Replace the browser-like default Origin: file:// even when no token is configured.
  webSocket.setExtraHeaders(extraHeaders.c_str());
  Serial.printf("[WS] Target: %s://%s:%u%s; controller token: %s\n",
                tlsMode == TLSMode::PLAINTEXT ? "ws" : "wss", server.c_str(), port,
                uri.c_str(), controllerToken.length() ? "configured" : "not configured");
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  webSocket.enableHeartbeat(1000, 1000, 2);
  webSocketStarted = true;
}

void beginWifiAttempt() {
  lastWifiAttempt = millis();
  WiFi.begin(ssid.c_str(), password.c_str());
  Serial.println("[WIFI] Starting nonblocking connection attempt.");
}

void serviceNetwork() {
  if (WiFi.status() != WL_CONNECTED) {
    if (wasWifiConnected) {
      clearControllerSession();
      if (webSocketStarted) webSocket.disconnect();
      wasWifiConnected = false;
      Serial.println("[WIFI] Connection lost; outputs disabled.");
    }
    if (static_cast<uint32_t>(millis() - lastWifiAttempt) >= wifiRetryMs) beginWifiAttempt();
    return;
  }
  if (!wasWifiConnected) {
    wasWifiConnected = true;
    Serial.println("[WIFI] Connected.");
  }
  if (!clockStarted) {
    configTime(0, 0, ntpServer.c_str());
    clockStarted = true;
  }
  // CA validation needs a credible clock. Wait without blocking inputs/retry handling.
  if (tlsMode != TLSMode::PLAINTEXT && !haveFingerprint && time(nullptr) < 1700000000) {
    if (static_cast<uint32_t>(millis() - lastStatusLog) >= 10000) {
      lastStatusLog = millis();
      Serial.println("[TLS] Waiting for NTP time; outputs remain disabled.");
    }
    return;
  }
  if (!otaChecked) { otaChecked = true; checkFirmwareUpdate(); }
  if (!webSocketStarted) startWebSocket();
  // No active relay may survive a potentially blocking reconnection attempt.
  if (!webSocket.isConnected() && relays.anyActive()) clearControllerSession();
  // Cooperative deadlines: networking can still delay execution; this is not a
  // hardware watchdog. Check immediately before and after servicing WebSockets.
  expireLeases();
  webSocket.loop();
  expireLeases();
}

void setup() {
  // Set the output latch before changing the GPIO direction to avoid an enable pulse.
  digitalWrite(oePin, HIGH);
  pinMode(oePin, OUTPUT);
  digitalWrite(stcpPin, LOW);
  digitalWrite(shcpPin, LOW);
  digitalWrite(serPin, LOW);
  pinMode(stcpPin, OUTPUT); pinMode(shcpPin, OUTPUT); pinMode(serPin, OUTPUT);
  disableOutputs();
  pinMode(powerSensePin, INPUT_PULLUP);
  pinMode(buttonPin, INPUT_PULLUP);
  powerState = readPowerSense();
  Serial.begin(115200);
  Serial.println("\n--- Smart Lift controller " VERSION " / protocol 2 ---");
  if (!LittleFS.begin()) { configError("LittleFS mount failed"); return; }
  if (!loadConfig()) return;
  configReady = true;
  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setAutoReconnect(true);
  WiFi.hostname(con_id.c_str());
  beginWifiAttempt();
}

void loop() {
  expireLeases();
  if (configReady) serviceNetwork();
  else if (static_cast<uint32_t>(millis() - lastStatusLog) >= 30000) {
    lastStatusLog = millis();
    Serial.println("[CFG] Controller disabled; correct configuration and restart.");
  }
  expireLeases();
  const uint32_t now = millis();
  const bool reading = digitalRead(buttonPin);
  if (reading != btnReading) { btnReading = reading; btnLastChangeMs = now; }
  if (static_cast<uint32_t>(now - btnLastChangeMs) >= 30 && btnReading != btnLastStable) {
    btnLastStable = btnReading;
    if (btnLastStable == LOW && relays.ready()) {
      MessageDocument<160> doc;
      doc["case"] = "error"; doc["detail"] = "Test Error: Manual Trigger";
      sendMessage(doc);
    }
  }
  if (static_cast<uint32_t>(now - lastPowerCheck) >= 500) {
    lastPowerCheck = now;
    const bool nextPower = readPowerSense();
    if (nextPower != powerState) {
      powerState = nextPower;
      if (relays.ready()) sendPowerState();
      Serial.printf("[PWR] Indication: %s\n", powerState ? "ON" : "OFF");
    }
  }
  delay(1);
}
