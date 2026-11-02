# Artemis Local LLM Voice Assistant

![Status](https://img.shields.io/badge/status-prototype-orange)
![Platform](https://img.shields.io/badge/platform-Raspberry%20Pi%205-red)
![Model](https://img.shields.io/badge/model-Qwen3.5%202B-green)
![TTS](https://img.shields.io/badge/TTS-SAM-lightgrey)

Artemis is an offline-first voice assistant prototype built around a local large language model, local knowledge files, and retro SAM text-to-speech. The current target is a Raspberry Pi 5 with 16 GB of RAM running Qwen3.5 2B through `llama.cpp`.

Artemis now uses a calm Home Helper identity focused on local household
information. It routes each prompt by intent and topic, loads only the relevant
local knowledge, keeps the prompt within a fixed token budget, requests a
response from the local model, and renders the result to a WAV file through
SAM.

## Current capabilities

- OpenAI-compatible local inference through `llama-server`
- Weighted intent, topic, and severity routing with fuzzy matching
- Selective loading of local knowledge instead of injecting every file
- Prompt and response token budgeting for Raspberry Pi constraints
- JSON-based identity and mode configuration
- Retro speech output through SAM
- Debug output for routing, prompt size, model timing, and token usage
- A lightweight router test that does not call the model or SAM
- Read-only MQTT temperature and humidity answers narrated from validated facts by the local LLM

## How it works

```mermaid
flowchart LR
    A[User input] --> B[Python controller]
    B --> C[Intent and topic router]
    C --> D[Token budget and selected knowledge]
    D --> E[llama-server]
    E --> F[Artemis response]
    F --> G[SAM text-to-speech]
    G --> H[WAV audio output]
```

The active request path is:

1. `load_llm_sam.py` loads the Artemis identity and active mode configuration.
2. `intent_router.py` scores the user's intent, topics, and urgency.
3. `token_budget.py` selects and trims relevant files from `memory/knowledge/`.
4. The controller sends the assembled prompt to the local `llama-server` endpoint.
5. The response is converted to a WAV file by SAM.

Sensor questions take a narrower branch: Artemis resolves a validated MQTT-backed answer plan, gives only those formatted facts to Qwen, validates the returned sentence, and then sends it to SAM. Invalid or unavailable model output uses the deterministic factual answer instead.

Inputs that receive no intent or topic score are logged to `unrecognized_inputs.txt` for later router tuning. They do not call the LLM.

## Project structure

```text
Python_Scripts/
  load_llm_sam.py    Main terminal application and prompt pipeline
  intent_router.py   Intent, topic, severity, and knowledge-file routing
  token_budget.py    Context and response token limits
memory/
  identity.json      Artemis identity and voice settings
  modes/             Mode definitions
  knowledge/         Local household capabilities, sensor guidance, and safety boundaries
Archive/             Older experiments and tests kept for reference
```

## Requirements

- Python 3.9 or newer
- [`rapidfuzz`](https://github.com/rapidfuzz/RapidFuzz)
- [`paho-mqtt`](https://github.com/eclipse-paho/paho.mqtt.python)
- A local [`llama.cpp`](https://github.com/ggml-org/llama.cpp) build containing `llama-server`
- A Qwen3.5 2B GGUF, currently using the `Q4_K_M` quantization
- [SAM: Software Automatic Mouth](https://github.com/s-macke/SAM)

The current hardware target is a Raspberry Pi 5 with 16 GB of RAM. Development and router testing can be done elsewhere, but the default SAM paths are Pi-specific.

## Setup

Clone the repository and install the Python dependency:

```bash
git clone https://github.com/Ace0I0/Local_LM_testing.git
cd Local_LM_testing
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Place `Qwen3.5-2B-Q4_K_M.gguf` under `~/models/qwen/`, then start the local server with thinking disabled:

```bash
~/llama.cpp/build-current/bin/llama-server \
  -m ~/models/qwen/Qwen3.5-2B-Q4_K_M.gguf \
  --host 127.0.0.1 \
  --port 8080 \
  -c 8192 \
  --jinja \
  --chat-template-kwargs '{"enable_thinking":false}'
```

Build SAM separately and confirm these constants in `Python_Scripts/load_llm_sam.py` match your installation:

```python
LLAMA_SERVER_URL = "http://127.0.0.1:8080/v1/chat/completions"
SAM_BINARY = Path("/home/pi/SAM/sam")
OUTPUT_WAV = Path("/home/pi/SAM/robot_response.wav")
```

Run Artemis from the repository root:

```bash
python Python_Scripts/load_llm_sam.py
```

## Start llama-server at boot

On the Raspberry Pi, run this installer once from the repository root:

```bash
bash scripts/setup_llama_server.sh
```

It asks for the Pi user, the existing `llama-server` path, and the existing
Qwen GGUF path, then installs and enables `artemis-llama.service`. It asks
for `sudo` once. The service remains bound to `127.0.0.1:8080`, so it is
not exposed to the LAN or Tailscale.

Check it after a reboot with:

```bash
sudo systemctl status artemis-llama.service
sudo journalctl -u artemis-llama.service -n 50 --no-pager
```

## Compare local models

The GGUF file and llama-server both run locally. Artemis talks to the
loopback HTTP endpoint; it does not send prompts to an internet service.
Benchmark one model at a time so the models do not compete for CPU or RAM.

Start llama-server with a model, then record its run:

    python scripts/benchmark_llms.py run --label qwen2.5-1.5b

Stop the server, restart it with the next GGUF, and repeat with
--label qwen3.5-2b and --label qwen3.5-4b. Each run uses the same
18 prompts, one warm-up, and three measured repetitions by default.
If the server is elsewhere, pass its full chat-completions URL:

    python scripts/benchmark_llms.py run \
      --label qwen3.5-2b \
      --url http://SERVER_ADDRESS:8080/v1/chat/completions

Compare the three timestamped JSON results:

    python scripts/benchmark_llms.py compare \
      benchmark-results/qwen2.5-1.5b-*.json \
      benchmark-results/qwen3.5-2b-*.json \
      benchmark-results/qwen3.5-4b-*.json

The Markdown report shows errors, automated response checks, wall time,
token usage, llama.cpp prompt and generation TPS when supplied by the
server, calculated end-to-end output TPS, and every raw answer. Generated
results remain under the ignored benchmark-results directory.

## MQTT broker setup

The first MQTT slice assumes the broker is running on the target Raspberry Pi: ARM64 (`aarch64`), Debian 13, and a trusted local network. From an interactive SSH session on the Pi, update this branch and run the setup wizard from the repository root:

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

### Manage accounts and add ESP32 sensors

Mosquitto keeps authentication and authorization separate. An account needs both a password-file entry and a matching ACL section. Run password commands interactively so secrets are not stored in shell history.

To add an account or change an existing account's password, run:

```bash
sudo mosquitto_passwd /etc/mosquitto/artemis.passwd ACCOUNT_NAME
sudo systemctl restart mosquitto
sudo systemctl --no-pager --full status mosquitto
```

Do not add `-c`: it would replace the existing password file. Changing a password disconnects the device until its saved MQTT password is updated.

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

#### Add an ESP32 sensor

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

Configure the ESP32 from the repository root:

```bash
cp esp32/include/secrets.example.h esp32/include/secrets.h
```

Edit `esp32/include/secrets.h` with the Wi-Fi credentials, broker IP address, `esp32_game_room` username, and the password just created. This file is ignored by Git and must not be committed.

The example firmware in `esp32/src/main.cpp` currently identifies itself as `game_room`. For another location, replace every `game_room`, `Game Room`, and `artemis-game-room` value with that device's unique location, display name, and client ID. Also change `DHTPIN` if the sensor uses a different GPIO. The state, availability, Home Assistant discovery, and ACL topics must all use the same location.

The `homeassistant` and `artemis` accounts created by the wizard already subscribe with a `+` location wildcard, so they can read additional locations without new ACL entries.

#### What the setup wizard does differently

`scripts/setup_mosquitto.sh` is an opinionated first-device setup, not a device-registration tool:

- It creates the fixed sensor username `esphome_living_room`.
- It grants that account access only to `living_room` topics and tests only that location.
- It does not create `esp32/include/secrets.h`, change the firmware's topics, or flash an ESP32.
- It preserves unrelated entries in `artemis.passwd`, but replaces `artemis.acl` with its four managed accounts every time it runs.
- The checked-in ESP32 firmware uses `game_room`, so it will not work with the wizard's `esphome_living_room` ACL until the firmware is changed to `living_room` or a matching `game_room` account and ACL are added as shown above.

If custom devices must survive future wizard runs, either reapply their ACL sections afterward or add their usernames and ACL rules to `scripts/setup_mosquitto.sh` before rerunning it.

Choose and save a different password for each account. `mosquitto_passwd` asks twice when creating a missing account, and the verification stage asks once more for each password. Input is hidden. Existing account hashes and unrelated users are preserved on reruns; a successful run ends with `Setup complete`.

The verification publishes retained QoS 1 sample values for `living_room` (`21.5` °C, `45.0`% humidity, and `online`), checks each permitted consumer, rejects cross-location and write attempts, restarts Mosquitto to prove retention, and repeats the test-account check over the Pi's LAN address.

## Artemis sensor questions

Artemis uses Paho MQTT to subscribe in the background with the read-only `artemis` account. Run the application normally and enter that account's MQTT password at the hidden prompt:

```bash
python Python_Scripts/load_llm_sam.py
```

For unattended startup, `ARTEMIS_MQTT_PASSWORD` may be supplied through the process environment. Never commit it or place it directly in a shell command. RapidFuzz handles question routing; Paho maintains the MQTT 5 connection and automatically reconnects when the local broker returns.

Initial supported questions include:

- `What is the living room temperature?`
- `What is the living room temperature in Celsius?`
- `What is the humidity?`
- `How are conditions in the living room?`

How to start up our Qwen3.5-2B LLM

```bash
 /home/pi/llama.cpp/build-current/bin/llama-server   -m /home/pi/models/qwen/Qwen3.5-2B-Q4_K_M.gguf   --host 127.0.0.1   --port 8080   -c 8192   --jinja   --chat-template-kwargs '{"enable_thinking":false}'
```

MQTT measurements remain Celsius internally. Artemis presents Fahrenheit by default and uses Celsius when requested explicitly. A measurement becomes unavailable after 180 seconds without an update. General condition reports omit unavailable measurements; a direct question says only that no current reading is available. Broker downtime does not stop non-sensor questions.

Every routed sensor question is offered to the local Qwen model for one-sentence phrasing. The model receives only the resolved location, requested measurement, formatted value and unit, or availability fact. Artemis rejects changed values or units, extra numbers, swapped measurements, interpretations, warnings, advice, Markdown, and extra sentences. Rejected output, malformed responses, connection errors, or the 60-second sensor timeout use the existing deterministic answer and keep Artemis running.

The setup wizard's retained sample is accepted when Artemis starts, but it becomes unavailable after 180 seconds because it is not a live sensor. The future ESPHome node will refresh it every 60 seconds.

Run the local checks with:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Python_Scripts python3 -m unittest discover -s tests -p 'test_*.py' -v
bash tests/test_setup_mosquitto.sh
python3 Python_Scripts/load_llm_sam.py --router-test
```

## Router test

The current controller includes a small routing check that does not require a running model server or SAM installation:

```bash
python Python_Scripts/load_llm_sam.py --router-test
```

## Current status and limitations

- Home Helper is the single active mode; mode switching is not implemented.
- Microphone input, wake-word detection, and physical robot controls are not implemented.
- SAM and output paths are currently hardcoded for `/home/pi/SAM/`.
- The files under `Archive/` are historical references, not the active test suite.

## Near-term direction

Artemis is moving toward a local, read-only smart-home helper. The first milestone will use MQTT and Mosquitto to observe basic sensors, with Home Assistant as the primary dashboard. Artemis, the broker, and Home Assistant will initially share one Raspberry Pi 5.

The ongoing questions and confirmed decisions are recorded in [`docs/project-direction-interview.md`](docs/project-direction-interview.md).

## Credits

- [`llama.cpp`](https://github.com/ggml-org/llama.cpp) for local LLM inference
- [`Qwen2.5`](https://huggingface.co/Qwen/Qwen2.5-1.5B) for the language model
- [`SAM`](https://github.com/s-macke/SAM) for retro text-to-speech
- Raspberry Pi Foundation for the target hardware platform
