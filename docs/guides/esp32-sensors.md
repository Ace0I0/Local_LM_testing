[Documentation index](../README.md) · [Project README](../../README.md)

# Add an ESP32 sensor

Give every physical device its own account, password, MQTT client ID, and location name. Use lowercase location names with underscores, such as `game_room`, consistently in the ACL and firmware.

For example, create an account for a game-room ESP32:

```bash
sudo mosquitto_passwd /etc/mosquitto/artemis.passwd esp32_game_room
sudoedit /etc/mosquitto/artemis.acl
```

Add this least-privilege ACL section:

```text
user esp32_game_room
topic write artemis/sensors/game_room/sensor/temperature/state
topic write artemis/sensors/game_room/sensor/humidity/state
topic write artemis/sensors/game_room/status
topic write homeassistant/+/game_room/#
topic read homeassistant/status
```

Restart the broker after saving the ACL:

```bash
sudo systemctl restart mosquitto
sudo systemctl --no-pager --full status mosquitto
```

On the computer used to flash the ESP32, configure it from the repository root. Create `secrets.h` only for a new checkout; if it exists, edit it directly. The interactive copy asks before overwriting an existing file:

```bash
cp -i esp32/include/secrets.example.h esp32/include/secrets.h
```

Edit `esp32/include/secrets.h` with the Wi-Fi credentials, broker IP address, `esp32_game_room` username, and the password just created. This file is ignored by Git and must not be committed.

The example firmware in `esp32/src/main.cpp` currently identifies itself as `game_room`. For another location, replace every `game_room`, `Game Room`, and `artemis-game-room` value with that device's unique location, display name, and client ID. Also change `DHTPIN` if the sensor uses a different GPIO. The state, availability, Home Assistant discovery, and ACL topics must all use the same location.

The `homeassistant` and `artemis` accounts created by the wizard already have read permissions with a `+` location wildcard, so they can read additional locations without new ACL entries.

## Build, upload, and verify

Install [PlatformIO Core](https://docs.platformio.org/en/latest/core/installation/index.html) on the computer connected to the ESP32 by USB. Commands below run from the repository root. The checked-in environment targets an ESP32 development board with a DHT22/AM2302 sensor on GPIO 13; check your board and wiring before flashing.

Build and upload the configured firmware, then open the serial monitor:

```bash
pio run -d esp32
pio run -d esp32 --target upload
pio device monitor -d esp32
```

If multiple serial devices are connected, select the intended ESP32 with PlatformIO's upload-port and monitor-port options. The serial monitor uses 115200 baud. Look for `Connecting to MQTT broker... connected`. An invalid-reading message means the sensor reading was rejected; inspect the wiring and sensor configuration.

Allow a reporting interval (60 seconds by default), then confirm the temperature and humidity entities in Home Assistant or [ask Artemis about that location](sensor-questions.md). A successful MQTT connection alone does not prove the ACL permits all publications.

The wizard's sensor account only permits `living_room`, while this firmware publishes `game_room`. Use the account and matching ACL above, or change all firmware location values consistently. See [wizard limitations](mqtt-broker.md#what-the-setup-wizard-does-differently).

## MQTT values

Each device publishes retained QoS 1 temperature, humidity, and availability messages. Temperature payloads are decimal Celsius values; humidity is a decimal percentage. Availability uses `online` and a retained `offline` last will. Discovery messages identify the entities to Home Assistant.

Keep one environmental node per location with the current topic convention. Reusing another device's MQTT client ID can cause reconnect loops; reusing discovery identifiers can make Home Assistant treat two sensors as the same entity.
