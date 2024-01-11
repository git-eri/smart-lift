// Controller ID: must be unique!
const String con_id = "con1";
// Lifts start from 0. If controller handles lifts 6-10 it must be 5.
const uint8_t lift_begin = 0;
// Lift count: How many lifts the controller handles.
const uint8_t lift_count = 5;
// Which relais-id's for which lift, they are in order of the lifts.
// This example is for a 16 relais board with 5 connected lifts per controller.
// Each lift uses 3 relais (up, down, lock).
const uint8_t lifts[lift_count][3] = { {15,14,13},
                                       {12,11,10},
                                       {9,8,7},
                                       {6,5,4},
                                       {3,2,1}
                                      };
// Wifi connections
// If you have more than one Wifi connection, change the 1 to the number of connections.
const String networks[1][4] = { {"SSID","Password","Server IP","Server Port"},
                               };
