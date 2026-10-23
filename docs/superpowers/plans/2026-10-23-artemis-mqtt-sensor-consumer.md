# Artemis MQTT Sensor Consumer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let Artemis subscribe read-only to environmental MQTT state and answer current temperature and humidity questions deterministically without calling the LLM.

**Architecture:** A focused `sensor_state.py` module validates MQTT topics and payloads and owns thread-safe in-memory state. A thin Paho adapter maintains the MQTT 5 connection in a background thread, while `sensor_answers.py` converts routed questions and current snapshots into speech-ready answers before the existing LLM path.

**Tech Stack:** Python 3.9+, standard-library `dataclasses`, `threading`, `unittest`, RapidFuzz, Eclipse Paho MQTT 2.x, MQTT 5

**Spec:** `docs/superpowers/specs/2026-10-23-artemis-mqtt-sensor-consumer-design.md`

## Global Constraints

- Subscribe only as `artemis` to the three approved `artemis/sensors/+/...` filters at QoS 1; never publish.
- Keep Celsius on the wire and in state; present Fahrenheit by default and Celsius when explicitly requested.
- Use a 180-second stale timeout and preserve the last valid measurement when a later payload is invalid.
- Keep MQTT passwords out of Git, logs, debug output, command history, fixtures, and exception text.
- Sensor questions bypass the LLM but continue through the existing SAM speech path.
- General condition reports omit unavailable measurements; direct requests say only that no current reading is available.
- `--router-test` and unit tests must not prompt for credentials or contact a broker.
- Add only one runtime dependency, `paho-mqtt`; do not add dotenv, a database, or a test framework.

## Review Focus

- Malformed UTF-8, `NaN`, infinity, empty values, and out-of-range humidity must be rejected without losing prior state — pinned in Task 1 validation tests.
- Extra topic segments, wildcard-looking locations, and invalid Location IDs must not create state — pinned in Task 1 topic tests.
- A reading exactly 180 seconds old is current and one older than 180 seconds is stale — pinned in Task 1 clock-boundary tests.
- MQTT authentication refusal or broker downtime must leave non-sensor Artemis behavior available and avoid a reconnect busy loop — pinned in Task 2 callback and reconnect tests.
- A named unknown location must not silently fall back to the only known location — pinned in Task 3 location-resolution tests.

---

### Task 1: Validated environmental state

**Files:**
- Create: `Python_Scripts/sensor_state.py`
- Create: `tests/test_sensor_state.py`

**Interfaces:**
- Consumes: approved topic shapes and raw MQTT payload bytes; an injected `clock: Callable[[], float]` for deterministic freshness tests.
- Produces: `MeasurementSnapshot(value: float | None, state: Literal["current", "missing", "stale", "offline"])`; `LocationSnapshot(location_id: str, temperature: MeasurementSnapshot, humidity: MeasurementSnapshot, availability: Literal["online", "offline", "unknown"])`; `SensorState.ingest(topic: str, payload: bytes) -> bool`; `SensorState.snapshot(location_id: str) -> LocationSnapshot | None`; `SensorState.known_locations() -> tuple[str, ...]`.

- [ ] **Step 1: Write failing topic and payload tests**

Add `unittest` cases that assert:

```python
self.assertTrue(state.ingest("artemis/sensors/living_room/sensor/temperature/state", b"21.5"))
self.assertTrue(state.ingest("artemis/sensors/living_room/sensor/humidity/state", b"45.0"))
self.assertTrue(state.ingest("artemis/sensors/living_room/status", b"online"))
self.assertFalse(state.ingest("artemis/sensors/Living-Room/status", b"online"))
self.assertFalse(state.ingest("artemis/sensors/living_room/extra/status", b"online"))
```

Cover empty bytes, invalid UTF-8, `NaN`, positive/negative infinity, humidity below 0 and above 100, invalid availability text, and preservation of the prior valid value after every rejected update.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest discover -s tests -p 'test_sensor_state.py' -v`

Expected: import failure because `sensor_state` does not exist.

- [ ] **Step 3: Implement the minimal state types and ingestion boundary**

In `sensor_state.py`, define `MeasurementSnapshot`, `LocationSnapshot`, and `SensorState` with:

```python
class SensorState:
    def __init__(self, clock: Callable[[], float] = time.monotonic, stale_after: float = 180.0) -> None: ...
    def ingest(self, topic: str, payload: bytes) -> bool: ...
    def snapshot(self, location_id: str) -> LocationSnapshot | None: ...
    def known_locations(self) -> tuple[str, ...]: ...
```

Use one anchored topic parser, `math.isfinite`, the approved Location ID grammar, and a `threading.Lock`. Decode UTF-8 strictly. Record the injected monotonic time only for accepted messages.

- [ ] **Step 4: Add freshness, offline, and ordering tests**

Assert the 180-second boundary, stale state after 180 seconds, explicit offline overriding otherwise-current measurements, online state restoring measurement visibility, sorted location IDs, partial locations, and a repeated valid QoS 1 delivery refreshing its receipt time.

- [ ] **Step 5: Run the focused test and verify GREEN**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest discover -s tests -p 'test_sensor_state.py' -v`

