---
type: "query"
date: "2026-10-28T18:52:03.982755+00:00"
question: "I can handle SSHing into the Pi; tell me what to do there."
contributor: "graphify"
outcome: "useful"
source_nodes: ["Mosquitto Setup Wizard", "MqttSensorClient", "Artemis Local LLM Voice Assistant", "Broker Acceptance Checks"]
---

# Q: I can handle SSHing into the Pi; tell me what to do there.

## Answer

Expanded from graph vocabulary: [artemis, mosquitto, mqtt, broker, setup, sensor, password, sam, server, test]. First run a read-only Pi audit: identity and architecture, repository branch/status/commit, Mosquitto active/enabled status, listeners on ports 1883 and 8080, SAM binary at the hardcoded path, llama-server binary, GGUF model files, virtual environment, and imports for rapidfuzz and paho-mqtt. Paste the output before running git pull, the Mosquitto setup wizard, dependency installation, or entering credentials. This prevents overwriting local Pi work and determines the smallest next command set.

## Outcome

- Signal: useful

## Source Nodes

- Mosquitto Setup Wizard
- MqttSensorClient
- Artemis Local LLM Voice Assistant
- Broker Acceptance Checks