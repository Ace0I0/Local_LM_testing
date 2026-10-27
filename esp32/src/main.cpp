#include <Arduino.h>

void setup() {
    Serial.begin(115200);
    Serial.println("ESP32 initialized!");
}

void loop() {
    Serial.println("ESP32 running...");
    delay(1000);
}
