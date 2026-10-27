#include <Arduino.h>
#include <DHT.h>

// Define the pin connected to the AM2302 data line
#define DHTPIN 13

// AM2302 is the wired version of the DHT22 sensor
#define DHTTYPE DHT22

// Initialize DHT sensor
DHT dht(DHTPIN, DHTTYPE);

void setup() {
  // Start the serial communication for the Serial Monitor
  Serial.begin(115200);
  Serial.println(F("AM2302 (DHT22) Test Starting..."));

  // Initialize the sensor
  dht.begin();
}

void loop() {
  // Wait 2 seconds between measurements (AM2302 requires this minimum delay)
  delay(2000);

  // Reading temperature or humidity takes about 250 milliseconds
  float humidity = dht.readHumidity();
  // Read temperature as Celsius (the default)
  float temperature = dht.readTemperature();

  // Check if any reads failed and exit early (to try again)
  if (isnan(humidity) || isnan(temperature)) {
    Serial.println(F("Failed to read from AM2302 sensor!"));
    return;
  }

  // Print the results to the PlatformIO Serial Monitor
  Serial.print(F("Humidity: "));
  Serial.print(humidity);
  Serial.print(F("%  |  Temperature: "));
  Serial.print(temperature);
  Serial.println(F("°C"));
}
