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

## Documentation

See the [documentation index](docs/README.md) for detailed guides. The setup and common commands below are the starting point.

## Components

| Component | Role |
| --- | --- |
| ESP32 + DHT22/AM2302 | Measures temperature and humidity; publishes readings over Wi-Fi |
| [Mosquitto](https://mosquitto.org/) / MQTT | Broker and messaging protocol connecting sensors and consumers |
| [Home Assistant](https://www.home-assistant.io/) | Dashboard for sensor readings, using MQTT discovery |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) + Qwen3.5 2B | Local language model for household answers and sensor phrasing |
| [SAM](https://github.com/s-macke/SAM) | Converts responses to WAV speech |
| RapidFuzz / Paho MQTT | Python routing and MQTT client libraries |

Artemis and Home Assistant read sensor data independently from the broker. Home Assistant is not required in Artemis's request path. The current ESP32 example uses Arduino/PlatformIO firmware.

General questions use local knowledge selected by intent and topic. Sensor questions use validated MQTT readings, with model phrasing checked against those facts and a deterministic fallback. Inputs with no matching intent or topic are logged to `unrecognized_inputs.txt` without calling the model.

## Requirements

- Python 3.9 or newer
- [`rapidfuzz`](https://github.com/rapidfuzz/RapidFuzz)
- [`paho-mqtt`](https://github.com/eclipse-paho/paho.mqtt.python)
- A local [`llama.cpp`](https://github.com/ggml-org/llama.cpp) build containing `llama-server`
- A Qwen3.5 2B GGUF, currently using the `Q4_K_M` quantization
- [SAM: Software Automatic Mouth](https://github.com/s-macke/SAM)

The current hardware target is a Raspberry Pi 5 with 16 GB of RAM. Development and router testing can be done elsewhere, but the default SAM paths are Pi-specific.

## Setup

Clone the repository and install the Python dependencies:

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

Artemis asks for the `artemis` MQTT account password at a hidden prompt. Set up the broker below before using sensor readings. For unattended startup, the application also accepts `ARTEMIS_MQTT_PASSWORD` in its process environment; keep it out of Git and shell history.

To start the model automatically at boot:

```bash
bash scripts/setup_llama_server.sh
```

The installer requires an existing model and server binary. See the [llama-server guide](docs/guides/llama-server.md) for service details and diagnostic commands.

## MQTT and Home Assistant

On the target Pi (Debian 13, ARM64), run the broker wizard from an interactive SSH session. It requires passwordless sudo:

```bash
bash scripts/setup_mosquitto.sh
```

The wizard creates `artemis_test`, `esphome_living_room`, `homeassistant`, and the read-only `artemis` account. It configures port 1883 for a trusted LAN without TLS. Keep the broker private to that network.

The wizard replaces its ACL file on reruns. Its sensor account permits `living_room`, while the ESP32 example uses `game_room`; follow the [ESP32 guide](docs/guides/esp32-sensors.md) to align credentials and topics.

For an existing Home Assistant installation, configure its MQTT integration with the Pi's broker address, port 1883, and the `homeassistant` account. Firmware publishes discovery messages under `homeassistant/#`; confirm the sensor entities appear after the device connects. See the [official MQTT integration instructions](https://www.home-assistant.io/integrations/mqtt/) for the UI steps.

### Add an account or change a password

On the broker Pi, replace `ACCOUNT_NAME` with the intended username:

```bash
sudo mosquitto_passwd /etc/mosquitto/artemis.passwd ACCOUNT_NAME
sudo systemctl restart mosquitto
```

Enter the password twice. Update the client's saved password afterward. Do not use `-c` with an existing password file: it overwrites the file.

New accounts also need permissions in `/etc/mosquitto/artemis.acl`. See the [broker guide](docs/guides/mqtt-broker.md) for ACL examples and managed-account settings.

### Change an account's username

Create the new account with the command above. Add its ACL section, restart the broker, and update the client with the new username and password. Once it reconnects successfully, remove the old ACL section and old account:

```bash
sudo mosquitto_passwd -D /etc/mosquitto/artemis.passwd OLD_ACCOUNT_NAME
sudo systemctl restart mosquitto
```

The [broker guide](docs/guides/mqtt-broker.md#manage-accounts) lists which firmware, application, and wizard settings must change with a managed username.

## Use and check Artemis

Run from the repository root with the virtual environment activated:

```bash
python Python_Scripts/load_llm_sam.py
```

Try `What is the game room temperature?` using your sensor's actual location, or `What is the humidity?` when only one location is known. Readings use Fahrenheit by default; ask explicitly for Celsius to change presentation. Measurements become unavailable after 180 seconds without an update. See [sensor behavior and checks](docs/guides/sensor-questions.md).

For multiple sensors, try `Give me a house summary`, `Compare the bedroom and game room temperature`, or `Which room is warmest?`. Artemis computes comparisons from current readings and asks the LLM to phrase the verified facts. See [multi-room questions](docs/guides/sensor-questions.md#multiple-rooms).

Run the router check without the model or SAM:

```bash
python Python_Scripts/load_llm_sam.py --router-test
```

For performance comparisons, follow the [model benchmark guide](docs/guides/model-benchmarks.md).

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

## Current status and limitations

- Home Helper is the single active mode; mode switching is not implemented.
- Microphone input, wake-word detection, and physical robot controls are not implemented.
- SAM and output paths are currently hardcoded for `/home/pi/SAM/`.
- The files under `Archive/` are historical references, not the active test suite.

## Project direction

Artemis is developing into a local, read-only household helper, with Home Assistant as the sensor dashboard. See the [project direction interview](docs/project-direction-interview.md) for the original decisions and open questions. Dated plans and specifications are linked from the [documentation index](docs/README.md#project-history).

## Credits

- [`llama.cpp`](https://github.com/ggml-org/llama.cpp) for local LLM inference
- [`Qwen3.5`](https://huggingface.co/Qwen/Qwen3.5-2B) for the language model
- [`SAM`](https://github.com/s-macke/SAM) for retro text-to-speech
- Raspberry Pi Foundation for the target hardware platform
