[Documentation index](../README.md) · [Project README](../../README.md)

# MQTT broker setup

This setup targets a Raspberry Pi running Debian 13 on ARM64 (`aarch64`), with passwordless sudo and a trusted local network. From an interactive SSH session on the Pi, run the setup wizard from the repository root:

```bash
bash scripts/setup_mosquitto.sh
```

The wizard installs Mosquitto, creates any missing Artemis MQTT accounts, enables the service, and verifies authenticated MQTT 5 publish/subscribe behavior locally and through the Pi's LAN address. It owns these files:

- `/etc/mosquitto/conf.d/artemis.conf`
- `/etc/mosquitto/artemis.passwd`
- `/etc/mosquitto/artemis.acl`

The password file contains usernames and password hashes, while the ACL file contains their permissions. MQTT topics such as `artemis/sensors/living_room/status` are broker addresses, not directories. Retained topic values live in Mosquitto's persistence database when persistence is enabled by Debian's broker configuration.

The wizard provisions these least-privilege accounts:

| Account | Access |
| --- | --- |
| `artemis_test` | Read/write under `artemis/test/#` |
| `esphome_living_room` | Publish the living-room temperature, humidity, availability, and discovery messages; read `homeassistant/status` |
| `homeassistant` | Read sensor and discovery messages; publish `homeassistant/status` |
| `artemis` | Read temperature, humidity, and availability only |

## Manage accounts

Mosquitto keeps authentication and authorization separate. An account needs both a password-file entry and a matching ACL section. Run password commands interactively so secrets are not stored in shell history.

To add an account or change an existing account's password, run:

```bash
sudo mosquitto_passwd /etc/mosquitto/artemis.passwd ACCOUNT_NAME
sudo systemctl restart mosquitto
sudo systemctl --no-pager --full status mosquitto
```

Do not add `-c`: it would replace the existing password file. Restarting the broker disconnects clients; after changing a password, update it on the client so it can reconnect.

Mosquitto does not rename accounts in place. To change a username safely:

1. Create the new account with `mosquitto_passwd`.
2. Add a new ACL section for it in `/etc/mosquitto/artemis.acl`.
3. Restart Mosquitto, update the client with the new username and password, and verify that it reconnects.
4. Remove the old ACL section, delete the old password entry, and restart Mosquitto again:

```bash
sudo mosquitto_passwd -D /etc/mosquitto/artemis.passwd OLD_ACCOUNT_NAME
sudo systemctl restart mosquitto
```

For one of the wizard-managed accounts, also update the client that uses it:

| Renamed account | Client setting to update |
| --- | --- |
| `artemis_test` | `ARTEMIS_MQTT_USER` in `scripts/setup_mosquitto.sh` |
| `esphome_living_room` | `MQTT_USER` in the ESP32's uncommitted `esp32/include/secrets.h` |
| `homeassistant` | The MQTT username in Home Assistant's integration settings |
| `artemis` | The username passed to `username_pw_set()` in `Python_Scripts/mqtt_sensor_client.py` |

To keep any managed-account rename across wizard runs, change the corresponding `*_MQTT_USER` value in `scripts/setup_mosquitto.sh` and update its assertions in `tests/test_setup_mosquitto.sh`. For additional ESP32 devices, prefer a new per-device account instead of renaming a shared consumer account.

### Add an ESP32 sensor

Follow the [ESP32 sensor guide](esp32-sensors.md) for the per-device account, ACL, credentials, and firmware settings.

## What the setup wizard does differently

`scripts/setup_mosquitto.sh` is an opinionated first-device setup, not a device-registration tool:

- It creates the fixed sensor username `esphome_living_room`.
- It grants that account access only to `living_room` topics and tests only that location.
- It does not create `esp32/include/secrets.h`, change the firmware's topics, or flash an ESP32.
- It preserves unrelated entries in `artemis.passwd`, but replaces `artemis.acl` with its four managed accounts every time it runs.
- The checked-in ESP32 firmware uses `game_room`, so it will not work with the wizard's `esphome_living_room` ACL until the firmware is changed to `living_room` or a matching `game_room` account and ACL are added as shown in the [ESP32 sensor guide](esp32-sensors.md).

If custom devices must survive future wizard runs, either reapply their ACL sections afterward or add their usernames and ACL rules to `scripts/setup_mosquitto.sh` before rerunning it.

Choose and save a different password for each account. `mosquitto_passwd` asks twice when creating a missing account, and the verification stage asks once more for each password. Input is hidden. Existing account hashes and unrelated users are preserved on reruns; a successful run ends with `Setup complete`.

The verification publishes retained QoS 1 sample values for `living_room` (`21.5` °C, `45.0`% humidity, and `online`), checks each permitted consumer, rejects cross-location and write attempts, restarts Mosquitto to prove retention, and repeats the test-account check over the Pi's LAN address.
