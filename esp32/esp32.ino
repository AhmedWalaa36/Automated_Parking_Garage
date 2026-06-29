#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <ESP32Servo.h>
#include <climits>

// WiFi & Server
const char* WIFI_SSID   = "TP-Link5C27";
const char* WIFI_PASS   = "97428121";
const char* LAPTOP_IP   = "192.168.1.7";
const int   LAPTOP_PORT = 5000;

// I2C Expanders
#define EXP1 0x26
#define EXP2 0x27

uint8_t exp1State = 0x00;
uint8_t exp2State = 0x00;

void expanderWrite(uint8_t addr, uint8_t val)
{
    Wire.beginTransmission(addr);
    Wire.write(val);
    Wire.endTransmission();
}

// 28BYJ-48 Half-Step Sequence
const uint8_t STEP_SEQ[8] =
{
    0b1000, 0b1100, 0b0100, 0b0110,
    0b0010, 0b0011, 0b0001, 0b1001
};

#define STEP_DELAY_US 2000
#define STEPS_PER_REV 2048

int stepPos1 = 0;
int stepPos2 = 0;
int stepPos3 = 0;

// Motor 1 — EXP1 upper nibble (p4-p7)
void setMotor1(uint8_t pattern)
{
    exp1State = (exp1State & 0x0F) | ((pattern & 0x0F) << 4);
    expanderWrite(EXP1, exp1State);
}

// Motor 2 — EXP1 lower nibble (p0-p3)
void setMotor2(uint8_t pattern)
{
    exp1State = (exp1State & 0xF0) | (pattern & 0x0F);
    expanderWrite(EXP1, exp1State);
}

// Motor 3 — EXP2 lower nibble (p0-p3)
void setMotor3(uint8_t pattern)
{
    exp2State = (exp2State & 0xF0) | (pattern & 0x0F);
    expanderWrite(EXP2, exp2State);
}

void stepMotor(int motorNum, int* pos, int steps)
{
    int dir      = (steps > 0) ? 1 : -1;
    int absSteps = abs(steps);

    for (int i = 0; i < absSteps; i++)
    {
        *pos = (*pos + dir + 8) % 8;
        switch (motorNum)
        {
            case 1: setMotor1(STEP_SEQ[*pos]); break;
            case 2: setMotor2(STEP_SEQ[*pos]); break;
            case 3: setMotor3(STEP_SEQ[*pos]); break;
        }
        delayMicroseconds(STEP_DELAY_US);
    }

    switch (motorNum)
    {
        case 1: setMotor1(0x00); break;
        case 2: setMotor2(0x00); break;
        case 3: setMotor3(0x00); break;
    }
}

// Servo & DC Motor (for hook and pull mechanism)
Servo hookServo;
#define SERVO_PIN    25
#define DC_IN1       26
#define DC_IN2       27
#define DC_EN        14

#define HOOK_ENGAGE  120   
#define HOOK_RELEASE  30   
#define DC_PULL_MS  2000   
#define DC_PUSH_MS  2000 

void hookEngage()
{
    hookServo.write(HOOK_ENGAGE);
    delay(800);
}

void hookRelease()
{
    hookServo.write(HOOK_RELEASE);
    delay(800);
}

void dcPull()
{
    digitalWrite(DC_IN1, HIGH);
    digitalWrite(DC_IN2, LOW);
    analogWrite(DC_EN, 200);
    delay(DC_PULL_MS);
    digitalWrite(DC_IN1, LOW);
    analogWrite(DC_EN, 0);
}

void dcPush()
{
    digitalWrite(DC_IN1, LOW);
    digitalWrite(DC_IN2, HIGH);
    analogWrite(DC_EN, 200);
    delay(DC_PUSH_MS);
    digitalWrite(DC_IN2, LOW);
    analogWrite(DC_EN, 0);
}

// Parking Slots
// distance = relative steps needed to reach slot
// guideSteps = how far motor 2 moves laterally
struct ParkingSlot
{
    byte    id;
    char    name[6];
    int     conveyorSteps;   // motor 1 — how far in
    int     shuttleSteps;    // motor 2 — lateral position
    int     liftSteps;       // motor 3 — lift height
    int     distance;        // used to rank nearest slot
    bool    occupied;
};

ParkingSlot slots[] =
{
    {1, "PL.1",  512,   256,  128,  1, false},
    {2, "PL.2",  512,   512,  128,  2, false},
    {3, "PL.3",  512,   768,  128,  3, false},
    {4, "PL.4", 1024,   256,  256,  4, false},
    {5, "PL.5", 1024,   512,  256,  5, false},
    {6, "PL.6", 1024,   768,  256,  6, false}
};

const byte TOTAL_SLOTS = sizeof(slots) / sizeof(slots[0]);

// Find nearest available slot by distance rank
int findBestSlot()
{
    int bestSlot    = -1;
    int minDistance = INT_MAX;

    for (byte i = 0; i < TOTAL_SLOTS; i++)
    {
        if (!slots[i].occupied && slots[i].distance < minDistance)
        {
            minDistance = slots[i].distance;
            bestSlot    = i;
        }
    }

    return bestSlot;
}

int slotIndexByName(const char* name)
{
    for (byte i = 0; i < TOTAL_SLOTS; i++)
    {
        if (strcmp(slots[i].name, name) == 0) return i;
    }
    return -1;
}

