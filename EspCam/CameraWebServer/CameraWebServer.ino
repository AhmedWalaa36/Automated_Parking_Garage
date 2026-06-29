#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>

// WiFi & Server
const char* WIFI_SSID   = "TP-Link5C27";
const char* WIFI_PASS   = "97428121";
const char* LAPTOP_IP   = "192.168.1.7";
const int   LAPTOP_PORT = 5000;

// pin definitions
#define IR_PIN    13
#define FLASH_PIN  4

#define DEBOUNCE_MS 4000

//ESP32-CAM Pin Map
#define PWDN_GPIO_NUM   32
#define RESET_GPIO_NUM  -1
#define XCLK_GPIO_NUM    0
#define SIOD_GPIO_NUM   26
#define SIOC_GPIO_NUM   27
#define Y9_GPIO_NUM     35
#define Y8_GPIO_NUM     34
#define Y7_GPIO_NUM     39
#define Y6_GPIO_NUM     38
#define Y5_GPIO_NUM     37
#define Y4_GPIO_NUM     36
#define Y3_GPIO_NUM     21
#define Y2_GPIO_NUM     19
#define VSYNC_GPIO_NUM  25
#define HREF_GPIO_NUM   23
#define PCLK_GPIO_NUM   22


// Init
bool initCamera()
{
    camera_config_t cfg;
    cfg.ledc_channel = LEDC_CHANNEL_0;
    cfg.ledc_timer   = LEDC_TIMER_0;
    cfg.pin_d0       = Y2_GPIO_NUM;
    cfg.pin_d1       = Y3_GPIO_NUM;
    cfg.pin_d2       = Y4_GPIO_NUM;
    cfg.pin_d3       = Y5_GPIO_NUM;
    cfg.pin_d4       = Y6_GPIO_NUM;
    cfg.pin_d5       = Y7_GPIO_NUM;
    cfg.pin_d6       = Y8_GPIO_NUM;
    cfg.pin_d7       = Y9_GPIO_NUM;
    cfg.pin_xclk     = XCLK_GPIO_NUM;
    cfg.pin_pclk     = PCLK_GPIO_NUM;
    cfg.pin_vsync    = VSYNC_GPIO_NUM;
    cfg.pin_href     = HREF_GPIO_NUM;
    cfg.pin_sscb_sda = SIOD_GPIO_NUM;
    cfg.pin_sscb_scl = SIOC_GPIO_NUM;
    cfg.pin_pwdn     = PWDN_GPIO_NUM;
    cfg.pin_reset    = RESET_GPIO_NUM;
    cfg.xclk_freq_hz = 20000000;
    cfg.pixel_format = PIXFORMAT_JPEG;
    cfg.frame_size   = FRAMESIZE_VGA;
    cfg.jpeg_quality = 10;
    cfg.fb_count     = 1;

    if (esp_camera_init(&cfg) != ESP_OK)
    {
        Serial.println("[CAM] Init failed");
        return false;
    }

    sensor_t* s = esp_camera_sensor_get();
    s->set_brightness(s,    1);
    s->set_contrast(s,      1);
    s->set_sharpness(s,     2);
    s->set_whitebal(s,      1);
    s->set_exposure_ctrl(s, 1);

    Serial.println("[CAM] Ready");
    return true;
}

// Capture & Send
void captureAndSend()
{
    // discards first frame cuz sensor needs one cycle to adjust exposure
    camera_fb_t* warmup = esp_camera_fb_get();
    if (warmup) esp_camera_fb_return(warmup);
    delay(200);

    digitalWrite(FLASH_PIN, HIGH);
    delay(200);
    digitalWrite(FLASH_PIN, LOW);

    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb)
    {
        Serial.println("[CAM] Capture failed");
        return;
    }

    Serial.printf("[CAM] Frame: %u bytes\n", fb->len);

    String endpoint = String("http://") + LAPTOP_IP + ":" + LAPTOP_PORT + "/entry";
    HTTPClient http;
    http.begin(endpoint);
    http.setTimeout(15000);
    http.addHeader("Content-Type", "image/jpeg");

    int code = http.POST(fb->buf, fb->len);
    esp_camera_fb_return(fb);

    if      (code == 200) Serial.println("[API] Accepted — park command queued");
    else if (code == 404) Serial.println("[API] Plate not registered");
    else if (code == 409) Serial.println("[API] Vehicle already parked");
    else                  Serial.printf("[API] HTTP %d\n", code);

    http.end();
}

// WiFi
void connectWifi()
{
    Serial.printf("[WIFI] Connecting to %s", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
    Serial.printf("\n[WIFI] Connected — %s\n", WiFi.localIP().toString().c_str());
}

unsigned long lastTrigger = 0;

void setup()
{
    Serial.begin(115200);
    delay(500);

    pinMode(IR_PIN,    INPUT);
    pinMode(FLASH_PIN, OUTPUT);
    digitalWrite(FLASH_PIN, LOW);

    if (!initCamera())
    {
        // blink rapidly if camera failed
        while (true)
        {
            digitalWrite(FLASH_PIN, HIGH); delay(150);
            digitalWrite(FLASH_PIN, LOW);  delay(150);
        }
    }

    connectWifi();
    Serial.println("[READY] Waiting for vehicle...");
}

void loop()
{
    if (WiFi.status() != WL_CONNECTED) connectWifi();

    if (digitalRead(IR_PIN) == LOW)
    {
        unsigned long now = millis();
        if (now - lastTrigger < DEBOUNCE_MS) { delay(50); return; }
        lastTrigger = now;

        Serial.println("[IR] Vehicle detected");
        delay(600);   // let car settle in frame
        captureAndSend();
        Serial.println("[READY] Waiting for next vehicle...");
    }

    delay(50);
}