Expected: all sensor-state tests pass.

- [ ] **Step 6: Commit the state boundary**

```bash
git add Python_Scripts/sensor_state.py tests/test_sensor_state.py
git commit -m "Add validated environmental sensor state"
```

---

### Task 2: Background MQTT client and dependency manifest

**Files:**
- Create: `requirements.txt`
- Create: `Python_Scripts/mqtt_sensor_client.py`
- Create: `tests/test_mqtt_sensor_client.py`

**Interfaces:**
- Consumes: `SensorState.ingest(topic, payload)`, broker password, and an optional injected Paho-compatible client for tests.
- Produces: `MqttSensorClient(state: SensorState, password: str, client: Any | None = None, host: str = "127.0.0.1", port: int = 1883)` with `start() -> None`, `stop() -> None`, `connected: bool`, and `rejected_messages: int`.

- [ ] **Step 1: Add the runtime dependency manifest**

Create `requirements.txt` containing compatible major-version ranges for the existing RapidFuzz 3.x dependency and Paho MQTT 2.x. Install it in the active virtual environment:

```bash
python3 -m pip install -r requirements.txt
```

- [ ] **Step 2: Write failing fake-client tests**

Test that construction rejects an empty password; configures MQTT 5 callback API v2, username `artemis`, and the supplied password; sets bounded reconnect delay; and does not expose the password through public fields or `repr`.

Using a fake Paho client, test that a successful connection subscribes exactly once to each approved topic at QoS 1, a refused connection does not subscribe, incoming messages call `SensorState.ingest`, rejected messages increment only a count, and `start()`/`stop()` invoke the background-loop lifecycle without a real network connection.

- [ ] **Step 3: Run the focused test and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest discover -s tests -p 'test_mqtt_sensor_client.py' -v`

Expected: import failure because `mqtt_sensor_client` does not exist.

- [ ] **Step 4: Implement the Paho adapter**

Use `paho.mqtt.client.Client(mqtt.CallbackAPIVersion.VERSION2, protocol=mqtt.MQTTv5)`, `username_pw_set`, `connect_async`, `loop_start`, `loop_stop`, and `disconnect`. Subscribe in the successful `on_connect` callback so reconnects restore all filters. Set `reconnect_delay_set(min_delay=1, max_delay=120)` and update connection diagnostics without raising into the terminal loop.

- [ ] **Step 5: Run MQTT adapter and state tests**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest discover -s tests -p 'test_*sensor*.py' -v`

Expected: all tests pass without contacting Mosquitto.

- [ ] **Step 6: Commit the adapter and documented dependency source**

```bash
git add requirements.txt Python_Scripts/mqtt_sensor_client.py tests/test_mqtt_sensor_client.py
git commit -m "Add background MQTT sensor client"
```

---

### Task 3: Sensor routing and deterministic answers

**Files:**
- Modify: `Python_Scripts/intent_router.py:82-437,604-656`
- Create: `Python_Scripts/sensor_answers.py`
- Create: `tests/test_sensor_answers.py`
- Modify: `Python_Scripts/load_llm_sam.py:624-660`

**Interfaces:**
- Consumes: `LocationSnapshot`, `SensorState.snapshot()`, `SensorState.known_locations()`, and the existing route dictionary returned by `analyze_query()`.
- Produces: router intent `sensor_query`; topics `temperature`, `humidity`, and `environment`; `build_sensor_answer(user_text: str, route: dict[str, Any], state: SensorState) -> str | None`.

- [ ] **Step 1: Write failing router cases**

Extend `run_router_tests()` and add answer tests for at least:

```text
what is the living room temperature -> sensor_query / temperature
how humid is the living room -> sensor_query / humidity
how are conditions in the living room -> sensor_query / environment
what is the tempeture -> sensor_query / temperature
```

Keep every existing router case green. Pin `sensor_query` to `needs_knowledge == False` and an empty selected-file list.

- [ ] **Step 2: Write failing answer and location-resolution tests**

Assert exact speech-ready results for current Fahrenheit, explicit Celsius, humidity, and combined conditions. Also assert:

```python
self.assertEqual(answer_temperature, "The living room temperature is 70.7 degrees Fahrenheit.")
self.assertEqual(answer_celsius, "The living room temperature is 21.5 degrees Celsius.")
self.assertEqual(answer_humidity, "The living room humidity is 45 percent.")
self.assertEqual(answer_conditions, "The living room is 70.7 degrees Fahrenheit with 45 percent relative humidity.")
```

- general conditions omit unavailable humidity while retaining current temperature;
- direct unavailable humidity returns `I do not have a current humidity reading for the living room.`;
- no current measurements returns `I do not have current sensor information for the living room.`;
- one known location is selected only when no location was named;
- multiple known locations return `Which location do you mean?`;
- explicitly named unknown `bedroom` does not fall back to known `living_room`;
- non-sensor routes return `None`.