// Motor Sequences
void parkAtSlot(int idx)
{
    Serial.printf("[MOTOR] Parking at %s\n", slots[idx].name);

    // conveyor brings car to row
    stepMotor(1, &stepPos1, slots[idx].conveyorSteps);
    delay(300);

    // Shuttle moves car laterally to correct column
    stepMotor(2, &stepPos2, slots[idx].shuttleSteps);
    delay(300);

    // lift raises car to correct floor
    stepMotor(3, &stepPos3, slots[idx].liftSteps);
    delay(300);

    // Hook grabs car and DC motor pulls it into slot
    hookEngage();
    dcPull();
    hookRelease();

    Serial.printf("[MOTOR] Parked at %s\n", slots[idx].name);
}

void retrieveFromSlot(int idx)
{
    Serial.printf("[MOTOR] Retrieving from %s\n", slots[idx].name);

    // DC motor pushes car out of slot, hook guides
    hookEngage();
    dcPush();
    hookRelease();
    delay(300);

    // Reverse lift
    stepMotor(3, &stepPos3, -slots[idx].liftSteps);
    delay(300);

    // Reverse shuttle
    stepMotor(2, &stepPos2, -slots[idx].shuttleSteps);
    delay(300);

    // Reverse conveyor and brings car to exit
    stepMotor(1, &stepPos1, -slots[idx].conveyorSteps);

    Serial.printf("[MOTOR] Retrieved from %s\n", slots[idx].name);
}

// HTTP Helpers
String url(const char* path)
{
    return String("http://") + LAPTOP_IP + ":" + LAPTOP_PORT + path;
}

int postJson(const char* path, String body)
{
    HTTPClient http;
    http.begin(url(path));
    http.addHeader("Content-Type", "application/json");
    int code = http.POST(body);
    http.end();
    return code;
}

// Command Handlers
void handlePark(int cmdId, const char* plateNo)
{
    int idx = findBestSlot();

    if (idx == -1)
    {
        Serial.println("[PARK] No available slots");
        return;
    }

    Serial.printf("[PARK] Best slot for %s is %s\n", plateNo, slots[idx].name);

    parkAtSlot(idx);
    slots[idx].occupied = true;

    StaticJsonDocument<200> doc;
    doc["cmd_id"]    = cmdId;
    doc["plate_no"]  = plateNo;
    doc["spot_code"] = slots[idx].name;
    String body;
    serializeJson(doc, body);
    postJson("/parked", body);
}

void handleRetrieve(int cmdId, const char* spotCode)
{
    int idx = slotIndexByName(spotCode);

    if (idx == -1)
    {
        Serial.printf("[RETRIEVE] Unknown slot: %s\n", spotCode);
        return;
    }

    retrieveFromSlot(idx);
    slots[idx].occupied = false;

    StaticJsonDocument<200> doc;
    doc["cmd_id"]    = cmdId;
    doc["spot_code"] = spotCode;
    String body;
    serializeJson(doc, body);
    postJson("/retrieved", body);
}

// Poll Server for Commands
void pollServer()
{
    HTTPClient http;
    http.begin(url("/command"));
    int code = http.GET();

    if (code != 200)
    {
        http.end();
        return;
    }

    String payload = http.getString();
    http.end();

    StaticJsonDocument<256> doc;
    if (deserializeJson(doc, payload)) return;

    const char* command = doc["command"];
    if (strcmp(command, "none") == 0) return;

    int         cmdId    = doc["cmd_id"]    | 0;
    const char* plateNo  = doc["plate_no"]  | "";
    const char* spotCode = doc["spot_code"] | "";

    Serial.printf("[CMD] %s  id=%d\n", command, cmdId);

    if      (strcmp(command, "park")     == 0) handlePark(cmdId, plateNo);
    else if (strcmp(command, "retrieve") == 0) handleRetrieve(cmdId, spotCode);
}

// WiFi
void connectWifi()
{
    Serial.printf("[WIFI] Connecting to %s", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
    Serial.printf("\n[WIFI] Connected — %s\n", WiFi.localIP().toString().c_str());
}


unsigned long lastPoll = 0;
#define POLL_MS 1000

void setup()
{
    Serial.begin(115200);
    Wire.begin(21, 22);

    Wire.beginTransmission(EXP1);
    Serial.printf("[I2C] EXP1 0x26: %s\n", Wire.endTransmission() == 0 ? "OK" : "NOT FOUND");
    Wire.beginTransmission(EXP2);
    Serial.printf("[I2C] EXP2 0x27: %s\n", Wire.endTransmission() == 0 ? "OK" : "NOT FOUND");

    expanderWrite(EXP1, 0x00);
    expanderWrite(EXP2, 0x00);

    hookServo.attach(SERVO_PIN);
    hookServo.write(HOOK_RELEASE);

    pinMode(DC_IN1, OUTPUT);
    pinMode(DC_IN2, OUTPUT);
    pinMode(DC_EN,  OUTPUT);
    digitalWrite(DC_IN1, LOW);
    digitalWrite(DC_IN2, LOW);
    analogWrite(DC_EN, 0);

    connectWifi();
    Serial.println("[READY] Polling for commands...");
}

void loop()
{
    if (WiFi.status() != WL_CONNECTED) connectWifi();

    if (millis() - lastPoll >= POLL_MS)
    {
        lastPoll = millis();
        pollServer();
    }
}
