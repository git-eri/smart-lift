// Controller ID: must be unique
const String con_id = "con1";
// Lifts start from 0, if Controller handles Lift 6-10 it must be 5
const uint8_t lift_begin = 0;
// Lift count: How many lifts the controller handles
const uint8_t lift_count = 5;
// which Relais for which lift
const uint8_t lifts[lift_count][3] = { {15,14,13},
                                       {12,11,10},
                                       {9,8,0},
                                       {1,2,3},
                                       {4,5,6}
                                      };

// Wifi connections
const String SSID = "SSID";
const String PASSWORD = "PASSWORD";
const String SERVER = "SERVER_DOMAIN";
const int PORT = 8000;

// Server certificate
const char SERVER_CERT[] PROGMEM = R"EOF(
-----BEGIN CERTIFICATE-----
postyourcerthere
-----END CERTIFICATE-----
)EOF";