- [ ] **Step 3: Run the focused tests and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest discover -s tests -p 'test_sensor_answers.py' -v`

Expected: failures for the missing `sensor_query` rules and `sensor_answers` module.

- [ ] **Step 4: Add the sensor intent without knowledge loading**

Add weighted exact/fuzzy rules for temperature, humidity, and conditions to `INTENT_RULES` and `TOPIC_RULES`. Update `_needs_knowledge()` so `sensor_query` never selects EAS knowledge. Add the new cases to the existing `--router-test` list.

- [ ] **Step 5: Implement deterministic answer formatting**

In `sensor_answers.py`, implement:

```python
def build_sensor_answer(user_text: str, route: dict[str, Any], state: SensorState) -> str | None: ...
```

Match humanized known Location IDs, detect an explicitly named unknown location before applying the single-location fallback, convert Celsius with `(celsius * 9 / 5) + 32`, and round only rendered values. Do not include internal `missing`, `stale`, or `offline` labels in household responses.

- [ ] **Step 6: Run answer and router tests and verify GREEN**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest discover -s tests -p 'test_sensor_answers.py' -v`

Run: `python3 Python_Scripts/load_llm_sam.py --router-test`

Expected: all new answer tests pass and every router check reports `PASS` without MQTT credentials.

- [ ] **Step 7: Commit routing and answers**

```bash
git add Python_Scripts/intent_router.py Python_Scripts/sensor_answers.py Python_Scripts/load_llm_sam.py tests/test_sensor_answers.py
git commit -m "Answer environmental sensor questions"
```

---

### Task 4: Controller lifecycle, documentation, and Pi acceptance

**Files:**
- Modify: `Python_Scripts/load_llm_sam.py:1-20,317-421,663-end`
- Create: `tests/test_sensor_controller.py`
- Modify: `README.md:56-136,140-158`

**Interfaces:**
- Consumes: `MqttSensorClient.start()/stop()`, `SensorState`, `build_sensor_answer()`, `ARTEMIS_MQTT_PASSWORD`, and existing `make_sam_wav()`.
- Produces: `build_system_prompt(identity: dict, mode: dict, user_text: str, route: dict | None = None) -> tuple[str, dict]`; `get_mqtt_password(environ: Mapping[str, str], prompt: Callable[[str], str]) -> str`; `handle_sensor_turn(user_text: str, route: dict, state: SensorState, identity: dict) -> bool`; normal startup with hidden password fallback.

- [ ] **Step 1: Write failing controller-boundary tests**

Test that a provided route prevents `build_system_prompt()` from calling `route_intent()` again. Test `get_mqtt_password()` with an environment password, hidden-prompt fallback, and empty-value rejection. Test `handle_sensor_turn()` returns `True` and passes sensor text to the existing SAM function, while a non-sensor route returns `False` without calling SAM.

- [ ] **Step 2: Run the controller test and verify RED**

Run: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest discover -s tests -p 'test_sensor_controller.py' -v`

Expected: failures because route injection, credential lookup, and the sensor branch do not exist.

- [ ] **Step 3: Integrate lifecycle and direct answers**

Keep the `--router-test` early exit before any Paho import or credential prompt. During normal startup, import the MQTT adapter with a clear `python -m pip install -r requirements.txt` error if unavailable, obtain the password from `ARTEMIS_MQTT_PASSWORD` or `getpass.getpass`, start one client, and stop it in `finally`.

For each user turn, call `route_intent()` once and pass it to `handle_sensor_turn()`. The helper calls `build_sensor_answer()` and, when handled, prints the result and calls `make_sam_wav()`. Return to the prompt without building an LLM request. Otherwise pass the same route into `build_system_prompt()` and preserve the current behavior.

- [ ] **Step 4: Update dependency and operator documentation**

Change README setup to `python -m pip install -r requirements.txt`; list RapidFuzz and Paho's purposes; document the hidden `artemis` password flow, supported questions, Fahrenheit default and explicit Celsius behavior, 180-second freshness window, broker-unavailable behavior, and these verification commands:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest discover -s tests -p 'test_*.py' -v
bash tests/test_setup_mosquitto.sh
python3 Python_Scripts/load_llm_sam.py --router-test
```

- [ ] **Step 5: Run the complete local verification**

Run all three commands from Step 4, then `git diff --check`.

Expected: every unit and shell test passes, router cases all report `PASS`, and the diff check prints nothing.

- [ ] **Step 6: Commit controller integration and docs**

```bash
git add Python_Scripts/load_llm_sam.py tests/test_sensor_controller.py README.md
git commit -m "Integrate MQTT readings into Artemis"
```

- [ ] **Step 7: Verify on the Raspberry Pi**

After pushing `project-testing`, on the Pi run:

```bash
cd ~/Local_LM_testing
git pull --ff-only origin project-testing
source .venv/bin/activate
python -m pip install -r requirements.txt
python Python_Scripts/load_llm_sam.py
```

At the hidden prompt, enter the existing `artemis` MQTT password. Ask `What is the living room temperature?`, `What is the humidity?`, and `How are conditions in the living room?`. Confirm the answer uses the retained MQTT sample, sensor questions produce no llama-server timing, and a normal non-sensor prompt still follows the existing LLM path.
