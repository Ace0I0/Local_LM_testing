#include <Arduino.h>
#include <ArduinoMqttClient.h>
#include <DHT.h>
#include <WiFi.h>

#include "mqtt_sensor_validation.h"
#include "secrets.h"

namespace {
constexpr uint8_t DHTPIN = 13;
constexpr uint8_t DHTTYPE = DHT22;
constexpr unsigned long SENSOR_UPDATE_INTERVAL_MS = 60UL * 1000UL;
constexpr unsigned long WIFI_RETRY_INTERVAL_MS = 10UL * 1000UL;
constexpr unsigned long MQTT_RETRY_INTERVAL_MS = 5UL * 1000UL;

constexpr char TEMPERATURE_TOPIC[] =
    "artemis/sensors/living_room/sensor/temperature/state";
constexpr char HUMIDITY_TOPIC[] =
    "artemis/sensors/living_room/sensor/humidity/state";
constexpr char STATUS_TOPIC[] = "artemis/sensors/living_room/status";
constexpr char TEMPERATURE_DISCOVERY_TOPIC[] =
    "homeassistant/sensor/living_room/temperature/config";
constexpr char HUMIDITY_DISCOVERY_TOPIC[] =
    "homeassistant/sensor/living_room/humidity/config";

constexpr char TEMPERATURE_DISCOVERY[] = R"json({"name":"Living Room Temperature","unique_id":"artemis_living_room_temperature","state_topic":"artemis/sensors/living_room/sensor/temperature/state","availability_topic":"artemis/sensors/living_room/status","payload_available":"online","payload_not_available":"offline","device_class":"temperature","state_class":"measurement","unit_of_measurement":"\u00b0C","device":{"identifiers":["artemis_living_room"],"name":"Living Room Sensor","manufacturer":"Artemis","model":"ESP32 AM2302"}})json";
constexpr char HUMIDITY_DISCOVERY[] = R"json({"name":"Living Room Humidity","unique_id":"artemis_living_room_humidity","state_topic":"artemis/sensors/living_room/sensor/humidity/state","availability_topic":"artemis/sensors/living_room/status","payload_available":"online","payload_not_available":"offline","device_class":"humidity","state_class":"measurement","unit_of_measurement":"%","device":{"identifiers":["artemis_living_room"],"name":"Living Room Sensor","manufacturer":"Artemis","model":"ESP32 AM2302"}})json";

DHT dht(DHTPIN, DHTTYPE);
WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);
unsigned long lastWifiAttempt = 0;
unsigned long lastMqttAttempt = 0;
unsigned long lastMeasurement = 0;

bool publishRetained(const char* topic, const char* payload) {
  if (!mqttClient.beginMessage(topic, strlen(payload), true, 1)) {
    Serial.print(F("Could not start MQTT publish for "));
    Serial.println(topic);
    return false;
  }
  mqttClient.print(payload);
  return mqttClient.endMessage();
}

void publishDiscovery() {
  publishRetained(TEMPERATURE_DISCOVERY_TOPIC, TEMPERATURE_DISCOVERY);
  publishRetained(HUMIDITY_DISCOVERY_TOPIC, HUMIDITY_DISCOVERY);
}

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED ||
      (lastWifiAttempt != 0 &&
       millis() - lastWifiAttempt < WIFI_RETRY_INTERVAL_MS)) {
    return;
  }

  lastWifiAttempt = millis();
  Serial.println(F("Connecting to Wi-Fi..."));
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void connectMqtt() {
  if (WiFi.status() != WL_CONNECTED || mqttClient.connected() ||
      (lastMqttAttempt != 0 &&
       millis() - lastMqttAttempt < MQTT_RETRY_INTERVAL_MS)) {
    return;
  }

  lastMqttAttempt = millis();
  Serial.print(F("Connecting to MQTT broker..."));
  if (!mqttClient.connect(MQTT_HOST, MQTT_PORT)) {
    Serial.print(F(" failed, error="));
    Serial.println(mqttClient.connectError());
    return;
  }

  Serial.println(F(" connected"));
  publishDiscovery();
  publishRetained(STATUS_TOPIC, "online");
  lastMeasurement = 0;
}

void publishMeasurements() {
  if (lastMeasurement != 0 &&
      millis() - lastMeasurement < SENSOR_UPDATE_INTERVAL_MS) {
    return;
  }
  lastMeasurement = millis();

  const float humidity = dht.readHumidity();
  const float temperature = dht.readTemperature();
  if (!isValidReading(temperature, humidity)) {
    Serial.println(F("Invalid AM2302 reading; retaining previous MQTT state."));
    return;
  }

  char temperaturePayload[16];
  char humidityPayload[16];
  snprintf(temperaturePayload, sizeof(temperaturePayload), "%.1f", temperature);
  snprintf(humidityPayload, sizeof(humidityPayload), "%.1f", humidity);
  publishRetained(TEMPERATURE_TOPIC, temperaturePayload);
  publishRetained(HUMIDITY_TOPIC, humidityPayload);
}
}  // namespace

void setup() {
  Serial.begin(115200);
  dht.begin();

  WiFi.mode(WIFI_STA);
  mqttClient.setId("artemis-living-room");
  mqttClient.setUsernamePassword(MQTT_USER, MQTT_PASSWORD);
  mqttClient.setTxPayloadSize(1024);
  mqttClient.beginWill(STATUS_TOPIC, 7, true, 1);
  mqttClient.print("offline");
  mqttClient.endWill();

  connectWifi();
}

void loop() {
  connectWifi();
  connectMqtt();

  if (mqttClient.connected()) {
    mqttClient.poll();
    publishMeasurements();
  }
}
