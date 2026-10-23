# Artemis MQTT Sensor Consumer Design

Date: 2026-10-23
Status: Proposed

## Intent

Give Artemis direct, read-only access to the environmental MQTT contract so it can answer current living-room temperature and humidity questions without asking the language model to interpret or invent measurements.

This is the first application feature built on the Mosquitto and Home Assistant infrastructure already running on the Raspberry Pi.

## Goals

- Subscribe with the existing least-privilege `artemis` MQTT account.
- Consume temperature, humidity, and availability for every valid Location ID.
- Validate messages before they can replace the last valid state.
- Distinguish missing, offline, stale, and current readings.
- Answer sensor questions deterministically and continue using SAM for speech.
- Keep MQTT credentials out of Git, logs, debug output, and command history.
- Record Python dependencies in a single installable file and document setup in the README.

## Non-goals

- Historical storage, trends, daily summaries, or a database.
- Alerts or unusual-reading thresholds.
- Device control or MQTT publishing.
- Home Assistant API access.
- ESPHome configuration or physical sensor setup.
- Running Artemis as a system service.
- Room-aware microphones, distributed voice units, or inferring location from where a request was heard. A future voice unit may provide location context, but this slice does not define that interface.

## Constraints

- The broker is local at `127.0.0.1:1883` and requires authentication.
- Artemis may only read the three topic filters already granted by Mosquitto.
- The existing controller blocks while waiting for terminal input, local-model responses, and SAM, so MQTT networking cannot use the main thread.
- Celsius remains the canonical wire unit. The current household presentation preference is Fahrenheit.
- The default reporting interval is 60 seconds and the stale timeout is 180 seconds.
- MQTT carries no measurement timestamp. A retained reading received at startup is treated as newly received, then becomes stale after 180 seconds if no update follows.

## Approaches considered

### In-process Paho subscriber — selected

Use the Eclipse Paho Python client and its background network loop. Subscribe from the connection callback so subscriptions are restored after reconnects. Keep validated current state in memory behind a lock.

This fits the existing single-process terminal application, reconnects without blocking user input, and adds only one runtime dependency.

### Subscribe when each question is asked

Invoke `mosquitto_sub` for every sensor question. This avoids a Python dependency, but creates a connection and subprocess for every answer, cannot observe updates between questions, and provides weaker connection and freshness state.

### Separate collector and database

Run an independent MQTT service that records readings in SQLite. This supports later history and summaries, but introduces a second process and persistence schema before either is required.

## Dependency and configuration contract

Create a repository-level `requirements.txt` as the source of truth for Python runtime dependencies. It will include both the existing `rapidfuzz` dependency and the new `paho-mqtt` dependency. The README setup command changes to:

```bash
python -m pip install -r requirements.txt
```

The application uses these MQTT settings:

| Setting | Value |
| --- | --- |
| Host | `127.0.0.1` |
| Port | `1883` |
| Username | `artemis` |
| Password | `ARTEMIS_MQTT_PASSWORD` environment variable, or a hidden startup prompt when unset |
| Protocol | MQTT 5 |
| Subscription QoS | 1 |

No dotenv library or committed secrets file is added. The password is never printed. `--router-test` and other tests do not prompt for a password or contact the broker.

If `paho-mqtt` is missing during normal startup, Artemis prints an installation instruction naming `requirements.txt` and exits cleanly. A missing password produces the hidden prompt. An unavailable broker does not stop non-sensor Artemis features; the MQTT client reconnects in the background and sensor questions report that data is unavailable.

## Sensor-state module

Add a focused module under `Python_Scripts/` that owns MQTT topic parsing, payload validation, thread-safe current state, freshness, and connection status. The controller owns starting and stopping it.

The client subscribes to:

```text
artemis/sensors/+/sensor/temperature/state
artemis/sensors/+/sensor/humidity/state
artemis/sensors/+/status
```

The module accepts only topics matching the approved shapes and Location ID grammar. It stores one in-memory record per location with:

- latest valid Celsius temperature and receipt time;
- latest valid relative humidity and receipt time;
- latest valid `online` or `offline` availability and receipt time.

Temperature and humidity payloads must be non-empty finite base-10 numbers. Humidity must be between 0 and 100 inclusive. Availability must be exactly `online` or `offline`. Invalid topics or payloads are ignored and do not overwrite prior valid state.

A measurement is current only when it exists, its receipt age is at most 180 seconds, and the location is not explicitly offline. The API returns structured status rather than making presentation decisions inside MQTT callbacks.

## Question routing and responses

Extend the existing RapidFuzz router with a sensor-query intent and environmental topics. Initial supported requests include temperature, humidity, or general conditions for a named location such as `living room`.

When a request omits its location, Artemis uses the location automatically only if exactly one location is known. If zero locations are known, it reports that no sensor location is available. If multiple locations are known, it asks the user to name one rather than guessing. A future room-aware microphone may supply location context before routing, without changing the MQTT state model.

Sensor questions are answered before prompt assembly and bypass the LLM. They still use the existing SAM output path. The route is computed once and reused so normal questions do not pay for duplicate routing.

Response behavior:

- A temperature request reports Fahrenheit by default while retaining Celsius internally. An explicit Celsius request reports Celsius.
- A humidity request reports relative humidity as a percentage.
- A general conditions request reports only measurements that are currently available. It omits a missing, stale, or unavailable measurement rather than turning an internal sensor condition into an apparent environmental warning.
- A request for a specific unavailable measurement says only that Artemis does not have a current reading for it. It does not describe the humidity or temperature itself as stale.
- If no requested measurements are available, Artemis says that it has no current sensor information for the location.
- Missing, stale, and offline remain distinct internal states for validation and debug output, but normal household responses do not expose those implementation details.
- An unknown location is reported plainly and never falls through to an invented LLM answer.

Values are rounded for speech presentation only; stored values remain unchanged.

## Lifecycle and failure behavior

Normal application startup creates the sensor-state service, starts Paho's background loop, and then enters the existing terminal input loop. Shutdown disconnects the client cleanly in a `finally` block.

Subscriptions are installed in the connection callback, which makes reconnects restore them. Connection failures and disconnects update diagnostics but do not terminate the controller. No callback prints credentials or raw authentication configuration.

MQTT connection state and message rejection counts may appear in debug output. Passwords and raw invalid payloads do not.

## Testing

Use the standard library test runner so this feature adds no test-only dependency.

Tests cover:

- parsing all three valid topic shapes and rejecting malformed or invalid-location topics;
- finite temperature validation and humidity range enforcement;
- invalid messages preserving the previous valid state;
- online, offline, missing, and stale snapshots using an injected clock;
- Celsius-to-Fahrenheit presentation;
- deterministic temperature, humidity, and combined responses;
- partial combined responses that omit unavailable measurements, plus direct requests that report no current reading;
- sensor intent routing, including the existing router tests remaining green;
- client subscription behavior with a fake Paho client, without a live broker;
- missing dependency and missing-password behavior where practical at the controller boundary.

The existing Mosquitto wizard test remains unchanged except for any dependency documentation assertions that belong in a new focused test.

## Documentation and acceptance

Update the README to document:

- `requirements.txt` installation;
- the `paho-mqtt` purpose;
- the `artemis` account and hidden-password startup flow;
- supported sensor questions and Fahrenheit/Celsius behavior;
- the 180-second stale rule;
- commands for running the new standard-library tests.

The slice is accepted when the Pi can run Artemis, receive the retained living-room sample through the read-only account, answer temperature and humidity questions without calling the LLM, reject invalid readings in tests, and continue handling non-sensor requests while the broker is temporarily unavailable.
